import streamlit as st
import sys
import re
sys.stdout.reconfigure(encoding="utf-8")
from llm_interface import call_live_gemini_api, call_with_tools, get_mock_response
from sandbox import execute_python_code
from mcp_manager import initialize_mcp_sync, get_all_tools_sync, call_tool_sync
from guardrails import run_guardrails, get_penalty_prompt, contains_toxic_input, detect_language_directive
from pathlib import Path
import pandas as pd
import json
from config import config
import datetime
from router import determine_agent_chain


def get_workspace_snapshot() -> str:
    """Scan workspace/ for CSV files and return a text summary."""
    ws = Path("workspace")
    if not ws.exists():
        return "**Workspace**: empty (no workspace directory)."

    csv_files = sorted(ws.glob("*.csv"))
    if not csv_files:
        return "**Workspace**: no CSV files found."

    lines = []
    for fpath in csv_files:
        try:
            df = pd.read_csv(fpath)
            cols = ", ".join(df.columns.astype(str))
            lines.append(
                f"  - **{fpath.name}**: {len(df)} rows, {len(df.columns)} columns "
                f"({cols})"
            )
        except Exception as e:
            lines.append(f"  - **{fpath.name}**: (read error — {e})")

    snapshot = "**Available workspace data:**\n" + "\n".join(lines)
    return snapshot


# ── Callback (guaranteed to run BEFORE page rerun on button click) ─────────

def select_file_callback(file_name):
    """Guaranteed to run BEFORE the page reruns on button click."""
    st.session_state.active_file_path = file_name

    # Pass the command to Robert under the hood,
    # but DO NOT append it to the visible chat history.
    st.session_state.pending_prompt = f"Выведи форму таблицы {file_name}, Роберт"


# ── System Prompts ─────────────────────────────────────────────────────────

_LANG_RULE = (
    "[LANGUAGE CODE OF CONDUCT] Language of response: English only. "
    "You must respond EXCLUSIVELY in English, regardless of the user's language. "
    "Never use Russian, even if the user writes in Russian. "
    "Maintain your character persona seamlessly in English."
)

ELENA_SYSTEM_PROMPT = (
    f"{_LANG_RULE} "
    "You are Elena, a senior data science mentor. "
    "[GUARDRAIL: You are forbidden from giving ready-made code solutions like "
    "df[...] or pd.read_csv(). Instead, explain the logic conceptually. "
    "Use metaphors (e.g., 'mask', 'filter') and ask guiding questions "
    "to make the user write the code themselves.]"
    " [MCP TOOLS AVAILABLE: You have access to documentation search tools. "
    "Use 'search_docs(library=, query=)' to find official docs for Python/DS libraries. "
    "Use 'fetch_url(url=)' to read content from any webpage. "
    "These tools help you verify facts and provide accurate guidance.]"
    "[CRITICAL CONVERSATION FLOW RULES] "
    "NEVER introduce yourself or state your role after the very first message of the conversation. "
    "DO NOT use repetitive greetings "
    "if this is a follow-up question or an ongoing discussion. "
    "If the user is continuing a topic or replying to your previous point, "
    "skip the pleasantries entirely. Dive IMMEDIATELY into the context, "
    "answer the question, or provide the guidance directly. "
    "Keep the dialogue fluid, natural, and continuous, like a real-time chat with a colleague."
)

CHAD_SYSTEM_PROMPT = (
    f"{_LANG_RULE} "
    "You are Chad, a vibe coder junior data scientist. "
    "Your tone is hyperactive, overconfident, and casual. "
    "You suggest quick, often destructive solutions. "
    "When you mention destructive operations (e.g., inplace=True), "
    "Elena will be notified to warn the user."
    " [MCP TOOLS AVAILABLE: You can use 'search_docs(library=, query=)' "
    "to look up documentation, 'fetch_url(url=)' to read web pages, "
    "and 'fetch(url=)' to fetch web content. Use these to find quick solutions.]"
    "[CRITICAL CONVERSATION FLOW RULES] "
    "NEVER introduce yourself or state your role after the very first message of the conversation. "
    "DO NOT use repetitive greetings. "
    "If the user is continuing a topic or replying to your previous point, "
    "skip pleasantries entirely. Dive IMMEDIATELY into the solution."
)

ROBERT_SYSTEM_PROMPT = (
    f"{_LANG_RULE} "
    "You are Robert, an MLOps engineer. "
    "Your core job is to generate clean, executable Python code when the user asks you to perform a data task. "
    "You MUST always respond with a Python code block (```python ... ```) containing the exact code needed. "
    "Do NOT simulate execution or say 'I would run this code'. "
    "Actually produce the ```python block with working code. "
    "When checking data shape, output code like:\n"
    "```python\nimport pandas as pd\ndf = pd.read_csv('workspace/FILE_NAME.csv')\nprint(df.shape)\n```\n"
    "Replace FILE_NAME with the actual active filename from the directive below.\n"
    "Focus on correctness, performance, and reproducibility."
    " [MCP TOOLS AVAILABLE: You have access to 'search_docs(library=, query=)' "
    "to look up official Python/DS library documentation, and 'fetch_url(url=)' "
    "to read content from any webpage. Use these to verify API signatures and best practices.]"
    "[CRITICAL CONVERSATION FLOW RULES] "
    "NEVER introduce yourself or state your role after the very first message of the conversation. "
    "DO NOT use repetitive greetings. "
    "If the user is continuing a topic or replying to your previous point, "
    "skip pleasantries entirely. Focus on correctness and results."
)

GEOFFREY_SYSTEM_PROMPT = (
    f"{_LANG_RULE} "
    "You are Geoffrey — the Godfather of Deep Learning. "
    "You are an absolute expert in Neural Networks, Transformers, PyTorch, "
    "Computer Vision, NLP, and advanced ML optimization "
    "(Kaggle-tier ensembles, loss functions, hyperparameter tuning, etc.). "
    "Your tone is wise, slightly academic, but highly pragmatic. "
    "You explain WHY things work mathematically or architecturally, "
    "rather than just giving code. "
    "Focus on state-of-the-art solutions and deep structural understanding."
    "[CRITICAL CONVERSATION FLOW RULES] "
    "NEVER introduce yourself or state your role after the very first message of the conversation. "
    "DO NOT use repetitive greetings. "
    "If the user is continuing a topic or replying to your previous point, "
    "skip pleasantries entirely. Provide deep technical insight directly."
)

