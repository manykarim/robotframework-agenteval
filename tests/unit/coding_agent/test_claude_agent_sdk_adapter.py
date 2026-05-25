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

"""Unit tests for `AgentEval.coding_agent.claude_agent_sdk.ClaudeAgentSDKAdapter`.

Story 10.1 AC-10.1.4. The real `claude-agent-sdk` PyPI package is not a
test-time dependency; tests inject a fake module via `sys.modules` so the
adapter's lazy imports succeed without the SDK installed.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

# --------------------------------------------------------------------------- #
# Fake `claude_agent_sdk` module + `anyio` shim                                #
# --------------------------------------------------------------------------- #

# Module-level marker classes — replace the real SDK's typed classes. The
# adapter uses `isinstance` checks against these, so the fakes need to be
# discoverable as `claude_agent_sdk.AssistantMessage` etc.


class _FakeAssistantMessage:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class _FakeUserMessage:
    pass


class _FakeSystemMessage:
    pass


class _FakeResultMessage:
    """Story 10.1 review HIGH-1 patch: ``usage`` is now a ``dict``, NOT an
    attribute-bearing shim. Mirrors the real ``claude_agent_sdk.ResultMessage``
    field declaration: ``usage: dict[str, Any] | None`` (empirically verified
    via ``dataclasses.fields(ResultMessage)`` during the cross-LLM review).
    """

    def __init__(self, total_cost_usd: float, usage: dict[str, Any] | None = None) -> None:
        self.total_cost_usd = total_cost_usd
        self.usage = usage


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeToolUseBlock:
    def __init__(self, name: str, input: dict[str, Any], id: str = "tool_001") -> None:
        self.name = name
        self.input = input
        self.id = id


class _FakeClaudeAgentOptions:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _install_fake_sdk(monkeypatch: pytest.MonkeyPatch, query_messages: list[Any]) -> None:
    """Install a fake `claude_agent_sdk` module exposing the symbols the
    adapter imports. `query_messages` is the sequence the fake `query()`
    async generator yields.
    """

    fake_module = types.ModuleType("claude_agent_sdk")
    fake_module.AssistantMessage = _FakeAssistantMessage  # type: ignore[attr-defined]
    fake_module.UserMessage = _FakeUserMessage  # type: ignore[attr-defined]
    fake_module.SystemMessage = _FakeSystemMessage  # type: ignore[attr-defined]
    fake_module.ResultMessage = _FakeResultMessage  # type: ignore[attr-defined]
    fake_module.TextBlock = _FakeTextBlock  # type: ignore[attr-defined]
    fake_module.ToolUseBlock = _FakeToolUseBlock  # type: ignore[attr-defined]
    fake_module.ClaudeAgentOptions = _FakeClaudeAgentOptions  # type: ignore[attr-defined]

    async def _fake_query(prompt: str, options: Any):  # noqa: ARG001 — match SDK signature
        for msg in query_messages:
            yield msg

    fake_module.query = _fake_query  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


def test_import_error_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ClaudeAgentSDKAdapter()` raises ImportError when the SDK isn't installed."""
    # Ensure the fake module is NOT in sys.modules so the lazy import fails.
    monkeypatch.delitem(sys.modules, "claude_agent_sdk", raising=False)
    # Also block `claude_agent_sdk` from being importable via finders.

    import importlib.abc
    import importlib.machinery

    class _BlockClaudeAgentSDK(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path: Any, target: Any = None) -> importlib.machinery.ModuleSpec | None:
            if fullname == "claude_agent_sdk":
                raise ImportError("blocked by test")
            return None

    finder = _BlockClaudeAgentSDK()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    with pytest.raises(ImportError, match=r"claude-agent-sdk"):
        ClaudeAgentSDKAdapter()


def test_is_in_process_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter is a subclass of `InProcessAdapter` per ADR-003 direct-override pattern."""
    _install_fake_sdk(monkeypatch, [])
    from AgentEval.coding_agent.base import InProcessAdapter
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    assert isinstance(adapter, InProcessAdapter)


def test_name_is_ClaudeAgentSDKAdapter(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: N802
    """Adapter `.name` returns the class name per the project convention."""
    _install_fake_sdk(monkeypatch, [])
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    assert ClaudeAgentSDKAdapter().name == "ClaudeAgentSDKAdapter"


def test_init_captures_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor accepts model / max_turns / system_prompt + arbitrary kwargs.

    Verifies the adapter forwards kwargs to `InProcessAdapter.__init__` (so
    `self._adapter_config` is populated for downstream introspection).
    """
    _install_fake_sdk(monkeypatch, [])
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter(
        model="claude-sonnet-4-5",
        max_turns=3,
        system_prompt="You are helpful.",
        extra="kw",
    )
    assert adapter._adapter_config["model"] == "claude-sonnet-4-5"
    assert adapter._adapter_config["max_turns"] == 3
    assert adapter._adapter_config["system_prompt"] == "You are helpful."
    assert adapter._adapter_config["extra"] == "kw"


