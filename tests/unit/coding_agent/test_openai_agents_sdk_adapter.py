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


class _FakeRunResult:
    """Shape mirrors what the adapter reads. `usage` is a ``dict`` in this
    fixture — matches the JSON fixture's recorded shape.
    """

    def __init__(
        self,
        final_output: str,
        total_cost_usd: float = 0.0,
        usage: dict[str, Any] | None = None,
        raw_responses: list[Any] | None = None,
    ) -> None:
        self.final_output = final_output
        self.total_cost_usd = total_cost_usd
        self.usage = usage
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
        usage=fixture["usage"],
    )
    _install_fake_sdk(monkeypatch, next_result=sdk_result)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter(model="gpt-4o")
    result = adapter.run(prompt="hello")

    assert result.response_text == fixture["final_output"]
    assert result.cost_usd == pytest.approx(fixture["total_cost_usd"])
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
    sdk_result = _FakeRunResult(final_output="ok", total_cost_usd=0.001, usage={})
    _install_fake_sdk(monkeypatch, next_result=sdk_result)

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter()
    result = adapter.run(prompt="x", mcp_servers={"srv": object()})

    assert result.metadata.mcp_coverage == "external_mixed"
    assert result.response_text == "ok"


def test_extract_usage_handles_both_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 10.2 D-3 + Story 10.1 HIGH-1 regression-guard: ``_extract_usage``
    works for BOTH dict-shaped and attribute-bearing ``usage`` fields.

    Without this defensive branching, the next SDK release that flips the
    shape silently breaks usage reporting — exactly the bug Story 10.1's
    cross-LLM empirical probe surfaced.
    """
    _install_fake_sdk(monkeypatch)  # only for import path
    from AgentEval.coding_agent.openai_agents import _extract_usage

    # Branch 1: dict-shaped usage
    dict_result = _FakeRunResult(
        final_output="x",
        usage={"input_tokens": 11, "output_tokens": 22, "cached_input_tokens": 3},
    )
    u1 = _extract_usage(dict_result)
    assert u1.input_tokens == 11
    assert u1.output_tokens == 22
    assert u1.cached_input_tokens == 3

    # Branch 2: attribute-bearing usage
    class _AttrUsage:
        input_tokens = 7
        output_tokens = 14
        cached_input_tokens = 1

    class _AttrResult:
        final_output = "y"
        total_cost_usd = 0.0
        usage = _AttrUsage()
        raw_responses: list[Any] = []

    u2 = _extract_usage(_AttrResult())
    assert u2.input_tokens == 7
    assert u2.output_tokens == 14
    assert u2.cached_input_tokens == 1


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
    assert len(calls) == 1, "enforce_tier1_no_llm must be invoked exactly once per run()"


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
    assert kw["total_cost_usd"] == pytest.approx(0.002)
    assert kw["completeness"] == "complete"
    assert kw["mcp_coverage"] == "hosted_in_process"
    assert len(kw["prompt_hashes"]) == 1
