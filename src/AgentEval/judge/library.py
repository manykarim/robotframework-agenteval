# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line per the project docstring-refresh convention.

"""``JudgeLibrary`` — Tier-2 LLM-judge keyword surface (Story 12.1 / PRD FR48).

Ships the `Judge.Get Score` keyword that evaluates an `AgentRunResult`
against a Markdown rubric using an LLM judge. Returns a `JudgeScore`
dataclass with numeric score, pass/fail vs threshold, reasoning, per-
criterion breakdown, and cost.

Per architecture.md L613 + L983 + L1312-1316: Judge sub-library lands in
Epic 12 closing Devon's Journey 4 Tier-2 slot (Tier-1 static from Story
2.1 + Tier-2 LLM-deterministic here + Tier-3 cohort discoverability from
Story 7.2). LLM judge behavior is reproducible with `seed +
temperature=0` so `@tier(2)` (LLM-deterministic) applies.

## Phase-1 carve-outs (documented inline)

- **Markdown rubric format only** — YAML schema rubrics are DF-12.1-S1 / C79.
- **No retry loop on JudgeOutputParseError** — `seed + temperature=0`
  should make the judge response deterministic; if the model fails to
  format the response correctly the test fails loud (per the M_R11
  fail-loud pattern + Story 11.1 kilo HIGH-1 `feedback_listener_hook_api_surface_empirical_check`
  lesson applied UPSTREAM).
- **Single-shot LLM call** — no multi-turn chain-of-thought rubric;
  Phase-2 may extend (DF-12.1-S2 / C80 plug-in judges).
- **`@guarded_fanout` enforcement** — works via `_SUB_LIBRARIES` standard
  composition path; mirrors `StatsLibrary` precedent. The MCPLibrary
  8-epic-old `@guarded_fanout` carve-out (Epic 11 retro Action #3 /
  DF-4.4-S1 / C20) is specific to MCP's `WITH NAME` composition path
  and does NOT block this story.

## Thread safety

Host-instance budgets (`_max_cost_usd`, `_max_runtime_seconds`) are
read-only after `__init__`; per-call `@guarded_fanout` state
(`_BreachState`, meter thread, cancel event) is isolated per invocation.
**Phase-1 caveat:** the `@guarded_fanout` cost-meter source
(`guardrails._current_cost_usd_for_run`) is module-level and is
documented in `guardrails.py` as "single-fanout-at-a-time scoped in
Phase-1" — concurrent fan-outs within the same process are not
independently metered until the Story 4.1 follow-up wires a per-run
cost source. So "concurrent `Get Score` calls are safe" holds for
DATA (no shared mutable state on the JudgeLibrary instance) but NOT
for budget metering, which becomes a process-wide aggregate during
concurrent fan-out.

References:
- PRD FR48 (Judge.Get Score with rubric calibration).
- architecture.md L613, L983, L1312-1316 (Judge sub-library file homes + types).
- epics.md L2085-2099 (Story 12.1 AC).
- ADR-014 (error class hierarchy — `JudgeOutputParseError` + `InvalidJudgeRubricError`).
- ADR-015 (cost / runtime guardrails via `@guarded_fanout`).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from robot.api import logger
from robot.api.deco import keyword, library

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval._kernel.tier import tier
from AgentEval.errors import InvalidJudgeRubricError, JudgeOutputParseError
from AgentEval.judge.calibration import (
    KAPPA_HARD_FAIL_THRESHOLD,
    compute_cohen_kappa,
    load_calibration_set,
)
from AgentEval.judge.presets import get_preset_rubric
from AgentEval.judge.rubric import load_rubric, parse_rubric_text
from AgentEval.judge.types import CalibrationReport, JudgeRubric, JudgeScore
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

__all__ = ["JudgeLibrary"]


@library(scope="GLOBAL")
class JudgeLibrary(_HostBudgetPlumbing):
    """`Judge.Get Score` Tier-2 LLM-judge keyword surface (Story 12.1 / PRD FR48).

    Wired via `AgentEval._SUB_LIBRARIES` standard composition path.
    Inherits `_HostBudgetPlumbing` for the `_max_cost_usd` +
    `_max_runtime_seconds` instance attrs consumed by `@guarded_fanout`
    on `Judge.Get Score` (Tier-2 LLM-call keyword). Budgets are forwarded
    from `AgentEval.__init__` via `_build_components`' unified
    `_HostBudgetPlumbing` subclass check (`compose-single-library-import`
    change; formerly a dedicated class-name branch mirroring `StatsLibrary`
    per Story 6.3 AC-6.3.8).
    """

    @keyword(name="Judge.Get Score")
    @tier(2)
    @guarded_fanout()
    def get_score(
        self,
        *,
        result: AgentRunResult,
        rubric: str | Path | JudgeRubric,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).

        [Tier 2 — Stochastic Single-Shot] — single-shot LLM call against the
        configured `judge_adapter` (default `"generic"` LiteLLM-backed).
        LLM-deterministic per the determinism-contract.md `@tier(2)`
        contract when invoked with `seed + temperature=0`. Wraps
        `@guarded_fanout` cost+runtime guardrails per ADR-015.

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. Reads ``result.response_text`` for the agent's output. |
        | ``rubric`` | Path to a Markdown rubric file (`.md`) OR a pre-loaded `JudgeRubric` instance. |
        | ``judge_adapter`` | Adapter slug to resolve via `agenteval.coding_agents` entry-points. Defaults to ``"generic"``. |
        | ``judge_model`` | Model identifier for the judge adapter (e.g., ``"anthropic/claude-sonnet-4-6"``). Forwarded to the adapter's `run(model=...)` kwarg. |
        | ``**adapter_kwargs`` | Provider/adapter forward-compat kwargs (e.g., ``temperature=0.0``, ``seed=42``). |

        Returns ``JudgeScore`` with: ``numeric_score`` (0-10), ``pass_threshold_met``
        (vs rubric threshold), ``reasoning`` (LLM's narrative explanation),
        ``criteria_breakdown`` (per-criterion sub-scores), ``cost_usd``.

        Raises ``InvalidJudgeRubricError`` on rubric parse failure.
        Raises ``JudgeOutputParseError`` when the LLM response is not
        valid JSON OR is missing required fields OR ``numeric_score``
        is outside ``[0.0, 10.0]``.

        Example:
        | ${result} =    `Send Prompt`    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${score} =    `Judge.Get Score`    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6
        | Should Be True    ${score.pass_threshold_met}
        | Should Be True    ${score.numeric_score} >= 7.0
        | Log    Reasoning: ${score.reasoning}

        Notes:
        - PRD FR48 ratifies the keyword + rubric calibration discipline.
        - Tier-2 LLM-deterministic per `determinism-contract.md`; cost guardrails per ADR-015.
        - `JudgeScore` shape ratified Story 12.1 AC-12.1.2 per architecture L1316.
        - Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.
        - `rubric_source` is `"preloaded"` for a `JudgeRubric` instance, else `"file"`;
          `calibrated` is always `False` (a rubric file is not calibration evidence —
          add-judge-criteria-shortcuts D2; evidence-binding is `DF-JCS-S1` / C104).
        """
        # Load + parse the rubric (or accept a pre-parsed one). The provenance
        # marking is honest about where the rubric came from (D2): a file path
        # vs an already-parsed `JudgeRubric` instance.
        if isinstance(rubric, JudgeRubric):
            parsed_rubric = rubric
            rubric_source = "preloaded"
        else:
            parsed_rubric = load_rubric(rubric)
            rubric_source = "file"

        return _execute_judge(
            parsed_rubric,
            result,
            adapter_slug=judge_adapter,
            judge_model=judge_model,
            rubric_source=rubric_source,
            adapter_kwargs=adapter_kwargs,
        )

    @keyword(name="Judge.Calibrate Rubric", tags=("agenteval",))
    @tier(2)
    @guarded_fanout()
    def calibrate(
        self,
        *,
        rubric: str | Path | JudgeRubric,
        calibration_set: str | Path,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> CalibrationReport:
        """Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).

        [Tier 2 — Stochastic Single-Shot] — N single-shot LLM calls (one per
        calibration row) against the configured ``judge_adapter``. Cohen's
        kappa over binarized judge-pass / human-pass labels at the rubric's
        threshold; ``passes_hard_fail`` is True iff ``kappa >= 0.7`` per
        `architecture.md` L199 agentguard-borrowed calibration discipline.
        Wraps `@guarded_fanout` cost+runtime guardrails per ADR-015.

        | =Arguments= | =Description= |
        | ``rubric`` | Path to a Markdown rubric file (`.md`) OR a pre-loaded `JudgeRubric` instance. |
        | ``calibration_set`` | Path to a YAML calibration set with `rows:` list of `{prompt, response, human_label}`. |
        | ``judge_adapter`` | Adapter slug; defaults to ``"generic"``. |
        | ``judge_model`` | Model identifier; forwarded to the adapter's `run(model=...)` kwarg. |
        | ``**adapter_kwargs`` | Provider/adapter forward-compat kwargs. |

        Returns ``CalibrationReport`` with: ``cohen_kappa`` (float; ``nan``
        if zero-variance), ``passes_hard_fail`` (kappa >= 0.7),
        ``threshold_tuning`` (precision/recall/F1 sweep), ``recommended_threshold``
        (F1-maximizing), ``systematic_bias_diagnostics`` (human-readable
        bullets), ``total_cost_usd``, ``total_latency_seconds``.

        Raises ``InvalidJudgeRubricError`` on rubric parse failure.
        Raises ``InvalidCalibrationSetError`` on calibration set parse failure.
        Raises ``JudgeOutputParseError`` if any per-row judge invocation
        returns malformed JSON.

        Example:
        | ${report} =    `Judge.Calibrate Rubric`    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6
        | Should Be True    ${report.passes_hard_fail}
        | Log    Cohen's kappa = ${report.cohen_kappa}
        | Log    Recommended threshold = ${report.recommended_threshold}

        Notes:
        - `KAPPA_HARD_FAIL_THRESHOLD = 0.7` per `architecture.md` L199.
        - Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.
        - Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.
        """
        parsed_rubric = rubric if isinstance(rubric, JudgeRubric) else load_rubric(rubric)
        rows = load_calibration_set(calibration_set)

        adapter_cls = get_adapter(judge_adapter)
        adapter = adapter_cls()

        judge_scores: list[float] = []
        human_labels: list[float] = []
        total_cost = 0.0
        total_latency = 0.0

        for row in rows:
            # Synthesize a per-row `AgentRunResult` carrying the row's
            # `response` as if the agent had produced it; the judge then
            # scores against the rubric.
            synth_result = AgentRunResult(
                response_text=row.response,
                tool_calls=[],
                usage=Usage(input_tokens=0, output_tokens=0),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id=f"calibration-row-{len(judge_scores)}",
            )

            # Thread the row's `prompt` (the task/context the response was
            # produced for) into the judge prompt as a distinct `# Input`
            # section so calibration scores the SAME task the presets score.
            # The preset calibration templates
            # (`docs/examples/judge-presets/*.template.yaml`) instruct users to
            # put the grounding `CONTEXT:`/`QUESTION:` in `prompt`; dropping it
            # would validate a different, under-specified task than the preset
            # scores (add-judge-criteria-shortcuts codex MED). Guard on a
            # non-empty prompt so a blank prompt never adds an empty section.
            extra_sections: tuple[tuple[str, str], ...] = (
                (("Input", row.prompt),) if row.prompt.strip() else ()
            )
            judge_prompt = _compose_judge_prompt(parsed_rubric, synth_result, extra_sections=extra_sections)
            run_kwargs: dict[str, Any] = dict(adapter_kwargs)
            if judge_model is not None:
                run_kwargs["model"] = judge_model
            judge_run = adapter.run(prompt=judge_prompt, **run_kwargs)
            score = _parse_judge_response(judge_run, parsed_rubric)

            judge_scores.append(score.numeric_score)
            human_labels.append(row.human_label)
            total_cost += score.cost_usd
            total_latency += judge_run.latency_seconds

        kappa, undefined_reason = compute_cohen_kappa(judge_scores, human_labels, parsed_rubric.threshold)
        passes_hard_fail = not math.isnan(kappa) and kappa >= KAPPA_HARD_FAIL_THRESHOLD

        threshold_tuning = _sweep_thresholds(judge_scores, human_labels, parsed_rubric.threshold)
        recommended_threshold = _select_f1_max_threshold(threshold_tuning, parsed_rubric.threshold)
        bias_diagnostics = _diagnose_systematic_bias(judge_scores, human_labels)

        rubric_path_str = parsed_rubric.raw_text[:40] if isinstance(rubric, JudgeRubric) else str(rubric)
        return CalibrationReport(
            rubric_path=rubric_path_str,
            calibration_set_path=str(calibration_set),
            judge_adapter=judge_adapter,
            judge_model=judge_model,
            rows_total=len(rows),
            rows_processed=len(judge_scores),
            judge_scores=tuple(judge_scores),
            human_labels=tuple(human_labels),
            cohen_kappa=kappa,
            kappa_undefined_reason=undefined_reason,
            passes_hard_fail=passes_hard_fail,
            threshold_tuning=threshold_tuning,
            recommended_threshold=recommended_threshold,
            systematic_bias_diagnostics=bias_diagnostics,
            total_cost_usd=total_cost,
            total_latency_seconds=total_latency,
        )

    # ----------------------------------------------------------------------- #
    # add-judge-criteria-shortcuts — one-line on-ramp keywords                 #
    # ----------------------------------------------------------------------- #

    @keyword(name="Judge.Score With Criteria")
    @tier(2)
    @guarded_fanout()
    def score_with_criteria(
        self,
        *,
        result: AgentRunResult,
        criteria: str,
        threshold: float = 7.0,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Judges an `AgentRunResult` against a plain-language criteria string — no rubric file (add-judge-criteria-shortcuts).

        [Tier 2 — Stochastic Single-Shot] — the one-line on-ramp (DeepEval
        G-Eval idiom). Synthesizes a real `JudgeRubric` in memory from the
        ``criteria`` string (a single criterion carrying the verbatim string),
        then reuses the exact same judge pipeline as `Judge.Get Score` (prompt
        composition, adapter call, JSON parse) and returns the same `JudgeScore`
        shape. Wraps `@guarded_fanout` cost+runtime guardrails per ADR-015.

        **HONESTY (add-judge-criteria-shortcuts D2):** the returned `JudgeScore`
        is ALWAYS ``calibrated=False`` with ``rubric_source="criteria_string"``,
        and the first shortcut score per process emits an RF ``WARN`` pointing
        at the calibration recipe. Two-tier message: *one-line criteria string
        to start; graduate to a calibrated rubric (Cohen's κ ≥ 0.7) for CI
        gates* — see `Judge.Get Score` + `Judge.Calibrate Rubric`.

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. Reads ``result.response_text``. |
        | ``criteria`` | Plain-language evaluation instruction (the G-Eval idiom: the string IS the instruction; it is not decomposed). Empty / whitespace / nullish raises `InvalidJudgeRubricError` before any LLM call. |
        | ``threshold`` | Pass threshold in ``[0.0, 10.0]`` (default ``7.0``); ``pass_threshold_met == (numeric_score >= threshold)``. Out-of-range raises before any LLM call. |
        | ``judge_adapter`` | Adapter slug (default ``"generic"``). |
        | ``judge_model`` | Model identifier forwarded to ``adapter.run(model=...)``. |
        | ``**adapter_kwargs`` | Provider forward-compat kwargs (e.g., ``temperature=0.0``, ``seed=42``). |

        Returns ``JudgeScore`` with ``calibrated=False`` +
        ``rubric_source="criteria_string"``.

        Raises ``InvalidJudgeRubricError`` on empty/whitespace/nullish criteria
        or out-of-range threshold (before any LLM call).
        Raises ``JudgeOutputParseError`` on malformed judge JSON.

        Example:
        | ${score} =    `Judge.Score With Criteria`    result=${result}    criteria=Response is polite and answers the question    threshold=7
        | Should Be True    ${score.numeric_score} >= 7.0
        | Log    Uncalibrated (${score.rubric_source}); reasoning: ${score.reasoning}

        Notes:
        - PRD FR48 judge surface; add-judge-criteria-shortcuts D1 criteria synthesis.
        - Tier-2 LLM-deterministic per `determinism-contract.md`; cost guardrails per ADR-015.
        - `calibrated=False` is unfakeable here — no keyword in this change sets `calibrated=True` (`DF-JCS-S1` / C104).
        """
        rubric = _synthesize_criteria_rubric(criteria, threshold)
        _warn_uncalibrated_once("criteria_string")
        return _execute_judge(
            rubric,
            result,
            adapter_slug=judge_adapter,
            judge_model=judge_model,
            rubric_source="criteria_string",
            adapter_kwargs=adapter_kwargs,
        )

    @keyword(name="Judge.Get Faithfulness")
    @tier(2)
    @guarded_fanout()
    def get_faithfulness(
        self,
        *,
        result: AgentRunResult,
        context: str,
        threshold: float | None = None,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Metric preset — scores whether the response is grounded in the supplied context (add-judge-criteria-shortcuts).

        [Tier 2 — Stochastic Single-Shot] — thin wrapper over the judge pipeline
        backed by the curated ``faithfulness`` preset rubric. Wraps
        `@guarded_fanout` cost+runtime guardrails per ADR-015.

        Rubric criterion (verbatim): *"Every factual claim in the response is
        supported by the supplied grounding context. Penalize each claim that is
        unsupported, contradicted, or embellished beyond the context,
        proportionally to how central the claim is to the response. A response
        that stays strictly within what the context supports scores 10.0."*

        Does NOT measure: factual accuracy against the world — only support
        against the supplied ``context``. A response can be faithful to a wrong
        context and still score high. Does NOT measure relevancy to a question
        (use `Judge.Get Answer Relevancy`).

        **HONESTY:** ``calibrated=False`` always; ``rubric_source="preset:faithfulness"``;
        WARN-once per process. Graduate via `Judge.Get Preset Rubric` →
        `Judge.Calibrate Rubric` on your own labels (add-judge-criteria-shortcuts D5).

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. |
        | ``context`` | Grounding text the response's claims must be supported by. Rendered as a distinct ``# Context`` prompt section. |
        | ``threshold`` | Optional override of the preset's built-in ``7.0`` threshold; out-of-range raises before any LLM call. |
        | ``judge_adapter`` / ``judge_model`` / ``**adapter_kwargs`` | Standard judge pass-through. |

        Returns ``JudgeScore`` (``rubric_source="preset:faithfulness"``, ``calibrated=False``).

        Example:
        | ${score} =    `Judge.Get Faithfulness`    result=${result}    context=${source_document}
        | Should Be True    ${score.pass_threshold_met}

        Notes:
        - add-judge-criteria-shortcuts D3 preset registry (`judge/presets.py`).
        - Tier-2 LLM-deterministic; cost guardrails per ADR-015.
        - Uncalibrated-by-default per add-judge-criteria-shortcuts D5.
        """
        return self._score_with_preset(
            preset="faithfulness",
            result=result,
            extra_sections=(("Context", context),),
            threshold=threshold,
            judge_adapter=judge_adapter,
            judge_model=judge_model,
            adapter_kwargs=adapter_kwargs,
        )

    @keyword(name="Judge.Get Answer Relevancy")
    @tier(2)
    @guarded_fanout()
    def get_answer_relevancy(
        self,
        *,
        result: AgentRunResult,
        question: str,
        threshold: float | None = None,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Metric preset — scores whether the response addresses the supplied question (add-judge-criteria-shortcuts).

        [Tier 2 — Stochastic Single-Shot] — thin wrapper over the judge pipeline
        backed by the curated ``answer_relevancy`` preset rubric. Wraps
        `@guarded_fanout` cost+runtime guardrails per ADR-015.

        Rubric criterion (verbatim): *"The response directly addresses the
        supplied question: it is on-topic, answers what was actually asked, and
        does not evade, pad, or drift onto adjacent topics. Penalize non-answers,
        partial answers that skip the core of the question, and padding that does
        not advance the answer. A focused response that fully answers the question
        scores 10.0."*

        Does NOT measure: factual correctness of the answer (a confidently-wrong
        but on-topic answer can still score high on relevancy) — pair with
        `Judge.Get Faithfulness` for grounding. The original prompt is NOT
        recoverable from `AgentRunResult`, so ``question`` MUST be supplied
        explicitly; it is never silently substituted.

        **HONESTY:** ``calibrated=False`` always; ``rubric_source="preset:answer_relevancy"``;
        WARN-once per process. Graduate via `Judge.Get Preset Rubric` →
        `Judge.Calibrate Rubric` (add-judge-criteria-shortcuts D5).

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. |
        | ``question`` | The question the response is expected to answer. Rendered as a distinct ``# Question`` prompt section. |
        | ``threshold`` | Optional override of the preset's built-in ``7.0`` threshold. |
        | ``judge_adapter`` / ``judge_model`` / ``**adapter_kwargs`` | Standard judge pass-through. |

        Returns ``JudgeScore`` (``rubric_source="preset:answer_relevancy"``, ``calibrated=False``).

        Example:
        | ${score} =    `Judge.Get Answer Relevancy`    result=${result}    question=What is the capital of France?
        | Should Be True    ${score.pass_threshold_met}

        Notes:
        - add-judge-criteria-shortcuts D3 preset registry (`judge/presets.py`).
        - Tier-2 LLM-deterministic; cost guardrails per ADR-015.
        - Uncalibrated-by-default per add-judge-criteria-shortcuts D5.
        """
        return self._score_with_preset(
            preset="answer_relevancy",
            result=result,
            extra_sections=(("Question", question),),
            threshold=threshold,
            judge_adapter=judge_adapter,
            judge_model=judge_model,
            adapter_kwargs=adapter_kwargs,
        )

    @keyword(name="Judge.Get Hallucination Score")
    @tier(2)
    @guarded_fanout()
    def get_hallucination_score(
        self,
        *,
        result: AgentRunResult,
        context: str,
        threshold: float | None = None,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Metric preset — grounding score where HIGHER = LESS hallucination; 10.0 = none detected (add-judge-criteria-shortcuts D4).

        [Tier 2 — Stochastic Single-Shot] — thin wrapper over the judge pipeline
        backed by the curated ``hallucination`` preset rubric. Wraps
        `@guarded_fanout` cost+runtime guardrails per ADR-015.

        **Direction (READ THIS FIRST):** this is a GROUNDING score — HIGHER IS
        BETTER. ``10.0`` = no fabricated entities/facts/citations relative to the
        ``context``; ``0.0`` = pervasive fabrication. This deliberately INVERTS
        DeepEval's HallucinationMetric (which scores the hallucination
        proportion, lower-is-better) so the project-wide uniform
        ``numeric_score >= threshold`` pass semantics hold for all three presets
        (add-judge-criteria-shortcuts D4). A well-grounded response PASSES.

        Rubric criterion (verbatim): *"Freedom from hallucination as a GROUNDING
        score where HIGHER IS BETTER. 10.0 = no fabricated entities, facts,
        citations, or quantities relative to the supplied context; 0.0 =
        pervasive fabrication. Every named entity, statistic, quotation, or
        citation in the response must be traceable to the context; each
        fabricated or unverifiable item lowers the score proportionally."*

        Does NOT measure: whether the response is complete or relevant — only
        whether what it DID say is grounded in the context.

        **HONESTY:** ``calibrated=False`` always; ``rubric_source="preset:hallucination"``;
        WARN-once per process. Graduate via `Judge.Get Preset Rubric` →
        `Judge.Calibrate Rubric` (add-judge-criteria-shortcuts D5).

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. |
        | ``context`` | Grounding text; fabrications are measured relative to it. Rendered as a distinct ``# Context`` prompt section. |
        | ``threshold`` | Optional override of the preset's built-in ``7.0`` threshold. |
        | ``judge_adapter`` / ``judge_model`` / ``**adapter_kwargs`` | Standard judge pass-through. |

        Returns ``JudgeScore`` (``rubric_source="preset:hallucination"``, ``calibrated=False``).

        Example:
        | ${score} =    `Judge.Get Hallucination Score`    result=${result}    context=${source_document}
        | Should Be True    ${score.pass_threshold_met}    # high grounding score == low hallucination == pass

        Notes:
        - add-judge-criteria-shortcuts D4 (higher-is-better polarity) + D3 (preset registry).
        - Tier-2 LLM-deterministic; cost guardrails per ADR-015.
        - Uncalibrated-by-default per add-judge-criteria-shortcuts D5.
        """
        return self._score_with_preset(
            preset="hallucination",
            result=result,
            extra_sections=(("Context", context),),
            threshold=threshold,
            judge_adapter=judge_adapter,
            judge_model=judge_model,
            adapter_kwargs=adapter_kwargs,
        )

    @keyword(name="Judge.Get Preset Rubric")
    @tier(1)
    def get_preset_rubric(self, *, name: str) -> JudgeRubric:
        """Returns the parsed `JudgeRubric` for a named metric preset (add-judge-criteria-shortcuts).

        [Tier 1 — Deterministic] — pure registry lookup + parse; NO LLM call
        (hence no `@guarded_fanout`). This is the graduation path: feed the
        returned rubric straight into `Judge.Calibrate Rubric` (which already
        accepts a `JudgeRubric` instance) to calibrate a preset against YOUR
        own labeled data — no preset-specific calibration machinery required.

        | =Arguments= | =Description= |
        | ``name`` | One of the registered preset names: ``faithfulness``, ``answer_relevancy``, ``hallucination``. |

        Returns the parsed ``JudgeRubric`` (threshold ``7.0``).

        Raises ``InvalidJudgeRubricError`` (listing available presets) on an
        unknown ``name`` — fail-loud, no silent fallback.

        Example:
        | ${rubric} =    `Judge.Get Preset Rubric`    name=faithfulness
        | ${report} =    `Judge.Calibrate Rubric`    rubric=${rubric}    calibration_set=${CURDIR}/faithfulness-calibration.yaml
        | Should Be True    ${report.passes_hard_fail}

        Notes:
        - add-judge-criteria-shortcuts D3 (preset registry) + D5 (uncalibrated-by-default graduation).
        - Presets ship NO κ claims; calibration is against the operator's own labels.
        """
        return get_preset_rubric(name)

    @keyword(name="Judge Score Should Be Above")
    @tier(2)
    @guarded_fanout()
    def judge_score_should_be_above(
        self,
        *,
        result: AgentRunResult,
        criteria: str,
        threshold: float = 7.0,
        judge_adapter: str = "generic",
        judge_model: str | None = None,
        **adapter_kwargs: Any,
    ) -> JudgeScore:
        """Judge-and-assert in one line: fails the test when the criteria score is below threshold (add-judge-criteria-shortcuts).

        [Tier 2 — Stochastic Single-Shot] — assertion form (un-namespaced,
        matching the `AssertionsLibrary` ``X Should ...`` idiom) that lives on
        the judge library because it makes an LLM call (`AssertionsLibrary` is a
        Tier-1 surface). Runs the SAME criteria-string scoring path as
        `Judge.Score With Criteria`, then fails when the score does not meet the
        threshold. Wraps `@guarded_fanout` cost+runtime guardrails per ADR-015.

        Threshold semantics: the pass comparison is ``numeric_score >= threshold``
        (``>=``, matching ``pass_threshold_met`` project-wide — NOT a strict
        ``>`` despite the name "Above"). A score exactly equal to the threshold
        PASSES.

        On failure the message includes the numeric score, the threshold, the
        uncalibrated marker (``calibrated=False`` / ``rubric_source``), and the
        judge's ``reasoning``. On success it RETURNS the `JudgeScore` so callers
        can log/inspect without a second LLM call.

        | =Arguments= | =Description= |
        | ``result`` | The `AgentRunResult` to evaluate. |
        | ``criteria`` | Plain-language evaluation instruction (same as `Judge.Score With Criteria`). Empty/nullish raises before any LLM call. |
        | ``threshold`` | Pass threshold in ``[0.0, 10.0]`` (default ``7.0``); ``>=`` comparison. |
        | ``judge_adapter`` / ``judge_model`` / ``**adapter_kwargs`` | Standard judge pass-through. |

        Returns the ``JudgeScore`` on pass (``calibrated=False``,
        ``rubric_source="criteria_string"``).

        Raises ``AssertionError`` (RF test failure) when
        ``numeric_score < threshold``.
        Raises ``InvalidJudgeRubricError`` on empty/nullish criteria or
        out-of-range threshold (before any LLM call).

        Example:
        | ${score} =    `Judge Score Should Be Above`    result=${result}    criteria=Response is polite and answers the question    threshold=7
        | Log    Passed with ${score.numeric_score}

        Notes:
        - add-judge-criteria-shortcuts D6 (assertion form on the Tier-2 judge library).
        - `>=` semantics match `pass_threshold_met` (single threshold model library-wide).
        - Uncalibrated by design — the failure message restates the marker (`DF-JCS-S1` / C104).
        """
        rubric = _synthesize_criteria_rubric(criteria, threshold)
        _warn_uncalibrated_once("criteria_string")
        score = _execute_judge(
            rubric,
            result,
            adapter_slug=judge_adapter,
            judge_model=judge_model,
            rubric_source="criteria_string",
            adapter_kwargs=adapter_kwargs,
        )
        if not score.pass_threshold_met:
            raise AssertionError(
                f"Judge score {score.numeric_score} is below threshold {threshold} "
                f"(calibrated={score.calibrated}, rubric_source={score.rubric_source}). "
                f"Judge reasoning: {score.reasoning}"
            )
        return score

    # ----------------------------------------------------------------------- #
    # add-judge-criteria-shortcuts — shared preset-scoring helper              #
    # ----------------------------------------------------------------------- #

    def _score_with_preset(
        self,
        *,
        preset: str,
        result: AgentRunResult,
        extra_sections: tuple[tuple[str, str], ...],
        threshold: float | None,
        judge_adapter: str,
        judge_model: str | None,
        adapter_kwargs: dict[str, Any],
    ) -> JudgeScore:
        """Shared body for the three preset keywords (add-judge-criteria-shortcuts D3).

        Loads the preset rubric, applies an optional threshold override, warns
        once, and runs the judge with the preset's extra prompt section
        (``# Context`` / ``# Question``).
        """
        rubric = get_preset_rubric(preset)
        if threshold is not None:
            rubric = _with_threshold(rubric, threshold)
        rubric_source = f"preset:{preset}"
        _warn_uncalibrated_once(rubric_source)
        return _execute_judge(
            rubric,
            result,
            adapter_slug=judge_adapter,
            judge_model=judge_model,
            rubric_source=rubric_source,
            extra_sections=extra_sections,
            adapter_kwargs=adapter_kwargs,
        )


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #


_THRESHOLD_LINE_RE = re.compile(
    r"Pass\s+if\s+numeric_score\s*>=\s*[0-9]+(?:\.[0-9]+)?", re.IGNORECASE
)
"""Matches the `## Threshold` body line so a preset threshold override can be
reflected in the synthesized `raw_text` shown to the judge (not just the
`JudgeRubric.threshold` field used for `pass_threshold_met`)."""


_UNCALIBRATED_WARNING_EMITTED = False
"""Module-level once-flag for the uncalibrated-shortcut-score WARN.

Process-scoped (add-judge-criteria-shortcuts D2): the first shortcut score per
process warns at WARN; subsequent ones log at INFO to avoid flooding cohort
fan-outs. Parallel pabot workers each warn once (documented, acceptable). The
durable per-score signal is `JudgeScore.calibrated` / `rubric_source`; the log
line is a courtesy.
"""


def _reset_uncalibrated_warning_for_tests() -> None:
    """Reset the module-level WARN once-flag (test-only helper)."""
    global _UNCALIBRATED_WARNING_EMITTED
    _UNCALIBRATED_WARNING_EMITTED = False


def _warn_uncalibrated_once(rubric_source: str) -> None:
    """Emit the uncalibrated-shortcut-score warning (WARN once, INFO thereafter).

    add-judge-criteria-shortcuts D2: names the ``rubric_source``, states the
    score is uncalibrated, and points at the calibration recipe as the
    graduation path for CI gates.
    """
    global _UNCALIBRATED_WARNING_EMITTED
    message = (
        f"Uncalibrated judge score (rubric_source={rubric_source}). Fine for "
        f"exploration; for CI gates graduate to a calibrated rubric (Cohen's "
        f"kappa >= 0.7) — see docs/recipes/judge-calibration.md"
    )
    if not _UNCALIBRATED_WARNING_EMITTED:
        logger.warn(message)
        _UNCALIBRATED_WARNING_EMITTED = True
    else:
        logger.info(message)


def _synthesize_criteria_rubric(criteria: str, threshold: float) -> JudgeRubric:
    """Synthesize a `JudgeRubric` from a plain-language criteria string (add-judge-criteria-shortcuts D1).

    Builds standard-format Markdown ``raw_text`` (a single ``user_criteria``
    bullet + ``## Threshold`` line) and parses it back through the shared
    `parse_rubric_text` so the criteria-string path, file rubrics, and preset
    rubrics all share ONE validation path — and the synthesized rubric can
    itself be calibrated later without rewriting anything.

    Validation (fail-loud, BEFORE any LLM call): empty / whitespace-only /
    nullish (`None`-string) ``criteria`` raises `InvalidJudgeRubricError`;
    an out-of-range ``threshold`` raises via `parse_rubric_text`
    (per `feedback_nullish_input_fuzz_checklist`).
    """
    stripped = (criteria or "").strip()
    if not stripped or stripped.lower() == "none":
        raise InvalidJudgeRubricError(
            f"Judge criteria string is empty or nullish: {criteria!r}",
            file_path="<criteria_string>",
            line_number=None,
            field_name="criteria",
            fix_suggestion=(
                "Pass a non-empty plain-language criteria string, e.g. "
                "`criteria=Response is polite and answers the question`."
            ),
        )
    # Collapse internal whitespace/newlines so the single synthesized bullet
    # stays well-formed for the line-oriented `## Criteria` bullet parser
    # (G-Eval criteria are one-liners by idiom).
    one_line = " ".join(stripped.split())
    raw_text = (
        "# Criteria-string rubric (synthesized)\n\n"
        "## Criteria\n"
        f"- user_criteria: {one_line}\n\n"
        "## Threshold\n"
        f"Pass if numeric_score >= {threshold}\n"
    )
    return parse_rubric_text(raw_text, source="<criteria_string>")


def _with_threshold(rubric: JudgeRubric, threshold: float) -> JudgeRubric:
    """Return a copy of ``rubric`` with an overridden threshold.

    Rewrites the ``## Threshold`` body line in ``raw_text`` so the judge prompt
    and the `JudgeRubric.threshold` field agree. An out-of-range ``threshold``
    raises the SAME structured `InvalidJudgeRubricError` (source/field/
    fix_suggestion) that criteria-string synthesis surfaces via
    `parse_rubric_text` — NOT the bare dataclass `ValueError` from
    `JudgeRubric.__post_init__` — so the preset threshold-override path gives
    Robot/Python callers the public rubric error shape before any LLM call
    (add-judge-criteria-shortcuts codex LOW).
    """
    if not 0.0 <= threshold <= 10.0:
        raise InvalidJudgeRubricError(
            f"Judge rubric threshold {threshold} outside `[0.0, 10.0]` range (<preset_threshold_override>)",
            file_path="<preset_threshold_override>",
            line_number=None,
            field_name="## Threshold",
            fix_suggestion="Use a threshold in [0.0, 10.0]; the JudgeScore range is `0.0 - 10.0`.",
        )
    new_raw = _THRESHOLD_LINE_RE.sub(f"Pass if numeric_score >= {threshold}", rubric.raw_text)
    return JudgeRubric(criteria=rubric.criteria, threshold=threshold, raw_text=new_raw)


def _execute_judge(
    rubric: JudgeRubric,
    result: AgentRunResult,
    *,
    adapter_slug: str,
    judge_model: str | None,
    rubric_source: str,
    adapter_kwargs: dict[str, Any],
    extra_sections: tuple[tuple[str, str], ...] = (),
) -> JudgeScore:
    """Resolve the adapter, compose the prompt, run the judge, and parse the score.

    Shared by `Judge.Get Score` and every add-judge-criteria-shortcuts keyword
    so all sources funnel through one adapter-invocation + parse path. When
    ``extra_sections`` is empty the composed prompt is byte-identical to the
    pre-change composition (regression-guarded).
    """
    adapter_cls = get_adapter(adapter_slug)
    adapter = adapter_cls()

    judge_prompt = _compose_judge_prompt(rubric, result, extra_sections=extra_sections)

    # Story 11.1 + 11.2 + 11.3 cross-LLM review lessons applied UPSTREAM:
    # forward model + kwargs cleanly; defensive parse on response.
    run_kwargs: dict[str, Any] = dict(adapter_kwargs)
    if judge_model is not None:
        run_kwargs["model"] = judge_model
    judge_run = adapter.run(prompt=judge_prompt, **run_kwargs)

    return _parse_judge_response(judge_run, rubric, rubric_source=rubric_source)


_SYSTEM_PROMPT = (
    "You are an LLM judge evaluating an agent's response against a rubric. "
    "Return ONLY a single valid JSON object with the following exact shape, "
    "no markdown fences, no commentary:\n"
    "{\n"
    '  "numeric_score": <float 0.0 to 10.0>,\n'
    '  "reasoning": "<string narrative>",\n'
    '  "criteria_breakdown": {"<criterion_name>": <float 0.0 to 10.0>, ...}\n'
    "}\n"
    "Numeric scores MUST be in [0.0, 10.0]. The criteria_breakdown MUST "
    "include every criterion name from the rubric."
)


def _compose_judge_prompt(
    rubric: JudgeRubric,
    result: AgentRunResult,
    *,
    extra_sections: tuple[tuple[str, str], ...] = (),
) -> str:
    """Assemble the single-shot prompt sent to the judge LLM.

    ``extra_sections`` (add-judge-criteria-shortcuts D7) is a sequence of
    ``(title, body)`` pairs rendered as ``# <title>`` blocks BETWEEN the rubric
    and the agent response (e.g. ``# Question`` / ``# Context`` for presets).
    Pure-additive: with the default empty sequence the output is byte-identical
    to the pre-change composition, preserving Tier-2 seed+temperature=0
    reproducibility for existing suites.
    """
    parts: list[str] = [
        _SYSTEM_PROMPT,
        "",
        "# Rubric",
        rubric.raw_text.strip(),
    ]

    for title, body in extra_sections:
        parts.extend(["", f"# {title}", body])

    parts.extend(
        [
            "",
            "# Agent Response",
            result.response_text or "(empty response)",
        ]
    )

    # Include a brief tool-call trajectory summary so the judge can score
    # behavioral criteria (not just text). Phase-1: just the tool names in order.
    if result.tool_calls:
        tool_summary = ", ".join(tc.name for tc in result.tool_calls)
        parts.extend(["", "# Tool calls (in order)", tool_summary])

    return "\n".join(parts)


def _parse_judge_response(
    judge_run: AgentRunResult,
    rubric: JudgeRubric,
    *,
    rubric_source: str = "file",
) -> JudgeScore:
    """Parse the LLM judge response text as `JudgeScore` JSON.

    Phase-1: NO retry loop. If the LLM returns malformed JSON or missing
    required fields, raise `JudgeOutputParseError` per the M_R11 fail-
    loud pattern. The operator's seed+temperature=0 should make this
    deterministic; failure here indicates the judge prompt or model
    needs tuning, not silent recovery.
    """
    raw_response = judge_run.response_text or ""
    cost_usd = judge_run.cost_usd if judge_run.cost_usd is not None else 0.0

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise JudgeOutputParseError(
            f"Judge LLM response is not valid JSON: {exc.msg}",
            raw_response=raw_response,
            parse_error=str(exc),
            fix_suggestion=(
                "Verify the judge model + seed + temperature=0. If the model still "
                "produces non-JSON, switch judge_adapter/judge_model OR add a "
                "system-prompt nudge."
            ),
        ) from exc

    if not isinstance(parsed, dict):
        raise JudgeOutputParseError(
            f"Judge LLM response parsed as JSON but is not a JSON object (got {type(parsed).__name__})",
            raw_response=raw_response,
            parse_error="top-level JSON value is not an object",
            fix_suggestion="Tune the judge prompt so the model returns a single JSON object, not an array/scalar.",
        )

    # Required fields per AC-12.1.2.
    for required_field in ("numeric_score", "reasoning"):
        if required_field not in parsed:
            raise JudgeOutputParseError(
                f"Judge LLM response missing required field {required_field!r}",
                raw_response=raw_response,
                parse_error=f"missing field: {required_field}",
                fix_suggestion=f"Tune the judge prompt so the model includes {required_field!r}.",
            )

    # Boolean check BEFORE float() — `bool` is an `int` subclass, so
    # `float(True) == 1.0` / `float(False) == 0.0` cast cleanly and would
    # silently coerce a JSON boolean into a 0.0/1.0 score
    # (`feedback_nullish_input_fuzz_checklist`).
    if isinstance(parsed["numeric_score"], bool):
        raise JudgeOutputParseError(
            f"Judge LLM `numeric_score` is a boolean, not a number: {parsed['numeric_score']!r}",
            raw_response=raw_response,
            parse_error="numeric_score is bool, not number",
            fix_suggestion="Tune the judge prompt to return a float for `numeric_score` (0-10).",
        )

    try:
        numeric_score = float(parsed["numeric_score"])
    except (TypeError, ValueError) as exc:
        raise JudgeOutputParseError(
            f"Judge LLM `numeric_score` not numeric: {parsed['numeric_score']!r}",
            raw_response=raw_response,
            parse_error=str(exc),
            fix_suggestion="Tune the judge prompt to return a numeric `numeric_score` (0-10).",
        ) from exc

    # Range check — re-wrap `ValueError` from `JudgeScore.__post_init__`
    # into the documented `JudgeOutputParseError` to honour the
    # error-class-hierarchy.md L25 boundary contract: untrusted LLM
    # runtime data crossing a public keyword boundary must surface as an
    # `AgentEvalError` leaf (consumers `except JudgeOutputParseError`
    # should catch this, not a bare `ValueError`).
    if not 0.0 <= numeric_score <= 10.0:
        raise JudgeOutputParseError(
            f"Judge LLM `numeric_score` out of range [0.0, 10.0]: {numeric_score!r}",
            raw_response=raw_response,
            parse_error="numeric_score out of [0.0, 10.0]",
            fix_suggestion="Tune the judge prompt to return numeric_score in [0.0, 10.0].",
        )

    reasoning = str(parsed["reasoning"])
    criteria_breakdown_raw = parsed.get("criteria_breakdown", {})
    if not isinstance(criteria_breakdown_raw, dict):
        raise JudgeOutputParseError(
            f"Judge LLM `criteria_breakdown` not a JSON object (got {type(criteria_breakdown_raw).__name__})",
            raw_response=raw_response,
            parse_error="criteria_breakdown is not an object",
            fix_suggestion="Tune the judge prompt so `criteria_breakdown` is a `{name: score}` object.",
        )

    # Coerce all criterion values to float (defensive — LLMs sometimes return
    # strings or ints; our JudgeScore dataclass expects floats).
    criteria_breakdown: dict[str, float] = {}
    for crit_name, crit_value in criteria_breakdown_raw.items():
        try:
            criteria_breakdown[str(crit_name)] = float(crit_value)
        except (TypeError, ValueError) as exc:
            raise JudgeOutputParseError(
                f"Judge LLM criterion {crit_name!r} value not numeric: {crit_value!r}",
                raw_response=raw_response,
                parse_error=str(exc),
                fix_suggestion="Tune the judge prompt so each criterion in `criteria_breakdown` has a numeric value.",
            ) from exc

    pass_threshold_met = numeric_score >= rubric.threshold

    return JudgeScore(
        numeric_score=numeric_score,
        pass_threshold_met=pass_threshold_met,
        reasoning=reasoning,
        criteria_breakdown=criteria_breakdown,
        cost_usd=cost_usd,
        # add-judge-criteria-shortcuts D2: `calibrated` is never True in this
        # change (nothing threads calibration evidence yet — `DF-JCS-S1` / C104);
        # `rubric_source` records honest provenance.
        calibrated=False,
        rubric_source=rubric_source,
    )


# --------------------------------------------------------------------------- #
# Story 12.2 — calibration helpers                                              #
# --------------------------------------------------------------------------- #


_THRESHOLD_SWEEP: tuple[float, ...] = (5.0, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0)
"""Candidate thresholds for the `Judge.Calibrate Rubric` precision/recall sweep.

A coarser-than-finest sweep keeps `threshold_tuning` legible in user
output; covers the typical "lenient" (5.0) to "strict" (9.0) operator
range. Per Story 12.2 design — finer granularity is DF-12.2-S2 carry-over.
"""


def _sweep_thresholds(
    judge_scores: list[float],
    human_labels: list[float],
    rubric_threshold: float,
) -> dict[float, dict[str, float]]:
    """Compute precision/recall/F1 at each candidate threshold.

    Always includes the rubric's configured `rubric_threshold` in the sweep
    set so `recommended_threshold` is guaranteed to be a key in the returned
    `tuning` dict (Story 12.2 2-way HIGH/MED — Sonnet MED-2 + Opus MED-2;
    the cookbook explicitly tells operators to inspect
    `threshold_tuning[recommended_threshold]`, which would `KeyError` if
    the rubric's threshold isn't in the sweep set).

    Pass label = `score >= threshold`. F1 = 2 * P * R / (P + R) (or 0 if
    P+R == 0). Pure-Python — no scipy dependency.
    """
    sweep_set = sorted({*_THRESHOLD_SWEEP, rubric_threshold})
    tuning: dict[float, dict[str, float]] = {}
    for threshold in sweep_set:
        judge_bin = [1 if s >= threshold else 0 for s in judge_scores]
        human_bin = [1 if h >= threshold else 0 for h in human_labels]
        tp = sum(1 for j, h in zip(judge_bin, human_bin, strict=True) if j == 1 and h == 1)
        fp = sum(1 for j, h in zip(judge_bin, human_bin, strict=True) if j == 1 and h == 0)
        fn = sum(1 for j, h in zip(judge_bin, human_bin, strict=True) if j == 0 and h == 1)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        tuning[threshold] = {"precision": precision, "recall": recall, "f1": f1}
    return tuning


def _select_f1_max_threshold(tuning: dict[float, dict[str, float]], fallback_threshold: float) -> float:
    """Return the threshold with the highest F1 in `tuning`.

    Ties broken by lower threshold (more lenient — favours recall). If all
    F1 are 0 (e.g., no rows pass at any threshold), returns `fallback_threshold`
    (typically the rubric's configured threshold) so the report doesn't
    silently recommend an arbitrary value.
    """
    best_threshold = fallback_threshold
    best_f1 = -1.0
    for threshold in sorted(tuning.keys()):
        f1 = tuning[threshold]["f1"]
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
    if best_f1 <= 0.0:
        return fallback_threshold
    return best_threshold


def _diagnose_systematic_bias(judge_scores: list[float], human_labels: list[float]) -> tuple[str, ...]:
    """Surface human-readable systematic-bias bullets.

    Phase-1 diagnostics:
    - Mean delta: judge minus human, if |delta| > 1.0
    - Variance ratio: judge vs human, if judge variance >> human variance
      (judge over-spreads) or vice versa

    Returns an empty tuple if no notable patterns.
    """
    if not judge_scores or not human_labels:
        return ()
    n = len(judge_scores)
    mean_judge = sum(judge_scores) / n
    mean_human = sum(human_labels) / n
    delta = mean_judge - mean_human
    bullets: list[str] = []
    if abs(delta) > 1.0:
        direction = "above" if delta > 0 else "below"
        bullets.append(
            f"Judge mean score ({mean_judge:.2f}) consistently {direction} "
            f"human mean ({mean_human:.2f}) by {abs(delta):.2f} points."
        )
    if n > 1:
        var_judge = sum((s - mean_judge) ** 2 for s in judge_scores) / n
        var_human = sum((h - mean_human) ** 2 for h in human_labels) / n
        if var_human > 0:
            ratio = var_judge / var_human
            if ratio > 2.0:
                bullets.append(
                    f"Judge score variance ({var_judge:.2f}) is {ratio:.1f}x human "
                    f"variance ({var_human:.2f}) — judge over-spreads."
                )
            elif ratio == 0.0:
                bullets.append(
                    f"Judge score variance is 0.00 (all {n} judge scores equal) — "
                    f"judge under-discriminates entirely against human variance "
                    f"({var_human:.2f})."
                )
            elif ratio < 0.5:
                bullets.append(
                    f"Judge score variance ({var_judge:.2f}) is {1 / ratio:.1f}x SMALLER than "
                    f"human variance ({var_human:.2f}) — judge under-discriminates."
                )
    return tuple(bullets)
