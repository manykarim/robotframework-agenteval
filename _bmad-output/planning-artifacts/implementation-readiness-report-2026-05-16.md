---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
status: complete
filesIncluded:
  prd: "_bmad-output/planning-artifacts/prd.md"
  adrBacklog: "_bmad-output/planning-artifacts/adr-backlog-from-prd.md"
  architecture: null
  epics: null
  stories: null
  ux: "intentionally-skipped (no UI; visual contracts captured as FRs)"
inputArtifacts:
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval.md"
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval-distillate.md"
  - "_bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md"
scope: "PRD-only audit (Architecture and Epics not yet authored; user elected to validate PRD before downstream workflows)"
date: 2026-05-16
project_name: robotframework-agenteval
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-16
**Project:** robotframework-agenteval
**Scope:** PRD-only audit (per user direction; downstream artifacts not yet authored)
**Auditor role:** Expert Product Manager — requirements-traceability + planning-gap detection

## Section 1: Document Discovery

### Discovered files (in `_bmad-output/planning-artifacts/`)

**PRD documents (whole, no shards):**
- `prd.md` (166 KB, modified 2026-05-16, frontmatter `status: complete`, 12 sections, ~1,679 lines)
- `adr-backlog-from-prd.md` (18 KB, modified 2026-05-16) — ADR sidecar for downstream architecture step; NOT a duplicate PRD

**Input artifacts (preserved, used as PRD source material):**
- `product-brief-robotframework-agenteval.md` (17 KB) — product brief
- `product-brief-robotframework-agenteval-distillate.md` (17 KB) — distillate of brief for downstream LLM consumption
- `research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md` (~36 KB / 1,099 lines) — technical research feeding the brief + PRD

**Missing prerequisites (will limit assessment scope):**
- Architecture: not authored. `/bmad-create-architecture` has not run.
- Epics & Stories: not authored. `/bmad-create-epics-and-stories` has not run.

**Intentionally absent (NOT a gap):**
- UX Design: per PRD scope (library product, no UI), `/bmad-create-ux-design` was explicitly skipped. Visual contracts for evidence blocks (FR34b), cohort heatmap (FR55), and OTel trace visualization (FR58) are documented inline in the PRD and require no separate UX deliverable.

### Discovery issues to flag
- **No duplicate format conflicts** (no shard-vs-whole duplication, no competing PRD versions).
- **Missing downstream artifacts noted but accepted** per user direction. Audit will proceed PRD-only and surface readiness gaps for those downstream artifacts as findings rather than blocking issues.

## Section 2: PRD Analysis

### Functional Requirements — full inventory (65 total, by ID)

PRD organizes FRs across 11 capability areas with some sub-lettered IDs (FR9a/b, FR10a/b, FR13a-f, FR17a/b/c, FR23a/b, FR29a/b/c, FR30a/b, FR31a/b, FR33a/b, FR34a/b, FR36a/b, FR38a/b) — yielding **65 distinct FRs** with consistent numbering. Plus **FR11b** (time guardrail; sibling to FR11) added in Step 10 from empirical input. Final FR count = **65 IDs**.

#### Area 1 — Static Agent-Surface Inspection (Tier 1, Phase 1) [6 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR1 | `Skill.Get Frontmatter <path.md>` returns parsed YAML dict; raises `InvalidSkillFrontmatterError` with path+line+field | P1 |
| FR2 | Skill frontmatter field assertions via AssertionEngine matchers (`Should Be Valid Frontmatter`, `contains`, `matches`) | P1 |
| FR3 | `Subagent.Get Frontmatter <path.md>` for `.claude/agents/*.md` files | P1 |
| FR4 | `Hook.Get Config <settings.json>` returns hooks-by-event dict (PreToolUse, PostToolUse, Stop) | P1 |
| FR5 | `MCP.Get Server Config <.mcp.json>` returns declared-server dict without starting | P1 |
| FR6 | `MCP.Get Tool Schema` + `MCP.Validate Tool Schema` raises `InvalidMCPToolSchemaError` with JSON Pointer | P1 |

#### Area 2 — MCP Server Dynamic Evaluation [6 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR7 | `MCP.Start Server` with stdio/streamable_http/in_memory transports + per-test scope | P1 |
| FR8 | `MCP.Connect To Server` + version negotiation; raises `UnsupportedMCPVersionError` outside `mcp>=1.0,<2.0` | P1 |
| FR9a | `MCP.List Tools` + `Get Tool Names` / `Get Tool Descriptions` projections | P1 |
| FR9b | `MCP.Call Tool` returns `MCPToolResult` with AssertionEngine matchers | P1 |
| FR10a | `MCP.Get Tool Discoverability` single-runtime version with cohort + failed-task evidence | P1 |
| FR10b | `MCP.Compare Tool Discoverability` cross-runtime with Mann-Whitney U | P2 |
| FR11 | `CostExceededError` pre-flight + mid-run hard-stop at 1.1× `max_cost_usd` (default 5.00) | P1 |
| FR11b | `RuntimeBudgetExceededError` pre-flight + mid-run hard-stop on `max_runtime_seconds` (default None, opt-in) | P1 |

#### Area 3 — Agent Run Orchestration & Adapter Ecosystem [13 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR12 | `CodingAgentAdapter` Protocol + `InProcessAdapter` / `SubprocessAdapter` internal base classes (public contributor-facing API) | P1 |
| FR13a | `coding_agent/generic.py` (LiteLLM, 140+ providers including local Ollama/vLLM) | P1 |
| FR13b | `coding_agent/claude_code_cli.py` (`--output-format=stream-json`, pinned binary) | P1 |
| FR13c | `coding_agent/claude_agent_sdk.py` (SDK Python, in-process MCP) | P2 |
| FR13d | `coding_agent/openai_agents.py` (`Runner.run_streamed` + StreamEvent) | P2 |
| FR13e | `coding_agent/codex_cli.py` (JSON event stream, pinned binary) | P2 |
| FR13f | `coding_agent/copilot_cli.py` (live `-p --output-format=json` + post-hoc `events.jsonl`; pinned `copilot>=1.0.9,<2.0`) | P2 |
| FR14 | `Send Prompt <agent> <prompt>` returns `AgentRunResult` | P1 |
| FR15 | `Run Scenario <yaml_path>` executes declarative scenario | P1 |
| FR16 | `mcp_servers=` keyword arg with per-test scope + server-side observation | P1 |
| FR17a | Entry-points adapter registration `[project.entry-points."agenteval.coding_agents"]` | P1 |
| FR17b | Direct adapter composition via `__init__(coding_agent=MyAdapter())` | P1 |
| FR17c | Custom `LLMProviderAdapter` via entry-points or `__init__(provider=)` | P1 |
| FR18 | `agenteval new-adapter <name>` scaffolding command | P1 |

