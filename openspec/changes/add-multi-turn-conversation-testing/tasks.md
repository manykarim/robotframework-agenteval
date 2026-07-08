## 1. Shared types and errors (foundation)

- [ ] 1.1 Add `ConversationTurn` (index, role, content, result, continuation)
      and `ConversationTranscript` (turns, turn_count, total_cost_usd,
      total_latency_seconds, continuation_mode, stop_reason) frozen dataclasses
      to `src/AgentEval/types.py` with M_R6 defensive copies; unit tests for
      immutability and `asdict()` round-trip
- [ ] 1.2 Add `ConversationClosedError` and
      `ConversationContinuationUnsupportedError` to `src/AgentEval/errors.py`
      (File/Line/Field/Fix message discipline + `fix_suggestion`; exactly 2 new
      leaves per design D9); unit tests for message format
- [ ] 1.3 Define `ConversationState` (prior turns + adapter-opaque
      `session_ref`) and the optional duck-typed `run_turn()` contract doc in
      `src/AgentEval/conversation/` (do NOT touch the `CodingAgentAdapter`
      Protocol in `types.py`)

## 2. Conversation lifecycle library

- [ ] 2.1 Create `src/AgentEval/conversation/library.py` with
      `Start Conversation` (Tier-1; adapter discovery + `_split_adapter_kwargs`
      reuse; `require_native=` probe raising
      `ConversationContinuationUnsupportedError`), returning a test-owned
      `ConversationHandle` (adapter instance reused across turns; closed flag)
- [ ] 2.2 Implement `Send Message` (Tier-2): append user turn → thread via
      `run_turn` when adapter exposes it (`native_session`) else history-replay
      preamble into `run()` (`replayed_history`) → append agent turn with
      honest `continuation` value → return the turn's `AgentRunResult`;
      `ConversationClosedError` on closed handles
- [ ] 2.3 Implement `Get Conversation Transcript` (frozen snapshot; aggregates
      reconcile with per-turn results) and `End Conversation` (close + release
      native resources; transcript stays readable)
- [ ] 2.4 Implement `Transcript Should Contain` (Tier-1; role filter +
      `as_regex`; failure message reports text, role, turns inspected)
- [ ] 2.5 Implement the shared transcript renderer (used by replay preamble,
      judge prompts, and simulator prompts — design Open Question 3 resolution)
- [ ] 2.6 Compose `ConversationLibrary` into `_SUB_LIBRARIES` in
      `src/AgentEval/library.py` with `_HostBudgetPlumbing` budget auto-wiring;
      verify no `Get Frontmatter`-style keyword-name collisions (dossier E4)
- [ ] 2.7 Unit tests: lifecycle happy path on mock provider (deterministic, no
      keys), snapshot stability, closed-handle errors, replay-fallback prompt
      content, `require_native` fast-fail

## 3. Native continuation: generic adapter

- [ ] 3.1 Implement `GenericAdapter.run_turn()` building the full
      `messages=[...]` history from `conversation_state` (extends the
      single-message construction at `generic.py:216`)
- [ ] 3.2 Unit tests: mock provider receives full history on turn 2+;
      turn 1 `continuation="initial"`, turn 2 `"native_session"`

## 4. Judge at turn and transcript level

- [ ] 4.1 Document per-turn usage in `Judge.Get Score` docstring (works today —
      a turn result IS an `AgentRunResult`); add `ConversationTranscript`
      acceptance rendering the full role-tagged transcript via the shared
      renderer in `_compose_judge_prompt`
- [ ] 4.2 Implement `Judge Turn Should Pass` (Tier-2, `@guarded_fanout`;
      `turn=` index selection incl. negatives; out-of-range fails without an
      LLM call; failure message carries score + threshold + reasoning)
- [ ] 4.3 Unit tests with a stubbed judge adapter: turn selection, transcript
      rendering content, pass/fail assertion behavior

## 5. Conversational metrics

- [ ] 5.1 Implement `Get Conversation Results` and `Get Turn Count` (Tier-1;
      accept handle OR transcript) in `src/AgentEval/metrics/library.py`
- [ ] 5.2 Unit tests: extraction order, existing `Get Cost Total` /
      `Get Latency P95` aggregation over extracted lists
- [ ] 5.3 Browser-Library-style docstrings with tier annotations + a chained
      aggregation example; libdoc render smoke (multi-word keyword-name norm)

## 6. Native continuation: claude-code-cli (empirical probe first)

