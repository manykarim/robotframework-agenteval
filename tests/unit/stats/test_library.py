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

"""Unit tests for `StatsLibrary` (Story 6.3 AC-6.3.13)."""

from __future__ import annotations

import pytest

from AgentEval.errors import TierViolationError
from AgentEval.stats.library import StatsLibrary
from AgentEval.stats.types import KeywordRun

# --------------------------------------------------------------------------- #
# Stat.Run N Times — fan-out runner (8 tests)                                 #
# --------------------------------------------------------------------------- #


class _FakeAgentRunResult:
    """Minimal AgentRunResult-shaped fake (just `metadata.completeness` field)."""

    class _Meta:
        def __init__(self, completeness: str) -> None:
            self.completeness = completeness

    def __init__(self, completeness: str = "complete", payload: str = "ok") -> None:
        self.metadata = self._Meta(completeness)
        self.payload = payload


def test_run_n_times_n_equals_1_returns_single_keyword_run() -> None:
    """n=1 happy path: returns a 1-element list."""
    lib = StatsLibrary()
    runs = lib.run_n_times(n=1, keyword=lambda: _FakeAgentRunResult())
    assert len(runs) == 1
    assert isinstance(runs[0], KeywordRun)
    assert runs[0].trial_index == 0
    assert runs[0].completeness == "complete"


def test_run_n_times_n_equals_10_returns_ten_keyword_runs() -> None:
    """n=10 happy path: each trial gets sequential trial_index."""
    lib = StatsLibrary()
    runs = lib.run_n_times(n=10, keyword=lambda: _FakeAgentRunResult())
    assert len(runs) == 10
    assert [r.trial_index for r in runs] == list(range(10))


def test_run_n_times_invokes_callable_n_times_independently() -> None:
    """HIGH-ν fix (Blind 1-way): the pre-edit test was fake-green —
    `kw_with_default_mut` always created `history=[]` fresh per call regardless
    of dispatcher isolation. The test now empirically verifies each trial
    invokes the callable exactly once (the dispatcher does NOT share a
    callable across trials, does NOT batch the invocations).

    Phase-1 ContextVar-bind isolation is deferred to DF-6.3-S4 per Story 6.3
    code-review HIGH-μ amendment — the `test_id` field is a string label
    only, not a fresh ContextVar scope.
    """
    lib = StatsLibrary()
    invocations: list[int] = []

    def kw_recording_invocation() -> _FakeAgentRunResult:
        invocations.append(1)
        return _FakeAgentRunResult()

    lib.run_n_times(n=3, keyword=kw_recording_invocation)
    # Each trial invoked the callable exactly once; trial count = invocation count.
    assert len(invocations) == 3
    # Each trial's KeywordRun.test_id reflects the sub-scope per AC-6.3.2
    # (string label form; full ContextVar bind deferred per DF-6.3-S4).


from typing import Any  # noqa: E402  — late import to keep test grouping above


def test_run_n_times_seed_propagates_per_trial() -> None:
    """seed=42 → trial 0 gets seed=42, trial 1 gets seed=43, etc."""
    lib = StatsLibrary()
    observed_seeds: list[int] = []

    def kw_capture_seed(seed: int) -> _FakeAgentRunResult:
        observed_seeds.append(seed)
        return _FakeAgentRunResult()

    runs = lib.run_n_times(n=4, keyword=kw_capture_seed, seed=42)
    assert observed_seeds == [42, 43, 44, 45]
    assert [r.seed for r in runs] == [42, 43, 44, 45]


def test_run_n_times_seed_none_means_no_seed_kwarg() -> None:
    """seed=None: no `seed=` kwarg injected; KeywordRun.seed is None."""
    lib = StatsLibrary()

    def kw_no_seed_arg() -> _FakeAgentRunResult:
        return _FakeAgentRunResult()

    runs = lib.run_n_times(n=3, keyword=kw_no_seed_arg, seed=None)
    assert [r.seed for r in runs] == [None, None, None]


