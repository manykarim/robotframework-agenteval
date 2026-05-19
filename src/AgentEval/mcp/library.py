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

"""MCP sub-library — static-inspection keywords for `.mcp.json` files.

Story 2.3 ships 3 Tier-1 keywords per PRD FR5 + FR6 Phase-1 scope:
- `Get Server Config` — parse a `.mcp.json` server-config file into a
  dict mapping `<server_name>` → entry (`command`, `args`, `env`,
  `transport`, `tools`).
- `Get Tool Schema` — return the JSON Schema for a declared tool from
  the Phase-1 `.mcp.json:tools` extension (Phase-2 + Epic 3 add
  runtime retrieval).
- `Validate Tool Schema` — verify the tool's schema is well-formed
  per the jsonschema Draft 2020-12 meta-schema; raise
  `InvalidMCPToolSchemaError` with an RFC 6901 JSON Pointer + the
  wrapped jsonschema error message.

Per Story 2.2 code-review HIGH-1 ratification (DynamicCore composition
keyword-name collision prevention): `MCPLibrary` is NOT registered in
`src/AgentEval/__init__.py:_SUB_LIBRARIES`. Users access via standalone
import:

    *** Settings ***
    Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP

    *** Test Cases ***
    Echo Server Declares Stdio Transport
        ${servers}=    MCP.Get Server Config    ${CURDIR}/.mcp.json
        Should Be Equal    ${servers["echo"]["transport"]}    stdio

Phase-1 limitations:
- Tool schemas come from the declarative `.mcp.json:tools` extension
  (Story 2.3 drift-check D-D); PRD FR6 runtime retrieval is Phase-2.
- Transport enum: only `stdio` / `streamable_http` / `in_memory` per
  PRD FR7.
- jsonschema validation uses Draft 2020-12 meta-schema only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.mcp._parser import (
    get_tool_schema,
    parse_mcp_servers,
    validate_tool_schema,
)

__all__ = ["MCPLibrary"]


class MCPLibrary:
    """Static-inspection keywords for `.mcp.json` files [Tier 1 — Deterministic]."""

    @keyword(name="Get Server Config")
    @tier(1)
    def get_server_config(self, path: str | Path) -> dict[str, dict[str, Any]]:
        """Parse a `.mcp.json` file's `mcpServers` declarations.

        [Tier 1 — Deterministic] — pure file-read + JSON parse + per-entry
        validation. Does NOT spawn any MCP server subprocesses (verifiable
        via process inventory diff). Median ≤ 50 ms per NFR-PERF-02.

        Args:
            path: Filesystem path to the `.mcp.json` file.

        Returns:
            A dict mapping `<server_name>` → server-entry dict. Each
            entry has at minimum `command` (str); may contain `args`
            (list[str]), `env` (dict[str,str]), `transport`
            (str ∈ {`stdio`, `streamable_http`, `in_memory`} per PRD
            FR7), `tools` (dict[str, JSON Schema] — Phase-1 declarative
            extension).

        Raises:
            InvalidMCPServerConfigError: On any structural failure —
                file not found, wrong extension, malformed JSON, missing
                `command`, wrong types, unsupported transport. The
                `field_name` attribute carries an RFC 6901 JSON Pointer
                into the offending location.
        """
        return parse_mcp_servers(path)

    @keyword(name="Get Tool Schema")
    @tier(1)
    def get_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Return a tool's input JSON Schema from `.mcp.json:tools`.

        [Tier 1 — Deterministic] — Phase-1 reads from the declarative
        `tools` extension on each server entry (Story 2.3 drift-check
        D-D 2026-05-19). PRD FR6's "against a running or configured
        MCP server" runtime path is Phase-2 + Epic 3 scope.

        Args:
            config_path: Path to the `.mcp.json` file.
            tool_name: Name of the tool whose schema to retrieve.
            server_name: When `None`, search every server in
                declaration order + return the first match. When set,
                only consult the named server.

        Returns:
            The tool's input JSON Schema as a dict.

        Raises:
            InvalidMCPServerConfigError: On `.mcp.json` structural
                failure.
            InvalidMCPToolSchemaError: If the tool is not declared on
                any candidate server (or on the named server when
                `server_name` is set).
        """
        return get_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    @keyword(name="Validate Tool Schema")
    @tier(1)
    def validate_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> None:
        """Validate a tool's schema against the jsonschema Draft 2020-12 meta-schema.

        [Tier 1 — Deterministic] — verifies the schema-validity of an
        MCP tool's input schema. Does NOT validate any tool-call's
        ARGUMENTS against the schema — that's a runtime concern Epic 3
        will own. Median ≤ 50 ms per NFR-PERF-02.

        Args:
            config_path: Path to the `.mcp.json` file.
            tool_name: Tool whose schema to validate.
            server_name: Optional server scoping (see `Get Tool Schema`).

        Returns:
            None on success.

        Raises:
            InvalidMCPServerConfigError: On `.mcp.json` structural
                failure.
            InvalidMCPToolSchemaError: If the tool is not declared OR
                its schema fails Draft 2020-12 meta-schema validation.
                `field_name` carries an RFC 6901 JSON Pointer into the
                offending sub-schema; the wrapped jsonschema exception
                is available via `__cause__`.
        """
        validate_tool_schema(config_path, tool_name=tool_name, server_name=server_name)
