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

"""Unit tests for `AgentEval.providers.litellm_adapter.LiteLLMAdapter`.

Strategy: AVOID live network calls. We monkeypatch `litellm.completion`
to return a fixture response object that has the expected shape (per
LiteLLM's `ModelResponse` type). The integration with real LiteLLM
providers is exercised by Story 4.1's recorded-response fixtures, which
this test file consumes via monkeypatch.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval.providers.base import (
    ChatResponse,
    LLMProviderAdapter,
    Message,
    Tool,
)
from AgentEval.providers.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def captured_completion_call(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Monkeypatches `litellm.completion` to capture args + return a fixture response."""
    captured: dict[str, Any] = {}

    def _fake_completion(**kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        return _build_fixture_response(text="echo-back")

    import litellm

    monkeypatch.setattr(litellm, "completion", _fake_completion)
    monkeypatch.setattr(litellm, "completion_cost", lambda completion_response: 0.0042)
    return captured


def _build_fixture_response(*, text: str = "hi", with_tool_calls: bool = False) -> Any:
    """Build a minimal `ModelResponse`-shaped fixture using SimpleNamespace."""
    tool_calls = None
    if with_tool_calls:
        tool_calls = [
            SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(
                    name="search",
                    arguments='{"q": "abc"}',
                ),
            )
        ]
    message = SimpleNamespace(content=text, tool_calls=tool_calls)
    choices = [SimpleNamespace(message=message)]
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=choices, usage=usage)


def test_litellm_adapter_protocol_conformance() -> None:
    assert isinstance(LiteLLMAdapter(), LLMProviderAdapter)


def test_litellm_adapter_name_is_litellm() -> None:
    assert LiteLLMAdapter().name == "litellm"


def test_litellm_adapter_version_resolves_via_metadata() -> None:
    """`version` property uses `importlib.metadata.version("litellm")`."""
    v = LiteLLMAdapter().version
    assert v != "unknown"
    # Version string starts with a digit (semver-like).
    assert v[0].isdigit()


def test_litellm_chat_calls_completion_with_messages(
    captured_completion_call: dict[str, Any],
) -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    resp = adapter.chat(messages=[Message(role="user", content="hi")])
    assert resp.text == "echo-back"
    assert captured_completion_call["kwargs"]["model"] == "openai/gpt-4o"
    assert captured_completion_call["kwargs"]["messages"] == [{"role": "user", "content": "hi"}]


def test_litellm_chat_per_call_model_overrides_default(
    captured_completion_call: dict[str, Any],
) -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    adapter.chat(messages=[Message(role="user", content="hi")], model="anthropic/claude-sonnet-4-6")
    assert captured_completion_call["kwargs"]["model"] == "anthropic/claude-sonnet-4-6"


def test_litellm_chat_no_model_raises_value_error() -> None:
    """No default + no per-call model raises before reaching the SDK."""
    adapter = LiteLLMAdapter()
    with pytest.raises(ValueError, match="model"):
        adapter.chat(messages=[Message(role="user", content="hi")])


def test_litellm_chat_stream_true_raises_not_implemented() -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    with pytest.raises(NotImplementedError, match="streaming"):
        adapter.chat(messages=[Message(role="user", content="x")], stream=True)


def test_litellm_chat_extracts_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import litellm

    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kwargs: _build_fixture_response(text="", with_tool_calls=True),
    )
    monkeypatch.setattr(litellm, "completion_cost", lambda completion_response: 0.0)
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    resp = adapter.chat(messages=[Message(role="user", content="search for abc")])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search"
    assert resp.tool_calls[0].arguments == {"q": "abc"}


def test_litellm_chat_cost_falls_back_to_none_on_notfound_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`completion_cost()` raises `litellm.exceptions.NotFoundError` → `cost_usd=None`.

    Story 4.1 code-review 2-way HIGH fix 2026-05-20 (Blind H3 + Edge-cases H-2 +
    `feedback_test_name_assertion_match`): pre-edit test claimed AC-4.1.3
    NotFoundError fallback but raised generic `RuntimeError`. Test passed only
    because `_safe_cost`'s `except Exception` was overbroad — tightening the
    except clause to the actual documented `NotFoundError` would have broken
    the test, proving the test name's "NotFoundError" claim was fake-green.
    Now narrows BOTH the production code (litellm_adapter.py:_safe_cost) AND
    the test to the actual documented exception class.
    """
    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: _build_fixture_response())

    def _raise(completion_response: Any) -> float:
        raise litellm.exceptions.NotFoundError(
            message="provider has no pricing metadata",
            model="custom/local-vllm",
            llm_provider="custom",
        )

    monkeypatch.setattr(litellm, "completion_cost", _raise)
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    resp = adapter.chat(messages=[Message(role="user", content="x")])
    assert resp.cost_usd is None


def test_litellm_chat_cost_propagates_unrelated_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 4.1 code-review 2-way HIGH fix 2026-05-20: `_safe_cost` MUST NOT
    swallow `ValueError`, `TypeError`, etc. — those are real LiteLLM bugs +
    must fail loud per M_R11. Narrowing the catch ensures unrelated exceptions
    propagate.
    """
    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: _build_fixture_response())

    def _raise(completion_response: Any) -> float:
        raise ValueError("real LiteLLM bug not a missing-pricing case")

    monkeypatch.setattr(litellm, "completion_cost", _raise)
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    with pytest.raises(ValueError, match="real LiteLLM bug"):
        adapter.chat(messages=[Message(role="user", content="x")])


