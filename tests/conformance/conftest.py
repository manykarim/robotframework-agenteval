"""pytest fixture re-exports for the conformance suite (Story 1b.5 ADR-017 L40-43).

Re-exports the `adapter_registry`, `truncation_injection_harness`, and
`mock_provider` fixtures from `harness.py` so per-AC test files can use
them by parameter name without explicit imports. This is the canonical
pytest pattern for shared fixture surfaces.
"""

from __future__ import annotations

from .harness import (  # noqa: F401 — pytest fixture re-exports
    adapter_registry,
    mock_provider,
    truncation_injection_harness,
)