#### Area 4 — Tool-Call Metrics & Trajectory Analysis [7 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR19 | `Metric.Get Tool Call Count` + `Get Tool Call Names` | P1 |
| FR20 | `Metric.Get Tool Hit Rate` + `Get Tool Success Rate` | P1 |
| FR21 | `Metric.Get Unnecessary Call Rate` | P1 |
| FR22 | `Metric.Get Token Usage` + `Get Latency` + `Get Latency P95` + `Get Cost Total` | P1 |
| FR23a | `Trajectory Should Match` with modes: exact / subsequence / set (default exact) | P1 |
| FR23b | `Trajectory Should Match mode=regex` | P1 |
| FR24 | `Tool Call Should Have Occurred tool=<name> [args=<dict>]` | P1 |
| FR25 | `Agent Response Should Contain / Match Regex / Match Schema` | P1 |

#### Area 5 — Statistical Evaluation & Three-Tier Determinism Model [9 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR26 | `Stat.Run N Times` with independent samples (no state leakage) | P1 |
| FR27 | `Stat.Get Pass At K` (HumanEval unbiased estimator) + AssertionEngine matchers | P1 |
| FR28 | `PollingDisallowedError` on Tier-2/3 with `polling=` arg | P1 |
| FR29a | `Stat.Mann Whitney U` (advanced extras) | P2 |
| FR29b | `Stat.Cliff Delta` (advanced extras) | P2 |
| FR29c | `Stat.Bootstrap Confidence Interval` (advanced extras) | P2 |
| FR30a | Tier 1/2/3 categorization via metadata; `Get Keyword Tier` + libdoc badge | P1 |
| FR30b | `TierViolationError` on Tier-1 keyword attempting LLM provider invocation | P1 |
| FR31a | Tier-1 bit-identical reruns guarantee; `Assert Run Determinism expect=byte_identical` | P1 |
| FR31b | Tier-2/3 statistical interpretability via Pass@k + reproducibility footers | P1 |

#### Area 6 — Trace Recording & Observability [9 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR32 | OpenTelemetry GenAI spans (`invoke_agent → chat → execute_tool`) with `gen_ai.*` attributes | P1 |
| FR33a | RF Listener v3 registered via entry-points; opt-in `__init__(telemetry=True)` | P1 |
| FR33b | Memory + JSONL backends (P1); OTLP backend (P2 via `[otlp]`) | P1+P2 |
| FR34a | Evidence-block format with required sections (`AC-SIMPLICITY-01`) | P1 |
| FR34b | Evidence-block visual contract (monospace fenced, header + 3 subsections, 1000-char truncation) | P1 |
| FR35 | Hosted-MCP server-side observation with `source` field on `ToolCallTrace` | P1 |
| FR36a | `completeness` field required (`complete`/`truncated`/`partial`) | P1 |
| FR36b | `mcp_coverage` field required (`complete`/`library_only`/`external_mixed`/`no_mcp`) | P1 |
| FR37 | `IncompleteTraceError` on `external_mixed` unless `allow_external_mcp_blind=True` | P1 |
| FR38a | Credential redaction in trace artifacts (custom patterns via `config.add_redaction_pattern`) | P1 |
| FR38b | Same redaction in `Get Effective Config` output | P1 |
| FR39 | RunManifest JSON sidecar with seeds + versions + hashes + test_id + timestamp | P1 |
| FR40 | Per-test MCP scope via Listener v3 `test_id`; `mcp_per_test=False` opt-out | P1 |

#### Area 7 — Configuration & Provider/Agent Extensibility [4 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR41 | Config precedence (init args → env → .env → defaults) + `Get Effective Config` | P1 |
| FR42 | Documented defaults (provider=litellm, telemetry=True, etc.) | P1 |
| FR43 | `allow_validate_operator=True` opt-in (eval() security gate) | P1 |
| FR44 | `telemetry=False` disables OTel listener; `Assert No Egress To` verifiable | P1 |

#### Area 8 — Conformance & Compatibility Contracts [4 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR45 | `tests/conformance/` runnable suite via `python -m agenteval.conformance [--adapter]` | P1 |
| FR46 | `UnsupportedMCPVersionError` on out-of-range MCP spec versions (mock-server-verified) | P1 |
| FR47 | `UnsupportedBinaryVersionError` on CLI adapter binary outside pinned range; never auto-installs | P1 |
| FR48 | `plugins=[...]` keyword surface extension via `__init__` | P1 |

#### Area 9 — Reporting, CI Integration & First-Run Experience [11 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR49 | JUnit XML emission via `agenteval.reporting.junit_listener:JUnitListener` (opt-in) | P1 |
| FR50 | Non-zero exit codes (1=assertion fail; 2=cost/incomplete; 3=spec/binary/polling errors) | P1 |
| FR51 | Trace ID surfaced in `output.xml` per test (`trace_id` attribute) | P1 |
| FR52 | `agenteval init [--template basic|skill|mcp|scenario]` scaffolding | P1 |
| FR53 | (Cross-ref to FR18 — `agenteval new-adapter`) | P1 |
| FR54 | Terminal run summary to stderr (pass/fail counts + cost + time-to-first-test + next-step hint) | P1 |
| FR55 | `Metric.Get Cohort Heatmap` returns `CohortHeatmap` with `as_ascii()` / `as_dict()` (P1); `as_html()` (P2) | P1+P2 |
| FR56 | `PollingDisallowedError` text must contain keyword name + test file:line + remediation snippet + ADR link | P1 |
| FR57 | `python -m agenteval.conformance --adapter` emits JSON-on-stdout + human-summary-on-stderr | P1 |
| FR58 | OTel trace visualization contract published at `docs/contracts/otel-trace-visual.md` | P1 |
| FR59 | All Tier-1 setup-failure errors carry path+line+remediation hint | P1 |

