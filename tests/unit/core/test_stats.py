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

"""Tests for run-N, pass@k, and the Wilson interval."""

from __future__ import annotations

import pytest

from AgentEval._core.stats import (
    KeywordRun,
    default_pass_predicate,
    pass_at_k,
    run_n,
    wilson_interval,
)
from AgentEval._core.types import AgentRunMetadata, AgentRunResult


def _run(completeness: str = "complete", error: Exception | None = None) -> KeywordRun:
    return KeywordRun(trial_index=0, result=None, error=error, completeness=completeness, latency_seconds=0.0)


def test_run_n_collects_trials() -> None:
    calls: list[int] = []

    def kw() -> str:
        calls.append(1)
        return "ok"

    runs = run_n(kw, 5)
    assert len(runs) == 5
    assert len(calls) == 5
    assert all(r.error is None for r in runs)


def test_run_n_captures_errors_without_raising() -> None:
    def boom() -> None:
        raise RuntimeError("nope")

    runs = run_n(boom, 3)
    assert len(runs) == 3
    assert all(isinstance(r.error, RuntimeError) for r in runs)


def test_run_n_rejects_zero() -> None:
    with pytest.raises(ValueError):
        run_n(lambda: None, 0)


def test_run_n_extracts_completeness_from_agent_result() -> None:
    def kw() -> AgentRunResult:
        return AgentRunResult(response_text="x", metadata=AgentRunMetadata(completeness="truncated"))

    runs = run_n(kw, 1)
    assert runs[0].completeness == "truncated"


def test_default_predicate_does_not_silently_return_zero() -> None:
    # The old footgun: plain callables carry completeness "n/a" and were
    # scored as failures because the default checked completeness == "full".
    runs = run_n(lambda: "anything", 10)
    assert all(default_pass_predicate(r) for r in runs)
    assert pass_at_k(runs, 1) == 1.0


def test_default_predicate_fails_on_error_and_bad_completeness() -> None:
    assert default_pass_predicate(_run("complete")) is True
    assert default_pass_predicate(_run("n/a")) is True
    assert default_pass_predicate(_run("truncated")) is False
    assert default_pass_predicate(_run("partial")) is False
    assert default_pass_predicate(_run("complete", error=RuntimeError())) is False


def test_pass_at_k_all_pass() -> None:
    runs = [_run("complete") for _ in range(10)]
    assert pass_at_k(runs, 3) == 1.0


def test_pass_at_k_none_pass() -> None:
    runs = [_run("truncated") for _ in range(10)]
    assert pass_at_k(runs, 3) == 0.0


def test_pass_at_k_partial() -> None:
    # 5 of 10 pass; pass@1 should be 0.5.
    runs = [_run("complete") for _ in range(5)] + [_run("truncated") for _ in range(5)]
    assert pass_at_k(runs, 1) == pytest.approx(0.5)
    # pass@k is monotone non-decreasing in k.
    assert pass_at_k(runs, 5) >= pass_at_k(runs, 1)


def test_pass_at_k_custom_predicate() -> None:
    runs = [_run("complete", error=RuntimeError()) for _ in range(4)]
    assert pass_at_k(runs, 1, predicate=lambda r: True) == 1.0


def test_pass_at_k_validates_k() -> None:
    runs = [_run() for _ in range(3)]
    with pytest.raises(ValueError):
        pass_at_k(runs, 0)
    with pytest.raises(ValueError):
        pass_at_k(runs, 4)
    with pytest.raises(ValueError):
        pass_at_k([], 1)


def test_wilson_interval_bounds() -> None:
    lo, hi = wilson_interval(7, 10)
    assert 0.0 <= lo <= hi <= 1.0


def test_wilson_interval_no_trials_is_uniform() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_widens_with_confidence() -> None:
    lo95, hi95 = wilson_interval(5, 10, 0.95)
    lo99, hi99 = wilson_interval(5, 10, 0.99)
    assert (hi99 - lo99) >= (hi95 - lo95)


def test_wilson_interval_validates_inputs() -> None:
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(-1, 3)
    with pytest.raises(ValueError):
        wilson_interval(1, 3, 1.5)
