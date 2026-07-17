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

"""StatLibrary: run-N, pass@k, Wilson - the estimators reachable from .robot."""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval._core import stats
from AgentEval._core.stats import KeywordRun
from StatLibrary import StatLibrary


@pytest.fixture
def lib() -> StatLibrary:
    return StatLibrary()


def _run(trial_index: int, *, error: BaseException | None = None, completeness: str = "n/a") -> KeywordRun:
    return KeywordRun(
        trial_index=trial_index,
        result=None,
        error=error,
        completeness=completeness,
        latency_seconds=0.0,
    )


# ---------------------------------------------------------------------- #
# Stat.Run N Times                                                       #
# ---------------------------------------------------------------------- #


def test_run_n_times_with_callable_runs_n_trials(lib: StatLibrary) -> None:
    calls: list[int] = []

    def callable_() -> str:
        calls.append(1)
        return "ok"

    runs = lib.run_n_times(4, callable_)
    assert len(runs) == 4
    assert len(calls) == 4
    assert all(isinstance(r, KeywordRun) for r in runs)
    assert all(r.error is None for r in runs)
    assert [r.result for r in runs] == ["ok", "ok", "ok", "ok"]
    assert [r.trial_index for r in runs] == [0, 1, 2, 3]


def test_run_n_times_coerces_string_count(lib: StatLibrary) -> None:
    # RF passes bare scalars as strings; the keyword must int()-coerce.
    runs = lib.run_n_times("3", lambda: "x")  # type: ignore[arg-type]
    assert len(runs) == 3


def test_run_n_times_forwards_positional_args_to_callable(lib: StatLibrary) -> None:
    seen: list[tuple[Any, ...]] = []

    def callable_(a: int, b: int) -> int:
        seen.append((a, b))
        return a + b

    runs = lib.run_n_times(2, callable_, 3, 4)
    assert [r.result for r in runs] == [7, 7]
    assert seen == [(3, 4), (3, 4)]


def test_run_n_times_captures_trial_errors_instead_of_raising(lib: StatLibrary) -> None:
    def boom() -> None:
        raise ValueError("nope")

    runs = lib.run_n_times(2, boom)
    assert len(runs) == 2
    assert all(isinstance(r.error, ValueError) for r in runs)


def test_run_n_times_resolves_keyword_name_via_builtin(lib: StatLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    invocations: list[tuple[str, tuple[Any, ...]]] = []

    class FakeBuiltIn:
        def run_keyword(self, name: str, *args: Any) -> str:
            invocations.append((name, args))
            return f"ran:{name}"

    monkeypatch.setattr("StatLibrary.BuiltIn", FakeBuiltIn)

    runs = lib.run_n_times(3, "Some.Keyword", "arg1", flag="yes")
    assert [r.result for r in runs] == ["ran:Some.Keyword"] * 3
    # kwargs are folded into RF name=value string form.
    assert invocations == [("Some.Keyword", ("arg1", "flag=yes"))] * 3


def test_run_n_times_is_tier_3(lib: StatLibrary) -> None:
    assert getattr(lib.run_n_times, "_agenteval_tier", None) == 3


# ---------------------------------------------------------------------- #
# Stat.Get Pass At K                                                     #
# ---------------------------------------------------------------------- #


def test_get_pass_at_k_matches_spine(lib: StatLibrary) -> None:
    runs = [_run(i) for i in range(10)]  # all pass under default predicate
    assert lib.get_pass_at_k(runs, 5) == stats.pass_at_k(runs, 5)
    assert lib.get_pass_at_k(runs, 5) == 1.0


def test_get_pass_at_k_all_failures_is_zero(lib: StatLibrary) -> None:
    runs = [_run(i, error=RuntimeError("x")) for i in range(5)]
    assert lib.get_pass_at_k(runs, 3) == 0.0


def test_get_pass_at_k_coerces_string_k(lib: StatLibrary) -> None:
    runs = [_run(i) for i in range(4)]
    assert lib.get_pass_at_k(runs, "2") == 1.0  # type: ignore[arg-type]


def test_get_pass_at_k_honors_custom_predicate(lib: StatLibrary) -> None:
    runs = [_run(i, completeness=("complete" if i < 2 else "n/a")) for i in range(4)]

    def only_complete(run: KeywordRun) -> bool:
        return run.completeness == "complete"

    expected = stats.pass_at_k(runs, 2, predicate=only_complete)
    assert lib.get_pass_at_k(runs, 2, predicate=only_complete) == expected
    assert 0.0 < lib.get_pass_at_k(runs, 2, predicate=only_complete) < 1.0


def test_get_pass_at_k_is_tier_1(lib: StatLibrary) -> None:
    assert getattr(lib.get_pass_at_k, "_agenteval_tier", None) == 1


# ---------------------------------------------------------------------- #
# Stat.Wilson Interval                                                   #
# ---------------------------------------------------------------------- #


def test_wilson_interval_matches_spine(lib: StatLibrary) -> None:
    assert lib.wilson_interval(8, 10) == stats.wilson_interval(8, 10)


def test_wilson_interval_bounds(lib: StatLibrary) -> None:
    lower, upper = lib.wilson_interval(8, 10)
    assert 0.0 <= lower <= upper <= 1.0


def test_wilson_interval_coerces_string_inputs(lib: StatLibrary) -> None:
    from_strings = lib.wilson_interval("8", "10", "0.95")  # type: ignore[arg-type]
    assert from_strings == stats.wilson_interval(8, 10, 0.95)


def test_wilson_interval_respects_confidence(lib: StatLibrary) -> None:
    narrow = lib.wilson_interval(8, 10, 0.80)
    wide = lib.wilson_interval(8, 10, 0.99)
    # Higher confidence -> wider band.
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_wilson_interval_is_tier_1(lib: StatLibrary) -> None:
    assert getattr(lib.wilson_interval, "_agenteval_tier", None) == 1


# ---------------------------------------------------------------------- #
# End-to-end: the phantom example is now real.                          #
# ---------------------------------------------------------------------- #


def test_run_then_pass_at_k_pipeline(lib: StatLibrary) -> None:
    toggle = {"i": 0}

    def flaky() -> str:
        toggle["i"] += 1
        if toggle["i"] % 2 == 0:
            raise RuntimeError("flaked")
        return "ok"

    runs = lib.run_n_times(10, flaky)
    p = lib.get_pass_at_k(runs, 5)
    assert 0.0 <= p <= 1.0
    successes = sum(1 for r in runs if r.error is None)
    lower, upper = lib.wilson_interval(successes, len(runs))
    assert 0.0 <= lower <= upper <= 1.0
