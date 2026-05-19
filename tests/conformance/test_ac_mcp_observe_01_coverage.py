"""AC-MCP-OBSERVE-01 conformance tests (Story 1b.5 skeleton per ADR-017 L21-33).

Owning epic: Epic 3 Story 3.1 (MCP server lifecycle) / Epic 5 (observer).
"""

from __future__ import annotations

import pytest


def test_ac_mcp_observe_01_coverage_skeleton() -> None:
    pytest.skip(
        "Owning epic Epic 3 Story 3.1 / Epic 5 not yet shipped — "
        "echo_simple + echo_external_mcp fixtures publish the contract; "
        "mcp_coverage 3-state value space asserted when MCP keywords land. "
        "See ADR-016 + ADR-017 + PRD AC-MCP-OBSERVE-01 + FR36b."
    )
