# Recipe: Judge Calibration Cookbook

Calibrate `Judge.Get Score` against human-labeled ground truth before relying on
its scores in CI. Cohen's kappa ≥ 0.7 is the project's hard-fail threshold per
`architecture.md` L199 (borrowed from agentguard's calibration discipline).

## Two tiers: start in one line, graduate for CI gates

The judge has a deliberate two-tier on-ramp (add-judge-criteria-shortcuts):

- **Tier 1 — the one-line on-ramp (exploration).** `Judge.Score With Criteria`
  takes a plain-language criteria string (the DeepEval G-Eval idiom — no rubric
  file), and the named metric presets (`Judge.Get Faithfulness`,
  `Judge.Get Answer Relevancy`, `Judge.Get Hallucination Score`) score against
  curated built-in rubrics. These are the fastest way to a first score. **Every
  shortcut score is honestly marked `calibrated=False`** with a truthful
  `rubric_source` (`"criteria_string"` or `"preset:<name>"`), and the first
  shortcut score per process emits a `WARN` pointing here. Use them to explore —
  NOT to gate CI.

  ```robot
  *** Settings ***
  Library    AgentEval

  *** Test Cases ***
  Quick Criteria Score
      ${score}=    Judge.Score With Criteria
      ...    result=${result}
      ...    criteria=Response is polite and directly answers the question
      ...    threshold=7
      Log    Uncalibrated (${score.rubric_source}); score=${score.numeric_score}

  Judge And Assert In One Line
      Judge Score Should Be Above    result=${result}
      ...    criteria=Response is polite and directly answers the question    threshold=7
  ```

- **Tier 2 — a calibrated rubric (CI gates).** Once you need a score you can
  gate on, graduate to a rubric whose agreement with humans you have MEASURED:
  Cohen's kappa ≥ 0.7. That is the rest of this recipe. The `calibrated` field
  stays `False` in Phase-1 for all keywords (nothing threads calibration
  evidence into a score yet — carry-over `DF-JCS-S1` / C104); the field means
  "recorded passing calibration evidence," so it never rides on a shortcut.

### Graduating a preset (no new machinery)

Presets ship **uncalibrated by default**. Cohen's kappa is a joint property of
(rubric × judge model × domain × labelers), so a calibration set we authored
against our own labels would not transfer to your model + domain — shipping one
and claiming κ would be the vibes-over-evidence posture this project brands
against. Instead, calibrate a preset against YOUR own labels: `Judge.Get Preset
Rubric` returns the preset's `JudgeRubric`, which feeds straight into
`Judge.Calibrate Rubric` (which already accepts a `JudgeRubric` instance).

```robot
*** Test Cases ***
Calibrate The Faithfulness Preset On My Labels
    ${rubric}=    Judge.Get Preset Rubric    name=faithfulness
    ${report}=    Judge.Calibrate Rubric
    ...    rubric=${rubric}
    ...    calibration_set=my-faithfulness-labels.yaml
    Should Be True    ${report.passes_hard_fail}
```

Per-preset calibration-set templates (placeholder rows + labeling guidance, no
shipped κ claims) live under
[`docs/examples/judge-presets/`](../examples/judge-presets/).

## When to use this recipe

- Before claiming "my judge agrees with humans" in a release note or PR description.
- Before promoting a rubric from `experimental` to "team-blessed."
- Whenever you change the rubric Markdown, the judge model, or the
  `seed`/`temperature` settings — any of these can shift agreement.

## What "calibration" actually means here

The judge returns a 0-10 numeric score. The rubric declares a pass threshold
(e.g., `Pass if numeric_score >= 7.0`). Both judge scores and human labels are
binarized at that threshold (pass/fail). Cohen's kappa measures how much of the
agreement is beyond chance — a kappa of 1.0 is perfect, 0 is chance-level, and
negative is systematic disagreement.

**Phase-1 ships single-judge Cohen's kappa only.** Multi-judge ensemble and
Krippendorff's alpha are Phase-2 carry-overs.

## Step 1 — Author the rubric

```markdown
# Skill quality rubric

## Criteria
- correctness: did the agent produce a working solution?
- completeness: did it address every requirement in the prompt?
- tool-use-appropriateness: did it use tools that fit the task?
- response-clarity: is the explanation legible?

## Threshold
Pass if numeric_score >= 7.0

## Examples
### Example 1 (passing)
A short response that addresses all four criteria visibly.
```

Save it under `tests/fixtures/rubrics/skill-quality.md`.

## Step 2 — Build a calibration set

Pick 30-100 real or synthetic examples spanning your full pass/fail distribution.
At minimum, include some clear passes (8.0+), some clear fails (0.0-3.0), and a
borderline batch around the threshold.

```yaml
# tests/fixtures/calibration/skill-quality-calibration.yaml
rows:
  - prompt: "Write a Python function that adds two numbers."
    response: "def add(a: int, b: int) -> int: return a + b"
    human_label: 9.0
  - prompt: "Compute the determinant of a 3x3 matrix."
    response: "I don't know how to do that, sorry."
    human_label: 2.0
  - prompt: "Summarize the README in 2 sentences."
    response: "The README explains setup and lists three use cases."
    human_label: 7.0
```

Strict schema: each row is exactly `{prompt: str, response: str, human_label:
float in [0.0, 10.0]}`. Extra keys raise `InvalidCalibrationSetError`.

## Step 3 — Run `Judge.Calibrate Rubric` and inspect the report

```robot
*** Settings ***
Library    AgentEval    max_cost_usd=2.00    max_runtime_seconds=600

*** Test Cases ***
Calibrate Judge Against Human Labels
    ${report}=    Judge.Calibrate Rubric
    ...    rubric=tests/fixtures/rubrics/skill-quality.md
    ...    calibration_set=tests/fixtures/calibration/skill-quality-calibration.yaml
    ...    judge_adapter=generic
    ...    judge_model=anthropic/claude-sonnet-4-6
    Log    Cohen's kappa = ${report.cohen_kappa}
    Log    Recommended threshold = ${report.recommended_threshold}
    Should Be True    ${report.passes_hard_fail}
```

If `passes_hard_fail` is `False`:

- Look at `report.kappa_undefined_reason` for zero-variance edge cases (all
  human labels pass or all fail, or all judge scores equal).
- Look at `report.systematic_bias_diagnostics` for human-readable bullets like
  "Judge mean score (9.5) consistently above human mean (5.6) by 3.9 points."
- Inspect `report.threshold_tuning` to see whether a different threshold maxes
  out precision/recall against your labels — `report.recommended_threshold` is
  the F1-maximizing pick. If your rubric's static threshold doesn't match it,
  retune the rubric.

## Step 4 — Gate CI on calibration

```robot
*** Test Cases ***
Calibration Must Pass Hard Fail
    ${report}=    Judge.Calibrate Rubric    rubric=${RUBRIC}    calibration_set=${CALIBRATION_SET}
    Should Be True    ${report.passes_hard_fail}
    ...    Calibration failed: kappa=${report.cohen_kappa} below the 0.7 hard-fail threshold. Review systematic_bias_diagnostics + retune the rubric.
```

Run this on every PR that touches the rubric or the judge configuration.

## Anti-patterns

- **Don't** calibrate on the same calibration set you tune the rubric against.
  Hold out at least 20% of examples for the calibration measurement to avoid
  overfitting.
- **Don't** report a kappa from a calibration set where all human labels are
  on the same side of the threshold. `kappa_undefined_reason ==
  "human_label_zero_variance"` flags this; `passes_hard_fail` returns `False`.
- **Don't** treat kappa as the only signal. Always read
  `systematic_bias_diagnostics` — a systematic bias diagnostic can fire even
  when kappa looks OK because the bullet covers mean/variance gaps.

## See also

- `docs/contracts/stability-surface.md` for the `Judge.Calibrate Rubric` /
  `CalibrationReport` / `load_calibration_set` API surfaces.
- `docs/contracts/error-class-hierarchy.md` for `InvalidCalibrationSetError`
  (24th ratified leaf).
- `tests/fixtures/calibration/skill-quality-calibration.yaml` for a canonical
  5-row fixture.
