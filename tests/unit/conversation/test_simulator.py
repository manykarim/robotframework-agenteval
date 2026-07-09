# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Simulated-user unit tests (add-multi-turn-conversation-testing Task 7.4).

Deterministic on the mock provider + a scripted simulator adapter — no API keys.
"""

from __future__ import annotations

import pytest

from AgentEval._kernel import guardrails
from AgentEval.conversation import _cache as cache_mod
from AgentEval.conversation._cache import SimulationCache
from AgentEval.conversation.library import ConversationLibrary
from AgentEval.errors import ConversationClosedError, CostExceededError
from AgentEval.types import ConversationTurn

from . import conftest as ctx


def _simulate(lib: ConversationLibrary, **kw: object) -> object:
    conv = lib.start_conversation(adapter="native-mock")
    return lib.simulate_user(
        conv,
        persona="impatient traveler",
        goal="book the cheapest flight to Oslo",
        simulator_adapter="scripted-sim",
        **kw,
    )


def test_max_turns_caps_the_loop(lib: ConversationLibrary) -> None:
    ctx.SIM_SCRIPT.extend(["msg one", "msg two", "msg three", "msg four"])
    t = _simulate(lib, max_turns=3)
    assert t.turn_count == 3
    assert t.stop_reason == "max_turns"


def test_goal_achieved_sentinel_stops_early_and_is_stripped(lib: ConversationLibrary) -> None:
    ctx.SIM_SCRIPT.extend(["keep looking", "great, done <<GOAL_ACHIEVED>>", "should not run"])
    t = _simulate(lib, max_turns=5)
    assert t.stop_reason == "goal_achieved"
    assert t.turn_count == 2
    # The sentinel is absent from the recorded user turn.
    user_turns = [turn.content for turn in t.turns if turn.role == "user"]
    assert user_turns[-1] == "great, done"
    assert "<<GOAL_ACHIEVED>>" not in "".join(user_turns)


def test_gave_up_sentinel_records_stop_reason(lib: ConversationLibrary) -> None:
    ctx.SIM_SCRIPT.extend(["hmm <<GIVING_UP>>"])
    t = _simulate(lib, max_turns=5)
    assert t.stop_reason == "gave_up"
    assert t.turn_count == 1


def test_tests_can_require_genuine_goal_completion(lib: ConversationLibrary) -> None:
    # Simulation hits the cap without a goal-achieved sentinel; a test asserting
    # goal_achieved must fail (the transcript honestly reports max_turns).
    ctx.SIM_SCRIPT.extend(["a", "b", "c"])
    t = _simulate(lib, max_turns=2)
    assert t.stop_reason == "max_turns"
    assert t.stop_reason != "goal_achieved"


def test_mixed_scripted_then_simulated(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "SCRIPTED OPENING")
    lib.send_message(conv, "SECOND SCRIPTED")
    ctx.SIM_SCRIPT.extend(["now simulated <<GOAL_ACHIEVED>>"])
    lib.simulate_user(conv, persona="p", goal="g", simulator_adapter="scripted-sim", max_turns=3)
    # The simulator's first prompt was conditioned on the scripted turns.
    first_sim_prompt = ctx.SIM_STATE["prompts"][0]
    assert "SCRIPTED OPENING" in first_sim_prompt
    assert "SECOND SCRIPTED" in first_sim_prompt


def test_simulator_costs_included_in_total_cost(lib: ConversationLibrary) -> None:
    ctx.SIM_SCRIPT.extend(["one", "two"])
    t = _simulate(lib, max_turns=2)
    # 2 agent turns * 0.01 + 2 simulator calls * 0.02 = 0.06
    assert t.total_cost_usd == pytest.approx(0.06)


def test_budget_breach_aborts_the_simulation(lib: ConversationLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    # Cost source reports spend above the 0.0 cap → the @guarded_fanout meter
    # sets the cancel event; the loop aborts and the wrapper raises.
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 5.0)
    ctx.SIM_SCRIPT.extend(["a", "b", "c", "d", "e"])
    conv = lib.start_conversation(adapter="native-mock")
    with pytest.raises(CostExceededError):
        lib.simulate_user(
            conv,
            persona="p",
            goal="g",
            simulator_adapter="scripted-sim",
            max_turns=5,
            __agenteval_test_budget__=(0.0, None),
        )


def test_cache_key_replays_and_disabled_status(lib: ConversationLibrary, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "_resolve_output_dir", lambda: tmp_path)
    ctx.SIM_SCRIPT.extend(["cached msg <<GOAL_ACHIEVED>>"])
    # First run populates the cache.
    t1 = _simulate(lib, max_turns=3, cache_key="booking-v1")
    assert ctx.SIM_STATE["calls"] == 1
    first_status = [turn.simulator_cache for turn in t1.turns if turn.role == "user"]
    assert first_status == ["miss"]

    # Second run replays from cache — zero NEW simulator calls.
    ctx.SIM_STATE.update({"idx": 0, "prompts": [], "calls": 0})
    t2 = _simulate(lib, max_turns=3, cache_key="booking-v1")
    assert ctx.SIM_STATE["calls"] == 0
    replay_status = [turn.simulator_cache for turn in t2.turns if turn.role == "user"]
    assert replay_status == ["hit"]
    # Byte-identical user message.
    u1 = [turn.content for turn in t1.turns if turn.role == "user"]
    u2 = [turn.content for turn in t2.turns if turn.role == "user"]
    assert u1 == u2


def test_cache_disabled_records_disabled_status(lib: ConversationLibrary) -> None:
    ctx.SIM_SCRIPT.extend(["hi <<GOAL_ACHIEVED>>"])
    t = _simulate(lib, max_turns=2)  # no cache_key
    statuses = [turn.simulator_cache for turn in t.turns if turn.role == "user"]
    assert statuses == ["disabled"]


def test_simulate_user_on_closed_handle_raises(lib: ConversationLibrary) -> None:
    # codex MED: `Simulate User` must raise ConversationClosedError on a closed
    # handle BEFORE spending a simulator call. Pre-fix, a simulator whose first
    # message strips to empty (a bare goal sentinel) never reached execute_turn's
    # guard, so the keyword "succeeded" with stop_reason=goal_achieved and
    # turn_count=0 on a closed conversation.
    conv = lib.start_conversation(adapter="native-mock")
    lib.end_conversation(conv)
    ctx.SIM_SCRIPT.extend(["<<GOAL_ACHIEVED>>"])
    with pytest.raises(ConversationClosedError):
        lib.simulate_user(
            conv,
            persona="p",
            goal="g",
            simulator_adapter="scripted-sim",
            max_turns=3,
        )
    # The precheck fired before any simulator LLM call was spent.
    assert ctx.SIM_STATE["calls"] == 0


def test_simulate_user_on_closed_handle_raises_even_with_nonempty_message(lib: ConversationLibrary) -> None:
    # Even when the simulator would return a non-empty message (so execute_turn's
    # own guard would eventually fire), the up-front precheck must raise first —
    # no simulator call is spent.
    conv = lib.start_conversation(adapter="native-mock")
    lib.end_conversation(conv)
    ctx.SIM_SCRIPT.extend(["a real message"])
    with pytest.raises(ConversationClosedError):
        lib.simulate_user(conv, persona="p", goal="g", simulator_adapter="scripted-sim", max_turns=3)
    assert ctx.SIM_STATE["calls"] == 0


def test_simulation_cache_diverging_transcript_is_a_miss(tmp_path) -> None:
    cache = SimulationCache("k", base_dir=tmp_path)
    prior_a = (ConversationTurn(index=0, role="user", content="A"),)
    prior_b = (ConversationTurn(index=0, role="user", content="B"),)
    cache.store(1, prior_a, "cached-for-A")
    # Same turn index + cache key, but a DIFFERENT transcript-so-far → miss.
    assert cache.lookup(1, prior_a) == ("cached-for-A", "hit")
    assert cache.lookup(1, prior_b) == (None, "miss")
