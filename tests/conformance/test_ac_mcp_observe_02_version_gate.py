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

"""AC-MCP-OBSERVE-02 conformance test (Story 3.1 un-skip; was Story 1b.5 skeleton).

Per PRD AC-MCP-OBSERVE-02 L566 + FR46 L1571: "MCP observer validates
negotiated MCP spec version at session start. Raises
`UnsupportedMCPVersionError` if outside tested range (`mcp>=1.0,<2.0`).
Conformance suite injects a future-spec mock server to verify the gate
fires."

Story 3.1 ratification: the conformance test uses the SDK's
`SUPPORTED_PROTOCOL_VERSIONS` monkeypatch pattern (vs. spawning a real
out-of-range MCP server — the latter would require a mock-server
fixture that's deferred to Phase-1.5). The monkeypatch approach
exercises the SAME `check_protocol_version` raise site that a real
out-of-range server would trigger.

Owning epic: Epic 3 Story 3.1.
"""

from __future__ import annotations

import pytest

from AgentEval.errors import (
    AgentEvalCompatError,
    AgentEvalError,
    UnsupportedMCPVersionError,
)
from AgentEval.mcp.bundled.echo import build_server
from AgentEval.mcp.lifecycle import connect_to_server, start_server
from AgentEval.mcp.version_gate import SUPPORTED_RANGE, check_protocol_version


def test_unsupported_mcp_version_error_class_shipped() -> None:
    """The catalog L80 leaf is implemented as a class + inherits AgentEvalCompatError."""
    assert issubclass(UnsupportedMCPVersionError, AgentEvalCompatError)
    assert issubclass(UnsupportedMCPVersionError, AgentEvalError)
    assert UnsupportedMCPVersionError.error_code == "UNSUPPORTED_MCP_VERSION"


def test_version_gate_check_raises_on_unsupported() -> None:
    """The check_protocol_version raise site fires per FR46."""
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        check_protocol_version("2099-12-31")
    assert exc_info.value.server_version == "2099-12-31"
    assert exc_info.value.supported_range == SUPPORTED_RANGE


def test_version_gate_str_matches_fr8_verbatim() -> None:
    """PRD FR8: `MCP server version <X> outside library tested range <range>`."""
    exc = UnsupportedMCPVersionError(
        "MCP server version 2099-12-31 outside library tested range mcp>=1.0,<2.0",
        server_version="2099-12-31",
        supported_range="mcp>=1.0,<2.0",
    )
    assert "outside library tested range" in str(exc)


def test_full_lifecycle_raises_on_injected_unsupported_protocol_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end conformance per AC-MCP-OBSERVE-02 — in_memory transport.

    Story 3.1 code-review HIGH fix 2026-05-19 (Edge-cases + Codex 2-way):
    monkeypatch BOTH `mcp.shared.version.SUPPORTED_PROTOCOL_VERSIONS`
    AND `mcp.client.session.SUPPORTED_PROTOCOL_VERSIONS`. The pre-edit
    patched only `mcp.shared.version` — fake-green because the SDK
    snapshots the symbol at module-load time.
    """
    import mcp.client.session as mcp_client_session_mod
    from mcp.shared import version as mcp_version_mod

    monkeypatch.setattr(mcp_version_mod, "SUPPORTED_PROTOCOL_VERSIONS", ["FAKE-VERSION-FOR-TEST"])
    monkeypatch.setattr(mcp_client_session_mod, "SUPPORTED_PROTOCOL_VERSIONS", ["FAKE-VERSION-FOR-TEST"])

    handle = start_server(name="echo", transport="in_memory", server_factory=build_server)
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        connect_to_server(handle)
    assert exc_info.value.error_code == "UNSUPPORTED_MCP_VERSION"
    assert exc_info.value.supported_range == SUPPORTED_RANGE


def test_full_lifecycle_raises_on_injected_unsupported_protocol_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end conformance per AC-MCP-OBSERVE-02 — STDIO transport.

    Story 3.1 code-review HIGH fix 2026-05-19 (Edge-cases + Codex 2-way):
    the SDK-first reject path was previously untested on stdio
    (AC-MCP-OBSERVE-02 was fake-green on the PRIMARY production transport).
    This case exercises the typed-error mapping in
    `lifecycle.connect_to_server`'s try/except for the SDK's bare
    `RuntimeError("Unsupported protocol version from the server: ...")`.
    """
    import sys

    import mcp.client.session as mcp_client_session_mod
    from mcp.shared import version as mcp_version_mod

    monkeypatch.setattr(mcp_version_mod, "SUPPORTED_PROTOCOL_VERSIONS", ["FAKE-VERSION-FOR-TEST"])
    monkeypatch.setattr(mcp_client_session_mod, "SUPPORTED_PROTOCOL_VERSIONS", ["FAKE-VERSION-FOR-TEST"])

    handle = start_server(
        name="echo",
        transport="stdio",
        command=sys.executable,
        args=["-m", "AgentEval.mcp.bundled.echo"],
    )
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        connect_to_server(handle)
    assert exc_info.value.error_code == "UNSUPPORTED_MCP_VERSION"
    assert exc_info.value.supported_range == SUPPORTED_RANGE
