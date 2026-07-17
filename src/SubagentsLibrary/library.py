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

"""Test SubAgents - config drift and delegation routing.

Tier-1 keywords inspect a subagent ``.md`` and project delegations out of an
already-captured run. Tier-3 keywords drive a real agent through the shared
adapter to probe routing.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._core import (
    Adapter,
    AgentRunResult,
    InvalidConfigError,
    KeywordRun,
    SubagentDelegationError,
    get_adapter,
    stats,
    tier,
)
from SubagentsLibrary._internal import extract_delegations, observed_subagents
from SubagentsLibrary._parser import parse_subagent_frontmatter, validate_subagent_structure
from SubagentsLibrary._tasks import load_subagent_routing_tasks
from SubagentsLibrary.types import (
    DelegationDecision,
    DelegationRecord,
    SubagentRoutingResult,
    SubagentRoutingSummary,
    SubagentRoutingTaskResult,
)

__all__ = ["SubagentsLibrary"]


def _delegation_tools_arg(delegation_tool: str | None) -> list[str] | None:
    """Turn the singular ``delegation_tool=`` kwarg into the extractor's set arg."""
    return None if delegation_tool is None else [delegation_tool]


def _routed(run: KeywordRun) -> bool:
    """Pass predicate for a routing trial: a ``DelegationDecision`` that delegated."""
    return isinstance(run.result, DelegationDecision) and run.result.delegated


