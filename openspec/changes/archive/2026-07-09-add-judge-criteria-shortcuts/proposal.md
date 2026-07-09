## Why

The judge's on-ramp is steep: `Judge.Get Score` requires authoring a Markdown
rubric file before the first score, while the market's most-loved judge idiom
(DeepEval `GEval(criteria="...")`) is a one-line plain-language criteria string
with no rubric file (findings dossier E6 MAJOR, 2026-07-08). AgentEval also
ships no named metric presets (Faithfulness / Answer Relevancy / Hallucination),
which competitors treat as table stakes. Lowering the first-score cost to one
line — WITHOUT abandoning the Cohen's-κ ≥ 0.7 calibration hard gate that is the
project's unique market differentiator — closes the gap while amplifying the
honesty brand: uncalibrated shortcut scores are visibly marked as such.

## What Changes

- Add `Judge.Score With Criteria` keyword: takes an `AgentRunResult`, a
  plain-language `criteria` string, and a `threshold` (default `7.0`);
  synthesizes a `JudgeRubric` internally from the criteria string (G-Eval
  idiom) and returns the same `JudgeScore` shape as `Judge.Get Score`.
- Add 3 named metric presets as thin wrappers over the judge, each backed by a
  curated built-in rubric with documented semantics:
  `Judge.Get Faithfulness` (claims supported by a supplied `context`),
  `Judge.Get Answer Relevancy` (response addresses a supplied `question`),
  `Judge.Get Hallucination Score` (grounding score — higher = LESS
  hallucination, so the uniform `numeric_score >= threshold` pass semantics
  hold; documented loudly).
- Add `Judge.Get Preset Rubric` keyword returning a preset's `JudgeRubric` so
  presets feed directly into the existing `Judge.Calibrate Rubric` graduation
  path.
- Add assertion form `Judge Score Should Be Above` — judge-and-assert in one
  line (`${result}    criteria=...    threshold=7`), failing with the judge's
  reasoning in the message.
- Honesty story (two-tier message: "start with a criteria string in one line;
  graduate to a calibrated rubric for CI gates"): `JudgeScore` gains
  `calibrated: bool` (default `False`) + `rubric_source: str` provenance
  fields; criteria-string and preset scores are always `calibrated=False` and
  emit a documented RF `WARN` (once per process) pointing at the calibration
  recipe. Presets ship uncalibrated-by-default (design.md records why shipping
  "default calibration sets" would be dishonest) with per-preset calibration-set
  templates instead.
- Refactor `judge/rubric.py` to expose text-level parsing (`parse_rubric_text`)
  so file loading, criteria-string synthesis, and embedded preset rubrics share
  one parser. `Judge.Get Score` / `Judge.Calibrate Rubric` behavior is
  unchanged (additive fields on `JudgeScore` only).

NOT in scope: new judge backends, multi-turn judging (sibling change
`add-multi-turn-conversation-testing`), red-team refusal judging (sibling
`add-red-team-probes` reuses the judge).

## Capabilities

### New Capabilities

- `judge-criteria-shortcuts`: One-line criteria-string judging
  (`Judge.Score With Criteria`), named metric presets
  (Faithfulness / Answer Relevancy / Hallucination + `Judge.Get Preset Rubric`),
  the `Judge Score Should Be Above` assertion form, and the
  `calibrated`/`rubric_source` honesty marking on `JudgeScore`.

### Modified Capabilities

<!-- None. openspec/specs/ contains only `opencode-cli-adapter`, which is
     untouched. Existing Judge keyword behavior (Get Score / Calibrate Rubric)
     is extended additively, not changed at the requirements level. -->

## Impact

- **New code**: `src/AgentEval/judge/presets.py` (curated built-in rubrics as
  embedded Markdown constants + registry); new keywords + criteria-rubric
  synthesis in `src/AgentEval/judge/library.py`;
  `tests/unit/judge/` additions; per-preset calibration-set templates under
  `docs/` or `tests/fixtures/`.
- **Modified code**: `src/AgentEval/judge/types.py` (`JudgeScore` gains
  `calibrated` + `rubric_source` fields — additive with defaults, existing
  constructors keep working); `src/AgentEval/judge/rubric.py` (extract
  `parse_rubric_text` from `load_rubric`); `docs/recipes/judge-calibration.md`
  (two-tier graduation story) + `docs/contracts/stability-surface.md` (new
  keyword surfaces).
- **APIs**: 6 new public keywords on `JudgeLibrary` (`Judge.Score With
  Criteria`, `Judge.Get Faithfulness`, `Judge.Get Answer Relevancy`,
  `Judge.Get Hallucination Score`, `Judge.Get Preset Rubric`, `Judge Score
  Should Be Above`); 2 new `JudgeScore` fields. No breaking changes.
- **Dependencies**: none added; presets are single-shot LLM calls through the
  existing adapter path with existing `@tier(2)` + `@guarded_fanout`
  guardrails.
- **Constraint carried**: namespace-prefixed keyword names must keep the
  post-dot portion multi-word (libdoc auto-split defect,
  `feedback_libdoc_namespace_keyword_must_be_multiword`) — all 5 `Judge.*`
  names above comply.
