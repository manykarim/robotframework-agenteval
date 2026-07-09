# judge-criteria-shortcuts Specification

## Purpose

Lower the judge on-ramp to one line — a plain-language criteria string
(DeepEval G-Eval idiom) and named metric presets — while visibly marking every
shortcut score as uncalibrated, preserving the project's Cohen's-κ ≥ 0.7
calibrated-rubric differentiator as the documented graduation path for CI
gates.

## ADDED Requirements

### Requirement: Score With Criteria judges from a plain-language criteria string

The system SHALL provide a `Judge.Score With Criteria` keyword that evaluates
an `AgentRunResult` against a plain-language `criteria` string with a numeric
`threshold` (default `7.0`), without requiring a rubric file. The keyword MUST
synthesize an in-memory `JudgeRubric` from the criteria string (single
criterion carrying the verbatim string; `raw_text` in the standard Markdown
rubric format) and MUST reuse the existing judge pipeline (prompt composition,
adapter invocation, JSON response parsing), returning the same `JudgeScore`
dataclass shape as `Judge.Get Score`. The keyword MUST be decorated `@tier(2)`
and `@guarded_fanout()` and MUST accept the standard `judge_adapter`,
`judge_model`, and `**adapter_kwargs` pass-through arguments.

#### Scenario: One-line criteria score
- **WHEN** `Judge.Score With Criteria` is called with a valid `AgentRunResult`,
  `criteria=Response is polite and answers the question`, and `threshold=7`
- **THEN** the keyword SHALL make a single judge LLM call and return a
  `JudgeScore` with `numeric_score` in `[0.0, 10.0]`,
  `pass_threshold_met == (numeric_score >= 7.0)`, non-empty `reasoning`, and
  `rubric_source == "criteria_string"`

#### Scenario: Synthesized rubric parses under the standard rubric parser
- **WHEN** the internally synthesized rubric `raw_text` is fed back through the
  shared rubric text parser
- **THEN** it SHALL parse without error into an equivalent `JudgeRubric`
  (same criteria tuple and threshold)

#### Scenario: Empty or nullish criteria fail loud
- **WHEN** `Judge.Score With Criteria` is called with `criteria` that is empty,
  whitespace-only, or a nullish coercion artifact (`None`-string, `""`)
- **THEN** the keyword SHALL raise `InvalidJudgeRubricError` with a
  `fix_suggestion`, and SHALL NOT make any LLM call

#### Scenario: Out-of-range threshold rejected
- **WHEN** `Judge.Score With Criteria` is called with `threshold=11`
- **THEN** the keyword SHALL fail with the existing rubric threshold range
  error (threshold must be in `[0.0, 10.0]`) before any LLM call

### Requirement: JudgeScore carries calibration honesty marking

The `JudgeScore` dataclass SHALL gain two additive fields with defaults:
`calibrated: bool = False` and `rubric_source: str = "file"`. Scores produced
by `Judge.Score With Criteria` and by the metric preset keywords MUST have
`calibrated == False` and a truthful `rubric_source`
(`"criteria_string"` or `"preset:<name>"`). No keyword in this change SHALL
ever set `calibrated=True`. Existing construction sites and
`dataclasses.asdict()` consumers MUST keep working unchanged (additive-only,
frozen dataclass preserved).

#### Scenario: Criteria-string score is marked uncalibrated
- **WHEN** any score is produced via `Judge.Score With Criteria`
- **THEN** the returned `JudgeScore` SHALL have `calibrated == False` and
  `rubric_source == "criteria_string"`

#### Scenario: Preset score carries preset provenance
- **WHEN** a score is produced via `Judge.Get Faithfulness`
- **THEN** the returned `JudgeScore` SHALL have `calibrated == False` and
  `rubric_source == "preset:faithfulness"`

#### Scenario: Existing JudgeScore construction is unaffected
- **WHEN** a `JudgeScore` is constructed with only the pre-existing fields
  (as existing tests and dogfood suites do)
