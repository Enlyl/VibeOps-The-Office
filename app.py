import streamlit as st
import sys
import re
sys.stdout.reconfigure(encoding="utf-8")
from llm_interface import call_live_gemini_api, get_mock_response
from sandbox import execute_python_code
from pathlib import Path
import pandas as pd


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


# ── System Prompts ─────────────────────────────────────────────────────────

ELENA_SYSTEM_PROMPT = (
    "[CRITICAL: Always communicate in the language in which the question was asked.] "
    "You are Elena, a senior data science mentor. "
    "[GUARDRAIL: You are forbidden from giving ready-made code solutions like "
    "df[...] or pd.read_csv(). Instead, explain the logic conceptually. "
    "Use metaphors (e.g., 'mask', 'filter') and ask guiding questions "
    "to make the user write the code themselves.]"
)

ROBERT_SYSTEM_PROMPT = (
    "[CRITICAL: Always communicate in the language in which the question was asked.] "
    "You are Robert, an MLOps engineer. "
    "You run code in an isolated sandbox, check for errors, and report results. "
    "When the user gives you code, execute it and explain the output. "
    "Focus on correctness, performance, and reproducibility."
)


def determine_active_agent(user_input: str) -> str:
    """Route user input to the correct agent."""
    text = user_input.lower().strip()

    # 1. Explicit name mention (highest priority)
    if "роберт" in text or "robert" in text:
        return "robert"
    if "елена" in text or "elena" in text:
        return "elena"

    # 2. Code content heuristic
    code_keywords = [
        "выполни", "запусти", "код", "скрипт",
        "sandbox", "ошибка", "traceback",
        "```python", "import ", "def ",
    ]
    if any(kw in text for kw in code_keywords):
        return "robert"

    # 3. Default — Socratic mentor
    return "elena"


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
            .user-content, .elena-content, .robert-content { border: 1px solid #232635; border-radius: 8px; transition: border-color 0.2s ease; }
            .user-content:hover, .elena-content:hover, .robert-content:hover { border-color: #2a2d3a; }
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
            [data-testid="stSelectbox"] label { color: #a6accd; font-size: 12px; }
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
            [data-testid="stSidebar"] .stMarkdown { color: #24292f; }
            [data-testid="stSidebar"] .st-expander {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-bottom: 8px;
            }
            [data-testid="stSidebar"] .st-expander-header { color: #1f2328; font-weight: 600; font-size: 13px; }
            [data-testid="stSidebar"] .stCaption { color: #656d76; font-size: 12px; }
            [data-testid="stSidebar"] .stToggle { margin-bottom: 12px; }
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
                background-color: #1f2428;
                border-left: 3px solid #f66a0a;
                border-radius: 6px;
                padding: 10px 12px;
                font-family: 'SFMono-Regular', 'Menlo', monospace;
                font-size: 11px;
                line-height: 1.5;
                color: #f6f8fa;
                max-height: 300px;
                overflow-y: auto;
            }
            .terminal-line { border-bottom: 1px solid #2b3036; padding: 3px 0; }
            .terminal-line:last-child { border-bottom: none; }
            .user-content, .elena-content, .robert-content { border-radius: 6px; }
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
            [data-testid="chatMessage"] { margin-bottom: 8px; }
            .sandbox-output {
                background-color: #1f2428;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 12px;
                font-family: 'SFMono-Regular', 'Menlo', monospace;
                font-size: 12px;
                color: #f6f8fa;
                max-height: 200px;
                overflow-y: auto;
                white-space: pre-wrap;
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
            [data-testid="stChatInput"] input { color: #24292f; font-family: inherit; }
            [data-testid="stChatInput"] input::placeholder { color: #656d76; }
            [data-testid="stFileUploader"] { background-color: #f6f8fa; border: 1px dashed #d0d7de; border-radius: 6px; padding: 8px; }
            [data-testid="stFileUploader"]:hover { border-color: #0366d6; }
            [data-testid="stSelectbox"] label { color: #656d76; font-size: 12px; }
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
            [data-testid="stSelectbox"] label { color: #7a6a9a; font-size: 12px; }
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
            [data-testid="stSelectbox"] label { color: #cccccc; font-size: 12px; }
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
            [data-testid="stSidebar"] .stCaption { color: #33ff33; font-size: 12px; opacity: 0.8; }
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
            [data-testid="stSelectbox"] label { color: #33ff33; font-size: 12px; opacity: 0.8; }
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


def inject_custom_css() -> None:
    """Alias — applies default theme (Dark Tech)."""
    set_theme("dark-tech")

st.set_page_config(page_title="VibeOps MVP", layout="wide")

# ── State ──────────────────────────────────────────────────────────────────
st.session_state.setdefault("mock_mode", False)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("log_entries", [])
st.session_state.setdefault("sandbox_output", "")
st.session_state.setdefault("theme", "dark-tech")

# Pick up theme widget change (available on subsequent runs)
if "theme_widget" in st.session_state:
    st.session_state["theme"] = st.session_state.theme_widget

set_theme(st.session_state["theme"])

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛠️ VibeOps Cockpit")

    st.toggle(
        "🔌 Offline Simulation Mode",
        key="mock_toggle",
        value=st.session_state["mock_mode"],
    )
    st.session_state["mock_mode"] = st.session_state.mock_toggle

    # ── Agent Skills Matrix ─────────────────────────────────────────────────
    with st.expander("⚙️ Agents", expanded=False):
        st.markdown("**🧠 Elena** — Socratic mentor (questions only, no code)")
        st.markdown("**🔥 Chad** — Vibe coder (`inplace=True`)")
        st.markdown("**🛠️ Robert** — Sandbox (isolated code execution)")
        st.markdown("**👔 Geoffrey** — Head of AI (business goals)")

    # ── Workspace Data ──────────────────────────────────────────────────────
    with st.expander("📁 Data", expanded=False):
        workspace_dir = Path("workspace")
        workspace_dir.mkdir(exist_ok=True)

        uploaded_file = st.file_uploader("csv_upload", type=["csv"], label_visibility="collapsed")
        if uploaded_file is not None:
            with open(workspace_dir / uploaded_file.name, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ {uploaded_file.name}")

        csv_files = sorted(f.name for f in workspace_dir.glob("*.csv"))
        if csv_files:
            selected = st.selectbox("Table", csv_files, label_visibility="collapsed")
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
    elif agent == "elena":
        with st.chat_message("assistant", avatar="🧠"):
            st.markdown(_message_html(msg["content"], "elena-content", "Elena"), unsafe_allow_html=True)
    elif agent == "robert":
        with st.chat_message("assistant", avatar="🛠️"):
            st.markdown(_message_html(msg["content"], "robert-content", "Robert"), unsafe_allow_html=True)
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"])


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

# ── Main: Chat Input ───────────────────────────────────────────────────────
if user_input := st.chat_input("Your message…"):
    text_clean = user_input.strip()

    st.session_state.messages.append({"role": "user", "content": text_clean})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(_message_html(text_clean, "user-content", "You"), unsafe_allow_html=True)

    active_agent = determine_active_agent(text_clean)
    workspace_info = get_workspace_snapshot()

    if active_agent == "robert":
        with st.chat_message("assistant", avatar="🛠️"):
            st.session_state.log_entries.append("🤖 Invoking Robert (Sandbox)")

            # Extract and run code if present
            has_code = (
                "```python" in text_clean
                or text_clean.startswith("import ")
                or text_clean.startswith("def ")
            )
            if has_code:
                match = re.search(r"```python\n?(.*?)```", text_clean, re.DOTALL)
                code = match.group(1).strip() if match else text_clean
                try:
                    result = execute_python_code(code)
                    st.session_state.sandbox_output = result
                    sandbox_note = f"\n\nSandbox output:\n{result[:500]}"
                except Exception as e:
                    sandbox_note = f"\n\nSandbox error:\n{e}"

            robert_context = (
                f"{ROBERT_SYSTEM_PROMPT}\n\n{workspace_info}"
            )

            if st.session_state["mock_mode"]:
                agent_text = get_mock_response("robert", workspace_info=workspace_info)
            else:
                try:
                    agent_text = call_live_gemini_api(robert_context, text_clean)
                except Exception:
                    agent_text = get_mock_response("robert_429", workspace_info=workspace_info)

            if has_code:
                agent_text += sandbox_note

            st.markdown(_message_html(agent_text, "robert-content", "Robert"), unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "robert"})
    else:
        with st.chat_message("assistant", avatar="🧠"):
            st.session_state.log_entries.append("🧠 Invoking Elena (Mentor)")

            elena_context = f"{ELENA_SYSTEM_PROMPT}\n\n{workspace_info}"

            if st.session_state["mock_mode"]:
                agent_text = get_mock_response("elena", workspace_info=workspace_info)
            else:
                try:
                    agent_text = call_live_gemini_api(elena_context, text_clean)
                except Exception:
                    agent_text = get_mock_response("elena_429", workspace_info=workspace_info)

            st.markdown(_message_html(agent_text, "elena-content", "Elena"), unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": agent_text, "agent": "elena"})


# ── Theme Registry ──────────────────────────────────────────────────────────

