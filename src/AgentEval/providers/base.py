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

"""`LLMProviderAdapter` Protocol + supporting public types (PRD FR17c + architecture L883/L890).

Story 4.1 (Epic 4) — the public Protocol surface for pluggable LLM
provider integrations. Per architecture L890 the Protocol exposes a single
method `chat(messages, tools, *, stream=False, model=None, **kwargs) ->
ChatResponse`; per PRD FR17c contributors register custom providers via
`[project.entry-points."agenteval.providers"]` in their pyproject.toml.

Story 4.1 pre-create-story drift D-A 2026-05-20 ratification:
pre-edit epics.md L1325 declared `complete(prompt, model, **kwargs) ->
ProviderResponse` — architecture L890 is the authoritative shape, AND
LiteLLM's actual API (`litellm.completion(model=..., messages=[...])`)
maps onto `chat(messages, tools)` cleanly. The `stream` kwarg-only
parameter is added for forward-compatibility per PRD L1087's reference
to "the Protocol's stream arg + the Mock adapter's stream test as a
template" — Phase-1 providers raise `NotImplementedError` on
`stream=True` (DF-4.1-S3 stub).

Phase-1 limitations:
- `ChatResponse.raw: Any` is the provider-specific opaque payload escape
  hatch. Consumers SHOULD NOT pattern-match on `raw` shape — that path is
  reserved for adapter implementers needing to surface provider-specific
  metadata.
- `cost_usd: float | None` — None when the provider doesn't publish
  pricing metadata (LiteLLM's `completion_cost()` raises
  `litellm.exceptions.NotFoundError` for some custom providers).

References:
    - PRD FR17c (`agenteval.providers` entry-points group)
    - PRD L1087 (Raj narrative — `stream` arg + Mock-as-template)
    - Architecture L883 (`@runtime_checkable` Protocol convention)
    - Architecture L890 (`chat(messages, tools)` shape)
    - Story 1b.3 `_kernel/discovery.py:_GROUP_PROVIDERS = "agenteval.providers"`
    - Story 1b.4 `coding_agent/base.py:_default_version` (version-resolution helper)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

__all__ = [
    "LLMProviderAdapter",
    "Message",
    "Tool",
    "ChatResponse",
    "ContentBlock",
    "ToolCallRequest",
    "ProviderUsage",
]


@dataclass(frozen=True)
class ContentBlock:
    """One content block within a multi-modal `Message.content` list.

    Mirrors the MCP spec's content-block shape (`type` + type-specific
    keys) so providers + MCP can share the structure. Phase-1 ships
    plain dicts in the `data` field for forward-compat; typed variants
    deferred to Phase-1.5.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Story 1b.2 M_R6 shallow-copy pattern: protect against caller
        # mutating the source dict after construction.
        object.__setattr__(self, "data", dict(self.data))


@dataclass(frozen=True)
class ToolCallRequest:
    """A single tool-call request emitted by an LLM.

    Distinct from `ToolCallTrace` (in `AgentEval.types`) which captures
    the EXECUTED tool call across the full request→response lifecycle.
    `ToolCallRequest` is the LLM's request side only — what the model
    asked for. The adapter MAY translate this into a `ToolCallTrace`
    after dispatching + collecting the response.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True)
class Message:
    """One message in a `chat()` conversation (provider-agnostic).

    `content` accepts either a plain string (single text block) or a
    list of `ContentBlock` instances for multi-modal messages. The
    `tool_calls` field is populated only on `role="assistant"` messages
    that emitted tool-use requests.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_call_id: str | None = None  # set on role="tool" messages tying back to a prior request

    def __post_init__(self) -> None:
        # Defensive copies for list fields (M_R6 pattern).
        object.__setattr__(self, "tool_calls", list(self.tool_calls))
        if isinstance(self.content, list):
            object.__setattr__(self, "content", list(self.content))


@dataclass(frozen=True)
class Tool:
    """A tool descriptor passed to `chat(tools=...)` to advertise tool-use.

    Mirrors MCP's tool shape so the same descriptors round-trip from
    `MCP.List Tools` (Story 3.2) → `chat()` Tool list.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", dict(self.input_schema))


@dataclass(frozen=True)
class ProviderUsage:
    """Provider-reported token-usage summary for a single `chat()` call.

    Distinct from `AgentEval.types.Usage` which aggregates across a
    full run's spans. `ProviderUsage` is per-call; `Usage` is per-run.
    The Generic adapter sums per-call `ProviderUsage` into a run-level
    `Usage` when the run is a single-shot prompt.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


