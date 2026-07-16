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

"""Unit tests for HooksLibrary - one Tier-1 hook-testing surface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from AgentEval._core import HookExecutionError, InvalidConfigError, get_keyword_tier
from HooksLibrary import HooksLibrary
from HooksLibrary._runner import ENV_ALLOWLIST, FireReport, build_hook_env


def _write_config(tmp_path: Path, hooks: dict[str, Any]) -> str:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return str(path)


@pytest.fixture
def lib() -> HooksLibrary:
    return HooksLibrary()


# --------------------------------------------------------------------------- #
# Requirement: parses the real nested hook config
# --------------------------------------------------------------------------- #


def test_nested_config_parses_into_canonical_entries(lib: HooksLibrary, tmp_path: Path) -> None:
    """WHEN Get Config on a valid nested file THEN hooks keyed by event, canonical shape."""
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]},
    )
    config = lib.get_config(path)
    assert list(config) == ["PreToolUse"]
    (entry,) = config["PreToolUse"]
    assert entry["type"] == "command"
    assert entry["matcher"] == "Bash"
    assert entry["command"] == "echo hi"


def test_multiple_definitions_flatten_preserving_order(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "one"}, {"type": "command", "command": "two"}],
                }
            ]
        },
    )
    config = lib.get_config(path)
    assert [e["command"] for e in config["PreToolUse"]] == ["one", "two"]


def test_invalid_config_fails_with_a_pointer(lib: HooksLibrary, tmp_path: Path) -> None:
    """WHEN a malformed entry THEN a structured error points at the offending location."""
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command"}]}]},  # missing command
    )
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_config(path)
    assert exc.value.field == "/hooks/PreToolUse/0/hooks/0/command"


def test_missing_hooks_key_returns_empty(lib: HooksLibrary, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"other": 1}), encoding="utf-8")
    assert lib.get_config(str(path)) == {}


def test_legacy_flat_format_is_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    """The dropped legacy flat shape (command, no hooks list) no longer parses."""
    path = _write_config(tmp_path, {"PreToolUse": [{"command": "echo hi"}]})
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_config(path)
    assert "hooks" in str(exc.value).lower()


def test_inline_skill_frontmatter_is_not_extracted(lib: HooksLibrary, tmp_path: Path) -> None:
    """The dropped inline-skill extraction: no inline_skill field is ever added."""
    command = "---\nname: s\ndescription: d\n---\necho hi"
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]},
    )
    (entry,) = lib.get_config(path)["PreToolUse"]
    assert "inline_skill" not in entry


def test_non_json_extension_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        lib.get_config(str(path))


def test_missing_file_rejected(lib: HooksLibrary, tmp_path: Path) -> None:
    with pytest.raises(InvalidConfigError):
        lib.get_config(str(tmp_path / "nope.json"))


# --------------------------------------------------------------------------- #
# Requirement: deterministic - Tier-1 only, loads without extras
# --------------------------------------------------------------------------- #


def test_every_keyword_is_tier_1() -> None:
    """WHEN the library declares its keywords THEN every one is Tier-1."""
    keyword_methods = [
        HooksLibrary.get_config,
        HooksLibrary.fire_hook_event,
        HooksLibrary.decision_should_be,
        HooksLibrary.exit_code_should_be,
        HooksLibrary.output_field_should_be,
        HooksLibrary.get_hooks_for_event,
        HooksLibrary.validate_matcher_syntax,
        HooksLibrary.command_should_exist,
    ]
    for method in keyword_methods:
        assert get_keyword_tier(method) == 1


def test_library_imports_without_litellm_or_mcp() -> None:
    """WHEN the base install imports HooksLibrary THEN no litellm/mcp SDK is loaded."""
    code = (
        "import sys, HooksLibrary; HooksLibrary.HooksLibrary(); "
        "assert 'litellm' not in sys.modules, 'litellm loaded'; "
        "assert 'mcp' not in sys.modules, 'mcp loaded'; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# --------------------------------------------------------------------------- #
# Requirement: static simulation and live firing share one matcher engine
# --------------------------------------------------------------------------- #


def test_simulation_matches_execution(lib: HooksLibrary, tmp_path: Path) -> None:
    """WHEN Get Hooks For Event then Fire Hook Event for the same event+payload
    THEN the simulated set matches the executed set."""
    path = _write_config(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "exit 0"}]},
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "exit 0"}]},
            ]
        },
    )
    config = lib.get_config(path)
    simulated = lib.get_hooks_for_event(config, "PreToolUse", tool_name="Bash")
    report = lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    assert [e["command"] for e in simulated] == [r.command for r in report.results]
    assert [r.command for r in report.results] == ["exit 0"]


def test_matcher_syntax_valid_list(lib: HooksLibrary) -> None:
    assert lib.validate_matcher_syntax("Bash|Edit", subject="Edit") is True
    assert lib.validate_matcher_syntax("Bash|Edit", subject="Read") is False


def test_matcher_syntax_malformed_regex_fails(lib: HooksLibrary) -> None:
    """WHEN Validate Matcher Syntax on a malformed matcher THEN it fails with the error."""
    with pytest.raises(AssertionError) as exc:
        lib.validate_matcher_syntax("(unclosed[")
    assert "compile" in str(exc.value).lower()


def test_matcher_subject_length_cap(lib: HooksLibrary) -> None:
    """A regex matcher against an over-long subject is rejected, not searched."""
    with pytest.raises(HookExecutionError):
        lib.validate_matcher_syntax("a.*b", subject="x" * 5000)


# --------------------------------------------------------------------------- #
# Requirement: firing synthesizes a payload and normalizes decisions
# --------------------------------------------------------------------------- #


def test_blocking_hook_yields_block_decision(lib: HooksLibrary, tmp_path: Path) -> None:
    """WHEN a matched hook exits blocking THEN Decision Should Be block passes and
    Exit Code Should Be reports the exit code."""
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "exit 2"}]}]},
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    lib.decision_should_be(report, "block")
    lib.decision_should_be(report, "deny")  # deny aliases block
    lib.exit_code_should_be(report, 2)


def test_allow_decision_from_permission_json(lib: HooksLibrary, tmp_path: Path) -> None:
    command = 'echo \'{"hookSpecificOutput":{"permissionDecision":"allow"}}\''
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]},
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    lib.decision_should_be(report, "allow")
    lib.exit_code_should_be(report, 0)
    lib.output_field_should_be(report, "hookSpecificOutput.permissionDecision", "allow")


def test_hook_crash_is_recorded_not_raised(lib: HooksLibrary, tmp_path: Path) -> None:
    """WHEN a matched hook errors during execution THEN the failure is captured in
    that hook's record and the keyword still returns results for the other hooks."""
    path = _write_config(
        tmp_path,
        {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "/nonexistent/binary", "args": ["x"]},
                        {"type": "command", "command": "exit 0"},
                    ],
                }
            ]
        },
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    assert len(report.results) == 2
    assert report.results[0].status == "spawn_failed"
    assert report.results[1].status == "completed"


