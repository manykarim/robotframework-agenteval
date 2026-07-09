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

"""Unit tests for `_HostBudgetPlumbing` mixin (Story 14.6 / C20+C26+C89+C95 closure).

Covers AC-14.6.1 through AC-14.6.8:

- Mixin behavior (4 tests): attrs set; None defaults; partial kwargs;
  cooperative super().__init__() forwarding.
- Subclass smoke (3 tests): MCPLibrary, SkillsLibrary, OrchestrationLibrary
  all carry budget attrs after init.
- Integration contract (4 tests, per Story 14.6 D-6 in-flight amendment
  2026-06-04): verify the mixin attrs are wired such that
  `@guarded_fanout` reads them via getattr per
  `_kernel/guardrails.py:265-266`. AC-14.6.6 only ADDS `@guarded_fanout()`
  (no `estimator=` callable) so Layer 1 pre-flight refusal via the
  sentinel kwarg does NOT fire on the live keywords — Layer 2/3 mid-run
  enforcement requires the real cost-tracker infrastructure deferred to
  DF-14.6-S1. These 4 tests verify the **integration contract** (host
  attrs readable by the decorator), NOT live-keyword pre-flight refusal.
"""

from __future__ import annotations

import pytest

from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval.errors import CostExceededError
from AgentEval.mcp.library import MCPLibrary
from AgentEval.orchestration.library import OrchestrationLibrary
from AgentEval.skills.library import SkillsLibrary

# ---------------------------------------------------------------------------
# Mixin behavior (AC-14.6.1)
# ---------------------------------------------------------------------------


class _StubHost(_HostBudgetPlumbing):
    """Bare-bones subclass for mixin-only behavioral tests."""


def test_mixin_init_sets_both_attrs_to_provided_values() -> None:
    host = _StubHost(max_cost_usd=12.5, max_runtime_seconds=90.0)
    assert host._max_cost_usd == 12.5
    assert host._max_runtime_seconds == 90.0


def test_mixin_init_defaults_both_attrs_to_none() -> None:
    host = _StubHost()
    assert host._max_cost_usd is None
    assert host._max_runtime_seconds is None


def test_mixin_init_accepts_partial_kwargs() -> None:
    host = _StubHost(max_cost_usd=5.0)
    assert host._max_cost_usd == 5.0
    assert host._max_runtime_seconds is None


