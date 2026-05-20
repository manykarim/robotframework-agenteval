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

"""Unit tests for `AgentEval.coding_agent.generic.GenericAdapter` (Story 4.1 / PRD FR13a)."""

from __future__ import annotations

import re

import pytest

from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.providers.base import ChatResponse, ProviderUsage, ToolCallRequest
from AgentEval.providers.mock import MockProvider
from AgentEval.types import AgentRunResult


def _scripted_mock(text: str = "echoed", **kwargs: object) -> MockProvider:
    return MockProvider(
        responses=[
            ChatResponse(
                text=text,
                usage=ProviderUsage(input_tokens=10, output_tokens=5),
                cost_usd=0.01,
                **kwargs,  # type: ignore[arg-type]
            )
        ]
    )


def test_generic_adapter_is_in_process_adapter() -> None:
    adapter = GenericAdapter(provider_instance=MockProvider())
    assert isinstance(adapter, InProcessAdapter)


def test_generic_adapter_name_is_GenericAdapter() -> None:  # noqa: N802
    adapter = GenericAdapter(provider_instance=MockProvider())
    assert adapter.name == "GenericAdapter"


def test_generic_adapter_version_resolves_via_metadata() -> None:
    """Story 4.1 code-review Blind L3 fix 2026-05-20: assertion now actually
    exercises the `_default_version` semver-resolution path (not just
    non-empty), matching the test-name-vs-body invariant per
    `feedback_test_name_assertion_match`.
    """
    adapter = GenericAdapter(provider_instance=MockProvider())
    version = adapter.version
    # `_default_version` resolves the top-level package's installed-distribution
    # version. Result must be either the resolved version (digit-prefixed) OR
    # the fallback "unknown" sentinel — anything else indicates a regression.
    assert version != ""
    assert version == "unknown" or version[0].isdigit()


def test_generic_adapter_run_returns_agent_run_result() -> None:
    adapter = GenericAdapter(provider_instance=_scripted_mock("hello world"))
    result = adapter.run("hi")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "hello world"


def test_generic_adapter_run_populates_usage() -> None:
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi")
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5


def test_generic_adapter_run_populates_cost_usd() -> None:
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi")
    assert result.cost_usd == 0.01


def test_generic_adapter_run_coerces_none_cost_to_zero() -> None:
    """When provider returns `cost_usd=None`, GenericAdapter coerces to 0.0 (AC-4.1.6)."""
    mock = MockProvider(responses=[ChatResponse(text="x", cost_usd=None)])
    adapter = GenericAdapter(provider_instance=mock)
    result = adapter.run("hi")
    assert result.cost_usd == 0.0


def test_generic_adapter_run_populates_metadata_with_phase1_defaults() -> None:
    """Phase-1 no-MCP: `completeness="complete"`, `mcp_coverage="hosted_in_process"` (DF-4.1-S4)."""
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi")
    assert result.metadata.completeness == "complete"
    # Phase-1 vacuously-true value: 0 MCP servers used; 0 of them external.
    assert result.metadata.mcp_coverage == "hosted_in_process"


def test_generic_adapter_run_populates_latency_seconds() -> None:
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi")
    assert result.latency_seconds > 0.0


def test_generic_adapter_run_generates_uuid4_trace_id() -> None:
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi")
    # uuid4 hex = 32 lowercase hex chars.
    assert re.fullmatch(r"[0-9a-f]{32}", result.trace_id) is not None


def test_generic_adapter_run_generates_unique_trace_id_per_call() -> None:
    adapter = GenericAdapter(
        provider_instance=MockProvider(
            responses=[
                ChatResponse(text="a", usage=ProviderUsage(input_tokens=1, output_tokens=1)),
                ChatResponse(text="b", usage=ProviderUsage(input_tokens=1, output_tokens=1)),
            ]
        )
    )
    r1 = adapter.run("hi")
    r2 = adapter.run("hi")
    assert r1.trace_id != r2.trace_id


