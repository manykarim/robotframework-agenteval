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

"""Tests for the tier marker and the deterministic guard."""

from __future__ import annotations

import functools

import pytest

from AgentEval._core.errors import TierViolationError
from AgentEval._core.tier import (
    deterministic_scope,
    enforce_no_model,
    find_tier_through_wrappers,
    get_keyword_tier,
    tier,
    tier_badge,
)


def test_tier_stamps_attribute_and_classifies() -> None:
    @tier(1)
    def kw1() -> None: ...

    @tier(3)
    def kw3() -> None: ...

    assert get_keyword_tier(kw1) == 1
    assert get_keyword_tier(kw3) == 3


def test_unmarked_keyword_returns_none() -> None:
    def plain() -> None: ...

    assert get_keyword_tier(plain) is None


@pytest.mark.parametrize("bad", [0, 4, True, False, "1"])
def test_tier_rejects_invalid_levels(bad: object) -> None:
    with pytest.raises(ValueError):
        tier(bad)  # type: ignore[arg-type]


def test_tier_badges() -> None:
    assert tier_badge(1) == "[Tier 1 - Deterministic]"
    assert tier_badge(2) == "[Tier 2 - LLM Judge]"
    assert tier_badge(3) == "[Tier 3 - Coding Agent]"
    with pytest.raises(ValueError):
        tier_badge(9)


def test_find_tier_through_wrappers() -> None:
    @tier(3)
    def inner() -> None: ...

    @functools.wraps(inner)
    def outer() -> None: ...

    # The marker is on inner; wraps copies __wrapped__ so the walk finds it.
    assert find_tier_through_wrappers(outer) == 3


def test_deterministic_scope_blocks_model_calls() -> None:
    # Outside the scope, no-op.
    enforce_no_model()
    with deterministic_scope(), pytest.raises(TierViolationError):
        enforce_no_model()
    # Scope cleaned up: back to no-op.
    enforce_no_model()


def test_deterministic_scope_nests_and_restores() -> None:
    # Outer scope active; inner scope active; on inner exit still guarded;
    # on outer exit back to no-op.
    with deterministic_scope():
        with pytest.raises(TierViolationError):
            enforce_no_model()
        with deterministic_scope(), pytest.raises(TierViolationError):
            enforce_no_model()
        # Inner scope exited but outer still guards.
        with pytest.raises(TierViolationError):
            enforce_no_model()
    enforce_no_model()
