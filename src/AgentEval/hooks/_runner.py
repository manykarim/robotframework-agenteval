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

OpenSpec change `add-hooks-execution-testing`, design Decisions 3/4/6/7.

**Security posture (read this).** These functions EXECUTE USER-AUTHORED HOOK
SCRIPTS LOCALLY with the invoking user's privileges. Sanitization here
(default-deny env allowlist, no parent-secret inheritance, hard timeout,
process-group kill) LIMITS LEAKAGE — it is NOT a sandbox. Only fire configs
whose hook commands you trust to run on your machine.

Subprocess safety measures:

- **Sanitized, default-deny environment** (design Decision 6): the parent
  process env is NOT inherited by default. Hook subprocesses receive an
  explicit allowlist (``PATH`` / ``HOME`` / ``LANG`` / ``TMPDIR`` / ``USER`` /
  ``SHELL`` plus an enumerated locale set — ``LC_ALL`` / ``LC_CTYPE`` / ...,
  NOT an ``LC_*`` prefix wildcard) plus ``CLAUDE_PROJECT_DIR`` and any
  caller-supplied ``extra_env``, minus any allowlisted name that looks
  secret-bearing. The RF test process routinely holds provider API keys;
  handing them to a hook script under test violates the project key-hygiene
  norm. ``inherit_env=True`` is an explicit opt-in.
- **Enforced timeout** (design Decision 7): effective timeout = the entry's
  ``timeout`` field when set, else ``default_timeout`` (30 s default —
  deliberately far below Claude Code's 600 s so a test suite can't hang).
- **Process-group isolation (own process group ONLY)**: spawned with
  ``start_new_session=True``; on timeout the hook's OWN process group is killed
  (``SIGKILL``), so ordinary children that stay in that group die with it. This
  does NOT contain a descendant that starts a NEW session (``setsid`` / another
  ``start_new_session``) before the timeout — such a descendant leaves the
  killed group and can keep running after `Fire Hook Event` returns
  ``timed_out``. True descendant containment needs an OS primitive that spans
  sessions (Linux cgroup / job object); that is out of scope for the Phase-1
  non-sandbox posture (carry-over ``DF-HOOKS-S2`` in `docs/phase-1-5-carry-overs.md`).
- **No shell injection surface beyond the protocol's own**: a bare
  ``command`` string runs through the shell (protocol: hook commands ARE
  shell commands); a ``command`` + ``args`` array runs in exec form (no
  shell). The synthetic stdin payload is passed on the child's STDIN, never
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
    "HookResult",
    "FireReport",
    "ENV_ALLOWLIST",
    "LOCALE_ALLOWLIST",
    "normalize_decision",
    "build_hook_env",
    "run_command_hook",
]

# Default-deny env allowlist (design Decision 6).
ENV_ALLOWLIST: tuple[str, ...] = ("PATH", "HOME", "LANG", "TMPDIR", "USER", "SHELL")

# Explicit locale-variable allowlist (Codex security review MED, 2026-07-09).
# The former `LC_*` PREFIX rule copied ANY parent variable starting with `LC_`,
# leaking secret-bearing names like `LC_AWS_SECRET_ACCESS_KEY` / `LC_SECRET_TOKEN`
# into the hook subprocess even under default-deny. Enumerate the real POSIX
# locale categories instead — nothing outside this set is a locale variable.
LOCALE_ALLOWLIST: tuple[str, ...] = (
    "LC_ALL",
    "LC_COLLATE",
    "LC_CTYPE",
    "LC_MESSAGES",
    "LC_MONETARY",
    "LC_NUMERIC",
    "LC_TIME",
    "LC_PAPER",
    "LC_NAME",
    "LC_ADDRESS",
    "LC_TELEPHONE",
    "LC_MEASUREMENT",
    "LC_IDENTIFICATION",
)

# Defense-in-depth deny substrings: even an allowlisted name is dropped from the
# default-deny env if it looks secret-bearing (case-insensitive). Guards against
# a future allowlist entry — or a machine whose real `LC_*` locale var somehow
# collides with a secret naming convention — re-opening the leak.
_ENV_DENY_SUBSTRINGS: tuple[str, ...] = (
    "SECRET",
    "TOKEN",
    "KEY",
    "PASSWORD",
    "AWS",
    "ANTHROPIC",
    "OPENAI",
)


def _looks_secret_bearing(name: str) -> bool:
    """Return True if an env-var name contains a deny substring (case-insensitive)."""
    upper = name.upper()
    return any(marker in upper for marker in _ENV_DENY_SUBSTRINGS)