@dataclass(frozen=True)
class ChatResponse:
    """Result of a single `LLMProviderAdapter.chat()` invocation.

    Fields:
        - `text`: the assistant's response text (joined across content
          blocks if the provider emits multiple text blocks).
        - `tool_calls`: list of `ToolCallRequest` records the model
          asked for. Empty on plain-text responses.
        - `usage`: per-call `ProviderUsage` token counts.
        - `cost_usd`: per-call cost in USD as reported by the provider
          (e.g., LiteLLM's `completion_cost()`). `None` when the
          provider doesn't publish pricing metadata.
        - `raw`: opaque provider-specific payload escape hatch.
          Consumers SHOULD NOT pattern-match on `raw`; reserved for
          adapter implementers needing to surface provider-specific
          metadata to downstream code.
    """

    text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: ProviderUsage = field(default_factory=lambda: ProviderUsage(input_tokens=0, output_tokens=0))
    cost_usd: float | None = None
    raw: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", list(self.tool_calls))
        # Story 4.1 code-review Edge-cases L-3 fix 2026-05-20: a buggy
        # provider returning negative / NaN / Inf cost propagates into
        # `AgentRunResult.cost_usd`, silently bypassing downstream
        # cost-budget assertions (`assert result.cost_usd < 0.10` passes
        # on `-5.00`). Validate at construction per M_R11 fail-loud.
        if self.cost_usd is not None:
            import math

            if math.isnan(self.cost_usd) or math.isinf(self.cost_usd) or self.cost_usd < 0:
                raise ValueError(
                    f"ChatResponse.cost_usd must be non-negative finite OR None; "
                    f"got {self.cost_usd!r} (adapter likely emitted a sentinel "
                    "or provider bug — fix the adapter)"
                )


@runtime_checkable
class LLMProviderAdapter(Protocol):
    """Public Protocol for pluggable LLM provider integrations (PRD FR17c).

    Per architecture L883 the Protocol is decorated `@runtime_checkable`
    so `isinstance(provider, LLMProviderAdapter)` works at registration
    time. Phase-1 ships 2 implementations: `LiteLLMAdapter`
    (140+ providers via LiteLLM) + `MockProvider` (deterministic stub
    for unit tests).

    **`@runtime_checkable` limitation (Story 4.1 code-review Codex LOW-2
    2026-05-20):** `isinstance(provider, LLMProviderAdapter)` validates
    attribute *names* only — `chat()` SIGNATURE drift (e.g., a class
    with `def chat(self)` no-arg shape) silently passes the Protocol
    check. The conformance test suite (Story 1b.5) + `mypy --strict`
    are the load-bearing safety nets for signature conformance.

    Single method `chat()` per architecture L890. The `stream` keyword-
    only parameter is reserved per PRD L1087's narrative; Phase-1
    providers raise `NotImplementedError` on `stream=True` (DF-4.1-S3
    stub). The `model` keyword-only parameter overrides any model
    configured at adapter construction time — Phase-1 consumers may
    leave it `None` to use the adapter's default.
    """

    @property
    def name(self) -> str:
        """Adapter identity (e.g., `"litellm"`, `"mock"`)."""
        ...

    @property
    def version(self) -> str:
        """Installed-distribution version of the underlying provider.

        Conventions: LiteLLM adapter returns `litellm.__version__`; Mock
        adapter returns `"mock"`. Adapters using a custom resolver
        SHOULD route through `coding_agent.base._default_version` for
        consistency with the coding-agent surface (Story 1b.4 D5 ratification).
        """
        ...

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        *,
        stream: bool = False,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Send a conversation + optional tool descriptors to the provider; return the response.

        Args:
            messages: Ordered conversation history (system/user/assistant/tool roles).
            tools: Optional tool descriptors the model may call. `None`
                or empty list = no tools advertised.
            stream: Phase-1 stub-only — must be False; True raises
                `NotImplementedError` (DF-4.1-S3).
            model: Override the adapter's configured default model.
                `None` = use adapter's default.
            **kwargs: Provider-specific forward-compat kwargs (passed
                through to the underlying SDK call).

        Returns:
            `ChatResponse` with text, optional tool-call requests,
            usage, optional cost.
        """
        ...
