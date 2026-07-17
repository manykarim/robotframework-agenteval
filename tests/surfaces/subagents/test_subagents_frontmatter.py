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

"""Tier-1 frontmatter parsing for the subagent surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError, get_keyword_tier
from SubagentsLibrary import SubagentsLibrary


def _write(tmp_path: Path, body: str, name: str = "agent.md") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_get_frontmatter_parses_required_and_optional_fields(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "---\nname: code-reviewer\ndescription: Reviews diffs\ntools: [Read, Grep]\nskills: [lint]\n---\nbody\n",
    )
    fm = SubagentsLibrary().get_frontmatter(path)
    assert fm["name"] == "code-reviewer"
    assert fm["description"] == "Reviews diffs"
    assert fm["tools"] == ["Read", "Grep"]
    assert fm["skills"] == ["lint"]


def test_get_frontmatter_missing_file_raises_invalid_config(tmp_path: Path) -> None:
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().get_frontmatter(tmp_path / "nope.md")


def test_get_frontmatter_missing_required_field_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: only-name\n---\nbody\n")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().get_frontmatter(path)


def test_get_frontmatter_bad_yaml_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: x\n  bad: : :\n---\n")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().get_frontmatter(path)


def test_get_frontmatter_is_tier_1() -> None:
    assert get_keyword_tier(SubagentsLibrary.get_frontmatter) == 1
