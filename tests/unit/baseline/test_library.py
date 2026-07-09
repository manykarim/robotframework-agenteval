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

"""Unit tests: BaselineLibrary keyword surface, tiering, errors (tasks 6.6, 6.7)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from AgentEval import AgentEval
from AgentEval.baseline.library import BaselineLibrary
from AgentEval.errors import BaselineNotFoundError, BaselineWriteError, PossibleRegressionWarning

from ._builders import keyword_runs

_BASELINE_KEYWORDS = ("Save Metrics Baseline", "Metrics Should Not Regress", "Get Metric Trend")


# --- end-to-end save → regress → trend (task 6.6) -------------------------- #


def test_save_then_regress_pass(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    path = tmp_path / "baselines" / "main.json"
    lib.save_metrics_baseline(keyword_runs(45, 50), path)
    assert path.exists()
    report = lib.metrics_should_not_regress(keyword_runs(44, 50), path, tolerance="5%")
    assert not report.regressed


def test_save_then_regress_real_regression_raises(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    path = tmp_path / "main.json"
    lib.save_metrics_baseline(keyword_runs(45, 50), path)
    with pytest.raises(AssertionError) as exc:
        lib.metrics_should_not_regress(keyword_runs(5, 50), path, tolerance="5%")
    assert "regressed" in str(exc.value)
    assert "pass_rate" in str(exc.value)


def test_within_ci_drop_passes_with_warning(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    path = tmp_path / "main.json"
    lib.save_metrics_baseline(keyword_runs(9, 10), path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = lib.metrics_should_not_regress(keyword_runs(7, 10), path, tolerance="5%")
    assert not report.regressed
    assert [w for w in caught if w.category is PossibleRegressionWarning]


# --- structured errors ----------------------------------------------------- #


def test_missing_baseline_raises_not_found_with_fix(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    with pytest.raises(BaselineNotFoundError) as exc:
        lib.metrics_should_not_regress(keyword_runs(9, 10), tmp_path / "nope.json")
    msg = str(exc.value)
    assert "not found" in msg
    assert "Save Metrics Baseline" in msg  # save-then-commit fix suggestion


def test_unwritable_path_raises_write_error(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    # A path whose parent is an existing *file* cannot be created as a dir.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    with pytest.raises(BaselineWriteError):
        lib.save_metrics_baseline(keyword_runs(1, 1), blocker / "sub" / "main.json")


def test_missing_history_raises_not_found(tmp_path: Path) -> None:
    lib = BaselineLibrary()
    with pytest.raises(BaselineNotFoundError):
        lib.get_metric_trend("pass_at_1", tmp_path / "no-history.jsonl")


# --- tiering + composition (task 6.7) -------------------------------------- #


def test_all_three_keywords_report_tier_1() -> None:
    agent = AgentEval()
    for name in _BASELINE_KEYWORDS:
        assert agent.get_keyword_tier(name) == 1


def test_standalone_import_exposes_keywords() -> None:
    from robot.libdocpkg import LibraryDocumentation

    doc = LibraryDocumentation("AgentEval.baseline.library.BaselineLibrary")
    names = {kw.name for kw in doc.keywords}
    assert set(_BASELINE_KEYWORDS) <= names


def test_keywords_resolve_through_composed_library() -> None:
    agent = AgentEval()
    assert "BaselineLibrary" in agent._loaded_components
    for name in _BASELINE_KEYWORDS:
        assert name in agent.keywords


def test_no_keyword_name_collision() -> None:
    # AgentEval() raises at import if two components declare the same keyword;
    # constructing it is the collision check.
    AgentEval()
    baseline_names = set(_BASELINE_KEYWORDS)
    # None of the baseline names carry a dot (unprefixed core-loop convention).
    assert all("." not in n for n in baseline_names)