class SubagentsLibrary:
    """Config-drift and delegation-routing keywords for subagent ``.md`` files.

    Tier-1 keywords are deterministic (file read + trace projection). Tier-3
    keywords resolve an adapter through the shared spine and drive the agent.
    """

    # ------------------------------------------------------------------ #
    # Tier-1 static inspection                                           #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parses the YAML frontmatter at the head of a subagent ``.md`` file.

        Returns a dict with at least ``name`` and ``description``; may carry
        optional ``tools``, ``model``, and ``skills``. Raises
        ``InvalidConfigError`` on any structural failure.

        Example:
        | ${fm} =    Subagent.Get Frontmatter    ${CURDIR}/agents/code-reviewer.md
        | Should Be Equal    ${fm}[name]    code-reviewer
        """
        frontmatter = parse_subagent_frontmatter(path)
        validate_subagent_structure(frontmatter, file_path=str(path))
        return frontmatter

    # ------------------------------------------------------------------ #
    # Tier-1 delegation projection + assertions (over an existing result) #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Get Delegations")
    @tier(1)
    def get_delegations(
        self,
        result: AgentRunResult,
        delegation_tool: str | None = None,
    ) -> list[DelegationRecord]:
        """Extracts orchestrator to subagent delegations from a run result.

        Pure projection of ``result.tool_calls`` - one ``DelegationRecord`` per
        Task-tool call (default tool name ``Task``, matched case-insensitively),
        ordered by ``sequence_index``.

        Example:
        | ${dels} =    Subagent.Get Delegations    ${result}
        | Length Should Be    ${dels}    2
        """
        return extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))

    @keyword(name="Subagent.Should Have Delegated To")
    @tier(1)
    def should_have_delegated_to(
        self,
        result: AgentRunResult,
        subagent: str,
        delegation_tool: str | None = None,
    ) -> None:
        """Asserts the run delegated to the named subagent at least once.

        Passes when an extracted delegation's ``subagent`` exactly equals
        ``subagent``. On failure raises ``SubagentDelegationError`` naming the
        expected subagent and listing what was observed.

        Example:
        | Subagent.Should Have Delegated To    ${result}    code-reviewer
        """
        observed = observed_subagents(extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool)))
        if subagent in observed:
            return
        detail = f"the run delegated to: {observed}." if observed else "no delegations were observed in the run."
        raise SubagentDelegationError(f"Expected a delegation to '{subagent}', but {detail}")

    @keyword(name="Subagent.Should Not Have Delegated")
    @tier(1)
    def should_not_have_delegated(
        self,
        result: AgentRunResult,
        subagent: str | None = None,
        delegation_tool: str | None = None,
    ) -> None:
        """Asserts the run did NOT delegate (optionally, to a specific subagent).

        With a ``subagent`` name, fails only on a delegation to that subagent;
        without one, fails on any delegation. On failure raises
        ``SubagentDelegationError``.

        Example:
        | Subagent.Should Not Have Delegated    ${result}
        | Subagent.Should Not Have Delegated    ${result}    db-admin
        """
        observed = observed_subagents(extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool)))
        if subagent is None:
            if not observed:
                return
            raise SubagentDelegationError(f"Expected no delegations, but the run delegated to: {observed}.")
        if subagent not in observed:
            return
        raise SubagentDelegationError(f"Expected no delegation to '{subagent}', but the run delegated to it.")

    # ------------------------------------------------------------------ #
    # Tier-3 routing (raise-vs-return share one helper)                  #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Should Delegate To")
    @tier(3)
    def should_delegate_to(
        self,
        prompt: str,
        subagent: str,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        delegation_tool: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Runs a prompt once and asserts the orchestrator delegated to the subagent.

        Sends ``prompt`` through the adapter exactly once and passes only if the
        run delegated to ``subagent``. On a miss raises ``SubagentDelegationError``
        carrying the observed delegations and the agent's reasoning.

        Example:
        | Subagent.Should Delegate To    Review my PR    code-reviewer    adapter=generic
        """
        decision = self._route_once(prompt, subagent, adapter, model, delegation_tool, kwargs)
        if decision.delegated:
            return
        observed = observed_subagents(list(decision.delegations))
        detail = f"it delegated to: {observed}." if observed else "it did not delegate."
        raise SubagentDelegationError(
            f"Expected the orchestrator to delegate to '{subagent}' for the prompt, but {detail}"
        )

    @keyword(name="Subagent.Get Delegation Decision")
    @tier(3)
    def get_delegation_decision(
        self,
        prompt: str,
        subagent: str,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        delegation_tool: str | None = None,
        **kwargs: Any,
    ) -> DelegationDecision:
        """Runs a prompt once and returns a routing decision (fan-out composable).

        Returns a ``DelegationDecision`` (``delegated``, all ``delegations``,
        ``reasoning``, ``cost_usd``, ``latency_seconds``). Never raises on a
        routing miss - it reports the decision so a ``Run N Times`` cohort can
        aggregate it.

        Example:
        | ${d} =    Subagent.Get Delegation Decision    Review my PR    code-reviewer
        | Should Be True    ${d.delegated}
        """
        return self._route_once(prompt, subagent, adapter, model, delegation_tool, kwargs)

    @keyword(name="Subagent.Get Routing Accuracy")
    @tier(3)
    def get_routing_accuracy(
        self,
        tasks: str | Path,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        trials_per_task: int = 3,
        delegation_tool: str | None = None,
        **kwargs: Any,
    ) -> SubagentRoutingResult:
        """Runs a routing-tasks cohort and reports the fraction routed correctly.

        Loads a routing-tasks YAML (``tasks: [{id, prompt, expected_subagent}]``),
        runs ``trials_per_task`` calls per task through the adapter, and returns a
        ``SubagentRoutingResult``. The summary carries ``routing_accuracy`` and its
        Wilson 95% confidence interval (``ci_lower`` / ``ci_upper``).

        Example:
        | ${r} =    Subagent.Get Routing Accuracy    ${CURDIR}/tasks/routing.yaml
        | Should Be True    ${r.summary.routing_accuracy} >= 0.6
        """
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1, got {trials_per_task}")

        task_list = load_subagent_routing_tasks(tasks)
        t_start = time.perf_counter()

        per_task_results: list[SubagentRoutingTaskResult] = []
        total_trials = 0
        total_matches = 0
        total_cost = 0.0
        for task in task_list:
            runs = stats.run_n(
                self._route_once,
                trials_per_task,
                task.prompt,
                task.expected_subagent,
                adapter,
                model,
                delegation_tool,
                kwargs,
            )
            matches = sum(1 for run in runs if _routed(run))
            trial_costs = [run.result.cost_usd for run in runs if isinstance(run.result, DelegationDecision)]
            cost_per_trial = sum(trial_costs) / trials_per_task
            per_task_results.append(
                SubagentRoutingTaskResult(
                    task_id=task.id,
                    prompt=task.prompt,
                    expected_subagent=task.expected_subagent,
                    trials_run=trials_per_task,
                    matches_observed=matches,
                    pass_at_k=stats.pass_at_k(runs, 1, predicate=_routed),
                    cost_per_trial_usd=cost_per_trial,
                )
            )
            total_trials += trials_per_task
            total_matches += matches
            total_cost += sum(trial_costs)

        routing_accuracy = total_matches / total_trials if total_trials > 0 else 0.0
        ci_lower, ci_upper = stats.wilson_interval(total_matches, total_trials) if total_trials else (0.0, 1.0)
        summary = SubagentRoutingSummary(
            routing_accuracy=routing_accuracy,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            total_trials=total_trials,
            total_matches=total_matches,
            total_cost_usd=total_cost,
            total_runtime_seconds=time.perf_counter() - t_start,
        )
        return SubagentRoutingResult(per_task_results=tuple(per_task_results), summary=summary)

    # ------------------------------------------------------------------ #
    # Tier-1 config-drift static checks                                  #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Should Declare Skills")
    @tier(1)
    def should_declare_skills(self, path: str | Path, *skills: str) -> None:
        """Asserts a subagent frontmatter explicitly declares every named skill.

        Subagents do NOT inherit the parent agent's skills, so an absent or empty
        ``skills:`` field FAILS - it never vacuously passes. On failure raises
        ``InvalidConfigError`` naming the missing skill(s).

        Example:
        | Subagent.Should Declare Skills    ${CURDIR}/agents/researcher.md    pdf-tools    web-search
        """
        if not skills:
            raise ValueError(
                "Subagent.Should Declare Skills requires one or more expected skill names; "
                "calling it with none would vacuously pass and certify nothing."
            )
        frontmatter = self.get_frontmatter(path)
        declared_raw = frontmatter.get("skills")
        declared = declared_raw if isinstance(declared_raw, list) else []
        if not declared:
            raise InvalidConfigError(
                "Subagent frontmatter declares no skills, but subagents do not inherit parent skills.",
                file_path=str(path),
                fix="Add an explicit `skills:` list preloading every skill the subagent needs.",
            )
        missing = [s for s in skills if s not in declared]
        if missing:
            raise InvalidConfigError(
                f"Subagent frontmatter is missing required skill(s): {missing}.",
                file_path=str(path),
                field=",".join(missing),
                fix="Add the missing skill(s) to the subagent's `skills:` frontmatter list.",
            )

    @keyword(name="Subagent.Tools Should Be Subset Of")
    @tier(1)
    def tools_should_be_subset_of(self, path: str | Path, *allowlist: str) -> None:
        """Asserts a subagent's declared tools are all within an allowlist.

        An absent ``tools:`` field grants the full parent tool set, so a missing
        or empty declaration FAILS (fail-loud on inherit-everything). On failure
        raises ``InvalidConfigError`` naming the disallowed tools.

        Example:
        | Subagent.Tools Should Be Subset Of    ${CURDIR}/agents/reviewer.md    Read    Grep    Bash
        """
        frontmatter = self.get_frontmatter(path)
        declared_raw = frontmatter.get("tools")
        declared = declared_raw if isinstance(declared_raw, list) else []
        if not declared:
            raise InvalidConfigError(
                "Subagent frontmatter declares no `tools:` - omitting it inherits the full parent tool set.",
                file_path=str(path),
                fix="Declare an explicit `tools:` list in the subagent frontmatter.",
            )
        offending = [t for t in declared if t not in allowlist]
        if offending:
            raise InvalidConfigError(
                f"Subagent declares tool(s) outside the allowlist: {offending}.",
                file_path=str(path),
                field=",".join(offending),
                fix=f"Remove the offending tool(s), or add them to the asserted allowlist {list(allowlist)!r}.",
            )

    # ------------------------------------------------------------------ #
    # Shared adapter-run helpers (Tier-3)                                #
    # ------------------------------------------------------------------ #

    def _route_once(
        self,
        prompt: str,
        subagent: str,
        adapter: str | Adapter,
        model: str | None,
        delegation_tool: str | None,
        extra_kwargs: dict[str, Any],
    ) -> DelegationDecision:
        """Run ``prompt`` once and compute the routing decision for ``subagent``."""
        result = self._run_adapter_once(prompt, adapter, model, extra_kwargs)
        records = extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))
        return DelegationDecision(
            delegated=subagent in observed_subagents(records),
            delegations=tuple(records),
            reasoning=result.response_text,
            cost_usd=result.cost_usd,
            latency_seconds=result.latency_seconds,
        )

    def _run_adapter_once(
        self,
        prompt: str,
        adapter: str | Adapter,
        model: str | None,
        extra_kwargs: dict[str, Any],
    ) -> AgentRunResult:
        """Resolve the adapter through the spine and run ``prompt`` exactly once."""
        ctor_kwargs: dict[str, Any] = dict(extra_kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        return get_adapter(adapter, **ctor_kwargs).run(prompt)