def test_run_no_mcp_no_tools_returns_hosted_in_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run(prompt='hello')` with no MCP + no tools returns response_text +
    mcp_coverage='hosted_in_process'.

    This is the AC-10.1.2 branch 1 case (no MCP attached → trivially honest).

    Story 10.1 review MED-1 patch: this test now actually loads the
    ``single_shot_hello.json`` recorded fixture (was 0-caller dead data).
    AC-10.1.4 honored.
    """
    import json
    from pathlib import Path

    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "claude_agent_sdk_responses" / "single_shot_hello.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_text = fixture["assistant_messages"][0]["blocks"][0]["text"]
    expected_cost = fixture["result_message"]["total_cost_usd"]
    expected_usage = fixture["result_message"]["usage"]

    messages = [
        _FakeAssistantMessage(content=[_FakeTextBlock(expected_text)]),
        _FakeResultMessage(
            total_cost_usd=expected_cost,
            usage=expected_usage,  # Real SDK shape: dict, not object.
        ),
    ]
    _install_fake_sdk(monkeypatch, messages)
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter(model="claude-sonnet-4-5")
    result = adapter.run(prompt="hello")

    assert result.response_text == expected_text
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
    assert result.cost_usd == pytest.approx(expected_cost)
    assert result.usage.input_tokens == expected_usage["input_tokens"]
    assert result.usage.output_tokens == expected_usage["output_tokens"]
    assert result.tool_calls == []
    assert isinstance(result.trace_id, str) and len(result.trace_id) == 32
    assert result.latency_seconds >= 0.0


def test_run_with_unverified_mcp_marks_external_mixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 10.1 review HIGH-2 + HIGH-3 patch: MCP attached but no verified
    hosted-attachment signal → ``external_mixed`` per ADR-A6 L384.

    Until C68 (``HostedMcpObserver`` wiring for the Agent SDK) lands, the
    adapter cannot empirically distinguish hosted-in-process from external
    delegation; the SAFER default is ``external_mixed``. The original test
    asserted ``hosted_in_process`` here, which made ADR-A6's honesty contract
    unenforceable — caught by the cross-LLM adversarial review.
    """
    messages = [
        _FakeAssistantMessage(content=[_FakeTextBlock("Used the tool.")]),
        _FakeResultMessage(total_cost_usd=0.005),
    ]
    _install_fake_sdk(monkeypatch, messages)
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    result = adapter.run(prompt="use a tool", mcp_servers={"my-tools": object()})

    # Per ADR-A6 L384 safer-default rule until C68 lands.
    assert result.metadata.mcp_coverage == "external_mixed"
    assert result.response_text == "Used the tool."


def test_run_with_tool_use_blocks_projects_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool-use blocks from the SDK project into `AgentRunResult.tool_calls`.

    Verifies the `_project_tool_calls` shape — name + args + tool_call_id
    populated; result/error None (DF-10.1-S3 carry-over: use+result pairing
    is deferred).
    """
    messages = [
        _FakeAssistantMessage(
            content=[
                _FakeTextBlock("Calling search."),
                _FakeToolUseBlock(
                    name="search",
                    input={"query": "weather"},
                    id="toolu_abc",
                ),
            ]
        ),
        _FakeResultMessage(total_cost_usd=0.003),
    ]
    _install_fake_sdk(monkeypatch, messages)
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    result = adapter.run(prompt="search the web")

    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.name == "search"
    assert tc.args == {"query": "weather"}
    assert tc.gen_ai_tool_call_id == "toolu_abc"
    assert tc.result is None
    assert tc.error is None
    assert tc.source == "adapter"
    assert tc.sequence_index == 0


def test_run_propagates_sdk_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """SDK exceptions propagate from `run()`; the adapter does not swallow them.

    Per the AC-10.1.2 branch 3 detection-failure path, the adapter would
    flag `external_mixed` in this case but Python re-raises before
    `AgentRunResult` is constructed. This test verifies the re-raise.
    """
    fake_module = types.ModuleType("claude_agent_sdk")
    fake_module.AssistantMessage = _FakeAssistantMessage  # type: ignore[attr-defined]
    fake_module.UserMessage = _FakeUserMessage  # type: ignore[attr-defined]
    fake_module.SystemMessage = _FakeSystemMessage  # type: ignore[attr-defined]
    fake_module.ResultMessage = _FakeResultMessage  # type: ignore[attr-defined]
    fake_module.TextBlock = _FakeTextBlock  # type: ignore[attr-defined]
    fake_module.ToolUseBlock = _FakeToolUseBlock  # type: ignore[attr-defined]
    fake_module.ClaudeAgentOptions = _FakeClaudeAgentOptions  # type: ignore[attr-defined]

    async def _raising_query(prompt: str, options: Any):  # noqa: ARG001
        raise RuntimeError("SDK exploded")
        yield  # pragma: no cover — unreachable; needed to make this an async generator

    fake_module.query = _raising_query  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_module)
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    with pytest.raises(RuntimeError, match=r"SDK exploded"):
        adapter.run(prompt="trigger error")


def test_extract_usage_handles_dict_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 10.1 review HIGH-1 patch verification: ``ResultMessage.usage`` is
    a ``dict[str, Any] | None`` on the real SDK. The adapter MUST read keys
    via ``dict.get()``, not ``getattr()``.

    Direct unit test of `_extract_usage` with a dict argument — guards
    against future regressions where someone "tidies" the helper back to
    ``getattr()`` and reintroduces the silent zero-token bug.
    """
    _install_fake_sdk(monkeypatch, [])  # only needed for import path
    from AgentEval.coding_agent.claude_agent_sdk import _extract_usage

    result_msg = _FakeResultMessage(
        total_cost_usd=0.001,
        usage={"input_tokens": 42, "output_tokens": 17, "cache_read_input_tokens": 3},
    )
    usage = _extract_usage(result_msg)
    assert usage.input_tokens == 42
    assert usage.output_tokens == 17
    assert usage.cached_input_tokens == 3


def test_run_handles_missing_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """ResultMessage without cost attributes → cost_usd defaults to 0.0.

    Defensive against pre-1.0 SDK shape variations per the docstring.
    """

    class _MinimalResult:
        pass

    messages = [
        _FakeAssistantMessage(content=[_FakeTextBlock("done")]),
        _MinimalResult(),  # No total_cost_usd, no cost_usd, no usage attr.
    ]
    _install_fake_sdk(monkeypatch, messages)
    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    result = adapter.run(prompt="say done")

    assert result.cost_usd == 0.0
    assert result.usage.input_tokens == 0


def test_entry_point_registration() -> None:
    """`claude-agent-sdk` entry-point under `agenteval.coding_agents` resolves
    to `ClaudeAgentSDKAdapter` per AC-10.1.3 + AC-10.1.6.

    Smoke-test that doesn't import the SDK — uses `importlib.metadata` to
    read the entry-point + verifies the `(module, attr)` pair matches what
    `pyproject.toml` declares. Per Story 10.1 D-3 — the entry-point name
    `claude-agent-sdk` distinguishes from the existing `claude-code-cli`.
    """
    import importlib.metadata

    eps = importlib.metadata.entry_points(group="agenteval.coding_agents")
    matching = [ep for ep in eps if ep.name == "claude-agent-sdk"]
    assert len(matching) == 1, (
        f"expected exactly 1 `claude-agent-sdk` entry-point under "
        f"`agenteval.coding_agents`; got {len(matching)} ({matching!r})"
    )
    ep = matching[0]
    # Verify the (module, attr) pair without loading (would require SDK install).
    assert ep.module == "AgentEval.coding_agent.claude_agent_sdk"
    assert ep.attr == "ClaudeAgentSDKAdapter"


def test_run_calls_enforce_tier1_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """`enforce_tier1_no_llm()` is wired at run-entry per PRD FR30b + Story 6.3.

    Matches the GenericAdapter.run() precedent at
    `src/AgentEval/coding_agent/generic.py:194-197`.
    """
    _install_fake_sdk(
        monkeypatch,
        [
            _FakeAssistantMessage(content=[_FakeTextBlock("ok")]),
            _FakeResultMessage(total_cost_usd=0.0),
        ],
    )

    calls: list[None] = []

    def _spy() -> None:
        calls.append(None)

    monkeypatch.setattr("AgentEval._kernel.tier_acl.enforce_tier1_no_llm", _spy)

    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter()
    adapter.run(prompt="hello")
    assert len(calls) == 1, "enforce_tier1_no_llm must be invoked exactly once per run()"