def test_run_n_times_trial_raises_bubbles_up() -> None:
    """Trial-level errors RE-RAISE per AC-6.3.2 (no swallowing)."""
    lib = StatsLibrary()
    call_count = [0]

    def kw_raises_on_third(**_: Any) -> _FakeAgentRunResult:
        call_count[0] += 1
        if call_count[0] == 3:
            raise RuntimeError("boom on trial 3")
        return _FakeAgentRunResult()

    with pytest.raises(RuntimeError, match="boom on trial 3"):
        lib.run_n_times(n=10, keyword=kw_raises_on_third)
    assert call_count[0] == 3


def test_run_n_times_dict_keyword_args() -> None:
    """keyword_args=dict form: passed as kwargs to the wrapped callable."""
    lib = StatsLibrary()
    captured: list[dict] = []

    def kw_capture_kwargs(**kw: Any) -> _FakeAgentRunResult:
        captured.append(kw)
        return _FakeAgentRunResult()

    lib.run_n_times(n=2, keyword=kw_capture_kwargs, keyword_args={"adapter": "generic", "prompt": "Hi"})
    assert captured[0] == {"adapter": "generic", "prompt": "Hi"}
    assert captured[1] == {"adapter": "generic", "prompt": "Hi"}


def test_run_n_times_list_keyword_args_with_rf_named_form() -> None:
    """keyword_args=list of `key=value` strings (RF named-arg form): parsed into dict."""
    lib = StatsLibrary()
    captured: list[dict] = []

    def kw_capture(**kw: Any) -> _FakeAgentRunResult:
        captured.append(kw)
        return _FakeAgentRunResult()

    lib.run_n_times(n=1, keyword=kw_capture, keyword_args=["adapter=generic", "prompt=Hello"])
    assert captured[0] == {"adapter": "generic", "prompt": "Hello"}


# --------------------------------------------------------------------------- #
# Stat.Get Pass At K — HumanEval unbiased estimator (10 tests)                #
# --------------------------------------------------------------------------- #


def _runs(completenesses: list[str]) -> list[KeywordRun]:
    """Build KeywordRun fixtures with the given completeness values."""
    return [
        KeywordRun(
            trial_index=i,
            test_id=f"test::trial-{i}",
            keyword_name="fake",
            result=None,
            error=None,
            completeness=c,
            latency_seconds=0.0,
            seed=None,
        )
        for i, c in enumerate(completenesses)
    ]


def test_get_pass_at_k_all_pass() -> None:
    lib = StatsLibrary()
    runs = _runs(["complete"] * 10)
    assert lib.get_pass_at_k(runs, k=1) == 1.0


def test_get_pass_at_k_all_fail() -> None:
    lib = StatsLibrary()
    runs = _runs(["partial"] * 10)
    assert lib.get_pass_at_k(runs, k=1) == 0.0


def test_get_pass_at_k_half_pass_k1() -> None:
    """5 of 10 pass; pass@1 = 5/10 = 0.5."""
    lib = StatsLibrary()
    runs = _runs(["complete"] * 5 + ["partial"] * 5)
    assert lib.get_pass_at_k(runs, k=1) == 0.5


def test_get_pass_at_k_half_pass_k3() -> None:
    """5/10 pass, k=3: 1 - C(5,3)/C(10,3) = 1 - 10/120 ≈ 0.9166..."""
    lib = StatsLibrary()
    runs = _runs(["complete"] * 5 + ["partial"] * 5)
    expected = 1.0 - 10 / 120
    assert lib.get_pass_at_k(runs, k=3) == pytest.approx(expected)


def test_get_pass_at_k_invalid_k_greater_than_n() -> None:
    lib = StatsLibrary()
    runs = _runs(["complete"] * 5)
    with pytest.raises(ValueError, match=r"k must be <= n"):
        lib.get_pass_at_k(runs, k=10)


def test_get_pass_at_k_invalid_k_zero_or_negative() -> None:
    lib = StatsLibrary()
    runs = _runs(["complete"] * 5)
    with pytest.raises(ValueError, match=r"k must be positive"):
        lib.get_pass_at_k(runs, k=0)
    with pytest.raises(ValueError, match=r"k must be positive"):
        lib.get_pass_at_k(runs, k=-1)


