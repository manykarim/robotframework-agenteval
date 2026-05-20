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

"""Integration test for the FR43 `validate`-operator gate (Story 6.3 AC-6.3.14).

Per FR43 verbatim test-fixture (prd.md:1565):
    Run Keyword And Expect Error    ValidateOperatorDisallowed*    <getter>    validate    <expr>

This pytest-level integration test exercises the same gate through the
Python-side `assert_value()` API to keep the regression suite fast +
deterministic — a full Robot Framework fixture invocation lands in
Story 6.4 dogfood per the `feedback_interleaved_dogfood_load_bearing` norm.
"""

from __future__ import annotations

import pytest

from AgentEval._assertions.adapter import assert_value
from AgentEval.errors import ValidateOperatorDisallowed


def test_validate_gate_default_raises_with_fr56_style_format() -> None:
    """FR43 verbatim default: `allow_validate_operator=False` → raise.

    Message format per Story 6.3 D-8 resolution: FR56-style template
    (keyword name + path:line if inspectable + opt-in remediation
    snippet + ADR link).
    """
    with pytest.raises(ValidateOperatorDisallowed) as exc_info:
        assert_value(
            actual="42",
            operator=None,
            expected="value > 10",
            keyword_name="Should Validate Expression",
            tier=1,
            validate=True,
            allow_validate_operator=False,
        )
    msg = str(exc_info.value)
    # FR56 (a) keyword name verbatim.
    assert "Should Validate Expression" in msg
    # FR56 (c) opt-in remediation snippet.
    assert "Library    AgentEval    allow_validate_operator=True" in msg
    # FR56 (d) ADR link.
    assert "ADR-019" in msg


def test_validate_gate_opt_in_passes() -> None:
    """`allow_validate_operator=True` opens the gate; AssertionEngine dispatches normally."""
    # No operator dispatch (operator=None) — just verify the gate is open.
    assert_value(
        actual="42",
        operator=None,
        expected="value > 10",
        keyword_name="Should Validate Expression",
        tier=1,
        validate=True,
        allow_validate_operator=True,
    )


def test_validate_gate_message_includes_error_code() -> None:
    """`ValidateOperatorDisallowed` has `error_code = "VALIDATE_OPERATOR_DISALLOWED"`
    per error-class-hierarchy.md L67 + ADR-014 catalog.
    """
    try:
        assert_value(
            actual="x",
            operator=None,
            expected="y",
            keyword_name="Kw",
            tier=1,
            validate=True,
            allow_validate_operator=False,
        )
    except ValidateOperatorDisallowed as exc:
        assert exc.error_code == "VALIDATE_OPERATOR_DISALLOWED"
    else:
        pytest.fail("ValidateOperatorDisallowed was not raised")
