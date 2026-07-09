# Tasks — add-skill-ab-benchmark

## 1. Types and cohort schema

- [x] 1.1 Add frozen dataclasses to `src/AgentEval/skills/types.py`:
      `SkillBenchmarkTrialEvidence`, `SkillBenchmarkArmSummary`,
      `SkillBenchmarkComparisonResult` (with runtime closed-set validation
      for `skill_delivery` and `verdict` in `__post_init__`, defensive list
      copies per M_R6, `asdict()` round-trip)
- [x] 1.2 Add `InvalidSkillBenchmarkTasksError` to `src/AgentEval/errors.py`
      following the File/Line/Field/Fix format (RFC-6901 `field_name` +
      `fix_suggestion`), mirroring `InvalidSkillDiscoverabilityTasksError`
- [x] 1.3 Implement `load_skill_benchmark_tasks` (benchmark cohort YAML
      loader) in a new internal module `src/AgentEval/skills/_benchmark.py`:
      `id`/`prompt` required, exactly-one grading mode (`expected_content`
      list OR `rubric` path, with file-level `defaults.rubric` fallback),
      duplicate-id rejection, YAML/IO error handling consistent with
      `load_skill_discoverability_tasks`
- [x] 1.4 Unit tests for the loader covering: valid mixed-mode cohort, both
      grading modes on one task, neither mode and no default, duplicate ids,
      missing file, non-YAML extension, malformed YAML, nullish-field fuzz
      (`None`/`""`/`False`/`0`/missing-key per
      `feedback_nullish_input_fuzz_checklist`)

## 2. Arm execution and grading engine

- [x] 2.1 Implement the arm runner in `_benchmark.py`: per-arm N tasks ×
      `trials` loop reusing the `run_single_adapter_skill_discoverability`
      structure (adapter-per-trial construction, cost accumulation), with
      Phase-1 `prompt_injected` skill delivery (delimited skill
      frontmatter+body prepended for skill arms; bare prompt for
      `baseline=none`), collecting per-trial `AgentRunResult` tokens / cost /
      latency
- [x] 2.2 Implement deterministic `expected_content` grading (ALL substrings,
      case-insensitive, against `response_text`)
- [x] 2.3 Implement blind judge grading: compose judge prompts from rubric +
      task prompt + `response_text` ONLY (reuse `judge/` rubric loading and
      response parsing; assert no skill name / arm label in composed prompt),
      assign seed-derived blinded grading ids, seed-shuffle the interleaved
      grading queue, record the blinding map + judge cost per trial
- [x] 2.4 Unit tests for the engine with the mock/generic adapter + canned
      judge responses: two-arm run counts (2 × N × trials), prompt-injection
      presence/absence per arm, expected_content pass/fail, judge
      pass_threshold_met mapping, judge-prompt blindness (candidate vs
      baseline prompts differ only in response_text), deterministic shuffle
      for fixed seed

## 3. Statistics, verdict, evidence assembly

- [x] 3.1 Wire Epic-13 primitives: Mann-Whitney U + Cliff's delta over
      per-task pass-rate distributions, seeded bootstrap CI on the pass-rate
      delta; extras-gate check raising `ImportError` BEFORE fan-out
- [x] 3.2 Implement the closed-set verdict rule (D6): `skill_improves` /
      `skill_regresses` / `skill_unnecessary` (baseline=none only, threshold
      + no-significant-improvement) / `no_significant_difference`
- [x] 3.3 Assemble `SkillBenchmarkComparisonResult`: arm summaries
      (pass_rate, per-task rates, token totals/means, elapsed, cost),
      `pass_rate_delta`, stats fields, verdict, `skill_delivery`, blinding
      record, evidence list (with redaction-pass-applied response excerpts),
      `total_runtime_seconds` anchored at keyword entry (Story 13.3 HIGH-A
      precedent), `total_cost_usd` with judge cost broken out
- [x] 3.4 Unit tests: verdict truth table (all four verdicts + the
      improvement-beats-obsolescence and never-obsolete-in-v1v2 cases),
      bootstrap reproducibility at fixed seed, evidence count = 2 × N ×
      trials, `asdict()` serialization round-trip

## 4. Keyword surface and integrations

- [x] 4.1 Add `CohortHeatmap.from_skill_benchmark` to
      `src/AgentEval/_heatmap/models.py` (rows = task ids, columns =
      candidate/baseline, cells = per-task pass rate) + renderer unit tests
- [x] 4.2 Add the `Skill.Compare Against Baseline` `@keyword` to
      `SkillsLibrary` (`src/AgentEval/skills/library.py`) with `@tier(3)` +
      `@guarded_fanout()`, full signature per spec, upfront validation order
      (polling ban → arg validation → extras gate → cohort load → fan-out),
      judge calls inside the same guarded budget scope, RF-docstring with
      Arguments table / Raises / Example / Notes matching sibling keywords
- [x] 4.3 Unit tests for the keyword: validation matrix (polling, trials=0,
      missing skill/tasks, bad alpha/threshold), extras-gate fail-fast with
      zero adapter constructions, budget-cap trip parity with
      `Skill.Compare Discoverability`, baseline=none vs baseline=path modes
- [x] 4.4 Verify conventions suites pass for the new keyword (verb allowlist,
      tier annotation, namespace multi-word post-dot name per
      `feedback_libdoc_namespace_keyword_must_be_multiword`) and run the
      libdoc-render smoke (no auto-split of the keyword name)

## 5. Gates and documentation

- [x] 5.1 Run `uv run pytest tests/`, `uv run ruff check src/ tests/`,
      `uv run mypy src/` — all green
- [x] 5.2 Grep new files for `DF-X-SY` markers and register each in
      `docs/phase-1-5-carry-overs.md` + `deferred-work.md` (upstream
      carry-over catalog gate); expected entries include Phase-2
      `workspace_installed` delivery
- [x] 5.3 Caller-count check on new public helpers
      (`feedback_caller_count_check`); document any 0-caller helper as a
      DF entry
- [x] 5.4 Add the keyword to the README keyword table + docs/index.md counts
      (do not worsen finding E3 drift) and add a minimal recipe snippet;
      smoke-execute any fenced code block per
      `feedback_executable_doc_precheck`
