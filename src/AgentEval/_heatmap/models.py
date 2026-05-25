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

"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import DiscoverabilityResult

__all__ = ["CohortHeatmap"]


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
        # Compute column widths.
        task_col_width = max(len("Task"), *(len(t) for t in self.tasks))
        model_widths: dict[str, int] = {}
        for model in self.models:
            cells = [f"{data.get(task, {}).get(model, 0.0):.2f}" for task in self.tasks]
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
                value = data.get(task, {}).get(model, 0.0)
                cells.append(f"{value:.2f}".ljust(model_widths[model]))
            body_lines.append("│ " + " │ ".join(cells) + " │")

        return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
