Feature: VibeOps Multi-Agent Orchestrator Simulation
  As a Data Science student
  I want to interact with a multi-agent team
  So that I can safely learn Pandas and data science concepts without breaking the state.

  Background:
    Given the VibeOps orchestrator is initialized with mock mode active
    And the workspace directory contains "dirty_data.csv"

  Scenario: Route user code request through Robert with Vibe Diff pending approval
    When the user sends the message "Загрузи таблицу dirty_data.csv и покажи распределение пропусков"
    Then the orchestrator should route to Stage AGENT_ROBERT
    And Robert should return a pending Vibe Diff plan and proposed Python code
    And the orchestrator should stop execution before running the sandbox
    And the UI chat input should be disabled waiting for approval

  Scenario: Execute approved code in Sandbox
    Given a pending Vibe Diff execution for "dirty_data.csv" is displayed
    When the user clicks the "Approve Code Execution" button
    Then the orchestrator should run Robert with vibe_diff_approved set to true
    And Robert should execute the script inside the LocalPythonSandbox
    And the execution output metrics should be appended to the final response
    And the orchestrator should proceed through Chad and Elena turns

  Scenario: Enforce Rule A (Socratic Guardrail) on Elena
    When Elena tries to output a markdown code block containing Python code
    Then the guardrail engine should detect a Rule A violation
    And the orchestrator should rollback Elena's turn
    And inject a SYSTEM PENALTY instruction
    And force Elena to rewrite her response without code blocks

  Scenario: Enforce Rule B (Destructive Code warning) on Chad
    When Chad suggests a destructive operation like "inplace=True" or "drop"
    Then the guardrail engine should flag a Rule B warning
    And the orchestrator must force Elena to warn the user about data state mutation
