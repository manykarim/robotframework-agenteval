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

"""Unit tests for `_kernel/tier_acl.py` (Story 6.3 AC-6.3.13)."""

from __future__ import annotations

import pytest

from AgentEval._kernel.tier_acl import (
    build_polling_disallowed_message,
    enforce_tier1_no_llm,
    enforce_validate_operator_disallowed,
)
from AgentEval.errors import TierViolationError, ValidateOperatorDisallowed

# --------------------------------------------------------------------------- #
# enforce_tier1_no_llm — call-stack walker (4 tests)                          #
# --------------------------------------------------------------------------- #


class _Tier1FakeLib:
    """Tier-1 fake — the method name `kw` matches the class attribute."""

    def kw(self) -> None:
        enforce_tier1_no_llm()

    kw._agenteval_tier = 1  # type: ignore[attr-defined]
    kw.robot_name = "Get Frontmatter"  # type: ignore[attr-defined]


class _Tier2FakeLib:
    def kw(self) -> None:
        enforce_tier1_no_llm()

    kw._agenteval_tier = 2  # type: ignore[attr-defined]
    kw.robot_name = "Send Prompt"  # type: ignore[attr-defined]


class _Tier3FakeLib:
    def kw(self) -> None:
        enforce_tier1_no_llm()

    kw._agenteval_tier = 3  # type: ignore[attr-defined]
    kw.robot_name = "Stat.Run N Times"  # type: ignore[attr-defined]


def test_enforce_tier1_no_llm_tier_1_raises() -> None:
    """Tier-1 frame on stack → TierViolationError."""
    with pytest.raises(TierViolationError, match=r"Tier-1 keyword 'Get Frontmatter'"):
        _Tier1FakeLib().kw()


def test_enforce_tier1_no_llm_tier_2_passes() -> None:
    """Tier-2 frame on stack → no raise."""
    _Tier2FakeLib().kw()


def test_enforce_tier1_no_llm_tier_3_passes() -> None:
    _Tier3FakeLib().kw()


def test_enforce_tier1_no_llm_no_keyword_frame_is_noop() -> None:
    """Called from a non-`@keyword` context (pytest fixture): no raise."""
    enforce_tier1_no_llm()  # graceful no-op


# --------------------------------------------------------------------------- #
# enforce_validate_operator_disallowed (2 tests)                              #
# --------------------------------------------------------------------------- #


def test_validate_gate_raises_when_disabled() -> None:
    with pytest.raises(ValidateOperatorDisallowed) as exc_info:
        enforce_validate_operator_disallowed(
            allow_validate_operator=False,
            keyword_name="My Custom Assertion",
        )
    msg = str(exc_info.value)
    assert "My Custom Assertion" in msg
    assert "allow_validate_operator=True" in msg


def test_validate_gate_noop_when_enabled() -> None:
    # No raise when opt-in is True.
    enforce_validate_operator_disallowed(
        allow_validate_operator=True,
        keyword_name="My Custom Assertion",
    )


# --------------------------------------------------------------------------- #
# build_polling_disallowed_message — FR56 format (2 tests)                    #
# --------------------------------------------------------------------------- #


def test_polling_message_contains_fr56_fields() -> None:
    """FR56 verbatim: keyword name + remediation snippet + ADR link."""
    msg = build_polling_disallowed_message(keyword_name="Send Prompt", keyword_args={"prompt": "Hi"})
    assert "Send Prompt" in msg
    assert "Stat.Run N Times" in msg  # remediation snippet
    assert "ADR-019" in msg


def test_polling_message_no_args() -> None:
    """When `keyword_args=None`, message still includes a sensible remediation snippet."""
    msg = build_polling_disallowed_message(keyword_name="Send Prompt", keyword_args=None)
    assert "Send Prompt" in msg
    assert "Stat.Run N Times" in msg


# --------------------------------------------------------------------------- #
# Story 6.3 code-review HIGH regression tests                                 #
# --------------------------------------------------------------------------- #


