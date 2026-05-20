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

"""Unit tests for the `Get Last Warnings` keyword (Story 5.4 AC-5.4.5)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval.telemetry.library import TelemetryLibrary


@pytest.fixture(autouse=True)
def isolated_warnings_state() -> Iterator[None]:
    """Reset module-level buffers + context before + after each test."""
    _agenteval_warnings.clear_warnings(None)
    _kernel_context.unbind_context()
    yield
    _agenteval_warnings.clear_warnings(None)
    _kernel_context.unbind_context()


def test_get_last_warnings_current_returns_current_test_buffer() -> None:
    """`Get Last Warnings test_id=current` returns 5-key dicts for the bound test."""
    _kernel_context.set_current_test_id("S.test_a", suite_id="S")
    _agenteval_warnings.record_warning(
        warning_type="AgentEval.errors.DegradedTraceWarning",
        message="msg-a",
        source="telemetry.listener",
        remediation="advice",
    )
    lib = TelemetryLibrary()
    out = lib.get_last_warnings("current")
    assert len(out) == 1
    rec = out[0]
    # 5 fields per FR62 ratified shape.
    assert set(rec.keys()) == {"warning_type", "message", "source", "timestamp", "remediation"}
    assert rec["warning_type"] == "AgentEval.errors.DegradedTraceWarning"
    assert rec["message"] == "msg-a"
    assert rec["source"] == "telemetry.listener"
    assert rec["remediation"] == "advice"
    # Timestamp is RFC 3339 string (was datetime in WarningRecord).
    assert isinstance(rec["timestamp"], str)
    assert "T" in rec["timestamp"]


def test_get_last_warnings_all_unions_and_sorts_across_tests() -> None:
    """`Get Last Warnings test_id=all` returns the union sorted by timestamp ascending."""
    _kernel_context.set_current_test_id("S.test_a", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="a-first", source="s")
    _kernel_context.set_current_test_id("S.test_b", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="b-second", source="s")
    lib = TelemetryLibrary()
    out = lib.get_last_warnings("all")
    assert len(out) == 2
    # First event recorded should appear first.
    assert out[0]["message"] == "a-first"
    assert out[1]["message"] == "b-second"
    # Sort key is the timestamp; assert non-decreasing.
    assert out[0]["timestamp"] <= out[1]["timestamp"]


def test_get_last_warnings_unknown_test_id_returns_empty_list() -> None:
    """`Get Last Warnings test_id=does-not-exist` returns `[]` without raising."""
    lib = TelemetryLibrary()
    out = lib.get_last_warnings("S.never_ran")
    assert out == []


def test_get_last_warnings_no_current_test_returns_empty_list() -> None:
    """`Get Last Warnings test_id=current` returns `[]` when no test is bound."""
    assert _kernel_context.current_context() is None
    lib = TelemetryLibrary()
    out = lib.get_last_warnings("current")
    assert out == []
