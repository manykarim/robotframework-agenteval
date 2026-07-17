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

"""Tier-1 frontmatter getters + validator (deterministic, no model)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError
from SkillsLibrary import SkillsLibrary


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


def test_get_frontmatter_returns_parsed_mapping(lib: SkillsLibrary, skill_file: Path) -> None:
    fm = lib.get_frontmatter(skill_file)
    assert fm["name"] == "web-search"
    assert fm["allowed-tools"] == ["Bash", "Read"]


def test_get_description(lib: SkillsLibrary, skill_file: Path) -> None:
    assert lib.get_description(skill_file) == "Search the web for current information and news."


def test_get_allowed_tools_returns_declared_list(lib: SkillsLibrary, skill_file: Path) -> None:
    # Scenario: Read a frontmatter field -> returns the declared tool list.
    assert lib.get_allowed_tools(skill_file) == ["Bash", "Read"]


def test_get_disable_model_invocation(lib: SkillsLibrary, skill_file: Path) -> None:
    result = lib.get_disable_model_invocation(skill_file)
    assert result is False


def test_should_be_valid_frontmatter_passes_on_valid(lib: SkillsLibrary, skill_file: Path) -> None:
    fm = lib.get_frontmatter(skill_file)
    # Does not raise.
    lib.should_be_valid_frontmatter(fm)


def test_invalid_frontmatter_names_missing_field(lib: SkillsLibrary) -> None:
    # Scenario: Invalid frontmatter fails validation -> the assertion fails and
    # names the missing REQUIRED field. Only name + description are required
    # (Agent Skills spec); the other two are optional.
    broken = {"name": "web-search", "allowed-tools": []}  # missing description
    with pytest.raises(InvalidConfigError) as excinfo:
        lib.should_be_valid_frontmatter(broken)
    assert "description" in str(excinfo.value)
    assert excinfo.value.field == "description"


def test_optional_fields_absent_is_valid(lib: SkillsLibrary) -> None:
    # A skill with only the two required fields is valid (matches real skills).
    lib.should_be_valid_frontmatter({"name": "web-search", "description": "x"})


def test_get_description_fails_when_missing(lib: SkillsLibrary, tmp_path: Path) -> None:
    path = tmp_path / "no-desc.md"
    path.write_text(
        "---\nname: x\nallowed-tools: []\ndisable-model-invocation: false\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(InvalidConfigError) as excinfo:
        lib.get_description(path)
    assert "description" in str(excinfo.value)


def test_non_markdown_extension_rejected(lib: SkillsLibrary, tmp_path: Path) -> None:
    path = tmp_path / "skill.txt"
    path.write_text("---\nname: x\n---\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError) as excinfo:
        lib.get_frontmatter(path)
    assert ".md" in str(excinfo.value)


def test_missing_leading_delimiter_rejected(lib: SkillsLibrary, tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("name: x\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError) as excinfo:
        lib.get_frontmatter(path)
    assert "leading" in str(excinfo.value)


def test_disable_model_invocation_rejects_int(lib: SkillsLibrary, tmp_path: Path) -> None:
    path = tmp_path / "int-flag.md"
    path.write_text(
        "---\nname: x\ndescription: y\nallowed-tools: []\ndisable-model-invocation: 1\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(InvalidConfigError) as excinfo:
        lib.get_disable_model_invocation(path)
    assert "disable-model-invocation" in str(excinfo.value)
