"""Unit tests for _kernel/discovery.py (AC-1b.3.1, AC-1b.3.2, AC-1b.3.8).

Uses `monkeypatch.setattr(importlib_metadata, "entry_points", fake)` to stub
entry-point discovery so tests don't depend on installed adapter packages.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from AgentEval._kernel import discovery
from AgentEval.errors import AdapterDiscoveryError, DuplicateRegistrationError


class _FakeEntryPoint:
    """Minimal stand-in for importlib.metadata.EntryPoint."""

    def __init__(self, name: str, value: str, load_result: Any = None, load_exc: Exception | None = None) -> None:
        self.name = name
        self.value = value
        self._load_result = load_result
        self._load_exc = load_exc

    def load(self) -> Any:
        if self._load_exc is not None:
            raise self._load_exc
        return self._load_result


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Reset discovery caches + programmatic registrations between tests."""
    discovery._clear_discovery_cache()
    yield
    discovery._clear_discovery_cache()


def _patch_entry_points(monkeypatch: pytest.MonkeyPatch, group_to_entries: dict[str, list[_FakeEntryPoint]]) -> None:
    """Patch `importlib.metadata.entry_points(group=...)` to return the test's fake entries."""

    def fake_entry_points(*, group: str) -> list[_FakeEntryPoint]:
        return group_to_entries.get(group, [])

    monkeypatch.setattr(importlib_metadata, "entry_points", fake_entry_points)
    # discovery.py imported `importlib.metadata` via `from importlib import metadata as importlib_metadata`,
    # so we must also patch the attribute on the discovery module's view.
    monkeypatch.setattr(discovery, "importlib_metadata", importlib_metadata)


# ============================================================ #
# AC-1b.3.1: 3 typed group accessors                          #
# ============================================================ #


class _StubAdapter:
    """SimpleNamespace-like stand-in for the Story 1b.4 CodingAgentAdapter Protocol."""

    name = "stub"


def test_discover_adapters_loads_primary_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"agenteval.coding_agents": [_FakeEntryPoint("alpha", "pkg.Adapter", _StubAdapter)]},
    )
    adapters = discovery.discover_adapters()
    assert "alpha" in adapters
    assert adapters["alpha"] is _StubAdapter


def test_discover_adapters_loads_legacy_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"robotframework_agenteval.adapters": [_FakeEntryPoint("legacy-one", "pkg.Legacy", _StubAdapter)]},
    )
    adapters = discovery.discover_adapters()
    assert "legacy-one" in adapters


def test_cross_package_duplicate_raises_duplicate_registration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-013 L43: Cross-package collisions across primary + legacy raise
    `DuplicateRegistrationError(AdapterDiscoveryError)` fail-closed — agenteval
    refuses to silently pick one. (Pre-Story-1b.3-code-review: impl used
    warnings.warn + primary-wins, which the ADR forbids. Codex caught.)
    """

    class PrimaryAdapter:
        pass

    class LegacyAdapter:
        pass

    _patch_entry_points(
        monkeypatch,
        {
            "agenteval.coding_agents": [_FakeEntryPoint("shared", "pkg.Primary", PrimaryAdapter)],
            "robotframework_agenteval.adapters": [_FakeEntryPoint("shared", "pkg.Legacy", LegacyAdapter)],
        },
    )
    with pytest.raises(DuplicateRegistrationError) as exc_info:
        discovery.discover_adapters()
    # ADR-013 L43 contract surfaces both source-package names.
    assert exc_info.value.sources == (
        "agenteval.coding_agents",
        "robotframework_agenteval.adapters",
    )
    assert "refuses to silently pick one" in str(exc_info.value)
    # DuplicateRegistrationError is a subclass of AdapterDiscoveryError per ADR-013 L43.
    assert isinstance(exc_info.value, AdapterDiscoveryError)
    assert exc_info.value.error_code == "ADAPTER_DISCOVERY_ERROR"


def test_discover_providers_loads_providers_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"agenteval.providers": [_FakeEntryPoint("litellm", "pkg.LiteLLM", _StubAdapter)]},
    )
    providers = discovery.discover_providers()
    assert providers == {"litellm": _StubAdapter}


def test_discover_sandboxes_loads_sandboxes_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"agenteval.sandboxes": [_FakeEntryPoint("docker", "pkg.Docker", _StubAdapter)]},
    )
    sandboxes = discovery.discover_sandboxes()
    assert sandboxes == {"docker": _StubAdapter}


# ============================================================ #
# AC-1b.3.2: register_adapter + get_adapter + AdapterDiscoveryError #
# ============================================================ #


def test_register_adapter_then_get_returns_it() -> None:
    discovery.register_adapter("my-adapter", _StubAdapter)
    assert discovery.get_adapter("my-adapter") is _StubAdapter


def test_register_adapter_overwrites_with_warning() -> None:
    discovery.register_adapter("overwrite-me", _StubAdapter)

    class NewerAdapter:
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        discovery.register_adapter("overwrite-me", NewerAdapter)
    assert discovery.get_adapter("overwrite-me") is NewerAdapter
    assert any("already registered programmatically" in str(w.message) for w in caught)


def test_get_adapter_precedence_programmatic_over_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Programmatic registration wins over entry-point discovery."""

    class FromEntryPoint:
        pass

    class FromCode:
        pass

    _patch_entry_points(
        monkeypatch,
        {"agenteval.coding_agents": [_FakeEntryPoint("shared", "pkg.X", FromEntryPoint)]},
    )
    discovery.register_adapter("shared", FromCode)
    assert discovery.get_adapter("shared") is FromCode


