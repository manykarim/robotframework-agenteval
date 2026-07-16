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

"""Tier-1 schema keywords: Get Server Config / Get Tool Schema / Validate Tool Schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from AgentEval._core.errors import InvalidConfigError
from MCPLibrary import MCPLibrary


def _write(tmp_path: Path, doc: dict) -> str:
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def _config_with_search(tmp_path: Path, schema: dict) -> str:
    return _write(
        tmp_path,
        {
            "mcpServers": {
                "echo": {
                    "command": "python",
                    "args": ["-m", "echo"],
                    "transport": "stdio",
                    "tools": {"search": schema},
                }
            }
        },
    )


def test_get_server_config_parses_entries(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _write(tmp_path, {"mcpServers": {"echo": {"command": "node", "transport": "stdio", "args": ["s.js"]}}})
    servers = lib.get_server_config(path)
    assert servers["echo"]["transport"] == "stdio"
    assert servers["echo"]["args"] == ["s.js"]


def test_get_server_config_missing_command_points_at_field(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _write(tmp_path, {"mcpServers": {"echo": {"transport": "stdio"}}})
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_server_config(path)
    assert exc.value.field == "/mcpServers/echo/command"


def test_get_server_config_rejects_unsupported_transport(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _write(tmp_path, {"mcpServers": {"echo": {"command": "node", "transport": "websocket"}}})
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_server_config(path)
    assert exc.value.field == "/mcpServers/echo/transport"


def test_get_server_config_missing_file(tmp_path: Path) -> None:
    lib = MCPLibrary()
    with pytest.raises(InvalidConfigError):
        lib.get_server_config(str(tmp_path / "nope.json"))


def test_get_tool_schema_returns_declared_schema(tmp_path: Path) -> None:
    lib = MCPLibrary()
    schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    path = _config_with_search(tmp_path, schema)
    got = lib.get_tool_schema(path, "search")
    assert got == schema


def test_get_tool_schema_unknown_tool_raises_with_pointer(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _config_with_search(tmp_path, {"type": "object"})
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_tool_schema(path, "missing")
    assert exc.value.field == "/mcpServers"


def test_get_tool_schema_unknown_server_raises(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _config_with_search(tmp_path, {"type": "object"})
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_tool_schema(path, "search", server_name="ghost")
    assert exc.value.field == "/mcpServers/ghost"


def test_validate_tool_schema_passes_on_well_formed(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _config_with_search(tmp_path, {"type": "object", "properties": {"query": {"type": "string"}}})
    # No live server involved; a well-formed schema validates cleanly.
    assert lib.validate_tool_schema(path, "search") is None


def test_validate_tool_schema_fails_on_malformed_with_pointer(tmp_path: Path) -> None:
    lib = MCPLibrary()
    # `type` must be a string or list of strings; 123 is not a valid schema.
    path = _config_with_search(tmp_path, {"type": 123})
    with pytest.raises(InvalidConfigError) as exc:
        lib.validate_tool_schema(path, "search")
    assert exc.value.field is not None
    assert exc.value.field.startswith("/mcpServers/echo/tools/search")


def test_validate_tool_schema_unknown_tool_raises(tmp_path: Path) -> None:
    lib = MCPLibrary()
    path = _config_with_search(tmp_path, {"type": "object"})
    with pytest.raises(InvalidConfigError):
        lib.validate_tool_schema(path, "missing")
