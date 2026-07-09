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

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line; libdoc renders them correctly. The per-line 120-char
# limit is waived for this file per the Phase 2 docstring-refresh convention.

"""``BaselineLibrary`` — regression baseline tracking (OpenSpec ``add-regression-baseline-tracking``).

Three unprefixed Tier-1 keywords (core run-measure-assert loop idiom, design D9):

- ``Save Metrics Baseline`` → snapshot named metrics (with successes/trials +
  raw per-trial samples) to a deterministic, redacted, schema-versioned JSON
  file designed for committing to git; optionally append one JSONL history line.
- ``Metrics Should Not Regress`` → load a committed baseline + compare a new run
  with tolerance- and CI-overlap-aware per-metric regression detection
  (proportions: Wilson-CI-disjoint AND-rule; continuous: relative tolerance +
  Mann-Whitney U). A within-CI drop PASSES with ``PossibleRegressionWarning``;
  a real drop beyond tolerance FAILS. Statistical degradation / underpower is
  loud (``DegradedComparisonWarning`` / ``UnderpoweredComparisonWarning``).
- ``Get Metric Trend`` → read the append-mode JSONL history into a
  ``TrendSeries`` (per-point value + recomputed Wilson CI) plus an optional
  metrics × snapshots ``TrendGrid`` reusing the ``_heatmap`` ASCII renderer.

Composed into ``_SUB_LIBRARIES`` so keywords resolve under a single
``Library    AgentEval`` import; also importable standalone
(``Library    AgentEval.baseline.library.BaselineLibrary``).

References:
    - add-regression-baseline-tracking design D1-D10 + spec.
    - PRD FR10a (Wilson CI) + FR27 (Pass@k) + FR29a (Mann-Whitney U) reused.
    - docs/contracts/metrics-baseline-schema.json (published schema).
"""

from __future__ import annotations

import datetime as _datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.baseline import comparison as _comparison
from AgentEval.baseline import schema as _schema
from AgentEval.baseline._gitmeta import capture_git_metadata
from AgentEval.baseline.extraction import extract_metrics
from AgentEval.baseline.models import (
    MetricsBaseline,
    ProportionEvidence,
    RegressionReport,
    RunContext,
    TrendGrid,
    TrendPoint,
    TrendSeries,
)
from AgentEval.errors import BaselineNotFoundError, BaselineWriteError
from AgentEval.stats.wilson import wilson_score_interval

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["BaselineLibrary"]

# Browser-Library-style docstring migration marker.
_BROWSER_STYLE_MIGRATED = True

_logger = logging.getLogger("AgentEval.baseline")


def _coerce_k(k: int | list[int] | None) -> list[int]:
    if k is None:
        return [1]
    if isinstance(k, int):
        return [k]
    return [int(x) for x in k]


