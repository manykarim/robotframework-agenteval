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

"""Tests for the adapter seam, missing-extra gating, and the async bridge."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from AgentEval._core.adapter import (
    Adapter,
    GenericAdapter,
    get_adapter,
    resolve_config,
    run_async,
)
from AgentEval._core.errors import AdapterError, MissingExtraError
from AgentEval._core.tier import deterministic_scope
from AgentEval._core.types import AgentRunResult


class _StubAdapter:
    """A minimal object that satisfies the Adapter protocol."""

    name = "stub"

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        return AgentRunResult(response_text=f"echo:{prompt}")


def test_generic_adapter_satisfies_protocol() -> None:
    assert isinstance(GenericAdapter(), Adapter)


def test_custom_object_satisfies_protocol() -> None:
    assert isinstance(_StubAdapter(), Adapter)


def test_get_adapter_by_slug() -> None:
    adapter = get_adapter("generic")
    assert isinstance(adapter, GenericAdapter)


def test_get_adapter_passthrough_of_object() -> None:
    stub = _StubAdapter()
    assert get_adapter(stub) is stub


def test_get_adapter_unknown_slug_raises() -> None:
    with pytest.raises(AdapterError):
        get_adapter("no-such-adapter")


def test_missing_litellm_raises_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force `import litellm` to fail regardless of whether it is installed.
    monkeypatch.setitem(sys.modules, "litellm", None)
    adapter = GenericAdapter(model="openai/gpt-4o")
    with pytest.raises(MissingExtraError) as excinfo:
        adapter.run("hello")
    assert excinfo.value.extra == "llm"
    assert "llm" in str(excinfo.value)


def test_generic_adapter_maps_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("litellm")

    def _completion(*, model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        assert model == "openai/gpt-4o"
        assert messages == [{"role": "user", "content": "hi"}]
        return {
            "choices": [{"message": {"content": "hello back"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
        }

    def _completion_cost(*, completion_response: Any) -> float:
        return 0.0012

    fake.completion = _completion  # type: ignore[attr-defined]
    fake.completion_cost = _completion_cost  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)

    result = GenericAdapter(model="openai/gpt-4o").run("hi")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "hello back"
    assert result.usage.input_tokens == 5
    assert result.usage.output_tokens == 7
    assert result.cost_usd == pytest.approx(0.0012)


def test_generic_adapter_needs_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("litellm")
    fake.completion = lambda **kwargs: {}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)
    monkeypatch.delenv("AGENTEVAL_MODEL", raising=False)
    with pytest.raises(AdapterError):
        GenericAdapter().run("hi")


def test_generic_adapter_blocked_in_deterministic_scope() -> None:
    from AgentEval._core.errors import TierViolationError

    with deterministic_scope(), pytest.raises(TierViolationError):
        GenericAdapter(model="openai/gpt-4o").run("hi")


def test_resolve_config_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTEVAL_MODEL", "env-model")
    assert resolve_config("kw", env_var="AGENTEVAL_MODEL", default="def") == "kw"
    assert resolve_config(None, env_var="AGENTEVAL_MODEL", default="def") == "env-model"
    monkeypatch.delenv("AGENTEVAL_MODEL", raising=False)
    assert resolve_config(None, env_var="AGENTEVAL_MODEL", default="def") == "def"


def test_run_async_fast_path() -> None:
    async def coro() -> int:
        return 42

    assert run_async(coro()) == 42


def test_run_async_from_running_loop() -> None:
    import asyncio

    async def inner() -> int:
        return 7

    async def outer() -> int:
        # A loop is already running here; run_async must fall back to a worker thread.
        return run_async(inner())

    assert asyncio.run(outer()) == 7