#### Area 10 — Honest Failure Reporting (cross-cutting) [3 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR60 | `AdapterVersionDriftWarning` for binary versions in-range but lagging tested | P2 |
| FR61 | `DegradedTraceWarning` + `mcp_coverage=partial` on mid-run MCP interruption (non-blocking) | P1 |
| FR62 | `Get Last Warnings <run>` returns warnings list with source+message+remediation | P1 |

#### Area 11 — Determinism Contract & Stability Surface (documentation deliverables) [3 FRs]

| ID | Capability | Phase |
|---|---|---|
| FR63 | Determinism Contract doc at `docs/contracts/determinism-contract.md` (byte-identical to PRD §5) | P1 |
| FR64 | Stability Surface doc with stable/provisional/experimental labels per public surface | P1 |
| FR65 | 0.x→1.0 Exit Criteria doc (preliminary stub in PRD; final at Phase 1 close) | P1 |

**FR count by phase:** Phase 1 = 56; Phase 2 = 9 (FR10b, FR13c-f, FR29a/b/c, FR60); Phase 1+2 (split delivery: FR33b memory/JSONL P1, OTLP P2; FR55 ASCII P1, HTML P2) = 2.

### Non-Functional Requirements — full inventory (25 IDs across 5 categories)

#### Performance [8 NFRs]

| ID | Bar | Measurement |
|---|---|---|
| NFR-PERF-01 | Time-to-first-test ≤ 5 min on published cohort | CI smoke job runs README walkthrough end-to-end. **Release-blocking.** |
| NFR-PERF-02 | Tier-1 keyword execution ≤ 50 ms median on typical file sizes | `tests/benchmarks/`; >2× regression blocks release |
| NFR-PERF-03a | Bundled echo MCP server startup ≤ 200 ms median | CI smoke job |
| NFR-PERF-03b | User-provided MCP servers — **no startup cap** (rf-mcp/robotmcp take several seconds, acknowledged) | N/A (constraint documentation) |
| NFR-PERF-03c | MCP protocol handshake post-startup ≤ 500 ms median | Fixture timing |
| NFR-PERF-03d | `mcp_per_test=True|"suite"|False` trade-off matrix documented + tested | Cookbook + conformance suite |
| NFR-PERF-04 | Cost guardrail accuracy: pre-flight ±20%; mid-run hard-stop within 10% of limit | Cost-meter unit tests vs deterministic mock |
| NFR-PERF-05 | `pabot --processes 8` parallel — no cross-test pollution with bundled echo; heavy-server opt-out documented | Conformance suite parallel-test fixture + heavy-server simulation (sleep 3) |
| NFR-PERF-06 | `max_runtime_seconds` time guardrail pre-flight + 1.1× hard-stop | Subprocess fixture against slow-mock provider |

#### Reliability [5 NFRs]

| ID | Bar | Measurement |
|---|---|---|
| NFR-REL-01 | `tests/unit/` ≥ 99% pass on every PR (Python 3.12+3.13 × Linux+macOS) | GitHub Actions matrix. **Release-blocking.** |
| NFR-REL-02 | `tests/acceptance/` smoke = 100% on release-tag CI | **Release-blocking.** |
| NFR-REL-03 | `tests/integration/` live ≥ 95% nightly; 3 consecutive failures gate next release | Nightly cron CI |
| NFR-REL-04 | External dep pinning posture (floor+ceiling or rationale) documented per release | CHANGELOG review |
| NFR-REL-05 | Dogfood loop integrity: `rf-mcp` + `robotframework-agentskills` CI runs against released lib within 24h; regression blocks next release | Cross-repo CI integration |

#### Security [5 NFRs]

| ID | Bar | Measurement |
|---|---|---|
| NFR-SEC-01 | No credentials persisted in original form anywhere; `config.redact_env()` mandatory pre-trace-write | CI test + conformance suite unknown-shape redaction |
| NFR-SEC-02 | `eval()` only via opt-in `validate` operator; safe operators elsewhere | CI test on default config |
| NFR-SEC-03 | TLS for all LLM provider + Streamable HTTP traffic; no cert-validation-relax knobs | Code review / security audit |
| NFR-SEC-04 | Library never auto-downloads / installs / updates vendor binaries; supply-chain trust boundary in `SECURITY.md` | Documentation + code review |
| NFR-SEC-05 | No phone-home; only LLM + OTLP egress (latter opt-in P2); `telemetry=False` eliminates OTel egress | `Assert No Egress To` conformance fixture |

#### Integration & Compatibility [6 NFRs]

| ID | Bar | Measurement |
|---|---|---|
| NFR-COMPAT-01 | Python 3.12 + 3.13 Tier-1 CI; <3.12 unsupported; `requires-python = ">=3.12"` | CI matrix + pyproject |
| NFR-COMPAT-02 | RF `>=7.4,<9.0`; stable-APIs-only; RF 8.x.beta CI testing P2 deliverable | CI matrix |
| NFR-COMPAT-03 | Linux + macOS first-class CI; Windows best-effort + documented troubleshooting; FreeBSD unsupported | CI matrix + first-day guide |
| NFR-COMPAT-04 | `mcp>=1.0,<2.0`; transports stdio/streamable_http/in-memory; SSE legacy | Code + pyproject |
| NFR-COMPAT-05 | `litellm>=1.83` minor-floor; Protocol isolates; Mock fallback | Pyproject + Mock adapter |
| NFR-COMPAT-06 | `opentelemetry-api/sdk>=1.27` minor-floor; semconv internal facade; Datadog v1.37+ + Grafana Tempo as P2 first-party targets | Pyproject + facade module |

#### Maintainability [5 NFRs]

