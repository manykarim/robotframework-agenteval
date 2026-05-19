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

"""Unit tests for `src/AgentEval/hooks/library.py` (Story 2.2).

Covers AC-2.2.4 through AC-2.2.9: `Hook.Get Config` happy path,
inline-skill-frontmatter detection, every error path through
`_parser.py` + `InvalidHookConfigError`, RFC 6901 JSON Pointer in
`field_name`, Tier-1 latency budget per NFR-PERF-02, and the Story
1b.6 conventions invariants.
"""

from __future__ import annotations

import time
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


@pytest.fixture
def lib() -> HooksLibrary:
    return HooksLibrary()


def test_get_config_returns_dict_with_events(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    assert isinstance(config, dict)
    assert "hooks.PreToolUse" in config
    assert "hooks.PostToolUse" in config
    assert "hooks.Stop" in config


def test_get_config_pretooluse_entry_has_required_command(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    entry = config["hooks.PreToolUse"][0]
    assert entry["command"] == "echo pre-tool-use"


def test_get_config_preserves_optional_fields(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    entry = config["hooks.PreToolUse"][0]
    assert entry["args"] == ["--quiet"]
    assert entry["timeout"] == 5
    assert entry["matcher"] == "*"


def test_get_config_omits_absent_optional_fields(lib: HooksLibrary) -> None:
    config = lib.get_config(VALID_FIXTURE)
    posttool_entry = config["hooks.PostToolUse"][0]
    assert "args" not in posttool_entry
    assert "timeout" not in posttool_entry
    assert "matcher" not in posttool_entry


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


def test_missing_command_raises_with_json_pointer(lib: HooksLibrary) -> None:
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(MISSING_COMMAND_FIXTURE)
    # RFC 6901 JSON Pointer per Story 2.2 D-D catalog convention.
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/command"


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


def test_entry_not_object_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_entry.json"
    f.write_text('{"hooks": {"PreToolUse": ["string-entry"]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0"


def test_command_not_string_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_cmd.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": 42}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/command"


def test_args_not_list_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_args.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": "x", "args": "string"}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/args"


def test_args_with_non_string_element_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_args_elem.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": "x", "args": ["ok", 42]}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/args"


def test_timeout_not_int_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_timeout.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": "x", "timeout": "5"}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/timeout"


def test_timeout_bool_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    """`true` is `isinstance(True, int)` but we reject bool explicitly."""
    f = tmp_path / "bool_timeout.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": "x", "timeout": true}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/timeout"


def test_matcher_not_string_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad_matcher.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": "x", "matcher": 42}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/matcher"


def test_inline_skill_frontmatter_extraction(lib: HooksLibrary, tmp_path: Path) -> None:
    """A hook whose `command` contains canonical skill YAML surfaces it as `inline_skill`.

    Story 2.2 code-review Edge-MED-1 fix: canonical-shape gate requires
    both `name` and `description` keys to mark inline content as skill.
    """
    f = tmp_path / "inline.json"
    inline_command = "---\nname: inline-skill\ndescription: pre-tool-audit skill\n---\necho running audit\n"
    payload = {"hooks": {"PreToolUse": [{"command": inline_command}]}}
    import json as _json

    f.write_text(_json.dumps(payload))
    config = lib.get_config(f)
    entry = config["hooks.PreToolUse"][0]
    assert "inline_skill" in entry
    assert entry["inline_skill"]["name"] == "inline-skill"


def test_inline_skill_heuristic_rejects_non_skill_yaml(lib: HooksLibrary, tmp_path: Path) -> None:
    """A YAML mapping that lacks `name`+`description` is NOT classified as inline_skill.

    Story 2.2 code-review Edge-MED-1 fix: shell heredocs with `---`
    delimiters (Pandoc / Kubernetes manifests) used to false-positive.
    """
    f = tmp_path / "heredoc.json"
    heredoc_command = "---\nfoo: bar\nbaz: 1\n---\necho not-a-skill\n"
    import json as _json

    f.write_text(_json.dumps({"hooks": {"PreToolUse": [{"command": heredoc_command}]}}))
    config = lib.get_config(f)
    entry = config["hooks.PreToolUse"][0]
    assert "inline_skill" not in entry


def test_reserved_inline_skill_key_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    """User-supplied `inline_skill` field on hook entry is rejected.

    Story 2.2 code-review Blind-MED-1 fix: prevents silent overwrite
    of parser-reserved output keys.
    """
    f = tmp_path / "reserved.json"
    import json as _json

    f.write_text(_json.dumps({"hooks": {"PreToolUse": [{"command": "x", "inline_skill": {"injected": "yes"}}]}}))
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/inline_skill"


def test_inline_skill_absent_when_command_has_no_frontmatter(
    lib: HooksLibrary,
) -> None:
    config = lib.get_config(VALID_FIXTURE)
    for entry in config["hooks.PreToolUse"]:
        assert "inline_skill" not in entry


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
        field_name="/hooks/PreToolUse/0/command",
        fix_suggestion="set it",
    )
    rendered = str(exc)
    lines = rendered.splitlines()
    assert lines[0] == "INVALID_HOOK_CONFIG: boom"
    assert "File: x.json" in lines[1]
    assert "Line: 5" in lines[2]
    assert "Field: /hooks/PreToolUse/0/command" in lines[3]
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


def test_unknown_event_passes_through(lib: HooksLibrary, tmp_path: Path) -> None:
    """Events outside SUPPORTED_EVENTS still validate the required `command` field."""
    f = tmp_path / "future.json"
    f.write_text('{"hooks": {"FutureEvent": [{"command": "echo new event"}]}}')
    config = lib.get_config(f)
    assert "hooks.FutureEvent" in config
    assert config["hooks.FutureEvent"][0]["command"] == "echo new event"


def test_bom_prefixed_json_parses(lib: HooksLibrary, tmp_path: Path) -> None:
    """`utf-8-sig` strips BOM transparently per Story 2.1 code-review fix pattern."""
    bom = tmp_path / "bom.json"
    bom.write_bytes(b'\xef\xbb\xbf{"hooks": {"PreToolUse": [{"command": "x"}]}}')
    config = lib.get_config(bom)
    assert config["hooks.PreToolUse"][0]["command"] == "x"


def test_inline_skill_malformed_yaml_silently_ignored(lib: HooksLibrary, tmp_path: Path) -> None:
    """Malformed inline YAML is silently no-inline_skill (Phase-1 contract)."""
    f = tmp_path / "broken_inline.json"
    inline_command = "---\n: : broken yaml ::\n---\necho x\n"
    import json as _json

    f.write_text(_json.dumps({"hooks": {"PreToolUse": [{"command": inline_command}]}}))
    config = lib.get_config(f)
    entry = config["hooks.PreToolUse"][0]
    assert "inline_skill" not in entry  # silently no inline skill
    assert entry["command"] == inline_command  # hook itself still valid


def test_empty_string_command_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "empty.json"
    f.write_text('{"hooks": {"PreToolUse": [{"command": ""}]}}')
    with pytest.raises(InvalidHookConfigError) as exc_info:
        lib.get_config(f)
    assert exc_info.value.field_name == "/hooks/PreToolUse/0/command"


def test_no_hooks_section_returns_empty_dict(lib: HooksLibrary, tmp_path: Path) -> None:
    f = tmp_path / "no_hooks.json"
    f.write_text("{}")
    config = lib.get_config(f)
    assert config == {}


def test_inherits_shared_fr59_layout_from_intermediate_base() -> None:
    from AgentEval.errors import _FR59Tier1SetupFailureError

    assert issubclass(InvalidHookConfigError, _FR59Tier1SetupFailureError)
