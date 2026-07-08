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

"""Hook `settings.json` parser (Story 2.2; real-format rewrite 2026-07-08).

Parses Claude Code `settings.json` hook configurations into a normalized,
format-independent structure. Two input formats are accepted:

**Real (primary) format** — the current Claude Code schema
(https://code.claude.com/docs/en/hooks, verified 2026-07-08). A top-level
`hooks` mapping from event name to a list of *matcher groups*; each matcher
group is an object with an optional `matcher` string and a required `hooks`
list of typed hook definitions::

    {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [
            {"type": "command", "command": "..."}
        ]}
    ]}}

Five hook-definition types are recognized: `command`, `http`, `mcp_tool`,
`prompt`, `agent`. `command` requires `command`; `http` requires `url`;
`mcp_tool` requires `server` + `tool`; `prompt` / `agent` require `prompt`.
Unknown `type` values are passed through unvalidated (forward-compat with
Claude Code additions). A definition with `command` but no `type` is
grandfathered to `type: "command"`.

**Legacy flat format (DEPRECATED)** — the pre-change invented shape where an
event-array item is itself a flat entry with a `command` key and no `hooks`
key. Still accepted (validated as a `command` definition, stamped
`type: "command"`), but emits a single `DeprecationWarning` per parse call.

**Normalized return shape.** `parse_hook_config` returns
`dict[str, list[dict]]` keyed by PLAIN event name (e.g. `"PreToolUse"`, NOT
the former flattened `"hooks.PreToolUse"` key). Matcher groups are flattened:
each inner hook definition becomes one entry, with the group's `matcher`
(when present) copied onto it, preserving source order. Every returned entry
carries a `type` field. Fields the parser does not validate (`if`, `async`,
`statusMessage`, `once`, `url`, `headers`, `server`, `tool`, `input`,
`prompt`, `model`, future fields) pass through unmodified.

Inline-skill-frontmatter hooks: when a `command`-type entry's `command`
value begins with a column-0 YAML frontmatter block (`---\\n...\\n---\\n`)
whose mapping contains BOTH `name` and `description`, the parsed YAML is
surfaced as a nested `inline_skill: dict` field on the returned entry.
`inline_skill` is a parser-reserved output key.

`InvalidHookConfigError.field_name` carries an RFC 6901 JSON Pointer into the
offending SOURCE location: 5-segment for real-format definition fields
(`/hooks/PreToolUse/0/hooks/1/command`), 4-segment for group fields
(`/hooks/PreToolUse/0/matcher`), 3-segment for legacy-flat entry fields
(`/hooks/PreToolUse/0/command`).

Architecture-layout deviation (inherited from Story 2.1): architecture
L843-847 pins `_internal.py` as the canonical helper module name.
Story 2.2 inherits Story 2.1's `_parser.py` deviation (clarity > strict
convention for the Phase-1 parser modules); tracked in deferred-work
for Phase-1.5 cleanup.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidHookConfigError

__all__ = [
    "REQUIRED_HOOK_FIELDS",
    "SUPPORTED_EVENTS",
    "parse_hook_config",
]

# PRD FR4 explicitly mentions `PreToolUse`, `PostToolUse`, `Stop`. The real
# Claude Code hook format has 31+ events; the parser applies identical shape
# validation to every event and passes unknown events through. SUPPORTED_EVENTS
# is documentation-only (the PRD-pinned trio) and has no behavioral effect.
SUPPORTED_EVENTS: tuple[str, ...] = ("PreToolUse", "PostToolUse", "Stop")

REQUIRED_HOOK_FIELDS: tuple[str, ...] = ("command",)

# Canonical real-schema reminder embedded in fix suggestions.
_REAL_SCHEMA_HINT = (
    'Use the Claude Code hooks schema: {"hooks": {"<Event>": '
    '[{"matcher": "<pattern>", "hooks": [{"type": "command", '
    '"command": "..."}]}]}}.'
)


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
    """Parse a Claude Code `settings.json` hook config file.

    Args:
        path: Filesystem path to the `settings.json` file.

    Returns:
        A dict mapping each PLAIN event name (`"PreToolUse"`, ...) to a list
        of normalized hook entries. Each entry carries a `type` field, the
        group's `matcher` (when present), and — for `command`-type entries
        whose command begins with canonical inline YAML frontmatter — an
        `inline_skill: dict` field. Files without a top-level `hooks` field
        are permissively accepted and return `{}`.

    Raises:
        InvalidHookConfigError: On structural failure — file not found, wrong
            extension, malformed JSON, non-object top level, non-mapping
            `hooks`, event array not a list, ambiguous item (both/neither
            `command` and `hooks`), group `hooks` not a list, non-string
            group `matcher`, missing/empty required per-type field, wrong-type
            optional field, or reserved-key collision. `field_name` carries an
            RFC 6901 JSON Pointer into the offending location. (Absent `hooks`
            key is NOT a failure — returns `{}`.)
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
            fix_suggestion=(
                "Set `hooks` to a mapping of event name → list of matcher "
                f"groups. {_REAL_SCHEMA_HINT}"
            ),
        )

    result: dict[str, list[dict[str, Any]]] = {}
    legacy_seen = False
    for event_name, items in hooks_section.items():
        event_pointer = _build_pointer("hooks", event_name)
        if not isinstance(items, list):
            raise InvalidHookConfigError(
                f"`hooks.{event_name}` must be a list of matcher groups; got {type(items).__name__}.",
                file_path=file_path_str,
                field_name=event_pointer,
                fix_suggestion=(f"Set `{event_pointer}` to a JSON array of matcher groups. {_REAL_SCHEMA_HINT}"),
            )
        validated_entries: list[dict[str, Any]] = []
        for item_index, item in enumerate(items):
            item_pointer = _build_pointer("hooks", event_name, item_index)
            item_legacy, item_entries = _process_event_item(
                item,
                file_path_str=file_path_str,
                event_name=event_name,
                item_index=item_index,
                item_pointer=item_pointer,
            )
            legacy_seen = legacy_seen or item_legacy
            validated_entries.extend(item_entries)
        result[event_name] = validated_entries

    if legacy_seen:
        warnings.warn(
            f"Hook config {file_path_str!r} uses the DEPRECATED legacy flat hook "
            "format (entries with a top-level `command` and no `hooks` list). "
            f"Migrate to the real Claude Code schema. {_REAL_SCHEMA_HINT}",
            DeprecationWarning,
            stacklevel=2,
        )

    return result


