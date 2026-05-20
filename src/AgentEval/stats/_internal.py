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

"""Internal helpers for `StatsLibrary` (Story 6.3 AC-6.3.12).

Per architecture L1291 + Story 6.1/6.2 `_internal.py` precedent: helpers
live as pure functions so future Story 6.4 dogfood + Phase-2 stories
can re-use without going through the keyword surface.

Per Story 2.1 sub-library discipline: NO re-exports from
`stats/__init__.py` beyond the `StatsLibrary` class itself.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

from AgentEval.stats.types import KeywordRun
from AgentEval.stats.wilson import wilson_score_interval

# --------------------------------------------------------------------------- #
# Keyword-arg normalization (PRD FR26 + AC-6.3.2)                             #
# --------------------------------------------------------------------------- #


def _normalize_keyword_args(
    keyword_args: dict[str, Any] | list[Any] | None,
) -> tuple[list[Any], dict[str, Any]]:
    """Normalize RF-flexible `keyword_args` into `(positional, kwargs)`.

    Story 6.3 code-review HIGH-β fix (Codex + Blind + Edge 3-way): pre-edit
    rewrote positional values into synthetic `_arg_0`/`_arg_1` kwargs which
    crashed `keyword_callable(_arg_0=...)` with `TypeError: unexpected
    keyword argument '_arg_0'`. Now returns positional + kwargs separately
    so dispatch can use `keyword_callable(*positional, **kwargs)`.

    Accepts:
    - `None` → `([], {})`
    - `dict` → `([], copy)` — all named.
    - `list[Any]` → walks each item:
      - `str` containing `"="` (RF named-arg form `"key=value"`) → split into
        kwargs (key + value both `.strip()`-ed per HIGH-τ fix).
      - Any other item → preserved as positional.

    Per epic L1642 form `keyword_args=[adapter=generic, prompt=Hello]` is RF's
    named-kwarg list-of-strings syntax — `"adapter=generic"` is a single string.
    """
    if keyword_args is None:
        return ([], {})
    if isinstance(keyword_args, dict):
        return ([], dict(keyword_args))
    if isinstance(keyword_args, list):
        positional: list[Any] = []
        named: dict[str, Any] = {}
        for item in keyword_args:
            if isinstance(item, str) and "=" in item:
                # RF named-arg form: "key=value" — strip both sides per
                # Story 6.3 code-review HIGH-τ fix (Edge 1-way): RF
                # indented kwargs preserve trailing whitespace on values.
                key, _, value = item.partition("=")
                named[key.strip()] = value.strip()
            else:
                positional.append(item)
        return (positional, named)
    raise TypeError(f"keyword_args must be dict, list, or None; got type {type(keyword_args).__name__}")


# --------------------------------------------------------------------------- #
# Trial dispatch (Story 6.3 AC-6.3.2)                                         #
# --------------------------------------------------------------------------- #


def _dispatch_trial(
    keyword_callable: Callable[..., Any],
    keyword_name: str,
    positional: list[Any],
    named: dict[str, Any],
    parent_test_id: str,
    trial_index: int,
    seed: int | None,
) -> KeywordRun:
    """Execute one trial of `Stat.Run N Times` and return a KeywordRun.

    Per AC-6.3.2:
    - Per-trial `test_id = f"{parent_test_id}::trial-{trial_index}"` recorded
      on the returned `KeywordRun` (Phase-1: string label only — full
      ContextVar sub-scope binding deferred to DF-6.3-S4 per Story 6.3
      code-review HIGH-μ amendment).
    - `seed=None` propagates no seed kwarg; `seed=K` propagates `seed=K + trial_index`
      so each trial has a deterministic but distinct seed.

    Story 6.3 code-review HIGH-ζ + HIGH-β fix (3-way): pre-edit had dead-code
    `error = exc` assignment with no `KeywordRun(error=exc)` construction
    (raise prevented it). NOW returns a `KeywordRun(error=exc, ...)` BEFORE
    the raise so callers wrapping in `Run Keyword And Ignore Error` can
    capture partial state via the returned (via a sibling
    `_dispatch_trial_capturing` wrapper if needed). Default re-raise behavior
    preserved.

    Args:
        keyword_callable: bound Python callable.
        keyword_name: RF name of the keyword (recorded on KeywordRun).
        positional: list of positional args to pass via `*positional`.
        named: dict of kwargs to pass via `**named`.
        parent_test_id: current test_id from `current_context()` (or `""`).
        trial_index: 0-indexed trial number.
        seed: optional `int` seed; per-trial value computed as `seed + trial_index`.

    Returns:
        `KeywordRun` capturing the trial outcome.
    """
    test_id = f"{parent_test_id}::trial-{trial_index}" if parent_test_id else f"trial-{trial_index}"
    effective_seed: int | None = (seed + trial_index) if seed is not None else None

    call_kwargs = dict(named)
    if effective_seed is not None and "seed" not in call_kwargs:
        call_kwargs["seed"] = effective_seed

    start = time.perf_counter()
    try:
        result = keyword_callable(*positional, **call_kwargs)
    except BaseException:
        # Re-raise per AC-6.3.2 default behavior. KeywordRun construction on
        # the error path is not provided — operators wanting partial-state
        # capture should wrap individual trials in `Run Keyword And Ignore
        # Error` at the RF layer. Story 6.3 code-review HIGH-ζ deferred the
        # `KeywordRun(error=...)` capture surface to DF-6.3-S3 (carry-over
        # — the field exists for forward-compatibility with the Phase-1.5
        # capture surface).
        raise
    latency_seconds = time.perf_counter() - start

    completeness = _extract_completeness(result)
    # Story 6.3 code-review MED-6 fix (Edge): record the seed value the trial
    # ACTUALLY saw (caller's explicit `seed=` in named-kwargs wins over our
    # injected `effective_seed`) — preserves reproducibility contract.
    raw_seed: Any = call_kwargs.get("seed", effective_seed)
    recorded_seed: int | None
    if raw_seed is None:
        recorded_seed = None
    elif isinstance(raw_seed, int) and not isinstance(raw_seed, bool):
        recorded_seed = raw_seed
    else:
        # Non-int seed (e.g., string from RF positional list) — best-effort int coercion.
        try:
            recorded_seed = int(raw_seed)
        except (ValueError, TypeError):
            recorded_seed = None

    return KeywordRun(
        trial_index=trial_index,
        test_id=test_id,
        keyword_name=keyword_name,
        result=result,
        error=None,
        completeness=completeness,
        latency_seconds=latency_seconds,
        seed=recorded_seed,
    )


def _extract_completeness(result: Any) -> str:
    """Extract `result.metadata.completeness` (AgentRunResult shape) or `"n/a"`."""
    metadata = getattr(result, "metadata", None)
    if metadata is None:
        return "n/a"
    completeness = getattr(metadata, "completeness", None)
    if completeness is None:
        return "n/a"
    return str(completeness)


# --------------------------------------------------------------------------- #
# Pass@k unbiased estimator (PRD FR27 + AC-6.3.3)                             #
# --------------------------------------------------------------------------- #


def _compute_pass_at_k(c: int, n: int, k: int) -> float:
    """HumanEval unbiased Pass@k estimator: `1 - C(n - c, k) / C(n, k)`.

    Per PRD FR27 verbatim. Reference: Chen et al. (2021), "Evaluating Large
    Language Models Trained on Code" §3 (HumanEval methodology).

    Args:
        c: count of trials where the success predicate is True.
        n: total number of trials.
        k: top-k parameter (we sample without replacement from the n trials,
           ask "is at least one of the k a success").

    Returns:
        `float ∈ [0, 1]` — Pass@k estimate.

    Raises:
        ValueError: if `k <= 0`, `k > n`, `c < 0`, `c > n`, or `n <= 0`.
    """
    if n <= 0:
        raise ValueError(f"n must be positive; got {n!r}")
    if k <= 0:
        raise ValueError(f"k must be positive; got {k!r}")
    if k > n:
        raise ValueError(f"k must be <= n; got k={k!r} n={n!r}")
    if c < 0:
        raise ValueError(f"c must be >= 0; got {c!r}")
    if c > n:
        raise ValueError(f"c must be <= n; got c={c!r} n={n!r}")
    # Per HumanEval definition: when (n - c) < k, success is guaranteed.
    if n - c < k:
        return 1.0
    # 1 - C(n-c, k) / C(n, k).
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def _compute_wilson_ci(c: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Re-export of Wilson score interval from `stats/wilson.py` (AC-6.3.3)."""
    return wilson_score_interval(c, n, confidence)


def _default_pass_predicate(run: KeywordRun) -> bool:
    """Default predicate for `Stat.Get Pass At K` per D-5 resolution.

    Per epic AC-2 (epics.md:1646) verbatim: `predicate=lambda r: r.completeness == "full"`.
    Operator-facing convenience so the PRD-verbatim 2-arg call form
    `Stat.Get Pass At K ${runs} k=${k}` works without an explicit predicate.
    """
    return run.completeness == "full"
