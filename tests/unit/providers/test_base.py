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

"""Unit tests for `AgentEval.providers.base` — Protocol surface + supporting dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from AgentEval.providers.base import (
    ChatResponse,
    ContentBlock,
    LLMProviderAdapter,
    Message,
    ProviderUsage,
    Tool,
    ToolCallRequest,
)
from AgentEval.providers.mock import MockProvider


def test_llm_provider_adapter_is_runtime_checkable() -> None:
    """Per architecture L883: `LLMProviderAdapter` MUST be `@runtime_checkable`
    so `isinstance(provider, LLMProviderAdapter)` works at registration time.
    """
    assert isinstance(MockProvider(), LLMProviderAdapter)


def test_message_is_frozen_dataclass() -> None:
    msg = Message(role="user", content="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.role = "system"  # type: ignore[misc]


def test_message_content_list_is_defensively_copied() -> None:
    """M_R6 pattern: list-content is shallow-copied at construction."""
    blocks = [ContentBlock(type="text", data={"text": "hi"})]
    msg = Message(role="user", content=blocks)
    blocks.append(ContentBlock(type="text", data={"text": "MUTATED"}))
    # The Message's content list MUST NOT have grown.
    assert isinstance(msg.content, list)
    assert len(msg.content) == 1


def test_message_tool_calls_defensively_copied() -> None:
    tc_list = [ToolCallRequest(id="1", name="x", arguments={})]
    msg = Message(role="assistant", content="", tool_calls=tc_list)
    tc_list.append(ToolCallRequest(id="2", name="y", arguments={}))
    assert len(msg.tool_calls) == 1


def test_content_block_data_defensively_copied() -> None:
    src = {"text": "hi"}
    block = ContentBlock(type="text", data=src)
    src["text"] = "MUTATED"
    assert block.data == {"text": "hi"}


def test_tool_input_schema_top_level_defensively_copied() -> None:
    """M_R6 shallow-copy pattern: top-level dict shell is copied at construction.

    Nested-dict mutation is intentionally NOT blocked (frozen=True is shallow;
    documented in `MCPTool` docstring per Story 3.2 code-review 3-way MED).
    Test verifies the TOP-LEVEL contract: adding a new top-level key to the
    source after construction must not affect the Tool's input_schema.
    """
    schema = {"type": "object"}
    tool = Tool(name="search", description="search the web", input_schema=schema)
    schema["extra_top_level_key"] = "MUTATED"
    assert "extra_top_level_key" not in tool.input_schema


def test_tool_call_request_arguments_defensively_copied() -> None:
    args = {"q": "abc"}
    req = ToolCallRequest(id="1", name="search", arguments=args)
    args["q"] = "MUTATED"
    assert req.arguments == {"q": "abc"}


def test_chat_response_is_frozen_dataclass() -> None:
    resp = ChatResponse(text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.text = "x"  # type: ignore[misc]


def test_chat_response_defaults() -> None:
    resp = ChatResponse(text="hi")
    assert resp.tool_calls == []
    assert resp.cost_usd is None
    assert resp.raw is None
    assert resp.usage.input_tokens == 0
    assert resp.usage.output_tokens == 0


def test_provider_usage_fields() -> None:
    u = ProviderUsage(input_tokens=10, output_tokens=5, cached_input_tokens=3)
    assert u.input_tokens == 10
    assert u.output_tokens == 5
    assert u.cached_input_tokens == 3


def test_provider_usage_defaults_cached_input_to_zero() -> None:
    u = ProviderUsage(input_tokens=10, output_tokens=5)
    assert u.cached_input_tokens == 0


def test_protocol_has_name_property() -> None:
    """The Protocol declares `name` + `version` properties + `chat` method."""
    mp = MockProvider()
    assert mp.name == "mock"
    assert mp.version == "mock"
