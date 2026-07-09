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

"""Single-library-import composition tests (`compose-single-library-import` change).

Covers the `single-library-import` capability:
- `Library AgentEval` composes all 13 sub-libraries (task 4.1 / 4.2).
- The import-time collision detector stays loud (task 4.3).
- Budget forwarding to every `_HostBudgetPlumbing` subclass, incl. the C55
  closure for `Skill.Get Activation Decision` (task 4.4 / 4.5).
- Missing-module tolerance + constructor-failure loudness (task 4.6).
- Standalone imports keep working without `WITH NAME` (task 5.2 / 5.3).
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from robot.api.deco import keyword

from AgentEval import AgentEval
from AgentEval._kernel import guardrails
from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import CostExceededError
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

# The package module (holds the `_SUB_LIBRARIES` registry we monkeypatch).
# Imported via importlib to avoid shadowing the `AgentEval` class name.
_AGENTEVAL_MOD = importlib.import_module("AgentEval")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SKILL_FIXTURE = FIXTURES / "skills" / "example-valid.md"
MCP_FIXTURE = FIXTURES / "mcp" / "mcp-valid.json"


# --------------------------------------------------------------------------- #
# Task 4.1 — single import reaches one keyword from each of the 13 sub-libs    #
# --------------------------------------------------------------------------- #

_ONE_PER_SUBLIBRARY = [
    "Skill.Get Frontmatter",  # SkillsLibrary
    "Subagent.Get Frontmatter",  # SubagentsLibrary
    "Hook.Get Config",  # HooksLibrary
    "MCP.Get Server Config",  # MCPLibrary
    "Stat.Get Pass At K",  # StatsLibrary
    "Judge.Get Score",  # JudgeLibrary
    "Send Prompt",  # OrchestrationLibrary
    "Get Spans",  # TelemetryLibrary
    "Get Tool Call Count",  # MetricsLibrary
    "Trajectory Should Match",  # AssertionsLibrary
    "Get Cohort Heatmap",  # HeatmapLibrary
    "Start Conversation",  # ConversationLibrary (add-multi-turn-conversation-testing)
    "RedTeam.Run Probe",  # RedTeamLibrary (add-red-team-probes)
    "Save Metrics Baseline",  # BaselineLibrary (add-regression-baseline-tracking)
]


def test_single_import_reaches_all_sublibrary_keywords() -> None:
    lib = AgentEval()
    names = set(lib.get_keyword_names())
    missing = [kw for kw in _ONE_PER_SUBLIBRARY if kw not in names]
    assert not missing, f"single `Library AgentEval` import is missing keywords: {missing!r}"
    assert len(lib._loaded_components) == 14


# --------------------------------------------------------------------------- #
# Task 4.2 — composed set == union of sub-library @keyword methods + top-level #
# --------------------------------------------------------------------------- #


def _robot_names(cls: type) -> set[str]:
    names: set[str] = set()
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        try:
            attr = getattr(cls, attr_name)
        except Exception:
            continue
        target = getattr(attr, "__func__", attr)
        robot_name = getattr(target, "robot_name", None)
        if robot_name is not None:
            names.add(robot_name)
    return names


def test_composed_keyword_set_equals_union_of_parts() -> None:
    lib = AgentEval()
    composed = set(lib.get_keyword_names())

    expected = _robot_names(AgentEval)  # top-level config/tier keywords
    for module_path, cls_name in _AGENTEVAL_MOD._SUB_LIBRARIES:
        cls = getattr(importlib.import_module(module_path), cls_name)
        expected |= _robot_names(cls)

    assert composed == expected, (
        f"composed set != union of parts.\n"
        f"  only in composed: {sorted(composed - expected)!r}\n"
        f"  only in parts:    {sorted(expected - composed)!r}"
    )


# --------------------------------------------------------------------------- #
# Task 4.3 — collision detector stays loud; full registry constructs clean     #
# --------------------------------------------------------------------------- #


def _install_stub_module(name: str, cls: type) -> None:
    mod = types.ModuleType(name)
    setattr(mod, cls.__name__, cls)
    sys.modules[name] = mod


def test_duplicate_robot_name_raises_naming_both_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubA:
        @keyword(name="Dup.Keyword Name")
        def a(self) -> None: ...

    class _StubB:
        @keyword(name="Dup.Keyword Name")
        def b(self) -> None: ...

    _install_stub_module("agenteval_stub_collide_a", _StubA)
    _install_stub_module("agenteval_stub_collide_b", _StubB)
    monkeypatch.setattr(
        _AGENTEVAL_MOD,
        "_SUB_LIBRARIES",
        (
            ("agenteval_stub_collide_a", "_StubA"),
            ("agenteval_stub_collide_b", "_StubB"),
        ),
    )
    with pytest.raises(RuntimeError) as exc_info:
        AgentEval()
    msg = str(exc_info.value)
    assert "Dup.Keyword Name" in msg
    assert "_StubA" in msg and "_StubB" in msg


def test_full_registry_constructs_without_collision() -> None:
    # No RuntimeError over the real 13-component composition.
    lib = AgentEval()
    assert len(lib._loaded_components) == 14


# --------------------------------------------------------------------------- #
# Task 4.4 — C55 closure: composed Skill.Get Activation Decision enforces budget#
# --------------------------------------------------------------------------- #


def _make_stub_adapter(response_text: str, cost: float) -> type[InProcessAdapter]:
    class _Stub(InProcessAdapter):
        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=0.001,
                trace_id="a" * 32,
            )

    return _Stub


def test_c55_skill_activation_decision_enforces_composed_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under `AgentEval(max_cost_usd=0.0)` the composed `Skill.Get Activation Decision`
    reads the forwarded budget and its `@guarded_fanout` Layer-2 meter raises
    `CostExceededError` (closes C55 — the budget is no longer dropped by the
    Story 2.2 carve-out).
    """
    register_adapter("stub_c55_cost", _make_stub_adapter("no match here", cost=5.0))
    # Cost source reports nonzero spend; the t=0 meter check breaches the 0.0 cap.
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 5.0)

    lib = AgentEval(max_cost_usd=0.0)
    bound = lib.keywords["Skill.Get Activation Decision"]
    with pytest.raises(CostExceededError):
        bound(SKILL_FIXTURE, "does the skill activate?", adapter="stub_c55_cost")


