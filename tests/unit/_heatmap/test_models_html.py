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

"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).

Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
SPECIFIC structural counts (table count, tr count, td count, palette
hex presence) — NOT just "html.parser doesn't crash."

Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
anchor test asserts the required strings appear in the docstring.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

from AgentEval._heatmap.models import (
    _MISSING_CELL_STYLE,
    CohortHeatmap,
    _color_for_pass_rate,
)

# --------------------------------------------------------------------------- #
# `_color_for_pass_rate` helper (4 tests)                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "rate,expected_bg",
    [
        (0.0, "#ef4444"),  # red — bottom stop
        (0.19, "#ef4444"),  # still red
        (0.2, "#f97316"),  # orange boundary
        (0.39, "#f97316"),
        (0.4, "#eab308"),  # yellow
        (0.5, "#eab308"),
        (0.6, "#84cc16"),  # lime
        (0.79, "#84cc16"),
        (0.8, "#22c55e"),  # green
        (1.0, "#22c55e"),  # top stop
    ],
)
def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
    """Each color stop boundary maps to the correct background hex."""
    bg, _txt = _color_for_pass_rate(rate)
    assert bg == expected_bg


def test_color_for_pass_rate_none_returns_missing_style() -> None:
    """None input → missing-cell light-gray + slate-900 text."""
    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE


def test_color_for_pass_rate_exactly_one_returns_green() -> None:
    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
    bg, txt = _color_for_pass_rate(1.0)
    assert bg == "#22c55e"
    assert txt == "#ffffff"


def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
    """Defensive: negative rate → bottom stop (red) rather than raising."""
    bg, _txt = _color_for_pass_rate(-0.1)
    assert bg == "#ef4444"


# --------------------------------------------------------------------------- #
# `as_html` happy paths (5 tests)                                             #
# --------------------------------------------------------------------------- #


def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
    h = CohortHeatmap(tasks=(), models=(), cells=())
    html = h.as_html()
    assert "<!DOCTYPE html>" in html
    assert "(empty heatmap)" in html
    assert "</html>" in html


def test_as_html_single_model_3_tasks() -> None:
    """1 column × 3 rows produces correctly-shaped HTML."""
    h = CohortHeatmap(
        tasks=("t0", "t1", "t2"),
        models=("m0",),
        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
    )
    html = h.as_html()
    # Header row: <th>Task</th><th>m0</th>
    assert html.count("<th>") == 2
    # Body rows: 3 <tr>
    assert html.count("<tr>") == 4  # 1 header + 3 body rows
    # Body cells: 6 <td> (3 task names + 3 values)
    assert html.count("<td") == 6
    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
    assert "#22c55e" in html
    assert "#eab308" in html
    assert "#ef4444" in html


def test_as_html_3_adapter_3_tasks() -> None:
    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
    h = CohortHeatmap(
        tasks=("t0", "t1", "t2"),
        models=("a", "b", "c"),
        cells=(
            ("t0", "a", 1.0),
            ("t0", "b", 0.5),
            ("t0", "c", 0.0),
            ("t1", "a", 1.0),
            ("t1", "b", 0.5),
            ("t1", "c", 0.0),
            ("t2", "a", 1.0),
            ("t2", "b", 0.5),
            ("t2", "c", 0.0),
        ),
    )
    html = h.as_html()
    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
    assert html.count("<td") == 12
    # 4 header <th>: Task + a + b + c.
    assert html.count("<th>") == 4


def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
    """A cell missing from the input → em-dash + light-gray background."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0", "m1"),
        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
    )
    html = h.as_html()
    assert "—" in html
    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb


def test_as_html_pass_rates_formatted_two_decimals() -> None:
    """Pass@k values rendered as 2-decimal floats."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 0.123456),),
    )
    html = h.as_html()
    assert "0.12" in html
    # NOT showing the unrounded version.
    assert "0.123456" not in html


# --------------------------------------------------------------------------- #
# HTML validity (3 tests)                                                     #
# --------------------------------------------------------------------------- #


