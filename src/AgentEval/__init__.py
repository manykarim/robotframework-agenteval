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

"""robotframework-agenteval — Robot Framework library for evaluating AI coding agents.

Phase 1 surface (Story 1a.6): the AgentEval RF Library class with FR42 + FR11b
defaults wired into __init__, plus the `Get Effective Config` keyword.
Sub-libraries (coding_agent, mcp, telemetry, metrics, stats, judge, ...) land in
Epic 1b onward.

Usage from a .robot file:

    *** Settings ***
    Library    AgentEval    allow_validate_operator=False    telemetry=True

    *** Test Cases ***
    Example
        ${config}=    Get Effective Config
        Should Be Equal    ${config["provider"]}    litellm

Usage from a Python script:

    from AgentEval import AgentEval

    agent = AgentEval(allow_validate_operator=True, telemetry=False)
    config = agent.get_effective_config()
    assert config["allow_validate_operator"] is True
"""

from __future__ import annotations

from typing import Any, Literal

from robot.api.deco import keyword

__version__ = "0.0.1"
__all__: list[str] = ["AgentEval"]


class AgentEval:
    """Robot Framework library for evaluating AI coding agents.

    Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point.
    Phase-1 scope: kwarg-only config resolution + `Get Effective Config` accessor.
    Env-var precedence (FR41 — kwarg > env var > .env > defaults) lands in Epic
    1b `_kernel/context.py`.

    Args:
        provider: Provider plugin name resolved via `agenteval.providers`
            entry-points (FR42; ADR-013). Phase 1 ships only the `litellm`
            provider; future providers register via
            `[project.entry-points."agenteval.providers"]`.
        telemetry: Enable the OTel listener for trace recording (FR42 + FR44).
            When False, `Get Trace Backend Names` returns `[]` and no OTLP
            egress occurs (Phase 2). Phase 1 wires the parameter; full
            listener-disable enforcement lands in Epic 5 Story 5.1.
        trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports
            `"memory"` and `"jsonl"`; `"otlp"` is Phase 2.
        allow_validate_operator: Enable the AssertionEngine `validate` operator
            which uses `eval()` (FR42 + FR43; NFR-SEC-02). Default False — the
            safer posture per NFR-SEC-02. Gate enforcement (raising
            `ValidateOperatorDisallowed`) lands in Epic 6.
        default_temperature: Default provider temperature for non-stochastic
            keywords (FR42). 0.0 enforces deterministic provider calls where
            the underlying model supports it.
        mcp_per_test: MCP server scope per ADR-009 + architecture L314's 3-mode
            design:

            - True (default): per-test isolation; correct under
              `pabot --processes N`.
            - "suite": per-suite scope; recipe-5 dogfood-CI ergonomics override.
            - False: single shared instance across all tests; only correct
              serial.
        allow_external_mcp_blind: Opt-in to running with
            `mcp_coverage="external_mixed"` without `IncompleteTraceError`
            (FR42 + ADR-016 D4 adapter contract). Default False enforces
            loud-refusal posture from ADR-016.
        max_cost_usd: Cost budget for `@guarded_fanout`-decorated Tier-3
            keywords (FR42 + ADR-015). USD per fan-out invocation. Default
            5.00.
        max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords
            (FR11b + ADR-015). Default None = no cap (opt-in via explicit
            value). Sibling to `max_cost_usd`; catches slow MCP-server startup
            compounded across trials.

    Phase-1 limitation: env-var precedence (FR41) is wired by Epic 1b
    `_kernel/context.py`. This class accepts kwarg-only config; defaults come
    from the parameter defaults below. `.env.example` documents the
    Phase-1.5+ `AGENTEVAL_*` env-var names per architecture §Configuration
    Parameter Naming.

    References:
        - PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)
        - PRD FR11b (max_runtime_seconds keyword arg sibling)
        - PRD FR41 (config precedence)
        - ADR-009 (mcp_per_test 3-mode)
        - ADR-013 (entry-points discovery for `provider`)
        - ADR-015 (@guarded_fanout for cost + runtime guardrails)
        - ADR-016 (mcp_coverage detection + allow_external_mcp_blind)
        - docs/contracts/stability-surface.md (Phase-1 stability labels for this
          class)
    """

    def __init__(
        self,
        *,
        provider: str = "litellm",
        telemetry: bool = True,
        trace_backend: str = "memory",
        allow_validate_operator: bool = False,
        default_temperature: float = 0.0,
        mcp_per_test: bool | Literal["suite"] = True,
        allow_external_mcp_blind: bool = False,
        max_cost_usd: float = 5.00,
        max_runtime_seconds: float | None = None,
    ) -> None:
        self._provider = provider
        self._telemetry = telemetry
        self._trace_backend = trace_backend
        self._allow_validate_operator = allow_validate_operator
        self._default_temperature = default_temperature
        self._mcp_per_test = mcp_per_test
        self._allow_external_mcp_blind = allow_external_mcp_blind
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds

    @keyword(name="Get Effective Config")
    def get_effective_config(self) -> dict[str, Any]:
        """Return the resolved config as a dict.

        Phase 1: returns the kwarg-resolved values. Env-var precedence (FR41)
        lands in Epic 1b `_kernel/context.py`; this keyword will then return
        the precedence-resolved values.

        Returns:
            dict[str, Any]: One entry per `__init__` parameter, in declared
                order: `provider`, `telemetry`, `trace_backend`,
                `allow_validate_operator`, `default_temperature`,
                `mcp_per_test`, `allow_external_mcp_blind`, `max_cost_usd`,
                `max_runtime_seconds`.
        """
        return {
            "provider": self._provider,
            "telemetry": self._telemetry,
            "trace_backend": self._trace_backend,
            "allow_validate_operator": self._allow_validate_operator,
            "default_temperature": self._default_temperature,
            "mcp_per_test": self._mcp_per_test,
            "allow_external_mcp_blind": self._allow_external_mcp_blind,
            "max_cost_usd": self._max_cost_usd,
            "max_runtime_seconds": self._max_runtime_seconds,
        }

    def _get_rf_test_id(self) -> str | None:
        """Read the current RF Listener v3 `test_id` from RF context.

        Phase-1 stub: always returns None. Epic 5 Story 5.1 wires the Listener
        v3 context read for per-test MCP scoping per ADR-009.

        Returns:
            str | None: The current RF test_id when running under Listener v3;
                None when called outside RF context (e.g., direct Python
                instantiation).
        """
        return None
