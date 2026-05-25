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

"""Unit tests for `AgentEval.coding_agent.openai_agents.OpenAIAgentsSDKAdapter`.

Story 10.2 AC-10.2.4. The real `openai-agents` PyPI package (import path
``agents``) is not a test-time dependency; tests inject a fake module via
``sys.modules`` so the adapter's lazy imports succeed without the SDK
installed.

Story 10.1 lessons applied UPSTREAM:
- HIGH-1: ``_extract_usage`` regression-guard for both attribute + dict shapes.
- HIGH-3: every test's assertion body delivers on the test name's promise.
- HIGH-4: ``_record_run_metadata`` invocation is explicitly tested.
- MED-1: fixture JSON is actually loaded by the hello test.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

# --------------------------------------------------------------------------- #
# Fake `agents` module (the openai-agents import path)                         #
# --------------------------------------------------------------------------- #


class _FakeAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeInputTokensDetails:
    """Mirrors `agents.usage.InputTokensDetails` (pydantic). The real SDK
    keeps cached-token count nested here, NOT flat on Usage.
    """

    def __init__(self, cached_tokens: int = 0) -> None:
        self.cached_tokens = cached_tokens


class _FakeAgentsUsage:
    """Mirrors the real `agents.usage.Usage` shape (post-empirical-probe).

    Fields per `dataclasses.fields(agents.usage.Usage)`:
        input_tokens, output_tokens, total_tokens, requests,
        input_tokens_details (nested), output_tokens_details (nested),
        request_usage_entries.
    """

    def __init__(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens
        self.input_tokens_details = _FakeInputTokensDetails(cached_tokens=cached_tokens)


class _FakeRunContextWrapper:
    """Mirrors `agents.RunContextWrapper` — carries `usage` as an attribute."""

    def __init__(self, usage: Any) -> None:
        self.usage = usage


class _FakeRunResult:
    """Mirrors the real `agents.RunResult` shape (post cross-LLM retry
    empirical probe 2026-05-25). The canonical usage path is
    `context_wrapper.usage`, NOT a top-level `usage` attribute.

    `_extract_cost` reads top-level cost attributes for symmetry with
    hypothetical future SDK shapes (the real SDK exposes no cost field).
    """

    def __init__(
        self,
        final_output: str,
        total_cost_usd: float | None = None,
        cached_tokens: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        raw_responses: list[Any] | None = None,
    ) -> None:
        self.final_output = final_output
        if total_cost_usd is not None:
            self.total_cost_usd = total_cost_usd
        self.context_wrapper = _FakeRunContextWrapper(
            usage=_FakeAgentsUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
            )
        )
        self.raw_responses = raw_responses or []


class _FakeRunner:
    """Fake `Runner.run_sync` — class-method shim returning a programmed result."""

    next_result: _FakeRunResult | None = None
    next_exc: Exception | None = None
    last_agent: Any = None
    last_prompt: str | None = None

    @classmethod
    def run_sync(cls, agent: Any, prompt: str) -> _FakeRunResult:
        cls.last_agent = agent
        cls.last_prompt = prompt
        if cls.next_exc is not None:
            exc = cls.next_exc
            cls.next_exc = None
            raise exc
        assert cls.next_result is not None, "_FakeRunner.next_result must be set"
        return cls.next_result


def _install_fake_sdk(
    monkeypatch: pytest.MonkeyPatch,
    next_result: _FakeRunResult | None = None,
    next_exc: Exception | None = None,
) -> None:
    """Install a fake ``agents`` module exposing ``Agent`` + ``Runner``."""

    fake_module = types.ModuleType("agents")
    fake_module.Agent = _FakeAgent  # type: ignore[attr-defined]
    fake_module.Runner = _FakeRunner  # type: ignore[attr-defined]
    _FakeRunner.next_result = next_result
    _FakeRunner.next_exc = next_exc
    _FakeRunner.last_agent = None
    _FakeRunner.last_prompt = None
    monkeypatch.setitem(sys.modules, "agents", fake_module)


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


def test_import_error_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`OpenAIAgentsSDKAdapter()` raises ImportError when the SDK isn't installed."""
    monkeypatch.delitem(sys.modules, "agents", raising=False)

    import importlib.abc
    import importlib.machinery

    class _BlockAgentsSDK(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path: Any, target: Any = None) -> importlib.machinery.ModuleSpec | None:
            if fullname == "agents":
                raise ImportError("blocked by test")
            return None

    monkeypatch.setattr(sys, "meta_path", [_BlockAgentsSDK(), *sys.meta_path])

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    with pytest.raises(ImportError, match=r"openai-agents"):
        OpenAIAgentsSDKAdapter()


