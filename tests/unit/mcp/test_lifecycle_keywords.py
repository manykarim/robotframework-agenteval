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

"""Unit tests for `src/AgentEval/mcp/lifecycle.py` + Story 3.1 keyword extension to `MCPLibrary`."""

from __future__ import annotations

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import UnsupportedMCPVersionError
from AgentEval.mcp.bundled.echo import build_server
from AgentEval.mcp.library import MCPLibrary
from AgentEval.mcp.lifecycle import (
    MCPServerHandle,
    MCPSession,
    connect_to_server,
    start_server,
    stop_server,
)


@pytest.fixture
def lib() -> MCPLibrary:
    return MCPLibrary()


# --------------------------------------------------------------------------- #
# start_server (handle construction)
# --------------------------------------------------------------------------- #


def test_start_server_in_memory_returns_handle() -> None:
    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    assert handle.name == "echo"
    assert handle.transport == "in_memory"
    assert handle.server_factory is build_server


def test_start_server_stdio_returns_handle() -> None:
    handle = start_server(name="echo", transport="stdio", command="python", args=["-m", "AgentEval.mcp.bundled.echo"])
    assert handle.command == "python"
    assert handle.args == ("-m", "AgentEval.mcp.bundled.echo")


def test_start_server_stdio_missing_command_raises() -> None:
    with pytest.raises(ValueError, match="stdio transport requires"):
        start_server(name="echo", transport="stdio")


def test_start_server_in_memory_missing_factory_raises() -> None:
    with pytest.raises(ValueError, match="in_memory transport requires"):
        start_server(name="echo", transport="in_memory")


def test_start_server_streamable_http_passthrough() -> None:
    """`streamable_http` is Phase-1 passthrough — handle constructs without requiring params."""
    handle = start_server(name="remote", transport="streamable_http")
    assert handle.transport == "streamable_http"


def test_start_server_unsupported_transport_raises() -> None:
    with pytest.raises(ValueError, match="unsupported transport"):
        start_server(name="echo", transport="websocket")  # type: ignore[arg-type]


def test_start_server_handle_is_immutable() -> None:
    """`@dataclass(frozen=True)` raises FrozenInstanceError on mutation attempts."""
    import dataclasses

    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    with pytest.raises(dataclasses.FrozenInstanceError):
        handle.name = "renamed"  # type: ignore[misc]


def test_start_server_env_is_copied_not_referenced() -> None:
    """Mutating the source env dict after construction must not affect the handle."""
    src_env = {"KEY": "value"}
    handle = start_server(name="echo", transport="stdio", command="python", env=src_env)
    src_env["KEY"] = "MUTATED"
    assert handle.env == {"KEY": "value"}


# --------------------------------------------------------------------------- #
# connect_to_server — in_memory transport (fast)
# --------------------------------------------------------------------------- #


def test_connect_to_server_in_memory_returns_session() -> None:
    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    session = connect_to_server(handle)
    assert isinstance(session, MCPSession)
    assert session.name == "echo"
    assert session.transport == "in_memory"
    assert session.protocol_version  # non-empty per FR46 gate


def test_connect_to_server_in_memory_surfaces_server_info() -> None:
    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    session = connect_to_server(handle)
    # Bundled echo server identifies itself as `agenteval-bundled-echo`.
    assert session.server_info.get("name") == "agenteval-bundled-echo"


def test_connect_to_server_streamable_http_raises() -> None:
    """Phase-1 passthrough: `streamable_http` connect raises with explicit deferral message."""
    handle = start_server(name="remote", transport="streamable_http")
    with pytest.raises(ValueError, match="Phase-1 passthrough"):
        connect_to_server(handle)


# --------------------------------------------------------------------------- #
# connect_to_server — stdio transport (slower; subprocess)
# --------------------------------------------------------------------------- #


def test_connect_to_server_stdio_returns_session() -> None:
    handle = start_server(
        name="echo",
        transport="stdio",
        command="uv",
        args=["run", "python", "-m", "AgentEval.mcp.bundled.echo"],
    )
    session = connect_to_server(handle)
    assert session.name == "echo"
    assert session.transport == "stdio"
    assert session.protocol_version


