# VibeOps — Project Description

## The Short Version

I built a multi-agent AI system that teaches data science through conversation. Four characters — a mentor, a reckless junior, a code validator, and a boss — interact with the user in a Streamlit app. The twist? The system actively prevents agents from breaking their own rules. If the mentor accidentally gives code, it gets blocked. If the junior suggests something dangerous, the system forces a warning. It's guardrails all the way down.

## Why This Exists

Here's something every data scientist has done at least once: Googled "handle missing values pandas," found `df.dropna(inplace=True)` on Stack Overflow, copied it, ran it, lost half the dataset, and had zero idea what went wrong. That's vibe coding — writing code that runs but silently destroys your data.

I kept seeing this pattern in junior analysts at work too. They'd ask me questions, I'd explain the risks, they'd nod, and then do the exact same thing next time. Not because they were lazy — because there was no feedback loop. Nobody caught the mistake in the moment.

So I thought: what if an AI team could do that? Not just answer questions, but actively intercept bad habits, force you to think about what you're doing, and refuse to hand you code until you understand the tradeoffs?

## The Four Characters

**Elena** is the mentor. She follows the Socratic method religiously — she'll never write code for you. Ask her how to clean data and she'll respond with "What percentage of your rows have missing values? Have you checked whether the gaps are random or clustered in specific columns?" She's the one who makes you actually understand what's happening.

**Chad** is the junior who thinks `dropna(inplace=True)` is always the answer. He's hyperactive, overconfident, and speaks in "bros." He exists on purpose — as an anti-pattern demonstrator. When he suggests something risky, the system catches it and uses it as a teaching moment.

**Robert** is the MLOps engineer. He's the only one who can run code, and he never does it without asking first. He shows you a plan, the proposed code, waits for your approval, then executes it in a sandbox with a 10-second timeout. He'll also tell you exactly how long it took and what went wrong.

**Geoffrey** is the head of AI. He sets business context and reviews results. He never touches code — he's the one asking "does this actually move the needle on our churn metric?"

## How It Decides Who Talks

When you send a message, the system scans it for patterns. If it sees code (`import`, `df[`, `pd.`), Robert handles it. If you mention a name by name, that agent responds. Everything else goes to Elena by default, because most questions are better answered with guidance than with code.

This isn't just routing — it's a semantic gate that keeps the teaching agent away from raw code and the code agent away from conceptual questions. Different input types need fundamentally different handling.

## The Guardrail System

After every agent response, three rules run automatically:

**Rule A** is the Socratic guardrail. Elena is forbidden from outputting code blocks. If the LLM slips up and generates a ` ```python ``` ` block, the system catches it before you see it, injects a penalty prompt, and makes her rewrite the response. This happens surprisingly often — LLMs are stochastic, even with perfect instructions.

**Rule B** catches destructive code suggestions. When Chad recommends `inplace=True`, `drop()`, or `delete`, the system doesn't block him — it forces Elena to speak next with a specific warning about state mutation risks. His bad suggestion becomes a teachable moment.

**Rule C** blocks toxic language. Simple as that. The system stays professional.

There's also a casual-language allowlist so that normal greetings ("hey bro," "what's up") don't accidentally trigger the toxicity filter. I learned this the hard way when "nice" kept getting blocked.

## Human-in-the-Loop: Vibe Diff

The most important safety feature is Vibe Diff. When Robert generates code, he doesn't run it. Instead, the system shows you the plan and the code, then **locks the chat input**. You literally cannot continue until you click "Approve & Run" or "Reject." Only after approval does the sandbox execute.

This is five lines of orchestrator logic plus twenty lines of Streamlit UI, and it's the single thing that keeps the system safe. Without it, an agent could theoretically run arbitrary code on your machine.

## The Sandbox

Code runs in a completely separate Python subprocess. It has a 10-second hard timeout (no infinite loops), captures all stdout and stderr, and is fully isolated from the main application memory. If something crashes, it can't touch anything else.

## Memory Across Sessions

The system remembers you. A JSON profile in `workspace/user_profile.json` tracks what you've mastered, what you struggle with, and how many sessions you've had. When conversation history gets long (over 20 messages), older turns get compressed into factual summaries like "Chad suggested destructive operation; Elena warned about state mutation." This keeps the token budget under control without losing important context.

## Course Concepts in Action

Day 1's multi-agent architecture shows up in the state machine orchestrator — different input types get routed through completely different pipelines. Day 2's MCP integration connects to DevDocs and Fetch servers for documentation lookup, using the official `mcp` Python SDK on a background event loop. Day 3's token optimization is the compression system that condenses old turns into summaries. Day 4's guardrails are the three-rule engine with penalty prompts. Day 5's sandbox is the isolated subprocess with timeout and Vibe Diff approval.

I also built an ADK-compliant state machine in `adk_graph.py` with validated transitions, and kept all secrets in `.env` with a frozen immutable config class.

## Testing

I wrote 8 unit tests for routing, 13 BDD contract tests for guardrails and behavior, 8 stress tests for the guardrail engine, and a Gherkin feature file with 7 scenarios defining the full system contract. Everything runs without API keys in mock mode.

## What I Learned

The biggest insight is that agent safety is an infrastructure problem, not a prompt problem. You can write the perfect system prompt and the LLM will still occasionally break the rules. Guardrails catch those failures in real time. Vibe Diff keeps the human in control. Sandboxes limit the blast radius. That's what makes the difference between a demo and something you'd actually trust.
