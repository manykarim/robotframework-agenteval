# Claude Code CLI multi-turn `--resume` probe notes

add-multi-turn-conversation-testing Task 6.1 (per
`feedback_listener_hook_api_surface_empirical_check`).

## What is captured here

Two stream-json fixtures modelling a native two-turn Claude Code session:

- `multiturn_turn1_stream.jsonl` — turn 1. The `system`/`init` event carries
  `session_id` (here `"mt-session-42"`); every subsequent event repeats it.
  `ClaudeCodeCLIAdapter._finalize` captures the first `session_id` it sees into
  `self._last_session_id`, and `run_turn` stashes it into
  `ConversationState.session_ref`.
- `multiturn_turn2_resume_stream.jsonl` — turn 2, spawned with
  `claude --output-format=stream-json --verbose --print --resume mt-session-42 -- <prompt>`.
  The same `session_id` is returned (resume preserves it), and the usage shows
  `cache_read_input_tokens > 0` — the model re-read the prior turn from the
  resumed session rather than from a replayed text preamble.

## Invocation shape (to be finalized against the pinned 2.x binary)

The `_spawn` argv adds `--resume <session_id>` BEFORE the `--` end-of-options
sentinel when `run_turn` passes `_resume_session_id`:

    claude --output-format=stream-json --verbose --print --resume mt-session-42 -- "Make it business class"

## Honest-degradation contract

The EXACT `--resume` flag surface for non-interactive `-p` mode on the pinned
`>=2.0.0,<3.0.0` line is verified by the gated live smoke
`tests/integration/test_claude_code_cli_multiturn_live.py`
(`AGENTEVAL_INTEGRATION_TESTS=1`). If the live probe shows resume is unusable,
`run_turn` falls back to `replayed_history` (composing a delimited history
preamble into an ordinary `run()`) and records
`ConversationState.continuation = "replayed_history"` — the honesty field means
tests keep passing with the TRUE mode visible in the transcript rather than the
adapter lying about a native session that isn't there.
