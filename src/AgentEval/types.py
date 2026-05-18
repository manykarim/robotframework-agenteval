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

"""Top-level shared types for agenteval (architecture L853).

Cross-sub-library data flow goes through the trace store
(`_kernel/trace_store.py`) or via these shared types. Sub-libraries import
FROM this module ONLY; they NEVER define cross-cutting types in their own
sub-library `types.py`.

Story 1b.2 ships the 3 Phase-1 dataclasses needed by `trace_store.py`'s
projection accessors:

- `ToolCallTrace` per FR35 + architecture L975-985 OTel GenAI semconv mapping
- `Usage` per architecture L967 `gen_ai.usage.*` summing convention
- `RunManifest` per FR39 + architecture L669

Subsequent stories ADD types to this same module:

- Story 1b.4 (CodingAgentAdapter Protocol): `AgentRunResult`, `ToolCall`,
  `TokenUsage`, `Scenario`, `MCPServer`, `RawResponse`
- Story 1b.5 (Conformance harness): fixture-schema types
- Epic 3 (MCP lifecycle): `MCPHandle`, `MCPTool`
- Epic 4 (CodingAgent adapters): adapter-side projection types
- Epic 5 (OTel listener): trace-backend-specific serialization types

Phase-1 implementation decision (architecture deviation, ratified by Story
1b.2 create-story 2026-05-18):
    Architecture L853 wording says "Pydantic dataclasses". Story 1b.2 ships
    stdlib `@dataclass(frozen=True)` instead. Reasons: (1) Pydantic is NOT in
    the curated direct dependency set (Story 1a.1 baseline: `mcp /
    robotframework / anyio / litellm / opentelemetry-* / pyyaml /
    jsonschema`); adding it to direct deps requires explicit ratification.
    (2) Pydantic 2.x IS available transitively via the `mcp` SDK, but using
    it indirectly is brittle. (3) Stdlib dataclasses provide the same
    field-declaration syntax + `dataclasses.asdict()` for JSON serialization
    (sufficient for Phase-1 jsonl backend). The migration to Pydantic
    becomes load-bearing when Epic 5's OTLP serialization needs validation;
    tracked as a Phase-1.5 carry-over in `deferred-work.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

__all__ = [
    "ToolCallTrace",
    "Usage",
    "RunManifest",
]


@dataclass(frozen=True)
class ToolCallTrace:
    """Projection of an `execute_tool` OTel span into a typed record.

    Per FR35 + architecture L975-985 OTel GenAI semconv mapping (with the
    `agenteval.tool.*` namespacing extensions ratified by architecture amendment
    2026-05-18 per Story 1b.2 code-review H_R11):
        - `name` ← `gen_ai.tool.name`
        - `gen_ai_tool_call_id` ← `gen_ai.tool.call.id`
        - `args` ← `agenteval.tool.args` (post-redaction; JSON-parsed at projection
          time per Story 1b.2 code-review H_R5)
        - `result` ← `agenteval.tool.result` (post-redaction; None on error)
        - `error` ← `agenteval.tool.error` (None on success)
        - `latency_ms` ← `agenteval.tool.duration_ms`
        - `source` ← `agenteval.tool.source` ("adapter" | "hosted_mcp"; missing
          source defaults to "adapter" with DegradedTraceWarning per Story 1b.2
          code-review H_R4)
        - `sequence_index` ← derived from chronological span ordering at
          projection time per PRD FR35 + FR45(d) conformance assertion
          ("sequence_index monotonic per agent run"). Added by Story 1b.2
          code-review H_R6 fix; was deleted by the pre-create-story drift check's
          first pass.

    Defensive immutability (Story 1b.2 code-review M_R6 fix): `__post_init__`
    wraps `args` in `MappingProxyType` so caller mutations to the source dict
    after construction don't leak through. Frozen=True only protects against
    attribute rebinding, NOT against mutating the contents of mapping fields.

    Frozen + immutable; serialize via `dataclasses.asdict()` for jsonl backend.
    """

    name: str
    args: Mapping[str, Any]
    result: Any | None
    error: str | None
    latency_ms: float
    source: Literal["adapter", "hosted_mcp"]
    gen_ai_tool_call_id: str
    sequence_index: int

    def __post_init__(self) -> None:
        # M_R6: defensively copy args so caller mutations to the source dict
        # after construction don't leak through. NOTE: we use `dict()` not
        # `MappingProxyType` because `dataclasses.asdict()` invokes
        # `copy.deepcopy` on field values, and `MappingProxyType` isn't
        # deepcopy-safe — using MappingProxyType breaks the jsonl-backend
        # serialization path. The defensive copy still blocks
        # source-mutation-leakage (the M_R6 hazard); the weaker direct
        # `tct.args["k"] = v` mutation is allowed (matches Python's
        # `frozen=True` semantics for mutable type fields).
        object.__setattr__(self, "args", dict(self.args))


@dataclass(frozen=True)
class Usage:
    """Token-usage summary across a run's `chat` spans.

    Per architecture L975 — sums `gen_ai.usage.*` attributes:
        - `input_tokens` ← `gen_ai.usage.input_tokens`
        - `output_tokens` ← `gen_ai.usage.output_tokens`
        - `cached_input_tokens` ← `gen_ai.usage.cached_input_tokens` (default 0
          for providers that don't emit it)

    All values MUST be non-negative integers (validated in `__post_init__` per
    Story 1b.2 code-review M_R11 fix). Negative values raise `ValueError` —
    they typically indicate an adapter bug (e.g., "unknown" sentinel encoded
    as -1) that should fail loud rather than silently propagate into cost
    computations.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0

    def __post_init__(self) -> None:
        # M_R11: non-negative validation per docstring contract.
        for name in ("input_tokens", "output_tokens", "cached_input_tokens"):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(
                    f"Usage.{name} must be non-negative; got {value!r} "
                    f"(adapter likely emitted a sentinel value — fix the adapter)"
                )


@dataclass(frozen=True)
class RunManifest:
    """Per-test run manifest assembled from trace store resource attributes (FR39).

    Per architecture L669: assembled from resource attributes + library version
    + redaction-policy hash. Provides a reproducibility record for each run.

    Fields:
        - `library_version`: pinned to `AgentEval.__version__`
        - `test_id` / `suite_id`: Listener v3 identifiers from `current_context()`
        - `redaction_policy_hash`: SHA-256 hex of the active pattern set; lets
          consumers verify the redaction policy in effect at run time
        - `started_at` / `ended_at`: min/max span timestamps for the run
        - `agenteval_tier_breakdown`: count of spans per `_agenteval_tier`
          value (e.g., `{1: 12, 2: 3, 3: 1}` for a run that exercised 12
          Tier-1, 3 Tier-2, and 1 Tier-3 keywords)

    Frozen + immutable; serialize via `dataclasses.asdict()`.
    """

    library_version: str
    test_id: str
    suite_id: str
    redaction_policy_hash: str
    started_at: datetime
    ended_at: datetime
    agenteval_tier_breakdown: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6: defensively copy agenteval_tier_breakdown so caller mutations
        # to the source dict don't leak (same rationale as ToolCallTrace.args).
        object.__setattr__(
            self,
            "agenteval_tier_breakdown",
            dict(self.agenteval_tier_breakdown),
        )
