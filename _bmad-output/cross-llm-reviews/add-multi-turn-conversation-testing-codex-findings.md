# Codex adversarial review: add-multi-turn-conversation-testing

Reviewed working tree on branch `implement-explore-findings` against `openspec/changes/add-multi-turn-conversation-testing/`. No live API calls.

Targeted verification run:

```bash
uv run pytest tests/unit/conversation tests/unit/scenarios/test_turns.py tests/unit/coding_agent/test_claude_code_cli_run_turn.py tests/unit/judge/test_conversation_judge.py tests/unit/metrics/test_metrics_library.py tests/unit/test_composition.py tests/unit/conventions/test_keyword_namespace_prefix.py tests/integration/docs/test_keyword_count_drift.py -q
```

Result: `112 passed in 23.12s`.

## Findings

### HIGH: `Run Scenario` drops the continuation honesty signal from YAML `turns:` results

`Run Scenario` promises a flat `list[AgentRunResult]` where each multi-turn result still carries the per-turn continuation signal. The implementation only records `continuation` on the internal `ConversationTurn` appended by `execute_turn`, then discards the handle/transcript and returns the bare `AgentRunResult`.

- `src/AgentEval/orchestration/library.py:321` says the per-turn `continuation` honesty field survives.
- `src/AgentEval/orchestration/library.py:347` calls `execute_turn(handle, turn_message)`.
- `src/AgentEval/orchestration/library.py:349` appends only `turn_result` to the public flat result list.
- `src/AgentEval/types.py:388` defines `AgentRunResult` with no `continuation` field.
- `src/AgentEval/types.py:326` defines `AgentRunMetadata` with only `completeness` and `mcp_coverage`, so the signal is not in metadata either.

Concrete scenario: a YAML eval with two `turns:` runs against a replay-only adapter. Turn 2 is truthfully labeled `replayed_history` on the private `ConversationTurn`, but the caller receives only `AgentRunResult` objects and cannot inspect whether the adapter replayed history or used a native session. I confirmed locally with a no-network replay adapter:

```text
result_attrs_continuation [False, False]
metadata_attrs_continuation [False, False]
```

This breaks the load-bearing honest-degradation contract for YAML-driven cross-adapter comparisons: replay-only adapters do not falsely report `native_session`, but the required in-band degradation signal is absent from the only object `Run Scenario` returns.

### MED: `Simulate User` can succeed on a closed conversation instead of raising `ConversationClosedError`

`Send Message` is guarded by `execute_turn`, but `Simulate User` does not check the handle lifecycle before calling the simulator. If the simulator response strips to an empty user message, `execute_turn` is never reached, so a closed handle returns a transcript instead of raising.

- `src/AgentEval/conversation/library.py:359` documents that `Simulate User` raises `ConversationClosedError` on a closed handle.
- `src/AgentEval/conversation/library.py:374` calls `run_simulation(...)` without a closed-handle precheck.
- `src/AgentEval/conversation/simulator.py:119` reads `handle.turns` and proceeds on closed handles.
- `src/AgentEval/conversation/simulator.py:126` calls the simulator adapter before any lifecycle check.
- `src/AgentEval/conversation/simulator.py:134` only calls `execute_turn(...)` when `user_message` is non-empty.

Concrete scenario: end a conversation, then call `Simulate User` with a simulator that returns only `<<GOAL_ACHIEVED>>`. The sentinel strips to an empty user message, no agent turn is sent, and the keyword returns `stop_reason="goal_achieved"` with `turn_count=0` instead of raising. I confirmed locally:

```text
returned goal_achieved 0
```

Even when the simulator returns a non-empty message, the code spends a simulator LLM call before `execute_turn` raises. The closed-handle check should happen before simulator construction/calls and probably at the top of each loop iteration as a defensive guard.

### MED: multi-turn `Run Scenario` silently drops `mcp_servers` for `turns:` evals

`Run Scenario` resolves `mcp_servers` once and forwards it for single-prompt evals, but the multi-turn path never passes it into `execute_turn`. This creates silent no-MCP execution for `turns:` evals while the same keyword argument is honored for `prompt:` evals.

- `src/AgentEval/orchestration/library.py:300` initializes `mcp_servers_resolved`.
- `src/AgentEval/orchestration/library.py:308` sets it from a caller-provided dict.
- `src/AgentEval/orchestration/library.py:347` calls `execute_turn(handle, turn_message)` with no `call_kwargs`.
- `src/AgentEval/orchestration/library.py:354` correctly passes `mcp_servers=mcp_servers_resolved` for single-prompt evals.

Concrete scenario: call `Run Scenario` with `mcp_servers={"echo": handle}` and a YAML `turns:` eval. A replay-only probe adapter saw `mcp_servers=None` on every turn:

```text
mcp_args [None, None]
```

This is especially risky because `GenericAdapter.run_turn` explicitly raises on non-empty `mcp_servers` (`src/AgentEval/coding_agent/generic.py:292`), but the current scenario path hides that unsupported configuration by dropping the handles before the adapter sees them.

## Non-findings checked

- Replay-only keyword conversations do not report `native_session`; the non-native path in `execute_turn` labels turn 1 `initial` and later turns `replayed_history`.
- `Start Conversation require_native=True` fast-fails adapters without `run_turn` before any LLM call.
- `GenericAdapter.run_turn` includes prior user and assistant turns before appending the current user message; no off-by-one/drop found in the message-history path.
- `ClaudeCodeCLIAdapter.run_turn` degrades to `replayed_history` when no session id is captured and uses `--resume <session_id>` when one is available.
- Scenario loader rejects both/neither `prompt|turns`, empty `turns`, non-string turns, and blank turns; existing single-`prompt` scenarios still load.
- `Run Scenario` still returns a flat `list[AgentRunResult]`.
- `Simulate User` is `@guarded_fanout` Tier-3 and `max_turns` caps the loop.
- Simulation cache key includes `cache_key`, `turn_index`, and rendered prior turn role/content, so changed agent text invalidates subsequent cached user turns.
- `ConversationLibrary` is composed into the top-level `AgentEval` library, categorized in namespace convention tests, and the keyword count gate passes at 90.
