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

"""`MockProvider` — deterministic `LLMProviderAdapter` for unit tests (Story 4.1).

Two construction modes:

1. **Echo mode** (no `responses` argument): every `chat()` call returns
   a `ChatResponse(text=<last user message text>)`. Useful when callers
   want byte-stable conversations without scripting per-call shapes.

2. **Scripted mode** (`responses=[ChatResponse(...), ...]`): each
   `chat()` call consumes one response from the list in order. Raises
   `IndexError` when exhausted — surfaces test-script-vs-actual-call
   mismatches loudly per the Story 1b.2 M_R11 "fail loud" principle.

This adapter is the **canonical reference implementation** Raj copies
when writing a custom provider per PRD L1087's narrative ("notices the
Protocol's stream arg + the Mock adapter's stream test as a template").
"""

from __future__ import annotations

from typing import Any

from AgentEval.providers.base import (
    ChatResponse,
    LLMProviderAdapter,
    Message,
    ProviderUsage,
    Tool,
)

__all__ = ["MockProvider"]


class MockProvider:
    """Deterministic stub `LLMProviderAdapter` for unit tests.

    Implements the `LLMProviderAdapter` Protocol via structural
    duck-typing (no inheritance needed — `runtime_checkable` Protocol).
    """

    def __init__(self, responses: list[ChatResponse] | None = None) -> None:
        """Construct the Mock provider.

        Args:
            responses: Optional list of pre-scripted `ChatResponse`
                instances. When `None`, echo mode is used (each call
                returns the last user message text). When provided,
                each `chat()` call consumes one response in order.
        """
        # M_R6 pattern: defensive copy of the scripted-responses list.
        self._responses: list[ChatResponse] | None = list(responses) if responses is not None else None
        self._call_index: int = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def version(self) -> str:
        return "mock"

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        *,
        stream: bool = False,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Return a deterministic `ChatResponse`.

        Echo mode: extracts the last user-role message's text and
        returns it. Multi-modal content blocks are not echoed (Phase-1
        carve-out — only string-content messages echo).

        Scripted mode: consumes the next response from `self._responses`.

        Raises:
            NotImplementedError: when `stream=True` (DF-4.1-S3 Phase-1 stub).
            IndexError: scripted mode exhausted.
        """
        if stream:
            raise NotImplementedError(
                "MockProvider does not support streaming in Phase-1 (DF-4.1-S3); "
                "set stream=False or use a streaming-capable provider"
            )
        if self._responses is not None:
            # Scripted mode — IndexError naturally surfaces if exhausted.
            response = self._responses[self._call_index]
            self._call_index += 1
            return response
        # Echo mode: find last user-role text content.
        echoed_text = ""
        for msg in reversed(messages):
            if msg.role == "user" and isinstance(msg.content, str):
                echoed_text = msg.content
                break
        return ChatResponse(
            text=echoed_text,
            tool_calls=[],
            usage=ProviderUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            raw={"mock": True},
        )


# Runtime self-check: at module import time, verify the structural
# Protocol conformance via @runtime_checkable. This is a Phase-1
# safety net catching shape drift between MockProvider + Protocol.
_check: LLMProviderAdapter = MockProvider()
del _check