def _process_event_item(
    item: Any,
    *,
    file_path_str: str,
    event_name: str,
    item_index: int,
    item_pointer: str,
) -> tuple[bool, list[dict[str, Any]]]:
    """Classify + validate one item of an event array.

    Returns `(is_legacy, entries)` where `entries` is the flattened list of
    normalized hook entries contributed by this item (one per definition for
    a matcher group, exactly one for a legacy flat entry).

    Classification (design D1):
    - Matcher group: item has a `hooks` key whose value is a list. `matcher`
      is optional. → real format.
    - Legacy flat entry: item has a `command` key and NO `hooks` key. → legacy.
    - Both keys, or neither key → ambiguous, rejected.
    """
    if not isinstance(item, dict):
        raise InvalidHookConfigError(
            f"Hook event item must be an object; got {type(item).__name__}.",
            file_path=file_path_str,
            field_name=item_pointer,
            fix_suggestion=(f"Set `{item_pointer}` to a matcher group object. {_REAL_SCHEMA_HINT}"),
        )

    has_hooks = "hooks" in item
    has_command = "command" in item

    if has_hooks and has_command:
        raise InvalidHookConfigError(
            "Ambiguous hook event item: it has BOTH a `command` key and a `hooks` "
            "key. A matcher group carries `hooks` (a list of typed definitions); "
            "a legacy flat entry carries `command` — not both.",
            file_path=file_path_str,
            field_name=item_pointer,
            fix_suggestion=(f"Remove one of `command`/`hooks`. {_REAL_SCHEMA_HINT}"),
        )

    if has_hooks:
        return False, _process_matcher_group(
            item,
            file_path_str=file_path_str,
            event_name=event_name,
            item_index=item_index,
            group_pointer=item_pointer,
        )

    if has_command:
        entry = _validate_hook_definition(
            item,
            file_path_str=file_path_str,
            def_pointer=item_pointer,
            matcher=None,
        )
        return True, [entry]

    raise InvalidHookConfigError(
        "Hook event item has neither a `hooks` list (matcher group) nor a "
        "`command` (legacy flat entry).",
        file_path=file_path_str,
        field_name=item_pointer,
        fix_suggestion=(f"Provide a matcher group with a `hooks` list. {_REAL_SCHEMA_HINT}"),
    )