def test_is_in_process_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter is a subclass of `InProcessAdapter` per ADR-003 direct-override pattern."""
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.base import InProcessAdapter
    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    assert isinstance(adapter, InProcessAdapter)


def test_name_is_OpenAIAgentsSDKAdapter(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: N802
    """Adapter `.name` returns the class name per project convention."""
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    assert OpenAIAgentsSDKAdapter().name == "OpenAIAgentsSDKAdapter"


def test_init_captures_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor accepts model/name/instructions + arbitrary kwargs."""
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter(
        model="gpt-4o",
        name="custom-agent",
        instructions="Be helpful.",
        extra="kw",
    )
    assert adapter._adapter_config["model"] == "gpt-4o"
    assert adapter._adapter_config["name"] == "custom-agent"
    assert adapter._adapter_config["instructions"] == "Be helpful."
    assert adapter._adapter_config["extra"] == "kw"


def test_run_no_mcp_no_tools_loads_fixture_and_returns_hosted_in_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hello test loads the recorded fixture + asserts the projection.

    Story 10.2 MED-1-equivalent (Story 10.1 lesson applied UPSTREAM): the
    JSON fixture at ``tests/fixtures/openai_agents_responses/single_shot_hello.json``
    is the source of truth for expected values — NOT inline literals.
    """
    import json
    from pathlib import Path

    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "openai_agents_responses" / "single_shot_hello.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    sdk_result = _FakeRunResult(
        final_output=fixture["final_output"],
        total_cost_usd=fixture["total_cost_usd"],
        input_tokens=fixture["usage"]["input_tokens"],
        output_tokens=fixture["usage"]["output_tokens"],
        cached_tokens=fixture["usage"]["cached_input_tokens"],
    )
    _install_fake_sdk(monkeypatch, next_result=sdk_result)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter(model="gpt-4o")
    result = adapter.run(prompt="hello")

    assert result.response_text == fixture["final_output"]
    # Cross-LLM review MED-2 patch: real SDK exposes no cost attribute;
    # _extract_cost returns 0.0 unconditionally until C70 lands a priced
    # lookup. Fixture's `total_cost_usd` is hypothetical / for symmetry.
    assert result.cost_usd == 0.0
    assert result.usage.input_tokens == fixture["usage"]["input_tokens"]
    assert result.usage.output_tokens == fixture["usage"]["output_tokens"]
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
    assert result.tool_calls == []
    assert isinstance(result.trace_id, str) and len(result.trace_id) == 32
    assert result.latency_seconds >= 0.0


def test_run_with_unverified_mcp_marks_external_mixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 10.2 D-4 + Story 10.1 HIGH-2 lesson applied UPSTREAM: MCP
    attached but no verified hosted-attachment signal → ``external_mixed``
    per ADR-A6 L384.

    Story 10.1 shipped this contract after cross-LLM review caught the
    fake 3-branch ``hosted_in_process``-twice version. Story 10.2 ships
    the corrected contract from the start.
    """
    sdk_result = _FakeRunResult(final_output="ok", total_cost_usd=0.001)
    _install_fake_sdk(monkeypatch, next_result=sdk_result)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    result = adapter.run(prompt="x", mcp_servers={"srv": object()})

    assert result.metadata.mcp_coverage == "external_mixed"
    assert result.response_text == "ok"


