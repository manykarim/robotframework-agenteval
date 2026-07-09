# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Shared fixtures + stub adapters for the conversation unit tests.

Everything is deterministic on the mock provider — NO API keys required.
"""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval._kernel import discovery
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.conversation.library import ConversationLibrary
from AgentEval.providers.base import ChatResponse, Message, ProviderUsage
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def mk_result(text: str, *, cost: float = 0.01, latency: float = 0.001) -> AgentRunResult:
    return AgentRunResult(
        response_text=text,
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost,
        latency_seconds=latency,
        trace_id="t" * 8,
    )


class RecordingProvider:
    """Deterministic provider that records the message lists it received + echoes the last user turn."""

    name = "mock"
    version = "mock"

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, Any]]] = []

    def chat(
        self, messages: list[Message], tools: Any = None, *, stream: bool = False, model: Any = None, **kw: Any
    ) -> ChatResponse:
        self.calls.append([(m.role, m.content) for m in messages])
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ChatResponse(
            text=f"echo:{last_user}",
            usage=ProviderUsage(input_tokens=1, output_tokens=1),
            cost_usd=0.01,
        )


# Registry so tests can inspect the provider instances a NativeMockAdapter built.
NATIVE_PROVIDERS: list[RecordingProvider] = []


class NativeMockAdapter(GenericAdapter):
    """A `generic`-style adapter (HAS `run_turn`) bound to a fresh RecordingProvider per instance."""

    def __init__(self, **kwargs: Any) -> None:
        provider = RecordingProvider()
        super().__init__(provider_instance=provider, model="mock/mock")
        NATIVE_PROVIDERS.append(provider)
        self.recording_provider = provider


REPLAY_CALLS: list[str] = []


class ReplayOnlyAdapter(InProcessAdapter):
    """A replay-only adapter (NO `run_turn`) that records the prompt each `run()` received."""

    @property
    def name(self) -> str:
        return "replay-only"

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kwargs: Any) -> AgentRunResult:
        REPLAY_CALLS.append(prompt)
        return mk_result(f"replied:{prompt[-30:]}")


# --- Scripted user-simulator adapter -------------------------------------- #
# `SIM_SCRIPT` holds the sequence of simulator responses (strings, possibly
# carrying `<<GOAL_ACHIEVED>>` / `<<GIVING_UP>>` sentinels); `SIM_STATE` tracks
# the consumption index + captured prompts + call count. Reset per test.
SIM_SCRIPT: list[str] = []
SIM_STATE: dict[str, Any] = {"idx": 0, "prompts": [], "calls": 0}


class ScriptedSimAdapter(InProcessAdapter):
    """Deterministic simulator adapter — returns `SIM_SCRIPT` entries in order."""

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kwargs: Any) -> AgentRunResult:
        SIM_STATE["prompts"].append(prompt)
        SIM_STATE["calls"] += 1
        i = SIM_STATE["idx"]
        SIM_STATE["idx"] += 1
        text = SIM_SCRIPT[i] if i < len(SIM_SCRIPT) else "please continue"
        return mk_result(text, cost=0.02)


@pytest.fixture(autouse=True)
def _register_stub_adapters() -> Any:
    NATIVE_PROVIDERS.clear()
    REPLAY_CALLS.clear()
    SIM_SCRIPT.clear()
    SIM_STATE.update({"idx": 0, "prompts": [], "calls": 0})
    discovery.register_adapter("native-mock", NativeMockAdapter)
    discovery.register_adapter("replay-only", ReplayOnlyAdapter)
    discovery.register_adapter("scripted-sim", ScriptedSimAdapter)
    yield
    discovery._clear_discovery_cache()


@pytest.fixture
def lib() -> ConversationLibrary:
    return ConversationLibrary(default_provider=None)