| ID | Bar | Measurement |
|---|---|---|
| NFR-MAINT-01 | Solo + AI-agent-assisted posture in `MAINTAINERS.md`; bus-factor deliverables P1 (CONTRIBUTING + good-first-issue + portfolio docs + Mock template + conformance suite + SubprocessAdapter ABC) | Documentation review |
| NFR-MAINT-02 | Issue-triage SLA: best-effort 5 business days; security prioritized; published in `SUPPORT.md` | Documentation + GitHub Issues telemetry |
| NFR-MAINT-03 | Semver discipline: 0.x.y breaking → minor-bump; 1.0+ strict semver after exit criteria | Release process |
| NFR-MAINT-04 | Docs are first-class P1 (README + recipe gallery ≥8 + ADRs + 5 contracts docs); doc-build CI asserts required sections | Doc-build CI |
| NFR-MAINT-05 | Stability Surface metadata updated per release; every public element has exactly one label | Doc-build CI |

### Acceptance Criteria — cross-cutting inventory (9 unique)

| AC ID | Defines | Bound to FR(s) |
|---|---|---|
| AC-SIMPLICITY-01 | Evidence-block legibility on every assertion (pass + fail) | FR34a, FR34b |
| AC-SIMPLICITY-02 | Sub-library getter+matcher rule + core ergonomic carve-out + paired-getter requirement | All keyword FRs; FR12, FR23, FR25 |
| AC-DISCOVER-01 | `MCP.Get Tool Discoverability` evidence-block shape | FR10a, FR10b |
| AC-DISCOVER-02 | `max_cost_usd=5.00` default + pre-flight + mid-run hard-stop | FR11, NFR-PERF-04 |
| AC-DOGFOOD-01 | `rf-mcp` + `robotframework-agentskills` custom tests replaced by `.robot` at parity by end of Phase 1 | NFR-REL-05 + cross-repo CI integration |
| AC-CONFORMANCE-01 | Conformance suite includes fidelity oracles (golden-trace fixtures) | FR45 |
| AC-CONFORMANCE-02 | `completeness` field required + truncation-injection oracle | FR36a, FR45 |
| AC-MCP-OBSERVE-01 | `mcp_coverage` indicator + `IncompleteTraceError` on `external_mixed` | FR36b, FR37 |
| AC-MCP-OBSERVE-02 | MCP spec version validation at session start | FR8, FR46 |
| AC-MCP-OBSERVE-03 | Per-test MCP scope via Listener v3 `test_id` | FR40 |

### Additional Requirements / Constraints (not numbered as FR/NFR)

These are captured in the PRD but live in narrative form across Domain Constraints, Risk Mitigation, ADR backlog, and frontmatter `userProvidedContext`. They are real implementation constraints; architecture + epic-breakdown steps must honor them.

**Architecture decisions (10 new ADRs + 4 inherited, sidecar at `adr-backlog-from-prd.md`):**
- ADR-001..004 (inherited from `robotframework-agentguard`): DynamicCore composition, AssertionEngine adoption, polling ban, `validate` operator disabled by default.
- ADR-005: Tier-1 adapter cap rule "≤2 per vendor + 1 generic escape hatch."
- ADR-006: `CodingAgentAdapter` Protocol + `InProcessAdapter` / `SubprocessAdapter` internal class split.
- ADR-007: Hosted-MCP universal trace observation pattern.
- ADR-008: Conformance suite fidelity oracles (golden-trace fixtures).
- ADR-009: `AgentRunResult.metadata.completeness` field required.
- ADR-010: `mcp_coverage` + `IncompleteTraceError`.
- ADR-011: MCP spec version validation gate.
- ADR-012: Per-test MCP server scope (Listener v3 `test_id`).
- ADR-013: Copilot CLI adapter trace-extraction strategy (live + post-hoc).
- ADR-014: Three-persona model + persona-split test rule.

**Cross-cutting constraints (Domain Constraints §1-5):**
- Non-determinism handling: three-tier ACL gates, polling ban, statistical primitives in core, cost guardrails on multi-trial Tier-3.
- External-specification instability: pinning posture for MCP / OTel / LiteLLM / RF / coding-agent SDKs/CLIs.
- Maintainership: solo + AI-agent-assisted; AI productivity assumed near-zero on RF/MCP/OTel-internal surfaces; bus-factor stated openly.
- Trust & safety: LLM-as-judge bias acknowledged; `eval()` gated; credential redaction mandatory; eval ≠ authoring boundary; tool-discoverability vocabulary asymmetry documented.
- Determinism contract: what library promises (Tier-1 bit-identical, Tier-2/3 statistical interpretability via Pass@k, reproducibility footers, polling refusal) and does NOT promise (cross-model-version, cross-provider, bit-identical Tier-2/3, auto flake budgets).

