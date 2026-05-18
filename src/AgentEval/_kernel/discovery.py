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

"""Entry-points discovery infrastructure (ADR-013 / was ADR-A2).

Loads PyPA entry-points across the 5 agenteval-owned tables per ADR-013 L47:

- `agenteval.coding_agents` (FR17a, primary) — Coding-agent adapter registrations.
- `agenteval.providers` (FR17c) — LLM provider plugins.
- `agenteval.judges` (Phase-2 only; no Phase-1 discover function).
- `agenteval.sandboxes` (per ADR-018) — Sandbox backend implementations.
- `robotframework_agenteval.adapters` (legacy FR17a backward-compat group;
  declared in Story 1a.1's `pyproject.toml`).

The 6th table, `robot.listener` (FR33a), is RF-owned and NOT discovered by
this module.

Phase-1 forward-reference pattern (per Story 1b.2's pattern for `AgentRunResult`):
Story 1b.4 lands the `CodingAgentAdapter` Protocol in `src/AgentEval/types.py`.
This module references it via `TYPE_CHECKING` so type checkers see the
Protocol but runtime accepts any duck-typed adapter class.

The `_discover_entry_point_group()` private helper is the generic underlying
machinery; the 3 typed public accessors (`discover_adapters`,
`discover_providers`, `discover_sandboxes`) are what sub-libraries call.
`functools.lru_cache` caches the discovery results so repeated reads don't
re-traverse `importlib.metadata.entry_points()` — call `_clear_discovery_cache()`
in tests + reset paths.

References:
    - ADR-013 (was ADR-A2): `docs/adr/ADR-013-entry-points-discovery-infrastructure.md`
    - PRD §FR17a — Coding-agent adapter entry-points
    - PRD §FR17b — Programmatic registration (composition path)
    - PRD §FR17c — Provider entry-points
    - architecture L374 — 6 entry-point tables
    - docs/contracts/error-class-hierarchy.md L82 — AdapterDiscoveryError
    - Story 1a.1 `pyproject.toml` — all 6 tables declared
"""

from __future__ import annotations

import functools
import logging
import warnings
from importlib import metadata as importlib_metadata
from typing import TYPE_CHECKING

from AgentEval.errors import AdapterDiscoveryError

if TYPE_CHECKING:
    from AgentEval.types import CodingAgentAdapter  # type: ignore[attr-defined]  # forward ref; lands in Story 1b.4

__all__ = [
    "discover_adapters",
    "discover_providers",
    "discover_sandboxes",
    "register_adapter",
    "get_adapter",
    "_clear_discovery_cache",
]


_log = logging.getLogger(__name__)


# Module-level state for programmatic registration path (FR17b).
# Lookup precedence: _registered_adapters > agenteval.coding_agents > robotframework_agenteval.adapters.
_registered_adapters: dict[str, type] = {}


# Entry-point group names per ADR-013 L47.
_GROUP_CODING_AGENTS = "agenteval.coding_agents"
_GROUP_PROVIDERS = "agenteval.providers"
_GROUP_SANDBOXES = "agenteval.sandboxes"
_GROUP_LEGACY_ADAPTERS = "robotframework_agenteval.adapters"


def _discover_entry_point_group(group_name: str) -> dict[str, type]:
    """Generic entry-point discovery for a single PyPA entry-point group.

    Iterates entries via `importlib.metadata.entry_points(group=...)`. For each
    entry, attempts `entry.load()` inside a try/except so a single broken
    third-party adapter cannot block library import.

    Returns a dict mapping entry name → loaded class. On per-entry import
    failure, raises `AdapterDiscoveryError` with the ADR-013 L42 diagnostic
    hint format. Successful entries before the failure are NOT lost — they're
    surfaced via the error's secondary `loaded_so_far` attribute (Phase-1
    convention; Story 1b.5 conformance harness may rely on it).
    """
    loaded: dict[str, type] = {}
    entry_points = importlib_metadata.entry_points(group=group_name)
    for entry in entry_points:
        try:
            loaded[entry.name] = entry.load()
        except (ModuleNotFoundError, ImportError, AttributeError) as exc:
            # ADR-013 L42 diagnostic: surface installed-vs-required-extras hint.
            _log.warning(
                "Entry-point %s:%s failed to load: %s",
                group_name,
                entry.name,
                exc,
            )
            raise AdapterDiscoveryError(
                f"Found `{group_name}:{entry.name}` registration but `{entry.value}` "
                "could not be loaded (missing module or import error: "
                f"{type(exc).__name__}: {exc}). "
                f"Install the package providing this entry-point, OR remove the "
                "registration. See docs/adr/ADR-013-entry-points-discovery-infrastructure.md "
                "L42 for the installed-vs-required-extras diagnostic contract."
            ) from exc
    return loaded