def test_get_adapter_miss_raises_adapter_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"agenteval.coding_agents": [_FakeEntryPoint("alpha", "pkg.A", _StubAdapter)]},
    )
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        discovery.get_adapter("nonexistent")
    assert "nonexistent" in str(exc_info.value)
    # Error message lists known adapters.
    assert "'alpha'" in str(exc_info.value)
    # error_code per contract L82.
    assert exc_info.value.error_code == "ADAPTER_DISCOVERY_ERROR"


def test_partial_install_detection_raises_with_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-013 L42: partial-install raises AdapterDiscoveryError with the
    installed-vs-required-extras diagnostic hint format. Story 1b.3 code-review
    fix: the helper now CONTINUES PAST per-entry failures + surfaces
    `loaded_so_far` so callers can recover successful entries.
    """
    bad_entry = _FakeEntryPoint(
        "broken",
        "missing_module.NotImportable",
        load_exc=ModuleNotFoundError("No module named 'missing_module'"),
    )
    _patch_entry_points(monkeypatch, {"agenteval.coding_agents": [bad_entry]})
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        discovery.discover_adapters()
    # Diagnostic format covers the failing entry's value + the error type/message.
    assert "missing_module.NotImportable" in str(exc_info.value)
    assert "ModuleNotFoundError" in str(exc_info.value)
    assert "ADR-013" in str(exc_info.value)
    # `loaded_so_far` attribute present per ADR-013 L42 verbatim contract.
    assert hasattr(exc_info.value, "loaded_so_far")
    assert exc_info.value.loaded_so_far == {}


def test_attribute_error_on_load_also_raises_adapter_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_entry = _FakeEntryPoint(
        "bad-attr", "pkg:NotAClass", load_exc=AttributeError("module 'pkg' has no attribute 'NotAClass'")
    )
    _patch_entry_points(monkeypatch, {"agenteval.coding_agents": [bad_entry]})
    with pytest.raises(AdapterDiscoveryError):
        discovery.discover_adapters()


def test_partial_install_preserves_successful_entries_in_loaded_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-013 L42 contract: a broken entry does NOT lose successful entries
    that loaded BEFORE it. The aggregated error surfaces them via `loaded_so_far`.
    (Story 1b.3 code-review STAR catch: pre-edit impl aborted on first failure,
    contradicting AC-1b.3.2 + the module docstring claim.)
    """

    class GoodAdapter:
        pass

    good_entry = _FakeEntryPoint("good", "pkg.GoodAdapter", GoodAdapter)
    bad_entry = _FakeEntryPoint(
        "broken",
        "missing_module.NotImportable",
        load_exc=ModuleNotFoundError("No module named 'missing_module'"),
    )
    _patch_entry_points(
        monkeypatch,
        {"agenteval.coding_agents": [good_entry, bad_entry]},
    )
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        discovery.discover_adapters()
    # Successful entries are NOT lost.
    assert exc_info.value.loaded_so_far == {"good": GoodAdapter}
    # The aggregated message mentions BOTH the load count + the broken entry.
    assert "loaded 1 successfully" in str(exc_info.value)
    assert "missing_module" in str(exc_info.value)


