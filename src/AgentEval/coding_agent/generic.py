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

"""`GenericAdapter` — `InProcessAdapter` backed by `LLMProviderAdapter` (Story 4.1 / PRD FR13a).

The generic Phase-1 `CodingAgentAdapter` implementation: routes the
`run(prompt, ...)` call through a configurable provider (default
LiteLLM) and returns a normalized `AgentRunResult`.

Per ADR-003 L22-23 (direct method-override pattern; NO abstract hooks)
and PRD FR12 (single `run()` method).

Phase-1 carve-out (Story 4.1 DF-4.1-S2): `mcp_servers=` kwarg is
accepted on `run()` but a non-empty dict raises `NotImplementedError`
pointing at Story 4.3 (orchestration keywords) + Epic 5 (hosted-MCP
observer) where the actual integration lands. Phase-1 Generic adapter
exercises the LLMProvider surface only; MCP tool-call dispatch via
adapters is the next-story scope.

References:
    - PRD FR12 (single `run()` Protocol method)
    - PRD FR13a (Generic LiteLLM-backed adapter)
    - ADR-003 (InProcessAdapter base; direct override)
    - Story 1b.4 `coding_agent/base.py:InProcessAdapter` + `_default_version`
    - Story 1b.2 `_kernel/coverage.compute_mcp_coverage` (mcp_coverage field)
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from AgentEval.coding_agent.base import InProcessAdapter, _default_version
from AgentEval.providers.base import LLMProviderAdapter, Message
from AgentEval.providers.factory import get_provider
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

__all__ = ["GenericAdapter"]


class GenericAdapter(InProcessAdapter):
    """`InProcessAdapter` routing `run()` through a configurable `LLMProviderAdapter`.

    Phase-1 default: `provider="litellm"`, model selectable per-instance.
    Phase-1 carve-out: `mcp_servers=` is accepted but a non-empty dict
    raises `NotImplementedError` (DF-4.1-S2) — Story 4.3 lands the
    MCP-tool-surface integration.
    """

    def __init__(
        self,
        *,
        provider: str = "litellm",
        model: str | None = None,
        provider_instance: LLMProviderAdapter | None = None,
        **kwargs: Any,
    ) -> None:
        """Construct the Generic adapter.

        Args:
            provider: Provider name to resolve via the factory (default
                `"litellm"`). Ignored when `provider_instance` is set.
            model: Model string forwarded to the provider's `chat(model=...)`
                call (e.g., `"anthropic/claude-sonnet-4-6"`,
                `"openai/gpt-4o"`, `"ollama/llama3"`).
            provider_instance: Optional pre-constructed provider for
                testing / DI. When set, `provider` is ignored.
            **kwargs: Forwarded to `InProcessAdapter.__init__` (stored
                on `self._adapter_config`).
        """
        super().__init__(provider=provider, model=model, **kwargs)
        self._provider_name = provider
        self._model = model
        self._provider: LLMProviderAdapter = (
            provider_instance if provider_instance is not None else get_provider(provider)
        )

    @property
    def name(self) -> str:
        return "GenericAdapter"

    @property
    def version(self) -> str:
        return _default_version(type(self).__module__)

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Execute a single-shot prompt through the configured provider.

        Phase-1 scope:
        - `tools` is ignored — Phase-1 Generic adapter calls the
          provider WITHOUT advertising tools. Tool-call surface
          integration is Story 4.3 + Epic 5 scope (DF-4.1-S2).
        - `mcp_servers` non-empty raises `NotImplementedError` (DF-4.1-S2).
          Empty dict OR None is allowed (pass-through).
        - Remaining `**kwargs` forwarded to the provider's `chat()` call.

        Returns:
            `AgentRunResult` with the Story 1b.4 ratified frozen-dataclass
            shape: `response_text` from `ChatResponse.text`; `tool_calls=[]`
            (Phase-1 carve-out); `usage` mapped from `ChatResponse.usage`;
            `metadata` with `completeness="full"` + `mcp_coverage="none"`;
            `cost_usd` from `ChatResponse.cost_usd` coerced to float
            (`None` → `0.0`); `latency_seconds` from `time.monotonic()`
            delta; `trace_id` per-run `uuid4().hex`.

        Raises:
            NotImplementedError: when `mcp_servers` is non-empty
                (Phase-1 DF-4.1-S2).
        """
        if mcp_servers:
            raise NotImplementedError(
                "GenericAdapter.run does not integrate MCP tool surfaces in Phase-1 "
                "(DF-4.1-S2); Story 4.3 (orchestration keywords) + Epic 5 (hosted-MCP "
                "observer) land the MCP-tool-call dispatch + trace correlation. "
                "Use `mcp_servers=None` for Phase-1 single-shot prompts."
            )
        _ = tools  # Phase-1: Generic adapter doesn't advertise tools — see DF-4.1-S2.

        messages = [Message(role="user", content=prompt)]
        t0 = time.monotonic()
        response = self._provider.chat(messages=messages, model=self._model, **kwargs)
        latency_seconds = time.monotonic() - t0

        return AgentRunResult(
            response_text=response.text,
            tool_calls=[],
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cached_input_tokens=response.usage.cached_input_tokens,
            ),
            # Story 4.1 pre-create-story drift D-D-extension 2026-05-20:
            # epics.md L1329 said `mcp_coverage="none"` but Story 1b.4 +
            # ADR-016 §Decision L24-28 ratified the 3-value closed enum
            # (no "none"). PRD FR36b L1554 says mcp_coverage is REQUIRED
            # *conditional on `mcp_servers=` usage* — but AgentRunMetadata
            # makes it unconditionally required. For Phase-1 no-MCP runs,
            # the most-correct ratified value is "hosted_in_process"
            # (vacuously true: 0 MCP servers used, 0 of them were
            # external). DF-4.1-S4 tracks the FR36b-vs-AgentRunMetadata
            # required-vs-conditional drift for Phase-1.5 resolution.
            # Similarly `completeness="complete"` not pre-edit "full" —
            # Story 1b.4 ratified Literal is "complete"/"truncated"/"partial".
            metadata=AgentRunMetadata(
                completeness="complete",
                mcp_coverage="hosted_in_process",
            ),
            cost_usd=float(response.cost_usd) if response.cost_usd is not None else 0.0,
            latency_seconds=latency_seconds,
            trace_id=uuid.uuid4().hex,
        )