def test_generic_adapter_run_empty_mcp_servers_allowed() -> None:
    """`mcp_servers=None` or empty dict is allowed (no NotImplementedError)."""
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi", mcp_servers=None)
    assert isinstance(result, AgentRunResult)
    adapter2 = GenericAdapter(provider_instance=_scripted_mock())
    result2 = adapter2.run("hi", mcp_servers={})
    assert isinstance(result2, AgentRunResult)


def test_generic_adapter_run_non_empty_mcp_servers_wires_observer_not_raises() -> None:
    """Story 5.2 DF-4.1-S2 absorption (per Epic 4 retro Action #5): pre-edit the
    GenericAdapter raised NotImplementedError on non-empty `mcp_servers`. NOW it
    wires through `HostedMcpObserver` per ADR-004 + the per-adapter detection
    contract. Non-in_memory handles degrade to `external_mixed` (DF-5.2-S3
    deferred until Story 5.5 dogfood port wires the subprocess wrapper).
    """
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    # Bare-object handle (no transport attr) → observer marks external_mixed.
    fake_handle = object()
    result = adapter.run("hi", mcp_servers={"echo": fake_handle})
    # Observer's compute_coverage() resolves to external_mixed because the
    # handle has no recognized transport — ADR-016 D1 detection-failure default.
    assert result.metadata.mcp_coverage == "external_mixed"


def test_generic_adapter_run_non_empty_tools_raises_not_implemented() -> None:
    """Story 4.1 code-review Edge-cases M-3 fix 2026-05-20: `tools=` is now
    symmetric to `mcp_servers=` — non-empty raises NotImplementedError rather
    than silently no-op. Pre-edit silent-discard was the asymmetric footgun.
    """
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    with pytest.raises(NotImplementedError, match="advertise tools"):
        adapter.run("hi", tools=["real_tool"])


def test_generic_adapter_run_empty_tools_allowed() -> None:
    """Empty tools list OR None is still allowed (no raise)."""
    adapter = GenericAdapter(provider_instance=_scripted_mock())
    result = adapter.run("hi", tools=None)
    assert isinstance(result, AgentRunResult)
    adapter2 = GenericAdapter(provider_instance=_scripted_mock())
    result2 = adapter2.run("hi", tools=[])
    assert isinstance(result2, AgentRunResult)


def test_generic_adapter_constructor_resolves_provider_by_name() -> None:
    """Constructor with `provider="mock"` resolves via factory.get_provider."""
    adapter = GenericAdapter(provider="mock")
    result = adapter.run("hello")
    # Echo mode (no scripted responses) — returns the prompt text.
    assert result.response_text == "hello"


def test_generic_adapter_run_forwards_kwargs_to_provider() -> None:
    """Extra kwargs to `run()` flow through to `provider.chat(**kwargs)`."""
    captured: dict[str, object] = {}

    class _Capture(MockProvider):
        def chat(self, messages, tools=None, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return ChatResponse(text="ok", usage=ProviderUsage(input_tokens=0, output_tokens=0))

    adapter = GenericAdapter(provider_instance=_Capture())
    adapter.run("hi", temperature=0.5, max_tokens=100)
    assert captured.get("temperature") == 0.5
    assert captured.get("max_tokens") == 100


def test_generic_adapter_tool_calls_empty_phase1() -> None:
    """Phase-1 carve-out (DF-4.1-S2): tool_calls is always empty until Story 4.3."""
    mock = MockProvider(
        responses=[
            ChatResponse(
                text="",
                tool_calls=[ToolCallRequest(id="1", name="search", arguments={"q": "abc"})],
                usage=ProviderUsage(input_tokens=10, output_tokens=2),
            )
        ]
    )
    adapter = GenericAdapter(provider_instance=mock)
    result = adapter.run("hi")
    # The Generic adapter intentionally drops provider-reported tool_calls in
    # Phase-1; full dispatch + ToolCallTrace wiring lands in Story 4.3 + Epic 5.
    assert result.tool_calls == []
