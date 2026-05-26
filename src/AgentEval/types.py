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

- Story 1b.4 (CodingAgentAdapter Protocol): `CodingAgentAdapter` Protocol +
  `AgentRunResult` + `AgentRunMetadata` dataclasses. Pre-edit Story 1b.4
  spec mentioned `ToolCall` / `TokenUsage` / `Scenario` / `MCPServer` /
  `RawResponse` forward-refs which were retired by the 8th-consecutive
  pre-create-story drift check (D3/D4/D6/D7 — Story 1b.4 reuses existing
  `ToolCallTrace` + `Usage` types and drops the other 3 undefined types
  per architecture L853 import-discipline + ADR-003 + FR12 single-method
  Protocol).
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
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from AgentEval._kernel.context import ServerHandle  # forward ref; consumed by CodingAgentAdapter.run

__all__ = [
    "ToolCallTrace",
    "Usage",
    "RunManifest",
    "AgentRunMetadata",
    "AgentRunResult",
    "CodingAgentAdapter",
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
        - `reasoning_output_tokens` ← `gen_ai.usage.reasoning_output_tokens`
          (default 0 for providers that don't emit it; added Story 11.1
          code-review kilo HIGH-1 2026-05-26 — Codex emits this verbatim
          in ``turn.completed.usage`` and silently dropping it was a
          data-loss bug. Downstream cost-catalog integration (DF-11.1-S2 /
          C74) needs this field; per OTel GenAI semconv the canonical
          attribute name is ``gen_ai.usage.reasoning_tokens`` — we keep
          ``reasoning_output_tokens`` matching the Codex JSONL key + add
          the semconv mapping in the next listener pass)

    All values MUST be non-negative integers (validated in `__post_init__` per
    Story 1b.2 code-review M_R11 fix). Negative values raise `ValueError` —
    they typically indicate an adapter bug (e.g., "unknown" sentinel encoded
    as -1) that should fail loud rather than silently propagate into cost
    computations.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    reasoning_output_tokens: int = 0

    def __post_init__(self) -> None:
        # M_R11: non-negative validation per docstring contract.
        for name in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens"):
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

    Story 5.3 expansion (per spec D-2 drift fix 2026-05-20): the original 7
    fields (per architecture L896) are preserved verbatim as required fields;
    new operational fields per epics.md L1502 + PRD FR39 are added with
    ``Optional[...] = None`` defaults so the existing projection accessor at
    ``_kernel/trace_store.get_run_manifest()`` keeps building backward-compat
    manifests. Story 5.3's ``RunManifestEmitter`` populates the new fields
    via the Listener's ``record_run_metadata`` API.

    Fields (existing 7 — required):
        - `library_version`: pinned to `AgentEval.__version__`
        - `test_id` / `suite_id`: Listener v3 identifiers from `current_context()`
        - `redaction_policy_hash`: SHA-256 hex of the active pattern set; lets
          consumers verify the redaction policy in effect at run time
        - `started_at` / `ended_at`: min/max span timestamps for the run
        - `agenteval_tier_breakdown`: count of spans per `_agenteval_tier`

    New Story 5.3 fields (all Optional with safe defaults):
        - `adapter_name` / `adapter_version`: identifies the coding-agent
          adapter that drove the run (Story 4.1+4.2 surface)
        - `model`: model identifier passed to the provider (e.g., "claude-sonnet-4-6")
        - `mcp_servers`: list of `{name, transport, version_or_sha}` dicts —
          one entry per MCP server the run was configured with. Phase-1
          carve: `version_or_sha` is "<TBD Phase-1.5>" pending DF-5.3-S2.
        - `trace_backend`: which Story 5.1 backend ran (`"memory"` / `"jsonl"`)
        - `total_cost_usd`: sum of provider-reported cost across the run
        - `completeness` / `mcp_coverage`: AgentRunMetadata projection per FR36a/b
        - `warnings`: list[dict[str, Any]] — populated by Story 5.4's
          `DegradedTraceWarning` collector. Each entry is the 5-key
          `WarningRecord` shape (see `_kernel/warnings.WarningRecord`):
          `{warning_type: str, message: str, source: str, timestamp: str
          (RFC 3339), remediation: str | None}`. Story 5.3 placeholder
          was `list[str]`; the structured shape lands with the
          `Get Last Warnings` keyword surface.
        - `seed`: int | None — RNG seed for reproducibility (Phase-1 carve:
          populated only when caller explicitly seeded; defaults None)
        - `prompt_hashes`: list[str] — SHA-256 hex of each prompt the agent
          saw (Phase-1: hashes the user prompt only; multi-turn full sequence
          is DF-5.3-S3)

    Frozen + immutable; serialize via `dataclasses.asdict()`.
    """

    library_version: str
    test_id: str
    suite_id: str
    redaction_policy_hash: str
    started_at: datetime
    ended_at: datetime
    agenteval_tier_breakdown: Mapping[int, int] = field(default_factory=dict)
    # Story 5.3 expansion (D-2 drift fix 2026-05-20): operational fields per
    # epics.md L1502 + PRD FR39. All Optional with safe defaults so the
    # existing _kernel/trace_store.get_run_manifest() projection keeps
    # building backward-compatible manifests; new fields populated by
    # Story 5.3's RunManifestEmitter via Listener.record_run_metadata.
    adapter_name: str | None = None
    adapter_version: str | None = None
    model: str | None = None
    mcp_servers: list[dict[str, str]] = field(default_factory=list)
    trace_backend: str | None = None
    total_cost_usd: float | None = None
    completeness: str | None = None
    mcp_coverage: str | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    seed: int | None = None
    prompt_hashes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # M_R6: defensively copy mutable fields so caller mutations to the
        # source containers don't leak (same rationale as ToolCallTrace.args).
        object.__setattr__(
            self,
            "agenteval_tier_breakdown",
            dict(self.agenteval_tier_breakdown),
        )
        object.__setattr__(self, "mcp_servers", [dict(entry) for entry in self.mcp_servers])
        # Story 5.4 code-review 1-way Blind HIGH-D fix 2026-05-20: per
        # AC-5.4.10, the field type widened from list[str] (Story 5.3
        # placeholder) to list[dict[str, Any]] (5-key WarningRecord).
        # A stale fixture passing a raw `str` would crash `dict(entry)`
        # with `ValueError: dictionary update sequence element #0 has
        # length 1; 2 is required`. Coerce stale strings into a single-
        # field dict so backward-compat consumers don't break — the
        # missing structured fields are filled defensively + the
        # construction does not raise. New emitters always pass dicts.
        _coerced_warnings: list[dict[str, Any]] = []
        for entry in self.warnings:
            # mypy thinks `isinstance(entry, str)` is unreachable per the
            # dataclass field annotation `list[dict[str, Any]]`, but the
            # runtime check is load-bearing for backward-compat with
            # Story 5.3's `list[str]` placeholder shape — callers that
            # never updated their fixtures still construct against the
            # dataclass via untyped JSON/dict ingest. The ignore comment
            # documents the deliberate runtime widening.
            if isinstance(entry, str):  # type: ignore[unreachable]
                _coerced_warnings.append(  # type: ignore[unreachable]
                    {
                        "warning_type": "AgentEval.errors.DegradedTraceWarning",
                        "message": entry,
                        "source": "<legacy-str-warning>",
                        "timestamp": "",
                        "remediation": None,
                    }
                )
            else:
                _coerced_warnings.append(dict(entry))
        object.__setattr__(self, "warnings", _coerced_warnings)
        object.__setattr__(self, "prompt_hashes", list(self.prompt_hashes))


# --------------------------------------------------------------------------- #
# Story 1b.4 — CodingAgentAdapter Protocol + AgentRunResult shape             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AgentRunMetadata:
    """Run-level metadata for an `AgentRunResult` (PRD FR36a + FR36b + ADR-006 + ADR-016).

    Per ADR-006 L15 + PRD FR36a L1553: `completeness` is REQUIRED + the
    `.metadata.completeness` nesting is REQUIRED (NOT a flat top-level field
    on AgentRunResult).

    Per PRD FR36b L1554 + ADR-016 §Decision L24-28: `mcp_coverage` is
    REQUIRED + the 3-state value space `("hosted_in_process",
    "subprocess_with_observer", "external_mixed")` is closed (NO `"none"`
    value — pre-edit drafts had a 4-state version which the ratified ADR-016
    explicitly excludes).

    Runtime Literal-value enforcement (Story 1b.4 code-review D7 ratification):
    Python `Literal` types are TYPE-CHECK-only — `mypy` catches violations at
    type-check time but the runtime constructor accepts any string. Story
    1b.4's `__post_init__` adds a closed-set check that raises `ValueError`
    on invalid inputs so jsonl-replay paths + adapter-side construction get
    the same guarantee mypy provides. Removed-spec-text caveat: pre-edit
    AC-1b.4.6 wording "Defensive `dict()` copy in `__post_init__` per Story
    1b.2's M_R6 fix pattern" was stale (the dataclass has only Literal
    string fields, nothing dict-shaped to defensively copy); the actual
    `__post_init__` purpose ratified at Story 1b.4 code review is the
    runtime closed-set validation.

    Frozen + immutable; serializes cleanly via `dataclasses.asdict()`.
    """

    completeness: Literal["complete", "truncated", "partial"]
    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]

    _VALID_COMPLETENESS: ClassVar[frozenset[str]] = frozenset(("complete", "truncated", "partial"))
    _VALID_MCP_COVERAGE: ClassVar[frozenset[str]] = frozenset(
        ("hosted_in_process", "subprocess_with_observer", "external_mixed")
    )

    def __post_init__(self) -> None:
        if self.completeness not in self._VALID_COMPLETENESS:
            raise ValueError(
                f"AgentRunMetadata.completeness must be one of "
                f"{sorted(self._VALID_COMPLETENESS)}; got {self.completeness!r}"
            )
        if self.mcp_coverage not in self._VALID_MCP_COVERAGE:
            raise ValueError(
                f"AgentRunMetadata.mcp_coverage must be one of "
                f"{sorted(self._VALID_MCP_COVERAGE)}; got {self.mcp_coverage!r}"
            )


@dataclass(frozen=True)
class AgentRunResult:
    """Normalized result of a single coding-agent run (PRD FR12 + ADR-003 + ADR-006).

    Produced by every `CodingAgentAdapter.run()` invocation. Sub-libraries
    (`metrics/`, `_assertions/`, the OTel Listener) consume this shape per
    architecture L853's "Cross-sub-library data flow goes through ... shared
    types in `agenteval/types.py`" rule.

    Fields (per AC-1b.4.5 + architecture L885-889):
        - `response_text`: primary text output from the agent
        - `tool_calls`: list of `ToolCallTrace` (Story 1b.2 type; NOT a new
          `ToolCall` type — Story 1b.4 code-review drift D3 resolution)
        - `usage`: `Usage` token-usage record (Story 1b.2 type; NOT a new
          `TokenUsage` alias — Story 1b.4 drift D4 resolution)
        - `metadata`: `AgentRunMetadata` sub-dataclass holding nested
          `.metadata.completeness` + `.metadata.mcp_coverage` per ADR-006 L15
          + FR36a/b L1553-1554 (REQUIRED nesting; D2/D15 drift resolution)
        - `cost_usd`: total USD cost reported by the provider; 0.0 for the
          Phase-1 stub cost-source path
        - `latency_seconds`: wall-clock duration of the `run()` call
        - `trace_id`: opaque string linking to the trace artifact at
          `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` per FR51 L1579.
          **Phase-1 contract: unconstrained `str`** (no UUID/hex shape
          enforced at construction; Story 1b.4 code review D7 ratification
          downgraded the pre-edit "UUID hex string" claim because the
          Phase-1 jsonl backend accepts any opaque identifier and Phase-2
          OTLP migration may switch to OTel 32-char hex anyway — adding a
          UUID validator now would force a major-version bump at the
          OTLP-migration time). Concrete adapters SHOULD use
          `uuid.uuid4().hex` or the trace producer's session id; Story 4.1+
          may add a contributor-side validator if needed.

    Defensive list copy on `tool_calls` in `__post_init__` (Story 1b.2 M_R6
    pattern); blocks source-mutation leakage while preserving
    `dataclasses.asdict()` round-tripping.

    Frozen + immutable; serializes cleanly via `dataclasses.asdict()` for the
    jsonl Trace backend.
    """

    response_text: str
    tool_calls: list[ToolCallTrace]
    usage: Usage
    metadata: AgentRunMetadata
    cost_usd: float
    latency_seconds: float
    trace_id: str

    def __post_init__(self) -> None:
        # Defensive copy of tool_calls list per Story 1b.2 M_R6 pattern.
        # Inner ToolCallTrace items are already frozen dataclasses; the list
        # itself is the mutability surface we close here.
        object.__setattr__(self, "tool_calls", list(self.tool_calls))


@runtime_checkable
class CodingAgentAdapter(Protocol):
    """Contributor-facing Protocol for coding-agent adapters (PRD FR12 L1506 + ADR-003).

    SINGLE `run()` method per PRD FR12 (NOT a 2-method `send_prompt +
    run_scenario` split — the pre-edit Story 1b.4 spec had drifted; resolved
    by the 8th-consecutive pre-create-story drift check D1). Properties
    `name` + `version` expose adapter identity.

    Phase-1 import location ratification (Story 1b.4 D8 drift resolution):
    This Protocol lives at `src/AgentEval/types.py`, NOT at
    `src/AgentEval/coding_agent/base.py`. `coding_agent/base.py` re-exports
    it. The location decision is forced by architecture L853 cross-sub-
    library import discipline + Story 1b.3 `_kernel/discovery.py` L102
    TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter`
    (which would create a circular dep if the Protocol lived in a sub-library).

    Tier metadata note (D11 drift resolution): the Protocol does NOT carry a
    `_agenteval_tier` class attribute. Tier semantics apply to library KEYWORD
    methods (e.g., `Send Prompt`, `Run Scenario`) decorated with `@tier(3)`
    per Story 1b.1's `tier.py` + architecture L620, NOT to adapter classes.
    Adapters are runtime mechanisms; tier is a keyword-side property.

    MCP lifecycle note (D7 drift resolution): the adapter CONSUMES live
    `ServerHandle` instances via the `mcp_servers=` kwarg of `run()`.
    Adapters do NOT manage MCP server lifecycle — that's Story 1b.1's
    `MCPLifecycleManager` responsibility (per Story 0.2 spike findings:
    single canonical owner of acquire/release across the agent run).

    `@runtime_checkable` enables `isinstance(obj, CodingAgentAdapter)` for
    the FR17b composition path (`AgentEval.__init__(coding_agent=MyAdapter())`,
    wiring deferred to Story 4.1).

    Runtime check scope note (Story 1b.4 code-review D4 ratification):
    Python's `@runtime_checkable` Protocol ONLY verifies attribute /method
    presence at `isinstance` time — it does NOT verify signature shape
    (parameter names, types, defaults). A class with `run(self, prompt)`
    (no `tools`/`mcp_servers`/`**kwargs`) passes `isinstance(obj,
    CodingAgentAdapter) == True` even though it violates FR12's signature
    contract. Signature-shape conformance is the **Story 1b.5 conformance
    harness**'s responsibility — fixture-driven verification of every
    registered adapter against the FR12 signature + return-type +
    behavioral invariants. Until Story 1b.5 lands, callers should treat
    `isinstance` as a coarse-grained smoke check, NOT a typed contract.
    """

    name: str
    version: str

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, ServerHandle] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Execute a single agent run + return the normalized result.

        Args:
            prompt: Agent input prompt (single-turn semantics; multi-turn
                scenarios fold into this via Story 1b.5 fixture schemas).
            tools: Optional list of tool names the agent may use; None
                signals "adapter default tool set".
            mcp_servers: Optional dict of `{name: ServerHandle}` where each
                handle is the live MCP server connection owned by Story
                1b.1's `MCPLifecycleManager`.
            **kwargs: Adapter-specific extension parameters (e.g., a model
                override, temperature, tool-choice constraint).

        Returns:
            `AgentRunResult` with the 7 fields populated; the `metadata`
            sub-dataclass MUST carry both `completeness` + `mcp_coverage`
            per FR36a/b.
        """
        ...
