---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "_bmad-output/planning-artifacts/adr-backlog-from-prd.md"
  - "_bmad-output/planning-artifacts/adr-backlog-from-architecture.md"
  - "_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-16.md"
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval.md"
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval-distillate.md"
  - "_bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md"
extractionStats:
  fr_count: 68  # 65 original + 3 added 2026-05-17 (FR4b Skill Discoverability cohort, FR4c cross-adapter, FR4d Skill Should Activate For assertion — symmetric to FR10 MCP Tool Discoverability)
  nfr_count: 25  # NFR-MAINT-06 retired 2026-05-17 — see feedback_agentguard_inspiration_not_dependency
  ac_count: 9
  adr_count: 18  # 1 Architectural Influences Catalog + 10 PRD-originated + 7 architecture-originated (ADR-A4 retired 2026-05-17)
  architecture_new_modules: 7  # _kernel/tier, trace_store, redaction, discovery, run_async, guardrails, coverage
  doc_contracts: 10  # agentguard-inheritance.md retired 2026-05-17; listener-integration.md added 2026-05-17 per empirical findings on Library vs Regular Listener (see junit-xml-enrichment + listener-integration)
  ci_workflows: 7
  phase_1_spikes: 2  # MCP observer + per-test MCP cleanup
  ux_design_requirements: 0  # library has no UI; visual contracts captured as FR34b/FR55/FR58
project_name: robotframework-agenteval
date: 2026-05-17
---

# robotframework-agenteval - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for `robotframework-agenteval`, decomposing the requirements from the PRD, Architecture (including ADRs from both PRD-originated and architecture-originated sidecars), and Implementation Readiness Report into implementable stories. UX Design Specification is intentionally absent (library has no UI; visual contracts captured as FR34b / FR55 / FR58 in PRD).

The architecture-introduced additions to the PRD baseline are flagged in the Additional Requirements section so they receive story-level treatment alongside PRD FRs.

## Requirements Inventory

### Functional Requirements

The PRD specifies **65 distinct FR IDs** across 11 capability areas. Phase tags: P1 (Phase 1 MVP), P2 (Phase 2 Growth).

**Area 1 — Static Agent-Surface Inspection + Skill Discoverability (Tier 1 + Tier 3, Phase 1 + Phase 2) [9 FRs total: 6 static + 3 discoverability]:**

- **FR1 [P1]:** Agent Surface Author can call `Skill.Get Frontmatter <path.md>` and receive a dict containing the parsed YAML frontmatter; missing or malformed frontmatter raises `InvalidSkillFrontmatterError` with the file path, line number, and field name at fault.
- **FR2 [P1]:** Agent Surface Author can call `Skill.Get Frontmatter <path.md>` with the AssertionEngine matcher `Should Be Valid Frontmatter` or with `contains` / `matches` operators against any field via `Skill.Get Description`, `Skill.Get Allowed Tools`, `Skill.Get Disable Model Invocation`.
- **FR3 [P1]:** Agent Surface Author can call `Subagent.Get Frontmatter <path.md>` against `.claude/agents/*.md` files and receive the parsed sub-agent definition; same matcher surface as `Skill.Get Frontmatter`.
- **FR4 [P1]:** Agent Surface Author can call `Hook.Get Config <settings.json path>` and receive a dict mapping `hooks.<event>` → list of hook entries (`command`, `args`, `timeout`, `matcher`); supports `PreToolUse`, `PostToolUse`, `Stop` events and inline-skill-frontmatter hooks.

*Skill activation + discoverability — Tier-3 (LLM-dependent) extensions to FR4's intent, added 2026-05-17 for symmetry with FR10 MCP Tool Discoverability:*

- **FR4b [P1]:** Agent Surface Author (Devon) can call `Skill.Get Discoverability skill=<path.md> tasks=<list> by_models=<list> trials_per_task=<n> max_cost_usd=<budget>` and receive a `SkillDiscoverabilityResult` containing: per-task Pass@k of correct activation (Wilson CI), per-model selection-rate matrix, false-activation rate (skill activated when not appropriate), missed-activation rate (skill should have activated but did not), competing-skills-picked attribution per task, and the skill's `description` field as the docstring snippet under test. Cohort-style mirror of FR10a MCP Tool Discoverability.
- **FR4c [P2]:** Agent Surface Author can compare `SkillDiscoverabilityResult` across ≥2 coding-agent runtimes via `Skill.Compare Discoverability` with Mann-Whitney U significance — Phase 2 (depends on ≥2 fully-shipped Tier-1 runtimes; mirror of FR10b).
- **FR4d [P1]:** Agent Surface Author can assert `Skill Should Activate For prompt=<text> skill=<path.md> adapter=<name> model=<name>` and the assertion raises `SkillDidNotActivateError` with: (a) the prompt under test, (b) the skill that should have activated, (c) which skill (if any) the agent chose instead, (d) the agent's stated reasoning if exposed. Single-prompt assertion mirror of FR24 `Tool Call Should Have Occurred`.
- **FR5 [P1]:** Agent Surface Author can call `MCP.Get Server Config <.mcp.json path>` and receive a dict of declared MCP servers (`name`, `command`, `args`, `env`, `transport`) without starting any of them.
- **FR6 [P1]:** Agent Surface Author can call `MCP.Get Tool Schema <tool_name>` against a running or configured MCP server and receive the JSON Schema for tool input; `MCP.Validate Tool Schema <tool_name>` raises `InvalidMCPToolSchemaError` with the JSON Pointer and validation error message if the schema is malformed.

**Area 2 — MCP Server Dynamic Evaluation [8 FRs]:**

- **FR7 [P1]:** Agent Surface Author can call `MCP.Start Server <command> <args>... transport=<stdio|streamable_http|in_memory>` and receive a server handle; library spawns the server subprocess (or in-process instance) with per-test scope by default.
- **FR8 [P1]:** Agent Surface Author can call `MCP.Connect To Server <handle|url>` and receive a client connection; library negotiates MCP spec version and raises `UnsupportedMCPVersionError("server version <X> outside library tested range mcp>=1.0,<2.0")` on out-of-range.
- **FR9a [P1]:** Agent Surface Author can call `MCP.List Tools <connection>` and receive an ordered list of `MCPTool` records (`name`, `description`, `input_schema`, `output_schema`); field-projected lists via `Get Tool Names` / `Get Tool Descriptions`.
- **FR9b [P1]:** Agent Surface Author can call `MCP.Call Tool <connection> <tool_name> <args_json>` and receive an `MCPToolResult` (`result`, `error`, `latency_ms`); supports AssertionEngine matchers.
- **FR10a [P1]:** Agent Surface Author can call `MCP.Get Tool Discoverability tool=<name> by_models=<list> with_tasks=<list> k=<n>` against a single coding-agent runtime and receive a `ToolDiscoverabilityResult` containing per-model selection rate (Wilson CI), per-task verdict matrix, failed-task prompts, competing tools picked, and docstring snippet under test.
- **FR10b [P2]:** Agent Surface Author can compare `ToolDiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability` with Mann-Whitney U significance — Phase 2 (depends on ≥2 fully-shipped Tier-1 runtimes).
- **FR11 [P1]:** Library raises `CostExceededError` pre-flight if projected cost > `max_cost_usd` (default 5.00 USD); mid-run hard-stop at 1.1× the limit.
- **FR11b [P1]:** Library raises `RuntimeBudgetExceededError` pre-flight + mid-run if `max_runtime_seconds` (default None) exceeded; orthogonal to FR11.

**Area 3 — Agent Run Orchestration & Adapter Ecosystem [13 FRs]:**

- **FR12 [P1]:** Library exposes `CodingAgentAdapter` Protocol with single method `run(prompt, tools, mcp_servers, **kwargs) -> AgentRunResult`; internal base classes `InProcessAdapter` and `SubprocessAdapter(ABC)` are part of the public contributor-facing API.
- **FR13a [P1]:** Agent Developer can use `coding_agent/generic.py` (LiteLLM-backed) with `LLMProviderAdapter` Protocol composition for any of 140+ LiteLLM-supported providers including local Ollama/vLLM.
- **FR13b [P1]:** Agent Developer can use `coding_agent/claude_code_cli.py`; adapter validates `claude` binary on `$PATH` and raises `UnsupportedBinaryVersionError` if outside the pinned range; parses `--output-format=stream-json` live + post-hoc CC conversation history.
- **FR13c [P2]:** Agent Developer can use `coding_agent/claude_agent_sdk.py` (subprocess JSON-lines bridge + in-process MCP-tool support).
- **FR13d [P2]:** Agent Developer can use `coding_agent/openai_agents.py` (`Runner.run_streamed` + stream-event capture).
- **FR13e [P2]:** Agent Developer can use `coding_agent/codex_cli.py` (JSON event stream from Codex CLI; pinned binary version).
- **FR13f [P2]:** Agent Developer can use `coding_agent/copilot_cli.py`; adapter uses live `-p --output-format=json` + post-hoc `~/.copilot/session-state/{uuid}/events.jsonl`; MCP support via library-augmented `~/.copilot/mcp-config.json`; pinned `copilot` CLI `>=1.0.9,<2.0`.
- **FR14 [P1]:** Agent Developer can call `Send Prompt <agent> <prompt>` against a connected coding agent and receive an `AgentRunResult` with all required fields populated.
- **FR15 [P1]:** Agent Developer can call `Run Scenario <yaml_path>` to execute a declarative evaluation scenario; scenario YAML specifies `model`, `provider`, `agent`, `mcp_servers`, `evals[]` with `prompt`, `repeat`, `expect:` block, optional `judge:` block (Phase 2).
- **FR16 [P1]:** Agent Developer can register MCP servers (library-hosted or external) that a coding agent connects to during a run, with per-test scope isolation as the default behavior.
- **FR17a [P1]:** Contributor can register a custom `CodingAgentAdapter` implementation via `[project.entry-points."agenteval.coding_agents"]` in `pyproject.toml`.
- **FR17b [P1]:** Contributor can pass a custom `CodingAgentAdapter` instance directly via `__init__(coding_agent=MyAdapter())`.
- **FR17c [P1]:** Contributor can implement a custom `LLMProviderAdapter` and register it via `[project.entry-points."agenteval.providers"]`.
- **FR18 [P1]:** Contributor can run `agenteval new-adapter <name> --base <InProcessAdapter|SubprocessAdapter>` and receive a generated adapter skeleton with conformance-suite stubs pre-wired.

**Area 4 — Tool-Call Metrics & Trajectory Analysis (Phase 1) [7 FRs]:**

- **FR19 [P1]:** Agent Developer can call `Metric.Get Tool Call Count <run>` returning `int`; `Metric.Get Tool Call Names <run>` returning `list[str]`; both accept AssertionEngine matchers.
- **FR20 [P1]:** Agent Developer can call `Metric.Get Tool Hit Rate <run> <expected_tools>` returning `float` and `Metric.Get Tool Success Rate <run>` returning `float`.
- **FR21 [P1]:** Agent Developer can call `Metric.Get Unnecessary Call Rate <run> <expected_tools>` returning `float`.
- **FR22 [P1]:** Agent Developer can call `Metric.Get Token Usage <run>` returning `Usage(input_tokens, output_tokens, cached_input_tokens)` per Story 1b.2 ratified dataclass (epics amendment 2026-05-20 per Story 6.1 code-review Auditor HIGH-A drift fix); `Metric.Get Latency <run>` + `Metric.Get Latency P95 <run>` + `Metric.Get Cost Total <run>` returning USD float.
- **FR23a [P1]:** Agent Developer can call `Trajectory Should Match <run> <expected_sequence>` with three documented match modes: `mode=exact` (default), `mode=subsequence`, `mode=set`.
- **FR23b [P1]:** Agent Developer can pass `mode=regex` to `Trajectory Should Match` to match each step against a regex pattern over the tool-call name + serialized args.
- **FR24 [P1]:** QA Engineer can call `Tool Call Should Have Occurred <run> tool=<name> [args=<dict>]`.
- **FR25 [P1]:** QA Engineer can call `Agent Response Should Contain`, `Agent Response Should Match Regex`, or `Agent Response Should Match Schema`.

**Area 5 — Statistical Evaluation & Three-Tier Determinism Model [9 FRs]:**

- **FR26 [P1]:** Agent Developer can call `Stat.Run N Times <n> <keyword> <args>...` and receive `list[KeywordRun]`; library guarantees independent samples.
- **FR27 [P1]:** Agent Developer can call `Stat.Get Pass At K <runs> k=<int>` returning `float ∈ [0, 1]` via HumanEval unbiased estimator.
- **FR28 [P1]:** Library raises `PollingDisallowedError` whenever a Tier-2 or Tier-3 keyword receives `polling=` argument; error text directs to `Stat.Get Pass At K` and links ADR-003.
- **FR29a [P2]:** Agent Developer can call `Stat.Mann Whitney U <runs_a> <runs_b>` returning `MannWhitneyResult` (under `[agenteval-advanced]` extra).
- **FR29b [P2]:** Agent Developer can call `Stat.Cliff Delta <runs_a> <runs_b>` returning `float ∈ [-1, 1]`.
- **FR29c [P2]:** Agent Developer can call `Stat.Bootstrap Confidence Interval <samples> statistic=<callable> alpha=0.05` returning `(lo, hi)` tuple.
- **FR30a [P1]:** Library categorizes every `@keyword`-decorated method into Tier 1/2/3 via metadata; `Get Keyword Tier <keyword_name>` returns the tier; libdoc renders the tier badge.
- **FR30b [P1]:** Library raises `TierViolationError` if a Tier-1 keyword attempts to invoke an LLM provider or `validate` operator.
- **FR31a [P1]:** Library guarantees bit-identical Tier-1 reruns; verifiable via `Assert Run Determinism expect=byte_identical`.
- **FR31b [P1]:** Library guarantees statistical interpretability for Tier-2/Tier-3 reruns via `Stat.Run N Times` + `Stat.Get Pass At K`; documented determinism contract.

**Area 6 — Trace Recording & Observability [9 FRs]:**

- **FR32 [P1]:** Library emits OpenTelemetry GenAI-conformant spans (`invoke_agent → chat → execute_tool`) with `gen_ai.*` attributes.
- **FR33a [P1]:** Library registers RF Listener v3 via entry-points; opt-in via `__init__(telemetry=True)` (default on).
- **FR33b [P1+P2]:** Library emits trace artifacts to memory + JSONL backends (Phase 1); OTLP backend (Phase 2 via `[otlp]` extra).
- **FR34a [P1]:** Every assertion keyword writes a self-contained evidence block to the Robot Framework log on both pass and fail.
- **FR34b [P1]:** Evidence-block visual contract (monospace fenced section with header + 3 subsections + 1000-char truncation) verifiable via conformance suite snapshot fixtures.
- **FR35 [P1]:** Library performs server-side observation of `tools/call` invocations on every MCP server it spawns, populating `ToolCallTrace.source` with `"hosted_mcp"`.
- **FR36a [P1]:** `AgentRunResult.metadata.completeness` field is required (`complete`/`truncated`/`partial`); adapters MUST emit `truncated` on agent non-zero exit mid-stream.
- **FR36b [P1]:** `AgentRunResult.metadata.mcp_coverage` field is required (`complete`/`library_only`/`external_mixed`/`no_mcp`) on every result from keywords using `mcp_servers=`.
- **FR37 [P1]:** Library raises `IncompleteTraceError` when metric keywords are called against `mcp_coverage="external_mixed"` unless `allow_external_mcp_blind=True`.
- **FR38a [P1]:** Library redacts known credentials from all trace artifacts before serialization to any backend; `config.add_redaction_pattern()` for custom patterns.
- **FR38b [P1]:** Same `config.redact_env()` mechanism applies to env-var snapshots in `Get Effective Config` output.
- **FR39 [P1]:** Library emits a `RunManifest` JSON artifact alongside every evaluation report; manifest contains seeds, adapter versions, MCP server versions/SHAs, prompt hashes, library version, redaction-policy hash, test_id, ISO 8601 timestamp.
- **FR40 [P1]:** MCP observer scopes traces per-RF-test by reading Listener v3 `test_id`; each test gets a unique library-hosted MCP server instance by default; `mcp_per_test=False` opts out.

**Area 7 — Configuration & Provider/Agent Extensibility [4 FRs]:**

- **FR41 [P1]:** Library resolves configuration via precedence (highest wins): `__init__` args → environment variables → `.env` file → defaults; `Get Effective Config` returns `dict[str, ConfigValue]` with `source` field.
- **FR42 [P1]:** Documented defaults: `provider="litellm"`, `telemetry=True`, `trace_backend="memory"`, `allow_validate_operator=False`, `default_temperature=0.0`, `mcp_per_test=True`, `allow_external_mcp_blind=False`, `max_cost_usd=5.00`.
- **FR43 [P1]:** Library exposes `__init__(allow_validate_operator=True)` to enable AssertionEngine `validate` operator; default `False` for security.
- **FR44 [P1]:** Library exposes `__init__(telemetry=False)` to disable OTel listener; `Get Trace Backend Names` returns `[]`; no network egress to OTLP endpoints; verifiable via `Assert No Egress To`.

**Area 8 — Conformance & Compatibility Contracts [4 FRs]:**

- **FR45 [P1]:** Library publishes runnable conformance test suite at `tests/conformance/` as a public deliverable; `python -m agenteval.conformance [--adapter NAME]`; suite asserts AgentRunResult shape, ToolCallTrace shape, latency_ms > 0, sequence_index monotonic, source field honesty, completeness truncation, mcp_coverage detection, credential redaction on custom patterns.
- **FR46 [P1]:** MCP observer raises `UnsupportedMCPVersionError` on negotiated MCP spec versions outside `mcp>=1.0,<2.0`; verifiable via conformance fixture using a mock server negotiating spec version `2.5.0`.
- **FR47 [P1]:** Each CLI adapter raises `UnsupportedBinaryVersionError` at adapter instantiation if the vendor binary on `$PATH` is outside the pinned tested range; library never downloads, installs, or auto-updates vendor binaries.
- **FR48 [P1]:** Contributor can load custom plugin classes via `__init__(plugins=[MyMetricsClass(), MyAssertionsClass()])`; library auto-discovers `@keyword`-decorated methods.

**Area 9 — Reporting, CI Integration & First-Run Experience [11 FRs]:**

- **FR49 [P1]:** Library emits JUnit-compatible XML report via `--listener agenteval.reporting.junit_listener:JUnitListener` (opt-in).
- **FR50 [P1]:** Non-zero exit codes: 1 = assertion fail; 2 = CostExceededError or IncompleteTraceError; 3 = UnsupportedMCPVersionError / UnsupportedBinaryVersionError / PollingDisallowedError.
- **FR51 [P1]:** Every test's RF report line includes a `trace_id=<uuid>` attribute linking to the trace artifact.
- **FR52 [P1]:** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, `agenteval.yaml`, `.env.example`, README.
- **FR53 [P1]:** (Cross-ref to FR18 — `agenteval new-adapter` scaffolding command.)
- **FR54 [P1]:** Library writes a human-readable run summary to stderr after every `robot` invocation containing pass/fail counts, total cost USD, time-to-first-test, next-step hint.
- **FR55 [P1+P2]:** `Metric.Get Cohort Heatmap <ToolDiscoverabilityResult>` returns `CohortHeatmap` with `as_ascii()` / `as_dict()` (P1); `as_html()` (P2).
- **FR56 [P1]:** `PollingDisallowedError` text MUST contain keyword name + test file:line + remediation snippet + ADR link.
- **FR57 [P1]:** `python -m agenteval.conformance --adapter <name>` emits structured JSON on stdout + human-readable summary on stderr.
- **FR58 [P1]:** Library publishes a sample OTel trace visualization at `docs/contracts/otel-trace-visual.md` with field mapping.
- **FR59 [P1]:** All Tier-1 keyword setup failures raise structured errors with path/filename + line number + one-sentence remediation hint.

**Area 10 — Honest Failure Reporting [3 FRs]:**

- **FR60 [P2]:** Library surfaces `AdapterVersionDriftWarning` via RF Listener when binary version matches pinned range but lags tested.
- **FR61 [P1]:** Library emits `DegradedTraceWarning` if hosted-MCP observation detects partial-stream interruption mid-run; `mcp_coverage` set to `partial`.
- **FR62 [P1]:** `Get Last Warnings <run>` returns the list of warnings emitted during the run with source + message + remediation.

**Area 11 — Determinism Contract & Stability Surface (documentation deliverables) [3 FRs]:**

- **FR63 [P1]:** Library publishes a Determinism Contract document at `docs/contracts/determinism-contract.md` (byte-identical to PRD source).
- **FR64 [P1]:** Library publishes a Stability Surface document at `docs/contracts/stability-surface.md` labeling every public surface as `stable` / `provisional` / `experimental`.
- **FR65 [P1]:** Library publishes an evolving 0.x → 1.0 Exit Criteria document at `docs/contracts/exit-criteria-0x-to-1x.md` (preliminary stub; finalized at Phase 1 close).

### NonFunctional Requirements

The PRD specifies **25 NFRs** across 5 categories. (NFR-MAINT-06, an architecture-introduced agentguard-drift-check NFR, was retired 2026-05-17 when agentguard was reframed from dependency to inspiration — see `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md`.)

**Performance [8 NFRs]:**

- **NFR-PERF-01:** Time-to-first-test ≤ 5 minutes on the published happy-path cohort (Linux/macOS, Python ≥3.12, `uv` pre-installed, Tier-1 only, no API keys, bundled echo MCP server). **Release-blocking.**
- **NFR-PERF-02:** Tier-1 keyword execution: median ≤ 50 ms on typical file sizes. >2× regression blocks release.
- **NFR-PERF-03a:** Bundled echo MCP server startup ≤ 200 ms median on Linux/macOS.
- **NFR-PERF-03b:** User-provided MCP servers — no startup cap (rf-mcp / robotmcp take several seconds, acknowledged).
- **NFR-PERF-03c:** MCP protocol handshake post-startup ≤ 500 ms median.
- **NFR-PERF-03d:** `mcp_per_test=True|"suite"|False` trade-off matrix documented + tested.
- **NFR-PERF-04:** Cost guardrail accuracy: pre-flight ±20%; mid-run hard-stop within 10% of `max_cost_usd`.
- **NFR-PERF-05:** Concurrent execution under `pabot --processes 8` produces no cross-test trace pollution with bundled echo; heavy-server opt-out documented + tested.
- **NFR-PERF-06:** `max_runtime_seconds` time guardrail with pre-flight + 1.1× hard-stop.

**Reliability [5 NFRs]:**

- **NFR-REL-01:** `tests/unit/` pass rate ≥ 99% on every PR. **Release-blocking.**
- **NFR-REL-02:** `tests/acceptance/` smoke-tag pass rate = 100% on every release. **Release-blocking.**
- **NFR-REL-03:** `tests/integration/` live ≥ 95% nightly; 3 consecutive failures gate next release.
- **NFR-REL-04:** External dependency pinning posture documented per release in CHANGELOG.
- **NFR-REL-05:** Dogfood loop: `rf-mcp` + `robotframework-agentskills` CI runs against released library within 24h; regression blocks next release.

**Security [5 NFRs]:**

- **NFR-SEC-01:** No credentials persisted in original form anywhere; `config.redact_env()` mandatory pre-trace-write.
- **NFR-SEC-02:** `eval()` only via opt-in `validate` operator; safe operators elsewhere.
- **NFR-SEC-03:** TLS for all LLM provider + Streamable HTTP traffic; no cert-validation-relax knobs.
- **NFR-SEC-04:** Library never auto-downloads / installs / updates vendor binaries; supply-chain trust boundary in `SECURITY.md`.
- **NFR-SEC-05:** No phone-home; only LLM + OTLP egress (latter opt-in P2); `telemetry=False` eliminates OTel egress.

**Integration & Compatibility [6 NFRs]:**

- **NFR-COMPAT-01:** Python 3.12 + 3.13 Tier-1 CI; <3.12 unsupported.
- **NFR-COMPAT-02:** RF `>=7.4,<9.0`; stable-APIs-only; RF 8.x.beta CI testing P2 deliverable.
- **NFR-COMPAT-03:** Linux + macOS first-class CI; Windows best-effort + documented troubleshooting.
- **NFR-COMPAT-04:** `mcp>=1.0,<2.0`; transports stdio/streamable_http/in-memory; SSE legacy.
- **NFR-COMPAT-05:** `litellm>=1.83` minor-floor; Protocol isolates; Mock fallback.
- **NFR-COMPAT-06:** `opentelemetry-api/sdk>=1.27` minor-floor; semconv internal facade.

**Maintainability [5 NFRs]:**

- **NFR-MAINT-01:** Solo + AI-agent-assisted posture in `MAINTAINERS.md`; bus-factor deliverables P1.
- **NFR-MAINT-02:** Issue-triage SLA: best-effort 5 business days; security prioritized; published in `SUPPORT.md`.
- **NFR-MAINT-03:** Semver discipline: 0.x.y breaking → minor-bump; 1.0+ strict semver after exit criteria.
- **NFR-MAINT-04:** Docs are first-class P1 (README + recipe gallery ≥8 + ADRs + 9 contracts docs); doc-build CI asserts required sections.
- **NFR-MAINT-05:** Stability Surface metadata updated per release; every public element has exactly one label.
- **~~NFR-MAINT-06 (RETIRED 2026-05-17)~~:** Was "Automated agentguard-drift detection CI." Retired alongside ADR-A4 when agentguard was reframed from dependency to inspiration — no dependency to drift-check. See `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md`.

### Additional Requirements

Architecture document materially adds to the PRD baseline. These additions require story-level treatment:

**Architecture-introduced kernel modules (`src/AgentEval/_kernel/` — 7 modules per Step-2 cross-cutting concerns + Step-4 decisions):**

- `_kernel/tier.py` — `@tier(N)` decorator + `get_keyword_tier()` per Decision-1 (ADR-A1 numbering refers to async bridge; tier decorator is Decision-1 of Step-4).
- `_kernel/trace_store.py` — OTel SDK `InMemorySpanExporter` wrapper + per-test-id indexing + projection accessors per Decision-2.
- `_kernel/redaction.py` — OTel SpanProcessor for credential redaction per NFR-SEC-01 / Decision-2 cascading.
- `_kernel/discovery.py` — Entry-points discovery for 5 groups (`agenteval.coding_agents`, `agenteval.providers`, `agenteval.judges` (P2 implicit), `agenteval.sandboxes` (per ADR-018, was ADR-A8), `robot.listener`) + `plugins=[]` composition per ADR-A2.
- `_kernel/run_async.py` — `_run_async()` async-to-sync bridge per ADR-A1.
- `_kernel/guardrails.py` — `@guarded_fanout(estimator=)` decorator for cost + runtime guardrails per ADR-A5.
- `_kernel/coverage.py` — `_check_mcp_coverage()` helper + IncompleteTraceError gate per ADR-016 (was ADR-A6; ratified with D1 trust-floor semantics 2026-05-17).
- `_kernel/context.py` — Listener v3 `test_id` propagation context helpers (supports FR40 / AC-MCP-OBSERVE-03).

**Architecture-introduced error infrastructure:**

