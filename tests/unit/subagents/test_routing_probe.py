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

"""Unit tests for `Subagent.Should Delegate To` + `Subagent.Get Delegation Decision`
(task 6.4).

Uses a stub adapter (registered via `register_adapter`) that emits synthetic
`Task` `ToolCallTrace`s — the same pattern the skills activation tests use.
Covers pass, miss, polling rejection, tier annotations, and budget-sentinel
consumption.
"""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import PollingDisallowedError, SubagentDelegationAssertionError
from AgentEval.subagents.library import SubagentsLibrary
from AgentEval.subagents.types import DelegationDecision
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def _make_stub(subagent: str | None, cost: float = 0.002, latency: float = 0.01) -> type[InProcessAdapter]:
    """Stub adapter emitting one Task trace to `subagent` (or none when None)."""

    class _Stub(InProcessAdapter):
        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            traces: list[ToolCallTrace] = []
            if subagent is not None:
                traces.append(
                    ToolCallTrace(
                        name="Task",
                        args={"subagent_type": subagent, "prompt": prompt},
                        result=None,
                        error=None,
                        latency_ms=1.0,
                        source="adapter",
                        gen_ai_tool_call_id="d0",
                        sequence_index=0,
                    )
                )
            return AgentRunResult(
                response_text=f"delegating to {subagent}" if subagent else "no delegation",
                tool_calls=traces,
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=latency,
                trace_id="s" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


# --------------------------------------------------------------------------- #
# Tier annotations                                                           #
# --------------------------------------------------------------------------- #


def test_should_delegate_to_is_tier_2() -> None:
    func = SubagentsLibrary.should_delegate_to
    assert get_keyword_tier(func) == 2
    assert tier_badge(2) in (func.__doc__ or "")


def test_get_delegation_decision_is_tier_3() -> None:
    func = SubagentsLibrary.get_delegation_decision
    assert get_keyword_tier(func) == 3
    assert tier_badge(3) in (func.__doc__ or "")


# --------------------------------------------------------------------------- #
# Should Delegate To                                                          #
# --------------------------------------------------------------------------- #


def test_should_delegate_to_passes(lib: SubagentsLibrary) -> None:
    register_adapter("stub_del_pass", _make_stub("code-reviewer"))
    lib.should_delegate_to("Review my PR", "code-reviewer", adapter="stub_del_pass")  # no raise


def test_should_delegate_to_fails_with_diagnostics(lib: SubagentsLibrary) -> None:
    register_adapter("stub_del_miss", _make_stub("test-writer"))
    with pytest.raises(SubagentDelegationAssertionError) as exc_info:
        lib.should_delegate_to("Review my PR", "code-reviewer", adapter="stub_del_miss")
    exc = exc_info.value
    assert exc.prompt == "Review my PR"
    assert exc.expected_subagent == "code-reviewer"
    assert "test-writer" in exc.observed_delegations
    assert exc.reasoning  # response_text carried as reasoning


def test_should_delegate_to_fails_on_no_delegation(lib: SubagentsLibrary) -> None:
    register_adapter("stub_del_none", _make_stub(None))
    with pytest.raises(SubagentDelegationAssertionError):
        lib.should_delegate_to("Review my PR", "code-reviewer", adapter="stub_del_none")


def test_should_delegate_to_rejects_polling(lib: SubagentsLibrary) -> None:
    with pytest.raises(PollingDisallowedError):
        lib.should_delegate_to("Review my PR", "code-reviewer", adapter="stub_del_pass", polling=1.0)


# --------------------------------------------------------------------------- #
# Get Delegation Decision                                                     #
# --------------------------------------------------------------------------- #


def test_get_delegation_decision_hit(lib: SubagentsLibrary) -> None:
    register_adapter("stub_dec_hit", _make_stub("code-reviewer", cost=0.05, latency=1.2))
    decision = lib.get_delegation_decision("Review my PR", "code-reviewer", adapter="stub_dec_hit")
    assert isinstance(decision, DelegationDecision)
    assert decision.delegated is True
    assert len(decision.delegations) == 1
    assert abs(decision.cost_usd - 0.05) < 1e-9
    assert abs(decision.latency_seconds - 1.2) < 1e-9


def test_get_delegation_decision_miss_does_not_raise(lib: SubagentsLibrary) -> None:
    register_adapter("stub_dec_miss", _make_stub("test-writer"))
    decision = lib.get_delegation_decision("Review my PR", "code-reviewer", adapter="stub_dec_miss")
    assert decision.delegated is False
    # `delegations` still carries what actually happened (the test-writer call).
    assert [d.subagent for d in decision.delegations] == ["test-writer"]


def test_get_delegation_decision_rejects_polling(lib: SubagentsLibrary) -> None:
    with pytest.raises(PollingDisallowedError):
        lib.get_delegation_decision("Review my PR", "code-reviewer", adapter="stub_dec_hit", polling=2.0)


def test_budget_sentinel_not_leaked_to_adapter(lib: SubagentsLibrary) -> None:
    captured: dict[str, Any] = {}

    class _CapturingStub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            captured.update(self._adapter_config)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="no delegation",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id="b" * 32,
            )

    register_adapter("stub_dec_sentinel", _CapturingStub)
    lib.get_delegation_decision(
        "prompt",
        "code-reviewer",
        adapter="stub_dec_sentinel",
        __agenteval_test_budget__=(10.0, 60.0),
    )
    assert "__agenteval_test_budget__" not in captured


def test_model_kwarg_forwarded_to_ctor(lib: SubagentsLibrary) -> None:
    ctor_kwargs_seen: dict[str, Any] = {}

    class _KwargsCapture(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            ctor_kwargs_seen.update(self._adapter_config)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="no delegation",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id="c" * 32,
            )

    register_adapter("stub_dec_model", _KwargsCapture)
    lib.get_delegation_decision("prompt", "x", adapter="stub_dec_model", model="anthropic/claude-sonnet-4-6")
    assert ctor_kwargs_seen.get("model") == "anthropic/claude-sonnet-4-6"