def test_polling_message_renders_rf_valid_keyword_args_syntax() -> None:
    """HIGH-8 regression (Blind 1-way): `keyword_args` must render as RF
    list-of-`key=value` syntax (NOT Python dict repr). Pre-edit produced
    `keyword_args={'prompt': 'Hi'}` which RF parses as a single string.
    """
    msg = build_polling_disallowed_message(
        keyword_name="Send Prompt",
        keyword_args={"prompt": "Hi", "model": "gpt-4"},
    )
    # RF named-arg syntax: `keyword_args=[prompt=Hi, model=gpt-4]`
    assert "[prompt=Hi, model=gpt-4]" in msg
    # MUST NOT contain Python dict literal punctuation.
    assert "{'prompt'" not in msg
    assert "'Hi'" not in msg


def test_extract_caller_path_line_rejects_cache_robot_paths() -> None:
    """HIGH-ε regression (Codex + Edge + Auditor 3-way): pre-edit
    `"/robot/" in filename` falsely matched any path containing `/robot/`
    (e.g., `.cache/robot/`, `site-packages/robot/`). Now matches
    `.endswith('.robot')` only.

    Direct unit-level test of the helper using `inspect.stack()` simulation.
    """
    import inspect
    from unittest.mock import patch

    from AgentEval._kernel.tier_acl import _extract_caller_path_line

    # Build fake frames containing `/robot/` substring but not ending in `.robot`.
    class FakeFrameInfo:
        def __init__(self, filename: str, lineno: int = 42) -> None:
            self.filename = filename
            self.lineno = lineno

    fake_stack = [
        FakeFrameInfo("/home/many/.cache/robot/tmp.py", 10),
        FakeFrameInfo("/.venv/lib/python3.12/site-packages/robot/libraries/BuiltIn.py", 20),
        FakeFrameInfo("/some/regular/python.py", 30),
    ]
    with patch.object(inspect, "stack", return_value=fake_stack):
        assert _extract_caller_path_line() is None


def test_extract_caller_path_line_accepts_real_robot_file() -> None:
    """HIGH-ε positive case: `.endswith('.robot')` correctly matches."""
    import inspect
    from unittest.mock import patch

    from AgentEval._kernel.tier_acl import _extract_caller_path_line

    class FakeFrameInfo:
        def __init__(self, filename: str, lineno: int = 42) -> None:
            self.filename = filename
            self.lineno = lineno

    fake_stack = [
        FakeFrameInfo("/some/regular/python.py", 10),
        FakeFrameInfo("/path/to/tests/my_suite.robot", 25),
    ]
    with patch.object(inspect, "stack", return_value=fake_stack):
        assert _extract_caller_path_line() == "/path/to/tests/my_suite.robot:25"


def test_enforce_tier1_no_llm_through_guarded_fanout_wrapped_method() -> None:
    """HIGH-δ regression (Codex + Blind + Auditor 3-way): the stack walker
    must use `find_tier_through_wrappers` so `@tier(1)` annotations on
    decorator-wrapped methods (functools.wraps chain) are detected.
    """
    import functools

    from robot.api.deco import keyword as rf_keyword

    from AgentEval._kernel.tier import tier

    def _decorator(func):
        @functools.wraps(func)
        def wrapper(self):
            return func(self)

        return wrapper

    class WrappedLib:
        @rf_keyword(name="Wrapped Tier 1")
        @tier(1)
        @_decorator
        def wrapped_kw(self) -> None:
            enforce_tier1_no_llm()

    with pytest.raises(TierViolationError, match=r"Wrapped Tier 1"):
        WrappedLib().wrapped_kw()


def test_polling_message_renders_rf_keyword_args_when_threaded_through_adapter() -> None:
    """LOW-10 regression (Codex + Blind 2-way): `adapter.assert_value` must
    thread the caller's `keyword_args` through to `build_polling_disallowed_message`
    so the FR56 remediation snippet shows actual args (not `[]`).
    """
    from AgentEval._assertions.adapter import assert_value
    from AgentEval.errors import PollingDisallowedError

    with pytest.raises(PollingDisallowedError) as exc_info:
        assert_value(
            actual=1,
            operator=">=",
            expected=0,
            keyword_name="Send Prompt",
            tier=2,
            polling=0.5,
            keyword_args={"prompt": "Hello"},
        )
    msg = str(exc_info.value)
    # FR56 (c) verbatim: remediation snippet contains the actual args.
    assert "[prompt=Hello]" in msg