- `src/AgentEval/errors.py` — `AgentEvalError` base + 4 sub-bases (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`) + 9 leaf classes + `error_code` field per ADR-A3.

**Architecture-introduced sandbox surface (sandbox policy moved from PRD Phase 3 to Phase 1):**

- `src/AgentEval/security/protocols.py` — `SandboxBackend` Protocol per ADR-018 (was ADR-A8).
- `src/AgentEval/security/null_sandbox.py` — `NullSandbox` default backend (raises `SandboxRequiredError` on every call).
- `src/AgentEval/security/policy.py` — Sandbox policy + gate logic.

**Architecture-introduced documentation contracts (4 additions to PRD's 5 → total 9; agentguard-inheritance.md retired 2026-05-17):**

- `docs/contracts/error-class-hierarchy.md` per ADR-A3.
- `docs/contracts/mcp-coverage-detection.md` per ADR-016 (was ADR-A6).
- `docs/contracts/conformance-fixture-format.md` per Step-4 Decision-4.
- `docs/contracts/coding-conventions.md` per Step-5 patterns reference card.

**Architecture-locked ADRs to ratify (18 total in `docs/adr/` per Hybrid scheme from Step-1; ADR-A4 retired 2026-05-17):**

- **ADR-001** Architectural Influences Catalog — content drafted from `architecture.md` frontmatter `reconciliationMatrix`; catalogs ~14 patterns reviewed in `robotframework-agentguard` (among other references — `wolfeidau/mcp-evals`, `lastmile-ai/mcp-eval`, OpenTelemetry GenAI semconv, etc.); each entry annotated with adopt / adapt / diverge rationale evaluated on merit for agenteval. No dependency on agentguard; free to diverge.
- **ADR-002..011** — 10 PRD-originated ADRs (renumbered from `adr-backlog-from-prd.md` working IDs ADR-005..014).
- **ADR-012..018** — 7 architecture-originated ADRs (renumbered from `adr-backlog-from-architecture.md` working IDs ADR-A1/A2/A3/A5/A6/A7/A8; ADR-A4 retired 2026-05-17).

**Architecture-locked CI workflows (7 GitHub Actions files; agentguard-drift-check.yml retired 2026-05-17 — replaced by security-scan.yml to keep count at 7):**

- `.github/workflows/ci.yml` — PR-gating matrix.
- `.github/workflows/nightly-live.yml` — `@pytest.mark.live` + acceptance-tier3 cron.
- `.github/workflows/conformance.yml` — per-release conformance suite.
- `.github/workflows/security-scan.yml` — CodeQL scan on every PR (standard hygiene; replaces retired agentguard-drift-check.yml).
- `.github/workflows/dogfood-integration.yml` — per-release per NFR-REL-05.
- `.github/workflows/docs-build.yml` — libdoc + contracts assertion per NFR-MAINT-04.
- `.github/workflows/release.yml` — PyPI OIDC trusted publishing per NFR-MAINT-03.

**Phase 1 Week 1 spike work (per architecture Step-4 Decision-3):**

- **Spike A** — Hosted-MCP universal trace observer (5-day budget): determine `mcp` Python SDK middleware/interceptor vs custom MCP server subclass; output is ADR amendment locking the approach.
- **Spike B** — Per-test MCP server cleanup under `pabot --processes 8` (3-day budget): validate Listener v3 hooks reliably spawn + clean up subprocesses; output is ADR amendment locking the cleanup mechanism.

**Architecture-locked test infrastructure:**

- `tests/conformance/` directory with per-AC test files (10 AC test files), `harness.py` (truncation-injection + `adapter_registry` fixture + mock-agent fixtures per AC-CONFORMANCE-02), `loader.py` (validates against `fixture-schema.json` per Decision-4 + returns Pydantic `ConformanceFixture` instances), `fixture-schema.json`, and `fixtures/<adapter>/<scenario>.json` files (6 initial fixtures: 3 per Tier-1 Phase-1 adapter).
- `tests/unit/conventions/` directory with 5 CI-enforcement tests (`test_import_graph.py`, `test_error_classes.py`, `test_no_asyncio_run.py`, `test_print_banned.py`, `test_config_naming.py`) per Step-5 CI-enforcement pattern.
- `tests/benchmarks/` directory with `bench_static_inspection.py`, `bench_mcp_handshake.py`, `bench_echo_server_startup.py` per NFR-PERF-02 / NFR-PERF-03.
- `tests/fixtures/mcp/` — bundled echo MCP server (`echo_server.py`), heavy-server simulation (`heavy_simulator.py` with `time.sleep(3)` startup for NFR-PERF-05 testing), future-spec mock (`future_spec_mock.py` negotiating MCP spec 2.5.0 to verify version_gate per FR46).

**Greenfield setup work (per implementation-readiness-report Section 5 Issue 3 — gap not captured in PRD FRs):**

- `pyproject.toml` initial creation with hatchling build backend + PEP 621/735 dependency groups (per Compatibility Matrix).
- `uv.lock` initial generation + dev/optional dep groups (per Extras Matrix).
- `MAINTAINERS.md` + `CONTRIBUTING.md` + `SUPPORT.md` + `SECURITY.md` skeleton authoring (per NFR-MAINT-01/02/03/04 + NFR-SEC-04).
- Initial `examples/00_setup.robot` against bundled echo MCP server (verifies setup story complete; satisfies NFR-PERF-01 happy-path target).

**Acceptance Criteria (9 cross-cutting; referenced from FRs):**

- AC-SIMPLICITY-01: evidence-block legibility on every assertion (FR34a/b).
- AC-SIMPLICITY-02: sub-library getter+matcher rule + core ergonomic carve-out + paired-getter requirement (all keyword FRs; enforced via `tests/unit/conventions/` + conformance suite).
- AC-DISCOVER-01: `MCP.Get Tool Discoverability` evidence-block shape (FR10a/b).
- AC-DISCOVER-02: `max_cost_usd=5.00` default + pre-flight + mid-run hard-stop (FR11).
- AC-DOGFOOD-01: `rf-mcp` + `robotframework-agentskills` custom tests replaced by `.robot` at parity by end of Phase 1 (NFR-REL-05).
- AC-CONFORMANCE-01: conformance suite includes fidelity oracles (FR45 + Decision-4).
- AC-CONFORMANCE-02: `completeness` field required + truncation-injection oracle (FR36a, FR45).
- AC-MCP-OBSERVE-01: `mcp_coverage` indicator + `IncompleteTraceError` on `external_mixed` (FR36b, FR37).
- AC-MCP-OBSERVE-02: MCP spec version validation at session start (FR8, FR46).
- AC-MCP-OBSERVE-03: per-test MCP scope via Listener v3 `test_id` (FR40).

### UX Design Requirements

**N/A** — `robotframework-agenteval` is a Python Robot Framework PyPI library with no UI surface. UX-adjacent visual contracts (evidence-block format, cohort heatmap format, OTel trace visualization, terminal run summary, polling-error message text) are captured as first-class FRs in PRD: FR34b, FR55, FR58, FR54, FR56 respectively. `/bmad-create-ux-design` was intentionally skipped per PRD scope.

### FR Coverage Map

Every FR ID is owned by exactly one epic. Phase 1 = Epics 0–9; Phase 2 = Epics 10–13.

| FR | Epic | Note |
|---|---|---|
| FR1, FR2, FR3, FR4 (Hook config inspection), FR5, FR6 | Epic 2 | Static Agent-Surface Inspection (Tier-1, deterministic) |
| FR4b (Skill.Get Discoverability cohort) | Epic 7 Story 7.2 | Tier-3 cohort + Pass@k (depends on Epic 4 adapter + Epic 6 stats) |
| FR4c (Skill.Compare Discoverability cross-adapter) | Epic 13 Story 13.5 [P2] | Cross-adapter Skill Discoverability (mirrors FR10b for skills) |
| FR4d (Skill Should Activate For assertion) | Epic 7 Story 7.2 | Single-prompt assertion mirroring FR24 Tool Call Should Have Occurred |
| FR4 (Skill activation reliability — single-prompt via Skill.Get Activation Decision) | Epic 7 Story 7.1 | Architecture-added keyword (single-prompt activation decision; depends on Epic 4 adapter) |
| FR7, FR8, FR9a, FR9b, FR46 | Epic 3 | MCP Server Lifecycle + version gate |
| FR10a (MVP single-runtime) | Epic 4 Story 4.4 | Tool Discoverability MVP per AC-DISCOVER-01 (relocated from Epic 3 — needs adapter to drive trials) |
| FR10b | Epic 13 [P2] | Compare Tool Discoverability across adapters (cross-adapter) |
| FR11, FR11b | Epic 4 Story 4.4 (MVP Discoverability) + Epic 7 Story 7.2 (Skill Discoverability) | Both keywords inherit `CostExceededError` + `RuntimeBudgetExceededError` from `@guarded_fanout` decorator in Story 1b.3 kernel — no duplicate guardrail logic |
| FR12 | Epic 1b (Protocol + ABCs scaffolded) + Epic 4 (Generic + CC CLI concrete impls) | Adapter Protocol + concrete adapters |
| FR13a | Epic 4 | Generic adapter (LiteLLM) |
| FR13b | Epic 4 | Claude Code CLI adapter (merged with Generic per Amelia) |
| FR13c | Epic 10 [P2] | Claude Agent SDK |
| FR13d | Epic 10 [P2] | OpenAI Agents SDK |
| FR13e | Epic 11 [P2] | Codex CLI |
| FR13f | Epic 11 [P2] | Copilot CLI |
| FR14 | Epic 4 | Send Prompt |
| FR15 | Epic 4 | Run Scenario YAML |
| FR16 | Epic 4 | mcp_servers= keyword arg |
| FR17a, FR17b, FR17c | Epic 1b | Entry-points + direct composition (`_kernel/discovery.py`) |
| FR18 | Epic 8b | `agenteval new-adapter` scaffold |
| FR19, FR20, FR21, FR22 | Epic 6 | Tool-Call Metrics |
| FR23a, FR23b, FR24, FR25 | Epic 6 | Trajectory + tool-call + response assertions |
| FR26, FR27, FR28 | Epic 6 | Statistical primitives + polling ban |
| FR29a, FR29b, FR29c | Epic 13 [P2] | Advanced stats via `[agenteval-advanced]` extra |
| FR30a | Epic 1b (kernel tier decorator + libdoc badge) + Epic 6 (Get Keyword Tier keyword surface) | Tier model — decorator moved to kernel per Winston |
| FR30b, FR31a, FR31b | Epic 6 | TierViolationError + determinism guarantees (enforced where stats live) |
| FR32, FR33a | Epic 5 | OTel spans + Listener v3 registration |
| FR33b memory + JSONL | Epic 5 | Phase 1 trace backends |
| FR33b OTLP | Epic 13 [P2] | OTLP trace backend |
| FR34a, FR34b | Epic 5 | Evidence-block format + visual contract |
| FR35 | Epic 5 (post-Epic-0 spike) | Hosted-MCP universal observer |
| FR36a, FR36b, FR37 | Epic 5 | Honesty fields + IncompleteTraceError |
| FR38a, FR38b | Epic 5 (via Epic 1b `_kernel/redaction.py`) | Credential redaction |
| FR39 | Epic 5 | RunManifest JSON sidecar |
| FR40 | Epic 5 (via Epic 1b `_kernel/context.py` + Epic 0 spike output) | Per-test MCP scope |
| FR41 | Epic 4 (`config.py`) | Config precedence + Get Effective Config |
| FR42 | Epic 1a (defaults documentation) | Defaults |
| FR43 | Epic 1a (allow_validate_operator wiring) + Epic 6 (gate enforcement) | validate operator opt-in |
| FR44 | Epic 1a (telemetry=False wiring) | OTel disable |
| FR45 | Epic 1b (conformance scaffolding) + each domain epic (per-AC fixtures added as ACs land) | Conformance suite |
| FR47 | Epic 4 (CC CLI binary check) + Epic 10/11 [P2] (other CLI binary checks) | UnsupportedBinaryVersionError |
| FR48 | Epic 12 [P2] | Judge.Get Score |
| FR49, FR50, FR51 | Epic 8a | JUnit XML + exit codes + trace_id surfacing |
| FR52, FR53 | Epic 8b | `agenteval init` + cross-ref to FR18 |
| FR54 | Epic 8b | Terminal run summary |
| FR55 ASCII + dict | Epic 8b | Cohort heatmap (relocated from dissolved Epic 8 per Winston) |
| FR55 HTML | Epic 13 [P2] | Cohort heatmap HTML rendering |
| FR56 | Epic 8a | Polling-ban error testability |
| FR57 | Epic 8a | Conformance report JSON+human |
| FR58 | Epic 8b | OTel trace visual doc |
| FR59 | Epic 1a (error format documented) + Epic 2 (Tier-1 errors implemented with format) | Tier-1 setup-failure diagnostics |
| FR60 | Epic 11 [P2] | AdapterVersionDriftWarning (needs ≥2 Tier-1 CLI adapters) |
| FR61, FR62 | Epic 5 | DegradedTraceWarning + Get Last Warnings |
| FR63 | Epic 1b (Determinism Contract doc) | Determinism Contract doc |
| FR64 | Epic 1a (Stability Surface doc skeleton) + each epic (labels added per release) | Stability Surface doc |
| FR65 | Epic 1a (Exit Criteria stub) + Phase 1 close (final content via Epic 9 retrospective) | 0.x→1.0 Exit Criteria doc |

**Coverage check:** All 65 FR IDs accounted for across 13 epics (Epic 0 ships decision records only — no FR coverage).

**AC coverage:**
- AC-SIMPLICITY-01 (evidence-block legibility) → Epic 5 (FR34a/b)
- AC-SIMPLICITY-02 (keyword idiom) → Epic 1b (CI-enforcement conventions test scaffolding) + every epic adding keywords (via enforced convention)
- AC-DISCOVER-01 (Tool Discoverability cohort) → Epic 3 (MVP single-runtime) + Epic 13 [P2] (full cross-adapter cohort)
- AC-DISCOVER-02 (cost guardrail) → Epic 7
- AC-DOGFOOD-01 (replace custom tests) → Epics 3 + 5 + 6 (interleaved dogfood stories) + Epic 9 (consolidation + cross-repo CI verification)
- AC-CONFORMANCE-01 (fidelity oracles) → Epic 1b (scaffolding) + per-domain epics (oracle implementations as ACs land)
- AC-CONFORMANCE-02 (completeness truncation) → Epic 5 (`completeness` field) + Epic 1b (truncation injection harness)
- AC-MCP-OBSERVE-01 (mcp_coverage indicator) → Epic 5
- AC-MCP-OBSERVE-02 (MCP spec version gate) → Epic 3
- AC-MCP-OBSERVE-03 (per-test MCP scope) → Epic 5 (via Epic 0 spike output + Epic 1b `_kernel/context.py`)

---

## Epic List

**Phase 1: 12 epics (Epic 0 + 1a + 1b + 2–8b + 9) | Phase 2: 4 epics (10–13).**

**Calendar honesty:** Phase 1 realistic estimate = **10–12 weeks** at solo + AI-agent-assisted throughput, with interleaved dogfood. The original 6–8 week brief target was retired during Step-2 party-mode review (Amelia's shipping math, accepted). De-risking moves baked in: Epic 0 splits the two architecture-gating spikes out before downstream epics commit; dogfood stories interleaved into Epics 3 + 5 + 6 + 7 to catch integration pain by week 3–4 instead of week 10; Tool Discoverability MVP slice in Epic 4 + Skill Discoverability cohort surface in Epic 7 + advanced cross-adapter variants in Phase 2.

**Persona first-value milestone table (post-Step-4 corrections):**

| Persona | First-value milestone | Epic position |
|---|---|---|
| **Devon (Skill Author)** | Epic 2 (static skill validation) → Epic 7 (cohort Skill Discoverability + activation reliability) | #4 → #9 of 12 |
| **Mei (MCP Author)** | Epic 3 (MCP runtime + tool inspection) → Epic 4 Story 4.4 (MVP Tool Discoverability) | #5 → #6 of 12 |
| **Raj (Agent Developer)** | Epic 4 (Generic adapter + Send Prompt + MVP Discoverability) | #6 of 12 |
| **Priya (QA Engineer)** | Epic 6 (metric assertions) → Epic 8a (CI integration + enriched xunit) | #8 → #10 of 12 |

**Note:** Mei's first-value milestone shifted from Epic 3 (MVP Discoverability bundled there) to Epic 3+4 split (MCP runtime in Epic 3; Discoverability requires adapter so lands in Epic 4 Story 4.4). Devon's value milestones updated: full Skill Discoverability cohort + activation surface now lands in restructured Epic 7 (4 stories: 7.1 single-prompt activation, 7.2 cohort + assertion, 7.3 stacked recipe, 7.4 dogfood) per the FR4b/c/d additions on 2026-05-17.

---

### Epic 0: Spikes & Architectural Decisions

**Goal:** De-risk the two architectural questions whose outcomes change downstream epic design BEFORE those epics commit. Hosted-MCP universal observer spike (5 days) decides `mcp/observer.py` API shape consumed by Epic 5. Per-test MCP cleanup-under-pabot spike (3 days) decides `mcp/transport.py` + `_kernel/context.py` cleanup semantics consumed by Epic 3 + Epic 5. Output is amended ADR-007 (hosted-MCP observer) + ADR-A6 (MCP coverage detection default) + ADR-A8 (sandbox policy Phase 1) ratification with empirical confirmation. Ships decision records, not code.

**FRs covered:** None directly — gates FR35 + FR40 implementation in Epic 5 and FR7 cleanup behavior in Epic 3.

**Dependencies:** None — first epic.

**Primary persona:** All (architecture quality affects every persona).

---

### Epic 1a: Project Bootstrap + CI + ADR Ratification + Project-Hygiene Documentation

**Goal:** Any contributor can clone the repo, run `uv sync`, see all 7 CI workflows green on a trivial PR, and read all 10 doc-contract skeletons + 15 ratified non-spike ADRs (with the 3 spike-dependent ADRs from Epic 0 amended in). Closes the greenfield setup gap surfaced in `implementation-readiness-report-2026-05-16.md` Section 5 Issue 3. Includes Architectural Influences Catalog (ADR-001) content drafting (catalogs patterns reviewed in `robotframework-agentguard` among other references; agenteval evaluates each on merit and is free to diverge), CONTRIBUTING.md, SECURITY.md, issue templates, license headers — hidden labor surfaced by Amelia, no longer silent. (Previously included the agentguard-drift CI workflow per NFR-MAINT-06 / ADR-A4; both retired 2026-05-17 when agentguard was reframed from dependency to inspiration. Doc-contract count adjusted 10 → 9 → 10 on 2026-05-17 — `agentguard-inheritance.md` retired, then `listener-integration.md` + `junit-xml-enrichment.md` added per empirical findings on RF Listener architecture.)

**FRs covered:** FR42 (defaults documentation), FR43 (allow_validate_operator wiring; gate enforcement is Epic 6), FR44 (telemetry=False wiring), FR59 (Tier-1 setup-failure error format documented; instances implemented in Epic 2), FR64 (Stability Surface doc skeleton), FR65 (Exit Criteria doc stub).

**Dependencies:** Epic 0 (ratified ADR amendments to incorporate).

**Primary persona:** Contributor (Day-1 onboarding cleanliness).

---

### Epic 1b: Cross-Cutting Kernel + Conformance Scaffolding + Determinism Contract

**Goal:** All 8 `_kernel/` modules (`tier.py` with `@tier(N)` decorator + libdoc tier badge, `trace_store.py`, `redaction.py`, `discovery.py`, `run_async.py`, `guardrails.py` with `@guarded_fanout` decorator, `coverage.py`, `context.py`) ship complete and unit-tested. Conformance suite harness (`tests/conformance/{harness.py, loader.py, fixture-schema.json}`) accepts 6 reference fixtures and round-trips them. CodingAgentAdapter Protocol + InProcessAdapter/SubprocessAdapter ABCs scaffolded (concrete adapters land Epic 4). Determinism Contract doc (FR63) authored from kernel guarantees. 5 CI-enforcement conventions tests (`tests/unit/conventions/*.py`) pass on the skeleton.

**FRs covered:** FR12 (Protocol + ABCs — concrete impls Epic 4), FR17a/b/c (adapter discovery infrastructure), FR30a (kernel tier decorator + libdoc badge — Get Keyword Tier keyword surface lands Epic 6), FR45 (conformance scaffolding), FR63 (Determinism Contract doc).

**Dependencies:** Epic 0 (cleanup spike output informs `context.py` cleanup semantics).

**Primary persona:** All (cross-cutting substrate every subsequent epic imports).

---

### Epic 2: Static Agent-Surface Inspection — Tier-1 Keywords (Skill / Subagent / Hook / MCP Config)

**Goal:** QA Engineer (Priya) or Agent Surface Author (Devon, Mei) can validate skill `.md` files, sub-agent definitions, hook configurations, and `.mcp.json` server configs **without API keys, without network, in milliseconds**. First user-value milestone after foundation. Devon's first hands-on value; Priya's first deterministic-test value. Implements Tier-1 setup-failure errors per the format documented in Epic 1a (`InvalidSkillFrontmatterError`, `InvalidMCPToolSchemaError`, etc.).

**FRs covered:** FR1, FR2, FR3, FR4 (Hook config — skill activation reliability is Epic 7), FR5, FR6.

**Dependencies:** Epic 1a (error format + sandbox Protocol scaffolds) + Epic 1b (`@tier(1)` decorator + conformance harness).

**Primary persona:** QA Engineer + Agent Surface Author (Devon first value; Mei partial).

---

### Epic 3: MCP Server Lifecycle + Runtime Inspection

**Goal:** Mei (Agent Surface Author — MCP author mode) can start, connect to, introspect, and stop MCP servers (stdio + Streamable HTTP + in-memory transports). MVP Tool Discoverability (FR10a) relocated to Epic 4 Story 4.4 because it requires the adapter to drive trials; Mei's full Phase 1 Discoverability value materializes after Epic 4 ships. **Interleaved dogfood story: port `rf-mcp` MCP surface tests to `.robot` suites using this epic's keywords** — first proof the library survives a real downstream repo. Validates MCP spec version at session start per AC-MCP-OBSERVE-02.

**FRs covered:** FR7, FR8, FR9a, FR9b, FR46. (FR10a moved to Epic 4 Story 4.4 per Step-2 dependency-graph correction; see FR Coverage Map.)

**Dependencies:** Epic 0 (cleanup spike output) + Epic 1b (`_kernel/run_async.py` + `_kernel/context.py`).

**Primary persona:** Agent Surface Author (Mei's first value; the novel Tool Discoverability primitive lands here in MVP form).

---

### Epic 4: Coding-Agent Adapter Suite (Generic + Claude Code CLI) + Agent Orchestration + MVP Tool Discoverability

**Goal:** Raj (Agent Developer) can connect to any LLM provider via LiteLLM-backed Generic adapter, send prompts, run YAML scenarios, and receive normalized `AgentRunResult` data. Devon's CC CLI adapter ships in parallel (Amelia's merge call) — two concrete `CodingAgentAdapter` implementations validate the abstraction in a single epic. Custom adapters registerable via entry-points or direct composition (FR17 infrastructure from Epic 1b).

**FRs covered:** FR12 (concrete Generic + CC CLI implementations), FR13a (Generic LiteLLM), FR13b (Claude Code CLI), FR14 (Send Prompt), FR15 (Run Scenario YAML), FR16 (mcp_servers= keyword arg), FR41 (config precedence + Get Effective Config), FR47 (UnsupportedBinaryVersionError for `claude` binary).

**Dependencies:** Epic 1b (Protocol + ABCs + entry-points discovery + errors).

**Primary persona:** Agent Developer (Raj's first value) + Agent Surface Author (Devon's adapter dependency for Epic 7 Skill Author Flow).

---

### Epic 5: Trace Recording + Observability + Honesty Fields

**Goal:** Every agent run produces auditable OTel-shape evidence (`invoke_agent → chat → execute_tool` spans) with `gen_ai.*` attributes, per-test scope via Listener v3 `test_id`, hosted-MCP server-side observation (post-spike, from Epic 0), and honesty fields (`completeness`, `mcp_coverage`) populated on every `AgentRunResult`. Closes the agent-agnostic trace truth claim. Implements credential redaction as a mandatory choke point per `_kernel/redaction.py` (Epic 1b). **Interleaved dogfood story: port `rf-mcp` trace assertions** — proves trace artifacts survive a real downstream repo's CI under pabot.

**FRs covered:** FR32 (OTel GenAI spans), FR33a (Listener v3 entry-point registration), FR33b memory + JSONL backends, FR34a (evidence-block format per AC-SIMPLICITY-01), FR34b (visual contract), FR35 (hosted-MCP observer per ADR-004 (was ADR-007), ratified), FR36a (completeness per ADR-A3), FR36b (mcp_coverage per ADR-016 (was ADR-A6), ratified), FR37 (IncompleteTraceError on external_mixed), FR38a/b (credential redaction in traces + Get Effective Config), FR39 (RunManifest JSON sidecar), FR40 (per-test MCP scope per ADR-016 + Story 0.2 spike), FR61 (DegradedTraceWarning), FR62 (Get Last Warnings).

**Dependencies:** Epic 0 (observer + cleanup spike outputs) + Epic 1b (kernel modules) + Epic 3 (MCP runtime exists to be observed) + Epic 4 (adapter emits spans).

**Primary persona:** Agent Developer + Agent Surface Author (hosted-MCP traces give Mei cohort evidence).

---

### Epic 6: Tool-Call Metrics + Statistical Assertions + Determinism Enforcement

**Goal:** Raj can compute tool-call count, names, hit rate, success rate, unnecessary-call rate, token usage, latency, cost. Assert on trajectory matches (exact / subsequence / set / regex). Assert specific tool calls + response content. Run statistical primitives (`Run N Times`, `Pass At K` via HumanEval estimator) for non-deterministic scenarios. Three-tier ACL gates enforced at `_assertions/adapter.py`: polling on Tier-2/3 → `PollingDisallowedError`; Tier-1 keyword LLM invocation attempts → `TierViolationError`. **Interleaved dogfood story: port `robotframework-agentskills` metrics tests** — closes Raj's primary journey evidence loop.

**Note on merge:** Winston's merge of v1 Epics 6 + 7 ships here because metrics without tier-aware stats has no pass/fail semantics. Tier decorator infrastructure already in Epic 1b kernel (cross-cutting) — what lives here is the `Get Keyword Tier` keyword surface + the assertion-engine integration.

**FRs covered:** FR19, FR20, FR21, FR22 (metrics), FR23a/b, FR24, FR25 (assertions), FR26 (Run N Times), FR27 (Pass At K), FR28 (PollingDisallowedError per ADR-003 — pattern borrowed from agentguard, evaluated on merit), FR30a (Get Keyword Tier keyword + libdoc badge integration), FR30b (TierViolationError enforcement), FR31a/b (determinism guarantees enforcement), FR43 (validate-operator gate enforcement — wiring is in Epic 1a).

**Dependencies:** Epic 1b (kernel tier decorator + `_assertions/adapter.py` scaffolding) + Epic 5 (trace store populated with span data).

**Primary persona:** All — Raj's primary surface; Priya's first CI-relevant pass/fail; Devon's Pass@k dependency.

---

### Epic 7: Skill Author Validation Flow + Skill Discoverability (Cohort + Assertion + Cross-Repo Dogfood)

**Goal:** Devon (Agent Surface Author — skill author mode) completes his Journey 4 Phase 1 portion: Tier-1 static skill inspection (Epic 2) **stacked with** Tier-3 cohort Skill Discoverability + activation reliability via 4 stories — `Skill.Get Activation Decision` (single-prompt; Story 7.1), `Skill.Get Discoverability` cohort + `Skill Should Activate For` assertion (Story 7.2), Devon's stacked validation recipe + integration test (Story 7.3), and interleaved dogfood against `robotframework-agentskills` real skills (Story 7.4). Symmetric to Mei's MCP Tool Discoverability (FR10a/b) — both Agent Surface Author personas now have first-class cohort discoverability surfaces.

**FRs covered:** FR4b (Skill.Get Discoverability cohort — Story 7.2), FR4d (Skill Should Activate For assertion + SkillDidNotActivateError — Story 7.2). Plus architecture-added `Skill.Get Activation Decision` single-prompt keyword (Story 7.1) tracked under FR4's intent. Phase 2 cross-adapter mirror (FR4c) ships in Epic 13 Story 13.5. (FR11 + FR11b moved to Epic 4 Story 4.4 — both this epic's Skill Discoverability AND Epic 4's MVP Tool Discoverability inherit cost/runtime guardrails from `@guarded_fanout` decorator in Story 1b.3; no duplicate guardrail logic.)

**Dependencies:** Epic 2 (static skill foundation) + Epic 4 (adapter pattern) + Epic 6 (Pass@k machinery + tier model).

**Primary persona:** Agent Surface Author (Devon's primary value; Mei's discoverability hardening).

---

### Epic 8a: CI Integration + Conformance Reporting — "CI-Grade" Claim

**Goal:** Priya (QA Engineer) can drop `robotframework-agenteval` into any CI system that consumes JUnit XML + non-zero exit codes. trace_id surfaced in `output.xml` per test enables tracing across CI logs. Polling-ban error gives actionable diagnostic for accidental Tier-2/3 misuse. Conformance report (JSON + human-readable) consumable by any downstream tooling that wants to verify adapter conformance.

**FRs covered:** FR49 (JUnit XML), FR50 (exit codes mapped via error_code per ADR-A3), FR51 (trace_id in output.xml), FR56 (polling-ban error testability), FR57 (conformance report JSON+human).

**Dependencies:** Epic 1a (error_code mapping infrastructure) + Epic 5 (trace_id exists) + Epic 6 (PollingDisallowedError already implemented).

**Primary persona:** QA Engineer (Priya's CI-grade claim).

---

### Epic 8b: First-Run UX + Adapter Authoring + Cohort Heatmap — "5-Minute First-Run" Claim

**Goal:** New users bootstrap via `agenteval init` scaffolding (FR52) and add custom adapters via `agenteval new-adapter` (FR18). Terminal run summary (FR54) closes the first-run loop. Cohort heatmap rendering (ASCII + dict) from FR55 lives here (relocated from dissolved Epic 8 per Winston). 8 recipe gallery entries authored here covering all primary user journeys (Recipes 1-8 distributed per source journey). OTel trace visualization doc (FR58) included.

**FRs covered:** FR18 (`agenteval new-adapter`), FR52 (`agenteval init`), FR53 (cross-ref to FR18), FR54 (terminal run summary), FR55 ASCII + dict (cohort heatmap), FR58 (OTel trace visual doc).

**Dependencies:** Epics 1a (CLI infrastructure), 3, 4, 5, 6, 7 (recipes derive from full surface area; heatmap consumes metric data).

**Primary persona:** All (Day-1 friction killer; new-adapter scaffold helps contributors).

---

### Epic 9: Dogfood Loop Consolidation + Phase 1 Close

**Goal:** Falsifiable Phase 1 completion bar per AC-DOGFOOD-01. The interleaved dogfood stories from Epics 3, 5, 6 already exercised the library against real workloads — this epic verifies the cross-repo `dogfood-integration.yml` workflow stays green across both downstream repos, closes any remaining gap in `rf-mcp` + `robotframework-agentskills` custom-test parity, and authors the final FR65 0.x→1.0 Exit Criteria doc content from Phase 1 retrospective evidence.

**FRs covered:** None directly (exercises existing keyword surface against real workloads). Satisfies **AC-DOGFOOD-01** and **NFR-REL-05** and closes **FR65** content.

**Dependencies:** Epics 2 through 8b (full Phase 1 keyword surface must exist and survive interleaved dogfood).

**Primary persona:** Agent Developer (Raj's Journey 5 close); all personas benefit from Phase 1 stability bar.

---

### Epic 10 [Phase 2]: Native Agent SDK Adapters

**Goal:** Ship Claude Agent SDK + OpenAI Agents SDK adapters under the established `InProcessAdapter` ABC. Amelia's Phase-2A split — Anthropic-side first, OpenAI-side parallel-ready. Lays AdapterVersionDriftWarning groundwork (full wiring in Epic 11 once ≥2 Tier-1 CLI adapters ship per ADR-A4).

**FRs covered:** FR13c (Claude Agent SDK), FR13d (OpenAI Agents SDK).

**Dependencies:** Epic 4 (Generic + CC CLI as reference impl) + Phase 1 completion.

**Primary persona:** Agent Developer (multi-runtime support).

---

### Epic 11 [Phase 2]: CLI Adapters + AdapterVersionDriftWarning

**Goal:** Ship Codex CLI + Copilot CLI adapters under `SubprocessAdapter` ABC. With CC CLI (Epic 4) + Codex + Copilot all live, `AdapterVersionDriftWarning` (FR60) can ship fully wired per ADR-A4. Closes the Tier-1 adapter set under ADR-005's "≤2 per vendor + 1 universal" rule.

**FRs covered:** FR13e (Codex CLI), FR13f (Copilot CLI), FR60 (AdapterVersionDriftWarning).

**Dependencies:** Epic 4 (SubprocessAdapter ABC + CC CLI reference) + Epic 10 (concurrent if desired).

**Primary persona:** Agent Developer (full multi-runtime coverage).

---

### Epic 12 [Phase 2]: LLM-Judge + Rubric Calibration

**Goal:** `Judge.Get Score` ships with rubric calibration against human-labeled scenarios. Amelia's call: this is its own epic because LLM judge calibration is weeks of work (calibration set construction + agreement scoring + threshold tuning). Closes Devon's Journey 4 Tier-2 portion (stacked validation: Tier-1 static + Tier-3 activation reliability from Phase 1 + Tier-2 judge here).

**FRs covered:** FR48 (Judge.Get Score with rubric calibration — pattern informed by agentguard ADR-011, evaluated on merit for agenteval).

**Dependencies:** Phase 1 completion + Epic 6 (statistical primitives for calibration agreement scoring).

**Primary persona:** Agent Surface Author (Devon's full three-tier validation flow).

---

### Epic 13 [Phase 2]: Advanced Stats + OTLP + Cross-Adapter Discoverability (Tool + Skill) + HTML Polish

**Goal:** Phase 2 maturity surface: Mann-Whitney U + Cliff's δ + Bootstrap CI behind `[agenteval-advanced]` extra (FR29a/b/c); OTLP trace export to production observability backends (FR33b OTLP); `Compare Tool Discoverability` cross-adapter with statistical significance (FR10b, requires ≥2 fully-shipped Tier-1 runtimes from Epic 11); HTML cohort heatmap rendering (FR55 HTML).

**FRs covered:** FR10b (Compare Tool Discoverability cross-adapter), FR29a (Mann Whitney U), FR29b (Cliff Delta), FR29c (Bootstrap CI), FR33b OTLP, FR55 `as_html()`.

**Dependencies:** Phase 1 completion + Epic 11 (≥2 Tier-1 CLI adapters for cross-adapter discoverability).

**Primary persona:** Agent Developer (multi-model statistical comparison) + Agent Surface Author (cross-runtime cohort) + observability-focused QA Engineers (OTLP integration).

---

## Epic Story Details

Stories listed per epic in implementation order. Stories within an epic are self-contained and must not depend on future stories.

---

### Epic 0: Spikes & Architectural Decisions

#### Story 0.1: Run Hosted-MCP Universal Observer Spike

As an **architect** (representing all Phase 1 stakeholders),
I want a 5-day spike on the hosted-MCP universal observer pattern,
So that **ADR-007 lands with empirical evidence** about which trace-observation backend pattern survives MCP server diversity (stdio + streamable_http + in-memory) and Listener v3 per-test scope concurrency — before Epic 5 commits to a `mcp/observer.py` API surface.

**Acceptance Criteria:**

**Given** an MCP server hosted in-process (via the in-memory transport) and a second MCP server launched as a subprocess (via stdio transport),
**When** the spike's observer implementation captures tool-call traces from both during a single `.robot` suite execution,
**Then** the observer produces a coherent `mcp_coverage` field per `AgentRunResult` reflecting which observation path provided the data (one of `"hosted_in_process"`, `"subprocess_with_observer"`, or `"external_mixed"`).

**And Given** the spike completes,
**When** the architect reviews the output,
**Then** a written findings document lands at `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` covering: (a) which transports the observer pattern supports, (b) edge cases where coverage degrades to `"external_mixed"`, (c) recommended ADR-007 amendments, (d) any breaking changes to the planned `mcp/observer.py` API surface that affect Epic 5 story planning.

**And** the findings document explicitly answers: "does the observer survive a hosted MCP server with concurrent Listener v3 per-test scope under `pabot --processes 4`?" with reproducible evidence (commands + captured output).

---

#### Story 0.2: Run Per-Test MCP Cleanup-Under-Pabot Spike

As an **architect**,
I want a 3-day spike on per-test MCP scope cleanup under `pabot` parallel execution,
So that **ADR-A6 (MCP coverage detection default) and ADR-A8 (sandbox policy Phase 1) land with empirical evidence** about which cleanup strategy survives 8-process concurrent test execution per NFR-PERF-05 — before Epic 1b commits to the `_kernel/context.py` API surface and Epic 3 commits to `mcp/transport.py` cleanup semantics.

**Acceptance Criteria:**

**Given** a representative `.robot` test suite running under `pabot --processes 8` with `mcp_per_test="test"` mode,
**When** each test independently starts and stops MCP servers via the spike's prototype `_kernel/context.py` cleanup primitive,
**Then** no MCP server processes leak after the suite completes, verified via OS-level process inventory diff (before vs. after) on **Linux required; macOS deferred to Phase-1.5** (architect waiver per D2.1 review decision 2026-05-17).

**And Given** the same suite is re-run with `mcp_per_test="suite"` and `mcp_per_test="process"` modes,
**When** measured against the `mcp_per_test="test"` mode,
**Then** a cleanup-overhead measurement table is produced (mean + P95 startup/shutdown latency per mode, **Linux only — macOS deferred to Phase-1.5**, per MCP server type — bundled echo, rf-mcp, custom Python).

**And Given** the spike completes,
**When** the architect reviews the output,
**Then** a findings document at `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` covers: (a) which cleanup strategy works reliably, (b) measured overhead supporting NFR-PERF-03d cost trade-off table updates, (c) the precise `_kernel/context.py` API surface needed by Epic 1b (function signatures + lifecycle hooks), (d) any recommended ADR-A6 + ADR-A8 amendments.

---

#### Story 0.3: Amend & Ratify Spike-Dependent ADRs

As an **architect**,
I want **ADR-007** (hosted-MCP universal observation), **ADR-A6** (MCP coverage detection default), and **ADR-A8** (sandbox policy Phase 1) updated with empirical findings from Stories 0.1 and 0.2 and formally ratified,
So that downstream epics (Epic 1b kernel, Epic 3 MCP lifecycle, Epic 5 trace observability) implement against grounded decisions instead of speculative API shapes — and the Phase 1 ADR slate has zero `proposed`-status ADRs blocking implementation.

**Acceptance Criteria:**

**Given** findings documents from Stories 0.1 and 0.2 are merged,
**When** I amend ADR-007 + ADR-A6 + ADR-A8 with the empirical findings inline (in their Decision and Consequences sections),
**Then** each amended ADR is committed to `docs/adr/` with status `accepted` (no longer `proposed`), and each amendment cites the source findings document.

**And** the ADR-001 Architectural Influences Catalog is updated to record the three amendments (date + summary line per ADR).

**And** a brief delta note (≤200 words) is appended to `_bmad-output/planning-artifacts/architecture.md` Step-4 section, linking to the ratified ADRs and flagging any deviations from the original Step-4 critical-decision defaults.

**And** the ratified ADRs unblock Story 1b.1 (`_kernel/context.py` implementation), Story 3.1 (MCP lifecycle keywords), and Story 5.1 (hosted-MCP observer implementation) — verified by the Epic 1b / 3 / 5 story preludes referencing the ratified ADR IDs without `proposed`-status warnings.

---

### Epic 1a: Project Bootstrap + CI + ADR Ratification + Project-Hygiene Documentation

#### Story 1a.1: Project Bootstrap (Standalone Python+RF Library)

As a **contributor**,
I want a working `uv sync` against a freshly cloned `robotframework-agenteval` repository that produces a green import of the empty `AgentEval` package,
So that subsequent epics can land code without first fighting build/install plumbing.

**Acceptance Criteria:**

**Given** standard Python+RF library conventions and a curated set of dependencies the architecture identified (`robotframework>=7.3`, `mcp>=1.10`, `litellm>=1.50`, `opentelemetry-api`, `opentelemetry-sdk`, `pyyaml`, `jsonschema`; `[dev]` extras: `pytest`, `pytest-cov`, `ruff`, `mypy`, `pabot`),
**When** I author `pyproject.toml` + `uv.lock` + `.python-version` + `.gitignore` + `LICENSE` (Apache 2.0) + `hatchling` build config from scratch, optionally borrowing structural patterns from reviewed reference projects (`robotframework-agentguard` among them — adopt where its choices fit agenteval, diverge freely where agenteval has a better option),
**Then** `uv sync` completes without errors on Linux + macOS, and `python -c "import AgentEval"` succeeds against the empty package.

**And Given** the project layout from `architecture.md` Step-6 project tree,
**When** I create the directory skeleton (`src/AgentEval/{_kernel, _assertions, providers, telemetry, security, scenarios, mcp, skills, subagents, hooks, coding_agent, metrics, stats, reporting}/`, plus `tests/{unit, integration, conformance}/`, plus `docs/{adr, contracts, recipes}/`),
**Then** each directory contains a minimal `__init__.py` (for src dirs) or `.gitkeep` (for test/doc dirs) and the tree matches the architecture's project-tree section.

**And** the `pyproject.toml` declares Apache 2.0 license, author = "Many Kasiriha", project URLs (GitHub + PyPI placeholder), Python `>=3.12`, and an empty `[project.entry-points."robotframework_agenteval.adapters"]` table (registration mechanism per FR17a).

---

#### Story 1a.2: Set Up 7 GitHub Actions CI Workflows

As a **contributor**,
I want 7 CI workflows running automatically per the architecture project tree (`ci`, `nightly-live`, `conformance`, `security-scan`, `dogfood-integration`, `docs-build`, `release`),
So that quality, security, and release-hygiene gates catch regressions before merge, CodeQL surfaces vulnerabilities introduced by new code, NFR-REL-03 (nightly live-LLM coverage), NFR-REL-05 (dogfood integration), NFR-MAINT-03 (PyPI OIDC trusted publishing), and NFR-MAINT-04 (docs-build asserts required sections exist) are gated in CI from Phase-1 day one.

**Source-of-truth ratification (2026-05-17):** The architecture.md §Complete Project Directory Structure (Step-4 Ratification Delta 2026-05-17) is the authoritative source for this 7-workflow list. This story description was updated 2026-05-17 to align with that source (previously listed `{test, lint, typecheck, conformance, security-scan, dogfood-integration, release}.yml`, which conflicted with architecture's project tree). Spec drift caught and corrected pre-create-story per the "pre-create-story spec-vs-ratified-doc check" project norm established 2026-05-17.

**Acceptance Criteria:**

**Given** the project bootstrap from Story 1a.1,
**When** I author `.github/workflows/{ci, nightly-live, conformance, security-scan, dogfood-integration, docs-build, release}.yml`,
**Then** each workflow has at minimum: appropriate trigger (push / pull_request / schedule / release as relevant), runner (`ubuntu-latest` for Phase 1 per D2.1 architect macOS waiver inherited from Story 0.2), Python `3.12` + `3.13` matrix for `ci.yml`, `uv sync` step, and a Phase-1-safe placeholder step (e.g., `pytest tests/unit -q --collect-only` or `python -c "import AgentEval; print('ok')"`) — real test invocations land per-epic as fixtures and code arrive.

**And Given** the `ci.yml` workflow (PR-gating),
**When** any PR is opened against `main`,
**Then** the workflow runs `pytest tests/unit -q` (collect-only allowed in Phase 1 where no unit tests yet exist), `pytest tests/acceptance/smoke -q` + `pytest tests/acceptance/tier1 -q` (collect-only allowed where empty), `ruff check src/ tests/`, `ruff format --check src/ tests/`, `mypy src/`, AND `pytest tests/unit/conventions -q` (convention enforcers per architecture §Tests Folder Structure).

**And Given** the `nightly-live.yml` workflow (NFR-REL-03),
**When** the GitHub Actions cron schedule fires (daily on `main`),
**Then** the workflow runs `pytest tests/integration -m live` + `pytest tests/acceptance -m tier3`. Phase 1 placeholder pass-step acceptable where no integration tests exist yet; real invocations land in Epic 4+ (live coding-agent adapters).

**And Given** the `conformance.yml` workflow (per-release / on-demand),
**When** triggered manually via `workflow_dispatch` OR on a release tag,
**Then** the workflow runs `pytest tests/conformance` against all Tier-1 adapters registered in `agenteval.coding_agents` entry points. Phase 1 placeholder pass-step acceptable; adapters land in Epic 1b + Epic 4.

**And Given** the `security-scan.yml` workflow,
**When** a PR is opened or merged to `main`,
**Then** GitHub CodeQL analysis runs on the diff plus a weekly full-repo scan (cron), surfacing security findings as PR annotations and the GitHub Security tab. `security-scan.yml` explicitly replaces the retired `agentguard-drift-check.yml` (originally proposed under retired NFR-MAINT-06 / ADR-A4) — `robotframework-agentguard` is inspiration-only, not a drift target.

**And Given** the `dogfood-integration.yml` workflow scaffolding (NFR-REL-05),
**When** a `release-pending`-labeled PR is opened OR a tagged release fires,
**Then** the workflow clones the planned downstream targets (`rf-mcp`, `robotframework-agentskills`) at their current `main` and runs their test suites against the PR's `agenteval` wheel built via `uv build`. Phase 1 placeholder pass-step acceptable where the downstream repos don't yet integrate `agenteval`; real cross-repo invocations land per-epic during dogfood interleaving (Epics 3, 5, 6).

**And Given** the `docs-build.yml` workflow (NFR-MAINT-04),
**When** triggered on a release tag OR via `workflow_dispatch`,
**Then** the workflow runs `robot --pythonpath src --output NONE --report NONE --log NONE` libdoc generation across `src/AgentEval/` keywords, builds `docs/contracts/` rendered output, AND asserts each contract doc contains the architecture-mandated sections (purpose, scope, contract, change-policy) via a grep-based section-presence check. Phase 1 placeholder pass-step acceptable where the libdoc surface is empty.

**And Given** the `release.yml` workflow (NFR-MAINT-03),
**When** a release tag (e.g., `v0.0.1`) is pushed AND the `release-pending` label is present on the merge commit's PR,
**Then** the workflow runs `uv build` to produce wheel + sdist, then `uv publish` via PyPI OIDC trusted publishing (no `PYPI_TOKEN` secret — uses GitHub's OIDC token exchange). Phase 1: release is wired but PyPI trusted-publisher claim setup is deferred until first real release; the workflow may print "dry-run" and skip `uv publish` if the OIDC claim is not yet configured.

**And** all 7 workflows green on a trivial PR (empty test suite, empty `_kernel/` modules) — verified by opening a PR against `main` that modifies only this story's content.

**And** every workflow uses `actions/checkout@v4` + `astral-sh/setup-uv@v3` + caches `~/.cache/uv` keyed by `pyproject.toml` hash for fast cold-starts.

**Note:** `agentguard-drift-check.yml` (originally proposed under retired NFR-MAINT-06 / ADR-A4) is intentionally NOT included — `robotframework-agentguard` is an inspiration-only reference, not a dependency to drift-check against. `security-scan.yml` (CodeQL) takes its place as a more valuable CI workflow.

---

#### Story 1a.3: Ratify Non-Spike ADRs + Author ADR-001 Architectural Influences Catalog

As an **architect**,
I want the 15 non-spike ADRs committed to `docs/adr/` with `accepted` status, and ADR-001 "Architectural Influences Catalog" authored documenting patterns reviewed across multiple reference projects (`robotframework-agentguard` + competitor MCP-eval frameworks + relevant standards) with explicit adopt / adapt / diverge rationale per pattern,
So that every subsequent epic implements against ratified decisions, and the project's architectural inheritance is transparent without implying any dependency or required alignment with `robotframework-agentguard` or any other source.

**Acceptance Criteria:**

**Given** the ADR backlog sidecars at `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` (ADR-005..014, 10 ADRs) and `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` (now 7 ADRs after ADR-A4 retirement: ADR-A1, A2, A3, A5, A6, A7, A8),
**When** I copy each non-spike ADR (excluding ADR-004 (was ADR-007) + ADR-016 (was ADR-A6) + ADR-018 (was ADR-A8) which Epic 0 owns and ratified into `docs/adr/` on 2026-05-17; ADR-A4 already retired) into `docs/adr/` using the MADR template (status, context, decision, consequences, alternatives),
**Then** the resulting ADR files exist with `status: accepted`, numbered consistently per the architecture's renumbering plan, each referencing source PRD/architecture sections.

**And Given** `robotframework-agentguard` at `/home/many/workspace/robotframework-agentguard` (one reviewed reference project) + competitor MCP-eval projects (`wolfeidau/mcp-evals`, `lastmile-ai/mcp-eval`) + relevant standards (OpenTelemetry GenAI semantic conventions, Model Context Protocol specification),
**When** I author `docs/adr/ADR-001-architectural-influences-catalog.md`,
**Then** the Catalog lists each reviewed pattern with: (a) source project + reference (URL / commit / ADR ID), (b) what the pattern does, (c) decision for agenteval — exactly one of `adopt-verbatim`, `adapt`, `borrow-concept`, `explicitly-diverge`, or `not-applicable`, (d) a one-line rationale per decision.

**And** the Catalog is explicit about scope: it credits influences but creates **no obligation** to stay aligned with any source project. agenteval is free to evolve its decisions independently of any catalogued source.

**And** the Catalog is committed at `docs/adr/ADR-001-architectural-influences-catalog.md` with status `accepted` and linked from `docs/adr/README.md` (index file).

---

#### Story 1a.4: Author 11 Doc-Contract Skeletons

As a **contributor or downstream consumer**,
I want all 11 doc-contract skeletons present at `docs/contracts/` with consistent structure (purpose, scope, contract, change-policy),
So that future epics can fill in contract details against an agreed structure, and external consumers can audit the library's contracts without spelunking the code.

**Source-of-truth ratification (2026-05-18):** The 11-contract list comes from architecture.md §Complete Project Directory Structure → `docs/contracts/` (L1419-1428) — the 9 architecture-canonical contracts — PLUS 2 empirically-justified additions (`listener-integration.md` per Story 0.1/0.2 RF Library vs Regular Listener findings; `junit-xml-enrichment.md` per FR49 JUnit XML emission contract). Previous epics.md spec drift (title:9 / body:10 / AC:11 / final-sentence:9, plus dropping evidence-block-format + otel-trace-visual, plus adding non-architecture-blessed tier-model + sandbox-protocol) corrected pre-create-story 2026-05-18 per `feedback_spec_vs_ratified_doc_precheck` project norm.

**Acceptance Criteria:**

**Given** the 11 doc-contract names — **9 architecture-canonical** (per architecture.md L1419-1428: `evidence-block-format.md`, `determinism-contract.md`, `stability-surface.md`, `exit-criteria-0x-to-1x.md`, `otel-trace-visual.md`, `error-class-hierarchy.md`, `mcp-coverage-detection.md`, `conformance-fixture-format.md`, `coding-conventions.md`) PLUS **2 empirically-justified additions** (`listener-integration.md` per Story 0.1/0.2 RF Library vs Regular Listener scoping findings; `junit-xml-enrichment.md` per FR49 contract),
**When** I create each file at `docs/contracts/<name>.md`,
**Then** each has at minimum: (a) Purpose section (≤100 words explaining what this contract governs), (b) Scope section (in-scope / out-of-scope bullets), (c) Contract section (placeholder for the formal specification — filled by the epic that owns the contract), (d) Change Policy section (how the contract can evolve — links to `stability-surface.md` labels).

**And Given** the `error-class-hierarchy.md` skeleton,
**When** I author its initial content,
**Then** it specifies the FR59 error-format requirement: every Tier-1 setup-failure error MUST surface (file path, line number, field name at fault, fix suggestion if applicable) in its `__str__` representation; lists all error leaves from ratified ADR-014 (`AgentEvalError` base + 4 sub-bases + 11 leaves — see ADR-014 table) with one-line description each; references which epic implements each class.

**And** `docs/contracts/README.md` index file lists all 11 contracts with one-line description each, linked.

**Note (2026-05-18 spec correction):** Previously-listed `tier-model.md` and `sandbox-protocol.md` are NOT separate doc contracts — they are subsections of `determinism-contract.md` (tier model + ACL gates) and `stability-surface.md` (sandbox Protocol surface). `agentguard-inheritance.md` remains retired per ADR-A4 / NFR-MAINT-06 retirement (2026-05-17).

---

#### Story 1a.5: Project Hygiene — CONTRIBUTING + SECURITY + Issue Templates + License Headers

As a **contributor or potential security reporter**,
I want `CONTRIBUTING.md`, `SECURITY.md`, GitHub issue templates, and Apache 2.0 license headers on every source file,
So that the project meets open-source hygiene baseline before the first external contributor or vulnerability report arrives.

**Acceptance Criteria:**

**Given** the project bootstrap from Story 1a.1,
**When** I author `CONTRIBUTING.md` at the repo root,
**Then** it covers: dev environment setup (`uv sync`), test invocation (`pytest`, `robot --listener AgentEval.telemetry.listener tests/`), PR conventions (commit message format, PR title format), conformance-suite requirement for new keywords (every Tier-2/3 keyword needs a conformance fixture per AC-CONFORMANCE-01), and the contributor agreement decision: **DCO sign-off required** (standard OSS practice; chosen on merit for agenteval's contribution model — no comparative reference to other projects required).

**And** `SECURITY.md` exists at the repo root specifying responsible disclosure policy: report channel (private GitHub security advisory), expected acknowledgement time (≤7 days), embargo period (≤90 days), credential-redaction guarantee (FR38a/b — traces never contain raw credentials in published reports).

**And** `.github/ISSUE_TEMPLATE/{bug-report, feature-request, question}.md` exist with templated frontmatter (labels, assignees) and structured prompts (for `bug-report`: RF version + agenteval version + minimal `.robot` reproducer + expected vs actual).

**And Given** Apache 2.0 license header text (standard 11-line copyright notice),
**When** I run a one-time script (`scripts/apply-license-headers.py`) over `src/AgentEval/**/*.py`,
**Then** every Python source file in `src/` has the Apache 2.0 header at top, and a `pre-commit` hook (or CI check in `lint.yml`) validates the presence of the header on all new `.py` files going forward.

---

#### Story 1a.6: Wire FR42 + FR43 + FR44 Library Defaults + Stability/Exit-Criteria Doc Stubs

As a **library consumer**,
I want sensible defaults wired into the `AgentEval` Robot Framework library entry point (FR42), plus opt-in scaffolding for `allow_validate_operator` (FR43 wiring; enforcement Epic 6) and `telemetry=False` (FR44 OTel disable), plus skeletons for the Stability Surface doc (FR64) and Exit Criteria doc (FR65),
So that consumers get a coherent first-import experience and the stability + exit-criteria contracts are visible from Day 1 even before content is populated.

**Acceptance Criteria:**

**Given** the `AgentEval` package at `src/AgentEval/__init__.py`,
**When** the library is imported via `Library    AgentEval` in a `.robot` file with no kwargs,
**Then** the 9 defaults from PRD FR42 + FR11b apply (documented in `docs/contracts/stability-surface.md` Phase-1 registry + `.env.example` env-var template):
- `provider="litellm"` (FR42 — provider plugin selection per ADR-013)
- `telemetry=True` (FR42 + FR44 — OTel listener on; opt-out via `telemetry=False`)
- `trace_backend="memory"` (FR42 — in-memory trace store; `jsonl` Phase-1, `otlp` Phase-2)
- `allow_validate_operator=False` (FR42 + FR43 — AssertionEngine `validate` operator gate; default-deny per `eval()` safety per NFR-SEC-02)
- `default_temperature=0.0` (FR42 — deterministic provider calls)
- `mcp_per_test=True` (FR42 + ADR-009 — per-test MCP server isolation; valid values: `True | "suite" | False` per architecture L314 3-mode design)
- `allow_external_mcp_blind=False` (FR42 + ADR-016 — external-MCP coverage gate; default-deny; `IncompleteTraceError` on `mcp_coverage="external_mixed"`)
- `max_cost_usd=5.00` (FR42 + ADR-015 — `@guarded_fanout` cost guardrail)
- `max_runtime_seconds=None` (FR11b — Tier-3 fan-out wall-clock guardrail; default `None` = no cap; opt-in)

(Default set ratified 2026-05-18 per Story 1a.6 pre-create-story drift correction; previous epics.md draft listed `mcp_per_test="suite"` and a 6-default subset — superseded by PRD FR42 + ADR-009 ratified 8-default canonical + FR11b 9th.)

**And Given** the same library import,
**When** the consumer passes `Library    AgentEval    allow_validate_operator=True    telemetry=False`,
**Then** both kwargs are accepted without error and threaded through the library's `__init__` to internal state — gate enforcement (raising `PollingDisallowedError` when `validate` is used without the flag) lives in Epic 6, but the wiring + accessor (`Get Effective Config` shows the flag values) lives here.

**And** `docs/contracts/stability-surface.md` skeleton exists documenting the labels (`stable`, `provisional`, `experimental`) per FR64; per-keyword labels are populated by the epics that ship the keywords. (Label set ratified 2026-05-18 per Story 1a.6 pre-create-story drift correction; previous draft used `stable/beta/experimental/deprecated` — superseded by PRD FR64 + Story 1a.4 ratified `docs/contracts/stability-surface.md` content.)

**And** `docs/contracts/exit-criteria-0x-to-1x.md` stub exists per FR65 listing the 0.x→1.0 promotion criteria placeholder (filled in Epic 9 close): conformance coverage threshold, dogfood parity bar, ADR completeness, public API stability period — each currently `TBD` with rationale "filled in Phase 1 close per FR65". (Slug ratified 2026-05-18; previous draft used `exit-criteria.md` — superseded by architecture L1423 + PRD FR65 + Story 1a.4 ratified slug.)

---

### Epic 1b: Cross-Cutting Kernel + Conformance Scaffolding + Determinism Contract

#### Story 1b.1: Foundational Kernel — Context + Tier + Async Bridge

As a **subsequent-epic implementer** (Epics 2-8b),
I want the three foundational `_kernel/` modules (`context.py` for per-test scope, `tier.py` for `@tier(N)` keyword annotation, `run_async.py` for async-to-sync bridging) implemented and unit-tested,
So that every other kernel module + sub-library can build on a stable per-test-scope/tier/async-bridge foundation without re-deriving primitives.

**Acceptance Criteria:**

**Source-of-truth ratification (2026-05-18):** Pre-create-story drift check (5th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 6 drifts in this story's spec vs ratified sources: (1) `mcp_per_test` enum translation undefined (user kwarg `bool | Literal["suite"]` vs internal Scope `Literal["test", "suite", "process"]`); (2) `_kernel/context.py` scope drastically underspecified — Story 0.2 spike findings §`_kernel/context.py` draft (L273-414) is the LOAD-BEARING source per the spike's explicit hand-off to Story 1b.1, including `MCPLifecycleManager` + `ServerSpec` + `ServerHandle` + `ReleaseResult` + atexit failsafe + auto-installed SIGTERM handler + all 12+ deferred-work items; (3) `tier.py` attribute name `__agenteval_tier__` vs architecture L620 `_agenteval_tier`; (4) ADR-A1 citation drift (ratified as ADR-012); (5) FR41 (env-var precedence) wiring assigned to Story 1b.1 by Story 1a.6's docstring but unscoped in epics.md; (6) `TestContext` dataclass invented in epics.md with no ratified source. All 6 resolved by honoring ratified sources; epics.md updated below pre-authoring per "fix-the-losing-source-NOW" pattern.

**Given** the ratified ADRs from Epic 0 — ADR-016 (was ADR-A6) amended with Story 0.1 trust-floor + adapter contract findings; ADR-018 (was ADR-A8) ratified as-is with Story 0.2 cross-cutting confirmation; ADR-004 (was ADR-007) amended with Story 0.1 handler-wrap pattern; **and Story 0.2 spike findings §`_kernel/context.py` draft (LOAD-BEARING per spike's Story-1b.1 hand-off, with 18 review patches P2.1-P2.18 + atexit-on-SIGTERM auto-handler integrated)**,
**When** I implement `src/AgentEval/_kernel/context.py`,
**Then** the module exposes:
- **`Scope = Literal["test", "suite", "process"]`** — internal scope enum (matches Story 0.2 spike's `MCPLifecycleManager.scope`).
- **`_resolve_scope(mcp_per_test: bool | Literal["suite"]) -> Scope`** — the SINGLE canonical translator between the user-facing Library kwarg vocabulary (FR42 + ADR-009 + Story 1a.6: `True` / `"suite"` / `False`) and the internal Scope vocabulary (`"test"` / `"suite"` / `"process"`). Mapping: `True → "test"`, `False → "process"`, `"suite" → "suite"`.
- **`TestContext` dataclass** with `test_id: str`, `suite_id: str`, `scope: Scope` (uses the internal Scope enum). ContextVar-backed `current_context() -> TestContext | None` accessor + `bind_context(ctx: TestContext) -> None` / `unbind_context() -> None` lifecycle functions. Architecture L1554's module-level `set_current_test_id(test_id)` is implemented as a convenience wrapper around `bind_context()`.
- **`MCPLifecycleManager`** + `ServerSpec` (with `env: MappingProxyType` per deferred-work.md L46 + P2.15) + `ServerHandle` + `ReleaseResult` + `acquire(test_id, suite_id, spec) -> ServerHandle` + `release_test(test_id)` + `release_suite(suite_id)` + `shutdown_all()` + `atexit` failsafe registration in `__init__` + **auto-installed SIGTERM→sys.exit handler in `__init__` per D2.4 LOAD-BEARING finding** (configurable via `install_sigterm_handler=False`). Concrete behavior cited in the module docstring per the spike's findings doc.
- **All 12+ Story 0.2 deferred-work items applied:** `threading.RLock` (P2.8); spawn outside the lock; `pid` directly as pgid since `start_new_session=True`; EPERM/ESRCH distinction in `_kill`; post-kill liveness verification; state-transition release event recording; minimize child env (`os.environ.copy()` leaks credentials); `MappingProxyType` for `ServerSpec.env` (P2.15); `startup_timeout_s` either implemented or removed from API (P2.4); split `shutdown_latency_ms` into `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms`; rename `startup_latency_ms` → `process_lifetime_ms` (P2.2); document atexit-on-SIGKILL unrecoverable + operator-mitigation note (D2.2). See `deferred-work.md` L40-47 for the full list with rationale per item.

**And** `src/AgentEval/_kernel/context.py` ALSO wires **FR41 (config precedence: kwarg → env-var → `.env` → defaults)** — `resolve_config(kwargs: dict[str, Any]) -> dict[str, Any]` function that takes kwarg overrides + reads `AGENTEVAL_*` env-vars (per `.env.example`) + loads `.env` if present + falls back to PRD FR42 defaults; returns the precedence-resolved config dict consumed by `AgentEval.__init__` (Story 1a.6's `Get Effective Config` keyword will return precedence-resolved values once this lands). Unit tests cover all 4 precedence layers + missing-env-var fallback + `.env` parsing.

**And** `src/AgentEval/_kernel/tier.py` exposes a `@tier(N: Literal[1, 2, 3])` decorator that attaches **`_agenteval_tier`** (single-underscore convention per architecture L620, NOT `__agenteval_tier__` dunder) attribute to the decorated function, plus a `get_keyword_tier(func) -> int | None` accessor, plus a `tier_badge(tier: int) -> str` helper returning the libdoc badge text (e.g., `"[Tier 1 — Deterministic]"`).

**And** `src/AgentEval/_kernel/run_async.py` exposes `_run_async(coro)` per **ADR-012 (was ADR-A1)** — runs the coroutine via `asyncio.run()` from a synchronous context, with worker-thread fallback when called from an already-running event loop (IDE runners, nested test executions); no `nest_asyncio` import by default.

**And** unit tests in `tests/unit/kernel/test_{context, tier, run_async}.py` cover: `context.py` — `_resolve_scope` all 3 mappings, TestContext bind/unbind round-trip, ContextVar isolation across threads, MCPLifecycleManager acquire/release per scope, atexit failsafe scenarios, SIGTERM auto-handler installed, FR41 precedence layers; `tier.py` — decorator attaches `_agenteval_tier` attribute, libdoc badge text matches expectation, invalid tier raises ValueError; `run_async.py` — sync-context invocation, nested-loop fallback path, exception propagation.

**And** the modules pass `mypy --strict` and `ruff` checks per the lint workflow from Story 1a.2.

**And** `ci.yml` is restructured to actually-execute `tests/unit` (split from the collect-only sweep into a dedicated `uv run pytest tests/unit -q` step, no `--collect-only`, no exit-5 leniency) — generalizing the Story 1a.6 HIGH-1 lesson. The collect-only sweep narrows further to `tests/unit/conventions` (still placeholder until Story 1b.6 lands the 5 enforcement tests).

---

#### Story 1b.2: Trace + Observability Kernel — Trace Store + Redaction + Coverage

As a **trace producer** (Epic 5),
I want the three trace/observability `_kernel/` modules (`trace_store.py` wrapping OTel SDK `InMemorySpanExporter`, `redaction.py` enforcing credential redaction as a choke point, `coverage.py` computing `mcp_coverage` field values) implemented and unit-tested,
So that Epic 5 can ship the hosted-MCP observer + OTel listener against a stable kernel layer, and credential leaks are impossible-by-construction.

**Acceptance Criteria:**

**Source-of-truth ratification (2026-05-18):** Pre-create-story drift check (6th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 6 drifts in Story 1b.2 spec + 2 pre-emptive drifts in Story 1b.4 spec vs ratified sources: (1) `trace_store.py` API surface — spec said `TraceStore` class with `add_span/get_spans/clear` raw primitives; architecture L664-669 says 5 projection accessors function-style (`get_run_spans/get_tool_calls/get_usage/get_latency/get_run_manifest`) per "no direct span access by sub-libraries" rule; (2) `coverage.py` function name + intent — spec said `compute_mcp_coverage` (detect); ADR-016 L44 + architecture L384/L1058 say `_check_mcp_coverage(run, allow_external_mcp_blind)` (enforce + raise `IncompleteTraceError`); detection lives in adapters; (3) `errors.py` + `IncompleteTraceError` not in scope but required by ADR-016 + FR37; errors.py doesn't exist yet; (4) `redaction.py` SpanProcessor integration missing from spec; architecture L679 + L1193 says `_kernel/redaction.py` IS an OTel `RedactionProcessor` SpanProcessor; (5) `RunData` type undefined; ratified sources use `AgentRunResult`; (6) `Span` vs `ReadableSpan` type. All 6 resolved by honoring ratified sources. Story 1b.4 pre-emptive cleanup applied (D4 + D7 + D8 below): `__agenteval_tier__` dunder → `_agenteval_tier` single-underscore per architecture L620 + Story 1b.1 implementation; `AgentRunResult` location moved to top-level `src/AgentEval/types.py` per architecture L853; `mcp_coverage` Literal drops `"none"` to match ratified ADR-016 3-state value space.

**Given** Story 1b.1's `context.py` for per-test scope,
**When** I implement `src/AgentEval/_kernel/trace_store.py`,
**Then** the module exposes the **5 projection accessors per architecture L664-669 + Decision-2** ("no direct span access by sub-libraries" rule):
- `get_run_spans(test_id: str) -> list[ReadableSpan]` — all spans tagged with the given `test_id` (uses `current_context().test_id` from Story 1b.1's `_kernel/context.py` when no `test_id` is supplied). Returned in chronological order. Cross-test isolation enforced (test A's call never returns test B's spans).
- `get_tool_calls(test_id: str, source: Literal["adapter", "hosted_mcp", None] = None) -> list[ToolCallTrace]` — projection of `execute_tool` spans into `ToolCallTrace` Pydantic dataclasses (per FR35); `source` filter optional.
- `get_usage(test_id: str) -> Usage` — sum of `gen_ai.usage.*` attributes across `chat` spans.
- `get_latency(test_id: str) -> float` — sum of span durations.
- `get_run_manifest(test_id: str) -> RunManifest` — assembled per FR39 from resource attributes + library version + redaction-policy hash.

Internal `InMemorySpanExporter` lifecycle: TracerProvider configured with `agenteval.test_id` resource attribute read from `current_context()`; per-test cleanup hook `clear_spans(test_id: str)` invoked by the Listener's `end_test` (Epic 5 Story 5.1 wires it). Phase-1 memory backend only; jsonl + otlp backends in `agenteval/telemetry/` (Epic 5).

**And** `src/AgentEval/types.py` is **co-created in Story 1b.2** with the 3 Pydantic dataclasses needed by `trace_store.py`'s projection accessors per architecture L853:
- `ToolCallTrace(name: str, args: dict, result: Any, error: str | None, latency_ms: float, source: Literal["adapter", "hosted_mcp"], gen_ai_tool_call_id: str)` per FR35 + architecture L975-985.
- `Usage(input_tokens: int, output_tokens: int, cached_input_tokens: int = 0)` summing `gen_ai.usage.*` per architecture L984 (`gen_ai.usage.*` attribute namespace) + L667 (`get_usage(test_id) -> Usage` projection accessor) — corrected via Story 6.1 code-review 1-way Auditor HIGH-B 2026-05-20 (pre-edit `L967` was an asyncio anti-pattern code block, citation drift).
- `RunManifest(library_version: str, test_id: str, suite_id: str, redaction_policy_hash: str, started_at: datetime, ended_at: datetime, agenteval_tier_breakdown: dict[int, int])` per FR39 + architecture L669.
Subsequent stories (1b.4 CodingAgentAdapter; 1b.5 conformance harness) add `AgentRunResult` + related types to the same `types.py`.

**And** `src/AgentEval/_kernel/redaction.py` exposes:
- `redact(text: str, patterns: list[Pattern] | None = None) -> str` — primitive scrubbing of known credential patterns (API keys matching `sk-*`, `ANTHROPIC_API_KEY=*`, OpenAI keys, bearer tokens; default pattern list ships in module).
- `redact_dict(d: dict) -> dict` — recursive variant for nested config objects + JSONL serialization paths.
- `register_pattern(regex: str) -> None` — opt-in extension for project-specific credential patterns.
- **`RedactionProcessor(SpanProcessor)` class** per architecture L679 + L1193 — OTel `SpanProcessor` integration: `on_start(span, parent_context)` and `on_end(span)` hooks scrub span attributes (`gen_ai.request.messages`, `gen_ai.response.text`, `agenteval.tool.args`, etc.) via `redact()`. Single choke point per NFR-SEC-01 / FR38a. Epic 5 Story 5.1's TracerProvider configuration wires `RedactionProcessor → InMemoryExporter` chain.

**And** `src/AgentEval/_kernel/coverage.py` exposes **`_check_mcp_coverage(run: AgentRunResult, *, allow_external_mcp_blind: bool = False) -> None`** per ADR-016 L44 + architecture L384/L1058 — **enforces** the gate (does NOT compute; detection happens in adapters per ADR-016 §D4):
- Reads `run.metadata.mcp_coverage` (the ratified 3-state `Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per ADR-016 §Decision; **NO `"none"` value**).
- When `mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=False`: raises `IncompleteTraceError` per FR37 + ADR-016 L44.
- When `mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=True`: returns `None` (opt-in blind run; documented escape hatch per FR42 + ADR-016).
- When `mcp_coverage` is `hosted_in_process` or `subprocess_with_observer`: returns `None` (trace is complete per the trust-floor decision tree).
- The trust-floor decision tree itself (D1 amendment per ADR-016 L17-28) is exercised by ADAPTERS at metadata-population time; the kernel just consumes the resolved value.

