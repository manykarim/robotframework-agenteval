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

Loads PyPA entry-points across the 4 agenteval-owned `agenteval.*` tables + 1
legacy table per ADR-013 L47:

- `agenteval.coding_agents` (FR17a, primary) — Coding-agent adapter registrations.
- `agenteval.providers` (FR17c) — LLM provider plugins.
- `agenteval.judges` (Phase-2 only; no Phase-1 discover function).
- `agenteval.sandboxes` (per ADR-018) — Sandbox backend implementations.
- `robotframework_agenteval.adapters` (legacy FR17a backward-compat group;
  declared in Story 1a.1's `pyproject.toml`).

The 6th table, `robot.listener` (FR33a), is RF-owned and NOT discovered by
this module. (ADR-013 L40's "5 agenteval.* entry-point groups" phrasing
predates Story 1b.3's create-story drift check; the L47 Consequences listing
of 4 agenteval.* + 1 legacy = 5 agenteval-owned is the truth source. ADR-013
L40 was amended post-Story-1b.3-code-review per the citation-drift
fix-the-losing-source norm.)

Phase-1 forward-reference pattern (per Story 1b.2's pattern for `AgentRunResult`):
Story 1b.4 lands the `CodingAgentAdapter` Protocol in `src/AgentEval/types.py`.
This module references it via `TYPE_CHECKING` so type checkers see the
Protocol but runtime accepts any duck-typed adapter class.

Resilience contract (Story 1b.3 code-review fix per ADR-013 L42 verbatim):
The generic `_discover_entry_point_group()` helper CONTINUES PAST per-entry
load failures, accumulating successes into a `loaded_so_far` dict. If ANY
entry failed, it raises `AdapterDiscoveryError` at the end of the scan with
the per-entry failure messages joined + the `loaded_so_far` attribute set so
callers can opt into "best-effort" behavior. A single broken third-party
adapter therefore CANNOT block library import or hide the successfully-loaded
adapters from a partial-failure scan. (The pre-Story-1b.3-code-review version
of this helper raised on first failure, contradicting both AC-1b.3.2 + the
module docstring's "cannot block library import" claim.)

Duplicate-rejection contract (Story 1b.3 code-review fix per ADR-013 L43):
Cross-package collisions between `agenteval.coding_agents` (primary) AND
`robotframework_agenteval.adapters` (legacy) raise `DuplicateRegistrationError`
fail-closed — agenteval refuses to silently pick one. (Pre-edit code used
`warnings.warn` + primary-wins, which the ADR explicitly forbids.) Intra-group
collisions remain governed by PyPA installer-side metadata-uniqueness rules;
if an installer accepts a duplicate anyway, the dict-update last-wins fallback
applies and a UserWarning is emitted.

The 3 typed public accessors (`discover_adapters`, `discover_providers`,
`discover_sandboxes`) call into `@functools.lru_cache(maxsize=1)`-backed
helpers that cache the SUCCESSFUL scan result + skip the cache on a prior
failure (negative-result non-memoization, so reinstalling a missing adapter
package + re-importing yields the fresh state without an explicit reset).
Tests + reset paths must still call `_clear_discovery_cache()` for explicit
state reset.

Programmatic-registration thread-safety (Story 1b.3 code-review fix per P7):
`_registered_adapters` mutations + reads now hold `_registration_lock`
(an `RLock`) to guard against the multi-threaded RF parallel-execution case.

Phase-1 limitation note for `_kernel/guardrails._current_cost_usd_for_run`:
The cost-source function is module-level + single-fanout-at-a-time scoped
(no run id / context key / provider handle). Per Story 4.1 (Generic LiteLLM
adapter), the per-run scoped interface lands when the real cost-tracking
provider is wired. Story 1b.3 ships the polling-loop + breach-detection +
cooperative-cancellation hook; the per-run scoping is deferred.

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
import threading
import warnings
from collections.abc import Mapping
from importlib import metadata as importlib_metadata
from types import MappingProxyType
from typing import TYPE_CHECKING

from AgentEval.errors import AdapterDiscoveryError, DuplicateRegistrationError

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
# Both mutation + read are guarded by _registration_lock (RLock so callers can
# nest register_adapter → register_adapter calls without deadlock).
_registered_adapters: dict[str, type] = {}
_registration_lock = threading.RLock()


# Entry-point group names per ADR-013 L47.
_GROUP_CODING_AGENTS = "agenteval.coding_agents"
_GROUP_PROVIDERS = "agenteval.providers"
_GROUP_SANDBOXES = "agenteval.sandboxes"
_GROUP_LEGACY_ADAPTERS = "robotframework_agenteval.adapters"


def _discover_entry_point_group(group_name: str) -> dict[str, type]:
    """Generic resilient entry-point discovery for a single PyPA group.

    Iterates entries via `importlib.metadata.entry_points(group=...)`. For each
    entry, attempts `entry.load()` inside a try/except. PER-ENTRY failures are
    LOGGED at WARNING + captured into a `per_entry_errors` list; successes are
    captured into a `loaded` dict. After the entire iteration, if any failures
    occurred, raises `AdapterDiscoveryError` with the aggregated diagnostic +
    sets `loaded_so_far=loaded` on the exception so callers can recover the
    successful entries.

    Returns a dict mapping entry name → loaded class on full success (no
    failures encountered). Successful entries are NEVER lost — they're either
    returned via the normal return OR surfaced via the raised exception's
    `loaded_so_far` attribute per ADR-013 L42 contract.

    A single broken third-party adapter cannot block library import:
    `discover_adapters()`-style callers that want best-effort behavior can
    catch `AdapterDiscoveryError` and read `exc.loaded_so_far`. Callers that
    want strict behavior re-raise.
    """
    loaded: dict[str, type] = {}
    per_entry_errors: list[str] = []
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
            per_entry_errors.append(f"`{group_name}:{entry.name}` -> `{entry.value}`: {type(exc).__name__}: {exc}")
    if per_entry_errors:
        raise AdapterDiscoveryError(
            (
                f"{len(per_entry_errors)} entry-point(s) in `{group_name}` failed to "
                f"load (loaded {len(loaded)} successfully). Install the missing "
                "packages OR remove the broken registrations. See "
                "docs/adr/ADR-013-entry-points-discovery-infrastructure.md L42 for "
                "the installed-vs-required-extras diagnostic contract. Per-entry: " + "; ".join(per_entry_errors)
            ),
            loaded_so_far=loaded,
        )
    return loaded


# ===== Cached helpers (negative-result non-memoization) ============================ #
# lru_cache only memoizes SUCCESSFUL returns; a raised exception is NOT cached, so
# the next call re-attempts. Successful results are returned as a frozen MappingProxy
# so consumers can't accidentally mutate the cached dict.


@functools.lru_cache(maxsize=1)
def _cached_coding_agents() -> Mapping[str, type]:
    """Cached merge of `agenteval.coding_agents` (primary) + `robotframework_agenteval.adapters` (legacy).

    Cross-package collisions raise `DuplicateRegistrationError(AdapterDiscoveryError)`
    fail-closed per ADR-013 L43 verbatim — agenteval refuses to silently pick
    one when a name appears in both groups.
    """
    # Both groups are scanned eagerly; if either has partial-install failures,
    # the AdapterDiscoveryError propagates through the helper and lru_cache
    # does NOT memoize the failure (Python exception-result semantics).
    primary = _discover_entry_point_group(_GROUP_CODING_AGENTS)
    legacy = _discover_entry_point_group(_GROUP_LEGACY_ADAPTERS)
    merged: dict[str, type] = dict(legacy)
    for name, cls in primary.items():
        if name in merged:
            raise DuplicateRegistrationError(
                f"Adapter name {name!r} is declared in BOTH "
                f"`{_GROUP_CODING_AGENTS}` (primary, class {cls!r}) AND "
                f"`{_GROUP_LEGACY_ADAPTERS}` (legacy, class {merged[name]!r}). "
                f"Per ADR-013 L43, agenteval refuses to silently pick one. "
                f"Resolve by removing one of the two registrations.",
                sources=(_GROUP_CODING_AGENTS, _GROUP_LEGACY_ADAPTERS),
                loaded_so_far={k: v for k, v in merged.items() if k != name},
            )
        merged[name] = cls
    return MappingProxyType(merged)


@functools.lru_cache(maxsize=1)
def _cached_providers() -> Mapping[str, type]:
    return MappingProxyType(dict(_discover_entry_point_group(_GROUP_PROVIDERS)))


@functools.lru_cache(maxsize=1)
def _cached_sandboxes() -> Mapping[str, type]:
    return MappingProxyType(dict(_discover_entry_point_group(_GROUP_SANDBOXES)))


def discover_adapters() -> dict[str, type[CodingAgentAdapter]]:
    """Discover coding-agent adapters across `agenteval.coding_agents` (primary)
    + `robotframework_agenteval.adapters` (legacy backward-compat per ADR-013 L18).

    On cross-package name collision, raises `DuplicateRegistrationError` per
    ADR-013 L43 (agenteval refuses to silently pick one).

    Returns a fresh `dict` (caller-mutable; the underlying cached MappingProxy
    is read-only).

    Raises:
        DuplicateRegistrationError: cross-package adapter-name collision.
        AdapterDiscoveryError: one or more entry-points failed to load
            (e.g., partial install, broken import). The exception's
            `loaded_so_far` attribute holds the successfully-loaded entries.
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


# ===== Programmatic-registration path (FR17b) ===================================== #
# Adapter-only per PRD FR17b; providers + sandboxes are entry-points-only by design.
# Future stories may add register_provider / register_sandbox if FR17b is broadened.


def register_adapter(name: str, cls: type[CodingAgentAdapter]) -> None:
    """Register a coding-agent adapter programmatically (FR17b composition path).

    Lookup precedence in `get_adapter`: programmatic > primary entry-points >
    legacy entry-points. Same-name re-registration overwrites with a
    `UserWarning` (stacklevel=2 → warning attributes the caller's frame, not
    this module's; intentional for user-facing diagnostic).

    Validates `name` is a non-empty string + `cls` is a class (not an instance,
    None, or anything else duck-typed). Type validation is intentionally
    minimal — Story 1b.4 lands the `CodingAgentAdapter` Protocol and Story 1b.5
    lands conformance checks against it.

    Args:
        name: Adapter identifier consumed by `get_adapter(name)`.
        cls: Adapter class (duck-typed against `CodingAgentAdapter` Protocol
            until Story 1b.4 ratifies the type).

    Raises:
        TypeError: `name` is not a non-empty str OR `cls` is not a class.
    """
    if not isinstance(name, str) or not name:
        raise TypeError(f"register_adapter: `name` must be a non-empty str (got {name!r})")
    if not isinstance(cls, type):
        raise TypeError(
            f"register_adapter: `cls` must be a class (got instance of {type(cls).__name__!r}). "
            "Pass the class itself, not an instance."
        )
    with _registration_lock:
        if name in _registered_adapters:
            warnings.warn(
                f"Adapter {name!r} was already registered programmatically; overwriting.",
                UserWarning,
                stacklevel=2,  # attribute to the caller's frame
            )
        _registered_adapters[name] = cls


def get_adapter(name: str) -> type[CodingAgentAdapter]:
    """Resolve an adapter by name across all lookup paths.

    Precedence:
        1. Programmatic registrations (`register_adapter` calls).
        2. `agenteval.coding_agents` entry-points (primary).
        3. `robotframework_agenteval.adapters` entry-points (legacy).

    Raises:
        TypeError: `name` is not a non-empty str.
        AdapterDiscoveryError: name not found in any lookup path. Error
            message lists known adapter names. `loaded_so_far` is the empty
            dict for lookup-miss; populated for partial-install scans.
    """
    if not isinstance(name, str) or not name:
        raise TypeError(f"get_adapter: `name` must be a non-empty str (got {name!r})")
    with _registration_lock:
        if name in _registered_adapters:
            return _registered_adapters[name]
    discovered = _cached_coding_agents()
    if name in discovered:
        return discovered[name]
    with _registration_lock:
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
    clears `_registered_adapters` (under the registration lock).

    Production code MUST NOT call this — there is no documented use case
    outside the test harness, and clearing the cache mid-process is not
    thread-safe with respect to concurrent `get_adapter` lookups.
    """
    _cached_coding_agents.cache_clear()
    _cached_providers.cache_clear()
    _cached_sandboxes.cache_clear()
    with _registration_lock:
        _registered_adapters.clear()
