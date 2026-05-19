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

"""`.mcp.json` parser + tool-schema validator (Story 2.3).

Parses Claude Code `.mcp.json` configurations per PRD FR5 + the declared
MCP server format:

    {
      "mcpServers": {
        "echo": {
          "command": "node",
          "args": ["server.js"],
          "env": {"DEBUG": "1"},
          "transport": "stdio",
          "tools": {
            "search": {"type": "object", "properties": {...}}
          }
        }
      }
    }

The `tools` field on each server entry is a Phase-1 declarative
extension ratified by Story 2.3 pre-create-story drift-check D-D
2026-05-19. PRD FR6's "against a running or configured MCP server"
runtime retrieval is Phase-2 + Epic 3 scope. The declarative shape
provides the Phase-1 Tier-1 tool-schema inspection surface.

`InvalidMCPServerConfigError` (15th leaf) covers `.mcp.json` structural
failures; `InvalidMCPToolSchemaError` (16th leaf) covers tool-schema
validation failures against the jsonschema Draft 2020-12 meta-schema.
Both errors' `field_name` attribute carries an RFC 6901 JSON Pointer
(e.g., `/mcpServers/echo/command` or
`/mcpServers/echo/tools/search/properties/query`).

Architecture-layout deviation (inherited from Story 2.1): architecture
L843-847 pins `_internal.py` as the canonical helper module name.
Story 2.3 inherits Story 2.1's `_parser.py` deviation; tracked in
deferred-work for Phase-1.5 cleanup.

Transport enumeration per PRD FR7: only `stdio`, `streamable_http`,
`in_memory` are accepted. Other values (e.g., `sse`, `websocket`)
raise `InvalidMCPServerConfigError`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from AgentEval.errors import InvalidMCPServerConfigError, InvalidMCPToolSchemaError

__all__ = [
    "SUPPORTED_TRANSPORTS",
    "REQUIRED_SERVER_FIELDS",
    "parse_mcp_servers",
    "get_tool_schema",
    "validate_tool_schema",
]


# PRD FR7: `<stdio|streamable_http|in_memory>`. Other transport values
# (e.g., MCP-spec `sse`, future `websocket`) are NOT supported in
# Phase-1 — the `transport` field MUST be one of these 3.
SUPPORTED_TRANSPORTS: tuple[str, ...] = ("stdio", "streamable_http", "in_memory")

REQUIRED_SERVER_FIELDS: tuple[str, ...] = ("command",)


def _build_pointer(*segments: str | int) -> str:
    """Build an RFC 6901 JSON Pointer from path segments.

    Per RFC 6901 §3: `~` → `~0`, `/` → `~1`. The `~` substitution MUST
    precede the `/` substitution to avoid double-encoding (matches
    `hooks/_parser._build_pointer`).
    """
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, int):
            parts.append(str(seg))
        else:
            parts.append(seg.replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(parts)


def _load_mcp_document(path: str | Path) -> tuple[dict[str, Any], str]:
    """Read + JSON-parse the `.mcp.json` file. Returns `(document, file_path_str)`.

    Raises `InvalidMCPServerConfigError` on file / extension / JSON failure.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".json":
        raise InvalidMCPServerConfigError(
            f"MCP config file must have a .json extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix_suggestion="Rename the file so it ends in `.json` (Claude Code uses `.mcp.json`).",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidMCPServerConfigError(
            f"MCP config file not found: {file_path_str}.",
            file_path=file_path_str,
            fix_suggestion="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidMCPServerConfigError(
            f"MCP config file could not be read: {exc}.",
            file_path=file_path_str,
            fix_suggestion="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidMCPServerConfigError(
            f"JSON failed to parse: {exc.msg}.",
            file_path=file_path_str,
            line_number=exc.lineno,
            fix_suggestion="Check JSON quoting + commas; run a JSON linter on the file.",
        ) from exc

    if not isinstance(document, dict):
        raise InvalidMCPServerConfigError(
            f"Top-level JSON value must be an object; got {type(document).__name__}.",
            file_path=file_path_str,
            field_name="",
            fix_suggestion="Wrap the content in `{ ... }` with a `mcpServers` field.",
        )

    return document, file_path_str