def test_litellm_chat_maps_tools_to_openai_function_shape(
    captured_completion_call: dict[str, Any],
) -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    tool = Tool(name="search", description="search the web", input_schema={"type": "object"})
    adapter.chat(messages=[Message(role="user", content="hi")], tools=[tool])
    assert captured_completion_call["kwargs"]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "search the web",
                "parameters": {"type": "object"},
            },
        }
    ]


def test_litellm_chat_extracts_usage_from_response(
    captured_completion_call: dict[str, Any],
) -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    resp = adapter.chat(messages=[Message(role="user", content="hi")])
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5


def test_litellm_chat_returns_chat_response_shape(
    captured_completion_call: dict[str, Any],
) -> None:
    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    resp = adapter.chat(messages=[Message(role="user", content="hi")])
    assert isinstance(resp, ChatResponse)
    assert resp.cost_usd == 0.0042


def test_message_to_litellm_dict_emits_tool_calls_arguments_as_json_string(
    captured_completion_call: dict[str, Any],
) -> None:
    """Story 4.1 code-review Blind HIGH-2 fix 2026-05-20: OpenAI / LiteLLM
    spec REQUIRES `messages[].tool_calls[].function.arguments` to be a
    JSON-encoded STRING, not a Python dict. Pre-edit emitted dict, which
    breaks multi-turn tool-use round-trips against real providers.
    """
    from AgentEval.providers.base import ToolCallRequest

    adapter = LiteLLMAdapter(default_model="openai/gpt-4o")
    adapter.chat(
        messages=[
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCallRequest(id="1", name="search", arguments={"q": "abc", "limit": 5})],
            ),
        ]
    )
    forwarded = captured_completion_call["kwargs"]["messages"][0]
    tc = forwarded["tool_calls"][0]
    # The arguments field MUST be a JSON STRING, not a dict.
    assert isinstance(tc["function"]["arguments"], str)
    # The JSON string MUST round-trip back to the original dict.
    import json

    assert json.loads(tc["function"]["arguments"]) == {"q": "abc", "limit": 5}


def test_parse_arguments_surfaces_malformed_json_via_sentinel() -> None:
    """Story 4.1 code-review 2-way HIGH (Edge-cases H-3 + Codex MED-2 + Blind M2)
    fix 2026-05-20: pre-edit `_parse_arguments` silently returned `{}` on
    malformed JSON / non-object inputs. Now stashes a `_parse_error` sentinel
    key so downstream tool-dispatch code can detect + react.
    """
    from AgentEval.providers.litellm_adapter import _parse_arguments

    # Malformed JSON.
    bad = _parse_arguments('{"q": "abc"')
    assert "_parse_error" in bad
    assert "malformed JSON" in bad["_parse_error"]
    assert bad["_raw"] == '{"q": "abc"'

    # Non-object JSON (null, list, scalar).
    null_args = _parse_arguments("null")
    assert "_parse_error" in null_args
    assert "expected JSON object" in null_args["_parse_error"]

    list_args = _parse_arguments("[1, 2, 3]")
    assert "_parse_error" in list_args

    # Valid JSON object still passes cleanly (no sentinel).
    clean = _parse_arguments('{"q": "abc"}')
    assert "_parse_error" not in clean
    assert clean == {"q": "abc"}


def test_safe_cost_propagates_unrelated_exceptions_loudly() -> None:
    """Story 4.1 code-review 2-way HIGH (Blind H3 + Edge-cases H-2) fix
    2026-05-20: `_safe_cost` narrows from `except Exception` to
    `except (litellm.exceptions.NotFoundError, KeyError)`. Direct unit test.
    """
    import litellm

    from AgentEval.providers.litellm_adapter import _safe_cost

    # Build a fake completion response that triggers a TypeError inside the
    # cost computation via monkeypatching the litellm function.
    original = litellm.completion_cost
    try:
        litellm.completion_cost = lambda completion_response: (_ for _ in ()).throw(  # noqa: B023
            TypeError("real bug not a missing-pricing case")
        )
        with pytest.raises(TypeError, match="real bug"):
            _safe_cost(object())
    finally:
        litellm.completion_cost = original
