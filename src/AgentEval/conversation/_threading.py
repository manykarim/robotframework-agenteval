# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Turn-threading core (add-multi-turn-conversation-testing design D4).

`execute_turn` appends a user turn + an agent turn to a `ConversationHandle`
and returns the agent turn's `AgentRunResult`. It threads via the adapter's
optional `run_turn` (`native_session`) when present, else composes a delimited
history preamble into the ordinary `run()` (`replayed_history`). Every agent
turn records its honest `continuation` value.

Shared by `Send Message`, `Simulate User`, and `Run Scenario`'s `turns:` path
so all three surfaces produce byte-identical threading + honesty fields.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from AgentEval.conversation._renderer import render_replay_prompt
from AgentEval.conversation.state import ConversationState
from AgentEval.errors import ConversationClosedError
from AgentEval.types import AgentRunResult, ConversationTranscript, ConversationTurn

if TYPE_CHECKING:
    from AgentEval.conversation._handle import ConversationHandle

__all__ = ["execute_turn", "snapshot_transcript"]


def execute_turn(
    handle: ConversationHandle,
    message: str,
    *,
    call_kwargs: dict[str, Any] | None = None,
    simulator_cache: str | None = None,
) -> AgentRunResult:
    """Thread one user→agent exchange onto `handle`; return the agent result.

    Args:
        handle: the live `ConversationHandle`.
        message: the new user message text.
        call_kwargs: per-call kwargs merged over the handle's frozen run
            kwargs (per-call wins).
        simulator_cache: for a simulated user turn, the cache status
            (`"hit"`/`"miss"`/`"disabled"`) recorded on the user turn.

    Raises:
        ConversationClosedError: the handle was already ended.
    """
    if handle._closed:
        raise ConversationClosedError(
            f"conversation on adapter {handle.adapter_name!r} is closed; "
            f"no further messages can be sent (it already has {handle.agent_turn_count} agent turn(s))",
            fix_suggestion=(
                "Start a fresh conversation with `Start Conversation` for a new exchange; "
                "`Get Conversation Transcript` still works on a closed handle."
            ),
        )

    run_kwargs: dict[str, Any] = {**handle._run_kwargs, **(call_kwargs or {})}

    # Snapshot prior turns BEFORE appending the new user turn.
    prior_turns: tuple[ConversationTurn, ...] = tuple(handle._turns)
    first_agent_turn = not any(t.role == "agent" for t in prior_turns)

    # Append the user turn.
    user_index = len(handle._turns)
    handle._turns.append(
        ConversationTurn(
            index=user_index,
            role="user",
            content=message,
            simulator_cache=simulator_cache,  # type: ignore[arg-type]
        )
    )

    adapter = handle._adapter
    if handle.supports_native:
        state = ConversationState(prior_turns=prior_turns, session_ref=handle._session_ref)
        result = _assert_agent_run_result(adapter.run_turn(message, conversation_state=state, **run_kwargs), adapter)
        handle._session_ref = state.session_ref
        # First agent turn is always `initial`. Otherwise the adapter MAY report
        # an honest degradation (session capture failed); default to the
        # advertised native mode when it stays silent.
        continuation = "initial" if first_agent_turn else (state.continuation or "native_session")
    else:
        if first_agent_turn:
            prompt = message
            continuation = "initial"
        else:
            prompt = render_replay_prompt(prior_turns, message)
            continuation = "replayed_history"
        result = _assert_agent_run_result(adapter.run(prompt, **run_kwargs), adapter)

    # HIGH fix (add-multi-turn-conversation-testing codex review): stamp the
    # honest per-turn `continuation` into the result's metadata so the signal
    # survives on the bare `AgentRunResult` a caller receives — notably the flat
    # list `Run Scenario` returns for a `turns:` eval, where the private
    # `ConversationTurn` is discarded. `metadata.continuation` is the honesty
    # sibling of `mcp_coverage` (ADR-016). Single-shot / `prompt:` runs never
    # reach this path, so their `continuation` stays None (unchanged shape).
    result = dataclasses.replace(
        result,
        metadata=dataclasses.replace(result.metadata, continuation=continuation),  # type: ignore[arg-type]
    )

    agent_index = len(handle._turns)
    handle._turns.append(
        ConversationTurn(
            index=agent_index,
            role="agent",
            content=result.response_text,
            result=result,
            continuation=continuation,  # type: ignore[arg-type]
        )
    )
    return result


def _assert_agent_run_result(result: Any, adapter: Any) -> AgentRunResult:
    if not isinstance(result, AgentRunResult):
        raise TypeError(
            f"adapter {getattr(adapter, 'name', type(adapter).__name__)!r} returned "
            f"{type(result).__name__}, expected AgentRunResult"
        )
    return result


def _continuation_mode(agent_turns: list[ConversationTurn]) -> str:
    """Reduce per-turn continuation values to one conversation-wide mode."""
    if not agent_turns:
        return "none"
    # A single agent turn is always `initial`.
    if len(agent_turns) == 1:
        return agent_turns[0].continuation or "initial"
    # Post-first turns carry the operative mode; `initial` (turn 1) is expected.
    post_first = {t.continuation for t in agent_turns[1:]}
    if len(post_first) == 1:
        return next(iter(post_first)) or "initial"
    return "mixed"


def snapshot_transcript(handle: ConversationHandle) -> ConversationTranscript:
    """Build an immutable `ConversationTranscript` snapshot from the handle.

    Aggregates reconcile with per-turn results: `total_cost_usd` sums agent
    turns' `result.cost_usd` plus any recorded simulator costs;
    `total_latency_seconds` sums agent turns' `result.latency_seconds`.
    """
    turns = tuple(handle._turns)
    agent_turns = [t for t in turns if t.role == "agent"]
    total_cost = sum((t.result.cost_usd for t in agent_turns if t.result is not None), 0.0)
    total_cost += handle._simulator_cost_usd
    total_latency = sum((t.result.latency_seconds for t in agent_turns if t.result is not None), 0.0)
    return ConversationTranscript(
        turns=turns,
        turn_count=len(agent_turns),
        total_cost_usd=total_cost,
        total_latency_seconds=total_latency,
        continuation_mode=_continuation_mode(agent_turns),
        stop_reason=handle._stop_reason,
    )