# --------------------------------------------------------------------------- #
# stop_server
# --------------------------------------------------------------------------- #


def test_stop_server_is_noop() -> None:
    """Phase-1 design: stop_server is a no-op (per-call sessions self-clean)."""
    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    result = stop_server(handle)
    assert result is None  # explicit None return for keyword chaining


def test_stop_server_idempotent() -> None:
    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    stop_server(handle)
    stop_server(handle)  # second call must not raise


# --------------------------------------------------------------------------- #
# Library keyword surface
# --------------------------------------------------------------------------- #


def test_library_start_server_keyword_returns_handle(lib: MCPLibrary) -> None:
    handle = lib.start_server(name="echo", transport="in_memory", server_factory=build_server)
    assert isinstance(handle, MCPServerHandle)


def test_library_connect_to_server_keyword_returns_session(lib: MCPLibrary) -> None:
    handle = lib.start_server(name="echo", transport="in_memory", server_factory=build_server)
    session = lib.connect_to_server(handle)
    assert isinstance(session, MCPSession)


def test_library_stop_server_keyword_returns_none(lib: MCPLibrary) -> None:
    handle = lib.start_server(name="echo", transport="in_memory", server_factory=build_server)
    assert lib.stop_server(handle) is None


# --------------------------------------------------------------------------- #
# Story 1b.6 conventions invariants
# --------------------------------------------------------------------------- #


KEYWORD_METHODS = ["start_server", "connect_to_server", "stop_server"]


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


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_is_not_async(method_name: str) -> None:
    """ADR-012 + Story 1b.6: no bare `async def @keyword` — must wrap via `_run_async`."""
    import inspect

    func = getattr(MCPLibrary, method_name)
    assert not inspect.iscoroutinefunction(func)


# --------------------------------------------------------------------------- #
# Library composition (DynamicCore exclusion preserved)
# --------------------------------------------------------------------------- #


def test_agenteval_does_not_expose_mcp_library_post_story_3_1() -> None:
    """`MCPLibrary` REMAINS excluded from `_SUB_LIBRARIES` after Story 3.1.

    Story 2.2 collision-prevention norm: sub-libraries with potential
    keyword-name collisions stay excluded. Story 3.1 adds 3 keywords
    (`Start Server`, `Connect To Server`, `Stop Server`) — none collide
    with HooksLibrary's `Get Config`, but the exclusion-precedent
    stands per Story 2.3+2.4 ratification.
    """
    from AgentEval import AgentEval as AgentEvalLib

    library = AgentEvalLib()
    assert "MCPLibrary" not in library._loaded_components


# --------------------------------------------------------------------------- #
# Version gate integration (AC-MCP-OBSERVE-02 surface)
# --------------------------------------------------------------------------- #


def test_connect_raises_unsupported_mcp_version_on_injected_unsupported_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject `SUPPORTED_PROTOCOL_VERSIONS = ["FAKE-VERSION-FOR-TEST"]`.

    With the SDK's accepted-version list reduced to a string the
    bundled echo server WON'T negotiate (`2025-11-25` etc. all fall
    outside the fake-only set), `Connect To Server` must raise
    `UnsupportedMCPVersionError` per AC-MCP-OBSERVE-02.
    """
    from mcp.shared import version as mcp_version_mod

    import AgentEval.mcp.version_gate as version_gate_mod

    monkeypatch.setattr(mcp_version_mod, "SUPPORTED_PROTOCOL_VERSIONS", ["FAKE-VERSION-FOR-TEST"])

    # Sanity: ensure the patched value is what `check_protocol_version`
    # will see (it imports lazily inside the function).
    _ = version_gate_mod  # keep import for lazy-import path

    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        connect_to_server(handle)
    assert exc_info.value.error_code == "UNSUPPORTED_MCP_VERSION"
    assert exc_info.value.supported_range == "mcp>=1.0,<2.0"
