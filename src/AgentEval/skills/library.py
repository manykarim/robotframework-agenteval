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
# Browser-Library-style docstring tables can carry long descriptions
# on a single physical line. Per-line 120-char limit waived for this
# file per Phase 6 docstring-refresh proposal (2026-05-26).

"""Skill sub-library — static-inspection keywords for skill `.md` files.

Story 2.1 ships 5 Tier-1 keywords (per architecture L620 Decision-1 +
PRD FR1 + epics.md Epic 2 Story 2.1):

- `Get Frontmatter` — parse a skill `.md`'s YAML frontmatter into a dict.
- `Get Description` — return the `description` field.
- `Get Allowed Tools` — return the `allowed-tools` list.
- `Get Disable Model Invocation` — return the `disable-model-invocation` bool.
- `Should Be Valid Frontmatter` — structural validator (Phase-1 plain
  `@keyword`; full AssertionEngine matcher deferred to Phase-2 per
  ADR-022 catalog row).

Every method is `@tier(1)`-annotated (deterministic, ≤50 ms per call on
typical 5 KB inputs per NFR-PERF-02). Tier-1 keywords do NOT touch the
provider, the trace store, or external services; they read the local
`.md` file + parse YAML only.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval.skills.library    WITH NAME    Skill

    *** Test Cases ***
    Skill File Has Correct Description
        ${desc}=    Skill.Get Description    skills/example.md
        Should Be Equal    ${desc}    Example skill for testing.

**NOTE (per Phase 6 review):** unlike other AgentEval sub-libraries,
`SkillsLibrary` is NOT registered in `_SUB_LIBRARIES` and is NOT
composed under the top-level `AgentEval` library (DF-7.1-S1 / name
collision with `SubagentsLibrary.Get Frontmatter`). All 8 keywords
must be imported via the direct path shown in the Usage block above.

Phase-1 limitations explicitly documented:
- `Should Be Valid Frontmatter` is a plain `@keyword`-decorated function,
  NOT a `robotframework-assertion-engine` matcher. The Phase-1 manual-
  validation contract is load-bearing; Phase-2 (ADR-022 adoption) re-
  wires it with the full operator-chain idiom.
- The verb allowlist (`tests/unit/conventions/test_keyword_name_idiom.py`
  `_VERB_ALLOWLIST`) is extended with `"should"` per Story 1b.6 Dev
  Notes growth policy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.tier import tier
from AgentEval._kernel.tier_acl import build_polling_disallowed_message
from AgentEval.errors import PollingDisallowedError, SkillDidNotActivateError
from AgentEval.skills._internal import load_skill_discoverability_tasks
from AgentEval.skills._parser import parse_frontmatter, validate_frontmatter_structure
from AgentEval.skills.types import (
    ActivationDecision,
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillTaskResult,
)

__all__ = ["SkillsLibrary"]

# Browser-Library-style docstring migration marker (Phase 6, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


class SkillsLibrary:
    """Static-inspection keywords for skill `.md` files [Tier 1 — Deterministic].

    All 5 public methods are `@keyword`-decorated + `@tier(1)`-annotated
    per Story 1b.6 conventions. The class holds no mutable state; each
    call re-parses the target file so the keywords are stateless +
    parallel-safe under `pabot --processes N`.
    """

    @keyword(name="Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parses the YAML frontmatter at the head of a skill ``.md`` file (PRD FR1).

        [Tier 1 — Deterministic] — pure file-read + YAML parse; no
        provider, no trace store. Returns the raw parsed YAML as a
        ``dict[str, Any]``. Does NOT enforce the required-fields
        contract — see `Should Be Valid Frontmatter` for structural
        validation, OR the typed getters (`Get Description`,
        `Get Allowed Tools`, etc.) which validate during projection.
        Median ≤ 50 ms per call on the 5 KB reference fixture.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` on YAML / file-level
        structural failure (missing file, broken YAML, missing ``---``
        delimiters, frontmatter not a mapping). Error format per FR59 +
        `docs/contracts/error-class-hierarchy.md` L96-104.

        Example:
        | ${frontmatter} =    `Get Frontmatter`    ${CURDIR}/skills/example.md
        | Should Be Equal    ${frontmatter}[name]    example-skill
        | Should Contain    ${frontmatter}[allowed-tools]    Bash

        Notes:
        - PRD FR1 ratifies the YAML frontmatter parse + dict-return contract.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation` (typed-validated projections); `Should Be Valid Frontmatter` (structural validator).
        - Parallel surface: `SubagentsLibrary.Get Frontmatter` for sub-agent ``.md`` files (different validation rules).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return parse_frontmatter(path)

    @keyword(name="Get Description")
    @tier(1)
    def get_description(self, path: str | Path) -> str:
        """Returns the ``description`` field from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a ``description``-field non-empty-string check.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR the ``description`` field is missing / non-string /
        empty.

        Example:
        | ${desc} =    `Get Description`    ${CURDIR}/skills/example.md
        | Should Contain    ${desc}    example skill
        | Should Be True    len('${desc}') > 0

        Notes:
        - PRD FR1 ratifies the description-field projection contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Frontmatter` (raw dict); `Should Be Valid Frontmatter` (all-fields validator).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return str(self._read_and_validate(path)["description"])

    @keyword(name="Get Allowed Tools")
    @tier(1)
    def get_allowed_tools(self, path: str | Path) -> list[str]:
        """Returns the ``allowed-tools`` list from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a ``list[str]`` type check. The list MAY be empty (a skill
        with no tool allowlist is valid).

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR ``allowed-tools`` is not a list of strings.

        Example:
        | @{tools} =    `Get Allowed Tools`    ${CURDIR}/skills/example.md
        | Should Contain    ${tools}    Bash
        | Should Contain    ${tools}    Read
        | Length Should Be    ${tools}    3

        Notes:
        - PRD FR1 ratifies the allowed-tools projection contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Frontmatter` (raw dict); `Get Disable Model Invocation` (companion projection).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return list(self._read_and_validate(path)["allowed-tools"])

    @keyword(name="Get Disable Model Invocation")
    @tier(1)
    def get_disable_model_invocation(self, path: str | Path) -> bool:
        """Returns the ``disable-model-invocation`` bool from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a strict bool type check. YAML coercion rules:

        - ``true``/``false``/``yes``/``no``/``on``/``off`` parse to Python
          bool (PyYAML 1.1 semantics) — accepted.
        - ``1``/``0`` integers parse to Python int — **rejected**
          (``isinstance(value, bool)`` is False for ints).
        - String forms like ``"true"`` are **rejected** — must be unquoted.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR ``disable-model-invocation`` is not a bool.

        Example:
        | ${disabled} =    `Get Disable Model Invocation`    ${CURDIR}/skills/example.md
        | Should Be Equal    ${disabled}    ${FALSE}                                      # Default for most skills.
        | ${disabled} =    `Get Disable Model Invocation`    ${CURDIR}/skills/static-only.md
        | Should Be Equal    ${disabled}    ${TRUE}

        Notes:
        - PRD FR1 ratifies the disable-model-invocation projection contract.
        - Strict bool typing — int / string forms rejected. The PyYAML 1.1 coercion of unquoted ``true``/``yes`` etc. to Python bool IS accepted.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keyword: `Get Allowed Tools` (companion projection).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return bool(self._read_and_validate(path)["disable-model-invocation"])

    def _read_and_validate(self, path: str | Path) -> dict[str, Any]:
        """Parse + structurally-validate a skill `.md` file once per call.

        Internal helper that consolidates the parse + validate steps
        shared by `Get Description` / `Get Allowed Tools` / `Get
        Disable Model Invocation`. Story 2.1 code-review B2 fix: the
        earlier per-keyword `parse_frontmatter` + `validate_frontmatter_structure`
        call pair iterated `REQUIRED_FIELDS` once per call; this
        helper makes the cost one read + one parse + one validation
        sweep per public-keyword invocation, matching the NFR-PERF-02
        budget framing.

        Tier-1 callers that need ALL fields should call `Get Frontmatter`
        once + `Should Be Valid Frontmatter` on the result; chained
        per-field getters each incur ONE I/O + parse cycle (cache-free
        by design — `SkillsLibrary` is stateless under `pabot --processes N`).
        """
        frontmatter = parse_frontmatter(path)
        validate_frontmatter_structure(frontmatter, file_path=str(path))
        return frontmatter

    @keyword(name="Should Be Valid Frontmatter")
    @tier(1)
    def should_be_valid_frontmatter(self, frontmatter: dict[str, Any]) -> None:
        """Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).

        [Tier 1 — Deterministic] — structural validator. Required fields:
        ``name`` (str), ``description`` (str), ``allowed-tools``
        (``list[str]``), ``disable-model-invocation`` (bool). Phase-1
        plain ``@keyword`` per ADR-019 catalog row; full AssertionEngine
        matcher deferred to Phase-2.

        | =Arguments= | =Description= |
        | ``frontmatter`` | The dict returned by `Get Frontmatter`. |

        Raises ``InvalidSkillFrontmatterError`` when any required field
        is missing OR has the wrong type. The error message lists the
        offending field(s) so the test author can remediate. Error
        format per FR59 + `docs/contracts/error-class-hierarchy.md`
        L96-104.

        Example:
        | ${frontmatter} =    `Get Frontmatter`    ${CURDIR}/skills/example.md
        | `Should Be Valid Frontmatter`    ${frontmatter}
        | ${fm_broken} =    Create Dictionary    name=just-a-name
        | Run Keyword And Expect Error    InvalidSkillFrontmatterError*    `Should Be Valid Frontmatter`    ${fm_broken}

        Notes:
        - PRD FR1 ratifies the required-fields contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - ADR-019 ratifies the Phase-1 plain-``@keyword`` form; Phase-2 will adopt the AssertionEngine matcher idiom.
        - Sibling keyword: `Get Frontmatter` (raw dict — feed its return into this validator).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        validate_frontmatter_structure(frontmatter)

    @keyword(name="Get Activation Decision")
    @tier(3)
    @guarded_fanout()
    def get_activation_decision(
        self,
        skill: str | Path,
        prompt: str,
        adapter: str = "generic",
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> ActivationDecision:
        """Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).

        [Tier 3 — Stochastic Fan-Out] — sends ``prompt`` to the named
        adapter and returns an ``ActivationDecision`` with ``activated``
        (bool), ``reasoning`` (the response text), ``cost_usd``, and
        ``latency_seconds``. Phase-1 activation heuristic: case-
        insensitive substring check of the skill's ``name`` field in
        ``result.response_text``. Phase-2 will adopt a more robust
        classifier (DF-7.1-S1 / C55).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |
        | ``prompt`` | Prompt text to send to the agent. |
        | ``adapter`` | Adapter identifier registered via the ``agenteval.coding_agents`` entry-points group. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.1.5. Use `Stat.Run N Times` for fan-out instead. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``InvalidSkillFrontmatterError`` when the skill
        file cannot be read or parsed as valid YAML. Structurally
        invalid frontmatter (missing required fields) does NOT raise
        here — missing ``name`` silently yields ``activated=False``.

        Example (illustrative — assumes a real adapter):
        | ${decision} =    `Get Activation Decision`    ${CURDIR}/skills/web-search.md    prompt=Find news about Robot Framework
        | Should Be True    ${decision.activated}
        | Should Be True    ${decision.cost_usd} >= 0.0

        Notes:
        - PRD FR1 ratifies the skill-activation surface; AC-7.1 ratifies the keyword contract.
        - Phase-1 heuristic per AC-7.1.4 — substring check on skill ``name`` in response text. Phase-2 classifier deferred per DF-7.1-S1 / C55.
        - FR28 prohibits polling — use `Stat.Run N Times` for statistical assertions instead.
        - Sibling keyword: `Should Activate For` (assertion wrapper); `Get Discoverability` (multi-task cohort evaluation).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Get Activation Decision",
                    {"skill": str(skill), "prompt": prompt, "adapter": adapter},
                )
            )
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""
        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        adapter_instance = adapter_cls(**ctor_kwargs)
        result = adapter_instance.run(prompt)
        activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
        return ActivationDecision(
            activated=activated,
            reasoning=result.response_text,
            cost_usd=result.cost_usd,
            latency_seconds=result.latency_seconds,
        )

    @keyword(name="Get Discoverability")
    @tier(3)
    @guarded_fanout()
    def get_discoverability(
        self,
        skill: str | Path,
        tasks: str | Path,
        adapter: str = "generic",
        model: str | None = None,
        trials_per_task: int = 3,
        polling: float | None = None,
        **kwargs: Any,
    ) -> SkillDiscoverabilityResult:
        """Runs a cohort discoverability evaluation across N tasks × M trials (PRD FR4b).

        [Tier 3 — Stochastic Fan-Out] — runs ``trials_per_task`` adapter
        calls per task across all tasks in the YAML, returning a
        ``SkillDiscoverabilityResult`` with ``per_task_results``,
        ``summary``, and ``adapter_coverage``. Phase-1 activation
        heuristic per AC-7.2.4: case-insensitive substring check of the
        skill ``name`` field in each trial's ``response_text``. Phase-2
        adds structured-response schema for competing-skills-picked
        detection (DF-7.2-S1 / C56).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``trials_per_task`` | Number of adapter calls per task. Defaults to ``3``. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.2.6. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``ValueError`` when ``trials_per_task < 1``.
        Raises ``InvalidSkillFrontmatterError`` when the skill file is
        unreadable / un-parseable. Raises
        ``InvalidSkillDiscoverabilityTasksError`` when the tasks YAML
        is structurally invalid.

        Example (illustrative — assumes a real adapter):
        | ${disc} =    `Get Discoverability`    ${CURDIR}/skills/web-search.md    ${CURDIR}/tasks/web-search.yaml    trials_per_task=5
        | Should Be True    ${disc.summary.activation_accuracy} >= 0.6
        | FOR    ${task_result}    IN    @{disc.per_task_results}
        |     Log    ${task_result.task_id}: ${task_result.pass_at_k}
        | END

        Notes:
        - PRD FR4b ratifies the cohort-discoverability contract; AC-7.2 ratifies the keyword surface.
        - Phase-1 activation heuristic per AC-7.2.4. Phase-2 structured-response classifier deferred per DF-7.2-S1 / C56.
        - FR28 prohibits polling — fan-out via this keyword's own ``trials_per_task`` or via `Stat.Run N Times`.
        - Sibling keywords: `Get Activation Decision` (single-task variant); `Should Activate For` (assertion wrapper).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Get Discoverability",
                    {"skill": str(skill), "tasks": str(tasks), "adapter": adapter},
                )
            )
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1, got {trials_per_task}")
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""

        skill_tasks = load_skill_discoverability_tasks(tasks)

        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model

        t_start = time.perf_counter()
        task_results: list[SkillTaskResult] = []
        for task in skill_tasks:
            activations = 0
            trial_costs: list[float] = []
            for _ in range(trials_per_task):
                adapter_instance = adapter_cls(**ctor_kwargs)
                result = adapter_instance.run(task.prompt)
                activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
                if activated:
                    activations += 1
                trial_costs.append(result.cost_usd)
            pass_at_k = activations / trials_per_task if trials_per_task > 0 else 0.0
            cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
            task_results.append(
                SkillTaskResult(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    should_activate=task.should_activate,
                    trials_run=trials_per_task,
                    activations_observed=activations,
                    pass_at_k=pass_at_k,
                    competing_skills_picked={},
                    cost_per_trial_usd=cost_per_trial,
                )
            )
        total_runtime = time.perf_counter() - t_start
        summary = self._build_discoverability_summary(task_results, total_runtime)
        return SkillDiscoverabilityResult(
            per_task_results=tuple(task_results),
            summary=summary,
            adapter_coverage="in_process",
        )

    @keyword(name="Should Activate For")
    @tier(2)
    def should_activate_for(
        self,
        prompt: str,
        skill: str | Path,
        adapter: str = "generic",
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Asserts that the given skill activates for the given prompt (PRD FR4d).

        [Tier 2 — Stochastic Single-Shot] — sends ``prompt`` to the
        adapter once and asserts the skill name appears in the response
        text. Phase-1 activation heuristic per AC-7.2.5: case-insensitive
        substring check of the skill ``name`` field in
        ``result.response_text`` (same heuristic as `Get Activation Decision`).

        | =Arguments= | =Description= |
        | ``prompt`` | Natural-language prompt to test. |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.2.6. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``SkillDidNotActivateError`` on no-activation
        with diagnostic fields (``prompt``, ``skill_path``,
        ``skill_name``, ``competing_skill`` (None in Phase-1),
        ``reasoning``, ``fix_suggestion``). Raises
        ``InvalidSkillFrontmatterError`` on YAML / file failure.

        Note: missing / empty / non-string ``name`` field causes the
        activation check to always evaluate False — this keyword raises
        ``SkillDidNotActivateError`` unconditionally in that case
        (same as `Get Activation Decision` per AC-7.1.4).

        Example (illustrative — assumes a real adapter):
        | `Should Activate For`    Find news about Robot Framework    ${CURDIR}/skills/web-search.md
        | Run Keyword And Expect Error    SkillDidNotActivateError*    `Should Activate For`    Calculate 2+2    ${CURDIR}/skills/web-search.md

        Notes:
        - PRD FR4d ratifies the activation-assertion contract; AC-7.2.5 + AC-7.2.6 ratify the keyword surface.
        - Phase-1 heuristic per AC-7.1.4 — substring check on skill ``name`` in response text.
        - FR28 prohibits polling — fan-out via `Stat.Run N Times` if statistical evidence is needed.
        - Sibling keywords: `Get Activation Decision` (returns decision instead of raising); `Get Discoverability` (multi-task cohort).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Should Activate For",
                    {"prompt": prompt, "skill": str(skill), "adapter": adapter},
                )
            )
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""

        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        adapter_instance = adapter_cls(**ctor_kwargs)
        result = adapter_instance.run(prompt)
        activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
        if not activated:
            raise SkillDidNotActivateError(
                f"Skill '{skill_name}' did not activate for prompt.",
                prompt=prompt,
                skill_path=str(skill),
                skill_name=skill_name,
                competing_skill=None,
                reasoning=result.response_text,
                fix_suggestion=(
                    "Rephrase prompt to match the skill description, or revise the skill "
                    "description to better match this prompt pattern."
                ),
            )

    def _build_discoverability_summary(
        self, task_results: list[SkillTaskResult], total_runtime: float
    ) -> SkillDiscoverabilityTaskSummary:
        """Compute aggregate summary across all task results."""
        total_trials = sum(r.trials_run for r in task_results)
        total_correct = sum(
            r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed)
            for r in task_results
        )
        activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0

        decoy_results = [r for r in task_results if not r.should_activate]
        false_act_obs = sum(r.activations_observed for r in decoy_results)
        false_act_denom = sum(r.trials_run for r in decoy_results)
        false_activation_rate = false_act_obs / false_act_denom if false_act_denom > 0 else 0.0

        should_act_results = [r for r in task_results if r.should_activate]
        missed_obs = sum(r.trials_run - r.activations_observed for r in should_act_results)
        missed_denom = sum(r.trials_run for r in should_act_results)
        missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0

        total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)

        return SkillDiscoverabilityTaskSummary(
            activation_accuracy=activation_accuracy,
            false_activation_rate=false_activation_rate,
            missed_activation_rate=missed_activation_rate,
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
        )