**Empirical performance datum:** `rf-mcp` / `robotmcp` startup is **several seconds** (Many's input at Step 10). Drove NFR-PERF-03 split and the new `mcp_per_test="suite"` mode.

**Risk register (consolidated in Phasing Strategy section):** 13 technical risks, 5 market risks, 4 resource risks — each with mitigation and ownership pointer.

### PRD Completeness Assessment (initial)

| Dimension | Status | Notes |
|---|---|---|
| Information density | ✅ High | Anti-pattern scan at Step 11 polish returned no matches (no "in order to", "It is important", "will allow users", subjective "fast/easy/intuitive") |
| Traceability chain (Vision → Success Criteria → Journeys → FRs) | ✅ Intact | Every FR maps to at least one Journey and one Success-Criteria bar; Persona-split test (ADR-014) enforces persona-to-FR alignment |
| FR observability (testability rule) | ✅ Applied globally | Every FR specifies exact keyword call, error class, or measurable output; no "per AC-X" pointer-style FRs remain |
| AC ↔ FR symmetry | ✅ Symmetric | All 9 ACs are referenced inside FRs that name the testable observable |
| Phase boundary clarity (P1 vs P2) | ✅ Marked inline | Every FR carries Phase tag; some FRs (FR10a/b, FR33b, FR55) split delivery across P1+P2 explicitly |
| Personas covered | ✅ Three personas with split-test rule | QA Engineer + Agent Surface Author + Agent Developer + Contributor (4th journey only) |
| Dogfood scope falsifiability | ✅ AC-DOGFOOD-01 names two real repos | `rf-mcp` + `robotframework-agentskills`; CI integration in NFR-REL-05 |
| Cost + time guardrails | ✅ Present | `max_cost_usd` (FR11) + `max_runtime_seconds` (FR11b) as orthogonal axes |
| ADR backlog seeded for architecture step | ✅ 10 new + 4 inherited | `adr-backlog-from-prd.md` sidecar ready for ingestion |
| Documentation deliverables specified | ✅ 5 contracts docs + recipe gallery + ADRs + README | NFR-MAINT-04 commits to doc-build CI enforcement |
| Initial readiness gaps to surface in later steps | Coverage to be validated downstream | (1) Architecture not yet authored — Step 4 will note; (2) Epics not yet authored — Step 3 will note; (3) UX intentionally skipped — not a gap |

## Section 3: Epic Coverage Validation

### Status: BLOCKED — no epics document exists

Discovery in Section 1 confirmed: `/bmad-create-epics-and-stories` has not been run; there is no epics or stories document at `_bmad-output/planning-artifacts/*epic*.md` or `*stor*.md`.

### Coverage statistics

- **Total PRD FRs**: 65 (per Section 2 inventory)
- **FRs covered in epics**: 0 (no epics exist)
- **Coverage percentage**: 0% — **all 65 FRs are uncovered** by epics

This is **not a defect in the PRD**; it is a missing downstream artifact. The PRD itself is complete and trace-ready; the next workflow step in the planning pipeline (`/bmad-create-epics-and-stories`) is the one that produces the epic-level coverage mapping.

### What epic coverage should look like when authored

For the architecture and epic-breakdown steps downstream, the 65 FRs map naturally to **11 epic candidates** corresponding to the 11 capability areas already structured in the PRD:

| Capability Area | Suggested Epic Title | FR IDs | Phase split |
|---|---|---|---|
| 1. Static Agent-Surface Inspection | "Static Inspection Keywords" | FR1-6 | All P1 |
| 2. MCP Server Dynamic Evaluation | "MCP Server Lifecycle + Tool Discoverability" | FR7-11, FR11b | FR10b → P2 |
| 3. Agent Run Orchestration & Adapter Ecosystem | "Coding Agent Adapters" | FR12-18 | FR13c-f → P2 |
| 4. Tool-Call Metrics & Trajectory Analysis | "Metrics & Trajectory Keywords" | FR19-25 | All P1 |
| 5. Statistical Evaluation & Three-Tier Determinism Model | "Statistical Primitives + Tier Model" | FR26-31 | FR29a/b/c → P2 |
| 6. Trace Recording & Observability | "OTel Tracing + Evidence Block Legibility + Hosted-MCP Observation" | FR32-40 | FR33b OTLP backend → P2 |
| 7. Configuration & Provider/Agent Extensibility | "Configuration & Extension Surface" | FR41-44 | All P1 |
| 8. Conformance & Compatibility Contracts | "Conformance Suite + Version Gates" | FR45-48 | All P1 |
| 9. Reporting, CI Integration & First-Run Experience | "Reporting, CI Integration & `agenteval init`/`new-adapter` CLI" | FR49-59 | FR55 HTML → P2 |
| 10. Honest Failure Reporting | "Adapter Drift + Degraded Trace Warnings" | FR60-62 | FR60 → P2 |
| 11. Determinism Contract & Stability Surface (docs) | "Documentation Contracts Deliverables" | FR63-65 | All P1 |

Each epic should also reference:
- Its bound **ACs** (cross-listed in Section 2 — 9 unique IDs).
- Its dependent **ADRs** from the sidecar `adr-backlog-from-prd.md` (e.g., Epic 3 depends on ADR-005, ADR-006; Epic 6 depends on ADR-007, ADR-009, ADR-010, ADR-011, ADR-012).
- Its **NFR pressures** (e.g., Epic 1's stories must satisfy NFR-PERF-02; Epic 2's stories must satisfy NFR-PERF-03a/b/c/d, NFR-PERF-04; Epic 6's stories must satisfy NFR-SEC-01, NFR-PERF-05).

### Recommended stories per persona (preview — for use when epics are authored)

Stories should cover the persona Journey arcs already documented in PRD `## User Journeys`:

- **QA Engineer (Priya):** Journeys 1 + 2 stories cover FR1, FR5, FR6, FR9a, FR23a, FR24, FR25, FR26-28, FR45, FR49-52, FR54.
- **Agent Surface Author — MCP mode (Mei):** Journey 3 stories cover FR5-11, FR11b, FR16, FR19-23, FR32, FR34-37, FR55.
- **Agent Surface Author — Skill mode (Devon):** Journey 4 stories cover FR1-3, FR26-28, FR59 (P1); FR29a-c, FR60 (P2 — Judge-extended flow).
- **Agent Developer — Multi-step (Raj):** Journey 5 stories cover FR12-18, FR14-15, FR19-22, FR23a/b, FR39-40, NFR-PERF-03d (mcp_per_test trade-off), NFR-REL-05 (dogfood integration).
- **Contributor (Inês):** Journey 6 stories cover FR12, FR17a-c, FR18, FR45, FR47, FR48.

### Missing-prerequisite finding (for the report)

**Finding 3.1 (BLOCKING for full readiness):** Epic-level coverage map cannot be validated against the 65 PRD FRs because no epics document exists. To resolve: run `/bmad-create-epics-and-stories` consuming `prd.md` + `adr-backlog-from-prd.md` as inputs. The epic candidates table above is the recommended starting point.

**Finding 3.2 (RECOMMENDATION):** The "11 capability areas = 11 epics" mapping above is the PRD's natural decomposition; whoever authors the epics should challenge this default before adopting it (some areas may merit splitting — e.g., Area 6 Trace Recording could reasonably split into "Trace + Listener" + "MCP Observation" epics if the team capacity / sprint cadence calls for finer epic granularity).

**Finding 3.3 (NOTE):** Each epic must inherit the dependencies the PRD already documents — bound ACs, dependent ADRs, NFR pressures. The architecture step should produce these dependency edges; epic-breakdown can then anchor on them.

## Section 4: UX Alignment Assessment

### UX Document Status

**Not found AND intentionally skipped per PRD scope.** Discovery confirmed no `*ux*.md` files or `ux/` folder in `_bmad-output/planning-artifacts/`. `/bmad-create-ux-design` was NOT run, and was NOT intended to run.

### Is UX implied?

**No.** The product is an **open-source Robot Framework PyPI library** that exposes keywords for use in `.robot` test suites. The PRD scope explicitly establishes:

- **No UI surface.** Library output flows to Robot Framework's `output.xml`, HTML report, and `libdoc` keyword reference — these are RF Tooling's own surfaces, not bespoke UX.
- **No web/mobile components.** Per `## Product Scope > MVP > Explicitly out of scope`: "Not a hosted observability platform. No dashboards, no human-annotation UI, no regression-tracking SaaS."
- **No standalone CLI app for non-RF users.** Per same scope section: "Not for non-Robot-Framework users. No standalone CLI..." (Note: the library *does* ship `agenteval init` and `agenteval new-adapter` per FR52 / FR18 — these are scaffolding utilities, not user-facing applications.)

### UX-adjacent capabilities captured as FRs (not separate UX deliverable)

The PRD intentionally promoted what would have been "UX touchpoints" into first-class FRs, eliminating the need for a separate UX design step:

| UX touchpoint | Captured as |
|---|---|
| Evidence-block visual contract | **FR34b** (monospace fenced section, header + 3 subsections, 1000-char truncation; conformance-suite snapshot fixtures) |
| Cohort heatmap format | **FR55** (`CohortHeatmap.as_ascii()` / `as_dict()` Phase 1; `as_html()` Phase 2; ASCII format fixture) |
| OTel trace visual reference | **FR58** (sample trace visualization at `docs/contracts/otel-trace-visual.md` with Jaeger/Grafana Tempo screenshots + field mapping) |
| Terminal run summary format | **FR54** (pass/fail counts + cost + time-to-first-test + next-step hint, written to stderr) |
| Polling-error message text | **FR56** (4 required elements: keyword name + test file:line + remediation snippet + ADR link; conformance suite asserts presence) |
| Error message UX (Tier-1 setup failures) | **FR59** (path + line + remediation hint required) |
| Conformance report shape | **FR57** (JSON-on-stdout + human-summary-on-stderr) |
| Documentation contracts (5 of them) | NFR-MAINT-04 + FR58/FR63/FR64/FR65 (doc-build CI asserts required sections exist) |

### Alignment Issues

**None to report at this layer.** Since UX is not a separate deliverable, there's no UX↔PRD or UX↔Architecture misalignment risk to assess. The relevant alignment is *PRD's visual-contract FRs* ↔ *Architecture implementation* — to be validated in Section 5 when (if) Architecture is authored.

### Warnings

**None.** UX is correctly not in scope. The decision was explicit at PRD Step 9 and validated by the user (see PRD frontmatter `Persona Persona-split test` entry: "Skip /bmad-create-ux-design — library has no UI; FR34b + FR55 + FR58 are documented in PRD and need no separate UX deliverable.").

### Finding 4.1 (NOTE for architecture step)

When `/bmad-create-architecture` runs, it MUST inherit the visual contract commitments named in FR34b / FR55 / FR58 as design constraints — NOT treat them as "UI work" delegated to a future UX step. Architecture's role here is to specify the implementation surface (e.g., how `as_ascii()` renders unicode box-drawing chars on Windows where terminal encoding may degrade) that delivers on the visual contracts FRs already pin.

## Section 5: Epic Quality Review (forward-looking advisory)

### Status: BLOCKED for direct review — no epics exist

As in Section 3: epics document does not exist; review is converted into a **forward-looking advisory** applying epic-quality best practices proactively against the 11 candidate epics proposed in Section 3. The goal: flag specific risks the epic-author (`/bmad-create-epics-and-stories`) should design around.

### Best-practices applied: User value, independence, no forward dependencies, no technical-milestone epics

#### 🔴 Critical risks if Section 3's candidate epic list is adopted verbatim

**Risk 5.1 — Forward-dependency cascade across 7 of 11 candidate epics.**

The "11 capability areas = 11 epics" mapping in Section 3 is **structured by capability**, not by **dependency order**. Many of the proposed epics have hard dependencies on epics that come later in the capability-area numbering:

| Candidate Epic (Section 3) | Depends on | Issue |
|---|---|---|
| Epic 2 (MCP Server Dynamic Eval; FR7-11, FR11b) | Epic 3 for FR10a/b (Tool Discoverability needs a coding-agent adapter to drive trials) + FR11/FR11b (cost/runtime guardrails need adapter to monitor) | **Forward dependency.** Can split: 2a = MCP lifecycle (FR7-9) is independent; 2b = Tool Discoverability + guardrails (FR10/11/11b) requires Epic 3 |
| Epic 4 (Tool-Call Metrics; FR19-25) | Epic 3 (Metric. keywords read from `AgentRunResult.tool_calls` which only exist after agent runs) | **Hard forward dependency.** Cannot start Epic 4 without Epic 3 minimum (Generic adapter) |
| Epic 5 (Statistical Primitives + Tier Model; FR26-31) | Epic 3 + Epic 4 (Pass@k requires N runs from an adapter, plus metric extraction) | **Hard forward dependency** |
| Epic 6 (Trace + Observability; FR32-40) | Epic 3 (trace spans emit during agent runs) | **Hard forward dependency** |
| Epic 9 (Reporting/CI/First-Run; FR49-59) | Mixed — `agenteval init` (FR52) is independent; JUnit XML / exit codes / trace ID (FR49-51) require agent runs and assertion lifecycle, depend on Epics 3-6 | **Partial forward dependency.** Should split |
| Epic 10 (Honest Failure Reporting; FR60-62) | Epic 3 (adapter drift warning requires adapter infra); Epic 6 (DegradedTraceWarning requires trace) | **Hard forward dependency** |
| Epic 11 (Determinism Contract docs; FR63-65) | Domain Constraints §5 (PRD source for byte-identical-equality assertion); independent of code | **Acceptable** |

**Severity: critical.** Epic-author must re-order from "capability-area-grouped" to "dependency-clean greenfield-ready" or epics 4, 5, 6, 9, 10 will block sprint progress.

#### 🔴 Critical risk — Greenfield project-setup gap

**Risk 5.2 — No FR captures greenfield project-bootstrap stories.**

Greenfield projects per the step-05 spec require initial setup stories (project init, dev env config, CI/CD pipeline early). None of the 65 PRD FRs cover:

- `pyproject.toml` initial creation with hatchling build backend + PEP 621/735 dependency groups (per Developer Tool Requirements > Compatibility Matrix).
- `uv` lockfile generation + dev/optional dep groups (per Extras Matrix).
- GitHub Actions CI matrix scaffolding (Python 3.12 + 3.13 on Linux + macOS).
- PyPI trusted-publishing OIDC setup (per `## Developer Tool — Specific Requirements` mention).
- `_assertions/` kernel skeleton inheriting from `robotframework-agentguard` (the SHARED-SKELETON commitment from Executive Summary).
- ADR backlog ratification (10 ADRs from `adr-backlog-from-prd.md` → `docs/adr/`).
- `MAINTAINERS.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md` skeleton creation (per NFR-MAINT-01/02/03).

**These are not FRs because they are infrastructure scaffolding**, not user-facing capabilities. But they are MUST-HAVE Epic 0 / Epic 1 stories for a greenfield Phase 1. The epic-author MUST add a foundation epic before user-value epics.

#### 🟠 Major issues

**Issue 5.3 — Epic 3 "Coding Agent Adapters" is a borderline technical epic.**

Per the step spec, "Authentication System — borderline" is the canonical example. Epic 3 as currently proposed bundles 7 FRs (FR12 Protocol + FR13a-f per-adapter + FR14-18) into one "adapter infrastructure" epic. This:

- *Does* deliver user value (FR14 `Send Prompt` is a user-callable keyword; FR15 `Run Scenario` likewise).
- *But* the bulk of the work (Protocol design + 2 Phase-1 adapters + 4 Phase-2 adapters) is infrastructure rollout.
- **Recommendation:** split into Epic 3a (Generic adapter only; user can Send Prompt against any LiteLLM provider) and Epic 3b (Claude Code CLI adapter; user can Send Prompt against CC CLI). Each ships with end-to-end user-value examples (`uv add` → `Send Prompt` against echo MCP + Generic adapter → green). Phase-2 adapters become Epic 3c/3d/3e/3f or get consolidated as Epic 12 (Phase 2 Adapter Expansion).

**Issue 5.4 — Conformance suite (FR45) shipping in Phase 1 needs an Epic with no FRs of its own.**

FR45 says the conformance suite ships in Phase 1 as **contract publication** (not consistency enforcement) so community adapter authors have a runnable target Day 1. This is unusual: the suite has fidelity oracles (golden-trace fixtures) that REQUIRE adapters to test against. Phase 1 has only 2 adapters (Generic + CC CLI). The suite's user value in Phase 1 is *the act of publishing the contract*, not testing 2 adapters.

- **Recommendation:** Make the conformance suite a story in Epic 3 (alongside the first adapter), not its own epic. The suite's value emerges incrementally as adapters arrive — it's not an independent deliverable.

**Issue 5.5 — Documentation epic (Epic 11 in Section 3) needs slicing.**

FR63 + FR64 + FR65 are 3 different doc deliverables with different deadlines:
- FR63 (Determinism Contract doc): can be written immediately from PRD Domain Constraints §5 — Story 1 of any epic that opens.
- FR64 (Stability Surface doc): requires labels on every public-API element → must wait until Epic 1 first ships something to label.
- FR65 (0.x→1.0 Exit Criteria): final ratification at Phase 1 close per FR65 itself.

Treating these as a single "Docs Epic" creates timing mismatch. Each doc has a different correct epic placement.

#### 🟡 Minor concerns

**Concern 5.6 — Story sizing concerns for some FRs.**

A few FRs in the Section 3 mapping are too large for a single story:

- FR13b (Claude Code CLI adapter) — implementing `stream-json` live parsing + post-hoc conversation history + binary version validation + `mcp_servers=` integration + per-test scope is realistically 3-5 stories.
- FR45 (conformance suite with fidelity oracles + 8 assertion classes) — at least 5 stories (one per oracle class).
- FR10a (Tool Discoverability single-runtime) — full implementation including cohort table + per-task verdict matrix + failed-task evidence + competing-tool-picks extraction is 3-4 stories.

**Recommendation:** epic-author should plan story decomposition explicitly during `/bmad-create-epics-and-stories`. Stories must be sized for one sprint (one engineer, days not weeks).

**Concern 5.7 — Some FRs are pure config / declarations.**

FR42 (defaults documented) is a single config snippet. Not enough work for a story. Should be folded into FR41 (config precedence) as an AC.

### Best-practices compliance — forward-looking checklist

For the `/bmad-create-epics-and-stories` step downstream, here's the checklist to honor:

- [ ] **Epic order respects greenfield dependency chain.** Start with Foundation (config + library scaffolding + plugins API + ADR ratification + pyproject.toml + CI matrix setup). Then Static Inspection (no agent dep). Then Generic adapter + first Send Prompt + Run Scenario user value. Then metrics. Then statistics + tier model. Then trace + evidence-block legibility. Then Tool Discoverability + cost guards. Then CC CLI adapter. Then conformance suite oracles as Phase 2 adapters arrive. Then Phase 2 expansion.
- [ ] **Each epic delivers user value end-to-end** (with a runnable example, not just infrastructure).
- [ ] **No epic depends on a higher-numbered epic.** Validate by reading each epic's user-value statement in isolation: it must work with only earlier epics' outputs.
- [ ] **Stories within an epic are independently completable** within an epic-internal dependency chain (Story 1.1 alone; 1.2 with 1.1; 1.3 with 1.1+1.2; etc.).
- [ ] **Database / persistent state created when needed**, not upfront. (Less relevant here — the library is mostly stateless; in-memory trace store + JSONL backend per-test.)
- [ ] **Each AC is testable independently** (Given/When/Then or executable assertion).
- [ ] **FR↔Epic↔Story traceability preserved**: every FR has an epic; every epic story names which FRs it satisfies; every AC has a verifying test.
- [ ] **Greenfield setup story exists as Epic 1 Story 1.1**: covers pyproject.toml + uv lockfile + minimal CI matrix + `_assertions/` kernel skeleton from agentguard + `MAINTAINERS.md`/`CONTRIBUTING.md`/`SUPPORT.md`/`SECURITY.md` skeletons + 10-ADR ratification into `docs/adr/`.
- [ ] **Phase 1 vs Phase 2 boundary is at the EPIC level, not at the story level** within an epic (per Product Scope) — except for adapter epic and trace-backend epic where the split delivery is explicit.

### Section 5 findings summary

- **2 critical risks** (forward dependency cascade across 7 epics; greenfield setup gap).
- **3 major issues** (Epic 3 borderline technical; conformance suite epic placement; docs epic slicing).
- **2 minor concerns** (story sizing for large FRs; FR42 too small for a story).
- **8-item compliance checklist** for `/bmad-create-epics-and-stories` to honor.

**Net call:** the Section 3 candidate-epic mapping is a useful FR-to-area projection but **must not be adopted as the epic-delivery order**. The epic-author needs to re-derive the order from dependency analysis (which the Architecture step should produce), with a greenfield Foundation epic that the PRD doesn't capture in FRs.

## Section 6: Summary and Recommendations

### Overall Readiness Status

**Split status (honest framing):**

- **For PRD quality:** ✅ **READY.** The PRD is complete, internally consistent, traceability-clean, and testability-rule-compliant. Quality assessment in Section 2 passed all 11 evaluated dimensions.
- **For Phase-4 implementation:** ⚠️ **NOT READY.** Two prerequisite planning artifacts (Architecture, Epics & Stories) have not been authored yet. The PRD is *correctly positioned* to feed these next, but they must exist before code work begins.
- **For continuation of the planning pipeline:** ✅ **READY for next step.** The PRD + ADR sidecar are sufficient inputs to run `/bmad-create-architecture` immediately. No PRD remediation required before that step.

### Critical Issues Requiring Immediate Action

**None blocking the next planning step (`/bmad-create-architecture`).** The PRD is ready to feed it.

**5 issues to address BEFORE Phase-4 implementation can begin:**

| # | Issue | Section | Severity | Action owner |
|---|---|---|---|---|
| 1 | Architecture not authored — required for dependency analysis, ADR ratification, technical-feasibility traceability | §3 + §5 | 🔴 Critical | Run `/bmad-create-architecture` next |
| 2 | Epics & Stories not authored — required for sprint-level scope, FR coverage map, story-AC chain | §3 + §5 | 🔴 Critical | Run `/bmad-create-epics-and-stories` after architecture |
| 3 | Greenfield setup epic gap — no FR captures `pyproject.toml` / `uv` lockfile / CI matrix scaffolding / ADR ratification into `docs/adr/` / `MAINTAINERS.md` skeleton, but these are MUST-HAVE for Epic 0 / Epic 1 Story 1.1 | §5.2 | 🔴 Critical | Epic author MUST add Foundation epic; not an FR addition |
| 4 | Forward-dependency cascade if Section 3 candidate-epic mapping adopted verbatim — 7 of 11 candidate epics depend on later-numbered epics | §5.1 | 🟠 Major | Epic author MUST re-derive order from dependency graph (architecture step output) |
| 5 | Some FRs need story-decomposition planning during epic breakdown — FR13b (CC CLI adapter), FR45 (conformance suite), FR10a (Tool Discoverability) are each 3-5 stories not 1 | §5.6 | 🟡 Minor | Epic author should size stories explicitly per sprint capacity |

### Recommended Next Steps

1. **Run `/bmad-create-architecture`** with inputs: `prd.md` + `adr-backlog-from-prd.md` (sidecar). Architecture step should:
   - Ratify the 10 new ADRs (ADR-005..014) + 4 inherited (ADR-001..004) into `docs/adr/` with formal numbering.
   - Produce a dependency graph that informs the correct epic order (addresses Issue 4 above).
   - Specify the implementation surface for visual contracts (FR34b, FR55, FR58) so the epic-author treats them as design constraints, not delegated UX work (Finding 4.1).
   - Carry forward all 9 ACs as conformance-suite requirements (FR45 lists them); architecture must specify HOW each AC's oracle is implemented.

2. **Run `/bmad-create-epics-and-stories`** with inputs: `prd.md` + architecture output + this readiness report (for Section 5's forward-looking advisory). Epic-author MUST:
   - Add a Foundation Epic (Epic 0 or Epic 1.1) covering greenfield setup that the PRD's FRs don't capture (Issue 3 above).
   - Re-derive epic order from the architecture's dependency graph (NOT from Section 3's capability-area mapping verbatim).
   - Honor the 8-item compliance checklist at the end of Section 5.
   - Plan story decomposition for the large FRs flagged in §5.6 / §5.7.
   - Reference each story's bound FRs + ACs + ADRs + NFR pressures (per Section 3 epic candidate table).

3. **Re-run `/bmad-check-implementation-readiness`** after Architecture + Epics & Stories are authored. The full validation (FR coverage map, story quality, AC testability per story, NFR-bar coverage by epic) requires those artifacts. This PRD-only audit is a partial validation.

4. **Optional:** Run `/bmad-checkpoint-preview` between architecture and epic breakdown if substantive scope changes emerge.

### Final Note

This assessment identified **0 issues with the PRD** and **5 readiness issues for Phase-4 implementation** (2 critical missing prerequisites, 2 forward-looking warnings, 1 minor concern). Three of the five resolve naturally when the next two planning steps run (`/bmad-create-architecture` and `/bmad-create-epics-and-stories`). The remaining two (Issue 3 greenfield gap; Issue 4 forward-dependency cascade) are flagged as guidance for the epic-author when that step runs.

**The PRD is ready to feed the next planning step.** No PRD rework required.

**Phase-4 implementation is NOT ready** — two prerequisite planning artifacts remain to be authored. Estimated effort: `/bmad-create-architecture` is typically a single focused session; `/bmad-create-epics-and-stories` is typically a single-to-multi session depending on epic count and story granularity. Both should complete within 1-2 working days of focused planning effort, after which Phase-4 implementation can begin.

---

**Assessment auditor:** Claude (Opus 4.7, 1M context) acting as expert Product Manager
**Audit date:** 2026-05-16
**Report file:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-16.md`
**PRD audited:** `_bmad-output/planning-artifacts/prd.md` (status: complete)
**Audit scope:** PRD-only (user-elected; downstream artifacts not yet authored)





