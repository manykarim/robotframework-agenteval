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

"""Epic 2 static-inspection conformance tests (Story 2.4).

Discovers fixtures under `tests/conformance/fixtures/static_inspection/`,
validates each fixture against `tests/conformance/static-inspection-fixture-schema.json`,
parametrizes per fixture, and invokes the named Tier-1 keyword against
the declared input file. Happy-path fixtures assert the returned shape;
error-path fixtures assert the typed leaf raises with the expected
`error_code` (and optional JSON Pointer substring on `field_name`).

This conformance test runs in the PR-gating `ci.yml` via the existing
`pytest tests/conformance -q` step. The Story 1b.5 adapter-fixture
harness stays adapter-focused; this is the parallel static-inspection
fixture surface ratified by Story 2.4 pre-create-story drift-check D-B
2026-05-19.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from AgentEval.errors import AgentEvalIntegrityError
from AgentEval.hooks.library import HooksLibrary
from AgentEval.mcp.library import MCPLibrary
from AgentEval.skills.library import SkillsLibrary
from AgentEval.subagents.library import SubagentsLibrary

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "conformance" / "fixtures" / "static_inspection"
SCHEMA_PATH = REPO_ROOT / "tests" / "conformance" / "static-inspection-fixture-schema.json"

_SKILLS = SkillsLibrary()
_SUBAGENTS = SubagentsLibrary()
_HOOKS = HooksLibrary()
_MCP = MCPLibrary()


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_fixtures() -> list[dict[str, Any]]:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    fixtures: list[dict[str, Any]] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(data)
        data["_fixture_path"] = str(path.relative_to(REPO_ROOT))
        fixtures.append(data)
    return fixtures


_FIXTURES = _load_fixtures()


def _invoke_keyword(fixture: dict[str, Any]) -> Any:
    """Dispatch to the named keyword + return its result.

    `Should Be Valid Frontmatter` is special: it takes a frontmatter
    dict, not a path. For conformance purposes, we parse the input file
    via `Skills.get_frontmatter` first, then pass the dict to
    `should_be_valid_frontmatter`.
    """
    kw = fixture["keyword_name"]
    path = REPO_ROOT / fixture["input_file_path"]
    kwargs = fixture.get("kwargs", {})

    if kw == "Skill.Get Frontmatter":
        return _SKILLS.get_frontmatter(path)
    if kw == "Skill.Get Description":
        return _SKILLS.get_description(path)
    if kw == "Skill.Get Allowed Tools":
        return _SKILLS.get_allowed_tools(path)
    if kw == "Skill.Get Disable Model Invocation":
        return _SKILLS.get_disable_model_invocation(path)
    if kw == "Should Be Valid Frontmatter":
        # For error-path with missing fields, parse_frontmatter still
        # succeeds (it doesn't validate); only `Should Be Valid Frontmatter`
        # raises. Use the parser-level helper to avoid the
        # `Skills.get_frontmatter` no-validate contract.
        from AgentEval.skills._parser import parse_frontmatter

        frontmatter = parse_frontmatter(path)
        return _SKILLS.should_be_valid_frontmatter(frontmatter)
    if kw == "Subagent.Get Frontmatter":
        return _SUBAGENTS.get_frontmatter(path)
    if kw == "Hook.Get Config":
        return _HOOKS.get_config(path)
    if kw == "MCP.Get Server Config":
        return _MCP.get_server_config(path)
    if kw == "MCP.Get Tool Schema":
        return _MCP.get_tool_schema(path, **kwargs)
    if kw == "MCP.Validate Tool Schema":
        return _MCP.validate_tool_schema(path, **kwargs)
    raise AssertionError(f"Unknown keyword in fixture: {kw!r}")


def _assert_result_shape(result: Any, shape: dict[str, Any]) -> None:
    """Verify the keyword's return value matches `expected_result_shape`."""
    expected_type = shape.get("type")
    type_map = {
        "dict": dict,
        "list": list,
        "str": str,
        "bool": bool,
        "int": int,
        "float": float,
        "none": type(None),
    }
    if expected_type is not None:
        py_type = type_map[expected_type]
        # Special-case: `bool` is `int`-subclass; check exact type for bool.
        if expected_type == "bool":
            assert isinstance(result, bool), f"expected bool, got {type(result).__name__}"
        elif expected_type == "int":
            assert isinstance(result, int) and not isinstance(result, bool)
        elif expected_type == "none":
            assert result is None, f"expected None, got {result!r}"
        else:
            assert isinstance(result, py_type), f"expected {expected_type}, got {type(result).__name__}"

    contains_keys = shape.get("contains_keys")
    if contains_keys is not None:
        assert isinstance(result, dict), "contains_keys requires dict result"
        for key in contains_keys:
            assert key in result, f"expected key {key!r} in result; got keys {list(result.keys())!r}"

    equals = shape.get("equals")
    if equals is not None:
        assert result == equals, f"expected {equals!r}, got {result!r}"


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f["fixture_id"])
def test_static_inspection_fixture(fixture: dict[str, Any]) -> None:
    if fixture["path_type"] == "happy":
        result = _invoke_keyword(fixture)
        _assert_result_shape(result, fixture["expected_result_shape"])
    else:
        with pytest.raises(AgentEvalIntegrityError) as exc_info:
            _invoke_keyword(fixture)
        assert exc_info.value.error_code == fixture["expected_error_code"], (
            f"fixture {fixture['fixture_id']!r}: expected error_code "
            f"{fixture['expected_error_code']!r}, got {exc_info.value.error_code!r}"
        )
        substring = fixture.get("expected_field_name_substring")
        if substring is not None:
            field_name = getattr(exc_info.value, "field_name", None) or ""
            assert substring in field_name, (
                f"fixture {fixture['fixture_id']!r}: expected field_name substring "
                f"{substring!r}; got field_name {field_name!r}"
            )


def test_fixture_coverage_exhausts_keyword_set() -> None:
    """Every one of the 10 Epic-2 Tier-1 keywords has ≥1 happy + ≥1 error fixture."""
    expected_keywords = {
        "Skill.Get Frontmatter",
        "Skill.Get Description",
        "Skill.Get Allowed Tools",
        "Skill.Get Disable Model Invocation",
        "Should Be Valid Frontmatter",
        "Subagent.Get Frontmatter",
        "Hook.Get Config",
        "MCP.Get Server Config",
        "MCP.Get Tool Schema",
        "MCP.Validate Tool Schema",
    }
    happy: set[str] = set()
    error: set[str] = set()
    for fixture in _FIXTURES:
        target = happy if fixture["path_type"] == "happy" else error
        target.add(fixture["keyword_name"])
    missing_happy = expected_keywords - happy
    missing_error = expected_keywords - error
    assert not missing_happy, f"keywords without happy-path fixture: {missing_happy!r}"
    assert not missing_error, f"keywords without error-path fixture: {missing_error!r}"


def test_at_least_20_fixtures_shipped() -> None:
    """Story 2.4 AC requires 20+ fixtures (10 keywords × 2 paths)."""
    assert len(_FIXTURES) >= 20, f"expected ≥20 fixtures; found {len(_FIXTURES)}"