def test_get_pass_at_k_default_predicate_matches_completeness_complete() -> None:
    """D-5 default predicate per Story 6.4 DOGFOOD-FINDING-1 fix-NOW 2026-05-20:
    `r.completeness == "complete"` (pre-edit `"full"` was fake-green vs
    `AgentRunMetadata._VALID_COMPLETENESS = ('complete', 'truncated', 'partial')`).
    """
    lib = StatsLibrary()
    runs = _runs(["complete", "partial", "complete", "truncated"])
    # 2 of 4 pass with default predicate (only "complete" matches).
    assert lib.get_pass_at_k(runs, k=1) == 0.5


def test_get_pass_at_k_custom_predicate() -> None:
    lib = StatsLibrary()
    runs = _runs(["complete", "partial", "partial", "truncated"])
    # Custom predicate: include "partial" as passing.
    custom = lambda r: r.completeness in ("complete", "partial")  # noqa: E731
    assert lib.get_pass_at_k(runs, k=1, predicate=custom) == 0.75


def test_get_pass_at_k_empty_runs_raises() -> None:
    lib = StatsLibrary()
    with pytest.raises(ValueError, match=r"n must be positive"):
        lib.get_pass_at_k([], k=1)


def test_get_pass_at_k_n_minus_c_lt_k_returns_one() -> None:
    """When n-c < k (cannot fail k consecutive trials), returns 1.0 per HumanEval."""
    lib = StatsLibrary()
    # 9 of 10 pass; k=2 means n-c=1 < k → 1.0.
    runs = _runs(["complete"] * 9 + ["partial"])
    assert lib.get_pass_at_k(runs, k=2) == 1.0


# --------------------------------------------------------------------------- #
# Stat.Get Pass At K Confidence Interval — Wilson CI (4 tests)                #
# --------------------------------------------------------------------------- #


def test_get_pass_at_k_ci_reference_computation() -> None:
    """c=8/n=10/confidence=0.95: Wilson interval ~ (0.4901, 0.9430)."""
    lib = StatsLibrary()
    runs = _runs(["complete"] * 8 + ["partial"] * 2)
    lo, hi = lib.get_pass_at_k_confidence_interval(runs, k=1, confidence=0.95)
    # Reference: Wilson(0.8, 10, 95%) ≈ (0.4901, 0.9430). Allow ~1e-3 tolerance for
    # the inverse-normal-CDF approximation.
    assert 0.488 < lo < 0.492
    assert 0.941 < hi < 0.945


def test_get_pass_at_k_ci_empty_runs_returns_uniform() -> None:
    """n=0 → (0.0, 1.0) uniform prior per wilson.py edge case."""
    lib = StatsLibrary()
    # With n=0 we can't compute pass@k validation; signal via the underlying CI.
    lo, hi = lib.get_pass_at_k_confidence_interval([], k=1)
    assert (lo, hi) == (0.0, 1.0)


def test_get_pass_at_k_ci_higher_confidence_is_wider() -> None:
    lib = StatsLibrary()
    runs = _runs(["complete"] * 7 + ["partial"] * 3)
    lo_95, hi_95 = lib.get_pass_at_k_confidence_interval(runs, k=1, confidence=0.95)
    lo_99, hi_99 = lib.get_pass_at_k_confidence_interval(runs, k=1, confidence=0.99)
    assert lo_99 < lo_95
    assert hi_99 > hi_95


def test_get_pass_at_k_ci_default_predicate() -> None:
    """Same default predicate as Stat.Get Pass At K."""
    lib = StatsLibrary()
    runs = _runs(["complete"] * 5 + ["partial"] * 5)
    lo, hi = lib.get_pass_at_k_confidence_interval(runs, k=1)
    # 5/10 = 0.5 should center the Wilson interval roughly around 0.5.
    assert 0.0 < lo < 0.5
    assert 0.5 < hi < 1.0


# --------------------------------------------------------------------------- #
# Stat.Assert Run Determinism (6 tests)                                       #
# --------------------------------------------------------------------------- #


