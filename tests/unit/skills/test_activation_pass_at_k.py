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

"""Unit tests for `Skill.Get Activation Pass At K` (Story 14.5 / C59 / DF-7.3-S1 closure).

Covers AC-14.5.1 through AC-14.5.3 (≥10 tests):

- Predicate helper tests (4): TRUE on activated; FALSE on not-activated;
  FALSE on non-ActivationDecision; FALSE on None.
- Keyword tests (8): all-activated → 1.0; none-activated → 0.0; mixed-runs math;
  validation (k<1, k>n, n=0); ignores non-activation results; no predicate kwarg.
- C59 regression-guard (2): hand-built guard proves the silent-zero failure mode;
  real-path guard (`Stat.Run N Times` → `_extract_completeness` pipeline) proves
  the production-path reproduction (added per Codex MED-2 pre-emptive).
"""

from __future__ import annotations

import inspect

import pytest

from AgentEval.skills._internal import _activation_pass_predicate
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import ActivationDecision
from AgentEval.stats.library import StatsLibrary
from AgentEval.stats.types import KeywordRun


def _make_run(result: object, *, completeness: str = "n/a", trial_index: int = 0) -> KeywordRun:
    """Build a minimal `KeywordRun` carrying `result` for predicate tests."""
    return KeywordRun(
        trial_index=trial_index,
        test_id=f"unit::trial-{trial_index}",
        keyword_name="Skill.Get Activation Decision",
        result=result,
        error=None,
        completeness=completeness,
        latency_seconds=0.001,
        seed=None,
    )


def _activation_decision(activated: bool) -> ActivationDecision:
    return ActivationDecision(
        activated=activated,
        reasoning="stub reasoning",
        cost_usd=0.0,
        latency_seconds=0.001,
    )


# ---------------------------------------------------------------------------
# Predicate helper tests (AC-14.5.2)
# ---------------------------------------------------------------------------


def test_predicate_true_when_activation_decision_activated_true() -> None:
    run = _make_run(_activation_decision(activated=True))
    assert _activation_pass_predicate(run) is True


def test_predicate_false_when_activation_decision_activated_false() -> None:
    run = _make_run(_activation_decision(activated=False))
    assert _activation_pass_predicate(run) is False


def test_predicate_false_when_result_not_activation_decision() -> None:
    # An arbitrary non-ActivationDecision object — e.g., a string.
    run = _make_run("not an ActivationDecision")
    assert _activation_pass_predicate(run) is False


def test_predicate_false_when_result_is_none() -> None:
    run = _make_run(None)
    assert _activation_pass_predicate(run) is False


# ---------------------------------------------------------------------------
# Keyword tests (AC-14.5.1)
# ---------------------------------------------------------------------------


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


def test_get_activation_pass_at_k_returns_1_0_when_all_activated_k_equals_n(lib: SkillsLibrary) -> None:
    runs = [_make_run(_activation_decision(activated=True), trial_index=i) for i in range(5)]
    assert lib.get_activation_pass_at_k(runs, k=5) == 1.0


def test_get_activation_pass_at_k_returns_0_0_when_none_activated(lib: SkillsLibrary) -> None:
    runs = [_make_run(_activation_decision(activated=False), trial_index=i) for i in range(5)]
    assert lib.get_activation_pass_at_k(runs, k=1) == 0.0


def test_get_activation_pass_at_k_matches_humaneval_math_for_mixed_runs(lib: SkillsLibrary) -> None:
    """3 activated of 5 trials → Pass@1 = 3/5 = 0.6 (HumanEval estimator collapses to c/n at k=1)."""
    runs = [
        _make_run(_activation_decision(activated=True), trial_index=0),
        _make_run(_activation_decision(activated=False), trial_index=1),
        _make_run(_activation_decision(activated=True), trial_index=2),
        _make_run(_activation_decision(activated=False), trial_index=3),
        _make_run(_activation_decision(activated=True), trial_index=4),
    ]
    assert lib.get_activation_pass_at_k(runs, k=1) == pytest.approx(0.6)


def test_get_activation_pass_at_k_raises_value_error_when_k_lt_1(lib: SkillsLibrary) -> None:
    runs = [_make_run(_activation_decision(activated=True), trial_index=i) for i in range(3)]
    with pytest.raises(ValueError):
        lib.get_activation_pass_at_k(runs, k=0)


def test_get_activation_pass_at_k_raises_value_error_when_k_gt_len_runs(lib: SkillsLibrary) -> None:
    runs = [_make_run(_activation_decision(activated=True), trial_index=i) for i in range(3)]
    with pytest.raises(ValueError):
        lib.get_activation_pass_at_k(runs, k=4)


def test_get_activation_pass_at_k_raises_value_error_when_runs_empty(lib: SkillsLibrary) -> None:
    with pytest.raises(ValueError):
        lib.get_activation_pass_at_k([], k=1)


def test_get_activation_pass_at_k_ignores_non_activation_results(lib: SkillsLibrary) -> None:
    """Mixed-type runs: 2 activated ActivationDecisions + 3 non-AD results → c=2, n=5, Pass@1 = 0.4."""
    runs = [
        _make_run(_activation_decision(activated=True), trial_index=0),
        _make_run("string result", trial_index=1),
        _make_run(_activation_decision(activated=True), trial_index=2),
        _make_run(None, trial_index=3),
        _make_run({"unrelated": "dict"}, trial_index=4),
    ]
    assert lib.get_activation_pass_at_k(runs, k=1) == pytest.approx(0.4)


