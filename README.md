#VibeOps — Multi-Agent Data Science Assistant

VibeOps is an educational multi-agent simulation dashboard designed to safely guide users through data science, table cleaning, and validation workflows. It demonstrates state-of-the-art patterns in AI agent architectures, sandboxing, Model Context Protocol (MCP), and custom output guardrails.

Built as the Capstone Project for the **Kaggle 5-Day AI Agents Intensive Course with Google**, VibeOps implements a spec-driven, observable development workflow using Google Gemini API.

---

## Architecture Overview

VibeOps utilizes a 5-stage orchestration pipeline built on a state machine:

`
                  USER INPUT
                      ¦
                      ¡
               ANALYSIS STAGE
               (Semantic Gating)
               +-- Code Query ---------> Robert (Sandbox Engine)
               ¦                             ¦ (requires User approval)
               ¦                             ¡
               ¦                        [VIBE DIFF]
               ¦                             ¦ (Approved)
               ¦                             ¡
               ¦                        [SANDBOX RUN] 
               ¦                             ¦
               ¦                             ¡
               L-- Chat / Q&A ---------> Chad (Vibe Coder)
                                             ¦
                                             ¡
                                         Elena (Socratic Mentor)
                                             ¦
                                             ¡
                                     VERIFICATION STAGE
                                     (LLM-as-Judge & Guardrails)
                                     +-- Rule A: Socratic Violation -> Rollback & Rerun
                                     +-- Rule B: Destructive warning -> Force warning
                                     L-- Rule C: Toxicity check -> Block
                                             ¦
                                             ¡
                                         USER VIEW
`

---

## The Data Squad (Agent Roster)

1. **?? Elena (Senior Mentor & Scientist)**: Uses the Socratic method to ask guiding questions about data distributions, missing values, and pandas APIs. **Never** provides ready-to-use code blocks.
2. **?? Chad (The Vibe Coder)**: Junior data scientist representing the "vibe coding" anti-pattern. Suggests quick, sometimes destructive solutions (like inplace=True) to stress-test guardrails.
3. **??? Robert (Sandbox Engineer)**: MLOps engineer obsessed with logs and TDD. Runs proposed Python code against local files in an isolated environment.
4. **?? Geoffrey (Head of Analytics)**: demanding but fair business lead focusing on metrics, data security, and tight deadlines. Does not write code.

---

## ??? Core Features (Intensive Capstone Topics)

*   **Pillar 3: Model Context Protocol (MCP)**: Custom implementation in mcp_client.py providing isolated read-only and write-only filesystem tools for ./workspace/ to prevent hallucinations.
*   **Pillar 4: Safe Sandboxed Code Execution**: LocalPythonSandbox in sandbox.py runs Python code in an isolated subprocess with a hard 10-second timeout, capturing stdout, stderr, and tracebacks.
*   **Pillar 5 & 7: Short-term Memory & Token Optimization**: Maintains a 10-turn sliding window. Older dialogue is condensed into system facts dynamically to preserve the token budget.
*   **Pillar 5: Long-term Memory (MCP Profile)**: Masters user progress across sessions. Struggles (e.g. Socratic violations) and Mastered Concepts (e.g. successful sandboxing) are serialized to workspace/user_profile.json and rendered in the sidebar.
*   **Pillar 6: Semantic Output Guardrails**:
    *   **Rule A (Socratic Guardrail)**: Intercepts Elena's response if it contains a code block, rolls back the turn, issues a system penalty, and forces a rerun.
    *   **Rule B (Destructive Code Guardrail)**: If Chad suggests destructive code (e.g. inplace=True), forces Elena to warn the user on the next turn.
    *   **Rule C (Toxicity Guardrail)**: Filters toxic or offensive phrases from Chad or Geoffrey before display.
*   **Human-in-the-Loop (Vibe Diff)**: Before executing code in the Sandbox, the Orchestrator stops and outputs a Vibe Diff containing the proposed code and a plan. The UI blocks input and requests approval.
*   **?? Simulation Mode (Offline client)**: A robust MockLLMClient in llm_interface.py simulates agent dialogue, guardrail violations, and physical sandbox runs without calling the Gemini API.

---

## How to Run

1.  **Clone the workspace** and navigate to the directory.
2.  Create a .env file in the root directory:
    `env
    GEMINI_API_KEY="your-google-gemini-api-key"
    GEMINI_MODEL="gemini-3.5-flash"
    `
3.  Install dependencies:
    `ash
    pip install streamlit google-genai pandas python-dotenv
    `
4.  Run the application:
    `ash
    streamlit run app.py
    `

---

## Gherkin BDD Contracts
All orchestration paths are validated against Gherkin criteria defined in ibeops_simulation.feature.
