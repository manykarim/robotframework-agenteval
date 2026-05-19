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

"""Orchestration Library — `Send Prompt` + `Run Scenario` keywords (Story 4.3).

Implements PRD FR14 (Send Prompt) + FR15 (Run Scenario) + FR16
(mcp_servers= keyword arg). Wraps adapter resolution + scenario YAML
loading + eval-by-eval execution.

Phase-1 carve-outs (DF-4.3-S2 + DF-4.3-S3):
- `mcp_servers=` is accepted as a comma-separated name list OR an
  empty default; resolution to live `ServerHandle` instances is
  Phase-1.5 — Story 3.1 ratified the per-call-session pattern where
  the .robot test owns the `MCPServerHandle`, not a Library-managed
  registry. The Phase-1 orchestration layer forwards `mcp_servers`
  to `adapter.run(mcp_servers=...)` as a dict; today both Generic
  + Claude Code CLI adapters Phase-1-raise on non-empty mcp_servers
  (DF-4.1-S2 + DF-4.2-S1). Story 4.3 ships the API surface; the
  adapter-side integration is the upstream-blocking carry-over.
- `Run Scenario` executes each `evals[]` entry as a separate
  `adapter.run()` call sequentially. Full multi-turn conversation
  threading is Phase-1.5 — DF-4.3-S4.
"""

from __future__ import annotations

import inspect
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.tier import tier
from AgentEval.scenarios.loader import load_scenario
from AgentEval.scenarios.schema import Scenario
from AgentEval.types import AgentRunResult

__all__ = ["OrchestrationLibrary"]


# Story 4.3 code-review 3-way HIGH-A fix 2026-05-20 (Blind H2 + Edge-cases H1 +
# Codex HIGH-3): the pre-edit `adapter: str = "generic"` default could not
# distinguish "caller didn't pass adapter" from "caller explicitly passed
# adapter=generic". Use a sentinel matching Story 1b.1 H3 `_UNSET` pattern.
class _Unset:
    __slots__ = ()

    def __repr__(self) -> str:
        return "_UNSET"

    def __bool__(self) -> bool:
        return False


_UNSET: Any = _Unset()


