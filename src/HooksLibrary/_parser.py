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

"""Parser for the real nested Claude Code hooks config.

A top-level ``hooks`` mapping from event name to a list of *matcher groups*;
each group has an optional ``matcher`` string and a required ``hooks`` list of
typed hook definitions::

    {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "..."}]}]}}

Five definition types are recognized: ``command`` (needs ``command``), ``http``
(needs ``url``), ``mcp_tool`` (needs ``server`` + ``tool``), ``prompt`` /
``agent`` (need ``prompt``). Unknown types pass through unvalidated. A
definition with ``command`` but no ``type`` is read as ``type: "command"``.

`parse_hook_config` returns ``dict[str, list[dict]]`` keyed by plain event name.
Matcher groups are flattened: each inner definition becomes one entry, with the
group's ``matcher`` (when present) copied onto it, preserving source order.

On any structural failure it raises `InvalidConfigError` whose ``field`` carries
an RFC 6901 JSON Pointer into the offending source location.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from AgentEval._core import InvalidConfigError

__all__ = [
    "REQUIRED_HOOK_FIELDS",
    "SUPPORTED_EVENTS",
    "parse_hook_config",
]

# The PRD-pinned trio. Documentation-only: the parser shape-validates every
# event identically and passes unknown events through.
SUPPORTED_EVENTS: tuple[str, ...] = ("PreToolUse", "PostToolUse", "Stop")

REQUIRED_HOOK_FIELDS: tuple[str, ...] = ("command",)

_REAL_SCHEMA_HINT = (
    'Use the Claude Code hooks schema: {"hooks": {"<Event>": '
    '[{"matcher": "<pattern>", "hooks": [{"type": "command", '
    '"command": "..."}]}]}}.'
)


def _build_pointer(*segments: str | int) -> str:
    """Build an RFC 6901 JSON Pointer from path segments."""
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, int):
            parts.append(str(seg))
        else:
            parts.append(seg.replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(parts)


def parse_hook_config(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Parse a Claude Code ``settings.json`` hook config file.

    Returns a dict mapping each plain event name to a list of normalized hook
    entries. Each entry carries a ``type`` field and the group's ``matcher``
    when present. A file without a top-level ``hooks`` field returns ``{}``.

    Raises `InvalidConfigError` on any structural failure; ``field`` carries an
    RFC 6901 JSON Pointer into the offending location.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".json":
        raise InvalidConfigError(
            f"Hook config file must have a .json extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix="Rename the file so it ends in `.json` (Claude Code uses `settings.json`).",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidConfigError(
            f"Hook config file not found: {file_path_str}.",
            file_path=file_path_str,
            fix="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidConfigError(
            f"Hook config file could not be read: {exc}.",
            file_path=file_path_str,
            fix="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(
            f"JSON failed to parse at line {exc.lineno}: {exc.msg}.",
            file_path=file_path_str,
            fix="Check JSON quoting + commas; run a JSON linter on the file.",
        ) from exc

    if not isinstance(document, dict):
        raise InvalidConfigError(
            f"Top-level JSON value must be an object; got {type(document).__name__}.",
            file_path=file_path_str,
            field="",
            fix="Wrap the content in `{ ... }` with a `hooks` field.",
        )

    hooks_section = document.get("hooks", {})
    if not isinstance(hooks_section, dict):
        raise InvalidConfigError(
            f"`hooks` must be a mapping; got {type(hooks_section).__name__}.",
            file_path=file_path_str,
            field="/hooks",
            fix=f"Set `hooks` to a mapping of event name -> list of matcher groups. {_REAL_SCHEMA_HINT}",
        )

    result: dict[str, list[dict[str, Any]]] = {}
    for event_name, items in hooks_section.items():
        event_pointer = _build_pointer("hooks", event_name)
        if not isinstance(items, list):
            raise InvalidConfigError(
                f"`hooks.{event_name}` must be a list of matcher groups; got {type(items).__name__}.",
                file_path=file_path_str,
                field=event_pointer,
                fix=f"Set `{event_pointer}` to a JSON array of matcher groups. {_REAL_SCHEMA_HINT}",
            )
        validated_entries: list[dict[str, Any]] = []
        for item_index, item in enumerate(items):
            item_pointer = _build_pointer("hooks", event_name, item_index)
            validated_entries.extend(
                _process_matcher_group(
                    item,
                    file_path_str=file_path_str,
                    event_name=event_name,
                    item_index=item_index,
                    group_pointer=item_pointer,
                )
            )
        result[event_name] = validated_entries

    return result


def _process_matcher_group(
    item: Any,
    *,
    file_path_str: str,
    event_name: str,
    item_index: int,
    group_pointer: str,
) -> list[dict[str, Any]]:
    """Validate one matcher group; return its flattened, normalized entries."""
    if not isinstance(item, dict):
        raise InvalidConfigError(
            f"Hook event item must be a matcher group object; got {type(item).__name__}.",
            file_path=file_path_str,
            field=group_pointer,
            fix=f"Set `{group_pointer}` to a matcher group object. {_REAL_SCHEMA_HINT}",
        )

    if "hooks" not in item:
        raise InvalidConfigError(
            f"Matcher group `{group_pointer}` has no `hooks` list of typed definitions.",
            file_path=file_path_str,
            field=group_pointer,
            fix=f"Provide a matcher group with a `hooks` list. {_REAL_SCHEMA_HINT}",
        )

    matcher: str | None = None
    if "matcher" in item:
        matcher_value = item["matcher"]
        if not isinstance(matcher_value, str):
            raise InvalidConfigError(
                f"Matcher group `matcher` (optional) must be a string; got {type(matcher_value).__name__}.",
                file_path=file_path_str,
                field=f"{group_pointer}/matcher",
                fix="Set `matcher` to a string tool/source pattern, or omit it.",
            )
        matcher = matcher_value

    definitions = item["hooks"]
    if not isinstance(definitions, list):
        raise InvalidConfigError(
            f"Matcher group `hooks` must be a list of typed hook definitions; got {type(definitions).__name__}.",
            file_path=file_path_str,
            field=f"{group_pointer}/hooks",
            fix=f"Set `{group_pointer}/hooks` to a JSON array of typed hook definitions. {_REAL_SCHEMA_HINT}",
        )

    entries: list[dict[str, Any]] = []
    for def_index, definition in enumerate(definitions):
        def_pointer = _build_pointer("hooks", event_name, item_index, "hooks", def_index)
        if not isinstance(definition, dict):
            raise InvalidConfigError(
                f"Hook definition must be an object; got {type(definition).__name__}.",
                file_path=file_path_str,
                field=def_pointer,
                fix=f"Set `{def_pointer}` to a typed hook definition object. {_REAL_SCHEMA_HINT}",
            )
        entries.append(
            _validate_hook_definition(
                definition,
                file_path_str=file_path_str,
                def_pointer=def_pointer,
                matcher=matcher,
            )
        )
    return entries


def _validate_hook_definition(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
    matcher: str | None,
) -> dict[str, Any]:
    """Validate + normalize a single hook definition."""
    hook_type = _resolve_hook_type(definition, file_path_str=file_path_str, def_pointer=def_pointer)
    _validate_timeout(definition, file_path_str=file_path_str, def_pointer=def_pointer)

    if hook_type == "command":
        _validate_command_definition(definition, file_path_str=file_path_str, def_pointer=def_pointer)
    elif hook_type == "http":
        _require_non_empty_str(
            definition, "url", file_path_str=file_path_str, def_pointer=def_pointer, type_label="http"
        )
    elif hook_type == "mcp_tool":
        _require_non_empty_str(
            definition, "server", file_path_str=file_path_str, def_pointer=def_pointer, type_label="mcp_tool"
        )
        _require_non_empty_str(
            definition, "tool", file_path_str=file_path_str, def_pointer=def_pointer, type_label="mcp_tool"
        )
    elif hook_type in ("prompt", "agent"):
        _require_non_empty_str(
            definition, "prompt", file_path_str=file_path_str, def_pointer=def_pointer, type_label=hook_type
        )
    # Unknown types pass through without per-type field validation.

    validated = dict(definition)
    validated["type"] = hook_type
    if matcher is not None:
        validated["matcher"] = matcher
    return validated


def _resolve_hook_type(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> str:
    """Resolve the definition's ``type``.

    A present ``type`` must be a non-empty string. Absent but with ``command``
    present, it is read as ``"command"``. Absent with no ``command`` is an error.
    """
    if "type" in definition:
        type_value = definition["type"]
        if not isinstance(type_value, str) or not type_value:
            raise InvalidConfigError(
                f"Hook definition `type` must be a non-empty string; got {type(type_value).__name__}.",
                file_path=file_path_str,
                field=f"{def_pointer}/type",
                fix='Set `type` to one of "command", "http", "mcp_tool", "prompt", "agent".',
            )
        return type_value

    if "command" in definition:
        return "command"

    raise InvalidConfigError(
        "Hook definition missing required field `type`.",
        file_path=file_path_str,
        field=f"{def_pointer}/type",
        fix=f'Add `type` (e.g. "command", "http", "mcp_tool", "prompt", "agent"). {_REAL_SCHEMA_HINT}',
    )


def _require_non_empty_str(
    definition: dict[str, Any],
    field: str,
    *,
    file_path_str: str,
    def_pointer: str,
    type_label: str,
) -> None:
    """Require ``field`` on ``definition`` to be present + a non-empty string."""
    if field not in definition:
        raise InvalidConfigError(
            f"`{type_label}` hook definition missing required field `{field}`.",
            file_path=file_path_str,
            field=f"{def_pointer}/{field}",
            fix=f"Add `{field}: <non-empty-string>` to the `{type_label}` hook definition.",
        )
    value = definition[field]
    if not isinstance(value, str) or not value:
        raise InvalidConfigError(
            f"`{type_label}` hook definition `{field}` must be a non-empty string; got {type(value).__name__}.",
            file_path=file_path_str,
            field=f"{def_pointer}/{field}",
            fix=f"Set `{field}` to a non-empty string.",
        )


def _validate_command_definition(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> None:
    """Validate a ``command``-type definition's fields."""
    if "command" not in definition:
        raise InvalidConfigError(
            "Hook definition missing required field `command`.",
            file_path=file_path_str,
            field=f"{def_pointer}/command",
            fix="Add `command: <shell-command-string>` to the `command` hook definition.",
        )

    command = definition["command"]
    if not isinstance(command, str) or not command:
        raise InvalidConfigError(
            f"Hook definition `command` must be a non-empty string; got {type(command).__name__}.",
            file_path=file_path_str,
            field=f"{def_pointer}/command",
            fix="Set `command` to a non-empty string.",
        )

    if "args" in definition:
        args = definition["args"]
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise InvalidConfigError(
                f"Hook definition `args` (optional) must be a list of strings; got {type(args).__name__}.",
                file_path=file_path_str,
                field=f"{def_pointer}/args",
                fix="Set `args` to a JSON array of strings, or omit the field.",
            )


def _validate_timeout(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> None:
    """Validate ``timeout`` when present: int seconds, not bool."""
    if "timeout" in definition:
        timeout = definition["timeout"]
        # bool is a subclass of int - reject explicitly so `timeout: true`
        # doesn't silently coerce to 1.
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            raise InvalidConfigError(
                f"Hook definition `timeout` (optional) must be an int (seconds); got {type(timeout).__name__}.",
                file_path=file_path_str,
                field=f"{def_pointer}/timeout",
                fix="Set `timeout` to an integer number of seconds, or omit.",
            )
