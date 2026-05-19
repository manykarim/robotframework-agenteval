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
            # Story 4.1 code-review Codex LOW-1 fix 2026-05-20: explicit
            # IndexError with diagnostic context. Pre-edit bare list-index
            # error had no scripted-count + no call-index. PRD L1087
            # positions MockProvider as the canonical reference Raj copies,
            # so diagnostic quality matters.
            if self._call_index >= len(self._responses):
                raise IndexError(
                    f"MockProvider scripted-mode exhausted: configured "
                    f"{len(self._responses)} responses, call #{self._call_index + 1} "
                    "overflows. Add more responses or use echo mode (responses=None)."
                )
            response = self._responses[self._call_index]
            self._call_index += 1
            return response
        # Echo mode: find last user-role text content.
        # Story 4.1 code-review Edge-cases M-2 fix 2026-05-20: pre-edit
        # silently returned `text=""` when the last user message had
        # list-content (multi-modal). Now explicitly raise so callers
        # know multi-modal echo is Phase-1 out-of-scope (DF-4.1-S3).
        # Empty echo for "no user message at all" stays silent (matches
        # test_mock_echo_returns_empty_when_no_user_messages).
        echoed_text = ""
        for msg in reversed(messages):
            if msg.role == "user":
                if isinstance(msg.content, str):
                    echoed_text = msg.content
                else:
                    # List-content user message — explicitly NotImplementedError.
                    raise NotImplementedError(
                        "MockProvider echo mode does not flatten multi-modal "
                        "list-content user messages in Phase-1 (DF-4.1-S3 stub). "
                        "Use scripted mode (responses=[...]) for multi-modal cases."
                    )
                break
        return ChatResponse(
            text=echoed_text,
            tool_calls=[],
            usage=ProviderUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            raw={"mock": True},
        )


# Story 4.1 code-review 3-way HIGH (Blind H1 + Edge-cases H-1 + Codex MED-1
# 2026-05-20): the pre-edit `_check: LLMProviderAdapter = MockProvider(); del _check`
# pattern was DECORATIVE — Python doesn't enforce annotations at runtime, so
# attribute-name drift on MockProvider silently passes import. Replaced with
# explicit `assert isinstance(...)` which DOES exercise the
# `@runtime_checkable` Protocol attribute check at module load time. The
# assert catches attribute-presence drift (missing `chat`, `name`, `version`);
# signature drift (e.g., `chat(self)` no-arg) still escapes per Python's
# `@runtime_checkable` limitation — that's caught by mypy strict + the
# conformance test suite (Story 1b.5).
assert isinstance(MockProvider(), LLMProviderAdapter), (
    "MockProvider drifted from LLMProviderAdapter Protocol attribute set"
)
