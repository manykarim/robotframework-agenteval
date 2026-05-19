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

"""`LiteLLMAdapter` — `LLMProviderAdapter` backed by LiteLLM (Story 4.1 / PRD FR13a).

Wraps `litellm.completion(model=..., messages=[...])` to expose 140+
LiteLLM-supported providers through a single agenteval adapter shape.
LiteLLM itself supports sync + async; Phase-1 uses sync to keep the
wrapper thin (no `_run_async` bridge). Async via `_run_async` is
deferred to Phase-1.5.

Cost computation falls back to `None` when LiteLLM's
`completion_cost()` raises (some custom providers don't publish
pricing metadata). `GenericAdapter` (Story 4.1 sibling) coerces this
to `0.0` for the `AgentRunResult.cost_usd` float field.

References:
    - PRD FR13a (LiteLLM-backed Generic adapter)
    - LiteLLM docs: https://docs.litellm.ai/docs/completion
    - `pyproject.toml` `litellm>=1.50,<2.0` pin
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

import litellm

from AgentEval.providers.base import (
    ChatResponse,
    ContentBlock,
    LLMProviderAdapter,
    Message,
    ProviderUsage,
    Tool,
    ToolCallRequest,
)

__all__ = ["LiteLLMAdapter"]


class LiteLLMAdapter:
    """`LLMProviderAdapter` implementation routing through `litellm.completion()`.

    Phase-1 scope:
    - Sync `litellm.completion(...)` call (no async/_run_async bridge).
    - Maps `Message` → LiteLLM dict shape; `Tool` → OpenAI tool-use shape.
    - Extracts `text`, `tool_calls`, `usage`, `cost_usd` from the response.
    - `stream=True` raises `NotImplementedError` (DF-4.1-S3).
    """

    def __init__(self, default_model: str | None = None, **kwargs: Any) -> None:
        """Construct the LiteLLM adapter.

        Args:
            default_model: Optional default model string (e.g.,
                `"anthropic/claude-sonnet-4-6"`, `"openai/gpt-4o"`).
                Callers may override per-call via `chat(model=...)`.
            **kwargs: Forwarded to every `litellm.completion()` call
                (e.g., `api_base`, `api_key`, `temperature`).
        """
        self._default_model: str | None = default_model
        self._extra_kwargs: dict[str, Any] = dict(kwargs)

    @property
    def name(self) -> str:
        return "litellm"

    @property
    def version(self) -> str:
        try:
            return importlib.metadata.version("litellm")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        *,
        stream: bool = False,
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Send a conversation to LiteLLM + map the response back."""
        if stream:
            raise NotImplementedError(
                "LiteLLMAdapter does not support streaming in Phase-1 (DF-4.1-S3); "
                "set stream=False or wait for Phase-1.5 streaming surface"
            )

        resolved_model = model or self._default_model
        if resolved_model is None:
            raise ValueError(
                "LiteLLMAdapter.chat requires `model` either via constructor `default_model` "
                "or per-call `model=` kwarg; got None for both"
            )

        litellm_messages = [_message_to_litellm_dict(m) for m in messages]
        litellm_tools = [_tool_to_litellm_dict(t) for t in tools] if tools else None

        call_kwargs: dict[str, Any] = {**self._extra_kwargs, **kwargs}
        if litellm_tools is not None:
            call_kwargs["tools"] = litellm_tools

        response = litellm.completion(
            model=resolved_model,
            messages=litellm_messages,
            **call_kwargs,
        )

        return _map_response(response)


def _message_to_litellm_dict(msg: Message) -> dict[str, Any]:
    """Map an agenteval `Message` to LiteLLM's expected dict shape.

    LiteLLM follows the OpenAI Chat-Completion message shape:
    `{"role": ..., "content": ...}` with optional `tool_calls` /
    `tool_call_id` on assistant / tool roles.
    """
    out: dict[str, Any] = {"role": msg.role}
    if isinstance(msg.content, str):
        out["content"] = msg.content
    else:
        # Multi-modal content: LiteLLM accepts a list of content-part dicts.
        out["content"] = [_content_block_to_litellm_dict(b) for b in msg.content]
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id is not None:
        out["tool_call_id"] = msg.tool_call_id
    return out


