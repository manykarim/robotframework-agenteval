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

"""Unit tests: append-mode history + trend surface + grid (task 6.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.baseline.library import BaselineLibrary
from AgentEval.baseline.models import TrendGrid

from ._builders import keyword_runs


def _history_with(tmp_path: Path, snapshots: list[tuple[int, int]]) -> Path:
    lib = BaselineLibrary()
    hist = tmp_path / "history.jsonl"
    for successes, trials in snapshots:
        lib.save_metrics_baseline(
            keyword_runs(successes, trials),
            tmp_path / "throwaway.json",
            history=hist,
            timestamp="2026-07-09T00:00:00+00:00",
        )
    return hist


def test_history_accumulates_exactly_n_lines(tmp_path: Path) -> None:
    hist = _history_with(tmp_path, [(45, 50), (40, 50), (30, 50)])
    lines = [ln for ln in hist.read_text().splitlines() if ln.strip()]
    assert len(lines) == 3


def test_append_never_truncates(tmp_path: Path) -> None:
    hist = _history_with(tmp_path, [(45, 50)])
    first = hist.read_text()
    _history_with(tmp_path, [(40, 50)])  # append a second snapshot to the same file
    after = hist.read_text()
    assert after.startswith(first)
    assert len([ln for ln in after.splitlines() if ln.strip()]) == 2


def test_trend_series_three_ordered_points_with_recomputed_ci(tmp_path: Path) -> None:
    hist = _history_with(tmp_path, [(45, 50), (40, 50), (30, 50)])
    lib = BaselineLibrary()
    series = lib.get_metric_trend("pass_at_1", hist)
    assert len(series.points) == 3
    assert series.values() == [0.9, 0.8, 0.6]
    for p in series.points:
        assert p.ci_lower is not None
        assert p.ci_upper is not None
        assert p.ci_lower <= p.value <= p.ci_upper  # type: ignore[operator]
        assert p.n_trials == 50


def test_missing_metric_is_missing_point_not_zero(tmp_path: Path) -> None:
    hist = _history_with(tmp_path, [(45, 50)])
    lib = BaselineLibrary()
    series = lib.get_metric_trend("tool_hit_rate", hist)  # never captured
    assert len(series.points) == 1
    assert series.points[0].value is None  # NOT 0.0


def test_corrupt_history_line_skipped(tmp_path: Path) -> None:
    hist = _history_with(tmp_path, [(45, 50), (40, 50)])
    with hist.open("a", encoding="utf-8") as fp:
        fp.write("{ this is not valid json\n")
    lib = BaselineLibrary()
    series = lib.get_metric_trend("pass_at_1", hist)
    # Corrupt line skipped → still 2 valid points.
    assert len(series.points) == 2


def test_malformed_metric_evidence_line_skipped_not_crashed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # MED-2: a line that is valid JSON with schema_version:1 but malformed metric
    # evidence (successes="oops") passes top-level shape validation, then used to
    # crash Get Metric Trend in int()/float()/wilson coercion. It must instead be
    # skipped with a warning naming its line number, and the surviving points kept.
    hist = _history_with(tmp_path, [(45, 50), (40, 50)])
    malformed = (
        '{"schema_version":1,'
        '"metrics":{"pass_rate":{"kind":"proportion","successes":"oops","trials":10,"value":0.9}},'
        '"extra_metrics":{},"run_context":{}}'
    )
    with hist.open("a", encoding="utf-8") as fp:
        fp.write(malformed + "\n")
    lib = BaselineLibrary()
    with caplog.at_level("WARNING", logger="AgentEval.baseline"):
        series = lib.get_metric_trend("pass_rate", hist)
    # The malformed line is skipped (not crashed) → the 2 valid points survive.
    assert len(series.points) == 2
    assert series.values() == [0.9, 0.8]
    # Skipped with a warning that names the offending line number (line 3).
    warned = [r.getMessage() for r in caplog.records if "skipping corrupt history line" in r.getMessage()]
    assert warned, "expected a corrupt-line skip warning"
    assert any(":3" in m or "line 3" in m for m in warned)


def test_trend_grid_missing_cell_em_dash(tmp_path: Path) -> None:
    # Two snapshots; the second lacks cost_usd (no agent-result payloads).
    lib = BaselineLibrary()
    hist = tmp_path / "h.jsonl"
    lib.save_metrics_baseline(
        keyword_runs(9, 10, with_agent_result=True),
        tmp_path / "t.json",
        history=hist,
        timestamp="2026-07-09T00:00:00+00:00",
    )
    lib.save_metrics_baseline(
        keyword_runs(9, 10, with_agent_result=False),
        tmp_path / "t.json",
        history=hist,
        timestamp="2026-07-09T00:00:00+00:00",
    )
    series = lib.get_metric_trend("pass_at_1", hist)
    grid = series.grid
    assert isinstance(grid, TrendGrid)
    ascii_out = grid.as_ascii()
    # cost_usd present in snap0 but missing in snap1 → em-dash sentinel.
    assert "cost_usd" in ascii_out
    assert " — " in ascii_out
    d = grid.as_dict()
    assert "snap1" not in d["cost_usd"]  # missing cell omitted, not 0.0


def test_empty_trend_grid_placeholder() -> None:
    grid = TrendGrid(metrics=(), snapshots=(), cells=())
    assert grid.as_ascii() == "(empty trend grid)"
