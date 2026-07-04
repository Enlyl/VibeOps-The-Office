# VibeOps — Project Documentation

> **Type**: Capstone Project — [Kaggle 5-Day AI Agents Intensive: Vibe Coding with Google](https://www.kaggle.com/learn-guide/5-day-agents-vibecoding)
> **Stack**: Python · Google Gemini API (`gemini-2.5-flash`) · Streamlit · Google ADK (Graph Workflow)
> **Entry point**: `app.py` → `streamlit run app.py`
> **Status**: Production-ready, fully functional

---

## Quick orientation for AI agents

This is a **multi-agent educational chatbot** simulating a Data Science team at a fictional company called VibeOps. The user types questions or code; the orchestrator routes them to the appropriate AI agents; agents respond according to strict pedagogical and safety rules. The UI is a Streamlit web app.

The **single source of truth for agent roles** is `AGENTS.md`.
The **8-pillar engineering spec** is in `ARCHITECTURE.md`.
The **BDD contract** (all test scenarios) is in `vibeops_simulation.feature`.

---

## 1. Purpose & Role

### What it does
VibeOps teaches safe, professional Data Science practices through **interactive multi-agent dialogue**. Each user interaction is handled by a team of AI agents who respond according to their role, guardrails, and a shared memory context.

### Educational philosophy
The system is built around the **Socratic Method**: the mentor agent (Elena) never gives direct answers or ready-to-use code. Instead, she asks guiding questions that lead the user to the answer themselves. This prevents "copy-paste learning" and builds genuine understanding.

The antagonist pattern is **"Vibe Coding"** — represented by Chad (the Junior Data Scientist), who intentionally suggests fast, risky, destructive solutions. The system's guardrails intercept these suggestions and use them as teachable moments.

### Target audience
- Beginners learning Pandas / Data Science
- Students studying safe data mutation practices
- Engineers learning MLOps thinking (code validation, sandboxing, human approval)

---

## 2. Core Concepts

| Concept | Implementation |
|---|---|
| **Multi-Agent Routing** | `Stage` enum + `_contains_code()` regex → routes to Robert (code) or Chad→Elena (chat) |
| **Stateless Agents** | Each agent receives `MemoryContext` on every call; no instance state is kept |
| **File Bus Pattern** | `MemoryContext` is the single shared state object passed between all agents |
| **Socratic Guardrail** | Rule A: Elena is blocked if she outputs a `python` code block |
| **Human-in-the-Loop** | Vibe Diff: Robert proposes code, UI waits for user approval before sandbox execution |
| **Long-term Memory** | `workspace/user_profile.json` persists progress across sessions via MCP |
| **Token Optimization** | History >10 turns is compressed into `system_facts` (Pillar 7) |

---

## 3. Architecture

### 3.1 State Machine (Orchestrator)

```
User Input
    │
    ▼
ANALYSIS_STAGE
    ├── contains code? (import/df[/pd./np./def/=)
    │       YES ──────────────────────────► AGENT_ROBERT
    │                                           │
    │                                    vibe_diff_approved?
    │                                     NO ──► ⏸ VIBE DIFF
    │                                            (UI blocks, awaits ✅/❌)
    │                                     YES ──► execute_python_code (Sandbox)
    │
    └── chat/question?
            YES ──────────► AGENT_CHAD ──► AGENT_ELENA
                                               │
                                               ▼
                                      VERIFICATION_STAGE
                                      (LLM-as-Judge / Rules A/B/C)
                                               │
                                               ▼
                                         OUTPUT_STAGE
                                         (memory update + render)
```

### 3.2 Components

| File | Class / Key Functions | Responsibility | Pillar |
|---|---|---|---|
| `orchestrator.py` | `Orchestrator`, `MemoryContext`, `Stage`, agents | Core state machine, routing, memory management | 1, 2 |
| `guardrails.py` | `run_guardrails()`, `compress_context()` | Post-generation validation (Rules A/B/C), token compression | 6, 7 |
| `sandbox.py` | `LocalPythonSandbox`, `execute_python_code()` | Isolated Python subprocess execution with timeout | 4 |
| `mcp_client.py` | `list_workspace_directory()`, `read_workspace_file()`, `write_workspace_file()` | MCP-style filesystem access (read-only to `./workspace/`) | 3 |
| `llm_interface.py` | `LLMClient`, `MockLLMClient` | Gemini API client with retry logic; mock for offline/SIM mode | 2, 8 |
| `config.py` | `AppConfig` (frozen dataclass), `get_config()`, `config()` | Secure secrets loader; single source of all constants | 8 |
| `app.py` | `render_sidebar()`, `render_chat()`, Vibe Diff UI | Streamlit UI: themes, chat, sidebar cockpit, Vibe Diff form | — |
| `prompts/*.txt` | System instructions per agent | Loaded at session start by `PromptLoader` | 1 |
| `workspace/` | `dirty_data.csv`, `model_docs.md`, `user_profile.json` | Dataset + docs (read-only MCP); long-term memory (writable) | 3, 5 |

### 3.3 Memory Model

```
MemoryContext (shared state / File Bus)
├── short_term: list[AgentTurn]     ← sliding window, max 10 turns
├── system_facts: list[str]         ← compressed facts when window overflows
├── current_input: str              ← raw user message for active turn
├── current_route: Stage            ← routing decision for this turn
├── turn_index: int                 ← monotonically increasing counter
├── system_instructions: dict       ← agent_name → prompt text (loaded at start)
├── mock_mode: bool                 ← True=SIM (MockLLMClient), False=API (Gemini)
├── long_term_profile: dict         ← persisted to workspace/user_profile.json
└── vibe_diff_approved: bool        ← Human-in-the-Loop gate for sandbox execution
```

**Short-term Memory**: Last 10 `AgentTurn` objects. Passed as conversation history to every agent on each turn.

**Compression** (Pillar 7): When `len(short_term) > 10`, the oldest turn is popped and summarized as a string in `system_facts`. These facts are prepended to every future prompt as context.

**Long-term Profile** (Pillar 5): JSON file at `workspace/user_profile.json`. Auto-created on first run. Updated after every turn via `write_workspace_file()`. Tracks: sessions, mastered concepts, struggles, compressed facts.

---

## 4. Agents

### 🧠 Elena — Senior Data Scientist & Team Mentor

| Attribute | Value |
|---|---|
| **ADK node** | `elena_node` |
| **Tone** | Calm, analytical, encouraging, intellectually rigorous |
| **Method** | Strict Socratic Method — only asks questions, never gives direct code or answers |
| **Tools (AFC)** | `list_workspace_directory`, `read_workspace_file` |
| **Triggered by** | Always follows Chad; also triggered by Rule B (Chad's destructive code) |
| **BLOCKED by Rule A** | Any output containing ` ```python ``` ` → rollback → penalty prompt → rerun |
| **Prompt file** | `prompts/elena.txt` |

Elena is the **primary pedagogical agent**. When Chad proposes a dangerous solution, Elena asks guiding questions about edge cases, data distributions, and state mutation — without directly criticizing Chad or giving the answer.

---

### 🔥 Chad — Junior Data Scientist (Vibe Coder)

| Attribute | Value |
|---|---|
| **ADK node** | `chad_node` |
| **Tone** | Hyperactive, overconfident. Uses: "bro", "vibe", "just", "Stack Overflow" |
| **Method** | Fastest, often destructive solutions; intentionally an anti-pattern |
| **Tools** | None |
| **Triggered by** | Any non-code user input (speaks first); also follows Robert on code path |
| **Triggers Rule B** | Any suggestion of `inplace=True`, `drop`, `delete` → forces Elena to warn |
| **Triggers Rule C** | Toxic phrases → immediate BLOCK |
| **Prompt file** | `prompts/chad.txt` |

Chad **stress-tests the guardrails system** and demonstrates the "vibe coding" anti-pattern. His output is always validated by the Verification Stage before reaching the user.

---

### 🛠️ Robert — MLOps Engineer & Code Validator

| Attribute | Value |
|---|---|
| **ADK node** | `robert_node` |
| **Tone** | Pedantic, direct, risk-averse, obsessed with logs and TDD |
| **Method** | Validates and sandboxes code; reports metrics |
| **Tools (AFC)** | `list_workspace_directory`, `read_workspace_file`; `execute_python_code` (only when `vibe_diff_approved=True`) |
| **Triggered by** | Code patterns in user input: `import`, `df[`, `pd.`, `np.`, `def`, `=` |
| **Vibe Diff gate** | On first run (`vibe_diff_approved=False`): generates plan only, no execution |
| **Prompt file** | `prompts/robert.txt` |

Robert enforces **Human-in-the-Loop** safety. On the first pass, he generates a Vibe Diff (plan + code). The UI blocks further input until the user clicks ✅ Approve or ❌ Reject. On ✅, he reruns with `execute_python_code` available and produces a full technical report (time, stdout, stderr, tracebacks).

---

### 👔 Geoffrey — Head of AI & Analytics

| Attribute | Value |
|---|---|
| **ADK node** | `geoffrey_node` |
| **Tone** | Professional, authoritative, pragmatic, demanding but fair |
| **Method** | Sets business goals; reviews final metrics |
| **Tools** | None |
| **Triggered by** | Session start; final metrics review |
| **NEVER** | Writes, suggests, or explains Python code |
| **Prompt file** | `prompts/geoffrey.txt` |

---

## 5. Guardrails System

**File**: `guardrails.py`
**Triggered**: After every agent turn, in `VERIFICATION_STAGE`

```python
def run_guardrails(turns: List[AgentTurn]) -> Tuple[List[AgentTurn], Dict[str, bool]]:
    ...
```

### Rules

| Rule | Source Agent | Trigger | Action |
|---|---|---|---|
| **Rule A** — Socratic Guardrail | Elena | ` ```python ``` ` in output | `turn.blocked = True` → penalty prompt injected → Elena reruns |
| **Rule B** — Destructive Code | Chad | `inplace=True`, `drop`, `delete` in output | Flag `force_elena_warning=True` → Elena must warn next turn |
| **Rule C** — Toxicity | Chad, Geoffrey | Words: `stupid`, `idiot`, `moron`, `shut up`, `trash` | `turn.blocked = True` immediately |

### Token Optimizer

```python
def compress_context(memory_turns, max_history=10) -> List[str]:
    ...
```

When `len(short_term) > 10`, pops oldest turns and summarizes them:
`"[CHAD]: Just do df.dropna(inpl..."` → appended to `memory.system_facts`.

---

## 6. MCP Tools (Filesystem Access)

**File**: `mcp_client.py`
**Workspace root**: `./workspace/` (absolute: `Path(__file__).parent / "workspace"`)
**Security**: Directory traversal blocked (`..`, `/`, `\` in filename → `[Error]`)

| Function | Signature | Access | Used by |
|---|---|---|---|
| `list_workspace_directory()` | `() → list[str]` | Read | Elena, Robert (AFC tools) |
| `read_workspace_file(file_name)` | `(str) → str` | Read | Elena, Robert (AFC tools) |
| `write_workspace_file(file_name, content)` | `(str, str) → str` | Write | Orchestrator (profile save only) |

The Gemini API receives these as **Automatic Function Calling (AFC)** tools. When the model decides to call them, the SDK executes the Python function and injects the result back into the conversation automatically.

---

## 7. Sandbox

**File**: `sandbox.py`

```python
class LocalPythonSandbox:
    def execute(self, code: str) -> SandboxResult: ...
```

- Uses `multiprocessing.get_context('spawn')` — Windows-compatible, isolated memory
- Hard timeout: **10 seconds** (`config().sandbox_timeout`)
- Captures: `stdout`, `stderr`, `traceback`, `execution_time_sec`, `timed_out`
- Exposed as AFC tool `execute_python_code(code: str)` for Robert

```python
@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    error: Optional[str]
    traceback: Optional[str]
    execution_time_sec: float
    timed_out: bool
```

---

## 8. LLM Interface

**File**: `llm_interface.py`

### `LLMClient` (Live API)
- Uses `google-genai` SDK: `genai.Client(api_key=...)`
- Model: `gemini-2.5-flash` (default, from `config().gemini_model`)
- AFC: tools list → `FunctionCallingConfig`
- If no tools: `FunctionCallingConfig(mode="NONE")` — prevents hallucinated tool calls
- **Retry on 429** RESOURCE_EXHAUSTED: 3 attempts, base wait 62s, linear backoff

### `MockLLMClient` (SIM mode)
- No API calls; returns canned responses per agent
- Deliberately triggers Rule A (Elena outputs code with 20% probability) for demo
- Used when `mock_mode=True` in session state

---

## 9. Configuration

**File**: `config.py`

```python
@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str          # from GEMINI_API_KEY env var (NEVER log)
    gemini_model: str            # default: "gemini-2.5-flash"
    token_limit: int             # 1_000_000
    memory_window: int           # 10 turns
    sandbox_timeout: int         # 10 seconds
    mcp_dirty_data_path: str     # "./workspace/dirty_data.csv"
    mcp_model_docs_path: str     # "./workspace/model_docs.md"
```

- **Immutable** (`frozen=True`) — cannot be mutated at runtime
- **Singleton** via `config()` — cached after first load
- **API key masked** in `__repr__`: `AQ.Ab8...RehQ`
- **Fail-fast**: `sys.exit(1)` if `GEMINI_API_KEY` is missing

---

## 10. Vibe Diff (Human-in-the-Loop)

Vibe Diff is the approval flow for code execution. It prevents Robert from running arbitrary code without explicit user consent.

### Flow

```
1. User sends code/data query
2. ANALYSIS_STAGE → routes to AGENT_ROBERT
3. RobertAgent.run() checks vibe_diff_approved:
   - False → tools=[list_workspace, read_workspace] only
             generates plan + proposed code (NO execution)
   - True  → tools=[..., execute_python_code]
             runs code in sandbox, reports results

4. If False (first pass):
   - Orchestrator sets st.session_state.vibe_diff_processing = True
   - UI renders: ✅ "Approve Code Execution" | ❌ "Reject Plan"
   - st.chat_input is DISABLED

5a. User clicks ✅:
   - vibe_diff_processing = False
   - Orchestrator reruns with vibe_diff_approved=True
   - Robert executes in sandbox

5b. User clicks ❌:
   - vibe_diff_processing = False
   - last_prompt cleared, state reset
```

### State in `MemoryContext`
```python
vibe_diff_approved: bool = False  # set by Orchestrator before each Robert call
```

---

## 11. File Structure

```
vibeops/main/
│
├── app.py                     # Streamlit UI — 893 lines
│                              # Themes, chat render, sidebar, Vibe Diff UI
│
├── orchestrator.py            # Core orchestrator — 801 lines
│                              # Stage enum, MemoryContext, all 4 agents,
│                              # routing logic, long-term profile management
│
├── guardrails.py              # Guardrail engine — 99 lines
│                              # Rules A/B/C, compress_context()
│
├── sandbox.py                 # Python sandbox — 164 lines
│                              # LocalPythonSandbox, _worker(), SandboxResult
│
├── mcp_client.py              # MCP filesystem — 80 lines
│                              # list/read/write workspace file
│
├── llm_interface.py           # Gemini API client — 217 lines
│                              # LLMClient, MockLLMClient, retry logic
│
├── config.py                  # Secure config — 190 lines
│                              # AppConfig frozen dataclass, get_config()
│
├── prompts/
│   ├── chad.txt               # Chad system prompt (~852 bytes)
│   ├── elena.txt              # Elena system prompt (~875 bytes)
│   ├── geoffrey.txt           # Geoffrey system prompt (~839 bytes)
│   └── robert.txt             # Robert system prompt (~928 bytes)
│
├── workspace/
│   ├── dirty_data.csv         # Training dataset with intentional errors
│   ├── model_docs.md          # Model documentation (read-only via MCP)
│   └── user_profile.json      # Long-term memory (auto-created, writable)
│
├── guardrails/
│   └── output_filter.txt      # Guardrail spec document
│
├── AGENTS.md                  # ← Single source of truth for agent roles
├── ARCHITECTURE.md            # ← 8-pillar engineering specification
├── PROJECT.md                 # ← This file
├── vibeops_simulation.feature # BDD Gherkin contract
├── README.md                  # Kaggle submission overview
├── run.bat                    # Windows launch script
├── generate_data.py           # Utility to regenerate dirty_data.csv
├── .env                       # Secrets (NOT in git)
├── .gitignore                 # .env, __pycache__, etc.
└── .streamlit/                # Streamlit server config
```

---

## 12. Kaggle Intensive Pillars Compliance

| Pillar | Topic | Implementation | Status |
|---|---|---|---|
| **1** | Multi-Agent Architecture & Semantic Gating | `Stage` enum, `_contains_code()`, regex routing in `ANALYSIS_STAGE` | ✅ |
| **2** | Google ADK Framework (Stateless Agents, File Bus) | `MemoryContext` as File Bus, dependency injection via `__init__` | ✅ |
| **3** | MCP Servers (Isolated Filesystem Access) | `mcp_client.py`, anti-traversal guards, typed Google docstrings for AFC | ✅ |
| **4** | Advanced Tool Use (Sandbox Execution) | `LocalPythonSandbox`, `multiprocessing.spawn`, 10s timeout, stdout/stderr capture | ✅ |
| **5** | Agent Memory (Short-term + Long-term) | Sliding window 10 turns + `workspace/user_profile.json` via `write_workspace_file` | ✅ |
| **6** | Evaluation & Guardrails (LLM-as-Judge) | Rules A/B/C in `guardrails.py` + Vibe Diff Human-in-the-Loop | ✅ |
| **7** | Context Engineering (Token Optimization) | `compress_context()`, 1M token budget in `AppConfig` | ✅ |
| **8** | Security (No Hardcoded Secrets) | `frozen dataclass`, `.env` via `python-dotenv`, key masking in `__repr__` | ✅ |

---

## 13. Setup & Run

### Prerequisites
```bash
pip install streamlit google-genai pandas python-dotenv
```

### `.env` file (required)
```env
GEMINI_API_KEY=your-key-from-aistudio.google.com
GEMINI_MODEL=gemini-2.5-flash
```

### Launch
```bash
# Windows
.\run.bat

# or directly
streamlit run app.py
```

### Environment variable for Windows (UTF-8 fix)
```bash
set PYTHONUTF8=1
streamlit run app.py
```

### Access
- Local: http://localhost:8501
- The app starts in **API Mode** by default (`mock_mode=False`)

---

## 14. Session State Keys (Streamlit)

| Key | Type | Default | Purpose |
|---|---|---|---|
| `orchestrator` | `Orchestrator` | `Orchestrator()` | Core engine instance |
| `chat_history` | `list[dict]` | `[]` | Rendered message list for UI |
| `mock_mode` | `bool` | `False` | SIM vs API mode toggle |
| `active_csv` | `str \| None` | `None` | Currently selected workspace CSV |
| `active_agent` | `str \| None` | `None` | Last agent that ran (for UI indicator) |
| `last_prompt` | `str` | `""` | Last user input (for Vibe Diff rerun) |
| `vibe_diff_processing` | `bool` | `False` | True = UI blocked, awaiting Vibe Diff approval |

---

## 15. Key Design Decisions

| Decision | Rationale |
|---|---|
| `multiprocessing.spawn` in Sandbox | Windows-compatible; full memory isolation from main process |
| `frozen dataclass` for `AppConfig` | Prevents accidental mutation of config at runtime |
| `FunctionCallingConfig(mode="NONE")` | Prevents Gemini from hallucinating tool calls when no tools are provided |
| `Stage` enum instead of strings | Type safety, readable logs, prevents typos in transition logic |
| `vibe_diff_approved` in `MemoryContext` | No global state; clean UI/logic separation; rerun-safe |
| `st.html()` instead of `st.markdown()` | Fixes CSS rendering regression in newer Streamlit versions |
| `gemini-2.5-flash` as default | 1500 req/day free tier vs 20 for older models — critical for classroom use |
| `setdefault()` for all session state | Prevents `KeyError` on Streamlit page refresh / hot-reload |
