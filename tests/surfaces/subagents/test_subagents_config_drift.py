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

"""Tier-1 config-drift checks: Should Declare Skills, Tools Should Be Subset Of."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError, get_keyword_tier
from SubagentsLibrary import SubagentsLibrary


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "agent.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_should_declare_skills_passes_when_declared(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\nskills: [pdf-tools, web-search]\n---\n")
    SubagentsLibrary().should_declare_skills(path, "pdf-tools", "web-search")


def test_should_declare_skills_fails_when_missing(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\nskills: [pdf-tools]\n---\n")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().should_declare_skills(path, "review-checklist")


def test_should_declare_skills_fails_when_skills_absent(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\n---\n")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().should_declare_skills(path, "review-checklist")


def test_should_declare_skills_requires_expected_names(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\nskills: [x]\n---\n")
    with pytest.raises(ValueError):
        SubagentsLibrary().should_declare_skills(path)


def test_tools_subset_passes_when_within_allowlist(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\ntools: [Read, Grep]\n---\n")
    SubagentsLibrary().tools_should_be_subset_of(path, "Read", "Grep", "Bash")


def test_tools_subset_fails_and_names_disallowed(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\ntools: [Read, Bash]\n---\n")
    with pytest.raises(InvalidConfigError) as exc:
        SubagentsLibrary().tools_should_be_subset_of(path, "Read", "Grep")
    assert "Bash" in str(exc.value)


def test_tools_subset_fails_when_tools_absent(tmp_path: Path) -> None:
    path = _write(tmp_path, "---\nname: r\ndescription: d\n---\n")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().tools_should_be_subset_of(path, "Read")


def test_config_drift_keywords_are_tier_1() -> None:
    assert get_keyword_tier(SubagentsLibrary.should_declare_skills) == 1
    assert get_keyword_tier(SubagentsLibrary.tools_should_be_subset_of) == 1
