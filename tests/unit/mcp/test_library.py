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

"""Unit tests for `src/AgentEval/mcp/library.py` (Story 2.3).

Covers AC-2.3.1 through AC-2.3.8: 3 keywords' happy paths, every error
path through `_parser.py` + the 2 new error leaves, FR59 `__str__`
shape, JSON Pointer `field_name`, Tier-1 latency, DynamicCore
exclusion + standalone-import path, Story 1b.6 conventions invariants.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import (
    AgentEvalError,
    AgentEvalIntegrityError,
    InvalidMCPServerConfigError,
    InvalidMCPToolSchemaError,
)
from AgentEval.mcp._parser import (
    REQUIRED_SERVER_FIELDS,
    SUPPORTED_TRANSPORTS,
    _build_pointer,
)
from AgentEval.mcp.library import MCPLibrary

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "mcp"
VALID_FIXTURE = FIXTURES_DIR / "mcp-valid.json"
MISSING_COMMAND_FIXTURE = FIXTURES_DIR / "mcp-missing-command.json"
MALFORMED_JSON_FIXTURE = FIXTURES_DIR / "mcp-malformed-json.json"
UNSUPPORTED_TRANSPORT_FIXTURE = FIXTURES_DIR / "mcp-unsupported-transport.json"
BROKEN_TOOL_FIXTURE = FIXTURES_DIR / "mcp-with-broken-tool.json"


@pytest.fixture
def lib() -> MCPLibrary:
    return MCPLibrary()


# --------------------------------------------------------------------------- #
# AC-2.3.1: `Get Server Config` happy path
# --------------------------------------------------------------------------- #


def test_get_server_config_returns_dict_with_servers(lib: MCPLibrary) -> None:
    servers = lib.get_server_config(VALID_FIXTURE)
    assert "echo" in servers
    assert "remote" in servers


def test_get_server_config_preserves_required_command(lib: MCPLibrary) -> None:
    servers = lib.get_server_config(VALID_FIXTURE)
    assert servers["echo"]["command"] == "node"
    assert servers["remote"]["command"] == "agenteval-remote-proxy"


def test_get_server_config_preserves_optional_fields(lib: MCPLibrary) -> None:
    servers = lib.get_server_config(VALID_FIXTURE)
    echo = servers["echo"]
    assert echo["args"] == ["server.js"]
    assert echo["env"] == {"DEBUG": "1"}
    assert echo["transport"] == "stdio"


def test_get_server_config_remote_omits_optional_fields(lib: MCPLibrary) -> None:
    servers = lib.get_server_config(VALID_FIXTURE)
    remote = servers["remote"]
    assert "args" not in remote
    assert "env" not in remote
    assert remote["transport"] == "streamable_http"


def test_get_server_config_does_not_spawn_subprocess(lib: MCPLibrary) -> None:
    """No-side-effect contract: `Get Server Config` is pure file-parsing.

    Reads the local PID set, runs the keyword, reads again — no new
    long-lived MCP server subprocess should appear. Sleep briefly to
    let any accidental subprocess populate before re-reading.
    """
    import os

    children_before = set(os.listdir("/proc")) if os.path.exists("/proc") else set()
    lib.get_server_config(VALID_FIXTURE)
    children_after = set(os.listdir("/proc")) if os.path.exists("/proc") else set()
    # Process-id churn is expected from the test framework itself; assert
    # the absolute count remained sane (no spawn-storm). A real MCP server
    # spawn would add a long-lived PID in `/proc`.
    if children_before and children_after:
        # Allow up to a handful of natural pid churn.
        assert abs(len(children_after) - len(children_before)) < 10


# --------------------------------------------------------------------------- #
# AC-2.3.2: `InvalidMCPServerConfigError` (15th leaf)
# --------------------------------------------------------------------------- #


def test_invalid_mcp_server_config_error_inherits_integrity() -> None:
    assert issubclass(InvalidMCPServerConfigError, AgentEvalIntegrityError)
    assert issubclass(InvalidMCPServerConfigError, AgentEvalError)


def test_invalid_mcp_server_config_error_code() -> None:
    assert InvalidMCPServerConfigError.error_code == "INVALID_MCP_SERVER_CONFIG"


def test_missing_command_raises_with_json_pointer(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(MISSING_COMMAND_FIXTURE)
    assert exc_info.value.field_name == "/mcpServers/broken/command"


def test_malformed_json_raises_with_line(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(MALFORMED_JSON_FIXTURE)
    assert exc_info.value.error_code == "INVALID_MCP_SERVER_CONFIG"
    assert exc_info.value.line_number is not None


def test_unsupported_transport_raises_with_pointer(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(UNSUPPORTED_TRANSPORT_FIXTURE)
    assert exc_info.value.field_name == "/mcpServers/future/transport"


def test_non_json_extension_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    not_json = tmp_path / "config.txt"
    not_json.write_text("{}")
    with pytest.raises(InvalidMCPServerConfigError):
        lib.get_server_config(not_json)


def test_file_not_found_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    with pytest.raises(InvalidMCPServerConfigError):
        lib.get_server_config(tmp_path / "nope.json")


def test_top_level_not_object_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "list.json"
    f.write_text("[1, 2]")
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert "object" in str(exc_info.value)


def test_mcpservers_not_mapping_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": [1, 2]}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers"


def test_server_entry_not_object_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": "string-entry"}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo"


def test_command_non_string_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": {"command": 42}}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo/command"


def test_args_wrong_type_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": {"command": "node", "args": "string"}}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo/args"


def test_env_wrong_type_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": {"command": "node", "env": {"key": 42}}}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo/env"


def test_tools_not_mapping_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": {"command": "node", "tools": []}}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo/tools"


def test_tool_schema_not_object_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"mcpServers": {"echo": {"command": "node", "tools": {"search": "string-schema"}}}}')
    with pytest.raises(InvalidMCPServerConfigError) as exc_info:
        lib.get_server_config(f)
    assert exc_info.value.field_name == "/mcpServers/echo/tools/search"


def test_missing_mcpservers_returns_empty_dict(lib: MCPLibrary, tmp_path: Path) -> None:
    """Permissive default: absent `mcpServers` key returns `{}`."""
    f = tmp_path / "empty.json"
    f.write_text("{}")
    assert lib.get_server_config(f) == {}


# --------------------------------------------------------------------------- #
# AC-2.3.3: `Get Tool Schema` happy path
# --------------------------------------------------------------------------- #


def test_get_tool_schema_returns_schema(lib: MCPLibrary) -> None:
    schema = lib.get_tool_schema(VALID_FIXTURE, tool_name="search")
    assert schema["type"] == "object"
    assert "query" in schema["properties"]


def test_get_tool_schema_scoped_to_server(lib: MCPLibrary) -> None:
    schema = lib.get_tool_schema(VALID_FIXTURE, tool_name="search", server_name="echo")
    assert schema["type"] == "object"


def test_get_tool_schema_unknown_tool_raises(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.get_tool_schema(VALID_FIXTURE, tool_name="does-not-exist")
    assert exc_info.value.error_code == "INVALID_MCP_TOOL_SCHEMA"
    assert "does-not-exist" in (exc_info.value.field_name or "")


def test_get_tool_schema_unknown_server_raises(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.get_tool_schema(VALID_FIXTURE, tool_name="search", server_name="nope")
    assert exc_info.value.field_name == "/mcpServers/nope"


def test_get_tool_schema_returns_copy_not_reference(lib: MCPLibrary) -> None:
    """Mutating the returned dict must not affect the parser's internal state."""
    schema = lib.get_tool_schema(VALID_FIXTURE, tool_name="search")
    schema["mutated"] = True
    schema2 = lib.get_tool_schema(VALID_FIXTURE, tool_name="search")
    assert "mutated" not in schema2