_THEMES = {
    # ═══════════════════════════════════════════════════════════════════════
    # 1. DARK TECH  (Tokyo Night / Material Deep Ocean)
    # ═══════════════════════════════════════════════════════════════════════
    "dark-tech": {
        "name": "Dark Tech",
        "css": """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            .stApp {
                background-color: #0f111a;
                color: #bfc7d5;
                font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            }
            .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
                color: #e2e6f0;
                font-weight: 600;
                letter-spacing: -0.01em;
            }
            .stApp a { color: #82aaff; text-decoration: none; }
            .stApp a:hover { color: #a6c1ff; text-decoration: underline; }
            .stApp hr { border-color: #1e2030; margin: 16px 0; }
            [data-testid="stSidebar"] { background-color: #090a0f; border-right: 1px solid #1a1c25; }
            [data-testid="stSidebar"] .stMarkdown { color: #a6accd; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #0b0d14;
                border: 1px solid #1e2030;
                border-radius: 8px;
                margin-bottom: 8px;
                transition: border-color 0.2s ease;
            }
            [data-testid="stSidebar"] .st-expander:hover { border-color: #2a2d3a; }
            [data-testid="stSidebar"] .st-expander-header { color: #bfc7d5; font-weight: 600; font-size: 13px; }
            [data-testid="stSidebar"] .stCaption { color: #79809c; font-size: 12px; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
            .stButton button {
                background-color: #171924 !important;
                color: #bfc7d5 !important;
                border: 1px solid #232635 !important;
                border-radius: 6px !important;
                font-family: inherit !important;
                font-size: 13px !important;
                transition: all 0.3s ease !important;
            }
            .stButton button:hover {
                background-color: #1e2030 !important;
                border-color: #82aaff !important;
                color: #e2e6f0 !important;
                box-shadow: 0 0 12px rgba(130, 170, 255, 0.15) !important;
            }
            .stButton button:active { transform: scale(0.98); }
            .terminal-container {
                background-color: #050608;
                border-left: 3px solid #ff9e3b;
                border-radius: 6px;
                padding: 10px 12px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.5;
                color: #a6accd;
                max-height: 300px;
                overflow-y: auto;
            }
            .terminal-line { border-bottom: 1px solid #0d0e16; padding: 3px 0; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content, .elena-content, .chad-content, .robert-content, .geoffrey-content { border: 1px solid #232635; border-radius: 8px; transition: border-color 0.2s ease; }
            .user-content:hover, .elena-content:hover, .chad-content:hover, .robert-content:hover, .geoffrey-content:hover { border-color: #2a2d3a; }
            .user-content { background-color: #212433; padding: 12px 16px; color: #bfc7d5; font-size: 16px; margin: 4px 0; }
            .elena-content {
                background-color: #171924;
                border-left: 4px solid #82aaff;
                padding: 14px 18px;
                color: #c8d0e0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .elena-content strong { color: #a6c1ff; }
            .chad-content {
                background-color: #171924;
                border-left: 4px solid #ff9e3b;
                padding: 14px 18px;
                color: #c8d0e0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .chad-content strong { color: #ff9e3b; }
            .robert-content {
                background-color: #171924;
                border-left: 4px solid #ffcb6b;
                padding: 14px 18px;
                color: #c8d0e0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
            }
            .robert-content strong { color: #ffcb6b; }
            .geoffrey-content {
                background-color: #171924;
                border-left: 4px solid #ffd700;
                padding: 14px 18px;
                color: #c8d0e0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .geoffrey-content strong { color: #ffd700; }
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #050608;
                border: 1px solid #1e2030;
                border-radius: 6px;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
                font-size: 12px;
                color: #a6accd;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
            }
            .welcome-title { color: #e2e6f0; font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 16px; }
            .welcome-agents { color: #a6accd; font-size: 15px; line-height: 1.8; }
            [data-testid="stChatInput"] {
                background-color: #171924;
                border: 1px solid #232635;
                border-radius: 8px;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }
            [data-testid="stChatInput"]:focus-within {
                border-color: #82aaff;
                box-shadow: 0 0 0 2px rgba(130, 170, 255, 0.15);
            }
            [data-testid="stChatInput"] input { color: #bfc7d5; font-family: inherit; }
            [data-testid="stChatInput"] input::placeholder { color: #5a607a; }
            [data-testid="stFileUploader"] { background-color: #0b0d14; border: 1px dashed #1e2030; border-radius: 6px; padding: 8px; }
            [data-testid="stFileUploader"]:hover { border-color: #82aaff; }
            [data-testid="stSelectbox"] label {
                color: #bfc7d5;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 15px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            [data-baseweb="popover"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #0f111a; }
            ::-webkit-scrollbar-thumb { background: #212433; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #2a2d3a; }
        </style>
        """,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # 2. LIGHT PAPER  (GitHub UI / Notion)
    # ═══════════════════════════════════════════════════════════════════════
    "light-paper": {
        "name": "Light Paper",
        "css": """
        <style>
            .stApp {
                background-color: #f6f8fa;
                color: #24292f;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
            }
            .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #1f2328; font-weight: 600; }
            .stApp a { color: #0366d6; text-decoration: none; }
            .stApp a:hover { text-decoration: underline; }
            .stApp hr { border-color: #d0d7de; margin: 16px 0; }
            [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #d0d7de; }
            [data-testid="stSidebar"] * { color: #1f2328 !important; }
            [data-testid="stSidebar"] .stMarkdown { color: #1f2328; font-size: 14px; font-weight: 400; line-height: 1.5; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-bottom: 8px;
            }
            [data-testid="stSidebar"] .st-expander-header { color: #1f2328 !important; font-weight: 600; font-size: 14px; }
            [data-testid="stSidebar"] .stCaption { color: #1f2328 !important; font-size: 13px; font-weight: 500; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
            [data-testid="stSidebar"] .stSelectbox label,
            [data-testid="stSidebar"] label { color: #1f2328 !important; font-weight: 500; }
            [data-testid="stSidebar"] [data-baseweb="select"] {
                background-color: #ffffff !important;
                color: #1f2328 !important;
                border-color: #d0d7de !important;
            }
            .stButton button {
                background-color: #f6f8fa !important;
                color: #24292f !important;
                border: 1px solid #d0d7de !important;
                border-radius: 6px !important;
                font-family: inherit !important;
                font-size: 13px !important;
                transition: all 0.2s ease !important;
            }
            .stButton button:hover {
                background-color: #eaeef2 !important;
                border-color: #0366d6 !important;
            }
            .terminal-container {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-left: 3px solid #f66a0a;
                border-radius: 6px;
                padding: 10px 12px;
                font-family: 'SFMono-Regular', 'Menlo', monospace;
                font-size: 11px;
                line-height: 1.5;
                color: #24292f;
                max-height: 300px;
                overflow-y: auto;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            .terminal-line { border-bottom: 1px solid #e8eaed; padding: 3px 0; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content, .elena-content, .chad-content, .robert-content, .geoffrey-content { border-radius: 6px; }
            .user-content {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                padding: 12px 16px;
                color: #24292f;
                font-size: 16px;
                margin: 4px 0;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            .elena-content {
                background-color: #ffffff;
                border-left: 4px solid #0366d6;
                border-top: 1px solid #d0d7de;
                border-right: 1px solid #d0d7de;
                border-bottom: 1px solid #d0d7de;
                padding: 14px 18px;
                color: #24292f;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .elena-content strong { color: #0366d6; }
            .chad-content {
                background-color: #ffffff;
                border-left: 4px solid #d15704;
                border-top: 1px solid #d0d7de;
                border-right: 1px solid #d0d7de;
                border-bottom: 1px solid #d0d7de;
                padding: 14px 18px;
                color: #24292f;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .chad-content strong { color: #d15704; }
            .robert-content {
                background-color: #ffffff;
                border-left: 4px solid #f66a0a;
                border-top: 1px solid #d0d7de;
                border-right: 1px solid #d0d7de;
                border-bottom: 1px solid #d0d7de;
                padding: 14px 18px;
                color: #24292f;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                font-family: 'SFMono-Regular', 'Menlo', monospace;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .robert-content strong { color: #f66a0a; }
            .geoffrey-content {
                background-color: #ffffff;
                border-left: 4px solid #d4a017;
                border-top: 1px solid #d0d7de;
                border-right: 1px solid #d0d7de;
                border-bottom: 1px solid #d0d7de;
                padding: 14px 18px;
                color: #24292f;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .geoffrey-content strong { color: #d4a017; }
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 12px;
                font-family: 'SFMono-Regular', 'Menlo', monospace;
                font-size: 12px;
                color: #24292f;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            .welcome-title { color: #1f2328; font-size: 28px; font-weight: 700; margin-bottom: 16px; }
            .welcome-agents { color: #656d76; font-size: 15px; line-height: 1.8; }
            [data-testid="stChatInput"] {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
            }
            [data-testid="stChatInput"]:focus-within {
                border-color: #0366d6;
                box-shadow: 0 0 0 2px rgba(3, 102, 214, 0.15);
            }
            [data-testid="stChatInput"] input { color: #24292f !important; font-family: inherit; background-color: #ffffff !important; }
            [data-testid="stChatInput"] input::placeholder { color: #656d76; }
            [data-testid="stFileUploader"] { background-color: #f6f8fa; border: 1px dashed #d0d7de; border-radius: 6px; padding: 8px; }
            [data-testid="stFileUploader"]:hover { border-color: #0366d6; }
            [data-testid="stSelectbox"] label {
                color: #24292f;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 15px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            [data-baseweb="popover"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #f6f8fa; }
            ::-webkit-scrollbar-thumb { background: #d0d7de; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #afb8c1; }
        </style>
        """,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # 3. CYBERPUNK NEON
    # ═══════════════════════════════════════════════════════════════════════
    "cyberpunk": {
        "name": "Cyberpunk Neon",
        "css": """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
            .stApp {
                background-color: #08010f;
                color: #c0b0e0;
                font-family: 'Orbitron', 'Courier New', monospace;
            }
            .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
                color: #ffffff;
                text-shadow: 0 0 5px #00f0ff, 0 0 10px #00f0ff;
                font-weight: 700;
            }
            .stApp a { color: #00f0ff; text-decoration: none; text-shadow: 0 0 4px #00f0ff; }
            .stApp a:hover { color: #ff007f; text-shadow: 0 0 8px #ff007f; }
            .stApp hr { border-color: #1a0a2e; margin: 16px 0; }
            [data-testid="stSidebar"] { background-color: #000000; border-right: 1px solid #1a0a2e; }
            [data-testid="stSidebar"] .stMarkdown { color: #c0b0e0; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #0a0018;
                border: 1px solid #1a0a2e;
                border-radius: 4px;
                margin-bottom: 8px;
            }
            [data-testid="stSidebar"] .st-expander-header { color: #ffffff; font-weight: 700; font-size: 12px; text-shadow: 0 0 3px #00f0ff; }
            [data-testid="stSidebar"] .stCaption { color: #7a6a9a; font-size: 12px; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
            .stButton button {
                background-color: #0a0018 !important;
                color: #00f0ff !important;
                border: 1px solid #ff007f !important;
                border-radius: 4px !important;
                font-family: 'Orbitron', monospace !important;
                font-size: 11px !important;
                text-transform: uppercase !important;
                letter-spacing: 2px !important;
                transition: all 0.3s ease !important;
            }
            .stButton button:hover {
                background: linear-gradient(45deg, #ff007f, #00f0ff) !important;
                color: #000000 !important;
                border-color: #ffffff !important;
                box-shadow: 0 0 20px rgba(255, 0, 127, 0.4) !important;
            }
            .terminal-container {
                background-color: #000000;
                border-left: 3px solid #ff007f;
                border-radius: 4px;
                padding: 10px 12px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.5;
                color: #00f0ff;
                max-height: 300px;
                overflow-y: auto;
                box-shadow: inset 0 0 10px rgba(0, 240, 255, 0.05);
            }
            .terminal-line { border-bottom: 1px solid #0a0020; padding: 3px 0; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content {
                background-color: #0a0018;
                border: 1px solid #1a0a2e;
                border-radius: 4px;
                padding: 12px 16px;
                color: #c0b0e0;
                font-size: 16px;
                margin: 4px 0;
            }
            .elena-content {
                background-color: #0a0018;
                border: 1px solid #00f0ff;
                border-left: 4px solid #00f0ff;
                border-radius: 4px;
                padding: 14px 18px;
                color: #c0f0ff;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 12px rgba(0, 240, 255, 0.15);
            }
            .elena-content strong { color: #00f0ff; text-shadow: 0 0 4px #00f0ff; }
            .chad-content {
                background-color: #0a0018;
                border: 1px solid #ff9e3b;
                border-left: 4px solid #ff9e3b;
                border-radius: 4px;
                padding: 14px 18px;
                color: #ffd9a0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 12px rgba(255, 158, 59, 0.15);
            }
            .chad-content strong { color: #ff9e3b; text-shadow: 0 0 4px #ff9e3b; }
            .robert-content {
                background-color: #0a0018;
                border: 1px solid #ff007f;
                border-left: 4px solid #ff007f;
                border-radius: 4px;
                padding: 14px 18px;
                color: #ffc0d0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                font-family: 'Courier New', monospace;
                box-shadow: 0 0 12px rgba(255, 0, 127, 0.15);
            }
            .robert-content strong { color: #ff007f; text-shadow: 0 0 4px #ff007f; }
            .geoffrey-content {
                background-color: #0a0018;
                border: 1px solid #ffd700;
                border-left: 4px solid #ffd700;
                border-radius: 4px;
                padding: 14px 18px;
                color: #ffe680;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 12px rgba(255, 215, 0, 0.15);
            }
            .geoffrey-content strong { color: #ffd700; text-shadow: 0 0 4px #ffd700; }
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #000000;
                border: 1px solid #1a0a2e;
                border-radius: 4px;
                padding: 12px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                color: #00f0ff;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
            }
            .welcome-title { color: #ffffff; font-size: 28px; font-weight: 700; text-shadow: 0 0 10px #00f0ff, 0 0 20px #ff007f; margin-bottom: 16px; }
            .welcome-agents { color: #c0b0e0; font-size: 15px; line-height: 1.8; text-shadow: 0 0 3px #00f0ff; }
            [data-testid="stChatInput"] {
                background-color: #0a0018;
                border: 1px solid #ff007f;
                border-radius: 4px;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }
            [data-testid="stChatInput"]:focus-within {
                border-color: #00f0ff;
                box-shadow: 0 0 0 2px rgba(0, 240, 255, 0.2), 0 0 15px rgba(255, 0, 127, 0.1);
            }
            [data-testid="stChatInput"] input { color: #c0f0ff; font-family: 'Courier New', monospace; }
            [data-testid="stChatInput"] input::placeholder { color: #5a4a7a; }
            [data-testid="stFileUploader"] { background-color: #0a0018; border: 1px dashed #1a0a2e; border-radius: 4px; padding: 8px; }
            [data-testid="stFileUploader"]:hover { border-color: #ff007f; }
            [data-testid="stSelectbox"] label {
                color: #a699c9;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 15px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            [data-baseweb="popover"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #08010f; }
            ::-webkit-scrollbar-thumb { background: #1a0a2e; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #ff007f; }
        </style>
        """,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # 4. ZX SPECTRUM  (8-bit Retro)
    # ═══════════════════════════════════════════════════════════════════════
    "zx-spectrum": {
        "name": "ZX Spectrum",
        "css": """
        <style>
            .stApp {
                background-color: #000000;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                border: 8px solid #ffffff;
            }
            .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #ffffff; font-weight: 900 !important; text-transform: uppercase; }
            .stApp a { color: #00ffff; }
            .stApp a:hover { color: #ffff00; }
            .stApp hr { border-color: #333333; margin: 16px 0; }
            [data-testid="stSidebar"] { background-color: #000000; border-right: 2px solid #ffffff; }
            [data-testid="stSidebar"] .stMarkdown { color: #ffffff; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #000000;
                border: 2px solid #ffffff;
                border-radius: 0px !important;
                margin-bottom: 8px;
            }
            [data-testid="stSidebar"] .st-expander-header { color: #ffffff; font-weight: 900 !important; font-size: 16px; text-transform: uppercase; }
            [data-testid="stSidebar"] .stCaption { color: #cccccc; font-size: 12px; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
            .stButton button {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 2px solid #ffffff !important;
                border-radius: 0px !important;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 13px !important;
                text-transform: uppercase !important;
            }
            .stButton button:hover {
                background-color: #ffffff !important;
                color: #000000 !important;
            }
            .terminal-container {
                background-color: #000000;
                border-left: 3px solid #ffff00;
                border-radius: 0px !important;
                padding: 10px 12px;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 11px;
                line-height: 1.5;
                color: #ffff00;
                max-height: 300px;
                overflow-y: auto;
            }
            .terminal-line { border-bottom: 1px solid #222222; padding: 3px 0; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content {
                background-color: #000000;
                border: 2px solid #ffffff !important;
                border-radius: 0px !important;
                padding: 12px 16px;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 16px;
                margin: 4px 0;
            }
            .elena-content {
                background-color: #000000;
                border: 3px solid #00ffff !important;
                border-radius: 0px !important;
                padding: 14px 18px;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .elena-content strong { color: #00ffff; }
            .chad-content {
                background-color: #000000;
                border: 3px solid #ff9e3b !important;
                border-radius: 0px !important;
                padding: 14px 18px;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .chad-content strong { color: #ff9e3b; }
            .robert-content {
                background-color: #000000;
                border: 3px solid #ffff00 !important;
                border-radius: 0px !important;
                padding: 14px 18px;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .robert-content strong { color: #ffff00; }
            .geoffrey-content {
                background-color: #000000;
                border: 3px solid #ffd700 !important;
                border-radius: 0px !important;
                padding: 14px 18px;
                color: #ffffff;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
            }
            .geoffrey-content strong { color: #ffd700; }
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #000000;
                border: 2px solid #ffffff !important;
                border-radius: 0px !important;
                padding: 12px;
                font-family: 'Courier New', monospace !important;
                font-weight: 900 !important;
                font-size: 12px;
                color: #ffffff;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
            }
            .welcome-title { color: #ffffff; font-size: 28px; font-weight: 900 !important; text-transform: uppercase; margin-bottom: 16px; }
            .welcome-agents { color: #cccccc; font-family: 'Courier New', monospace !important; font-weight: 900 !important; font-size: 15px; line-height: 1.8; }
            [data-testid="stChatInput"] {
                background-color: #000000;
                border: 2px solid #ffffff !important;
                border-radius: 0px !important;
            }
            [data-testid="stChatInput"]:focus-within { border-color: #ffff00 !important; }
            [data-testid="stChatInput"] input { color: #ffffff; font-family: 'Courier New', monospace !important; font-weight: 900 !important; }
            [data-testid="stChatInput"] input::placeholder { color: #666666; }
            [data-testid="stFileUploader"] { background-color: #000000; border: 2px dashed #ffffff !important; border-radius: 0px !important; padding: 8px; }
            [data-testid="stFileUploader"]:hover { border-color: #00ffff !important; }
            [data-testid="stSelectbox"] label {
                color: #dddddd;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 15px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            [data-baseweb="popover"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            ::-webkit-scrollbar { width: 8px; height: 8px; }
            ::-webkit-scrollbar-track { background: #000000; }
            ::-webkit-scrollbar-thumb { background: #ffffff; border-radius: 0px !important; }
            ::-webkit-scrollbar-thumb:hover { background: #cccccc; }
        </style>
        """,
    },

    # ═══════════════════════════════════════════════════════════════════════
    # 5. RETRO SCI-FI CRT
    # ═══════════════════════════════════════════════════════════════════════
    "retro-crt": {
        "name": "Retro Sci-Fi CRT",
        "css": """
        <style>
            @keyframes crt-pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.96; }
            }
            .stApp {
                background-color: #0a0f0d;
                background-image: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%);
                background-size: 100% 4px;
                color: #33ff33;
                font-family: 'Courier New', 'Terminal', monospace;
                animation: crt-pulse 3s infinite;
            }
            .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #33ff33; text-transform: uppercase; letter-spacing: 3px; }
            .stApp a { color: #33ff33; text-decoration: underline; }
            .stApp a:hover { color: #66ff66; }
            .stApp hr { border-color: #1a2a1a; margin: 16px 0; }
            [data-testid="stSidebar"] { background-color: #060a08; border-right: 1px solid #1a2a1a; }
            [data-testid="stSidebar"] .stMarkdown { color: #33ff33; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #080c0a;
                border: 1px solid #1a2a1a;
                border-radius: 6px;
                margin-bottom: 8px;
                box-shadow: 0 0 4px #33ff33;
            }
            [data-testid="stSidebar"] .st-expander-header { color: #33ff33; font-weight: bold; font-size: 13px; text-transform: uppercase; letter-spacing: 2px; }
            [data-testid="stSidebar"] .stCaption { color: #66ff66; font-size: 13px; font-weight: 500; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
            .stButton button {
                background-color: #0a0f0d !important;
                color: #33ff33 !important;
                border: 1px solid #33ff33 !important;
                border-radius: 6px !important;
                font-family: 'Courier New', monospace !important;
                font-size: 12px !important;
                text-transform: uppercase !important;
                letter-spacing: 2px !important;
                box-shadow: 0 0 4px #33ff33 !important;
                transition: all 0.2s ease !important;
            }
            .stButton button:hover {
                background-color: #0a1a0a !important;
                box-shadow: 0 0 8px #33ff33, inset 0 0 4px #33ff33 !important;
            }
            .terminal-container {
                background-color: #050807;
                border-left: 3px solid #ffb000;
                border-radius: 6px;
                padding: 10px 12px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.5;
                color: #33ff33;
                max-height: 300px;
                overflow-y: auto;
                box-shadow: 0 0 4px #33ff33;
            }
            .terminal-line { border-bottom: 1px solid #0a1a0a; padding: 3px 0; color: #ffb000; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content {
                background-color: #080c0a;
                border: 1px solid #1a2a1a;
                border-radius: 6px;
                padding: 12px 16px;
                color: #33ff33;
                font-size: 16px;
                margin: 4px 0;
                box-shadow: 0 0 3px #33ff33;
            }
            .elena-content {
                background-color: #080c0a;
                border: 1px solid #33ff33;
                border-left: 4px solid #33ff33;
                border-radius: 6px;
                padding: 14px 18px;
                color: #33ff33;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 4px #33ff33;
            }
            .elena-content strong { color: #66ff66; }
            .chad-content {
                background-color: #080c0a;
                border: 1px solid #ff9e3b;
                border-left: 4px solid #ff9e3b;
                border-radius: 6px;
                padding: 14px 18px;
                color: #ffd9a0;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 4px #ff9e3b;
            }
            .chad-content strong { color: #ff9e3b; }
            .robert-content {
                background-color: #080c0a;
                border: 1px solid #ffb000;
                border-left: 4px solid #ffb000;
                border-radius: 6px;
                padding: 14px 18px;
                color: #ffb000;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                font-family: 'Courier New', monospace;
                box-shadow: 0 0 4px #ffb000;
            }
            .robert-content strong { color: #ffcc33; }
            .geoffrey-content {
                background-color: #080c0a;
                border: 1px solid #ffd700;
                border-left: 4px solid #ffd700;
                border-radius: 6px;
                padding: 14px 18px;
                color: #ffe680;
                font-size: 16px;
                line-height: 1.6;
                margin: 4px 0;
                box-shadow: 0 0 4px #ffd700;
            }
            .geoffrey-content strong { color: #ffd700; }
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #050807;
                border: 1px solid #1a2a1a;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                color: #33ff33;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
                box-shadow: inset 0 0 6px #33ff33;
            }
            .welcome-title { color: #33ff33; font-size: 28px; font-weight: bold; text-transform: uppercase; letter-spacing: 4px; text-shadow: 0 0 6px #33ff33; margin-bottom: 16px; }
            .welcome-agents { color: #33ff33; font-size: 15px; line-height: 1.8; opacity: 0.9; }
            [data-testid="stChatInput"] {
                background-color: #080c0a;
                border: 1px solid #33ff33;
                border-radius: 6px;
                box-shadow: 0 0 4px #33ff33;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }
            [data-testid="stChatInput"]:focus-within {
                box-shadow: 0 0 8px #33ff33, inset 0 0 4px #33ff33;
            }
            [data-testid="stChatInput"] input { color: #33ff33; font-family: 'Courier New', monospace; }
            [data-testid="stChatInput"] input::placeholder { color: #1a4a1a; }
            [data-testid="stFileUploader"] { background-color: #080c0a; border: 1px dashed #1a2a1a; border-radius: 6px; padding: 8px; box-shadow: 0 0 3px #33ff33; }
            [data-testid="stFileUploader"]:hover { border-color: #33ff33; }
            [data-testid="stSelectbox"] label {
                color: #66ff66;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 15px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            [data-baseweb="popover"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, sans-serif;
                font-size: 14px;
                font-weight: 500;
                text-rendering: optimizeLegibility;
                -webkit-font-smoothing: antialiased;
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #050807; }
            ::-webkit-scrollbar-thumb { background: #1a2a1a; border-radius: 3px; box-shadow: 0 0 3px #33ff33; }
            ::-webkit-scrollbar-thumb:hover { background: #33ff33; }
        </style>
        """,
    },
}


def set_theme(name: str = "dark-tech") -> None:
    """Inject CSS for the named theme."""
    theme = _THEMES.get(name)
    if theme is None:
        available = ", ".join(_THEMES)
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    st.markdown(theme["css"], unsafe_allow_html=True)
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] .stCaption {
                font-size: 13px !important;
                font-weight: 500 !important;
                opacity: 1 !important;
                letter-spacing: 0.3px !important;
            }
            [data-testid="stSidebar"] .st-expander-header {
                font-size: 14px !important;
                font-weight: 600 !important;
                letter-spacing: 0.4px !important;
            }
            [data-testid="stSelectbox"] label {
                font-size: 14px !important;
                font-weight: 500 !important;
                opacity: 1 !important;
            }
            [data-testid="stSelectbox"],
            [data-testid="stSelectbox"] * {
                cursor: pointer !important;
            }
            [data-testid="stSelectbox"] [data-baseweb="select"],
            [data-testid="stSelectbox"] [data-baseweb="select"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, Ubuntu, sans-serif !important;
                font-size: 15px !important;
                font-weight: 400 !important;
                text-rendering: optimizeLegibility !important;
                -webkit-font-smoothing: antialiased !important;
                letter-spacing: 0.3px !important;
            }
            .MuiPopover-root,
            .MuiPopover-root *,
            .MuiMenu-paper,
            .MuiMenu-paper *,
            .MuiMenuItem-root,
            .MuiMenuItem-root *,
            [data-baseweb="popover"],
            [data-baseweb="popover"] *,
            [data-baseweb="menu"],
            [data-baseweb="menu"] *,
            [role="listbox"],
            [role="listbox"] *,
            [role="menu"],
            [role="menu"] *,
            [role="option"],
            [role="option"] * {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
                font-size: 16px !important;
                font-weight: 500 !important;
                line-height: 1.5 !important;
                text-rendering: optimizeLegibility !important;
                -webkit-font-smoothing: antialiased !important;
                letter-spacing: normal !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="VibeOps MVP", layout="wide")

# ── State ──────────────────────────────────────────────────────────────────
st.session_state.setdefault("mock_mode", False)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("log_entries", [])
st.session_state.setdefault("sandbox_output", "")
st.session_state.setdefault("theme", "dark-tech")
st.session_state.setdefault("mcp_initialized", False)
st.session_state.setdefault("mcp_available", False)
st.session_state.setdefault("mcp_tools", [])

# ── Active file path ────────────────────────────────────────────────────
st.session_state.setdefault("active_file_path", "workspace/dirty_data.csv")

# ── Vibe Diff state ─────────────────────────────────────────────────────
st.session_state.setdefault("vibe_diff_pending", False)
st.session_state.setdefault("vibe_diff_code", "")
st.session_state.setdefault("vibe_diff_plan", "")
st.session_state.setdefault("vibe_diff_user_input", "")

# ── Guardrail state ────────────────────────────────────────────────────
st.session_state.setdefault("force_elena_warning", False)
st.session_state.setdefault("elena_warning_message", "")
st.session_state.setdefault("user_profile", {})
st.session_state.setdefault("user_profile_loaded", False)

# Pick up theme widget change (available on subsequent runs)
if "theme_widget" in st.session_state:
    st.session_state["theme"] = st.session_state.theme_widget

set_theme(st.session_state["theme"])

# ── MCP Initialization (once per session) ──────────────────────────────
if not st.session_state["mcp_initialized"]:
    try:
        initialize_mcp_sync()
        tools = get_all_tools_sync()
        if tools:
            st.session_state["mcp_tools"] = tools
            st.session_state["mcp_available"] = True
            st.session_state.log_entries.append(
                f"🔌 MCP: {len(tools)} tools ready"
            )
        else:
            st.session_state["mcp_available"] = False
            st.session_state.log_entries.append("🔌 MCP: no servers connected")
    except Exception as e:
        st.session_state["mcp_available"] = False
        st.session_state.log_entries.append(f"🔌 MCP init error: {e}")
    st.session_state["mcp_initialized"] = True

# ── Long-term Memory (user profile) ───────────────────────────────────────
if not st.session_state["user_profile_loaded"]:
    profile_path = Path("workspace/user_profile.json")
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                st.session_state["user_profile"] = json.load(f)
            st.session_state.log_entries.append(
                f"👤 Profile loaded ({st.session_state['user_profile'].get('session_count', '?')} sessions)"
            )
        except Exception:
            st.session_state["user_profile"] = {}
    else:
        st.session_state["user_profile"] = {"session_count": 0, "mastered_concepts": [], "struggles": [], "history_facts": []}
    st.session_state["user_profile_loaded"] = True

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛠️ VibeOps: The Office")

    st.toggle(
        "🔌 Offline Simulation Mode",
        key="mock_toggle",
        value=st.session_state["mock_mode"],
    )
    st.session_state["mock_mode"] = st.session_state.mock_toggle

    # ── Guardrail Status ────────────────────────────────────────────────────
    with st.expander("🛡️ Guardrails", expanded=False):
        st.markdown("**Rule A** — Elena code blocks: ✅ Active")
        st.markdown("**Rule B** — Destructive ops: ✅ Active")
        st.markdown("**Rule C** — Toxicity filter: ✅ Active")
        if st.session_state.get("vibe_diff_pending", False):
            st.markdown("**⚡ Vibe Diff** — Pending approval")
        else:
            st.markdown("**⚡ Vibe Diff** — Standby")

    # ── Agent Skills Matrix ─────────────────────────────────────────────────
    with st.expander("⚙️ Agents", expanded=False):
        st.markdown("**🧠 Elena** — Socratic mentor (questions only, no code)")
        st.markdown("**🔥 Chad** — Vibe coder")
        st.markdown("**🛠️ Robert** — Sandbox (isolated code execution)")
        st.markdown("**👔 Geoffrey** — Head of AI (business goals)")

    # ── MCP Tools ─────────────────────────────────────────────────────────
    if st.session_state.get("mcp_available", False):
        with st.expander("🔧 MCP Tools", expanded=False):
            for tool in st.session_state["mcp_tools"]:
                svr = tool.get("server", "?")
                name = tool.get("name", "?")
                desc = tool.get("description", "")[:80]
                st.markdown(f"`{svr}` **{name}** — {desc}")

    # ── Workspace Data ──────────────────────────────────────────────────────
    with st.expander("📁 Data", expanded=False):
        workspace_dir = Path("workspace")
        workspace_dir.mkdir(exist_ok=True)

        uploaded_file = st.file_uploader("csv_upload", type=["csv"], label_visibility="collapsed")
        if uploaded_file is not None:
            dest = workspace_dir / uploaded_file.name
            with open(dest, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.session_state.active_file_path = f"workspace/{uploaded_file.name}"
            st.success(f"✅ {uploaded_file.name}")

        csv_files = sorted(f.name for f in workspace_dir.glob("*.csv"))
        if csv_files:
            sel_col, del_col = st.columns([4, 1])
            with sel_col:
                selected = st.selectbox("Table", csv_files, label_visibility="collapsed")
                st.session_state.active_file_path = f"workspace/{selected}"
            with del_col:
                if st.button("🗑️", key=f"del_{selected}", help="Delete this file"):
                    (workspace_dir / selected).unlink(missing_ok=True)
                    if st.session_state.get("active_file_path", "") == f"workspace/{selected}":
                        remaining = sorted(f.name for f in workspace_dir.glob("*.csv"))
                        st.session_state.active_file_path = f"workspace/{remaining[0]}" if remaining else "workspace/dirty_data.csv"
                    st.rerun()
            try:
                df = pd.read_csv(workspace_dir / selected)
                st.caption(f"{len(df)} rows x {len(df.columns)} columns")
                with st.expander("Preview", expanded=False):
                    st.dataframe(df, width="stretch")
            except Exception as err:
                st.caption(f"Error: {err}")
        else:
            st.caption("No CSV in workspace/")

    # ── Agent Log (terminal style) ──────────────────────────────────────────
    with st.expander("📜 Agent Log", expanded=False):
        if st.session_state.log_entries:
            lines = "".join(
                f'<div class="terminal-line">▸ {entry}</div>'
                for entry in st.session_state.log_entries[-10:]
            )
            st.markdown(f'<div class="terminal-container">{lines}</div>', unsafe_allow_html=True)
        else:
            st.caption("Awaiting input…")

    # ── Sandbox Output ──────────────────────────────────────────────────────
    with st.expander("📦 Sandbox", expanded=False):
        if st.session_state.sandbox_output:
            st.markdown(
                f'<div class="sandbox-output">{st.session_state.sandbox_output}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No output.")

    # ── Recent turns ────────────────────────────────────────────────────────
    with st.expander("🕵️ History", expanded=False):
        turns = st.session_state.messages
        if not turns:
            st.caption("No messages.")
        else:
            for msg in reversed(turns[-6:]):
                role = msg["role"]
                icon = "🧑" if role == "user" else "🤖"
                preview = msg["content"][:120].replace("\n", " ")
                st.markdown(f"`{icon}` {preview}…")

    # ── Copy Chat Button ───────────────────────────────────────────────────
    if st.button("📋 Copy Chat", use_container_width=True):
        chat_text = ""
        for msg in st.session_state.messages:
            role = msg["role"]
            agent = msg.get("agent", "")
            name = {"user": "You", "system": "System"}.get(role, agent.capitalize() if agent else "Assistant")
            chat_text += f"[{name}]: {msg['content']}\n\n"
        st.markdown(
            f"<textarea id='chat-copy-area' style='position:fixed;left:-9999px'>{chat_text}</textarea>"
            "<script>"
            "var ta=document.getElementById('chat-copy-area');"
            "ta.select();"
            "navigator.clipboard.writeText(ta.value).then(function(){"
            "}).catch(function(e){});"
            "</script>",
            unsafe_allow_html=True,
        )
        st.toast("✅ Chat copied to clipboard", icon="📋")

    # ── Theme Switcher ──────────────────────────────────────────────────────
    st.divider()
    theme_names = {
        "dark-tech": "🌙 Dark Tech",
        "light-paper": "☀️ Light Paper",
        "cyberpunk": "🌃 Cyberpunk Neon",
        "zx-spectrum": "🟦 ZX Spectrum",
        "retro-crt": "🖥️ Retro Sci-Fi CRT",
    }
    current = st.session_state["theme"]
    theme_keys = list(theme_names.keys())
    st.selectbox(
        "Theme",
        theme_keys,
        format_func=lambda k: theme_names[k],
        key="theme_widget",
        index=theme_keys.index(current) if current in theme_keys else 0,
    )


# ── Long-term Memory & Context Compression ────────────────────────────────

_USER_PROFILE_PATH = Path("workspace/user_profile.json")


def _save_user_profile():
    """Persist current user_profile dict to workspace file."""
    try:
        with open(_USER_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(st.session_state["user_profile"], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _build_profile_context() -> str:
    """Build a prose string from user_profile to inject into agent prompts."""
    profile = st.session_state.get("user_profile", {})
    if not profile:
        return ""
    parts = []
    if profile.get("mastered_concepts"):
        parts.append("User has mastered: " + ", ".join(profile["mastered_concepts"]))
    if profile.get("struggles"):
        parts.append("User struggles with: " + ", ".join(profile["struggles"]))
    if profile.get("session_count", 0) > 0:
        parts.append(f"Session count: {profile['session_count']}")
    return "---\n**Long-term Memory:**\n" + "\n".join(parts) + "\n---\n" if parts else ""





def _compress_context() -> str:
    """Compress old conversation history when it exceeds the memory window.
    Returns an empty string if no compression is needed.
    If beyond MEMORY_WINDOW*2 messages, older turns are condensed into a summary fact."""
    msgs = st.session_state.messages
    window = config().memory_window  # 10
    threshold = window * 2  # 20

    if len(msgs) <= threshold:
        return ""

    # Condense first len(msgs)-window messages to a single summary
    old = msgs[: -window]
    summary_lines = []
    for m in old:
        speaker = "User" if m["role"] == "user" else m.get("agent", "Assistant").capitalize()
        preview = m["content"][:120].replace("\n", " ")
        summary_lines.append(f"{speaker}: {preview}")
    summary = "\n".join(summary_lines)

    # Store the summary in history_facts for persistence
    profile = st.session_state["user_profile"]
    if "history_facts" not in profile:
        profile["history_facts"] = []
    compressed_note = f"[Compressed {len(old)} earlier turns: {summary}]"
    profile["history_facts"].append(compressed_note)
    _save_user_profile()
    st.session_state.log_entries.append(f"🗜️ Context compressed ({len(old)} turns → 1 fact)")
    return compressed_note


# ── Helpers ────────────────────────────────────────────────────────────────
def _message_html(content: str, css_class: str, name: str = "") -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = text.replace("\n", "<br>")
    name_html = f'<div style="font-size:12px;font-weight:600;opacity:0.7;margin-bottom:4px;letter-spacing:0.3px">{name}</div>' if name else ""
    return f'<div class="{css_class}">{name_html}{text}</div>'


def _render_message(msg: dict):
    role = msg["role"]
    agent = msg.get("agent")

    if role == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(_message_html(msg["content"], "user-content", "You"), unsafe_allow_html=True)
    elif role == "system":
        st.error(msg["content"])
    elif agent == "elena":
        with st.chat_message("assistant", avatar="🧠"):
            st.markdown(_message_html(msg["content"], "elena-content", "Elena"), unsafe_allow_html=True)
    elif agent == "chad":
        with st.chat_message("assistant", avatar="🔥"):
            st.markdown(_message_html(msg["content"], "chad-content", "Chad"), unsafe_allow_html=True)
    elif agent == "robert":
        with st.chat_message("assistant", avatar="🛠️"):
            st.markdown(_message_html(msg["content"], "robert-content", "Robert"), unsafe_allow_html=True)
    elif agent == "geoffrey":
        with st.chat_message("assistant", avatar="👔"):
            st.markdown(_message_html(msg["content"], "geoffrey-content", "Geoffrey"), unsafe_allow_html=True)


# ── Welcome Screen ───────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        '<div class="welcome-title">Welcome to VibeOps! 🤖</div>'
        '<div class="welcome-agents">'
        "🧠 Elena &mdash; Socratic mentor<br>"
        "🔥 Chad &mdash; Vibe coder<br>"
        "🛠️ Robert &mdash; Sandbox engineer<br>"
        "👔 Geoffrey &mdash; Head of AI"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Main: Chat History ─────────────────────────────────────────────────────
for msg in st.session_state.messages:
    _render_message(msg)

# ── Vibe Diff: Approval UI ────────────────────────────────────────────────
if st.session_state.get("vibe_diff_pending", False):
    st.markdown("---")
    st.markdown(
        '<div style="'
        'border:1px solid #45475a;border-radius:12px;padding:20px;'
        'background:linear-gradient(135deg,#1e1e2e 0%,#181825 100%);'
        'margin:12px 0;box-shadow:0 4px 12px rgba(0,0,0,0.3)'
        '">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">'
        '<span style="font-size:24px">🛠️</span>'
        '<span style="font-size:18px;font-weight:600;color:#cdd6f4">'
        "Robert — Review &amp; Confirm"
        '</span>'
        '</div>'
        '<div style="color:#a6adc8;font-size:14px;margin-bottom:16px;line-height:1.5">'
        'Robert generated the code below. '
        'Review it, then choose to approve execution in the sandbox or reject it.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    plan_tab, code_tab = st.tabs(["📝 Explanation", "💻 Code"])
    with plan_tab:
        plan_no_code = st.session_state.vibe_diff_plan
        plan_no_code = re.sub(r"```python\n?.*?```", "", plan_no_code, flags=re.DOTALL).strip()
        st.markdown(plan_no_code)
    with code_tab:
        st.code(st.session_state.vibe_diff_code, language="python")

    st.markdown(
        '<div style="margin:12px 0 4px 0;padding:8px 0;'
        'border-top:1px solid #313244">'
        '</div>',
        unsafe_allow_html=True,
    )
    _approve, _spacer, _reject = st.columns([1, 0.2, 1])
    with _approve:
        if st.button("🟢 Approve & Run", type="primary", use_container_width=True):
            code = st.session_state.vibe_diff_code
            robert_response = st.session_state.vibe_diff_plan
            try:
                result = execute_python_code(code)
                st.session_state.sandbox_output = result
                sandbox_note = f"\n\n**Sandbox output:**\n```\n{result.strip()}\n```"
                st.session_state.log_entries.append("✅ Vibe Diff approved — sandbox executed")
            except Exception as e:
                sandbox_note = f"\n\n**Sandbox error:**\n{e}"
                st.session_state.log_entries.append(f"❌ Vibe Diff sandbox error: {e}")

            agent_text = robert_response + "\n" + sandbox_note
            st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "robert"})
            st.session_state.vibe_diff_pending = False
            st.session_state.vibe_diff_code = ""
            st.session_state.vibe_diff_plan = ""
            st.session_state.vibe_diff_user_input = ""
            st.rerun()

    with _reject:
        if st.button("🔴 Reject", use_container_width=True, type="secondary"):
            st.session_state.log_entries.append("⛔ Vibe Diff rejected by user")
            robert_response = st.session_state.vibe_diff_plan
            reject_msg = robert_response + "\n\n" + (
                "**⛔ Execution rejected by user.**\n\n"
                "No code was executed. Edit your request and try again."
            )
            st.session_state.messages.append({"role": "assistant", "content": reject_msg, "agent": "robert"})
            st.session_state.vibe_diff_pending = False
            st.session_state.vibe_diff_code = ""
            st.session_state.vibe_diff_plan = ""
            st.session_state.vibe_diff_user_input = ""
            st.rerun()

# ── Main: Capture Input (keyboard OR pending callback) ────────────────────
prompt_to_process = None
chat_disabled = st.session_state.get("vibe_diff_pending", False)
chat_placeholder = "⏳ Approve or reject the pending execution…" if chat_disabled else "Your message…"

if prompt := st.chat_input(chat_placeholder, disabled=chat_disabled):
    prompt_to_process = prompt
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(_message_html(prompt, "user-content", "You"), unsafe_allow_html=True)
elif "pending_prompt" in st.session_state and st.session_state.pending_prompt:
    prompt_to_process = st.session_state.pending_prompt
    del st.session_state.pending_prompt

# ── Bilingual Ambiguity Interceptor (ROBUST BILINGUAL REGEX) ───────────
if prompt_to_process:
    cleaned = prompt_to_process.lower()
    available_files = ["dirty_data.csv", "raw_car_dataset.csv"]

    # Comprehensive bilingual patterns with word boundaries (\b)
    # Handles plurals (table/tables), inflections (форма/форму), and common data science slang (df/dataset)
    keywords = [
        # --- English Data Keywords ---
        r"\bshow(s|ing)?\b",       # show, shows, showing
        r"\btables?\b",            # table, tables
        r"\bshapes?\b",            # shape, shapes
        r"\binfo\b",               # info (strict, avoids breaking on longer text if not intended)
        r"\bdata(sets?)?\b",       # data, dataset, datasets
        r"\bdf\b",                 # df
        r"\bview\b",               # view

        # --- Russian Data Keywords ---
        r"\bтаблиц[аыеуя]?\b",     # таблица, таблицы, таблицу...
        r"\bформ[ауеы]\b",         # форма, форму, форме... (strict boundaries to avoid "формат")
        r"\bразмер[ы]?\b",         # размер, размеры
        r"\bпокажи(те)?\b",        # покажи, покажите
        r"\bинфо\b",               # инфо (strict boundaries to avoid "информации")
    ]

    has_keyword = any(re.search(pattern, cleaned) for pattern in keywords)
    has_filename = any(f in cleaned for f in available_files)

    if has_keyword and not has_filename:
        with st.chat_message("assistant"):
            st.write("🤖 **Robert:** I'm ready! However, we have multiple datasets available. Which table would you like to inspect?")
            cols = st.columns(len(available_files))
            for idx, file_name in enumerate(available_files):
                cols[idx].button(
                    f"📊 {file_name}",
                    key=f"btn_{file_name}_{idx}",
                    on_click=select_file_callback,
                    args=(file_name,)
                )
        st.stop()

# ── Guardrails: Check user input for toxicity ──────────────────────────
if prompt_to_process:
    if contains_toxic_input(prompt_to_process):
        st.session_state.log_entries.append("🛑 RULE C — Toxic user input blocked")
        warning = "🚫 Your message was blocked by Guardrails (Rule C). Toxic or offensive language is not permitted. Please rephrase your request respectfully."
        st.session_state.messages.append({"role": "system", "content": warning})
        st.rerun()

# ── Agent Execution ────────────────────────────────────────────────────
if prompt_to_process:
    # Context compression — if history exceeds threshold, compact older turns
    compressed_fact = _compress_context()

    # Build conversation history context for LLM (skip system messages)
    history_msgs = [m for m in st.session_state.messages[:-1] if m.get("role") != "system"]
    if history_msgs:
        history_lines = []
        if compressed_fact:
            history_lines.append(f"[SUMMARY]: {compressed_fact}")
        for msg in history_msgs:
            speaker = "User" if msg["role"] == "user" else msg.get("agent", "Assistant").capitalize()
            history_lines.append(f"{speaker}: {msg['content'][:500]}")
        history_context = "--- Previous conversation:\n" + "\n".join(history_lines[-6:]) + "\n---\n"
    else:
        history_context = ""

    # Inject long-term memory profile into the prompt
    profile_context = _build_profile_context()

    prompt_with_lang = profile_context + history_context + prompt_to_process

    # Language override directive (appended at end for highest attention)
    lang_directive = detect_language_directive(prompt_to_process)
    prompt_with_lang += "\n\n" + lang_directive

    agent_chain = determine_agent_chain(prompt_to_process)
    workspace_info = get_workspace_snapshot()

    mcp_tools = st.session_state.get("mcp_tools", [])
    mcp_available = st.session_state.get("mcp_available", False)

    for active_agent in agent_chain:
        if active_agent == "robert":
            with st.chat_message("assistant", avatar="🛠️"):
                st.session_state.log_entries.append("🤖 Invoking Robert (Sandbox)")

                active_file = st.session_state.get("active_file_path", "workspace/dirty_data.csv")
                dynamic_file_directive = (
                    f"CRITICAL CONTEXT: The active dataset the user is working with "
                    f"is located at: '{active_file}'. "
                    f"In your generated Python code, you MUST use this exact path string "
                    f"inside `pd.read_csv('{active_file}')`. "
                    f"Do not hardcode any other filenames."
                )
                robert_context = f"{ROBERT_SYSTEM_PROMPT}\n\n{workspace_info}\n\n{dynamic_file_directive}"
                if st.session_state["mock_mode"]:
                    agent_text = get_mock_response("robert", workspace_info=workspace_info)
                else:
                    try:
                        if mcp_available and mcp_tools:
                            agent_text = call_with_tools(
                                robert_context, prompt_with_lang, mcp_tools,
                                lambda s, n, a: call_tool_sync(s, n, a),
                            )
                        else:
                            agent_text = call_live_gemini_api(robert_context, prompt_with_lang)
                    except Exception:
                        agent_text = get_mock_response("robert_429", workspace_info=workspace_info)

                # Extract code blocks from Robert's response for HITL
                code_match = re.search(r"```python\n?(.*?)```", agent_text, re.DOTALL)
                has_code = bool(code_match and code_match.group(1).strip())

                if has_code and not st.session_state.get("vibe_diff_pending", False):
                    extracted_code = code_match.group(1).strip()
                    st.session_state.vibe_diff_code = extracted_code
                    st.session_state.vibe_diff_plan = agent_text
                    st.session_state.vibe_diff_user_input = prompt_to_process
                    st.session_state.vibe_diff_pending = True
                    st.session_state.sandbox_output = ""

                    st.markdown(
                        f'<div style="border:1px solid #ffcb6b;border-radius:8px;padding:16px;'
                        f'background-color:#1e1e2e;margin:8px 0">'
                        f'<h4 style="color:#ffcb6b;margin:0 0 8px 0">⚡ Robert — Generated Code</h4>'
                        f'<p style="color:#cdd6f4">Robert generated the following code. '
                        f'Review and approve below to execute in the sandbox.</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.session_state.log_entries.append("⏳ Vibe Diff pending — awaiting approval")
                    st.rerun()
                else:
                    st.markdown(_message_html(agent_text, "robert-content", "Robert"), unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "robert"})
        elif active_agent == "chad":
            with st.chat_message("assistant", avatar="🔥"):
                st.session_state.log_entries.append("🔥 Invoking Chad (Vibe Coder)")

                chad_context = f"{CHAD_SYSTEM_PROMPT}\n\n{workspace_info}"

                if st.session_state["mock_mode"]:
                    agent_text = get_mock_response("chad", workspace_info=workspace_info)
                else:
                    try:
                        if mcp_available and mcp_tools:
                            agent_text = call_with_tools(
                                chad_context, prompt_with_lang, mcp_tools,
                                lambda s, n, a: call_tool_sync(s, n, a),
                            )
                        else:
                            agent_text = call_live_gemini_api(chad_context, prompt_with_lang)
                    except Exception:
                        agent_text = get_mock_response("chad_429", workspace_info=workspace_info)

                # ── Guardrails: Check Chad output ───────────────────────────
                gr_result = run_guardrails("chad", agent_text)
                if gr_result.blocked:
                    st.session_state.log_entries.append(f"🛑 RULE {gr_result.rule_triggered} BLOCKED Chad output")
                    st.warning(f"Guardrail Rule {gr_result.rule_triggered}: Chad's response was blocked.")
                    agent_text = (
                        "**[This response was blocked by Guardrails.]**\n\n"
                        "Chad's output was filtered. Please rephrase your request."
                    )
                if gr_result.force_elena_warning:
                    st.session_state.force_elena_warning = True
                    st.session_state.elena_warning_message = (
                        "⚠️ **Note:** Chad suggested a destructive operation "
                        "(e.g., `inplace=True`, `drop`). "
                        "Let's discuss safer approaches to data manipulation."
                    )
                    st.session_state.log_entries.append("⚠️ RULE B triggered — Elena will warn next")

                st.markdown(_message_html(agent_text, "chad-content", "Chad"), unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "chad"})
        elif active_agent == "geoffrey":
            with st.chat_message("assistant", avatar="👔"):
                st.session_state.log_entries.append("👔 Invoking Geoffrey (Head of AI)")

                geoffrey_context = f"{GEOFFREY_SYSTEM_PROMPT}\n\n{workspace_info}"

                if st.session_state["mock_mode"]:
                    agent_text = get_mock_response("geoffrey", workspace_info=workspace_info)
                else:
                    try:
                        if mcp_available and mcp_tools:
                            agent_text = call_with_tools(
                                geoffrey_context, prompt_with_lang, mcp_tools,
                                lambda s, n, a: call_tool_sync(s, n, a),
                            )
                        else:
                            agent_text = call_live_gemini_api(geoffrey_context, prompt_with_lang)
                    except Exception:
                        agent_text = get_mock_response("geoffrey_429", workspace_info=workspace_info)

                # ── Guardrails: Check Geoffrey output (Rule C — Toxicity) ──
                gr_result = run_guardrails("geoffrey", agent_text)
                if gr_result.blocked:
                    st.session_state.log_entries.append(f"🛑 RULE {gr_result.rule_triggered} BLOCKED Geoffrey output")
                    st.warning(f"Guardrail Rule {gr_result.rule_triggered}: Geoffrey's response was blocked.")
                    agent_text = (
                        "**[This response was blocked by Guardrails.]**\n\n"
                        "Geoffrey's output was filtered. Please rephrase your request."
                    )

                st.markdown(_message_html(agent_text, "geoffrey-content", "Geoffrey"), unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "geoffrey"})
        elif active_agent == "elena":
            with st.chat_message("assistant", avatar="🧠"):
                st.session_state.log_entries.append("🧠 Invoking Elena (Mentor)")

                # If Rule B was triggered by Chad, prepend warning to Elena's context
                rule_b_prefix = ""
                if st.session_state.get("force_elena_warning", False):
                    rule_b_prefix = (
                        "[SYSTEM NOTICE — RULE B]\n"
                        "Chad previously suggested a destructive operation. "
                        "You MUST warn the user about state mutation risks "
                        "and ask a guiding question about safer alternatives.\n"
                        f"Context: {st.session_state.elena_warning_message}\n\n"
                    )
                    st.session_state.force_elena_warning = False
                    st.session_state.log_entries.append("🧠 Elena prompted with Rule B warning")

                elena_context = f"{ELENA_SYSTEM_PROMPT}\n\n{rule_b_prefix}{workspace_info}"

                if st.session_state["mock_mode"]:
                    agent_text = get_mock_response("elena", workspace_info=workspace_info)
                else:
                    try:
                        if mcp_available and mcp_tools:
                            agent_text = call_with_tools(
                                elena_context, prompt_with_lang, mcp_tools,
                                lambda s, n, a: call_tool_sync(s, n, a),
                            )
                        else:
                            agent_text = call_live_gemini_api(elena_context, prompt_with_lang)
                    except Exception:
                        agent_text = get_mock_response("elena_429", workspace_info=workspace_info)

                # ── Guardrails: Check Elena output (Rule A — Socratic) ─────
                gr_result = run_guardrails("elena", agent_text)
                if gr_result.blocked:
                    st.session_state.log_entries.append(f"🛑 RULE {gr_result.rule_triggered} — Elena code block detected, rerunning")
                    penalty = get_penalty_prompt(gr_result.rule_triggered, "elena")
                    penalty_context = f"{penalty}\n\n{rule_b_prefix}{workspace_info}"
                    if st.session_state["mock_mode"]:
                        agent_text = (
                            "🧠 **ELENA:** Let me rephrase. Rather than writing code directly, "
                            "let's think about the problem conceptually. What specific data "
                            "transformation are you trying to achieve?"
                        )
                    else:
                        try:
                            agent_text = call_live_gemini_api(penalty_context, prompt_with_lang)
                        except Exception:
                            agent_text = (
                                "🧠 **ELENA:** Let's think about this step by step. "
                                "What does your data look like right now?"
                            )
                    st.session_state.log_entries.append("🔄 Elena rerun after Rule A penalty")

                st.markdown(_message_html(agent_text, "elena-content", "Elena"), unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "elena"})

    # Update & persist long-term memory after each turn
    profile = st.session_state["user_profile"]
    profile["session_count"] = profile.get("session_count", 0) + 1
    profile["last_active"] = datetime.datetime.now().isoformat()
    _save_user_profile()


