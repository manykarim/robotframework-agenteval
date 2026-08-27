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

"""Regression: allowed-tools / disable-model-invocation are OPTIONAL (Agent Skills spec).

Dogfood finding: the real published skills carry only name + description, so the
validator must accept them and the getters must default gracefully.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError
from SkillsLibrary import SkillsLibrary

MINIMAL = """---
name: rf-results
description: Parse Robot Framework output.xml into JSON summaries.
---

# Robot Framework Results
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "SKILL.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_minimal_skill_is_valid(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    fm = lib.get_frontmatter(_write(tmp_path, MINIMAL))
    lib.should_be_valid_frontmatter(fm)  # must not raise


def test_absent_optional_fields_default(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    path = _write(tmp_path, MINIMAL)
    assert lib.get_allowed_tools(path) == []
    assert lib.get_disable_model_invocation(path) is False
    assert lib.get_description(path) == "Parse Robot Framework output.xml into JSON summaries."


def _with_allowed_tools(value: str) -> str:
    """Insert an ``allowed-tools`` line before the closing frontmatter delimiter."""
    return MINIMAL.replace("---\n\n# Robot", f"allowed-tools: {value}\n---\n\n# Robot")


def test_comma_string_allowed_tools_normalizes(tmp_path: Path) -> None:
    # Previously this comma form was (wrongly) rejected; it is now accepted as a
    # compatibility extension and normalized to a list.
    lib = SkillsLibrary()
    path = _write(tmp_path, _with_allowed_tools("Read, Write"))
    lib.should_be_valid_frontmatter(lib.get_frontmatter(path))  # must not raise
    assert lib.get_allowed_tools(path) == ["Read", "Write"]


def test_space_separated_allowed_tools_normalizes(tmp_path: Path) -> None:
    # The Agent Skills spec form: space-separated, with tool-scoping syntax.
    lib = SkillsLibrary()
    path = _write(tmp_path, _with_allowed_tools("Bash(git:*) Bash(jq:*) Read"))
    lib.should_be_valid_frontmatter(lib.get_frontmatter(path))
    assert lib.get_allowed_tools(path) == ["Bash(git:*)", "Bash(jq:*)", "Read"]


def test_scoped_token_with_internal_separator_is_preserved(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    assert lib.get_allowed_tools(_write(tmp_path, _with_allowed_tools("Bash(git add:*)"))) == ["Bash(git add:*)"]
    assert lib.get_allowed_tools(_write(tmp_path, _with_allowed_tools("WebFetch(a.com,b.com)"))) == [
        "WebFetch(a.com,b.com)"
    ]


def test_standalone_validator_accepts_string_form(tmp_path: Path) -> None:
    # `Should Be Valid Frontmatter` takes a caller-built dict directly (not via
    # `Get Frontmatter`), so the validator must normalize the string forms itself.
    lib = SkillsLibrary()
    fm = {"name": "x", "description": "y", "allowed-tools": "Read, Grep"}
    lib.should_be_valid_frontmatter(fm)  # must not raise


def test_genuinely_mistyped_allowed_tools_still_raises(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    body = _with_allowed_tools("5")  # YAML int, not a string or list
    with pytest.raises(InvalidConfigError):
        lib.should_be_valid_frontmatter(lib.get_frontmatter(_write(tmp_path, body)))
    # A list containing a non-string element also still raises.
    with pytest.raises(InvalidConfigError):
        lib.should_be_valid_frontmatter({"name": "x", "description": "y", "allowed-tools": ["Read", 5]})
