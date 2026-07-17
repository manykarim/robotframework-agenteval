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

"""Test Claude Code hooks - parse, simulate, and execute hook configs.

Every keyword is Tier-1 (deterministic): hook outputs are deterministic local
programs, so this library needs no LLM or MCP dependency and runs on the base
install. Parse a config with `Hook.Get Config`, ask `Hook.Get Hooks For Event`
which hooks would fire, then `Hook.Fire Hook Event` to actually run them and
assert on the normalized decision, exit code, and output fields.

    *** Settings ***
    Library    HooksLibrary

    *** Test Cases ***
    Dangerous Bash Is Blocked
        ${config}=    Hook.Get Config    ${CURDIR}/.claude/settings.json
        ${report}=    Hook.Fire Hook Event    ${config}    PreToolUse    tool_name=Bash
        Hook.Decision Should Be    ${report}    block
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._core import HookExecutionError, tier
from HooksLibrary._matcher import (
    MATCHER_ENGINE_NOTE,
    matcher_matches,
    validate_matcher,
)
from HooksLibrary._parser import parse_hook_config, validate_event_name
from HooksLibrary._payload import synthesize_payload
from HooksLibrary._runner import (
    FireReport,
    HookResult,
    build_hook_env,
    run_command_hook,
)

__all__ = ["HooksLibrary"]

# Normalized decision vocabulary. `deny` is accepted at the assertion boundary
# as an alias of `block`.
_VALID_DECISIONS: frozenset[str] = frozenset({"block", "allow", "ask", "none"})


class HooksLibrary:
    """Parse, simulate, and execute Claude Code hook configs [Tier 1 - Deterministic]."""

    # ----------------------------------------------------------------- #
    # Internal helpers (not keywords)
    # ----------------------------------------------------------------- #

    @staticmethod
    def _require_config(config: Any) -> dict[str, list[dict[str, Any]]]:
        """Narrow + validate the parsed-config object passed to a keyword."""
        if not isinstance(config, dict):
            raise HookExecutionError(
                f"Parsed hook config must be a dict keyed by event name; got {type(config).__name__}. "
                "Pass the object returned by `Hook.Get Config`, not a settings.json path."
            )
        return config

    @staticmethod
    def _resolve_subject(payload: dict[str, Any] | None, event_fields: dict[str, Any]) -> str:
        """Derive the matcher subject (tool name) from override or event fields."""
        if payload is not None and "tool_name" in payload:
            return str(payload["tool_name"])
        if "tool_name" in event_fields:
            return str(event_fields["tool_name"])
        return ""

    @staticmethod
    def _effective_timeout(entry: dict[str, Any], default_timeout: float) -> float:
        """Entry ``timeout`` (int seconds, not bool) if set, else the keyword default."""
        raw = entry.get("timeout")
        if isinstance(raw, bool):
            return float(default_timeout)
        if isinstance(raw, int):
            return float(raw)
        return float(default_timeout)

    @staticmethod
    def _matcher_matches_safe(matcher: str | None, subject: str) -> bool:
        """Matcher match that treats an uncompilable regex as a non-match.

        The live runner must not crash the whole fire because one matcher is a
        bad regex - `Hook.Validate Matcher Syntax` is the loud pre-flight.
        """
        try:
            return matcher_matches(matcher, subject)
        except re.error:
            return False

    @staticmethod
    def _coerce_record(result: Any) -> HookResult:
        """Coerce a `Fire Hook Event` report OR a single record into one record.

        A report with exactly one record yields that record; a report with 0 or
        >1 records fails loud, telling the caller to index into
        ``${report.results}`` so an assertion can target the intended hook.
        """
        if isinstance(result, HookResult):
            return result
        if isinstance(result, FireReport):
            if len(result.results) == 1:
                return result.results[0]
            raise AssertionError(
                f"hook report for event {result.event!r} holds {len(result.results)} records; "
                "index into `${report.results}` and pass a single record to the assertion."
            )
        raise TypeError(
            f"expected a `Hook.Fire Hook Event` report or a single hook record; got {type(result).__name__}."
        )

    # ----------------------------------------------------------------- #
    # Keywords
    # ----------------------------------------------------------------- #

    @keyword(name="Hook.Get Config")
    @tier(1)
    def get_config(self, path: str | Path) -> dict[str, list[dict[str, Any]]]:
        """Parses a Claude Code ``settings.json`` hook configuration.

        [Tier 1 - Deterministic] Reads the file, parses the JSON, and validates
        each entry. Accepts the nested Claude Code schema: a top-level ``hooks``
        mapping from event name to a list of matcher groups, each group carrying
        an optional ``matcher`` and a required ``hooks`` list of typed
        definitions.

        Returns a dict keyed by plain event name (``PreToolUse``, ...). Matcher
        groups are flattened - each inner definition becomes one entry with the
        group's ``matcher`` copied onto it, preserving source order. A file
        without a top-level ``hooks`` field returns ``{}``.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the ``settings.json`` file (``str`` or ``pathlib.Path``). |

        Raises ``InvalidConfigError`` on any structural failure; its ``field``
        carries an RFC 6901 JSON Pointer to the offending location.

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | Length Should Be    ${config}[PreToolUse]    1
        | Should Be Equal    ${config}[PreToolUse][0][type]    command
        """
        return parse_hook_config(path)

    @keyword(name="Hook.Fire Hook Event")
    @tier(1)
    def fire_hook_event(
        self,
        config: dict[str, list[dict[str, Any]]],
        event: str,
        project_dir: str | None = None,
        default_timeout: float = 30,
        inherit_env: bool = False,
        extra_env: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        **event_fields: Any,
    ) -> FireReport:
        """Fires a synthetic hook event and EXECUTES every matching command hook.

        [Tier 1 - Deterministic] Hook scripts are deterministic local programs;
        executing them involves no LLM and needs no API keys.

        *SECURITY: this keyword runs USER-AUTHORED HOOK SCRIPTS LOCALLY* with
        your privileges. The subprocess environment is sanitized (a default-deny
        allowlist plus ``CLAUDE_PROJECT_DIR``; parent secrets are not inherited),
        a hard timeout is enforced, and on timeout the hook's own process group
        is killed - but this LIMITS LEAKAGE, it is NOT a sandbox. Only fire
        configs whose commands you trust.

        Synthesizes the Claude Code stdin JSON for the event, then runs each
        configured ``type: "command"`` hook whose matcher matches the subject
        (the ``tool_name``). A bare ``command`` runs through the shell; a
        ``command`` + ``args`` array runs in exec form.

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config`` (not a path). |
        | ``event`` | An event in ``SUPPORTED_EVENTS``; an unknown name raises ``InvalidConfigError``. |
        | ``project_dir`` | Value for ``CLAUDE_PROJECT_DIR`` + the subprocess cwd. Defaults to the test's cwd. |
        | ``default_timeout`` | Per-hook timeout (s) when the entry has no ``timeout``. Default 30. |
        | ``inherit_env`` | ``True`` inherits the full parent env (opt-in). Default ``False``. |
        | ``extra_env`` | Optional dict of extra env vars for the hook subprocess. |
        | ``payload`` | Full-override dict for the event-specific fields (common fields fill gaps). |
        | ``**event_fields`` | Event-specific fields (``tool_name=Bash``, ``tool_input=${dict}``, ...). |

        Returns a report with one frozen record per matching hook (``.results``).
        Each record carries ``status``, ``exit_code``, ``stdout``, ``stderr``,
        ``stdout_json``, ``duration``, and the normalized ``decision``. Execution
        failures are recorded, not raised. Matching non-command hooks appear as
        ``skipped`` records.

        Raises ``InvalidConfigError`` when ``event`` is not a recognized Claude
        Code hook event (a typo like ``PostToolusage`` would otherwise read as
        "no hooks fire"). Raises ``HookExecutionError`` when zero configured
        hooks match (an empty report would let a decision assertion silently
        never run).

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Decision Should Be`    ${report}    block
        """
        config = self._require_config(config)
        validate_event_name(event)
        entries = config.get(event, [])
        subject = self._resolve_subject(payload, event_fields)

        matched = [entry for entry in entries if self._matcher_matches_safe(entry.get("matcher"), subject)]
        if not matched:
            raise HookExecutionError(
                f"No configured hook for event {event!r} matches subject {subject!r} "
                f"(config has {len(entries)} hook(s) for this event). Call `Hook.Get Hooks For Event` "
                "with the same event + tool_name to see which hooks would fire."
            )

        resolved_project_dir = project_dir if project_dir is not None else os.getcwd()
        transcript_path = os.path.join(tempfile.gettempdir(), "agenteval-hooks", "synthetic-transcript.jsonl")
        payload_dict = synthesize_payload(
            event,
            cwd=resolved_project_dir,
            transcript_path=transcript_path,
            payload=payload,
            event_fields=event_fields,
        )
        stdin_payload = json.dumps(payload_dict)
        env = build_hook_env(project_dir=resolved_project_dir, extra_env=extra_env, inherit_env=inherit_env)

        results: list[HookResult] = []
        for entry in matched:
            hook_type = entry.get("type")
            if hook_type != "command":
                results.append(
                    HookResult(
                        type=str(hook_type),
                        matcher=entry.get("matcher"),
                        command=entry.get("command"),
                        status="skipped",
                        exit_code=None,
                        stdout="",
                        stderr="",
                        stdout_json=None,
                        duration=0.0,
                        decision="none",
                        skip_reason=f"type={hook_type!r} is not a locally executable command hook",
                    )
                )
                continue
            results.append(
                run_command_hook(
                    entry,
                    stdin_payload=stdin_payload,
                    effective_timeout=self._effective_timeout(entry, default_timeout),
                    env=env,
                    cwd=resolved_project_dir,
                )
            )

        return FireReport(event=event, subject=subject, payload=payload_dict, results=tuple(results))

    @keyword(name="Hook.Decision Should Be")
    @tier(1)
    def decision_should_be(self, result: Any, expected: str) -> None:
        """Asserts a fired hook's normalized block/allow/ask/none decision.

        [Tier 1 - Deterministic] A pure comparison over a captured record.

        Accepts a ``Hook.Fire Hook Event`` report (with exactly one record) or a
        single hook record. ``deny`` is accepted as an alias of ``block``. Fails
        loud when the target record's status is not ``completed`` (e.g.
        ``timed_out``), naming the status rather than reporting a stale decision.

        | =Arguments= | =Description= |
        | ``result`` | A ``Hook.Fire Hook Event`` report (single record) or one hook record. |
        | ``expected`` | ``block`` / ``allow`` / ``ask`` / ``none`` (``deny`` aliases ``block``). |

        Example:
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Decision Should Be`    ${report}    block
        """
        record = self._coerce_record(result)
        want = "block" if str(expected).lower() == "deny" else str(expected).lower()
        if want not in _VALID_DECISIONS:
            raise ValueError(
                f"expected decision {expected!r} is not one of {sorted(_VALID_DECISIONS)} "
                "(or the `deny` alias of `block`)."
            )
        if record.status != "completed":
            raise AssertionError(
                f"cannot assert hook decision: record status is {record.status!r} (not 'completed'); "
                f"stderr: {record.stderr!r}"
            )
        if record.decision != want:
            raise AssertionError(
                f"expected hook decision {expected!r} (normalized {want!r}) but got {record.decision!r} "
                f"(exit_code={record.exit_code}, stdout_json={record.stdout_json!r})."
            )

    @keyword(name="Hook.Exit Code Should Be")
    @tier(1)
    def exit_code_should_be(self, result: Any, expected: int) -> None:
        """Asserts a fired hook's raw subprocess exit code.

        [Tier 1 - Deterministic] A pure comparison over a captured record.

        Fails loud when the record's status is not ``completed`` (a
        ``timed_out`` / ``spawn_failed`` hook has no exit code to compare).

        | =Arguments= | =Description= |
        | ``result`` | A ``Hook.Fire Hook Event`` report (single record) or one hook record. |
        | ``expected`` | The expected integer exit code (``0`` allow, ``2`` block, ...). |

        Example:
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Exit Code Should Be`    ${report}    2
        """
        record = self._coerce_record(result)
        if record.status != "completed":
            raise AssertionError(
                f"cannot assert exit code: record status is {record.status!r} (not 'completed'); "
                f"stderr: {record.stderr!r}"
            )
        expected_int = int(expected)
        if record.exit_code != expected_int:
            raise AssertionError(f"expected hook exit code {expected_int} but got {record.exit_code}.")

    @keyword(name="Hook.Output Field Should Be")
    @tier(1)
    def output_field_should_be(self, result: Any, field_path: str, expected: Any) -> None:
        """Asserts a dotted field in a fired hook's parsed stdout JSON.

        [Tier 1 - Deterministic] A pure navigation + comparison over a record.

        Navigates the record's ``stdout_json`` by a dotted path (e.g.
        ``hookSpecificOutput.permissionDecision``) and compares the value's
        string form to ``expected``. Fails loud when the record is not
        ``completed`` or produced no stdout JSON.

        | =Arguments= | =Description= |
        | ``result`` | A ``Hook.Fire Hook Event`` report (single record) or one hook record. |
        | ``field_path`` | Dotted path into the stdout JSON (e.g. ``hookSpecificOutput.permissionDecision``). |
        | ``expected`` | Expected value (compared by string form). |

        Example:
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Output Field Should Be`    ${report}    hookSpecificOutput.permissionDecision    deny
        """
        record = self._coerce_record(result)
        if record.status != "completed":
            raise AssertionError(f"cannot assert output field: record status is {record.status!r} (not 'completed').")
        if record.stdout_json is None:
            raise AssertionError(
                f"cannot assert output field {field_path!r}: the hook produced no parseable stdout JSON "
                f"(exit_code={record.exit_code}; raw stdout: {record.stdout!r})."
            )
        value: Any = record.stdout_json
        for segment in field_path.split("."):
            if not isinstance(value, dict) or segment not in value:
                raise AssertionError(
                    f"stdout JSON has no field {field_path!r} (failed at segment {segment!r}); "
                    f"available JSON: {record.stdout_json!r}."
                )
            value = value[segment]
        if str(value) != str(expected):
            raise AssertionError(f"expected stdout JSON field {field_path!r} to be {expected!r} but got {value!r}.")

    @keyword(name="Hook.Get Hooks For Event")
    @tier(1)
    def get_hooks_for_event(
        self,
        config: dict[str, list[dict[str, Any]]],
        event: str,
        tool_name: str = "",
    ) -> list[dict[str, Any]]:
        """Returns which configured hooks would fire - statically, no execution.

        [Tier 1 - Deterministic] A pure static analysis; spawns no subprocess.

        Uses the SAME matcher engine as ``Hook.Fire Hook Event``, so the static
        simulation and live execution can never disagree about which hooks match
        a given event + tool name.

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config``. |
        | ``event`` | The event name to simulate (e.g. ``PreToolUse``). |
        | ``tool_name`` | The matcher subject (tool name). Empty matches only match-all matchers. |

        Returns the configured hook entries (source order) whose matcher matches
        ``tool_name`` - including non-command entries, which ``Hook.Fire Hook
        Event`` would report as ``skipped``. A recognized event with no hooks
        configured returns an empty list; an *unknown* event name (a typo like
        ``PostToolusage``) raises ``InvalidConfigError`` rather than returning an
        empty list that reads as "no hooks fire".

        Example:
        | ${hooks} =    `Hook.Get Hooks For Event`    ${config}    PreToolUse    tool_name=Bash
        | Length Should Be    ${hooks}    1
        """
        config = self._require_config(config)
        validate_event_name(event)
        entries = config.get(event, [])
        return [entry for entry in entries if self._matcher_matches_safe(entry.get("matcher"), tool_name)]

    @keyword(name="Hook.Validate Matcher Syntax")
    @tier(1)
    def validate_matcher_syntax(self, matcher: str | None, subject: str | None = None) -> bool:
        """Validates a matcher compiles, optionally reporting whether it matches a subject.

        [Tier 1 - Deterministic] A static compile check; executes nothing.

        Checks the matcher under the engine's dispatch rules (``*``/empty
        match-all; simple ``|``/``,`` list; otherwise a Python regex). Fails loud
        on a regex that will not compile, naming the offending pattern. When a
        ``subject`` is supplied and the matcher is valid, returns whether the
        matcher matches that subject.

        | =Arguments= | =Description= |
        | ``matcher`` | The matcher string to validate (``None`` / ``""`` / ``*`` are match-all). |
        | ``subject`` | Optional tool name to test the matcher against. |

        Returns ``True`` when the matcher is valid and no subject was supplied;
        otherwise the boolean subject-match result.

        Example:
        | ${matches} =    `Hook.Validate Matcher Syntax`    Bash|Edit    subject=Edit
        | Should Be True    ${matches}
        """
        outcome = validate_matcher(matcher, subject)
        if not outcome.valid:
            raise AssertionError(f"{outcome.error} {MATCHER_ENGINE_NOTE}")
        if subject is not None:
            return bool(outcome.subject_matches)
        return True

    @keyword(name="Hook.Command Should Exist")
    @tier(1)
    def command_should_exist(
        self,
        config: dict[str, list[dict[str, Any]]],
        event: str | None = None,
        project_dir: str | None = None,
    ) -> None:
        """Asserts each configured hook command resolves to an executable on disk.

        [Tier 1 - Deterministic] A static path/``PATH`` resolution; executes
        nothing.

        For each ``type: "command"`` hook (optionally scoped to one ``event``),
        resolves the interpreter (the first ``shlex``-split token of the
        ``command`` string, or the ``command`` itself in exec form) via
        ``shutil.which`` or a path-existence-plus-executable-bit check. When the
        command names a *target script* (a path-bearing argument such as
        ``node "${CLAUDE_PLUGIN_ROOT}/scripts/x.mjs"`` or an exec-form ``args``
        entry), that script's existence on disk is ALSO verified - so a hook
        whose interpreter is installed but whose script is missing still fails.

        Environment references are expanded first: ``$CLAUDE_PROJECT_DIR`` /
        ``${CLAUDE_PROJECT_DIR}`` resolve against ``project_dir``; every other
        ``$VAR`` / ``${VAR}`` (notably ``${CLAUDE_PLUGIN_ROOT}`` used by Claude
        Code *plugin* hook configs) resolves from ``os.environ``. When a
        variable needed to resolve a script path is unset, the check FAILS and
        names that variable rather than passing vacuously.

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config``. |
        | ``event`` | Optional event name to scope the check. When ``None``, checks every event. |
        | ``project_dir`` | Value substituted for ``$CLAUDE_PROJECT_DIR``. Defaults to the test's cwd. |

        Fails, naming every unresolved command, when an interpreter cannot be
        resolved to an executable, a target script does not exist, or an env var
        needed to resolve a script path is unset.

        Example:
        | `Hook.Command Should Exist`    ${config}
        | `Hook.Command Should Exist`    ${config}    event=PreToolUse
        """
        config = self._require_config(config)
        resolved_project_dir = project_dir if project_dir is not None else os.getcwd()
        events = [event] if event is not None else list(config.keys())

        unresolved: list[str] = []
        for ev in events:
            for entry in config.get(ev, []):
                if entry.get("type") != "command":
                    continue
                command = entry.get("command")
                if not isinstance(command, str) or not command:
                    continue
                if entry.get("args"):
                    interpreter = command  # exec form: command is the executable
                    rest = [str(arg) for arg in entry["args"]]
                else:
                    split = shlex.split(command)
                    if not split:
                        continue
                    interpreter = split[0]
                    rest = split[1:]

                problem = self._resolve_command_problem(interpreter, rest, resolved_project_dir)
                if problem is not None:
                    unresolved.append(f"{ev}: {command!r} ({problem})")

        if unresolved:
            raise AssertionError(
                "hook command(s) did not resolve to an executable before a live session depends on them:\n  "
                + "\n  ".join(unresolved)
            )

    @classmethod
    def _resolve_command_problem(cls, interpreter: str, rest: list[str], project_dir: str) -> str | None:
        """Return a human-readable problem string, or ``None`` when the command resolves.

        Resolves the interpreter on PATH/disk (after env expansion) and, when a
        path-bearing target script is present, verifies it exists on disk.
        """
        interp_expanded, interp_unset = cls._expand_env_vars(interpreter, project_dir)
        if interp_unset:
            return f"interpreter {interpreter!r} references unset env var(s): {cls._name_vars(interp_unset)}"
        if not cls._command_resolves(interp_expanded):
            return f"first token {interp_expanded!r} not found on PATH or disk"

        script_token = cls._find_script_token(rest, project_dir)
        if script_token is None:
            return None
        script_expanded, script_unset = cls._expand_env_vars(script_token, project_dir)
        if script_unset:
            return (
                f"target script {script_token!r} cannot be resolved; unset env var(s): {cls._name_vars(script_unset)}"
            )
        if not Path(script_expanded).exists():
            return f"target script {script_expanded!r} does not exist on disk"
        return None

    # Matches a ``${VAR}`` or ``$VAR`` environment reference.
    _ENV_VAR_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")

    @classmethod
    def _expand_env_vars(cls, token: str, project_dir: str) -> tuple[str, list[str]]:
        """Expand ``$VAR`` / ``${VAR}`` references, returning ``(expanded, unset_vars)``.

        ``CLAUDE_PROJECT_DIR`` resolves against ``project_dir`` (falling back to
        ``os.environ``); every other variable (e.g. ``CLAUDE_PLUGIN_ROOT``)
        resolves from ``os.environ``. Names with no value are left literal and
        collected so the caller can fail loud instead of passing vacuously.
        """
        unset: list[str] = []

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1) or match.group(2)
            if name == "CLAUDE_PROJECT_DIR":
                value: str | None = project_dir if project_dir is not None else os.environ.get(name)
            else:
                value = os.environ.get(name)
            if value is None:
                if name not in unset:
                    unset.append(name)
                return match.group(0)
            return value

        return cls._ENV_VAR_RE.sub(_replace, token), unset

    @classmethod
    def _find_script_token(cls, rest: list[str], project_dir: str) -> str | None:
        """Return the first path-bearing (non-flag) argument, or ``None``.

        A token is path-bearing when, after env expansion, it contains a path
        separator - covering both literal paths and ``${VAR}/...`` references
        whose variable is unset (the literal ``${VAR}/`` still carries a ``/``,
        so the unresolved variable is surfaced rather than silently skipped).
        """
        for token in rest:
            if token.startswith("-"):
                continue
            expanded, _ = cls._expand_env_vars(token, project_dir)
            if "/" in expanded or os.sep in expanded:
                return token
        return None

    @staticmethod
    def _name_vars(names: list[str]) -> str:
        """Render env-var names as a ``$NAME`` comma-joined list for error messages."""
        return ", ".join(f"${name}" for name in names)

    @staticmethod
    def _command_resolves(token: str) -> bool:
        """Resolve a command token via ``shutil.which`` or a path+exec-bit check."""
        if not token:
            return False
        if shutil.which(token) is not None:
            return True
        candidate = Path(token)
        return candidate.exists() and os.access(candidate, os.X_OK)
