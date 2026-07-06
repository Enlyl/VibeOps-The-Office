# VibeOps — Multi-Agent Data Science Assistant

**VibeOps** is a multi-agent AI assistant that simulates a Data Science team to teach safe data analysis. Built as the capstone for the **Kaggle 5-Day AI Agents Intensive with Google**.

---

## Architecture

```
User Input
    |
    v
[Bilingual Ambiguity Interceptor]
  - Detects "show me table" / "покажи таблицу"
  - If ambiguous -> file selection buttons
  - If filename specified -> routes to agents
    |
    v
[Semantic Router]
  - Code/Data query (df[...], pd., import) -> Robert
  - Chat/Question -> Chad -> Elena -> Guardrails
    |
    v
[Agent Execution]
  +-- Robert -> generates Python code
  |     +-- Vibe Diff (Approve/Reject) -> Sandbox
  +-- Chad -> vibe coder (triggers Rule B)
  +-- Elena -> Socratic mentor (Rule A enforced)
  +-- Geoffrey -> business review
    |
    v
[Guardrails]
  - Rule A: no code blocks from Elena
  - Rule B: destructive ops -> Elena warns
  - Rule C: toxicity filter
    |
    v
[Output + Memory Update]
  - Short-term: sliding window (10 turns)
  - Long-term: user_profile.json
  - Context compression on overflow
```

---

## The Team

| Agent | Role | Personality |
|---|---|---|
| **Elena** | Senior Mentor | Socratic method, asks questions, never gives code |
| **Chad** | Junior Vibe Coder | Hyperactive, suggests quick destructive solutions |
| **Robert** | MLOps Engineer | Generates code, sandbox execution, metrics |
| **Geoffrey** | Head of AI | Business goals, final review, no code |

---

## Features

- **Multi-Agent Routing** — code queries go to Robert, chat to Chad+Elena
- **Bilingual Detection** — regex-based, supports English and Russian keywords
- **Vibe Diff (HITL)** — Robert's code requires user approval before execution
- **Sandbox** — isolated subprocess, 10s timeout, stdout/stderr capture
- **Guardrails** — Socratic (A), destructive ops (B), toxicity (C)
- **MCP Tools** — DevDocs search, web fetch, workspace file access
- **English-only** — all agents respond in English regardless of input
- **5 Themes** — Dark Tech, Light Paper, Cyberpunk, ZX Spectrum, Retro CRT
- **Memory** — short-term (10-turn window) + long-term (JSON profile)
- **Context Compression** — auto-summarizes overflow history

---

## Quick Start

```bash
pip install streamlit google-genai pandas python-dotenv
echo GEMINI_API_KEY=your-key-here > .env
streamlit run app.py
```

Open **http://localhost:8501**

---

## Project Structure

| File | Role |
|---|---|
| `app.py` | Streamlit UI |
| `router.py` | Semantic routing |
| `guardrails.py` | Rules A/B/C, language directive |
| `llm_interface.py` | Gemini API + mock mode |
| `sandbox.py` | Code execution sandbox |
| `mcp_manager.py` | MCP server connections |
| `config.py` | .env config loader |
| `orchestrator.py` | ADK graph workflow |
| `test_agents.py` | 8 routing tests |
| `test_lang.py` | 9 language tests |
| `test_bdd.py` | BDD contract tests |
| `kaggle_submission/` | Writeups, script, screenshots |

---

## Kaggle Submission

- **Track**: Agents for Business / Freestyle
- **Writeup**: `kaggle_submission/PROJECT_DESCRIPTION.md` (EN) / `PROJECT_DESCRIPTION_RU.md` (RU)
- **Video Script**: `kaggle_submission/VIDEO_SCRIPT.md`
- **Concepts**: Multi-Agent, Guardrails, Sandbox + Vibe Diff (HITL)
