# Story 12.2: Judge Calibration Suite + Agreement Scoring + Threshold Tuning

Status: done

## Story

As an **agent surface author** (Devon) calibrating Judge scores against human labels,
I want a `Judge.Calibrate` workflow that runs the judge against a curated calibration set with human-labeled ground truth, computes Cohen's kappa or similar agreement metric, surfaces threshold-tuning recommendations,
So that judge scores are trustworthy across runs — calibrated to a known agreement baseline rather than vibes-based.

## Pre-create-story drift check (49th use of `feedback_spec_vs_ratified_doc_precheck`)

10 drift items surfaced — 6 fresh + 4 UPSTREAM from Story 12.1 review patterns:

- **D-1 (HIGH — PRD vs epics ambiguity):** PRD L864 + L1183 + L1254 + L1310 + L1322 + L1478 + L1676 consistently describe Phase 2 as shipping a *"calibration cookbook"* — i.e., a documentation/recipe asset, NOT a `Judge.Calibrate` keyword. epics.md L2103 Story 12.2 specifies a `Judge.Calibrate` keyword. **Decision:** ship BOTH per `/goal` directive intent — the `Judge.Calibrate` keyword (epics.md authoritative for stories) + a calibration cookbook section in `docs/recipes/judge-calibration.md` referencing the keyword and the kappa-≥-0.7 hard-fail discipline. The PRD "cookbook" framing is honoured via the recipe; the keyword is shipped per epics.md.
- **D-2 (MED — architecture file-layout drift):** architecture.md L1315 says calibration helpers live in `judge/_internal.py`; Story 12.1 already shipped the rubric loader at `judge/rubric.py` instead (not `_internal.py`). **Decision:** ship calibration helpers at `judge/calibration.py` for clarity (parallel to existing `rubric.py`), NOT at `_internal.py`. This is a fix-the-losing-source-NOW amendment of architecture.md L1315 to reflect actual file layout (`judge/rubric.py` + `judge/calibration.py` + `judge/types.py` + `judge/library.py`).
- **D-3 (HIGH — kappa hard-fail threshold):** architecture.md L199 ratifies "Cohen's κ ≥ 0.7 hard-fail" calibration discipline borrowed from agentguard. **Decision:** encode `KAPPA_HARD_FAIL_THRESHOLD = 0.7` as a module-level constant in `judge/calibration.py`; `CalibrationReport.passes_hard_fail()` returns True iff `cohen_kappa >= 0.7`. The keyword does NOT raise on kappa-below-0.7 — it returns the report with `passes_hard_fail=False` so callers can choose to fail their own assertion (e.g., via `Should Be True    ${report.passes_hard_fail}`).
- **D-4 (HIGH — UPSTREAM Story 12.1 HIGH-2 & MED-2):** Calibration set is YAML-loaded untrusted input. Parsing failures MUST raise an `AgentEvalError` leaf (NOT bare `ValueError`/`yaml.YAMLError`). **Decision:** add `InvalidCalibrationSetError(_FR59Tier1SetupFailureError)` — sibling to `InvalidJudgeRubricError` + `InvalidScenarioYAMLError`; carries `file_path`, `line_number`, `field_name`, `fix_suggestion`. Per-row schema validation (each row must have `prompt: str`, `response: str`, `human_label: float in [0.0, 10.0]`); nullish fuzz (`None`, `""`, `False`, missing key) raises `InvalidCalibrationSetError` with field-specific diagnostic. NEW 24th ratified error leaf.
- **D-5 (MED — UPSTREAM Story 12.1 MED-3):** AC-12.2.6 MUST include an empirical `@guarded_fanout` budget-exceeded test (50 calibration rows × judge calls = significant cost; budget enforcement load-bearing). Synthesize a breach via `__agenteval_test_budget__=(0.001, None)` + monkeypatched `_current_cost_usd_for_run` returning > 0.001; assert `CostExceededError` fires. Same pattern as Story 12.1's `test_get_score_raises_cost_exceeded_when_budget_breached`.
- **D-6 (MED — UPSTREAM Story 12.1 MED-4 + general):** YAML schema parsing must be strict — unknown top-level keys reject as malformed (NOT silently ignored); per-row field set must match documented schema exactly. Prevents stray "human_score" / "label" / "ground_truth" alias keys from silently dropping rows.
- **D-7 (MED — Cohen's kappa floor/ceiling + edge cases):** Cohen's kappa is undefined when all human labels are equal (zero-variance) — the formula's denominator goes to zero. **Decision:** `compute_cohen_kappa(judge_scores, human_labels)` returns `nan` + sets `CalibrationReport.kappa_undefined_reason = "human_label_zero_variance"` instead of dividing by zero. Similarly for `judge_scores` zero-variance. `passes_hard_fail()` returns `False` if kappa is `nan`. Unit tests cover both zero-variance cases + perfect-agreement (kappa=1.0) + perfect-disagreement (kappa < 0) + chance-level (kappa≈0).
- **D-8 (LOW — pre-emptive carry-over catalog gate UPSTREAM, 30th consecutive):** Surface DF-12.2-S1 (Phase-2 multi-judge ensemble + Krippendorff's alpha as alternative agreement metric) + DF-12.2-S2 (Phase-2 active-learning calibration set curation — auto-select diverse examples) BEFORE code-review.
- **D-9 (MED — UPSTREAM Story 12.1 in-flight spec amendment):** If dev decisions diverge from AC text mid-story, amend AC in same commit (e.g., if `judge/calibration.py` file location differs from this spec at dev time, amend D-2 + AC text together).
- **D-10 (MED — UPSTREAM Story 12.1 test contamination):** New unit tests for `Judge.Calibrate` MUST use the `feedback_monkeypatch_decorator_chain_walk` pattern — walk `JudgeLibrary.calibrate.__wrapped__` chain to innermost + `monkeypatch.setitem(innermost.__globals__, "get_adapter", ...)`. Conventions test re-loads `library.py` via `load_module_from_path` and overwrites `sys.modules` — naïve `setattr` patches land on the wrong module dict.

## Acceptance Criteria

### AC-12.2.1 — `JudgeLibrary.calibrate` keyword

`src/AgentEval/judge/library.py` extended with:

```python
@keyword(name="Judge.Calibrate", tags=("agenteval",))
@tier(2)
@guarded_fanout()
def calibrate(
    self,
    rubric: Union[str, Path, JudgeRubric],
    calibration_set: Union[str, Path],
    judge_adapter: str = "generic",
    judge_model: Optional[str] = None,
    **adapter_kwargs: Any,
) -> CalibrationReport:
    """[Tier 2 — Stochastic Single-Shot] Run the judge against a labeled calibration set, compute Cohen's kappa, return a CalibrationReport.

    Loads each row from `calibration_set` (YAML), invokes `judge.get_score` per row,
    computes Cohen's kappa between binary judge-pass / human-pass labels (per row),
    returns a `CalibrationReport` with kappa, threshold tuning chart, systematic-bias
    diagnostics, and `passes_hard_fail` (kappa >= 0.7 per architecture L199).
    """
```

`@tier(2)` + `@guarded_fanout()` budget enforcement (same plumbing as `Get Score`).

### AC-12.2.2 — `CalibrationReport` dataclass

`src/AgentEval/judge/types.py` extended with:

```python
@dataclass(frozen=True)
class CalibrationReport:
    rubric_path: str
    calibration_set_path: str
    judge_adapter: str
    judge_model: Optional[str]
    rows_total: int
    rows_processed: int
    judge_scores: tuple[float, ...]
    human_labels: tuple[float, ...]
    cohen_kappa: float                            # nan if zero-variance
    kappa_undefined_reason: Optional[str]         # "human_label_zero_variance" | "judge_score_zero_variance" | None
    passes_hard_fail: bool                        # kappa >= 0.7 (architecture L199)
    threshold_tuning: dict[float, dict[str, float]]  # {threshold: {precision, recall, f1}}
    recommended_threshold: float                  # threshold maximizing F1
    systematic_bias_diagnostics: tuple[str, ...]  # human-readable bullets, e.g., "judge consistently scores +1.2 above humans"
    total_cost_usd: float
    total_latency_seconds: float
```

`__post_init__` validates: `rows_processed <= rows_total`, lengths of `judge_scores` and `human_labels` match `rows_processed`, all human labels in `[0.0, 10.0]`, `recommended_threshold` in `[0.0, 10.0]`.

### AC-12.2.3 — `load_calibration_set(path) -> tuple[CalibrationRow, ...]`

`src/AgentEval/judge/calibration.py` ships `load_calibration_set(path)` that loads YAML calibration sets:

```yaml
# Schema
rubric_pass_threshold: 7.0   # optional — defaults to rubric's threshold
rows:
  - prompt: "Write a function that adds two numbers."
    response: "def add(a, b): return a + b"
    human_label: 9.0
  - prompt: "..."
    response: "..."
    human_label: 4.5
```

Each `CalibrationRow` is a frozen dataclass: `prompt: str`, `response: str`, `human_label: float` (validated in `[0.0, 10.0]`).

Failure modes raise `InvalidCalibrationSetError`:
- file not found / not `.yaml` / not `.yml`
- top-level not a dict or missing `rows` key
- `rows` not a list
- per-row missing required field / unknown extra field / `human_label` out of range / nullish-input variant (`None`/`""`/`False`/missing-key)

### AC-12.2.4 — `compute_cohen_kappa(judge_scores, human_labels, pass_threshold)`

`judge/calibration.py` ships pure-Python `compute_cohen_kappa()` implementation (NO scipy dependency — agenteval-core SHOULD ship without scipy per `[agenteval-advanced]` extra rationale at PRD L864). Binarizes both sequences against `pass_threshold` (>= threshold → 1, else → 0), computes Cohen's kappa via the standard formula:

```
kappa = (P_o - P_e) / (1 - P_e)
```

where `P_o = sum(agreement) / n` and `P_e = sum over classes c of (P_judge[c] * P_human[c])`.

Edge cases (per D-7):
- both sequences all-equal (e.g., all 1s) → `nan` + `kappa_undefined_reason="human_label_zero_variance"` or `"judge_score_zero_variance"`
- empty sequences → raises `ValueError` (programmer error — caller must validate first)
- length mismatch → raises `ValueError`

### AC-12.2.5 — `KAPPA_HARD_FAIL_THRESHOLD = 0.7` constant

`judge/calibration.py` ships `KAPPA_HARD_FAIL_THRESHOLD: Final[float] = 0.7` per architecture L199. `CalibrationReport.passes_hard_fail` is `True` iff `not math.isnan(self.cohen_kappa) and self.cohen_kappa >= KAPPA_HARD_FAIL_THRESHOLD`.

### AC-12.2.6 — `InvalidCalibrationSetError` error leaf

`src/AgentEval/errors.py` extended with `InvalidCalibrationSetError(_FR59Tier1SetupFailureError)` (24th ratified leaf). Exit code `65` (EX_DATAERR). Carries `file_path: str`, `line_number: int | None`, `field_name: str`, `fix_suggestion: str` (per FR59 + parallel to `InvalidJudgeRubricError`). Added to `errors.py.__all__` (Sonnet HIGH-1 lesson UPSTREAM). Added to `docs/contracts/error-class-hierarchy.md` family table + per-leaf inventory + count 23 → 24.

### AC-12.2.7 — `Judge.Calibrate` integration with `_SUB_LIBRARIES`

`Judge.Calibrate` is automatically exposed via the existing JudgeLibrary `_SUB_LIBRARIES` registration from Story 12.1. `_build_components` already forwards `max_cost_usd` + `max_runtime_seconds`. Verify via:

```python
from AgentEval import AgentEval
agent_eval = AgentEval()
assert "Judge.Calibrate" in agent_eval.get_keyword_names()
```

### AC-12.2.8 — Unit + integration tests

Unit tests at `tests/unit/judge/test_calibration.py` cover:
1. `compute_cohen_kappa` perfect-agreement → kappa=1.0
2. `compute_cohen_kappa` perfect-disagreement → kappa < 0
3. `compute_cohen_kappa` chance-level → |kappa| < 0.1
4. `compute_cohen_kappa` zero-variance human labels → nan + reason
5. `compute_cohen_kappa` zero-variance judge scores → nan + reason
6. `compute_cohen_kappa` empty / length-mismatch → ValueError
7. `load_calibration_set` canonical fixture → 5 rows parsed
8. `load_calibration_set` file not found → `InvalidCalibrationSetError`
9. `load_calibration_set` non-yaml extension → `InvalidCalibrationSetError`
10. `load_calibration_set` non-dict top-level → `InvalidCalibrationSetError`
11. `load_calibration_set` missing `rows` key → `InvalidCalibrationSetError`
12. `load_calibration_set` per-row missing `prompt` / `response` / `human_label` → `InvalidCalibrationSetError`
13. `load_calibration_set` `human_label` out of range → `InvalidCalibrationSetError`
14. `load_calibration_set` nullish-input fuzz: `human_label: None` / `human_label: false` / `human_label: ""` → `InvalidCalibrationSetError`
15. `load_calibration_set` unknown extra key in row → `InvalidCalibrationSetError`
16. `CalibrationReport.__post_init__` validation (lengths, ranges)
17. `KAPPA_HARD_FAIL_THRESHOLD` is `0.7` (architecture L199)
18. `CalibrationReport.passes_hard_fail` True at exactly kappa=0.7
19. `CalibrationReport.passes_hard_fail` False at kappa=nan

Unit tests at `tests/unit/judge/test_library_calibrate.py` cover:
20. Happy path: 5-row calibration set + monkeypatched adapter returning predictable scores → CalibrationReport with expected kappa
21. AC-12.2.5 budget-exceeded empirical probe: `__agenteval_test_budget__=(0.001, None)` + monkeypatched `_current_cost_usd_for_run` → `CostExceededError` (UPSTREAM Story 12.1 MED-3 lesson)
22. Threshold tuning identifies recommended F1-maximizing threshold
23. Systematic bias diagnostic surfaces when judge scores avg > human labels avg by > 1.0

Integration test at `tests/integration/test_judge_calibrate_live.py` env-gated (`AGENTEVAL_LIVE_LLM_TESTS=1`).

### AC-12.2.9 — `tests/fixtures/calibration/skill-quality-calibration.yaml`

Canonical 5-row calibration fixture (NOT 50 as epics says — D-11 in-flight amendment if we deviate). Rows balanced: 2 clear-pass (human_label >= 8.0) + 2 clear-fail (human_label <= 4.0) + 1 borderline (human_label = 7.0).

### AC-12.2.10 — `docs/recipes/judge-calibration.md` recipe

Per D-1: ship a calibration cookbook recipe documenting the `Judge.Calibrate` keyword usage, kappa-≥-0.7 hard-fail discipline, and how to construct a calibration set. Recipe code blocks pass `robot --dryrun -t` smoke test per `feedback_executable_doc_precheck`.

### AC-12.2.11 — `docs/contracts/stability-surface.md` amendment

Add 5 new entries at `experimental`: `JudgeLibrary.Calibrate`, `CalibrationReport`, `load_calibration_set`, `compute_cohen_kappa`, `KAPPA_HARD_FAIL_THRESHOLD`. **In-flight spec amendment 2026-05-27** per `feedback_in_flight_spec_amendment` (Opus LOW-3): original AC said "3 entries"; shipped 5 because `compute_cohen_kappa` + `KAPPA_HARD_FAIL_THRESHOLD` are also Phase-2-promotable public surfaces worth documenting.

### AC-12.2.12 — Carry-over catalog gate UPSTREAM (30th consecutive)

Pre-emptively surface DF-12.2-S1 (Phase-2 multi-judge ensemble + Krippendorff's alpha) + DF-12.2-S2 (Phase-2 active-learning calibration set curation) in BOTH `docs/phase-1-5-carry-overs.md` AND `_bmad-output/implementation-artifacts/deferred-work.md` BEFORE invoking code-review. Catalog 80 → 82.

## Tasks/Subtasks

- [ ] **Task 1** — Add `InvalidCalibrationSetError` to `src/AgentEval/errors.py` + `__all__` (Sonnet HIGH-1 lesson UPSTREAM). Amend `docs/contracts/error-class-hierarchy.md` family table + per-leaf inventory + count 23 → 24 (Story 12.1 MED-1 lesson UPSTREAM).
- [ ] **Task 2** — Ship `src/AgentEval/judge/calibration.py` with `CalibrationRow` dataclass, `load_calibration_set`, `compute_cohen_kappa`, `KAPPA_HARD_FAIL_THRESHOLD = 0.7` constant.
- [ ] **Task 3** — Extend `src/AgentEval/judge/types.py` with `CalibrationReport` frozen dataclass + `__post_init__` validation.
- [ ] **Task 4** — Extend `src/AgentEval/judge/library.py` with `JudgeLibrary.calibrate` keyword (`@tier(2)` + `@guarded_fanout()` + canonical tier-2 badge in docstring).
- [ ] **Task 5** — Ship `tests/fixtures/calibration/skill-quality-calibration.yaml` (5 rows, balanced pass/fail/borderline).
- [ ] **Task 6** — Unit tests at `tests/unit/judge/test_calibration.py` (covering ACs 1-19 from AC-12.2.8).
- [ ] **Task 7** — Unit tests at `tests/unit/judge/test_library_calibrate.py` (covering ACs 20-23 from AC-12.2.8); USE `feedback_monkeypatch_decorator_chain_walk` pattern (UPSTREAM Story 12.1 lesson) — `JudgeLibrary.calibrate.__wrapped__` chain walk + `monkeypatch.setitem(innermost.__globals__, "get_adapter", ...)`.
- [ ] **Task 8** — Integration test at `tests/integration/test_judge_calibrate_live.py` (env-gated).
- [ ] **Task 9** — Ship `docs/recipes/judge-calibration.md` calibration cookbook recipe (D-1 PRD-honouring); smoke-test code blocks via `robot --dryrun` per `feedback_executable_doc_precheck`.
- [ ] **Task 10** — Amend `docs/contracts/stability-surface.md` with 3 new `experimental` entries (Calibrate keyword + CalibrationReport + load_calibration_set).
- [ ] **Task 11** — Carry-over catalog gate UPSTREAM (30th consecutive): surface DF-12.2-S1 + DF-12.2-S2 in BOTH `docs/phase-1-5-carry-overs.md` AND `_bmad-output/implementation-artifacts/deferred-work.md` BEFORE invoking code-review. Catalog 80 → 82.
- [ ] **Task 12** — Run full pytest + ruff + format + mypy clean. Expected: 1736 + ~25 new tests → ~1761 passed + 13 skipped. Run `tests/unit/conventions/ tests/unit/judge/` combined to confirm no contamination from Story 12.1 + 12.2 combined.
- [ ] **Task 13** — Amend `architecture.md` L1315 fix-the-losing-source-NOW: `judge/_internal.py` → `judge/rubric.py` + `judge/calibration.py` (D-2).
- [ ] **Task 14** — Update `sprint-status.yaml` + flip Story 12.2 status `ready-for-dev` → `review` → `done`.

## Dev Notes

Building on Story 12.1's JudgeLibrary surface:
- `judge/library.py` already has `JudgeLibrary` class registered via `_SUB_LIBRARIES`; just add the `calibrate` method.
- `judge/types.py` already has `JudgeRubric` + `JudgeScore`; add `CalibrationReport` + `CalibrationRow` alongside.
- `judge/rubric.py` already has Markdown rubric loader; new file `judge/calibration.py` is parallel — NOT inside `_internal.py` per D-2 amendment.

UPSTREAM lessons applied from Story 12.1 reviews:
- D-4 (Sonnet HIGH-2 + Opus HIGH-1 2-way): boundary-rewrap untrusted runtime data into `AgentEvalError` leaves.
- D-5 (Opus MED-3): empirical `@guarded_fanout` budget test.
- D-6 (Opus MED-4): strict schema parsing, no silent alias drops.
- D-7 (Sonnet MED-2): nullish-input fuzz on numeric fields.
- D-10 (project norm `feedback_monkeypatch_decorator_chain_walk`): decorator-chain walk + setitem patch.

## File List

**New files:**
- `src/AgentEval/judge/calibration.py` — `load_calibration_set` + `compute_cohen_kappa` + `CalibrationRow` + `KAPPA_HARD_FAIL_THRESHOLD`.
- `tests/unit/judge/test_calibration.py` — calibration helper unit tests (~19 tests).
- `tests/unit/judge/test_library_calibrate.py` — `Judge.Calibrate` keyword unit tests (~4 tests).
- `tests/integration/test_judge_calibrate_live.py` — env-gated.
- `tests/fixtures/calibration/skill-quality-calibration.yaml` — canonical 5-row calibration fixture.
- `docs/recipes/judge-calibration.md` — calibration cookbook recipe.

**Modified files:**
- `src/AgentEval/judge/types.py` — add `CalibrationReport`.
- `src/AgentEval/judge/library.py` — add `calibrate` keyword.
- `src/AgentEval/errors.py` — add `InvalidCalibrationSetError` (24th leaf) + `__all__` entry.
- `docs/contracts/error-class-hierarchy.md` — family table + per-leaf inventory + count 23 → 24.
- `docs/contracts/stability-surface.md` — 3 new `experimental` entries.
- `docs/phase-1-5-carry-overs.md` — C81 + C82 entries (80 → 82).
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-12.2-S1 + DF-12.2-S2 entries.
- `_bmad-output/planning-artifacts/architecture.md` — L1315 file layout amendment (D-2 fix-the-losing-source).
- `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-27 | 0.1.0 | Initial story creation (ready-for-dev). **49th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact across 49 consecutive uses). 10 drifts caught (6 fresh + 4 UPSTREAM Story 12.1 lessons). **Cross-story upstream lesson propagation** (`feedback_cross_story_upstream_lesson_propagation` — N=4 propagation: Stories 11.1→11.2→11.3→12.1→12.2; 12.1→12.2 propagated Sonnet HIGH-1 `__all__` lesson + 2-way HIGH numeric-score-out-of-range boundary-rewrap pattern + MED-2 nullish-input fuzz + MED-3 empirical budget test + MED-4 strict-schema-section-scope + Opus LOW-1 thread-safety-docstring + project norm `feedback_monkeypatch_decorator_chain_walk` test patch pattern). Pre-emptive carry-over catalog gate UPSTREAM (30th consecutive). 12 ACs + 14 Tasks. | Bob |
| 2026-05-27 | 0.2.0 | Dev complete + 2-tier Claude CLI review (sonnet + opus) per /goal. 13 findings (1 HIGH + 6 MED + 6 LOW; 4 cross-tier 2-way agreements per `feedback_n_way_agreement_weight`). All HIGH+MED applied inline: (1) **2-way HIGH/MED**: ship `tests/integration/test_judge_calibrate_live.py` env-gated live integration test (Sonnet HIGH-1 + Opus MED-1). (2) **Sonnet MED-1**: top-level strict schema — extra top-level YAML keys raise `InvalidCalibrationSetError` (D-6 enforcement was asymmetric: row-level strict, doc-level lenient). (3) **2-way MED**: `_sweep_thresholds` now injects `rubric_threshold` into sweep set; `recommended_threshold` guaranteed to be in `threshold_tuning` (Sonnet MED-2 empirical KeyError + Opus MED-2 same finding). (4) **2-way MED**: `CalibrationReport.__post_init__` enforces `passes_hard_fail` ↔ `cohen_kappa` invariant (Sonnet MED-3 + Opus LOW-1). (5) **2-way MED**: chance-level `compute_cohen_kappa` test + `recommended_threshold` happy-path assertion + new `test_calibrate_kappa_between_zero_and_threshold_passes_hard_fail_false` (defined-kappa < 0.7 path) + renamed zero-variance test for `feedback_test_name_assertion_match` (Opus MED-3 + Sonnet LOW-3). (6) **Sonnet LOW-1**: annotated dead `p_expected == 1.0` guard as defensive belt-and-braces. (7) **Sonnet LOW-2**: `__all__` count comment 22 → 23. (8) **Opus LOW-2**: reworded CalibrationReport docstring to scope defensive-copy claim. (9) **Opus LOW-3**: amended AC-12.2.1 `judge_adapter="generic"` (matches ship) + AC-12.2.11 "5 entries" (matches ship). Final: 1770 passed + 14 skipped (was 1768 + 13; +2 new tests, +1 skipped for live integration). ruff/format/mypy clean. | Amelia |
