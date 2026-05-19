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
    "DeterministicMockAgent",
    "deterministic_mock_agent",
]


@pytest.fixture
def adapter_registry() -> list[type[CodingAgentAdapter]]:
    """Yield all adapters discovered via Story 1b.3 discovery + entry-points.

    Empty list at end-of-Story-1b.5 — Generic LiteLLM lands Story 4.1,
    Claude Code CLI lands Story 4.2. Per-AC test files parametrize over
    this fixture + SKIP when empty (the ratified end-of-Story-1b.5
    state).

    Story 1b.5 code-review Codex STAR catch M4: catches
    `AdapterDiscoveryError` per Story 1b.3 `loaded_so_far` contract.
    A single broken third-party adapter entry-point should NOT abort the
    whole conformance suite — instead, surface the successfully-loaded
    adapters via `loaded_so_far` so resilient discovery flows through.
    """
    from AgentEval.errors import AdapterDiscoveryError

    try:
        discovered = discovery.discover_adapters()
    except AdapterDiscoveryError as exc:
        # Per ADR-013 L42 + Story 1b.3 partial-install contract: recover
        # successfully-loaded adapters via `loaded_so_far`. Log the broken
        # registration via stderr (pytest captures by default).
        loaded_so_far: dict[str, type] = getattr(exc, "loaded_so_far", {}) or {}
        return list(loaded_so_far.values())
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

    Story 1b.5 code-review H2 fix (4-way: Blind+Auditor+Codex+spec AC-1b.5.4):
    pre-edit checked only name presence + "has-some-default" + `**kwargs`
    presence. Strengthened to also assert:
    - `adapter_cls` is a class (NOT an instance).
    - `prompt` is `POSITIONAL_OR_KEYWORD` (NOT positional-only NOR keyword-only).
    - `tools` + `mcp_servers` defaults are EXACTLY `None` (NOT `[]` / `()` / `...`).
    - Return annotation is `AgentRunResult` or its forward-ref string.

    Args:
        adapter_cls: A class purporting to implement the
            `CodingAgentAdapter` Protocol.

    Raises:
        AssertionError: signature shape doesn't match FR12. The message
            includes which parameter is missing/renamed/has-wrong-kind/
            has-wrong-default/has-wrong-return-annotation.
    """
    if adapter_cls is None:
        raise AssertionError("adapter_cls is None (PRD FR12 violation)")
    if not isinstance(adapter_cls, type):
        raise AssertionError(
            f"assert_adapter_signature expected a class; got instance of {type(adapter_cls).__name__!r}"
        )
    cls_name = adapter_cls.__name__
    run = getattr(adapter_cls, "run", None)
    if run is None:
        raise AssertionError(f"{cls_name!r} has no `run` method (PRD FR12 violation)")
    sig = inspect.signature(run)
    params = list(sig.parameters.values())

    # First param is `self`; skip.
    if not params or params[0].name != "self":
        raise AssertionError(f"{cls_name}.run must have `self` as first parameter; got {[p.name for p in params]!r}")

    expected_params = ["self", "prompt", "tools", "mcp_servers"]
    actual_param_names = [p.name for p in params]
    for expected_name in expected_params:
        if expected_name not in actual_param_names:
            raise AssertionError(
                f"{cls_name}.run is missing required parameter "
                f"{expected_name!r} per PRD FR12 `run(prompt, tools=None, "
                f"mcp_servers=None, **kwargs) -> AgentRunResult`; got "
                f"{actual_param_names!r}"
            )

    # H2 fix: `prompt` MUST be POSITIONAL_OR_KEYWORD (NOT keyword-only,
    # NOT positional-only) per FR12 `(self, prompt: str, ...)` shape.
    prompt_param = sig.parameters["prompt"]
    if prompt_param.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD,):
        raise AssertionError(
            f"{cls_name}.run parameter `prompt` must be POSITIONAL_OR_KEYWORD "
            f"per PRD FR12; got {prompt_param.kind.name}"
        )

    # H2 fix: `tools` and `mcp_servers` defaults MUST be exactly None.
    for kw_name in ("tools", "mcp_servers"):
        param = sig.parameters[kw_name]
        if param.default is inspect.Parameter.empty:
            raise AssertionError(
                f"{cls_name}.run parameter {kw_name!r} must have default value None per PRD FR12; got no default"
            )
        if param.default is not None:
            raise AssertionError(
                f"{cls_name}.run parameter {kw_name!r} default must be exactly None per PRD FR12; got {param.default!r}"
            )

    # `**kwargs` MUST be present.
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    if not has_var_keyword:
        raise AssertionError(f"{cls_name}.run must accept `**kwargs` per PRD FR12; got {actual_param_names!r}")

    # H2 fix: return annotation MUST be `AgentRunResult` or its forward-ref
    # string `"AgentRunResult"` (when adapter uses `from __future__ import
    # annotations`). Pre-edit code didn't check this despite the docstring
    # claiming to + AC-1b.5.4 explicitly enumerating "wrong return
    # annotation" as a catch surface.
    ret = sig.return_annotation
    if ret is inspect.Signature.empty:
        raise AssertionError(
            f"{cls_name}.run must declare a return annotation per PRD FR12 (`-> AgentRunResult`); got no annotation"
        )
    # Accept either the live class object OR the forward-ref string
    # (because adapters typically use `from __future__ import annotations`
    # which stringifies all annotations).
    ret_name = ret.__name__ if isinstance(ret, type) else str(ret)
    if ret_name != "AgentRunResult":
        raise AssertionError(
            f"{cls_name}.run return annotation must be `AgentRunResult` per PRD FR12; got {ret_name!r}"
        )


# ===== Phase-1 deterministic mock agent (ADR-005 L17/L28 + Story 1b.5 code-review H3) ============ #


class DeterministicMockAgent:
    """Deterministic mock agent per ADR-005 L17/L28 + Story 1b.5 code-review H3.

    The Codex + Auditor STAR catch in Story 1b.5 code review surfaced that
    ADR-005 L17 mandates a deterministic mock agent shipping in Phase 1
    ("It implements `CodingAgentAdapter` with hardcoded responses for a
    fixed scenario set") + L28 ratifies "Mock agent + fixed-scenario
    fixtures must ship in Phase 1". The pre-Story-1b.5-code-review impl
    omitted the mock-agent class entirely, leaving `run_fixture` unable
    to exercise the contract end-to-end.

    This class implements `CodingAgentAdapter` (via Story 1b.4 Protocol
    duck-typing) with hardcoded responses keyed by `scenario_name`
    matching the 6 reference fixtures. Concrete adapters in Epic 4 Story
    4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI) replace this
    mock for production-quality runs; the mock stays in the test infra
    for harness self-validation + community adapter authors who want a
    reference impl.

    Phase-1 scope: covers `echo_simple` / `echo_truncated` /
    `echo_external_mcp` per the 6-fixture set. New scenarios in future
    stories add cases here.
    """

    name: str = "deterministic_mock"
    version: str = "1.0.0"

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,  # noqa: ARG002
        mcp_servers: dict[str, Any] | None = None,  # noqa: ARG002
        scenario_name: str = "echo_simple",
        **kwargs: Any,  # noqa: ARG002
    ) -> Any:
        """Return a hardcoded `AgentRunResult` matching the named scenario.

        Note: return type is `Any` (not `AgentRunResult`) to defer the
        import until call time + avoid the test-infra-vs-src-package
        import discipline question. Concrete adapters in Epic 4 use the
        proper `-> AgentRunResult` annotation per FR12.
        """
        from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

        if scenario_name == "echo_simple":
            return AgentRunResult(
                response_text=prompt,
                tool_calls=[],
                usage=Usage(input_tokens=5, output_tokens=5),
                metadata=AgentRunMetadata(
                    completeness="complete",
                    mcp_coverage="hosted_in_process",
                ),
                cost_usd=0.0001,
                latency_seconds=0.05,
                trace_id="mock-trace-echo-simple",
            )
        if scenario_name == "echo_truncated":
            return AgentRunResult(
                response_text=prompt[: len(prompt) // 2],
                tool_calls=[],
                usage=Usage(input_tokens=5, output_tokens=2),
                metadata=AgentRunMetadata(
                    completeness="truncated",
                    mcp_coverage="hosted_in_process",
                ),
                cost_usd=0.00005,
                latency_seconds=0.02,
                trace_id="mock-trace-echo-truncated",
            )
        if scenario_name == "echo_external_mcp":
            return AgentRunResult(
                response_text=f"{prompt} from external MCP",
                tool_calls=[],
                usage=Usage(input_tokens=5, output_tokens=8),
                metadata=AgentRunMetadata(
                    completeness="complete",
                    mcp_coverage="external_mixed",
                ),
                cost_usd=0.0001,
                latency_seconds=0.08,
                trace_id="mock-trace-echo-external-mcp",
            )
        raise ValueError(
            f"DeterministicMockAgent: unknown scenario_name {scenario_name!r}; "
            f"supported: echo_simple, echo_truncated, echo_external_mcp"
        )


@pytest.fixture
def deterministic_mock_agent() -> DeterministicMockAgent:
    """pytest fixture exposing a `DeterministicMockAgent` instance.

    Used by Story 1b.5 conformance harness self-tests + future Epic 4
    smoke tests that need a Phase-1 adapter without depending on Story
    4.1/4.2's concrete adapters.
    """
    return DeterministicMockAgent()
