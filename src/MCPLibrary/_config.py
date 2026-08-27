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

"""Deterministic `.mcp.json` parsing + tool-schema validation.

Pure file-read + JSON parse + jsonschema Draft 2020-12 checks. No MCP SDK,
no live server - this is the Tier-1 path that runs with the base install.
Every failure raises ``InvalidConfigError`` whose ``field`` is an RFC 6901
JSON Pointer at the offending location.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from AgentEval._core.errors import InvalidConfigError

__all__ = [
    "SUPPORTED_TRANSPORTS",
    "parse_mcp_servers",
    "get_tool_schema",
    "validate_tool_schema",
]

# The transport enum a `.mcp.json` server entry may declare.
SUPPORTED_TRANSPORTS: tuple[str, ...] = ("stdio", "streamable_http", "sse", "in_memory")

# Claude Code's ``.mcp.json`` entry ``type`` field (distinct from the library
# ``transport`` enum above). ``http``/``sse`` are remote servers; ``stdio`` (or an
# absent ``type``) is a local subprocess server.
REMOTE_ENTRY_TYPES: frozenset[str] = frozenset({"http", "sse"})
ACCEPTED_ENTRY_TYPES: frozenset[str] = frozenset({"http", "sse", "stdio"})


def _pointer(*segments: str | int) -> str:
    """Build an RFC 6901 JSON Pointer from path segments (``~``/``/`` escaped)."""
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, int):
            parts.append(str(seg))
        else:
            parts.append(seg.replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(parts)


def _load_document(path: str | Path) -> tuple[dict[str, Any], str]:
    """Read + JSON-parse a `.mcp.json` file into a dict. Raise on any failure."""
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".json":
        raise InvalidConfigError(
            f"MCP config file must end in .json; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix="Rename the file so it ends in `.json` (Claude Code uses `.mcp.json`).",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidConfigError(
            f"MCP config file not found: {file_path_str}.",
            file_path=file_path_str,
            fix="Check the path; make sure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidConfigError(
            f"MCP config file could not be read: {exc}.",
            file_path=file_path_str,
            fix="Check the file's permissions and encoding (expected UTF-8).",
        ) from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(
            f"JSON failed to parse at line {exc.lineno}: {exc.msg}.",
            file_path=file_path_str,
            fix="Check the JSON quoting and commas; run a JSON linter on the file.",
        ) from exc

    if not isinstance(document, dict):
        raise InvalidConfigError(
            f"Top-level JSON value must be an object; got {type(document).__name__}.",
            file_path=file_path_str,
            field="",
            fix="Wrap the content in `{ ... }` with an `mcpServers` field.",
        )
    return document, file_path_str


def parse_mcp_servers(path: str | Path) -> dict[str, dict[str, Any]]:
    """Parse a `.mcp.json` file into ``{server_name: entry}``.

    A **local** entry has a ``command``; optional ``args`` (list[str]),
    ``env`` (dict[str, str]), ``transport`` (one of ``SUPPORTED_TRANSPORTS``),
    and ``tools`` (a declarative ``{tool_name: json_schema}`` map). A **remote**
    entry declares ``type: http``/``sse`` (or carries a ``url`` and no ``command``)
    with a required ``url`` and optional ``headers`` (string map; ``${VAR}``
    placeholders pass through unexpanded). A missing ``mcpServers`` section yields
    ``{}``.
    """
    document, file_path_str = _load_document(path)

    servers_section = document.get("mcpServers", {})
    if not isinstance(servers_section, dict):
        raise InvalidConfigError(
            f"`mcpServers` must be a mapping; got {type(servers_section).__name__}.",
            file_path=file_path_str,
            field="/mcpServers",
            fix="Set `mcpServers: {server_name: {command: ..., ...}}`.",
        )

    result: dict[str, dict[str, Any]] = {}
    for server_name, entry in servers_section.items():
        entry_pointer = _pointer("mcpServers", server_name)
        if not isinstance(entry, dict):
            raise InvalidConfigError(
                f"MCP server entry must be an object; got {type(entry).__name__}.",
                file_path=file_path_str,
                field=entry_pointer,
                fix=f"Set `{entry_pointer}` to a JSON object with `command` and optional fields.",
            )
        result[server_name] = _validate_entry(entry, file_path_str=file_path_str, entry_pointer=entry_pointer)
    return result


def _validate_entry(entry: dict[str, Any], *, file_path_str: str, entry_pointer: str) -> dict[str, Any]:
    """Validate one MCP-server entry and return a shallow copy of it.

    A **remote** entry (Claude Code's ``type: http`` / ``type: sse``, or leniently an
    entry that carries a ``url`` and no ``command``) requires a non-empty ``url`` and
    does not require ``command``; a default/``stdio`` entry keeps requiring
    ``command``. Optional ``headers`` pass through with ``${VAR}`` placeholders
    unexpanded - the parser never resolves or returns a secret.
    """
    entry_type = entry.get("type")
    if entry_type is not None and (not isinstance(entry_type, str) or entry_type not in ACCEPTED_ENTRY_TYPES):
        raise InvalidConfigError(
            f"MCP server `type` must be one of {sorted(ACCEPTED_ENTRY_TYPES)!r}; got {entry_type!r}.",
            file_path=file_path_str,
            field=f"{entry_pointer}/type",
            fix=f"Set `type` to one of {sorted(ACCEPTED_ENTRY_TYPES)!r}, or omit it for a local stdio server.",
        )
    is_remote = (isinstance(entry_type, str) and entry_type in REMOTE_ENTRY_TYPES) or (
        "url" in entry and "command" not in entry
    )

    if is_remote:
        url = entry.get("url")
        if not isinstance(url, str) or not url:
            raise InvalidConfigError(
                "MCP remote server entry requires a non-empty `url`.",
                file_path=file_path_str,
                field=f"{entry_pointer}/url",
                fix="Add `url: <endpoint>` to the remote (http/sse) server entry.",
            )
        if "headers" in entry:
            headers = entry["headers"]
            if not isinstance(headers, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
            ):
                raise InvalidConfigError(
                    f"MCP server `headers` must be a dict[str, str]; got {type(headers).__name__}.",
                    file_path=file_path_str,
                    field=f"{entry_pointer}/headers",
                    fix="Set `headers` to a JSON object of string keys/values (`${VAR}` placeholders are fine).",
                )
        if entry.get("transport") in ("stdio", "in_memory"):
            raise InvalidConfigError(
                f"MCP remote `type: {entry_type}` conflicts with local `transport: {entry['transport']}`.",
                file_path=file_path_str,
                field=f"{entry_pointer}/transport",
                fix="Omit `transport` on a remote http/sse entry, or set it to `streamable_http`/`sse`.",
            )
    else:
        if "command" not in entry:
            raise InvalidConfigError(
                "MCP server entry missing required field `command`.",
                file_path=file_path_str,
                field=f"{entry_pointer}/command",
                fix="Add `command: <executable-name>` to the server entry.",
            )
        command = entry["command"]
        if not isinstance(command, str) or not command:
            raise InvalidConfigError(
                f"MCP server `command` must be a non-empty string; got {type(command).__name__}.",
                file_path=file_path_str,
                field=f"{entry_pointer}/command",
                fix="Set `command` to a non-empty executable name (e.g. `node`).",
            )

    if "args" in entry:
        args = entry["args"]
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise InvalidConfigError(
                f"MCP server `args` must be a list of strings; got {type(args).__name__}.",
                file_path=file_path_str,
                field=f"{entry_pointer}/args",
                fix="Set `args` to a JSON array of strings, or omit it.",
            )

    if "env" in entry:
        env = entry["env"]
        if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
            raise InvalidConfigError(
                f"MCP server `env` must be a dict[str, str]; got {type(env).__name__}.",
                file_path=file_path_str,
                field=f"{entry_pointer}/env",
                fix="Set `env` to a JSON object whose keys and values are all strings.",
            )

    if "transport" in entry:
        transport = entry["transport"]
        if not isinstance(transport, str) or transport not in SUPPORTED_TRANSPORTS:
            raise InvalidConfigError(
                f"MCP server `transport` must be one of {list(SUPPORTED_TRANSPORTS)!r}; got {transport!r}.",
                file_path=file_path_str,
                field=f"{entry_pointer}/transport",
                fix=f"Set `transport` to one of {list(SUPPORTED_TRANSPORTS)!r}, or omit it.",
            )

    if "tools" in entry:
        tools = entry["tools"]
        if not isinstance(tools, dict):
            raise InvalidConfigError(
                f"MCP server `tools` must be a dict[str, schema]; got {type(tools).__name__}.",
                file_path=file_path_str,
                field=f"{entry_pointer}/tools",
                fix="Set `tools` to a JSON object mapping tool_name to a JSON Schema, or omit it.",
            )
        for tool_name, tool_schema in tools.items():
            if not isinstance(tool_schema, dict):
                raise InvalidConfigError(
                    f"MCP tool schema `{tool_name}` must be a JSON object; got {type(tool_schema).__name__}.",
                    file_path=file_path_str,
                    field=f"{entry_pointer}/tools/{tool_name}",
                    fix=f"Set `{entry_pointer}/tools/{tool_name}` to a JSON Schema object.",
                )
    return dict(entry)


def get_tool_schema(
    path: str | Path,
    *,
    tool_name: str,
    server_name: str | None = None,
) -> dict[str, Any]:
    """Return a declared tool's input JSON Schema from `.mcp.json:tools`.

    With ``server_name`` unset, every server is searched in declaration order
    and the first match wins. Raises ``InvalidConfigError`` when the tool (or
    the named server) is not declared.
    """
    servers = parse_mcp_servers(path)
    file_path_str = str(Path(path))
    if server_name == "":
        server_name = None

    if server_name is not None:
        if server_name not in servers:
            raise InvalidConfigError(
                f"MCP server {server_name!r} not declared in {file_path_str}.",
                file_path=file_path_str,
                field=_pointer("mcpServers", server_name),
                fix=f"Check the server name; known servers: {sorted(servers.keys())!r}.",
            )
        candidates = [(server_name, servers[server_name])]
    else:
        candidates = list(servers.items())

    for _srv, entry in candidates:
        tools = entry.get("tools", {})
        if tool_name in tools:
            return dict(tools[tool_name])

    if server_name is not None:
        not_found = _pointer("mcpServers", server_name, "tools", tool_name)
    else:
        not_found = _pointer("mcpServers")
    raise InvalidConfigError(
        f"MCP tool {tool_name!r} not declared in any server's `tools` map.",
        file_path=file_path_str,
        field=not_found,
        fix=f"Add `{tool_name}` to the server's `tools` map with a JSON Schema value, or check the spelling.",
    )


def validate_tool_schema(
    path: str | Path,
    *,
    tool_name: str,
    server_name: str | None = None,
) -> None:
    """Validate a declared tool's schema against JSON Schema Draft 2020-12.

    Checks schema *well-formedness*, not whether any call's arguments conform.
    Raises ``InvalidConfigError`` when the tool is undeclared or its schema is
    malformed; ``field`` points at the offending schema location and the
    wrapped jsonschema error is available via ``__cause__``.
    """
    if server_name == "":
        server_name = None

    servers = parse_mcp_servers(path)
    file_path_str = str(Path(path))

    matched_server: str | None = server_name
    schema: dict[str, Any] | None = None
    if server_name is not None:
        schema = get_tool_schema(path, tool_name=tool_name, server_name=server_name)
    else:
        for srv_name, entry in servers.items():
            tools = entry.get("tools", {})
            if tool_name in tools:
                matched_server = srv_name
                schema = dict(tools[tool_name])
                break
        if schema is None:
            # No server declares it - reuse the canonical not-found error.
            get_tool_schema(path, tool_name=tool_name, server_name=server_name)

    assert schema is not None  # get_tool_schema raised if the tool was absent
    assert matched_server is not None

    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        segments: list[str | int] = ["mcpServers", matched_server, "tools", tool_name]
        segments.extend(exc.absolute_path)
        raise InvalidConfigError(
            f"MCP tool {tool_name!r} schema failed Draft 2020-12 validation: {exc.message}.",
            file_path=file_path_str,
            field=_pointer(*segments),
            fix="Repair the JSON Schema to conform to Draft 2020-12; see __cause__ for the exact diagnostic.",
        ) from exc
