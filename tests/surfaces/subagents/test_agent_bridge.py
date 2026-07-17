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

"""The Claude-subagent-``.md`` -> harness ``SubAgents`` bridge shim.

Unit tests build the capability from real Claude-shaped ``.md`` files (no LLM is
called - constructing ``SubAgents`` only reads frontmatter and builds model-less
delegate agents). A gated live smoke drives an actual in-process run and asserts
the model routed to the expected subagent, read back through
``Subagent.Get Routed Subagents``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from AgentEval._core import InvalidConfigError, MissingExtraError
from SubagentsLibrary import SubagentsLibrary

pytest.importorskip("pydantic_ai_harness", reason="the subagent bridge needs the [agent] extra")


def _write_agent(folder: Path, name: str, description: str, extra: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra}---\nYou are the {name}.\n",
        encoding="utf-8",
    )
    return path


def test_builds_subagents_capability_from_dir(tmp_path: Path) -> None:
    _write_agent(tmp_path, "code-reviewer", "Reviews code for bugs")
    _write_agent(tmp_path, "docs-writer", "Writes documentation")
    caps = SubagentsLibrary().as_subagents_capability(tmp_path)
    # One delegate per file, discovered by the harness under the delegate_task tool.
    assert sorted(caps._by_name.keys()) == ["code-reviewer", "docs-writer"]
    assert caps.tool_name == "delegate_task"


def test_tolerates_claude_extra_frontmatter_fields(tmp_path: Path) -> None:
    # Claude subagent files carry model/color and comma-form tools; none of these
    # should break discovery - the harness parser ignores unknown keys.
    _write_agent(
        tmp_path,
        "researcher",
        "Researches topics",
        extra="tools: Read, Grep, WebSearch\nmodel: sonnet\ncolor: blue\n",
    )
    caps = SubagentsLibrary().as_subagents_capability(tmp_path)
    assert list(caps._by_name.keys()) == ["researcher"]


def test_custom_tool_name_is_honored(tmp_path: Path) -> None:
    _write_agent(tmp_path, "planner", "Plans work")
    caps = SubagentsLibrary().as_subagents_capability(tmp_path, tool_name="route_to")
    assert caps.tool_name == "route_to"


def test_custom_tool_resolver_is_passed_through(tmp_path: Path) -> None:
    _write_agent(tmp_path, "worker", "Does work", extra="tools: Read\n")
    sentinel: list[str] = []

    def resolver(tool_name: str) -> tuple[Any, ...]:
        sentinel.append(tool_name)
        return ()

    caps = SubagentsLibrary().as_subagents_capability(tmp_path, tool_resolver=resolver)
    assert caps.tool_resolver is resolver
    # The harness invoked the resolver for the declared tool while building the delegate.
    assert sentinel == ["Read"]


def test_missing_directory_raises_invalid_config(tmp_path: Path) -> None:
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().as_subagents_capability(tmp_path / "does-not-exist")


def test_directory_without_md_files_raises_invalid_config(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not an agent", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().as_subagents_capability(tmp_path)


def test_missing_agent_extra_reports_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    _write_agent(tmp_path, "x", "An agent")
    # Force the lazy `from pydantic_ai_harness.subagents import SubAgents` to fail.
    monkeypatch.setitem(sys.modules, "pydantic_ai_harness.subagents", None)
    with pytest.raises(MissingExtraError) as excinfo:
        SubagentsLibrary().as_subagents_capability(tmp_path)
    assert excinfo.value.extra == "agent"


# --------------------------------------------------------------------------- #
# Gated live smoke - real MiniMax run, real routing.                          #
# --------------------------------------------------------------------------- #

_LIVE = pytest.mark.skipif(
    not (os.environ.get("AGENTEVAL_API_KEY") and os.environ.get("AGENTEVAL_MODEL")),
    reason="set AGENTEVAL_MODEL/AGENTEVAL_BASE_URL/AGENTEVAL_API_KEY for the live subagent-routing smoke",
)


@_LIVE
def test_live_routes_to_expected_subagent(tmp_path: Path) -> None:
    from AgentEval._core import get_adapter

    _write_agent(
        tmp_path,
        "sql-expert",
        "Writes and optimizes SQL database queries and schema migrations.",
    )
    _write_agent(
        tmp_path,
        "poet",
        "Writes poems, verse, and creative literary prose.",
    )
    lib = SubagentsLibrary()
    caps = lib.as_subagents_capability(tmp_path)

    result = get_adapter("in-process", capabilities=[caps]).run(
        "I need help writing a SQL query to find the top 10 customers by total order value. "
        "Delegate this to the most appropriate specialist subagent."
    )
    routed = lib.get_routed_subagents(result)
    # Report the REAL routing; assert the DB task went to the SQL specialist.
    assert "sql-expert" in routed.names, f"observed routing: names={routed.names} total={routed.total}"
