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
    except AdapterDiscoveryError as exc:
        # Story 4.1 code-review Codex HIGH (Probe 6b 2026-05-20):
        # `discover_providers()` raises `AdapterDiscoveryError` on
        # partial install but per `_kernel/discovery.py:168-178` contract
        # the successfully-loaded entries live on `exc.loaded_so_far`.
        # Pre-fix this factory dropped them, silently breaking FR17c
        # entry-points override when ANY unrelated provider entry-point
        # failed. Recover `loaded_so_far` so successful overrides
        # survive a single broken third-party plugin.
        entry_point_providers = dict(exc.loaded_so_far or {})

    # Story 4.1 code-review Edge-cases M-4 fix 2026-05-20: warn when an
    # entry-point overrides a built-in provider so debuggability survives
    # contention. Compare ADR-013 cross-package collision precedent
    # (DuplicateRegistrationError raises); for SAME-name built-in-vs-
    # entry-points conflicts the FR17c contract is "entry-points win" so
    # we warn rather than raise.
    for builtin_name, builtin_cls in BUILTIN_PROVIDERS.items():
        if builtin_name in entry_point_providers and entry_point_providers[builtin_name] is not builtin_cls:
            import warnings

            warnings.warn(
                f"Provider {builtin_name!r} entry-point override detected: "
                f"built-in {builtin_cls!r} → entry-point {entry_point_providers[builtin_name]!r}. "
                "Per PRD FR17c entry-points win over built-ins; emitted at debug-time so the "
                "consumer can confirm the override is intentional.",
                stacklevel=2,
            )

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