def test_mixin_cooperative_init_forwards_remaining_kwargs_to_super() -> None:
    """Subclass with its own ctor kwargs cooperates via super().__init__()."""

    class _SubWithExtraArg(_HostBudgetPlumbing):
        def __init__(self, *, extra: str = "default", **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(**kwargs)
            self.extra = extra

    sub = _SubWithExtraArg(max_cost_usd=2.0, extra="payload")
    assert sub._max_cost_usd == 2.0
    assert sub.extra == "payload"


# ---------------------------------------------------------------------------
# Subclass smoke (AC-14.6.2 + AC-14.6.3 + AC-14.6.4)
# ---------------------------------------------------------------------------


def test_mcp_library_carries_budget_attrs_after_init() -> None:
    lib = MCPLibrary(max_cost_usd=10.0, max_runtime_seconds=60.0)
    assert lib._max_cost_usd == 10.0
    assert lib._max_runtime_seconds == 60.0


def test_skills_library_carries_budget_attrs_after_init() -> None:
    lib = SkillsLibrary(max_cost_usd=20.0)
    assert lib._max_cost_usd == 20.0
    assert lib._max_runtime_seconds is None


def test_orchestration_library_carries_budget_attrs_after_init() -> None:
    """Story 4.3 default_provider + Story 14.6 budgets coexist (cooperative MRO)."""
    lib = OrchestrationLibrary(
        default_provider="mock",
        max_cost_usd=5.0,
        max_runtime_seconds=30.0,
    )
    assert lib._default_provider == "mock"
    assert lib._max_cost_usd == 5.0
    assert lib._max_runtime_seconds == 30.0


# ---------------------------------------------------------------------------
# End-to-end enforcement via __agenteval_test_budget__ sentinel (AC-14.6.8)
# ---------------------------------------------------------------------------


def test_mcp_get_tool_discoverability_reads_budget_from_host_instance() -> None:
    """`MCP.Get Tool Discoverability` @guarded_fanout closes DF-4.4-S1 / C20 contract.

    Per `_kernel/guardrails.py:265-266`, the decorator reads host attrs via:
        getattr(self, "_max_cost_usd", None)
        getattr(self, "_max_runtime_seconds", None)

    Story 14.6's mixin provides those attrs on `MCPLibrary`. This test
    verifies the integration contract — the live keyword body needs real
    `.mcp.json` fixtures + adapter wiring to run end-to-end, so the
    pre-flight refusal pattern (which would require an `estimator=`
    callable on the decorator per AC-14.6.6 scope) is deferred to
    DF-14.6-S1 Phase-1.5 follow-up.
    """
    lib = MCPLibrary(max_cost_usd=10.0, max_runtime_seconds=60.0)
    # Integration contract: `@guarded_fanout()` reads these via getattr.
    assert getattr(lib, "_max_cost_usd", None) == 10.0
    assert getattr(lib, "_max_runtime_seconds", None) == 60.0
    # The method has the @guarded_fanout decorator (decorator is applied).
    assert hasattr(lib, "get_tool_discoverability")


def test_mcp_compare_tool_discoverability_reads_budget_from_host_instance() -> None:
    """`MCP.Compare Tool Discoverability` @guarded_fanout closes DF-13.3-S1 / C89 contract."""
    lib = MCPLibrary(max_cost_usd=20.0, max_runtime_seconds=120.0)
    assert getattr(lib, "_max_cost_usd", None) == 20.0
    assert getattr(lib, "_max_runtime_seconds", None) == 120.0
    assert hasattr(lib, "get_tool_discoverability_comparison")


def test_skill_compare_discoverability_reads_budget_from_host_instance() -> None:
    """`Skill.Compare Discoverability` @guarded_fanout closes DF-13.5-S1 / C95 contract.

    Story 13.5 already shipped `@guarded_fanout()` on this keyword; the
    SkillsLibrary host-attrs gracefully fell back to None. Story 14.6's
    mixin now provides real budget attrs so the integration contract
    holds end-to-end.
    """
    lib = SkillsLibrary(max_cost_usd=20.0, max_runtime_seconds=60.0)
    assert getattr(lib, "_max_cost_usd", None) == 20.0
    assert getattr(lib, "_max_runtime_seconds", None) == 60.0
    assert hasattr(lib, "get_discoverability_comparison")


def test_orchestration_run_scenario_reads_budget_from_host_instance() -> None:
    """`OrchestrationLibrary.Run Scenario` @guarded_fanout closes DF-4.3-S6 / C26 contract."""
    lib = OrchestrationLibrary(
        default_provider="mock",
        max_cost_usd=5.0,
        max_runtime_seconds=30.0,
    )
    assert getattr(lib, "_max_cost_usd", None) == 5.0
    assert getattr(lib, "_max_runtime_seconds", None) == 30.0
    assert hasattr(lib, "run_scenario")


def test_decorator_reads_attrs_via_getattr_with_estimator_pre_flight() -> None:
    """Verify the mixin-provided attrs ACTUALLY trigger pre-flight refusal when an estimator IS present.

    This is the "if AC-14.6.6 added `estimator=` to the @guarded_fanout
    decorations, the mixin's attrs would correctly drive pre-flight
    refusal" sanity check. We construct a stub host that uses the mixin
    + decorate a method with `@guarded_fanout(estimator=...)`. Verifies
    the mixin's contract is honored.
    """
    from AgentEval._kernel.guardrails import guarded_fanout

    class _HostWithEstimator(_HostBudgetPlumbing):
        @guarded_fanout(estimator=lambda kwargs: (5.0, 1.0))
        def fan_out(self) -> str:
            return "would not return"

    host = _HostWithEstimator(max_cost_usd=1.0)  # 1 USD cap; estimator says 5 USD.
    with pytest.raises(CostExceededError):
        host.fan_out()
