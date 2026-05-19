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

"""Unit tests for `AgentEval.providers.mock.MockProvider`."""

from __future__ import annotations

import pytest

from AgentEval.providers.base import ChatResponse, Message, ProviderUsage, ToolCallRequest
from AgentEval.providers.mock import MockProvider


def test_mock_echo_mode_returns_last_user_text() -> None:
    mp = MockProvider()
    resp = mp.chat(messages=[Message(role="user", content="hello world")])
    assert resp.text == "hello world"
    assert resp.tool_calls == []
    assert resp.usage.input_tokens == 0


def test_mock_echo_mode_skips_system_messages() -> None:
    mp = MockProvider()
    resp = mp.chat(
        messages=[
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ]
    )
    assert resp.text == "hi"


def test_mock_echo_returns_empty_when_no_user_messages() -> None:
    mp = MockProvider()
    resp = mp.chat(messages=[Message(role="system", content="be terse")])
    assert resp.text == ""


def test_mock_scripted_mode_consumes_responses_in_order() -> None:
    scripted = [
        ChatResponse(text="first"),
        ChatResponse(text="second"),
        ChatResponse(text="third"),
    ]
    mp = MockProvider(responses=scripted)
    assert mp.chat(messages=[Message(role="user", content="ignored")]).text == "first"
    assert mp.chat(messages=[Message(role="user", content="ignored")]).text == "second"
    assert mp.chat(messages=[Message(role="user", content="ignored")]).text == "third"


def test_mock_scripted_mode_raises_index_error_on_overflow() -> None:
    """Scripted mode exhaustion raises IndexError per Story 1b.2 M_R11 'fail loud'."""
    mp = MockProvider(responses=[ChatResponse(text="only")])
    mp.chat(messages=[Message(role="user", content="x")])
    with pytest.raises(IndexError):
        mp.chat(messages=[Message(role="user", content="x")])


def test_mock_scripted_responses_defensively_copied() -> None:
    """Caller-side mutation of the responses list after construction must not affect playback."""
    scripted = [ChatResponse(text="first")]
    mp = MockProvider(responses=scripted)
    scripted[0] = ChatResponse(text="MUTATED")
    scripted.append(ChatResponse(text="extra"))
    assert mp.chat(messages=[Message(role="user", content="x")]).text == "first"
    with pytest.raises(IndexError):
        mp.chat(messages=[Message(role="user", content="x")])


def test_mock_chat_stream_true_raises_not_implemented() -> None:
    """DF-4.1-S3 Phase-1 stub: stream=True raises NotImplementedError."""
    mp = MockProvider()
    with pytest.raises(NotImplementedError, match="streaming"):
        mp.chat(messages=[Message(role="user", content="x")], stream=True)


def test_mock_returns_scripted_tool_calls() -> None:
    """Scripted responses can include tool_calls for tool-use scenarios."""
    scripted = [
        ChatResponse(
            text="",
            tool_calls=[ToolCallRequest(id="1", name="search", arguments={"q": "abc"})],
            usage=ProviderUsage(input_tokens=10, output_tokens=2),
        )
    ]
    mp = MockProvider(responses=scripted)
    resp = mp.chat(messages=[Message(role="user", content="x")])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search"
    assert resp.tool_calls[0].arguments == {"q": "abc"}


def test_mock_name_is_mock() -> None:
    assert MockProvider().name == "mock"


def test_mock_version_is_mock() -> None:
    assert MockProvider().version == "mock"
