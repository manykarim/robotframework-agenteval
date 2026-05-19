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

Phase 1 surface:
- Story 1a.6 wired the AgentEval RF Library class with FR42 + FR11b defaults
  + the `Get Effective Config` keyword.
- Story 1b.1 integrated FR41 config precedence (kwarg → env-var → `.env` →
  defaults) via `_kernel.context.resolve_config`. `Get Effective Config` now
  returns precedence-resolved values, not just kwarg-resolved values.

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

import importlib
import logging
from typing import Any, Literal

from robot.api.deco import keyword
from robotlibcore import DynamicCore

from AgentEval._kernel.context import _resolve_scope, resolve_config

__version__ = "0.0.1"
__all__: list[str] = ["AgentEval"]

_logger = logging.getLogger("AgentEval.library")

# Sub-library registry per architecture L299/L354/L573 + agentguard ADR-003
# inheritance catalog row (`docs/adr/ADR-001-architectural-influences-catalog.md`
# row "agenteval_concept: DynamicCore composition"). Each entry is
# `(module_path, class_name)`; the lazy-import loop in
# `AgentEval._build_components` instantiates the class + appends to the
# DynamicCore components list. Missing modules / classes are swallowed
# silently (matches agentguard `library.py:82-93` pattern) so the
# top-level `AgentEval` import remains green even while later Epic
# sub-libraries are not yet shipped. Story 2.1 ships entry 1 (skills);
# future Epics extend this tuple.
_SUB_LIBRARIES: tuple[tuple[str, str], ...] = (("AgentEval.skills.library", "SkillsLibrary"),)


# Sentinel: distinguishes "user passed this kwarg" from "kwarg defaulted to
# the FR42 value". Needed so FR41's env-var/.env layers can fire when the
# user did NOT pass the kwarg. Story 1b.1 introduced this for FR41 wiring;
# Story 1b.1 code review H5 added the `__repr__` so libdoc rendering is
# deterministic (a bare `object()` renders as `<object object at 0x...>`
# with a memory address, breaking reproducible doc builds).
class _UnsetType:
    """Singleton sentinel type with a stable `__repr__` for libdoc determinism."""

    _instance: _UnsetType | None = None

    def __new__(cls) -> _UnsetType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "_UNSET"

    def __bool__(self) -> bool:
        return False


_UNSET: Any = _UnsetType()


