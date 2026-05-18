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
from AgentEval.errors import AdapterDiscoveryError


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


def test_discover_adapters_merge_primary_wins_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collision between primary + legacy: primary wins + UserWarning emitted."""

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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        adapters = discovery.discover_adapters()
    assert adapters["shared"] is PrimaryAdapter
    assert any("primary group wins" in str(w.message) for w in caught)


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
    installed-vs-required-extras diagnostic hint format.
    """
    bad_entry = _FakeEntryPoint(
        "broken",
        "missing_module.NotImportable",
        load_exc=ModuleNotFoundError("No module named 'missing_module'"),
    )
    _patch_entry_points(monkeypatch, {"agenteval.coding_agents": [bad_entry]})
    with pytest.raises(AdapterDiscoveryError) as exc_info:
        discovery.discover_adapters()
    # Diagnostic format from ADR-013 L42.
    assert "missing_module.NotImportable" in str(exc_info.value)
    assert "could not be loaded" in str(exc_info.value)
    assert "ADR-013" in str(exc_info.value)


def test_attribute_error_on_load_also_raises_adapter_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_entry = _FakeEntryPoint(
        "bad-attr", "pkg:NotAClass", load_exc=AttributeError("module 'pkg' has no attribute 'NotAClass'")
    )
    _patch_entry_points(monkeypatch, {"agenteval.coding_agents": [bad_entry]})
    with pytest.raises(AdapterDiscoveryError):
        discovery.discover_adapters()


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