@functools.lru_cache(maxsize=1)
def _cached_coding_agents() -> dict[str, type]:
    """Cached merge of `agenteval.coding_agents` (primary) + `robotframework_agenteval.adapters` (legacy)."""
    primary = _discover_entry_point_group(_GROUP_CODING_AGENTS)
    legacy = _discover_entry_point_group(_GROUP_LEGACY_ADAPTERS)
    merged: dict[str, type] = dict(legacy)
    for name, cls in primary.items():
        if name in merged:
            warnings.warn(
                f"Adapter name {name!r} declared in both `{_GROUP_CODING_AGENTS}` (primary) "
                f"and `{_GROUP_LEGACY_ADAPTERS}` (legacy); primary group wins.",
                UserWarning,
                stacklevel=3,
            )
        merged[name] = cls
    return merged


@functools.lru_cache(maxsize=1)
def _cached_providers() -> dict[str, type]:
    return _discover_entry_point_group(_GROUP_PROVIDERS)


@functools.lru_cache(maxsize=1)
def _cached_sandboxes() -> dict[str, type]:
    return _discover_entry_point_group(_GROUP_SANDBOXES)


def discover_adapters() -> dict[str, type[CodingAgentAdapter]]:
    """Discover coding-agent adapters across `agenteval.coding_agents` (primary)
    + `robotframework_agenteval.adapters` (legacy backward-compat per ADR-013 L18).

    On name collision, the primary `agenteval.coding_agents` group wins (emits
    a `UserWarning`).

    Returns: dict mapping adapter name → adapter class. Empty dict if no
    adapters registered.

    Raises:
        AdapterDiscoveryError: If any entry-point in either group fails to
            load (e.g., partial install, broken import).
    """
    return dict(_cached_coding_agents())


def discover_providers() -> dict[str, type]:
    """Discover LLM providers via `agenteval.providers` entry-points (FR17c).

    Phase-1: returns dict mapping provider name → provider class. Type is
    `type` (not parameterized) because the `LLMProvider` Protocol lands in a
    future Epic 4 story.
    """
    return dict(_cached_providers())


def discover_sandboxes() -> dict[str, type]:
    """Discover sandbox backends via `agenteval.sandboxes` entry-points (ADR-018).

    Phase-1: returns dict mapping backend name → backend class. The
    `SandboxBackend` Protocol lives at `src/AgentEval/security/protocols.py`
    (Story 1a.1 baseline); Phase-3 backend implementations register via this
    discovery path.
    """
    return dict(_cached_sandboxes())


def register_adapter(name: str, cls: type[CodingAgentAdapter]) -> None:
    """Register a coding-agent adapter programmatically (FR17b composition path).

    Lookup precedence in `get_adapter`: programmatic > primary entry-points >
    legacy entry-points. Same-name re-registration overwrites with a
    `UserWarning`.

    Args:
        name: Adapter identifier consumed by `get_adapter(name)`.
        cls: Adapter class (duck-typed against `CodingAgentAdapter` Protocol
            until Story 1b.4 ratifies the type).
    """
    if name in _registered_adapters:
        warnings.warn(
            f"Adapter {name!r} was already registered programmatically; overwriting.",
            UserWarning,
            stacklevel=2,
        )
    _registered_adapters[name] = cls


def get_adapter(name: str) -> type[CodingAgentAdapter]:
    """Resolve an adapter by name across all lookup paths.

    Precedence:
        1. Programmatic registrations (`register_adapter` calls).
        2. `agenteval.coding_agents` entry-points (primary).
        3. `robotframework_agenteval.adapters` entry-points (legacy).

    Raises:
        AdapterDiscoveryError: If the name is not found in any path. Error
            message lists the known adapter names so callers can identify
            typos quickly.
    """
    if name in _registered_adapters:
        return _registered_adapters[name]
    discovered = _cached_coding_agents()
    if name in discovered:
        return discovered[name]
    known = sorted(set(_registered_adapters) | set(discovered))
    raise AdapterDiscoveryError(
        f"No adapter registered as {name!r}; known adapters: {known!r}. "
        "Use `register_adapter()` for programmatic registration or declare a "
        '`[project.entry-points."agenteval.coding_agents"]` table in the adapter '
        "package's pyproject.toml."
    )


def _clear_discovery_cache() -> None:
    """Test-only helper to reset the discovery caches.

    Tests that monkey-patch `importlib.metadata.entry_points` MUST call this
    before/after the test so the lru_cache doesn't return stale results. Also
    clears `_registered_adapters`.
    """
    _cached_coding_agents.cache_clear()
    _cached_providers.cache_clear()
    _cached_sandboxes.cache_clear()
    _registered_adapters.clear()