- **THEN** construction SHALL succeed with `calibrated == False` and
  `rubric_source == "file"` defaults, and `dataclasses.asdict()` SHALL include
  the two new keys

### Requirement: Uncalibrated shortcut scores emit a documented warning

The system SHALL emit, on the first uncalibrated shortcut score
(criteria-string or preset) per process, an RF `WARN`-level log message that
names the `rubric_source`,
states the score is uncalibrated, and points to the calibration recipe as the
graduation path for CI gates. Subsequent shortcut scores in the same process
SHALL log the same message at `INFO` level (no WARN flooding under fan-out).

#### Scenario: First shortcut score warns once
- **WHEN** two consecutive `Judge.Score With Criteria` calls run in one process
- **THEN** exactly one WARN-level message SHALL be emitted (on the first call)
  containing a reference to the calibration recipe, and the second call SHALL
  log at INFO level

### Requirement: Named metric presets judge via curated built-in rubrics

The system SHALL provide exactly three preset keywords in this change, each a
thin wrapper over the judge pipeline backed by a curated built-in rubric
registered in a preset registry, each decorated `@tier(2)` +
`@guarded_fanout()`, each returning a `JudgeScore`:

- `Judge.Get Faithfulness` — requires `result` and `context` (grounding text);
  measures whether every factual claim in the response is supported by the
  supplied context.
- `Judge.Get Answer Relevancy` — requires `result` and `question`; measures
  whether the response directly addresses the supplied question.
- `Judge.Get Hallucination Score` — requires `result` and `context`; returns a
  grounding score where HIGHER is better (`10.0` = no fabricated
  entities/facts/citations relative to the context), preserving the uniform
  `numeric_score >= threshold` pass semantics.

