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

"""MCP spec version gate (Story 3.1).

Validates the negotiated MCP protocol version against the agenteval-
supported range. Raises `UnsupportedMCPVersionError` per PRD FR8 + FR46
+ AC-MCP-OBSERVE-02 when the server's `InitializeResult.protocolVersion`
falls outside `mcp>=1.0,<2.0` (NFR-COMPAT-04 + ADR-008).

The MCP protocol version is a date-stamped string per the spec (e.g.,
`"2024-11-05"`, `"2025-03-26"`). The agenteval-supported range is
expressed as the `mcp` PyPI package version constraint (`>=1.0,<2.0`),
which the MCP Python SDK maps internally to a set of acceptable
protocol-version strings. The gate accepts ANY protocol-version string
the SDK's `mcp.types.LATEST_PROTOCOL_VERSION` chain successfully
negotiates AND rejects any string the SDK couldn't negotiate against
the pinned `mcp==1.27.1` dep.

Phase-1 implementation: the gate's range check is delegated to the MCP
SDK's own protocol negotiation. If `session.initialize()` succeeds at
all, the version IS in range; if it raises OR returns a version we
don't recognize via the SDK's `SUPPORTED_PROTOCOL_VERSIONS` constant,
we surface that as `UnsupportedMCPVersionError`. Phase-2 may add an
explicit per-version allowlist if MCP spec drift accelerates.
"""

from __future__ import annotations

from AgentEval.errors import UnsupportedMCPVersionError

__all__ = [
    "SUPPORTED_RANGE",
    "check_protocol_version",
]


# Per pyproject.toml `mcp==1.27.1` pin + NFR-COMPAT-04. The string form
# is what surfaces in `UnsupportedMCPVersionError.__str__` per PRD FR8.
SUPPORTED_RANGE: str = "mcp>=1.0,<2.0"


def check_protocol_version(server_version: str | None) -> None:
    """Validate a negotiated MCP protocol version string against the agenteval-supported range.

    Args:
        server_version: The `InitializeResult.protocolVersion` returned
            by the MCP server during the `ClientSession.initialize()`
            handshake. `None` means the SDK didn't surface a version
            (treated as out-of-range — fail loudly per ADR-011's
            loud-refusal posture).

    Raises:
        UnsupportedMCPVersionError: If the version is `None`, empty,
            or NOT in the MCP SDK's `SUPPORTED_PROTOCOL_VERSIONS` set.
            `server_version` + `supported_range` attrs populated per
            Story 1b.4 D7 structured-attrs precedent.
    """
    if not server_version:
        raise UnsupportedMCPVersionError(
            f"MCP server version <None> outside library tested range {SUPPORTED_RANGE}",
            server_version=server_version,
            supported_range=SUPPORTED_RANGE,
        )

    # Defer to the MCP SDK's own version-acceptance set. Per the pinned
    # `mcp==1.27.1` build, `mcp.shared.version.SUPPORTED_PROTOCOL_VERSIONS`
    # is a list of accepted protocol-version strings. The SDK's own
    # `ClientSession.initialize()` raises a bare `RuntimeError` on
    # unsupported versions; this gate catches the bare error path AND
    # ALSO validates pre-handshake so callers can probe a candidate
    # version string without round-tripping to a server.
    try:
        from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
    except ImportError as exc:
        # Defensive: the mcp dep is a hard requirement (pyproject.toml
        # `mcp==1.27.1`). If the import fails, surface the version
        # error rather than crash the gate.
        raise UnsupportedMCPVersionError(
            f"MCP SDK does not expose SUPPORTED_PROTOCOL_VERSIONS: {exc}",
            server_version=server_version,
            supported_range=SUPPORTED_RANGE,
        ) from exc

    if server_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise UnsupportedMCPVersionError(
            f"MCP server version {server_version} outside library tested range {SUPPORTED_RANGE}",
            server_version=server_version,
            supported_range=SUPPORTED_RANGE,
        )