def parse_mcp_servers(path: str | Path) -> dict[str, dict[str, Any]]:
    """Parse a `.mcp.json` file + return a dict of server-name → entry.

    Args:
        path: Filesystem path to the `.mcp.json` file.

    Returns:
        A dict mapping `<server_name>` → server-entry dict. Each entry
        has at minimum `command` (str). Optional fields preserved when
        present + type-checked: `args` (list[str]), `env` (dict[str,str]),
        `transport` (str ∈ `SUPPORTED_TRANSPORTS`), `tools`
        (dict[str, dict] — Phase-1 declarative tool-schema extension).
        If `mcpServers` is absent (permissive default per PRD FR5
        silence on requirement), returns `{}`.

    Raises:
        InvalidMCPServerConfigError: On structural failure (file not
            found, malformed JSON, missing `command`, wrong types,
            unsupported transport). `field_name` carries an RFC 6901
            JSON Pointer into the offending location.
    """
    document, file_path_str = _load_mcp_document(path)

    servers_section = document.get("mcpServers", {})
    if not isinstance(servers_section, dict):
        raise InvalidMCPServerConfigError(
            f"`mcpServers` must be a mapping; got {type(servers_section).__name__}.",
            file_path=file_path_str,
            field_name="/mcpServers",
            fix_suggestion="Set `mcpServers: {server_name: {command: ..., ...}}`.",
        )

    result: dict[str, dict[str, Any]] = {}
    for server_name, entry in servers_section.items():
        entry_pointer = _build_pointer("mcpServers", server_name)
        if not isinstance(entry, dict):
            raise InvalidMCPServerConfigError(
                f"MCP server entry must be an object; got {type(entry).__name__}.",
                file_path=file_path_str,
                field_name=entry_pointer,
                fix_suggestion=f"Set `{entry_pointer}` to a JSON object with `command` + optional fields.",
            )
        result[server_name] = _validate_server_entry(entry, file_path_str=file_path_str, entry_pointer=entry_pointer)

    return result


def _validate_server_entry(
    entry: dict[str, Any],
    *,
    file_path_str: str,
    entry_pointer: str,
) -> dict[str, Any]:
    """Validate one MCP-server entry; return the validated dict."""
    if "command" not in entry:
        raise InvalidMCPServerConfigError(
            "MCP server entry missing required field `command`.",
            file_path=file_path_str,
            field_name=f"{entry_pointer}/command",
            fix_suggestion="Add `command: <executable-name>` to the server entry.",
        )

    command = entry["command"]
    if not isinstance(command, str) or not command:
        raise InvalidMCPServerConfigError(
            f"MCP server `command` must be a non-empty string; got {type(command).__name__}.",
            file_path=file_path_str,
            field_name=f"{entry_pointer}/command",
            fix_suggestion="Set `command` to a non-empty executable name (e.g., `node`).",
        )

    if "args" in entry:
        args = entry["args"]
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise InvalidMCPServerConfigError(
                f"MCP server `args` (optional) must be a list of strings; got {type(args).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/args",
                fix_suggestion="Set `args` to a JSON array of strings, or omit.",
            )

    if "env" in entry:
        env = entry["env"]
        if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
            raise InvalidMCPServerConfigError(
                f"MCP server `env` (optional) must be a dict[str,str]; got {type(env).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/env",
                fix_suggestion="Set `env` to a JSON object whose keys and values are all strings.",
            )

    if "transport" in entry:
        transport = entry["transport"]
        if not isinstance(transport, str) or transport not in SUPPORTED_TRANSPORTS:
            raise InvalidMCPServerConfigError(
                f"MCP server `transport` (optional) must be one of {list(SUPPORTED_TRANSPORTS)!r}; got {transport!r}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/transport",
                fix_suggestion=(f"Set `transport` to one of {list(SUPPORTED_TRANSPORTS)!r} per PRD FR7, or omit."),
            )

    if "tools" in entry:
        tools = entry["tools"]
        if not isinstance(tools, dict):
            raise InvalidMCPServerConfigError(
                f"MCP server `tools` (optional) must be a dict[str, schema]; got {type(tools).__name__}.",
                file_path=file_path_str,
                field_name=f"{entry_pointer}/tools",
                fix_suggestion="Set `tools` to a JSON object mapping tool_name → JSON Schema, or omit.",
            )
        for tool_name, tool_schema in tools.items():
            if not isinstance(tool_schema, dict):
                raise InvalidMCPServerConfigError(
                    f"MCP tool schema `{tool_name}` must be a JSON object; got {type(tool_schema).__name__}.",
                    file_path=file_path_str,
                    field_name=f"{entry_pointer}/tools/{tool_name}",
                    fix_suggestion=f"Set `{entry_pointer}/tools/{tool_name}` to a JSON Schema object.",
                )

    return dict(entry)


