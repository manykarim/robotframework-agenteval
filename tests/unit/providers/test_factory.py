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

"""Unit tests for `AgentEval.providers.factory.get_provider`."""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval.errors import AdapterDiscoveryError
from AgentEval.providers.base import ChatResponse, LLMProviderAdapter, Message
from AgentEval.providers.factory import BUILTIN_PROVIDERS, get_provider
from AgentEval.providers.litellm_adapter import LiteLLMAdapter
from AgentEval.providers.mock import MockProvider


def test_get_provider_litellm_returns_litellm_adapter_instance() -> None:
    p = get_provider("litellm")
    assert isinstance(p, LiteLLMAdapter)
    assert p.name == "litellm"


def test_get_provider_mock_returns_mock_provider_instance() -> None:
    p = get_provider("mock")
    assert isinstance(p, MockProvider)
    assert p.name == "mock"


def test_get_provider_unknown_raises_adapter_discovery_error() -> None:
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        get_provider("nonexistent_provider_xyz")
    # Error message lists known providers for diagnostic per AC-4.1.4.
    assert "litellm" in str(exc_info.value)
    assert "mock" in str(exc_info.value)


def test_get_provider_forwards_kwargs_to_constructor() -> None:
    p = get_provider("mock", responses=[ChatResponse(text="scripted")])
    resp = p.chat(messages=[Message(role="user", content="ignored")])
    assert resp.text == "scripted"


def test_builtin_providers_includes_litellm_and_mock() -> None:
    assert "litellm" in BUILTIN_PROVIDERS
    assert "mock" in BUILTIN_PROVIDERS


def test_get_provider_returns_protocol_conforming_instance() -> None:
    """Result MUST satisfy `isinstance(p, LLMProviderAdapter)` via `runtime_checkable`."""
    assert isinstance(get_provider("mock"), LLMProviderAdapter)
    assert isinstance(get_provider("litellm"), LLMProviderAdapter)


def test_get_provider_entry_points_override_built_in_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR17c: entry-points OVERRIDE the built-in registry."""

    class CustomMock:
        name = "litellm"  # SAME name as built-in to test override
        version = "custom"

        def chat(self, messages: Any, tools: Any = None, **kwargs: Any) -> ChatResponse:  # type: ignore[no-untyped-def]
            return ChatResponse(text="CUSTOM")

    # Monkeypatch the discover_providers to return our custom override.
    import AgentEval.providers.factory as factory_mod

    monkeypatch.setattr(factory_mod, "discover_providers", lambda: {"litellm": CustomMock})
    p = get_provider("litellm")
    # Custom override wins.
    assert isinstance(p, CustomMock)
    assert p.chat(messages=[Message(role="user", content="ignored")]).text == "CUSTOM"


def test_get_provider_tolerates_discover_providers_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When discover_providers raises AdapterDiscoveryError (partial install),
    factory falls back to built-in registry per AC-4.1.4 comment."""
    import AgentEval.providers.factory as factory_mod

    def _boom() -> dict[str, type]:
        raise AdapterDiscoveryError("partial install detected", loaded_so_far={})

    monkeypatch.setattr(factory_mod, "discover_providers", _boom)
    # Built-in litellm still resolves cleanly.
    p = get_provider("litellm")
    assert isinstance(p, LiteLLMAdapter)
