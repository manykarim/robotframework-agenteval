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

from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.tier import tier
from AgentEval.scenarios.loader import load_scenario
from AgentEval.scenarios.schema import Scenario
from AgentEval.types import AgentRunResult

__all__ = ["OrchestrationLibrary"]


class OrchestrationLibrary:
    """`Send Prompt` + `Run Scenario` keywords (Story 4.3 / PRD FR14 + FR15)."""

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
        # Resolve the adapter class via Story 1b.3 entry-points discovery.
        # Forward all kwargs to the adapter constructor; the adapter
        # decides what to keep as construction state (e.g., provider,
        # model) vs apply per-call. Phase-1 design: `Send Prompt
        # provider=mock model=foo` constructs `GenericAdapter(provider=
        # "mock", model="foo")`. Story 4.3 carry-over DF-4.3-S5: a
        # future story could split constructor-kwargs from run-kwargs
        # via adapter-signature introspection; Phase-1 ships the
        # all-to-constructor pattern + relies on the adapter ignoring
        # unknown kwargs (Story 1b.4 InProcessAdapter stores them in
        # `self._adapter_config`).
        adapter_cls = get_adapter(adapter)
        adapter_kwargs = {k: v for k, v in kwargs.items() if k != "prompt"}
        adapter_instance = adapter_cls(**adapter_kwargs)

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
        # Phase-1: all caller kwargs went to the constructor; run() only
        # gets prompt + mcp_servers. The adapter applies its stored
        # construction state (e.g., GenericAdapter._model) in run().
        result = adapter_instance.run(prompt, mcp_servers=mcp_servers_resolved)
        assert isinstance(result, AgentRunResult)
        return result

    @keyword(name="Run Scenario")
    @tier(3)
    def run_scenario(
        self,
        adapter: str = "generic",
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

        # PRD FR15 precedence resolution: keyword kwarg WINS over scenario
        # YAML `agent:` field per epics.md ratified contract (per-keyword
        # kwargs are call-time overrides; scenario YAML is per-scenario
        # static config). Defensible Phase-1 stance.
        resolved_adapter_name = (
            adapter if adapter != "generic" or scenario_obj.agent is None else (scenario_obj.agent or adapter)
        )
        adapter_cls = get_adapter(resolved_adapter_name)
        # Story 4.3 Phase-1: forward kwargs to adapter constructor (see
        # Send Prompt comment for rationale). Scenario YAML top-level
        # `model`/`provider` fields are also forwarded as construction
        # kwargs unless the caller passed an explicit override.
        adapter_kwargs: dict[str, Any] = dict(kwargs)
        if scenario_obj.model is not None and "model" not in adapter_kwargs:
            adapter_kwargs["model"] = scenario_obj.model
        if scenario_obj.provider is not None and "provider" not in adapter_kwargs:
            adapter_kwargs["provider"] = scenario_obj.provider
        adapter_instance = adapter_cls(**adapter_kwargs)

        # mcp_servers Phase-1 stub (DF-4.3-S2 — same as Send Prompt).
        mcp_servers_resolved: dict[str, Any] | None = None
        if mcp_servers is not None:
            if isinstance(mcp_servers, dict):
                mcp_servers_resolved = mcp_servers if mcp_servers else None
            elif isinstance(mcp_servers, str):
                name_list = [n.strip() for n in mcp_servers.split(",") if n.strip()]
                if name_list:
                    raise NotImplementedError(
                        "Run Scenario does not yet resolve comma-separated MCP server name lists "
                        "to ServerHandle instances (Story 4.3 DF-4.3-S2 carry-over)."
                    )

        results: list[AgentRunResult] = []
        for eval_entry in scenario_obj.evals:
            for _ in range(eval_entry.repeat):
                result = adapter_instance.run(
                    eval_entry.prompt,
                    mcp_servers=mcp_servers_resolved,
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
