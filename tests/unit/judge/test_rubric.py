# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `judge/rubric.py` (Story 12.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.errors import InvalidJudgeRubricError
from AgentEval.judge.rubric import load_rubric

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md"


def test_load_rubric_parses_canonical_fixture() -> None:
    """The shipped `skill-quality.md` rubric must round-trip cleanly."""
    rubric = load_rubric(FIXTURE_RUBRIC)
    assert rubric.threshold == 7.0
    assert len(rubric.criteria) == 4
    names = [name for name, _desc in rubric.criteria]
    assert names == ["correctness", "completeness", "tool-use-appropriateness", "response-clarity"]
    assert "Pass if numeric_score >= 7.0" in rubric.raw_text


def test_load_rubric_raises_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(missing)
    assert "not found" in str(exc_info.value)


def test_load_rubric_raises_on_wrong_extension(tmp_path: Path) -> None:
    rubric_txt = tmp_path / "rubric.txt"
    rubric_txt.write_text("# rubric")
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_txt)
    assert "must have `.md` extension" in str(exc_info.value)


def test_load_rubric_raises_on_missing_criteria_section(tmp_path: Path) -> None:
    rubric_md = tmp_path / "no-criteria.md"
    rubric_md.write_text("# Rubric\n\n## Threshold\nPass if numeric_score >= 7.0\n")
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "missing required `## Criteria`" in str(exc_info.value)


def test_load_rubric_raises_on_missing_threshold_section(tmp_path: Path) -> None:
    rubric_md = tmp_path / "no-threshold.md"
    rubric_md.write_text("# Rubric\n\n## Criteria\n- correctness: did it work?\n")
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "missing required `## Threshold`" in str(exc_info.value)


def test_load_rubric_raises_on_malformed_bullet(tmp_path: Path) -> None:
    """Bullet without `: description` separator → InvalidJudgeRubricError."""
    rubric_md = tmp_path / "malformed-bullet.md"
    rubric_md.write_text(
        "# Rubric\n\n## Criteria\n- correctness without colon separator\n\n## Threshold\nPass if numeric_score >= 7.0\n"
    )
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "bullet malformed" in str(exc_info.value)


def test_load_rubric_raises_on_unparseable_threshold(tmp_path: Path) -> None:
    rubric_md = tmp_path / "bad-threshold.md"
    rubric_md.write_text(
        "# Rubric\n\n## Criteria\n- correctness: did it work?\n\n## Threshold\nseven point zero is the threshold\n"
    )
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "unparseable" in str(exc_info.value)


def test_load_rubric_raises_on_threshold_out_of_range(tmp_path: Path) -> None:
    rubric_md = tmp_path / "bad-range.md"
    rubric_md.write_text(
        "# Rubric\n\n## Criteria\n- correctness: did it work?\n\n## Threshold\nPass if numeric_score >= 15.0\n"
    )
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "outside `[0.0, 10.0]`" in str(exc_info.value)


def test_load_rubric_raises_on_empty_criteria_section(tmp_path: Path) -> None:
    rubric_md = tmp_path / "empty-criteria.md"
    rubric_md.write_text("# Rubric\n\n## Criteria\n\n## Threshold\nPass if numeric_score >= 7.0\n")
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "no bullets" in str(exc_info.value)


def test_load_rubric_preserves_raw_text_for_llm_prompt(tmp_path: Path) -> None:
    """`raw_text` is sent to the LLM verbatim — must include Examples section."""
    rubric_md = tmp_path / "with-examples.md"
    rubric_md.write_text(
        "# Rubric\n\n"
        "## Criteria\n- correctness: did it work?\n\n"
        "## Threshold\nPass if numeric_score >= 7.0\n\n"
        "## Examples\n### Example 1\nA short example.\n"
    )
    rubric = load_rubric(rubric_md)
    assert "## Examples" in rubric.raw_text
    assert "Example 1" in rubric.raw_text


def test_load_rubric_threshold_scope_ignores_pass_lines_in_other_sections(tmp_path: Path) -> None:
    """A `Pass if numeric_score >= 9.0` line inside `## Examples` MUST NOT mask
    a malformed `## Threshold` section body.

    Regression for Story 12.1 Tier-2 Opus MED-4: pre-fix `_THRESHOLD_RE.search`
    ran over the whole document; this fixture would have returned threshold=9.0
    (the stray example line) instead of raising `InvalidJudgeRubricError`. Post-
    fix, threshold parsing is scoped to the `## Threshold` section body only.
    """
    rubric_md = tmp_path / "scope-leak.md"
    rubric_md.write_text(
        "# Rubric\n\n"
        "## Criteria\n- correctness: did it work?\n\n"
        "## Threshold\n(intentionally empty — should fail to parse)\n\n"
        "## Examples\nPass if numeric_score >= 9.0 should NOT be treated as the threshold.\n"
    )
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        load_rubric(rubric_md)
    assert "unparseable" in str(exc_info.value)
