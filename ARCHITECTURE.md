# VibeOps Core Architecture & System Constraints

## Role Definition
Target: VibeOps Core Workflow Orchestrator & Harness Engine.
Purpose: Manage the lifecycle, routing, memory, and safety of a multi-agent session based on Google ADK 2.0, MCP, and BDD specifications. The underlying execution loop processes user input, coordinates 4 agents (Geoffrey, Chad, Elena, Robert), manages external data via MCP, executes sandboxed code, and enforces strict Guardrails.

The system MUST strictly adhere to the following 7 pillars of Agentic Engineering:

=====================================================================
1. MULTI-AGENT ARCHITECTURE (Routing Rules & Semantic Gating)
=====================================================================
The Orchestrator must direct traffic using the following state machine:
- INPUT_STAGE: Receive message from User.
- ANALYSIS_STAGE: 
    * If User input contains code patterns (e.g., 'df[', 'pd.', '=', 'import'), route IMMEDIATELY to Robert.
    * If User input is a question or chat text, route to Chad first, then pass Chad's output directly to Elena.
- VERIFICATION_STAGE (Semantic Gating): An LLM-as-judge agent must verify the combined response candidate for compliance with security rules and absence of hallucinations before issuing it to the user.
- OUTPUT_STAGE: Display the validated message to the User and update short-term memory.
*Constraint:* Agent roles and the Orchestrator's task graph must be documented in a central `AGENTS.md` file. All core interaction scenarios must be definable in Gherkin BDD (Given/When/Then) format.

=====================================================================
2. GOOGLE ADK FRAMEWORK COMPLIANCE
=====================================================================
- Maintain state transitions strictly using official Google ADK Workflow abstractions.
- Use ADK 2.0 Graph Workflow to configure transitions between nodes. State transfer must occur via File Bus (pass pointers to files, never heavy raw data in the prompt).
- Every agent instance must remain completely stateless. The explicit MemoryContext block must be passed on every turn execution.
- Turn transitions must be logged in the system console for debugging.

=====================================================================
3. MCP SERVERS (Context Access & Interfaces)
=====================================================================
- The active MCP Filesystem Server connection status must be verified before executing any agent turn.
- Agents must have read-only access to './workspace/dirty_data.csv' and './workspace/model_docs.md' exclusively through the MCP protocol.
- Hallucination of file structures is strictly prohibited; agents must rely entirely on the directory tree provided by the MCP server.
- *Constraint:* All function-calling interfaces must include detailed docstrings and explicit Type Hints to ensure reliable LLM execution.

=====================================================================
4. ADVANCED TOOL USE (Sandbox Execution)
=====================================================================
- When Robert receives a code block, the 'LocalPythonSandbox' tool must be triggered.
- All generated or executable code must run in an isolated, ephemeral sandbox (e.g., a gVisor simulation) to limit the blast radius.
- Execution must capture all stdout, stderr, and tracebacks, returning raw data to Robert for response formatting.
- Infinite loops must be prevented by enforcing a strict 10-second execution timeout.

=====================================================================
5. AGENT MEMORY MANAGEMENT
=====================================================================
- Short-term Memory: Maintain a linear sliding window of the last 10 messages in the current session.
- Long-term Memory: Track user progress across sessions. A summary of mastered concepts or struggles must be saved in a local profile file via MCP.

=====================================================================
6. EVALUATION & GUARDRAILS (Safety & Contract Enforcement)
=====================================================================
A strict post-generation check must be executed on every agent's output:
- Rule A (Socratic Guardrail): If Elena's generated text contains a code block (```python ... ```), INTERCEPT IT. Do not show it to the user. Rollback her state, issue a system penalty prompt, and force a rerun.
- Rule B (Destructive Code Guardrail): If Chad suggests a destructive operation (e.g., 'inplace=True'), the Workflow must force Elena to speak next to explicitly warn the user.
- Rule C (Toxicity Guardrail): Block any offensive or toxic phrases from Chad or Geoffrey. The environment must remain strictly professional.
- Vibe Diff Mechanism: Before executing critical actions, the agent must output a human-readable description of the planned steps for user confirmation (Human-in-the-loop).

=====================================================================
7. CONTEXT ENGINEERING & TOKEN OPTIMIZATION
=====================================================================
- Token usage for the active model must be strictly monitored. The hard limit for the active context window is 1,000,000 tokens.
- If history length > 10 messages, trigger a token-compression routine: condense older dialogue turns into concise historical facts (e.g., 'User successfully handled missing values in column A').
- System behavior must be continuously validated against the Gherkin BDD contract ('vibeops_simulation.feature'). Any violation of a 'Then' clause must be marked as a test failure in system logs.

=====================================================================
8. SECURITY & SECRETS MANAGEMENT
=====================================================================
- API keys (including the strictly required Gemini API key) and sensitive credentials MUST NEVER be hardcoded into the source code, agent prompts, or configuration dictionaries.
- All secrets must be dynamically loaded from a localized, non-public configuration file (e.g., `.env`).
- The secrets file MUST be strictly excluded from version control (e.g., explicitly listed in `.gitignore` before any commits).
- Agents and the Orchestrator must access the Gemini API key exclusively via environment variables (e.g., `os.getenv()`) at runtime, preventing accidental leakage in logs or chat outputs.