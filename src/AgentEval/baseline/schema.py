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

"""Baseline (de)serialization + schema validation (design Decision 6).

- ``SCHEMA_VERSION = 1``.
- ``serialize`` produces deterministic, diff-friendly JSON (``indent=2``,
  ``sort_keys=True``, trailing newline) after passing the payload through the
  kernel redaction layer (``redact_dict``) at the write boundary — a committed
  file must never carry a credential.
- ``serialize_line`` produces one compact JSON line for the append-mode
  history (``JSONLBackend`` idiom).
- ``load`` validates ``schema_version`` + required fields and reconstructs the
  ``MetricsBaseline``, raising the structured ``BaselineSchemaError`` on drift.
"""

from __future__ import annotations

import json
from typing import Any

from AgentEval._kernel.redaction import redact_dict
from AgentEval.baseline.models import (
    ContinuousEvidence,
    MetricsBaseline,
    ProportionEvidence,
    RunContext,
)
from AgentEval.errors import BaselineSchemaError

__all__ = [
    "SCHEMA_VERSION",
    "load",
    "parse_snapshot",
    "serialize",
    "serialize_line",
    "to_payload",
]

SCHEMA_VERSION = 1

_RUN_CONTEXT_KEYS = (
    "model",
    "adapter_name",
    "adapter_version",
    "library_version",
    "timestamp",
    "git_sha",
    "git_dirty",
)


def to_payload(baseline: MetricsBaseline) -> dict[str, Any]:
    """Redacted, JSON-serializable dict for ``baseline`` (defense-in-depth redaction)."""
    return redact_dict(baseline.as_dict())


