# Changelog

All notable changes to **robotframework-agenteval** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(per NFR-MAINT-03).

Story-level provenance: every Story X.Y bullet below has a companion spec at
`_bmad-output/implementation-artifacts/X-Y-*.md` containing AC text, dev
notes, completion notes, and (when applicable) Senior Developer Review
(AI) cross-LLM review records.

---

## [Unreleased]

### Phase 2 — launched 2026-05-25

#### Epic 10 — Native Agent SDK Adapters (FR13c + FR13d)

- **Story 10.1 — `ClaudeAgentSDKAdapter(InProcessAdapter)`** at `src/AgentEval/coding_agent/claude_agent_sdk.py`. Wraps Anthropic's `claude-agent-sdk` PyPI package (distinct from the LLM-only `anthropic` client) under the new `[claude-sdk]` optional extra. Entry-point `claude-agent-sdk = "AgentEval.coding_agent.claude_agent_sdk:ClaudeAgentSDKAdapter"`. Lazy-imports the SDK in `__init__`; clear ImportError if extra not installed. Drives `query(prompt, options)` via `anyio.run()` for sync wrapping. Sync surfaces: `model`, `max_turns`, `system_prompt` constructor kwargs. **Cross-LLM-reviewed** (Claude CLI v0.3.0 — 6 findings applied incl. empirical SDK probe revealing `ResultMessage.usage` is `dict`-shaped; kilo/minimax v0.4.0 — 16 `ADR-A6 L384` citation drift corrected to `ADR-016 L59`). Carry-overs C67 (multi-turn + tool use/result pairing) + C68 (HostedMcpObserver wiring).

- **Story 10.2 — `OpenAIAgentsSDKAdapter(InProcessAdapter)`** at `src/AgentEval/coding_agent/openai_agents.py`. Wraps OpenAI's `openai-agents` PyPI package (import path: `from agents import Agent, Runner`, distinct from the bare `openai` LLM client) under `[openai-agents]` extra. Entry-point `openai-agents-sdk = "AgentEval.coding_agent.openai_agents:OpenAIAgentsSDKAdapter"`. Uses `Runner.run_sync(agent, prompt)` (sync API). **3-stage cross-LLM review** (Claude CLI + Codex CLI both empty → empirical SDK probe caught real `RunResult.context_wrapper.usage` canonical path → kilo/minimax delivered 5 substantive findings, 3 MED patches applied). 15 unit tests + 1 env-gated integration test. Carry-overs C69 (MCP attachment empirical verification) + C70 (cost/usage shape verification — `_extract_cost` returns `0.0` until priced lookup wired).

### Phase 1 — closed 2026-05-25 (Story 9.3 retro + FR65 exit criteria ratification)

#### Epic 9 — Dogfood Loop Consolidation + Phase-1 Close

- **Story 9.1 — Verify rf-mcp Full Parity + Cross-Repo CI Workflow Stays Green**. Gap-analysis synthesis at `tests/dogfood/rf-mcp/parity-checklist-rf-mcp-FULL.md` classifies 58 rf-mcp tests (17 ported / 4 stays-custom / 38 Phase-2-batch). `.github/workflows/dogfood-integration.yml::parity-suite-smoke` job added (workflow_dispatch + release + release-pending PR-label trigger after kilo/minimax review HIGH-2 patch). DF-9.1-S1 / C65 catalogued (downstream rf-mcp adoption + 7-day monitoring deferred to Phase-2).

- **Story 9.2 — Verify robotframework-agentskills Full Parity**. Phase-1 surface 100% covered (metrics + assertions + stats from Story 6.4 + 3-of-11-skills discoverability from Story 7.4). 8 remaining skills + live-provider activation-quality at C60. `.github/workflows/dogfood-integration.yml::agentskills-parity-suite-smoke` job added. DF-9.2-S1 / C66 catalogued (downstream agentskills adoption + 7-day monitoring deferred to Phase-2).

- **Story 9.3 — Phase 1 Retrospective + FR65 Exit Criteria Doc Final Content**. Phase-1 retrospective authored at `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md` covering all 11 epic slots + top 3 successes + top 3 surprises + 13+ dogfood findings catalogued. `docs/contracts/exit-criteria-0x-to-1x.md` rewritten from Phase-1 stub to `accepted` with 6 ratified promotion criteria (conformance coverage ≥90%, dogfood parity ≥3-month sustained, ADR completeness, public API stability ≥3-month-no-break, ≥3 external contributors, ≥1 use case beyond rf-mcp + agentskills). Phase-1 close: 0 of 6 criteria fully satisfied at close per honest-framing convention (4 ⚠ shipped + 2 ❌ Phase-2).

#### Epic 8b — CLI Scaffolding + Terminal Run Summary + Recipe Gallery

- **Story 8b.1 — `agenteval init` Scaffolding Command**. New CLI subcommand at `src/AgentEval/cli.py` + scaffold logic at `src/AgentEval/_init/scaffold.py`. Generates 8 scaffolded files: 3 `.robot` example tests (skill validation + MCP runtime + agent run) + 3 fixtures (`example-skill.md`, `mcp.json`, `scenario.yaml`) + `agenteval.yaml` config + `README.md`. Per AC-8b.1.1 the scaffolded project satisfies the NFR-UX-01 5-minute setup time. Recipe #1 (`docs/recipes/01-first-eval-in-five-minutes.md`) is the canonical worked example.