class BaselineLibrary:
    """Regression baseline snapshot + comparison + trend keyword surface (design D9).

    All three keywords are ``@tier(1)`` — deterministic file IO + arithmetic,
    no LLM calls, no polling. The library takes no constructor budget kwargs
    (no Tier-3 fan-out), matching the ``HeatmapLibrary`` shape.
    """

    def __init__(self, **kwargs: Any) -> None:
        # No budget plumbing needed (all Tier-1). Accept + ignore stray kwargs
        # for composition robustness.
        del kwargs

    # ------------------------------------------------------------------ #
    # Save Metrics Baseline (Tier-1)                                     #
    # ------------------------------------------------------------------ #

    @keyword(name="Save Metrics Baseline")
    @tier(1)
    def save_metrics_baseline(
        self,
        results: list[Any],
        path: str | Path,
        *,
        history: str | Path | None = None,
        predicate: Callable[[Any], bool] | None = None,
        k: int | list[int] | None = None,
        expected_tools: list[str] | None = None,
        extra_metrics: dict[str, float] | None = None,
        model: str | None = None,
        adapter_name: str | None = None,
        adapter_version: str | None = None,
        timestamp: str | None = None,
    ) -> MetricsBaseline:
        """Snapshots named metrics (with evidence) to a diff-friendly JSON baseline (design D1/D6).

        [Tier 1 — Deterministic] — computes ``pass_rate``, ``pass_at_k``,
        ``tool_hit_rate`` (when ``expected_tools=`` given), ``cost_usd`` and
        ``latency_p95_ms`` from the ``results`` union and persists them WITH the
        underlying evidence (``successes``/``trials`` for proportions, raw
        per-trial sample lists for continuous metrics) plus ``run_context``
        (model / adapter version / library version / RFC 3339 timestamp / git
        SHA + dirty flag). Serialization is deterministic (``indent=2``,
        sorted keys, trailing newline), redacted at the write boundary, and
        schema-versioned — designed for committing to git.

        | =Arguments= | =Description= |
        | ``results`` | ``list[KeywordRun]`` (from ``Stat.Run N Times``) OR ``list[AgentRunResult]``. |
        | ``path`` | Destination JSON file (parent dirs are created). Convention: ``baselines/main.json``. |
        | ``history`` | Optional JSONL history path; when given, ONE compact snapshot line is appended (never truncates). |
        | ``predicate`` | Optional success predicate; default ``completeness == "complete"`` (ratified `Stat.Get Pass At K` default). |
        | ``k`` | ``int`` or list of ints for ``pass_at_k`` (default ``1``). |
        | ``expected_tools`` | Tool names for ``tool_hit_rate`` (omitted when absent). |
        | ``extra_metrics`` | User-supplied named scalars (compared point-only later). |
        | ``model`` / ``adapter_name`` / ``adapter_version`` | Optional ``run_context`` labels. |
        | ``timestamp`` | Optional RFC 3339 override; defaults to the current UTC time. |

        Raises ``BaselineWriteError`` (structured File/Line/Field/Fix) on any
        write failure — a silently missing baseline would fake-green the CI
        gate built on it (design D6). Unavailable metric families are omitted
        and logged, never zero-filled.

        Example:
        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
        | ${baseline} =    `Save Metrics Baseline`    ${runs}    path=baselines/main.json    history=baselines/history.jsonl
        | Should Be Equal As Integers    ${baseline.metrics['pass_rate'].trials}    20

        Notes:
        - Design Decision 1 (store evidence, not verdicts) + Decision 6 (deterministic redacted JSON).
        - Sibling keywords: `Metrics Should Not Regress`, `Get Metric Trend`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        from AgentEval import __version__ as _library_version

        extraction = extract_metrics(
            list(results),
            predicate=predicate,
            k_list=_coerce_k(k),
            expected_tools=list(expected_tools) if expected_tools else None,
            extra_metrics=extra_metrics,
        )
        git_sha, git_dirty = capture_git_metadata()
        ts = timestamp or _datetime.datetime.now(_datetime.UTC).isoformat()
        run_context = RunContext(
            model=model,
            adapter_name=adapter_name,
            adapter_version=adapter_version,
            library_version=_library_version,
            timestamp=ts,
            git_sha=git_sha,
            git_dirty=git_dirty,
        )
        baseline = MetricsBaseline(
            schema_version=_schema.SCHEMA_VERSION,
            metrics=extraction.metrics,
            extra_metrics=extraction.extra_metrics,
            run_context=run_context,
        )

        self._write_baseline(baseline, Path(path))
        if history is not None:
            self._append_history(baseline, Path(history))
        if extraction.omitted:
            _logger.info("Save Metrics Baseline: %d metric(s) omitted: %s", len(extraction.omitted), extraction.omitted)
        return baseline

    @staticmethod
    def _write_baseline(baseline: MetricsBaseline, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_schema.serialize(baseline), encoding="utf-8")
        except (OSError, ValueError, TypeError) as exc:
            raise BaselineWriteError(
                f"could not write baseline to {path}: {exc}",
                file_path=str(path),
                field_name=None,
                fix_suggestion=(
                    "Check filesystem permissions + disk space at the target directory. "
                    "The baseline was NOT written; the CI gate would fake-green without it."
                ),
            ) from exc

    @staticmethod
    def _append_history(baseline: MetricsBaseline, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(_schema.serialize_line(baseline))
        except (OSError, ValueError, TypeError) as exc:
            raise BaselineWriteError(
                f"could not append snapshot to history {path}: {exc}",
                file_path=str(path),
                field_name=None,
                fix_suggestion="Check filesystem permissions + disk space at the history directory.",
            ) from exc

    # ------------------------------------------------------------------ #
    # Metrics Should Not Regress (Tier-1)                                #
    # ------------------------------------------------------------------ #

    @keyword(name="Metrics Should Not Regress")
    @tier(1)
    def metrics_should_not_regress(
        self,
        results: list[Any],
        baseline: str | Path,
        *,
        tolerance: str | float = "5%",
        tolerances: dict[str, str | float] | None = None,
        confidence: float = 0.95,
        predicate: Callable[[Any], bool] | None = None,
        expected_tools: list[str] | None = None,
        directions: dict[str, str] | None = None,
    ) -> RegressionReport:
        """Asserts a new run has not regressed vs a committed baseline (design D2/D3/D7).

        [Tier 1 — Deterministic] — loads ``baseline=``, recomputes the same
        metric set from ``results``, and applies the honest, direction-aware
        rule. Proportion metrics FAIL only when the drop exceeds ``tolerance``
        (absolute percentage points) AND the Wilson CIs are disjoint — a
        within-CI drop PASSES and emits ``PossibleRegressionWarning``.
        Continuous metrics use relative tolerance + a one-sided Mann-Whitney U
        (when raw samples + the ``[agenteval-advanced]`` extra are present);
        otherwise they degrade to tolerance-only and emit
        ``DegradedComparisonWarning``. Underpowered proportion comparisons emit
        ``UnderpoweredComparisonWarning``. Run-context mismatch is reported,
        never gated.

        | =Arguments= | =Description= |
        | ``results`` | New-run ``list[KeywordRun]`` OR ``list[AgentRunResult]``. |
        | ``baseline`` | Path to the committed baseline JSON. |
        | ``tolerance`` | ``"5%"`` (default) = 5 pp absolute for proportions, 5% relative for continuous. |
        | ``tolerances`` | Per-metric override map, e.g. ``{"cost_usd": "10%"}``. |
        | ``confidence`` | Wilson CI confidence level (default ``0.95``). |
        | ``predicate`` | Optional success predicate (default ``completeness == "complete"``). |
        | ``expected_tools`` | Needed to compare ``tool_hit_rate`` (else skipped). |
        | ``directions`` | Optional per-metric direction override (``higher_is_better`` / ``lower_is_better``). |

        On regression, RAISES ``AssertionError`` whose message quotes every
        per-metric number (both points, both CIs, tolerance semantics restated
        numerically, both trial counts) so the failure is a numeric bar, not a
        vibe. On pass, RETURNS the ``RegressionReport`` (per-metric verdicts).

        Raises ``BaselineNotFoundError`` when ``baseline=`` does not exist (with
        the save-then-commit fix), ``BaselineSchemaError`` on version/shape
        drift.

        Example:
        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
        | ${report} =    `Metrics Should Not Regress`    ${runs}    baseline=baselines/main.json    tolerance=5%
        | Should Be Equal    ${report.regressed}    ${FALSE}

        Notes:
        - Design Decision 2 (proportion AND-rule) + Decision 3 (continuous rank test) + Decision 7 (context reported not gated).
        - Sibling keywords: `Save Metrics Baseline`, `Get Metric Trend`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        base = self._load_baseline(Path(baseline))

        # Recompute current with the SAME k set the baseline stored, so the
        # pass_at_k comparison is symmetric.
        k_values = sorted(
            {ev.k for ev in base.metrics.values() if isinstance(ev, ProportionEvidence) and ev.k is not None}
        ) or [1]
        extraction = extract_metrics(
            list(results),
            predicate=predicate,
            k_list=k_values,
            expected_tools=list(expected_tools) if expected_tools else None,
        )
        from AgentEval import __version__ as _library_version

        current = MetricsBaseline(
            schema_version=_schema.SCHEMA_VERSION,
            metrics=extraction.metrics,
            extra_metrics=extraction.extra_metrics,
            run_context=RunContext(library_version=_library_version),
        )

        report = _comparison.compare(
            base,
            current,
            tolerance=tolerance,
            tolerances=tolerances,
            directions=directions,
            confidence=confidence,
        )

        if report.regressed:
            lines = [
                "Metrics regressed beyond tolerance vs the committed baseline "
                f"({Path(baseline)}):",
            ]
            for c in report.failures():
                lines.append(f"  - {c.metric}: {c.reason}")
            lines.append(
                f"  Baseline run_context: model={base.run_context.model!r} "
                f"adapter={base.run_context.adapter_name!r}/{base.run_context.adapter_version!r} "
                f"git={base.run_context.git_sha!r}"
            )
            lines.append(
                "  Fix: if this regression is intentional, re-snapshot with "
                "`Save Metrics Baseline` and commit the updated baseline. If it is flaky, "
                "raise n in `Stat.Run N Times` (do NOT raise tolerance)."
            )
            raise AssertionError("\n".join(lines))
        return report

    @staticmethod
    def _load_baseline(path: Path) -> MetricsBaseline:
        if not path.exists():
            raise BaselineNotFoundError(
                f"baseline file not found: {path}",
                file_path=str(path),
                field_name=None,
                fix_suggestion=(
                    "Run `Save Metrics Baseline` to create the baseline, then commit the file "
                    "so CI can gate against it."
                ),
            )
        return _schema.load(path.read_text(encoding="utf-8"), source=str(path))

    # ------------------------------------------------------------------ #
    # Get Metric Trend (Tier-1)                                          #
    # ------------------------------------------------------------------ #

    @keyword(name="Get Metric Trend")
    @tier(1)
    def get_metric_trend(
        self,
        metric: str,
        history: str | Path,
    ) -> TrendSeries:
        """Reads the append-mode JSONL history into a time-ordered `TrendSeries` (design D8).

        [Tier 1 — Deterministic] — parses each snapshot line (corrupt lines are
        skipped with a logged warning), and returns a ``TrendSeries`` of
        ``TrendPoint``s for ``metric`` in append order. Each point carries
        ``value`` + Wilson ``ci_lower``/``ci_upper`` (recomputed from the stored
        ``successes``/``trials`` for proportion metrics, else ``None``),
        ``n_trials``, ``git_sha``, ``timestamp`` and ``model``. Snapshots that
        lack the requested metric surface as a MISSING point (``value=None``),
        never ``0.0``. The returned series also carries ``.grid`` — a metrics ×
        snapshots ``TrendGrid`` (reusing the ``_heatmap`` ASCII renderer).

        | =Arguments= | =Description= |
        | ``metric`` | Metric name, e.g. ``pass_at_1`` / ``pass_rate`` / ``cost_usd`` / ``latency_p95_ms``. |
        | ``history`` | Path to the JSONL history written by ``Save Metrics Baseline``'s ``history=``. |

        Raises ``BaselineNotFoundError`` when ``history=`` does not exist.

        Example:
        | ${series} =    `Get Metric Trend`    metric=pass_at_1    history=baselines/history.jsonl
        | Length Should Be    ${series.points}    3
        | Log    ${series.grid.as_ascii()}

        Notes:
        - Design Decision 8 (TrendSeries + grid reuse of `_heatmap`).
        - Sibling keywords: `Save Metrics Baseline`, `Metrics Should Not Regress`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        path = Path(history)
        if not path.exists():
            raise BaselineNotFoundError(
                f"history file not found: {path}",
                file_path=str(path),
                field_name=None,
                fix_suggestion="Pass `history=` to `Save Metrics Baseline` to accumulate a history first.",
            )

        snapshots = self._read_history(path)
        points: list[TrendPoint] = []
        for snap in snapshots:
            metrics = snap.get("metrics", {}) or {}
            rc = snap.get("run_context", {}) or {}
            payload = metrics.get(metric)
            if not isinstance(payload, dict):
                points.append(
                    TrendPoint(
                        timestamp=rc.get("timestamp"),
                        git_sha=rc.get("git_sha"),
                        value=None,
                        ci_lower=None,
                        ci_upper=None,
                        n_trials=None,
                        model=rc.get("model"),
                    )
                )
                continue
            ci_lower: float | None = None
            ci_upper: float | None = None
            n_trials: int | None = None
            if payload.get("kind") == "proportion":
                successes = int(payload.get("successes", 0))
                trials = int(payload.get("trials", 0))
                n_trials = trials
                if trials > 0:
                    ci_lower, ci_upper = wilson_score_interval(successes, trials)
            elif payload.get("kind") == "continuous":
                n_trials = len(payload.get("samples", []) or [])
            value = payload.get("value")
            points.append(
                TrendPoint(
                    timestamp=rc.get("timestamp"),
                    git_sha=rc.get("git_sha"),
                    value=(float(value) if value is not None else None),
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    n_trials=n_trials,
                    model=rc.get("model"),
                )
            )

        labels = [f"snap{i}" for i in range(len(snapshots))]
        grid = TrendGrid.from_snapshots(snapshots, labels)
        return TrendSeries(metric=metric, points=tuple(points), grid=grid)

    @staticmethod
    def _read_history(path: Path) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                # validate_metrics=True forces full per-line reconstruction so a line
                # that is valid JSON + schema_version but has malformed metric evidence
                # (e.g. successes="oops") is skipped+warned here, not crashed on later
                # during trend coercion (MED-2).
                snapshots.append(_schema.parse_snapshot(line, source=f"{path}:{lineno}", validate_metrics=True))
            except Exception as exc:  # noqa: BLE001 — skip+warn on corrupt lines (design 4.1)
                _logger.warning("Get Metric Trend: skipping corrupt history line %d in %s: %s", lineno, path, exc)
        return snapshots
