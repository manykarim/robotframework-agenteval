# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Dataclass types for the Judge sub-library (Story 12.1 / PRD FR48).

Per architecture.md L1316 — the Judge sub-package's types live here:
`JudgeRubric` (parsed rubric document) + `JudgeScore` (LLM judge output).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class JudgeRubric:
    """A parsed Judge rubric (Story 12.1).

    Phase-1 Markdown rubric format with two required sections:

    - ``## Criteria`` — one bullet per criterion: ``- <name>: <description>``.
      Order is preserved (the LLM sees criteria in spec order).
    - ``## Threshold`` — single-line ``Pass if numeric_score >= <N>``.

    Optional ``## Examples`` section is preserved verbatim in ``raw_text``
    but not parsed into structured fields (the LLM reads it through the
    raw prompt).

    Phase-1 carve-out (DF-12.1-S1 / C79): YAML schema rubrics deferred.
    """

    criteria: tuple[tuple[str, str], ...]
    threshold: float
    raw_text: str

    def __post_init__(self) -> None:
        # Defensive: validate threshold is in [0.0, 10.0] (JudgeScore range).
        if not 0.0 <= self.threshold <= 10.0:
            raise ValueError(f"JudgeRubric.threshold must be in [0.0, 10.0]; got {self.threshold!r}")
        # Defensive: criteria must be non-empty.
        if not self.criteria:
            raise ValueError("JudgeRubric.criteria must contain at least one criterion")


@dataclass(frozen=True)
class JudgeScore:
    """An LLM judge's score for a single agent run (Story 12.1 / PRD FR48).

    Returned by ``Judge.Get Score`` keyword. Frozen + immutable;
    serializes cleanly via ``dataclasses.asdict()``.

    Fields (per epics.md L2095):
        - ``numeric_score: float`` — overall score in ``[0.0, 10.0]``.
        - ``pass_threshold_met: bool`` — ``numeric_score >= rubric.threshold``.
        - ``reasoning: str`` — the LLM's narrative explanation.
        - ``criteria_breakdown: Mapping[str, float]`` — per-criterion sub-scores
          keyed by criterion name. Defensive ``dict()`` copy in
          ``__post_init__`` per Story 1b.2 M_R6 pattern.
        - ``cost_usd: float`` — provider-reported cost of the single judge
          LLM call (non-negative; validated in ``__post_init__``).
    """

    numeric_score: float
    pass_threshold_met: bool
    reasoning: str
    criteria_breakdown: Mapping[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.numeric_score <= 10.0:
            raise ValueError(
                f"JudgeScore.numeric_score must be in [0.0, 10.0]; "
                f"got {self.numeric_score!r} (judge model violated the rubric range — fix the prompt or the rubric)"
            )
        if self.cost_usd < 0.0:
            raise ValueError(f"JudgeScore.cost_usd must be non-negative; got {self.cost_usd!r}")
        # M_R6: defensive copy so caller mutations to the source dict don't leak.
        object.__setattr__(self, "criteria_breakdown", dict(self.criteria_breakdown))


__all__ = ["JudgeRubric", "JudgeScore"]
