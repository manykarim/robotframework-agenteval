"""AC-MCP-OBSERVE-02 conformance tests (Story 1b.5 skeleton per ADR-017 L21-33).

Owning epic: Epic 3 Story 3.1 (MCP spec-version gate per ADR-008).
"""

from __future__ import annotations

import pytest


def test_ac_mcp_observe_02_version_gate_skeleton() -> None:
    pytest.skip(
        "Owning epic Epic 3 Story 3.1 not yet shipped — "
        "UnsupportedMCPVersionError raise site lands with MCP transport. "
        "See ADR-008 + ADR-017 + PRD AC-MCP-OBSERVE-02 + FR46."
    )
