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

"""Conformance CLI main loop (Story 8a.2 AC-8a.2.3).

Phase-1 design notes:

- Fixture discovery walks ``tests/conformance/fixtures/**/*.json`` (the
  Story 1b.5 layout); a future Phase-1.5 enhancement may relocate fixtures
  under a packaged path so the CLI works from an installed wheel without
  the repo tree.
- Fixture execution: Phase-1 records each fixture as `skipped` with a
  rationale (`adapter=<name>` not yet wired to the fixture-execute loop).
  The CLI's primary value in Phase-1 is the **schema + shape** of the
  report; Phase-1.5 / Epic 9 will wire real adapter dispatch.
- Exit code: 0 if no failures, 70 (EX_SOFTWARE) per
  `cli.error_code_to_exit_code` fallback if any fixtures failed/errored.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from AgentEval import __version__ as _agenteval_version
from AgentEval.cli import EXIT_CODE_FALLBACK
from AgentEval.conformance._report import (
    FixtureResult,
    write_json_report,
    write_md_report,
)

__all__ = ["main"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse `python -m AgentEval.conformance` arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m AgentEval.conformance",
        description=(
            "Generate a conformance report (JSON + Markdown) for the configured "
            "adapter per PRD FR57. Phase-1 ships report-shape + atomic-write + "
            "fixture-discovery; per-adapter fixture execution wires in Phase-1.5."
        ),
    )
    parser.add_argument(
        "--adapter",
        default="mock",
        help=(
            "Adapter name to test (default: mock). Phase-1: only `mock` is "
            "wired; other adapter names produce a `skipped` fixture record "
            "with a deferral rationale."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "conformance-report",
        help=(
            "Directory to write `conformance-report.json` + "
            "`conformance-report.md` (created if absent; default: "
            "./conformance-report/)."
        ),
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing conformance fixtures (default: "
            "auto-discovered from `tests/conformance/fixtures/` relative "
            "to CWD; falls back to the agenteval-installed fixture path)."
        ),
    )
    return parser.parse_args(argv)


def _discover_fixtures(fixtures_dir: Path | None) -> list[Path]:
    """Discover conformance-fixture JSON files.

    Phase-1: scans `tests/conformance/fixtures/**/*.json` relative to CWD if
    `fixtures_dir` is None. If the directory doesn't exist, returns an
    empty list (which produces a valid report with `total=0`).
    """
    candidate = Path.cwd() / "tests" / "conformance" / "fixtures" if fixtures_dir is None else fixtures_dir
    if not candidate.exists() or not candidate.is_dir():
        return []
    # `fixture-schema.json` at the top level is the schema, not a fixture.
    return sorted(
        path
        for path in candidate.rglob("*.json")
        if path.name != "fixture-schema.json" and path.name != "static-inspection-fixture-schema.json"
    )


def _execute_fixture(fixture_path: Path, *, adapter: str) -> FixtureResult:
    """Phase-1 fixture execution: records `skipped` with deferral rationale.

    Phase-1.5 will wire real adapter dispatch via the Story 1b.5 harness.
    For now, the CLI's value is the report schema + shape; this function
    returns a deterministic `skipped` record so the JSON + Markdown reports
    are well-formed.
    """
    start = time.monotonic()
    duration = time.monotonic() - start
    return FixtureResult(
        fixture_id=fixture_path.stem,
        fixture_path=str(fixture_path),
        status="skipped",
        duration_seconds=duration,
        oracle_evidence={},
        error={
            "type": "Phase1Deferral",
            "message": (
                f"Per-fixture execution against adapter={adapter!r} is "
                "deferred to Phase-1.5; Story 8a.2 ships report-shape + "
                "atomic-write + discovery only. See "
                "deferred-work.md DF-8a.2-S1 / C63."
            ),
        }
        if adapter != "mock"
        else None,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 if no failures/errors, ``EXIT_CODE_FALLBACK`` (70) otherwise.
    """
    args = _parse_args(argv)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fixtures = _discover_fixtures(args.fixtures_dir)
    results = [_execute_fixture(fx, adapter=args.adapter) for fx in fixtures]

    executed_at = datetime.now(UTC).isoformat(timespec="seconds")
    json_summary = write_json_report(
        output_dir / "conformance-report.json",
        agenteval_version=_agenteval_version,
        adapter=args.adapter,
        executed_at=executed_at,
        results=results,
    )
    write_md_report(
        output_dir / "conformance-report.md",
        agenteval_version=_agenteval_version,
        adapter=args.adapter,
        executed_at=executed_at,
        results=results,
    )

    # Human-readable summary on stderr per PRD FR57 ("human-readable summary
    # on stderr (pass/fail count + first 5 failure summaries + link to full
    # report)" — Phase-1: link only, no failure summaries since fixtures are
    # all skipped pending Phase-1.5 wiring).
    sys.stderr.write(
        f"agenteval conformance: {json_summary.total} fixtures discovered "
        f"(adapter={args.adapter}); "
        f"passed={json_summary.passed} failed={json_summary.failed} "
        f"errored={json_summary.errored} skipped={json_summary.skipped}. "
        f"Full report: {output_dir / 'conformance-report.json'}\n"
    )

    # FR57: machine-readable JSON path on stdout (CI consumers parse).
    sys.stdout.write(str(output_dir / "conformance-report.json") + "\n")

    if json_summary.failed or json_summary.errored:
        return EXIT_CODE_FALLBACK
    return 0
