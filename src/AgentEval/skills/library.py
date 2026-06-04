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

The 5 static-inspection keywords above are `@tier(1)`-annotated
(deterministic, ≤50 ms per call on typical 5 KB inputs per NFR-PERF-02).
Tier-1 keywords do NOT touch the provider, the trace store, or external
services; they read the local `.md` file + parse YAML only. Stochastic
fan-out keywords (`Get Activation Decision`, `Get Discoverability`,
`Skill.Compare Discoverability`) are `@tier(3)` and `Should Activate For`
is `@tier(2)` — these were added in later epics (7 / 12 / 13) and are
NOT covered by the ≤50 ms NFR.

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
collision with `SubagentsLibrary.Get Frontmatter`). All 9 keywords
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
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

if TYPE_CHECKING:
    from AgentEval.stats.types import KeywordRun

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.tier import tier
from AgentEval._kernel.tier_acl import build_polling_disallowed_message
from AgentEval.errors import PollingDisallowedError, SkillDidNotActivateError
from AgentEval.skills._internal import load_skill_discoverability_tasks
from AgentEval.skills._parser import parse_frontmatter, validate_frontmatter_structure
from AgentEval.skills.types import (
    ActivationDecision,
    SkillDiscoverabilityComparisonResult,
    SkillDiscoverabilityComparisonSummary,
    SkillDiscoverabilityResult,
    SkillPairwiseAdapterDelta,
)

__all__ = ["SkillsLibrary"]

# Browser-Library-style docstring migration marker (Phase 6, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