# Decision vocabulary produced by `normalize_decision`.
_PERMISSION_DECISION_MAP: dict[str, str] = {
    "deny": "block",
    "allow": "allow",
    "ask": "ask",
    "defer": "none",
}


@dataclass(frozen=True)
class HookResult:
    """One per-hook execution record (frozen; design Decision 4).

    ``status`` is one of:

    - ``"completed"`` — the command ran to completion (any exit code).
      ``exit_code`` / ``stdout`` / ``stderr`` / ``stdout_json`` / ``decision``
      are meaningful.
    - ``"timed_out"`` — killed after the effective timeout; ``exit_code`` is
      ``None``.
    - ``"spawn_failed"`` — the binary could not be launched (missing/not
      executable); ``exit_code`` is ``None`` and ``stderr`` carries the OS
      error.
    - ``"skipped"`` — a matching hook whose ``type`` is not ``command`` (e.g.
      ``http``); ``skip_reason`` names the unsupported type. Never executed.

    ``decision`` is the normalized block/allow/ask/none decision (only
    meaningful for ``completed`` records; ``"none"`` otherwise).
    ``error_status`` carries ``"nonblocking_error"`` when a completed hook
    exited with a code other than 0 or 2.
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
    """Report returned by `Fire Hook Event` — one record per matching hook.

    ``results`` preserves configured source order. Non-matching hooks are
    omitted entirely; matching non-``command`` hooks appear as ``skipped``
    records (design Decision 4).
    """

    event: str
    subject: str
    payload: dict[str, Any]
    results: tuple[HookResult, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.results)


def normalize_decision(exit_code: int | None, stdout_json: dict[str, Any] | None) -> tuple[str, str | None]:
    """Derive ``(decision, error_status)`` from the protocol's three channels.

    Precedence (design Decision 3 / spec "Normalized decision vocabulary"):

    1. exit code ``2`` → ``block`` (stdout JSON IGNORED, stderr is the message).
    2. exit ``0`` + ``hookSpecificOutput.permissionDecision``:
       ``deny``→``block``, ``allow``→``allow``, ``ask``→``ask``, ``defer``→``none``.
    3. exit ``0`` + top-level ``decision: "block"`` → ``block``.
    4. exit ``0`` with no decision-bearing JSON → ``none``.
    5. any other exit code → ``none`` with ``error_status="nonblocking_error"``.
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
    # Any other exit code (including None from a crash before wait, though the
    # runner routes timeouts/spawn-failures through dedicated statuses).
    return "none", "nonblocking_error"


def build_hook_env(
    *,
    project_dir: str,
    extra_env: dict[str, str] | None = None,
    inherit_env: bool = False,
) -> dict[str, str]:
    """Build the sanitized subprocess environment (design Decision 6).

    Default-deny: only the allowlisted variables are copied from the parent
    env, plus ``CLAUDE_PROJECT_DIR`` and any ``extra_env``. ``inherit_env=True``
    starts from a full copy of the parent env instead (explicit opt-in).

    Env values are read via ``os.environ.get`` and NEVER logged (project
    key-hygiene norm).
    """
    if inherit_env:
        env: dict[str, str] = dict(os.environ)
    else:
        env = {}
        for key in (*ENV_ALLOWLIST, *LOCALE_ALLOWLIST):
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
        # Defense-in-depth: drop any allowlisted name that looks secret-bearing
        # (Codex security review MED — see `LOCALE_ALLOWLIST`/`_ENV_DENY_SUBSTRINGS`).
        env = {key: value for key, value in env.items() if not _looks_secret_bearing(key)}
    env["CLAUDE_PROJECT_DIR"] = project_dir
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    return env


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    """SIGKILL the child's process group; suppress races (mirrors adapter cleanup)."""
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

    A bare ``command`` string runs through the shell (protocol: hook commands
    are shell commands). A ``command`` + ``args`` array runs in exec form (no
    shell). The synthetic ``stdin_payload`` JSON is written to the child's
    STDIN. Execution failures are RECORDED (``timed_out`` / ``spawn_failed``),
    never raised (design Decision 4).
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
            errors="replace",  # a hook writing invalid UTF-8 must not crash the parent (Codex LOW)
            env=env,
            cwd=cwd,
            start_new_session=True,  # own process group → clean group-kill on timeout
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
        # Drain any buffered output post-kill (best-effort; may be empty).
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
    # Per protocol, exit code 2 IGNORES stdout JSON — only parse it otherwise
    # so a stray `allow` on stdout can never leak into a blocking result.
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
