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

"""Unit tests for `src/AgentEval/hooks/library.py` (Story 2.2 + real-format rewrite).

Covers the real nested Claude Code hook schema (matcher groups of typed hook
definitions), the deprecated legacy-flat alias, the normalized plain-event-key
return shape, per-type validation, inline-skill-frontmatter detection, every
error path through `_parser.py` + `InvalidHookConfigError`, RFC 6901 JSON
Pointer in `field_name`, the Tier-1 latency budget per NFR-PERF-02, and the
Story 1b.6 conventions invariants. See
`openspec/changes/accept-real-claude-hook-config/specs/hook-config-parsing/spec.md`.
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import (
    AgentEvalError,
    AgentEvalIntegrityError,
    InvalidHookConfigError,
)
from AgentEval.hooks._parser import SUPPORTED_EVENTS, _build_pointer
from AgentEval.hooks.library import HooksLibrary

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "hooks"
VALID_FIXTURE = FIXTURES_DIR / "settings-valid.json"
MALFORMED_JSON_FIXTURE = FIXTURES_DIR / "settings-malformed-json.json"
MISSING_COMMAND_FIXTURE = FIXTURES_DIR / "settings-missing-command.json"
LEGACY_FLAT_FIXTURE = FIXTURES_DIR / "settings-legacy-flat.json"
REAL_WORLD_FIXTURE = FIXTURES_DIR / "settings-real-world.json"


@pytest.fixture
def lib() -> HooksLibrary:
    return HooksLibrary()


def _write(tmp_path: Path, name: str, payload: object) -> Path:
    f = tmp_path / name
    f.write_text(json.dumps(payload))
    return f


# --------------------------------------------------------------------------- #
# Real-format happy path — plain event keys + matcher flattening
# --------------------------------------------------------------------------- #


def test_get_config_returns_dict_with_plain_event_keys(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    assert isinstance(config, dict)
    assert "PreToolUse" in config
    assert "PostToolUse" in config
    assert "Stop" in config


def test_get_config_does_not_contain_flattened_keys(lib: HooksLibrary) -> None:
    """BREAKING migration: the old `hooks.<event>` composite keys are gone."""
    config = lib.get_config(VALID_FIXTURE)
    assert "hooks.PreToolUse" not in config


def test_get_config_flattens_group_definitions_in_order(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    pre = config["PreToolUse"]
    assert len(pre) == 2
    assert pre[0]["command"] == "echo pre-tool-use"
    assert pre[1]["command"] == "echo pre-tool-use-second"


def test_get_config_copies_group_matcher_onto_each_entry(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    pre = config["PreToolUse"]
    assert pre[0]["matcher"] == "Bash"
    assert pre[1]["matcher"] == "Bash"


def test_get_config_every_entry_has_type(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    for entries in config.values():
        for entry in entries:
            assert entry["type"] == "command"


def test_get_config_preserves_optional_fields(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    entry = config["PreToolUse"][0]
    assert entry["args"] == ["--quiet"]
    assert entry["timeout"] == 5


def test_get_config_matcherless_group_has_no_matcher_forced(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    stop_entry = config["Stop"][0]
    assert "matcher" not in stop_entry
    assert stop_entry["command"] == "echo stop"


def test_get_config_omits_absent_optional_fields(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    posttool_entry = config["PostToolUse"][0]
    assert "args" not in posttool_entry
    assert "timeout" not in posttool_entry
    # matcher IS present (copied from the group), but args/timeout are not.
    assert posttool_entry["matcher"] == "Edit|Write"


def test_real_world_scenario_parses_with_plain_key(lib: HooksLibrary, tmp_path: Path) -> None:
    """Spec scenario: real-world settings.json parses without error (dossier E2)."""
    f = _write(
        tmp_path,
        "rw.json",
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}},
    )
    config = lib.get_config(f)
    assert config["PreToolUse"][0]["command"] == "echo hi"


def test_matcher_copied_onto_two_definitions(lib: HooksLibrary, tmp_path: Path) -> None:
    """Spec scenario: group matcher copied onto each flattened entry in order."""
    f = _write(
        tmp_path,
        "two.json",
        {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {"type": "command", "command": "first"},
                            {"type": "command", "command": "second"},
                        ],
                    }
                ]
            }
        },
    )
    entries = lib.get_config(f)["PostToolUse"]
    assert [e["command"] for e in entries] == ["first", "second"]
    assert all(e["matcher"] == "Edit|Write" for e in entries)


def test_matcherless_group_accepted(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "ml.json",
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "cleanup"}]}]}},
    )
    entry = lib.get_config(f)["Stop"][0]
    assert entry["command"] == "cleanup"
    assert "matcher" not in entry


def test_unknown_event_passes_through(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "future.json",
        {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo new event"}]}]}},
    )
    config = lib.get_config(f)
    assert "SessionStart" in config
    assert config["SessionStart"][0]["command"] == "echo new event"


def test_unknown_fields_pass_through(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "extra.json",
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "lint",
                                "async": True,
                                "statusMessage": "linting...",
                            }
                        ],
                    }
                ]
            }
        },
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert entry["async"] is True
    assert entry["statusMessage"] == "linting..."


# --------------------------------------------------------------------------- #
# Per-type validation
# --------------------------------------------------------------------------- #


def test_http_type_requires_url(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "http.json", {"hooks": {"PreToolUse": [{"hooks": [{"type": "http"}]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/0/url"


def test_http_type_valid(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "http_ok.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "http", "url": "https://x"}]}]}},
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert entry["type"] == "http"
    assert entry["url"] == "https://x"


def test_mcp_tool_requires_server_and_tool(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "mcp.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "mcp_tool", "server": "s"}]}]}},
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/0/tool"


def test_prompt_type_requires_prompt(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "prompt.json", {"hooks": {"Stop": [{"hooks": [{"type": "prompt"}]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/Stop/0/hooks/0/prompt"


def test_agent_type_requires_prompt(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "agent.json", {"hooks": {"Stop": [{"hooks": [{"type": "agent"}]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/Stop/0/hooks/0/prompt"


def test_unknown_type_passes_through(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "unk.json",
        {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "some_future_type", "whatever": 1}]}
                ]
            }
        },
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert entry["type"] == "some_future_type"
    assert entry["whatever"] == 1
    assert entry["matcher"] == "Bash"


def test_typeless_definition_with_command_grandfathered(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "typeless.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"command": "echo x"}]}]}},
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert entry["type"] == "command"
    assert entry["command"] == "echo x"


def test_definition_missing_type_and_command_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "notype.json", {"hooks": {"Stop": [{"hooks": [{"foo": "bar"}]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/Stop/0/hooks/0/type"


def test_command_definition_missing_command_nested_pointer(lib: HooksLibrary) -> None:
    """Spec scenario: command def missing `command` → 5-segment nested pointer."""
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(MISSING_COMMAND_FIXTURE)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/1/command"


def test_timeout_bool_rejected_nested(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "to.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "x", "timeout": True}]}]}},
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/0/timeout"


def test_timeout_validated_on_non_command_type(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "http_to.json",
        {"hooks": {"Stop": [{"hooks": [{"type": "http", "url": "https://x", "timeout": "5"}]}]}},
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/Stop/0/hooks/0/timeout"


# --------------------------------------------------------------------------- #
# Nullish-fuzz on new required fields (feedback_nullish_input_fuzz_checklist)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [None, "", False, 0])
def test_type_nullish_variants_rejected(lib: HooksLibrary, tmp_path: Path, bad: object) -> None:
    f = _write(tmp_path, "type_null.json", {"hooks": {"Stop": [{"hooks": [{"type": bad, "command": "x"}]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/Stop/0/hooks/0/type"


@pytest.mark.parametrize("field,typ", [("url", "http"), ("server", "mcp_tool"), ("prompt", "prompt")])
@pytest.mark.parametrize("bad", [None, "", False, 0])
def test_required_field_nullish_variants_rejected(
    lib: HooksLibrary, tmp_path: Path, field: str, typ: str, bad: object
) -> None:
    defn: dict[str, object] = {"type": typ, field: bad}
    if typ == "mcp_tool":
        defn.setdefault("tool", "t")
    f = _write(tmp_path, "req_null.json", {"hooks": {"Stop": [{"hooks": [defn]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == f"/hooks/Stop/0/hooks/0/{field}"


@pytest.mark.parametrize("field,typ", [("url", "http"), ("server", "mcp_tool"), ("prompt", "prompt")])
def test_required_field_missing_key_rejected(lib: HooksLibrary, tmp_path: Path, field: str, typ: str) -> None:
    defn: dict[str, object] = {"type": typ}
    if typ == "mcp_tool":
        defn["tool"] = "t"
    f = _write(tmp_path, "req_missing.json", {"hooks": {"Stop": [{"hooks": [defn]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == f"/hooks/Stop/0/hooks/0/{field}"


# --------------------------------------------------------------------------- #
# Ambiguous / neither classification
# --------------------------------------------------------------------------- #


def test_item_with_both_command_and_hooks_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "both.json",
        {"hooks": {"PreToolUse": [{"command": "x", "hooks": [{"type": "command", "command": "y"}]}]}},
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0"


def test_item_with_neither_command_nor_hooks_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "neither.json", {"hooks": {"PreToolUse": [{"matcher": "Bash"}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0"


def test_group_hooks_not_a_list_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "badgroup.json", {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": "nope"}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks"


def test_group_matcher_not_string_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "badmatcher.json",
        {"hooks": {"PreToolUse": [{"matcher": 42, "hooks": [{"type": "command", "command": "x"}]}]}},
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/matcher"


def test_definition_not_object_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "baddef.json", {"hooks": {"PreToolUse": [{"hooks": ["string-def"]}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/0"


# --------------------------------------------------------------------------- #
# Legacy flat format + deprecation warning
# --------------------------------------------------------------------------- #


def test_legacy_flat_config_still_parses(lib: HooksLibrary) -> None:
    """Spec scenario: legacy flat config parses with `type: command` stamped."""
    with pytest.warns(DeprecationWarning):
        config = lib.get_config(LEGACY_FLAT_FIXTURE)
    entry = config["PreToolUse"][0]
    assert entry["command"] == "echo pre-tool-use"
    assert entry["matcher"] == "*"
    assert entry["type"] == "command"


def test_legacy_flat_emits_single_deprecation_warning(lib: HooksLibrary, tmp_path: Path) -> None:
    """Spec scenario: exactly ONE DeprecationWarning per parse for 2 legacy entries."""
    f = _write(
        tmp_path,
        "legacy2.json",
        {"hooks": {"PreToolUse": [{"command": "a"}, {"command": "b"}]}},
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        lib.get_config(f)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1


def test_real_format_emits_no_deprecation_warning(lib: HooksLibrary) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        lib.get_config(VALID_FIXTURE)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations == []


def test_legacy_flat_missing_command_pointer_is_3_segment(lib: HooksLibrary, tmp_path: Path) -> None:
    f = _write(tmp_path, "legacy_bad.json", {"hooks": {"PreToolUse": [{"args": ["x"]}]}})
    # An item with neither `command` nor `hooks` is ambiguous (points at item).
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0"


def test_legacy_flat_bad_command_type_3_segment_pointer(lib: HooksLibrary, tmp_path: Path) -> None:
    """A legacy flat entry field failure carries a 3-segment pointer.

    The deprecation warning is emitted only on a fully successful parse; a
    mid-parse structural error short-circuits before it fires.
    """
    f = _write(tmp_path, "legacy_cmd.json", {"hooks": {"PreToolUse": [{"command": 42}]}})
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/command"


# --------------------------------------------------------------------------- #
# Inline-skill frontmatter (nested + reserved-key)
# --------------------------------------------------------------------------- #


def test_inline_skill_extracted_from_real_format_command(lib: HooksLibrary, tmp_path: Path) -> None:
    inline_command = "---\nname: guard\ndescription: blocks rm\n---\necho running audit\n"
    f = _write(
        tmp_path,
        "inline.json",
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": inline_command}]}]}},
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert entry["inline_skill"] == {"name": "guard", "description": "blocks rm"}


def test_inline_skill_heuristic_rejects_non_skill_yaml(lib: HooksLibrary, tmp_path: Path) -> None:
    heredoc_command = "---\nfoo: bar\nbaz: 1\n---\necho not-a-skill\n"
    f = _write(
        tmp_path,
        "heredoc.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": heredoc_command}]}]}},
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert "inline_skill" not in entry


def test_reserved_inline_skill_key_rejected_nested_pointer(lib: HooksLibrary, tmp_path: Path) -> None:
    """Spec scenario: reserved-key collision rejected with 5-segment pointer."""
    f = _write(
        tmp_path,
        "reserved.json",
        {
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"type": "command", "command": "x", "inline_skill": {"injected": "yes"}}]}
                ]
            }
        },
    )
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/hooks/0/inline_skill"


def test_inline_skill_absent_when_command_has_no_frontmatter(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    for entry in config["PreToolUse"]:
        assert "inline_skill" not in entry


def test_inline_skill_malformed_yaml_silently_ignored(lib: HooksLibrary, tmp_path: Path) -> None:
    inline_command = "---\n: : broken yaml ::\n---\necho x\n"
    f = _write(
        tmp_path,
        "broken_inline.json",
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": inline_command}]}]}},
    )
    entry = lib.get_config(f)["PreToolUse"][0]
    assert "inline_skill" not in entry
    assert entry["command"] == inline_command


# --------------------------------------------------------------------------- #
# File-level failures (format-independent)
# --------------------------------------------------------------------------- #


def test_invalid_hook_config_error_inherits_integrity() -> None:
    assert issubclass(InvalidHookConfigError, AgentEvalIntegrityError)
    assert issubclass(InvalidHookConfigError, AgentEvalError)


def test_invalid_hook_config_error_code() -> None:
    assert InvalidHookConfigError.error_code == "INVALID_HOOK_CONFIG"


def test_malformed_json_raises_with_line(lib: HooksLibrary) -> None:
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(MALFORMED_JSON_FIXTURE)
    exc = exc_info.value
    assert exc.error_code == "INVALID_HOOK_CONFIG"
    assert exc.line_number is not None


def test_non_json_extension_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    not_json = tmp_path / "settings.txt"
    not_json.write_text('{"hooks": {}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(not_json)
    assert ".txt" in str(exc_info.value)


def test_file_not_found_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    with pytest.raises(InvalidHookConfigError):
        lib.get_config(tmp_path / "nope.json")


def test_top_level_not_object_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "list.json"
    f.write_text("[1, 2, 3]")
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert "object" in str(exc_info.value)


def test_hooks_section_not_mapping_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_hooks.json"
    f.write_text('{"hooks": [1, 2, 3]}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks"


def test_event_array_not_list_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_event.json"
    f.write_text('{"hooks": {"PreToolUse": "should-be-array"}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse"


def test_event_item_not_object_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_item.json"
    f.write_text('{"hooks": {"PreToolUse": ["string-item"]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0"


def test_no_hooks_section_returns_empty_dict(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "no_hooks.json"
    f.write_text("{}")
    config = lib.get_config(f)
    assert config == {}


def test_bom_prefixed_json_parses(lib: HooksLibrary, tmp_path: Path) -> None:
    """`utf-8-sig` strips BOM transparently per Story 2.1 code-review fix pattern."""
    bom = tmp_path / "bom.json"
    bom.write_bytes(
        b'\xef\xbb\xbf{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]}}'
    )
    config = lib.get_config(bom)
    assert config["PreToolUse"][0]["command"] == "x"


# --------------------------------------------------------------------------- #
# Contract / conventions invariants
# --------------------------------------------------------------------------- #


def test_get_config_meets_nfr_perf_02(lib: HooksLibrary) -> None:
    """Median latency ≤ 50 ms per NFR-PERF-02."""
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.get_config(VALID_FIXTURE)
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 budget"


def test_keyword_has_tier_1_annotation() -> None:
    assert get_keyword_tier(HooksLibrary.get_config) == 1


def test_keyword_docstring_has_tier_1_badge() -> None:
    doc = HooksLibrary.get_config.__doc__ or ""
    assert tier_badge(1) in doc


def test_keyword_has_robot_marker() -> None:
    assert hasattr(HooksLibrary.get_config, "robot_name")


def test_invalid_hook_config_str_fr59_layout() -> None:
    exc = InvalidHookConfigError(
        "boom",
        file_path="x.json",
        line_number=5,
        field_name="/hooks/PreToolUse/0/hooks/1/command",
        fix_suggestion="set it",
    )
    rendered = str(exc)
    lines = rendered.splitlines()
    assert lines[0] == "INVALID_HOOK_CONFIG: boom"
    assert "File: x.json" in lines[1]
    assert "Line: 5" in lines[2]
    assert "Field: /hooks/PreToolUse/0/hooks/1/command" in lines[3]
    assert "Fix: set it" in lines[4]


def test_dynamic_core_loads_hooks_library() -> None:
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    assert "HooksLibrary" in library._loaded_components
    assert "Get Config" in library.get_keyword_names()


def test_build_pointer_escapes_special_chars() -> None:
    """RFC 6901 §3 escaping: `/` → `~1`, `~` → `~0`."""
    assert _build_pointer("hooks", "PreToolUse", 0) == "/hooks/PreToolUse/0"
    assert _build_pointer("with/slash") == "/with~1slash"
    assert _build_pointer("with~tilde") == "/with~0tilde"
    assert _build_pointer("with/both~") == "/with~1both~0"


def test_supported_events_contract() -> None:
    """SUPPORTED_EVENTS matches PRD FR4: `PreToolUse`, `PostToolUse`, `Stop`."""
    assert set(SUPPORTED_EVENTS) == {"PreToolUse", "PostToolUse", "Stop"}


def test_inherits_shared_fr59_layout_from_intermediate_base() -> None:
    from AgentEval.errors import _FR59Tier1SetupFailureError

    assert issubclass(InvalidHookConfigError, _FR59Tier1SetupFailureError)
