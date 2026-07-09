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

"""Shared ASCII box-drawing grid renderer (`_heatmap` internal helper).

Extracted from ``CohortHeatmap.as_ascii`` (design D8 of
``add-regression-baseline-tracking``) so both ``CohortHeatmap`` and the new
``baseline.models.TrendGrid`` render through ONE box-drawing implementation
rather than a second copy (the ``wilson_ci`` duplication smell the audit
flagged). ``CohortHeatmap``'s public rendered output is byte-identical to the
pre-extraction version — the extraction is a pure internal move.

Private module (leading underscore); not part of the stability surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["render_ascii_grid"]


def render_ascii_grid(
    *,
    corner_label: str,
    row_labels: Sequence[str],
    col_labels: Sequence[str],
    format_cell: Callable[[str, str], str],
) -> str:
    """Render a labelled cell grid with box-drawing characters.

    Args:
        corner_label: top-left header cell label (e.g. ``"Task"`` / ``"Metric"``).
        row_labels: one label per body row (non-empty).
        col_labels: one label per column (non-empty).
        format_cell: ``(row_label, col_label) -> str`` returning the
            already-formatted cell text (including any missing-cell sentinel).

    Returns:
        The multi-line box-drawing grid string. Callers guard the empty case
        (no rows / no columns) themselves and supply their own placeholder.
    """
    # Column widths.
    row_col_width = max(len(corner_label), *(len(r) for r in row_labels))
    col_widths: dict[str, int] = {}
    for col in col_labels:
        cells = [format_cell(row, col) for row in row_labels]
        col_widths[col] = max(len(col), *(len(c) for c in cells))

    # Header row.
    header_cells = [
        corner_label.ljust(row_col_width),
        *(col.ljust(col_widths[col]) for col in col_labels),
    ]
    header_line = "│ " + " │ ".join(header_cells) + " │"

    # Separator lines.
    sep_parts = [
        "─" * (row_col_width + 2),
        *("─" * (col_widths[col] + 2) for col in col_labels),
    ]
    top_line = "┌" + "┬".join(sep_parts) + "┐"
    mid_line = "├" + "┼".join(sep_parts) + "┤"
    bot_line = "└" + "┴".join(sep_parts) + "┘"

    # Body rows.
    body_lines: list[str] = []
    for row in row_labels:
        cells = [row.ljust(row_col_width)]
        for col in col_labels:
            cells.append(format_cell(row, col).ljust(col_widths[col]))
        body_lines.append("│ " + " │ ".join(cells) + " │")

    return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
