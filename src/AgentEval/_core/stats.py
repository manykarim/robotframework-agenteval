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

"""Stochastic-run statistics: run N times, pass@k, Wilson interval.

Tier-3 keywords are noisy, so you run them N times and reason about the spread.
``run_n`` gathers trials, ``pass_at_k`` gives the unbiased HumanEval estimate,
and ``wilson_interval`` puts a confidence band on the success proportion. The
cross-arm A/B tests (Mann-Whitney, Cliff's delta, bootstrap) deliberately do
not live here.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "KeywordRun",
    "run_n",
    "pass_at_k",
    "wilson_interval",
    "default_pass_predicate",
]


@dataclass(frozen=True, slots=True)
class KeywordRun:
    """One trial from ``run_n``.

    ``result`` is whatever the callable returned; ``error`` holds the exception
    if it raised. ``completeness`` mirrors ``result.metadata.completeness`` for
    an ``AgentRunResult``, else ``"n/a"``.
    """

    trial_index: int
    result: Any
    error: BaseException | None
    completeness: str
    latency_seconds: float


def run_n(
    callable_: Callable[..., Any],
    n: int,
    *args: Any,
    **kwargs: Any,
) -> list[KeywordRun]:
    """Run ``callable_`` ``n`` times and return a ``KeywordRun`` per trial.

    Trial errors are captured on the ``KeywordRun`` rather than raised, so a
    partial fan-out still yields analyzable results.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1; got {n!r}")

    runs: list[KeywordRun] = []
    for trial_index in range(n):
        start = time.perf_counter()
        result: Any = None
        error: BaseException | None = None
        try:
            result = callable_(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - captured per trial for post-hoc analysis
            error = exc
        latency_seconds = time.perf_counter() - start
        runs.append(
            KeywordRun(
                trial_index=trial_index,
                result=result,
                error=error,
                completeness=_extract_completeness(result),
                latency_seconds=latency_seconds,
            )
        )
    return runs


def _extract_completeness(result: Any) -> str:
    """Read ``result.metadata.completeness`` if present, else ``"n/a"``."""
    metadata = getattr(result, "metadata", None)
    completeness = getattr(metadata, "completeness", None)
    return str(completeness) if completeness is not None else "n/a"


def default_pass_predicate(run: KeywordRun) -> bool:
    """Default pass test for pass@k.

    A trial passes when it did not raise and its completeness is not a
    known-bad value. Trials that carry no completeness signal (plain callables,
    non-agent results) count as passing - this is the fix for the old footgun
    where the default demanded a specific ``completeness`` literal, silently
    scoring every plain-callable run 0.
    """
    if run.error is not None:
        return False
    return run.completeness not in ("truncated", "partial")


def pass_at_k(
    runs: list[KeywordRun],
    k: int,
    predicate: Callable[[KeywordRun], bool] | None = None,
) -> float:
    """HumanEval unbiased pass@k over ``runs``: ``1 - C(n-c, k) / C(n, k)``.

    ``predicate`` classifies each trial as pass/fail; defaults to
    ``default_pass_predicate``.
    """
    predicate_fn = predicate if predicate is not None else default_pass_predicate
    n = len(runs)
    c = sum(1 for run in runs if predicate_fn(run))
    return _compute_pass_at_k(c, n, k)


def _compute_pass_at_k(c: int, n: int, k: int) -> float:
    """Closed-form unbiased pass@k estimator."""
    if n <= 0:
        raise ValueError(f"n must be positive; got {n!r}")
    if k <= 0:
        raise ValueError(f"k must be positive; got {k!r}")
    if k > n:
        raise ValueError(f"k must be <= n; got k={k!r} n={n!r}")
    if c < 0 or c > n:
        raise ValueError(f"c must be in [0, n]; got c={c!r} n={n!r}")
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation for small samples or extreme
    proportions. Returns ``(lower, upper)`` in ``[0, 1]``.
    """
    if trials < 0:
        raise ValueError(f"trials must be >= 0; got {trials!r}")
    if successes < 0:
        raise ValueError(f"successes must be >= 0; got {successes!r}")
    if successes > trials:
        raise ValueError(f"successes must be <= trials; got successes={successes!r} trials={trials!r}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1); got {confidence!r}")

    if trials == 0:
        return (0.0, 1.0)

    z = _standard_normal_quantile((1.0 + confidence) / 2.0)
    n = float(trials)
    p_hat = successes / n
    denom = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2.0 * n)) / denom
    margin = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + (z * z) / (4.0 * n * n))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _standard_normal_quantile(p: float) -> float:
    """Inverse standard-normal CDF via Beasley-Springer-Moro (accurate to ~1e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p!r}")

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )
