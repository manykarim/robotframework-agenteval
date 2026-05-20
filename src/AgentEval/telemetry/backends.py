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

"""Trace backends for Story 5.1 — memory (default) + JSONL (opt-in).

Per PRD FR33b ("memory + JSONL backends Phase 1; OTLP Phase 2 via ``[otlp]``
extra"). Memory backend is a thin wrapper around Story 1b.2's
``_kernel/trace_store`` projection accessors; JSONL backend serializes spans
to a one-line-per-span JSONL file at flush time.

JSONL artifact path convention (per PRD FR51 + Story 5.1 AC-5.1.6):

    <output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl

Story 5.4 forward-ref: JSONL write failures emit ``DegradedTraceWarning``
(Story 5.4 lands the class). Story 5.1 uses ``warnings.warn`` with a future-
class TODO; DF-5.1-S1 tracks the upgrade.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from AgentEval._kernel import trace_store

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

__all__ = [
    "MemoryBackend",
    "JSONLBackend",
]


# Allow alnum + `_-.` only; anything else collapses to `_` to avoid path traversal.
_PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9_.\-]")


def _sanitize_path_segment(segment: str) -> str:
    """Replace path-unsafe characters with `_` to prevent traversal via test_id/suite_id.

    Story 5.1 code-review 2-way MED fix 2026-05-20 (Blind MED-2 + Edge-cases
    M1): pre-edit allowed ``.``-only segments (``..``, ``...``) through
    verbatim because the regex permits ``.``. POSIX path components are flat
    so traversal didn't actually escape, but the safety guarantee was
    accidental — defense-in-depth says reject the literal `.` / `..` /
    all-dot patterns explicitly.
    """
    sanitized = _PATH_SAFE_RE.sub("_", segment)
    if not sanitized:
        return "_"
    # Reject `.` / `..` / all-dot segments outright — they're path-component
    # semantics, not data, even on POSIX where they can't traverse a single
    # filename segment.
    if sanitized.strip(".") == "":
        return "_"
    return sanitized


class MemoryBackend:
    """In-memory trace backend (default per PRD FR42).

    Thin wrapper around Story 1b.2's ``_kernel/trace_store`` projection
    accessors. Memory backend isolation is enforced by the
    ``agenteval.test_id`` Resource attribute filter at the trace_store layer
    (Story 1b.2 H_R2). This class exists primarily so the Listener has a
    uniform backend API; consumers query traces via the public
    ``_kernel/trace_store`` accessors directly.

    No persistence; spans are cleared via ``clear_spans(test_id)`` after
    each test (Listener's ``end_test`` hook).
    """

    name = "memory"

    def flush_test(self, test_id: str, suite_id: str = "", output_dir: Path | None = None) -> None:
        """No-op flush. The InMemorySpanExporter already holds spans in memory.

        Args:
            test_id: RF Listener v3 test identifier.
            suite_id: RF Listener v3 suite identifier (unused for memory).
            output_dir: Unused for memory; accepted for API uniformity.
        """
        _ = test_id
        _ = suite_id
        _ = output_dir


class JSONLBackend:
    """JSONL trace backend (opt-in via ``trace_backend="jsonl"``).

    On ``flush_test``, serializes all spans for the test into one JSON line
    per span at ``<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl``.

    On write failure: emits a warning (forward-ref to Story 5.4's
    ``DegradedTraceWarning``) and does NOT raise — test outcomes must not
    be masked by trace-backend hygiene. The spans are preserved in memory
    (clear is gated on a successful write per Story 5.1 AC-5.1.6).
    """

    name = "jsonl"

    def flush_test(
        self,
        test_id: str,
        suite_id: str = "",
        output_dir: Path | None = None,
    ) -> Path | None:
        """Serialize all spans for ``test_id`` to a JSONL file.

        Args:
            test_id: RF Listener v3 test identifier.
            suite_id: RF Listener v3 suite identifier (used in the filename).
            output_dir: Directory to write the JSONL artifact into. When
                ``None``, falls back to ``Path.cwd()``. The function creates
                ``<output_dir>/agenteval/`` if missing.

        Returns:
            The written file path on success; ``None`` on write failure
            (after emitting a warning).
        """
        spans = trace_store.get_run_spans(test_id)
        # Story 5.1 code-review Edge-cases M3 fix 2026-05-20: skip writing
        # the JSONL file entirely when the test produced zero spans —
        # phantom 0-byte artifacts mislead operators into thinking the test
        # was traced when in reality it ran without span emission.
        if not spans:
            return None
        target_dir = (output_dir if output_dir is not None else Path.cwd()) / "agenteval"
        safe_suite = _sanitize_path_segment(suite_id or "_suite")
        safe_test = _sanitize_path_segment(test_id or "_test")
        target_path = target_dir / f"trace__{safe_suite}__{safe_test}.jsonl"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            with target_path.open("w", encoding="utf-8") as fp:
                for span in spans:
                    fp.write(_span_to_jsonl_line(span))
                    fp.write("\n")
        except (OSError, ValueError, RecursionError) as exc:
            # Story 5.1 code-review HIGH-J fix 2026-05-20 (Edge-cases H2):
            # pre-edit only caught OSError. ValueError (json.dumps circular
            # references) and RecursionError (deep nesting) propagated past
            # flush_test → end_test → into RF Listener machinery, violating
            # AC-5.1.6's "backend failures must not mask test outcomes"
            # guarantee. Now widened to the full JSON-serialization failure
            # surface. Story 5.4 forward-ref (DF-5.1-S1): replace
            # `UserWarning` with `DegradedTraceWarning` once Story 5.4 lands.
            warnings.warn(
                f"AgentEval JSONL backend write failed at {target_path}: {exc}; "
                "spans preserved in memory backend for next attempt "
                "(DF-5.1-S1 upgrade to DegradedTraceWarning when Story 5.4 lands)",
                UserWarning,
                stacklevel=2,
            )
            return None
        return target_path


def _span_to_jsonl_line(span: ReadableSpan) -> str:
    """Serialize one ``ReadableSpan`` to a JSON line.

    Schema (Phase-1; aligned to OTel JSON envelope shape but not strictly
    OTel-LP-compliant; Phase-2 OTLP backend will use the canonical envelope):

        {
          "name": "<span name>",
          "trace_id": "<32-hex trace id>",
          "span_id": "<16-hex span id>",
          "parent_span_id": "<16-hex span id> | null",
          "start_time_unix_ns": <int>,
          "end_time_unix_ns": <int>,
          "attributes": {<key>: <value>, ...},
          "resource_attributes": {<key>: <value>, ...},
          "status": {"status_code": "OK"|"ERROR"|"UNSET", "description": <str>|null}
        }

    On any serialization failure for a specific attribute value, fall back
    to ``str(value)`` so the overall write proceeds.
    """
    ctx = span.get_span_context()
    parent_ctx = span.parent
    record = {
        "name": span.name,
        "trace_id": f"{ctx.trace_id:032x}" if ctx is not None else None,
        "span_id": f"{ctx.span_id:016x}" if ctx is not None else None,
        "parent_span_id": f"{parent_ctx.span_id:016x}" if parent_ctx is not None else None,
        "start_time_unix_ns": span.start_time,
        "end_time_unix_ns": span.end_time,
        "attributes": _safe_dict(dict(span.attributes) if span.attributes else {}),
        "resource_attributes": _safe_dict(
            dict(span.resource.attributes) if span.resource and span.resource.attributes else {}
        ),
        "status": {
            "status_code": span.status.status_code.name if span.status else "UNSET",
            "description": span.status.description if span.status else None,
        },
    }
    return json.dumps(record, ensure_ascii=False)


def _safe_dict(d: dict[str, object]) -> dict[str, object]:
    """Coerce any non-JSON-encodable values to ``str(value)`` defensively.

    OTel attribute values are restricted to JSON-encodable primitives + lists
    of primitives by the SDK, but a buggy producer could still emit a value
    that ``json.dumps`` rejects. Backend write failures must not mask test
    outcomes, so we fall back to ``str``.

    Story 5.1 code-review Edge-cases H2 fix 2026-05-20: widen the catch from
    just ``TypeError`` to ``(TypeError, ValueError, RecursionError)`` so
    circular-reference + deep-nesting attributes don't propagate. ``repr()``
    is the last-resort fallback when even ``str()`` fails.
    """
    safe: dict[str, object] = {}
    for k, v in d.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError, RecursionError):
            try:
                safe[k] = str(v)
            except Exception:  # noqa: BLE001 — last-resort serialization
                safe[k] = repr(v)
    return safe