class _StructuralHTMLParser(HTMLParser):
    """Count opening tags + collect script data for defense-in-depth tests."""

    def __init__(self) -> None:
        super().__init__()
        self.tag_open_counts: dict[str, int] = {}
        self.script_data: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
        if tag == "script":
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.script_data.append(data)


def test_as_html_parses_via_stdlib_html_parser() -> None:
    """`html.parser.HTMLParser` parses the output without raising."""
    h = CohortHeatmap(
        tasks=("t0", "t1"),
        models=("m0", "m1"),
        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
    )
    parser = _StructuralHTMLParser()
    parser.feed(h.as_html())
    parser.close()
    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
    assert parser.tag_open_counts.get("table", 0) == 1
    # tr = 1 (header) + 2 (body rows) = 3.
    assert parser.tag_open_counts.get("tr", 0) == 3
    # th = 1 (Task header) + 2 (model headers).
    assert parser.tag_open_counts.get("th", 0) == 3
    # td = 2 tasks × (1 task name + 2 models) = 6.
    assert parser.tag_open_counts.get("td", 0) == 6


def test_as_html_has_no_external_resources() -> None:
    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 1.0),),
    )
    html = h.as_html()
    # NO external stylesheet link.
    assert "<link" not in html
    # NO script element (D-3 explicit prohibition for offline-safety).
    assert "<script" not in html.lower()
    # NO external image / font URLs.
    assert 'src="http' not in html.lower()
    assert 'href="http' not in html.lower()
    # NO external `url(...)` references in styles.
    assert "url(http" not in html.lower()


def test_as_html_no_script_data_under_html_parser() -> None:
    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 1.0),),
    )
    parser = _StructuralHTMLParser()
    parser.feed(h.as_html())
    parser.close()
    assert parser.script_data == []
    assert parser.tag_open_counts.get("script", 0) == 0


# --------------------------------------------------------------------------- #
# HTML escaping (2 tests)                                                     #
# --------------------------------------------------------------------------- #


def test_as_html_escapes_script_tags_in_task_ids() -> None:
    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
    malicious = "<script>alert(1)</script>"
    h = CohortHeatmap(
        tasks=(malicious,),
        models=("m0",),
        cells=((malicious, "m0", 1.0),),
    )
    html = h.as_html()
    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_as_html_escapes_special_characters_in_model_names() -> None:
    """Model names with `&`, `<`, `>` get HTML-escaped."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("A&B<C>D",),
        cells=(("t0", "A&B<C>D", 0.5),),
    )
    html = h.as_html()
    assert "A&amp;B&lt;C&gt;D" in html
    # Original unescaped form must NOT appear.
    assert "A&B<C>D" not in html


# --------------------------------------------------------------------------- #
# `write_html` file ops (4 tests)                                             #
# --------------------------------------------------------------------------- #


def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
    """write_html writes the same content as as_html + returns the resolved path."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 1.0),),
    )
    target = tmp_path / "heatmap.html"
    result = h.write_html(target)
    assert result == target.resolve()
    assert result.exists()
    assert result.read_text(encoding="utf-8") == h.as_html()


