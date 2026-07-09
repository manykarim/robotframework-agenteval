# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Scenario `turns:` (BREAKING) unit tests (add-multi-turn-conversation-testing Task 8.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel import discovery
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.errors import InvalidScenarioYAMLError
from AgentEval.orchestration.library import OrchestrationLibrary
from AgentEval.providers.base import ChatResponse, Message, ProviderUsage
from AgentEval.scenarios.loader import load_scenario
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "scenario.yaml"
    p.write_text(content)
    return p


# --------------------------------------------------------------------------- #
# Loader: exactly-one-of validation matrix                                     #
# --------------------------------------------------------------------------- #


def test_existing_single_prompt_yaml_still_loads(tmp_path: Path) -> None:
    scen = load_scenario(_write(tmp_path, "evals:\n  - prompt: hello\n"))
    assert scen.evals[0].prompt == "hello"
    assert scen.evals[0].turns is None
    assert scen.evals[0].is_multi_turn is False


def test_turns_based_eval_loads(tmp_path: Path) -> None:
    scen = load_scenario(
        _write(tmp_path, "evals:\n  - turns:\n      - Book a flight to Oslo\n      - Make it business class\n")
    )
    ev = scen.evals[0]
    assert ev.prompt is None
    assert ev.turns == ("Book a flight to Oslo", "Make it business class")
    assert ev.is_multi_turn is True


def test_both_prompt_and_turns_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "evals:\n  - prompt: hi\n    turns:\n      - a\n")
    with pytest.raises(InvalidScenarioYAMLError, match="exactly one") as exc:
        load_scenario(p)
    assert exc.value.field_name == "/evals/0"


def test_neither_prompt_nor_turns_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidScenarioYAMLError, match="exactly one"):
        load_scenario(_write(tmp_path, "evals:\n  - repeat: 2\n"))


def test_empty_turns_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidScenarioYAMLError, match="empty"):
        load_scenario(_write(tmp_path, "evals:\n  - turns: []\n"))


def test_non_string_turn_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "evals:\n  - turns:\n      - 42\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a string") as exc:
        load_scenario(p)
    assert exc.value.field_name == "/evals/0/turns/0"


def test_whitespace_turn_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, 'evals:\n  - turns:\n      - "   "\n')
    with pytest.raises(InvalidScenarioYAMLError, match="non-empty"):
        load_scenario(p)


# --------------------------------------------------------------------------- #
# Run Scenario execution: ordering, isolation, mixed, degradation              #
# --------------------------------------------------------------------------- #

_SCEN_PROVIDERS: list[Any] = []
_SCEN_REPLAY_CALLS: list[str] = []
_SCEN_REPLAY_MCP: list[Any] = []


class _RecProvider:
    name = "mock"
    version = "mock"

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, Any]]] = []

    def chat(
        self, messages: list[Message], tools: Any = None, *, stream: bool = False, model: Any = None, **kw: Any
    ) -> ChatResponse:
        self.calls.append([(m.role, m.content) for m in messages])
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ChatResponse(text=f"echo:{last}", usage=ProviderUsage(input_tokens=1, output_tokens=1), cost_usd=0.01)


class _ScenNativeAdapter(GenericAdapter):
    def __init__(self, **kw: Any) -> None:
        prov = _RecProvider()
        super().__init__(provider_instance=prov, model="mock/mock")
        _SCEN_PROVIDERS.append(prov)


class _ScenReplayAdapter(InProcessAdapter):
    @property
    def name(self) -> str:
        return "scen-replay"

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        _SCEN_REPLAY_CALLS.append(prompt)
        _SCEN_REPLAY_MCP.append(mcp_servers)
        return AgentRunResult(
            response_text=f"r:{prompt[-20:]}",
            tool_calls=[],
            usage=Usage(input_tokens=1, output_tokens=1),
            metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
            cost_usd=0.01,
            latency_seconds=0.001,
            trace_id="x" * 8,
        )


@pytest.fixture(autouse=True)
def _register() -> Any:
    _SCEN_PROVIDERS.clear()
    _SCEN_REPLAY_CALLS.clear()
    _SCEN_REPLAY_MCP.clear()
    discovery.register_adapter("scen-native", _ScenNativeAdapter)
    discovery.register_adapter("scen-replay", _ScenReplayAdapter)
    yield
    discovery._clear_discovery_cache()


@pytest.fixture
def orch() -> OrchestrationLibrary:
    return OrchestrationLibrary(default_provider=None)


