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
from pathlib import Path
from typing import Any

from robot.api.deco import keyword, library

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.tier import tier
from AgentEval.errors import JudgeOutputParseError
from AgentEval.judge.rubric import load_rubric
from AgentEval.judge.types import JudgeRubric, JudgeScore
from AgentEval.types import AgentRunResult

__all__ = ["JudgeLibrary"]


@library(scope="GLOBAL")
class JudgeLibrary:
    """`Judge.Get Score` Tier-2 LLM-judge keyword surface (Story 12.1 / PRD FR48).

    Wired via `AgentEval._SUB_LIBRARIES` standard composition path.
    Host-instance budgets (`max_cost_usd` / `max_runtime_seconds`)
    forwarded from `AgentEval.__init__` via `_build_components` (mirrors
    `StatsLibrary` precedent per Story 6.3 AC-6.3.8).
    """

    def __init__(
        self,
        max_cost_usd: float | None = None,
        max_runtime_seconds: float | None = None,
    ) -> None:
        """Library-level cost/runtime budgets per Story 1a.6 + ADR-015.

        Forwarded from top-level `AgentEval(max_cost_usd=...,
        max_runtime_seconds=...)` via `_build_components`. Consumed by
        `@guarded_fanout` on `Judge.Get Score` (Tier-2 LLM-call keyword).
        """
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds

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
        """
        # Load + parse the rubric (or accept a pre-parsed one).
        parsed_rubric = rubric if isinstance(rubric, JudgeRubric) else load_rubric(rubric)

        # Resolve the judge adapter via the standard discovery path.
        adapter_cls = get_adapter(judge_adapter)
        adapter = adapter_cls()

        # Compose the judge prompt: system instructions + rubric + agent response.
        judge_prompt = _compose_judge_prompt(parsed_rubric, result)

        # Run the single-shot judge call.
        # Story 11.1 + 11.2 + 11.3 cross-LLM review lessons applied UPSTREAM:
        # forward model + kwargs cleanly; defensive parse on response.
        run_kwargs: dict[str, Any] = dict(adapter_kwargs)
        if judge_model is not None:
            run_kwargs["model"] = judge_model
        judge_run = adapter.run(prompt=judge_prompt, **run_kwargs)

        # Parse the judge response into a `JudgeScore`.
        return _parse_judge_response(judge_run, parsed_rubric)


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #


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


def _compose_judge_prompt(rubric: JudgeRubric, result: AgentRunResult) -> str:
    """Assemble the single-shot prompt sent to the judge LLM."""
    parts: list[str] = [
        _SYSTEM_PROMPT,
        "",
        "# Rubric",
        rubric.raw_text.strip(),
        "",
        "# Agent Response",
        result.response_text or "(empty response)",
    ]

    # Include a brief tool-call trajectory summary so the judge can score
    # behavioral criteria (not just text). Phase-1: just the tool names in order.
    if result.tool_calls:
        tool_summary = ", ".join(tc.name for tc in result.tool_calls)
        parts.extend(["", "# Tool calls (in order)", tool_summary])

    return "\n".join(parts)


def _parse_judge_response(judge_run: AgentRunResult, rubric: JudgeRubric) -> JudgeScore:
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
    )
