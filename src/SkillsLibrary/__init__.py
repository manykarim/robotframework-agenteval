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

"""Test Agent Skills - parse frontmatter, check activation, score discoverability.

Three modes, honestly labelled:

- *Tier 1* getters and the frontmatter validator read the skill ``.md`` file and
  never touch a model.
- *Tier 2* judge-based activation asks the shared LLM judge whether a response
  actually applied the skill's guidance - the honest LLM check.
- *Tier 3* agent-mode keywords drive a real coding agent and read back whether
  the skill fired, one shot or over a pass@k cohort.

Import it on its own::

    *** Settings ***
    Library    SkillsLibrary

Every keyword carries the ``Skill.`` prefix, so no ``WITH NAME`` is needed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._core import Adapter, AgentRunResult, SkillDidNotActivateError, judge, stats, tier
from SkillsLibrary._agent_bridge import load_capabilities_from_dir, skill_to_capability
from SkillsLibrary._internal import (
    activation_pass_predicate,
    load_skill_discoverability_tasks,
    resolve_skill_adapter,
    run_skill_discoverability,
    skill_activated_in,
)
from SkillsLibrary._parser import parse_frontmatter, validate_frontmatter_structure
from SkillsLibrary._types import (
    ActivationDecision,
    ActivationPassAtK,
    JudgeActivationDecision,
    SkillDiscoverabilityResult,
)

__all__ = ["SkillsLibrary"]


class SkillsLibrary:
    """Parse skill frontmatter, check activation, and score discoverability."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    # ------------------------------------------------------------------ #
    # Tier 1 - deterministic frontmatter getters + validator.            #
    # ------------------------------------------------------------------ #

    @keyword(name="Skill.Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parse a skill ``.md`` file's YAML frontmatter into a dict.

        Returns the raw parsed mapping. Use `Skill.Should Be Valid Frontmatter`
        or the typed getters if you need the required-field contract enforced.

        Example:
        | ${fm}=    Skill.Get Frontmatter    ${CURDIR}/skills/example.md
        | Should Be Equal    ${fm}[name]    example-skill
        """
        return parse_frontmatter(path)

    @keyword(name="Skill.Get Description")
    @tier(1)
    def get_description(self, path: str | Path) -> str:
        """Return the ``description`` field from a skill ``.md`` file.

        Fails loud if the frontmatter is invalid or ``description`` is missing.

        Example:
        | ${desc}=    Skill.Get Description    ${CURDIR}/skills/web-search.md
        | Should Contain    ${desc}    search
        """
        return str(self._read_and_validate(path)["description"])

    @keyword(name="Skill.Get Allowed Tools")
    @tier(1)
    def get_allowed_tools(self, path: str | Path) -> list[str]:
        """Return the ``allowed-tools`` list from a skill ``.md`` file.

        Optional field: a skill that omits it (or leaves it empty) is still
        valid and yields an empty list.

        Example:
        | ${tools}=    Skill.Get Allowed Tools    ${CURDIR}/skills/web-search.md
        | Should Contain    ${tools}    Read
        """
        return list(self._read_and_validate(path).get("allowed-tools", []))

    @keyword(name="Skill.Get Disable Model Invocation")
    @tier(1)
    def get_disable_model_invocation(self, path: str | Path) -> bool:
        """Return the ``disable-model-invocation`` bool from a skill ``.md`` file.

        Optional field, defaulting to ``False`` when absent. Strict bool typing
        when present: unquoted YAML ``true``/``false`` are accepted; ``1``/``0``
        and quoted strings are rejected.

        Example:
        | ${off}=    Skill.Get Disable Model Invocation    ${CURDIR}/skills/web-search.md
        | Should Be Equal    ${off}    ${False}
        """
        return bool(self._read_and_validate(path).get("disable-model-invocation", False))

    @keyword(name="Skill.Should Be Valid Frontmatter")
    @tier(1)
    def should_be_valid_frontmatter(self, frontmatter: dict[str, Any]) -> None:
        """Assert a parsed frontmatter dict is a valid skill.

        Required: ``name`` (str) and ``description`` (str). Optional but
        type-checked when present: ``allowed-tools`` (list of str),
        ``disable-model-invocation`` (bool). Raises naming the offending field.

        Example:
        | ${fm}=    Skill.Get Frontmatter    ${CURDIR}/skills/example.md
        | Skill.Should Be Valid Frontmatter    ${fm}
        """
        validate_frontmatter_structure(frontmatter)

    def _read_and_validate(self, path: str | Path) -> dict[str, Any]:
        """Parse and structurally validate a skill file in one pass."""
        frontmatter = parse_frontmatter(path)
        validate_frontmatter_structure(frontmatter, file_path=str(path))
        return frontmatter

    def _skill_name(self, path: str | Path) -> str:
        """Read the skill's ``name`` field, or ``""`` if absent or non-string."""
        name_raw = parse_frontmatter(path).get("name")
        return name_raw if isinstance(name_raw, str) else ""

    # ------------------------------------------------------------------ #
    # Tier 2 - LLM-judge activation (the honest LLM mode).               #
    # ------------------------------------------------------------------ #

    @keyword(name="Skill.Get Judge Activation Decision")
    @tier(2)
    def get_judge_activation_decision(
        self,
        response: str,
        skill: str | Path,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        threshold: float = 7.0,
        **kwargs: Any,
    ) -> JudgeActivationDecision:
        """Ask the LLM judge whether a response actually applied the skill's guidance.

        Unlike the Tier-3 substring heuristic, this reads the response for
        *meaning*: the judge scores how well ``response`` reflects the skill's
        description and passes when the score clears ``threshold`` (out of 10).
        Returns a decision with the judge's justification.

        Example:
        | ${d}=    Skill.Get Judge Activation Decision    ${response}    ${CURDIR}/skills/web-search.md
        | Should Be True    ${d.activated}
        """
        fm = self._read_and_validate(skill)
        name = str(fm["name"])
        description = str(fm["description"])
        rubric = judge.rubric_from_criteria(
            f"The response applies the guidance of the '{name}' skill. Skill guidance: {description}",
            threshold=threshold,
        )
        result = judge.score(response, rubric, adapter=adapter, model=model, **kwargs)
        return JudgeActivationDecision(
            activated=result.pass_threshold_met,
            justification=result.reasoning,
            numeric_score=result.numeric_score,
            cost_usd=result.cost_usd,
        )

    # ------------------------------------------------------------------ #
    # Tier 3 - agent-mode activation (drives a real coding agent).       #
    # ------------------------------------------------------------------ #

    @keyword(name="Skill.Get Activation Decision")
    @tier(3)
    def get_activation_decision(
        self,
        skill: str | Path,
        prompt: str,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        **kwargs: Any,
    ) -> ActivationDecision:
        """Drive an agent with ``prompt`` and report whether the skill activated.

        Activation is the shared substring heuristic: the skill's ``name`` appears
        (case-insensitively) in the agent response. Returns the decision plus the
        response text, cost, and latency.

        Example:
        | ${d}=    Skill.Get Activation Decision    ${CURDIR}/skills/web-search.md    Find recent Robot Framework news
        | Should Be True    ${d.activated}
        """
        skill_name = self._skill_name(skill)
        adapter_obj = resolve_skill_adapter(adapter, model, kwargs)
        result = adapter_obj.run(prompt)
        return ActivationDecision(
            activated=skill_activated_in(skill_name, result.response_text),
            reasoning=result.response_text,
            cost_usd=result.cost_usd,
            latency_seconds=result.latency_seconds,
        )

    @keyword(name="Skill.Should Activate For")
    @tier(3)
    def should_activate_for(
        self,
        prompt: str,
        skill: str | Path,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Assert that the skill activates for ``prompt``; raise if it does not.

        Drives the agent once (same heuristic as `Skill.Get Activation Decision`)
        and raises ``SkillDidNotActivateError`` when the skill stays quiet.

        Example:
        | Skill.Should Activate For    Find news about Robot Framework    ${CURDIR}/skills/web-search.md
        """
        skill_name = self._skill_name(skill)
        decision = self.get_activation_decision(skill, prompt, adapter=adapter, model=model, **kwargs)
        if not decision.activated:
            raise SkillDidNotActivateError(
                f"Skill {skill_name!r} did not activate for prompt {prompt!r}. "
                f"Response: {decision.reasoning!r}. "
                "Rephrase the prompt to match the skill description, or revise the "
                "description to better match this prompt pattern."
            )

    @keyword(name="Skill.Get Discoverability")
    @tier(3)
    def get_discoverability(
        self,
        skill: str | Path,
        tasks: str | Path,
        adapter: str | Adapter = "generic",
        model: str | None = None,
        trials_per_task: int = 3,
        **kwargs: Any,
    ) -> SkillDiscoverabilityResult:
        """Score how well a skill's description surfaces it across a task set.

        Runs every task in the ``tasks`` YAML ``trials_per_task`` times, then
        reports per-task activation rates and an aggregate summary (accuracy,
        false-activation rate, missed-activation rate).

        Example:
        | ${d}=    Skill.Get Discoverability    ${CURDIR}/skills/web-search.md    ${CURDIR}/tasks.yaml
        | Should Be True    ${d.summary.activation_accuracy} >= 0.6
        """
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        skill_name = self._skill_name(skill)
        task_list = load_skill_discoverability_tasks(tasks)
        return run_skill_discoverability(
            skill_name=skill_name,
            task_list=task_list,
            adapter=adapter,
            model=model,
            trials_per_task=trials_per_task,
            extra_adapter_kwargs=dict(kwargs),
            t_start=time.perf_counter(),
        )

    # ------------------------------------------------------------------ #
    # Tier 1 - pass@k over already-collected activation trials.          #
    # ------------------------------------------------------------------ #

    @keyword(name="Skill.Get Activation Pass At K")
    @tier(1)
    def get_activation_pass_at_k(self, runs: list[stats.KeywordRun], k: int) -> ActivationPassAtK:
        """Estimate activation pass@k over trials, with a Wilson confidence band.

        Feed the ``runs`` from ``Stat.Run N Times`` wrapping
        `Skill.Get Activation Decision`. A trial counts as a success when its
        result is an activated ``ActivationDecision``. Pure estimator math over
        pre-collected runs - no model call - so this stays Tier 1.

        Example:
        | ${runs}=    Stat.Run N Times    10    Skill.Get Activation Decision    ${skill}    ${prompt}
        | ${p}=    Skill.Get Activation Pass At K    ${runs}    k=5
        | Should Be True    ${p.pass_at_k} >= 0.7
        """
        successes = sum(1 for r in runs if activation_pass_predicate(r))
        trials = len(runs)
        estimate = stats.pass_at_k(runs, k, predicate=activation_pass_predicate)
        interval = stats.wilson_interval(successes, trials)
        return ActivationPassAtK(
            pass_at_k=estimate,
            confidence_interval=interval,
            successes=successes,
            trials=trials,
            k=k,
        )

    # ------------------------------------------------------------------ #
    # Tier 1 - in-process agent bridge (SKILL.md <-> pydantic-ai).        #
    # ------------------------------------------------------------------ #

    @keyword(name="Skill.As Capability")
    @tier(1)
    def as_capability(self, skill: str | Path) -> Any:
        """Load a Claude-style ``SKILL.md`` into a deferred pydantic-ai ``Capability``.

        Reuses this library's frontmatter parser to map name->id,
        description->description, body->instructions, ``defer_loading=True``.
        Hand the result to ``get_adapter("in-process", capabilities=[...])`` and
        read back activations with `Skill.Get Activated Skills`.

        VALIDATION CEILING: ``allowed-tools`` / ``disable-model-invocation`` are
        NOT enforced - pydantic-ai capabilities have no equivalent, so this is a
        discoverability proxy, not a Claude tool-permission sandbox. Needs the
        ``[agent]`` extra (pydantic-ai).

        Example:
        | ${cap}=    Skill.As Capability    ${CURDIR}/skills/web-search.md
        | ${agent}=    Evaluate    AgentEval.get_adapter('in-process', capabilities=[$cap])
        """
        return skill_to_capability(skill)

    @keyword(name="Skill.Load Capabilities From Dir")
    @tier(1)
    def load_capabilities_from_dir(self, directory: str | Path, pattern: str = "*.md") -> list[Any]:
        """Load every skill ``.md`` under ``directory`` into deferred ``Capability`` objects.

        Globs ``directory`` (non-recursively) in sorted order and maps each file
        through `Skill.As Capability`. Returns the list ready for
        ``get_adapter("in-process", capabilities=[...])``. Same validation
        ceiling as `Skill.As Capability`; needs the ``[agent]`` extra.

        Example:
        | ${caps}=    Skill.Load Capabilities From Dir    ${CURDIR}/skills
        | ${agent}=    Evaluate    AgentEval.get_adapter('in-process', capabilities=$caps)
        """
        return load_capabilities_from_dir(directory, pattern=pattern)

    @keyword(name="Skill.Get Activated Skills")
    @tier(1)
    def get_activated_skills(self, result: AgentRunResult) -> list[str]:
        """Return the skill ids the model activated during an in-process agent run.

        Reads ``result.tool_calls`` for the framework ``load_capability`` tool
        calls and collects each call's ``args["id"]`` in call order (deduplicated,
        first occurrence wins). A pure Tier-1 reader over an already-collected
        ``AgentRunResult`` - no model call. Ids missing or non-string args are
        skipped.

        Example:
        | ${cap}=    Skill.As Capability    ${CURDIR}/skills/refunds.md
        | ${agent}=    Evaluate    AgentEval.get_adapter('in-process', capabilities=[$cap])
        | ${r}=    Evaluate    $agent.run("Is order #4821 refundable?")
        | ${activated}=    Skill.Get Activated Skills    ${r}
        | Should Contain    ${activated}    refunds
        """
        activated: list[str] = []
        for call in result.tool_calls:
            if call.name != "load_capability":
                continue
            skill_id = call.args.get("id")
            if isinstance(skill_id, str) and skill_id and skill_id not in activated:
                activated.append(skill_id)
        return activated