def _split_adapter_kwargs(adapter_cls: type, kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Story 4.3 code-review 2-way HIGH-D fix 2026-05-20 (Codex HIGH-2):
    split caller kwargs into "constructor kwargs" (accepted by the adapter's
    `__init__`) vs "run-time kwargs" (forwarded to `run()`). Pre-edit ALL
    kwargs went to the constructor; strict third-party adapters crashed
    (TypeError) + per-call kwargs like `temperature` never reached `run()`.

    Strategy: introspect `adapter_cls.__init__` signature. Named params (other
    than `self` and `kwargs`) are constructor-bound; everything else goes to
    `run_kwargs`. Adapters accepting `**kwargs` get ALL kwargs (preserves the
    Story 1b.4 InProcessAdapter._adapter_config swallow-pattern).
    """
    try:
        sig = inspect.signature(adapter_cls)  # signature of the class IS the __init__ signature minus self
    except (TypeError, ValueError):
        # Fallback: forward everything to ctor (Story 4.3 Phase-1 behavior).
        return dict(kwargs), {}
    accepts_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    if accepts_var_keyword:
        # Adapter's __init__ has **kwargs — forward everything (Story 1b.4
        # InProcessAdapter pattern stores unknown kwargs on _adapter_config).
        return dict(kwargs), {}
    ctor_param_names = {
        p.name
        for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    ctor_kwargs = {k: v for k, v in kwargs.items() if k in ctor_param_names}
    run_kwargs = {k: v for k, v in kwargs.items() if k not in ctor_param_names}
    return ctor_kwargs, run_kwargs


class OrchestrationLibrary:
    """`Send Prompt` + `Run Scenario` keywords (Story 4.3 / PRD FR14 + FR15)."""

    def __init__(self, default_provider: str | None = None) -> None:
        """Story 4.3 code-review 2-way HIGH-C fix 2026-05-20 (Blind H3 + Codex HIGH-1):
        accept a `default_provider` to receive the AgentEval library's resolved
        config. Without this, `AgentEval(provider='mock').send_prompt(prompt='hi')`
        bypassed the library-level config and hit real LiteLLM with no model
        (raising ValueError). The AgentEval `_build_components()` now passes
        `self._provider` here so PRD FR41 precedence propagates to the
        orchestration surface.
        """
        self._default_provider: str | None = default_provider

    @keyword(name="Send Prompt")
    @tier(2)
    def send_prompt(
        self,
        adapter: str = "generic",
        prompt: str = "",
        mcp_servers: dict[str, Any] | str | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Execute a single-shot prompt against a coding-agent adapter (PRD FR14).

        [Tier 2 — Stochastic Single-Shot] — invokes the named adapter's
        `run()` method per Story 1b.4 ratified CodingAgentAdapter Protocol.

        Args:
            adapter: Adapter name registered via `agenteval.coding_agents`
                entry-points group (default: `"generic"` — Story 4.1
                LiteLLM-backed). Resolved via Story 1b.3 `get_adapter()`.
            prompt: Prompt text to send to the agent.
            mcp_servers: Phase-1 stub: dict[str, ServerHandle] forwarded
                to adapter.run(mcp_servers=...). String form (comma-separated
                names) is the user-facing convenience but Story 4.3
                Phase-1 doesn't yet resolve names → handles (DF-4.3-S2).
                Default None passes through cleanly.
            **kwargs: Provider/adapter-specific forward-compat kwargs
                (e.g., `model="anthropic/claude-sonnet-4-6"`, `temperature=0.5`).

        Returns:
            `AgentRunResult` with the agent's response per Story 1b.4
            ratified shape.

        Raises:
            AdapterDiscoveryError: when `adapter` name is unknown.
            NotImplementedError: when `mcp_servers` is non-empty (DF-4.3-S2
                + DF-4.1-S2 + DF-4.2-S1 — adapter-side integration is
                Phase-1.5).
        """
        # Story 4.3 code-review 2-way HIGH-C fix 2026-05-20: inject the
        # library-level `provider` default when caller didn't pass one.
        # Preserves PRD FR41 precedence (call kwarg > library config).
        effective_kwargs = dict(kwargs)
        if self._default_provider is not None and "provider" not in effective_kwargs:
            effective_kwargs["provider"] = self._default_provider

        # Story 4.3 code-review 2-way HIGH-D fix 2026-05-20 (Codex HIGH-2):
        # split caller kwargs into adapter-constructor kwargs vs run() kwargs
        # via signature introspection. Pre-edit ALL kwargs went to ctor,
        # which (a) crashed strict adapters with TypeError on unknown kwargs
        # + (b) silently dropped per-call kwargs like `temperature` that
        # the user intended to reach `chat()`.
        adapter_cls = get_adapter(adapter)
        ctor_kwargs, run_kwargs = _split_adapter_kwargs(adapter_cls, effective_kwargs)
        adapter_instance = adapter_cls(**ctor_kwargs)

        # Story 4.3 Phase-1 carve-out (DF-4.3-S2): mcp_servers string-form
        # name-resolution to live handles is Phase-1.5; the dict-form
        # passes through directly. Empty / None is allowed.
        mcp_servers_resolved: dict[str, Any] | None = None
        if mcp_servers is not None:
            if isinstance(mcp_servers, dict):
                mcp_servers_resolved = mcp_servers if mcp_servers else None
            elif isinstance(mcp_servers, str):
                name_list = [name.strip() for name in mcp_servers.split(",") if name.strip()]
                if name_list:
                    raise NotImplementedError(
                        "Send Prompt does not yet resolve comma-separated MCP server name lists "
                        "to ServerHandle instances (Story 4.3 DF-4.3-S2 carry-over). "
                        "Pass `mcp_servers={'name': handle}` dict directly OR use `mcp_servers=None` "
                        "for Phase-1 single-shot prompts. Adapter-side `mcp_servers=` integration "
                        "is tracked in DF-4.1-S2 (Generic) + DF-4.2-S1 (Claude Code CLI)."
                    )

        # Forward to the adapter's `run()` per FR12 single-method Protocol.
        # Per HIGH-D fix: run_kwargs (kwargs the adapter ctor didn't take)
        # are forwarded to run() so per-call settings like `temperature`
        # reach the underlying provider.
        result = adapter_instance.run(prompt, mcp_servers=mcp_servers_resolved, **run_kwargs)
        assert isinstance(result, AgentRunResult)
        return result

    @keyword(name="Run Scenario")
    @tier(3)
    def run_scenario(
        self,
        adapter: str | _Unset = _UNSET,
        scenario: str = "",
        mcp_servers: dict[str, Any] | str | None = None,
        **kwargs: Any,
    ) -> list[AgentRunResult]:
        """Execute a scenario YAML file's `evals[]` against an adapter (PRD FR15).

        [Tier 3 — Stochastic Fan-Out] — loads the scenario YAML via
        `scenarios.loader.load_scenario()`, validates against the
        `Scenario` schema (raises `InvalidScenarioYAMLError` per
        Story 4.3 catalog amendment 18th leaf), then dispatches each
        eval's prompt to `adapter.run()` `eval.repeat` times.

        Args:
            adapter: Adapter name (default `"generic"`). Per-scenario
                `agent:` field in the YAML OVERRIDES this kwarg
                (precedence per PRD FR41 spirit — YAML beats default
                but not explicit kwarg per FR15's "scenario YAML
                specifies model/provider/agent" wording).
            scenario: Path to the scenario YAML file.
            mcp_servers: Phase-1 stub (see `Send Prompt` for semantics).
            **kwargs: Adapter forward-compat kwargs.

        Returns:
            List of `AgentRunResult` records — one per eval execution.
            For an `evals[]` of N entries with `repeat: k` each, length
            is N * k.

        Raises:
            InvalidScenarioYAMLError: on YAML parse / schema violation.
            AdapterDiscoveryError: on unknown adapter name.
            NotImplementedError: on non-empty `mcp_servers` (DF-4.3-S2).
        """
        if not scenario:
            raise ValueError("Run Scenario requires `scenario=<path>` kwarg")
        scenario_obj = load_scenario(scenario)

        # Story 4.3 code-review 3-way HIGH-A fix 2026-05-20 (Blind H2 +
        # Edge-cases H1 + Codex HIGH-3): use `_UNSET` sentinel to honestly
        # distinguish "caller didn't pass adapter" from "caller explicitly
        # passed adapter=generic". Pre-edit string-compared to "generic"
        # which collided with the function default — the inverse of the
        # docstring contract.
        resolved_adapter_name: str
        if adapter is _UNSET:
            resolved_adapter_name = scenario_obj.agent or "generic"
        else:
            assert isinstance(adapter, str)
            resolved_adapter_name = adapter
        adapter_cls = get_adapter(resolved_adapter_name)
        # Story 4.3 code-review 2-way HIGH-C fix: inject library-level
        # `provider` default when neither caller kwargs NOR scenario YAML
        # specifies one.
        merged_kwargs: dict[str, Any] = dict(kwargs)
        if scenario_obj.model is not None and "model" not in merged_kwargs:
            merged_kwargs["model"] = scenario_obj.model
        if scenario_obj.provider is not None and "provider" not in merged_kwargs:
            merged_kwargs["provider"] = scenario_obj.provider
        if self._default_provider is not None and "provider" not in merged_kwargs and scenario_obj.provider is None:
            merged_kwargs["provider"] = self._default_provider
        # Story 4.3 code-review 2-way HIGH-D fix: split into ctor / run kwargs.
        ctor_kwargs, run_kwargs = _split_adapter_kwargs(adapter_cls, merged_kwargs)
        adapter_instance = adapter_cls(**ctor_kwargs)

        # Story 4.3 code-review 2-way HIGH-B fix 2026-05-20 (Blind H1 +
        # Codex HIGH-4): pre-edit silently dropped `scenario_obj.mcp_servers`
        # — the loader parsed + validated the field but the executor never
        # read it. A user writing scenario YAML with `mcp_servers: [echo]`
        # got silent no-MCP execution. Now we honor the YAML field when
        # the caller didn't pass `mcp_servers=` explicitly; resolution
        # then flows through the SAME name-list path (which today raises
        # NotImplementedError per DF-4.3-S2 — loud-fail is correct).
        mcp_servers_resolved: dict[str, Any] | None = None
        effective_mcp_servers: dict[str, Any] | str | None = mcp_servers
        if effective_mcp_servers is None and scenario_obj.mcp_servers:
            # Comma-join the scenario YAML list and pass through the same
            # name-list resolution code path that the caller-string form uses.
            effective_mcp_servers = ",".join(scenario_obj.mcp_servers)
        if effective_mcp_servers is not None:
            if isinstance(effective_mcp_servers, dict):
                mcp_servers_resolved = effective_mcp_servers if effective_mcp_servers else None
            elif isinstance(effective_mcp_servers, str):
                name_list = [n.strip() for n in effective_mcp_servers.split(",") if n.strip()]
                if name_list:
                    raise NotImplementedError(
                        "Run Scenario does not yet resolve comma-separated MCP server name lists "
                        "to ServerHandle instances (Story 4.3 DF-4.3-S2 carry-over). "
                        "This applies to BOTH the caller `mcp_servers=` kwarg AND the scenario "
                        "YAML `mcp_servers:` field — pre-fix the YAML field was silently dropped."
                    )

        results: list[AgentRunResult] = []
        for eval_entry in scenario_obj.evals:
            for _ in range(eval_entry.repeat):
                result = adapter_instance.run(
                    eval_entry.prompt,
                    mcp_servers=mcp_servers_resolved,
                    **run_kwargs,
                )
                assert isinstance(result, AgentRunResult)
                results.append(result)
        return results

    @keyword(name="Load Scenario")
    @tier(1)
    def load_scenario_kw(self, scenario: str) -> Scenario:
        """Load + validate a scenario YAML without executing.

        [Tier 1 — Deterministic] — pure file read + YAML parse + schema
        validation. Story 4.3 surface for callers who want to inspect
        the parsed `Scenario` shape before deciding whether to `Run
        Scenario` against it (e.g., for `.robot` tests that assert
        on scenario metadata).

        Raises:
            InvalidScenarioYAMLError: on parse / schema failure.
        """
        return load_scenario(scenario)
