---
title: "ADR Backlog Seeded from Architecture Step"
source: "_bmad-output/planning-artifacts/architecture.md (Step 2 advanced-elicitation)"
created: "2026-05-16"
status: "seeds — to be ratified at Phase 1 close alongside PRD-originated sidecar"
intent: |
  7 active architectural decisions surfaced during /bmad-create-architecture Step 2 advanced-
  elicitation (First Principles + Failure Mode Analysis + Architecture Decision Records methods);
  ADR-A4 retired 2026-05-17. Each entry is a SEED — Context, Decision, Rationale, Alternatives
  rejected, Consequences — sufficient for the Architectural Influences Catalog step (later in
  architecture workflow) to ingest. Final ratified ADRs live in `docs/adr/` once Phase 1
  implementation begins.

  Companion sidecar: `adr-backlog-from-prd.md` (10 PRD-originated ADRs ADR-005..014).
  Combined Phase 1 ADR slate: 1 Architectural Influences Catalog (catalogs ~14 reviewed patterns
  from robotframework-agentguard among other references) + 10 PRD-originated + 7 architecture-
  originated = 18 distinct agenteval-numbered ADRs in docs/adr/ (ADR-A4 retired 2026-05-17).

working_id_scheme: |
  These ADRs use working IDs `ADR-A1..A8` to distinguish from the PRD sidecar's `ADR-005..014`.
  Per Step-1 Hybrid ADR scheme decision (captured in architecture.md frontmatter
  step01Decisions.adrNumberingScheme), final agenteval ADR numbering renumbers everything:
    - agenteval ADR-001: Architectural Influences Catalog (catalogs ~14 reviewed patterns from
      robotframework-agentguard among other references; each evaluated on merit for agenteval)
    - agenteval ADR-002..011: 10 PRD-originated ADRs (PRD sidecar's ADR-005..014 renumbered)
    - agenteval ADR-012..018: 7 architecture-originated ADRs (this sidecar's ADR-A1/A2/A3/A5/A6/A7/A8 renumbered; ADR-A4 retired 2026-05-17)

new_modules_introduced:
  - "agenteval/_kernel/ (top-level kernel directory for cross-cutting helpers)"
  - "agenteval/_kernel/run_async.py (per ADR-A1)"
  - "agenteval/_kernel/discovery.py (per ADR-A2)"
  - "agenteval/_kernel/guardrails.py (per ADR-A5; @guarded_fanout decorator)"
  - "agenteval/_kernel/coverage.py (per ADR-A6; _check_mcp_coverage helper)"
  - "agenteval/errors.py (per ADR-A3; AgentEvalError base + 4 sub-bases + 9 leaves)"
  - "agenteval/security/protocols.py (per ADR-A8; SandboxBackend Protocol)"
  - "tests/conformance/ (per ADR-A7; per-AC test files + per-adapter parametrize + fixtures + harness)"

new_documentation_contracts:
  # These ADD to the 5 PRD-named contracts in NFR-MAINT-04 (total 9 — agentguard-inheritance.md retired 2026-05-17)
  - "docs/contracts/error-class-hierarchy.md (per ADR-A3)"
  - "docs/contracts/mcp-coverage-detection.md (per ADR-A6)"

ci_workflow_added:
  # agentguard-drift-check.yml retired 2026-05-17 along with ADR-A4 + NFR-MAINT-06.
  # Adding a security-scan.yml (CodeQL) in its place keeps the workflow count at 7.
  - ".github/workflows/security-scan.yml (CodeQL on every PR; standard hygiene)"
---

# ADR Backlog Seeded from Architecture Step (Phase 2 of Phase-3 Planning)

7 active ADRs surfaced via First Principles + FMA + ADR-method elicitation rounds at Step 2 of `/bmad-create-architecture`. Working IDs `ADR-A1..A8` (ADR-A4 retired 2026-05-17). Status: **Proposed (to be ratified at Phase 1 close).**

---

## ADR-A1: Async-to-Sync Bridge as Kernel Module (`_run_async`)

**Context.** 4+ sub-libraries call async libraries (MCP Python SDK, LiteLLM async paths, OpenTelemetry async exporter Phase 2, coding-agent SDKs). Each path needs consistent sync-to-async bridging in Robot Framework's sync keyword model. Without a single canonical bridge, each sub-library would reinvent the wheel with potentially incompatible fallback strategies under nested event loops.

**Decision.** `agenteval/_kernel/run_async.py` exposes a single `_run_async(coro)` helper mirroring agentguard precedent: `asyncio.run()` with worker-thread fallback for nested-loop contexts. `nest_asyncio` import path is opt-in for IDE runners only (documented but NOT imported by default).

**Rationale.** Single canonical bridge prevents per-sub-library reinvention. PRD explicitly bans `async def` keywords (RF 6.1+ async support too rough; complicates listener interactions per RF issue #4803) and `robotframework-async` third-party dep (unclear maintenance trajectory). agentguard's pattern is one reviewed reference (agenteval evaluates on merit; free to diverge).

**Alternatives rejected.**
- `async def` keywords using RF 6.1+ experimental support — too rough, complicates listener interactions.
- `robotframework-async` third-party dep — unclear maintenance trajectory.
- Per-sub-library async bridging — duplication; inconsistent fallback strategies risk drift over time.

**Consequences.** 1 kernel module to maintain; documented `nest_asyncio` workaround for IDE-integrated runners; per-keyword unit tests can mock async paths via dependency injection. Touches every sub-library that calls async libs — cross-cutting concern #9 from the architecture's Project Context Analysis.

---

## ADR-A2: Entry-Points Discovery Infrastructure (3 agenteval groups + 1 RF group + direct composition)

**Context.** 4 distinct entry-point discovery paths at library import time: `[project.entry-points."agenteval.coding_agents"]` (FR17a), `[project.entry-points."agenteval.providers"]` (FR17c), `[project.entry-points."agenteval.judges"]` (Phase 2 implicit), and `[project.entry-points."robot.listener"]` (FR33a). Plus 4th implicit `plugins=[]` direct-composition path (FR48 + FR17b). Without a unified discovery layer, each sub-library independently calling `importlib.metadata.entry_points` risks inconsistent precedence semantics and divergent error handling for partially-installed adapter packages.

**Decision.** `agenteval/_kernel/discovery.py` standardizes via stdlib `importlib.metadata.entry_points`. **Precedence:** `__init__` direct args > entry-points-discovered > defaults. Single discovery module handles all 4 entry-point groups + plugin composition. Raises `AdapterDiscoveryError(AgentEvalCompatError)` with `installed-vs-required-extras` hint when a partially-installed adapter package is encountered.

**Rationale.** stdlib mechanism (no `pkg_resources` dep — deprecated path). Precedence rule prevents entry-point shadowing of explicit user choices (Journey 6 Inês scenario). Partial-install hint reduces support burden — a common failure mode is "user installed `[claude]` extra but not `claude-agent-sdk`."

**Alternatives rejected.**
- Single composite entry-point — mixes coding_agent + provider concerns; couples discovery to namespace.
- Plugin-only mechanism (no entry-points) — breaks org-wide auto-discovery (Journey 6).
- Per-sub-library discovery — duplication, inconsistent precedence, divergent error messages.

**Consequences.** 4 entry-point groups documented in `pyproject.toml` template + contributor docs; error path tested in conformance suite (`tests/conformance/test_ac_*_discovery.py` parametrized over installed-extras scenarios); community adapter authors get a single documented registration pattern.

---

## ADR-A3: Error-Class Hierarchy (`AgentEvalError` base + 4 sub-bases + 9 leaves)

**Context.** 9 distinct error classes are raised across the library; FR49 (JUnit XML emission) and FR50 (exit-code mapping) need structured error information. Currently no common base class declared.

**Decision.** Common `AgentEvalError(Exception)` base with structured `error_code: str` field. 4 semantic sub-bases enable selective handling:

| Sub-base | Leaves | FR50 exit code |
|---|---|---|
| `AgentEvalSafetyError` | `SandboxRequiredError`, `ValidateOperatorDisallowed` | 3 |
| `AgentEvalBudgetError` | `CostExceededError`, `RuntimeBudgetExceededError` | 2 |
| `AgentEvalCompatError` | `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `AdapterDiscoveryError` (per ADR-A2) | 3 |
| `AgentEvalIntegrityError` | `PollingDisallowedError`, `IncompleteTraceError`, `TierViolationError` | 2 or 3 (per leaf) |

Single import path: `from agenteval.errors import AgentEvalError, AgentEvalBudgetError, ...`. Each leaf class sets its own `error_code` class attribute (e.g., `PollingDisallowedError.error_code = "POLLING_DISALLOWED"`).

**Rationale.** `try/except AgentEvalError` enables programmatic catch; `error_code` field drives FR50 exit-code mapping + FR49 JUnit XML `failure type` attribute; semantic sub-bases enable selective handling (`try/except AgentEvalBudgetError` to retry with smaller scope, `try/except AgentEvalIntegrityError` to fail fast). 4 sub-bases align with the 4 exit-code-distinct error families.

**Alternatives rejected.**
- Flat hierarchy (no semantic grouping) — consumers can't catch by category.
- Inherit from `RobotError` — couples to RF internals; breaks for non-RF programmatic use of the library.
- Per-sub-library base classes (`MCPError`, `SkillError`, etc.) — 4× more bases at sub-library boundary; no semantic value for users.

**Consequences.** `agenteval/errors.py` is one file; conformance suite validates `error_code` populated for every raised error class; documentation contract `docs/contracts/error-class-hierarchy.md` published as part of Phase 1 doc deliverables. Cross-cutting concern #11 from the architecture's Project Context Analysis. **Adds 1 new doc contract to NFR-MAINT-04's enumerated list.**

---

## ADR-A4: RETIRED 2026-05-17

See `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` for the reframing that retired this ADR. NFR-MAINT-06 retired in the same pass; no drift-check CI is needed because there is no dependency to drift-check. agenteval treats robotframework-agentguard as one reviewed pattern source among others (alongside wolfeidau/mcp-evals, lastmile-ai/mcp-eval, OpenTelemetry GenAI semconv, etc.) and is free to diverge from agentguard's choices whenever a different approach serves agenteval better.

---

## ADR-A5: Cost + Runtime Guardrail as `@guarded_fanout` Decorator

**Context.** Cost guardrail (FR11 / AC-DISCOVER-02) and runtime guardrail (FR11b / NFR-PERF-06) apply only to Tier-3 fan-out keywords (not kernel-level). Currently 3 keywords: `MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`. Phase 2 adds more fan-out keywords (`Stat.Mann Whitney U` comparison flows). Without a shared mechanism, each keyword would re-implement pre-flight estimation + mid-run metering with risk of divergent semantics.

**Decision.** `agenteval/_kernel/guardrails.py` exposes `@guarded_fanout(estimator=callable)` decorator. The decorator wraps any Tier-3 fan-out keyword. Decorator handles: (1) pre-flight estimation via the user-supplied `estimator` callable; (2) mid-run cost meter (USD via provider cost-tracking) + wall-clock meter; (3) raises `AgentEvalBudgetError` subclass (`CostExceededError` or `RuntimeBudgetExceededError`) on threshold breach. The `estimator` callable signature: `estimator(kwargs: dict) -> (cost_estimate_usd: float, runtime_estimate_seconds: float)`.

**Rationale.** Selective application (not every keyword needs it); shared estimation interface ensures consistent guardrail semantics across keywords; new fan-out keywords just add the decorator with their estimator function; estimator signature documented for community adapter authors who add custom fan-out keywords via `plugins=[...]` (FR48).

**Alternatives rejected.**
- Per-keyword guardrail re-implementation — duplication; risk of divergent semantics (one keyword measures cost differently from another).
- Base-class `GuardedFanoutKeyword` — RF keyword decoration is method-level not class-level; doesn't fit `DynamicCore` composition model.
- Kernel-level mandatory guardrails on all keywords — over-applies; static-inspection keywords don't need it.

**Consequences.** Single decorator in `agenteval/_kernel/guardrails.py`; estimator interface documented in contributor docs; conformance suite validates the decorator against deterministic mock provider with known cost/runtime characteristics. Cross-cutting concern #8 from the architecture's Project Context Analysis (selectively-applied shared pattern, not kernel-level).

---

## ADR-A6: Honesty Fields — Detection-failure Defaults to `external_mixed`

> **⚠️ HISTORICAL — superseded by ratified text.** This proposed text was ratified into `docs/adr/ADR-016-mcp-coverage-detection-default.md` on 2026-05-17 with D1 trust-floor + D4 adapter contract amendments from Story 0.1 spike. The text below is the original 2026-05-15 draft kept for traceability; see ADR-016 for the authoritative ratified version.

**Context.** `mcp_coverage` detection per adapter (AC-MCP-OBSERVE-01 / FR36b) requires reading external MCP configurations:
- Claude Code CLI adapter: parse `~/.claude.json` + project `.mcp.json` before run
- Copilot CLI adapter: parse `~/.copilot/mcp-config.json`
- Generic LiteLLM adapter: trivially `"library_only"` since LiteLLM doesn't speak MCP

Detection can fail: file missing, malformed JSON, permission denied, race condition mid-read. Adapter behavior on detection failure is a critical design choice.

**Decision.** Detection-failure default is `mcp_coverage="external_mixed"` (NOT `"library_only"`). Kernel-level enforcement at metric keyword entry point via shared `_check_mcp_coverage(run)` helper in `agenteval/_kernel/coverage.py` that raises `IncompleteTraceError` per FR37 unless `allow_external_mcp_blind=True` is set on the keyword call OR on the library `__init__`.

**Rationale.** Safer than `"library_only"` default — false positives (claiming full coverage when adapter couldn't actually check) would produce silent partial-truth metric reports, violating AC-MCP-OBSERVE-01's load-bearing principle ("loud refusal beats silent half-truth"). The user who explicitly accepts blindness via `allow_external_mcp_blind=True` keeps shipping; the user who doesn't know detection failed gets stopped before metrics produce wrong answers.

**Alternatives rejected.**
- Default `"library_only"` on detection failure — silent partial truth; violates AC-MCP-OBSERVE-01.
- Refuse to run on detection failure (raise `MCPCoverageDetectionError`) — too aggressive; breaks legitimate cases where the user knows there's no external MCP (e.g., in CI environments without any user-level config files).
- Three-state field (`"complete" | "library_only" | "unknown"`) — adds complexity; defers the decision rather than making it.

**Consequences.** Adapter authors implement detection per their CLI's config conventions; documentation contract `docs/contracts/mcp-coverage-detection.md` published; conformance suite injects detection-failure scenarios (e.g., missing `~/.claude.json` permission) and asserts `mcp_coverage == "external_mixed"` result. Cross-cutting concern #9 from architecture's Project Context Analysis (adapter-emitted data contract). **Adds 1 new doc contract to NFR-MAINT-04's enumerated list.**

---

## ADR-A7: Conformance Suite Organization — Per-AC Test Files + Per-Adapter Parametrize

**Context.** Conformance suite (FR45 / AC-CONFORMANCE-01 / AC-CONFORMANCE-02) tests every adapter against 9 ACs + structural shape (`AgentRunResult`, `ToolCallTrace`, `AgentRunMetadata`). Phase 1 has 2 adapters (Generic + Claude Code CLI); Phase 2 adds 4 more (Claude Agent SDK, OpenAI Agents SDK, Codex CLI, Copilot CLI); community Tier-2 adds adapters self-service. Without organizational discipline, the suite becomes unmaintainable at 10+ ACs × 6+ adapters.

**Decision.** Directory layout `tests/conformance/`:
- `test_ac_simplicity_01_evidence_block.py`, `test_ac_simplicity_02_keyword_idiom.py`, `test_ac_discover_01_cohort.py`, `test_ac_discover_02_cost_guardrail.py`, `test_ac_dogfood_01_replacement.py`, `test_ac_conformance_01_fidelity_oracles.py`, `test_ac_conformance_02_completeness.py`, `test_ac_mcp_observe_01_coverage.py`, `test_ac_mcp_observe_02_version_gate.py`, `test_ac_mcp_observe_03_per_test_scope.py` — one file per AC; pytest parametrizes each test over all registered adapters via `adapter_registry` fixture
- `test_structural_shape.py` — `AgentRunResult` / `ToolCallTrace` / `AgentRunMetadata` shape assertions
- `fixtures/<adapter_name>/<scenario_name>.json` — golden-trace fixtures per AC-CONFORMANCE-01
- `harness.py` — truncation-injection harness + mock-agent fixtures + `adapter_registry` fixture per AC-CONFORMANCE-02
- `__init__.py` — entry point: `python -m agenteval.conformance [--adapter <name>]` per FR45 / FR57

**Rationale.** AC-grouped tests map 1:1 to PRD-locked acceptance criteria — failures point directly to violated AC; per-adapter parametrize allows incremental adapter rollout (community adapter authors add their adapter to a registry, all test files auto-discover); published as importable test-discovery path so external community adapter authors run `python -m agenteval.conformance --adapter my_adapter` from outside agenteval's repo.

**Alternatives rejected.**
- Per-adapter test files (`test_generic_adapter.py`, `test_claude_code_cli.py`, ...) — replicates ACs across adapters; AC changes require N file updates.
- Per-capability-area files (`test_static_inspection.py`, `test_dynamic_eval.py`, ...) — mixes ACs; failures don't point to specific ACs; harder to maintain AC ↔ test traceability.
- Single monolithic `test_conformance.py` — unwieldy at 10+ ACs × 6+ adapters; failures pile into one test file.

**Consequences.** ~12 test files Phase 1 (9 AC files + ~3 structural-shape files); community adapter authors run `python -m agenteval.conformance --adapter my_adapter` per FR45 to verify their adapter; failures produce per-AC actionable reports per FR57 (JSON-on-stdout + human-summary-on-stderr). Architectural concern #11 from architecture's Project Context Analysis (test infrastructure deliverable, NOT cross-cutting kernel concern).

---

## ADR-A8: Sandbox Policy in Phase 1 — Policy + Gate + Protocol (Backends Deferred to Phase 3)

> **⚠️ HISTORICAL — superseded by ratified text.** This proposed text was ratified into `docs/adr/ADR-018-sandbox-phase-1-policy.md` on 2026-05-17 with NO spike-driven amendments (original text accepted as-is per Story 0.2 cross-cutting confirmation). The text below is the original 2026-05-15 draft kept for traceability; see ADR-018 for the authoritative ratified version.

**Context.** Per Step-1 decision (captured in architecture.md frontmatter `step01Decisions.sandboxPolicyScope`), sandbox policy moves from PRD-anticipated Phase 3 deferral into Phase 1 with a tighter scope: Phase 1 ships policy + gate + Protocol; Phase 3 ships bundled backend implementations. This ADR formalizes the decision.

**Decision.** Phase 1 ships:
1. Sandbox Policy adopted into agenteval's Architectural Influences Catalog (agenteval ADR-001) with `adopt` status (pattern borrowed from agentguard ADR-013, evaluated on merit).
2. `SandboxRequiredError(AgentEvalSafetyError)` raised when Tier-3 code-execution scenarios are requested without a configured sandbox backend.
3. `SandboxBackend` Protocol published in `agenteval/security/protocols.py` as part of contributor-facing API; minimal Protocol surface: `execute(code: str, language: str, timeout: float) -> SandboxResult`.
4. Default backend: `NullSandbox` raises `SandboxRequiredError` on every call (forces user to either configure a real backend or opt out explicitly).

Phase 3 ships: bundled sandbox backend implementations (Docker, ephemeral worktree, gVisor optionally).

**Rationale.** Policy + gate + Protocol have low implementation cost (~3 days) and high security-posture value — Day 1 sandbox-aware behavior even without backends; community contributors get the Protocol to implement their own backends in Phase 2 (any registered via `[project.entry-points."agenteval.sandboxes"]` — adds a 5th entry-point group; ADR-A2 to be updated). Deferring backends keeps Phase 1 implementation scope honest.

**Alternatives rejected.**
- Defer everything sandbox-related to Phase 3 (PRD's original framing) — leaves security posture incoherent in Phase 1; agenteval borrows agentguard's `validate` operator gate (per Architectural Influences Catalog) without the parallel sandbox gate.
- Ship a Docker backend in Phase 1 — Docker dep adds platform-specific install friction; bloats MVP install size; Windows + macOS Docker setup is non-trivial.
- Ship no policy, only the Protocol — confuses contributors about expected gate behavior; raises questions like "what happens if I don't configure a backend?"

**Consequences.** Epic-author MUST add Phase 1 story "Sandbox Policy + Gate + Protocol (NullSandbox default)" — surfaced in `implementation-readiness-report-2026-05-16.md` Section 5 (Issue 3 = greenfield setup gap; this is one specific gap-filler). PRD `## Product Scope > Vision — Phase 3` updated implicitly to reflect backend-only deferral; agenteval ADR-A8 modifies PRD scope as sanctioned architecture refinement. **Adds 1 new entry-point group (`agenteval.sandboxes`) to ADR-A2's enumerated list (4 → 5 groups).**

---

# Cross-cutting notes for the Architectural Influences Catalog step

- **All 7 active ADRs introduce new structural elements that must be reflected in agenteval's module layout (ADR-A4 retired 2026-05-17):**
  - New top-level kernel directory `agenteval/_kernel/` (4 modules: `run_async.py`, `discovery.py`, `guardrails.py`, `coverage.py`)
  - New `agenteval/errors.py` (1 module, ~12 classes)
  - New `agenteval/security/protocols.py` (Protocol surface)
  - New `tests/conformance/` directory (~12 test files + `fixtures/` + `harness.py`)
  - New `docs/contracts/error-class-hierarchy.md` + `docs/contracts/mcp-coverage-detection.md`

- **ADR-A2 will need updating** during Architectural Influences Catalog authoring when ADR-A8's `agenteval.sandboxes` entry-point group is added (4 groups → 5).

- **AC-MCP-OBSERVE-01 enforcement path** (FR37 `IncompleteTraceError`) is now formalized via ADR-A6's `_check_mcp_coverage(run)` kernel helper. Architecture step downstream should ensure this helper is called from every metric keyword via either decorator or explicit invocation pattern.

- **NFR-MAINT-04 documentation deliverables list grows by 2** (error-class-hierarchy, mcp-coverage-detection). Doc-build CI assertion must include these 2 new files. (agentguard-inheritance.md retired 2026-05-17.)

- **The Step-1 frontmatter decision `step01Decisions.sandboxPolicyScope`** is now ratified as ADR-A8 — both can co-exist (frontmatter as session-state record, ADR as decision-archive).