class AgentEval(DynamicCore):  # type: ignore[misc]
    """Robot Framework library for evaluating AI coding agents.

    Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point
    + the FR41 precedence chain (kwarg → env-var → `.env` → defaults) via
    `_kernel.context.resolve_config` (Story 1b.1). `Get Effective Config`
    returns the precedence-resolved values.

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
        mcp_per_test: MCP server scope.

            - True (default): per-test isolation; correct under
              `pabot --processes N`. (ADR-009 §Decision — ratified True/False.)
            - False: single shared instance across all tests; only correct
              serial. (ADR-009 §Decision — ratified True/False.)
            - "suite": per-suite scope; recipe-5 dogfood-CI ergonomics override.
              (Architecture L314 + NFR-PERF-03d — not in ADR-009 proper.)
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

    FR41 precedence behavior (Story 1b.1):
        Each `__init__` parameter defaults to a private sentinel; if the caller
        does NOT pass it, the value falls through to `AGENTEVAL_*` env-vars,
        then to a `.env` file in cwd, then to the FR42 + FR11b defaults
        documented in this docstring. Callers who want to force a value
        explicitly (even when an env-var is set) pass that value as a kwarg.
        `.env.example` documents the canonical `AGENTEVAL_*` env-var names.

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
        provider: str = _UNSET,
        telemetry: bool = _UNSET,
        trace_backend: str = _UNSET,
        allow_validate_operator: bool = _UNSET,
        default_temperature: float = _UNSET,
        mcp_per_test: bool | Literal["suite"] = _UNSET,
        allow_external_mcp_blind: bool = _UNSET,
        max_cost_usd: float = _UNSET,
        max_runtime_seconds: float | None = _UNSET,
    ) -> None:
        # Story 1b.1 FR41 wiring: strip _UNSET sentinels, pass the remainder
        # to resolve_config() so the env-var / .env / defaults layers can fire
        # for kwargs the caller did NOT pass. Explicit None IS a user-passed
        # value (e.g., max_runtime_seconds=None) and takes precedence over
        # env-vars.
        kwarg_overrides: dict[str, Any] = {
            "provider": provider,
            "telemetry": telemetry,
            "trace_backend": trace_backend,
            "allow_validate_operator": allow_validate_operator,
            "default_temperature": default_temperature,
            "mcp_per_test": mcp_per_test,
            "allow_external_mcp_blind": allow_external_mcp_blind,
            "max_cost_usd": max_cost_usd,
            "max_runtime_seconds": max_runtime_seconds,
        }
        kwarg_overrides = {k: v for k, v in kwarg_overrides.items() if v is not _UNSET}
        resolved = resolve_config(kwarg_overrides)

        self._provider = resolved["provider"]
        self._telemetry = resolved["telemetry"]
        self._trace_backend = resolved["trace_backend"]
        self._allow_validate_operator = resolved["allow_validate_operator"]
        self._default_temperature = resolved["default_temperature"]
        self._mcp_per_test = resolved["mcp_per_test"]
        self._allow_external_mcp_blind = resolved["allow_external_mcp_blind"]
        self._max_cost_usd = resolved["max_cost_usd"]
        self._max_runtime_seconds = resolved["max_runtime_seconds"]

        # Internal scope for MCP server lifecycle (Story 1b.1 _resolve_scope
        # translates the user-vocab `mcp_per_test` into the internal Scope enum).
        self._scope = _resolve_scope(self._mcp_per_test)

        # AC-1a.6.8: lazy RF Listener v3 context hook. Phase-1 stub returns None;
        # Epic 5 Story 5.1 wires the real `test_id` read for per-test MCP scoping.
        self._rf_test_id = self._get_rf_test_id()

        # Story 2.1: DynamicCore composition per architecture L299/L354/L573 +
        # agentguard ADR-003 inheritance catalog row. Sub-libraries are
        # lazy-imported; missing modules are swallowed so future Epic
        # sub-libraries don't break the top-level `Library AgentEval` import.
        components = self._build_components()
        self._loaded_components: list[str] = [c.__class__.__name__ for c in components]
        DynamicCore.__init__(self, components)

    def _build_components(self) -> list[Any]:
        """Lazy-import sub-libraries declared in `_SUB_LIBRARIES`.

        Per architecture L299/L354/L573 + agentguard `library.py:82-93`
        pattern: each entry is `(module_path, class_name)`; an
        `ImportError` or `AttributeError` on the lazy-import is logged
        at DEBUG + the sub-library is silently skipped (so the
        top-level library imports green even when later Epic
        sub-libraries are not yet shipped).

        Constructor-side exceptions on `cls()` are NOT silently
        swallowed (Story 2.1 code-review B7 fix; pre-edit shape logged
        at WARNING + continued, which masked real bugs in sub-library
        `__init__`). A constructor failure on a sub-library is a bug,
        not optionality — re-raise so `Library AgentEval` fails loudly
        instead of silently exposing a partial keyword namespace.
        """
        components: list[Any] = []
        for mod_name, cls_name in _SUB_LIBRARIES:
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
            except (ImportError, AttributeError) as exc:
                _logger.debug(
                    "AgentEval: sub-library %s.%s not loaded (%s)",
                    mod_name,
                    cls_name,
                    exc,
                )
                continue
            # Constructor errors propagate — they indicate bugs, not
            # optional sub-libraries. (Code-review B7 fix.)
            components.append(cls())
        return components

    @keyword(name="Get Effective Config")
    def get_effective_config(self) -> dict[str, Any]:
        """Return the resolved config as a dict.

        Story 1b.1: returns the FR41 precedence-resolved values (kwarg →
        env-var → `.env` → FR42 defaults).

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
