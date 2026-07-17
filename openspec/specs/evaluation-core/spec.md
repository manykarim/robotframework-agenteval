# evaluation-core Specification

## Purpose
The shared internal spine every surface rides - the tier model (deterministic/LLM/agent), the coding-agent adapter seam and single LiteLLM adapter, the LLM judge, the stats runner (run-N / pass@k / Wilson CI), the trace/evidence projection, the slim error hierarchy, the four-library packaging with dependency extras, and the Robot Framework voice.

## Requirements

### Requirement: Three test modes are encoded once via a tier marker

The shared spine SHALL provide a single `@tier(1|2|3)` marker that classifies every public keyword as Tier-1 (deterministic — no model), Tier-2 (LLM judge), or Tier-3 (coding agent). Each of the four surface libraries SHALL reuse this one marker; no surface reimplements the mode concept. A `Get Keyword Tier` keyword SHALL report the tier of a named keyword.

#### Scenario: Tier is discoverable per keyword

- **WHEN** a user calls `Get Keyword Tier    Fire Hook Event`
- **THEN** the library returns `1` because firing a synthetic hook event needs no model

#### Scenario: The same marker classifies an agent-mode keyword

- **WHEN** a user calls `Get Keyword Tier    Get Routing Pass At K`
- **THEN** the library returns `3` because the keyword drives a real coding agent

### Requirement: One coding-agent adapter seam with a single generic adapter

The spine SHALL define an `AgentRunResult` type and a `run(prompt) -> AgentRunResult` adapter protocol, and SHALL ship exactly one concrete adapter backed by LiteLLM. Vendor-specific CLI/SDK adapters SHALL NOT be shipped. Any surface keyword that drives an agent SHALL resolve its adapter through this one seam.

#### Scenario: Agent-mode keyword runs through the generic adapter

- **WHEN** a Tier-3 keyword is invoked with a configured model and no explicit adapter
- **THEN** it constructs the generic LiteLLM adapter, runs the prompt, and returns a populated `AgentRunResult`

#### Scenario: A custom adapter satisfies the protocol

- **WHEN** a user passes an object exposing `run(prompt) -> AgentRunResult`
- **THEN** the keyword uses it without requiring any vendor-specific base class

### Requirement: The LLM judge is a lean rubric-to-score core

The spine SHALL provide an LLM judge that parses a rubric or plain-language criteria, composes a judge prompt, calls the configured adapter, and parses a strict JSON score. It SHALL expose one scoring keyword and one assertion keyword. Judge calibration (Cohen's kappa, F1 sweeps, bias diagnostics) SHALL NOT be included.

#### Scenario: Score an output against criteria

- **WHEN** a user calls the judge scoring keyword with an output and a criteria string
- **THEN** the judge returns a numeric score with the model's justification

#### Scenario: Assert a score threshold

- **WHEN** a user calls the judge assertion keyword with a minimum score
- **THEN** it passes when the judged score meets the threshold and fails loudly otherwise

### Requirement: A statistics core provides run-N, pass@k, and a confidence interval

The spine SHALL provide keywords to run a keyword N times, compute pass@k over the trials, and report a Wilson confidence interval. Cross-arm A/B comparison (Mann-Whitney, Cliff's delta, bootstrap) SHALL NOT be included in the base library.

#### Scenario: Compute pass@k over stochastic trials

- **WHEN** a user runs a Tier-3 keyword 10 times and requests pass@3
- **THEN** the stats core reports the pass@3 estimate and a Wilson interval over the 10 trials

### Requirement: A deterministic trace projection exposes spans and tool calls

The spine SHALL provide an evidence projection that surfaces recorded spans and tool calls so a Tier-1 assertion can verify that a specific tool was invoked with specific arguments. Enterprise export paths (OTLP, JSONL, JUnit-XML enrichment, evidence-block markdown, run-manifest sidecar) SHALL NOT be included.

#### Scenario: Assert a tool was called

- **WHEN** a test inspects the trace projection after an agent run
- **THEN** it can assert deterministically that a named tool was called with expected arguments

### Requirement: A slim error hierarchy with a synchronized exit-code table

The spine SHALL provide a compact exception hierarchy (on the order of a dozen classes, not several dozen) rooted at a single base, with a `error_code` prefix on messages and a CLI exit-code table kept in sync with the leaf classes.

#### Scenario: A structured error carries its code

- **WHEN** the library raises an integrity error
- **THEN** its string form is prefixed with the stable error code and maps to a defined CLI exit code

### Requirement: Four independently importable libraries with a thin optional composite

The distribution SHALL expose four independently importable Robot Framework libraries — `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, `HooksLibrary` — each usable on its own. A thin optional `AgentEval` library MAY compose all four for single-import convenience, but the four separate libraries SHALL be the documented default. No runtime keyword-collision detector or per-keyword namespace-prefix baking is required for the separate libraries.

#### Scenario: Import only the surface you need

- **WHEN** a suite declares `Library    HooksLibrary`
- **THEN** every Hook keyword is available and no MCP, Skills, or SubAgent keyword is loaded

#### Scenario: Optional composite offers one import

- **WHEN** a suite declares `Library    AgentEval`
- **THEN** the keywords of all four surface libraries are available under one import

### Requirement: Heavy modes live behind dependency extras

The base install SHALL provide deterministic (Tier-1) capability for all four surfaces with a minimal dependency footprint (Robot Framework, robotlibcore, PyYAML). LLM and agent modes SHALL require the `[llm]` extra; live MCP server testing SHALL require the `[mcp]` extra; `[all]` SHALL install everything. A keyword whose mode needs an uninstalled extra SHALL fail with a clear message naming the extra to install.

#### Scenario: Deterministic hook testing needs no extras

- **WHEN** a user installs the base distribution and runs Tier-1 Hook keywords
- **THEN** the keywords work without litellm or the MCP SDK installed

#### Scenario: Missing extra fails helpfully

- **WHEN** a user invokes a Tier-3 keyword without the `[llm]` extra installed
- **THEN** the keyword raises an error naming the `[llm]` extra to install

### Requirement: Identity and readable content follow the Robot Framework voice

The distribution SHALL keep the `robotframework-agenteval` PyPI name and reframe its mission from evaluating AI coding agents to testing the agentic stack (MCP servers, Skills, SubAgents, Hooks). All readable content — README, recipes, keyword docstrings, and error messages — SHALL be written in the Robot Framework voice: friendly, direct, dry, and free of fluff and internal process jargon (no FR/AC/ADR/Story provenance in user-facing docs).

#### Scenario: Keyword docs are terse and jargon-free

- **WHEN** a user reads a shipped keyword's libdoc
- **THEN** it describes what the keyword does and how to call it, with no story/AC/ADR provenance prose

#### Scenario: Mission reframed

- **WHEN** a user reads the README tagline
- **THEN** it describes testing MCP servers, Skills, SubAgents, and Hooks deterministically, with an LLM, or with a coding agent
