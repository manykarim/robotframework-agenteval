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

"""Unit tests for the OpenSpec change `add-hooks-execution-testing`.

Covers the matcher engine, payload synthesis, the subprocess runner + decision
normalization, and the seven new `HooksLibrary` keywords — including the
headline block-on-dangerous-bash end-to-end demonstration. Fixture hook
scripts live under tests/fixtures/hooks/exec/.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.errors import HookExecutionError
from AgentEval.hooks._matcher import matcher_matches, safe_search, validate_matcher
from AgentEval.hooks._payload import SYNTHETIC_SESSION_ID, synthesize_payload
from AgentEval.hooks._runner import FireReport, HookResult, build_hook_env, normalize_decision
from AgentEval.hooks.library import HooksLibrary

EXEC_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "hooks" / "exec"


def _cmd(script: str) -> str:
    """Build a shell command string invoking a fixture script with this interpreter."""
    return f"{sys.executable} {EXEC_DIR / script}"


@pytest.fixture
def lib() -> HooksLibrary:
    return HooksLibrary()


def _config(*entries: dict[str, Any], event: str = "PreToolUse") -> dict[str, list[dict[str, Any]]]:
    return {event: list(entries)}


# --------------------------------------------------------------------------- #
# Matcher engine
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("matcher", [None, "", "*"])
def test_matcher_match_all(matcher: str | None) -> None:
    assert matcher_matches(matcher, "Bash") is True
    assert matcher_matches(matcher, "") is True


def test_matcher_exact() -> None:
    assert matcher_matches("Bash", "Bash") is True
    assert matcher_matches("Bash", "Edit") is False


def test_matcher_pipe_list() -> None:
    assert matcher_matches("Bash|Edit", "Bash") is True
    assert matcher_matches("Bash|Edit", "Edit") is True
    assert matcher_matches("Bash|Edit", "Read") is False


def test_matcher_comma_list() -> None:
    assert matcher_matches("Bash, Edit", "Edit") is True
    assert matcher_matches("Bash, Edit", "Read") is False


def test_matcher_regex_path() -> None:
    assert matcher_matches("mcp__.*", "mcp__github__create_issue") is True
    assert matcher_matches("mcp__.*", "Bash") is False


def test_validate_matcher_invalid_regex_names_pattern() -> None:
    outcome = validate_matcher("(unclosed")
    assert outcome.valid is False
    assert "(unclosed" in (outcome.error or "")


def test_validate_matcher_optional_subject() -> None:
    outcome = validate_matcher("Bash|Edit", "Edit")
    assert outcome.valid is True
    assert outcome.subject_matches is True
    assert validate_matcher("Bash|Edit", "Read").subject_matches is False


# --------------------------------------------------------------------------- #
# Payload synthesis
# --------------------------------------------------------------------------- #


def test_payload_pretooluse_carries_tool_fields() -> None:
    payload = synthesize_payload(
        "PreToolUse",
        cwd="/tmp/x",
        transcript_path="/tmp/t.jsonl",
        event_fields={"tool_name": "Bash", "tool_input": {"command": "ls"}},
    )
    assert payload["hook_event_name"] == "PreToolUse"
    assert payload["session_id"] == SYNTHETIC_SESSION_ID
    assert payload["cwd"] == "/tmp/x"
    assert payload["tool_name"] == "Bash"
    assert payload["tool_input"] == {"command": "ls"}


def test_payload_unknown_event_passes_through() -> None:
    payload = synthesize_payload(
        "SessionStart",
        cwd="/tmp/x",
        transcript_path="/tmp/t.jsonl",
        event_fields={"source": "startup"},
    )
    assert payload["hook_event_name"] == "SessionStart"
    assert payload["source"] == "startup"
    # No PreToolUse defaults leaked into an unknown event.
    assert "tool_name" not in payload


def test_payload_override_replaces_event_fields() -> None:
    payload = synthesize_payload(
        "PreToolUse",
        cwd="/tmp/x",
        transcript_path="/tmp/t.jsonl",
        payload={"tool_name": "Edit", "custom": 1},
        event_fields={"tool_name": "Bash"},  # ignored when payload override present
    )
    assert payload["tool_name"] == "Edit"
    assert payload["custom"] == 1
    # Synthesized common fields still fill gaps.
    assert payload["session_id"] == SYNTHETIC_SESSION_ID


# --------------------------------------------------------------------------- #
# Decision normalization (three-channel precedence)
# --------------------------------------------------------------------------- #


def test_decision_exit_two_blocks_and_ignores_stdout() -> None:
    # Even with an allow stdout JSON, exit 2 → block.
    decision, err = normalize_decision(
        2, {"hookSpecificOutput": {"permissionDecision": "allow"}}
    )
    assert decision == "block"
    assert err is None


def test_decision_permission_deny_maps_to_block() -> None:
    decision, _ = normalize_decision(0, {"hookSpecificOutput": {"permissionDecision": "deny"}})
    assert decision == "block"


def test_decision_permission_allow_ask_defer() -> None:
    assert normalize_decision(0, {"hookSpecificOutput": {"permissionDecision": "allow"}})[0] == "allow"
    assert normalize_decision(0, {"hookSpecificOutput": {"permissionDecision": "ask"}})[0] == "ask"
    assert normalize_decision(0, {"hookSpecificOutput": {"permissionDecision": "defer"}})[0] == "none"


def test_decision_top_level_block() -> None:
    assert normalize_decision(0, {"decision": "block"})[0] == "block"


def test_decision_no_json_is_none() -> None:
    assert normalize_decision(0, None) == ("none", None)


def test_decision_other_exit_is_nonblocking_error() -> None:
    assert normalize_decision(1, None) == ("none", "nonblocking_error")


# --------------------------------------------------------------------------- #
# Runner env sanitization
# --------------------------------------------------------------------------- #


def test_build_env_default_deny_excludes_parent_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = build_hook_env(project_dir="/tmp/p")
    assert "OPENAI_API_KEY" not in env
    assert env["PATH"] == "/usr/bin"
    assert env["CLAUDE_PROJECT_DIR"] == "/tmp/p"


def test_build_env_inherit_opt_in_restores_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    env = build_hook_env(project_dir="/tmp/p", inherit_env=True)
    assert env["OPENAI_API_KEY"] == "sk-secret"


def test_build_env_extra_env_merged() -> None:
    env = build_hook_env(project_dir="/tmp/p", extra_env={"MY_FLAG": "1"})
    assert env["MY_FLAG"] == "1"


# --------------------------------------------------------------------------- #
# Fire Hook Event — execution
# --------------------------------------------------------------------------- #


def test_fire_matching_command_executes_and_captures(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "Bash", "command": _cmd("deny_permission_json.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    assert isinstance(report, FireReport)
    assert len(report.results) == 1
    rec = report.results[0]
    assert rec.status == "completed"
    assert rec.exit_code == 0
    assert rec.stdout_json is not None
    assert rec.decision == "block"  # deny → block
    assert rec.duration >= 0.0


def test_fire_zero_match_raises_hook_execution_error(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "Edit", "command": _cmd("exit_zero.py")})
    with pytest.raises(HookExecutionError) as exc:
        lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    assert "Get Hooks For Event" in str(exc.value)


def test_fire_multi_hook_reports_timeout_and_completed_sibling(lib: HooksLibrary) -> None:
    config = _config(
        {"type": "command", "matcher": "*", "command": _cmd("slow.py"), "timeout": 1},
        {"type": "command", "matcher": "*", "command": _cmd("exit_zero.py")},
    )
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash", default_timeout=2)
    assert len(report.results) == 2
    statuses = [r.status for r in report.results]
    assert statuses == ["timed_out", "completed"]


def test_fire_non_command_hook_recorded_skipped(lib: HooksLibrary) -> None:
    config = _config(
        {"type": "http", "matcher": "*", "url": "https://example.com/hook"},
    )
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    assert len(report.results) == 1
    rec = report.results[0]
    assert rec.status == "skipped"
    assert "http" in (rec.skip_reason or "")


def test_fire_spawn_failed_on_missing_binary(lib: HooksLibrary) -> None:
    config = _config(
        {"type": "command", "matcher": "*", "command": "/nonexistent/path/hook", "args": ["x"]},
    )
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    assert report.results[0].status == "spawn_failed"


def test_fire_env_sanitization_secret_absent_by_default(lib: HooksLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    config = _config({"type": "command", "matcher": "*", "command": _cmd("echo_env.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    hook_env = report.results[0].stdout_json["env"]  # type: ignore[index]
    assert "ANTHROPIC_API_KEY" not in hook_env
    assert "CLAUDE_PROJECT_DIR" in hook_env


def test_fire_env_inherit_opt_in(lib: HooksLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-inherited")
    config = _config({"type": "command", "matcher": "*", "command": _cmd("echo_env.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash", inherit_env=True)
    hook_env = report.results[0].stdout_json["env"]  # type: ignore[index]
    assert hook_env["ANTHROPIC_API_KEY"] == "sk-inherited"


def test_fire_string_command_runs_via_shell(lib: HooksLibrary) -> None:
    # A pipe is only honored when run through the shell.
    config = _config({"type": "command", "matcher": "*", "command": "echo hi | cat"})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    assert report.results[0].status == "completed"
    assert report.results[0].stdout.strip() == "hi"


# --------------------------------------------------------------------------- #
# Simulation / execution agreement
# --------------------------------------------------------------------------- #


def test_get_hooks_for_event_static_matches(lib: HooksLibrary) -> None:
    config = _config(
        {"type": "command", "matcher": "Bash", "command": _cmd("exit_zero.py")},
        {"type": "command", "matcher": "Edit", "command": _cmd("exit_zero.py")},
    )
    hooks = lib.get_hooks_for_event(config, "PreToolUse", tool_name="Bash")
    assert len(hooks) == 1
    assert hooks[0]["matcher"] == "Bash"


def test_simulation_and_execution_agree(lib: HooksLibrary) -> None:
    config = _config(
        {"type": "command", "matcher": "Bash|Edit", "command": _cmd("exit_zero.py")},
        {"type": "command", "matcher": "Read", "command": _cmd("exit_zero.py")},
    )
    simulated = lib.get_hooks_for_event(config, "PreToolUse", tool_name="Edit")
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Edit")
    assert len(simulated) == len(report.results) == 1


# --------------------------------------------------------------------------- #
# Validate Matcher Syntax / Command Should Exist
# --------------------------------------------------------------------------- #


def test_validate_matcher_syntax_invalid_raises(lib: HooksLibrary) -> None:
    with pytest.raises(AssertionError) as exc:
        lib.validate_matcher_syntax("(unclosed")
    assert "(unclosed" in str(exc.value)


def test_validate_matcher_syntax_subject_match(lib: HooksLibrary) -> None:
    assert lib.validate_matcher_syntax("Bash|Edit", subject="Edit") is True
    assert lib.validate_matcher_syntax("Bash|Edit", subject="Read") is False


def test_command_should_exist_passes_for_real_binary(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": f"{sys.executable} -c 'pass'"})
    lib.command_should_exist(config)  # no raise


def test_command_should_exist_fails_for_missing(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": "definitely-not-a-real-binary-xyz --flag"})
    with pytest.raises(AssertionError) as exc:
        lib.command_should_exist(config)
    assert "definitely-not-a-real-binary-xyz" in str(exc.value)


def test_command_should_exist_expands_project_dir(lib: HooksLibrary, tmp_path: Path) -> None:
    script = tmp_path / "hook.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    config = _config({"type": "command", "matcher": "*", "command": "$CLAUDE_PROJECT_DIR/hook.sh"})
    lib.command_should_exist(config, project_dir=str(tmp_path))  # no raise


# --------------------------------------------------------------------------- #
# Assertion keywords
# --------------------------------------------------------------------------- #


def test_decision_should_be_deny_alias(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": _cmd("deny_permission_json.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    lib.decision_should_be(report, "block")
    lib.decision_should_be(report, "deny")  # alias
    with pytest.raises(AssertionError):
        lib.decision_should_be(report, "allow")


def test_decision_should_be_fails_loud_on_non_completed(lib: HooksLibrary) -> None:
    rec = HookResult(
        type="command",
        matcher="*",
        command="x",
        status="spawn_failed",
        exit_code=None,
        stdout="",
        stderr="boom",
        stdout_json=None,
        duration=0.0,
        decision="none",
        error_status="spawn_failed",
    )
    with pytest.raises(AssertionError) as exc:
        lib.decision_should_be(rec, "block")
    assert "spawn_failed" in str(exc.value)


def test_exit_code_should_be(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": _cmd("exit_two_with_allow_stdout.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    lib.exit_code_should_be(report, 2)
    with pytest.raises(AssertionError):
        lib.exit_code_should_be(report, 0)


def test_exit_two_ignores_allow_stdout_end_to_end(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": _cmd("exit_two_with_allow_stdout.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    # Despite the allow on stdout, the exit-2 rule wins.
    lib.decision_should_be(report, "block")
    assert report.results[0].stdout_json is None


def test_output_field_should_be(lib: HooksLibrary) -> None:
    config = _config({"type": "command", "matcher": "*", "command": _cmd("deny_permission_json.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    lib.output_field_should_be(report, "hookSpecificOutput.permissionDecision", "deny")
    with pytest.raises(AssertionError):
        lib.output_field_should_be(report, "hookSpecificOutput.permissionDecision", "allow")


def test_top_level_decision_block(lib: HooksLibrary) -> None:
    config = {"PostToolUse": [{"type": "command", "matcher": "*", "command": _cmd("decision_block_json.py")}]}
    report = lib.fire_hook_event(config, "PostToolUse", tool_name="Bash")
    lib.decision_should_be(report, "block")


# --------------------------------------------------------------------------- #
# HEADLINE: block-on-dangerous-bash end-to-end
# --------------------------------------------------------------------------- #


def test_headline_block_dangerous_bash(lib: HooksLibrary) -> None:
    """The differentiating capability: a real PreToolUse hook blocks `rm -rf`."""
    config = _config(
        {"type": "command", "matcher": "Bash", "command": _cmd("block_dangerous_bash.py")}
    )

    # Dangerous command → BLOCK (exit 2).
    dangerous = lib.fire_hook_event(
        config, "PreToolUse", tool_name="Bash", tool_input={"command": "rm -rf /"}
    )
    lib.decision_should_be(dangerous, "block")
    lib.exit_code_should_be(dangerous, 2)

    # Safe command → ALLOW/none (exit 0).
    safe = lib.fire_hook_event(
        config, "PreToolUse", tool_name="Bash", tool_input={"command": "ls -la"}
    )
    lib.decision_should_be(safe, "none")
    lib.exit_code_should_be(safe, 0)


# --------------------------------------------------------------------------- #
# Security regressions (Codex security review 2026-07-09)
# --------------------------------------------------------------------------- #


def test_safe_search_redos_pattern_raises_fast_not_hangs() -> None:
    """HIGH: a catastrophic-backtracking matcher is interrupted, not hung."""
    import time

    start = time.monotonic()
    with pytest.raises(HookExecutionError) as exc:
        safe_search("(a+)+$", "a" * 28 + "!", timeout_s=0.5)
    elapsed = time.monotonic() - start
    # Un-guarded, `re.search` would spin for many seconds; the guard must trip
    # in ~timeout_s, well under a couple of seconds.
    assert elapsed < 3.0
    assert "(a+)+$" in str(exc.value)


def test_safe_search_rejects_overlong_subject() -> None:
    with pytest.raises(HookExecutionError) as exc:
        safe_search("mcp__.*", "x" * 5000)
    assert "cap" in str(exc.value)


def test_fire_redos_matcher_raises_fast_before_subprocess(lib: HooksLibrary) -> None:
    """HIGH: `Fire Hook Event` matcher resolution can't hang on a ReDoS matcher."""
    import time

    config = _config({"type": "command", "matcher": "(a+)+$", "command": _cmd("exit_zero.py")})
    start = time.monotonic()
    with pytest.raises(HookExecutionError):
        # Route through the runner's matcher guard via a monkeypatched short timeout.
        import AgentEval.hooks._matcher as matcher_mod

        original = matcher_mod._MATCHER_SEARCH_TIMEOUT_S
        matcher_mod._MATCHER_SEARCH_TIMEOUT_S = 0.5
        try:
            lib.fire_hook_event(config, "PreToolUse", tool_name="a" * 28 + "!")
        finally:
            matcher_mod._MATCHER_SEARCH_TIMEOUT_S = original
    assert time.monotonic() - start < 3.0