# --------------------------------------------------------------------------- #
# Task 4.5 — budget forwarded to every _HostBudgetPlumbing subclass, no branch #
# --------------------------------------------------------------------------- #


def _budget_components(lib: AgentEval) -> dict[str, _HostBudgetPlumbing]:
    out: dict[str, _HostBudgetPlumbing] = {}
    for bound in lib.keywords.values():
        inst = getattr(bound, "__self__", None)
        if isinstance(inst, _HostBudgetPlumbing):
            out[type(inst).__name__] = inst
    return out


def test_composed_mcp_component_carries_forwarded_budget() -> None:
    lib = AgentEval(max_cost_usd=1.0, max_runtime_seconds=60)
    comps = _budget_components(lib)
    mcp = comps["MCPLibrary"]
    assert mcp._max_cost_usd == 1.0
    assert mcp._max_runtime_seconds == 60.0


def test_every_host_budget_subclass_is_forwarded_without_a_class_branch() -> None:
    """The unified `_HostBudgetPlumbing` subclass check forwards budgets to ALL
    such components (Skills, MCP, Stats, Judge, Orchestration) — no per-class
    branch needed. Verified by asserting every composed budget-aware component
    carries the forwarded values.
    """
    lib = AgentEval(max_cost_usd=3.0, max_runtime_seconds=45)
    comps = _budget_components(lib)
    # All 5 budget-aware sub-libraries composed under AgentEval.
    assert {"SkillsLibrary", "MCPLibrary", "StatsLibrary", "JudgeLibrary", "OrchestrationLibrary"} <= set(comps)
    for name, inst in comps.items():
        assert inst._max_cost_usd == 3.0, f"{name} did not receive max_cost_usd"
        assert inst._max_runtime_seconds == 45.0, f"{name} did not receive max_runtime_seconds"


# --------------------------------------------------------------------------- #
# Task 4.6 — missing-module tolerance + constructor-failure loudness           #
# --------------------------------------------------------------------------- #


def test_missing_module_is_skipped_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _AGENTEVAL_MOD,
        "_SUB_LIBRARIES",
        (
            ("AgentEval.hooks.library", "HooksLibrary"),
            ("AgentEval.does_not_exist.library", "GhostLibrary"),
        ),
    )
    lib = AgentEval()  # constructs despite the missing module.
    assert "HooksLibrary" in lib._loaded_components
    assert "GhostLibrary" not in lib._loaded_components


def test_constructor_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomLibrary:
        def __init__(self) -> None:
            raise ValueError("boom from constructor")

    _install_stub_module("agenteval_stub_boom", _BoomLibrary)
    monkeypatch.setattr(
        _AGENTEVAL_MOD,
        "_SUB_LIBRARIES",
        (("agenteval_stub_boom", "_BoomLibrary"),),
    )
    with pytest.raises(ValueError, match="boom from constructor"):
        AgentEval()


# --------------------------------------------------------------------------- #
# Task 5.2 — standalone import with budget kwargs, no WITH NAME                 #
# --------------------------------------------------------------------------- #


def test_standalone_skills_import_with_budget_kwargs() -> None:
    from AgentEval.skills.library import SkillsLibrary

    standalone = SkillsLibrary(max_cost_usd=2.0)
    assert standalone._max_cost_usd == 2.0
    # Baked prefix means the call site reads identically to the composed import.
    assert SkillsLibrary.get_frontmatter.robot_name == "Skill.Get Frontmatter"
    fm = standalone.get_frontmatter(SKILL_FIXTURE)
    assert fm["name"] == "example-valid-skill"


# --------------------------------------------------------------------------- #
# Task 5.3 — call site is portable between composed + standalone import         #
# --------------------------------------------------------------------------- #


def test_mcp_get_server_config_portable_between_import_styles() -> None:
    from AgentEval.mcp.library import MCPLibrary

    composed = AgentEval()
    standalone = MCPLibrary()

    # Same RF keyword name resolves under both import styles.
    assert "MCP.Get Server Config" in composed.get_keyword_names()
    assert MCPLibrary.get_server_config.robot_name == "MCP.Get Server Config"

    via_composed = composed.keywords["MCP.Get Server Config"](MCP_FIXTURE)
    via_standalone = standalone.get_server_config(MCP_FIXTURE)
    assert via_composed == via_standalone


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
