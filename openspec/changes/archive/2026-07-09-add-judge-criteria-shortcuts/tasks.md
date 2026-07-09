## 1. JudgeScore honesty fields + parser refactor (foundation)

- [x] 1.1 Add `calibrated: bool = False` + `rubric_source: str = "file"` fields to `JudgeScore` in `src/AgentEval/judge/types.py` (additive, frozen preserved; docstring states "no keyword sets calibrated=True in Phase-1 — the flag means recorded passing calibration evidence, which nothing threads yet")
- [x] 1.2 Extract `parse_rubric_text(raw_text, *, source)` from `load_rubric` in `src/AgentEval/judge/rubric.py`; `load_rubric` becomes file-IO wrapper (extension/existence checks stay in the wrapper; section/bullet/threshold validation moves to the text parser with unchanged error types + fields)
- [x] 1.3 Unit tests: existing rubric-loading tests stay green unmodified; new tests for `parse_rubric_text` direct use; `JudgeScore` default-field construction + `dataclasses.asdict()` includes the 2 new keys
- [x] 1.4 Grep existing `JudgeScore(` construction sites + dogfood asdict consumers and confirm no updates needed (or apply mechanical updates)

## 2. Criteria-string scoring (`Judge.Score With Criteria`)

- [x] 2.1 Implement rubric synthesis helper (criteria string + threshold → `JudgeRubric` with `criteria=(("user_criteria", <string>),)` and standard-format `raw_text`); round-trip test: synthesized `raw_text` re-parses via `parse_rubric_text` to an equivalent rubric
- [x] 2.2 Validate inputs fail-loud BEFORE any LLM call: empty/whitespace/nullish criteria → `InvalidJudgeRubricError` with `fix_suggestion` (cover `None`-string, `""`, whitespace per `feedback_nullish_input_fuzz_checklist`); out-of-range threshold → existing range error
- [x] 2.3 Add `Judge.Score With Criteria` keyword to `src/AgentEval/judge/library.py` with `@keyword` + `@tier(2)` + `@guarded_fanout()`, args `result`, `criteria`, `threshold=7.0`, `judge_adapter="generic"`, `judge_model=None`, `**adapter_kwargs`; returns `JudgeScore` with `calibrated=False`, `rubric_source="criteria_string"` (multi-word post-dot name satisfies `feedback_libdoc_namespace_keyword_must_be_multiword`)
- [x] 2.4 Implement WARN-once-per-process / INFO-thereafter uncalibrated-score log (module-level once-flag; message names `rubric_source` + points to `docs/recipes/judge-calibration.md`); unit test with two consecutive calls asserting exactly one WARN then INFO
- [x] 2.5 Unit tests with a fake adapter: happy path (score/pass/reasoning/rubric_source), threshold boundary (`score == threshold` → pass), malformed judge JSON still raises `JudgeOutputParseError`

## 3. Preset registry + preset keywords

- [x] 3.1 Create `src/AgentEval/judge/presets.py`: 3 embedded Markdown rubric constants (`faithfulness`, `answer_relevancy`, `hallucination`, each threshold 7.0), lazily parsed via `parse_rubric_text`; `get_preset_rubric(name)` raising a loud error listing available names on unknown preset; hallucination rubric text states higher-is-better grounding semantics in its first line
- [x] 3.2 Extend `_compose_judge_prompt` with optional `extra_sections` (default empty) rendered as `# <title>` blocks between rubric and agent response; regression unit test asserting byte-identical output vs pre-change composition when no extra sections supplied
- [x] 3.3 Add `Judge.Get Faithfulness` (requires `context`), `Judge.Get Answer Relevancy` (requires `question`), `Judge.Get Hallucination Score` (requires `context`) — each `@tier(2)` + `@guarded_fanout()`, optional `threshold` override, standard adapter pass-through, returns `JudgeScore` with `rubric_source="preset:<name>"`, `calibrated=False`; docstrings quote criteria bullets verbatim + state what the preset does NOT measure; hallucination docstring first paragraph states 10.0 = no hallucination
- [x] 3.4 Add `Judge.Get Preset Rubric` keyword returning the parsed `JudgeRubric` (Tier-1-safe, no LLM call; no `@guarded_fanout`)
- [x] 3.5 Unit tests: each preset composes prompt containing rubric + supplied context/question section + response; missing `question`/`context` fails with clear argument error (no silent substitution from `AgentRunResult`); threshold override respected; unknown preset name error lists available presets; preset rubric → `Judge.Calibrate Rubric` with the existing 5-row calibration fixture completes and returns a `CalibrationReport` (fake adapter)
- [x] 3.6 Add per-preset calibration-set template YAMLs under `docs/examples/judge-presets/` (schema accepted by `load_calibration_set`; placeholder rows + labeling-guidance comments; NO shipped κ claims anywhere)

## 4. Assertion form (`Judge Score Should Be Above`)

- [x] 4.1 Add `Judge Score Should Be Above` keyword to `JudgeLibrary` (`@tier(2)` + `@guarded_fanout()`; args `result`, `criteria`, `threshold=7.0` + adapter pass-through); delegates to the criteria-string scoring path; passes on `numeric_score >= threshold` (docstring states >= explicitly); returns the `JudgeScore` on pass
- [x] 4.2 Failure message includes numeric score, threshold, `calibrated=False`/`rubric_source` marker, and judge `reasoning`
- [x] 4.3 Unit tests: fail path message content, pass path returns score, boundary equality passes, empty criteria fails before LLM call

## 5. Docs + surface registration

- [x] 5.1 Update `docs/recipes/judge-calibration.md` with the two-tier story ("start with a criteria string in one line; graduate to a calibrated rubric for CI gates"), preset graduation via `Judge.Get Preset Rubric` → `Judge.Calibrate Rubric`, and the uncalibrated-by-default rationale for presets
- [x] 5.2 Smoke-execute every new/changed doc code block per `feedback_executable_doc_precheck` (`robot --dryrun` for RF blocks / `python -c` for snippets)
- [x] 5.3 Add the 6 new keywords + `JudgeScore` field additions + `presets.py` surface to `docs/contracts/stability-surface.md`
- [x] 5.4 Libdoc-render smoke check: all 5 `Judge.*` names render un-split (multi-word post-dot rule) and `Judge Score Should Be Above` renders as-is

## 6. Quality gates & review

- [x] 6.1 `uv run ruff check src/ tests/` clean; `uv run mypy src/` clean
- [x] 6.2 `uv run pytest tests/` green — including all pre-existing judge unit + dogfood tests unmodified where possible (byte-identical prompt regression test from 3.2 green)
- [x] 6.3 Caller-count check (`feedback_caller_count_check`): new public helpers (`parse_rubric_text`, `get_preset_rubric`) each have ≥1 caller or a `DF-*` caller-gap entry
- [x] 6.4 Carry-over catalog gate: grep new/changed files for `DF-X-SY` markers (incl. the deferred `calibration_report=` evidence-binding for `calibrated=True`) and verify each is in `docs/phase-1-5-carry-overs.md`
- [ ] 6.5 Run the cross-LLM review chain (Tiers 1+2 in parallel; Tier 3 on degradation) per CLAUDE.md; apply HIGH findings inline before marking done
