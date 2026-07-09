# Codex adversarial review: add-judge-criteria-shortcuts

## Findings

### MED — Preset calibration path drops the context/question, so calibrated preset reports are based on the wrong prompt

`src/AgentEval/judge/library.py:240-254` builds each calibration row's synthetic `AgentRunResult` from `row.response` only and calls `_compose_judge_prompt(parsed_rubric, synth_result)` with no extra sections. The calibration row schema has `prompt` (`src/AgentEval/judge/calibration.py:46-57`), and the new preset templates explicitly instruct users to put the preset's required context/question there. For example, the faithfulness template says the context goes in `prompt` and claims the calibration loader passes prompt+response to the judge (`docs/examples/judge-presets/faithfulness-calibration.template.yaml:14-18`), while the recipe advertises `Judge.Get Preset Rubric` -> `Judge.Calibrate Rubric` as "no new machinery" (`docs/recipes/judge-calibration.md:45-63`).

Concrete scenario: a user follows `docs/examples/judge-presets/faithfulness-calibration.template.yaml`, puts `CONTEXT: ...` in each `prompt`, and calibrates the returned faithfulness preset rubric. The judge prompt contains the rubric and agent response, but not the grounding context, so the judge is asked to score "supported by supplied context" with no supplied context. Answer relevancy and hallucination have the same issue for their `question`/`context` templates. This can produce a `CalibrationReport` that appears to validate a preset while measuring a different, under-specified task.

Targeted probe confirmed the first prompt from calibrating `docs/examples/judge-presets/faithfulness-calibration.template.yaml` had `has_context_placeholder_in_prompt False`; the rendered prompt contained only `# Rubric` and `# Agent Response`.

### LOW — Preset threshold override range errors escape as bare `ValueError`

`src/AgentEval/judge/library.py:678-680` applies preset threshold overrides through `_with_threshold`, which constructs `JudgeRubric` directly (`src/AgentEval/judge/library.py:784-792`). For `threshold=11.0`, this raises `ValueError: JudgeRubric.threshold must be in [0.0, 10.0]` from the dataclass instead of the public rubric error shape used by criteria-string synthesis (`InvalidJudgeRubricError` with source/field/fix suggestion).

Concrete scenario: `Judge.Get Faithfulness    result=${result}    context=ctx    threshold=11` fails before any LLM call, but Robot users and Python callers see an unstructured Python `ValueError`, unlike `Judge.Score With Criteria` where the same invalid threshold is surfaced as `InvalidJudgeRubricError`. This is not a cost/safety bug, but it is a public keyword diagnostics regression and makes the preset path inconsistent with the new shortcut path.

## Checks Run

- `uv run pytest tests/unit/judge/test_library_shortcuts.py tests/unit/judge/test_presets.py tests/unit/judge/test_library.py tests/unit/judge/test_rubric.py tests/unit/judge/test_types.py tests/unit/conventions/test_keyword_namespace_prefix.py tests/unit/conventions/test_keyword_name_idiom.py tests/integration/docs/test_keyword_count_drift.py -q` -> 85 passed
- `uv run pytest -k "judge or keyword_count or keyword_namespace_prefix or keyword_name_idiom" -q` -> 124 passed, 2 skipped
- Composed keyword probe: `AgentEval().get_keyword_names()` -> 81 keywords; judge surface includes exactly one unprefixed `Judge Score Should Be Above`
- Honesty probe: adapter JSON containing `"calibrated": true` and `"rubric_source": "fake"` still returned `JudgeScore(calibrated=False, rubric_source="criteria_string")`
- Criteria validation probe: `None`, empty, whitespace, `"None"`, and `threshold=11.0` fail before adapter lookup/call
- Grep probes over `calibrated=True`, `rubric_source`, keyword names, count gate, and namespace carve-out

## Non-Findings

- I did not find a keyword path that can return `JudgeScore.calibrated=True`; `_parse_judge_response` stamps `calibrated=False` and ignores any adapter-provided honesty fields.
- `Judge.Get Score` prompt composition is byte-identical for callers that do not pass `extra_sections`.
- Hallucination preset polarity is consistently higher-is-better in the rubric text, keyword docstring, score interpretation, and example assertion.
- The WARN-once path is emitted before the shortcut adapter call and is not caught/swallowed; subsequent shortcut scores log at INFO.
