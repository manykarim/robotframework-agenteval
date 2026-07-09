# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `judge/presets.py` (add-judge-criteria-shortcuts D3/D4/D5)."""

from __future__ import annotations

import pytest

from AgentEval.errors import InvalidJudgeRubricError
from AgentEval.judge.presets import PRESET_RUBRICS, get_preset_rubric, preset_names
from AgentEval.judge.rubric import parse_rubric_text
from AgentEval.judge.types import JudgeRubric


def test_exactly_three_presets_ship() -> None:
    """Scope cap: exactly the 3 named presets ship in this change."""
    assert set(preset_names()) == {"faithfulness", "answer_relevancy", "hallucination"}


@pytest.mark.parametrize("name", ["faithfulness", "answer_relevancy", "hallucination"])
def test_each_preset_parses_via_shared_parser(name: str) -> None:
    """Every embedded preset rubric parses via the shared `parse_rubric_text`."""
    rubric = get_preset_rubric(name)
    assert isinstance(rubric, JudgeRubric)
    assert rubric.threshold == 7.0
    assert rubric.criteria  # at least one criterion
    # Same parser used for file rubrics parses the embedded text identically.
    reparsed = parse_rubric_text(PRESET_RUBRICS[name], source=f"<preset:{name}>")
    assert reparsed.criteria == rubric.criteria
    assert reparsed.threshold == rubric.threshold


def test_hallucination_states_higher_is_better() -> None:
    """add-judge-criteria-shortcuts D4: hallucination rubric text states the
    higher-is-better grounding polarity so pass semantics stay uniform."""
    rubric = get_preset_rubric("hallucination")
    assert "HIGHER IS BETTER" in rubric.raw_text
    assert "10.0 = no fabricated" in rubric.raw_text


def test_unknown_preset_lists_available_names() -> None:
    """Unknown preset name fails loud and lists the available presets."""
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        get_preset_rubric("relevance")  # typo of answer_relevancy
    msg = str(exc_info.value)
    assert "faithfulness" in msg
    assert "answer_relevancy" in msg
    assert "hallucination" in msg


def test_no_shipped_kappa_claims_in_preset_text() -> None:
    """add-judge-criteria-shortcuts D5: no preset artifact claims a Cohen's
    kappa value (presets are uncalibrated-by-default)."""
    for name, raw in PRESET_RUBRICS.items():
        lowered = raw.lower()
        assert "kappa" not in lowered, f"preset {name!r} rubric must not claim a kappa value"
        assert "calibrated" not in lowered, f"preset {name!r} rubric must not claim calibration"
