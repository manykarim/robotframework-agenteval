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

"""Unit tests for `_kernel/warnings.py` (Story 5.4 AC-5.4.1 + AC-5.4.6)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import warnings as _agenteval_warnings


@pytest.fixture(autouse=True)
def isolated_warnings_state() -> Iterator[None]:
    """Reset module-level warning buffers + context before + after each test."""
    _agenteval_warnings.clear_warnings(None)
    _kernel_context.unbind_context()
    yield
    _agenteval_warnings.clear_warnings(None)
    _kernel_context.unbind_context()


def test_warning_record_is_frozen_dataclass() -> None:
    """`WarningRecord` is frozen — fields cannot be mutated post-construction.

    Story 5.4 code-review 1-way Auditor MED-1 fix 2026-05-20: pre-edit
    used `pytest.raises((AttributeError, Exception))` which matched
    literally any exception class. Tightened to `FrozenInstanceError`
    so a regression where the dataclass is no longer frozen — but
    the mutation raises some unrelated error — would fail this test
    rather than silently pass.
    """
    import dataclasses

    rec = _agenteval_warnings.WarningRecord(
        warning_type="AgentEval.errors.DegradedTraceWarning",
        message="something degraded",
        source="telemetry.listener",
        timestamp=datetime.now(UTC),
        remediation=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.message = "tampered"  # type: ignore[misc]


def test_record_warning_keys_buffer_by_current_test_id() -> None:
    """`record_warning` reads `current_context().test_id` to key the buffer."""
    _kernel_context.set_current_test_id("S.test_alpha", suite_id="S")
    _agenteval_warnings.record_warning(
        warning_type="AgentEval.errors.DegradedTraceWarning",
        message="msg-1",
        source="telemetry.listener",
        remediation="try again",
    )
    records = _agenteval_warnings.get_warnings("S.test_alpha")
    assert len(records) == 1
    assert records[0].message == "msg-1"
    assert records[0].source == "telemetry.listener"
    assert records[0].remediation == "try again"
    assert records[0].warning_type == "AgentEval.errors.DegradedTraceWarning"
    # Timestamp is timezone-aware UTC datetime.
    assert records[0].timestamp.tzinfo is not None
    assert records[0].timestamp.tzinfo.utcoffset(None) == UTC.utcoffset(None)


def test_get_warnings_returns_defensive_copy() -> None:
    """`get_warnings` returns a defensive copy — mutating it doesn't poison the buffer."""
    _kernel_context.set_current_test_id("S.test_alpha", suite_id="S")
    _agenteval_warnings.record_warning(
        warning_type="X",
        message="m1",
        source="src",
    )
    snapshot = _agenteval_warnings.get_warnings("S.test_alpha")
    snapshot.append(
        _agenteval_warnings.WarningRecord(
            warning_type="injected",
            message="hostile",
            source="hostile",
            timestamp=datetime.now(UTC),
            remediation=None,
        )
    )
    # Re-read — the second WarningRecord must NOT be in the buffer.
    fresh = _agenteval_warnings.get_warnings("S.test_alpha")
    assert len(fresh) == 1
    assert fresh[0].message == "m1"


def test_clear_warnings_with_none_removes_all_buffers() -> None:
    """`clear_warnings(None)` wipes ALL per-test buffers + pre-test sentinel."""
    _kernel_context.set_current_test_id("S.test_a", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="a", source="s")
    _kernel_context.set_current_test_id("S.test_b", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="b", source="s")
    removed = _agenteval_warnings.clear_warnings(None)
    assert removed == 2
    assert _agenteval_warnings.get_warnings("S.test_a") == []
    assert _agenteval_warnings.get_warnings("S.test_b") == []


def test_clear_warnings_with_specific_test_id_removes_only_that_buffer() -> None:
    """`clear_warnings('test_id')` removes only the named buffer."""
    _kernel_context.set_current_test_id("S.test_a", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="a1", source="s")
    _agenteval_warnings.record_warning(warning_type="X", message="a2", source="s")
    _kernel_context.set_current_test_id("S.test_b", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="b1", source="s")
    removed = _agenteval_warnings.clear_warnings("S.test_a")
    assert removed == 2
    assert _agenteval_warnings.get_warnings("S.test_a") == []
    # Test B's buffer is untouched.
    assert len(_agenteval_warnings.get_warnings("S.test_b")) == 1


def test_record_warning_under_concurrent_threads_does_not_lose_records() -> None:
    """Story 5.4 code-review 3-way HIGH-A regression: `_warning_buffers` access
    is now guarded by `threading.RLock`. Concurrent `record_warning` calls
    from N threads MUST yield N records (no lost append).
    """
    import threading

    _kernel_context.set_current_test_id("S.parallel", suite_id="S")

    def emit(index: int) -> None:
        _agenteval_warnings.record_warning(
            warning_type="X",
            message=f"thread-{index}",
            source="thread-fixture",
        )

    threads = [threading.Thread(target=emit, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    records = _agenteval_warnings.get_warnings("S.parallel")
    # Each of the 20 threads sees the same bound test_id (ContextVar is
    # set on the main thread; child threads inherit ONLY when spawned
    # via copy_context. Bare `threading.Thread` does NOT copy — child
    # threads see context=None and route to the sentinel). Trace the
    # routing: with bare Thread, all 20 go to `__suite__`. Either way,
    # the lock invariant means: total record count across all buffers
    # is EXACTLY 20 (no lost append from race conditions).
    sentinel_count = len(_agenteval_warnings.get_warnings(_agenteval_warnings._PRE_TEST_BUFFER_KEY))
    assert len(records) + sentinel_count == 20, (
        f"HIGH-A regression: expected 20 total records across S.parallel + sentinel; "
        f"got {len(records)} + {sentinel_count}"
    )


def test_pre_test_sentinel_flushes_into_first_bound_test() -> None:
    """Warnings emitted with NO test bound go into the pre-test sentinel; the
    next `start_test` flush merges them into the first test's buffer.

    Per AC-5.4.6: `current_context() is None` → records go to `__suite__`
    sentinel; the helper `flush_pre_test_buffer(test_id)` merges + clears.
    """
    # No test bound — record goes to the sentinel.
    assert _kernel_context.current_context() is None
    _agenteval_warnings.record_warning(warning_type="X", message="suite-bootstrap-warning", source="discovery")
    # Bind a test + flush the sentinel.
    _kernel_context.set_current_test_id("S.test_first", suite_id="S")
    _agenteval_warnings.flush_pre_test_buffer("S.test_first")
    records = _agenteval_warnings.get_warnings("S.test_first")
    assert len(records) == 1
    assert records[0].message == "suite-bootstrap-warning"
    # Pre-test buffer is cleared after merge.
    assert _agenteval_warnings.get_warnings(_agenteval_warnings._PRE_TEST_BUFFER_KEY) == []
