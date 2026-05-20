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

"""Per-test structured warning collector (Story 5.4 AC-5.4.1 + AC-5.4.6).

Story 5.4 introduces the parallel structured channel that lives alongside
Python's `warnings.warn()` machinery: every `warnings.warn(msg, DegradedTraceWarning)`
emit site in the telemetry pipeline ALSO calls `record_warning(...)` here
so the warning is captured as a typed `WarningRecord` keyed by the current
`_kernel_context.current_context().test_id`. The Listener's `end_test`
serializes the buffer into the run's `RunManifest.warnings` field BEFORE
calling `clear_warnings(test_id)`; the `Get Last Warnings` keyword
(`telemetry/_keywords.py`) is the consumer surface for test authors.

The structured channel does NOT replace Python's `warnings.warn` —- the two
fire side-by-side at each emit site so `-W error::AgentEval.errors.DegradedTraceWarning`
filter semantics are preserved.
"""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from AgentEval._kernel.context import current_context

__all__ = [
    "WarningRecord",
    "record_warning",
    "get_warnings",
    "clear_warnings",
    "flush_pre_test_buffer",
    "warning_record_to_dict",
]


# Sentinel key used when no test_id is bound at `record_warning()` time.
# `flush_pre_test_buffer(test_id)` merges sentinel records into the first
# bound test's buffer and clears the sentinel.
_PRE_TEST_BUFFER_KEY = "__suite__"


@dataclass(frozen=True)
class WarningRecord:
    """Typed per-emit-site warning record (Story 5.4 AC-5.4.1, FR62 ratified shape).

    Five fields matching the 2026-05-20 ratification that unified PRD FR62
    (`source + message + remediation`) with the epics-level Story 5.4 AC
    (`warning_type + timestamp`). The `severity` field from the original
    epics draft was dropped — severity is implicit in the Python warning
    class hierarchy that `warning_type` names.
    """

    warning_type: str
    message: str
    source: str
    timestamp: datetime
    remediation: str | None = None


# Module-level buffer keyed by test_id. Mirrors the `_kernel/trace_store`
# `_spans_by_test` pattern. Each process gets its own module-level dict —
# under `pabot --processes N` this provides natural per-process isolation
# matching the trace-store backplane.
#
# Story 5.4 code-review 3-way HIGH-A fix 2026-05-20 (Blind + Edge-cases ×2):
# pre-edit the dict had no lock, so `record_warning` (read-modify-append
# via `setdefault(key, []).append(record)`) + `clear_warnings(None)`
# (full `dict.clear()`) + `flush_pre_test_buffer` (non-atomic pop+extend)
# could race under any threaded emit path (OTel BatchSpanProcessor worker,
# async MCP observer callbacks). Mirrors the Story 1b.2 H_R8 catch on
# `trace_store.clear_spans`. Re-entrant friendly so a `record_warning`
# call from inside a lock-holding caller does not deadlock.
_buffer_lock = threading.RLock()
_warning_buffers: dict[str, list[WarningRecord]] = {}


def record_warning(
    *,
    warning_type: str,
    message: str,
    source: str,
    remediation: str | None = None,
) -> None:
    """Capture a `WarningRecord` keyed by the current test_id.

    MUST NOT raise — internal errors are swallowed via
    `contextlib.suppress(Exception)`. The original `warnings.warn(...)`
    Python channel still fires per caller contract.

    Per AC-5.4.6: when `current_context()` returns None (no test bound,
    e.g., warnings emitted during library bootstrap at `start_suite`
    time), records go into the `_PRE_TEST_BUFFER_KEY` sentinel. The
    Listener calls `flush_pre_test_buffer(test_id)` at the next
    `start_test` to merge the sentinel into the test's buffer.
    """
    with contextlib.suppress(Exception):
        ctx = current_context()
        key = ctx.test_id if ctx is not None and ctx.test_id else _PRE_TEST_BUFFER_KEY
        record = WarningRecord(
            warning_type=warning_type,
            message=message,
            source=source,
            timestamp=datetime.now(UTC),
            remediation=remediation,
        )
        with _buffer_lock:
            _warning_buffers.setdefault(key, []).append(record)