def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
    """write_html creates non-existent parent directories via mkdir(parents=True)."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 0.5),),
    )
    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
    assert not target.parent.exists()
    result = h.write_html(target)
    assert result.exists()
    assert target.parent.is_dir()


def test_write_html_empty_string_path_raises_value_error() -> None:
    """write_html('') raises ValueError per D-5."""
    h = CohortHeatmap(tasks=(), models=(), cells=())
    with pytest.raises(ValueError, match="non-empty path"):
        h.write_html("")


def test_write_html_empty_path_object_raises_value_error() -> None:
    """write_html(Path('')) ALSO raises ValueError (Opus MED-1 + Sonnet LOW-1 fix).

    Pre-fix the empty-path guard only caught `str` "" — `Path("")` got
    `IsADirectoryError` further down (Path("") resolves to a directory),
    leading to a non-obvious failure mode.
    """
    h = CohortHeatmap(tasks=(), models=(), cells=())
    with pytest.raises(ValueError, match="non-empty path"):
        h.write_html(Path(""))


def test_as_html_tasks_empty_but_models_non_empty_returns_sentinel() -> None:
    """Asymmetric empty (no tasks, but models declared) → empty sentinel (Sonnet MED-2 fix)."""
    h = CohortHeatmap(tasks=(), models=("m0",), cells=())
    html = h.as_html()
    assert "(empty heatmap)" in html
    assert "<table>" not in html


def test_as_html_models_empty_but_tasks_non_empty_returns_sentinel() -> None:
    """Asymmetric empty (no models, but tasks declared) → empty sentinel (Sonnet MED-2 fix)."""
    h = CohortHeatmap(tasks=("t0",), models=(), cells=())
    html = h.as_html()
    assert "(empty heatmap)" in html
    assert "<table>" not in html


def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
    """Both `str` and `Path` inputs work + return identical resolved paths."""
    h = CohortHeatmap(
        tasks=("t0",),
        models=("m0",),
        cells=(("t0", "m0", 1.0),),
    )
    str_path = str(tmp_path / "a.html")
    path_obj = tmp_path / "b.html"
    r1 = h.write_html(str_path)
    r2 = h.write_html(path_obj)
    assert r1.exists()
    assert r2.exists()
    assert r1 == Path(str_path).resolve()
    assert r2 == path_obj.resolve()


# --------------------------------------------------------------------------- #
# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
# --------------------------------------------------------------------------- #


def test_as_html_docstring_carries_anchors() -> None:
    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
    doc = CohortHeatmap.as_html.__doc__ or ""
    assert "as_html" in doc.lower() or "AS_HTML" in doc
    assert "FR55" in doc
    assert "Phase-2" in doc or "Phase 2" in doc
    assert "embedded CSS" in doc or "embedded `<style>" in doc


# --------------------------------------------------------------------------- #
# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
# --------------------------------------------------------------------------- #


def _build_2_adapter_baseline() -> CohortHeatmap:
    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
    return CohortHeatmap(
        tasks=("task_alpha", "task_beta", "task_gamma"),
        models=("adapter_red", "adapter_green"),
        cells=(
            ("task_alpha", "adapter_red", 1.0),
            ("task_alpha", "adapter_green", 0.0),
            ("task_beta", "adapter_red", 0.5),
            ("task_beta", "adapter_green", 0.5),
            ("task_gamma", "adapter_red", 0.0),
            ("task_gamma", "adapter_green", 1.0),
        ),
    )


def _build_3_adapter_baseline() -> CohortHeatmap:
    """Deterministic 3-adapter × 3-task input.

    Missing cell ("t1", "b") is represented by OMISSION from the
    `cells` tuple — matching the public `cells: tuple[tuple[str, str,
    float], ...]` type contract. Story 13.4 code-review 3-way fix
    2026-06-01 (Codex MED-1 + Opus LOW-2 + Sonnet MED-1): pre-fix
    encoded the missing cell as `("t1", "b", None)` which silently
    violated the cells-are-floats type contract. Omission is the
    documented missing-cell convention per `as_dict()`'s type
    annotation + the existing `as_ascii()` precedent.
    """
    return CohortHeatmap(
        tasks=("t0", "t1", "t2"),
        models=("a", "b", "c"),
        cells=(
            ("t0", "a", 1.0),
            ("t0", "b", 0.5),
            ("t0", "c", 0.0),
            ("t1", "a", 0.7),
            # ("t1", "b") missing on purpose — represented by omission.
            ("t1", "c", 0.3),
            ("t2", "a", 0.0),
            ("t2", "b", 0.0),
            ("t2", "c", 0.0),
        ),
    )


def test_html_matches_recorded_baseline_2_adapter() -> None:
    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
    expected = fixture.read_text(encoding="utf-8")
    actual = _build_2_adapter_baseline().as_html()
    assert actual == expected


def test_html_matches_recorded_baseline_3_adapter() -> None:
    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
    expected = fixture.read_text(encoding="utf-8")
    actual = _build_3_adapter_baseline().as_html()
    assert actual == expected
