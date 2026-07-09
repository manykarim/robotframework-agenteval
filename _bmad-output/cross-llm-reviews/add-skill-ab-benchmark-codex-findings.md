# Codex Findings - add-skill-ab-benchmark

## HIGH - Verdict direction can contradict the significance test

**File:** `src/AgentEval/skills/_benchmark.py:605`

`run_skill_benchmark()` correctly computes Mann-Whitney and Cliff's delta over the per-task pass-rate distributions (`candidate_rates`, `baseline_rates`) at `src/AgentEval/skills/_benchmark.py:690-699`, but `compute_benchmark_verdict()` decides the significant direction from the aggregate arm pass rates:

```python
if significant and candidate_pass_rate > baseline_pass_rate:
    return "skill_improves"
if significant and candidate_pass_rate < baseline_pass_rate:
    return "skill_regresses"
```

That is not the same direction as the Mann-Whitney/Cliff distribution direction. A few large candidate wins can make the aggregate pass rate higher while the candidate is worse on most tasks. Repro with the repo's own stats helpers:

```python
candidate = [1.0] * 10 + [0.49] * 90
baseline = [0.5] * 90 + [0.0] * 10
```

This has `candidate_mean=0.541`, `baseline_mean=0.45`, but `compute_mann_whitney_u(...).p_value == 5.414760489291158e-17` and both `effect_size_r` and Cliff's delta are `-0.62` (candidate tends lower than baseline). The current verdict function returns `skill_improves`.

Concrete impact: the closed-set verdict can say a skill improves when the selected significance test says the candidate arm is significantly worse in distribution. The reverse misclassification is also possible. Use the signed Mann-Whitney effect or Cliff's delta direction for `skill_improves` / `skill_regresses`; keep aggregate pass rate for the headline delta and obsolescence threshold only.

## HIGH - `max_cost_usd` is ignored, so adapter and judge spend are not capped by the keyword argument/default

**File:** `src/AgentEval/skills/library.py:767`

The public keyword signature exposes `max_cost_usd=20.00`, and the spec requires the cap to cover both arms and judge grading. But `compare_against_baseline()` never uses `max_cost_usd` or `max_runtime_seconds` after declaring them, and it does not pass them into `run_skill_benchmark()` or the guardrail sentinel. `@guarded_fanout()` reads only instance attributes (`self._max_cost_usd`, `self._max_runtime_seconds`) before the function body, so a per-call `max_cost_usd=` value is invisible to the guard.

Repro with a mock adapter returning `$5.00` per run:

```text
SkillsLibrary().compare_against_baseline(..., trials=1, max_cost_usd=1.0)
NO_ERROR calls=8 total=40.0
```

The default is also ineffective for the common `SkillsLibrary()` case because `_HostBudgetPlumbing` defaults `_max_cost_usd` to `None`, so the wrapper takes its no-budget fast path before the keyword body. Judge spend has the same problem: judge costs are only summed into `total_cost_usd` after the calls (`src/AgentEval/skills/_benchmark.py:724-741`) and are never surfaced to the active guardrail meter.

Concrete impact: live runs can spend beyond the documented/default cap, including the extra judge calls, while still returning a successful benchmark. The keyword needs to bind the per-call budget into the guarded scope and/or perform cooperative cost checks after each adapter and judge call using the same accumulated cost.

## MED - A single adapter failure aborts the benchmark with no per-trial evidence

**File:** `src/AgentEval/skills/_benchmark.py:389`

`_run_arm()` calls `adapter_instance.run(prompt)` directly and only appends a `_RawTrial` after a successful `AgentRunResult`. If one trial raises, the whole benchmark raises the adapter exception immediately:

```text
RuntimeError scripted trial failure calls=3
```

No `SkillBenchmarkComparisonResult` is produced, so the already-completed trials and the failed trial are not represented in `evidence`. This conflicts with the evidence-bearing benchmark contract for fan-out work: every trial should be auditable, and failures should be recorded as failed trial evidence instead of disappearing behind an aborted aggregate run.

Concrete impact: a flaky adapter/judge can erase partial benchmark evidence and make pass rates/verdict unavailable, even though the benchmark has already spent budget on earlier trials. Add an explicit failed-trial representation (for example an error field or failure reason on evidence) and count those trials as non-passing, while still failing loud only for setup/configuration errors where continuing would be invalid.

## Notes Checked

- I did not find a concrete harness-added blind grading leak. The judge prompt is synthesized from rubric + neutral task section + `response_text` only (`src/AgentEval/skills/_benchmark.py:497-511`), and graded results are written back by raw-trial index, so I did not find a shuffle/unblinding misattribution bug.
- `skill_delivery` is closed to `{"prompt_injected"}` and the implementation emits only `"prompt_injected"`.
- Targeted tests run: `uv run pytest -k benchmark -q` and `uv run pytest tests/unit/conventions/test_keyword_name_idiom.py tests/unit/conventions/test_tier_annotation_present.py tests/integration/docs/test_keyword_count_drift.py -q`.