def get_tool_schema(
    path: str | Path,
    *,
    tool_name: str,
    server_name: str | None = None,
) -> dict[str, Any]:
    """Return the JSON Schema for a tool declared in `.mcp.json:tools`.

    Phase-1 reads from the declarative `tools` extension (Story 2.3
    drift-check D-D). PRD FR6 runtime retrieval is Phase-2 + Epic 3.

    Args:
        path: Path to the `.mcp.json` file.
        tool_name: Name of the tool whose schema to return.
        server_name: When `None` (default), the tool is searched across
            ALL servers in declaration order; the first match wins.
            When set, only the named server is consulted.

    Returns:
        The JSON Schema dict for the tool's input parameters.

    Raises:
        InvalidMCPServerConfigError: On structural failure of the
            `.mcp.json` itself (delegated to `parse_mcp_servers`).
        InvalidMCPToolSchemaError: If the tool is not declared OR if
            `server_name` is set but the server doesn't exist OR if
            the located schema is not a mapping.
    """
    servers = parse_mcp_servers(path)
    file_path_str = str(Path(path))

    if server_name is not None:
        if server_name not in servers:
            raise InvalidMCPToolSchemaError(
                f"MCP server {server_name!r} not declared in {file_path_str}.",
                file_path=file_path_str,
                field_name=_build_pointer("mcpServers", server_name),
                fix_suggestion=(f"Check the server name; known servers: {sorted(servers.keys())!r}."),
            )
        candidates = [(server_name, servers[server_name])]
    else:
        candidates = list(servers.items())

    for _srv_name, entry in candidates:
        tools = entry.get("tools", {})
        if tool_name in tools:
            return dict(tools[tool_name])

    raise InvalidMCPToolSchemaError(
        f"MCP tool {tool_name!r} not declared in any server's `tools` extension.",
        file_path=file_path_str,
        field_name=(
            _build_pointer("mcpServers", server_name, "tools", tool_name)
            if server_name
            else f"/mcpServers/*/tools/{tool_name}"
        ),
        fix_suggestion=(
            f"Add `{tool_name}` to the server's `tools` mapping with a JSON Schema value, "
            f"or check the spelling. Phase-1 reads schemas from the declarative `tools` "
            f"extension; runtime retrieval lands Phase-2 per PRD FR6."
        ),
    )


def validate_tool_schema(
    path: str | Path,
    *,
    tool_name: str,
    server_name: str | None = None,
) -> None:
    """Validate that a tool's schema is a well-formed JSON Schema (Draft 2020-12).

    Args:
        path: Path to the `.mcp.json` file.
        tool_name: Name of the tool whose schema to validate.
        server_name: Optional server scoping (see `get_tool_schema`).

    Returns:
        None on success.

    Raises:
        InvalidMCPServerConfigError: On `.mcp.json` structural failure.
        InvalidMCPToolSchemaError: If the tool is not declared OR the
            schema fails Draft 2020-12 meta-schema validation. The
            wrapped jsonschema exception is available via `__cause__`.
    """
    schema = get_tool_schema(path, tool_name=tool_name, server_name=server_name)
    file_path_str = str(Path(path))

    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        # `exc.absolute_path` is a deque of segments into the schema; build
        # an RFC 6901 pointer from `mcpServers/<server>/tools/<tool>/...`
        # — when server_name is None we omit the server segment in the
        # message but include the tool path.
        base_segments: list[str | int] = ["mcpServers"]
        if server_name is not None:
            base_segments.append(server_name)
        else:
            base_segments.append("*")
        base_segments.extend(["tools", tool_name])
        for seg in exc.absolute_path:
            base_segments.append(seg)
        pointer = _build_pointer(*base_segments)
        raise InvalidMCPToolSchemaError(
            f"MCP tool {tool_name!r} schema failed Draft 2020-12 validation: {exc.message}.",
            file_path=file_path_str,
            field_name=pointer,
            fix_suggestion=(
                "Repair the JSON Schema to conform to Draft 2020-12; the wrapped jsonschema "
                "exception is available via `__cause__` for the verbatim diagnostic."
            ),
        ) from exc