- **Story 8b.2 — `agenteval new-adapter` Scaffolding + Terminal Run Summary + Cohort Heatmap**. New CLI subcommand `agenteval new-adapter <name>` at `src/AgentEval/_new_adapter/scaffold.py` — generates `SubprocessAdapter` / `InProcessAdapter` template skeletons + companion conformance test. FR54 terminal run summary at `src/AgentEval/telemetry/_terminal_summary.py` (env-var-gated via `AGENTEVAL_TERMINAL_SUMMARY=1`); pass/fail counts deferred to C71 (`DF-8b.2-S1`) — display shows `"—"` sentinel per kilo/minimax review HIGH-2 honest-framing patch. `CohortHeatmap` ASCII + dict renderer at `src/AgentEval/_heatmap/models.py` (FR55) with missing-cell `" — "` sentinel per kilo/minimax review HIGH-1 patch.

- **Story 8b.3 — 8 Recipe Gallery Entries + OTel Trace Visual Doc**. 8 recipes at `docs/recipes/01-…` through `docs/recipes/08-ci-integration.md` covering Devon (skill author) + Raj (library maintainer) + Many (CI integrator) personas. New `docs/contracts/otel-trace-visual.md` documenting the OTel GenAI semantic conventions + `agenteval.*` namespace surfacing in `output.xml`. Recipe #5 `feedback_executable_doc_precheck` (Epic 7 retro NEW norm) ratified after broken `keyword_args` + `${lambda}` syntax caught by Blind+Codex review. C64 (recipe CI extraction) catalogued for Phase-1.5.

#### Epic 8a — JUnit XML Enrichment + Structured Exit Codes + Conformance Report

- **Story 8a.1 — Enrich RF `--xunit` Output Via Listener v3 `xunit_file` Hook + Structured Exit Codes**. Listener v3 `xunit_file(path)` hook at `src/AgentEval/telemetry/_xunit_enrichment.py` — atomic-write enrichment idempotent on re-enrichment. 9 ratified `agenteval.*` JUnit XML properties per `docs/contracts/junit-xml-enrichment.md`. Sysexits-style 21-leaf exit-code mapping (`_ERROR_EXIT_CODES` dict at `src/AgentEval/cli.py:56`) per FR50 ratified at `docs/contracts/error-class-hierarchy.md` L66-L101. **Cross-LLM-reviewed** (Claude CLI v1 caught 3 HIGH including v1 HIGH-1 `cost_usd` key mismatch — real adapters use `total_cost_usd` not `cost_usd`; v1 HIGH-2 `SANDBOX_POLICY_VIOLATION` → `VALIDATE_OPERATOR_DISALLOWED` rename in `_ERROR_EXIT_CODES`; v1 HIGH-3 missing leaves in exit-code map fixed by amending `error-class-hierarchy.md` from "19 leaves" to "21 leaves" per fix-the-losing-source-NOW pattern). C62 (per-leaf `exit_code: ClassVar[int]` attribute) catalogued for Phase-1.5.

- **Story 8a.2 — trace_id Surfacing in output.xml + Polling-Ban Error Testability + Conformance Report**. `start_test()` extended at `src/AgentEval/telemetry/listener.py` with `result.tags.add(f"trace_id:{test_id}")` — empirical verification caught D-5 `data.tags.add()` no-op (only `result.tags` surfaces in `output.xml`; `feedback_listener_hook_api_surface_empirical_check` Epic 8 retro NEW norm ratified). FR56 polling-ban regex contract at `docs/contracts/error-class-hierarchy.md`; conformance verification artifact at `tests/conformance/fixtures/_fr56_polling_ban_regex_contract.json` (renamed from `fix-polling-ban-error-format.json` 2026-05-26 per kilo/minimax review HIGH-1 — was not a valid `ConformanceFixture`). FR57 conformance report standalone CLI `python -m AgentEval.conformance --adapter <name>` emits JSON + Markdown reports; sysexits-mapped exit codes. D-6 empirical caught broken canonical `--listener AgentEval.telemetry.listener` invocation (module-path-only accepted by RF 7.x but `Listener` class hooks do NOT fire); requires explicit `Module.Class` path — propagated to 3 contract docs + 7 scaffolds via `feedback_contract_doc_invocation_smoke_test` Epic 8 retro NEW norm.

#### Epic 7 — Skill Author Validation + Skill Discoverability

- **Story 7.1 — Skill.Get Activation Decision Keyword**. Tier-2 keyword at `src/AgentEval/skills/library.py::SkillsLibrary.get_activation_decision`. `ActivationDecision` dataclass (skill_name, activated, response_text, cost_usd, latency_ms). 10 unit tests + N=1 evidence for `feedback_nullish_input_fuzz_checklist` (CONDITIONAL norm — `bool('None') == True` null-name bug caught + fixed; sunset path = re-ratify if Epic 8 produces a second case).