def test_fire_with_no_match_raises(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "exit 0"}]}]},
    )
    config = lib.get_config(path)
    with pytest.raises(HookExecutionError):
        lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")


def test_non_command_hook_is_skipped(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "http", "url": "http://x"}]}]},
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(config, "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    (record,) = report.results
    assert record.status == "skipped"
    assert record.skip_reason is not None


def test_top_level_decision_block(lib: HooksLibrary, tmp_path: Path) -> None:
    command = 'echo \'{"decision":"block"}\''
    path = _write_config(
        tmp_path,
        {"Stop": [{"hooks": [{"type": "command", "command": command}]}]},
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(config, "Stop", project_dir=str(tmp_path))
    lib.decision_should_be(report, "block")


def test_payload_full_override(lib: HooksLibrary, tmp_path: Path) -> None:
    """The full-override payload sets the matcher subject and reaches the hook stdin."""
    command = "cat"  # echoes stdin back to stdout
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]},
    )
    config = lib.get_config(path)
    report = lib.fire_hook_event(
        config, "PreToolUse", project_dir=str(tmp_path), payload={"tool_name": "Bash", "custom": 1}
    )
    (record,) = report.results
    echoed = json.loads(record.stdout)
    assert echoed["tool_name"] == "Bash"
    assert echoed["custom"] == 1


# --------------------------------------------------------------------------- #
# Assertion-keyword edge behavior
# --------------------------------------------------------------------------- #


def test_decision_should_be_rejects_unknown_vocab(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "exit 0"}]}]},
    )
    report = lib.fire_hook_event(lib.get_config(path), "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    with pytest.raises(ValueError):
        lib.decision_should_be(report, "maybe")


def test_coerce_record_rejects_multi_record_report(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "exit 0"}, {"type": "command", "command": "exit 0"}],
                }
            ]
        },
    )
    report = lib.fire_hook_event(lib.get_config(path), "PreToolUse", project_dir=str(tmp_path), tool_name="Bash")
    with pytest.raises(AssertionError):
        lib.exit_code_should_be(report, 0)


def test_require_config_rejects_non_dict(lib: HooksLibrary) -> None:
    with pytest.raises(HookExecutionError):
        lib.get_hooks_for_event("not-a-dict", "PreToolUse")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Command Should Exist
# --------------------------------------------------------------------------- #


def test_command_should_exist_passes_for_real_binary(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]},
    )
    lib.command_should_exist(lib.get_config(path))  # `echo` resolves


def test_command_should_exist_fails_for_missing_binary(lib: HooksLibrary, tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {"PreToolUse": [{"hooks": [{"type": "command", "command": "totally-not-a-real-binary-xyz --flag"}]}]},
    )
    with pytest.raises(AssertionError):
        lib.command_should_exist(lib.get_config(path))


# --------------------------------------------------------------------------- #
# Env sanitization - one allowlist, default-deny
# --------------------------------------------------------------------------- #


def test_build_hook_env_default_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("MY_SECRET_TOKEN", "sk-abc")
    env = build_hook_env(project_dir="/proj")
    assert "MY_SECRET_TOKEN" not in env
    assert env["PATH"] == "/usr/bin"
    assert env["CLAUDE_PROJECT_DIR"] == "/proj"


def test_build_hook_env_only_allowlist_copied(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_ALLOWLIST:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", "/home/x")
    monkeypatch.setenv("RANDOM_VAR", "v")
    env = build_hook_env(project_dir="/proj")
    assert env["HOME"] == "/home/x"
    assert "RANDOM_VAR" not in env


def test_build_hook_env_inherit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RANDOM_VAR", "v")
    env = build_hook_env(project_dir="/proj", inherit_env=True)
    assert env["RANDOM_VAR"] == "v"


def test_fire_report_type() -> None:
    report = FireReport(event="X", subject="", payload={}, results=())
    assert len(report) == 0
