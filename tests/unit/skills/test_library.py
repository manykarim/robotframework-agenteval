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

"""Unit tests for `src/AgentEval/skills/library.py` (Story 2.1).

Covers AC-2.1.1 through AC-2.1.8: happy-path keyword behavior, every
error path through `_parser.py` + `InvalidSkillFrontmatterError`, the
FR59-exact `__str__` format, the Tier-1 latency budget per NFR-PERF-02,
and the Story 1b.6 conventions invariants (tier annotation + badge in
docstring) on every keyword.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import (
    AgentEvalError,
    AgentEvalIntegrityError,
    InvalidSkillFrontmatterError,
)
from AgentEval.skills._parser import (
    REQUIRED_FIELDS,
    parse_frontmatter,
    validate_frontmatter_structure,
)
from AgentEval.skills.library import SkillsLibrary

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "skills"
VALID_FIXTURE = FIXTURES_DIR / "example-valid.md"
MALFORMED_YAML_FIXTURE = FIXTURES_DIR / "example-malformed-yaml.md"
MISSING_FIELDS_FIXTURE = FIXTURES_DIR / "example-missing-fields.md"


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


# --------------------------------------------------------------------------- #
# AC-2.1.1: `Skill.Get Frontmatter` happy path
# --------------------------------------------------------------------------- #


def test_get_frontmatter_returns_dict_with_all_fields(lib: SkillsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    assert isinstance(frontmatter, dict)
    for field in REQUIRED_FIELDS:
        assert field in frontmatter, f"missing required field {field!r}"


def test_get_frontmatter_accepts_str_path(lib: SkillsLibrary) -> None:
    frontmatter = lib.get_frontmatter(str(VALID_FIXTURE))
    assert frontmatter["name"] == "example-valid-skill"


def test_get_frontmatter_accepts_path_object(lib: SkillsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    assert frontmatter["name"] == "example-valid-skill"


def test_get_frontmatter_field_types_match_contract(lib: SkillsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    assert isinstance(frontmatter["name"], str)
    assert isinstance(frontmatter["description"], str)
    assert isinstance(frontmatter["allowed-tools"], list)
    assert all(isinstance(tool, str) for tool in frontmatter["allowed-tools"])
    assert isinstance(frontmatter["disable-model-invocation"], bool)


# --------------------------------------------------------------------------- #
# AC-2.1.2: `Skill.Get Description` / `Get Allowed Tools` / `Get Disable Model Invocation`
# --------------------------------------------------------------------------- #


def test_get_description_returns_string(lib: SkillsLibrary) -> None:
    description = lib.get_description(VALID_FIXTURE)
    assert isinstance(description, str)
    assert description.startswith("A canonical valid skill")


def test_get_allowed_tools_returns_list_of_strings(lib: SkillsLibrary) -> None:
    tools = lib.get_allowed_tools(VALID_FIXTURE)
    assert isinstance(tools, list)
    assert tools == ["read_file", "write_file", "search_database", "run_tests"]
    assert all(isinstance(tool, str) for tool in tools)


def test_get_disable_model_invocation_returns_bool(lib: SkillsLibrary) -> None:
    value = lib.get_disable_model_invocation(VALID_FIXTURE)
    assert isinstance(value, bool)
    assert value is False


# --------------------------------------------------------------------------- #
# AC-2.1.3: `InvalidSkillFrontmatterError` per FR59 format
# --------------------------------------------------------------------------- #


def test_invalid_skill_frontmatter_error_inherits_integrity() -> None:
    assert issubclass(InvalidSkillFrontmatterError, AgentEvalIntegrityError)
    assert issubclass(InvalidSkillFrontmatterError, AgentEvalError)


def test_invalid_skill_frontmatter_error_code_constant() -> None:
    assert InvalidSkillFrontmatterError.error_code == "INVALID_SKILL_FRONTMATTER"


def test_invalid_skill_frontmatter_error_structured_attrs() -> None:
    exc = InvalidSkillFrontmatterError(
        "boom",
        file_path="foo/bar.md",
        line_number=7,
        field_name="allowed-tools",
        fix_suggestion="use a list",
    )
    assert exc.file_path == "foo/bar.md"
    assert exc.line_number == 7
    assert exc.field_name == "allowed-tools"
    assert exc.fix_suggestion == "use a list"


def test_invalid_skill_frontmatter_error_str_fr59_format() -> None:
    exc = InvalidSkillFrontmatterError(
        "broken YAML",
        file_path="x.md",
        line_number=3,
        field_name="allowed-tools",
        fix_suggestion="quote the value",
    )
    rendered = str(exc)
    assert rendered.startswith("INVALID_SKILL_FRONTMATTER: broken YAML")
    assert "File: x.md" in rendered
    assert "Line: 3" in rendered
    assert "Field: allowed-tools" in rendered
    assert "Fix: quote the value" in rendered


def test_invalid_skill_frontmatter_error_str_handles_none_fields() -> None:
    exc = InvalidSkillFrontmatterError("msg")
    rendered = str(exc)
    assert "File: N/A" in rendered
    assert "Line: N/A" in rendered
    assert "Field: N/A" in rendered
    assert "Fix: N/A" in rendered


def test_malformed_yaml_raises_with_line_number(lib: SkillsLibrary) -> None:
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(MALFORMED_YAML_FIXTURE)
    exc = exc_info.value
    assert exc.error_code == "INVALID_SKILL_FRONTMATTER"
    assert exc.file_path is not None
    assert "example-malformed-yaml" in exc.file_path
    assert exc.line_number is not None
    assert exc.line_number > 1
    assert exc.fix_suggestion is not None


def test_file_not_found_raises_with_path(lib: SkillsLibrary, tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(missing)
    exc = exc_info.value
    assert exc.file_path == str(missing)
    assert exc.fix_suggestion is not None


def test_non_md_extension_raises(lib: SkillsLibrary, tmp_path: Path) -> None:
    not_md = tmp_path / "skill.txt"
    not_md.write_text("---\nname: x\n---\n")
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(not_md)
    assert ".txt" in str(exc_info.value)


def test_missing_leading_delimiter_raises(lib: SkillsLibrary, tmp_path: Path) -> None:
    no_open = tmp_path / "no_open.md"
    no_open.write_text("name: x\ndescription: y\n")
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(no_open)
    assert exc_info.value.line_number == 1


def test_missing_closing_delimiter_raises(lib: SkillsLibrary, tmp_path: Path) -> None:
    no_close = tmp_path / "no_close.md"
    no_close.write_text("---\nname: x\ndescription: y\n")
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(no_close)
    assert exc_info.value.line_number is not None


def test_non_mapping_frontmatter_raises(lib: SkillsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "list_frontmatter.md"
    skill.write_text("---\n- name\n- description\n---\n")
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(skill)
    assert "mapping" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# AC-2.1.4: `Should Be Valid Frontmatter` validation keyword
# --------------------------------------------------------------------------- #


def test_should_be_valid_frontmatter_accepts_complete_dict(lib: SkillsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    # Should NOT raise; returns None.
    result = lib.should_be_valid_frontmatter(frontmatter)
    assert result is None


def test_should_be_valid_frontmatter_rejects_missing_name(lib: SkillsLibrary) -> None:
    bad: dict[str, Any] = {
        "description": "ok",
        "allowed-tools": [],
        "disable-model-invocation": False,
    }
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    assert exc_info.value.field_name == "name"


def test_should_be_valid_frontmatter_lists_all_missing_fields(lib: SkillsLibrary) -> None:
    bad: dict[str, Any] = {"description": "ok"}
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    field_name = exc_info.value.field_name or ""
    assert "name" in field_name
    assert "allowed-tools" in field_name
    assert "disable-model-invocation" in field_name


def test_should_be_valid_frontmatter_rejects_non_list_allowed_tools(
    lib: SkillsLibrary,
) -> None:
    bad: dict[str, Any] = {
        "name": "x",
        "description": "y",
        "allowed-tools": "not_a_list",
        "disable-model-invocation": False,
    }
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    assert exc_info.value.field_name == "allowed-tools"


def test_should_be_valid_frontmatter_rejects_non_bool_disable(lib: SkillsLibrary) -> None:
    bad: dict[str, Any] = {
        "name": "x",
        "description": "y",
        "allowed-tools": [],
        "disable-model-invocation": "false",
    }
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    assert exc_info.value.field_name == "disable-model-invocation"


def test_should_be_valid_frontmatter_rejects_empty_name(lib: SkillsLibrary) -> None:
    bad: dict[str, Any] = {
        "name": "",
        "description": "y",
        "allowed-tools": [],
        "disable-model-invocation": False,
    }
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    assert exc_info.value.field_name == "name"


def test_should_be_valid_frontmatter_rejects_non_string_in_allowed_tools(
    lib: SkillsLibrary,
) -> None:
    bad: dict[str, Any] = {
        "name": "x",
        "description": "y",
        "allowed-tools": ["ok", 42],
        "disable-model-invocation": False,
    }
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.should_be_valid_frontmatter(bad)
    assert exc_info.value.field_name == "allowed-tools"


def test_get_description_raises_on_missing_fields_fixture(lib: SkillsLibrary) -> None:
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_description(MISSING_FIELDS_FIXTURE)
    assert exc_info.value.field_name == "name"


# --------------------------------------------------------------------------- #
# AC-2.1.6: Story 1b.6 conventions invariants applied to every keyword
# --------------------------------------------------------------------------- #


KEYWORD_METHODS = [
    "get_frontmatter",
    "get_description",
    "get_allowed_tools",
    "get_disable_model_invocation",
    "should_be_valid_frontmatter",
]


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_every_keyword_has_tier_one_annotation(method_name: str) -> None:
    func = getattr(SkillsLibrary, method_name)
    assert get_keyword_tier(func) == 1


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_every_keyword_docstring_contains_tier_one_badge(method_name: str) -> None:
    func = getattr(SkillsLibrary, method_name)
    assert func.__doc__ is not None
    assert tier_badge(1) in func.__doc__


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_every_keyword_has_robot_marker(method_name: str) -> None:
    func = getattr(SkillsLibrary, method_name)
    # `@keyword` from robot.api.deco sets `robot_name` (canonical marker).
    assert hasattr(func, "robot_name")


# --------------------------------------------------------------------------- #
# AC-2.1.8: NFR-PERF-02 Tier-1 latency budget
# --------------------------------------------------------------------------- #


def test_get_frontmatter_meets_nfr_perf_02_latency(lib: SkillsLibrary) -> None:
    """Median latency ≤ 50 ms on the 5 KB-class reference fixture per NFR-PERF-02.

    Sampling 11 calls + asserting on the median (not the max) avoids
    flakiness from per-run noise (GC pauses, system load); the budget
    in the PRD is a median statement, not a worst-case statement.
    """
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.get_frontmatter(VALID_FIXTURE)
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 50ms budget"


# --------------------------------------------------------------------------- #
# Parser-level helper coverage (defense in depth on the public helpers)
# --------------------------------------------------------------------------- #


def test_parse_frontmatter_module_level_function_matches_keyword() -> None:
    direct = parse_frontmatter(VALID_FIXTURE)
    via_keyword = SkillsLibrary().get_frontmatter(VALID_FIXTURE)
    assert direct == via_keyword


def test_validate_frontmatter_structure_returns_none_on_valid() -> None:
    valid = parse_frontmatter(VALID_FIXTURE)
    assert validate_frontmatter_structure(valid) is None


# --------------------------------------------------------------------------- #
# Code-review fixes (Story 2.1 cross-LLM review 2026-05-19)
# --------------------------------------------------------------------------- #


def test_parse_frontmatter_handles_utf8_bom(lib: SkillsLibrary, tmp_path: Path) -> None:
    """BOM-prefixed `.md` files (common on Windows) must parse cleanly.

    Code-review B6/E3 fix: prior `read_text(encoding="utf-8")` left the BOM
    in `lines[0]` so `.strip() != "---"` and the parser raised a misleading
    "missing leading delimiter". Now reads with `utf-8-sig`.
    """
    bom_file = tmp_path / "bom.md"
    bom_file.write_bytes(
        b"\xef\xbb\xbf---\n"
        b"name: bom-skill\n"
        b"description: BOM-prefixed.\n"
        b"allowed-tools: []\n"
        b"disable-model-invocation: false\n"
        b"---\n"
        b"body\n"
    )
    frontmatter = lib.get_frontmatter(bom_file)
    assert frontmatter["name"] == "bom-skill"


def test_indented_dashes_inside_block_scalar_are_not_delimiters(lib: SkillsLibrary, tmp_path: Path) -> None:
    """An indented `---` inside a YAML block scalar must NOT close the frontmatter.

    Code-review E2 fix: prior `.strip() == "---"` check matched any line whose
    trimmed content was `---`, silently truncating frontmatter that contained
    `description: |\\n  ---\\n...`. Now uses `.rstrip() == "---"` so leading
    whitespace prevents a match (delimiter must be at column 0).
    """
    skill = tmp_path / "block_scalar.md"
    skill.write_text(
        "---\n"
        "name: block-scalar-skill\n"
        "description: |\n"
        "  multi-line\n"
        "  ---\n"
        "  more text\n"
        "allowed-tools: []\n"
        "disable-model-invocation: false\n"
        "---\n"
        "body\n"
    )
    # All 4 required fields must be reachable (parser must NOT have
    # truncated the YAML block at the indented `---`).
    frontmatter = lib.get_frontmatter(skill)
    for field in REQUIRED_FIELDS:
        assert field in frontmatter, f"indented `---` truncated frontmatter, lost {field!r}"
    assert "multi-line" in frontmatter["description"]


def test_malformed_yaml_error_summary_is_single_line(lib: SkillsLibrary) -> None:
    """FR59 requires the `__str__` header to be a one-line summary.

    Code-review C1 fix: `yaml.YAMLError.__str__` is multi-line (problem +
    excerpt + caret); prior shape spilled the whole render into the
    InvalidSkillFrontmatterError message, breaking the FR59 single-summary
    contract. Now uses `exc.problem` or `.splitlines()[0]`.
    """
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(MALFORMED_YAML_FIXTURE)
    message = Exception.__str__(exc_info.value)
    # The Exception.__str__ value is the one-line summary (the multi-line
    # FR59 layout is built by __str__ on top of this).
    assert "\n" not in message, f"YAML error message spilled to multiple lines: {message!r}"


def test_rendered_str_first_line_matches_fr59_header(lib: SkillsLibrary) -> None:
    """The first line of `str(exc)` MUST be `INVALID_SKILL_FRONTMATTER: <summary>`.

    Code-review C1 follow-up: the contract at
    `docs/contracts/error-class-hierarchy.md` L96-104 requires the
    header line then `File:` / `Line:` / `Field:` / `Fix:`. Pre-fix,
    a multi-line YAML message pushed `File:` to line 5+.
    """
    with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
        lib.get_frontmatter(MALFORMED_YAML_FIXTURE)
    rendered = str(exc_info.value)
    lines = rendered.splitlines()
    assert lines[0].startswith("INVALID_SKILL_FRONTMATTER: ")
    assert lines[1].startswith("  File: ")
    assert lines[2].startswith("  Line: ")
    assert lines[3].startswith("  Field: ")
    assert lines[4].startswith("  Fix: ")
    assert len(lines) == 5, f"expected 5 lines; got {len(lines)}: {rendered!r}"


def test_agenteval_does_not_expose_skills_library_via_dynamic_core() -> None:
    """`SkillsLibrary` is EXCLUDED from top-level DynamicCore composition.

    Story 2.2 code-review HIGH-1 fix (Edge-cases + Blind): the
    `SkillsLibrary.Get Frontmatter` keyword collided with
    `SubagentsLibrary.Get Frontmatter` under DynamicCore's last-wins
    flattening, silently shadowing Story 2.1's validation surface.
    Resolution per the PRD-documented canonical user pattern (PRD FR1
    uses `Skill.Get Frontmatter` syntax → user pattern is `Library X
    WITH NAME prefix`): `SkillsLibrary` is excluded from `_SUB_LIBRARIES`.
    Users access via `Library AgentEval.skills.library.SkillsLibrary
    WITH NAME Skill` (which the Story 2.1 RF integration test exercises).
    """
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    assert "SkillsLibrary" not in library._loaded_components
    # Skill keywords are NOT in the top-level keyword registry; they're
    # reachable only via the standalone-import path.
    keyword_names = library.get_keyword_names()
    assert "Get Frontmatter" not in keyword_names


def test_skills_library_callable_standalone() -> None:
    """Sanity check: importing `SkillsLibrary` standalone still works (no DynamicCore needed)."""
    standalone = SkillsLibrary()
    frontmatter = standalone.get_frontmatter(VALID_FIXTURE)
    assert frontmatter["name"] == "example-valid-skill"


def test_get_frontmatter_does_not_validate_required_fields(lib: SkillsLibrary) -> None:
    """`Get Frontmatter` parses YAML but does NOT enforce the required-fields contract.

    Code-review B3 fix: clarified in the docstring that `Get Frontmatter`
    is YAML-structural-only; field validation lives in the sibling
    getters + `Should Be Valid Frontmatter`. This test pins the
    intentional asymmetry so future code-review feedback doesn't
    re-flag it as a bug.
    """
    frontmatter = lib.get_frontmatter(MISSING_FIELDS_FIXTURE)
    # Parser succeeds + returns partial dict; validation is the caller's job.
    assert isinstance(frontmatter, dict)
    assert "name" not in frontmatter  # MISSING_FIELDS_FIXTURE omits `name`