def test_get_activation_pass_at_k_does_not_accept_predicate_kwarg(lib: SkillsLibrary) -> None:
    """API rigidity: no `predicate=` kwarg — that's the WHOLE POINT of the dedicated keyword.

    Per AC-14.5.1 + Devon UX: if you need a custom predicate, call `Stat.Get Pass At K`
    directly. The dedicated keyword removes the predicate-customization pitfall.
    """
    runs = [_make_run(_activation_decision(activated=True), trial_index=i) for i in range(3)]
    sig = inspect.signature(lib.get_activation_pass_at_k)
    assert "predicate" not in sig.parameters, (
        "Skill.Get Activation Pass At K MUST NOT accept a `predicate` kwarg — "
        "removing the predicate-customization pitfall is the whole reason this "
        "keyword exists."
    )
    with pytest.raises(TypeError):
        # type: ignore[call-arg]
        lib.get_activation_pass_at_k(runs, k=1, predicate=lambda r: True)  # noqa: ARG005


# ---------------------------------------------------------------------------
# C59 regression-guard (AC-14.5.3)
# ---------------------------------------------------------------------------


def test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59() -> None:
    """C59 regression-guard: prove the silent-zero failure mode the dedicated keyword closes.

    Story 7.3 D-1 (HIGH, 2026-05-21) empirically confirmed: `Stat.Get Pass At K`
    with the default predicate returns 0.0 when called on a list of KeywordRuns
    whose `.result` is an `ActivationDecision`, because the default predicate is
    `completeness == "complete"` and `ActivationDecision` has no
    `.metadata.completeness` (so the `KeywordRun.completeness` field defaults
    to `"n/a"`).

    This test DOCUMENTS the failure mode AS A LIVING TEST. If the default
    `Stat.Get Pass At K` predicate is ever changed to silently start returning
    nonzero on activation runs (e.g., someone "fixes" it without realizing the
    `Skill.Get Activation Pass At K` keyword exists), this test will FAIL,
    forcing the change author to make an explicit decision about which surface
    handles activation Pass@k.

    Closes C59 / DF-7.3-S1.
    """
    stats = StatsLibrary()
    # 5 ActivationDecisions, ALL activated=True. With the correct predicate
    # Pass@1 would be 1.0. With the default predicate (`completeness == "complete"`)
    # it returns 0.0 because each KeywordRun's completeness is "n/a" (not "complete").
    runs = [
        _make_run(
            _activation_decision(activated=True),
            completeness="n/a",
            trial_index=i,
        )
        for i in range(5)
    ]
    # The bug: default predicate returns 0.0 even though all 5 trials should pass.
    default_result = stats.get_pass_at_k(runs, k=1)
    assert default_result == 0.0, (
        "C59 regression-guard: the silent-zero bug is no longer reproducible. "
        "Either the default Stat.Get Pass At K predicate was changed (without "
        "updating this test) OR the KeywordRun.completeness default changed. "
        "Either way the dedicated Skill.Get Activation Pass At K keyword's "
        "rationale needs a re-review."
    )
    # And the fix: the dedicated keyword gets the right answer.
    skills = SkillsLibrary()
    fixed_result = skills.get_activation_pass_at_k(runs, k=1)
    assert fixed_result == 1.0, (
        f"C59 closure regression: dedicated keyword's predicate should report "
        f"1.0 for 5/5 activated runs at k=1, got {fixed_result}."
    )


def test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path() -> None:
    """C59 living regression-guard via the REAL `Stat.Run N Times` dispatch path (Codex MED-2).

    The previous test (`test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59`)
    hand-builds `KeywordRun` objects with `completeness="n/a"`. That tests the symptom but
    not the failure-producing path. Codex MED-2 (Story 14.5 cross-LLM review): a future
    change in `_extract_completeness` (e.g., a special-case for `ActivationDecision` results
    returning `"complete"`) would silently break the C59 fix but the hand-built test would
    still pass.

    This test goes through the real `StatsLibrary.run_n_times()` → `_dispatch_trial` →
    `_extract_completeness` pipeline so it actually exercises the production path that
    produced C59 in the first place. If `_extract_completeness` is ever changed to coerce
    `ActivationDecision` to `"complete"`, THIS test will start failing — forcing the change
    author to either confirm the change is intentional + remove the dedicated keyword OR
    revert the coercion.
    """
    stats = StatsLibrary()
    skills = SkillsLibrary()

    # Callable that mimics what `Skill.Get Activation Decision` returns.
    # `Stat.Run N Times` wraps this in real `KeywordRun` objects with
    # `.completeness` populated by the real `_extract_completeness` helper.
    def _always_activate() -> ActivationDecision:
        return _activation_decision(activated=True)

    runs = stats.run_n_times(n=5, keyword=_always_activate)
    assert len(runs) == 5

    # Real-path verification: each KeywordRun's completeness is "n/a"
    # because ActivationDecision has no `.metadata.completeness`.
    assert all(r.completeness == "n/a" for r in runs), (
        "Real-path KeywordRun completeness drifted from 'n/a' for "
        "ActivationDecision results — `_extract_completeness` may have been "
        "changed; re-verify the C59 closure rationale."
    )

    # The bug: default predicate returns 0.0 even on this real-path real-result.
    assert stats.get_pass_at_k(runs, k=1) == 0.0, (
        "C59 real-path regression: default predicate should still return 0.0 "
        "for ActivationDecision runs wrapped via the real Stat.Run N Times "
        "path. Either `_extract_completeness` was changed OR `_default_pass_predicate` "
        "was changed — the dedicated keyword's rationale needs re-review."
    )
    # The fix: the dedicated keyword works on the same real-path runs.
    assert skills.get_activation_pass_at_k(runs, k=1) == 1.0