def test_validate_matcher_syntax_redos_subject_raises_fast(lib: HooksLibrary) -> None:
    """HIGH: the optional subject match in Validate Matcher Syntax is guarded too."""
    import time

    import AgentEval.hooks._matcher as matcher_mod

    original = matcher_mod._MATCHER_SEARCH_TIMEOUT_S
    matcher_mod._MATCHER_SEARCH_TIMEOUT_S = 0.5
    start = time.monotonic()
    try:
        with pytest.raises(HookExecutionError):
            lib.validate_matcher_syntax("(a+)+$", subject="a" * 28 + "!")
    finally:
        matcher_mod._MATCHER_SEARCH_TIMEOUT_S = original
    assert time.monotonic() - start < 3.0


def test_build_env_drops_lc_prefixed_secret_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """MED: secret-bearing `LC_*` names must NOT leak into the default-deny env."""
    monkeypatch.setenv("LC_SECRET_TOKEN", "lc-secret")
    monkeypatch.setenv("LC_AWS_SECRET_ACCESS_KEY", "lc-aws-secret")
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")  # a real locale var still passes through
    env = build_hook_env(project_dir="/tmp/p")
    assert "LC_SECRET_TOKEN" not in env
    assert "LC_AWS_SECRET_ACCESS_KEY" not in env
    assert env["LC_ALL"] == "en_US.UTF-8"


