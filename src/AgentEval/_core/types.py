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

"""Shared frozen dataclasses the four surfaces pass around.

An agent run produces an ``AgentRunResult``; its tool calls project into
``ToolCallTrace`` records; token counts sum into ``Usage``. These are the only
cross-surface types - everything else lives in its own surface module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

__all__ = [
    "Usage",
    "ToolCallTrace",
    "AgentRunMetadata",
    "AgentRunResult",
]


@dataclass(frozen=True)
class Usage:
    """Token counts for a run. All values must be non-negative integers."""

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens", "cached_input_tokens"):
            value: int = getattr(self, name)
            if value < 0:
                raise ValueError(f"Usage.{name} must be non-negative; got {value!r}")


@dataclass(frozen=True)
class ToolCallTrace:
    """One tool call, projected from the trace so a Tier-1 test can assert on it.

    ``args`` is defensively copied so a caller mutating the source dict after
    construction can't change a recorded call.
    """

    name: str
    args: Mapping[str, Any]
    result: Any | None = None
    error: str | None = None
    latency_ms: float = 0.0
    source: Literal["adapter", "hosted_mcp"] = "adapter"
    tool_call_id: str = ""
    sequence_index: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", dict(self.args))


@dataclass(frozen=True)
class AgentRunMetadata:
    """Run-level honesty fields.

    ``completeness`` says whether the run finished cleanly; ``mcp_coverage``
    says how well we could observe any MCP tool use. Both are closed value sets
    validated at construction.
    """

    completeness: Literal["complete", "truncated", "partial"] = "complete"
    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"] = "hosted_in_process"

    _VALID_COMPLETENESS: ClassVar[frozenset[str]] = frozenset(("complete", "truncated", "partial"))
    _VALID_MCP_COVERAGE: ClassVar[frozenset[str]] = frozenset(
        ("hosted_in_process", "subprocess_with_observer", "external_mixed")
    )

    def __post_init__(self) -> None:
        if self.completeness not in self._VALID_COMPLETENESS:
            raise ValueError(
                f"completeness must be one of {sorted(self._VALID_COMPLETENESS)}; got {self.completeness!r}"
            )
        if self.mcp_coverage not in self._VALID_MCP_COVERAGE:
            raise ValueError(
                f"mcp_coverage must be one of {sorted(self._VALID_MCP_COVERAGE)}; got {self.mcp_coverage!r}"
            )


@dataclass(frozen=True)
class AgentRunResult:
    """The normalized result of one agent run - what every adapter returns."""

    response_text: str
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=0, output_tokens=0))
    metadata: AgentRunMetadata = field(default_factory=AgentRunMetadata)
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    trace_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", list(self.tool_calls))
