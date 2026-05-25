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

"""Conformance-report serialisers (Story 8a.2 AC-8a.2.3 + AC-8a.2.5).

Atomic-write pattern symmetric with Story 8a.1 `_xunit_enrichment`: write
to ``<path>.tmp`` then ``os.replace`` so a failure mid-write preserves any
pre-existing file (or leaves no partial file behind).

Schema authority: ``docs/contracts/conformance-fixture-format.md``
"Conformance Report Schema (Phase-1.5)" section.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "FixtureResult",
    "ReportSummary",
    "write_json_report",
    "write_md_report",
]


FixtureStatus = Literal["passed", "failed", "errored", "skipped"]


@dataclass(frozen=True)
class FixtureResult:
    """Per-fixture conformance-run record."""

    fixture_id: str
    fixture_path: str
    status: FixtureStatus
    duration_seconds: float
    oracle_evidence: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None


@dataclass(frozen=True)
class ReportSummary:
    """Aggregate conformance-run summary."""

    total: int
    passed: int
    failed: int
    errored: int
    skipped: int

    @classmethod
    def from_results(cls, results: list[FixtureResult]) -> ReportSummary:
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errored = sum(1 for r in results if r.status == "errored")
        skipped = sum(1 for r in results if r.status == "skipped")
        return cls(
            total=len(results),
            passed=passed,
            failed=failed,
            errored=errored,
            skipped=skipped,
        )


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text to `path` via atomic-replace.

    Failure mid-write does not leave a partial `path` behind: write goes
    to `<path>.tmp` first, then `os.replace` atomically moves it into place.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def write_json_report(
    path: Path,
    *,
    agenteval_version: str,
    adapter: str,
    executed_at: str,
    results: list[FixtureResult],
) -> ReportSummary:
    """Write `conformance-report.json` per the schema; return aggregate summary."""
    summary = ReportSummary.from_results(results)
    payload: dict[str, Any] = {
        "agenteval_version": agenteval_version,
        "adapter": adapter,
        "executed_at": executed_at,
        "summary": {
            "total": summary.total,
            "passed": summary.passed,
            "failed": summary.failed,
            "errored": summary.errored,
            "skipped": summary.skipped,
        },
        "fixtures": [
            {
                "fixture_id": r.fixture_id,
                "fixture_path": r.fixture_path,
                "status": r.status,
                "duration_seconds": r.duration_seconds,
                "oracle_evidence": r.oracle_evidence,
                "error": r.error,
            }
            for r in results
        ],
    }
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return summary


def write_md_report(
    path: Path,
    *,
    agenteval_version: str,
    adapter: str,
    executed_at: str,
    results: list[FixtureResult],
) -> ReportSummary:
    """Write `conformance-report.md` human-readable summary; return aggregate summary."""
    summary = ReportSummary.from_results(results)
    lines: list[str] = [
        f"# Conformance Report — {adapter} @ {executed_at}",
        "",
        f"agenteval version: `{agenteval_version}`",
        "",
        "## Summary",
        "",
        "| Total | Passed | Failed | Errored | Skipped |",
        "| --- | --- | --- | --- | --- |",
        f"| {summary.total} | {summary.passed} | {summary.failed} | {summary.errored} | {summary.skipped} |",
        "",
    ]
    failures = [r for r in results if r.status in ("failed", "errored")]
    if failures:
        lines.extend(["## First 5 failures", ""])
        for r in failures[:5]:
            err_msg = (r.error or {}).get("message", "(no message)") if r.error else "(no message)"
            err_msg_truncated = err_msg if len(err_msg) <= 200 else err_msg[:197] + "..."
            lines.append(f"- **{r.fixture_id}** (`{r.fixture_path}`) — `{r.status}`: {err_msg_truncated}")
        lines.append("")
    _atomic_write_text(path, "\n".join(lines))
    return summary
