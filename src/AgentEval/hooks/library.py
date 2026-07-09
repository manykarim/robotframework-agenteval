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

"""Hook sub-library — parse, simulate, and EXECUTE Claude Code hook configs.

`Hook.Get Config` (Story 2.2; real-format rewrite 2026-07-08) parses a Claude
Code `settings.json` hook configuration into a dict mapping each PLAIN event
name (`PreToolUse`, ...) → list of normalized hook entries. Accepts the real
nested Claude Code schema (matcher groups of typed hook definitions) as
primary, and the deprecated legacy flat entry shape as an alias. Every entry
carries `type`, the group's `matcher` when present, and any optional fields
(`args` / `timeout` / ...). Inline-skill-frontmatter hooks surface as an extra
`inline_skill: dict` field on `command`-type entries.

The OpenSpec change `add-hooks-execution-testing` adds seven Tier-1 keywords
that turn a parsed config into a testable surface:

- `Hook.Fire Hook Event` — synthesize the real Claude Code stdin JSON payload
  for an event and EXECUTE every matching `type: "command"` hook as a
  subprocess, capturing exit code / stdout / stderr / parsed JSON / duration /
  normalized decision per hook.
- `Hook.Decision Should Be` — assert the normalized block/allow/ask/none
  decision (`deny` accepted as an alias of `block`).
- `Hook.Exit Code Should Be` / `Hook.Output Field Should Be` — assert raw
  exit-code and stdout-JSON fields.
- `Hook.Get Hooks For Event` — static "which hooks would fire for tool X?"
  simulation (no execution), sharing the matcher engine with the runner.
- `Hook.Validate Matcher Syntax` — matcher compile check + optional subject
  match, reporting the Python-`re`-vs-JS-RegExp divergence.
- `Hook.Command Should Exist` — resolve each hook command's first token on
  disk before a live session depends on it.

**SECURITY — these keywords EXECUTE USER-AUTHORED HOOK SCRIPTS LOCALLY** with
the invoking user's privileges. The runner sanitizes the subprocess
environment (default-deny allowlist, no parent-secret inheritance), enforces a
hard timeout far below Claude Code's 600 s, and kills the process group on
timeout — but this LIMITS LEAKAGE, it is NOT a sandbox. Only fire configs
whose hook commands you trust to run on your machine.

Each keyword bakes its `Hook.` namespace prefix into its `@keyword(name=...)`
value, so the call site is identical under the composed `Library AgentEval`
import and a standalone module-path import.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval

    *** Test Cases ***
    PreToolUse Has Audit Hook
        ${config}=    Hook.Get Config    .claude/settings.json
        Length Should Be    ${config}[PreToolUse]    1

Composition: registered in `AgentEval.__init__._SUB_LIBRARIES` so
`Library AgentEval` flattens the keyword into the parent namespace via
`robotlibcore.DynamicCore`. Do NOT add `WITH NAME Hook` to a standalone
import — RF would stack the name on top of the baked prefix
(`Hook.Hook.Get Config`); harmless but pointless.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.errors import HookExecutionError
from AgentEval.hooks._matcher import (
    MATCHER_ENGINE_NOTE,
    matcher_matches,
    validate_matcher,
)
from AgentEval.hooks._parser import parse_hook_config
from AgentEval.hooks._payload import synthesize_payload
from AgentEval.hooks._runner import (
    FireReport,
    HookResult,
    build_hook_env,
    run_command_hook,
)

__all__ = ["HooksLibrary"]

# Normalized decision vocabulary (design Decision 3). `deny` is accepted at the
# assertion boundary as an alias of `block`.
_VALID_DECISIONS: frozenset[str] = frozenset({"block", "allow", "ask", "none"})

# Browser-Library-style docstring migration marker (Phase 1, 2026-05-26).
# Read by `tests/unit/conventions/test_docstring_browser_style.py` +
# `test_docstring_examples_dryrun.py` to determine which libraries are
# subject to the Browser-style structure + example-dryrun enforcement.
# Derived-via-marker pattern adopted per Kilo Phase 1 review HIGH (Patch B);
# replaces the hardcoded `MIGRATED_LIBRARIES` allow-list that drifted as
# new libraries shipped.
_BROWSER_STYLE_MIGRATED = True


class HooksLibrary:
    """Parse, simulate, and execute Claude Code hook configs [Tier 1 — Deterministic]."""

    # ----------------------------------------------------------------- #
    # Internal helpers (not keywords)
    # ----------------------------------------------------------------- #

    @staticmethod
    def _require_config(config: Any) -> dict[str, list[dict[str, Any]]]:
        """Narrow + validate the parsed-config object passed to a keyword."""
        if not isinstance(config, dict):
            raise HookExecutionError(
                f"Parsed hook config must be a dict keyed by event name; got {type(config).__name__}.",
                fix_suggestion="Pass the object returned by `Hook.Get Config`, not a settings.json path.",
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
        """Entry `timeout` (int seconds, not bool) if set, else the keyword default."""
        raw = entry.get("timeout")
        if isinstance(raw, bool):
            return float(default_timeout)
        if isinstance(raw, int):
            return float(raw)
        return float(default_timeout)

    @staticmethod
    def _coerce_record(result: Any) -> HookResult:
        """Coerce a `Fire Hook Event` report OR a single record into one record.

        A `FireReport` with exactly one record yields that record; a report
        with 0 or >1 records fails loud, telling the caller to index into
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

    @keyword(name="Hook.Get Config")
    @tier(1)
    def get_config(self, path: str | Path) -> dict[str, list[dict[str, Any]]]:
        """Parses a Claude Code ``settings.json`` hook configuration.

        [Tier 1 — Deterministic] — pure file-read + JSON parse + per-entry
        validation. Accepts the REAL nested Claude Code schema (primary) and
        the DEPRECATED legacy flat shape (alias). Returns a dict mapping each
        PLAIN event name (``PreToolUse``, ``PostToolUse``, ``Stop``, and any
        other event such as ``SessionStart``) → list of normalized hook
        entries. Median ≤ 50 ms on typical hook configs per NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the ``settings.json`` file. Accepts ``str`` OR ``pathlib.Path``. |

        *Real (primary) input schema* — a top-level ``hooks`` mapping from
        event name to a list of matcher groups; each group has an optional
        ``matcher`` string and a required ``hooks`` list of typed hook
        definitions (``type`` one of ``command`` / ``http`` / ``mcp_tool`` /
        ``prompt`` / ``agent``)::

            {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}}

        *Legacy flat input (DEPRECATED)* — an event-array item that is itself
        a flat entry with a ``command`` key and no ``hooks`` list. Still
        accepted, but emits a single ``DeprecationWarning`` per parse call.

        *Normalized return shape* — matcher groups are FLATTENED: each inner
        hook definition becomes one entry, with the group's ``matcher`` (when
        present) copied onto it, preserving source order. Every returned entry
        carries a ``type`` field; keys the parser does not validate (``if``,
        ``async``, ``url``, ``server``, ``model``, future fields...) pass
        through unmodified. Entries are keyed by PLAIN event name — use
        ``${config}[PreToolUse]``, NOT the former ``${config}[hooks.PreToolUse]``.
        Entries whose ``command`` contains a canonical inline YAML frontmatter
        block additionally surface an ``inline_skill: dict`` field.

        Raises ``InvalidHookConfigError`` on any structural failure (file not
        found, malformed JSON, ambiguous item, missing per-type required field,
        wrong-type optional field). The error's ``field_name`` attribute carries
        an RFC 6901 JSON Pointer (e.g. ``/hooks/PreToolUse/0/hooks/1/command``
        for a real-format definition field) pinpointing the source location.
        Format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.

        This keyword is composed into the top-level ``AgentEval`` library
        and resolves as ``Hook.Get Config`` under a plain ``Library
        AgentEval`` import (no ``WITH NAME`` needed — the ``Hook.`` prefix
        is baked into the keyword name).

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | Length Should Be    ${config}[PreToolUse]    1
        | Should Be Equal    ${config}[PreToolUse][0][command]    /usr/local/bin/audit-hook
        | Should Be Equal    ${config}[PreToolUse][0][type]    command
        | Should Be Equal As Integers    ${config}[PostToolUse][0][timeout]    30

        Notes:
        - Real Claude Code schema (nested matcher groups) is the primary input;
          the legacy flat shape is accepted with a ``DeprecationWarning``.
        - Unknown events + unknown hook ``type`` values pass through unvalidated.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format: FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
          The ``field_name`` attribute on raised errors carries an RFC 6901 JSON Pointer.
        - Inline-skill-frontmatter hooks are an extension surface — the inner skill
          is reachable via `SkillsLibrary` keywords passed the ``inline_skill`` dict directly.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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

        [Tier 1 — Deterministic] — hook scripts are deterministic local
        programs; executing them involves no LLM and needs no API keys.

        **SECURITY: this keyword runs USER-AUTHORED HOOK SCRIPTS LOCALLY** with
        your privileges. The subprocess environment is sanitized (default-deny
        allowlist + ``CLAUDE_PROJECT_DIR``; parent secrets NOT inherited), a
        hard timeout is enforced, and on timeout the hook's OWN process group is
        killed — but this LIMITS LEAKAGE, it is NOT a sandbox. In particular, a
        hook descendant that starts a NEW session (``setsid`` / ``start_new_session``)
        before the timeout escapes the killed process group and can keep running
        after this keyword returns ``timed_out`` (Phase-1 non-sandbox limitation;
        containing cross-session descendants needs a cgroup/job-object primitive
        — carry-over ``DF-HOOKS-S2``). Only fire configs whose commands you trust.

        Synthesizes the real Claude Code stdin JSON (common fields
        ``session_id`` / ``transcript_path`` / ``cwd`` / ``hook_event_name`` /
        ``permission_mode`` merged with event-specific fields), then runs each
        configured ``type: "command"`` hook whose matcher matches the subject
        (the ``tool_name``). A bare ``command`` string runs through the shell;
        a ``command`` + ``args`` array runs in exec form.

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config`` (NOT a settings.json path). |
        | ``event`` | Event name; ``PreToolUse`` / ``PostToolUse`` / ``Stop`` are pinned, others pass through. |
        | ``project_dir`` | Value for ``CLAUDE_PROJECT_DIR`` + the subprocess cwd. Defaults to the test's cwd. |
        | ``default_timeout`` | Per-hook timeout (s) when the entry has no ``timeout``. Default 30 (below 600). |
        | ``inherit_env`` | ``True`` inherits the full parent env (opt-in). Default ``False`` (default-deny). |
        | ``extra_env`` | Optional dict of extra env vars for the hook subprocess. |
        | ``payload`` | Full-override dict for the event-specific fields (common fields fill gaps; explicit keys win). |
        | ``**event_fields`` | Event-specific fields (``tool_name=Bash``, ``tool_input=${dict}``, ...). |

        Returns a report with one frozen-dataclass record per matching hook
        (``.results``). Each record carries ``status`` (``completed`` /
        ``timed_out`` / ``spawn_failed`` / ``skipped``), ``exit_code``,
        ``stdout``, ``stderr``, ``stdout_json``, ``duration``, and the
        normalized ``decision``. Execution failures are RECORDED, not raised,
        so a multi-hook event reports every hook. Matching non-``command``
        hooks appear as ``skipped`` records with a ``skip_reason``.

        Raises ``HookExecutionError`` immediately when ZERO configured hooks
        match (an empty report would let a decision assertion silently never
        run) — the fix suggestion points at ``Hook.Get Hooks For Event``.

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash    tool_input=${dangerous}
        | `Hook.Decision Should Be`    ${report}    block
        | Log    ${report.results}[0].stderr

        Notes:
        - Consumes the flattened per-entry shape produced by `Hook.Get Config`
          (the sibling change `accept-real-claude-hook-config`); reads only the
          stable ``type`` / ``command`` / ``args`` / ``timeout`` / ``matcher`` subset.
        - Protocol snapshot: https://code.claude.com/docs/en/hooks (2026-07-08).
          Exact payload synthesis is pinned for the PRD FR4 events
          (``PreToolUse`` / ``PostToolUse`` / ``Stop``); other events pass through.
        - Windows ``shell: powershell`` is recorded but NOT honored in Phase-1
          (carry-over ``DF-HOOKS-S1`` in `docs/phase-1-5-carry-overs.md`).
        - Decision normalization + subprocess safety live in
          `src/AgentEval/hooks/_runner.py`; the shared matcher engine in
          `_matcher.py` guarantees this keyword and `Hook.Get Hooks For Event` agree.
        """
        config = self._require_config(config)
        entries = config.get(event, [])
        subject = self._resolve_subject(payload, event_fields)

        matched = [entry for entry in entries if self._matcher_matches_safe(entry.get("matcher"), subject)]
        if not matched:
            raise HookExecutionError(
                f"No configured hook for event {event!r} matches subject {subject!r} "
                f"(config has {len(entries)} hook(s) for this event).",
                field_name=event,
                fix_suggestion=(
                    "Call `Hook.Get Hooks For Event` with the same event + tool_name to see which "
                    "hooks would fire, then check the matcher pattern or the tool_name you passed."
                ),
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

    @staticmethod
    def _matcher_matches_safe(matcher: str | None, subject: str) -> bool:
        """Matcher match that treats an uncompilable regex as a non-match.

        The live runner must not crash the whole fire because one matcher is a
        bad regex — `Hook.Validate Matcher Syntax` is the loud pre-flight.
        """
        import re

        try:
            return matcher_matches(matcher, subject)
        except re.error:
            return False

    @keyword(name="Hook.Decision Should Be")
    @tier(1)
    def decision_should_be(self, result: Any, expected: str) -> None:
        """Asserts a fired hook's normalized block/allow/ask/none decision.

        [Tier 1 — Deterministic] — a pure comparison over a captured record.

        Accepts a ``Hook.Fire Hook Event`` report (with exactly one record) OR
        a single hook record. ``deny`` is accepted as an alias of ``block`` so
        you can assert in either the PreToolUse vocabulary or the exit-code
        vocabulary. Fails loud when the target record's status is not
        ``completed`` (e.g. ``timed_out`` / ``spawn_failed``), naming the
        status rather than reporting a misleading decision.

        | =Arguments= | =Description= |
        | ``result`` | A ``Hook.Fire Hook Event`` report (single record) or one hook record. |
        | ``expected`` | ``block`` / ``allow`` / ``ask`` / ``none`` (``deny`` accepted as an alias of ``block``). |

        Example:
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Decision Should Be`    ${report}    block
        | `Hook.Decision Should Be`    ${report}    deny

        Notes:
        - Decision precedence (exit 2 blocks + ignores stdout; PreToolUse
          ``permissionDecision``; top-level ``decision: "block"``) is
          normalized in `src/AgentEval/hooks/_runner.py`.
        - Raw ``exit_code`` / ``stdout`` / ``stderr`` / ``stdout_json`` stay on
          the record for precise assertions via `Hook.Output Field Should Be`.
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

        [Tier 1 — Deterministic] — a pure comparison over a captured record.

        Fails loud when the record's status is not ``completed`` (a
        ``timed_out`` / ``spawn_failed`` hook has no exit code to compare).

        | =Arguments= | =Description= |
        | ``result`` | A ``Hook.Fire Hook Event`` report (single record) or one hook record. |
        | ``expected`` | The expected integer exit code (``0`` allow, ``2`` block, ...). |

        Example:
        | ${report} =    `Hook.Fire Hook Event`    ${config}    PreToolUse    tool_name=Bash
        | `Hook.Exit Code Should Be`    ${report}    2

        Notes:
        - Exit-code semantics follow the Claude Code protocol snapshot
          (https://code.claude.com/docs/en/hooks, 2026-07-08): ``0`` success,
          ``2`` blocking error, any other code a non-blocking error.
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

        [Tier 1 — Deterministic] — a pure navigation + comparison over a
        captured record.

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

        Notes:
        - Per the Claude Code protocol snapshot
          (https://code.claude.com/docs/en/hooks, 2026-07-08), exit-code-2
          hooks IGNORE stdout JSON — such records carry ``stdout_json=None`` and
          this assertion fails loud rather than reading a stale field.
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
        """Returns which configured hooks would fire — statically, no execution.

        [Tier 1 — Deterministic] — a pure static analysis; spawns NO subprocess.

        Uses the SAME matcher engine as ``Hook.Fire Hook Event``, so the static
        simulation and live execution can never disagree about which hooks
        match a given event + tool name.

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config``. |
        | ``event`` | The event name to simulate (e.g. ``PreToolUse``). |
        | ``tool_name`` | The matcher subject (tool name). Empty string matches only match-all matchers. |

        Returns the list of configured hook entries (in source order) whose
        matcher matches ``tool_name`` — including non-``command`` entries, which
        ``Hook.Fire Hook Event`` would report as ``skipped``.

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | ${hooks} =    `Hook.Get Hooks For Event`    ${config}    PreToolUse    tool_name=Bash
        | Length Should Be    ${hooks}    1
        | Should Be Equal    ${hooks}[0][type]    command

        Notes:
        - Matcher dispatch (``*``/empty match-all; simple ``|``/``,`` list;
          otherwise Python ``re``) lives in `src/AgentEval/hooks/_matcher.py`.
        """
        config = self._require_config(config)
        entries = config.get(event, [])
        return [entry for entry in entries if self._matcher_matches_safe(entry.get("matcher"), tool_name)]

    @keyword(name="Hook.Validate Matcher Syntax")
    @tier(1)
    def validate_matcher_syntax(self, matcher: str | None, subject: str | None = None) -> bool:
        """Validates a matcher compiles, optionally reporting whether it matches a subject.

        [Tier 1 — Deterministic] — a static compile check; executes nothing.

        Checks the matcher under the engine's dispatch rules (``*``/empty
        match-all; simple ``|``/``,`` list; otherwise a Python regex). Fails
        loud on a regex that will not compile, naming the offending pattern.
        When a ``subject`` is supplied and the matcher is valid, returns whether
        the matcher matches that subject (a deterministic pre-flight for regex
        matchers).

        | =Arguments= | =Description= |
        | ``matcher`` | The matcher string to validate (``None`` / ``""`` / ``*`` are match-all). |
        | ``subject`` | Optional tool name to test the matcher against. |

        Returns ``True`` when the matcher is valid and no subject was supplied;
        otherwise the boolean subject-match result.

        Example:
        | ${matches} =    `Hook.Validate Matcher Syntax`    Bash|Edit    subject=Edit
        | Should Be True    ${matches}
        | `Hook.Validate Matcher Syntax`    mcp__.*

        Notes:
        - Matchers are evaluated with Python ``re``, NOT JavaScript RegExp as
          Claude Code itself uses — the divergence is documented in
          `src/AgentEval/hooks/_matcher.py` and echoed in compile-failure messages.
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

        [Tier 1 — Deterministic] — a static path/``PATH`` resolution; executes
        nothing.

        For each ``type: "command"`` hook (optionally scoped to one ``event``),
        takes the first ``shlex``-split token of the ``command`` string (or the
        ``command`` itself in exec form), expands a literal
        ``$CLAUDE_PROJECT_DIR`` / ``${CLAUDE_PROJECT_DIR}`` prefix against
        ``project_dir``, and resolves it via ``shutil.which`` or a
        path-existence-plus-executable-bit check. This is a HEURISTIC pre-flight
        checking the FIRST TOKEN ONLY — not a full shell parse (a compound
        ``jq ... | grep ...`` resolves ``jq``).

        | =Arguments= | =Description= |
        | ``config`` | The parsed config dict from ``Hook.Get Config``. |
        | ``event`` | Optional event name to scope the check. When ``None``, checks every event. |
        | ``project_dir`` | Value substituted for a ``$CLAUDE_PROJECT_DIR`` prefix. Defaults to the test's cwd. |

        Fails, naming every unresolved command, when any first token cannot be
        resolved to an executable.

        Example:
        | ${config} =    `Hook.Get Config`    ${CURDIR}/.claude/settings.json
        | `Hook.Command Should Exist`    ${config}
        | `Hook.Command Should Exist`    ${config}    event=PreToolUse

        Notes:
        - Resolution uses ``shlex`` + ``shutil.which`` per the design's
          command-resolution decision; shell builtins + inline compound
          commands resolve on their first token only.
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
                    token = command  # exec form: command is the executable
                else:
                    split = shlex.split(command)
                    token = split[0] if split else ""
                token = self._expand_project_dir(token, resolved_project_dir)
                if not self._command_resolves(token):
                    unresolved.append(f"{ev}: {command!r} (first token {token!r} not found on PATH or disk)")

        if unresolved:
            raise AssertionError(
                "hook command(s) did not resolve to an executable before a live session depends on them:\n  "
                + "\n  ".join(unresolved)
            )

    @staticmethod
    def _expand_project_dir(token: str, project_dir: str) -> str:
        """Expand a literal ``$CLAUDE_PROJECT_DIR`` / ``${CLAUDE_PROJECT_DIR}`` prefix."""
        for prefix in ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR"):
            if token.startswith(prefix):
                return project_dir + token[len(prefix) :]
        return token

    @staticmethod
    def _command_resolves(token: str) -> bool:
        """Resolve a command token via ``shutil.which`` or path+exec-bit check."""
        if not token:
            return False
        if shutil.which(token) is not None:
            return True
        candidate = Path(token)
        return candidate.exists() and os.access(candidate, os.X_OK)
