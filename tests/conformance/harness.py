"""Conformance harness fixtures + runners (Story 1b.5 — ADR-017 L40-43).

Provides the four ratified surfaces per ADR-017 L40-43:

1. `adapter_registry` pytest fixture — yields all adapters discovered via
   Story 1b.3's `_kernel.discovery.discover_adapters()` + entry-points
   lookup. Empty at end-of-Story-1b.5 (no concrete adapter registered yet;
   Generic LiteLLM lands Story 4.1, Claude Code CLI lands Story 4.2).

2. `truncation_injection_harness` pytest fixture — exposes a mock-agent
   subprocess controller with `kill_at` parameter (`"mid_stream"` /
   `"early_eof"` / `"after_first_event"`) per ADR-006 + AC-CONFORMANCE-02.
   Used by `test_ac_conformance_02_completeness.py` when Epic 6 lands.
   Phase-1 implementation returns a simple builder that documents the
   contract; concrete subprocess control wires when concrete adapters
   ship.

3. `mock_provider` pytest fixture — known cost/runtime characteristics
   per ADR-015 (for Tier-3 cost-guardrail conformance tests when Epic 6
   Story 6.x lands).

4. `run_fixture(fixture, adapter) -> ConformanceResult` — orchestrates
   `adapter.run()` against the fixture's `scenario_name` + asserts the
   ADR-005 L19-22 allowable-variation contract. Phase-1 stub returns
   `ConformanceResult(passed=False, skip_reason="No concrete adapter
   implementation yet")` for ALL calls until concrete adapters land.

5. `assert_adapter_signature(adapter_cls) -> None` — signature-shape
   verifier per Story 1b.4 hand-off (`src/AgentEval/types.py` L346-356)
   + ADR-017 L36. Inspects `adapter_cls.run`'s signature against PRD
   FR12's `(self, prompt: str, tools=None, mcp_servers=None, **kwargs)
   -> AgentRunResult` contract; raises `AssertionError` with structured
   diff on mismatch.

References:
    - ADR-017 L21-43 (per-AC test files + harness fixtures)
    - ADR-005 L17-22 (fidelity-oracle contract)
    - ADR-006 (truncation injection)
    - ADR-015 (cost-runtime guardrails)
    - Story 1b.3 `_kernel/discovery.py` (`discover_adapters()`)
    - Story 1b.4 `src/AgentEval/types.py` L346-356 (signature-shape hand-off)
    - PRD FR12 L1506 (Protocol `run()` signature contract)
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

import pytest

from AgentEval._kernel import discovery

from .types import ConformanceFixture, ConformanceResult

if TYPE_CHECKING:
    from AgentEval.types import CodingAgentAdapter

__all__ = [
    "adapter_registry",
    "truncation_injection_harness",
    "mock_provider",
    "run_fixture",
    "assert_adapter_signature",
]


@pytest.fixture
def adapter_registry() -> list[type[CodingAgentAdapter]]:
    """Yield all adapters discovered via Story 1b.3 discovery + entry-points.

    Empty list at end-of-Story-1b.5 — Generic LiteLLM lands Story 4.1,
    Claude Code CLI lands Story 4.2. Per-AC test files parametrize over
    this fixture + SKIP when empty (the ratified end-of-Story-1b.5
    state).
    """
    discovered = discovery.discover_adapters()
    return list(discovered.values())


@pytest.fixture
def truncation_injection_harness() -> dict[str, Any]:
    """Mock-agent subprocess controller for AC-CONFORMANCE-02 + ADR-006.

    Phase-1 contract (Story 1b.5): returns a builder dict documenting the
    `kill_at` Literal value space. Concrete subprocess control wires when
    Epic 4 ships concrete adapters + Epic 6 ships Tier-3 keyword
    infrastructure.

    Returns:
        Builder dict with keys:
            - `kill_at`: Literal["mid_stream", "early_eof", "after_first_event"]
            - `build()`: callable producing a configured mock-subprocess controller
              (Phase-1 stub raises NotImplementedError until Epic 4 lands).
    """

    def _build() -> Any:
        raise NotImplementedError(
            "truncation_injection_harness builder is a Phase-1 stub; "
            "Epic 4 Story 4.1/4.2 (concrete adapters) + Epic 6 (Tier-3 "
            "keywords) wire the real subprocess controller."
        )

    return {
        "kill_at_options": ["mid_stream", "early_eof", "after_first_event"],
        "build": _build,
    }


@pytest.fixture
def mock_provider() -> dict[str, Any]:
    """Mock provider with known cost/runtime characteristics per ADR-015.

    Phase-1 stub for Tier-3 cost-guardrail conformance tests. Returns a
    builder dict; concrete provider implementation lands when Epic 6
    cost-guardrail keywords ship.
    """

    def _build() -> Any:
        raise NotImplementedError(
            "mock_provider builder is a Phase-1 stub; Epic 6 cost-guardrail "
            "keywords wire the real provider with known cost/runtime values."
        )

    return {
        "default_cost_per_call_usd": 0.0,
        "default_latency_ms": 0.0,
        "build": _build,
    }


def run_fixture(fixture: ConformanceFixture, adapter: CodingAgentAdapter | None) -> ConformanceResult:
    """Orchestrate `adapter.run()` against the fixture; return structured pass/fail.

    Phase-1 contract (Story 1b.5): returns
    `ConformanceResult(passed=False, skip_reason="No concrete adapter
    implementation yet")` for ALL calls until concrete adapters ship.
    Story 4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI) wire the
    real assertion logic against ADR-005 L19-22 allowable-variations.

    Args:
        fixture: Loaded `ConformanceFixture` from `load_fixture(path)`.
        adapter: Concrete `CodingAgentAdapter` instance to exercise, or
            `None` to short-circuit with `skip_reason`.

    Returns:
        `ConformanceResult` with `passed` + `evidence` + optional
        `skip_reason`.
    """
    if adapter is None:
        return ConformanceResult(
            passed=False,
            fixture=fixture,
            skip_reason=(
                f"No concrete adapter instance provided for "
                f"{fixture.adapter_name!r}/{fixture.scenario_name!r}; "
                "Story 4.1/4.2 wire concrete adapters."
            ),
        )
    # Phase-1 stub: even with an adapter, full evidence-gathering against
    # ADR-005 allowable-variations is Story 4.1/4.2 + per-AC test file
    # scope. Story 1b.5 ships only the contract publication.
    return ConformanceResult(
        passed=False,
        fixture=fixture,
        skip_reason=(
            f"run_fixture is a Phase-1 stub; full ADR-005 allowable-variation "
            f"assertion wires in Story 4.1 (Generic LiteLLM) + Story 4.2 "
            f"(Claude Code CLI). Adapter {type(adapter).__name__!r} not yet "
            "exercised against fixture."
        ),
    )


def assert_adapter_signature(adapter_cls: type) -> None:
    """Verify adapter class's `run()` signature matches PRD FR12 contract.

    Story 1b.4 hand-off (`src/AgentEval/types.py` L346-356): Python's
    `@runtime_checkable` Protocol only verifies attribute presence at
    `isinstance` time, NOT signature shape. This helper inspects
    `adapter_cls.run`'s signature against FR12's
    `(self, prompt: str, tools=None, mcp_servers=None, **kwargs) ->
    AgentRunResult` contract and raises `AssertionError` with a
    structured diff on mismatch.

    Used by `test_structural_shape.py` (per ADR-017 L36) against every
    registered adapter from the `adapter_registry` fixture.

    Args:
        adapter_cls: A class purporting to implement the
            `CodingAgentAdapter` Protocol.

    Raises:
        AssertionError: signature shape doesn't match FR12. The message
            includes which parameter is missing/renamed/has-wrong-default.
    """
    run = getattr(adapter_cls, "run", None)
    if run is None:
        raise AssertionError(f"{adapter_cls.__name__!r} has no `run` method (PRD FR12 violation)")
    sig = inspect.signature(run)
    params = list(sig.parameters.values())

    # First param is `self`; skip.
    if not params or params[0].name != "self":
        raise AssertionError(
            f"{adapter_cls.__name__}.run must have `self` as first parameter; got {[p.name for p in params]!r}"
        )

    expected_params = ["self", "prompt", "tools", "mcp_servers"]
    actual_param_names = [p.name for p in params]
    for expected_name in expected_params:
        if expected_name not in actual_param_names:
            raise AssertionError(
                f"{adapter_cls.__name__}.run is missing required parameter "
                f"{expected_name!r} per PRD FR12 `run(prompt, tools=None, "
                f"mcp_servers=None, **kwargs) -> AgentRunResult`; got "
                f"{actual_param_names!r}"
            )

    # `tools` and `mcp_servers` MUST have None defaults per FR12.
    for kw_name in ("tools", "mcp_servers"):
        param = sig.parameters[kw_name]
        if param.default is inspect.Parameter.empty:
            raise AssertionError(
                f"{adapter_cls.__name__}.run parameter {kw_name!r} must have "
                f"default value None per PRD FR12; got no default"
            )

    # `**kwargs` MUST be present.
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    if not has_var_keyword:
        raise AssertionError(
            f"{adapter_cls.__name__}.run must accept `**kwargs` per PRD FR12; got {actual_param_names!r}"
        )
