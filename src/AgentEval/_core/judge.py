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

"""The LLM judge: rubric in, score out.

Parse a Markdown rubric (or a one-line criteria string), compose a judge
prompt, call the adapter, and read back a strict JSON score. That is the whole
job - no calibration, no kappa sweeps, no uncalibrated-warning bookkeeping.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from AgentEval._core.adapter import Adapter, get_adapter
from AgentEval._core.errors import InvalidRubricError, JudgeOutputParseError
from AgentEval._core.types import AgentRunResult

__all__ = [
    "JudgeRubric",
    "JudgeScore",
    "load_rubric",
    "parse_rubric_text",
    "rubric_from_criteria",
    "compose_judge_prompt",
    "parse_judge_response",
    "score",
]


@dataclass(frozen=True)
class JudgeRubric:
    """A parsed rubric: named criteria, a pass threshold, and the raw text."""

    criteria: tuple[tuple[str, str], ...]
    threshold: float
    raw_text: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 10.0:
            raise ValueError(f"threshold must be in [0.0, 10.0]; got {self.threshold!r}")
        if not self.criteria:
            raise ValueError("a rubric must have at least one criterion")


@dataclass(frozen=True)
class JudgeScore:
    """The judge's verdict for one response."""

    numeric_score: float
    pass_threshold_met: bool
    reasoning: str
    criteria_breakdown: Mapping[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.numeric_score <= 10.0:
            raise ValueError(f"numeric_score must be in [0.0, 10.0]; got {self.numeric_score!r}")
        if self.cost_usd < 0.0:
            raise ValueError(f"cost_usd must be non-negative; got {self.cost_usd!r}")
        object.__setattr__(self, "criteria_breakdown", dict(self.criteria_breakdown))


# --------------------------------------------------------------------------- #
# Rubric parsing                                                               #
# --------------------------------------------------------------------------- #

_THRESHOLD_RE = re.compile(r"Pass\s+if\s+numeric_score\s*>=\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_CRITERIA_HEADER_RE = re.compile(r"^##\s+Criteria\s*$", re.MULTILINE)
_THRESHOLD_HEADER_RE = re.compile(r"^##\s+Threshold\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^-\s+([^:]+?)\s*:\s*(.+?)\s*$")
_NEXT_HEADER_RE = re.compile(r"^##\s+", re.MULTILINE)


def load_rubric(path: str | Path) -> JudgeRubric:
    """Load and parse a ``.md`` rubric file."""
    rubric_path = Path(path)
    if rubric_path.suffix != ".md":
        raise InvalidRubricError(
            f"rubric file must be Markdown (.md); got {rubric_path.suffix!r}",
            source=str(rubric_path),
            fix="Rename the rubric to a .md file.",
        )
    if not rubric_path.exists():
        raise InvalidRubricError(
            f"rubric file not found: {rubric_path}",
            source=str(rubric_path),
            fix="Create the rubric with `## Criteria` and `## Threshold` sections.",
        )
    return parse_rubric_text(rubric_path.read_text(encoding="utf-8"), source=str(rubric_path))


def parse_rubric_text(raw_text: str, *, source: str) -> JudgeRubric:
    """Parse rubric Markdown into a ``JudgeRubric``.

    Requires a ``## Criteria`` section (one ``- name: description`` bullet each)
    and a ``## Threshold`` section (``Pass if numeric_score >= <N>``).
    """
    if not _CRITERIA_HEADER_RE.search(raw_text):
        raise InvalidRubricError(
            f"rubric missing a `## Criteria` section ({source})",
            source=source,
            field="## Criteria",
            fix="Add a `## Criteria` section with `- name: description` bullets.",
        )
    if not _THRESHOLD_HEADER_RE.search(raw_text):
        raise InvalidRubricError(
            f"rubric missing a `## Threshold` section ({source})",
            source=source,
            field="## Threshold",
            fix="Add `## Threshold` with a line: `Pass if numeric_score >= 7.0`.",
        )

    criteria = _parse_criteria_bullets(raw_text, source)

    threshold_section = _slice_section(raw_text, _THRESHOLD_HEADER_RE)
    threshold_match = _THRESHOLD_RE.search(threshold_section)
    if threshold_match is None:
        raise InvalidRubricError(
            f"rubric `## Threshold` unparseable; expected `Pass if numeric_score >= <N>` ({source})",
            source=source,
            field="## Threshold",
            fix="Use a line like `Pass if numeric_score >= 7.0`.",
        )
    threshold = float(threshold_match.group(1))
    if not 0.0 <= threshold <= 10.0:
        raise InvalidRubricError(
            f"rubric threshold {threshold} outside [0.0, 10.0] ({source})",
            source=source,
            field="## Threshold",
            fix="Use a threshold in [0.0, 10.0].",
        )

    return JudgeRubric(criteria=tuple(criteria), threshold=threshold, raw_text=raw_text)


def rubric_from_criteria(criteria: str, threshold: float = 7.0) -> JudgeRubric:
    """Synthesize a one-criterion rubric from a plain-language criteria string.

    The on-ramp form: the string is the instruction, scored as a whole. Empty
    or nullish input raises before any LLM call.
    """
    stripped = (criteria or "").strip()
    if not stripped or stripped.lower() == "none":
        raise InvalidRubricError(
            f"criteria string is empty or nullish: {criteria!r}",
            source="<criteria_string>",
            field="criteria",
            fix="Pass a non-empty criteria string, e.g. `Response is polite and answers the question`.",
        )
    one_line = " ".join(stripped.split())
    raw_text = (
        "# Criteria-string rubric\n\n"
        "## Criteria\n"
        f"- criteria: {one_line}\n\n"
        "## Threshold\n"
        f"Pass if numeric_score >= {threshold}\n"
    )
    return parse_rubric_text(raw_text, source="<criteria_string>")


def _slice_section(raw_text: str, header_re: re.Pattern[str]) -> str:
    """Return a section body (header to next `##` header or EOF)."""
    header_match = header_re.search(raw_text)
    if header_match is None:
        return ""
    start = header_match.end()
    next_header = _NEXT_HEADER_RE.search(raw_text[start:])
    end = start + next_header.start() if next_header else len(raw_text)
    return raw_text[start:end]


def _parse_criteria_bullets(raw_text: str, source: str) -> list[tuple[str, str]]:
    """Extract `- name: description` bullets from the `## Criteria` section."""
    section = _slice_section(raw_text, _CRITERIA_HEADER_RE)
    criteria: list[tuple[str, str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        match = _BULLET_RE.match(stripped)
        if match is None:
            raise InvalidRubricError(
                f"rubric criterion bullet malformed (want `- name: description`): {stripped!r} ({source})",
                source=source,
                field=stripped,
                fix="Format each bullet as `- name: description`.",
            )
        criteria.append((match.group(1).strip(), match.group(2).strip()))
    if not criteria:
        raise InvalidRubricError(
            f"rubric `## Criteria` has no bullets ({source})",
            source=source,
            field="## Criteria",
            fix="Add at least one `- name: description` bullet.",
        )
    return criteria


# --------------------------------------------------------------------------- #
# Prompt compose + response parse                                             #
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = (
    "You are an LLM judge evaluating an agent's response against a rubric. "
    "Return ONLY a single valid JSON object with this exact shape, no markdown "
    "fences, no commentary:\n"
    "{\n"
    '  "numeric_score": <float 0.0 to 10.0>,\n'
    '  "reasoning": "<string>",\n'
    '  "criteria_breakdown": {"<criterion_name>": <float 0.0 to 10.0>, ...}\n'
    "}\n"
    "Scores MUST be in [0.0, 10.0]. Include every criterion name from the rubric."
)


def compose_judge_prompt(
    rubric: JudgeRubric,
    response_text: str,
    *,
    extra_sections: tuple[tuple[str, str], ...] = (),
) -> str:
    """Assemble the single-shot prompt sent to the judge.

    ``extra_sections`` renders ``(title, body)`` pairs as ``# title`` blocks
    between the rubric and the response (e.g. ``# Context`` for grounding).
    """
    parts: list[str] = [_SYSTEM_PROMPT, "", "# Rubric", rubric.raw_text.strip()]
    for title, body in extra_sections:
        parts.extend(["", f"# {title}", body])
    parts.extend(["", "# Agent Response", response_text or "(empty response)"])
    return "\n".join(parts)


def parse_judge_response(raw_response: str, rubric: JudgeRubric, *, cost_usd: float = 0.0) -> JudgeScore:
    """Parse the judge's raw text as a ``JudgeScore``. No retries - fail loud."""
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise JudgeOutputParseError(
            f"judge response is not valid JSON: {exc.msg}",
            raw_response=raw_response,
            fix="Check the judge model with seed + temperature=0, or nudge the system prompt.",
        ) from exc

    if not isinstance(parsed, dict):
        raise JudgeOutputParseError(
            f"judge response is JSON but not an object (got {type(parsed).__name__})",
            raw_response=raw_response,
            fix="Tune the prompt so the model returns a single JSON object.",
        )

    for required in ("numeric_score", "reasoning"):
        if required not in parsed:
            raise JudgeOutputParseError(
                f"judge response missing required field {required!r}",
                raw_response=raw_response,
                fix=f"Tune the prompt so the model includes {required!r}.",
            )

    raw_score = parsed["numeric_score"]
    if isinstance(raw_score, bool):
        raise JudgeOutputParseError(
            f"numeric_score is a boolean, not a number: {raw_score!r}",
            raw_response=raw_response,
            fix="Tune the prompt to return a float for numeric_score.",
        )
    try:
        numeric_score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise JudgeOutputParseError(
            f"numeric_score is not numeric: {raw_score!r}",
            raw_response=raw_response,
            fix="Tune the prompt to return a numeric numeric_score (0-10).",
        ) from exc
    if not 0.0 <= numeric_score <= 10.0:
        raise JudgeOutputParseError(
            f"numeric_score out of range [0.0, 10.0]: {numeric_score!r}",
            raw_response=raw_response,
            fix="Tune the prompt to keep numeric_score in [0.0, 10.0].",
        )

    breakdown_raw = parsed.get("criteria_breakdown", {})
    if not isinstance(breakdown_raw, dict):
        raise JudgeOutputParseError(
            f"criteria_breakdown is not an object (got {type(breakdown_raw).__name__})",
            raw_response=raw_response,
            fix="Tune the prompt so criteria_breakdown is a {name: score} object.",
        )
    criteria_breakdown: dict[str, float] = {}
    for crit_name, crit_value in breakdown_raw.items():
        try:
            criteria_breakdown[str(crit_name)] = float(crit_value)
        except (TypeError, ValueError) as exc:
            raise JudgeOutputParseError(
                f"criterion {crit_name!r} value is not numeric: {crit_value!r}",
                raw_response=raw_response,
                fix="Tune the prompt so each criterion has a numeric value.",
            ) from exc

    return JudgeScore(
        numeric_score=numeric_score,
        pass_threshold_met=numeric_score >= rubric.threshold,
        reasoning=str(parsed["reasoning"]),
        criteria_breakdown=criteria_breakdown,
        cost_usd=cost_usd,
    )


def score(
    response_text: str,
    rubric: JudgeRubric,
    *,
    adapter: str | Adapter = "generic",
    model: str | None = None,
    extra_sections: tuple[tuple[str, str], ...] = (),
    **adapter_kwargs: Any,
) -> JudgeScore:
    """Judge ``response_text`` against ``rubric`` and return a ``JudgeScore``.

    Resolves the adapter, composes the prompt, runs it, and parses the JSON.
    Pass either an adapter slug or your own adapter object.
    """
    resolved = get_adapter(adapter)
    prompt = compose_judge_prompt(rubric, response_text, extra_sections=extra_sections)
    run_kwargs: dict[str, Any] = dict(adapter_kwargs)
    if model is not None:
        run_kwargs["model"] = model
    run: AgentRunResult = resolved.run(prompt, **run_kwargs)
    return parse_judge_response(run.response_text, rubric, cost_usd=run.cost_usd)
