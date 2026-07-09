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

"""Unit tests for `Subagent.Get Routing Pass At K` (task 6.3).

Parity with `_compute_pass_at_k`, foreign-result-type counts as non-pass,
ValueError paths. Mirrors the C59 lesson behind `Skill.Get Activation Pass At K`.
"""

from __future__ import annotations

import pytest

from AgentEval.stats._internal import _compute_pass_at_k
from AgentEval.stats.types import KeywordRun
from AgentEval.subagents.library import SubagentsLibrary
from AgentEval.subagents.types import DelegationDecision


def _run(idx: int, result: object) -> KeywordRun:
    return KeywordRun(
        trial_index=idx,
        test_id=f"t::trial-{idx}",
        keyword_name="Subagent.Get Delegation Decision",
        result=result,
        error=None,
        completeness="n/a",
        latency_seconds=0.0,
        seed=None,
    )


def _decision(delegated: bool) -> DelegationDecision:
    return DelegationDecision(delegated=delegated, delegations=(), reasoning="", cost_usd=0.0, latency_seconds=0.0)


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


def test_pass_at_k_matches_compute_helper(lib: SubagentsLibrary) -> None:
    runs = [_run(i, _decision(i < 3)) for i in range(5)]
    assert lib.get_routing_pass_at_k(runs, 2) == _compute_pass_at_k(3, 5, 2)


def test_foreign_result_type_counts_as_non_pass(lib: SubagentsLibrary) -> None:
    runs = [_run(0, _decision(True)), _run(1, "not a decision"), _run(2, None)]
    # Only 1 of 3 passes; no crash on the foreign types.
    assert lib.get_routing_pass_at_k(runs, 1) == _compute_pass_at_k(1, 3, 1)


def test_all_pass(lib: SubagentsLibrary) -> None:
    runs = [_run(i, _decision(True)) for i in range(4)]
    assert lib.get_routing_pass_at_k(runs, 2) == 1.0


def test_no_pass(lib: SubagentsLibrary) -> None:
    runs = [_run(i, _decision(False)) for i in range(4)]
    assert lib.get_routing_pass_at_k(runs, 2) == 0.0


def test_no_predicate_kwarg_exposed(lib: SubagentsLibrary) -> None:
    import inspect

    sig = inspect.signature(SubagentsLibrary.get_routing_pass_at_k)
    assert "predicate" not in sig.parameters


@pytest.mark.parametrize("k", [0, -1, 6])
def test_invalid_k_raises_value_error(lib: SubagentsLibrary, k: int) -> None:
    runs = [_run(i, _decision(True)) for i in range(5)]
    with pytest.raises(ValueError):
        lib.get_routing_pass_at_k(runs, k)


def test_empty_runs_raises_value_error(lib: SubagentsLibrary) -> None:
    with pytest.raises(ValueError):
        lib.get_routing_pass_at_k([], 1)
