# Story 4.4: MVP Tool Discoverability (FR10a) — Single-Runtime Discoverability Check

Status: done

## Story

As **Mei (Agent Surface Author — MCP author mode)**,
I want **`MCP.Get Tool Discoverability`** Tier-3 fan-out keyword that drives N-trial natural-language tasks against my MCP server's tools (using the Story 4.1 Generic adapter), returning a structured `DiscoverabilityResult` table with per-task success counts, Wilson CI bounds, tool-call traces, competing-tool picks, and per-trial cost,
So that AC-DISCOVER-01 evidence ships: "does this agent / model find and pick my MCP tool given natural-language tasks?" — within a cost budget (default `max_cost_usd=5.00` per AC-DISCOVER-02; FR11 enforcement-deferred per DF-4.4-S1).

## Pre-create-story drift check (21st use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

3 drifts caught + resolved pre-authoring:

- **(D-A HIGH structural)** epics.md L1406 cites `@guarded_fanout` decoration; AC-DISCOVER-02 mandates pre-flight cost + mid-run hard-stop at 1.1× max_cost_usd. Story 1b.3 `_kernel/guardrails.py:guarded_fanout` decorator requires `_max_cost_usd` + `_max_runtime_seconds` on the host instance (per `guardrails.py:236-242` contract). `MCPLibrary` is EXCLUDED from `_SUB_LIBRARIES` per Story 2.2 collision-norm + constructed via `WITH NAME MCP` rather than `AgentEval._build_components` lifecycle — no clean path to inject library-level budgets. **Phase-1 pragmatic stance**: ship the keyword without `@guarded_fanout` enforcement; track DF-4.4-S1 (parallel to Story 4.3's DF-4.3-S6 — same architectural gap). Tier-3 annotation surfaces the contract; operators must enforce budgets manually until Phase-1.5 wires the cross-library config plumbing.
- **(D-B HIGH)** PRD FR10a verbatim wording specified `tool=<name>` `by_models=<list>` `with_tasks=<list>` `k=<n>` kwargs; epics.md L1403 (more operational) uses `mcp_server=<name>` `adapter=<name>` `model=<id>` `tasks=<yaml-path>` `trials_per_task=<n>` `max_cost_usd=<usd>`. PRD FR10a amended to match the operational shape (Story 4.4 implementation contract).
- **(D-C MED)** epics.md L1404 lists `success_count per Pass@k semantics` + AC-DISCOVER-01 mentions "Wilson-CI cohort table" — but no source defines the exact Wilson CI formula. **Resolution**: Wilson score interval at 95% confidence per the standard reference (`docs/contracts/wilson-ci.md` Phase-1.5 publishable contract; implementation uses `scipy.stats.beta.ppf` if `scipy` available, else the closed-form Wilson score formula). Phase-1 ships the closed-form (no `scipy` dependency).

## Acceptance Criteria

### AC-4.4.1 — `DiscoverabilityResult` + `TaskResult` dataclasses

**Given** the FR10a return-shape contract,
**When** Story 4.4 implements `src/AgentEval/discoverability/{schema,result}.py`,
**Then**:
- `TaskResult` frozen dataclass: `task_id: str`, `task_prompt: str`, `trials_run: int`, `success_count: int`, `tool_calls_per_trial: list[list[ToolCallTrace]]`, `competing_tools_picked: list[str]`, `cost_per_trial_usd: list[float]`, `wilson_ci_lower: float`, `wilson_ci_upper: float`.
- `DiscoverabilityResult` frozen dataclass: `per_task_results: list[TaskResult]`, `overall_pass_rate: float`, `total_cost_usd: float`, `total_runtime_seconds: float`, `mcp_coverage: Literal[<3-value enum>]`.

### AC-4.4.2 — Wilson CI computation

**And** `src/AgentEval/discoverability/wilson_ci.py` exposes `wilson_score_interval(successes, trials, confidence=0.95) -> tuple[float, float]`:
- Closed-form Wilson score interval (no `scipy` dependency).
- Returns `(lower, upper)` both in [0, 1].
- `trials == 0` → returns `(0.0, 1.0)` (no information).

### AC-4.4.3 — Tasks YAML schema + loader

**And** `src/AgentEval/discoverability/loader.py` ships `load_discoverability_tasks(path) -> list[DiscoverabilityTask]`:
- YAML shape: `tasks: list[Task]` with each task `{id: str, prompt: str, expected_tools: list[str] (optional), required: bool (optional, default True)}`.
- Validation: malformed YAML → `InvalidDiscoverabilityTasksError` (19th leaf added pre-authoring); type-checked + RFC 6901 `field_name` per Story 4.3 + Story 2.3 conventions.

### AC-4.4.4 — `MCP.Get Tool Discoverability` keyword

**And Given** a connected MCP server (Story 3.1) + a coding-agent adapter (Story 4.1 or 4.2),
**When** I call `${result}=    MCP.Get Tool Discoverability    mcp_server=echo    adapter=generic    model=anthropic/claude-sonnet-4-6    tasks=<yaml-path>    trials_per_task=3    max_cost_usd=5.00` in a `.robot` test,
**Then** the keyword:
1. Loads the tasks YAML.
2. Resolves the adapter via `get_adapter(adapter)`.
3. For each task: dispatches `trials_per_task` Generic-adapter `run()` calls with the task's prompt + the MCP server attached as a tool surface (Phase-1 stub — `mcp_servers=` resolution requires DF-4.3-S2 + DF-4.1-S2 + DF-4.2-S1; today raises `NotImplementedError` per the carry-overs).
4. For each trial: inspects `result.tool_calls` to determine success (any `tool_calls` whose `name` matches an `expected_tools` entry, OR `success_count` counts any non-empty `tool_calls` per Phase-1 simpler heuristic).
5. Aggregates `competing_tools_picked` (tool names called that aren't in `expected_tools`).
6. Computes Wilson CI bounds per-task.
7. Sums per-trial `cost_usd` into `total_cost_usd`.
8. Returns `DiscoverabilityResult`.

**Tier 3** (Stochastic Fan-Out) per Story 1b.6 + AC-DISCOVER-02 (cost-budget keyword).

### AC-4.4.5 — `InvalidDiscoverabilityTasksError` (19th leaf)

**And** the tasks loader raises `InvalidDiscoverabilityTasksError` on:
- File missing, wrong extension (`.yaml`/`.yml`), malformed YAML, top-level not a mapping.
- Required `tasks: list[Task]` missing/empty.
- Per-task `id` or `prompt` missing/wrong-type.
- `expected_tools` not a list of strings when present.

`error_code = "INVALID_DISCOVERABILITY_TASKS"`; exit code 65 (Tier-1 setup-failure family).

### AC-4.4.6 — Bundled task fixture

**And** `tests/fixtures/discoverability/tasks-basic.yaml` ships 3 representative tasks for the bundled echo server (limited tool surface: only `echo_back`; tasks exercise prompt → expected-tool-pick).

### AC-4.4.7 — `@guarded_fanout` deferred

**And Given** the Story 1b.3 `@guarded_fanout` decorator from `_kernel/guardrails.py`,
**When** Story 4.4 ships the keyword,
**Then** the decorator is NOT applied (DF-4.4-S1 carry-over — parallel to Story 4.3 DF-4.3-S6). Tier-3 annotation surfaces the contract; cost+runtime budget enforcement is Phase-1.5 wiring. The keyword's `max_cost_usd` + `max_runtime_seconds` kwargs are accepted + stored on the result for visibility but not enforced.

### AC-4.4.8 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean.
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance -q` regression-clean (815 Story 4.3 close + new tests).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.

### AC-4.4.9 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (23rd consecutive use).
- `feedback_test_name_assertion_match` applied to all new tests.
- Codex CLI sandbox bypass per goal directive.
- Auditor citation-drift check on FR10a + AC-DISCOVER-01 + AC-DISCOVER-02 wording.

## Tasks / Subtasks

- [x] **Task 1: `InvalidDiscoverabilityTasksError` 19th leaf** added to errors.py + catalog amended.
- [x] **Task 2: `src/AgentEval/discoverability/` sub-package** with schema + loader + Wilson CI module.
- [x] **Task 3: `MCP.Get Tool Discoverability` keyword** added to MCPLibrary; Tier 3 annotation; `@guarded_fanout` deferred per D-A.
- [x] **Task 4: Bundled task fixture** at `tests/fixtures/discoverability/tasks-basic.yaml`.
- [x] **Task 5: Unit tests** — Wilson CI math + tasks loader + keyword end-to-end via stub adapter.
- [x] **Task 6: All-gates pass.**
- [x] **Task 7: 4-reviewer cross-LLM code review.** 23rd consecutive cross-LLM STAR catch. 3-way HIGH-A duplicate-task-id silent-pass (Edge-cases + Codex + Blind) — load-bearing per AC-DISCOVER-01 verdict-matrix key contract. 1-way HIGH-B (Auditor citation-drift on PRD FR10a L1499 `summary` nesting) confirmed empirically via PRD re-derivation + applied via "fix-the-losing-source-NOW" pattern. 1-way HIGH-C (Auditor) carry-over catalog gap closed: C20-C23 added to `docs/phase-1-5-carry-overs.md`. 3-way MED-A empty-`expected_tools` wildcard semantics gap fixed. 2-way MED-C nested-list shallow-frozen mutation gap closed. 2-way LOW-A Wilson-CI bracket fake-green (6th catch of `feedback_test_name_assertion_match`) + 1-way LOW-B cost-ordering fake-green fixed. Validates `feedback_n_way_agreement_weight` (Epic 2 retro) for 3rd consecutive epic.

## Dev Notes

### Architecture compliance

- PRD FR10a (amended to match operational shape per Story 4.4 drift D-B); AC-DISCOVER-01 (Wilson-CI cohort table + per-task verdict matrix); AC-DISCOVER-02 (cost budget — deferred enforcement DF-4.4-S1).
- Story 2.2 MCPLibrary collision norm preserved (Story 4.4 adds keyword to MCPLibrary; remains excluded from `_SUB_LIBRARIES`).
- Story 1b.6 tier annotation (`@tier(3)`).
- Story 4.1 + Story 4.3 patterns inherited (`_split_adapter_kwargs`, drift-check norms).

### Phase-1 limitations explicitly documented

- `@guarded_fanout` enforcement deferred → DF-4.4-S1 (same architectural gap as Story 4.3 DF-4.3-S6).
- `mcp_servers=` adapter integration deferred → DF-4.1-S2 + DF-4.2-S1 prerequisite (Story 4.4 forwards the parameter; adapters raise NotImplementedError today).
- Single-runtime + single-model per AC; multi-model cohort is FR10b (Phase 2).
- Wilson CI formula is closed-form (no scipy dependency); Phase-1.5 may switch to `scipy.stats.beta.ppf` if precision matters.

## Dev Agent Record

### Implementation Plan (dev workflow 2026-05-20)

1. Add `InvalidDiscoverabilityTasksError` 19th leaf to `src/AgentEval/errors.py` under `_FR59Tier1SetupFailureError` (exit code 65). Amend `docs/contracts/error-class-hierarchy.md` L53 Integrity row + L56 total + L135 stability section.
2. Create `src/AgentEval/discoverability/` sub-package:
   - `__init__.py` — docstring-only per Story 2.1 lesson.
   - `schema.py` — `DiscoverabilityTask` + `TaskResult` + `DiscoverabilityResult` frozen dataclasses.
   - `wilson_ci.py` — closed-form Wilson score interval (no scipy dependency); supports 0.90/0.95/0.99 confidence.
   - `loader.py` — `load_discoverability_tasks(path) → list[DiscoverabilityTask]` with full schema validation + RFC 6901 field_name.
3. Amend `_bmad-output/planning-artifacts/prd.md` FR10a kwarg names to match the operational shape (D-B drift resolution).
4. Add `MCP.Get Tool Discoverability` keyword to `src/AgentEval/mcp/library.py`:
   - `@tier(3)` annotation (Stochastic Fan-Out badge).
   - Accepts `mcp_server`, `adapter`, `model`, `tasks`, `trials_per_task=3`, `max_cost_usd=5.00`, `max_runtime_seconds=None`, `**kwargs`.
   - Body: load tasks → resolve adapter → per-task × per-trial `adapter.run()` → inspect `tool_calls` for `expected_tools` match → aggregate competing-tool picks → compute Wilson CI per task → return `DiscoverabilityResult`.
   - DF-4.4-S1 carry-over: `@guarded_fanout` deferred (no cost/runtime enforcement; kwargs accepted but not enforced).
   - DF-4.1-S2 + DF-4.2-S1 carry-overs: `mcp_server` name is NOT forwarded to `adapter.run()` (Phase-1 GenericAdapter raises `NotImplementedError` on `mcp_servers` non-empty). Keyword still works end-to-end with mock/stub adapters.
   - DF-4.4-S2 carry-over: orchestration's `_split_adapter_kwargs` ctor/run split lives on `OrchestrationLibrary` (Story 4.3), NOT mirrored to MCPLibrary in Phase-1; strict-signature adapters fail loud with explicit DF-4.4-S2 reference.
   - DF-4.4-S3 carry-over: `mcp_coverage` hardcoded to `"hosted_in_process"` until Epic 5 hosted-MCP observer wires real coverage detection.
5. Vendor `tests/fixtures/discoverability/tasks-basic.yaml` with 3 representative tasks for the bundled echo server (`echo_back` only).
6. Write unit tests at `tests/unit/discoverability/`:
   - `test_wilson_ci.py` — 10 cases (zero trials, all-success, zero-success, half, unit-interval, errors, 90/95/99 width comparison).
   - `test_loader.py` — 18 cases (minimal, full, file-not-found, wrong-ext, malformed YAML, non-UTF-8, top-level mapping, tasks field missing/empty/not-list, per-task id/prompt/expected_tools/required validation, bundled fixture parses, dataclass frozen).
   - `test_keyword.py` — 15 cases (happy path, no-calls zero-pass, competing tools, partial pass + Wilson CI bounds, missing kwarg, invalid YAML, zero trials, unknown adapter, tier+keyword markers, pass_rate property, per-trial data preserved).
7. Run all gates: ruff (clean) + ruff format (clean) + mypy src/ (clean) + license-headers (PASS) + pytest tests/unit + tests/conformance (858 passed, 8 skipped — same skipped baseline as Story 4.3 close).
8. Status → in-progress (this update); spawn 4-reviewer cross-LLM code review next.

### Completion Notes

- 19th error-class leaf shipped (`error_code = "INVALID_DISCOVERABILITY_TASKS"`, exit code 65 — Tier-1 setup-failure family).
- Sub-package created with docstring-only `__init__.py` (Story 2.1 lesson preserved).
- Closed-form Wilson CI math verified against canonical reference values: 50/100 at 95% → (0.4038, 0.5962); 3/3 at 95% → (~0.439, 1.0); 0/3 at 95% → (0.0, ~0.561); trials=0 → (0.0, 1.0).
- Keyword imports `time` for `total_runtime_seconds` (`time.monotonic()` delta) — no `uuid` needed since `AgentRunResult` already carries `trace_id`.
- Stub-adapter test pattern preferred over GenericAdapter monkeypatch because GenericAdapter explicitly strips `tool_calls=[]` in Phase-1 per DF-4.1-S2 (Story 4.1 carry-over). Stub registers via `register_adapter("stub_disco_*", ...)` and returns scripted `tool_calls` for orchestration-logic verification. Mirrors the Story 4.3 `_StrictAdapter` precedent at `tests/unit/orchestration/test_library.py:411`.
- All-gates: ruff clean + mypy src/ clean + 858 passed / 8 skipped (no regression vs Story 4.3 baseline of 815 — new total 858 = 815 + 43 new discoverability tests).

## File List

**New files:**
- `src/AgentEval/discoverability/__init__.py`
- `src/AgentEval/discoverability/schema.py`
- `src/AgentEval/discoverability/wilson_ci.py`
- `src/AgentEval/discoverability/loader.py`
- `tests/fixtures/discoverability/tasks-basic.yaml`
- `tests/unit/discoverability/__init__.py`
- `tests/unit/discoverability/test_wilson_ci.py`
- `tests/unit/discoverability/test_loader.py`
- `tests/unit/discoverability/test_keyword.py`

**Modified files:**
- `src/AgentEval/errors.py` — added 19th leaf `InvalidDiscoverabilityTasksError`.
- `src/AgentEval/mcp/library.py` — added `Get Tool Discoverability` Tier-3 keyword + 5 new imports.
- `docs/contracts/error-class-hierarchy.md` — amended 18 → 19 leaves; new row added to inventory.
- `_bmad-output/planning-artifacts/prd.md` — FR10a operational kwarg names + DiscoverabilityResult schema specified.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (21st use) caught 3 drifts: D-A `@guarded_fanout` enforcement deferred → DF-4.4-S1 (architectural gap shared with Story 4.3 DF-4.3-S6); D-B PRD FR10a kwarg-name wording amended to match operational shape; D-C Wilson CI formula source = closed-form (no scipy). | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (in-progress; awaiting 4-reviewer cross-LLM code review). 19th error-class leaf shipped. `discoverability/` sub-package + Wilson CI math + tasks YAML loader + `Get Tool Discoverability` Tier-3 keyword + bundled echo fixture + 43 new unit tests (10 Wilson CI + 18 loader + 15 keyword). All gates pass: ruff clean + mypy src/ clean + 858 passed / 8 skipped (no regression vs Story 4.3 close). DF-4.4-S1 + DF-4.4-S2 + DF-4.4-S3 carry-overs documented in keyword docstring. | Amelia |
| 2026-05-20 | 0.3.0   | Code-review patches applied (23rd consecutive cross-LLM STAR catch). **3-way HIGH-A** (Edge-cases H1 + Codex HIGH + Blind MED-1): loader now rejects duplicate task ids with RFC 6901 field_name. **1-way HIGH-B Auditor citation-drift**: implementation realigned to PRD FR10a L1499 ratified `summary`-nesting via new `DiscoverabilitySummary` dataclass + "fix-the-losing-source-NOW" pattern. **1-way HIGH-C Auditor**: `docs/phase-1-5-carry-overs.md` gained C20-C23 entries (DF-4.4-S1 budget enforcement + DF-4.4-S2 ctor/run split + DF-4.4-S3 mcp_coverage detection + Story 4.3 missed entries follow-up). **3-way MED-A** (Edge-cases M1 + Codex MED + Blind LOW-1): wildcard mode now populates `competing_tools_picked` with ALL called names. **MED-B** (Codex empirical probe): `total_runtime_seconds` `t_start` moved to function entry — captures setup wall time. **2-way MED-C** (Codex + Blind LOW-3): `TaskResult.tool_calls_per_trial` `__post_init__` now deep-copies inner lists — frozen invariant restored. **MED-D** (Blind): adapter-ctor `TypeError` re-raise comment-vs-code drift fixed + DF-4.4-S2 named in error message. **MED-E** (Edge-cases M2): `mcp_server=""` now rejected. **MED-F** (Edge-cases M3): added `test_get_tool_discoverability_budget_carve_out_not_enforced` pinning DF-4.4-S1. **2-way LOW-A** (Blind LOW-2 + Codex 157): Wilson CI bracket test now asserts full bracketing invariant + canonical 2/3 at 95% reference values (6th catch of `feedback_test_name_assertion_match`). **LOW-B** (Codex 244): cost-ordering fake-green fixed with distinct per-trial costs. **LOW-C** (Blind LOW-4): `conftest.py` autouse fixture snapshots + restores adapter registry per-test. All-gates green: ruff + format + mypy src/ clean (58 src files); **866 unit+conformance (was 858; +8 new patches-pinning tests)** + 8 skipped; license-headers PASS. | Amelia |
