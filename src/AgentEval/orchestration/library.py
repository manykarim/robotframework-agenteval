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

# ruff: noqa: E501
# Browser-Library-style docstring tables (`| =Arguments= | =Description= |`)
# can carry long descriptions on a single physical line; libdoc renders
# them correctly. The per-line 120-char limit is waived for this file
# per Phase 2 docstring-refresh proposal (2026-05-26).

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

# Browser-Library-style docstring migration marker (Phase 2, 2026-05-26).
# See `tests/unit/conventions/test_docstring_browser_style.py`.
_BROWSER_STYLE_MIGRATED = True


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
        """Executes a single-shot prompt against a coding-agent adapter (PRD FR14).

        [Tier 2 — Stochastic Single-Shot] — invokes the named adapter's
        ``run()`` method per the `CodingAgentAdapter` Protocol. Returns
        an ``AgentRunResult`` carrying ``response_text``, ``tool_calls``,
        ``usage``, ``metadata`` (with ``completeness`` + ``mcp_coverage``),
        ``cost_usd``, ``latency_seconds``, and ``trace_id``.

        | =Arguments= | =Description= |
        | ``adapter`` | Adapter name registered via the ``agenteval.coding_agents`` entry-points group. Defaults to ``"generic"`` (LiteLLM-backed). |
        | ``prompt`` | Prompt text to send to the agent. |
        | ``mcp_servers`` | Optional ``dict[str, ServerHandle]`` of attached MCP servers. Phase-1: comma-separated name strings raise ``NotImplementedError`` (DF-4.3-S2 — name resolution to handles deferred). |

        Additional keyword arguments are forwarded to the adapter — caller
        kwargs that match the adapter's ``__init__`` signature flow to
        construction; the rest flow to ``run()``. Useful for
        ``model="anthropic/claude-sonnet-4-6"``, ``temperature=0.5``, etc.

        Raises ``AdapterDiscoveryError`` when the ``adapter`` name is not
        registered. Raises ``NotImplementedError`` on comma-separated
        ``mcp_servers`` name strings until DF-4.3-S2 lands the name →
        handle resolver (pass ``mcp_servers={'name': handle}`` directly to
        forward Phase-1).

        Example:
        | ${result} =    `Send Prompt`    prompt=Hello, world.
        | ${result} =    `Send Prompt`    adapter=claude-code-cli    prompt=Run the build.
        | ${result} =    `Send Prompt`    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6
        | `Tool Call Should Have Occurred`    ${result}    web_search

        Notes:
        - PRD FR14 ratifies the single-prompt orchestration contract.
        - Adapter discovery per Story 1b.3 + ADR-013 entry-points.
        - ``cost_usd`` is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.
        - Sibling keyword: `Run Scenario` for multi-eval YAML-driven dispatch (Tier-3).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).

        [Tier 3 — Stochastic Fan-Out] — loads the scenario YAML via
        ``load_scenario()``, validates against the ``Scenario`` schema,
        then dispatches each eval's prompt to ``adapter.run()`` ``repeat``
        times. Returns a flat ``list[AgentRunResult]`` of length
        ``sum(eval.repeat for eval in scenario.evals)``.

        | =Arguments= | =Description= |
        | ``adapter`` | Adapter name. Per-scenario ``agent:`` field in the YAML overrides this kwarg per FR15 ("scenario YAML specifies agent" — YAML beats default but not explicit kwarg). |
        | ``scenario`` | Filesystem path to the scenario YAML file. |
        | ``mcp_servers`` | Optional ``dict[str, ServerHandle]``. Phase-1: comma-separated name strings raise ``NotImplementedError`` (DF-4.3-S2). |

        Additional keyword arguments are split between adapter
        constructor + ``run()`` per the same signature-introspection
        rule as `Send Prompt`. Scenario-YAML ``model:`` /
        ``provider:`` fields inject into the merged kwargs unless the
        caller already passed them.

        Raises ``InvalidScenarioYAMLError`` on YAML parse / schema
        failure, ``AdapterDiscoveryError`` on unknown adapter name, and
        ``NotImplementedError`` on non-empty comma-separated
        ``mcp_servers`` (Phase-1 DF-4.3-S2 carve-out).

        Example:
        | @{results} =    `Run Scenario`    scenario=${CURDIR}/scenarios/web-search.yaml
        | Length Should Be    ${results}    5
        | `Trajectory Should Match`    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}
        | @{results} =    `Run Scenario`    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml

        Notes:
        - PRD FR15 ratifies the multi-eval orchestration contract.
        - FR41 precedence resolution: explicit kwarg > scenario YAML > library default.
        - Sibling keyword: `Load Scenario` (Tier-1) to validate the YAML without executing.
        - Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Loads + validates a scenario YAML without executing it.

        [Tier 1 — Deterministic] — pure file read + YAML parse + schema
        validation. Returns the parsed ``Scenario`` dataclass without
        dispatching to any adapter — useful for ``.robot`` tests that
        assert on scenario metadata or pre-flight-check scenarios before
        a `Run Scenario` invocation.

        | =Arguments= | =Description= |
        | ``scenario`` | Filesystem path to the scenario YAML file. |

        Raises ``InvalidScenarioYAMLError`` on parse failure or schema
        violation. The error's ``field_name`` attribute pinpoints the
        offending field per FR59.

        Example:
        | ${scenario} =    `Load Scenario`    ${CURDIR}/scenarios/web-search.yaml
        | Should Be Equal    ${scenario.name}    web-search
        | Length Should Be    ${scenario.evals}    5
        | Should Contain    ${scenario.tags}    smoke

        Notes:
        - PRD FR15 ratifies the scenario YAML schema; see `Scenario` dataclass in `scenarios/schema.py`.
        - Sibling keyword: `Run Scenario` (Tier-3) for dispatch + execution.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return load_scenario(scenario)