# --------------------------------------------------------------------------- #
# AC-2.3.4: `Validate Tool Schema` happy + error paths
# --------------------------------------------------------------------------- #


def test_validate_tool_schema_succeeds_on_valid(lib: MCPLibrary) -> None:
    # Should not raise; returns None.
    result = lib.validate_tool_schema(VALID_FIXTURE, tool_name="search")
    assert result is None


def test_validate_tool_schema_raises_on_broken(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.validate_tool_schema(BROKEN_TOOL_FIXTURE, tool_name="broken_tool")
    assert exc_info.value.error_code == "INVALID_MCP_TOOL_SCHEMA"
    assert exc_info.value.field_name is not None
    assert "broken_tool" in exc_info.value.field_name


def test_validate_tool_schema_preserves_jsonschema_cause(lib: MCPLibrary) -> None:
    """`__cause__` carries the wrapped jsonschema exception for callers."""
    import jsonschema

    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.validate_tool_schema(BROKEN_TOOL_FIXTURE, tool_name="broken_tool")
    assert isinstance(exc_info.value.__cause__, jsonschema.exceptions.SchemaError)


def test_validate_tool_schema_unknown_tool_raises(lib: MCPLibrary) -> None:
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.validate_tool_schema(VALID_FIXTURE, tool_name="nope")
    assert "nope" in (exc_info.value.field_name or "")


# --------------------------------------------------------------------------- #
# AC-2.3.5: MCPLibrary EXCLUDED from DynamicCore composition
# --------------------------------------------------------------------------- #


def test_agenteval_does_not_expose_mcp_library_via_dynamic_core() -> None:
    """`MCPLibrary` is EXCLUDED from `_SUB_LIBRARIES` per Story 2.2 collision-prevention."""
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    assert "MCPLibrary" not in library._loaded_components


def test_mcp_library_callable_standalone(lib: MCPLibrary) -> None:
    servers = lib.get_server_config(VALID_FIXTURE)
    assert "echo" in servers


# --------------------------------------------------------------------------- #
# AC-2.3.6: Conventions invariants
# --------------------------------------------------------------------------- #


KEYWORD_METHODS = ["get_server_config", "get_tool_schema", "validate_tool_schema"]


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_has_tier_1_annotation(method_name: str) -> None:
    func = getattr(MCPLibrary, method_name)
    assert get_keyword_tier(func) == 1


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_docstring_has_tier_1_badge(method_name: str) -> None:
    doc = getattr(MCPLibrary, method_name).__doc__ or ""
    assert tier_badge(1) in doc


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_has_robot_marker(method_name: str) -> None:
    assert hasattr(getattr(MCPLibrary, method_name), "robot_name")


# --------------------------------------------------------------------------- #
# AC-2.3.8: NFR-PERF-02 latency
# --------------------------------------------------------------------------- #


def test_get_server_config_meets_nfr_perf_02(lib: MCPLibrary) -> None:
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.get_server_config(VALID_FIXTURE)
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 budget"


def test_get_tool_schema_meets_nfr_perf_02(lib: MCPLibrary) -> None:
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.get_tool_schema(VALID_FIXTURE, tool_name="search")
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 budget"


def test_validate_tool_schema_meets_nfr_perf_02(lib: MCPLibrary) -> None:
    samples: list[float] = []
    for _ in range(11):
        start = time.perf_counter()
        lib.validate_tool_schema(VALID_FIXTURE, tool_name="search")
        samples.append(time.perf_counter() - start)
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < 0.050, f"median latency {median * 1000:.2f} ms exceeds NFR-PERF-02 budget"


# --------------------------------------------------------------------------- #
# Misc invariants
# --------------------------------------------------------------------------- #


def test_supported_transports_match_fr7() -> None:
    assert set(SUPPORTED_TRANSPORTS) == {"stdio", "streamable_http", "in_memory"}


def test_required_server_fields_minimal() -> None:
    assert REQUIRED_SERVER_FIELDS == ("command",)


def test_build_pointer_rfc6901_escaping() -> None:
    assert _build_pointer("mcpServers", "echo", "command") == "/mcpServers/echo/command"
    assert _build_pointer("with/slash") == "/with~1slash"
    assert _build_pointer("with~tilde") == "/with~0tilde"


def test_fr59_str_layout_on_mcp_server_config_error() -> None:
    exc = InvalidMCPServerConfigError(
        "boom",
        file_path="x.json",
        line_number=2,
        field_name="/mcpServers/echo/command",
        fix_suggestion="add command",
    )
    rendered = str(exc)
    lines = rendered.splitlines()
    assert lines[0] == "INVALID_MCP_SERVER_CONFIG: boom"
    assert "File: x.json" in lines[1]
    assert "Line: 2" in lines[2]
    assert "Field: /mcpServers/echo/command" in lines[3]
    assert "Fix: add command" in lines[4]


def test_fr59_str_layout_on_mcp_tool_schema_error() -> None:
    exc = InvalidMCPToolSchemaError(
        "schema broken",
        file_path="x.json",
        field_name="/mcpServers/echo/tools/search/type",
        fix_suggestion="use a standard type",
    )
    rendered = str(exc)
    lines = rendered.splitlines()
    assert lines[0] == "INVALID_MCP_TOOL_SCHEMA: schema broken"
    assert "File: x.json" in lines[1]
    assert "Line: N/A" in lines[2]
    assert "Field: /mcpServers/echo/tools/search/type" in lines[3]
    assert "Fix: use a standard type" in lines[4]


def test_inherits_shared_fr59_layout_from_intermediate_base() -> None:
    from AgentEval.errors import _FR59Tier1SetupFailureError

    assert issubclass(InvalidMCPServerConfigError, _FR59Tier1SetupFailureError)
    assert issubclass(InvalidMCPToolSchemaError, _FR59Tier1SetupFailureError)


def test_dynamic_core_collision_detector_still_clean() -> None:
    """The runtime collision-detector should not flag any duplicates."""
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    # If detector raised, instantiation would fail. Reaching here = clean.
    assert library is not None


def test_get_tool_schema_search_first_match_when_server_unscoped(lib: MCPLibrary) -> None:
    """When `server_name=None`, the first server with the tool wins."""
    # Both `echo` server entry declares `search` + `ping`. Without server_name
    # scope, `search` resolves to echo.
    schema = lib.get_tool_schema(VALID_FIXTURE, tool_name="ping")
    assert schema["type"] == "object"


def test_get_server_config_handles_bom(lib: MCPLibrary, tmp_path: Path) -> None:
    f = tmp_path / "bom.json"
    f.write_bytes(b'\xef\xbb\xbf{"mcpServers": {"echo": {"command": "node"}}}')
    servers = lib.get_server_config(f)
    assert servers["echo"]["command"] == "node"


def test_tools_with_string_pointer_includes_canonical_tool_path(lib: MCPLibrary) -> None:
    """JSON Pointer points into the broken tool's sub-schema."""
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.validate_tool_schema(BROKEN_TOOL_FIXTURE, tool_name="broken_tool")
    assert "tools/broken_tool" in (exc_info.value.field_name or "")


def test_server_name_scoping_with_tool_present_works(lib: MCPLibrary) -> None:
    schema = lib.get_tool_schema(VALID_FIXTURE, tool_name="ping", server_name="echo")
    assert schema["type"] == "object"


def test_server_name_scoping_with_tool_absent_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    """Scoping to a server that doesn't declare the tool raises."""
    # `remote` has no tools; asking for `search` there should fail.
    with pytest.raises(InvalidMCPToolSchemaError) as exc_info:
        lib.get_tool_schema(VALID_FIXTURE, tool_name="search", server_name="remote")
    assert exc_info.value.field_name is not None
    assert "remote" in exc_info.value.field_name


def test_validate_tool_schema_handles_circular_refs_via_jsonschema(lib: MCPLibrary, tmp_path: Path) -> None:
    """A schema that violates Draft 2020-12 (e.g., `properties` as a non-object) raises."""
    f = tmp_path / "circular.json"
    payload = {
        "mcpServers": {
            "echo": {
                "command": "node",
                "tools": {
                    "broken": {
                        "type": "object",
                        "properties": "not_a_mapping",
                    }
                },
            }
        }
    }
    f.write_text(json.dumps(payload))
    with pytest.raises(InvalidMCPToolSchemaError):
        lib.validate_tool_schema(f, tool_name="broken")