def test_extract_usage_canonical_context_wrapper_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Empirical canonical path** (post cross-LLM retry probe 2026-05-25):
    the real ``agents.RunResult`` exposes usage at
    ``context_wrapper.usage`` — NOT a top-level ``usage`` attribute.

    This test pins the canonical path. Without it, ``_extract_usage``
    would silently return ``Usage(0, 0, 0)`` on every live run (the
    same Story 10.1 HIGH-1 bug pattern that Claude CLI's empirical
    probe surfaced for the Claude SDK).

    The cached-token count lives at the nested
    ``input_tokens_details.cached_tokens`` — also exercised here.
    """
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import _extract_usage

    sdk_result = _FakeRunResult(
        final_output="x",
        input_tokens=42,
        output_tokens=17,
        cached_tokens=5,
    )
    u = _extract_usage(sdk_result)
    assert u.input_tokens == 42
    assert u.output_tokens == 17
    assert u.cached_input_tokens == 5


def test_extract_usage_handles_both_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 10.1 HIGH-1 regression-guard: ``_project_agents_usage``
    works for BOTH dict-shaped and attribute-bearing usage objects.

    The canonical real-SDK path goes through ``context_wrapper`` (see
    ``test_extract_usage_canonical_context_wrapper_path``); this test
    pins the hypothetical-future-shape branches via the helper directly.
    """
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import _project_agents_usage

    # Branch 1: dict-shaped usage (hypothetical future SDK shape).
    u1 = _project_agents_usage({"input_tokens": 11, "output_tokens": 22, "cached_input_tokens": 3})
    assert u1.input_tokens == 11
    assert u1.output_tokens == 22
    assert u1.cached_input_tokens == 3

    # Branch 2: flat-attribute usage (hypothetical legacy shape; no nested
    # input_tokens_details — falls back to flat cached_input_tokens).
    class _AttrUsage:
        input_tokens = 7
        output_tokens = 14
        cached_input_tokens = 1
        input_tokens_details = None  # No nested details — exercise fallback.

    u2 = _project_agents_usage(_AttrUsage())
    assert u2.input_tokens == 7
    assert u2.output_tokens == 14
    assert u2.cached_input_tokens == 1


def test_project_tool_calls_extracts_from_raw_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-LLM review MED-1 patch (kilo/minimax 2026-05-25): without
    this test, ``_project_tool_calls`` was unreached at unit-test level
    because ``_FakeRunResult.raw_responses`` always defaulted to ``[]``.
    Real-SDK responses populated with tool-use blocks would have gone
    silently un-projected.

    Exercises both the attribute-shape and dict-shape paths inside
    ``_project_tool_calls`` — defensive against pre-1.0 SDK shape drift.
    """
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import _project_tool_calls

    # Attribute-shaped tool-call objects (one plausible real-SDK shape).
    class _AttrToolCall:
        def __init__(self, name: str, arguments: dict, id: str) -> None:
            self.name = name
            self.arguments = arguments
            self.id = id

    class _AttrResp:
        def __init__(self, tcs: list[_AttrToolCall]) -> None:
            self.tool_calls = tcs

    # Dict-shaped tool calls (alternative real-SDK shape).
    dict_resp = {
        "tool_calls": [
            {"name": "lookup", "arguments": {"q": "weather"}, "id": "call_d1"},
        ]
    }

    raw_responses = [
        _AttrResp([_AttrToolCall("search", {"q": "agenteval"}, "call_a1")]),
        dict_resp,
    ]
    traces = _project_tool_calls(raw_responses)

    assert len(traces) == 2
    assert traces[0].name == "search"
    assert traces[0].args == {"q": "agenteval"}
    assert traces[0].gen_ai_tool_call_id == "call_a1"
    assert traces[0].sequence_index == 0
    assert traces[1].name == "lookup"
    assert traces[1].args == {"q": "weather"}
    assert traces[1].gen_ai_tool_call_id == "call_d1"
    assert traces[1].sequence_index == 1


def test_project_tool_calls_handles_empty_or_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_project_tool_calls`` returns ``[]`` for None, non-list, and
    empty inputs without raising. Pinned per cross-LLM review MED-1.
    """
    _install_fake_sdk(monkeypatch)
    from AgentEval.coding_agent.openai_agents import _project_tool_calls

    assert _project_tool_calls(None) == []
    assert _project_tool_calls([]) == []
    assert _project_tool_calls("not a list") == []


