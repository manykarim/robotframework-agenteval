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

"""Statistical primitives RF-keyword surface (Story 6.3 / PRD FR26 + FR27 + FR31a).

Ships 4 `@keyword`-decorated methods on `StatsLibrary`:

- FR26: `Stat.Run N Times` (Tier-3 fan-out via `@guarded_fanout`) — independent-
  sample N-trial runner; returns `list[KeywordRun]` per Story 1b.6 ratified
  return type.
- FR27: `Stat.Get Pass At K` (Tier-1) — HumanEval unbiased estimator; returns
  `float ∈ [0, 1]`.
- D-1 resolution paired getter: `Stat.Get Pass At K Confidence Interval` (Tier-1)
  — Wilson score interval at `confidence` level.
- FR31a: `Stat.Assert Run Determinism` (Tier-1) — runs a Tier-1 keyword twice,
  asserts bit-identical output.

Sub-library registration via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.
Tier-3 `Stat.Run N Times` reads `_max_cost_usd` + `_max_runtime_seconds`
from `self` (forwarded from top-level `AgentEval(...)` per Story 1a.6 +
Story 4.3 propagation pattern).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.context import current_context
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.redaction import redact
from AgentEval._kernel.tier import tier
from AgentEval.errors import TierViolationError
from AgentEval.stats import _internal
from AgentEval.stats.types import KeywordRun

__all__ = ["StatsLibrary"]


class StatsLibrary:
    """4 `@keyword`-decorated statistical primitives (Story 6.3 / PRD FR26-FR31a)."""

    def __init__(
        self,
        max_cost_usd: float | None = None,
        max_runtime_seconds: float | None = None,
    ) -> None:
        """Library-level cost/runtime budgets per Story 1a.6 + ADR-015.

        Forwarded from top-level `AgentEval(max_cost_usd=..., max_runtime_seconds=...)`
        via `_build_components` per Story 4.3 pattern. Consumed by `@guarded_fanout`
        on `Stat.Run N Times` (Tier-3 fan-out keyword).
        """
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds

    # ----------------------------------------------------------------- #
    # FR26 — Stat.Run N Times (Tier-3 fan-out)                          #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Run N Times")
    @tier(3)
    @guarded_fanout()
    def run_n_times(
        self,
        n: int,
        keyword: str | Callable[..., Any],
        keyword_args: dict[str, Any] | list[Any] | None = None,
        seed: int | None = None,
    ) -> list[KeywordRun]:
        """[Tier 3 — Stochastic Fan-Out] Run a keyword `n` times independently (PRD FR26).

        Args:
            n: Number of independent trials. Must be `>= 1`.
            keyword: RF keyword name (`str`) OR a Python callable. When a string
                is provided, the keyword is resolved via the Robot Framework
                `BuiltIn` library; this requires an active RF execution context.
                When a callable is provided, it's invoked directly (useful for
                pytest unit tests).
            keyword_args: Optional dict OR list of kwargs / RF named-arg strings
                to pass to the wrapped keyword (e.g.,
                `{"adapter": "generic", "prompt": "Hello"}` OR
                `["adapter=generic", "prompt=Hello"]`). `None` = no args.
            seed: Optional `int` seed; each trial receives `seed + trial_index`
                via a `seed=` kwarg injection (so trials are deterministic but
                distinct). `None` = OS-entropy seeding per trial.

        Returns:
            `list[KeywordRun]` of length `n` per PRD FR26 + determinism-contract L55.
            Trial-level errors are RE-RAISED from this keyword — operators
            wanting "ignore failures" semantic must wrap in
            `Run Keyword And Ignore Error`.

        Raises:
            ValueError: if `n < 1`.
            CostExceededError / RuntimeBudgetExceededError: per `@guarded_fanout`
                Layer 1/2/3 enforcement (ADR-015).
        """
        if n < 1:
            raise ValueError(f"n must be >= 1; got {n!r}")
        positional, named = _internal._normalize_keyword_args(keyword_args)
        callable_ref: Callable[..., Any]
        kw_name: str
        if isinstance(keyword, str):
            kw_name = keyword
            # Story 6.3 code-review HIGH-γ fix (Codex empirical STAR):
            # `BuiltIn.run_keyword(name, /, *args)` is varargs-only — passing
            # `**kwargs` raises TypeError. Reconstruct RF-style positional +
            # `key=value` tokens that the run_keyword(name, *args) signature
            # accepts.
            from robot.libraries.BuiltIn import BuiltIn

            def callable_ref_impl(*pos: Any, **kw: Any) -> Any:
                rf_args: list[Any] = list(pos)
                for k, v in kw.items():
                    rf_args.append(f"{k}={v}")
                return BuiltIn().run_keyword(kw_name, *rf_args)

            callable_ref = callable_ref_impl
        else:
            callable_ref = keyword
            # Story 6.3 code-review LOW-9 fix (Codex): prefer `robot_name`
            # over Python `__name__` for operator-facing telemetry consistency.
            target = getattr(keyword, "__func__", keyword)
            kw_name = str(
                getattr(target, "robot_name", None) or getattr(keyword, "__name__", repr(keyword))
            )

        ctx = current_context()
        parent_test_id = ctx.test_id if ctx is not None else ""

        runs: list[KeywordRun] = []
        for trial_index in range(n):
            run = _internal._dispatch_trial(
                callable_ref,
                kw_name,
                positional,
                named,
                parent_test_id,
                trial_index,
                seed,
            )
            runs.append(run)
        return runs

    # ----------------------------------------------------------------- #
    # FR27 — Stat.Get Pass At K (Tier-1)                                #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Get Pass At K")
    @tier(1)
    def get_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
        predicate: Callable[[KeywordRun], bool] | None = None,
    ) -> float:
        """[Tier 1 — Deterministic] HumanEval Pass@k estimate (PRD FR27).

        Args:
            runs: List of `KeywordRun` instances (typically from `Stat.Run N Times`).
            k: Top-k parameter for the unbiased estimator. Must satisfy
                `1 <= k <= len(runs)`.
            predicate: Optional `Callable[[KeywordRun], bool]` for pass/fail
                classification. Default (when `None`): `lambda r: r.completeness == "full"`
                per epic AC-2 (D-5 resolution).

        Returns:
            `float ∈ [0, 1]` Pass@k estimate via the HumanEval unbiased estimator
            `1 - C(n-c, k) / C(n, k)`. PRD FR27 verbatim return type — no tuple,
            no dataclass (preserves AssertionEngine `>=` / `<=` matcher compatibility).

        Raises:
            ValueError: if `k < 1`, `k > len(runs)`, or `len(runs) == 0`.
        """
        predicate_fn = predicate if predicate is not None else _internal._default_pass_predicate
        c = sum(1 for r in runs if predicate_fn(r))
        n = len(runs)
        return _internal._compute_pass_at_k(c, n, k)

    @keyword(name="Stat.Get Pass At K Confidence Interval")
    @tier(1)
    def get_pass_at_k_confidence_interval(
        self,
        runs: list[KeywordRun],
        k: int,
        predicate: Callable[[KeywordRun], bool] | None = None,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """[Tier 1 — Deterministic] Wilson score CI for Pass@k (Story 6.3 D-1 paired getter).

        Returns the Wilson score interval at `confidence` level for the
        predicate-pass proportion. Paired with `Stat.Get Pass At K` per the
        D-1 drift resolution (PRD FR27 ratifies scalar `float` return for
        the point estimate; epic AC-2's "with confidence interval per Wilson
        CI" promise is satisfied via this separate getter).

        Args:
            runs: List of `KeywordRun` instances.
            k: Top-k parameter (validated but only used for k-vs-n sanity check;
                the Wilson interval is on the underlying success proportion, not
                the Pass@k estimate itself — interpretation: CI of the latent
                per-trial success probability).
            predicate: Same as `Stat.Get Pass At K`.
            confidence: Confidence level in `(0, 1)`; default 0.95.

        Returns:
            `(ci_lower, ci_upper)` tuple of `float`s in `[0, 1]`.
        """
        predicate_fn = predicate if predicate is not None else _internal._default_pass_predicate
        c = sum(1 for r in runs if predicate_fn(r))
        n = len(runs)
        # Story 6.3 code-review MED Wilson-k fix (Codex MED-7 + Edge MED-11 2-way):
        # validate `k` unconditionally regardless of `n` value. Pre-edit
        # short-circuited validation when `n=0`, silently returning `(0.0, 1.0)`
        # for invalid k values like `k=-5` or `k=99`.
        if k < 1:
            raise ValueError(f"k must be positive; got {k!r}")
        if n > 0 and k > n:
            raise ValueError(f"k must be <= n; got k={k!r} n={n!r}")
        return _internal._compute_wilson_ci(c, n, confidence)

    # ----------------------------------------------------------------- #
    # FR31a — Stat.Assert Run Determinism (Tier-1)                      #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Assert Run Determinism")
    @tier(1)
    def assert_run_determinism(
        self,
        keyword: str | Callable[..., Any],
        keyword_args: dict[str, Any] | list[Any] | None = None,
        expect: str = "byte_identical",
    ) -> None:
        """[Tier 1 — Deterministic] Assert bit-identical Tier-1 output across 2 runs (PRD FR31a).

        Invokes the wrapped keyword twice with identical inputs + compares via
        deep-equality. Phase-1 supports `expect="byte_identical"` only; other
        modes (`"approximate"`, `"schema_identical"`) deferred to Phase-2.

        Args:
            keyword: RF keyword name (`str`) OR callable; same dispatch as
                `Stat.Run N Times`.
            keyword_args: Optional dict / list per `Stat.Run N Times`.
            expect: Comparison mode. Only `"byte_identical"` supported in Phase-1.

        Raises:
            ValueError: if `expect` is not `"byte_identical"`.
            TierViolationError: if the wrapped keyword's tier is not 1 (FR31a
                bit-identical guarantee scoped to Tier-1 only).
            AssertionError: on output mismatch, with a `redact()`-scrubbed diff
                per FR38a (Story 5.3 contract).
        """
        if expect != "byte_identical":
            raise ValueError(
                f"expect must be 'byte_identical' in Phase-1; got {expect!r}. "
                f"Other modes (approximate, schema_identical) deferred to Phase-2."
            )
        positional, named = _internal._normalize_keyword_args(keyword_args)
        callable_ref: Callable[..., Any]
        kw_name: str
        if isinstance(keyword, str):
            kw_name = keyword
            from robot.libraries.BuiltIn import BuiltIn

            builtin = BuiltIn()
            kw_tier = _resolve_keyword_tier_by_name(kw_name, builtin)
            # Story 6.3 code-review HIGH-α fix (4-way Codex empirical + Blind +
            # Edge + Auditor): pre-edit `if kw_tier is not None and kw_tier != 1`
            # silently admitted unknown-tier keywords. Now `None` raises too —
            # unresolved tier is treated as a TierViolationError per FR31a
            # "bit-identical guarantee scoped to Tier-1 only" — we cannot
            # guarantee anything for keywords we can't resolve.
            if kw_tier != 1:
                actual = f"tier {kw_tier}" if kw_tier is not None else "unresolved (tier annotation not found)"
                raise TierViolationError(
                    f"Stat.Assert Run Determinism: keyword {kw_name!r} is {actual}; "
                    f"bit-identical only guaranteed for Tier-1 (FR31a)."
                )

            # Story 6.3 code-review HIGH-γ fix (Codex empirical): use varargs form.
            def callable_ref_impl(*pos: Any, **kw: Any) -> Any:
                rf_args: list[Any] = list(pos)
                for k, v in kw.items():
                    rf_args.append(f"{k}={v}")
                return builtin.run_keyword(kw_name, *rf_args)

            callable_ref = callable_ref_impl
        else:
            callable_ref = keyword
            # Story 6.3 code-review HIGH-δ fix (Codex + Blind + Auditor 3-way):
            # `find_tier_through_wrappers` walks the decorator chain so
            # `@tier`-annotated wrapped methods are detected.
            from AgentEval._kernel.tier import find_tier_through_wrappers

            target = getattr(keyword, "__func__", keyword)
            kw_name = str(
                getattr(target, "robot_name", None) or getattr(keyword, "__name__", repr(keyword))
            )
            kw_tier = find_tier_through_wrappers(target)
            # Story 6.3 code-review HIGH-α fix (4-way): callable-form likewise
            # raises on unresolved tier (was silent bypass pre-edit).
            if kw_tier != 1:
                actual = f"tier {kw_tier}" if kw_tier is not None else "unresolved (no @tier annotation)"
                raise TierViolationError(
                    f"Stat.Assert Run Determinism: keyword {kw_name!r} is {actual}; "
                    f"bit-identical only guaranteed for Tier-1 (FR31a)."
                )

        result_1 = callable_ref(*positional, **named)
        result_2 = callable_ref(*positional, **named)
        if not _byte_identical(result_1, result_2):
            # Truncate diff per FR34b (1000-char convention) + redact per FR38a.
            diff_repr = f"result_1={result_1!r}\nresult_2={result_2!r}"
            if len(diff_repr) > 1000:
                diff_repr = diff_repr[:1000] + "...(truncated)"
            raise AssertionError(
                redact(
                    f"Stat.Assert Run Determinism: bit-identical guarantee violated for "
                    f"keyword={kw_name!r}.\n{diff_repr}"
                )
            )


def _byte_identical(a: Any, b: Any) -> bool:
    """Story 6.3 code-review HIGH-ο fix (Blind): NaN-aware equality.

    Python `==` on `float('nan')` returns False, breaking the bit-identical
    guarantee for any Tier-1 keyword returning NaN. This helper does
    structural equality with `math.isnan` short-circuit. For non-float
    values, falls back to `==`. Handles nested containers via recursion.
    """
    import math

    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b
    if type(a) is not type(b):
        # Differing types still allow Python `==` to handle numeric coercion
        # but reject for sequence/dict mismatches.
        return bool(a == b)
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_byte_identical(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_byte_identical(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


def _resolve_keyword_tier_by_name(kw_name: str, builtin: Any) -> int | None:
    """Look up the `_agenteval_tier` for an RF-named keyword via `BuiltIn`.

    Story 6.3 code-review HIGH-δ fix (Codex + Blind + Auditor): walks the
    DynamicCore-composed `keywords` registry (not `dir(lib)` which only
    enumerates direct attrs) + unwraps decorator chains with `inspect.unwrap`
    so wrapped `@tier`-annotated methods are detected.

    Returns the tier int when found + annotated, or `None` when the keyword
    is unknown OR its method has no `@tier` annotation.
    """
    from AgentEval._kernel.tier import find_tier_through_wrappers

    try:
        lib = builtin.get_library_instance("AgentEval")
    except Exception:
        return None
    # DynamicCore `self.keywords` is the canonical {name: bound_method} registry.
    kw_map = getattr(lib, "keywords", None)
    if isinstance(kw_map, dict) and kw_name in kw_map:
        bound = kw_map[kw_name]
        target = getattr(bound, "__func__", bound)
        return find_tier_through_wrappers(target)
    # Fallback: walk direct attrs (some sub-libraries may register outside DynamicCore).
    for attr_name in dir(lib):
        if attr_name.startswith("_"):
            continue
        attr = getattr(lib, attr_name, None)
        target = getattr(attr, "__func__", attr) if attr is not None else None
        if target is None:
            continue
        if getattr(target, "robot_name", None) == kw_name:
            return find_tier_through_wrappers(target)
    return None
