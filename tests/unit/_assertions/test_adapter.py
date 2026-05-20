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

"""Unit tests for `_assertions/adapter.py` (Story 6.3 AC-6.3.13)."""

from __future__ import annotations

import pytest

from AgentEval._assertions.adapter import assert_value
from AgentEval.errors import PollingDisallowedError, ValidateOperatorDisallowed

# --------------------------------------------------------------------------- #
# Gate 1: FR28 polling-ban                                                    #
# --------------------------------------------------------------------------- #


def test_polling_on_tier_2_with_polling_set_raises() -> None:
    """Tier-2 + polling=0.5 → PollingDisallowedError per FR28."""
    with pytest.raises(PollingDisallowedError) as exc_info:
        assert_value(
            actual="x",
            operator="==",
            expected="x",
            keyword_name="Send Prompt",
            tier=2,
            polling=0.5,
        )
    msg = str(exc_info.value)
    assert "Send Prompt" in msg  # FR56 (a): keyword name
    assert "Stat.Run N Times" in msg  # FR56 (c): remediation snippet
    assert "ADR-019" in msg  # FR56 (d): ADR link


def test_polling_on_tier_3_with_polling_set_raises() -> None:
    """Tier-3 + polling=non-None → PollingDisallowedError per FR28."""
    with pytest.raises(PollingDisallowedError):
        assert_value(
            actual=1,
            operator=">=",
            expected=0,
            keyword_name="Stat.Run N Times",
            tier=3,
            polling=1.0,
        )


def test_polling_on_tier_1_with_polling_set_is_noop() -> None:
    """Tier-1 + polling=0.5: no raise (FR28 trigger is Tier-2/3 only)."""
    assert_value(
        actual="x",
        operator="==",
        expected="x",
        keyword_name="Skill.Get Frontmatter",
        tier=1,
        polling=0.5,
    )


def test_polling_none_on_tier_2_is_noop() -> None:
    """Tier-2 + polling=None: no raise."""
    assert_value(
        actual="x",
        operator="==",
        expected="x",
        keyword_name="Send Prompt",
        tier=2,
        polling=None,
    )


# --------------------------------------------------------------------------- #
# Gate 2: FR43 validate-gate                                                  #
# --------------------------------------------------------------------------- #


def test_validate_without_opt_in_raises() -> None:
    """validate=True with allow_validate_operator=False → ValidateOperatorDisallowed per FR43."""
    with pytest.raises(ValidateOperatorDisallowed) as exc_info:
        assert_value(
            actual="x",
            operator=None,  # skip dispatch for gating-only test
            expected="x",
            keyword_name="My Custom Assertion",
            tier=1,
            validate=True,
            allow_validate_operator=False,
        )
    msg = str(exc_info.value)
    assert "My Custom Assertion" in msg
    assert "allow_validate_operator=True" in msg
    assert "ADR-019" in msg


def test_validate_with_opt_in_passes() -> None:
    """validate=True with allow_validate_operator=True → gate open."""
    assert_value(
        actual="x",
        operator=None,
        expected="x",
        keyword_name="My Custom Assertion",
        tier=1,
        validate=True,
        allow_validate_operator=True,
    )


# --------------------------------------------------------------------------- #
# Gate 3: AssertionEngine dispatch                                            #
# --------------------------------------------------------------------------- #


def test_dispatch_equal_happy() -> None:
    """operator='==' + matching values: no raise."""
    assert_value(
        actual="foo",
        operator="==",
        expected="foo",
        keyword_name="Kw",
        tier=1,
    )


def test_dispatch_equal_mismatch_raises_assertion_error() -> None:
    """operator='==' + mismatch: AssertionError from AssertionEngine dispatch."""
    with pytest.raises(AssertionError):
        assert_value(
            actual="foo",
            operator="==",
            expected="bar",
            keyword_name="Kw",
            tier=1,
        )


def test_dispatch_greater_than_happy() -> None:
    assert_value(
        actual=5,
        operator=">=",
        expected=3,
        keyword_name="Kw",
        tier=1,
    )


def test_dispatch_contains_happy() -> None:
    """`contains` operator (AssertionEngine `*=`)."""
    assert_value(
        actual="hello world",
        operator="*=",
        expected="world",
        keyword_name="Kw",
        tier=1,
    )


def test_dispatch_operator_none_skips() -> None:
    """operator=None: gates run, dispatch skipped."""
    # No raise (gating-only mode).
    assert_value(
        actual="anything",
        operator=None,
        expected="ignored",
        keyword_name="Kw",
        tier=1,
    )


def test_dispatch_invalid_operator_raises_value_error() -> None:
    """Unknown operator string → ValueError."""
    with pytest.raises(ValueError, match=r"invalid AssertionEngine operator"):
        assert_value(
            actual="x",
            operator="not_a_real_op",
            expected="x",
            keyword_name="Kw",
            tier=1,
        )
