"""Unit tests for _kernel/tier.py (AC-1b.1.6)."""

from __future__ import annotations

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier, tier_badge

# ---- AC-1b.1.6: decorator attaches _agenteval_tier (single-underscore) -- #


def test_tier_decorator_attaches_single_underscore_attribute() -> None:
    @tier(1)
    def my_keyword() -> None:
        pass

    # Architecture L620 ratified single-underscore convention.
    assert my_keyword._agenteval_tier == 1  # type: ignore[attr-defined]
    # NOT the dunder variant (Story 1b.1 D3 drift resolution).
    assert not hasattr(my_keyword, "__agenteval_tier__")


def test_tier_decorator_supports_all_three_levels() -> None:
    @tier(1)
    def k1() -> None:
        pass

    @tier(2)
    def k2() -> None:
        pass

    @tier(3)
    def k3() -> None:
        pass

    assert k1._agenteval_tier == 1  # type: ignore[attr-defined]
    assert k2._agenteval_tier == 2  # type: ignore[attr-defined]
    assert k3._agenteval_tier == 3  # type: ignore[attr-defined]


# ---- AC-1b.1.6: get_keyword_tier ---------------------------------------- #


def test_get_keyword_tier_returns_int_for_decorated() -> None:
    @tier(2)
    def my_keyword() -> None:
        pass

    assert get_keyword_tier(my_keyword) == 2


def test_get_keyword_tier_returns_none_for_undecorated() -> None:
    def plain_function() -> None:
        pass

    assert get_keyword_tier(plain_function) is None


# ---- AC-1b.1.6: tier_badge exact strings -------------------------------- #


def test_tier_badge_exact_strings() -> None:
    assert tier_badge(1) == "[Tier 1 — Deterministic]"
    assert tier_badge(2) == "[Tier 2 — Stochastic Single-Shot]"
    assert tier_badge(3) == "[Tier 3 — Stochastic Fan-Out]"


# ---- AC-1b.1.6: invalid tier raises ValueError -------------------------- #


def test_tier_decorator_raises_on_invalid_tier() -> None:
    with pytest.raises(ValueError, match="tier must be 1, 2, or 3"):
        tier(0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="tier must be 1, 2, or 3"):
        tier(4)  # type: ignore[arg-type]


def test_tier_badge_raises_on_invalid_tier() -> None:
    with pytest.raises(ValueError, match="tier must be 1, 2, or 3"):
        tier_badge(0)
    with pytest.raises(ValueError, match="tier must be 1, 2, or 3"):
        tier_badge(99)