def test_fire_env_drops_lc_prefixed_secret_end_to_end(
    lib: HooksLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MED: a fired hook must not see an `LC_`-prefixed secret in its os.environ."""
    monkeypatch.setenv("LC_SECRET_TOKEN", "lc-secret")
    monkeypatch.setenv("LC_AWS_SECRET_ACCESS_KEY", "lc-aws-secret")
    config = _config({"type": "command", "matcher": "*", "command": _cmd("echo_env.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    child_env = report.results[0].stdout_json["env"]  # type: ignore[index]
    assert "LC_SECRET_TOKEN" not in child_env
    assert "LC_AWS_SECRET_ACCESS_KEY" not in child_env


def test_fire_invalid_utf8_output_records_not_crashes(lib: HooksLibrary) -> None:
    """LOW: a hook writing invalid UTF-8 is recorded with replacement chars, not a crash."""
    config = _config({"type": "command", "matcher": "*", "command": _cmd("invalid_utf8_stdout.py")})
    report = lib.fire_hook_event(config, "PreToolUse", tool_name="Bash")
    rec = report.results[0]
    assert rec.status == "completed"
    assert rec.exit_code == 0
    assert "�" in rec.stdout  # U+FFFD replacement character


# --------------------------------------------------------------------------- #
# Tier annotations
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method_name",
    [
        "fire_hook_event",
        "decision_should_be",
        "exit_code_should_be",
        "output_field_should_be",
        "get_hooks_for_event",
        "validate_matcher_syntax",
        "command_should_exist",
    ],
)
def test_new_keywords_are_tier_1(method_name: str) -> None:
    method = getattr(HooksLibrary, method_name)
    assert get_keyword_tier(method) == 1