def serialize(baseline: MetricsBaseline) -> str:
    """Deterministic pretty JSON for a committed baseline (design D6).

    ``sort_keys=True`` + ``indent=2`` + trailing newline so re-snapshots
    produce reviewable diffs.
    """
    payload = to_payload(baseline)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def serialize_line(baseline: MetricsBaseline) -> str:
    """One compact JSON line for the append-mode history (``JSONLBackend`` idiom)."""
    payload = to_payload(baseline)
    # Compact separators; sorted keys keep each line stable/diffable too.
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def parse_snapshot(text: str, *, source: str = "<history>", validate_metrics: bool = False) -> dict[str, Any]:
    """Parse one snapshot JSON object (raw dict) + validate its ``schema_version``.

    Used by the history reader for each JSONL line. Raises ``BaselineSchemaError``
    on parse failure or unsupported version.

    When ``validate_metrics=True`` the full per-metric evidence is reconstructed
    (via ``_from_payload``) so a line that is valid JSON with a supported
    ``schema_version`` but malformed metric evidence (e.g. ``successes="oops"``)
    raises ``BaselineSchemaError`` HERE rather than crashing a downstream
    consumer that coerces the fields later (design 4.1 — corrupt lines are
    skipped with a warning, not left to crash trend parsing).
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BaselineSchemaError(
            f"could not parse baseline JSON: {exc}",
            file_path=source,
            field_name=None,
            fix_suggestion="Re-generate the baseline via `Save Metrics Baseline`; the file is corrupt.",
        ) from exc
    _validate_shape(data, source=source)
    # `_validate_shape` raises unless `data` is a dict; narrow for mypy.
    assert isinstance(data, dict)
    if validate_metrics:
        # Full reconstruction for the raise-on-drift side effect only; the caller
        # keeps the raw dict. `load` performs the same call after parse_snapshot.
        _from_payload(data, source=source)
    return data


def load(text: str, *, source: str = "<baseline>") -> MetricsBaseline:
    """Parse + validate a baseline file's text → ``MetricsBaseline`` (design D6).

    Raises ``BaselineSchemaError`` when the JSON is unparseable, the
    ``schema_version`` is unsupported, or a required field is missing / of the
    wrong shape (naming the offending field).
    """
    data = parse_snapshot(text, source=source)
    return _from_payload(data, source=source)


def _validate_shape(data: Any, *, source: str) -> None:
    if not isinstance(data, dict):
        raise BaselineSchemaError(
            f"baseline root must be a JSON object; got {type(data).__name__}",
            file_path=source,
            field_name=None,
            fix_suggestion="Re-generate via `Save Metrics Baseline`.",
        )
    if "schema_version" not in data:
        raise BaselineSchemaError(
            "baseline is missing the required 'schema_version' field",
            file_path=source,
            field_name="schema_version",
            fix_suggestion=f"Re-generate via `Save Metrics Baseline` (current schema_version={SCHEMA_VERSION}).",
        )
    found = data["schema_version"]
    if found != SCHEMA_VERSION:
        raise BaselineSchemaError(
            f"unsupported baseline schema_version {found!r}; this build supports {SCHEMA_VERSION}",
            file_path=source,
            field_name="schema_version",
            fix_suggestion=(
                f"Found schema_version={found!r}, supported={SCHEMA_VERSION}. Upgrade/downgrade "
                "robotframework-agenteval to a build that matches, or re-snapshot the baseline."
            ),
        )
    for key in ("metrics", "run_context"):
        if key not in data:
            raise BaselineSchemaError(
                f"baseline is missing the required {key!r} field",
                file_path=source,
                field_name=key,
                fix_suggestion="Re-generate via `Save Metrics Baseline`.",
            )
    if not isinstance(data["metrics"], dict):
        raise BaselineSchemaError(
            "baseline 'metrics' must be a JSON object",
            file_path=source,
            field_name="metrics",
            fix_suggestion="Re-generate via `Save Metrics Baseline`.",
        )
    if not isinstance(data["run_context"], dict):
        raise BaselineSchemaError(
            "baseline 'run_context' must be a JSON object",
            file_path=source,
            field_name="run_context",
            fix_suggestion="Re-generate via `Save Metrics Baseline`.",
        )


def _schema_error(source: str, name: str, field: str, message: str) -> BaselineSchemaError:
    return BaselineSchemaError(
        message,
        file_path=source,
        field_name=f"metrics.{name}.{field}",
        fix_suggestion="Re-generate via `Save Metrics Baseline`; the metric evidence is malformed.",
    )


def _require(payload: dict[str, Any], name: str, field: str, source: str) -> Any:
    if field not in payload:
        raise _schema_error(source, name, field, f"metric {name!r} is missing required field {field!r}")
    return payload[field]


def _as_int(value: Any, name: str, field: str, source: str) -> int:
    # Reject bool (a JSON `true` is not a valid count) and any non-integer coercion.
    if isinstance(value, bool) or not isinstance(value, int):
        raise _schema_error(source, name, field, f"metric {name!r} field {field!r} must be an integer; got {value!r}")
    return int(value)


def _as_float(value: Any, name: str, field: str, source: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _schema_error(source, name, field, f"metric {name!r} field {field!r} must be a number; got {value!r}")
    return float(value)


def _from_payload(data: dict[str, Any], *, source: str) -> MetricsBaseline:
    metrics: dict[str, ProportionEvidence | ContinuousEvidence] = {}
    for name, payload in data["metrics"].items():
        if not isinstance(payload, dict) or "kind" not in payload:
            raise BaselineSchemaError(
                f"metric {name!r} entry must be an object with a 'kind' field",
                file_path=source,
                field_name=f"metrics.{name}",
                fix_suggestion="Re-generate via `Save Metrics Baseline`.",
            )
        kind = payload["kind"]
        if kind == "proportion":
            successes = _as_int(_require(payload, name, "successes", source), name, "successes", source)
            trials = _as_int(_require(payload, name, "trials", source), name, "trials", source)
            value = _as_float(_require(payload, name, "value", source), name, "value", source)
            if not (0 <= successes <= trials):
                raise _schema_error(
                    source,
                    name,
                    "successes",
                    f"metric {name!r} requires 0 <= successes <= trials; got successes={successes}, trials={trials}",
                )
            if not (0.0 <= value <= 1.0):
                raise _schema_error(
                    source, name, "value", f"metric {name!r} proportion value must be in [0, 1]; got {value!r}"
                )
            k_raw = payload.get("k")
            metrics[name] = ProportionEvidence(
                successes=successes,
                trials=trials,
                value=value,
                k=(_as_int(k_raw, name, "k", source) if k_raw is not None else None),
            )
        elif kind == "continuous":
            samples_raw = payload.get("samples", ())
            if not isinstance(samples_raw, (list, tuple)):
                raise _schema_error(
                    source, name, "samples", f"metric {name!r} field 'samples' must be a list of numbers"
                )
            metrics[name] = ContinuousEvidence(
                samples=tuple(_as_float(s, name, "samples", source) for s in samples_raw),
                value=_as_float(_require(payload, name, "value", source), name, "value", source),
                total=_as_float(payload.get("total", 0.0), name, "total", source),
                mean=_as_float(payload.get("mean", 0.0), name, "mean", source),
                p50=_as_float(payload.get("p50", 0.0), name, "p50", source),
                p95=_as_float(payload.get("p95", 0.0), name, "p95", source),
                samples_truncated=bool(payload.get("samples_truncated", False)),
            )
        else:
            raise BaselineSchemaError(
                f"metric {name!r} has unknown kind {kind!r}",
                file_path=source,
                field_name=f"metrics.{name}.kind",
                fix_suggestion="Supported kinds: 'proportion', 'continuous'.",
            )
    rc = data["run_context"]
    run_context = RunContext(**{key: rc.get(key) for key in _RUN_CONTEXT_KEYS})
    extra = data.get("extra_metrics", {}) or {}
    extra_metrics = {str(k): float(v) for k, v in extra.items()}
    return MetricsBaseline(
        schema_version=SCHEMA_VERSION,
        metrics=metrics,
        extra_metrics=extra_metrics,
        run_context=run_context,
    )