def test_run_propagates_sdk_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """SDK exceptions propagate from `run()`; adapter does not swallow them."""
    _install_fake_sdk(monkeypatch, next_exc=RuntimeError("SDK exploded"))

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    with pytest.raises(RuntimeError, match=r"SDK exploded"):
        adapter.run(prompt="trigger error")


def test_run_handles_missing_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """RunResult without cost attributes → cost_usd defaults to 0.0."""

    class _Minimal:
        final_output = "done"
        raw_responses: list[Any] = []

    _install_fake_sdk(monkeypatch, next_result=_Minimal())  # type: ignore[arg-type]

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    result = adapter.run(prompt="say done")

    assert result.cost_usd == 0.0
    assert result.usage.input_tokens == 0


def test_entry_point_registration() -> None:
    """``openai-agents-sdk`` entry-point under ``agenteval.coding_agents``
    resolves to ``OpenAIAgentsSDKAdapter`` per AC-10.2.3.
    """
    import importlib.metadata

    eps = importlib.metadata.entry_points(group="agenteval.coding_agents")
    matching = [ep for ep in eps if ep.name == "openai-agents-sdk"]
    assert len(matching) == 1, (
        f"expected exactly 1 `openai-agents-sdk` entry-point under "
        f"`agenteval.coding_agents`; got {len(matching)} ({matching!r})"
    )
    ep = matching[0]
    assert ep.module == "AgentEval.coding_agent.openai_agents"
    assert ep.attr == "OpenAIAgentsSDKAdapter"


def test_run_calls_enforce_tier1_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """`enforce_tier1_no_llm()` is wired at run-entry per PRD FR30b."""
    _install_fake_sdk(
        monkeypatch,
        next_result=_FakeRunResult(final_output="ok"),
    )

    calls: list[None] = []

    def _spy() -> None:
        calls.append(None)

    monkeypatch.setattr("AgentEval._kernel.tier_acl.enforce_tier1_no_llm", _spy)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    adapter.run(prompt="hello")
    assert len(calls) == 1, "enforce_tier1_no_llm must be invoked once per run()"


def test_run_calls_record_run_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 10.1 HIGH-4 lesson applied UPSTREAM: ``_record_run_metadata``
    is invoked at end of ``run()`` so Agent SDK runs surface in the
    RunManifest sidecar.
    """
    _install_fake_sdk(
        monkeypatch,
        next_result=_FakeRunResult(final_output="ok", total_cost_usd=0.002),
    )

    calls: list[dict[str, Any]] = []

    def _spy(**kwargs: Any) -> None:
        calls.append(kwargs)

    # Patch the helper at its canonical location (generic.py imports the
    # listener-side `record_active_run_metadata`); the adapter pulls the
    # wrapper from `generic.py`, so patch there.
    monkeypatch.setattr("AgentEval.coding_agent.generic._record_run_metadata", _spy)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter(model="gpt-4o")
    adapter.run(prompt="hello")
    assert len(calls) == 1, "_record_run_metadata must be invoked once per run()"
    kw = calls[0]
    assert kw["adapter_name"] == "OpenAIAgentsSDKAdapter"
    assert kw["model"] == "gpt-4o"
    # Cross-LLM review MED-2: cost is permanently 0.0 (real SDK exposes none).
    assert kw["total_cost_usd"] == 0.0
    assert kw["completeness"] == "complete"
    assert kw["mcp_coverage"] == "hosted_in_process"
    assert len(kw["prompt_hashes"]) == 1