class SkillsLibrary:
    """Static-inspection + cross-adapter keywords for skill `.md` files.

    All 9 public methods are `@keyword`-decorated per Story 1b.6
    conventions, spanning mixed tiers: `@tier(1)` for deterministic
    static-inspection (Get Frontmatter, Get Description, Get Allowed
    Tools, Get Disable Model Invocation, Should Be Valid Frontmatter) —
    these hold no mutable state and re-parse the target file per call
    (stateless + parallel-safe under `pabot --processes N`); `@tier(2)`
    for `Should Activate For` (declarative-match keyword); `@tier(3)`
    for stochastic fan-out keywords delegating to coding-agent adapters
    (`Get Activation Decision`, `Get Discoverability` Story 7.2,
    `Skill.Compare Discoverability` Story 13.5).
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

    # ----------------------------------------------------------------- #
    # FR27 specialised — Story 14.5 / C59 / DF-7.3-S1 closure             #
    # ----------------------------------------------------------------- #

    @keyword(name="Skill.Get Activation Pass At K")
    @tier(1)
    def get_activation_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
    ) -> float:
        """[Tier 1 — Deterministic] HumanEval Pass@k unbiased estimator over activation-decision trials.

        Specialised sibling of ``Stat.Get Pass At K`` with the
        activation-decision pass-predicate HARD-CODED in. Returns
        ``float ∈ [0, 1]`` — same HumanEval estimator math as
        ``Stat.Get Pass At K`` (delegates to the same internal helper).

        | =Arguments= | =Description= |
        | ``runs`` | ``list[KeywordRun]`` — typically the result of ``Stat.Run N Times`` wrapping ``Skill.Get Activation Decision``. |
        | ``k`` | Top-k parameter. Must satisfy ``1 <= k <= len(runs)``. |

        Raises ``ValueError`` when ``k < 1``, ``k > len(runs)``, or
        ``len(runs) == 0`` (delegated to ``_compute_pass_at_k`` validation).

        Example:
        | ${pass_at_5} =    `Skill.Get Activation Pass At K`    ${RUNS}    k=5
        | Should Be True    ${pass_at_5} >= 0.7

        Notes:
        - PRD FR27 — Pass@k unbiased estimator math reused via
          ``AgentEval.stats._internal._compute_pass_at_k``.
        - Pass-predicate is HARD-CODED to
          ``isinstance(run.result, ActivationDecision) and
          run.result.activated``. The default ``Stat.Get Pass At K``
          predicate (``completeness == "complete"``) returns ``False``
          for ``ActivationDecision`` results because
          ``ActivationDecision`` has no ``metadata.completeness``
          attribute — the silent-zero failure mode Story 7.3 D-1
          empirically confirmed (closes C59 / DF-7.3-S1).
        - No ``predicate`` kwarg by design — removing the
          predicate-customization pitfall is the whole purpose. Operators
          needing a custom predicate call ``Stat.Get Pass At K`` directly.
        - Sibling keyword: ``Stat.Get Pass At K`` (Tier-1) for generic
          Pass@k on ``AgentRunResult`` runs.
        - Closes Epic 12 retro Action #5 + Epic 13 retro Action #5 (the
          C59 closure ratified 6 epics later in Story 14.5). The multi-word
          post-dot keyword name complies with the ratified norm
          ``feedback_libdoc_namespace_keyword_must_be_multiword``
          (Epic 12 retro 2026-06-01) — single-word post-dot names trigger
          the RF libdoc auto-split bug; multi-word names are immune.
        """
        from AgentEval.skills._internal import _activation_pass_predicate
        from AgentEval.stats._internal import _compute_pass_at_k

        c = sum(1 for r in runs if _activation_pass_predicate(r))
        return _compute_pass_at_k(c, len(runs), k)

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

        # Story 13.5 refactor: per-adapter logic extracted to
        # `skills/_internal.run_single_adapter_skill_discoverability` so
        # the new `Skill.Compare Discoverability` keyword reuses it
        # without duplication. Behavior MUST equal pre-refactor —
        # verified by Story 7.2's existing tests passing unchanged.
        from AgentEval.skills._internal import run_single_adapter_skill_discoverability

        t_start = time.perf_counter()
        return run_single_adapter_skill_discoverability(
            skill_name=skill_name,
            task_list=skill_tasks,
            adapter=adapter,
            model=model,
            trials_per_task=trials_per_task,
            extra_adapter_kwargs=dict(kwargs),
            t_start=t_start,
        )

    # --------------------------------------------------------------- #
    # Story 13.5: Cross-adapter Skill Discoverability comparison      #
    # (PRD FR4c). Symmetric to Story 13.3's `MCP.Compare Tool         #
    # Discoverability` (FR10b). Behind the `[agenteval-advanced]`     #
    # extra (Mann-Whitney U from Story 13.1).                         #
    # --------------------------------------------------------------- #

    @keyword(name="Skill.Compare Discoverability")
    @tier(3)
    @guarded_fanout()
    def get_discoverability_comparison(
        self,
        skill: str | Path = "",
        tasks: str | Path = "",
        adapters: list[str] | None = None,
        trials_per_task: int = 3,
        max_cost_usd: float = 20.00,
        max_runtime_seconds: float | None = None,
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> SkillDiscoverabilityComparisonResult:
        """Compares Skill Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).

        [Tier 3 — Stochastic Fan-Out] — runs `Skill.Get Discoverability`
        once per adapter against the SAME task set, then computes
        pairwise Mann-Whitney U deltas across the per-task `pass_at_k`
        distributions PLUS false-activation-rate + missed-activation-
        rate deltas. Returns a `SkillDiscoverabilityComparisonResult`
        with per-adapter results + cross-adapter deltas + multi-column
        cohort heatmap + aggregate summary.

        Requires the ``[agenteval-advanced]`` optional extra (scipy +
        numpy) for the Mann-Whitney U cross-adapter delta computation;
        raises ``ImportError`` on invocation WITHOUT the extra
        (fail-fast BEFORE per-adapter fan-out — operators discovering
        the missing extra should not pay N-adapter trial cost first).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML (loaded ONCE; shared across adapters). |
        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. |
        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2218 (4× single-adapter typical). Phase-1 carve-out DF-13.5-S1 / C95: tracked NOT enforced (same SkillsLibrary architectural gap as DF-4.4-S1 / C20 and DF-13.3-S1). |
        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. |
        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 (mirrors `Get Discoverability`). |
        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |

        Returns ``SkillDiscoverabilityComparisonResult`` with
        ``adapters`` + ``per_adapter_results`` (one
        ``SkillDiscoverabilityResult`` per adapter) +
        ``cross_adapter_deltas`` (C(N, 2) ``SkillPairwiseAdapterDelta``
        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
        ``CohortHeatmap`` via ``from_skill_comparison``) + ``summary``
        (``SkillDiscoverabilityComparisonSummary``).

        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
        missing. Raises ``PollingDisallowedError`` when ``polling`` is
        provided. Raises ``ValueError`` on missing ``skill`` / ``tasks``
        / ``adapters`` (≥2 distinct required) / invalid
        ``trials_per_task``.

        Example:
        | ${comparison}=    `Skill.Compare Discoverability`
        | ...    skill=${CURDIR}/skills/example.md
        | ...    tasks=${CURDIR}/discoverability/skill-tasks.yaml
        | ...    adapters=${{['claude_code_cli', 'codex_cli']}}
        | ...    trials_per_task=5
        | Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
        | Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3

        Notes:
        - Story 13.5 (Epic 13) ships this Phase-2 keyword closing Devon's cross-adapter analysis loop. Symmetric to Story 13.3's `MCP.Compare Tool Discoverability` (FR10b).
        - PRD FR4c ratifies the cross-adapter Skill Discoverability surface; epics.md L2218-2219 ratifies the keyword signature + extended fields (per-adapter false-activation / missed-activation rate comparison).
        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper). Mann-Whitney U is computed on the per-task ``pass_at_k`` lists per adapter; false-activation + missed-activation deltas are aggregate-summary subtractions.
        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition.
        - Phase-2.5 carry-overs: DF-13.5-S1 (`@guarded_fanout` cross-library budget plumbing); DF-13.5-S2 (per-adapter MCP attachment); DF-13.5-S3 (Bonferroni multi-pairwise correction); DF-13.5-S4 (`robotframework-agentskills` dogfood CI matrix).
        - Sibling keyword: `Skill.Get Discoverability` (Phase-1 single-adapter). The ≥2-adapter validation rejects N=1 callers — use the simpler `Get` keyword for single-adapter runs.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        # Story 13.3 HIGH-A precedent (codex MED-2 13.5 fix): anchor the
        # comparison-level wall-clock at keyword entry — BEFORE validation,
        # extras gate, frontmatter parse, and per-adapter fan-out — so
        # `summary.total_runtime_seconds` is end-to-end (what the operator
        # waited), not "fan-out-only" (which would exclude real setup time).
        compare_t_start = time.perf_counter()

        # Validate args (mirrors single-adapter Get + adds N>=2 constraint).
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Skill.Compare Discoverability",
                    {"skill": str(skill), "tasks": str(tasks), "adapters": adapters},
                )
            )
        if not skill:
            raise ValueError("Skill.Compare Discoverability requires `skill=<path>` kwarg")
        if not tasks:
            raise ValueError("Skill.Compare Discoverability requires `tasks=<yaml-path>` kwarg")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        if adapters is None or len(adapters) < 2:
            raise ValueError(
                f"Skill.Compare Discoverability requires adapters=[<adapter_1>, "
                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
            )
        if len(set(adapters)) != len(adapters):
            raise ValueError(
                f"Skill.Compare Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
            )

        # `[agenteval-advanced]` extras gate (Story 13.5 D-4 + L-2).
        # Module-attr read per Story 13.3 amendment (NOT `from X import Y`
        # which captures stale value across pytest session reload).
        from AgentEval.stats import library as _stats_lib

        if not _stats_lib._ADVANCED_AVAILABLE:
            raise ImportError(
                "Skill.Compare Discoverability: scipy + numpy required. "
                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
            )

        # Parse skill frontmatter + tasks YAML ONCE (shared across adapters).
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""
        skill_tasks = load_skill_discoverability_tasks(tasks)

        from AgentEval._heatmap.models import CohortHeatmap
        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
        from AgentEval.stats.mannwhitney import compute_mann_whitney_u

        per_adapter_results: dict[str, SkillDiscoverabilityResult] = {}
        for adapter_name in adapters:
            per_adapter_results[adapter_name] = run_single_adapter_skill_discoverability(
                skill_name=skill_name,
                task_list=skill_tasks,
                adapter=adapter_name,
                model=model,
                trials_per_task=trials_per_task,
                extra_adapter_kwargs=dict(kwargs),
                t_start=time.perf_counter(),
            )

        # Build C(N, 2) pairwise deltas.
        import itertools
        import math as _math

        cross_adapter_deltas: dict[str, SkillPairwiseAdapterDelta] = {}
        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
            a_result = per_adapter_results[adapter_a]
            b_result = per_adapter_results[adapter_b]
            rates_a = [t.pass_at_k for t in a_result.per_task_results]
            rates_b = [t.pass_at_k for t in b_result.per_task_results]
            if not rates_a or not rates_b:
                continue
            mwu = compute_mann_whitney_u(rates_a, rates_b)
            delta_key = f"{adapter_a}_vs_{adapter_b}"
            mean_a = sum(rates_a) / len(rates_a)
            mean_b = sum(rates_b) / len(rates_b)
            cross_adapter_deltas[delta_key] = SkillPairwiseAdapterDelta(
                adapter_a=adapter_a,
                adapter_b=adapter_b,
                pass_at_k_delta=mean_a - mean_b,
                pass_at_k_mann_whitney_result=mwu,
                false_activation_rate_delta=a_result.summary.false_activation_rate
                - b_result.summary.false_activation_rate,
                missed_activation_rate_delta=a_result.summary.missed_activation_rate
                - b_result.summary.missed_activation_rate,
                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
            )

        # Build summary.
        activation_accuracy_per_adapter = {
            name: per_adapter_results[name].summary.activation_accuracy for name in adapters
        }
        best_adapter = max(
            activation_accuracy_per_adapter,
            key=lambda a: activation_accuracy_per_adapter[a],
        )
        worst_adapter = min(
            activation_accuracy_per_adapter,
            key=lambda a: activation_accuracy_per_adapter[a],
        )
        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
        # Story 13.3 HIGH-A: comparison wall-clock measured from
        # `compare_t_start` (NOT MAX of per-adapter, which would
        # under-report serial execution by ~N-1×).
        total_runtime = time.perf_counter() - compare_t_start
        summary = SkillDiscoverabilityComparisonSummary(
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
            activation_accuracy_per_adapter=activation_accuracy_per_adapter,
            best_adapter=best_adapter,
            worst_adapter=worst_adapter,
        )

        # Build heatmap via the new classmethod. Use a shim namespace
        # (mirrors Story 13.3 D-5 pattern) so the classmethod can read
        # `.adapters` + `.per_adapter_results` before the full result
        # dataclass is constructed.
        class _ComparisonShim:
            pass

        shim = _ComparisonShim()
        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
        heatmap = CohortHeatmap.from_skill_comparison(shim)  # type: ignore[arg-type]

        return SkillDiscoverabilityComparisonResult(
            adapters=tuple(adapters),
            per_adapter_results=per_adapter_results,
            cross_adapter_deltas=cross_adapter_deltas,
            heatmap=heatmap,
            summary=summary,
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

    # `_build_discoverability_summary` removed Story 13.5 refactor 2026-06-01:
    # logic extracted to `AgentEval.skills._internal.build_skill_discoverability_summary`
    # so the new `Skill.Compare Discoverability` keyword reuses it. The
    # only caller was `get_discoverability` which now delegates to the
    # `run_single_adapter_skill_discoverability` helper (which calls
    # `build_skill_discoverability_summary` internally).
