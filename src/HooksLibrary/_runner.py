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

"""Hook subprocess runner, result records, and decision normalization.

These functions EXECUTE USER-AUTHORED HOOK SCRIPTS LOCALLY with your
privileges. The sanitization here (default-deny env allowlist, no parent-secret
inheritance, hard timeout, process-group kill) LIMITS LEAKAGE - it is NOT a
sandbox. Only fire configs whose hook commands you trust to run on your machine.

- Sanitized, default-deny environment: the parent env is not inherited by
  default. Hook subprocesses get one explicit allowlist plus
  ``CLAUDE_PROJECT_DIR`` and any caller ``extra_env``. ``inherit_env=True`` is
  an explicit opt-in.
- Enforced timeout: the entry's ``timeout`` when set, else ``default_timeout``
  (30 s - far below Claude Code's 600 s so a test suite can't hang).
- Process-group isolation: spawned with ``start_new_session=True``; on timeout
  the hook's own process group is killed. A descendant that starts a new session
  before the timeout escapes the group (non-sandbox limitation).
- A bare ``command`` string runs through the shell; a ``command`` + ``args``
  array runs in exec form. The synthetic payload is passed on stdin, never
  interpolated into the command line.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ENV_ALLOWLIST",
    "FireReport",
    "HookResult",
    "build_hook_env",
    "normalize_decision",
    "run_command_hook",
]

# Single default-deny env allowlist: the only parent variables a hook
# subprocess sees. Common process vars plus the POSIX locale categories -
# nothing secret-bearing is on this list, so no separate deny filter is needed.
ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH",
    "HOME",
    "LANG",
    "TMPDIR",
    "USER",
    "SHELL",
    "LC_ALL",
    "LC_COLLATE",
    "LC_CTYPE",
    "LC_MESSAGES",
    "LC_MONETARY",
    "LC_NUMERIC",
    "LC_TIME",
)

# Decision vocabulary produced by `normalize_decision`.
_PERMISSION_DECISION_MAP: dict[str, str] = {
    "deny": "block",
    "allow": "allow",
    "ask": "ask",
    "defer": "none",
}


@dataclass(frozen=True)
class HookResult:
    """One per-hook execution record.

    ``status`` is ``"completed"`` (ran to completion, any exit code),
    ``"timed_out"`` (killed after the timeout; ``exit_code`` is ``None``),
    ``"spawn_failed"`` (could not launch; ``exit_code`` is ``None``,
    ``stderr`` carries the OS error), or ``"skipped"`` (a matching non-command
    hook; ``skip_reason`` names the type). ``decision`` is the normalized
    block/allow/ask/none decision (meaningful only for ``completed`` records).
    ``error_status`` is ``"nonblocking_error"`` when a completed hook exited
    with a code other than 0 or 2.
    """

    type: str
    matcher: str | None
    command: str | None
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_json: dict[str, Any] | None
    duration: float
    decision: str
    error_status: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class FireReport:
    """Report from `Fire Hook Event` - one record per matching hook.

    ``results`` preserves configured source order. Non-matching hooks are
    omitted; matching non-command hooks appear as ``skipped`` records.
    """

    event: str
    subject: str
    payload: dict[str, Any]
    results: tuple[HookResult, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.results)


def normalize_decision(exit_code: int | None, stdout_json: dict[str, Any] | None) -> tuple[str, str | None]:
    """Derive ``(decision, error_status)`` from the protocol's three channels.

    Precedence: exit ``2`` blocks (stdout JSON ignored); exit ``0`` +
    ``hookSpecificOutput.permissionDecision`` (``deny``->``block``,
    ``allow``->``allow``, ``ask``->``ask``, ``defer``->``none``); exit ``0`` +
    top-level ``decision: "block"`` blocks; exit ``0`` with no decision JSON is
    ``none``; any other exit code is ``none`` + ``"nonblocking_error"``.
    """
    if exit_code == 2:
        return "block", None
    if exit_code == 0:
        if isinstance(stdout_json, dict):
            hook_specific = stdout_json.get("hookSpecificOutput")
            if isinstance(hook_specific, dict) and "permissionDecision" in hook_specific:
                raw = hook_specific.get("permissionDecision")
                if isinstance(raw, str):
                    return _PERMISSION_DECISION_MAP.get(raw, "none"), None
                return "none", None
            if stdout_json.get("decision") == "block":
                return "block", None
        return "none", None
    return "none", "nonblocking_error"


def build_hook_env(
    *,
    project_dir: str,
    extra_env: dict[str, str] | None = None,
    inherit_env: bool = False,
) -> dict[str, str]:
    """Build the sanitized subprocess environment.

    Default-deny: only ``ENV_ALLOWLIST`` variables are copied from the parent
    env, plus ``CLAUDE_PROJECT_DIR``, ``CLAUDE_PLUGIN_ROOT`` (when set in the
    parent env - Claude Code *plugin* hook commands reference it), and any
    ``extra_env``. ``inherit_env=True`` starts from a full copy of the parent
    env instead (explicit opt-in). Values are read via ``os.environ`` and never
    logged.
    """
    if inherit_env:
        env: dict[str, str] = dict(os.environ)
    else:
        env = {}
        for key in ENV_ALLOWLIST:
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
    env["CLAUDE_PROJECT_DIR"] = project_dir
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    return env


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    """SIGKILL the child's process group; suppress races."""
    with contextlib.suppress(OSError, ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        proc.wait(timeout=5.0)


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Parse stdout as a JSON object, or ``None`` if it isn't one."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def run_command_hook(
    entry: dict[str, Any],
    *,
    stdin_payload: str,
    effective_timeout: float,
    env: dict[str, str],
    cwd: str,
) -> HookResult:
    """Execute one ``type: "command"`` hook entry, capturing its result.

    A bare ``command`` string runs through the shell; a ``command`` + ``args``
    array runs in exec form. The synthetic ``stdin_payload`` JSON is written to
    the child's stdin. Execution failures are recorded (``timed_out`` /
    ``spawn_failed``), never raised.
    """
    command = entry["command"]
    matcher = entry.get("matcher")
    args = entry.get("args")
    use_shell = not args
    args_list: list[str] = list(args) if args else []
    popen_target: str | list[str] = command if use_shell else [command, *args_list]

    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            popen_target,
            shell=use_shell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",  # a hook writing invalid UTF-8 must not crash the parent
            env=env,
            cwd=cwd,
            start_new_session=True,  # own process group -> clean group-kill on timeout
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return HookResult(
            type="command",
            matcher=matcher,
            command=command,
            status="spawn_failed",
            exit_code=None,
            stdout="",
            stderr=str(exc),
            stdout_json=None,
            duration=time.monotonic() - start,
            decision="none",
            error_status="spawn_failed",
        )

    try:
        stdout, stderr = proc.communicate(input=stdin_payload, timeout=effective_timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        with contextlib.suppress(Exception):
            stdout, stderr = proc.communicate(timeout=5.0)
        return HookResult(
            type="command",
            matcher=matcher,
            command=command,
            status="timed_out",
            exit_code=None,
            stdout="",
            stderr=f"hook timed out after {effective_timeout}s (effective timeout).",
            stdout_json=None,
            duration=time.monotonic() - start,
            decision="none",
            error_status="timed_out",
        )

    duration = time.monotonic() - start
    exit_code = proc.returncode
    # Per protocol, exit code 2 ignores stdout JSON - only parse it otherwise so
    # a stray `allow` on stdout can never leak into a blocking result.
    stdout_json = _try_parse_json(stdout) if exit_code != 2 else None
    decision, error_status = normalize_decision(exit_code, stdout_json)
    return HookResult(
        type="command",
        matcher=matcher,
        command=command,
        status="completed",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        stdout_json=stdout_json,
        duration=duration,
        decision=decision,
        error_status=error_status,
    )
