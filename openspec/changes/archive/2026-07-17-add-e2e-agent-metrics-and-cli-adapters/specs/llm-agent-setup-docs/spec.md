## ADDED Requirements

### Requirement: Live LLM setup documentation

The `README.md` and `docs/running-against-a-real-model.md` SHALL document how to configure a live LLM run so a user can go from a fresh checkout to a real-model evaluation without guessing. The documentation MUST state that the LiteLLM path rides the `[llm]` extra, MUST name the `AGENTEVAL_MODEL` environment variable used to select the model, and MUST explain that provider API keys are supplied via provider-specific environment variables (never committed, never logged).

#### Scenario: LLM setup section names extra, model var, and keys

- **WHEN** a reader opens `README.md` or `docs/running-against-a-real-model.md` to configure a live LLM run
- **THEN** the documentation states the install command for the `[llm]` LiteLLM extra (e.g. `pip install robotframework-agenteval[llm]`)
- **AND** it documents the `AGENTEVAL_MODEL` environment variable and how it selects the LiteLLM model string
- **AND** it documents that provider API keys are read from provider-specific environment variables sourced from the process environment, not stored in Robot Framework variables that would leak into `log.html`

#### Scenario: LLM install command is runnable

- **WHEN** the documented `[llm]` install command is executed in a clean environment
- **THEN** the command succeeds and installs the LiteLLM dependency, confirming the documented setup is real and not aspirational

### Requirement: Per-CLI coding-agent setup documentation

The setup documentation SHALL, for each coding-agent CLI adapter shipped by this change (claude-code, gemini, codex, opencode, kilo, copilot), document how to install the CLI binary, the adapter slug used to select it, and where the CLI's credentials are configured. DEGRADED-tier adapters (kilo, copilot) MUST be labeled as such so their real-world numbers are never read as full-fidelity.

#### Scenario: Each CLI adapter has install, slug, and credential guidance

- **WHEN** a reader wants to run a scenario through a specific coding-agent CLI
- **THEN** the documentation provides, for that CLI, the command or link to install its binary
- **AND** it names the adapter slug that selects that CLI from a scenario
- **AND** it states where that CLI expects its credentials (the environment variables or credential files it reads)

#### Scenario: Fidelity tier is disclosed per adapter

- **WHEN** a reader consults the CLI-agent setup section for kilo or copilot
- **THEN** the adapter is explicitly marked DEGRADED (best-effort), so a reader knows its tool-call/token/cost numbers are lower-fidelity than FULL/PARTIAL adapters

### Requirement: End-to-end metrics recipe

A recipe under `docs/recipes/` SHALL demonstrate a real agent run that produces tool-call, token, and cost metrics end to end. The recipe MUST show a scenario driving a real agent (LiteLLM or a CLI adapter) and reading the resulting metrics via the shipped metric keywords, and MUST make clear that the captured numbers are ground-truth from the run rather than model self-report.

#### Scenario: Recipe shows a run yielding tool-call, token, and cost numbers

- **WHEN** a reader follows the end-to-end metrics recipe under `docs/recipes/`
- **THEN** the recipe walks through configuring and executing a real agent run
- **AND** it shows reading tool-call metrics, token usage, and cost from the run result using the documented metric keywords
- **AND** it identifies where derived (non-native) cost or token numbers are flagged so real-world numbers are not overstated

### Requirement: Documented commands and examples are runnable and in Robot Framework voice

All setup commands and `.robot` examples in `README.md`, `docs/running-against-a-real-model.md`, and the end-to-end metrics recipe SHALL be runnable and written in the Robot Framework voice (Settings/Test Cases with real keyword calls), and a gate SHALL smoke-execute the documented examples so they cannot silently rot.

#### Scenario: Robot Framework examples resolve and run

- **WHEN** the doc-example gate extracts each `.robot` example from the setup docs and the metrics recipe
- **THEN** every example resolves its keywords (RF `--dryrun`) and, where feasible, executes without error
- **AND** any example referencing a keyword that does not exist fails the gate rather than shipping as a phantom example

#### Scenario: Examples use Robot Framework keyword syntax

- **WHEN** a reader reads a documented example intended to be run from a suite
- **THEN** the example is expressed as Robot Framework keyword calls (not raw Python), consistent with the library's public keyword surface
