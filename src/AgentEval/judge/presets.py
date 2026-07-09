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

# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# ruff: noqa: E501
# Preset `## Criteria` bullets MUST stay on a single physical line — the rubric
# bullet parser (`judge/rubric.py`) is line-oriented (`- <name>: <description>`
# on one line). The verbatim criteria text is intentionally long.

"""Curated built-in judge rubric presets (add-judge-criteria-shortcuts D3).

Named metric presets ship as embedded Markdown rubric constants (NOT packaged
data files) so the rubric text stays grep-able + reviewable in one module and
the "document exactly what each preset measures" requirement is enforceable:
each preset's criteria bullets ARE the documentation, quoted verbatim in the
corresponding keyword docstring.

Exactly three presets ship in this change (scope cap 3-5; start minimal):

| Preset | Extra input | Measures |
|---|---|---|
| ``faithfulness`` | ``context`` | Every factual claim in the response is supported by the supplied context. |
| ``answer_relevancy`` | ``question`` | The response directly addresses the supplied question. |
| ``hallucination`` | ``context`` | Grounding score — HIGHER = better (10.0 = no fabrication relative to the context). |

Honesty (add-judge-criteria-shortcuts D5): presets ship **uncalibrated by
default**. Cohen's κ is a joint property of (rubric × judge model × domain ×
labelers); a calibration set authored against our own labels with one judge
model does not transfer to the user's model + domain, so shipping one and
riding ``calibrated=True`` on it would be exactly the vibes-over-evidence claim
this project brands against. Presets always yield ``calibrated=False``; the
graduation path is `Judge.Get Preset Rubric` → `Judge.Calibrate Rubric` on the
user's own labels (per-preset calibration-set templates live under
``docs/examples/judge-presets/``).

References:
- add-judge-criteria-shortcuts design D3 (embedded-constants registry) + D4
  (hallucination higher-is-better) + D5 (uncalibrated-by-default).
- `judge/rubric.py:parse_rubric_text` — the single shared parser.
"""

from __future__ import annotations

from collections.abc import Mapping

from AgentEval.errors import InvalidJudgeRubricError
from AgentEval.judge.rubric import parse_rubric_text
from AgentEval.judge.types import JudgeRubric

__all__ = ["PRESET_RUBRICS", "get_preset_rubric", "preset_names"]


# --------------------------------------------------------------------------- #
# Embedded preset rubric Markdown (parsed lazily via `parse_rubric_text`).      #
# --------------------------------------------------------------------------- #


_FAITHFULNESS_RUBRIC = """\
# Faithfulness (preset)

## Criteria
- faithfulness: Every factual claim in the response is supported by the supplied grounding context. Penalize each claim that is unsupported, contradicted, or embellished beyond the context, proportionally to how central the claim is to the response. A response that stays strictly within what the context supports scores 10.0.

## Threshold
Pass if numeric_score >= 7.0
"""


_ANSWER_RELEVANCY_RUBRIC = """\
# Answer Relevancy (preset)

## Criteria
- answer_relevancy: The response directly addresses the supplied question: it is on-topic, answers what was actually asked, and does not evade, pad, or drift onto adjacent topics. Penalize non-answers, partial answers that skip the core of the question, and padding that does not advance the answer. A focused response that fully answers the question scores 10.0.

## Threshold
Pass if numeric_score >= 7.0
"""


_HALLUCINATION_RUBRIC = """\
# Hallucination — Grounding Score (preset)

## Criteria
- grounding: Freedom from hallucination as a GROUNDING score where HIGHER IS BETTER. 10.0 = no fabricated entities, facts, citations, or quantities relative to the supplied context; 0.0 = pervasive fabrication. Every named entity, statistic, quotation, or citation in the response must be traceable to the context; each fabricated or unverifiable item lowers the score proportionally. NOTE: this inverts DeepEval's HallucinationMetric (which scores the hallucination proportion, lower-is-better) so the uniform `numeric_score >= threshold` pass semantics hold.

## Threshold
Pass if numeric_score >= 7.0
"""


PRESET_RUBRICS: Mapping[str, str] = {
    "faithfulness": _FAITHFULNESS_RUBRIC,
    "answer_relevancy": _ANSWER_RELEVANCY_RUBRIC,
    "hallucination": _HALLUCINATION_RUBRIC,
}
"""Registry of preset name -> raw Markdown rubric text.

Parsed lazily into a `JudgeRubric` by `get_preset_rubric` (via the shared
`parse_rubric_text`), so a malformed preset fails loudly at first use with the
standard `InvalidJudgeRubricError` shape.
"""


def preset_names() -> tuple[str, ...]:
    """Return the registered preset names in registry order."""
    return tuple(PRESET_RUBRICS)


def get_preset_rubric(name: str) -> JudgeRubric:
    """Return the parsed `JudgeRubric` for a named preset (add-judge-criteria-shortcuts D3).

    Args:
        name: One of the registered preset names (see `preset_names`).

    Returns:
        The parsed `JudgeRubric` for the preset (threshold 7.0), suitable for
        feeding directly to `Judge.Calibrate Rubric` (the graduation path).

    Raises:
        InvalidJudgeRubricError: if ``name`` is not a registered preset. The
            message lists the available preset names (fail-loud, no silent
            fallback).
    """
    raw_text = PRESET_RUBRICS.get(name)
    if raw_text is None:
        available = ", ".join(preset_names())
        raise InvalidJudgeRubricError(
            f"Unknown judge preset {name!r}; available presets: {available}",
            file_path=f"<preset:{name}>",
            line_number=None,
            field_name="",
            fix_suggestion=f"Use one of the registered preset names: {available}.",
        )
    return parse_rubric_text(raw_text, source=f"<preset:{name}>")