def _tier_1(func: Any) -> Any:
    """Helper: tag a callable as Tier-1 for `assert_run_determinism` tests
    (post HIGH-α fix — unannotated callables now correctly raise TierViolationError).
    """
    func._agenteval_tier = 1
    return func


def test_assert_run_determinism_passes_for_deterministic_callable() -> None:
    lib = StatsLibrary()

    @_tier_1
    def deterministic_kw() -> str:
        return "always-the-same"

    lib.assert_run_determinism(keyword=deterministic_kw)


def test_assert_run_determinism_fails_for_non_deterministic_callable() -> None:
    lib = StatsLibrary()
    call_count = [0]

    @_tier_1
    def non_deterministic_kw() -> int:
        call_count[0] += 1
        return call_count[0]

    with pytest.raises(AssertionError, match=r"bit-identical guarantee violated"):
        lib.assert_run_determinism(keyword=non_deterministic_kw)


def test_assert_run_determinism_rejects_tier_2_callable() -> None:
    """A callable with `_agenteval_tier = 2` attribute raises TierViolationError."""
    lib = StatsLibrary()

    def tier_2_kw() -> str:
        return "x"

    tier_2_kw._agenteval_tier = 2  # type: ignore[attr-defined]
    with pytest.raises(TierViolationError, match=r"bit-identical only guaranteed for Tier-1"):
        lib.assert_run_determinism(keyword=tier_2_kw)


def test_assert_run_determinism_rejects_unannotated_callable() -> None:
    """HIGH-α regression (4-way Codex + Blind + Edge + Auditor): an
    unannotated callable (no `@tier` attribute) raises `TierViolationError`
    per FR31a — bit-identical guarantee is Tier-1 scoped only; we cannot
    promise anything for keywords whose tier we can't resolve.
    """
    lib = StatsLibrary()

    def plain_kw() -> str:
        return "x"

    with pytest.raises(TierViolationError, match=r"unresolved.*Tier-1"):
        lib.assert_run_determinism(keyword=plain_kw)


def test_assert_run_determinism_invalid_expect_raises() -> None:
    lib = StatsLibrary()
    with pytest.raises(ValueError, match=r"expect must be 'byte_identical'"):
        lib.assert_run_determinism(keyword=_tier_1(lambda: "x"), expect="approximate")


def test_assert_run_determinism_dict_keyword_args() -> None:
    lib = StatsLibrary()

    @_tier_1
    def kw(**kw_args: Any) -> tuple:
        return tuple(sorted(kw_args.items()))

    lib.assert_run_determinism(keyword=kw, keyword_args={"a": 1, "b": 2})


def test_assert_run_determinism_list_keyword_args() -> None:
    lib = StatsLibrary()

    @_tier_1
    def kw(**kw_args: Any) -> tuple:
        return tuple(sorted(kw_args.items()))

    lib.assert_run_determinism(keyword=kw, keyword_args=["a=1", "b=2"])


# --------------------------------------------------------------------------- #
# Stat.Run N Times input validation                                            #
# --------------------------------------------------------------------------- #


def test_run_n_times_n_less_than_1_raises() -> None:
    lib = StatsLibrary()
    with pytest.raises(ValueError, match=r"n must be >= 1"):
        lib.run_n_times(n=0, keyword=lambda: _FakeAgentRunResult())


# --------------------------------------------------------------------------- #
# Story 6.3 code-review HIGH/MED regression tests (10 tests)                  #
# --------------------------------------------------------------------------- #


def test_run_n_times_pure_positional_list_args_dispatches_as_positional() -> None:
    """HIGH-β regression (Codex + Blind + Edge 3-way): pure-positional
    `keyword_args=[...]` (no `key=value` form) must dispatch as `*args`,
    NOT as synthetic `_arg_0=...` kwargs. Pre-edit raised
    `TypeError: kw() got an unexpected keyword argument '_arg_0'`.
    """
    lib = StatsLibrary()
    captured: list[tuple] = []

    def kw(*args: Any) -> _FakeAgentRunResult:
        captured.append(args)
        return _FakeAgentRunResult()

    lib.run_n_times(n=2, keyword=kw, keyword_args=["hello", "world"])
    assert captured[0] == ("hello", "world")
    assert captured[1] == ("hello", "world")


