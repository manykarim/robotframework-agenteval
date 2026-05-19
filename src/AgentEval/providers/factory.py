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

"""Provider factory — resolve `LLMProviderAdapter` by name (Story 4.1 / PRD FR17c).

Lookup precedence:
1. **Built-in registry** (`{"litellm": LiteLLMAdapter, "mock": MockProvider}`)
   — ensures the factory works even when entry-points haven't loaded
   (test-friendly + zero-config OOTB experience).
2. **Entry-points group `"agenteval.providers"`** (PRD FR17c) — OVERRIDES
   the built-in registry; contributors can replace the built-in
   `litellm` adapter with a custom one without monkey-patching.

Programmatic registration is NOT supported (Phase-1 — per Story 1b.3
`_kernel/discovery.py:269` comment: "Adapter-only per PRD FR17b;
providers + sandboxes are entry-points-only by design"). Future
stories may broaden this if FR17b scope expands.
"""

from __future__ import annotations

from typing import Any

from AgentEval._kernel.discovery import discover_providers
from AgentEval.errors import AdapterDiscoveryError
from AgentEval.providers.base import LLMProviderAdapter
from AgentEval.providers.litellm_adapter import LiteLLMAdapter
from AgentEval.providers.mock import MockProvider

__all__ = ["get_provider", "BUILTIN_PROVIDERS"]


# Built-in registry — provider name → adapter class.
# Entry-points OVERRIDE these per FR17c.
BUILTIN_PROVIDERS: dict[str, type] = {
    "litellm": LiteLLMAdapter,
    "mock": MockProvider,
}


def get_provider(name: str, **kwargs: Any) -> LLMProviderAdapter:
    """Resolve a provider adapter class by name + instantiate with `**kwargs`.

    Args:
        name: Provider identifier (e.g., `"litellm"`, `"mock"`, or a
            custom name registered via entry-points).
        **kwargs: Forwarded to the adapter's constructor.

    Returns:
        Constructed `LLMProviderAdapter` instance.

    Raises:
        AdapterDiscoveryError: when `name` is unknown across both
            built-in registry + entry-points discovery. The error
            message lists all known provider names for diagnostic.
    """
    # FR17c semantics: entry-points override built-in registry.
    entry_point_providers: dict[str, type] = {}
    try:
        entry_point_providers = discover_providers()
    except AdapterDiscoveryError:
        # Partial-install or scan failure — fall through to built-in
        # registry. The Story 1b.3 contract is that discover_providers()
        # raises only on partial install AND collects successes into the
        # error's `loaded_so_far` attr; we accept the strict raise here
        # rather than peeling open loaded_so_far because the built-in
        # registry already covers the Phase-1 default providers.
        entry_point_providers = {}

    merged_registry: dict[str, type] = {**BUILTIN_PROVIDERS, **entry_point_providers}

    if name not in merged_registry:
        known = sorted(merged_registry.keys())
        raise AdapterDiscoveryError(
            f"Unknown provider {name!r}; known: {known}. "
            "Register a custom provider via "
            '`[project.entry-points."agenteval.providers"]` in your pyproject.toml '
            "per PRD FR17c."
        )

    cls = merged_registry[name]
    instance: LLMProviderAdapter = cls(**kwargs)
    return instance
