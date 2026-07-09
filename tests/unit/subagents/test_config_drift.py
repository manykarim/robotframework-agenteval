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

"""Unit tests for the parser `skills` type-check + config-drift keywords (task 6.6).

Covers every spec scenario for the optional-`skills` parser check,
`Subagent.Should Declare Skills`, and `Subagent.Tools Should Be Subset Of`,
including the `InvalidSubagentDefinitionError`-vs-`SubagentConfigDriftError`
split.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import InvalidSubagentDefinitionError, SubagentConfigDriftError
from AgentEval.subagents.library import SubagentsLibrary


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


def _write(tmp_path: Path, body: str, name: str = "sub.md") -> Path:
    p = tmp_path / name
    p.write_text(body)
    return p


# --------------------------------------------------------------------------- #
# Parser `skills` field type check                                            #
# --------------------------------------------------------------------------- #


def test_valid_skills_list_returned(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills:\n  - pdf-tools\n  - web-search\n---\n")
    fm = lib.get_frontmatter(p)
    assert fm["skills"] == ["pdf-tools", "web-search"]


def test_bare_string_skills_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills: pdf-tools\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(p)
    assert exc_info.value.field_name == "skills"


def test_skills_list_with_non_string_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills:\n  - ok\n  - 42\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(p)
    assert exc_info.value.field_name == "skills"


def test_absent_skills_field_parses_fine(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\n---\n")
    fm = lib.get_frontmatter(p)
    assert "skills" not in fm


# --------------------------------------------------------------------------- #
# Should Declare Skills                                                        #
# --------------------------------------------------------------------------- #


def test_should_declare_skills_is_tier_1() -> None:
    func = SubagentsLibrary.should_declare_skills
    assert get_keyword_tier(func) == 1
    assert tier_badge(1) in (func.__doc__ or "")


def test_all_required_skills_declared_passes(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills:\n  - pdf-tools\n  - web-search\n  - citations\n---\n")
    lib.should_declare_skills(p, "pdf-tools", "web-search")  # no raise


def test_missing_skill_fails_with_drift(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills:\n  - pdf-tools\n---\n")
    with pytest.raises(SubagentConfigDriftError) as exc_info:
        lib.should_declare_skills(p, "pdf-tools", "web-search")
    exc = exc_info.value
    assert "web-search" in exc.offending
    assert exc.fix_suggestion
    assert "preload" in exc.fix_suggestion.lower() or "inherit" in exc.fix_suggestion.lower()


def test_absent_skills_field_fails_loud(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\n---\n")
    with pytest.raises(SubagentConfigDriftError) as exc_info:
        lib.should_declare_skills(p, "pdf-tools")
    assert "do not inherit" in str(exc_info.value).lower()


def test_unparseable_file_propagates_definition_error(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "no frontmatter here")
    with pytest.raises(InvalidSubagentDefinitionError):
        lib.should_declare_skills(p, "pdf-tools")


def test_no_expected_skills_raises_value_error(lib: SubagentsLibrary, tmp_path: Path) -> None:
    # Codex LOW: calling with zero expected skill names must fail loud rather
    # than vacuously certify a non-empty `skills:` declaration.
    p = _write(tmp_path, "---\nname: r\ndescription: d\nskills:\n  - pdf-tools\n---\n")
    with pytest.raises(ValueError, match="one or more expected skill names"):
        lib.should_declare_skills(p)


# --------------------------------------------------------------------------- #
# Tools Should Be Subset Of                                                    #
# --------------------------------------------------------------------------- #


def test_tools_should_be_subset_of_is_tier_1() -> None:
    func = SubagentsLibrary.tools_should_be_subset_of
    assert get_keyword_tier(func) == 1
    assert tier_badge(1) in (func.__doc__ or "")


def test_declared_tools_within_allowlist_passes(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\ntools:\n  - Read\n  - Grep\n---\n")
    lib.tools_should_be_subset_of(p, "Read", "Grep", "Bash")  # no raise


def test_tool_outside_allowlist_fails_naming_offender(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\ntools:\n  - Read\n  - WebFetch\n---\n")
    with pytest.raises(SubagentConfigDriftError) as exc_info:
        lib.tools_should_be_subset_of(p, "Read", "Grep", "Bash")
    assert "WebFetch" in exc_info.value.offending


def test_absent_tools_field_fails_loud(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "---\nname: r\ndescription: d\n---\n")
    with pytest.raises(SubagentConfigDriftError) as exc_info:
        lib.tools_should_be_subset_of(p, "Read", "Grep")
    assert "inherit" in str(exc_info.value).lower()


def test_tools_unparseable_file_propagates_definition_error(lib: SubagentsLibrary, tmp_path: Path) -> None:
    p = _write(tmp_path, "not a subagent file")
    with pytest.raises(InvalidSubagentDefinitionError):
        lib.tools_should_be_subset_of(p, "Read")


# --------------------------------------------------------------------------- #
# Error-class semantics                                                        #
# --------------------------------------------------------------------------- #


def test_config_drift_error_str_layout() -> None:
    exc = SubagentConfigDriftError(
        "drift",
        file_path="a.md",
        offending=["x", "y"],
        fix_suggestion="fix it",
    )
    rendered = str(exc)
    assert rendered.splitlines()[0] == "SUBAGENT_CONFIG_DRIFT: drift"
    assert "File: a.md" in rendered
    assert "Offending: x, y" in rendered
    assert "Fix: fix it" in rendered


def test_config_drift_error_is_integrity_error() -> None:
    from AgentEval.errors import AgentEvalIntegrityError

    assert issubclass(SubagentConfigDriftError, AgentEvalIntegrityError)