- [ ] 6.1 Empirical probe (per
      `feedback_listener_hook_api_surface_empirical_check`): capture real
      `claude -p --resume <session_id>` stream-json against the pinned
      `>=2.0.0,<3.0.0` binary; save fixtures under
      `tests/fixtures/claude_code_cli/`; record findings in the probe notes
- [ ] 6.2 Implement `ClaudeCodeCLIAdapter.run_turn()`: capture session id from
      the `system`/init event on turn 1, spawn later turns with `--resume`;
      fall back to `replayed_history` (honesty field) if the probe shows
      resume is unusable in `-p` mode
- [ ] 6.3 Fixture-driven unit tests + gated live integration smoke
      (`AGENTEVAL_INTEGRATION_TESTS`, mirroring `tests/integration/test_*_live.py`)
- [ ] 6.4 Add documented follow-up markers (carry-over convention) for native
      continuation on codex/copilot/opencode/openai-agents adapters; run the
      carry-over catalog gate (grep new files for `DF-X-SY` patterns and
      catalog each)

## 7. Simulated user

- [ ] 7.1 Implement the simulator core in
      `src/AgentEval/conversation/simulator.py`: persona/goal/transcript prompt
      composition, sentinel-token stop protocol (`goal_achieved` / `gave_up` /
      `max_turns`), sentinel stripped from recorded turns
- [ ] 7.2 Implement `Simulate User` keyword (Tier-3, `@guarded_fanout()`;
      `simulator_adapter=`/`simulator_model=` mirroring judge naming; returns
      transcript with `stop_reason`; simulator costs added to
      `total_cost_usd`)
- [ ] 7.3 Implement the `cache_key` disk cache under
      `${OUTPUT_DIR}/agenteval/simulation-cache/` keyed by
      hash(cache_key, turn_index, transcript_so_far); per-turn
      `simulator_cache` hit/miss/disabled status on the transcript
- [ ] 7.4 Unit tests on mock provider: turn cap, sentinel stop + stripping,
      mixed scripted-then-simulated flow, budget-abort mid-loop
      (`__agenteval_test_budget__` override), cache hit replay + divergence
      invalidation

## 8. Scenario YAML turns (BREAKING — land last)

- [ ] 8.1 Extend `ScenarioEval` in `src/AgentEval/scenarios/schema.py` with
      `turns: list[str]`; loader validation in `scenarios/loader.py` becomes
      exactly-one-of `prompt` | `turns` with JSON-Pointer `field_name` errors
- [ ] 8.2 Extend `Run Scenario` in `src/AgentEval/orchestration/library.py`:
      turns evals run as one conversation per repetition (fresh handle each
      repeat) via the conversation layer; flat ordered `list[AgentRunResult]`
      return preserved; existing prompt evals unchanged
- [ ] 8.3 Unit tests: exactly-one-of validation matrix (both / neither / empty
      / non-string), 3-turns×repeat-2 ordering, fresh-handle isolation, mixed
      prompt+turns suites, replay-only-adapter honest degradation
- [ ] 8.4 Update `docs/` scenario schema reference + release notes flagging the
      pre-1.0 breaking validation change

## 9. Docs, dogfood, and validation gates

- [ ] 9.1 Recipe doc showing BOTH styles side by side (scripted `Send Message`
      sequence vs `Simulate User`, plus the mixed style) with per-recipe
      troubleshooting table; run the executable-doc precheck
      (`robot --dryrun` / smoke-execute every code block per
      `feedback_executable_doc_precheck`)
- [ ] 9.2 Note in the recipe + design docs that `add-red-team-probes` builds
      multi-turn attack loops on `ConversationHandle`/`Simulate User` (do not
      implement attacks here)
- [ ] 9.3 Dogfood `.robot` test under `tests/dogfood/` driving a scripted +
      simulated conversation on the mock provider; dogfood fake-green precheck
      before review (`feedback_dogfood_fake_green_precheck`)
- [ ] 9.4 Update README keyword tables + `docs/contracts/stability-surface.md`
      with the new keywords/types; verify keyword counts honestly
      (`feedback_honest_framing` — dossier E3 counts are already drifted; do
      not worsen)
- [ ] 9.5 Full gates: `uv run pytest tests/`, `uv run ruff check src/ tests/`,
      `uv run mypy src/`, libdoc render smoke, caller-count check on new
      public helpers (`feedback_caller_count_check`)
