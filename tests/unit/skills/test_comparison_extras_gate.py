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

"""ImportError-gate tests for `Skill.Compare Discoverability` (Story 13.5 / L-2 lesson).

Mirrors `tests/unit/discoverability/test_comparison_extras_gate.py`
(Story 13.3) + `tests/unit/stats/test_advanced_extras_gate.py` (Story
13.1) + `tests/unit/telemetry/test_backends_otlp_extras_gate.py` (Story
13.2) discipline: NO module-top `pytest.importorskip` so the
gate-coverage tests run in BOTH the WITH-extras and WITHOUT-extras CI
environments.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_skill_comparison_schema_importable_without_extra() -> None:
    """`from AgentEval.skills.types import SkillDiscoverabilityComparisonResult` works without extras."""
    from AgentEval.skills.types import (  # noqa: F401
        SkillDiscoverabilityComparisonResult,
        SkillDiscoverabilityComparisonSummary,
        SkillPairwiseAdapterDelta,
    )


def test_compare_keyword_raises_import_error_when_advanced_extra_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Skill.Compare Discoverability` raises ImportError when `_ADVANCED_AVAILABLE=False`.

    Story 13.5 L-2 + Story 13.3 amendment: gate read via module-attr
    (`_stats_lib._ADVANCED_AVAILABLE`) so the monkeypatch is observed
    even across pytest session-wide module reload.
    """
    from AgentEval.skills.library import SkillsLibrary
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)

    lib = SkillsLibrary()
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
    tasks_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.get_discoverability_comparison(
            skill=str(fixture_path),
            tasks=str(tasks_path),
            adapters=["any_a", "any_b"],
            trials_per_task=1,
        )


def test_compare_keyword_import_error_message_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ImportError message carries the verbatim install hint with `Skill.Compare Discoverability` prefix."""
    from AgentEval.skills.library import SkillsLibrary
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
    tasks_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
    lib = SkillsLibrary()
    with pytest.raises(ImportError) as exc_info:
        lib.get_discoverability_comparison(
            skill=str(fixture_path),
            tasks=str(tasks_path),
            adapters=["a", "b"],
            trials_per_task=1,
        )
    msg = str(exc_info.value)
    assert "Skill.Compare Discoverability" in msg
    assert "scipy + numpy required" in msg
    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg


def test_compare_keyword_arg_validation_runs_before_extras_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arg validation (skill / adapters / tasks) runs BEFORE the extras gate.

    Mirrors Story 13.3's analogous test — operator with both missing
    extra AND missing args should see the arg error first (more
    actionable).
    """
    from AgentEval.skills.library import SkillsLibrary
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    lib = SkillsLibrary()
    with pytest.raises(ValueError, match="skill"):
        lib.get_discoverability_comparison(
            skill="",  # empty — arg validation should fire first.
            tasks="some.yaml",
            adapters=["a", "b"],
            trials_per_task=1,
        )