Each preset keyword MUST accept an optional `threshold` override (default:
the preset rubric's built-in threshold of `7.0`) plus the standard
`judge_adapter` / `judge_model` / `**adapter_kwargs` arguments. Each preset's
keyword documentation MUST quote the rubric's criteria verbatim and state what
the preset does NOT measure. The built-in preset rubrics MUST parse via the
same shared rubric text parser used for rubric files.

#### Scenario: Faithfulness judges response against supplied context
- **WHEN** `Judge.Get Faithfulness` is called with a `result` and
  `context=<source document text>`
- **THEN** the judge prompt SHALL include the preset rubric, the supplied
  context as a distinct section, and the agent response, and the keyword SHALL
  return a `JudgeScore` with `rubric_source == "preset:faithfulness"`

#### Scenario: Answer Relevancy requires the question explicitly
- **WHEN** `Judge.Get Answer Relevancy` is called without a `question` argument
- **THEN** the keyword SHALL fail with a clear argument error (the original
  prompt is not recoverable from `AgentRunResult` and MUST NOT be silently
  substituted)

#### Scenario: Hallucination score direction is higher-is-better
- **WHEN** `Judge.Get Hallucination Score` returns a `JudgeScore` with
  `numeric_score=9.5` and `threshold=7.0`
- **THEN** `pass_threshold_met` SHALL be `True`, and the keyword documentation
  SHALL state in its first paragraph that the score measures freedom from
  hallucination (10.0 = none detected)

#### Scenario: Preset threshold override
- **WHEN** `Judge.Get Faithfulness` is called with `threshold=9.0`
- **THEN** `pass_threshold_met` SHALL be computed against `9.0`, not the
  preset default

#### Scenario: Unknown preset name fails loud
- **WHEN** a preset rubric is requested from the registry under a name that is
  not registered
- **THEN** the system SHALL raise an error listing the available preset names

### Requirement: Preset rubrics are retrievable for calibration graduation

The system SHALL provide a `Judge.Get Preset Rubric` keyword that returns the
parsed `JudgeRubric` for a named preset, so operators can pass it directly to
the existing `Judge.Calibrate Rubric` keyword (which already accepts a
`JudgeRubric` instance) and calibrate a preset against their own labeled data.
Presets SHALL be documented as uncalibrated-by-default; the system MUST NOT
ship pre-computed calibration results claiming κ for any preset. Each preset
SHALL ship a calibration-set template file (in the schema accepted by the
existing calibration loader) with placeholder rows and labeling guidance.

#### Scenario: Preset rubric feeds the existing calibration keyword
- **WHEN** `Judge.Get Preset Rubric    name=faithfulness` is called and the
  returned rubric is passed to `Judge.Calibrate Rubric` with a valid
  calibration set
- **THEN** calibration SHALL run to completion and return a standard
  `CalibrationReport`, with no preset-specific calibration machinery required

#### Scenario: No shipped calibration claims
- **WHEN** any preset keyword or preset documentation is inspected
- **THEN** no shipped artifact SHALL claim a Cohen's κ value for the preset,
  and preset scores SHALL carry `calibrated == False`

### Requirement: Judge Score Should Be Above assertion form

The system SHALL provide a `Judge Score Should Be Above` keyword (assertion
naming convention, no `Judge.` namespace prefix) that judges and asserts in
one line: it takes `result`, `criteria` (plain-language string), and
`threshold` (default `7.0`), runs the same criteria-string scoring path as
`Judge.Score With Criteria`, and fails the test when the score does not meet
the threshold. The pass comparison SHALL be `numeric_score >= threshold`
(consistent with `pass_threshold_met` project-wide), and the keyword
documentation MUST state this explicitly. The failure message MUST include the
numeric score, the threshold, the uncalibrated marker (`calibrated=False` /
`rubric_source`), and the judge's `reasoning`. On success the keyword SHALL
return the `JudgeScore` so callers can inspect it without a second LLM call.
The keyword MUST be decorated `@tier(2)` and `@guarded_fanout()` and MUST live
on the judge library (it makes an LLM call; it is not a Tier-1 assertion).

#### Scenario: Failing assertion carries the judge's reasoning
- **WHEN** `Judge Score Should Be Above    ${result}    criteria=...
  threshold=7` runs and the judge returns `numeric_score=4.0`
- **THEN** the keyword SHALL fail the test with a message containing `4.0`,
  `7.0`, the uncalibrated marker, and the judge's `reasoning` text

#### Scenario: Passing assertion returns the score
- **WHEN** the judge returns `numeric_score=8.5` against `threshold=7`
- **THEN** the keyword SHALL pass and return the `JudgeScore` (with
  `calibrated == False`, `rubric_source == "criteria_string"`)

#### Scenario: Boundary score passes
- **WHEN** the judge returns `numeric_score` exactly equal to `threshold`
- **THEN** the keyword SHALL pass (>= semantics, matching
  `pass_threshold_met`)

### Requirement: Existing judge pipeline behavior is preserved

Adding the shortcut surface MUST NOT change the observable behavior of
`Judge.Get Score` and `Judge.Calibrate Rubric` beyond the additive
`JudgeScore` fields. The prompt-composition extension for preset inputs MUST
be pure-additive: when no extra sections are supplied, the composed judge
prompt SHALL be byte-identical to the pre-change composition (preserving
Tier-2 seed+temperature=0 reproducibility for existing suites). The rubric
file loader MUST retain its full existing validation behavior after the
text-parsing extraction.

#### Scenario: Existing prompt composition is byte-identical
- **WHEN** the judge prompt is composed for a rubric and result with no extra
  sections
- **THEN** the output SHALL be byte-identical to the pre-change
  `_compose_judge_prompt` output for the same inputs

#### Scenario: Rubric file loading behavior unchanged
- **WHEN** an existing valid rubric file and each documented invalid rubric
  variant (missing section, malformed bullet, bad threshold) are loaded after
  the refactor
- **THEN** results and raised error types/fields SHALL match the pre-refactor
  behavior