def test_partial_install_aggregates_multiple_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple broken entries: all surfaced in one aggregated error message."""
    bad1 = _FakeEntryPoint("bad1", "missing1.X", load_exc=ImportError("import failed for 1"))
    bad2 = _FakeEntryPoint("bad2", "missing2.Y", load_exc=ModuleNotFoundError("no module 2"))
    _patch_entry_points(monkeypatch, {"agenteval.coding_agents": [bad1, bad2]})
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        discovery.discover_adapters()
    msg = str(exc_info.value)
    assert "2 entry-point(s)" in msg
    assert "bad1" in msg
    assert "bad2" in msg


# ============================================================ #
# AC-1b.3.8: TYPE_CHECKING forward-ref / duck-typed runtime    #
# ============================================================ #


def test_register_adapter_accepts_duck_typed_class() -> None:
    """Story 1b.4 lands CodingAgentAdapter Protocol; until then, any class works."""

    class WeirdShape:
        random_attr = 1

    discovery.register_adapter("weird", WeirdShape)
    assert discovery.get_adapter("weird") is WeirdShape


# ============================================================ #
# Cache + reset helpers                                       #
# ============================================================ #


def test_clear_discovery_cache_resets_caches_and_registrations(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(
        monkeypatch,
        {"agenteval.coding_agents": [_FakeEntryPoint("alpha", "pkg.A", _StubAdapter)]},
    )
    discovery.register_adapter("manual", _StubAdapter)
    assert "alpha" in discovery.discover_adapters()
    assert discovery.get_adapter("manual") is _StubAdapter

    discovery._clear_discovery_cache()
    # Registrations gone; cache cleared.
    with pytest.raises(AdapterDiscoveryError):
        discovery.get_adapter("manual")


def test_no_entry_points_returns_empty_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, {})
    assert discovery.discover_adapters() == {}
    assert discovery.discover_providers() == {}
    assert discovery.discover_sandboxes() == {}


# ============================================================ #
# Story 1b.3 code-review patches: input validation + thread-safety #
# ============================================================ #


def test_register_adapter_rejects_non_class_cls() -> None:
    """P12: register_adapter validates `cls` is a class (not an instance, None, etc.)."""
    with pytest.raises(TypeError, match="must be a class"):
        discovery.register_adapter("instance", _StubAdapter())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a class"):
        discovery.register_adapter("none", None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a class"):
        discovery.register_adapter("lambda", lambda: None)  # type: ignore[arg-type]


def test_register_adapter_rejects_empty_or_non_str_name() -> None:
    """P12: register_adapter validates `name` is a non-empty str."""
    with pytest.raises(TypeError, match="non-empty str"):
        discovery.register_adapter("", _StubAdapter)
    with pytest.raises(TypeError, match="non-empty str"):
        discovery.register_adapter(None, _StubAdapter)  # type: ignore[arg-type]


def test_get_adapter_rejects_empty_or_non_str_name() -> None:
    """P13: get_adapter validates `name` is a non-empty str."""
    with pytest.raises(TypeError, match="non-empty str"):
        discovery.get_adapter("")
    with pytest.raises(TypeError, match="non-empty str"):
        discovery.get_adapter(None)  # type: ignore[arg-type]


def test_registered_adapters_thread_lock_does_not_deadlock_on_reentrant_register() -> None:
    """P7: `_registration_lock` is an RLock so a same-thread register_adapter
    chain (e.g., from a __init__ that calls register_adapter on another
    adapter) doesn't deadlock. (We don't test multi-threaded race here because
    pytest's main thread suffices to verify reentrant acquisition.)
    """
    discovery.register_adapter("outer", _StubAdapter)
    # If the lock were a non-reentrant Lock, this would deadlock the main thread.
    discovery.register_adapter("inner", _StubAdapter)
    assert discovery.get_adapter("outer") is _StubAdapter
    assert discovery.get_adapter("inner") is _StubAdapter


def test_negative_result_lru_cache_retries_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3: After a partial-install failure, subsequent discover_adapters()
    calls SHOULD re-traverse entry_points (Python lru_cache semantics: failures
    are not memoized). This protects users who install a missing package + retry.
    """
    bad_entry = _FakeEntryPoint("broken", "missing.X", load_exc=ModuleNotFoundError("not yet installed"))

    class GoodAdapter:
        pass

    state = {"phase": "bad"}

    def dynamic_entry_points(*, group: str) -> list[_FakeEntryPoint]:
        if group != "agenteval.coding_agents":
            return []
        if state["phase"] == "bad":
            return [bad_entry]
        return [_FakeEntryPoint("good", "pkg.G", GoodAdapter)]

    monkeypatch.setattr(discovery.importlib_metadata, "entry_points", dynamic_entry_points)

    # First call: bad; raises.
    with pytest.raises(AdapterDiscoveryError):
        discovery.discover_adapters()

    # Simulate user installing the missing package; entry_points now returns good.
    state["phase"] = "good"

    # Second call: would still return cached bad-result if lru_cache memoized failures.
    # Python's lru_cache does NOT memoize exceptions, so this succeeds.
    assert discovery.discover_adapters() == {"good": GoodAdapter}


def test_cached_helpers_return_immutable_mapping_proxy() -> None:
    """P3: lru_cache helpers wrap results in MappingProxyType so consumers
    can't mutate the cached dict. The public accessors return a fresh dict()
    so caller mutations are safe.
    """
    from types import MappingProxyType

    cached = discovery._cached_coding_agents()
    assert isinstance(cached, MappingProxyType)
    # Public accessor returns a fresh dict (caller-mutable).
    fresh = discovery.discover_adapters()
    assert isinstance(fresh, dict) and not isinstance(fresh, MappingProxyType)
