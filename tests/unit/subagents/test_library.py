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

"""Unit tests for `src/AgentEval/subagents/library.py` (Story 2.2).

Covers AC-2.2.1 through AC-2.2.9: happy-path keyword behavior, error
paths through `_parser.py` + `InvalidSubagentDefinitionError`, the
FR59 `__str__` shape, the Tier-1 latency budget per NFR-PERF-02 + the
Story 1b.6 conventions invariants (tier annotation + badge in
docstring).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import (
    AgentEvalError,
    AgentEvalIntegrityError,
    InvalidSubagentDefinitionError,
)
from AgentEval.subagents._parser import REQUIRED_FIELDS, parse_subagent_frontmatter
from AgentEval.subagents.library import SubagentsLibrary

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "subagents"
VALID_FIXTURE = FIXTURES_DIR / "example-valid.md"
MALFORMED_YAML_FIXTURE = FIXTURES_DIR / "example-malformed-yaml.md"
MISSING_FIELDS_FIXTURE = FIXTURES_DIR / "example-missing-fields.md"


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


def test_get_frontmatter_returns_dict_with_required_fields(lib: SubagentsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    assert isinstance(frontmatter, dict)
    for field in REQUIRED_FIELDS:
        assert field in frontmatter


def test_get_frontmatter_includes_optional_fields_when_present(lib: SubagentsLibrary) -> None:
    frontmatter = lib.get_frontmatter(VALID_FIXTURE)
    assert frontmatter["tools"] == ["read_file", "run_tests"]
    assert frontmatter["model"] == "claude-sonnet-4-6"


def test_get_frontmatter_accepts_str_or_path(lib: SubagentsLibrary) -> None:
    via_str = lib.get_frontmatter(str(VALID_FIXTURE))
    via_path = lib.get_frontmatter(VALID_FIXTURE)
    assert via_str == via_path


def test_invalid_subagent_definition_error_inherits_integrity() -> None:
    assert issubclass(InvalidSubagentDefinitionError, AgentEvalIntegrityError)
    assert issubclass(InvalidSubagentDefinitionError, AgentEvalError)


def test_invalid_subagent_definition_error_code() -> None:
    assert InvalidSubagentDefinitionError.error_code == "INVALID_SUBAGENT_DEFINITION"


def test_malformed_yaml_raises(lib: SubagentsLibrary) -> None:
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(MALFORMED_YAML_FIXTURE)
    exc = exc_info.value
    assert exc.error_code == "INVALID_SUBAGENT_DEFINITION"
    assert exc.line_number is not None
    assert exc.line_number > 1


def test_missing_required_field_raises(lib: SubagentsLibrary) -> None:
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(MISSING_FIELDS_FIXTURE)
    assert exc_info.value.field_name == "name"


def test_optional_tools_wrong_type_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "subagent.md"
    skill.write_text("---\nname: x\ndescription: y\ntools: not_a_list\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert exc_info.value.field_name == "tools"


def test_optional_model_wrong_type_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "subagent.md"
    skill.write_text("---\nname: x\ndescription: y\nmodel: 42\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert exc_info.value.field_name == "model"


def test_file_not_found_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    with pytest.raises(InvalidSubagentDefinitionError):
        lib.get_frontmatter(tmp_path / "nope.md")


def test_non_md_extension_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    txt = tmp_path / "subagent.txt"
    txt.write_text("---\nname: x\ndescription: y\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError):
        lib.get_frontmatter(txt)


def test_bom_prefixed_file_parses(lib: SubagentsLibrary, tmp_path: Path) -> None:
    bom = tmp_path / "bom.md"
    bom.write_bytes(b"\xef\xbb\xbf---\nname: bom-subagent\ndescription: BOM-prefixed.\n---\n")
    frontmatter = lib.get_frontmatter(bom)
    assert frontmatter["name"] == "bom-subagent"


def test_indented_dashes_in_block_scalar_not_delimiters(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "bs.md"
    skill.write_text("---\nname: bs\ndescription: |\n  multi\n  ---\n  more\n---\nbody\n")
    frontmatter = lib.get_frontmatter(skill)
    assert "multi" in frontmatter["description"]


def test_get_frontmatter_meets_nfr_perf_02(lib: SubagentsLibrary) -> None:
    """Median latency ≤ 50 ms on the reference fixture per NFR-PERF-02."""
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.get_frontmatter(VALID_FIXTURE)
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 budget"


def test_keyword_has_tier_1_annotation() -> None:
    assert get_keyword_tier(SubagentsLibrary.get_frontmatter) == 1


def test_keyword_docstring_has_tier_1_badge() -> None:
    doc = SubagentsLibrary.get_frontmatter.__doc__ or ""
    assert tier_badge(1) in doc


def test_keyword_has_robot_marker() -> None:
    assert hasattr(SubagentsLibrary.get_frontmatter, "robot_name")


def test_invalid_subagent_str_fr59_layout() -> None:
    exc = InvalidSubagentDefinitionError(
        "broken",
        file_path="x.md",
        line_number=3,
        field_name="name",
        fix_suggestion="fix it",
    )
    rendered = str(exc)
    lines = rendered.splitlines()
    assert lines[0] == "INVALID_SUBAGENT_DEFINITION: broken"
    assert "File: x.md" in lines[1]
    assert "Line: 3" in lines[2]
    assert "Field: name" in lines[3]
    assert "Fix: fix it" in lines[4]


def test_parse_subagent_frontmatter_module_level_matches_keyword() -> None:
    direct = parse_subagent_frontmatter(VALID_FIXTURE)
    via_keyword = SubagentsLibrary().get_frontmatter(VALID_FIXTURE)
    # `get_frontmatter` runs validation but returns the same parsed dict.
    assert direct == via_keyword


def test_agenteval_does_not_expose_subagents_library_via_dynamic_core() -> None:
    """`SubagentsLibrary` is EXCLUDED from top-level DynamicCore composition.

    Story 2.2 code-review HIGH-1 fix: `Get Frontmatter` collides with
    `SkillsLibrary`. Resolution: users access via `Library AgentEval.subagents.library.SubagentsLibrary
    WITH NAME Subagent`. The collision-detector in `AgentEval._build_components`
    enforces this exclusion at import time so future stories cannot
    silently re-introduce the collision.
    """
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    assert "SubagentsLibrary" not in library._loaded_components


def test_subagents_library_callable_standalone() -> None:
    standalone = SubagentsLibrary()
    frontmatter = standalone.get_frontmatter(VALID_FIXTURE)
    assert frontmatter["name"] == "example-valid-subagent"


def test_non_string_name_raises_typed_error(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "s.md"
    skill.write_text("---\nname: 42\ndescription: y\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert exc_info.value.field_name == "name"


def test_empty_string_description_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "s.md"
    skill.write_text('---\nname: x\ndescription: ""\n---\n')
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert exc_info.value.field_name == "description"


def test_non_mapping_frontmatter_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "s.md"
    skill.write_text("---\n- name\n- description\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert "mapping" in str(exc_info.value)


def test_optional_fields_absent_succeeds(lib: SubagentsLibrary, tmp_path: Path) -> None:
    """Both `tools` + `model` are optional; absence is valid."""
    skill = tmp_path / "minimal.md"
    skill.write_text("---\nname: minimal\ndescription: bare bones\n---\n")
    frontmatter = lib.get_frontmatter(skill)
    assert frontmatter["name"] == "minimal"
    assert "tools" not in frontmatter
    assert "model" not in frontmatter


def test_non_string_in_tools_list_raises(lib: SubagentsLibrary, tmp_path: Path) -> None:
    skill = tmp_path / "s.md"
    skill.write_text("---\nname: x\ndescription: y\ntools:\n  - ok\n  - 42\n---\n")
    with pytest.raises(InvalidSubagentDefinitionError) as exc_info:
        lib.get_frontmatter(skill)
    assert exc_info.value.field_name == "tools"


def test_inherits_shared_fr59_layout_from_intermediate_base(lib: SubagentsLibrary) -> None:
    """Story 2.2 refactor: 3 setup-failure leaves share `_FR59Tier1SetupFailureError`."""
    from AgentEval.errors import _FR59Tier1SetupFailureError

    assert issubclass(InvalidSubagentDefinitionError, _FR59Tier1SetupFailureError)


def test_error_str_handles_none_fields() -> None:
    rendered = str(InvalidSubagentDefinitionError("msg"))
    assert "File: N/A" in rendered
    assert "Line: N/A" in rendered
    assert "Field: N/A" in rendered
    assert "Fix: N/A" in rendered


def test_structured_attrs_preserved() -> None:
    exc = InvalidSubagentDefinitionError(
        "boom",
        file_path="x.md",
        line_number=7,
        field_name="tools",
        fix_suggestion="use list",
    )
    assert exc.file_path == "x.md"
    assert exc.line_number == 7
    assert exc.field_name == "tools"
    assert exc.fix_suggestion == "use list"
