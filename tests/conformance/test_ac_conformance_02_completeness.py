"""AC-CONFORMANCE-02 conformance tests (Story 1b.5 skeleton per ADR-017 L21-33).

Owning epic: Epic 4 Story 4.2 (CLI adapter for truncation) + Epic 6 (Tier-3 metric keywords).
"""

from __future__ import annotations

import pytest


def test_ac_conformance_02_completeness_skeleton() -> None:
    pytest.skip(
        "Owning epic Epic 4 Story 4.2 + Epic 6 not yet shipped — "
        "echo_truncated fixtures published by Story 1b.5; truncation-"
        "injection harness exposed but concrete subprocess control wires "
        "in Story 4.2. See ADR-006 + ADR-017 + PRD AC-CONFORMANCE-02 + FR36a."
    )
