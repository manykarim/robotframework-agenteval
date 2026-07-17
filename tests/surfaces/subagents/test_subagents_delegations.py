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

"""Tier-1 delegation extraction + occurrence/absence assertions."""

from __future__ import annotations

import pytest

from AgentEval._core import SubagentDelegationError, ToolCallTrace, get_keyword_tier
from SubagentsLibrary import SubagentsLibrary

from ._fakes import delegating_result


def test_get_delegations_extracts_in_sequence_order() -> None:
    result = delegating_result("docs-writer", "code-reviewer")
    dels = SubagentsLibrary().get_delegations(result)
    assert [d.subagent for d in dels] == ["docs-writer", "code-reviewer"]


def test_get_delegations_honors_custom_tool_name() -> None:
    from AgentEval._core import AgentRunResult

    result = AgentRunResult(
        response_text="",
        tool_calls=[ToolCallTrace(name="dispatch_agent", args={"subagent_type": "x"}, sequence_index=0)],
    )
    lib = SubagentsLibrary()
    assert SubagentsLibrary().get_delegations(result) == []
    dels = lib.get_delegations(result, delegation_tool="dispatch_agent")
    assert [d.subagent for d in dels] == ["x"]


def test_should_have_delegated_to_passes_on_occurrence() -> None:
    result = delegating_result("docs-writer")
    SubagentsLibrary().should_have_delegated_to(result, "docs-writer")


def test_should_have_delegated_to_fails_when_absent() -> None:
    result = delegating_result("docs-writer")
    with pytest.raises(SubagentDelegationError):
        SubagentsLibrary().should_have_delegated_to(result, "db-admin")


def test_should_not_have_delegated_passes_when_none() -> None:
    result = delegating_result()
    SubagentsLibrary().should_not_have_delegated(result)


def test_should_not_have_delegated_targeted_ignores_others() -> None:
    result = delegating_result("docs-writer")
    SubagentsLibrary().should_not_have_delegated(result, "db-admin")


def test_should_not_have_delegated_fails_on_any_when_untargeted() -> None:
    result = delegating_result("docs-writer")
    with pytest.raises(SubagentDelegationError):
        SubagentsLibrary().should_not_have_delegated(result)


def test_should_not_have_delegated_fails_on_named_target() -> None:
    result = delegating_result("db-admin")
    with pytest.raises(SubagentDelegationError):
        SubagentsLibrary().should_not_have_delegated(result, "db-admin")


def test_delegation_keywords_are_tier_1() -> None:
    assert get_keyword_tier(SubagentsLibrary.get_delegations) == 1
    assert get_keyword_tier(SubagentsLibrary.should_have_delegated_to) == 1
    assert get_keyword_tier(SubagentsLibrary.should_not_have_delegated) == 1
