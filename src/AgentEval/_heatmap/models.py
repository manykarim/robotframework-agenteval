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

"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import (
        DiscoverabilityComparisonResult,
        DiscoverabilityResult,
    )
    from AgentEval.skills.types import SkillDiscoverabilityComparisonResult

__all__ = ["CohortHeatmap"]


# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
#   [0.0, 0.2) → red (high failure)
#   [0.2, 0.4) → orange
#   [0.4, 0.6) → yellow
#   [0.6, 0.8) → lime
#   [0.8, 1.0] → green (high success)
# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
# mode (viridis/magma sequential per WCAG 2.1 AA).
_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
    # (lower_bound_inclusive, background_hex, text_hex)
    (0.0, "#ef4444", "#ffffff"),  # red — high failure
    (0.2, "#f97316", "#ffffff"),  # orange
    (0.4, "#eab308", "#0f172a"),  # yellow
    (0.6, "#84cc16", "#0f172a"),  # lime
    (0.8, "#22c55e", "#ffffff"),  # green — high success
)
# Missing cell (cell[(task, model)] not present in `cells`): light gray.
_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")


def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.

    Args:
        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.

    Returns:
        ``(background_hex, text_hex)`` tuple.

    Edge cases:
        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
        - ``rate < 0.0`` → first stop (red); not validated upstream so
          defensively clamps to the bottom rather than raising.
    """
    if rate is None:
        return _MISSING_CELL_STYLE
    # Linear scan: walk the palette + return the HIGHEST entry whose lower
    # bound is `<=` the rate. The palette is sorted ascending by lower bound
    # so we walk forward and remember the last match.
    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
        if rate >= lower:
            bg, txt = candidate_bg, candidate_txt
    return (bg, txt)


@dataclass(frozen=True)
class CohortHeatmap:
    """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).

    Phase-1: single-model heatmap (rows = tasks, single column = model).
    Multi-model comparison (rows = tasks, columns = models) is Phase-2.

    The model name in Phase-1 defaults to ``"default"`` unless the caller
    provides one via ``from_discoverability(result, model_name=...)``.
    """

    tasks: tuple[str, ...]
    models: tuple[str, ...]
    # Mapping: cell[(task_id, model_name)] = pass_at_k.
    # Stored as a frozen-friendly tuple of (task, model, value) triples so the
    # dataclass remains hashable.
    cells: tuple[tuple[str, str, float], ...]

    @classmethod
    def from_discoverability(
        cls,
        result: DiscoverabilityResult,
        *,
        model_name: str = "default",
    ) -> CohortHeatmap:
        """Build a single-model heatmap from a ``DiscoverabilityResult``.

        Args:
            result: Story 4.4 ``DiscoverabilityResult``.
            model_name: Column label for the single-model column.

        Returns:
            ``CohortHeatmap`` instance with one column.
        """
        tasks = tuple(t.task_id for t in result.per_task_results)
        cells = tuple((t.task_id, model_name, t.pass_rate) for t in result.per_task_results)
        return cls(tasks=tasks, models=(model_name,), cells=cells)

    @classmethod
    def from_comparison(
        cls,
        result: DiscoverabilityComparisonResult,
    ) -> CohortHeatmap:
        """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).

        Columns = adapter names (preserving input order from ``result.adapters``).
        Rows = task IDs (union across all per-adapter results, preserving
        first-encounter order — defensively handles the edge case where a
        stub adapter dropped a task; in production all adapters run the
        SAME task set so the union equals each adapter's task list).

        Args:
            result: Story 13.3 ``DiscoverabilityComparisonResult``.

        Returns:
            ``CohortHeatmap`` with one column per adapter + one row per task.
        """
        # Build the row list as the union preserving first-encounter order.
        seen: set[str] = set()
        tasks_list: list[str] = []
        for adapter in result.adapters:
            for task_result in result.per_adapter_results[adapter].per_task_results:
                if task_result.task_id not in seen:
                    seen.add(task_result.task_id)
                    tasks_list.append(task_result.task_id)
        tasks = tuple(tasks_list)
        models = result.adapters
        cells = tuple(
            (task_result.task_id, adapter, task_result.pass_rate)
            for adapter in result.adapters
            for task_result in result.per_adapter_results[adapter].per_task_results
        )
        return cls(tasks=tasks, models=models, cells=cells)

    @classmethod
    def from_skill_comparison(
        cls,
        result: SkillDiscoverabilityComparisonResult,
    ) -> CohortHeatmap:
        """Build a multi-column heatmap from a cross-adapter Skill comparison (Story 13.5 / FR4c).

        Symmetric to ``from_comparison`` but reads the Skill-domain
        ``pass_at_k`` field (NOT the MCP-domain ``pass_rate`` property).
        Columns = adapter names (preserving input order). Rows = task IDs
        (union across all per-adapter results, preserving first-encounter
        order). Story 13.4 L-7 lesson applied: missing cells represented
        by OMISSION from the ``cells`` tuple (NOT explicit ``None``) to
        preserve the public ``cells: tuple[tuple[str, str, float], ...]``
        type contract.

        Args:
            result: Story 13.5 ``SkillDiscoverabilityComparisonResult``.

        Returns:
            ``CohortHeatmap`` with one column per adapter + one row per task.
        """
        seen: set[str] = set()
        tasks_list: list[str] = []
        for adapter in result.adapters:
            for task_result in result.per_adapter_results[adapter].per_task_results:
                if task_result.task_id not in seen:
                    seen.add(task_result.task_id)
                    tasks_list.append(task_result.task_id)
        tasks = tuple(tasks_list)
        models = result.adapters
        cells = tuple(
            (task_result.task_id, adapter, task_result.pass_at_k)
            for adapter in result.adapters
            for task_result in result.per_adapter_results[adapter].per_task_results
        )
        return cls(tasks=tasks, models=models, cells=cells)

    def as_dict(self) -> dict[str, dict[str, float]]:
        """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
        out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
        for task, model, value in self.cells:
            out.setdefault(task, {})[model] = value
        return out

    def as_ascii(self) -> str:
        """ASCII heatmap with box-drawing characters.

        Rows = tasks, columns = models, cells = Pass@k as 2-decimal float.
        Empty input → ``"(empty heatmap)"`` placeholder.
        """
        if not self.tasks or not self.models:
            return "(empty heatmap)"

        data = self.as_dict()
        # Story 8b.2 v0.2.0 kilo/minimax cross-LLM review HIGH-1 patch
        # (2026-05-26): missing cells render as " — " sentinel (em-dash with
        # spaces) instead of silently substituting 0.0, which was
        # indistinguishable from a genuine 0% pass-rate. Operators can now
        # tell missing-from-data apart from real-zero.
        _missing = " — "

        def _fmt(task: str, model: str) -> str:
            value = data.get(task, {}).get(model)
            return _missing if value is None else f"{value:.2f}"

        # Compute column widths.
        task_col_width = max(len("Task"), *(len(t) for t in self.tasks))
        model_widths: dict[str, int] = {}
        for model in self.models:
            cells = [_fmt(task, model) for task in self.tasks]
            model_widths[model] = max(len(model), *(len(c) for c in cells))

        # Render header row.
        header_cells = [
            "Task".ljust(task_col_width),
            *(model.ljust(model_widths[model]) for model in self.models),
        ]
        header_line = "│ " + " │ ".join(header_cells) + " │"

        # Separator line (top + below header + bottom).
        sep_parts = [
            "─" * (task_col_width + 2),
            *("─" * (model_widths[model] + 2) for model in self.models),
        ]
        top_line = "┌" + "┬".join(sep_parts) + "┐"
        mid_line = "├" + "┼".join(sep_parts) + "┤"
        bot_line = "└" + "┴".join(sep_parts) + "┘"

        # Body rows.
        body_lines: list[str] = []
        for task in self.tasks:
            cells = [task.ljust(task_col_width)]
            for model in self.models:
                cells.append(_fmt(task, model).ljust(model_widths[model]))
            body_lines.append("│ " + " │ ".join(cells) + " │")

        return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])

    def as_html(self) -> str:
        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).

        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
        `<style>`), and `<body>` containing a `<table>` with header row +
        one row per task. Each Pass@k cell carries inline
        `style="background-color: <hex>; color: <text-hex>;"` for the
        color gradient.

        All styling embedded in `<head><style>...</style>`. NO external
        stylesheet links, NO external image references, NO `<script>`
        elements — operators can email the file or save to shared
        storage and view offline.

        Empty heatmap (no tasks OR no models): returns a minimal valid
        document with `<body><p>(empty heatmap)</p></body>` (symmetric
        with `as_ascii()`'s `"(empty heatmap)"` sentinel).

        Pass@k color gradient (5-stop hue palette; text color chosen for
        WCAG AA contrast):
            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
              with text "—" (em-dash, matching `as_ascii()` fallback).

        See module-level `_PASS_RATE_PALETTE` constant for the canonical
        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
        alternative palette.

        Security: all user-provided strings (task IDs, model names)
        pass through ``html.escape`` before insertion to prevent HTML
        injection. Float Pass@k values are formatted via
        ``f"{value:.2f}"`` (safe — no escape needed).

        Returns:
            Standalone HTML5 document as a string.
        """
        if not self.tasks or not self.models:
            return (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '  <meta charset="utf-8">\n'
                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
                "</head>\n"
                "<body>\n"
                "  <p>(empty heatmap)</p>\n"
                "</body>\n"
                "</html>\n"
            )

        data = self.as_dict()
        # Build header row.
        header_cells = ["<th>Task</th>"]
        for model in self.models:
            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"

        # Build body rows.
        body_rows: list[str] = []
        for task in self.tasks:
            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
            for model in self.models:
                value = data.get(task, {}).get(model)
                bg, txt_color = _color_for_pass_rate(value)
                cell_text = "—" if value is None else f"{value:.2f}"
                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            "  <title>AgentEval Cohort Heatmap</title>\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
            "    table { border-collapse: collapse; }\n"
            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
            "    th { background-color: #0f172a; color: #ffffff; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
            "</body>\n"
            "</html>\n"
        )

    def write_html(self, path: str | Path) -> Path:
        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).

        Args:
            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
                Relative paths resolve against ``Path.cwd()``. Empty
                string raises ``ValueError``. Parent directories are
                created with ``parents=True, exist_ok=True``.

        Returns:
            The resolved write path (post-``Path.resolve()``).

        Raises:
            ValueError: When ``path`` is the empty string.
            OSError: When the filesystem write fails (read-only,
                permission denied, etc.). NOT caught — propagates to
                the caller.

        Notes:
            - Convenience companion to ``as_html`` per Story 13.4 D-2.
            - Writes UTF-8 encoded text.
            - Story 13.4 D-5: empty-string path rejected up-front
              instead of relying on ``Path("").write_text`` which
              would write to the current directory's empty filename.
        """
        # Reject empty-string path early — covers both `""` (str) and
        # `Path("")` (Path normalizes empty string to `Path(".")` at
        # construction, so checking the str directly catches the str case,
        # and `Path(path).name == ""` catches Path objects whose
        # resolved name is empty (which Path('') becomes). Pre-fix only
        # caught the `str` "" path, leaving Path("") to fail later with
        # a confusing `IsADirectoryError`. Story 13.4 code-review fix
        # 2026-06-01 (Opus MED-1 + Sonnet LOW-1).
        if isinstance(path, str) and path == "":
            raise ValueError("write_html requires a non-empty path; got empty string")
        if isinstance(path, Path) and path.name == "":
            raise ValueError(
                "write_html requires a non-empty path; got Path-like with empty "
                f"name (repr: {path!r}, name: {path.name!r})"
            )
        resolved = Path(path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(self.as_html(), encoding="utf-8")
        return resolved