def test_flat_results_preserve_per_turn_granularity_with_repeat(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    p = _write(tmp_path, "evals:\n  - turns:\n      - one\n      - two\n      - three\n    repeat: 2\n")
    results = orch.run_scenario(adapter="scen-native", scenario=str(p))
    assert len(results) == 6
    # Ordered turn-1..3 of rep1, then turn-1..3 of rep2.
    assert [r.response_text for r in results] == [
        "echo:one",
        "echo:two",
        "echo:three",
        "echo:one",
        "echo:two",
        "echo:three",
    ]


def test_fresh_conversation_per_repetition(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    p = _write(tmp_path, "evals:\n  - turns:\n      - one\n      - two\n    repeat: 2\n")
    orch.run_scenario(adapter="scen-native", scenario=str(p))
    # Each repetition threads on a FRESH adapter/provider instance (isolation).
    # (Run Scenario also constructs one top-level adapter instance that stays
    # unused for an all-turns scenario, so we filter to the providers that were
    # actually driven.)
    used = [prov for prov in _SCEN_PROVIDERS if prov.calls]
    assert len(used) == 2
    rep1, rep2 = used
    # Repetition 2's FIRST turn saw only its own message (no rep-1 history).
    assert rep2.calls[0] == [("user", "one")]
    # Repetition 1's SECOND turn saw the full rep-1 history (native threading).
    assert rep1.calls[1] == [("user", "one"), ("assistant", "echo:one"), ("user", "two")]


def test_mixed_prompt_and_turns_suite(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    p = _write(
        tmp_path,
        "evals:\n  - prompt: single shot\n  - turns:\n      - t1\n      - t2\n",
    )
    results = orch.run_scenario(adapter="scen-native", scenario=str(p))
    # 1 (prompt) + 2 (turns) = 3, in eval order.
    assert len(results) == 3
    assert results[0].response_text == "echo:single shot"
    assert results[1].response_text == "echo:t1"
    assert results[2].response_text == "echo:t2"


def test_replay_only_adapter_degrades_honestly_in_yaml_run(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    p = _write(tmp_path, "evals:\n  - turns:\n      - first\n      - second\n")
    results = orch.run_scenario(adapter="scen-replay", scenario=str(p))
    assert len(results) == 2
    # Turn 2's run() prompt carried the rendered prior turns (history replay).
    assert "first" in _SCEN_REPLAY_CALLS[1]
    assert "second" in _SCEN_REPLAY_CALLS[1]
    assert "Conversation so far" in _SCEN_REPLAY_CALLS[1]


# --------------------------------------------------------------------------- #
# HIGH fix: per-turn continuation honesty survives on result.metadata          #
# --------------------------------------------------------------------------- #


def test_replay_only_turns_expose_continuation_via_metadata(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    # codex HIGH: a replay-only adapter driven through a YAML `turns:` eval must
    # expose its truthful per-turn continuation on the ONLY object Run Scenario
    # returns — the flat AgentRunResult list — via result.metadata.continuation.
    # Pre-fix the observed values were [None, None] (signal discarded on the
    # private ConversationTurn); codex's repro saw [False, False].
    p = _write(tmp_path, "evals:\n  - turns:\n      - first\n      - second\n")
    results = orch.run_scenario(adapter="scen-replay", scenario=str(p))
    assert len(results) == 2
    assert [r.metadata.continuation for r in results] == ["initial", "replayed_history"]
    # Constraint: a replay-only adapter NEVER reports native_session.
    assert "native_session" not in [r.metadata.continuation for r in results]


def test_native_turns_expose_native_session_continuation(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    p = _write(tmp_path, "evals:\n  - turns:\n      - one\n      - two\n")
    results = orch.run_scenario(adapter="scen-native", scenario=str(p))
    assert [r.metadata.continuation for r in results] == ["initial", "native_session"]


def test_single_prompt_eval_leaves_continuation_none(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    # Unchanged behavior: single-shot / prompt: evals never thread, so the
    # honesty field stays None (shape unbroken for existing callers).
    p = _write(tmp_path, "evals:\n  - prompt: hello\n")
    results = orch.run_scenario(adapter="scen-native", scenario=str(p))
    assert len(results) == 1
    assert results[0].metadata.continuation is None


# --------------------------------------------------------------------------- #
# MED fix: mcp_servers is NOT silently dropped for turns: evals                 #
# --------------------------------------------------------------------------- #


def test_turns_eval_forwards_mcp_servers_to_adapter(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    # codex MED: pre-fix the multi-turn path called execute_turn with no
    # call_kwargs, so mcp_servers was silently dropped (adapter saw None on every
    # turn). A replay adapter must now RECEIVE the caller-supplied handles.
    p = _write(tmp_path, "evals:\n  - turns:\n      - first\n      - second\n")
    servers = {"echo": object()}
    orch.run_scenario(adapter="scen-replay", scenario=str(p), mcp_servers=servers)
    assert len(_SCEN_REPLAY_MCP) == 2
    assert all(received is servers for received in _SCEN_REPLAY_MCP)
    assert None not in _SCEN_REPLAY_MCP


def test_turns_eval_mcp_servers_raises_honestly_on_native_adapter(tmp_path: Path, orch: OrchestrationLibrary) -> None:
    # GenericAdapter.run_turn raises NotImplementedError on non-empty mcp_servers
    # (multi-turn MCP is Phase-2 scope). The turns: path must surface that honest
    # failure rather than hide the unsupported config by dropping the handles.
    p = _write(tmp_path, "evals:\n  - turns:\n      - one\n      - two\n")
    with pytest.raises(NotImplementedError, match="mcp_servers"):
        orch.run_scenario(adapter="scen-native", scenario=str(p), mcp_servers={"echo": object()})
