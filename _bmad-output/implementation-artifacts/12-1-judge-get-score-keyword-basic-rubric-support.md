# Story 12.1: Judge.Get Score Keyword + Basic Rubric Support

Status: done

## Story

As **Devon (Agent Surface Author)** or **Raj (Agent Developer)** running Tier-2 LLM-deterministic scoring on an agent run,
I want a `Judge.Get Score` keyword that evaluates an `AgentRunResult` against a written Markdown rubric using an LLM judge,
so that I can apply LLM-deterministic scoring (with seed + temperature=0 reproducibility) to agent outputs — closing Devon's Tier-2 slot in his three-tier stacked validation flow (Tier-1 static from Story 2.1 + Tier-2 LLM-deterministic here + Tier-3 cohort discoverability from Story 7.2).

## Pre-create-story drift check (48th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-27)

10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM from Epic 11 review records (general patterns applicable to any new keyword surface). **100% real-drift catch rate intact across 48 consecutive uses.** First Epic 12 story; no immediately-prior same-surface story for `feedback_cross_story_upstream_lesson_propagation` propagation (Stories 11.x were subprocess CLI adapters; Story 12.1 is a Tier-2 LLM-judge keyword — different surface).

- **D-1 (HIGH):** epics.md AC-12.1 + PRD FR48 mandate `@tier(2)` + `@guarded_fanout`. **Decision:** `JudgeLibrary` is wired via `AgentEval/_SUB_LIBRARIES` (the standard composition path used by `StatsLibrary` / `OrchestrationLibrary` etc.) — NOT via `WITH NAME` like `MCPLibrary`. This means `@guarded_fanout` works via the host-instance plumbing (`self._max_cost_usd` / `self._max_runtime_seconds` forwarded from `AgentEval.__init__`) — the MCPLibrary 8-epics-old carve-out (Epic 11 retro Action #3 / DF-4.4-S1 / C20) is SPECIFIC to MCP's composition path and does NOT block Story 12.1.

- **D-2 (HIGH):** epics.md AC-12.1 invocation example: `judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6`. The existing `GenericAdapter` at `src/AgentEval/coding_agent/generic.py` is a single-shot LLM caller via `LLMProviderAdapter` (LiteLLM in Phase-1). **Decision:** `Judge.Get Score` constructs an `AdapterDiscoveryError`-resolved adapter via `_kernel/discovery.get_adapter(judge_adapter)`, runs ONE call with `prompt=<assembled_rubric_prompt>`, and parses the response. **NOT** a multi-turn agent — single LLM call per rubric application.

- **D-3 (HIGH):** epics.md AC-12.1 + architecture L1316 mandate `JudgeScore` dataclass shape: `numeric_score: float` (0-10), `pass_threshold_met: bool`, `reasoning: str`, `criteria_breakdown: dict[str, float]`, `cost_usd: float`. **Decision:** ship the dataclass at `src/AgentEval/judge/types.py` (per architecture L1316 file home) as a `@dataclass(frozen=True)` mirroring the Story 1b.4 type discipline. Validate `0.0 <= numeric_score <= 10.0` in `__post_init__`.

- **D-4 (HIGH — `feedback_listener_hook_api_surface_empirical_check` UPSTREAM N=4):** The LLM judge response shape is the surface this norm specifically protects (Epic 11 Story 11.1 kilo HIGH-1 catch class). **Decision:** the judge prompt MUST instruct the LLM to return a strict JSON object matching the `JudgeScore` shape. Parse the response defensively: surface `JudgeOutputParseError` (new error leaf) when JSON parse fails OR shape mismatches. Phase-1 carve: NO retry loop on parse failure — the operator's seed+temperature=0 should make the response deterministic; if the model fails to format, the test should fail loud.

- **D-5 (MED):** Mock provider semantics — `MockProvider` returns echo-style text + empty `tool_calls` + zero usage. For Judge unit tests to be deterministic, the Mock provider's response MUST be controllable per-test. **Decision:** the Mock provider already supports a per-test response-text override via `MockProvider(response_text=...)` (verify in implementation). Unit tests inject the exact `JudgeScore` JSON the judge should produce.

- **D-6 (MED — review-time catalog gate UPSTREAM Epic 11):** Anticipate inline `DF-12.1-SX` references in the new code. **Decision:** pre-emptively surface DF-12.1-S1 (Markdown rubric Phase-2 YAML schema) in the carry-over catalog BEFORE invoking code-review (Action #2 sub-pattern from Epic 11 retro).

- **D-7 (MED):** epics.md AC-12.1 + architecture L613 + `pyproject.toml` L143 reference `[project.entry-points."agenteval.judges"]` (declared but no entries in Phase-1). **Decision:** add the canonical `generic = "AgentEval.judge.library:JudgeLibrary"` entry-point — but the judge keyword family is INSIDE the library, not a separate Adapter. The `agenteval.judges` group was declared as forward-compat for plug-in judges (Phase-2 work; not yet exercised). Phase-1: declare-only / no entry; the JudgeLibrary is registered via `_SUB_LIBRARIES` like StatsLibrary, NOT via entry-points. **Decision:** leave `agenteval.judges` empty in Phase-1.5; revisit in Phase-2 plug-in epic.

- **D-8 (MED):** Rubric format. epics.md AC-12.1 uses `rubric=tests/fixtures/rubrics/skill-quality.md` (Markdown). PRD FR48 + architecture mention "calibration discipline." **Decision:** Phase-1 Markdown rubric format with structured sections: `## Criteria` (one-line `- criterion-name: description` bullets), `## Threshold` (single-line `Pass if numeric_score >= N`), `## Examples` (optional `### Example N` headers — not parsed by Phase-1 helper, just human-readable context). DF-12.1-S2 carry-over tracks Phase-2 YAML schema if operators want richer structure.

- **D-9 (LOW — `trace_id=""` Phase-1 placeholder discipline UPSTREAM Story 11.2):** Judge.Get Score returns `JudgeScore`, NOT `AgentRunResult` — so the underlying LLM call's `trace_id` is not surfaced in the returned dataclass. **Decision:** the underlying single-shot adapter call carries `trace_id` per usual; `JudgeScore` doesn't need a `trace_id` field (different return shape). No placeholder issue.

- **D-10 (LOW — thread-safety class docstring UPSTREAM Story 11.1 + 11.2):** `JudgeLibrary` will hold host-instance budgets via `_max_cost_usd` + `_max_runtime_seconds`. Same pattern as `StatsLibrary` (which doesn't carry an explicit thread-safety paragraph — implicitly thread-safe via the host-instance read-only access pattern). **Decision:** add a brief "Thread safety: budgets are read-only after `__init__`; safe for concurrent `Get Score` calls on the same instance" note to the class docstring.

## Acceptance Criteria

### AC-12.1.1 — `JudgeLibrary` keyword surface

`src/AgentEval/judge/library.py` ships `JudgeLibrary` class with `@library(scope="GLOBAL")` decorator + one keyword:

- `Judge.Get Score(*, result, rubric, judge_adapter="generic", judge_model=None, **adapter_kwargs) -> JudgeScore` — `@tier(2)` + `@guarded_fanout()`.

The keyword:
- Resolves the judge adapter via `_kernel/discovery.get_adapter(judge_adapter)`.
- Loads the rubric via `_kernel/rubric_loader.load_rubric(rubric)` (new helper at `src/AgentEval/judge/rubric.py`).
- Assembles the judge prompt = system instructions ("you are an LLM judge; return strict JSON") + rubric text + agent response from `result.response_text` + optional tool-call trajectory summary.
- Calls `adapter.run(prompt=<assembled>, model=judge_model, ..., **adapter_kwargs)` (single-shot).
- Parses the response as a `JudgeScore` JSON; raises `JudgeOutputParseError` on parse/shape failure.
- Returns `JudgeScore(numeric_score, pass_threshold_met, reasoning, criteria_breakdown, cost_usd)`.

### AC-12.1.2 — `JudgeScore` dataclass

`src/AgentEval/judge/types.py` ships `JudgeScore` as a `@dataclass(frozen=True)`:

```python
@dataclass(frozen=True)
class JudgeScore:
    numeric_score: float          # 0.0 - 10.0
    pass_threshold_met: bool
    reasoning: str
    criteria_breakdown: Mapping[str, float]
    cost_usd: float
```

`__post_init__` validates: `0.0 <= numeric_score <= 10.0` (raises `ValueError` on out-of-range); `cost_usd >= 0.0`; defensive `dict()` copy of `criteria_breakdown` per Story 1b.2 M_R6 pattern.

### AC-12.1.3 — Rubric loader

`src/AgentEval/judge/rubric.py` ships `load_rubric(path) -> JudgeRubric` where `JudgeRubric` is a `@dataclass(frozen=True)` with: `criteria: tuple[tuple[str, str], ...]` (ordered name + description pairs), `threshold: float`, `raw_text: str` (preserves the full rubric for the LLM prompt).

The loader parses Markdown rubrics with sections:
- `## Criteria` — bullets `- name: description` parsed line-by-line.
- `## Threshold` — single line `Pass if numeric_score >= N` (regex extract).
- `## Examples` — passed through verbatim in `raw_text` (not parsed into fields).

Raises `InvalidJudgeRubricError` (new error leaf) on missing sections OR malformed bullets OR unparseable threshold.

### AC-12.1.4 — `JudgeOutputParseError` + `InvalidJudgeRubricError` error leaves

`src/AgentEval/errors.py` extended with 2 new leaves:

- `JudgeOutputParseError(AgentEvalCompatError)` — `JUDGE_OUTPUT_PARSE` exit code `65` (EX_DATAERR — data shape error). Carries: `raw_response: str`, `parse_error: str`, `fix_suggestion: str` (per FR59). Has a custom `__str__` truncating `raw_response` at 500 chars per `feedback_honest_framing` (no log-spam from long LLM responses).
- `InvalidJudgeRubricError(_FR59Tier1SetupFailureError)` — `INVALID_JUDGE_RUBRIC` exit code `65` (EX_DATAERR). Carries: `file_path: str`, `line_number: int | None`, `field_name: str`, `fix_suggestion: str`. **In-flight spec amendment 2026-05-27** per `feedback_in_flight_spec_amendment`: original AC text specified `AgentEvalCompatError` parent + `path`/`field_name`/`fix_suggestion` attrs; dev chose `_FR59Tier1SetupFailureError` parent (Tier-1 setup-failure semantics, sibling to `InvalidScenarioYAMLError` per `error-class-hierarchy.md`) + `file_path`/`line_number`/`field_name`/`fix_suggestion` attrs. Reason: rubric loading happens BEFORE keyword execution begins (FR59 Tier-1 setup-failure semantics — same family as YAML schema validation); `_FR59Tier1SetupFailureError` is the correct parent. Surfaced by Story 12.1 Tier-2 Opus MED-1.

`docs/contracts/error-class-hierarchy.md` amended with the 2 new leaves under the catalog table.

### AC-12.1.5 — `_SUB_LIBRARIES` integration

`src/AgentEval/__init__.py` amended:
- `_SUB_LIBRARIES` adds `judge = JudgeLibrary` (registered via the standard composition path).
- `_build_components(...)` forwards `max_cost_usd` + `max_runtime_seconds` to `JudgeLibrary(...)` via `host_instance` plumbing per the Story 4.3 + StatsLibrary precedent.

### AC-12.1.6 — Unit tests (≥15 tests; Mock provider deterministic)

`tests/unit/judge/test_library.py` MUST cover:

- `JudgeScore` dataclass: in-range numeric_score accepted; out-of-range raises `ValueError`; negative cost raises; defensive dict copy.
- Rubric loader: valid Markdown rubric parses to `JudgeRubric`; missing `## Criteria` raises; missing `## Threshold` raises; malformed bullet raises; unparseable threshold raises.
- `Judge.Get Score`: Mock provider injected with a synthetic JudgeScore JSON response → returns matching `JudgeScore` dataclass.
- `Judge.Get Score`: Mock provider returns malformed JSON → raises `JudgeOutputParseError`.
- `Judge.Get Score`: Mock provider returns JSON missing required field → raises `JudgeOutputParseError`.
- `Judge.Get Score`: Mock provider returns `numeric_score=11.0` (out of range) → raises `ValueError` via `JudgeScore.__post_init__`.
- `Judge.Get Score`: `pass_threshold_met` computed correctly from `numeric_score >= rubric.threshold`.
- `Judge.Get Score` is decorated with `@tier(2)` (introspectable via `get_keyword_tier`).
- `Judge.Get Score` is decorated with `@guarded_fanout()` (host-instance budget plumbing works — synthesize a budget-exceeded scenario in a unit test).
- `JudgeLibrary` registered in `_SUB_LIBRARIES` (importable via `AgentEval`-top-level).
- Entry-point smoke: NO `agenteval.judges` entry-point added in Phase-1 (verify list is empty).

### AC-12.1.7 — Integration test gated behind env flag

`tests/integration/test_judge_live.py` skipped unless `AGENTEVAL_INTEGRATION_TESTS=1` AND a real provider's credentials are available. The live test runs `Judge.Get Score` against `anthropic/claude-sonnet-4-6` (or whatever `judge_model` resolves) with a small fixture rubric + asserts a non-empty `JudgeScore` returns.

### AC-12.1.8 — Stability surface

`docs/contracts/stability-surface.md` amended: add `JudgeLibrary.Get Score` + `JudgeScore` + `JudgeRubric` + `load_rubric` at `experimental` (Phase-2 surface; promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3).

### AC-12.1.9 — All-gates pass

- `uv run pytest tests/ -q --no-header` — 1696 + ≥15 new = ≥1711 passed + 12 skipped (was 1696 + 12 at Epic 11 close).
- `uv run ruff check src/ tests/` + `uv run ruff format --check src/ tests/` — clean.
- `uv run mypy src/` — expected `Success: no issues found in ≥102 source files` (99 + `judge/library.py` + `judge/types.py` + `judge/rubric.py`).

### AC-12.1.10 — `feedback_carry_over_catalog_gate` UPSTREAM (29th consecutive)

Surface DF-12.1-S1 (Phase-2 YAML rubric schema) + DF-12.1-S2 (entry-point plug-in judges) entries in `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review. Catalog total after this story: 78 → 80.

### AC-12.1.11 — Cross-story UPSTREAM lesson propagation (3rd application of the now-CONFIRMED norm; first Epic 12 story)

Story 12.1 is the first Epic 12 story; no IMMEDIATELY-prior same-surface story. However, GENERAL patterns from Epic 11 reviews are applied UPSTREAM:

- D-4 (Story 11.1 kilo HIGH-1 `feedback_listener_hook_api_surface_empirical_check`): the LLM response shape is the surface the norm protects. AC-12.1.6 mandates explicit JSON-shape parsing + `JudgeOutputParseError` on shape mismatch.
- D-10 (Story 11.1 + 11.2 MED-3 thread-safety): class docstring carries a brief thread-safety note.
- D-6 (Story 11.2 + 11.3 review-time catalog gate sub-pattern): DF-12.1-S1 + DF-12.1-S2 pre-emptively catalogued.
- General `feedback_test_name_assertion_match`: every test name's promise delivers on the assertion body.

## Tasks / Subtasks

- [ ] **Task 1** — Add `JudgeOutputParseError` + `InvalidJudgeRubricError` to `src/AgentEval/errors.py`; amend `docs/contracts/error-class-hierarchy.md`.
- [ ] **Task 2** — Implement `src/AgentEval/judge/types.py` with `JudgeScore` + `JudgeRubric` dataclasses.
- [ ] **Task 3** — Implement `src/AgentEval/judge/rubric.py` with `load_rubric(path)` + Markdown parser.
- [ ] **Task 4** — Implement `src/AgentEval/judge/library.py` with `JudgeLibrary` + `Get Score` keyword.
- [ ] **Task 5** — Amend `src/AgentEval/__init__.py` `_SUB_LIBRARIES` + `_build_components` for JudgeLibrary integration.
- [ ] **Task 6** — Create `tests/fixtures/rubrics/skill-quality.md` (canonical Phase-1 rubric example).
- [ ] **Task 7** — Implement `tests/unit/judge/test_library.py` + `tests/unit/judge/test_rubric.py` + `tests/unit/judge/test_types.py` covering AC-12.1.6 cases (≥15 tests across the 3 files).
- [ ] **Task 8** — Implement `tests/integration/test_judge_live.py` per AC-12.1.7 (env-gated).
- [ ] **Task 9** — Amend `docs/contracts/stability-surface.md` adding the 4 new surfaces at `experimental`.
- [ ] **Task 10** — Pre-write fake-green precheck per `feedback_test_name_assertion_match`.
- [ ] **Task 11** — Carry-over catalog gate UPSTREAM (29th consecutive): surface DF-12.1-S1 + DF-12.1-S2 entries in `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review.
- [ ] **Task 12** — All-gates run (pytest + ruff + mypy).

## Dev Notes

### Source citations + drift context

- **PRD FR48** (Judge.Get Score with rubric calibration).
- **epics.md L2085-2099** (Story 12.1 AC).
- **architecture.md L613, L983, L1312-1316** (Judge sub-library file homes + `JudgeRubric` / `JudgeScore` types).
- **`AgentEval/_kernel/discovery.get_adapter`** — entry-point-discovered adapter resolution (Story 1b.3); same path used by StatsLibrary.
- **`AgentEval/_kernel/guardrails.guarded_fanout`** — decorator at `_kernel/guardrails.py`; works via host-instance `_max_cost_usd` + `_max_runtime_seconds` plumbing.
- **`AgentEval/coding_agent/generic.py:GenericAdapter`** — the default `judge_adapter=generic` implementation; LiteLLM-backed single-shot LLM caller.
- **`AgentEval/providers/mock.py:MockProvider`** — Mock provider for deterministic unit tests; supports `response_text=...` override per-instance.
- **`AgentEval/stats/library.py:StatsLibrary`** — canonical `_SUB_LIBRARIES`-registered, `@guarded_fanout`-using library precedent.

### Phase-1 limitations explicitly documented

- Markdown rubric format (Phase-1); YAML schema deferred to DF-12.1-S1 / C79.
- `agenteval.judges` entry-point group declared empty (Phase-1); plug-in judges deferred to DF-12.1-S2 / C80.
- NO retry loop on `JudgeOutputParseError` — seed+temperature=0 expected to make response deterministic.
- Single-shot LLM call (no multi-turn agent loop); Phase-2 may extend for chain-of-thought rubric.

### Existing files this story modifies

- `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` + `_build_components`.
- `src/AgentEval/errors.py` — 2 new leaves.
- `docs/contracts/error-class-hierarchy.md` — 2 new catalog rows.
- `docs/contracts/stability-surface.md` — 4 new surfaces at `experimental`.
- `docs/phase-1-5-carry-overs.md` — DF-12.1-S1 + DF-12.1-S2.
- `pyproject.toml` — NO entry-point added (D-7 decision).

### Existing files this story creates

- `src/AgentEval/judge/library.py` (new JudgeLibrary).
- `src/AgentEval/judge/types.py` (JudgeScore + JudgeRubric dataclasses).
- `src/AgentEval/judge/rubric.py` (Markdown rubric loader).
- `tests/unit/judge/__init__.py` + 3 test files.
- `tests/integration/test_judge_live.py` (env-gated).
- `tests/fixtures/rubrics/skill-quality.md` (canonical rubric example).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

Story 12.1 dev complete 2026-05-27. All 11 ACs + 12 Tasks satisfied. **First Epic 12 story** — Tier-2 LLM-judge surface ships.

- **AC-12.1.1**: `JudgeLibrary` at `src/AgentEval/judge/library.py` with `Judge.Get Score` keyword (`@tier(2)` + `@guarded_fanout`).
- **AC-12.1.2**: `JudgeScore` dataclass at `judge/types.py` with `__post_init__` validation (numeric_score in [0.0, 10.0]; non-negative cost; defensive dict copy).
- **AC-12.1.3**: `load_rubric(path) -> JudgeRubric` at `judge/rubric.py` parses canonical Markdown rubric format (## Criteria + ## Threshold + optional ## Examples).
- **AC-12.1.4**: 2 new error leaves at `errors.py`: `InvalidJudgeRubricError` (Tier-1 setup-failure, `_FR59Tier1SetupFailureError` parent) + `JudgeOutputParseError` (`AgentEvalCompatError` parent with custom `__str__`). `docs/contracts/error-class-hierarchy.md` amended with 2 new catalog rows (22nd + 23rd ratified leaves).
- **AC-12.1.5**: `_SUB_LIBRARIES` registers JudgeLibrary; `_build_components` forwards `max_cost_usd` + `max_runtime_seconds` (mirrors StatsLibrary precedent).
- **AC-12.1.6**: 37 unit tests across 3 files (test_types.py + test_rubric.py + test_library.py).
- **AC-12.1.7**: env-gated `tests/integration/test_judge_live.py` (skipped in CI).
- **AC-12.1.8**: stability-surface.md amended with 4 new entries (JudgeLibrary.Get Score + JudgeScore + JudgeRubric + load_rubric) at `experimental`.
- **AC-12.1.9**: 1733 pytest pass + 12 skipped (was 1696 + 12; +37). ruff/format/mypy clean (102 src files; was 99 + new judge sub-package).
- **AC-12.1.10**: 29th consecutive `feedback_carry_over_catalog_gate` UPSTREAM — C79 + C80 added at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson. Catalog 78 → 80.
- **AC-12.1.11**: 4 cross-story UPSTREAM patterns applied (D-4 listener-hook-API-surface-empirical-check; D-6 catalog-gate review-time enforcement; D-10 thread-safety; general test-name-assertion-match).

### File List

**New files:**
- `src/AgentEval/judge/types.py` — `JudgeScore` + `JudgeRubric` dataclasses (~95 LoC).
- `src/AgentEval/judge/rubric.py` — Markdown rubric loader (~145 LoC).
- `src/AgentEval/judge/library.py` — `JudgeLibrary` + `Get Score` keyword + helpers (~290 LoC).
- `tests/unit/judge/__init__.py`
- `tests/unit/judge/test_types.py` — 9 tests.
- `tests/unit/judge/test_rubric.py` — 10 tests.
- `tests/unit/judge/test_library.py` — 18 tests.
- `tests/integration/test_judge_live.py` — env-gated.
- `tests/fixtures/rubrics/skill-quality.md` — canonical Phase-1 rubric example.

**Modified files:**
- `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` + `_build_components` for JudgeLibrary.
- `src/AgentEval/errors.py` — 2 new error leaves.
- `docs/contracts/error-class-hierarchy.md` — 2 new catalog rows (22nd + 23rd).
- `docs/contracts/stability-surface.md` — 4 new surfaces at `experimental`.
- `docs/phase-1-5-carry-overs.md` — C79 + C80 entries (78 → 80).
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-12.1-S1 + DF-12.1-S2 entries (carry-over catalog gate norm — entries in BOTH catalog files).
- `_bmad-output/implementation-artifacts/sprint-status.yaml`.

### Test-contamination Bug Fix Note (2026-05-27)

During dev close, full `tests/unit/conventions/ tests/unit/judge/` combined run revealed 13 judge-test failures (`LiteLLMAdapter.chat requires model ...`). Root cause: `tests/unit/conventions/_walk.py:load_module_from_path` calls `importlib.util.spec_from_file_location` + registers a freshly-loaded copy of `library.py` under `sys.modules["AgentEval.judge.library"]`, OVERWRITING the original module. After conventions runs, the test file's module-level `from AgentEval.judge.library import JudgeLibrary` still points at the OLD class (captured at test-collection time), but a fresh `from AgentEval.judge.library import JudgeLibrary` inside the patch helper retrieves the NEW class from the overwritten `sys.modules` entry. Patching `get_adapter` on the NEW module's dict does NOT affect the OLD function's lookup namespace.

Fix in `tests/unit/judge/test_library.py::_patch_adapter`: (1) use the module-level `JudgeLibrary` reference (not a fresh import); (2) walk the `@tier(2)` + `@guarded_fanout` decorator chain via `__wrapped__` to reach the innermost function whose `__globals__` IS `library.py`'s module dict (the outermost wrapper's `__globals__` is `_kernel/guardrails`'s dict); (3) use `monkeypatch.setitem(innermost.__globals__, "get_adapter", lambda name: _FakeAdapter)` instead of `monkeypatch.setattr` so the patch lands on the actual lookup dict regardless of `sys.modules` state. Combined run after fix: 279 passed (conventions + judge). Full suite: 1733 passed + 13 skipped. Memorialized as `feedback_monkeypatch_decorator_chain_walk` project norm.

### 2-tier Claude CLI review summary (2026-05-27)

Per /goal directive: Claude CLI sonnet + opus reviews dispatched on Story 12.1 source.

**Tier-1 Sonnet (5 findings: 2 HIGH + 2 MED + 1 LOW)**:
- HIGH-1: `errors.py.__all__` missing `InvalidJudgeRubricError` + `JudgeOutputParseError` → FIXED (added both + updated leaf count comment "19" → "21").
- HIGH-2: `numeric_score` out-of-range raises bare `ValueError` not `JudgeOutputParseError` per docstring contract → 2-WAY AGREEMENT with Opus HIGH-1; FIXED (explicit range check before dataclass construction; raises `JudgeOutputParseError` with `parse_error="numeric_score out of [0.0, 10.0]"`; test updated; `test_get_score_raises_on_numeric_score_boolean` added for the nullish-bool fuzz variant).
- MED-1: `error-class-hierarchy.md` family table + leaf count not updated → 2-WAY AGREEMENT with Opus MED-2; FIXED (family rows + count 21 → 23 with Story 12.1 attribution).
- MED-2: nullish-input fuzz gap — `numeric_score: false` silently coerces to `0.0` → FIXED (explicit boolean type guard before `float()` coercion; new test).
- LOW-1: bare `assert` in `rubric.py:_parse_criteria_bullets` → FIXED indirectly (refactored to `_slice_section` helper; assert no longer present).

**Tier-2 Opus (6 findings: 1 HIGH + 4 MED + 1 LOW)**:
- HIGH-1: numeric_score out-of-range ValueError leak → 2-way agreement (see Sonnet HIGH-2).
- MED-1: `InvalidJudgeRubricError` parent class + attrs diverge from AC-12.1.4 (`AgentEvalCompatError` vs `_FR59Tier1SetupFailureError`; `path` vs `file_path`) → FIXED (AC-12.1.4 amended per `feedback_in_flight_spec_amendment` — `_FR59Tier1SetupFailureError` parent is correct per FR59 Tier-1 setup-failure semantics, sibling to `InvalidScenarioYAMLError`).
- MED-2: error-class-hierarchy.md family table + leaf count → 2-way agreement (see Sonnet MED-1).
- MED-3: AC-12.1.6 `@guarded_fanout` empirical budget-exceeded test missing → FIXED (`test_get_score_raises_cost_exceeded_when_budget_breached` synthesizes a breach via `__agenteval_test_budget__=(0.001, None)` + monkeypatched `_current_cost_usd_for_run` returning `1.0`; asserts `CostExceededError`).
- MED-4: threshold regex not scoped to `## Threshold` section body → FIXED (`_slice_section` helper extracted; both Criteria + Threshold parsing now section-scoped; new test `test_load_rubric_threshold_scope_ignores_pass_lines_in_other_sections`).
- LOW-1: thread-safety docstring overclaim — concurrent fan-outs share Phase-1 cost meter → FIXED (docstring scoped to "DATA-safe but budget metering is process-wide aggregate during concurrent fan-out").

**2-way agreement on 2 findings** (Sonnet+Opus): numeric_score ValueError leak + error-hierarchy doc drift — both near-certain bugs per `feedback_n_way_agreement_weight`.

**Test count delta**: 37 → 40 unit tests (+3: boolean fuzz, threshold scope leak, budget breach). Full suite: 1736 passed + 13 skipped (was 1733 + 13). Lint/format/mypy clean.

**Note on review tier coverage**: /goal directive specified 2-tier Claude CLI (sonnet + opus) — Tier-3 (kilo / minimax-M2.7) was NOT invoked per the directive scope. Future stories may add the third tier per `feedback_third_llm_family_fallback` if degraded reviewer signal warrants it; Story 12.1's 2-way agreement on the critical findings + 11 unique findings across both tiers indicates the 2-tier chain was sufficient here.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-27 | 0.1.0 | Initial story creation (ready-for-dev). **48th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact across 48 consecutive uses). **First Epic 12 story** — Tier-2 LLM-judge surface (NOT same surface as Stories 11.x CLI adapters); no immediately-prior same-surface story for `feedback_cross_story_upstream_lesson_propagation` propagation BUT general patterns from Epic 11 reviews applied UPSTREAM (D-4 listener-hook-API-surface-empirical-check; D-6 catalog-gate review-time enforcement; D-10 thread-safety class docstring). 10 drifts caught (6 fresh + 4 UPSTREAM). 11 ACs. Resolves Epic 11 retro Action #3 D-1 decision: JudgeLibrary uses standard `_SUB_LIBRARIES` composition path; MCPLibrary's 8-epic-old `@guarded_fanout` carve-out does NOT block Story 12.1 (different composition path). | Bob |