- **Story 7.2 — Skill.Get Discoverability Cohort Keyword + Skill Should Activate For Assertion**. Tier-3 fan-out keyword at `SkillsLibrary.get_discoverability` — runs N trials × M tasks against a skill, returns per-task activation rates + aggregate summary (`activation_accuracy`, `false_activation_rate`). Companion Tier-2 assertion `SkillsLibrary.should_activate_for`. `@guarded_fanout()` cost+runtime guardrails inherited from ADR-015.

- **Story 7.3 — Devon's Stacked Validation Recipe + Integration Test**. Recipe #4 (`docs/recipes/04-skill-author-stacked-validation.md`) — stacked Tier-1 frontmatter → Tier-2 activation → Tier-3 Pass@k discoverability validation flow. Integration test at `tests/integration/recipes/test_skill_author_stacked_validation.robot` exercises the full stack with the Mock adapter.

- **Story 7.4 — Interleaved Dogfood — Skill Discoverability Against robotframework-agentskills**. `tests/dogfood/agentskills/test_skill_discoverability.robot` (4 tests; rf-browser-skill + 2 parallel-derived skills). DF-7.4-S1 / C60 (8 remaining skills + live-provider activation quality) catalogued for Phase-2. **VALIDATION-CEILING line** ratified per `feedback_dogfood_validation_ceiling` Epic 7 retro NEW norm — stub-adapter `false_activation_rate=1.0`-by-design framed explicitly.

#### Epic 6 — Tool-Call Metrics + Trajectory + Stats + ADR-019 Assertion Engine

- **Story 6.1 — Tool-Call Metrics Library**. Tier-1 keywords at `src/AgentEval/metrics/library.py`: `Get Tool Hit Rate` (|expected ∩ observed| / |expected|), `Get Tool Success Rate` (non-error / total), `Get Unnecessary Call Rate` (not_in_expected / total), `Get Tool Call Count`, `Get Tool Call Names`, `Get Tool Calls`, `Get Token Usage`, `Get Cost Total`, `Get Latency`, `Get Latency P95`. Returns project's `ToolCallTrace` shape per Story 1b.2.

- **Story 6.2 — Trajectory + Tool Call + Response Assertions**. Tier-1 keywords at `src/AgentEval/_assertions/library.py`: `Tool Call Should Have Occurred` (name + args), `Trajectory Should Match` (exact / subsequence / set), `Agent Response Should Contain`, `Agent Response Should Match Regex`, `Agent Response Should Match Schema` (jsonschema). ADR-019 assertion-engine adoption ratified at `docs/adr/ADR-019-assertion-engine-adoption.md` — polling-mode keywords explicitly prohibited per FR56.

