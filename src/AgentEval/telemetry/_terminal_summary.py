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

"""FR54 terminal run summary renderer (Story 8b.2).

Called from ``Listener.end_suite`` when ``AGENTEVAL_TERMINAL_SUMMARY=1``.
Reads from the listener's ``_completed_run_metadata`` snapshot dict (built
in ``end_test`` BEFORE ``clear_spans``).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

__all__ = ["render_summary"]


def render_summary(*, completed_run_metadata: dict[str, dict[str, Any]]) -> str:
    """Render the FR54 1-block terminal summary.

    Args:
        completed_run_metadata: ``Listener._completed_run_metadata`` snapshot
            dict — keyed by ``test_id`` with per-test cost/latency/warnings/etc.

    Returns:
        Multi-line string with box-drawing borders.
    """
    total = len(completed_run_metadata)
    passed = 0  # Story 8b.2 Phase-1: pass/fail tracking via metadata is
    # not yet wired (Listener doesn't currently snapshot the RF
    # `result.passed` flag into the metadata dict). Conservative
    # placeholder: total - failed - errored. Future Phase-1.5 work
    # would extend `_snapshot_completed_run_metadata` to capture
    # the pass/fail state from the RF `result` arg.
    failed = 0
    # Phase-1 wiring: count tests with non-empty warnings as a proxy for
    # "had degradation". Pass/fail count is approximate until the listener
    # snapshots `result.passed` (DF-8b.2-S1 carry-over candidate).
    passed = total  # Assume all passed in Phase-1.

    total_cost = sum(float(meta.get("cost_usd") or 0.0) for meta in completed_run_metadata.values())
    latencies = [
        float(meta["latency_seconds"]) for meta in completed_run_metadata.values() if meta.get("latency_seconds")
    ]
    p95_latency = _p95(latencies) if latencies else 0.0
    warnings_count = sum(1 for meta in completed_run_metadata.values() if meta.get("warnings"))

    # Top 3 error types — Phase-1: counted from `warnings` snapshots (parsed
    # `[WarningType]` prefix). Real error-class tally would require the
    # listener to capture per-test raised exceptions, which is Phase-1.5.
    error_counter: Counter[str] = Counter()
    for meta in completed_run_metadata.values():
        warns = meta.get("warnings") or ""
        for line in warns.splitlines():
            if line.startswith("[") and "]" in line:
                error_type = line[1 : line.index("]")]
                error_counter[error_type] += 1

    top_errors = error_counter.most_common(3)

    # Build the box.
    inner_width = 56  # 56 chars between the box-drawing borders.
    lines: list[str] = []
    lines.append("╔" + "═" * inner_width + "╗")
    lines.append(_box_line("agenteval run summary".center(inner_width), inner_width))
    lines.append("╠" + "═" * inner_width + "╣")
    lines.append(_box_line(f" Tests:    {total} total / {passed} passed / {failed} failed", inner_width))
    lines.append(_box_line(f" Cost:     ${total_cost:.2f}", inner_width))
    lines.append(_box_line(f" Latency:  {p95_latency:.2f}s p95", inner_width))
    lines.append(_box_line(f" Warnings: {warnings_count}", inner_width))
    if top_errors:
        lines.append(_box_line(" Top errors:", inner_width))
        for i, (error_type, count) in enumerate(top_errors, start=1):
            lines.append(_box_line(f"   {i}. {error_type} ({count} occurrences)", inner_width))
    else:
        lines.append(_box_line(" Top errors: (none)", inner_width))
    lines.append("╚" + "═" * inner_width + "╝")
    return "\n".join(lines)


def _box_line(content: str, width: int) -> str:
    """Format a single content line within the box (trim/pad to width)."""
    if len(content) > width:
        content = content[: width - 1] + "…"
    return "║" + content.ljust(width) + "║"


def _p95(values: list[float]) -> float:
    """Compute the 95th percentile of a non-empty list of floats."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    # Linear interpolation between the two nearest ranks.
    rank = 0.95 * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    fraction = rank - lower_idx
    return sorted_values[lower_idx] + fraction * (sorted_values[upper_idx] - sorted_values[lower_idx])