def _process_matcher_group(
    group: dict[str, Any],
    *,
    file_path_str: str,
    event_name: str,
    item_index: int,
    group_pointer: str,
) -> list[dict[str, Any]]:
    """Validate a matcher group; return its flattened, normalized entries."""
    matcher: str | None = None
    if "matcher" in group:
        matcher_value = group["matcher"]
        if not isinstance(matcher_value, str):
            raise InvalidHookConfigError(
                f"Matcher group `matcher` (optional) must be a string; got {type(matcher_value).__name__}.",
                file_path=file_path_str,
                field_name=f"{group_pointer}/matcher",
                fix_suggestion="Set `matcher` to a string tool/source pattern, or omit it.",
            )
        matcher = matcher_value

    definitions = group["hooks"]
    if not isinstance(definitions, list):
        raise InvalidHookConfigError(
            f"Matcher group `hooks` must be a list of typed hook definitions; got {type(definitions).__name__}.",
            file_path=file_path_str,
            field_name=f"{group_pointer}/hooks",
            fix_suggestion=(
                f"Set `{group_pointer}/hooks` to a JSON array of typed hook "
                f"definitions. {_REAL_SCHEMA_HINT}"
            ),
        )

    entries: list[dict[str, Any]] = []
    for def_index, definition in enumerate(definitions):
        def_pointer = _build_pointer("hooks", event_name, item_index, "hooks", def_index)
        if not isinstance(definition, dict):
            raise InvalidHookConfigError(
                f"Hook definition must be an object; got {type(definition).__name__}.",
                file_path=file_path_str,
                field_name=def_pointer,
                fix_suggestion=(f"Set `{def_pointer}` to a typed hook definition object. {_REAL_SCHEMA_HINT}"),
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
    """Validate + normalize a single hook definition (real or legacy flat).

    `matcher` is the enclosing matcher group's `matcher` (or None for a
    matcher-less group / legacy flat entry). It is copied onto the returned
    entry when not None. `inline_skill` remains a reserved output key.
    """
    if "inline_skill" in definition:
        # `inline_skill` is a parser-reserved output key; user payloads
        # MUST NOT collide (Blind-MED-1, pointer now extends into the nest).
        raise InvalidHookConfigError(
            "Hook definition uses reserved key `inline_skill` (parser-managed output field).",
            file_path=file_path_str,
            field_name=f"{def_pointer}/inline_skill",
            fix_suggestion=(
                "Remove `inline_skill` from the source definition — it is reserved as "
                "the parser's surface for extracted inline-frontmatter content."
            ),
        )

    hook_type = _resolve_hook_type(definition, file_path_str=file_path_str, def_pointer=def_pointer)

    # `timeout` when present MUST be int-not-bool on ANY definition type.
    _validate_timeout(definition, file_path_str=file_path_str, def_pointer=def_pointer)

    inline_skill: dict[str, Any] | None = None
    if hook_type == "command":
        command = _validate_command_definition(
            definition, file_path_str=file_path_str, def_pointer=def_pointer
        )
        inline_skill = _extract_inline_skill_frontmatter(command)
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
    # Unknown types: passed through without per-type field validation (D3).

    validated = dict(definition)
    validated["type"] = hook_type
    if matcher is not None:
        validated["matcher"] = matcher
    if inline_skill is not None:
        validated["inline_skill"] = inline_skill
    return validated


def _resolve_hook_type(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> str:
    """Resolve the definition's `type`, applying the grandfather rule (D3).

    - `type` present → must be a non-empty string.
    - `type` absent but `command` present → grandfathered to `"command"`.
    - `type` absent and `command` absent → error (docs require `type`).
    """
    if "type" in definition:
        type_value = definition["type"]
        if not isinstance(type_value, str) or not type_value:
            raise InvalidHookConfigError(
                f"Hook definition `type` must be a non-empty string; got {type(type_value).__name__}.",
                file_path=file_path_str,
                field_name=f"{def_pointer}/type",
                fix_suggestion=(
                    'Set `type` to one of "command", "http", "mcp_tool", "prompt", "agent" '
                    "(or a future Claude Code hook type)."
                ),
            )
        return type_value

    if "command" in definition:
        # Grandfather older real-world configs that predate strict typing.
        return "command"

    raise InvalidHookConfigError(
        "Hook definition missing required field `type`.",
        file_path=file_path_str,
        field_name=f"{def_pointer}/type",
        fix_suggestion=(
            'Add `type` (e.g. "command", "http", "mcp_tool", "prompt", "agent"). '
            f"{_REAL_SCHEMA_HINT}"
        ),
    )


def _require_non_empty_str(
    definition: dict[str, Any],
    field: str,
    *,
    file_path_str: str,
    def_pointer: str,
    type_label: str,
) -> None:
    """Require `field` on `definition` to be present + a non-empty string."""
    if field not in definition:
        raise InvalidHookConfigError(
            f"`{type_label}` hook definition missing required field `{field}`.",
            file_path=file_path_str,
            field_name=f"{def_pointer}/{field}",
            fix_suggestion=f"Add `{field}: <non-empty-string>` to the `{type_label}` hook definition.",
        )
    value = definition[field]
    if not isinstance(value, str) or not value:
        raise InvalidHookConfigError(
            f"`{type_label}` hook definition `{field}` must be a non-empty string; got {type(value).__name__}.",
            file_path=file_path_str,
            field_name=f"{def_pointer}/{field}",
            fix_suggestion=f"Set `{field}` to a non-empty string.",
        )


def _validate_command_definition(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> str:
    """Validate a `command`-type definition's fields; return the command string."""
    if "command" not in definition:
        raise InvalidHookConfigError(
            "Hook definition missing required field `command`.",
            file_path=file_path_str,
            field_name=f"{def_pointer}/command",
            fix_suggestion="Add `command: <shell-command-string>` to the `command` hook definition.",
        )

    command = definition["command"]
    if not isinstance(command, str) or not command:
        raise InvalidHookConfigError(
            f"Hook definition `command` must be a non-empty string; got {type(command).__name__}.",
            file_path=file_path_str,
            field_name=f"{def_pointer}/command",
            fix_suggestion="Set `command` to a non-empty string.",
        )

    if "args" in definition:
        args = definition["args"]
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise InvalidHookConfigError(
                f"Hook definition `args` (optional) must be a list of strings; got {type(args).__name__}.",
                file_path=file_path_str,
                field_name=f"{def_pointer}/args",
                fix_suggestion="Set `args` to a JSON array of strings, or omit the field.",
            )

    return command


def _validate_timeout(
    definition: dict[str, Any],
    *,
    file_path_str: str,
    def_pointer: str,
) -> None:
    """Validate `timeout` when present: int seconds, not bool."""
    if "timeout" in definition:
        timeout = definition["timeout"]
        # bool is a subclass of int — reject explicitly so `timeout: true`
        # doesn't silently coerce to 1.
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            raise InvalidHookConfigError(
                f"Hook definition `timeout` (optional) must be an int (seconds); got {type(timeout).__name__}.",
                file_path=file_path_str,
                field_name=f"{def_pointer}/timeout",
                fix_suggestion="Set `timeout` to an integer number of seconds, or omit.",
            )


_INLINE_SKILL_CANONICAL_KEYS: tuple[str, ...] = ("name", "description")


def _extract_inline_skill_frontmatter(command: str) -> dict[str, Any] | None:
    """Detect + parse an inline YAML frontmatter block at the head of `command`.

    Returns the parsed YAML dict if ALL of these hold:
        1. The command's first line (column 0) is `---`.
        2. A subsequent line (column 0) is also `---` (closing delimiter).
        3. The block between them parses as a YAML mapping.
        4. The mapping contains BOTH `name` and `description` keys
           (the canonical skill-frontmatter shape per PRD FR1).

    The 4th constraint (Story 2.2 code-review Edge-MED-1 fix 2026-05-19)
    eliminates false-positives on shell heredocs that incidentally
    start with `---\\n...\\n---\\n` (e.g., `cat <<EOF` emitting a
    Pandoc front-block or Kubernetes manifest).

    Malformed YAML inside an inline frontmatter is NOT raised — it's
    treated as "no inline skill" and silently ignored.
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
    # Canonical-shape gate: skill frontmatter MUST have both `name`
    # and `description`. Other shapes (heredocs, Pandoc blocks, etc.)
    # are not skills.
    if not all(key in parsed for key in _INLINE_SKILL_CANONICAL_KEYS):
        return None
    return parsed
