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

"""Hook `settings.json` parser (Story 2.2).

Parses Claude Code `settings.json` files per PRD FR4 + the Claude Code
hook format: a top-level `hooks` mapping where each key is an event
(`PreToolUse`, `PostToolUse`, `Stop`, ...) and the value is a list of
hook entries. Each entry has:
- `command` (required, str)
- `args` (optional, list[str])
- `timeout` (optional, int seconds)
- `matcher` (optional, str)

Inline-skill-frontmatter hooks: when a hook's `command` value contains
a YAML frontmatter block (delimited by `---\\n...\\n---\\n`), the
parser extracts the YAML + surfaces it as a nested `inline_skill: dict`
field on the entry. This is a per-PRD-FR4 ergonomic feature for hooks
that ship skill metadata alongside their command.

`InvalidHookConfigError.field_name` carries an RFC 6901 JSON Pointer
(e.g., `/hooks/PreToolUse/0/command`) into the offending location for
nested-JSON validation failures — parallel to FR6's JSON Pointer
convention for `InvalidMCPToolSchemaError`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidHookConfigError

__all__ = [
    "REQUIRED_HOOK_FIELDS",
    "SUPPORTED_EVENTS",
    "parse_hook_config",
]

# PRD FR4 explicitly mentions `PreToolUse`, `PostToolUse`, `Stop`. The
# Claude Code hook format has more events; Phase-1 only validates the
# 3 PRD-pinned ones strictly + passes through any others without
# per-entry validation (forward-compat with Claude Code additions).
SUPPORTED_EVENTS: tuple[str, ...] = ("PreToolUse", "PostToolUse", "Stop")

REQUIRED_HOOK_FIELDS: tuple[str, ...] = ("command",)


def _build_pointer(*segments: str | int) -> str:
    """Build an RFC 6901 JSON Pointer from path segments.

    Per RFC 6901 §3: each segment is preceded by `/`; literal `/` in a
    segment is escaped as `~1`; literal `~` is escaped as `~0`. Integer
    segments are stringified.
    """
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, int):
            parts.append(str(seg))
        else:
            parts.append(seg.replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(parts)


def parse_hook_config(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Parse a `settings.json` hook config file per PRD FR4.

    Args:
        path: Filesystem path to the `settings.json` file.

    Returns:
        A dict mapping `hooks.<event>` → list of hook entries.
        Each entry has `command` (str) + optional `args` (list[str])
        + `timeout` (int) + `matcher` (str). If a hook's `command`
        contains an inline YAML frontmatter block, the parsed YAML
        appears as an extra `inline_skill: dict` field on the entry.

    Raises:
        InvalidHookConfigError: On any structural failure — file not
            found, malformed JSON, hooks key missing/non-mapping,
            event arrays not lists, entries missing `command`, wrong
            types for optional fields. `field_name` carries an RFC
            6901 JSON Pointer into the offending location.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".json":
        raise InvalidHookConfigError(
            f"Hook config file must have a .json extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix_suggestion="Rename the file so it ends in `.json` (Claude Code uses `settings.json`).",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidHookConfigError(
            f"Hook config file not found: {file_path_str}.",
            file_path=file_path_str,
            fix_suggestion="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidHookConfigError(
            f"Hook config file could not be read: {exc}.",
            file_path=file_path_str,
            fix_suggestion="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidHookConfigError(
            f"JSON failed to parse: {exc.msg}.",
            file_path=file_path_str,
            line_number=exc.lineno,
            fix_suggestion="Check JSON quoting + commas; run a JSON linter on the file.",
        ) from exc

    if not isinstance(document, dict):
        raise InvalidHookConfigError(
            f"Top-level JSON value must be an object; got {type(document).__name__}.",
            file_path=file_path_str,
            field_name="",
            fix_suggestion="Wrap the content in `{ ... }` with a `hooks` field.",
        )

    hooks_section = document.get("hooks", {})
    if not isinstance(hooks_section, dict):
        raise InvalidHookConfigError(
            f"`hooks` must be a mapping; got {type(hooks_section).__name__}.",
            file_path=file_path_str,
            field_name="/hooks",
            fix_suggestion="Set `hooks: {event_name: [entries], ...}` per PRD FR4.",
        )

    result: dict[str, list[dict[str, Any]]] = {}
    for event_name, entries in hooks_section.items():
        event_pointer = _build_pointer("hooks", event_name)
        if not isinstance(entries, list):
            raise InvalidHookConfigError(
                f"`hooks.{event_name}` must be a list of hook entries; got {type(entries).__name__}.",
                file_path=file_path_str,
                field_name=event_pointer,
                fix_suggestion=(f"Set `{event_pointer}` to a JSON array of hook entries."),
            )
        validated_entries: list[dict[str, Any]] = []
        for entry_index, entry in enumerate(entries):
            entry_pointer = _build_pointer("hooks", event_name, entry_index)
            if not isinstance(entry, dict):
                raise InvalidHookConfigError(
                    f"Hook entry must be an object; got {type(entry).__name__}.",
                    file_path=file_path_str,
                    field_name=entry_pointer,
                    fix_suggestion=f"Set `{entry_pointer}` to a JSON object with `command` + optional fields.",
                )
            validated_entries.append(
                _validate_hook_entry(
                    entry,
                    file_path_str=file_path_str,
                    entry_pointer=entry_pointer,
                    strict=event_name in SUPPORTED_EVENTS,
                )
            )
        result[f"hooks.{event_name}"] = validated_entries

    return result


def _validate_hook_entry(
    entry: dict[str, Any],
    *,
    file_path_str: str,
    entry_pointer: str,
    strict: bool,
) -> dict[str, Any]:
    """Validate a single hook entry; return the validated dict (with `inline_skill` if applicable).

    When `strict` is False (events outside `SUPPORTED_EVENTS`), missing
    `command` is still flagged because the field is required by the
    Claude Code hook format itself. The `strict` flag is reserved for
    Phase-2 stricter-validation modes.
    """
    if "command" not in entry:
        raise InvalidHookConfigError(
            "Hook entry missing required field `command`.",
            file_path=file_path_str,
            field_name=f"{entry_pointer}/command",
            fix_suggestion="Add `command: <shell-command-string>` to the hook entry.",
        )

    command = entry["command"]
    if not isinstance(command, str) or not command:
        raise InvalidHookConfigError(
            f"Hook entry `command` must be a non-empty string; got {type(command).__name__}.",
            file_path=file_path_str,
            field_name=f"{entry_pointer}/command",
            fix_suggestion="Set `command` to a non-empty string.",
        )

    if "args" in entry:
        args = entry["args"]
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise InvalidHookConfigError(
                f"Hook entry `args` (optional) must be a list of strings; got {type(args).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/args",
                fix_suggestion="Set `args` to a JSON array of strings, or omit the field.",
            )

    if "timeout" in entry:
        timeout = entry["timeout"]
        # bool is a subclass of int — reject explicitly so `timeout: true`
        # doesn't silently coerce to 1.
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            raise InvalidHookConfigError(
                f"Hook entry `timeout` (optional) must be an int (seconds); got {type(timeout).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/timeout",
                fix_suggestion="Set `timeout` to an integer number of seconds, or omit.",
            )

    if "matcher" in entry:
        matcher = entry["matcher"]
        if not isinstance(matcher, str):
            raise InvalidHookConfigError(
                f"Hook entry `matcher` (optional) must be a string; got {type(matcher).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/matcher",
                fix_suggestion="Set `matcher` to a string pattern, or omit.",
            )

    # Inline-skill-frontmatter detection (per PRD FR4 + Story 2.2 spec):
    # if the command starts with `---` on its own line, treat everything
    # up to the next `---` line as a YAML block + parse to inline_skill.
    validated = dict(entry)
    inline_skill = _extract_inline_skill_frontmatter(command)
    if inline_skill is not None:
        validated["inline_skill"] = inline_skill

    return validated


def _extract_inline_skill_frontmatter(command: str) -> dict[str, Any] | None:
    """Detect + parse an inline YAML frontmatter block at the head of `command`.

    Returns the parsed YAML dict if a complete `---\\n...\\n---` block
    appears at the head of `command`; returns None otherwise.

    Malformed YAML inside an inline frontmatter is NOT raised — it's
    treated as "no inline skill" and silently ignored. The hook still
    parses; only static-inspection of the inline skill is unavailable.
    Phase-2 may tighten this to raise a typed warning.
    """
    lines = command.splitlines()
    if len(lines) < 3 or lines[0].rstrip() != "---":
        return None
    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end_index = index
            break
    if end_index is None:
        return None
    yaml_block = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