def get_warnings(test_id: str = "current") -> list[WarningRecord]:
    """Return a defensive copy of the per-test warning buffer.

    Four lookup modes per AC-5.4.5 + Story 5.5 code-review HIGH-C closure:

    - `test_id="current"` (default): resolves to `current_context().test_id`
      via the same accessor `record_warning` uses; returns `[]` if no test
      is bound.
    - `test_id="all"`: returns the union across all per-test buffers
      (EXCLUDING the pre-test sentinel), sorted by `timestamp` ascending.
    - `test_id="__suite__"`: explicit accessor for the pre-test sentinel
      buffer. Story 5.5 code-review 3-way HIGH-C fix 2026-05-20: required
      for Listener-less invocation contexts where `record_warning` routes
      to the sentinel (DF-5.5-DOGFOOD-4 closure / C45).
    - `test_id="<specific>"`: returns the named buffer (or `[]` if absent).

    Returns a defensive copy per Story 1b.2 M_R6 — callers mutating the
    returned list cannot poison the internal buffer.

    Must not raise; falls back to `[]` on any internal error.
    """
    try:
        if test_id == "current":
            ctx = current_context()
            if ctx is None or not ctx.test_id:
                return []
            key = ctx.test_id
        elif test_id == "all":
            # Story 5.4 code-review 3-way HIGH-A: snapshot under lock so
            # concurrent `record_warning` cannot mutate the per-test
            # lists during iteration. Defensive-copy each list before
            # `collected.extend` so the returned snapshot is decoupled
            # from buffer state.
            with _buffer_lock:
                collected: list[WarningRecord] = []
                for k, records in _warning_buffers.items():
                    if k == _PRE_TEST_BUFFER_KEY:
                        continue
                    collected.extend(list(records))
            collected.sort(key=lambda r: r.timestamp)
            return collected
        elif test_id == "__suite__":
            # Story 5.5 code-review 3-way HIGH-C fix 2026-05-20 (Blind HIGH-5 +
            # Edge-cases HIGH-EC-4 + Auditor HIGH-3): the `_PRE_TEST_BUFFER_KEY`
            # sentinel buffer is reachable for the Listener-less dogfood case
            # (DF-5.5-DOGFOOD-4). Pre-edit: `.robot` suites running without
            # `--listener AgentEval.telemetry.listener` had `current_context()`
            # return None → records routed to sentinel → `current` lookup
            # returns `[]` + `all` lookup EXCLUDES sentinel → records
            # unreachable via the public keyword surface. Now `test_id="__suite__"`
            # explicitly returns the sentinel records (closes C45 from
            # `feedback_carry_over_catalog_gate` catalog).
            with _buffer_lock:
                return list(_warning_buffers.get(_PRE_TEST_BUFFER_KEY, []))
        else:
            key = test_id
        with _buffer_lock:
            return list(_warning_buffers.get(key, []))
    except Exception:  # noqa: BLE001
        return []


def clear_warnings(test_id: str | None = None) -> int:
    """Remove a per-test buffer (or all buffers when `test_id is None`).

    Returns the number of `WarningRecord` instances removed. Must not raise.
    """
    try:
        with _buffer_lock:
            if test_id is None:
                total = sum(len(records) for records in _warning_buffers.values())
                _warning_buffers.clear()
                return total
            removed = _warning_buffers.pop(test_id, [])
            return len(removed)
    except Exception:  # noqa: BLE001
        return 0


def flush_pre_test_buffer(test_id: str) -> int:
    """Merge sentinel-keyed pre-test records into `test_id`'s buffer.

    Per AC-5.4.6: warnings emitted during `start_suite` (before any
    `start_test`) land in the `_PRE_TEST_BUFFER_KEY` sentinel. The
    Listener calls this helper from `start_test` AFTER `set_current_test_id`
    so the first test's `Get Last Warnings` output surfaces the
    library-bootstrap warnings.

    The merge is one-way (sentinel → first test) + the sentinel is
    cleared post-flush so subsequent `start_test` calls do not see
    the same records again.

    Returns the number of records merged. Must not raise.
    """
    try:
        # Story 5.4 code-review HIGH-A + Edge-cases HIGH-6: the pop+extend
        # is non-atomic — a concurrent `record_warning` to the sentinel
        # between these two operations would re-create the sentinel
        # entry with a fresh list while the flushed records routed to
        # the named test_id. Holding the buffer lock for the full
        # critical section closes the race.
        with _buffer_lock:
            sentinel_records = _warning_buffers.pop(_PRE_TEST_BUFFER_KEY, [])
            if not sentinel_records:
                return 0
            _warning_buffers.setdefault(test_id, []).extend(sentinel_records)
            return len(sentinel_records)
    except Exception:  # noqa: BLE001
        return 0


def warning_record_to_dict(record: WarningRecord) -> dict[str, Any]:
    """Convert a `WarningRecord` to a JSON-serializable dict (5-field shape).

    Used by both the Listener's `_emit_run_manifest_sidecar` (AC-5.4.4) +
    the `Get Last Warnings` keyword (AC-5.4.5) so the serialization shape
    is consistent across both surfaces.

    `timestamp` is serialized via `.isoformat()` per RFC 3339 — matches
    the `_json_default` callable in `telemetry/run_manifest.py` per
    Story 5.3 HIGH-J fix.
    """
    return {
        "warning_type": record.warning_type,
        "message": record.message,
        "source": record.source,
        "timestamp": record.timestamp.isoformat(),
        "remediation": record.remediation,
    }
