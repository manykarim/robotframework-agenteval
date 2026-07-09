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

"""LLM-driven user simulator core (add-multi-turn-conversation-testing D5 / Task 7.1).

Reuses the judge's architectural recipe (an adapter-backed single-shot LLM call
with a composed prompt): compose simulator prompt (persona + goal + rendered
transcript) → `simulator_adapter.run()` → extract next user message → thread it
onto the handle via the SAME turn machinery as `Send Message` → check stop.

Stop conditions (design D5): the simulator is instructed to emit a sentinel
token (`<<GOAL_ACHIEVED>>` / `<<GIVING_UP>>`) when the goal is met or
unmeetable; `max_turns` is the hard cap. The returned transcript records
`stop_reason ∈ {"goal_achieved", "gave_up", "max_turns"}` and sentinels are
STRIPPED from the recorded user turns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from AgentEval._kernel.adapter_kwargs import split_adapter_kwargs
from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import current_cancel_event
from AgentEval.conversation._cache import SimulationCache
from AgentEval.conversation._renderer import render_transcript_text
from AgentEval.conversation._threading import execute_turn
from AgentEval.errors import ConversationClosedError

if TYPE_CHECKING:
    from AgentEval.conversation._handle import ConversationHandle

__all__ = ["run_simulation", "GOAL_ACHIEVED_SENTINEL", "GIVING_UP_SENTINEL"]

GOAL_ACHIEVED_SENTINEL = "<<GOAL_ACHIEVED>>"
GIVING_UP_SENTINEL = "<<GIVING_UP>>"


def _compose_simulator_prompt(persona: str, goal: str, prior_turns: Any) -> str:
    """Assemble the prompt that drives one simulated-user message."""
    transcript = render_transcript_text(prior_turns) if prior_turns else "(the conversation has not started yet)"
    return (
        "You are role-playing a USER talking to an AI assistant. Stay in character.\n\n"
        f"# Your persona\n{persona}\n\n"
        f"# Your goal\n{goal}\n\n"
        "# Conversation so far\n"
        f"{transcript}\n\n"
        "# Instructions\n"
        "Write ONLY your next message to the assistant, as the user. Do not narrate, "
        "do not include a role label, do not quote the assistant.\n"
        f"- When your goal has been fully met, append the token {GOAL_ACHIEVED_SENTINEL} at the very end.\n"
        f"- When the goal is impossible or the assistant cannot help, append {GIVING_UP_SENTINEL} at the end.\n"
        "- Otherwise write just your next user message with no token."
    )


def _detect_sentinel(raw: str) -> str | None:
    """Map a simulator response to a stop reason, or None to continue."""
    if GOAL_ACHIEVED_SENTINEL in raw:
        return "goal_achieved"
    if GIVING_UP_SENTINEL in raw:
        return "gave_up"
    return None


def _strip_sentinels(raw: str) -> str:
    return raw.replace(GOAL_ACHIEVED_SENTINEL, "").replace(GIVING_UP_SENTINEL, "").strip()


def run_simulation(
    handle: ConversationHandle,
    *,
    persona: str,
    goal: str,
    max_turns: int,
    simulator_adapter: str,
    simulator_model: str | None,
    cache_key: str | None,
    agent_call_kwargs: dict[str, Any],
    simulator_kwargs: dict[str, Any],
) -> None:
    """Drive `handle` with a simulated user until a stop condition (design D5).

    Mutates `handle` in place (appending simulated user + agent turns,
    accumulating simulator cost, and setting `_stop_reason`). Cooperatively
    honors `@guarded_fanout` cancellation (the caller keyword is Tier-3): on a
    budget breach the meter thread sets the cancel event, the loop exits, and
    the decorator raises the typed budget error after the body returns.
    """
    if max_turns < 1:
        raise ValueError(f"max_turns must be >= 1, got {max_turns}")

    sim_cls = get_adapter(simulator_adapter)
    ctor_kwargs, run_kwargs = split_adapter_kwargs(sim_cls, dict(simulator_kwargs))
    sim_instance = sim_cls(**ctor_kwargs)
    sim_run_kwargs = dict(run_kwargs)
    if simulator_model is not None:
        sim_run_kwargs["model"] = simulator_model

    cache = SimulationCache(cache_key)
    cancel_event = current_cancel_event()

    # add-multi-turn-conversation-testing codex-review MED fix: fail fast on a
    # closed handle before any simulator LLM call, and defensively re-check at
    # the top of each loop iteration. `execute_turn` only raises once a non-empty
    # user message is threaded, so a simulator that immediately emits a bare
    # stop-sentinel (stripping to empty) would otherwise "succeed" on a closed
    # conversation. The keyword surface (`Simulate User`) also prechecks; this
    # guard protects direct `run_simulation` callers + mid-loop close.
    if handle._closed:
        raise ConversationClosedError(
            f"conversation on adapter {handle.adapter_name!r} is closed; "
            f"`Simulate User` cannot drive it (it already has "
            f"{handle.agent_turn_count} agent turn(s))",
            fix_suggestion=(
                "Start a fresh conversation with `Start Conversation` before simulating a user; "
                "`Get Conversation Transcript` still works on a closed handle."
            ),
        )

    stop_reason = "max_turns"
    for _ in range(max_turns):
        if handle._closed:
            raise ConversationClosedError(
                f"conversation on adapter {handle.adapter_name!r} was closed mid-simulation; "
                f"no further user turns can be driven (it has {handle.agent_turn_count} agent turn(s))",
                fix_suggestion=(
                    "Do not `End Conversation` while a `Simulate User` loop is in flight; "
                    "`Get Conversation Transcript` still works on a closed handle."
                ),
            )
        if cancel_event is not None and cancel_event.is_set():
            # Budget breach recorded by the meter thread — stop cooperatively;
            # the @guarded_fanout wrapper raises the typed error after return.
            return
        prior_turns = handle.turns
        turn_index = handle.agent_turn_count
        cached, status = cache.lookup(turn_index, prior_turns)
        if cached is not None:
            raw = cached
        else:
            sim_prompt = _compose_simulator_prompt(persona, goal, prior_turns)
            sim_result = sim_instance.run(sim_prompt, **sim_run_kwargs)
            raw = sim_result.response_text
            handle._simulator_cost_usd += sim_result.cost_usd
            cache.store(turn_index, prior_turns, raw)

        sentinel = _detect_sentinel(raw)
        user_message = _strip_sentinels(raw)

        if user_message:
            execute_turn(handle, user_message, call_kwargs=agent_call_kwargs, simulator_cache=status)

        if sentinel == "goal_achieved":
            stop_reason = "goal_achieved"
            break
        if sentinel == "gave_up":
            stop_reason = "gave_up"
            break

    handle._stop_reason = stop_reason
