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

"""Unit tests for the Tier-1 delegation assertion/getter keywords (task 6.2).

Covers every spec scenario for `Subagent.Get Delegations`,
`Subagent.Should Have Delegated To`, `Subagent.Should Not Have Delegated`.
"""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import SubagentDelegationAssertionError
from AgentEval.subagents.library import SubagentsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def _tct(name: str, args: dict[str, Any], seq: int) -> ToolCallTrace:
    return ToolCallTrace(
        name=name,
        args=args,
        result=None,
        error=None,
        latency_ms=0.0,
        source="adapter",
        gen_ai_tool_call_id=f"id-{seq}",
        sequence_index=seq,
    )


def _result(*traces: ToolCallTrace, response_text: str = "ok") -> AgentRunResult:
    return AgentRunResult(
        response_text=response_text,
        tool_calls=list(traces),
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="t" * 32,
    )


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


# --------------------------------------------------------------------------- #
# Tier annotations + badges                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method",
    ["get_delegations", "should_have_delegated_to", "should_not_have_delegated"],
)
def test_keywords_are_tier_1(lib: SubagentsLibrary, method: str) -> None:
    func = getattr(SubagentsLibrary, method)
    assert get_keyword_tier(func) == 1
    assert tier_badge(1) in (func.__doc__ or "")


# --------------------------------------------------------------------------- #
# Get Delegations                                                             #
# --------------------------------------------------------------------------- #


def test_get_delegations_returns_ordered_records(lib: SubagentsLibrary) -> None:
    result = _result(
        _tct("Task", {"subagent_type": "code-reviewer", "prompt": "review the diff"}, 0),
        _tct("Bash", {"command": "ls"}, 1),
        _tct("Task", {"subagent_type": "test-writer", "prompt": "add tests"}, 2),
    )
    records = lib.get_delegations(result)
    assert [r.subagent for r in records] == ["code-reviewer", "test-writer"]


def test_get_delegations_empty_on_no_delegation(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Read", {"file": "x"}, 0), _tct("Bash", {"command": "ls"}, 1))
    assert lib.get_delegations(result) == []


def test_get_delegations_custom_tool(lib: SubagentsLibrary) -> None:
    result = _result(_tct("dispatch_agent", {"agent": "docs-writer"}, 0))
    records = lib.get_delegations(result, delegation_tool="dispatch_agent")
    assert [r.subagent for r in records] == ["docs-writer"]


# --------------------------------------------------------------------------- #
# Should Have Delegated To                                                    #
# --------------------------------------------------------------------------- #


def test_should_have_delegated_to_passes(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "code-reviewer"}, 0))
    lib.should_have_delegated_to(result, "code-reviewer")  # no raise


def test_should_have_delegated_to_fails_listing_observed(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "test-writer"}, 0))
    with pytest.raises(SubagentDelegationAssertionError) as exc_info:
        lib.should_have_delegated_to(result, "code-reviewer")
    exc = exc_info.value
    assert exc.expected_subagent == "code-reviewer"
    assert "test-writer" in exc.observed_delegations
    assert exc.fix_suggestion


def test_should_have_delegated_to_fails_when_none(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Bash", {"command": "ls"}, 0))
    with pytest.raises(SubagentDelegationAssertionError) as exc_info:
        lib.should_have_delegated_to(result, "code-reviewer")
    assert "no delegations" in str(exc_info.value).lower()


def test_should_have_delegated_to_is_case_sensitive(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "Code-Reviewer"}, 0))
    with pytest.raises(SubagentDelegationAssertionError):
        lib.should_have_delegated_to(result, "code-reviewer")


# --------------------------------------------------------------------------- #
# Should Not Have Delegated                                                   #
# --------------------------------------------------------------------------- #


def test_should_not_have_delegated_passes_when_none(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Bash", {"command": "ls"}, 0))
    lib.should_not_have_delegated(result)  # no raise


def test_should_not_have_delegated_fails_on_any(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "code-reviewer"}, 0))
    with pytest.raises(SubagentDelegationAssertionError) as exc_info:
        lib.should_not_have_delegated(result)
    assert "code-reviewer" in exc_info.value.observed_delegations


def test_targeted_absence_ignores_other_subagents(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "code-reviewer"}, 0))
    lib.should_not_have_delegated(result, "deployer")  # no raise — deployer absent


def test_targeted_absence_fails_when_target_present(lib: SubagentsLibrary) -> None:
    result = _result(_tct("Task", {"subagent_type": "deployer"}, 0))
    with pytest.raises(SubagentDelegationAssertionError):
        lib.should_not_have_delegated(result, "deployer")


# --------------------------------------------------------------------------- #
# Codex MED: hosted-MCP tool named "task" is not a delegation                  #
# --------------------------------------------------------------------------- #


def _hosted_task(args: dict[str, Any], seq: int) -> ToolCallTrace:
    return ToolCallTrace(
        name="task",
        args=args,
        result=None,
        error=None,
        latency_ms=0.0,
        source="hosted_mcp",
        gen_ai_tool_call_id=f"mcp-{seq}",
        sequence_index=seq,
    )


def test_hosted_mcp_task_yields_no_delegations(lib: SubagentsLibrary) -> None:
    result = _result(_hosted_task({"input": "not delegation"}, 0))
    assert lib.get_delegations(result) == []


def test_should_not_have_delegated_passes_for_hosted_mcp_task(lib: SubagentsLibrary) -> None:
    result = _result(_hosted_task({"input": "not delegation"}, 0))
    lib.should_not_have_delegated(result)  # no raise — hosted "task" is not a delegation


def test_adapter_task_still_delegates_when_hosted_task_present(lib: SubagentsLibrary) -> None:
    result = _result(
        _tct("Task", {"subagent_type": "code-reviewer"}, 0),
        _hosted_task({"name": "code-reviewer"}, 1),
    )
    lib.should_have_delegated_to(result, "code-reviewer")  # adapter Task still counts


# --------------------------------------------------------------------------- #
# Codex LOW: empty-string (degraded) identities render visibly                 #
# --------------------------------------------------------------------------- #


def test_degraded_empty_identity_renders_visible_placeholder(lib: SubagentsLibrary) -> None:
    # An unrecognized Task arg-shape degrades to subagent="" (visible non-match).
    # The rendered error must NOT collapse `Observed:` to a blank line.
    result = _result(_tct("Task", {"unexpected_key": "code-reviewer"}, 0))
    with pytest.raises(SubagentDelegationAssertionError) as exc_info:
        lib.should_have_delegated_to(result, "code-reviewer")
    rendered = str(exc_info.value)
    observed_line = next(line for line in rendered.splitlines() if line.strip().startswith("Observed:"))
    assert observed_line.strip() == "Observed: <unresolved>"