**And** `src/AgentEval/errors.py` is **co-created in Story 1b.2** with the **MINIMAL subset** needed by `_check_mcp_coverage` per ADR-014 (was ADR-A3, ratified 2026-05-17): `AgentEvalError(Exception)` base + `AgentEvalIntegrityError(AgentEvalError)` sub-base + `IncompleteTraceError(AgentEvalIntegrityError)` leaf with `error_code = "TRACE_INCOMPLETE"`. The other 8 leaves (`PollingDisallowedError`, `CostExceededError`, `RuntimeBudgetExceededError`, `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `TierViolationError`, `SandboxRequiredError`, `ValidateOperatorDisallowed`) are added by the stories that need them (subsequent Epic 1b stories + Epic 3 + Epic 4 + Epic 6). Story 1b.2's `errors.py` MUST set up the base + sub-base structure cleanly so additions are pure extensions, not refactors.

**And** unit tests in `tests/unit/kernel/test_{trace_store, redaction, coverage}.py` + `tests/unit/test_errors.py` + `tests/unit/test_types.py` cover:
- `trace_store.py` — each of the 5 projection accessors with representative span fixtures; per-test isolation (test A's `get_run_spans()` never returns test B's spans); chronological ordering; `clear_spans(test_id)` semantics.
- `types.py` — `ToolCallTrace` + `Usage` + `RunManifest` Pydantic dataclass construction + serialization round-trip.
- `redaction.py` — known patterns scrubbed (API keys / bearer tokens), plain text unchanged, nested dict recursion, custom `register_pattern` extension; `RedactionProcessor` SpanProcessor's `on_end` scrubs span attributes correctly.
- `coverage.py` — `_check_mcp_coverage` raises `IncompleteTraceError` on `external_mixed` + `allow_external_mcp_blind=False`; returns None on the other 4 combinations (3 states × `allow=True` plus 2 non-failed states × `allow=False`). At least one explicit fixture exercises the trust-floor case (per ADR-016 §Decision L28: when both `hosted_in_process` AND `subprocess_with_observer` paths fire, the adapter populates `hosted_in_process` — kernel test verifies the kernel correctly accepts this value).
- `errors.py` — `IncompleteTraceError` inherits `AgentEvalError`; has `error_code = "TRACE_INCOMPLETE"`; the base + sub-base structure is correct.

**And** the modules pass `mypy --strict` and `ruff` checks.

---

#### Story 1b.3: Discovery + Guardrails Kernel — Entry-Points + Fan-Out Decorator

As an **adapter author** (Epic 4) **and Tool Discoverability consumer** (Epic 3 MVP, Epic 7 full guardrails),
I want the two discovery/guardrails `_kernel/` modules (`discovery.py` for adapter discovery via entry-points + direct composition, `guardrails.py` exposing the `@guarded_fanout` decorator) implemented and unit-tested,
So that custom adapters register cleanly via PyPA entry-points or programmatic composition (FR17a/b/c) and any fan-out keyword (Tool Discoverability, Pass@k) inherits cost + runtime guardrails by decoration without re-implementing the meter.

**Source-of-truth ratification (2026-05-19):** Pre-create-story drift check (7th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 8 drifts in Story 1b.3 spec vs ratified sources. All 8 resolved by honoring ratified sources: (D1) entry-point groups — spec mentioned only `robotframework_agenteval.adapters`; ADR-013 L47 + pyproject.toml ratify 6 tables (4 in `agenteval.*` namespace + 1 legacy + 1 RF-owned `robot.listener`); discovery.py exposes 4 group-specific accessors + generic helper; (D2) `@guarded_fanout` signature — spec used `cost_kwarg/runtime_kwarg`; ADR-015 §Decision L18 ratifies `estimator=callable`; (D3) `@guarded_fanout` enforcement — spec used 2 layers; ADR-015 §Decision L25-29 ratifies 3 layers (pre-flight + mid-run cost meter polling + mid-run wall-clock polling); (D4) `UnknownAdapterError` — spec invented it; docs/contracts/error-class-hierarchy.md L82 ratifies `AdapterDiscoveryError` for partial-install + lookup-miss cases; (D5) errors.py sub-base/leaf additions — Story 1b.3 adds 2 sub-bases (`AgentEvalBudgetError`, `AgentEvalCompatError`) + 3 leaves (`CostExceededError`, `RuntimeBudgetExceededError`, `AdapterDiscoveryError`) per ADR-014; (D6) `CodingAgentAdapter` forward-ref — Story 1b.4 lands the Protocol; Story 1b.3 uses TYPE_CHECKING; (D7) `KeywordTierMissingError` convention enforcer — architecture L648 says discovery.py raises this; Many's decision moves it to Story 1b.6 (which owns the 5 CI-enforcement conventions tests); (D8) ADR-013 filename drift in architecture L1426 — fixed pre-authoring (was `ADR-013-entry-points-discovery.md`, actual is `ADR-013-entry-points-discovery-infrastructure.md`).

**Acceptance Criteria:**

**Given** the Python entry-points groups declared in Story 1a.1's pyproject.toml — per ADR-013 ratified 6 tables: `agenteval.coding_agents` (FR17a, primary), `agenteval.providers` (FR17c), `agenteval.judges` (Phase-2 only), `agenteval.sandboxes` (per ADR-018), `robotframework_agenteval.adapters` (legacy FR17a backward-compat group), and the RF-owned `robot.listener` (FR33a),
**When** I implement `src/AgentEval/_kernel/discovery.py`,
**Then** the module exposes:
- `discover_adapters() -> dict[str, type["CodingAgentAdapter"]]` — loads `agenteval.coding_agents` (primary) + `robotframework_agenteval.adapters` (legacy, FR17a backward-compat) via `importlib.metadata.entry_points`. `CodingAgentAdapter` is a TYPE_CHECKING forward-ref (Story 1b.4 lands the Protocol).
- `discover_providers() -> dict[str, type]` — loads `agenteval.providers` (FR17c).
- `discover_sandboxes() -> dict[str, type]` — loads `agenteval.sandboxes` (per ADR-018).
- `_discover_entry_point_group(group_name: str) -> dict[str, type]` — generic underlying helper used by the 3 group-specific accessors above; not exposed publicly (sub-libraries call the typed accessors).
- `register_adapter(name: str, cls: type) -> None` — programmatic registration per FR17b (composition path that doesn't require an installed entry-point package).
- `get_adapter(name: str) -> type["CodingAgentAdapter"]` — lookup; raises `AdapterDiscoveryError` on miss (per docs/contracts/error-class-hierarchy.md L82; `UnknownAdapterError` is NOT in the ratified catalog — `AdapterDiscoveryError` covers both partial-install + lookup-miss cases).
- Entry-point loading errors are caught at the per-entry-point level + logged (one broken third-party adapter cannot block library import). Partial-install detection (entry-point points at a missing module / wrong import path) raises `AdapterDiscoveryError` with the `installed-vs-required-extras` diagnostic hint per ADR-013 L42.
- `robot.listener` group is NOT discovered by this module — RF owns it.
- `agenteval.judges` is Phase-2; no Phase-1 discover function (the group is declared in pyproject.toml for future use).

**And** `src/AgentEval/_kernel/guardrails.py` exposes `@guarded_fanout(estimator: Callable[[dict], tuple[float, float]] | None = None) -> Callable` per ADR-015 §Decision L18 — a decorator that wraps any fan-out keyword with the **3-layer enforcement per ADR-015 §Decision L25-29**:
- **Layer 1 — Pre-flight estimation**: when `estimator` is provided, calls `estimator(kwargs) -> (cost_estimate_usd, runtime_estimate_seconds)` BEFORE entering the keyword body. If either estimate exceeds the configured `max_cost_usd` or `max_runtime_seconds` from `AgentEval.__init__` (or env-var overrides per FR41 wired by Story 1b.1's `resolve_config`), raises `CostExceededError` or `RuntimeBudgetExceededError` without entering the keyword body. When `estimator=None`, the pre-flight layer is skipped (caller defers to mid-run meters only).
- **Layer 2 — Mid-run cost meter (Phase-1 stub)**: starts a USD meter that polls every `meter_interval_seconds` (default 5s; configurable via decorator kwarg). Phase-1 implementation: the actual provider cost-tracking API is stubbed (returns 0.0) until Epic 4 wires the real LiteLLM cost tracker. The meter loop + breach detection + `CostExceededError` raise + cooperative-cancellation hook ship in Story 1b.3 so Epic 4 just plugs in the cost source. Documented Phase-1 limitation.
- **Layer 3 — Mid-run wall-clock meter**: starts a wall-clock timer; polls every `meter_interval_seconds`. On breach, raises `RuntimeBudgetExceededError` (NOT at 1.1× — at exactly the configured budget per ADR-015 §Decision L29; the 1.1× wording in epics.md draft was unratified).
- Cooperative cancellation: when a mid-run meter breaches, the decorator sets an `asyncio.Event` / `threading.Event` that estimator-aware keywords can poll. Phase-1: the cancellation hook IS surfaced but caller must opt-in; full integration with Epic 4's provider client cancellation lands in Story 4.1.
- All 3 layers MUST integrate with Story 1b.1's `_run_async` for async-aware fan-out keywords (Tier-3 fan-out keywords commonly orchestrate async provider calls).

**And** `src/AgentEval/errors.py` is **extended in Story 1b.3** with 2 new sub-bases + 3 new leaves per ADR-014 catalog + docs/contracts/error-class-hierarchy.md (pure extension — no refactor of Story 1b.2's `AgentEvalError`/`AgentEvalIntegrityError`/`IncompleteTraceError`):
- `AgentEvalBudgetError(AgentEvalError)` — sub-base for cost/runtime budget breaches.
- `AgentEvalCompatError(AgentEvalError)` — sub-base for environment/version/compat issues.
- `CostExceededError(AgentEvalBudgetError)` — `error_code = "COST_EXCEEDED"`, exit code 66 (pinned by epics.md Story 8a.1 L1660). Raised by `@guarded_fanout` per ADR-015.
- `RuntimeBudgetExceededError(AgentEvalBudgetError)` — `error_code = "RUNTIME_BUDGET_EXCEEDED"`, exit code 75 (EX_TEMPFAIL per Story 1a.4 ratification). Raised by `@guarded_fanout` per ADR-015.
- `AdapterDiscoveryError(AgentEvalCompatError)` — `error_code = "ADAPTER_DISCOVERY_ERROR"`, exit code 78 (EX_CONFIG). Raised by `discovery.py` on partial-install (per ADR-013 L42) + on `get_adapter()` lookup miss.

**And** unit tests in `tests/unit/kernel/test_{discovery, guardrails}.py` + extended `tests/unit/test_errors.py` cover:
- `discovery.py` — entry-point loading for each of 3 typed groups (`coding_agents`/`providers`/`sandboxes`); legacy `robotframework_agenteval.adapters` fallback path; programmatic `register_adapter` + override-by-name behavior; `get_adapter` lookup miss raises `AdapterDiscoveryError`; broken-entry-point graceful degradation (one bad entry-point doesn't kill the whole load); `installed-vs-required-extras` diagnostic message format per ADR-013 L42.
- `guardrails.py` — pre-flight cost estimate raises `CostExceededError` (Layer 1); pre-flight runtime estimate raises `RuntimeBudgetExceededError` (Layer 1); mid-run cost-meter loop fires on schedule + raises on cumulative breach (Layer 2, with stubbed provider cost source); mid-run wall-clock-meter raises at exactly the budget (Layer 3, not 1.1×); cooperative-cancellation hook exposed + observable; `estimator=None` skips Layer 1; integration with `_run_async` for async-aware fan-out keywords; error message format surfaces cumulative cost at time of breach.
- `errors.py` — 2 new sub-bases inherit `AgentEvalError`; 3 new leaves inherit their sub-bases; `error_code` ClassVar attrs match the ratified strings exactly; base + sub-base + leaf 3-level hierarchy still extension-friendly for subsequent stories.

**And** the modules pass `mypy --strict` and `ruff` checks.

**Out of scope (deferred):** `KeywordTierMissingError` + the convention enforcer loop in `discovery.py` per architecture L648 is **deferred to Story 1b.6** (which owns the 5 CI-enforcement conventions tests). Story 1b.3's `discovery.py` ships the loader only — tier-annotation validation is a separate concern.

---

#### Story 1b.4: CodingAgentAdapter Protocol + InProcessAdapter / SubprocessAdapter ABCs

As an **Epic 4 implementer** (Generic + Claude Code CLI adapters) **and Phase 2 adapter authors** (Epics 10-11),
I want the `CodingAgentAdapter` Protocol + `InProcessAdapter` / `SubprocessAdapter` abstract base classes scaffolded with full type signatures, lifecycle hooks, and integration with `_kernel/discovery.py`,
So that concrete adapters (Generic LiteLLM, CC CLI, future SDK + CLI adapters) implement against a stable contract and the adapter cap rule (ADR-005 — ≤2 per vendor + 1 universal) has a structural enforcement point.

**Acceptance Criteria:**

**Source-of-truth ratification (2026-05-19):** Story 1b.4 pre-create-story drift check (8th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 14 drifts (6 HIGH + 4 MED + 4 LOW/clean) in the pre-2026-05-19 spec vs ratified sources. All 14 resolved by honoring ratified sources per the "fix-the-losing-source-NOW" pattern (Many's 2026-05-19 ratification). Key resolutions: (D1) single `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` Protocol method per PRD FR12 L1506 (NOT two-method `send_prompt + run_scenario`); (D2/D15) `AgentRunResult.metadata.{completeness, mcp_coverage}` nested per ADR-006 L15 + PRD FR36a/b L1553-1554 (NOT flat top-level fields); (D3/D4) reuse existing Story-1b.2 `ToolCallTrace` + `Usage` types (NOT new `ToolCall`/`TokenUsage` aliases); (D6/D7) drop undefined `Scenario`/`MCPServer`/`RawResponse`/`ParsedEvent` types — MCP lifecycle stays at Story 1b.1's `MCPLifecycleManager`, adapters consume `ServerHandle` instances via `run(... mcp_servers=...)`; (D8) Protocol class lives at `src/AgentEval/types.py` (re-exported from `coding_agent/base.py`) per architecture L853 cross-sub-library import discipline + Story 1b.3 `discovery.py` L102 TYPE_CHECKING forward-ref expectation; (D9) `InProcessAdapter` is direct-method-override pattern per ADR-003 L22-23 (NO abstract `_invoke_llm` hook + NO `RawResponse` type); (D10) `SubprocessAdapter` 3-hook template-method pattern per ADR-003 L24-29 + architecture L1228: `_spawn(prompt, **kwargs) -> subprocess.Popen` + `_parse_event(line: str) -> ParsedEvent | None` + `_finalize(events, exit_code) -> AgentRunResult` (NOT 2-hook `_subprocess_command`/`_parse_stream_output`); (D11) `_agenteval_tier` is set on keyword METHODS via `@tier(3)` per architecture L620 + Story 1b.1 tier.py implementation, NOT as a class attribute on the Protocol; (D13) `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf declaration belongs in Story 1b.4 errors.py (per Story 1b.3 errors.py L59 docstring) + per-adapter raise sites in Epic 4 Story 4.2 + Epic 11 Story 11.3 — error-class-hierarchy.md L81 ownership row amended pre-authoring. Scope-edges ratified: (a) FR47 error message exact format `<binary> version <X> outside tested range <range>` enforced by helper; (b) sandbox integration OUT-OF-SCOPE for adapters per architecture L1523 (sandbox routes through `scenarios/` + `security/policy.py`); (c) FR17b `coding_agent=` kwarg wiring on `AgentEval.__init__` deferred to Epic 4 Story 4.1 with forward-ref note.

**AC-1b.4.1** **Given** the kernel modules from Stories 1b.1-1b.3, **When** Story 1b.4 lands the Protocol + ABCs, **Then** `src/AgentEval/types.py` exposes the `CodingAgentAdapter` Protocol class (per architecture L853 cross-sub-library import discipline + Story 1b.3 discovery.py L102 TYPE_CHECKING forward-ref) with the single ratified method signature `run(prompt: str, tools: list[str] | None = None, mcp_servers: dict[str, ServerHandle] | None = None, **kwargs: Any) -> AgentRunResult` per PRD FR12 L1506, plus the read-only properties `name: str` (adapter identifier) + `version: str` (adapter package version). The Protocol does NOT carry a `_agenteval_tier` class attribute — tier semantics apply to library keywords (`Send Prompt`, `Run Scenario`) decorated with `@tier(3)` per Story 1b.1's `tier.py`, NOT to the adapter classes themselves. The Protocol uses `typing.Protocol` with `runtime_checkable` so `isinstance(obj, CodingAgentAdapter)` is supported at runtime for the FR17b composition path.

**AC-1b.4.2** **And** `src/AgentEval/coding_agent/base.py` re-exports `CodingAgentAdapter` from `src/AgentEval/types.py` (so contributor-facing imports use the documented `from AgentEval.coding_agent import CodingAgentAdapter` path AND so Story 1b.3 `_kernel/discovery.py` continues to import from `AgentEval.types` per its TYPE_CHECKING forward-ref pattern without circular-dep risk).

**AC-1b.4.3** **And** `src/AgentEval/coding_agent/base.py` exposes `InProcessAdapter` as a concrete-by-default base class for SDK-driven adapters per ADR-003 L22-23: "direct method-override pattern; no abstract hooks; SDK behavior is structured enough to populate `AgentRunResult` directly". Subclasses override `run()` directly. The base provides shared helpers (e.g., a default `name`/`version` property reading from `self.__class__.__module__`-derived metadata; a default constructor signature `__init__(self, **kwargs)` capturing adapter-side config) but ZERO `@abstractmethod`-decorated members.

**AC-1b.4.4** **And** `src/AgentEval/coding_agent/base.py` exposes `SubprocessAdapter(ABC)` as an abstract template-method base class for CLI-driven adapters per ADR-003 L24-29 + architecture L1228 with exactly 3 `@abstractmethod` hooks:
- `_spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]` — launches the CLI subprocess with proper env injection + `start_new_session=True` (per Story 1b.1 MCPLifecycleManager process-group hygiene precedent).
- `_parse_event(self, line: str) -> ParsedEvent | None` — parses one JSONL event line into the adapter's per-adapter intermediate event type `ParsedEvent` (declared as a `TypeAlias` for `Any` in `coding_agent/base.py` for Story 1b.4; concrete adapters in Epic 4/11 declare their own concrete intermediate types).
- `_finalize(self, events: list[ParsedEvent], exit_code: int) -> AgentRunResult` — folds the event stream into the final result.
The base class implements `run()` itself as a template method that orchestrates `_spawn` → JSONL-line iteration through `_parse_event` → `_finalize`. The base also provides the concrete `_assert_binary_version(self, binary: str, min: str, max: str | None) -> None` helper per FR47 + AC-1b.4.7.

**AC-1b.4.5** **And** `AgentRunResult` dataclass is added to `src/AgentEval/types.py` (the top-level types module per architecture L853) with these fields (all `@dataclass(frozen=True)` per Story 1b.2's stdlib-dataclass pattern):
- `response_text: str` — primary text output from the agent.
- `tool_calls: list[ToolCallTrace]` — tool invocations observed during the run; reuses Story 1b.2's `ToolCallTrace` type per architecture L885 (NOT a new `ToolCall` type).
- `usage: Usage` — token usage; reuses Story 1b.2's `Usage` type per architecture L984 (`gen_ai.usage.*` attribute namespace) + L667 (`get_usage(test_id) -> Usage` projection accessor) — corrected via Story 6.1 code-review 1-way Auditor HIGH-B 2026-05-20 (pre-edit `L967` was an asyncio anti-pattern code block, citation drift) (NOT a new `TokenUsage` alias).
- `metadata: AgentRunMetadata` — sub-dataclass containing the `.metadata.completeness` + `.metadata.mcp_coverage` fields per ADR-006 L15 + PRD FR36a/b L1553-1554 (nested, NOT flat). The nesting is REQUIRED by ADR-006.
- `cost_usd: float` — total USD cost reported by the provider (or 0.0 for Phase-1 stubs).
- `latency_seconds: float` — wall-clock duration of the `run()` call.
- `trace_id: str` — UUID hex string linking to the trace artifact at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` per PRD FR51 L1579. Format-specific contract (Phase-1 UUID hex vs Phase-2 OTel 32-char hex) documented in the dataclass docstring as a Phase-2 OTLP-migration carry-over.

**AC-1b.4.6** **And** `AgentRunMetadata` sub-dataclass is added to `src/AgentEval/types.py` with these fields:
- `completeness: Literal["complete", "truncated", "partial"]` per PRD FR36a L1553 — 3-state value space per ADR-006 L15 (NOT 4-state with `"none"`).
- `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per PRD FR36b L1554 + ADR-016 §Decision L24-28 — 3-state value space (NO `"none"` value).
Defensive `dict()` copy in `__post_init__` per Story 1b.2's M_R6 fix pattern (prevents source-mutation leakage; preserves `dataclasses.asdict()` serialization for the jsonl Trace backend). Both fields are REQUIRED per ADR-006 + ADR-016.

**AC-1b.4.7** **And** `_assert_binary_version` helper on `SubprocessAdapter` raises `UnsupportedBinaryVersionError` per FR47 with the EXACT error-message format `"<binary> version <X> outside tested range <range>"` (where `<range>` is the composed string `">={min}, <{max}"` when both bounds are set, or `">={min}"` when `max=None`). The Story 1b.4 errors.py extension lands the leaf class declaration `UnsupportedBinaryVersionError(AgentEvalCompatError)` with `error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"`; per-adapter raise sites land in Epic 4 Story 4.2 (Claude Code CLI) + Epic 11 Story 11.3 (Copilot CLI) per the amended error-class-hierarchy.md L81 ownership row.

**AC-1b.4.8** **And** `src/AgentEval/coding_agent/__init__.py` (Story 1a.1 baseline; verify it exists) re-exports the 4 contributor-facing names: `CodingAgentAdapter` (from `AgentEval.types`), `InProcessAdapter`, `SubprocessAdapter`, `AgentRunResult` (also from `AgentEval.types`). The re-exports are documented in `docs/contracts/stability-surface.md` as `provisional` (Protocol surface) / `provisional` (ABCs) / `provisional` (AgentRunResult dataclass).

**AC-1b.4.9** **And** the `_kernel/discovery.py` Story 1b.3 TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter` continues to resolve correctly (mypy clean) after Story 1b.4 lands the actual Protocol declaration. The pre-edit `type: ignore[attr-defined]` comment on Story 1b.3 discovery.py L102 is REMOVED in Story 1b.4 since the symbol is now resolvable.

**AC-1b.4.10** **And** unit tests in `tests/unit/coding_agent/test_base.py` (`~25+` tests; new directory under `tests/unit/`) cover:
- `CodingAgentAdapter` Protocol structural typing — a stub class with the right method signatures conforms; a missing-method stub does NOT (verified via mypy on a tiny fixture).
- `runtime_checkable` Protocol passes `isinstance(stub, CodingAgentAdapter)`.
- `InProcessAdapter` direct instantiation works (no `@abstractmethod` raises); subclass override of `run()` returns a valid `AgentRunResult`.
- `SubprocessAdapter` direct instantiation FAILS (3 abstract methods `_spawn`/`_parse_event`/`_finalize` un-implemented); subclass implementing all 3 + inheriting the template-method `run()` succeeds.
- `_assert_binary_version` raises `UnsupportedBinaryVersionError` with the FR47-exact format for: version below `min` / version above `max` (when set) / unsupported-format string. Does NOT raise for in-range version.
- `AgentRunResult` constructs with all 7 fields + defensive-copy on `metadata` sub-dataclass (`__post_init__` mirroring Story 1b.2's pattern).
- `AgentRunMetadata` enforces 3-state Literal values at type level (mypy-asserted in `tests/unit/conventions/` if convention-test infra is ready, or doctest-style).
- `CodingAgentAdapter` Protocol re-export path: `from AgentEval.coding_agent import CodingAgentAdapter` resolves to the SAME class as `from AgentEval.types import CodingAgentAdapter` (identity check).
- `_kernel/discovery.py` integration: `discover_adapters()` returns a `dict[str, type[CodingAgentAdapter]]` whose type checker satisfies the resolved Protocol (mypy verifies; runtime smoke does `next(iter(...))` and confirms an `isinstance` check passes).

**AC-1b.4.11** **And** all-gates pass:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (32 source files: previous 30 + new `coding_agent/base.py` + extended `types.py` + extended `errors.py` = still 30 source files since errors.py + types.py + coding_agent/__init__.py existed; net new = base.py + 1 new test dir + extended types.py / errors.py — Story 1b.3 had 30; Story 1b.4 has 31 source files including the new `coding_agent/base.py`).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all 220 kernel/errors/types unit tests + new ~25 Story 1b.4 tests pass (total ~245+).
- `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6 FR42 regression unchanged.
- `uv run robot tests/acceptance/smoke` — RF smoke regression unchanged.

**AC-1b.4.12** **And** project norms applied per AC-1b.4.11: cross-LLM adversarial code review via `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (8th consecutive use); cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (9th consecutive STAR-catch pattern at Story 1b.3 review demonstrated this catches real drift); Phase-1 limitations explicitly documented (sandbox routing through scenarios/ NOT adapter; FR17b `coding_agent=` kwarg deferred to Story 4.1; `_finalize` event-folding pattern Phase-1 returns minimal `AgentRunResult` — concrete adapters in Epic 4/11 enrich the result with provider-specific metadata).

---

#### Story 1b.5: Conformance Harness + Loader + Fixture Schema + 6 Reference Fixtures

As a **conformance-suite-respecting epic author** (Epics 2-8b — every Tier-2/3 keyword needs a fixture per AC-CONFORMANCE-01),
I want the conformance suite scaffolding at `tests/conformance/{harness.py, loader.py, fixture-schema.json}` complete + 6 reference fixtures shipped covering the most architecturally significant scenarios,
So that subsequent epics can drop in new fixture files and the harness loads/runs them without modification, and AC-CONFORMANCE-01 (fidelity oracles) is enforceable from Phase 1 Week 2 onward.

**Acceptance Criteria:**

**Source-of-truth ratification (2026-05-19):** Story 1b.5 pre-create-story drift check (9th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 20 drifts (12 HIGH + 6 MED + 2 LOW) in the pre-edit Story 1b.5 epics.md spec vs ratified sources — the spec had invented a parallel design across fixture organization, fixture schema, oracle taxonomy, error classes, type names, function signatures, SKIP semantics, and PR-trigger semantics. All 20 resolved via path-of-least-amendment by honoring ratified sources per Many's 2026-05-19 ratification + "fix-the-losing-source-NOW" pattern. Key resolutions: (D1 HIGH) per-adapter `fixtures/<adapter>/<scenario>.json` layout per architecture L738 + ADR-005 L18 + ADR-017 L38 + L272 summary (NOT per-keyword flat layout); (D2 HIGH) Decision-4 ratified schema field set `adapter_name`/`scenario_name`/`agent_run_result`/`expected_tool_calls`/`expected_errors`/`reproducibility_footer`/`_schema_version` (NOT invented `id`/`tier`/`keyword_under_test`/etc.); (D3 HIGH) per-AC test files per ADR-017 L21-33 (10 files: `test_ac_simplicity_01_evidence_block.py` ... `test_ac_mcp_observe_03_per_test_scope.py` + `test_structural_shape.py`); (D4 HIGH) drop invented `oracle_type` 4-state enum → use ADR-005 L19-22 per-field allowable-variations (`latency_ms > 0`, ISO-8601 monotonic timestamps, strict `metadata.completeness` match); (D5 MED) drop `trajectory_match` — Phase-2-deferred per architecture L239 + L1809 + PRD L1310; (D6 MED) drop `completeness_check` oracle — collapses ADR-006 truncation-injection mechanism + ADR-005 `metadata.completeness` exact match into a single label, losing the `expected_errors` consumption contract; (D7 HIGH) `InvalidConformanceFixtureError` NOT in ratified 11-leaf catalog → use stdlib `jsonschema.ValidationError` (conformance harness is test infra at `tests/conformance/`, not library-public surface at `src/AgentEval/`); (D8 HIGH) drop fixture (b) `InvalidSkillFrontmatterError` — Epic 2's error class to introduce, not Story 1b.5's; (D9 HIGH) `load_fixture(path) -> ConformanceFixture` (singular per architecture L737), NOT `load_fixtures -> list[Fixture]`; (D10 HIGH) introduce `tests/conformance/types.py` with stdlib `@dataclass(frozen=True) ConformanceFixture` + `ConformanceResult` per Story 1b.2 Pydantic-substitution precedent (D19); (D11 HIGH) drop SKIP-with-reason gate invention — use `pytest.skip("Owning epic N not yet shipped")` markers at per-AC test file level per ratified ADR-017 pattern; (D12 HIGH) `conformance.yml` stays per-release per ADR-005 L31 + ADR-017 L57 (`workflow_dispatch` + `release: published`), NOT per-PR (the "all 7 workflows green on trivial PR" property holds via `workflow_dispatch` reachability + `--collect-only` placeholder replaced with real `pytest tests/conformance -q`); (D13 LOW) confirmed Story-1b.4-to-1b.5 hand-off: signature-shape verification owned by Story 1b.5's `test_structural_shape.py` per ADR-017 L36 + types.py L346-356; (D14 HIGH) drop fixture (c) `InvalidMCPToolSchemaError` impl — Epic 3 Story 3.x owns the error class; (D15 MED) reframe AC-CONFORMANCE-01 as "contract publication from Phase 1 Week 2 onward" not "enforceable" per PRD L520-533 verbatim "**not for consistency enforcement** (P1 has only 2 adapters)"; (D16 LOW) drop Tier-3 tag from completeness fixture — tier is a keyword property NOT an adapter/fixture property; (D17 LOW) cite post-renumbering ADR-005 + ADR-006 + ADR-017 not stale PRD ADR-008/ADR-009 references; (D18 MED) add `adapter_registry` fixture + truncation-injection mock-agent harness + mock provider per ADR-017 L40-43; (D19 MED) ratify stdlib `@dataclass(frozen=True) ConformanceFixture` Phase-1 deviation from Decision-4's Pydantic per Story 1b.2 types.py L46-56 precedent; (D20 MED) adopt ratified 6-fixture set per architecture L739 (`generic/echo_simple.json`, `generic/echo_truncated.json`, `generic/echo_external_mcp.json`, `claude_code_cli/echo_simple.json`, `claude_code_cli/echo_truncated.json`, `claude_code_cli/echo_external_mcp.json`) — covers AC-CONFORMANCE-01 + AC-CONFORMANCE-02 + AC-MCP-OBSERVE-01 + FR36a + FR37 surface achievable at end-of-Story-1b.4. Phase-1 note: no concrete adapter exists at end of Story 1b.5 (Generic + Claude Code CLI adapters land in Epic 4 Stories 4.1 + 4.2); fixtures publish the contract, harness loads + schema-validates them, all 10 per-AC test files SKIP with `pytest.skip("Owning epic N not yet shipped")` until the corresponding epic's adapter + keyword infrastructure ships.

**Given** the JSON+jsonschema format choice from architecture Step-4 Decision-4 + ADR-005 L17-22 fidelity-oracle contract,
**When** I author `tests/conformance/fixture-schema.json`,
**Then** the schema validates the Decision-4 ratified field set: `_schema_version: str` (semver), `adapter_name: str` (required), `scenario_name: str` (required), `agent_run_result: object` (schema for `AgentRunResult` with required `metadata.completeness` + `metadata.mcp_coverage` per FR36a/b), `expected_tool_calls: array` (per ADR-005 L19-22 + AC-CONFORMANCE-01 — sequence of expected `ToolCallTrace` records with allowable-variation annotations: `latency_ms` `> 0` constraint, ISO-8601 timestamp + monotonic ordering, `source` strict match), `expected_errors: array` (per ADR-006 + AC-CONFORMANCE-02 — for truncation-injection scenarios), `reproducibility_footer: object` (per FR39 — captures `library_version`, `redaction_policy_hash`, `started_at`/`ended_at`).

**And** `tests/conformance/types.py` exposes `ConformanceFixture` + `ConformanceResult` as stdlib `@dataclass(frozen=True)` per Story 1b.2 types.py L46-56 Phase-1 Pydantic-substitution precedent (architecture Decision-4's "Pydantic dataclasses" wording is a Phase-1.5 carry-over per `deferred-work.md`; stdlib dataclasses ship Phase-1). `ConformanceFixture` mirrors the schema field set with typed attributes; `ConformanceResult` exposes `passed: bool`, `fixture: ConformanceFixture`, `evidence: dict[str, Any]` (per-allowable-variation witness or diff record), `skip_reason: str | None`.

**And** `tests/conformance/loader.py` exposes `load_fixture(path: Path) -> ConformanceFixture` (singular per architecture L737) — reads the JSON file, validates against `fixture-schema.json` via stdlib `jsonschema` (already a direct dep), raises `jsonschema.ValidationError` on schema violation. NO new error class added to `src/AgentEval/errors.py` — conformance harness is test infra, not library-public surface; consumers of the harness catch `jsonschema.ValidationError` directly.

**And** `tests/conformance/harness.py` exposes:
- `adapter_registry` pytest fixture (per ADR-017 L40-43) — yields all adapters discovered via Story 1b.3's `_kernel.discovery.discover_adapters()` + entry-points. Empty at end-of-Story-1b.5 (no adapters registered yet); per-AC test files parametrize over it + SKIP when empty.
- `truncation_injection_harness` fixture — exposes a mock-agent subprocess controller (kill mid-stream / EOF early / explicit-`mcp_coverage="external_mixed"` injection) per ADR-006 + AC-CONFORMANCE-02. Used by `test_ac_conformance_02_completeness.py`.
- `mock_provider` fixture — known cost/runtime characteristics per ADR-015 (for Tier-3 cost-guardrail conformance tests when Epic 6 lands).
- `run_fixture(fixture: ConformanceFixture, adapter: CodingAgentAdapter) -> ConformanceResult` — orchestrates `adapter.run()` against the fixture's `scenario_name` + asserts allowable-variation contract per ADR-005 L19-22; returns structured pass/fail with evidence (allowable-variation witness OR diff record OR `expected_errors`-match record OR truncation-injection-success record).
- `assert_adapter_signature(adapter_cls: type[CodingAgentAdapter]) -> None` — signature-shape verifier per Story 1b.4 hand-off + ADR-017 L36; inspects `adapter.run`'s signature against FR12's `(self, prompt: str, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` contract; raises `AssertionError` with structured diff on mismatch.

**And** 10 per-AC test files land at `tests/conformance/test_ac_*.py` per ADR-017 L21-33: `test_ac_simplicity_01_evidence_block.py`, `test_ac_simplicity_02_keyword_idiom.py`, `test_ac_discover_01_cohort.py`, `test_ac_discover_02_cost_guardrail.py`, `test_ac_dogfood_01_replacement.py`, `test_ac_conformance_01_fidelity_oracles.py`, `test_ac_conformance_02_completeness.py`, `test_ac_mcp_observe_01_coverage.py`, `test_ac_mcp_observe_02_version_gate.py`, `test_ac_mcp_observe_03_per_test_scope.py` — each scaffolded as a skeleton parametrized over `adapter_registry` with `pytest.skip("Owning epic N not yet shipped — Story X.Y will populate")` markers per ADR-017 pattern. Plus `test_structural_shape.py` parametrized over `adapter_registry` calling `assert_adapter_signature` against each registered adapter (also empty/skipping at end-of-Story-1b.5).

**And** 6 reference fixtures land at `tests/conformance/fixtures/<adapter>/<scenario>.json` per architecture L738-739: `generic/echo_simple.json` + `generic/echo_truncated.json` + `generic/echo_external_mcp.json` + `claude_code_cli/echo_simple.json` + `claude_code_cli/echo_truncated.json` + `claude_code_cli/echo_external_mcp.json`. The 3 scenarios map to ratified AC coverage:
- `echo_simple` → AC-CONFORMANCE-01 (fidelity oracles) + AC-MCP-OBSERVE-01 (`hosted_in_process` coverage) + AC-MCP-OBSERVE-02 (spec-version gate). Agent prompts a simple echo, no truncation, hosted MCP coverage.
- `echo_truncated` → AC-CONFORMANCE-02 (completeness) + FR36a (`metadata.completeness="truncated"`). Truncation-injection mid-stream; adapter MUST emit `truncated`.
- `echo_external_mcp` → AC-MCP-OBSERVE-01 (`external_mixed` coverage) + FR37 (`IncompleteTraceError` when `allow_external_mcp_blind=False`). External-MCP coverage; harness asserts the typed error on metric-keyword invocation.

Both adapters (`generic`, `claude_code_cli`) are forward-references at end-of-Story-1b.4; the fixtures publish the contract Tier-1 community adapter authors implement against. Story 4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI) populate the actual adapter implementations; conformance tests start asserting the fixtures against real adapters at that time.

**And** the `conformance.yml` CI workflow's pre-Story-1b.5 `--collect-only` placeholder is replaced with a real `pytest tests/conformance -q` invocation per ADR-005 L31 + ADR-017 L57: workflow stays per-release (`on: workflow_dispatch + release: published`); NOT per-PR. The all-7-workflows-green-on-trivial-PR property from Story 1a.2 holds via `workflow_dispatch` reachability + skeleton test files SKIPping until owning epics ship. AC-CONFORMANCE-01 framing per PRD L520-533: "Conformance suite ships in Phase 1 as **CONTRACT PUBLICATION** (so community adapter authors have a runnable target Day 1), NOT for consistency enforcement (P1 has only 2 adapters)."

**And** all-gates pass:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (31 source files — no new src/ files added; conformance harness lives at `tests/conformance/`).
- `uv run python scripts/check-license-headers.py` PASS (still 31/31; tests exempt per convention).
- `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — 263 prior tests still pass (regression).
- `uv run pytest tests/conformance -q` — harness collects + loads all 6 fixtures + 10 per-AC test files SKIP gracefully (NOT fail). `pytest` returncode 0 (skips OK).
- `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6 FR42 regression unchanged.
- `uv run robot tests/acceptance/smoke` — RF smoke regression unchanged.

---

#### Story 1b.6: Determinism Contract Doc + 5 CI-Enforcement Conventions Tests

As a **library consumer or contributor**,
I want `docs/contracts/determinism-contract.md` fully populated (no longer a skeleton) and 5 CI-enforcement conventions tests at `tests/unit/conventions/*.py` passing on the current skeleton,
So that the FR63 determinism contract is auditable from Day 1 and architecture-level conventions (tier annotation presence, error class inheritance, no-bare-async, keyword-name idiom, docstring-libdoc-badge alignment) cannot regress silently.

**Acceptance Criteria:**

**Given** the kernel guarantees from Stories 1b.1-1b.3,
**When** I author `docs/contracts/determinism-contract.md` per FR63,
**Then** the document covers: (a) Tier-1 keyword bit-identical determinism guarantee (FR31a — same input always produces same output, no randomness, no time-dependence), (b) Tier-2/3 statistical interpretability requirement (FR31b — non-deterministic results must be characterizable via Pass@k / Run N Times), (c) the polling ban on Tier-2/3 (no `validate` polling per FR28), (d) reproducibility checklist for bug reports.

**And** `tests/unit/conventions/test_tier_annotation_present.py` walks `src/AgentEval/**/library.py` modules + asserts every `@keyword`-decorated function has a `@tier(N)` annotation (no missing tier annotations on public keywords).

**And** `tests/unit/conventions/test_error_class_hierarchy.py` walks `src/AgentEval/errors.py` + asserts every exported error class inherits from `AgentEvalError` (no orphan error classes).

**And** `tests/unit/conventions/test_no_bare_async_keywords.py` asserts no `@keyword`-decorated function is `async def` (per ADR-A1 — async ops always go through `_run_async`).

**And** `tests/unit/conventions/test_keyword_name_idiom.py` asserts every `@keyword`-decorated function name uses snake_case (RF converts to Title Case at registration) and starts with a verb (per `docs/contracts/coding-conventions.md`).

**And** `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` asserts every `@keyword`-decorated function's docstring contains its tier badge text (e.g., a `@tier(1)` keyword's docstring contains `[Tier 1 — Deterministic]`).

**And** all 5 conventions tests pass on the current skeleton (no public keywords exist yet — tests pass trivially; they will catch violations as Epics 2+ add real keywords).

---

### Epic 2: Static Agent-Surface Inspection (Tier-1 Keywords)

#### Story 2.1: Skill Static Inspection Keywords

As **Devon (Agent Surface Author — skill author mode)** or **Priya (QA Engineer)**,
I want `Skill.Get Frontmatter`, `Skill.Get Description`, `Skill.Get Allowed Tools`, `Skill.Get Disable Model Invocation` keywords plus `Should Be Valid Frontmatter` validation keyword (Phase-1: plain `@keyword` per ADR-022 catalog row deferring AssertionEngine adoption to Phase-2; PRD FR2 ratifies the eventual matcher name. Story 2.1 code-review C5 fix 2026-05-19 amended this line.),
So that I can assert on skill `.md` file structure in a `.robot` test in milliseconds without API keys or network — first deterministic skill-validation surface.

**Acceptance Criteria:**

**Given** a valid skill `.md` file at `tests/fixtures/skills/example-valid.md` with YAML frontmatter containing `name`, `description`, `allowed-tools`, `disable-model-invocation`,
**When** I call `${frontmatter}=    Skill.Get Frontmatter    tests/fixtures/skills/example-valid.md` in a `.robot` test,
**Then** the variable receives a dict with the parsed YAML structure and the call completes in <50ms (per NFR-PERF-02 Tier-1 latency target L1608; NFR-PERF-01 is the separate 5-minute time-to-first-test bar — pre-edit citation was drift caught by Story 2.1 pre-create-story check D2).

**And Given** the same valid file,
**When** I call `${desc}=    Skill.Get Description    tests/fixtures/skills/example-valid.md`,
**Then** the variable receives the `description` field value as a string; analogous behavior for `Skill.Get Allowed Tools` (returns list) + `Skill.Get Disable Model Invocation` (returns bool).

**And Given** an invalid skill file at `tests/fixtures/skills/example-malformed-yaml.md` with broken YAML frontmatter,
**When** I call `Skill.Get Frontmatter    tests/fixtures/skills/example-malformed-yaml.md`,
**Then** `InvalidSkillFrontmatterError` is raised with message containing: (a) the file path, (b) the line number where YAML parsing failed, (c) the field name at fault (if identifiable), (d) a fix suggestion — per the FR59 format documented in Story 1a.4.

**And Given** a skill file missing required frontmatter fields,
**When** I call `Should Be Valid Frontmatter    ${frontmatter_dict}` as a plain `@keyword` (Phase-1; full AssertionEngine matcher wiring lands Phase-2 per ADR-022),
**Then** the assertion fails with a structured error listing each missing required field; passing the same operator a complete frontmatter dict succeeds without error.

**And** the keyword library exports the 4 keywords via `DynamicCore` lazy-loading per architecture L299/L354/L573 + agentguard ADR-003 inheritance catalog row (the pre-edit "ADR-006" citation was drift caught by Story 2.1 pre-create-story check D1 — ADR-006 is `agent-run-result-completeness-field.md`, NOT the DynamicCore composition source). Sub-library name "Skill" — short, clear, discoverable; e.g. `Skill.Get Description`. libdoc generation produces the `[Tier 1 — Deterministic]` badge on each keyword's docstring per Story 1b.6's conventions test.

**And** the `tests/unit/conventions/*` tests from Story 1b.6 all pass after this story lands (tier annotation present, error class hierarchy clean, docstring badge alignment correct, snake_case + verb-prefix keyword names).

---

#### Story 2.2: Subagent + Hook Static Inspection Keywords

As **Devon (Agent Surface Author)** or **Priya (QA Engineer)**,
I want `Subagent.Get Frontmatter` for sub-agent definition files and `Hook.Get Config` for hook configuration files,
So that I can assert on sub-agent + hook configurations using the same Tier-1 deterministic surface established by Story 2.1.

**Acceptance Criteria:**

**Given** a valid sub-agent file at `tests/fixtures/subagents/example-valid.md` with YAML frontmatter per the Claude Code sub-agent format,
**When** I call `${def}=    Subagent.Get Frontmatter    tests/fixtures/subagents/example-valid.md` in a `.robot` test,
**Then** the variable receives a dict with the parsed sub-agent definition (name, description, tools, model overrides if present) in <50ms.

**And Given** an invalid sub-agent file,
**When** I call `Subagent.Get Frontmatter` against it,
**Then** `InvalidSubagentDefinitionError` is raised with the FR59 error format (path + line + field + fix suggestion).

**And Given** a valid `settings.json` file at `tests/fixtures/hooks/settings-valid.json` containing `hooks.PreToolUse`, `hooks.PostToolUse`, `hooks.Stop` event arrays per the Claude Code hook format,
**When** I call `${config}=    Hook.Get Config    tests/fixtures/hooks/settings-valid.json` in a `.robot` test,
**Then** the variable receives a dict mapping `hooks.<event>` → list of hook entries; each entry contains `command`, `args`, `timeout`, `matcher` fields per FR4; inline-skill-frontmatter hooks are parsed and surfaced as a nested `inline_skill` field on the entry.

**And Given** an invalid `settings.json` (malformed JSON or missing required hook fields),
**When** I call `Hook.Get Config` against it,
**Then** `InvalidHookConfigError` is raised with the FR59 error format and a JSON Pointer to the offending location.

**And** all 4 keywords (`Subagent.Get Frontmatter`, `Hook.Get Config`, plus the 2 new error classes) ship with conventions-test compliance and tier-1 latency confirmed in unit tests (per-keyword **median** <50 ms over 11 samples per NFR-PERF-02 PRD L1608; the pre-edit "P95 <50ms over 100 invocations" wording was drift caught by Story 2.2 pre-create-story check D-A 2026-05-19 — NFR-PERF-02 specifies median, not P95).

---

#### Story 2.3: MCP Static Inspection Keywords

As **Mei (Agent Surface Author — MCP author mode)** or **Priya (QA Engineer)**,
I want `MCP.Get Server Config` to inspect declared MCP servers without starting them, plus `MCP.Get Tool Schema` + `MCP.Validate Tool Schema` for tool-schema inspection,
So that I can assert on `.mcp.json` declarations and MCP tool schemas in a `.robot` test in Tier-1 deterministic time — first MCP-author value milestone (full runtime lifecycle is Epic 3).

**Acceptance Criteria:**

**Given** a valid `.mcp.json` file at `tests/fixtures/mcp/mcp-valid.json` declaring multiple MCP servers with stdio + streamable_http transports,
**When** I call `${servers}=    MCP.Get Server Config    tests/fixtures/mcp/mcp-valid.json` in a `.robot` test,
**Then** the variable receives a dict of declared MCP servers (each entry has `name`, `command`, `args`, `env`, `transport`) **without starting any server processes** — verified by an OS-level process inventory diff (no new MCP server PIDs after the call).

**And Given** an invalid `.mcp.json` (missing required fields, malformed JSON, unsupported transport),
**When** I call `MCP.Get Server Config` against it,
**Then** `InvalidMCPServerConfigError` is raised with the FR59 error format and a JSON Pointer to the offending field.

**And Given** a JSON Schema describing an MCP tool's input at `tests/fixtures/mcp/tool-schema-valid.json` (e.g., a tool named `search` with parameter `query: string`),
**When** I call `${schema}=    MCP.Get Tool Schema    tool_name=search    config_path=tests/fixtures/mcp/mcp-valid.json` in a `.robot` test,
**Then** the variable receives the JSON Schema dict for the tool's input parameters.

**And Given** a malformed tool schema (e.g., invalid JSON Schema dialect, missing `type`, circular `$ref`),
**When** I call `MCP.Validate Tool Schema    tool_name=broken_tool    config_path=tests/fixtures/mcp/mcp-with-broken-tool.json`,
**Then** `InvalidMCPToolSchemaError` is raised with: (a) the JSON Pointer to the offending location, (b) the jsonschema validation error message, (c) the FR59 format applied.

**And** all 3 keywords ship with `[Tier 1 — Deterministic]` libdoc badges, snake_case + verb-prefix names, and per-keyword **median** <50 ms latency on the fixture set per NFR-PERF-02 PRD L1608 (pre-edit "P95 <50ms" wording was drift caught by Story 2.3 pre-create-story check D-A 2026-05-19 — NFR-PERF-02 specifies median, not P95; same drift as Story 2.2 D-A).

---

#### Story 2.4: Epic 2 Conformance Fixtures + Integration Tests Against Real Sample Files

As a **library maintainer**,
I want full conformance fixture coverage for all 11 Tier-1 keywords introduced in Stories 2.1-2.3 (extending Story 1b.5's reference set), plus integration tests against real-world sample files (skills from Claude Code documentation, MCP server configs from `rf-mcp`, hook configs representative of common patterns),
So that AC-CONFORMANCE-01 is satisfied for Epic 2 and regressions are caught by CI before merge.

**Acceptance Criteria:**

**Given** the 10 Tier-1 keywords from Stories 2.1-2.3 (`Skill.Get Frontmatter`, `Skill.Get Description`, `Skill.Get Allowed Tools`, `Skill.Get Disable Model Invocation`, `Should Be Valid Frontmatter`, `Subagent.Get Frontmatter`, `Hook.Get Config`, `MCP.Get Server Config`, `MCP.Get Tool Schema`, `MCP.Validate Tool Schema`) — pre-edit "11 Tier-1 keywords" was Story 2.4 pre-create-story drift check D-A 2026-05-19; the enumerated bullet list has 10 items,
**When** I author conformance fixtures at `tests/conformance/fixtures/`,
**Then** each keyword has at minimum one "happy path" fixture + one "error path" fixture, totaling 22+ fixtures for Epic 2 alone, all loading cleanly through the Story 1b.5 harness.

**And Given** real-world sample files curated from Claude Code documentation + `rf-mcp` repo + canonical hook patterns,
**When** I run integration tests at `tests/integration/static_inspection/test_real_world_samples.py`,
**Then** each Epic 2 keyword is exercised against ≥3 real-world files (not just synthetic fixtures), and all assertions pass — proving the keywords survive non-curated inputs.

**And** the `conformance.yml` CI workflow from Story 1a.2 now runs the full Epic 2 fixture set on every PR + reports per-fixture pass/fail in the PR check summary; no skipped fixtures for Epic 2 keywords after this story lands.

**And** Epic 2's keyword surface achieves the AC-SIMPLICITY-02 "keyword idiom" bar — confirmed by Story 1b.6's conventions tests all passing on the now-populated keyword set (no missing tier annotations, no orphan error classes, all docstrings carry correct badges).

**And** the dogfood prep for Epic 3 is unblocked: Mei's MCP author flow can now run static inspection (`MCP.Get Server Config` against rf-mcp's `.mcp.json`) before Epic 3 introduces lifecycle keywords.

---

### Epic 3: MCP Server Lifecycle + Runtime Inspection

**Scope adjustment (in-line note):** MVP Tool Discoverability (FR10a) moved from Epic 3 to Epic 4 because Discoverability requires the adapter to drive trials, and the adapter lands in Epic 4. FR Coverage Map line for FR10a and the Epic 3 entry in the Epic List both update in Step-4 final-validation cleanup.

#### Story 3.1: MCP Server Lifecycle Keywords — Start + Connect + Stop + Spec Version Gate

As **Mei (Agent Surface Author — MCP author mode)** or **Priya (QA Engineer)**,
I want `MCP.Start Server`, `MCP.Connect To Server` (per PRD FR8 verbatim — pre-edit "MCP.Connect" was Story 3.1 pre-create-story drift D-A 2026-05-19), `MCP.Stop Server` keywords supporting all 3 transports (stdio, streamable_http, in-memory), with MCP spec version validated at connect time and per-test scope cleanup honored under `pabot`,
So that I can lifecycle MCP servers in a `.robot` test using the cleanup strategy chosen by the consumer (suite/test/process per `mcp_per_test` setting from Story 1a.6), and unsupported MCP spec versions fail loudly with `UnsupportedMCPVersionError` per AC-MCP-OBSERVE-02 instead of silently degrading.

**Acceptance Criteria:**

**Given** the per-test-cleanup spike output from Story 0.2 (Epic 0) and the `_kernel/context.py` from Story 1b.1,
**When** I implement `src/AgentEval/mcp/library.py` keywords `MCP.Start Server`, `MCP.Connect To Server`, `MCP.Stop Server` (Story 1c-1 review fix 2026-05-19 — Auditor MED #2: D-A drift fix amended L1232 only; L1238/L1246/L1250 now also amended to `Connect To Server` per PRD FR8 verbatim) plus `src/AgentEval/mcp/transport.py` for the 3 transports plus `src/AgentEval/mcp/version_gate.py` for spec version negotiation,
**Then** in a `.robot` test calling `MCP.Start Server    name=echo    transport=stdio    command=python    args=-m AgentEval.mcp.bundled.echo` followed by `MCP.Connect To Server    name=echo` followed by tool inspection followed by `MCP.Stop Server    name=echo`, the server starts, connects with version negotiated successfully, supports tool calls, and stops cleanly with no orphan process (verified by OS-level PID inventory diff).

**And Given** the same lifecycle calls under `pabot --processes 8` with `mcp_per_test=True` mode (default per ADR-009 — pre-edit `mcp_per_test="test"` was Story 3.1 pre-create-story drift D-D 2026-05-19; the 3 valid modes per Story 1a.6 baseline + ADR-009 are `True / False / "suite"`),
**When** the test suite completes,
**Then** no MCP server processes leak (per Story 0.2 spike findings); cleanup overhead matches the Story 0.2 measurement table within ±10%.

**And Given** an MCP server advertising an unsupported MCP spec version (e.g., a forward-incompatible draft version not in the agenteval-pinned compat range from `version_gate.py`),
**When** `MCP.Connect To Server` runs against it,
**Then** `UnsupportedMCPVersionError` is raised per FR46 with: (a) the server's advertised version, (b) the agenteval-supported version range, (c) a fix suggestion ("upgrade `mcp` dep, downgrade server, or use a compatible server build").

**And Given** all 3 transports (stdio, streamable_http, in-memory),
**When** I exercise each via `MCP.Start Server` + `MCP.Connect To Server` in unit tests at `tests/unit/mcp/test_transport.py`,
**Then** each transport succeeds with its representative bundled echo server (in-memory uses the in-process echo server; stdio uses subprocess echo; streamable_http uses a local httpx-served echo).

**And** the keywords carry `[Tier 1 — Deterministic]` libdoc badges (pre-edit "Tier 2 — LLM-Deterministic" was Story 3.1 pre-create-story drift D-B 2026-05-19; that badge does not exist in `_kernel/tier.py` — the 3 ratified badges are `[Tier 1 — Deterministic]`, `[Tier 2 — Stochastic Single-Shot]`, `[Tier 3 — Stochastic Fan-Out]`. MCP lifecycle keywords are Tier 1 because they're deterministic given same env + server binary; I/O latency variance is captured separately via NFR-PERF metrics, NOT via tier badge); conventions tests from Story 1b.6 all pass on the new keywords.

---

#### Story 3.2: MCP Tool Inspection Keywords — List Tools + Call Tool

As **Mei (Agent Surface Author)** or **Priya (QA Engineer)**,
I want `MCP.List Tools` and `MCP.Call Tool` keywords with full `MCPToolResult` access (text content, structured content, error responses),
So that I can introspect what tools a connected MCP server offers, invoke tools with parameters, and assert on tool results in a `.robot` test — covering the dynamic-evaluation surface that the static Epic 2 keywords cannot reach.

**Acceptance Criteria:**

**Given** a connected MCP server from Story 3.1's `MCP.Connect To Server` (Story 3.2 pre-create-story drift D-A 2026-05-19; pre-edit "MCP.Connect" was Story 3.1 D-A drift that escaped initial fix scope),
**When** I call `${tools}=    MCP.List Tools    name=echo` in a `.robot` test,
**Then** the variable receives a list of `MCPTool` dataclass instances, each with `name`, `description`, `input_schema` (JSON Schema dict), and `output_schema` (optional).

**And Given** the same connected server and an invocation of a tool named `echo_back`,
**When** I call `${result}=    MCP.Call Tool    name=echo    tool=echo_back    arguments={"text": "hello"}` in a `.robot` test,
**Then** the variable receives an `MCPToolResult` dataclass with: `content` (list of text+structured content blocks per MCP spec), `is_error` (bool), `error_message` (str if `is_error` true), `latency_ms` (float), `correlation_id` (str for trace lookup).

**And Given** a tool that returns an error response (e.g., calling `echo_back` with missing required `text` parameter),
**When** I call `MCP.Call Tool` against it,
**Then** the returned `MCPToolResult` has `is_error=True` and `error_message` populated, but **no exception is raised** — error responses are first-class data, distinct from infrastructure failures (which DO raise).

**And Given** an MCP server that disconnects mid-call (e.g., subprocess crashes during tool execution),
**When** `MCP.Call Tool` is in flight,
**Then** `MCPConnectionLostError` is raised with the server name + last successful operation + a fix suggestion, and the per-test cleanup from Story 3.1 still runs (no resource leak).

**And** unit tests in `tests/unit/mcp/test_tool_inspection.py` cover happy path (echo) + error response + connection loss against the bundled echo server in all 3 transports.

---

#### Story 3.3: Interleaved Dogfood — Port `rf-mcp` MCP Surface Tests

As a **dogfood validator** (Raj's downstream consumer perspective),
I want the existing custom Python end-to-end tests in `rf-mcp` covering MCP surface inspection (server config validation, tool schema validation, lifecycle, tool calls) replaced by `.robot` suites using `robotframework-agenteval` Epic 2 + Epic 3 keywords,
So that AC-DOGFOOD-01 progresses with concrete evidence the library survives a real downstream repo's existing test patterns — and integration pain surfaces in week 3-4 instead of week 10 (per Amelia's interleaved-dogfood call).

**Acceptance Criteria:**

**Given** the `rf-mcp` repository at `https://github.com/manykarim/rf-mcp` and its existing custom Python end-to-end tests covering MCP surface inspection (the subset of tests that exercises server config, tool schema, lifecycle, tool calls — NOT trace/metric assertions which come Epic 5 + Epic 6),
**When** I author equivalent `.robot` suites in `rf-mcp`'s test directory using `robotframework-agenteval` Epic 2 + Epic 3 keywords (`MCP.Get Server Config`, `MCP.Get Tool Schema`, `MCP.Validate Tool Schema`, `MCP.Start Server`, `MCP.Connect To Server` (Story 3.2 code-review Auditor HIGH-3 fix 2026-05-19: stale `MCP.Connect` amended per FR8 verbatim; D-A drift had 2 escapees at L1294 + L1467), `MCP.List Tools`, `MCP.Call Tool`, `MCP.Stop Server`),
**Then** the `.robot` suites achieve **parity coverage** with the custom Python tests on the MCP surface subset — verified by side-by-side test-name mapping + assertion-by-assertion equivalence check (a `tests/dogfood/parity-checklist-rf-mcp-mcp-surface.md` document tracks each custom test's `.robot` equivalent).

**And Given** the `dogfood-integration.yml` CI workflow scaffolded in Story 1a.2,
**When** a PR to `robotframework-agenteval` touches Epic 2 or Epic 3 keyword code paths,
**Then** the workflow clones `rf-mcp` head, installs the PR's `agenteval` build, runs the new `.robot` suites in `rf-mcp`, and reports per-suite pass/fail. PR fails if `rf-mcp` MCP surface tests regress.

**And Given** the same `.robot` suites running locally under `pabot --processes 4` (Mei's realistic CI configuration),
**When** the suites complete,
**Then** no orphan MCP server processes leak (per Story 3.1 cleanup), and total suite runtime is within the `rf-mcp` empirical baseline (rf-mcp takes several seconds per MCP server startup — Recipe Gallery #5 from Epic 8b will document this baseline; here the test is that performance doesn't degrade beyond the baseline).

**And** the `.robot` suites adopt the `mcp_per_test="suite"` mode by default per NFR-PERF-03d (rf-mcp is a heavy MCP server — per-test startup is prohibitive); a documented exception suite uses `mcp_per_test="test"` for the small number of tests requiring strict isolation, and it completes within the suite's expected runtime budget.

**And** the dogfood pass surfaces ≥1 actionable improvement to agenteval (could be: missing edge case in `MCP.Call Tool` error handling, a docstring fix, a perf concern, a new fixture needed) — file as a follow-up issue tagged `dogfood-finding` and reference it in the parity checklist. Zero findings = the integration test wasn't real enough; investigate.

---

### Epic 4: Coding-Agent Adapter Suite + Agent Orchestration + MVP Tool Discoverability

**Scope note:** MVP Tool Discoverability (FR10a) relocated to Epic 4 from Epic 3 because Discoverability requires an adapter to drive trials. Also implicitly satisfies FR11 + FR11b for the MVP Discoverability keyword via `@guarded_fanout` decorator inheritance from Story 1b.3 — Epic 7's cost/runtime guardrail scope narrows accordingly.

#### Story 4.1: Provider Layer + Generic Coding-Agent Adapter

As **Raj (Agent Developer)**,
I want the `providers/` layer (`LLMProviderAdapter` Protocol + LiteLLM adapter + Mock adapter + factory) plus the Generic `CodingAgentAdapter` implementation that connects to any of LiteLLM's 140+ providers,
So that I can run agent flows against any commercial LLM (Anthropic, OpenAI, Mistral, Gemini, ...) or local model (Ollama, vLLM) using a single adapter configuration — no per-provider code path required for the most common cases.

**Acceptance Criteria:**

**Given** the `_kernel/discovery.py` + `_kernel/run_async.py` from Story 1b.3/1b.1,
**When** I implement `src/AgentEval/providers/{base, litellm_adapter, mock, factory}.py`,
**Then** `providers/base.py` exposes an `LLMProviderAdapter` Protocol (`@runtime_checkable` per architecture L883/L890) with method `chat(messages: list[Message], tools: list[Tool] | None = None, *, stream: bool = False, model: str | None = None, **kwargs) -> ChatResponse`, plus `name: str` property + `version: str` property. `litellm_adapter.py` implements the Protocol via `litellm.completion()` (sync wrapper around async via `_run_async`). `mock.py` provides deterministic stub responses for unit tests. `factory.py` resolves a provider by name from the entry-points group `"agenteval.providers"` per PRD FR17c L1518 + `_kernel/discovery.py:_GROUP_PROVIDERS` or programmatic registration. (Story 4.1 pre-create-story drift D-A 2026-05-20: pre-edit `complete(prompt, model, **kwargs) -> ProviderResponse` was epics.md drift relative to architecture L890; LiteLLM's `completion(model=..., messages=[...])` shape maps onto `chat(messages, tools)` cleanly; PRD L1087 references the Protocol's `stream` arg so it's added as a keyword-only param defaulting to `False` for Phase-1 non-streaming. D-B 2026-05-20: pre-edit `robotframework_agenteval.providers` entry-points group was epics.md drift relative to PRD FR17c L1518 + Story 1b.3 `discovery.py` L127 ratified `"agenteval.providers"`.)

**And Given** the `InProcessAdapter` base class from Story 1b.4,
**When** I implement `src/AgentEval/coding_agent/generic.py` (`GenericAdapter(InProcessAdapter)`),
**Then** the adapter accepts `provider: str = "litellm"`, `model: str` (e.g., "anthropic/claude-sonnet-4-6", "openai/gpt-4o", "ollama/llama3"), and additional provider-specific kwargs; calling `adapter.run("Hello")` (PRD FR12 single-method Protocol contract) returns an `AgentRunResult` with the Story 1b.4 ratified frozen-dataclass shape: `response_text` populated, `tool_calls=[]` (run with no tools available has no tool surface), `usage: Usage` extracted from the provider response, `metadata: AgentRunMetadata` with `completeness="full"` + `mcp_coverage="none"`, `cost_usd` computed via `litellm.completion_cost()`, `latency_seconds` measured, `trace_id` as the per-run uuid4 hex. (Story 4.1 pre-create-story drift D-C 2026-05-20: pre-edit `adapter.send_prompt("Hello")` was epics.md drift relative to FR12 single `run()` method ratified Story 1b.4 D1 — see `src/AgentEval/types.py:314` `CodingAgentAdapter` Protocol. D-D 2026-05-20: pre-edit flat `token_usage`/`completeness`/`mcp_coverage` was epics.md drift relative to Story 1b.4's ratified shape — `usage` not `token_usage`; `completeness`/`mcp_coverage` nest in `metadata`; `trace_id` is a top-level field.)

**And Given** the Generic adapter and a model that returns tool calls (e.g., Anthropic Claude with tool use enabled),
**When** I call `adapter.run("Use the search tool to find X")` with the adapter pre-connected to an MCP server providing a `search` tool,
**Then** the returned `AgentRunResult` has `tool_calls` populated with each tool invocation captured from the provider's response, `metadata.mcp_coverage="hosted_in_process"` (per Story 1b.2's `compute_mcp_coverage`), and the OTel spans for the tool execution are captured in the trace store from Story 1b.2.

**And** the Generic adapter is registered via the `"agenteval.coding_agents"` entry-points group (PRD FR17a + Story 1b.3 `discovery.py:_GROUP_CODING_AGENTS`) as `"generic"`; `discover_adapters()` from Story 1b.3 returns `{"generic": GenericAdapter, ...}` after Story 4.1 lands. (Story 4.1 pre-create-story drift D-B sibling 2026-05-20: pre-edit `robotframework_agenteval.adapters` was the LEGACY backward-compat group per Story 1b.3 ADR-013 L18; primary group is `agenteval.coding_agents`.)

**And** unit tests in `tests/unit/providers/test_litellm_adapter.py` + `tests/unit/coding_agent/test_generic.py` cover: provider Protocol conformance via mypy, Mock-adapter round-trip in unit tests (no network), LiteLLM adapter with the `mock` provider model (`litellm.completion(model="mock", ...)`) for integration tests not requiring live API keys, tool-call extraction from a recorded provider response fixture.

---

#### Story 4.2: Claude Code CLI Adapter

As **Devon (Agent Surface Author — skill author mode)** or **Raj (Agent Developer)**,
I want the Claude Code CLI adapter (`SubprocessAdapter` subclass) that invokes the `claude` binary with `--output-format=stream-json` and post-hoc conversation history parsing to produce normalized `AgentRunResult` data,
So that Devon's downstream skill-author flow (Epic 7) and Raj's testing of Claude Code skill workflows can use the same `CodingAgentAdapter` Protocol with the real Claude Code runtime — proving the abstraction works for both in-process SDKs and external CLI binaries.

**Acceptance Criteria:**

**Given** the `SubprocessAdapter` ABC from Story 1b.4 and a Claude Code installation (`claude` binary on `$PATH`, version within the agenteval-pinned compat range `>=2.0.0,<3.0.0` — covers the current Claude Code 2.x line; Story 4.2 pre-create-story drift D-E 2026-05-20: pre-edit example `>=1.5.0,<2.0.0` was a placeholder predating the Claude Code 2.x rollout + would REJECT every currently-installed binary; range chosen by inspecting the local `claude --version` output at story-authoring time per Phase-1 pragmatic stance),
**When** I implement `src/AgentEval/coding_agent/claude_code_cli.py` (`ClaudeCodeCLIAdapter(SubprocessAdapter)`),
**Then** the adapter implements the Story 1b.4 ratified abstract hooks `_spawn`, `_parse_event`, `_finalize` (NOT the pre-edit `_subprocess_command` / `_parse_stream_output` per Story 4.2 pre-create-story drift D-A 2026-05-20 — hook names amended to match `src/AgentEval/coding_agent/base.py:272-285` ratified SubprocessAdapter contract). `_spawn` returns a `subprocess.Popen` invoking `["claude", "--output-format=stream-json", "--verbose", "--print"]` with the prompt fed via stdin + `start_new_session=True` per Story 1b.4 process-group hygiene. `_parse_event` deserializes one JSONL line into a `ClaudeCodeEvent` intermediate type per architecture L1228's per-adapter pattern. `_finalize` folds the event stream into an `AgentRunResult` with the Story 1b.4 ratified frozen-dataclass shape: `response_text` from final assistant turn; `tool_calls` from `tool_use` content blocks (mapped to `ToolCallTrace`); `usage: Usage` from final-event token counts (Story 4.2 pre-create-story drift D-B 2026-05-20: epics.md `token_usage` was stale; Story 1b.4 ratified field name is `usage`); `cost_usd` from the `total_cost_usd` field on terminal `result` events (Story 4.2 pre-create-story drift D-F 2026-05-20: pre-edit `costUSD` was epics.md drift relative to the actual `claude --output-format=stream-json` schema verified by behavioral probe at story-authoring time — terminal event uses snake_case `total_cost_usd`); `latency_seconds` from start/end timestamps; `metadata.completeness` from stream-json terminal event (`"complete"` on clean exit; `"truncated"` on non-zero exit or missing-terminal); `metadata.mcp_coverage="external_mixed"` by default per `docs/contracts/mcp-coverage-detection.md` ratified Claude Code observation contract — Epic 5's hosted-MCP observer changes this when applicable; `trace_id` per-run `uuid4().hex`.

**And Given** a `claude` binary version outside the pinned compat range (e.g., version `1.9.0` below the 2.0.0 floor — Story 4.2 pre-create-story drift D-E 2026-05-20: example version updated to match the chosen `>=2.0.0,<3.0.0` Phase-1 range; pre-edit `0.9.0` was below the stale `>=1.5.0,<2.0.0` placeholder),
**When** the adapter is instantiated and `_assert_binary_version("claude", min="2.0.0", max="3.0.0")` runs (the Story 1b.4 ratified helper at `coding_agent/base.py:382-470`),
**Then** `UnsupportedBinaryVersionError` is raised per FR47 with: (a) detected version, (b) pinned range, (c) install/upgrade command suggestion (`npm install -g @anthropic-ai/claude-code@latest`).

**And Given** the adapter and a connected MCP server (via `_kernel/context.MCPLifecycleManager` from Story 1b.1),
**When** `adapter.run("Use the X tool")` runs (Story 4.2 pre-create-story drift D-C 2026-05-20: pre-edit `send_prompt` was stale; Story 1b.4 D1 ratified single `run()` method per PRD FR12 — same drift as Story 4.1 D-C),
**Then** the `claude` subprocess is invoked with the MCP server registered in its `.mcp.json` (a temporary `.mcp.json` is generated for the subprocess session and cleaned up on exit per per-test scope from Story 1b.1), tool calls executed by `claude` are captured via the stream-json output, and `AgentRunResult.metadata.mcp_coverage="external_mixed"` reflects that observation happens via stream-json parsing (not in-process span capture — Epic 5's hosted-MCP observer changes this when applicable).

**And** the adapter is registered via the `agenteval.coding_agents` entry-points group as `"claude-code-cli"` (Story 4.2 pre-create-story drift D-D 2026-05-20: pre-edit `robotframework_agenteval.adapters` was the LEGACY backward-compat group per ADR-013 L18; primary group is `agenteval.coding_agents` per Story 1b.3 `_GROUP_CODING_AGENTS` + Story 4.1 D-B precedent); declared as `[claude-code]` optional extra in `pyproject.toml` (`uv sync --extra claude-code` installs the adapter's deps + a doc note about needing the `claude` CLI on `$PATH`).

**And** unit tests in `tests/unit/coding_agent/test_claude_code_cli.py` use recorded stream-json fixtures (captured from a real `claude` invocation, sanitized for credentials per Story 1b.2's redaction) to exercise `_parse_stream_output()` without requiring the binary to be installed in CI.

---

#### Story 4.3: Orchestration Keywords + Config Precedence

As **Raj (Agent Developer)**,
I want `Send Prompt`, `Run Scenario`, and the `mcp_servers=` keyword argument plus `Get Effective Config` for inspecting resolved configuration,
So that I can run agent flows from a `.robot` test (single prompt or multi-step YAML scenario), connect any adapter to any MCP server, and audit which configuration values are actually in effect after the FR41 precedence rules resolve (defaults < library kwargs < environment < scenario YAML < per-keyword kwargs).

**Acceptance Criteria:**

**Given** the Generic adapter from Story 4.1 (or CC CLI adapter from Story 4.2),
**When** I call `${result}=    Send Prompt    adapter=generic    prompt=Hello    model=anthropic/claude-sonnet-4-6` in a `.robot` test,
**Then** the variable receives an `AgentRunResult` with the adapter's response; the call resolves the adapter via `_kernel/discovery.py`, executes the prompt, captures the trace via Story 1b.2's trace store, and returns the result in <30 seconds for a typical model + prompt.

**And Given** a scenario YAML file at `tests/fixtures/scenarios/multi-turn-search.yaml` (with multiple turns, tool expectations, response constraints — schema per PRD FR15 L1514: `model`, `provider`, `agent`, `mcp_servers`, `evals[]` with `prompt`, `repeat`, `expect:` block (per-keyword thresholds), optional `judge:` block Phase 2),
**When** I call `${result}=    Run Scenario    adapter=generic    scenario=tests/fixtures/scenarios/multi-turn-search.yaml    mcp_servers=echo` in a `.robot` test,
**Then** the scenario YAML is loaded + validated against a schema at `src/AgentEval/scenarios/schema.py` (raises `InvalidScenarioYAMLError` — Story 4.3 pre-create-story drift D-C 2026-05-20: 18th leaf added to error catalog as Tier-1 setup-failure semantics paralleling `InvalidMCPServerConfigError`; `error_code = "INVALID_SCENARIO_YAML"`; exit code 65 same family) with line + JSON Pointer on schema violation, the scenario is executed eval-by-eval against the adapter with the named MCP servers attached (Phase-1 carve-out: each `eval` is dispatched as a separate `adapter.run()` call; full multi-turn conversation threading is Phase-1.5 — DF-4.3-S? carry-over), and the returned `AgentRunResult`-like aggregate captures each eval's per-call result. (Story 4.3 pre-create-story drift D-D 2026-05-20: `mcp_servers=echo,echo2` comma-separated name list resolves via `_kernel/context.MCPLifecycleManager.get_handle(name)` → list of `ServerHandle` → forwarded to `adapter.run(mcp_servers=...)`; resolution failure on unknown name raises `KeyError("unknown MCP server: <name>; known: [...]")` per Phase-1 pragmatic stance.)

**And Given** the `mcp_servers=` keyword argument accepted on `Send Prompt` + `Run Scenario` + the Discoverability keyword (Story 4.4),
**When** I call any of these keywords with `mcp_servers=server1,server2` (comma-separated list of names previously started via `MCP.Start Server`),
**Then** the adapter connects to each named server before invocation, runs the operation, and disconnects per-test-scope cleanup (per Story 1b.1's context.py).

**And Given** the configuration precedence chain from FR41 (library `__init__` args → environment variables → `.env` file at project root → defaults; 4 levels per PRD FR41 L1563 verbatim — Story 4.3 pre-create-story drift D-A 2026-05-20: pre-edit text "defaults < library kwargs < environment < scenario YAML < per-keyword kwargs" added 2 unratified levels that PRD doesn't include; scenario-YAML config and per-keyword kwargs are CALL-TIME overrides, NOT library-level config that `Get Effective Config` reflects),
**When** I call `${config}=    Get Effective Config` in a `.robot` test, the returned dict maps each setting name → its resolved value (`dict[str, Any]` — preserves Story 1a.6 ratified shape for backwards-compatibility with existing tier1 tests). Calling `${cv}=    Get Effective Config    setting=max_cost_usd` returns a `ConfigValue` dataclass with `value` + `source: Literal["init_arg", "env", "dotenv", "default"]` fields per PRD FR41 L1563 (Story 4.3 pre-create-story drift D-B 2026-05-20: pre-edit "_provenance sub-dict" shape was epics.md drift relative to PRD; pragmatic Phase-1 stance ships ConfigValue via single-setting form + new `Get Effective Config With Provenance` keyword returning `dict[str, ConfigValue]` — full PRD FR41 dict-shape migration tracked as **DF-4.3-S1** Phase-1.5 carry-over because the existing `dict[str, Any]` shape is consumed by 5+ tier1 tests that would otherwise break).

**And** unit tests in `tests/unit/coding_agent/test_orchestration.py` cover: Send Prompt happy path with Mock adapter, Run Scenario YAML loading + schema violation paths, mcp_servers= attaching/detaching correctly, Get Effective Config precedence resolution for all 5 levels.

---

#### Story 4.4: MVP Tool Discoverability (FR10a) — Single-Runtime Discoverability Check

As **Mei (Agent Surface Author — MCP author mode)**,
I want `MCP.Get Tool Discoverability` to drive a single-runtime trial of natural-language tasks against my MCP server's tools (using the Generic adapter from Story 4.1), returning a structured result table that shows which tasks the agent solved and which tools it chose (or didn't),
So that I can prove my MCP tools are discoverable + chosen by a representative agent on representative tasks — per AC-DISCOVER-01 — within a cost budget (default `max_cost_usd=5.00` per AC-DISCOVER-02), with per-trial cost reported even on partial-budget exits.

**Acceptance Criteria:**

**Given** a connected MCP server from Story 3.1 (e.g., `rf-mcp` or the bundled echo server) + the Generic adapter from Story 4.1,
**When** I call `${result}=    MCP.Get Tool Discoverability    mcp_server=echo    adapter=generic    model=anthropic/claude-sonnet-4-6    tasks=tests/fixtures/discoverability/tasks-basic.yaml    trials_per_task=3    max_cost_usd=5.00` in a `.robot` test,
**Then** the variable receives a `DiscoverabilityResult` dataclass with: `per_task_results` (list of `TaskResult` with `task_id`, `task_prompt`, `trials_run`, `success_count` per Pass@k semantics, `tool_calls_per_trial`, `competing_tools_picked`, `cost_per_trial_usd`), `summary` (overall pass rate, total cost, total runtime), `mcp_coverage` (per Story 1b.2's compute_mcp_coverage).

**And Given** the keyword decorated with `@guarded_fanout(cost_kwarg="max_cost_usd", runtime_kwarg="max_runtime_seconds")` from Story 1b.3,
**When** the pre-flight cost estimate exceeds `max_cost_usd`,
**Then** `CostExceededError` is raised per FR11 + AC-DISCOVER-02 with: (a) projected cost, (b) cost cap, (c) suggested mitigation ("reduce trials, use a cheaper model, increase max_cost_usd").

**And Given** `max_runtime_seconds=60` and a trial that exceeds the runtime budget mid-execution,
**When** the wall-clock meter hits 1.1× the runtime budget,
**Then** `RuntimeBudgetExceededError` is raised per FR11b with: (a) elapsed time, (b) runtime cap, (c) per-trial cost accumulation up to the budget exit (consumed cost is reported even when budget exit is forced).

**And Given** the bundled task fixture at `tests/fixtures/discoverability/tasks-basic.yaml` containing 5 representative natural-language tasks that should exercise the bundled echo MCP server's tools,
**When** I call `MCP.Get Tool Discoverability` against echo with the Mock provider adapter (deterministic, no API cost),
**Then** the result is reproducible across multiple invocations (the Mock provider returns the same tool-call pattern each time), enabling unit test verification without external dependencies.

**And Given** the keyword carries `[Tier 3 — Non-Deterministic]` libdoc badge per Story 1b.6's conventions test,
**When** a user attempts to call the keyword inside a `validate` polling block,
**Then** `PollingDisallowedError` is raised at the AssertionEngine layer (gate enforcement is Epic 6, but the keyword's Tier-3 annotation makes it gateable from Day 1).

**And** `MCP.Get Tool Discoverability` is exercised against `rf-mcp`'s MCP server with the Mock provider in an integration test (no real API cost) verifying the per-task / per-trial structure works end-to-end on a non-trivial server. Recipe Gallery #3 (Epic 8b) will be built from this story's example invocation pattern.

---

### Epic 5: Trace Recording + Observability + Honesty Fields

#### Story 5.1: OTel Listener + Span Generation + Memory/JSONL Backends

As **Raj (Agent Developer)** or **Mei (Agent Surface Author)**,
I want a Robot Framework Listener v3 that registers automatically + generates OTel GenAI-shape spans (`invoke_agent → chat → execute_tool` hierarchy) backed by memory + JSONL backends,
So that every agent run captures auditable trace data with per-test scope from Day 1 — no consumer setup beyond `--listener AgentEval.telemetry.listener`.

**Acceptance Criteria:**

**Given** the `_kernel/trace_store.py` from Story 1b.2 and the `_kernel/context.py` from Story 1b.1,
**When** I implement `src/AgentEval/telemetry/listener.py` (Listener v3) + `src/AgentEval/telemetry/spans.py` (OTel GenAI span generation) + `src/AgentEval/telemetry/backends.py` (Memory + JSONL backends) + `src/AgentEval/telemetry/semconv.py` (Internal facade for `gen_ai.*` attribute names per NFR-COMPAT-06; Story 5.1 pre-create-story drift fix 2026-05-20 added — was missing from pre-edit epics.md L1437 despite being mandated by architecture L1251),
**Then** a `.robot` test invoked via `robot --listener AgentEval.telemetry.listener tests/` (the `--listener` flag is **required** — RF does NOT auto-discover listeners from PyPA entry-points; this was empirically verified 2026-05-17 and documented at `docs/contracts/listener-integration.md`) automatically captures `invoke_agent` spans (one per Send Prompt / Run Scenario / Discoverability call), `chat` child spans (one per LLM round-trip), `execute_tool` child spans (one per tool call), each with `gen_ai.*` attributes per OTel GenAI semconv (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, etc.).

**And Given** the empirically established constraint from 2026-05-17 — RF Library Listeners do NOT receive `xunit_file` / `output_file` hooks (their `close()` fires BEFORE RF writes those files; verified via /tmp/rf-lib-listener-experiment),
**When** the AgentEval listener implementation is chosen,
**Then** it is implemented as a **Regular RF Listener v3** (a standalone class registered via `--listener`), NOT as a Library Listener (the AgentEval library itself does NOT carry `ROBOT_LIBRARY_LISTENER` — that path was empirically disqualified for the xunit enrichment hook that Story 8a.1 needs). The listener class lives at `src/AgentEval/telemetry/listener.py` and the consumer-facing usage path (`--listener AgentEval.telemetry.listener`) is documented in `docs/contracts/listener-integration.md` + `agenteval init` scaffolds it in the README + first example.

**And Given** `trace_backend="memory"` (default per Story 1a.6),
**When** spans are emitted during a test,
**Then** they land in the in-memory trace store + are queryable via `${spans}=    Get Spans` keyword (returns spans for the current test's scope only — cross-test isolation enforced by Story 1b.2).

**And Given** `trace_backend="jsonl"` and `trace_path="/tmp/agenteval-traces.jsonl"`,
**When** the test completes,
**Then** all spans for the test scope are flushed to the JSONL file (one span per line, OTel JSON envelope shape), with each span's `test_id` + `suite_id` from the per-test context.

**And** unit tests in `tests/unit/telemetry/test_listener.py` + `test_spans.py` + `test_backends.py` cover: listener entry-point auto-registration, span hierarchy structure, GenAI attribute population, memory backend isolation, JSONL backend write + parse round-trip.

---

#### Story 5.2: Hosted-MCP Observer + Honesty Fields + IncompleteTraceError

As **Mei (Agent Surface Author)** or **Raj (Agent Developer)**,
I want the hosted-MCP universal observer (post-Epic-0-spike) wired so that tool-call traces are captured even for in-process MCP servers; plus the `completeness` and `mcp_coverage` honesty fields populated on every `AgentRunResult`; plus `IncompleteTraceError` raised when coverage is `external_mixed` and the consumer asserts on tool-level details that can't be honestly answered,
So that consumers get truthful evidence about what was observed vs assumed — never silent degradation.

**Acceptance Criteria:**

**Given** Story 0.1's hosted-MCP observer spike findings + the ratified ADR-004 (was ADR-007) from Story 0.3 (see `docs/adr/ADR-004-hosted-mcp-observation.md`),
**When** I implement `src/AgentEval/mcp/observer.py` per the spike API surface,
**Then** the observer attaches to any MCP server connected via `MCP.Connect To Server` from Story 3.1 (Story 3.2 code-review Auditor HIGH-3 fix 2026-05-19: stale `MCP.Connect` amended per FR8 verbatim; the same observer pattern works for in-process + subprocess transports per the spike output); tool-call traces flow into the Story 5.1 trace store with `gen_ai.system="mcp"` + tool name + arguments + result + latency.

**And Given** an agent run via the Generic adapter (Story 4.1) where the MCP server is hosted in-process,
**When** `AgentRunResult` is produced,
**Then** `completeness="full"` + `mcp_coverage="hosted_in_process"` (per the per-adapter detection contract at `docs/contracts/mcp-coverage-detection.md` — Story 5.2 pre-create-story drift D-1 fix 2026-05-20: pre-edit cited Story 1b.2's `compute_mcp_coverage` which doesn't exist; Story 1b.2 only ships `_check_mcp_coverage` enforcement gate, detection is per-adapter per ADR-016 D4), and the trace contains tool-execution spans observed via the hosted-MCP observer (not just inferred from the adapter's response).

**And Given** an agent run via the CC CLI adapter (Story 4.2) where MCP server tool calls happen inside the `claude` subprocess and observation is post-hoc from stream-json,
**When** `AgentRunResult` is produced,
**Then** `mcp_coverage="external_mixed"` (the hosted-MCP observer can't reach inside the subprocess) + `completeness="full"` if stream-json reports a normal terminal event or `"partial"` if the stream truncated.

**And Given** `mcp_coverage="external_mixed"` and a `.robot` test asserting on a `Tool Call Should Have Occurred` (Epic 6 keyword) for a tool that requires hosted observation to verify,
**When** the assertion runs,
**Then** `IncompleteTraceError` is raised per FR37 with: (a) the trace's `mcp_coverage` value, (b) the assertion that needs full coverage, (c) suggested mitigation ("use Generic adapter with hosted MCP server, or assert on response-level evidence instead of tool-level").

**And** integration tests in `tests/integration/telemetry/test_observer.py` cover all 4 `mcp_coverage` values produced from representative scenarios + IncompleteTraceError raising paths.

---

#### Story 5.3: Evidence Block + Redaction Wiring + RunManifest

As **Raj (Agent Developer)** auditing a test run,
I want the AC-SIMPLICITY-01 evidence-block format applied automatically to RF output (per-test trace summary with prompt, response, tool calls, cost, coverage, completeness), credential redaction wired into the listener pipeline (so traces NEVER contain raw API keys even on listener failure paths), and a RunManifest JSON sidecar produced per test capturing the full run metadata,
So that test reports are auditable + safe for sharing externally — no credential leaks, no missing run context.

**Acceptance Criteria:**

**Given** the evidence-block format per AC-SIMPLICITY-01 (≤80 chars per line, prompt + response + tool calls + cost + coverage + completeness in a single visual block),
**When** a test completes via the listener,
**Then** RF's `output.xml` receives the formatted evidence block as a structured message attached to each Send Prompt / Run Scenario / Discoverability keyword call, formatted per the visual contract from `docs/contracts/otel-trace-visual.md` (Story 8b authors this contract; Story 5.3 implements the format).

**And Given** the redaction primitives from Story 1b.2 (`_kernel/redaction.py`),
**When** any span/log/evidence block is generated containing text matching known credential patterns,
**Then** the credential is replaced with `[REDACTED:<pattern_name>]` before any backend write or output emission; the redaction pipeline runs at the listener choke point (no span bypasses redaction); `Get Effective Config` also redacts credentials in its output per FR38b.

**And Given** a test run completes,
**When** the RunManifest is written per FR39,
**Then** a JSON sidecar at `<output_dir>/run-manifest-<test_id>.json` contains: `test_id`, `suite_id`, `started_at`, `completed_at`, `library_version`, `adapter` (name + version), `model` (if applicable), `mcp_servers` (list with names + transports), `trace_backend`, `total_cost_usd`, `completeness`, `mcp_coverage`, `warnings` (list, populated by Story 5.4), `seed` (if any RNG was seeded for reproducibility).

**And** unit tests in `tests/unit/telemetry/test_evidence_block.py` + `test_redaction_wiring.py` + `test_run_manifest.py` cover: evidence block format conforms to visual contract, redaction catches representative credential patterns end-to-end (including in evidence blocks, JSONL trace files, RunManifest fields), RunManifest schema-validates against a published JSON schema at `docs/contracts/run-manifest-schema.json`.

---

#### Story 5.4: DegradedTraceWarning + Get Last Warnings + Per-Test Scope Polish

As **Raj (Agent Developer)** or **Priya (QA Engineer)**,
I want `DegradedTraceWarning` surfaced via the RF Listener whenever observability degrades (e.g., `mcp_coverage` falls to `external_mixed` mid-suite, RunManifest write fails, redaction encounters a novel pattern), plus the `Get Last Warnings` keyword for programmatic warning inspection, plus polish on the per-test MCP scope wiring per AC-MCP-OBSERVE-03,
So that I get loud, structured signals when trace quality degrades — instead of silently passing tests with degraded evidence.

**Acceptance Criteria:**

**Given** an agent run where the hosted-MCP observer fails partway (e.g., MCP server crashes mid-call),
**When** the run completes,
**Then** `DegradedTraceWarning` per FR61 is logged via RF's listener warning channel with: (a) the degradation cause, (b) the affected `mcp_coverage` change, (c) the test impact summary; the warning is also appended to the test's RunManifest `warnings` field.

**And Given** the `Get Last Warnings` keyword from FR62,
**When** I call `${warnings}=    Get Last Warnings    test_id=current` in a `.robot` test,
**Then** the variable receives a list of `WarningRecord` instances emitted during the current test scope (each with `warning_type`, `message`, `source`, `timestamp`, `remediation` per FR62 ratified shape 2026-05-20 unifying PRD `source + message + remediation` with the test-author-required `warning_type + timestamp`); calling with `test_id=all` returns warnings across the whole suite.

**And Given** AC-MCP-OBSERVE-03 (per-test MCP scope via Listener v3 `test_id`),
**When** I run a `.robot` test suite under `pabot --processes 4` with multiple tests that each start their own MCP servers,
**Then** each test's MCP servers + spans + warnings + RunManifest are scoped to that test's `test_id` only (no cross-test pollution), and cleanup runs at test-end per the `mcp_per_test` setting (per Story 3.1).

**And Given** all 3 `mcp_coverage` values (`hosted_in_process`, `subprocess_with_observer`, `external_mixed`) can be reached + reported correctly per ADR-016 D1 ratification (NOT 4 — the original 2026-05-15 draft's `partial` value was superseded by the 3-state Literal at 2026-05-17 ratification),
**When** I run integration tests at `tests/integration/telemetry/test_warnings.py`,
**Then** each coverage value triggers the appropriate warning behavior + the `Get Last Warnings` keyword returns the expected warning list for each scenario.

**And** Epic 5 coverage status: AC-MCP-OBSERVE-01 (mcp_coverage indicator) ✓, AC-MCP-OBSERVE-03 (per-test MCP scope) ✓, AC-SIMPLICITY-01 (evidence block legibility) ✓ — verified by integration tests.

---

#### Story 5.5: Interleaved Dogfood — Trace Observability Against `rf-mcp`

As a **dogfood validator** (Raj's downstream consumer perspective),
I want a `.robot` suite that exercises `rf-mcp`'s `robotmcp` MCP server through agenteval's Epic 5 trace pipeline (hosted-MCP observer + spans + RunManifest sidecar + DegradedTraceWarning collector + `Get Last Warnings` keyword) + asserts every trace artifact populates correctly,
So that AC-DOGFOOD-01 advances toward Phase 1 completion — `rf-mcp` is dogfooded as the MCP-under-test through agenteval's trace observability layer, surfacing real-world gaps before downstream consumers hit them.

**Story 5.5 epic-spec amendment 2026-05-20 pre-create-story drift check (26th use of `feedback_spec_vs_ratified_doc_precheck`):** the original draft framed Story 5.5 as "port rf-mcp's existing trace-observability tests" — but `rf-mcp`'s `test_mcp_*.py` corpus tests the MCP-server surface (call_tool, list_tools, error scenarios), NOT agent-side trace observability against rf-mcp. There are NO existing trace tests in rf-mcp to port. The honest framing: Story 5.5 dogfoods agenteval's trace pipeline against rf-mcp's `robotmcp` server as the MCP under test — this is the first place rf-mcp is exercised through agenteval's observability layer. Similarly, the original draft said "the workflow runs the new .robot trace suites" but `.github/workflows/dogfood-integration.yml` is Phase-1-smoke-only by design (Story 1a.2 HIGH-1 fake-green lesson); real cross-repo CI integration is deferred to Story 9.1/9.2. Story 5.5 ships a locally-runnable `.robot` suite matching the Story 3.3 dogfood pattern (`uv run robot tests/dogfood/rf-mcp/...` with `RF_MCP_REPO_ROOT` env override).

**Acceptance Criteria:**

**Given** rf-mcp's `robotmcp` MCP server exposed via the `.mcp.json` vendored at `tests/dogfood/rf-mcp/.mcp.json` (Story 3.3),
**When** a `.robot` test starts the server via Story 3.1's `MCP.Start Server`, wires it through `GenericAdapter(mcp_servers={...})` (Story 5.2 hosted-observer path), and triggers a tool call,
**Then** agenteval's hosted-MCP observer intercepts the tool call + populates: (a) the OTel span store (`_kernel/trace_store.get_run_spans`); (b) the tool-call list (`_kernel/trace_store.get_tool_calls`); (c) `AgentRunResult.metadata.mcp_coverage="hosted_in_process"` per ADR-016 D1; (d) the RunManifest JSON sidecar at `<output_dir>/agenteval/manifest__<suite>__<test>.json` (Story 5.3) — verified by reading the sidecar back + asserting on `warnings`, `mcp_coverage`, `completeness`, `total_cost_usd` fields.

**And Given** Story 5.5 ships a minimal extension to `TelemetryLibrary` (Story 5.4) — three new RF keywords (`Get Spans`, `Get Tool Calls`, `Get Run Manifest`) that wrap the `_kernel/trace_store` projection accessors with `@tier(1)` Tier-1 badges,
**When** the dogfood `.robot` suite calls those keywords against the bound `test_id`,
**Then** the suite reads spans + tool calls + manifest through the public keyword surface (not through Python `Evaluate`) — proving the public Epic 5 surface is usable from `.robot` tests.

**And Given** a forced degradation event (e.g., calling `observer.mark_external_mixed("simulated subprocess MCP")` after at least one tool call),
**When** the `.robot` suite calls `Get Last Warnings    test_id=current`,
**Then** the returned list contains ≥1 `WarningRecord` with `warning_type="AgentEval.errors.DegradedTraceWarning"` + `source="mcp.observer"` (per AC-5.4.3 canonical FR61 trigger) + `mcp_coverage` falls to `"external_mixed"`.

**And Given** the parity checklist at `tests/dogfood/rf-mcp/parity-checklist-rf-mcp-trace.md`,
**When** Story 5.5 closes,
**Then** the checklist documents: (a) what rf-mcp's pytest corpus actually covers (MCP-surface, NOT trace observability); (b) what this `.robot` suite NEWLY covers (the agent-side trace pipeline against rf-mcp as the MCP under test); (c) explicit honest framing of the Story 5.5 scope correction vs. the original epic draft (the D-3 drift fix per `feedback_spec_vs_ratified_doc_precheck`); (d) the local invocation command `uv run robot tests/dogfood/rf-mcp/test_trace_observability_parity.robot`.

**And** the dogfood pass surfaces ≥1 actionable agenteval improvement — file as `dogfood-finding` tagged issue. **Likely candidate**: DF-5.2-S3 (Generic adapter multi-turn tool-dispatch loop) is Phase-2 scope; without it the dogfood `.robot` suite cannot drive a real model to invoke rf-mcp tools, so the dogfood must use a controlled fixture (direct `Call Tool` invocation) rather than agent-driven dispatch. This validates the OBSERVER + TRACE pipeline but not the AGENT-LOOP integration; the agent-loop integration follow-up is the dogfood-finding to file.

**And** combined with Story 3.3's MCP-surface dogfood, rf-mcp now has 2 dogfood `.robot` suites at `tests/dogfood/rf-mcp/`. Metric-assertion dogfood (Epic 6 Story 6.4 candidate) remains for full `rf-mcp` parity per `AC-DOGFOOD-01`. **CI wiring deferred** per Phase-1 norm: `dogfood-integration.yml` stays smoke-only; real cross-repo CI integration is Story 9.1/9.2.

---

### Epic 6: Tool-Call Metrics + Statistical Assertions + Determinism Enforcement

#### Story 6.1: Tool-Call Metrics Library

As **Raj (Agent Developer)** or **Priya (QA Engineer)**,
I want **9 `Metric.*` keywords** — `Get Tool Call Count`, `Get Tool Call Names`, `Get Tool Hit Rate`, `Get Tool Success Rate`, `Get Unnecessary Call Rate`, `Get Token Usage`, `Get Latency`, `Get Latency P95`, `Get Cost Total` — reading from any captured `AgentRunResult` (Phase-1 source; future Phase-1.5+ trace-store-projection-accessor path tracked per architecture L677),
So that I can compute headline agent-performance metrics in a `.robot` test from the trace data already captured by Epic 5.

**Story 6.1 epic-spec amendment 2026-05-20 pre-create-story drift check (27th use of `feedback_spec_vs_ratified_doc_precheck`):** original draft had 7 drifts vs PRD FR19-22 + architecture L1290: (D-1) `Get Tool Names` → `Get Tool Call Names` (PRD verbatim); (D-2) single `Get Latency` → split into `Get Latency` (mean) + `Get Latency P95` (P95) per PRD FR22 + architecture L1290; (D-3) `LatencyStats with mean+P95+max` is a TYPE in `metrics/types.py`, NOT a keyword return — each latency keyword returns a scalar float per PRD FR22; (D-4) `Get Cost` → `Get Cost Total` (PRD verbatim + architecture L1290); (D-5) `Get Tool Call Names` returns the chronological list "preserving order" per PRD FR19 (NOT a unique set — duplicates preserved when an agent calls the same tool multiple times); (D-6) keyword count "8" → "9" (PRD enumerates 9: 2 in FR19 + 2 in FR20 + 1 in FR21 + 4 in FR22); (D-7) Phase-1 data source is `AgentRunResult` fields (populated by adapter/observer) NOT trace_store spans (which adapters don't yet emit per DF-5.5-DOGFOOD-2 / C44). All 7 drifts amended pre-authoring.

**Acceptance Criteria:**

**Given** an `AgentRunResult` from `Send Prompt` / `Run Scenario` / Discoverability,
**When** I call any of the 9 metrics keywords against it (e.g., `${count}=    Metric.Get Tool Call Count    ${result}`),
**Then** the variable receives the metric value per PRD FR19-22 verbatim semantics:
- `Get Tool Call Count` → `int` — `len(result.tool_calls)`
- `Get Tool Call Names` → `list[str]` preserving chronological order — `[tc.name for tc in result.tool_calls]` (duplicates preserved when an agent invokes the same tool multiple times)
- `Get Tool Hit Rate <expected_tools>` → `float` — `|{name ∈ expected ∩ observed}| / |expected|` (fraction of expected tools that appeared at least once)
- `Get Tool Success Rate` → `float` — `count(tc.error is None) / len(result.tool_calls)` (zero-len → 0.0)
- `Get Unnecessary Call Rate <expected_tools>` → `float` — `count(tc.name ∉ expected) / len(result.tool_calls)` (zero-len → 0.0)
- `Get Token Usage` → `Usage(input_tokens, output_tokens, cached_input_tokens)` — `result.usage` projection (Story 1b.2 ratified dataclass at `src/AgentEval/types.py:132`; no `total` field — consumers compute `total = input_tokens + output_tokens` at call site when needed)
- `Get Latency` → `float` — mean turn-level latency in **ms** (from `result.tool_calls[*].latency_ms` mean, with fallback to `result.latency_seconds * 1000` when tool_calls is empty)
- `Get Latency P95` → `float` — P95 of `result.tool_calls[*].latency_ms` (with same scalar-fallback when fewer than 2 tool_calls)
- `Get Cost Total` → `float` — `result.cost_usd` (USD)

**And Given** the same metrics keywords accepting a `list[AgentRunResult]` (multi-trial aggregation),
**When** I call `${cost_total}=    Metric.Get Cost Total    ${results_list}`,
**Then** the result aggregates across the trials (**sum** for `Cost Total` + `Tool Call Count`; **mean** for `Hit Rate` + `Success Rate` + `Unnecessary Call Rate` + `Latency`; **P95** computed across the union of tool_calls for `Latency P95`; **set-union preserving order-of-first-appearance** for `Tool Call Names`; **sum-per-field** for `Token Usage`) — supporting Pass@k post-hoc analysis from Story 6.3. Single-`AgentRunResult` callers pass `result`; multi-trial callers pass `[result_1, result_2, ...]`. Keyword dispatch on input type.

**And Given** Phase-1's `IncompleteTraceError` gate (Story 5.2),
**When** a metric keyword is called on an `AgentRunResult` with `metadata.mcp_coverage == "external_mixed"` AND tool-call-bearing metric (count, names, hit_rate, success_rate, unnecessary_rate),
**Then** `_kernel/coverage._check_mcp_coverage(run)` raises `IncompleteTraceError` per FR37 unless caller opts in via `allow_external_mcp_blind=True` Library kwarg. Token usage + latency + cost metrics do NOT trigger the gate (they're observer-independent provider-reported scalars).

**And** all 9 keywords ship Tier-1 badges (`@tier(1)` + `[Tier 1 — Deterministic]` docstring per `feedback_dogfood_fake_green_precheck`-related conventions); P95 latency <50ms per invocation; conventions tests pass; unit tests cover the aggregation paths against recorded fixture `AgentRunResult` data. **Phase-1 data source carve-out**: keywords read from `AgentRunResult` fields (populated by adapter/observer), NOT from `_kernel/trace_store` spans (per architecture L677's idealized design). Architecture L677 drift filed as DF-6.1-S1 carry-over for Phase-1.5 closure (when DF-5.5-DOGFOOD-2 adapter span instrumentation lands).

---

#### Story 6.2: Trajectory + Tool Call + Response Assertions

As **Raj (Agent Developer)**,
I want `Trajectory Should Match` (exact / subsequence / set / regex modes), `Tool Call Should Have Occurred`, and `Agent Response Should Contain` / `Should Match Regex` / `Should Match Schema` assertion keywords,
So that I can assert on agent behavior at the trajectory, tool-call, and response levels — covering the three falsifiable evidence layers per BFCL methodology.

**Acceptance Criteria:**

**Given** an `AgentRunResult` with captured tool calls,
**When** I call `Trajectory Should Match    ${result}    expected=[search, search, fetch]    mode=exact` in a `.robot` test,
**Then** the assertion compares the actual tool-call sequence to the expected list; `mode=exact` requires exact match, `mode=subsequence` allows interleaving with other calls, `mode=set` ignores order, `mode=regex` matches each expected entry as a regex per FR23b.

**And Given** a result + an expected tool invocation,
**When** I call `Tool Call Should Have Occurred    ${result}    tool=search    arguments={"query": "foo"}`,
**Then** the assertion passes if any tool call matches; argument matching uses dict-subset semantics (extra args allowed) unless `match_mode=exact` per FR24.

**And Given** an `AgentRunResult` + assertion variants,
**When** I call `Agent Response Should Contain    ${result}    "expected substring"` or `Agent Response Should Match Regex    ${result}    pattern` or `Agent Response Should Match Schema    ${result}    schema=path.json`,
**Then** each assertion variant verifies the response text per FR25; schema mode uses jsonschema validation against the provided schema.

**And Given** an IncompleteTraceError condition (mcp_coverage=external_mixed + tool-level assertion),
**When** `Tool Call Should Have Occurred` runs,
**Then** the error from Story 5.2 propagates with the FR37 message — proving the gate works end-to-end.

**And** all assertions ship with Tier-1 badges (`@tier(1)` + `[Tier 1 — Deterministic]` docstring); use **Python stdlib primitives** (`==`, `in`, `re.search` / `re.fullmatch`, `jsonschema.validate`) for the operator surface in Phase-1 — **NOT** RF builtins (Story 6.2 code-review HIGH-ζ Auditor 1-way spec-drift fix 2026-05-20: pre-edit framing said "RF builtins" but library code uses pure-Python primitives + raises `AssertionError` directly; RF-builtin / AssertionEngine wrapping is Story 6.3 scope); **AssertionEngine integration deferred to Story 6.3** (which plans `_assertions/adapter.py` scaffolding per epic L1649) — Story 6.3 will add the `robotframework-assertion-engine>=4.0,<5.0` dep + wrap these 5 Phase-1 keywords through the AssertionEngine `==`/`!=`/`contains`/`matches` operator surface. **Story 6.2 epic-spec amendment 2026-05-20 pre-create-story drift check (28th use of `feedback_spec_vs_ratified_doc_precheck`):** original AC mentioned AssertionEngine integration but `robotframework-assertion-engine` isn't pinned in pyproject.toml + `_assertions/adapter.py` doesn't exist yet (was placeholder from Story 1a.1). Per dev-story HALT condition "new dependencies need user approval", Phase-1 ships keyword surface only; AssertionEngine wiring is logically Story 6.3's `_assertions/adapter.py` work. Unit tests cover all 4 trajectory modes + 3 response assertion variants + IncompleteTraceError propagation + dict-subset arg-matching semantics.

---

#### Story 6.3: Statistical Primitives + Tier ACL + Determinism Enforcement

As **Raj (Agent Developer)** or **Devon (Agent Surface Author)**,
I want `Stat.Run N Times` (independent-sample N-trial runner), `Stat.Get Pass At K` (HumanEval unbiased estimator), three-tier ACL gates enforced at `_assertions/adapter.py` (polling ban on Tier-2/3, Tier-1 LLM-invocation ban), the `Get Keyword Tier` keyword surface, and the determinism guarantees from FR31a/b enforced,
So that non-deterministic agent flows are characterized statistically + the tier model is structurally enforced, not just documented.

**Acceptance Criteria:**

**Given** any agent keyword (Send Prompt, Run Scenario, Discoverability),
**When** I call `${results}=    Stat.Run N Times    n=10    keyword=Send Prompt    keyword_args=[adapter=generic, prompt=Hello]` in a `.robot` test,
**Then** the wrapper runs the keyword 10 independent times with proper test-id sub-scoping (each trial gets its own trace scope), accumulates results, returns a `list[KeywordRun]` of 10 instances (per FR26 verbatim return type + `docs/contracts/determinism-contract.md` L55 ratified by Story 1b.6 Codex STAR catch; pre-edit "10 `AgentRunResult` instances" was a doc-doc drift — `KeywordRun` is the FR26 type, NOT `AgentRunResult` — amended Story 6.3 pre-create-story drift check 2026-05-20 / 29th use of `feedback_spec_vs_ratified_doc_precheck`).

**And Given** the 10 results + a success predicate,
**When** I call `${pass_at_3}=    Stat.Get Pass At K    ${results}    k=3    predicate=lambda r: r.completeness == "full"`,
**Then** the variable receives the unbiased Pass@k estimate per HumanEval methodology (FR27), with confidence interval per Wilson CI.

**And Given** the kernel `tier.py` from Story 1b.1 + `_assertions/adapter.py` newly minted by Story 6.3 per architecture L647 (agentguard `_assertions/adapter.py:101-105` pattern),
**When** a `.robot` test calls a Tier-2 or Tier-3 keyword passing a `polling=` argument,
**Then** `PollingDisallowedError` is raised per FR28 with the FR56 actionable message format (keyword name + RF test file path + line number from call stack + verbatim `${runs}=  Stat.Run N Times ...` remediation snippet + ADR link). NOTE: pre-edit Story 6.3 AC-3 conflated polling-ban with validate-disabled gate — the `validate` operator + `allow_validate_operator=False` raise is `ValidateOperatorDisallowed` (AC-7), NOT `PollingDisallowedError`. Two distinct gates per FR28 (polling kwarg trigger) vs FR43 (validate operator trigger). Amended Story 6.3 pre-create-story drift check 2026-05-20 / 29th use of `feedback_spec_vs_ratified_doc_precheck` — architecture L647 + L922-931 + agentguard adapter all use `polling=` kwarg as the FR28 trigger.

**And Given** a Tier-1 keyword (e.g., `Skill.Get Frontmatter`) somehow registered to invoke an LLM (e.g., test mistake),
**When** the LLM invocation attempts during the keyword execution,
**Then** `TierViolationError` per FR30b is raised stating the tier conflict.

**And Given** `${tier}=    Get Keyword Tier    keyword=Skill.Get Frontmatter`,
**When** the keyword runs,
**Then** the result is `1` (the keyword's tier annotation); calling on `Stat.Run N Times` returns `3` (per architecture L380 + L1056 — `Stat.Run N Times` is a Tier-3 fan-out keyword carrying `@guarded_fanout` cost-guardrail enforcement per ADR-015; the wrapped keyword's tier governs the actual fan-out independently). NOTE: pre-edit epic AC-5 said "the runner itself is Tier-1; only the wrapped keyword may be Tier-2/3" — that wording confuses the tier classification (Tier-1/2/3 = LLM-call structure) with the fan-out enforcement model (`@guarded_fanout` only applies to Tier-3 keywords). Per Story 6.3 pre-create-story drift check 2026-05-20 / 29th use of `feedback_spec_vs_ratified_doc_precheck`: amended to architecture-aligned Tier-3 classification.

**And Given** Story 1b.6's determinism contract document,
**When** I run a Tier-1 keyword twice with identical inputs in a single test,
**Then** the outputs are bit-identical (FR31a guarantee enforced — confirmed by a conformance fixture that runs each Tier-1 keyword twice and asserts equality).

**And** validate-operator gate (FR43) enforcement: when `validate` is used WITH `allow_validate_operator=True` flag set via Library kwarg, the gate passes; without the flag, `ValidateOperatorDisallowed` is raised with FR59 format. (Class name ratified `ValidateOperatorDisallowed` per ADR-014 / Story 1a.4 code-review HIGH-4 2026-05-18; previous draft used `ValidateOperatorDisallowedError`.)

---

#### Story 6.4: Interleaved Dogfood — Port `robotframework-agentskills` Metrics Tests

As a **dogfood validator**,
I want `robotframework-agentskills` custom metrics tests replaced by `.robot` suites using Epic 6 keywords,
So that AC-DOGFOOD-01 advances + Raj's primary journey evidence loop closes.

**Acceptance Criteria:**

**Given** `robotframework-agentskills` existing custom Python tests for tool-call metrics + statistical assertions,
**When** I author equivalent `.robot` suites using Epic 6 keywords (`Metric.*`, `Trajectory Should Match`, `Stat.*`),
**Then** parity coverage achieved + tracked via `tests/dogfood/parity-checklist-agentskills-metrics.md`.

**And** `dogfood-integration.yml` runs the new suites in `robotframework-agentskills` head on every PR touching Epic 6 code.

**And** ≥1 actionable agenteval improvement filed as `dogfood-finding`.

---

### Epic 7: Skill Author Validation Flow + Skill Discoverability

**Scope note:** Epic 4 absorbed FR11 + FR11b for the MVP Discoverability keyword via `@guarded_fanout` inheritance. Epic 7 expanded 2026-05-17 to add Skill Discoverability (FR4b + FR4d) — symmetric to Mei's MCP Tool Discoverability (FR10a) — so Devon gets cohort-style evidence that his skill is consistently chosen across a representative task distribution. Phase 2 cross-adapter variant (FR4c) ships in Epic 13 Story 13.5.

#### Story 7.1: Skill.Get Activation Decision Keyword

As **Devon (Agent Surface Author — skill author mode)**,
I want a new `Skill.Get Activation Decision` keyword that takes a skill `.md` file + a prompt + an adapter, returns whether the agent decided to activate the skill (boolean + reasoning),
So that I can run Pass@k against my skill's activation reliability — proving the skill is consistently chosen by the agent on representative prompts.

**Acceptance Criteria:**

**Given** a skill file at `tests/fixtures/skills/example-search.md` + the Generic adapter from Story 4.1 + a connected agent context,
**When** I call `${decision}=    Skill.Get Activation Decision    skill=tests/fixtures/skills/example-search.md    prompt="Help me search for X"    adapter=generic    model=anthropic/claude-sonnet-4-6` in a `.robot` test,
**Then** the variable receives an `ActivationDecision` dataclass with: `activated` (bool), `reasoning` (str — the agent's stated rationale, extracted from response or trace), `cost_usd` (float), `latency_seconds` (float).

**And Given** the keyword decorated with `@tier(3)` (non-deterministic — depends on LLM behavior) + `@guarded_fanout` (cost + runtime guardrails inherited from Story 1b.3),
**When** the keyword is wrapped in `Stat.Run N Times    n=10` and analyzed via `Stat.Get Pass At K`,
**Then** Devon's full stacked validation pattern works end-to-end: Tier-1 static skill validation (Epic 2) + Tier-3 activation reliability (this story) — Recipe Gallery #4 entry from Story 8b will document this pattern.

**And Given** cost + runtime budgets,
**When** budgets exceeded,
**Then** the same `CostExceededError` + `RuntimeBudgetExceededError` from Epic 4 inheritance fire (no duplicate guardrail logic).

**And** unit tests in `tests/unit/skills/test_activation_decision.py` use the Mock provider to verify the dataclass structure deterministically.

---

#### Story 7.2: Skill.Get Discoverability Cohort Keyword + Skill Should Activate For Assertion

As **Devon (Agent Surface Author — skill author mode)**,
I want `Skill.Get Discoverability` cohort keyword (FR4b) that runs a task set against my skill across configurable models/trials, returning per-task Pass@k of correct activation + false-activation rate + missed-activation rate + competing-skills-picked attribution; plus `Skill Should Activate For` single-prompt assertion (FR4d) mirroring `Tool Call Should Have Occurred`,
So that I can claim "my skill is reliably discovered and activated across a representative task distribution" with cohort evidence — not just per-prompt anecdotes — symmetric to what Mei gets for MCP tools via FR10a.

**Acceptance Criteria:**

**Given** a skill file at `tests/fixtures/skills/example-search.md` + the Generic adapter from Story 4.1 + a tasks YAML at `tests/fixtures/discoverability/skill-tasks-basic.yaml` (containing prompts that SHOULD activate the skill + decoys that SHOULD NOT),
**When** I call `${result}=    Skill.Get Discoverability    skill=tests/fixtures/skills/example-search.md    tasks=tests/fixtures/discoverability/skill-tasks-basic.yaml    adapter=generic    model=anthropic/claude-sonnet-4-6    trials_per_task=3    max_cost_usd=5.00` in a `.robot` test,
**Then** the variable receives a `SkillDiscoverabilityResult` dataclass with: `per_task_results` (list of `SkillTaskResult` with `task_id`, `task_prompt`, `should_activate` (bool from fixture), `trials_run`, `activations_observed`, `pass_at_k` (Wilson CI per HumanEval estimator), `competing_skills_picked` (dict mapping competing skill name → trial count), `cost_per_trial_usd`), plus `summary` (overall activation accuracy = correct activations / total trials, false-activation rate, missed-activation rate, total cost, total runtime), plus `mcp_coverage` per Story 1b.2.

**And Given** the keyword decorated with `@guarded_fanout` from Story 1b.3,
**When** cost or runtime budgets exceeded,
**Then** `CostExceededError` / `RuntimeBudgetExceededError` fire identically to Story 4.4 MVP Tool Discoverability (inherited guardrail logic — no duplication).

**And Given** the assertion variant `Skill Should Activate For prompt="Help me search for X" skill=tests/fixtures/skills/example-search.md adapter=generic model=anthropic/claude-sonnet-4-6` (FR4d),
**When** the agent does activate the skill for the prompt,
**Then** the assertion passes.

**And Given** the same assertion call when the agent does NOT activate the target skill,
**When** the assertion runs,
**Then** `SkillDidNotActivateError` is raised with FR59 format containing: (a) the prompt under test, (b) the target skill file path + name, (c) which skill (if any) the agent activated instead, (d) the agent's stated reasoning extracted from the response or trace, (e) suggested mitigation ("rephrase prompt to match skill description, or revise skill description to better match this prompt pattern").

**And Given** the keyword carries `[Tier 3 — Non-Deterministic]` libdoc badge,
**When** a user attempts polling via `validate` operator,
**Then** `PollingDisallowedError` fires per Epic 6's enforcement (same gate as MCP Tool Discoverability).

**And** `Skill.Get Discoverability` is exercised against `robotframework-agentskills` (Story 7.4 dogfood) with the Mock provider in an integration test (no real API cost), verifying the per-task / per-trial structure works end-to-end on real skills. Recipe Gallery #4 (Epic 8b) includes this cohort pattern alongside the single-prompt activation pattern.

---

#### Story 7.3: Devon's Stacked Validation Recipe + Integration Test

As **Devon (Agent Surface Author)**,
I want a documented Recipe Gallery #4 entry showing the full Devon validation pattern (static + activation reliability stacked) plus an integration test proving the recipe works end-to-end against a real skill file,
So that other skill authors can copy the pattern + Phase 2's Epic 12 Judge can plug in as the Tier-2 layer to complete the three-tier flow.

**Acceptance Criteria:**

**Given** the keywords from Stories 2.1 (Skill.* static) + 7.1 (Skill.Get Activation Decision single-prompt) + 7.2 (Skill.Get Discoverability cohort + Skill Should Activate For assertion) + 6.3 (Stat.*),
**When** I author `tests/integration/skills/test_devon_stacked_validation.py`,
**Then** the integration test executes the full pattern: Tier-1 frontmatter validation + Tier-3 cohort Discoverability across 10 trials per task + Pass@5 estimate + assertion on Pass@5 ≥ 0.8 + `Skill Should Activate For` spot-check on representative prompts — all passing against a real skill file fixture using the Mock provider.

**And** Recipe Gallery #4 entry (`docs/recipes/04-skill-author-stacked-validation.md` — authored in Epic 8b but referenced here) is drafted as a stub during Story 7.3 covering both the single-prompt activation pattern (Story 7.1) AND the cohort discoverability pattern (Story 7.2) so Epic 8b can polish it without duplicating the example code.

**And** the integration test verifies that swap-in for the Phase 2 Judge layer is straightforward (the recipe's Tier-2 slot is clearly marked as `# TODO Phase 2: Judge.Get Score here`).

---

#### Story 7.4: Interleaved Dogfood — Skill Discoverability Against `robotframework-agentskills`

As a **dogfood validator** + **Devon validator**,
I want the cohort Skill Discoverability keyword from Story 7.2 exercised against `robotframework-agentskills`' real skill set with a curated representative task set,
So that Devon's cohort discoverability surface is empirically validated against real skills before Epic 9 close — surfacing any gaps in the FR4b/d implementation before Phase 1 ships.

**Acceptance Criteria:**

**Given** `robotframework-agentskills`' published skill `.md` files,
**When** I author a curated task set per skill (a YAML file per skill with `should_activate` + `should_not_activate` prompts, ≥5 each per skill),
**Then** the task sets land in `robotframework-agentskills`' test directory under a `tests/discoverability/` path and are committed to that repo.

**And Given** a `.robot` suite in `robotframework-agentskills` invoking `Skill.Get Discoverability` against each skill + its task set,
**When** the suite runs (locally with Mock provider; cross-repo CI uses a low-cost real provider per project budget),
**Then** per-skill Pass@k results land in the suite output + the activation accuracy table is auditable from the enriched xunit file (per Story 8a.1).

**And Given** the `dogfood-integration.yml` CI workflow,
**When** a PR touches Epic 7 code paths,
**Then** the workflow runs the new Skill Discoverability suites against `robotframework-agentskills` head + reports per-skill pass/fail.

**And** the dogfood pass surfaces ≥1 actionable finding (could be: a skill description needs tightening because the agent fails to discover it, or a misclassified decoy prompt, or an agenteval bug in cohort aggregation) — filed as `dogfood-finding` tagged issue. Zero findings is suspicious; investigate.

**And** the parity checklist at `tests/dogfood/parity-checklist-agentskills-discoverability.md` tracks which skills have Discoverability coverage.

---

### Epic 8a: CI Integration + Conformance Reporting ("CI-Grade" Claim)

#### Story 8a.1: Enrich RF `--xunit` Output Via Listener v3 `xunit_file` Hook + Structured Exit Codes

**Empirical grounding (2026-05-17):** RF's native `--xunit` already produces standard JUnit XML — CI tools (GitHub Actions, GitLab CI, Jenkins) consume it directly. RF's output is **minimal** (per-testcase name, classname, time, failure, skipped — no tags, no per-testcase Documentation, no per-testcase properties, no system-out/system-err). Library Listeners do NOT receive the `xunit_file(path)` / `output_file(path)` hooks (verified — Library Listener `close()` fires BEFORE RF writes the xunit file). Regular RF Listener v3 (the same listener from Story 5.1) DOES receive `xunit_file(path)` after RF writes the file, enabling post-write enrichment.

As **Priya (QA Engineer)** or **a CI operator**,
I want `robotframework-agenteval` to **enrich RF's native `--xunit` output** with per-testcase `<properties>` (cost, tokens, latency, coverage, completeness, trace_id, adapter, model, tier, error_code) + `<system-out>` evidence block + `<system-err>` warning content, via the **`xunit_file(path)` hook on the Story 5.1 Regular Listener** — plus FR50 error_code → exit code mapping for the process-exit channel,
So that mainstream CI tooling that already consumes JUnit XML automatically displays AgentEval cost / coverage / trace-id / agent telemetry alongside standard pass/fail — without parallel CI-tool integrations and without re-emitting JUnit XML from scratch.

**Acceptance Criteria:**

**Given** the Story 5.1 Regular Listener at `src/AgentEval/telemetry/listener.py`,
**When** I extend the listener class with an `xunit_file(self, path: pathlib.Path)` method,
**Then** the method fires after RF writes the xunit file (empirically verified — listener-via-`--listener` receives this hook); the method reads the xunit XML, looks up per-testcase agent metadata from the per-test trace store (Story 1b.2), injects `<properties>` + `<system-out>` + `<system-err>` per testcase, and writes the file back.

**And Given** the enrichment shape documented at `docs/contracts/junit-xml-enrichment.md` (authored as part of Story 8a.1),
**When** a testcase completes with agent telemetry (e.g., Send Prompt with cost $0.0247 + mcp_coverage=hosted_in_process + trace_id=01HRMK...),
**Then** the enriched xunit `<testcase>` contains:

```xml
<testcase classname="Suite" name="Test Name" time="12.4">
    <properties>
        <property name="agenteval.cost_usd" value="0.0247" />
        <property name="agenteval.total_tokens" value="3421" />
        <property name="agenteval.latency_p95_ms" value="2800" />
        <property name="agenteval.mcp_coverage" value="hosted_in_process" />
        <property name="agenteval.completeness" value="full" />
        <property name="agenteval.trace_id" value="01HRMK..." />
        <property name="agenteval.adapter" value="generic" />
        <property name="agenteval.model" value="anthropic/claude-sonnet-4-6" />
        <property name="agenteval.tier" value="3" />
    </properties>
    <system-out><![CDATA[ [Evidence Block per AC-SIMPLICITY-01 / Story 5.3] ]]></system-out>
    <system-err><![CDATA[ [DegradedTraceWarning content if any per Story 5.4] ]]></system-err>
</testcase>
```

**And Given** the property naming contract at `docs/contracts/junit-xml-enrichment.md`,
**When** the doc is published,
**Then** it specifies: namespace (`agenteval.*` prefix), required vs optional properties, type conventions (all `value` attributes are strings; numeric properties documented with parse semantics), backward-compat policy (new properties are additive; existing property semantics are stable per FR64 Stability Surface).

**And Given** the FR50 exit-code mapping (error_code from `AgentEvalError` hierarchy → process exit code),
**When** a test suite fails with specific error types,
**Then** the process exit code reflects the highest-severity error (`PollingDisallowedError` → 65, `CostExceededError` → 66, `IncompleteTraceError` → 67, `UnsupportedMCPVersionError` → 68, etc. per ADR-A3); the exit-code mapping table lives in `docs/contracts/error-class-hierarchy.md`.

**And** the consumer-facing requirement is documented loud-and-clear: the user MUST pass `--listener AgentEval.telemetry.listener` for both span capture AND xunit enrichment to function. `agenteval init` (Story 8b.1) generates a README + first example that shows the required flag (e.g., `robot --listener AgentEval.telemetry.listener --xunit junit.xml tests/`).

**And** unit tests in `tests/unit/telemetry/test_xunit_enrichment.py` cover: enrichment of a fixture xunit file with synthetic per-test data, `<properties>` injection, `<system-out>` + `<system-err>` injection, idempotency (re-running enrichment on an already-enriched file is safe), schema compliance (the enriched file still validates as JUnit XML per major CI tool parsers — verified by parsing with `pytest-junitxml` + a GitLab-test-reports compatible parser).

**And** integration tests in `tests/integration/ci/test_xunit_end_to_end.py` run a full `.robot` suite via `robot --listener AgentEval.telemetry.listener --xunit junit.xml tests/`, then assert the resulting xunit file contains the agent properties for each test that exercised an agent keyword.

---

#### Story 8a.2: trace_id Surfacing in output.xml + Polling-Ban Error Testability + Conformance Report

As **Priya** (CI log spelunking) or **a CI operator**,
I want each test's `trace_id` surfaced as a tag in RF's `output.xml`, the polling-ban error message structured for grep-ability, and a conformance report (JSON + human-readable) so I can route trace evidence and conformance status into downstream tooling,
So that CI logs link to trace data, polling-ban diagnostics are stable for tooling automation, and conformance status is consumable.

**Acceptance Criteria:**

**Given** a test that invokes any agent keyword (via Story 5.1's listener),
**When** the test completes,
**Then** `output.xml` contains the test's `trace_id` as a `<tag>` element on the test (per FR51) — searchable via `xmlstarlet sel -t -v "//test[@name='X']/tag" output.xml` and linkable to the JSONL trace file from Story 5.1 or to an external observability backend.

**And Given** the polling-ban error message from Story 6.3 (`PollingDisallowedError`),
**When** the error fires,
**Then** the message format is testable across releases (FR56) via a regex contract documented at `docs/contracts/error-class-hierarchy.md` (e.g., `r"^PollingDisallowedError: keyword '<name>' is Tier-(2|3); polling not allowed\. Use Stat\.Run N Times instead\."`); a conformance fixture in `tests/conformance/fixtures/fix-polling-ban-error-format.json` asserts the regex matches across all polling-ban error invocation contexts.

**And Given** the conformance harness from Story 1b.5,
**When** I run `robot --listener AgentEval.telemetry.listener --variable conformance_report:json+human tests/`,
**Then** the harness generates per FR57: (a) `<output_dir>/conformance-report.json` (per-fixture pass/fail + oracle evidence) + (b) `<output_dir>/conformance-report.md` (human-readable summary table) — both schemas documented at `docs/contracts/conformance-fixture-format.md`.

**And** integration tests verify trace_id grep-ability, polling-ban regex stability across 5 representative error contexts, and conformance report shape against both JSON schema + Markdown table format.

---

### Epic 8b: First-Run UX + Adapter Authoring + Cohort Heatmap ("5-Minute First-Run" Claim)

#### Story 8b.1: `agenteval init` Scaffolding Command

As a **new library consumer** (any persona),
I want `agenteval init` to scaffold a working project with example `.robot` tests, fixtures, and a config file — including the required `--listener AgentEval.telemetry.listener` flag visibly documented,
So that I can go from `uv add robotframework-agenteval` to a green test run in <5 minutes (NFR-UX-01 target) without discovering the listener requirement the hard way.

**Acceptance Criteria:**

**Given** a fresh project directory,
**When** I run `uvx agenteval init` (or `agenteval init` after install),
**Then** the command creates: (a) `tests/example_skill_validation.robot` (uses Epic 2 keywords), (b) `tests/example_mcp_runtime.robot` (uses Epic 3 keywords against the bundled echo server), (c) `tests/example_agent_run.robot` (uses Epic 4 Send Prompt with Mock provider), (d) `tests/fixtures/` directory with sample skill + MCP config + scenario YAML, (e) `agenteval.yaml` configuration with sensible defaults, (f) a `README.md` snippet showing how to run the tests with the required `--listener AgentEval.telemetry.listener` flag, (g) a top-level `Makefile` (optional, idiomatic) with `make test` target wrapping the full `robot` invocation.

**And Given** the scaffolded project,
**When** I run the documented `robot --listener AgentEval.telemetry.listener --xunit junit.xml tests/` invocation,
**Then** all example tests pass in <5 minutes against the Mock provider (no live API keys needed); a green `output.xml` + RunManifest + conformance report + agent-enriched xunit.xml are produced.

**And** Recipe Gallery #1 (`docs/recipes/01-first-eval-in-five-minutes.md`) is authored based on this init flow and explicitly highlights the `--listener` requirement.

---

#### Story 8b.2: `agenteval new-adapter` Scaffolding + Terminal Run Summary + Cohort Heatmap (ASCII + Dict)

As a **custom adapter author** or **post-run reviewer**,
I want `agenteval new-adapter` to scaffold a new adapter package skeleton + a terminal run summary (FR54) + `CohortHeatmap.as_ascii()` and `.as_dict()` methods for rendering cohort comparison results,
So that authoring custom adapters is friction-free and post-run results land legibly in terminal output (CI logs) or programmatic consumers.

**Acceptance Criteria:**

**Given** a project root,
**When** I run `agenteval new-adapter --name my-adapter --type subprocess`,
**Then** the command scaffolds `my_adapter_package/` with: `pyproject.toml` (declares the entry-points group registration per FR17a), `my_adapter/__init__.py` + `my_adapter/adapter.py` (subclass of `SubprocessAdapter` with abstract methods stubbed + TODOs), `tests/test_my_adapter.py` (with a Mock conformance test).

**And Given** a `.robot` suite running with Epic 4 keywords + the Story 5.1 listener,
**When** the suite completes,
**Then** stdout displays a terminal run summary per FR54: total tests + pass/fail count + total cost USD + p95 latency + warnings count + the 3 most-fired error types — formatted as a single visual block legible in CI logs (also reproduced in the enriched xunit suite-level `<properties>`).

**And Given** a `DiscoverabilityResult` (or list of them across models) from Story 4.4,
**When** I call `${heatmap}=    Get Cohort Heatmap    ${result}` and then `${ascii}=    ${heatmap.as_ascii()}`,
**Then** the variable receives an ASCII-formatted cohort table (rows=tasks, columns=models, cells=Pass@k); calling `${dict}=    ${heatmap.as_dict()}` returns a structured dict for programmatic consumers (HTML rendering deferred to Phase 2 Epic 13).

**And** unit tests verify the new-adapter scaffold produces a working package; terminal summary format conforms to a visual contract; ASCII heatmap format is stable across releases.

---

#### Story 8b.3: 8 Recipe Gallery Entries + OTel Trace Visual Doc

As **any persona** (Priya, Devon, Mei, Raj),
I want 8 recipe gallery entries documenting the headline user journeys + the OTel trace visualization document per FR58,
So that I have copy-pasteable patterns for the most common workflows and can visualize trace data in a familiar viewer.

**Acceptance Criteria:**

**Given** the keywords + patterns from Epics 2-7,
**When** I author `docs/recipes/{01-08}-*.md`,
**Then** 8 recipes land covering: (1) First eval in 5 min (Story 8b.1 init flow + `--listener` requirement), (2) Pass@k over polling (Stat primitives — Priya), (3) Tool Discoverability cohort (Mei — uses MVP from Story 4.4 + cohort heatmap from 8b.2), (4) Skill author stacked validation (Devon — from Story 7.2 stub), (5) Dogfood replacing custom tests (Raj — pattern from Epics 3+5+6 dogfood stories), (6) Custom Protocol adapter (from Story 8b.2 new-adapter flow), (7) First MCP server test Tier-1 (from Story 2.3 MCP static), (8) CI integration with enriched xunit + JUnit XML + exit codes (from Stories 8a.1 + 8a.2 — explicitly shows the `agenteval.*` property namespace in a real CI tool screenshot).

**And Given** the OTel trace visualization doc per FR58,
**When** I author `docs/contracts/otel-trace-visual.md`,
**Then** the doc describes how to load JSONL trace files into Jaeger / Honeycomb / Tempo for visualization, with screenshots/diagrams showing the `invoke_agent → chat → execute_tool` hierarchy and `gen_ai.*` attribute display.

**And** all 8 recipes pass as executable examples (each recipe's code block is extracted by CI + run as a smoke test).

---

### Epic 9: Dogfood Loop Consolidation + Phase 1 Close

#### Story 9.1: Verify rf-mcp Full Parity + Cross-Repo CI Workflow Stays Green

As a **Phase 1 close validator**,
I want verification that interleaved dogfood from Epics 3 (MCP surface), 5 (trace assertions), and 6 (metrics) covers `rf-mcp`'s full custom-test surface — no gaps, no remaining custom Python tests to port,
So that `rf-mcp` runs entirely on `agenteval`-based `.robot` suites + cross-repo CI workflow blocks any agenteval regression that breaks `rf-mcp`.

**Acceptance Criteria:**

**Given** the three parity checklists from Stories 3.3, 5.5, 6.4,
**When** I review remaining custom Python tests in `rf-mcp`,
**Then** every custom test has either a `.robot` equivalent OR a documented rationale for staying custom (e.g., infrastructure tests not in agenteval scope); the gap list is empty or has explicit rationale per entry.

**And Given** the `dogfood-integration.yml` workflow,
**When** I monitor the workflow over 7 consecutive days of agenteval PRs,
**Then** the workflow successfully gates `rf-mcp` regression: ≥1 PR was blocked by a regression caught in the dogfood suite (deliberate test if needed — introduce a temporary regression in a side PR to verify the gate works).

**And** Recipe Gallery #5 (Dogfood replacing custom tests) is updated with the `rf-mcp` story as a worked example.

---

#### Story 9.2: Verify robotframework-agentskills Full Parity

As a **Phase 1 close validator**,
I want `robotframework-agentskills` similarly verified to `rf-mcp` — full custom-test surface ported to `.robot` suites using Epic 6 metric keywords + Epic 7 Skill activation flow,
So that AC-DOGFOOD-01 is satisfied for both dogfood targets, not just one.

**Acceptance Criteria:**

**Given** Story 6.4's parity checklist for agentskills metrics + Story 7.1's `Skill.Get Activation Decision` keyword,
**When** I review remaining custom tests in `robotframework-agentskills`,
**Then** every custom test has a `.robot` equivalent or documented exception; the cross-repo CI workflow blocks regressions.

**And** Devon's full Journey 4 Phase 1 portion is exercised in robotframework-agentskills — proving Tier-1 + Tier-3 stacked validation works against real skills (not just fixtures).

---

#### Story 9.3: Phase 1 Retrospective + FR65 Exit Criteria Doc Final Content

As a **Phase 1 close stakeholder** (all personas + contributor),
I want a Phase 1 retrospective document + the `docs/contracts/exit-criteria.md` doc fully populated (no longer TBD) per FR65,
So that the 0.x→1.0 promotion criteria are concrete + Phase 1 learnings inform Phase 2 planning + the project has an honest scorecard for the 10-12 week effort.

**Acceptance Criteria:**

**Given** Phase 1 completion (Epics 0 through 8b shipped + dogfood verified),
**When** I author `docs/contracts/exit-criteria.md` per FR65,
**Then** the doc lists the 0.x→1.0 promotion criteria: (a) conformance suite coverage threshold (e.g., ≥90% of keywords have fidelity oracles), (b) dogfood parity bar maintained (both downstream repos green for ≥3 consecutive months), (c) all ADRs ratified to `accepted` status, (d) public API stability period (≥3 months without breaking changes), (e) ≥3 external contributors with merged PRs, (f) ≥1 documented use case beyond rf-mcp + agentskills.

**And** a retrospective at `_bmad-output/planning-artifacts/phase-1-retrospective-<date>.md` covers: what shipped vs planned, calendar reality vs 10-12 week estimate, top 3 successes, top 3 surprises, what would change for Phase 2, hidden labor that emerged, dogfood findings logged.

**And** Phase 1 success criteria status is reported: which ACs satisfied (all 9 expected per epic mapping), which NFRs validated, any open issues flagged.

---

### Epic 10 [Phase 2]: Native Agent SDK Adapters

#### Story 10.1: Claude Agent SDK Adapter

As **Raj (Agent Developer)** working with the Anthropic ecosystem,
I want a `ClaudeAgentSDKAdapter(InProcessAdapter)` using Anthropic's official Agent SDK,
So that I can run Anthropic agent workflows with native SDK semantics (system prompts, tools, multi-turn) without falling back to Generic adapter limitations.

**Acceptance Criteria:**

**Given** the `InProcessAdapter` ABC from Story 1b.4 + the `anthropic` Python SDK installed via `[claude-sdk]` extra,
**When** I implement `src/AgentEval/coding_agent/claude_agent_sdk.py`,
**Then** the adapter implements `_invoke_llm()` via `anthropic.AsyncAnthropic().messages.create()` (sync-wrapped via `_run_async`), supports MCP server integration via Anthropic's native MCP client support, populates `AgentRunResult` with proper `mcp_coverage="hosted_in_process"` (Anthropic SDK exposes the hosted MCP path).

**And** the adapter is registered as `"claude-agent-sdk"` via entry-points; declared as `[claude-sdk]` optional extra in `pyproject.toml`.

**And** unit tests cover SDK conformance + integration tests against a recorded SDK response fixture (no live API key required).

---

#### Story 10.2: OpenAI Agents SDK Adapter

As **Raj (Agent Developer)** working with the OpenAI ecosystem,
I want an `OpenAIAgentsSDKAdapter(InProcessAdapter)` using OpenAI's Agents SDK,
So that I can run OpenAI agent workflows with native SDK semantics.

**Acceptance Criteria:**

**Given** the `InProcessAdapter` ABC + the `openai` Python SDK installed via `[openai-agents]` extra,
**When** I implement `src/AgentEval/coding_agent/openai_agents.py`,
**Then** the adapter implements `_invoke_llm()` via OpenAI's Agents SDK with tool use + multi-turn support, MCP integration via OpenAI's MCP support, normalized `AgentRunResult`.

**And** registered as `"openai-agents-sdk"`; declared as `[openai-agents]` extra.

**And** unit + integration tests against recorded SDK fixtures.

---

### Epic 11 [Phase 2]: CLI Adapters + AdapterVersionDriftWarning

#### Story 11.1: Codex CLI Adapter

As **Raj (Agent Developer)**,
I want a `CodexCLIAdapter(SubprocessAdapter)` invoking the `codex` CLI binary,
So that I can run OpenAI Codex CLI agent workflows under the same `CodingAgentAdapter` Protocol.

**Acceptance Criteria:**

**Given** the `SubprocessAdapter` ABC + the `codex` binary on `$PATH` (version pinned via FR47 binary check),
**When** I implement `src/AgentEval/coding_agent/codex_cli.py`,
**Then** the adapter constructs proper CLI commands per Codex's output format, parses CLI output into `AgentRunResult`, supports MCP server attachment per Codex's MCP integration model.

**And** registered as `"codex-cli"`; declared as `[codex]` extra; binary version check raises `UnsupportedBinaryVersionError` if out of compat range.

**And** unit tests use recorded Codex output fixtures.

---

#### Story 11.2: Copilot CLI Adapter

As **Raj (Agent Developer)** or **a GitHub-ecosystem user**,
I want a `CopilotCLIAdapter(SubprocessAdapter)` invoking the `copilot` binary with proper events.jsonl post-hoc parsing (verified empirically in agenteval research phase as a viable Tier-1 adapter target),
So that I can run GitHub Copilot CLI agent workflows under the unified adapter Protocol.

**Acceptance Criteria:**

**Given** the `SubprocessAdapter` ABC + `copilot` binary v1.0.9+ on `$PATH`,
**When** I implement `src/AgentEval/coding_agent/copilot_cli.py`,
**Then** the adapter invokes copilot in autopilot mode, parses `~/.copilot/session-state/{uuid}/events.jsonl` for trace data, populates `AgentRunResult` including tool calls + cost.

**And** registered as `"copilot-cli"`; declared as `[copilot]` extra.

**And** unit tests use recorded events.jsonl fixtures.

---

#### Story 11.3: AdapterVersionDriftWarning Fully Wired

As **Raj (Agent Developer)** or **a CI operator**,
I want `AdapterVersionDriftWarning` per FR60 to fire one-time when an adapter detects its bundled CLI binary is N versions behind the latest-tested version (within compat range but at risk of conformance fidelity degradation),
So that conformance drift between adapter version and CLI version surfaces before tests start producing misleading results.

**Acceptance Criteria:**

**Given** any of the 3 Tier-1 CLI adapters (CC CLI from Epic 4, Codex from 11.1, Copilot from 11.2),
**When** the adapter is instantiated and the detected CLI version is within the pinned compat range BUT more than 2 minor versions behind the adapter's "tested-up-to" version,
**Then** `AdapterVersionDriftWarning` is logged via the listener warning channel per FR60 with: (a) detected version, (b) tested-up-to version, (c) drift severity, (d) recommendation ("upgrade adapter to test the latest CLI, or pin CLI to tested version").

**And** the warning fires ONCE per test session (not per adapter instantiation) — tracked via session-scoped state.

---

### Epic 12 [Phase 2]: LLM-Judge + Rubric Calibration

#### Story 12.1: Judge.Get Score Keyword + Basic Rubric Support

As **Devon (Agent Surface Author)** or **Raj (Agent Developer)**,
I want a `Judge.Get Score` keyword that evaluates an agent response (or pair of responses) against a written rubric using an LLM judge,
So that I can apply Tier-2 LLM-deterministic scoring to agent outputs — closing Devon's Tier-2 slot in his three-tier stacked validation flow.

**Acceptance Criteria:**

**Given** an `AgentRunResult` + a rubric document at `tests/fixtures/rubrics/skill-quality.md`,
**When** I call `${score}=    Judge.Get Score    result=${result}    rubric=tests/fixtures/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6` in a `.robot` test,
**Then** the variable receives a `JudgeScore` dataclass with: `numeric_score` (0-10), `pass_threshold_met` (bool — compared against rubric's stated threshold), `reasoning` (str), `criteria_breakdown` (dict mapping rubric criterion → per-criterion score), `cost_usd`.

**And** the keyword is `@tier(2)` (LLM-deterministic — judge model behavior is reproducible with seed + temperature=0); `@guarded_fanout` cost guardrails inherited.

**And** unit tests use Mock provider for deterministic rubric scoring verification.

---

#### Story 12.2: Judge Calibration Suite + Agreement Scoring + Threshold Tuning

As an **agent surface author** (Devon) calibrating Judge scores against human labels,
I want a `Judge.Calibrate` workflow that runs the judge against a curated calibration set with human-labeled ground truth, computes Cohen's kappa or similar agreement metric, surfaces threshold-tuning recommendations,
So that judge scores are trustworthy across runs — calibrated to a known agreement baseline rather than vibes-based.

**Acceptance Criteria:**

**Given** a calibration set at `tests/fixtures/calibration/skill-quality-calibration.yaml` (50 examples with human-assigned scores 0-10),
**When** I run `Judge.Calibrate    rubric=tests/fixtures/rubrics/skill-quality.md    calibration_set=tests/fixtures/calibration/skill-quality-calibration.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6`,
**Then** the keyword runs the judge against all 50 calibration examples, computes Cohen's kappa between judge scores + human labels, surfaces threshold-tuning chart (which threshold maximizes precision/recall against pass label), returns a `CalibrationReport` dataclass.

**And** the calibration report identifies systematic biases (e.g., "judge consistently scores 1 point higher than humans on examples in category X").

**And** integration tests verify calibration math against synthetic perfect-agreement + perfect-disagreement fixtures.

---

#### Story 12.3: Three-Tier Stacked Validation Integration (Completes Devon's Journey 4)

As **Devon (Agent Surface Author)**,
I want Recipe Gallery #4 updated to plug in `Judge.Get Score` as the Tier-2 layer between Story 2.1's Tier-1 static validation and Story 7.2's Tier-3 cohort Discoverability — completing the full three-tier flow,
So that Devon's Journey 4 from PRD is end-to-end exercisable.

**Acceptance Criteria:**

**Given** the recipe stub from Story 7.3 (Recipe Gallery #4 with `# TODO Phase 2: Judge.Get Score here`),
**When** I populate the Tier-2 slot with `Judge.Get Score`,
**Then** the recipe shows all 3 tiers stacked: Tier-1 frontmatter validation + Tier-2 judge scoring of agent responses + Tier-3 cohort Discoverability + Pass@k activation reliability.

**And** an integration test at `tests/integration/skills/test_devon_three_tier_complete.py` exercises all 3 tiers end-to-end against a real skill fixture with the Mock judge provider; the test asserts a coherent pass/fail across all 3 tiers.

**And** Devon's Journey 4 documentation marks the full flow as available from Phase 2 release onwards.

---

### Epic 13 [Phase 2]: Advanced Stats + OTLP + Cross-Adapter Discoverability + HTML

#### Story 13.1: Advanced Statistical Primitives Behind `[agenteval-advanced]` Extra

As **Raj (Agent Developer)** doing multi-model comparison,
I want `Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap CI` keywords behind the `[agenteval-advanced]` optional extra,
So that I can statistically compare two non-deterministic agent flows with proper effect-size + significance metrics.

**Acceptance Criteria:**

**Given** two `Stat.Run N Times` result lists,
**When** I call `${u}=    Stat.Mann Whitney U    ${results_a}    ${results_b}    predicate=lambda r: r.cost_usd`,
**Then** the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `n_a`, `n_b`; analogous for `Cliff Delta` (effect size) and `Bootstrap CI` (confidence interval on any predicate).

**And** all advanced stats keywords are behind `[agenteval-advanced]` extra (requires `scipy + numpy`); ImportError on import without the extra has a clear message recommending `uv pip install robotframework-agenteval[agenteval-advanced]`.

**And** unit tests verify math against scipy reference implementations.

---

#### Story 13.2: OTLP Trace Backend

As an **observability-focused user** (Raj or Priya integrating with production observability stacks),
I want `trace_backend="otlp"` shipping JSONL spans to an OTLP collector,
So that AgentEval traces flow into Jaeger / Honeycomb / Tempo / Grafana for production observability.

**Acceptance Criteria:**

**Given** `trace_backend="otlp"` + `otlp_endpoint="http://localhost:4318/v1/traces"` configuration,
**When** spans are emitted during a test,
**Then** they are exported via OTLP HTTP protocol to the configured endpoint; integration test verifies round-trip against a local OTLP collector docker container.

**And** OTLP backend supports both gRPC (`otlp_endpoint="grpc://..."`) and HTTP (`otlp_endpoint="http://..."`) per OTel SDK conventions.

**And** Recipe Gallery #8 (CI integration) is updated with an OTLP integration example showing trace data flowing into a Honeycomb/Jaeger dashboard.

---

#### Story 13.3: Compare Tool Discoverability Cross-Adapter

As **Mei (Agent Surface Author)** doing cross-runtime MCP analysis,
I want `MCP.Compare Tool Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per FR10b,
So that I can claim "tool X is discoverable by Claude AND GPT AND Copilot" with empirical evidence — the killer Mei feature deferred from Phase 1.

**Acceptance Criteria:**

**Given** the MVP Discoverability from Story 4.4 + the SDK adapters from Epic 10 + CLI adapters from Epic 11 (≥2 Tier-1 adapters fully shipped per ADR-A4 prerequisite),
**When** I call `${comparison}=    MCP.Compare Tool Discoverability    mcp_server=rf-mcp    tasks=...    adapters=[generic, claude-agent-sdk, openai-agents-sdk]    trials_per_task=5    max_cost_usd=20.00`,
**Then** the variable receives a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data.

**And** integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero).

---

#### Story 13.4: Cohort Heatmap HTML Rendering

As a **post-run reviewer** sharing results outside the terminal,
I want `CohortHeatmap.as_html()` rendering the same cohort data as a standalone HTML file with embedded CSS,
So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables.

**Acceptance Criteria:**

**Given** a `CohortHeatmap` from Story 4.4 (MVP single-runtime), Story 13.3 (cross-adapter Tool Discoverability), or Story 13.5 (cross-adapter Skill Discoverability),
**When** I call `${html}=    ${heatmap.as_html()}`,
**Then** the variable receives a standalone HTML string with embedded CSS rendering the heatmap as a color-coded table (Pass@k → color gradient); file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file.

**And** unit tests verify HTML validity (parseable by html.parser) + visual regression test against a recorded baseline image.

---

#### Story 13.5: Compare Skill Discoverability Cross-Adapter (FR4c)

As **Devon (Agent Surface Author)** doing cross-runtime skill activation analysis,
I want `Skill.Compare Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per FR4c,
So that I can claim "skill X is reliably activated by Claude AND GPT AND Copilot" with empirical evidence — symmetric to Mei's cross-adapter Tool Discoverability (Story 13.3), the killer Devon Phase 2 feature.

**Acceptance Criteria:**

**Given** the Story 7.2 cohort Skill Discoverability + the SDK adapters from Epic 10 + CLI adapters from Epic 11 (≥2 Tier-1 adapters fully shipped),
**When** I call `${comparison}=    Skill.Compare Discoverability    skill=tests/fixtures/skills/example-search.md    tasks=tests/fixtures/discoverability/skill-tasks-basic.yaml    adapters=[generic, claude-agent-sdk, openai-agents-sdk]    trials_per_task=5    max_cost_usd=20.00`,
**Then** the variable receives a `SkillDiscoverabilityComparisonResult` with per-adapter task-level activation results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data + per-adapter false-activation/missed-activation rate comparison.

**And** integration test verifies the comparison runs cleanly across all configured adapters using the Mock provider (zero real-API cost during CI).

**And** the keyword inherits `@guarded_fanout` cost/runtime guardrails identically to Story 13.3 (no duplicate logic; cross-adapter cohort math is the same shape).

**And** Recipe Gallery #4 is updated (during this story or Story 12.3 — whichever lands later) with a Phase 2 cross-adapter Skill Discoverability example.

**And** dogfood: `robotframework-agentskills` cross-adapter Skill Discoverability suite is added to that repo's CI matrix using the Mock provider (real-API cross-adapter runs are out of routine CI scope due to cost; a separate `weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a budget).