def test_normalize_keyword_args_strips_whitespace_on_values() -> None:
    """HIGH-τ regression (Edge 1-way): RF indented kwargs preserve trailing
    whitespace; the normalizer must strip BOTH key and value.
    """
    from AgentEval.stats._internal import _normalize_keyword_args

    pos, named = _normalize_keyword_args(["  key  =  value  "])
    assert pos == []
    assert named == {"key": "value"}


def test_assert_run_determinism_nan_returning_kw_is_bit_identical() -> None:
    """HIGH-ο regression (Blind 1-way): NaN-aware equality — two trials
    returning `float('nan')` are bit-identical per FR31a, even though
    Python `==` on NaN returns False.
    """
    lib = StatsLibrary()

    @_tier_1
    def nan_kw() -> float:
        return float("nan")

    lib.assert_run_determinism(keyword=nan_kw)


def test_assert_run_determinism_nan_in_nested_structure() -> None:
    """HIGH-ο follow-up: NaN inside a list/dict structure also handled."""
    lib = StatsLibrary()

    @_tier_1
    def nested_nan() -> dict:
        return {"score": float("nan"), "count": 3, "tags": [1.0, float("nan"), 2.0]}

    lib.assert_run_determinism(keyword=nested_nan)


def test_keyword_run_seed_field_reflects_what_trial_actually_saw() -> None:
    """MED-6 regression (Edge): when caller's explicit `keyword_args["seed"]`
    overrides the auto-injected `effective_seed`, `KeywordRun.seed` records
    the actual value the trial received (operator's value wins).
    """
    lib = StatsLibrary()

    @_tier_1
    def kw(seed: Any = None) -> _FakeAgentRunResult:
        return _FakeAgentRunResult()

    runs = lib.run_n_times(n=2, keyword=kw, keyword_args={"seed": 999}, seed=42)
    assert [r.seed for r in runs] == [999, 999]


def test_get_pass_at_k_ci_k_validation_unconditional() -> None:
    """MED Wilson-k regression (Codex + Edge 2-way): `k < 1` raises ValueError
    regardless of whether `n == 0`. Pre-edit silently returned `(0.0, 1.0)`
    for `k=-5, runs=[]`.
    """
    lib = StatsLibrary()
    with pytest.raises(ValueError, match=r"k must be positive"):
        lib.get_pass_at_k_confidence_interval([], k=0)
    with pytest.raises(ValueError, match=r"k must be positive"):
        lib.get_pass_at_k_confidence_interval([], k=-5)


def test_get_keyword_tier_through_guarded_fanout_wrapper() -> None:
    """HIGH-δ regression (Codex + Blind + Auditor 3-way): `find_tier_through_wrappers`
    detects `@tier(3)` on `Stat.Run N Times` despite `@guarded_fanout()`
    wrapping the inner function.
    """
    from AgentEval import AgentEval

    lib = AgentEval()
    # Stat.Run N Times has @tier(3) outermost-of-the-wrapped decoration:
    # @keyword(name=...) @tier(3) @guarded_fanout() def run_n_times(...)
    assert lib.get_keyword_tier("Stat.Run N Times") == 3


def test_get_keyword_tier_rejects_out_of_range_tier() -> None:
    """HIGH-π regression (Blind 1-way): a `@tier(4)` typo or any tier outside
    `{1, 2, 3}` raises ValueError with a "valid tiers are 1, 2, 3" hint
    instead of propagating the invalid value to operator-facing surfaces.
    """
    from AgentEval import AgentEval

    lib = AgentEval()
    # Forge a tier=4 by temporarily overriding the registered keyword's tier.
    original_kw = lib.keywords["Get Effective Config"]
    target = getattr(original_kw, "__func__", original_kw)
    original_tier = target._agenteval_tier
    target._agenteval_tier = 4
    try:
        with pytest.raises(ValueError, match=r"invalid tier annotation @tier\(4\)"):
            lib.get_keyword_tier("Get Effective Config")
    finally:
        target._agenteval_tier = original_tier
