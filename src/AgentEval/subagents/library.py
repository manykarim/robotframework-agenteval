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
# Browser-Library-style docstring tables carry long descriptions on a single
# physical line. Per-line 120-char limit waived for this file (mirrors the
# skills library's Phase 6 docstring-refresh waiver).

"""Subagent sub-library — static inspection + delegation-routing keywords.

Story 2.2 shipped 1 static-inspection keyword (`Subagent.Get Frontmatter`).
The `add-subagent-delegation-testing` change adds 9 keywords across two new
capabilities:

Delegation-routing (over the already-captured `AgentRunResult.tool_calls`):
- `Subagent.Get Delegations` (Tier 1) — extract Task-tool delegations.
- `Subagent.Should Have Delegated To` (Tier 1) — occurrence assertion.
- `Subagent.Should Not Have Delegated` (Tier 1) — absence assertion.
- `Subagent.Should Delegate To` (Tier 2) — single-shot routing probe.
- `Subagent.Get Delegation Decision` (Tier 3) — decision getter (fan-out).
- `Subagent.Get Routing Pass At K` (Tier 1) — Pass@k over routing trials.
- `Subagent.Get Routing Accuracy` (Tier 3) — tasks-YAML cohort evaluation.

Config-drift static checks on subagent `.md` files:
- `Subagent.Should Declare Skills` (Tier 1) — explicit `skills:` preloading.
- `Subagent.Tools Should Be Subset Of` (Tier 1) — tools allowlist validation.

Every keyword bakes its `Subagent.` namespace prefix into its
`@keyword(name=...)` value (multi-word post-dot per
`feedback_libdoc_namespace_keyword_must_be_multiword`), so the call site is
identical under the composed `Library AgentEval` import and a standalone
module-path import.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval

    *** Test Cases ***
    Orchestrator Routes To Reviewer
        ${result}=    Send Prompt    Review my open PR    adapter=claude_code_cli
        Subagent.Should Have Delegated To    ${result}    code-reviewer

Composition: registered in `AgentEval.__init__._SUB_LIBRARIES` so
`Library AgentEval` flattens every keyword into the parent namespace via
`robotlibcore.DynamicCore`. `SubagentsLibrary` subclasses `_HostBudgetPlumbing`
so the Tier-3 `@guarded_fanout` keywords honor `max_cost_usd` +
`max_runtime_seconds` (forwarded automatically under the composed import;
passed at RF `Library` import time for a standalone import).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval._kernel.tier import tier
from AgentEval._kernel.tier_acl import build_polling_disallowed_message
from AgentEval.errors import (
    PollingDisallowedError,
    SubagentConfigDriftError,
    SubagentDelegationAssertionError,
)
from AgentEval.subagents._internal import extract_delegations, observed_subagents
from AgentEval.subagents._parser import parse_subagent_frontmatter, validate_subagent_structure
from AgentEval.subagents.types import (
    DelegationDecision,
    DelegationRecord,
    SubagentRoutingResult,
    SubagentRoutingSummary,
    SubagentRoutingTaskResult,
)

if TYPE_CHECKING:
    from AgentEval.stats.types import KeywordRun
    from AgentEval.types import AgentRunResult

__all__ = ["SubagentsLibrary"]

# Browser-Library-style docstring migration marker (Phase 1, 2026-05-26).
# Read by `tests/unit/conventions/test_docstring_browser_style.py` +
# `test_docstring_examples_dryrun.py` to determine which libraries are
# subject to the Browser-style structure + example-dryrun enforcement.
_BROWSER_STYLE_MIGRATED = True


def _delegation_tools_arg(delegation_tool: str | None) -> list[str] | None:
    """Convert the singular `delegation_tool=` kwarg to the extractor's set arg."""
    return None if delegation_tool is None else [delegation_tool]