- **Story 6.3 — Statistical Primitives + Tier ACL + Determinism Enforcement**. Tier-3 fan-out keyword `Stat.Run N Times` at `src/AgentEval/stats/library.py` (independent N-trial execution). Tier-1 helpers: `Stat.Get Pass At K` (HumanEval Pass@k unbiased estimator), `Stat.Get Pass At K Confidence Interval` (Wilson score CI), `Stat.Assert Run Determinism` (bit-identical Tier-1 output assertion). **PRD FR30b Tier-1 LLM-invocation ban** enforced at `src/AgentEval/_kernel/tier_acl.py::enforce_tier1_no_llm` — wired at adapter `run()` entry to prevent Tier-1 keywords from transitively invoking LLMs. `feedback_test_name_assertion_match` Epic 3 retro norm ratified (2 fake-green patterns caught in this story's review).

- **Story 6.4 — Interleaved Dogfood — Port robotframework-agentskills Metrics Tests**. `tests/dogfood/agentskills/test_*.robot` (36 tests; reframed parallel-derived after D-2 decision — agentskills uses internally-scored `AgentRunResult` fixtures rather than live LLM scoring). DOGFOOD-FINDING-1 (`stats/_internal.py:250` `_default_pass_predicate` flipped from `"full"` to `"complete"` per `AgentRunMetadata._VALID_COMPLETENESS` literal set). C55 (SkillsLibrary budget propagation) catalogued.

#### Epic 5 — OTel Listener + Hosted-MCP Observer + RunManifest + DegradedTraceWarning

- **Story 5.1 — OTel Listener + Span Generation + Memory/JSONL Backends**. RF Listener v3 class at `src/AgentEval/telemetry/listener.py::Listener` — wraps `ROBOT_LISTENER_API_VERSION = 3`. Span generation per FR35 OTel GenAI semconv + `agenteval.*` namespace per `docs/contracts/listener-integration.md`. Two trace backends: in-memory (default, test-friendly) + jsonl (per-test sidecar at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` per FR51). `get_spans()` + `get_run_manifest()` keyword surfaces.

- **Story 5.2 — Hosted-MCP Observer + Honesty Fields + IncompleteTraceError + Adapter mcp_servers Integration**. `HostedMcpObserver` at `src/AgentEval/mcp/observer.py` — wraps `Server.request_handlers` per ADR-004 universal-observation pattern. `mcp_coverage` field on `AgentRunMetadata` per ADR-016 trust-floor semantics. `GenericAdapter.run()` wired to attach observer when `mcp_servers=` non-empty + `transport="in_memory"`. `_kernel/coverage.py::_check_mcp_coverage` enforces `IncompleteTraceError` per FR37 + ADR-016 unless caller opts in via `allow_external_mcp_blind=True`.

- **Story 5.3 — Evidence Block + Redaction Wiring + RunManifest**. `RunManifest` 7+ field dataclass at `src/AgentEval/types.py` per FR39. `RunManifestEmitter` at `src/AgentEval/telemetry/_run_manifest.py` populates `library_version`, `redaction_policy_hash`, `started_at`, `ended_at`, `agenteval_tier_breakdown`, `adapter_name`, `adapter_version`, `model`, `mcp_servers`, `trace_backend`, `total_cost_usd`, `completeness`, `mcp_coverage`, `warnings`, `seed`, `prompt_hashes`. Evidence-block redaction wired at trace-store-write boundary per `docs/contracts/evidence-block-format.md`.

- **Story 5.4 — DegradedTraceWarning + Get Last Warnings + Per-Test Scope Polish**. `DegradedTraceWarning` collector at `src/AgentEval/_kernel/warnings.py` — accumulates 5-key `WarningRecord` (warning_type, message, source, timestamp RFC 3339, remediation) per FR61. `Get Last Warnings` Tier-1 keyword. `mark_external_mixed(reason)` API for adapter-side degradation signaling. Per-test scope wired through Listener context.

- **Story 5.5 — Interleaved Dogfood — Trace Observability Against rf-mcp**. `tests/dogfood/rf-mcp/test_trace_observability_parity.robot` (8 tests). Validates the full Story 5.1+5.2+5.3 trace surface against the rf-mcp downstream MCP server. DF-5.5-DOGFOOD-2 (span helpers shipped Story 5.1, 0 callers, surfaced 5 stories later) → ratified `feedback_caller_count_check` Epic 5 retro NEW norm (grep new public helpers for caller count at story-close; 0 callers = `DF-X-SY` caller-gap entry).

#### Epic 4 — CodingAgentAdapter + Generic LiteLLM + Claude Code CLI + Discoverability MVP

- **Story 4.1 — Provider Layer + Generic Coding-Agent Adapter**. `LLMProviderAdapter` Protocol at `src/AgentEval/providers/base.py` (`chat(model, messages, **kwargs) -> ChatResponse`). `LiteLLMAdapter` concrete impl at `src/AgentEval/providers/litellm_adapter.py`. `MockProvider` test-friendly impl at `src/AgentEval/providers/mock.py`. `GenericAdapter(InProcessAdapter)` at `src/AgentEval/coding_agent/generic.py` — routes through configurable `LLMProviderAdapter`. Provider factory + entry-point discovery per ADR-013.

- **Story 4.2 — Claude Code CLI Adapter**. `ClaudeCodeCLIAdapter(SubprocessAdapter)` at `src/AgentEval/coding_agent/claude_code_cli.py`. FR47 binary version check (pinned `claude>=2.0.0,<3.0.0`). Output parsing per Claude Code CLI's JSONL event stream. Process-group cleanup per Story 1b.1 `MCPLifecycleManager` precedent (start_new_session=True + os.killpg on exception). DF-3.2-S7 `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check` workaround ratified as project default for cross-LLM Codex CLI review.

- **Story 4.3 — Orchestration Keywords + Config Precedence**. `Send Prompt` Tier-2 keyword at `src/AgentEval/orchestration/library.py`. `Run Scenario` (single-call YAML scenarios). `Load Scenario` (validate without exec). `_kernel/context.py` config precedence per FR41 (kwarg > env-var > library default). Story 4.3 retro NEW norm `feedback_carry_over_catalog_gate` UPSTREAM ratified (grep new files for `DF-X-SY` + verify each is in `docs/phase-1-5-carry-overs.md`).

- **Story 4.4 — MVP Tool Discoverability (FR10a) — Single-Runtime Discoverability Check**. `MCP.Get Tool Discoverability` keyword at `src/AgentEval/mcp/library.py::MCPLibrary.get_tool_discoverability`. Runs a single-runtime probe + classifies whether the agent + MCP server combo can discover an expected tool. Tier-2 keyword; uses the configured adapter.

#### Epic 3 — MCP Server Lifecycle + Tool Inspection + rf-mcp Dogfood

- **Story 3.1 — MCP Server Lifecycle Keywords**. Tier-1 keywords at `src/AgentEval/mcp/library.py`: `MCP.Start Server` (build handle; no spawn yet per Story 3.1 Phase-1 per-call-session design), `MCP.Connect To Server` (actual spawn + handshake), `MCP.Stop Server` (cleanup + process-group SIGTERM). `MCPServerHandle` dataclass. `MCPLifecycleManager` at `src/AgentEval/_kernel/mcp_lifecycle.py` enforces per-test scope per ADR-009. FR8 spec version gate raises `UnsupportedMCPSpecVersionError` per ADR-008.

- **Story 3.2 — MCP Tool Inspection Keywords**. Tier-1 keywords: `MCP.List Tools` + `MCP.Call Tool`. `MCPToolResult` dataclass (success, is_error, error_message, content, structured_content). `feedback_codex_probe_fitness` Epic 2 retro norm validated by `Counter(names)` false-clean on keyword collision (Codex behavioral probe caught what type-system review missed).

- **Story 3.3 — Interleaved Dogfood — Port rf-mcp MCP Surface Tests**. `tests/dogfood/rf-mcp/test_mcp_surface_parity.robot` (15 tests). DOGFOOD-FINDING-1 caught the stdio `errlog=sys.__stderr__` crash (MCP SDK called `.fileno()` on RF's non-fd stderr capture; pre-fix 11 of 15 tests failed at startup; fix lands in `src/AgentEval/mcp/transport.py::open_stdio_session`). **Ratifies `feedback_interleaved_dogfood_load_bearing` Epic 3 retro NEW norm** — interleaved dogfood is production correctness layer, not milestone gate.

#### Epic 2 — Static Inspection (Skills + Subagents + Hooks + MCP)

- **Story 2.1 — Skill Static Inspection Keywords**. Tier-1 keywords at `src/AgentEval/skills/library.py::SkillsLibrary`: `Get Frontmatter`, `Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation`, `Should Be Valid Frontmatter`. YAML frontmatter parsing + 4-required-field validation per Claude skill format. Pre-allocated for Story 7's discoverability extensions.

- **Story 2.2 — Subagent + Hook Static Inspection Keywords**. `SubagentsLibrary` + `HooksLibrary` parallel surfaces at `src/AgentEval/subagents/library.py` + `src/AgentEval/hooks/library.py`. `Get Config` for Claude Code `settings.json` hook configuration parsing. `Get Effective Config` + `Get Effective Config With Provenance` for kwarg-resolved-with-source-tracking config queries. Codex behavioral probe (`Counter(names)`) caught a keyword-collision bug type-system review missed → `feedback_codex_probe_fitness` Epic 2 retro NEW norm.

- **Story 2.3 — MCP Static Inspection Keywords**. `MCP.Get Server Config` at `MCPLibrary.get_server_config` — parses `.mcp.json` files; raises `InvalidMCPServerConfigError` with RFC 6901 JSON Pointer `field_name` attribute on structural failure. Supports the 3-transport enum (`stdio` / `streamable_http` / `in_memory`) per PRD FR7.

- **Story 2.4 — Epic 2 Conformance Fixtures + Integration Tests Against Real Sample Files**. Integration tests at `tests/integration/static_inspection/` exercise the Epic 2 keyword surface against real skill `.md` + subagent + hook config + `.mcp.json` files (no mocks). Conformance fixtures at `tests/conformance/fixtures/static_inspection/` per `docs/contracts/conformance-fixture-format.md`.

#### Epic 1c — Phase-1.5 Carry-Overs Catalog

- **Story 1c-1 — Phase-1.5 Carry-Overs Catalog**. `docs/phase-1-5-carry-overs.md` catalog file at repo. 71 entries at Phase-1 close (was 0 at Story 1c-1 start). Per-entry schema: ID, description, source, category, effort, owner, resolution. Effort sizing XS/S/M/L/XL. Ratifies `feedback_carry_over_catalog_gate` Epic 4 retro NEW norm + UPSTREAM extension Epic 5 retro.

#### Epic 1b — Kernel + Types + Adapter ABCs + Conformance Harness

- **Story 1b.1 — Foundational Kernel — Context + Tier + Async Bridge**. `_kernel/context.py` Listener-context-read helper. `_kernel/tier.py` `@tier(1|2|3)` decorator. `_kernel/async_bridge.py` per ADR-012 `anyio.from_thread.run` async-to-sync bridge. `MCPLifecycleManager` at `_kernel/mcp_lifecycle.py` + `ServerHandle` type — single canonical owner of acquire/release per Story 0.2 spike findings.

- **Story 1b.2 — Trace + Observability Kernel — Trace Store + Redaction + Coverage**. `_kernel/trace_store.py` per-test in-memory store. `_kernel/redaction.py` credential-pattern + ToolCallTrace projection. `_kernel/coverage.py::_check_mcp_coverage` ADR-016 enforcement helper. `ToolCallTrace` frozen dataclass with defensive `dict()` copy on `args` (M_R6 pattern). `Usage` dataclass with non-negative validation. 8 new norms via cross-LLM review patches (H_R1 → M_R11).

- **Story 1b.3 — Discovery + Guardrails Kernel — Entry-Points + Fan-Out Decorator**. `_kernel/discovery.py` per ADR-013 (entry-points dispatch + legacy `robotframework_agenteval.adapters` migration shim). `_kernel/guardrails.py::@guarded_fanout` per ADR-015 (cost+runtime decorator for Tier-3 fan-out). `AdapterDiscoveryError` leaf + `DuplicateRegistrationError` subclass (Codex STAR catch). `register_adapter()` + `get_adapter()` registry surface.

- **Story 1b.4 — CodingAgentAdapter Protocol + InProcessAdapter / SubprocessAdapter ABCs**. `CodingAgentAdapter` Protocol at `src/AgentEval/types.py` per PRD FR12 (single `run(prompt, tools, mcp_servers, **kwargs) -> AgentRunResult` method; `@runtime_checkable` for FR17b composition). `InProcessAdapter` concrete-by-default ABC at `coding_agent/base.py` per ADR-003 (NO `@abstractmethod` hooks; direct method-override). `SubprocessAdapter(ABC)` template-method with 3 hooks (`_spawn`, `_parse_event`, `_finalize`). `AgentRunResult` frozen dataclass with nested `AgentRunMetadata` per FR36a/b + ADR-006 + ADR-016.

- **Story 1b.5 — Conformance Harness + Loader + Fixture Schema + 6 Reference Fixtures**. `tests/conformance/loader.py::load_fixture(path) -> ConformanceFixture` per architecture L737. `tests/conformance/fixture-schema.json` with 7 required keys (`_schema_version`, `adapter_name`, `scenario_name`, `agent_run_result`, `expected_tool_calls`, `expected_errors`, `reproducibility_footer`). 6 reference fixtures (3 mock + 3 generic). `_kernel/conformance.py` test orchestrator.

- **Story 1b.6 — Determinism Contract Doc + 5 CI-Enforcement Conventions Tests**. `docs/contracts/determinism-contract.md` substantively populated. 5 CI-enforcement conventions tests at `tests/unit/conventions/` (license-header presence; type-annotation completeness; Tier-1 LLM-ban static check; FR59 error-format compliance; unused-helper detection). Wires `ruff` + `mypy` per `docs/contracts/coding-conventions.md`.

#### Epic 1a — Project Bootstrap + CI + ADR Ratification + Doc Skeletons + Hygiene + Library Defaults

- **Story 1a.6 — Wire FR42 + FR43 + FR44 Library Defaults + Stability + Exit-Criteria Doc Stubs**. `AgentEval` RF Library class at `src/AgentEval/__init__.py` — keyword-only `__init__` with 9 parameters (`provider`, `telemetry`, `trace_backend`, `allow_validate_operator`, `default_temperature`, `mcp_per_test: bool | Literal["suite"]`, `allow_external_mcp_blind`, `max_cost_usd`, `max_runtime_seconds`). `Get Effective Config` RF keyword. FR42 acceptance test (6 tests). `docs/contracts/stability-surface.md` Phase-1 registry populated. `docs/contracts/exit-criteria-0x-to-1x.md` Phase-1 stub (4-criteria placeholder; final content lands Story 9.3).

- **Story 1a.5 — Project Hygiene — CONTRIBUTING + SECURITY + Issue Templates + License Headers**. `CONTRIBUTING.md` + `SECURITY.md` full content. 3 GitHub issue templates (bug-report, feature-request, question). Apache 2.0 license headers prepended to all 20 `.py` files via `scripts/apply-license-headers.py` (idempotent) + verifier `scripts/check-license-headers.py`. `.pre-commit-config.yaml` with ruff + mypy + license-header check. `docs/contracts/coding-conventions.md` substantively populated. 3 new GitHub labels (`good first issue`, `help wanted`, `documentation`).

- **Story 1a.4 — Author 11 Doc-Contract Skeletons**. 11 doc-contract skeletons at `docs/contracts/` per NFR-MAINT-04 + architecture amendments: `evidence-block-format.md`, `determinism-contract.md`, `stability-surface.md`, `exit-criteria-0x-to-1x.md`, `otel-trace-visual.md`, `error-class-hierarchy.md` (substantive — 11-leaf ADR-014 table with per-leaf `error_code` + epic ownership), `mcp-coverage-detection.md`, `conformance-fixture-format.md`, `coding-conventions.md`, `listener-integration.md`, `junit-xml-enrichment.md`. `docs/contracts/README.md` index.

- **Story 1a.3 — Ratify 18 Non-Spike ADRs + Author ADR-001 Architectural Influences Catalog**. 14 new ADRs authored (9 PRD-renumbered + 5 architecture-renumbered). ADR-001 body authored — Architectural Influences Catalog with 22 reviewed `robotframework-agentguard` patterns + 2 competitor MCP-eval projects + 2 industry standards. `docs/adr/README.md` index with 18-row sorted index. `feedback_agentguard_inspiration_not_dependency` norm ratified.

- **Story 1a.2 — Set Up 7 GitHub Actions CI Workflows**. `ci.yml` (PR-gating: Python 3.12+3.13 × ubuntu-latest), `nightly-live.yml` (NFR-REL-03), `conformance.yml` (per-release), `security-scan.yml` (CodeQL + weekly), `dogfood-integration.yml` (NFR-REL-05 cross-repo install-smoke), `docs-build.yml` (NFR-MAINT-04), `release.yml` (NFR-MAINT-03 PyPI OIDC trusted publishing). All workflows pinned actions + `timeout-minutes: 10` + concurrency cancel-in-progress. **Cross-LLM-reviewed** — 1 HIGH-1 fake-green caught (`dogfood-integration.yml` `continue-on-error: true` masked 72 rf-mcp + 6 robotframework-agentskills failures — `feedback_ci_log_forensics` Epic 1a retro norm).

- **Story 1a.1 — Project Bootstrap — Standalone Python + RF Library**. `pyproject.toml` src-layout (`src/AgentEval/`) + hatchling build backend. Dependency pins per Story 0.1/0.2 spike validation. 6-entry-point table (4 `agenteval.*` discovery groups + 1 legacy migration shim + 1 RF listener). `src/AgentEval/` 16-sub-package skeleton + 3 security stubs (ADR-018). Empty `tests/{unit, integration, conformance, benchmarks, fixtures}/` + `docs/{contracts, recipes, scenarios, keywords, coming-from, troubleshooting}/`. `LICENSE` Apache-2.0 + `ruff.toml` + `mypy.ini` + `.env.example`.

#### Epic 0 — Architecture Spike Validation + ADR Ratification

- **Story 0.1 — Run Hosted-MCP Universal Observer Spike**. Empirically validated the `Server.request_handlers` wrap pattern per ADR-004. 5/5 edge-cases pass (`probe_dual_path_trust_floor` reports `hosted_in_process` when both paths fire; degradation rules verified). Spike-dependent ADR-004 ratified at `accepted` status.

- **Story 0.2 — Run Per-Test MCP Cleanup-Under-Pabot Spike**. Validated per-test MCP server scope under `robotframework-pabot` parallel execution. Process-group hygiene + cleanup-on-exception patterns ratified. macOS validation deferred to Phase-1.5 per D2.1 architect waiver (Linux-only Phase 1).

- **Story 0.3 — Amend & Ratify Spike-Dependent ADRs**. 4 ADRs ratified post-spike: ADR-004 (hosted-MCP observation), ADR-A6 → ADR-016 (mcp_coverage detection default), ADR-A8 → ADR-018 (sandbox Phase-1 policy), plus the §Amendments Log preserved byte-identical for cross-reference across Story 1a.3's catalog authoring.

### Methodology developments — 23 ratified `feedback_*` review-methodology norms

This phase establishes the cross-LLM adversarial review system that became load-bearing for the project's quality bar. Highlights:

- **`feedback_review_methodology_norms`** (Epic 0 retro, 2026-05-17 ratification) — cross-LLM adversarial review is the project standard. Single-LLM review is insufficient; ≥2 LLM families required.
- **`feedback_spec_vs_ratified_doc_precheck`** (Epic 1a retro, 2026-05-17 ratification) — 44 consecutive uses with 100% real-drift catch rate at Phase-1 close.
- **`feedback_codex_probe_fitness`** (Epic 2 retro) — Codex behavioral probes catch what type-system review can't (e.g., `Counter(names)` keyword collision false-clean).
- **`feedback_test_name_assertion_match`** (Epic 3 retro) — every test name MUST match its assertion body; 3 new violations caught in Epic 8 + 9 retro-batch.
- **`feedback_n_way_agreement_weight`** — 3-way HIGH findings = near-certain bugs (100% TP across Epics 2-5; extended to 11+ consecutive TPs across 7 epics by Epic 5 retro).
- **`feedback_carry_over_catalog_gate` UPSTREAM** — 24 consecutive stories at Phase-1 close. Gate moved upstream to `/bmad-dev-story` Task N-1 per Epic 5 retro.
- **`feedback_interleaved_dogfood_load_bearing`** (Epic 3 retro) — interleaved dogfood IS production correctness, not milestone gate; caught DOGFOOD-FINDING-1 stdio errlog crash that the 4-reviewer Story 3.1 code review missed.
- **`feedback_listener_hook_api_surface_empirical_check`** (Epic 8 retro) — Story 8a.2 `data.tags` vs `result.tags` empirical-API-surface check.
- **`feedback_contract_doc_invocation_smoke_test`** (Epic 8 retro) — contract docs documenting CLI/RF invocations MUST carry subprocess integration smoke test.
- **`feedback_integration_test_forcing_function`** (Epic 8 retro) — when cross-LLM review degrades, end-to-end integration tests substitute as empirical-truth check.
- **`feedback_third_llm_family_fallback`** (CANDIDATE Epic 10 retro, 2026-05-26) — kilocode/minimax delivers when Claude + Codex CLIs degrade. 9 consecutive substantive cross-LLM reviews across Epic 8 + 9 + 10 retro-batch. Promote to NEW at next retrospective.
- Plus 12 additional ratified norms (honest framing, agentguard inspiration-only, citation drift first-class, test-name/assertion-match, dogfood validation-ceiling, executable-doc precheck, retro-on-retro cross-LLM, sandbox-bypass operational, in-flight spec amendment, caller-count check, nullish-input fuzz CONDITIONAL, dogfood fake-green precheck).

Full registry lives in the project's auto-memory at `/home/many/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md`. Public mirror at `docs/methodology/feedback-norms.md` is a deferred work item.

### Cross-LLM pipeline degradation + restoration

- **Epic 8 (post-2026-05-25)**: Claude CLI began returning 0-byte output on long prompts; Codex CLI rate-limited from Story 8a.1 onward.
- **Epic 8 retro (2026-05-25)**: Action #1 catalogued the degradation + proposed 4 mitigation steps (i: re-run via `claude -p --model opus`, ii: Codex quota check, iii: third-LLM-family fallback, iv: in-loop circuit-breaker).
- **Epic 9 (2026-05-25)**: 0 of 3 stories received substantive cross-LLM review; 8 consecutive stories of degraded review across Epic 8 + 9.
- **Story 10.1 (2026-05-25)**: Claude CLI returned substantive 6-finding review via `claude -p --dangerously-skip-permissions --model opus` invocation — step (i) implicitly validated.
- **Story 10.2 + Epic 8/9 retro batch (2026-05-26)**: kilocode CLI / minimax-M2.7 delivered substantive cross-reviews across 9 stories. **Step (iii) functionally resolved.** `feedback_third_llm_family_fallback` candidate norm reinforced.

### Retrospectives

Per-epic retrospectives + cross-LLM retro-of-retro reviews at `_bmad-output/implementation-artifacts/epic-*-retro-*.md`:

- Epic 0 retro (Story 0.3) — `feedback_review_methodology_norms` ratification
- Epic 1a retro — `feedback_spec_vs_ratified_doc_precheck` + `feedback_ci_log_forensics`
- Epic 1b retro — `feedback_citation_drift_first_class`
- Epic 2 retro — `feedback_codex_probe_fitness` + `feedback_n_way_agreement_weight`
- Epic 3 retro — `feedback_test_name_assertion_match` + `feedback_interleaved_dogfood_load_bearing`
- Epic 4 retro — `feedback_carry_over_catalog_gate` + `feedback_codex_sandbox_bypass_operational`
- Epic 5 retro — `feedback_dogfood_fake_green_precheck` + `feedback_caller_count_check` + `feedback_in_flight_spec_amendment`
- Epic 7 retro — `feedback_executable_doc_precheck` + `feedback_dogfood_validation_ceiling` + `feedback_nullish_input_fuzz_checklist` (CONDITIONAL) + `feedback_retro_on_retro`
- Epic 8 retro (`fadb930`) — `feedback_listener_hook_api_surface_empirical_check` + `feedback_contract_doc_invocation_smoke_test` + `feedback_integration_test_forcing_function`
- Epic 9 retro (`8f2a161`) — `feedback_retro_debt_block_forward_progress` (CANDIDATE downgraded from CONDITIONAL after kilo cross-review)
- Epic 10 retro (forthcoming) — `feedback_third_llm_family_fallback` ratification expected
- Phase-1 retrospective at `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md`
- Epic 8 + 9 kilo/minimax retro-cross-review batch at `_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md` (commit `16ee936`)

---

## [0.0.1] — 2026-05-17

### Added

- Initial repository scaffolding (Story 1a.1):
  - `pyproject.toml` with src-layout (`src/AgentEval/`) + hatchling build backend.
  - Dependencies: `mcp==1.27.1`, `robotframework==7.4.2`, `anyio==4.13.0` (exact pins per Story 0.1/0.2 spike validation); `litellm`, `opentelemetry-api`, `opentelemetry-sdk`, `pyyaml`, `jsonschema` (range pins with upper-bound caps).
  - `[dev]` extras: `pytest`, `pytest-cov`, `ruff`, `mypy`, `robotframework-pabot==5.2.2`.
  - Empty entry-point tables (6 total): 4 `agenteval.*` discovery groups (coding_agents, providers, judges, sandboxes per ADR-018) + 1 legacy `robotframework_agenteval.adapters` (FR17a) + 1 RF-owned `robot.listener` (FR33a). Plus `[project.scripts] agenteval = "AgentEval.cli:main"` per FR18; cli.py is a Phase-1 placeholder (real subcommands `init` + `new-adapter` ship in Epic 8b).
  - `src/AgentEval/` skeleton with 16 sub-packages, each with `__init__.py`. Plus `src/AgentEval/cli.py` (Phase-1 placeholder), and 3 security stubs per ratified ADR-018 (`security/protocols.py` — SandboxBackend Protocol; `security/null_sandbox.py` — refuses every execute(); `security/policy.py` — gate placeholder for Epic 6 wiring).
  - `tests/{unit, integration, conformance, benchmarks, fixtures}/` directories.
  - `docs/{contracts, recipes, scenarios, keywords, coming-from, troubleshooting}/` directories. (`docs/adr/` pre-exists with 4 ratified ADRs from Story 0.3.)
  - `examples/` directory.
  - Config files: `.python-version`, `.gitignore`, `LICENSE` (Apache-2.0), `ruff.toml`, `mypy.ini`, `.env.example`.
  - Doc files: `README.md`, `CHANGELOG.md`, `MAINTAINERS.md`, `SUPPORT.md`.

### Known limitations

- macOS validation deferred to Phase-1.5 per D2.1 architect waiver (inherited from Story 0.2 review). Story 1a.1 only validates `uv sync` on Linux.
- Empty package — no public API yet. `import AgentEval` succeeds but exposes only `__version__`. Sub-libraries land in Epic 1b onward.

### References

- ADR-004 (was ADR-007) — hosted-MCP universal observation pattern
- ADR-016 (was ADR-A6) — MCP coverage detection default (D1 trust-floor + D4 adapter contract)
- ADR-018 (was ADR-A8) — sandbox Phase 1 policy
- ADR-001 (stub) — architectural influences catalog (body filled by Story 1a.3)
