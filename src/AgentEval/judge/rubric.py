# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Markdown rubric loader for the Judge sub-library (Story 12.1)."""

from __future__ import annotations

import re
from pathlib import Path

from AgentEval.errors import InvalidJudgeRubricError
from AgentEval.judge.types import JudgeRubric

__all__ = ["load_rubric"]


_THRESHOLD_RE = re.compile(r"Pass\s+if\s+numeric_score\s*>=\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_CRITERIA_HEADER_RE = re.compile(r"^##\s+Criteria\s*$", re.MULTILINE)
_THRESHOLD_HEADER_RE = re.compile(r"^##\s+Threshold\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^-\s+([^:]+?)\s*:\s*(.+?)\s*$")


def load_rubric(path: str | Path) -> JudgeRubric:
    """Load + parse a Markdown rubric file.

    Phase-1 format: two required sections (``## Criteria`` + ``## Threshold``)
    + an optional ``## Examples`` section preserved verbatim in
    ``JudgeRubric.raw_text`` but not parsed into structured fields.

    Args:
        path: Filesystem path to a ``.md`` rubric file.

    Returns:
        `JudgeRubric` with parsed criteria + threshold + raw text.

    Raises:
        InvalidJudgeRubricError: on file-not-found OR wrong extension OR
            missing required section OR malformed bullet OR unparseable
            threshold. ``field_name`` carries the section header or
            bullet that failed.
    """
    rubric_path = Path(path)

    if rubric_path.suffix != ".md":
        raise InvalidJudgeRubricError(
            f"Judge rubric file must have `.md` extension; got {rubric_path.suffix!r} ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Rename the rubric file to `*.md` (Markdown).",
        )
    if not rubric_path.exists():
        raise InvalidJudgeRubricError(
            f"Judge rubric file not found: {rubric_path}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Create the rubric file with `## Criteria` + `## Threshold` sections.",
        )

    raw_text = rubric_path.read_text(encoding="utf-8")

    # Check required section headers
    if not _CRITERIA_HEADER_RE.search(raw_text):
        raise InvalidJudgeRubricError(
            f"Judge rubric missing required `## Criteria` section ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Criteria",
            fix_suggestion="Add a `## Criteria` section with one bullet per criterion: `- name: description`.",
        )
    if not _THRESHOLD_HEADER_RE.search(raw_text):
        raise InvalidJudgeRubricError(
            f"Judge rubric missing required `## Threshold` section ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Threshold",
            fix_suggestion="Add a `## Threshold` section with a single line: `Pass if numeric_score >= <N>`.",
        )

    # Parse criteria bullets from the `## Criteria` section.
    criteria = _parse_criteria_bullets(raw_text, rubric_path)

    # Parse threshold — search ONLY within the `## Threshold` section body
    # (header → next `##` or EOF), NOT the whole document. A stray
    # "Pass if numeric_score >= 9.0" line in `## Examples` would otherwise
    # silently set the threshold instead of failing the malformed
    # `## Threshold` section.
    threshold_section = _slice_section(raw_text, _THRESHOLD_HEADER_RE)
    threshold_match = _THRESHOLD_RE.search(threshold_section)
    if threshold_match is None:
        raise InvalidJudgeRubricError(
            f"Judge rubric `## Threshold` section is unparseable; expected "
            f"`Pass if numeric_score >= <N>` ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Threshold",
            fix_suggestion="Replace the section body with: `Pass if numeric_score >= 7.0` (or your chosen threshold).",
        )
    try:
        threshold = float(threshold_match.group(1))
    except ValueError as exc:
        raise InvalidJudgeRubricError(
            f"Judge rubric threshold value not a valid float: {threshold_match.group(1)!r} ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Threshold",
            fix_suggestion="Use a numeric threshold value (e.g., `7.0`).",
        ) from exc

    if not 0.0 <= threshold <= 10.0:
        raise InvalidJudgeRubricError(
            f"Judge rubric threshold {threshold} outside `[0.0, 10.0]` range ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Threshold",
            fix_suggestion="Use a threshold in [0.0, 10.0]; the JudgeScore range is `0.0 - 10.0`.",
        )

    return JudgeRubric(
        criteria=tuple(criteria),
        threshold=threshold,
        raw_text=raw_text,
    )


def _slice_section(raw_text: str, header_re: re.Pattern[str]) -> str:
    """Return the body of a Markdown section (header → next `##` header or EOF).

    Used by both `## Criteria` bullet parsing and `## Threshold` value parsing
    to scope regex matches to the documented section, preventing stray
    section-shaped lines elsewhere from masking a malformed section body.
    """
    header_match = header_re.search(raw_text)
    if header_match is None:
        return ""
    section_start = header_match.end()
    next_header = re.search(r"^##\s+", raw_text[section_start:], re.MULTILINE)
    section_end = section_start + next_header.start() if next_header else len(raw_text)
    return raw_text[section_start:section_end]


def _parse_criteria_bullets(raw_text: str, rubric_path: Path) -> list[tuple[str, str]]:
    """Extract `- name: description` bullets from the `## Criteria` section."""
    section_body = _slice_section(raw_text, _CRITERIA_HEADER_RE)

    criteria: list[tuple[str, str]] = []
    for raw_line in section_body.splitlines():
        stripped = raw_line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        match = _BULLET_RE.match(stripped)
        if match is None:
            raise InvalidJudgeRubricError(
                f"Judge rubric `## Criteria` bullet malformed (expected "
                f"`- <name>: <description>`): {stripped!r} ({rubric_path})",
                file_path=str(rubric_path),
                line_number=None,
                field_name=stripped,
                fix_suggestion="Format each criterion bullet as `- <name>: <description>` (single colon separator).",
            )
        criteria.append((match.group(1).strip(), match.group(2).strip()))

    if not criteria:
        raise InvalidJudgeRubricError(
            f"Judge rubric `## Criteria` section has no bullets ({rubric_path})",
            file_path=str(rubric_path),
            line_number=None,
            field_name="## Criteria",
            fix_suggestion="Add at least one bullet: `- <name>: <description>`.",
        )

    return criteria
