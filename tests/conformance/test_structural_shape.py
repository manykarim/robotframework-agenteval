"""Adapter signature-shape conformance test (Story 1b.5 per ADR-017 L36 + Story 1b.4 hand-off).

Parametrized over the `adapter_registry` fixture; calls
`assert_adapter_signature(adapter_cls)` on each registered adapter to
verify the FR12 `run(prompt, tools=None, mcp_servers=None, **kwargs) ->
AgentRunResult` signature shape (Python's `@runtime_checkable` Protocol
only checks attribute presence, NOT signature — per Story 1b.4 D4
ratification + types.py L346-356).

Phase-1 status (end-of-Story-1b.5): `adapter_registry` is empty (no
concrete adapter registered); test SKIPs gracefully. Story 4.1 + Story
4.2 land concrete adapters; this test starts exercising them at that
time.
"""

from __future__ import annotations

import pytest

from .harness import assert_adapter_signature

# `adapter_registry` is provided by `conftest.py` re-export from `harness.py`.


def test_structural_shape_empty_registry_skips(
    adapter_registry: list[type],
) -> None:
    """When `adapter_registry` is empty (end-of-Story-1b.5), SKIP gracefully."""
    if not adapter_registry:
        pytest.skip(
            "adapter_registry is empty — no concrete adapter registered yet; "
            "Story 4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI) land "
            "the first adapters. See ADR-017 L36 + ADR-005."
        )
    # When adapters exist, exercise the signature check on each.
    for adapter_cls in adapter_registry:
        assert_adapter_signature(adapter_cls)
