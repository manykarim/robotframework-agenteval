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

"""The normalized run-metrics record and its declarative expected-tool contract.

``RunMetrics`` is modeled on rf-mcp's ``ScenarioResult`` shape - a superset that
adds token/cost attribution rf-mcp lacks - so numbers from the in-process
LiteLLM adapter and the CLI subprocess adapters land in one comparable record.
Every field is derived from the recorded trace, never from model self-report.

``ExpectedToolCall`` is a declarative contract: a run "meets" an entry when its
recorded trace called ``tool`` between ``min_calls`` and ``max_calls`` times with
every ``required_args`` key present (and, when a value is given, matching). The
``tool_hit_rate`` is the met/total ratio over the contract entries.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from AgentEval._core.types import AgentRunResult, ToolCallTrace, Usage

__all__ = [
    "ExpectedToolCall",
    "RunMetrics",
    "compute_run_metrics",
]


@dataclass(frozen=True)
class ExpectedToolCall:
    """One declarative expected-tool contract entry.

    ``required_args`` is a mapping of arg name to expected value. A recorded call
    satisfies a key when the key is present in the call's args; when the mapped
    value is not ``None`` the recorded value must equal it, so ``{"path": None}``
    asserts only that the ``path`` arg was passed at all.
    """

    tool: str
    min_calls: int = 1
    max_calls: int | None = None
    required_args: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.min_calls < 0:
            raise ValueError(f"ExpectedToolCall.min_calls must be non-negative; got {self.min_calls!r}")
        if self.max_calls is not None and self.max_calls < self.min_calls:
            raise ValueError(
                f"ExpectedToolCall.max_calls ({self.max_calls!r}) must be >= min_calls ({self.min_calls!r})"
            )
        if self.required_args is not None:
            object.__setattr__(self, "required_args", dict(self.required_args))

    def _call_matches(self, call: ToolCallTrace) -> bool:
        """True when a single recorded call matches this entry's tool + required args."""
        if call.name != self.tool:
            return False
        if self.required_args:
            for key, value in self.required_args.items():
                if key not in call.args:
                    return False
                if value is not None and call.args[key] != value:
                    return False
        return True

    def count_in(self, calls: Iterable[ToolCallTrace]) -> int:
        """Number of recorded calls that match this entry."""
        return sum(1 for call in calls if self._call_matches(call))

    def is_met_by(self, calls: Iterable[ToolCallTrace]) -> bool:
        """True when the recorded calls satisfy this contract's count bounds."""
        n = self.count_in(calls)
        if n < self.min_calls:
            return False
        return not (self.max_calls is not None and n > self.max_calls)


@dataclass(frozen=True)
class RunMetrics:
    """Normalized, exportable per-run metrics (rf-mcp ``ScenarioResult`` superset).

    All fields come from the recorded ``AgentRunResult`` / ``ToolCallTrace``
    records. ``tool_hit_rate`` is ``expected_met / expected_total`` (0.0 when the
    contract is empty). ``errors`` collects the non-``None`` ``error`` strings of
    the recorded tool calls.
    """

    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    total_tool_calls: int = 0
    tool_hit_rate: float = 0.0
    expected_met: int = 0
    expected_total: int = 0
    errors: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=0, output_tokens=0))
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", list(self.tool_calls))
        object.__setattr__(self, "errors", list(self.errors))

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serializable view of the record for the export keyword."""
        return {
            "tool_calls": [_trace_to_dict(call) for call in self.tool_calls],
            "total_tool_calls": self.total_tool_calls,
            "tool_hit_rate": self.tool_hit_rate,
            "expected_met": self.expected_met,
            "expected_total": self.expected_total,
            "errors": list(self.errors),
            "execution_time_seconds": self.execution_time_seconds,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "cached_input_tokens": self.usage.cached_input_tokens,
            },
            "cost_usd": self.cost_usd,
        }


def _trace_to_dict(call: ToolCallTrace) -> dict[str, Any]:
    """A JSON-serializable view of one recorded tool call."""
    return {
        "name": call.name,
        "args": dict(call.args),
        "result": call.result,
        "error": call.error,
        "latency_ms": call.latency_ms,
        "source": call.source,
        "tool_call_id": call.tool_call_id,
        "sequence_index": call.sequence_index,
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "cost_usd": call.cost_usd,
    }


def _coerce_expected(
    expected: ExpectedToolCall | Mapping[str, Any] | Iterable[ExpectedToolCall | Mapping[str, Any]] | None,
) -> list[ExpectedToolCall]:
    """Normalize the ``expected`` argument into a list of ``ExpectedToolCall``.

    Accepts ``None``, a single entry (``ExpectedToolCall`` or dict), or an
    iterable of entries. Dicts are coerced so ``.robot`` callers can pass plain
    ``&{...}`` / list-of-dict literals without importing the dataclass.
    """
    if expected is None:
        return []
    if isinstance(expected, ExpectedToolCall):
        return [expected]
    if isinstance(expected, Mapping):
        return [_dict_to_expected(expected)]
    result: list[ExpectedToolCall] = []
    for entry in expected:
        if isinstance(entry, ExpectedToolCall):
            result.append(entry)
        elif isinstance(entry, Mapping):
            result.append(_dict_to_expected(entry))
        else:
            raise TypeError(f"expected-tool entry must be an ExpectedToolCall or mapping; got {type(entry).__name__}")
    return result


def _dict_to_expected(entry: Mapping[str, Any]) -> ExpectedToolCall:
    """Build an ``ExpectedToolCall`` from a mapping, rejecting unknown keys."""
    allowed = {"tool", "min_calls", "max_calls", "required_args"}
    unknown = set(entry) - allowed
    if unknown:
        raise ValueError(f"unknown expected-tool keys: {sorted(unknown)}; allowed: {sorted(allowed)}")
    if "tool" not in entry:
        raise ValueError("expected-tool entry requires a 'tool' key")
    return ExpectedToolCall(
        tool=entry["tool"],
        min_calls=entry.get("min_calls", 1),
        max_calls=entry.get("max_calls"),
        required_args=entry.get("required_args"),
    )


def compute_run_metrics(
    run: AgentRunResult,
    expected: ExpectedToolCall | Mapping[str, Any] | Iterable[ExpectedToolCall | Mapping[str, Any]] | None = None,
) -> RunMetrics:
    """Project an ``AgentRunResult`` (+ optional expected contract) into ``RunMetrics``."""
    calls = list(run.tool_calls)
    entries = _coerce_expected(expected)
    met = sum(1 for entry in entries if entry.is_met_by(calls))
    total = len(entries)
    hit_rate = met / total if total else 0.0
    errors = [call.error for call in calls if call.error is not None]
    return RunMetrics(
        tool_calls=calls,
        total_tool_calls=len(calls),
        tool_hit_rate=hit_rate,
        expected_met=met,
        expected_total=total,
        errors=errors,
        execution_time_seconds=run.latency_seconds,
        usage=run.usage,
        cost_usd=run.cost_usd,
    )
