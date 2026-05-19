"""AC-CONFORMANCE-01 conformance tests (Story 1b.5 skeleton per ADR-017 L21-33).

Owning epic: Epic 4 Story 4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI).

Phase-1 contract publication (Story 1b.5): 6 reference fixtures at
`fixtures/<adapter>/<scenario>.json` publish the contract; this test
file SKIPs until concrete adapters land + start exercising the fixtures
through `run_fixture`.
"""

from __future__ import annotations

import pytest


def test_ac_conformance_01_fidelity_oracles_skeleton() -> None:
    pytest.skip(
        "Owning epic Epic 4 Story 4.1 + Story 4.2 not yet shipped — "
        "Story 1b.5 publishes the 6-fixture contract (generic + "
        "claude_code_cli × echo_simple/echo_truncated/echo_external_mcp); "
        "concrete adapters wire the assertions. See ADR-005 + ADR-017 + "
        "PRD AC-CONFORMANCE-01."
    )