def _content_block_to_litellm_dict(block: ContentBlock) -> dict[str, Any]:
    """Map an agenteval `ContentBlock` to LiteLLM's content-part dict."""
    # Phase-1 passthrough: assume the `data` dict already matches the
    # provider's expected shape (LiteLLM uses OpenAI's `{"type": "text",
    # "text": "..."}` shape, `{"type": "image_url", "image_url": {...}}`,
    # etc). The Tool descriptor's JSON Schema is the canonical contract
    # for validation; per-provider shape mapping lives downstream.
    return {"type": block.type, **block.data}


def _tool_to_litellm_dict(tool: Tool) -> dict[str, Any]:
    """Map an agenteval `Tool` to LiteLLM's OpenAI-style tool descriptor."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _map_response(response: Any) -> ChatResponse:
    """Map LiteLLM's `ModelResponse` to an agenteval `ChatResponse`.

    Handles both `litellm.utils.ModelResponse` instances + plain-dict
    responses (some LiteLLM custom providers return dicts).
    """
    choices = _safe_get(response, "choices") or []
    if not choices:
        return ChatResponse(text="", raw=response)
    first_choice = choices[0]
    message = _safe_get(first_choice, "message")

    text = _safe_get(message, "content") or ""
    if not isinstance(text, str):
        # Multi-content path — flatten to text-only Phase-1.
        text = ""

    tool_calls_raw = _safe_get(message, "tool_calls") or []
    tool_calls: list[ToolCallRequest] = []
    for tc in tool_calls_raw:
        tc_id = _safe_get(tc, "id") or ""
        function = _safe_get(tc, "function")
        name = _safe_get(function, "name") or ""
        arguments_raw = _safe_get(function, "arguments")
        arguments_dict = _parse_arguments(arguments_raw)
        tool_calls.append(ToolCallRequest(id=tc_id, name=name, arguments=arguments_dict))

    usage_raw = _safe_get(response, "usage")
    usage = ProviderUsage(
        input_tokens=int(_safe_get(usage_raw, "prompt_tokens") or 0),
        output_tokens=int(_safe_get(usage_raw, "completion_tokens") or 0),
        cached_input_tokens=int(_safe_get(usage_raw, "cached_input_tokens") or 0),
    )

    cost_usd = _safe_cost(response)

    return ChatResponse(
        text=text,
        tool_calls=tool_calls,
        usage=usage,
        cost_usd=cost_usd,
        raw=response,
    )


def _safe_get(obj: Any, key: str) -> Any:
    """Get `key` from `obj` via attribute access OR dict-key lookup; None on miss."""
    if obj is None:
        return None
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key)
    return None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Parse tool-call `arguments` which LiteLLM may return as a JSON-string OR dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            import json

            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _safe_cost(response: Any) -> float | None:
    """Compute cost via LiteLLM's `completion_cost()`; None on `NotFoundError`."""
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:  # noqa: BLE001 -- LiteLLM raises various NotFoundError variants for unknown models
        # The MED rationale: LiteLLM's `completion_cost()` raises
        # `litellm.exceptions.NotFoundError` for some custom providers
        # (e.g., local Ollama, vLLM without pricing metadata); using a
        # broad except here is intentional + matches the FR13a Phase-1
        # carve-out. Adapters that need stricter behavior can override
        # `_map_response` or filter on the specific LiteLLM exception
        # class downstream.
        return None
    return float(cost) if cost is not None else None


# Runtime self-check at module import: verify Protocol conformance.
_check: LLMProviderAdapter = LiteLLMAdapter()
del _check