class SubagentsLibrary(_HostBudgetPlumbing):
    """Static-inspection + delegation-routing keywords for sub-agent `.md` files [mixed tiers].

    Inherits `_HostBudgetPlumbing` so the Tier-3 `@guarded_fanout` keywords
    (`Subagent.Get Delegation Decision`, `Subagent.Get Routing Accuracy`)
    enforce `max_cost_usd` + `max_runtime_seconds` budgets. Tier-1 keywords
    hold no mutable state and re-read the target file / project the passed-in
    result per call (stateless + parallel-safe under `pabot --processes N`).
    """

    @keyword(name="Subagent.Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parses the YAML frontmatter at the head of a sub-agent ``.md`` file.

        [Tier 1 — Deterministic] — pure file-read + YAML parse + structural
        validation per PRD FR3. Returns a dict with at minimum ``name`` +
        ``description`` (both required); may carry optional ``tools`` (list),
        ``model`` (str), and ``skills`` (list). Median ≤ 50 ms on typical
        sub-agent files per NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the sub-agent ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSubagentDefinitionError`` on any structural failure
        (missing file, broken YAML, missing or wrong-type required field, or a
        malformed optional ``tools`` / ``model`` / ``skills`` field).

        Example:
        | ${frontmatter} =    `Subagent.Get Frontmatter`    ${CURDIR}/agents/code-reviewer.md
        | Should Be Equal    ${frontmatter}[name]    code-reviewer
        | Should Contain    ${frontmatter}[description]    Reviews diffs

        Notes:
        - PRD FR3 ratifies the required ``name`` + ``description`` fields.
        - Optional ``skills`` field type-checked since add-subagent-delegation-testing (list of non-empty strings); pair with `Subagent.Should Declare Skills` for the config-drift assertion.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format: FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Parallel surface: `SkillsLibrary.Get Frontmatter` for skill ``.md`` files (different validation rules).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        frontmatter = parse_subagent_frontmatter(path)
        validate_subagent_structure(frontmatter, file_path=str(path))
        return frontmatter

    # ------------------------------------------------------------------ #
    # Tier-1 delegation-routing assertions (over an existing result)      #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Get Delegations")
    @tier(1)
    def get_delegations(
        self,
        result: AgentRunResult,
        delegation_tool: str | None = None,
    ) -> list[DelegationRecord]:
        """Extracts orchestrator→subagent delegations from an agent run result.

        [Tier 1 — Deterministic] — pure projection of ``result.tool_calls``;
        no agent call, no network. Returns one ``DelegationRecord`` per
        Task-tool invocation (default tool-name set ``{"Task"}``, matched
        case-insensitively), ordered by ``sequence_index``. The subagent
        identity is probed from each trace's ``args`` in the fixed key order
        ``subagent_type`` → ``agent_type`` → ``agent`` → ``name``; an
        unrecognized shape yields ``subagent=""`` (a visible non-match, never a
        silent drop). The default tool name is Claude-Code-aligned.

        | =Arguments= | =Description= |
        | ``result`` | An ``AgentRunResult`` (e.g. from ``Send Prompt``). |
        | ``delegation_tool`` | Optional override of the delegation tool name (default ``Task``). Use for CLIs whose dispatch tool has a different name (e.g. ``dispatch_agent``). |

        Example:
        | ${dels} =    `Subagent.Get Delegations`    ${result}
        | Length Should Be    ${dels}    2
        | Should Be Equal    ${dels}[0].subagent    code-reviewer

        Notes:
        - Delegation evidence is the already-captured ``AgentRunResult.tool_calls`` stream (per FR35 tool-call normalization) — nothing new is traced.
        - The identity-probe order is deterministic + documented; exotic adapter shapes degrade to ``subagent=""`` visibly.
        - Sibling keywords: `Subagent.Should Have Delegated To` / `Subagent.Should Not Have Delegated` (assertions over the same extraction).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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

        [Tier 1 — Deterministic] — extracts delegations from
        ``result.tool_calls`` and passes when at least one extracted record's
        ``subagent`` exactly equals (case-sensitive) ``subagent``. On failure
        raises ``SubagentDelegationAssertionError`` naming the expected
        subagent, listing the observed delegations (or stating none occurred),
        and a ``fix_suggestion``.

        | =Arguments= | =Description= |
        | ``result`` | An ``AgentRunResult`` to inspect. |
        | ``subagent`` | The subagent identity expected among the delegations. Compared case-sensitively (structured trace data, not prose). |
        | ``delegation_tool`` | Optional delegation tool-name override (default ``Task``). |

        Example:
        | `Subagent.Should Have Delegated To`    ${result}    code-reviewer

        Notes:
        - Exact-match naming is the honest choice for structured ``args`` (stricter than the skills substring heuristic); the error lists observed names so near-misses are one-glance diagnosable.
        - Sibling keywords: `Subagent.Get Delegations` (projection); `Subagent.Should Not Have Delegated` (absence assertion).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        records = extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))
        observed = observed_subagents(records)
        if subagent in observed:
            return
        if observed:
            message = f"Expected a delegation to '{subagent}', but the run delegated to: {observed}."
        else:
            message = f"Expected a delegation to '{subagent}', but no delegations were observed in the run."
        raise SubagentDelegationAssertionError(
            message,
            expected_subagent=subagent,
            observed_delegations=observed,
            fix_suggestion=(
                "Confirm the orchestrator prompt routes to this subagent, or update the expected "
                "subagent name to match the one the orchestrator actually delegates to."
            ),
        )

    @keyword(name="Subagent.Should Not Have Delegated")
    @tier(1)
    def should_not_have_delegated(
        self,
        result: AgentRunResult,
        subagent: str | None = None,
        delegation_tool: str | None = None,
    ) -> None:
        """Asserts the run did NOT delegate (optionally, to a specific subagent).

        [Tier 1 — Deterministic] — with a ``subagent`` name, fails if any
        delegation to THAT subagent occurred; without a name, fails if ANY
        delegation occurred. On failure raises
        ``SubagentDelegationAssertionError`` listing the offending
        delegation(s).

        | =Arguments= | =Description= |
        | ``result`` | An ``AgentRunResult`` to inspect. |
        | ``subagent`` | Optional targeted subagent. When omitted, the assertion fails on ANY delegation. When given, only delegations to that subagent fail it (others are ignored). |
        | ``delegation_tool`` | Optional delegation tool-name override (default ``Task``). |

        Example:
        | `Subagent.Should Not Have Delegated`    ${result}
        | `Subagent.Should Not Have Delegated`    ${result}    deployer

        Notes:
        - Targeted-absence mode ignores delegations to other subagents (only the named one fails the assertion).
        - Sibling keyword: `Subagent.Should Have Delegated To` (occurrence assertion).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        records = extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))
        observed = observed_subagents(records)
        if subagent is None:
            offending = observed
            if not offending:
                return
            message = f"Expected no delegations, but the run delegated to: {offending}."
        else:
            offending = [name for name in observed if name == subagent]
            if not offending:
                return
            message = f"Expected no delegation to '{subagent}', but the run delegated to it."
        raise SubagentDelegationAssertionError(
            message,
            expected_subagent=subagent,
            observed_delegations=observed,
            fix_suggestion=(
                "Confirm the orchestrator prompt should not route to this subagent, or relax the "
                "assertion if the delegation is expected."
            ),
        )

    @keyword(name="Subagent.Get Routing Pass At K")
    @tier(1)
    def get_routing_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
    ) -> float:
        """[Tier 1 — Deterministic] HumanEval Pass@k unbiased estimator over routing trials.

        Specialised sibling of ``Stat.Get Pass At K`` with the
        routing-decision pass-predicate HARD-CODED in. Returns ``float ∈
        [0, 1]`` — same HumanEval estimator math as ``Stat.Get Pass At K``
        (delegates to the same internal helper).

        | =Arguments= | =Description= |
        | ``runs`` | ``list[KeywordRun]`` — typically the result of ``Stat.Run N Times`` wrapping ``Subagent.Get Delegation Decision``. |
        | ``k`` | Top-k parameter. Must satisfy ``1 <= k <= len(runs)``. |

        Raises ``ValueError`` when ``k < 1``, ``k > len(runs)``, or
        ``len(runs) == 0`` (delegated to ``_compute_pass_at_k`` validation).

        Example:
        | ${pass_at_2} =    `Subagent.Get Routing Pass At K`    ${RUNS}    k=2
        | Should Be True    ${pass_at_2} >= 0.7

        Notes:
        - PRD FR27 — Pass@k unbiased estimator math reused via ``AgentEval.stats._internal._compute_pass_at_k``.
        - Pass-predicate is HARD-CODED to ``isinstance(run.result, DelegationDecision) and run.result.delegated`` (C59 lesson): the default ``Stat.Get Pass At K`` predicate (``completeness == "complete"``) silently returns ``False`` for a ``DelegationDecision`` result. Foreign result types count as a non-pass, never a crash.
        - No ``predicate`` kwarg by design (removing the customization pitfall is the point). Operators needing a custom predicate call ``Stat.Get Pass At K`` directly.
        - Sibling keyword: ``Skill.Get Activation Pass At K`` (the same C59-closure pattern for skill activation).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        from AgentEval.stats._internal import _compute_pass_at_k
        from AgentEval.subagents._internal import _routing_pass_predicate

        c = sum(1 for r in runs if _routing_pass_predicate(r))
        return _compute_pass_at_k(c, len(runs), k)

    # ------------------------------------------------------------------ #
    # Tier-2 routing probe + Tier-3 decision getter + cohort              #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Should Delegate To")
    @tier(2)
    def should_delegate_to(
        self,
        prompt: str,
        subagent: str,
        adapter: str = "generic",
        model: str | None = None,
        delegation_tool: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Runs a prompt once and asserts the orchestrator delegated to the subagent (routing probe).

        [Tier 2 — Stochastic Single-Shot] — sends ``prompt`` to the named
        adapter exactly once (constructed via the same adapter-discovery path
        `SkillsLibrary` uses), extracts delegations from the returned
        ``AgentRunResult``, and asserts ``subagent`` is among them. On no-match
        raises ``SubagentDelegationAssertionError`` carrying the prompt, the
        expected subagent, the observed delegations, the run's response text as
        reasoning, and a ``fix_suggestion``.

        | =Arguments= | =Description= |
        | ``prompt`` | Natural-language prompt to send to the orchestrator agent. |
        | ``subagent`` | The subagent expected among the delegations (case-sensitive exact match). |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``delegation_tool`` | Optional delegation tool-name override (default ``Task``). |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28. Use `Stat.Run N Times` for fan-out instead. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided.
        Adapter-dependent: the mock/default provider emits no Task calls, so
        this keyword always fails against it (same caveat as
        `Skill.Should Activate For`).

        Example (illustrative — assumes a real adapter):
        | `Subagent.Should Delegate To`    Review my PR    code-reviewer    adapter=claude_code_cli

        Notes:
        - FR28 prohibits polling — fan-out via `Stat.Run N Times` if statistical evidence is needed.
        - Mirrors the ratified `Skill.Should Activate For` idiom set (adapter/model kwargs, FR28 guard, diagnostic error with ``fix_suggestion``).
        - Sibling keywords: `Subagent.Get Delegation Decision` (returns a decision instead of raising); `Subagent.Get Routing Accuracy` (multi-task cohort).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Subagent.Should Delegate To",
                    {"prompt": prompt, "subagent": subagent, "adapter": adapter},
                )
            )
        result = self._run_adapter_once(prompt, adapter, model, kwargs)
        records = extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))
        observed = observed_subagents(records)
        if subagent in observed:
            return
        raise SubagentDelegationAssertionError(
            f"Expected the orchestrator to delegate to '{subagent}' for the prompt, but it did not.",
            prompt=prompt,
            expected_subagent=subagent,
            observed_delegations=observed,
            reasoning=result.response_text,
            fix_suggestion=(
                "Rephrase the prompt to match the subagent's description, or revise the subagent "
                "description so the orchestrator routes to it for this prompt pattern."
            ),
        )

    @keyword(name="Subagent.Get Delegation Decision")
    @tier(3)
    @guarded_fanout()
    def get_delegation_decision(
        self,
        prompt: str,
        subagent: str,
        adapter: str = "generic",
        model: str | None = None,
        delegation_tool: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> DelegationDecision:
        """Runs a prompt once and returns a routing decision (fan-out composable).

        [Tier 3 — Stochastic Fan-Out] — runs ``prompt`` via the named adapter
        once and returns a ``DelegationDecision`` with ``delegated`` (bool —
        true iff at least one delegation to ``subagent`` occurred),
        ``delegations`` (all extracted ``DelegationRecord``s), ``reasoning``
        (the response text), ``cost_usd``, and ``latency_seconds``. Does NOT
        raise on a routing miss — it reports the decision so `Stat.Run N Times`
        cohorts can aggregate it (feed the runs into
        `Subagent.Get Routing Pass At K`).

        | =Arguments= | =Description= |
        | ``prompt`` | Prompt text to send to the orchestrator agent. |
        | ``subagent`` | The subagent whose delegation sets ``delegated=True``. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``delegation_tool`` | Optional delegation tool-name override (default ``Task``). |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided.
        Adapter-dependent: the mock/default provider emits no Task calls, so
        ``delegated`` is always ``False`` against it.

        Example (illustrative — assumes a real adapter):
        | ${decision} =    `Subagent.Get Delegation Decision`    Review my PR    code-reviewer    adapter=claude_code_cli
        | Should Be True    ${decision.delegated}

        Notes:
        - FR28 prohibits polling — use `Stat.Run N Times` for fan-out.
        - Mirrors `Skill.Get Activation Decision` (the ``Stat.Run N Times``-composable Tier-3 getter).
        - Sibling keywords: `Subagent.Should Delegate To` (assertion wrapper); `Subagent.Get Routing Pass At K` (Pass@k over these decisions).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Subagent.Get Delegation Decision",
                    {"prompt": prompt, "subagent": subagent, "adapter": adapter},
                )
            )
        result = self._run_adapter_once(prompt, adapter, model, kwargs)
        records = extract_delegations(result.tool_calls, _delegation_tools_arg(delegation_tool))
        delegated = subagent in observed_subagents(records)
        return DelegationDecision(
            delegated=delegated,
            delegations=tuple(records),
            reasoning=result.response_text,
            cost_usd=result.cost_usd,
            latency_seconds=result.latency_seconds,
        )

    @keyword(name="Subagent.Get Routing Accuracy")
    @tier(3)
    @guarded_fanout()
    def get_routing_accuracy(
        self,
        tasks: str | Path,
        adapter: str = "generic",
        model: str | None = None,
        trials_per_task: int = 3,
        delegation_tool: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> SubagentRoutingResult:
        """Runs a routing-tasks cohort and reports per-task + aggregate routing accuracy.

        [Tier 3 — Stochastic Fan-Out] — loads a routing-tasks YAML
        (``tasks: [{id, prompt, expected_subagent}]``), runs
        ``trials_per_task`` adapter calls per task, and returns a
        ``SubagentRoutingResult`` with per-task results (id, expected subagent,
        trials, matches, per-task Pass@k) and a summary including
        ``routing_accuracy`` (fraction of ALL trials whose delegations included
        that task's expected subagent).

        | =Arguments= | =Description= |
        | ``tasks`` | Filesystem path to the routing-tasks YAML. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``trials_per_task`` | Number of adapter calls per task. Defaults to ``3``. |
        | ``delegation_tool`` | Optional delegation tool-name override (default ``Task``). |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided.
        Raises ``ValueError`` when ``trials_per_task < 1``. Raises
        ``InvalidSubagentRoutingTasksError`` when the tasks YAML is
        structurally invalid. Adapter-dependent (mock provider emits no Task
        calls).

        Example (illustrative — assumes a real adapter):
        | ${routing} =    `Subagent.Get Routing Accuracy`    ${CURDIR}/tasks/routing.yaml    adapter=claude_code_cli
        | Should Be True    ${routing.summary.routing_accuracy} >= 0.6

        Notes:
        - FR28 prohibits polling — the cohort fans out via its own ``trials_per_task``.
        - Mirrors `Skill.Get Discoverability` (the tasks-YAML cohort getter); budget-guarded via ``@guarded_fanout()`` (``max_cost_usd`` / runtime caps).
        - Sibling keyword: `Subagent.Get Delegation Decision` (single-task variant).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Subagent.Get Routing Accuracy",
                    {"tasks": str(tasks), "adapter": adapter},
                )
            )
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1, got {trials_per_task}")

        import time

        from AgentEval.subagents._tasks import load_subagent_routing_tasks

        task_list = load_subagent_routing_tasks(tasks)
        tool_arg = _delegation_tools_arg(delegation_tool)
        t_start = time.perf_counter()

        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model

        per_task_results: list[SubagentRoutingTaskResult] = []
        total_trials = 0
        total_matches = 0
        total_cost = 0.0
        for task in task_list:
            matches = 0
            trial_costs: list[float] = []
            for _ in range(trials_per_task):
                adapter_instance = adapter_cls(**ctor_kwargs)
                run_result = adapter_instance.run(task.prompt)
                records = extract_delegations(run_result.tool_calls, tool_arg)
                if task.expected_subagent in observed_subagents(records):
                    matches += 1
                trial_costs.append(run_result.cost_usd)
            pass_at_k = matches / trials_per_task if trials_per_task > 0 else 0.0
            cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
            per_task_results.append(
                SubagentRoutingTaskResult(
                    task_id=task.id,
                    prompt=task.prompt,
                    expected_subagent=task.expected_subagent,
                    trials_run=trials_per_task,
                    matches_observed=matches,
                    pass_at_k=pass_at_k,
                    cost_per_trial_usd=cost_per_trial,
                )
            )
            total_trials += trials_per_task
            total_matches += matches
            total_cost += sum(trial_costs)

        routing_accuracy = total_matches / total_trials if total_trials > 0 else 0.0
        summary = SubagentRoutingSummary(
            routing_accuracy=routing_accuracy,
            total_trials=total_trials,
            total_matches=total_matches,
            total_cost_usd=total_cost,
            total_runtime_seconds=time.perf_counter() - t_start,
        )
        return SubagentRoutingResult(per_task_results=tuple(per_task_results), summary=summary)

    # ------------------------------------------------------------------ #
    # Tier-1 config-drift static checks                                   #
    # ------------------------------------------------------------------ #

    @keyword(name="Subagent.Should Declare Skills")
    @tier(1)
    def should_declare_skills(self, path: str | Path, *skills: str) -> None:
        """Asserts a subagent frontmatter explicitly declares every named skill.

        [Tier 1 — Deterministic] — parses the subagent ``.md`` and passes only
        when its frontmatter contains an explicit ``skills:`` list including
        every named skill. Because subagents do NOT inherit the parent agent's
        skills, an absent or empty ``skills:`` field FAILS the assertion (never
        vacuously passes). On failure raises ``SubagentConfigDriftError``
        naming the missing skill(s); an unparseable file propagates
        ``InvalidSubagentDefinitionError``.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the sub-agent ``.md`` file. |
        | ``*skills`` | One or more skill names that MUST appear in the frontmatter ``skills:`` list. |

        Example:
        | `Subagent.Should Declare Skills`    ${CURDIR}/agents/researcher.md    pdf-tools    web-search

        Notes:
        - Static (lint/CI) check — it deliberately does NOT run an agent to verify the skill loads; that composes via the Tier-2/3 keywords.
        - Distinct from `Subagent.Get Frontmatter`'s parse error: a file that parses fine but omits ``skills:`` raises ``SubagentConfigDriftError`` (a test failure), not ``InvalidSubagentDefinitionError`` (a setup failure).
        - Sibling keyword: `Subagent.Tools Should Be Subset Of` (the tools-allowlist config-drift check).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if not skills:
            raise ValueError(
                "Subagent.Should Declare Skills requires one or more expected skill names; "
                "calling it with none would vacuously pass and certify nothing."
            )
        frontmatter = self.get_frontmatter(path)
        declared_raw = frontmatter.get("skills")
        declared = declared_raw if isinstance(declared_raw, list) else []
        if not declared:
            raise SubagentConfigDriftError(
                "Subagent frontmatter declares no skills, but subagents do not inherit parent skills.",
                file_path=str(path),
                offending=list(skills),
                fix_suggestion=(
                    "Add an explicit `skills:` list to the subagent frontmatter preloading every "
                    "skill it needs — subagents do NOT inherit the parent agent's skills."
                ),
            )
        missing = [s for s in skills if s not in declared]
        if missing:
            raise SubagentConfigDriftError(
                f"Subagent frontmatter is missing required skill(s): {missing}.",
                file_path=str(path),
                offending=missing,
                fix_suggestion=(
                    "Add the missing skill(s) to the subagent's `skills:` frontmatter list — "
                    "skills must be explicitly preloaded because subagents do not inherit them."
                ),
            )

    @keyword(name="Subagent.Tools Should Be Subset Of")
    @tier(1)
    def tools_should_be_subset_of(self, path: str | Path, *allowlist: str) -> None:
        """Asserts a subagent's declared tools are all within an allowlist (fail-loud on absent tools).

        [Tier 1 — Deterministic] — parses the subagent ``.md`` and passes only
        when its frontmatter declares a ``tools:`` list whose every entry is in
        ``allowlist``. Because an absent ``tools`` field grants the subagent the
        FULL parent tool set, a missing or empty ``tools:`` field FAILS the
        assertion (never vacuously passes). On failure raises
        ``SubagentConfigDriftError`` listing the offending tools (or the absent
        declaration); an unparseable file propagates
        ``InvalidSubagentDefinitionError``.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the sub-agent ``.md`` file. |
        | ``*allowlist`` | The permitted tool names. Every declared ``tools:`` entry must be one of these. |

        Example:
        | `Subagent.Tools Should Be Subset Of`    ${CURDIR}/agents/reviewer.md    Read    Grep    Bash

        Notes:
        - Fail-loud inherit-everything default (per `feedback_honest_framing`): silently passing the least-constrained config (no ``tools:`` = inherit all) is the worst outcome, so it fails.
        - Sibling keyword: `Subagent.Should Declare Skills` (the skills config-drift check).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        frontmatter = self.get_frontmatter(path)
        declared_raw = frontmatter.get("tools")
        declared = declared_raw if isinstance(declared_raw, list) else []
        if not declared:
            raise SubagentConfigDriftError(
                "Subagent frontmatter declares no `tools:` — omitting it inherits the full parent tool set.",
                file_path=str(path),
                offending=[],
                fix_suggestion=(
                    "Declare an explicit `tools:` list in the subagent frontmatter — omitting it "
                    "grants the subagent the full parent tool set (inherit-everything)."
                ),
            )
        offending = [t for t in declared if t not in allowlist]
        if offending:
            raise SubagentConfigDriftError(
                f"Subagent declares tool(s) outside the allowlist: {offending}.",
                file_path=str(path),
                offending=offending,
                fix_suggestion=(
                    f"Remove the offending tool(s) from the subagent's `tools:` list, or add them to "
                    f"the asserted allowlist {list(allowlist)!r} if they are intended."
                ),
            )

    # ------------------------------------------------------------------ #
    # Shared adapter-run helper (Tier-2/3)                                #
    # ------------------------------------------------------------------ #

    def _run_adapter_once(
        self,
        prompt: str,
        adapter: str,
        model: str | None,
        extra_kwargs: dict[str, Any],
    ) -> AgentRunResult:
        """Resolve + construct the named adapter and run ``prompt`` exactly once.

        Mirrors the adapter-discovery path `SkillsLibrary` uses: ``model`` is
        added to the constructor kwargs (never the ``run()`` kwargs) and
        ``extra_kwargs`` are forwarded to the adapter constructor.
        """
        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(extra_kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        adapter_instance = adapter_cls(**ctor_kwargs)
        return adapter_instance.run(prompt)
