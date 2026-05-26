# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `_kernel/version_drift.py` (Story 11.3 / PRD FR60)."""

from __future__ import annotations

import subprocess
import warnings
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval._kernel.version_drift import (
    AdapterVersionDriftWarning,
    emit_adapter_version_drift_warning_if_applicable,
    parse_binary_version,
    reset_session_drift_dedupe,
)


@pytest.fixture(autouse=True)
def _reset_drift_dedupe() -> None:
    """Reset the module-level dedupe set before each test."""
    reset_session_drift_dedupe()


# --------------------------------------------------------------------------- #
# Drift detection logic (AC-11.3.6 tests 1-4)                                  #
# --------------------------------------------------------------------------- #


def test_emit_warning_when_drift_exceeds_threshold() -> None:
    """tested.minor - detected.minor = 3 (>= 2 threshold) → warning fires."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.103.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is True
    assert any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


def test_no_warning_when_drift_under_threshold() -> None:
    """tested.minor - detected.minor = 1 (< 2 threshold) → no warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.132.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is False
    assert not any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


def test_no_warning_when_detected_equals_tested() -> None:
    """No drift → no warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.133.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is False
    assert not any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


def test_no_warning_when_detected_above_tested() -> None:
    """Detected newer than tested → no warning (operator likely forgot to bump _TESTED_UP_TO)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.150.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is False
    assert not any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


# --------------------------------------------------------------------------- #
# Session-scoped dedupe (AC-11.3.4 + AC-11.3.6 tests 5-6)                       #
# --------------------------------------------------------------------------- #


def test_session_dedupe_fires_once_per_triple() -> None:
    """Same triple emitted twice → only first fires."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        first = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
        second = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert first is True
    assert second is False
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 1


def test_session_dedupe_different_triples_fire_independently() -> None:
    """Different adapters / different MINOR-version drift → independent dedupe.

    Both examples have ``tested.minor - detected.minor >= 2`` so both fire.
    Copilot's 1.0.x → 1.0.y line shares minor=0 by design — patch-level drift
    does NOT fire (correct per epics.md L2076 'minor versions behind').
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
        emit_adapter_version_drift_warning_if_applicable(
            adapter_name="hypothetical-cli",
            detected_version="2.5.0",
            tested_up_to="2.8.0",
            compat_min="2.0.0",
            compat_max="3.0.0",
        )
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 2


# --------------------------------------------------------------------------- #
# Warning content (AC-11.3.3 + AC-11.3.6 test 7)                                #
# --------------------------------------------------------------------------- #


def test_warning_message_contains_all_fr60_elements() -> None:
    """The warning message MUST contain ALL 5 FR60-mandated elements."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 1
    msg = str(drift_warnings[0].message)
    # (a) adapter name
    assert "codex-cli" in msg
    # (b) detected version
    assert "0.100.0" in msg
    # (c) tested-up-to version
    assert "0.133.0" in msg
    # (d) drift severity (minor-version delta)
    assert "minor versions" in msg
    # (e) remediation
    assert "upgrade adapter" in msg or "pin CLI to tested version" in msg


# --------------------------------------------------------------------------- #
# Defensive input handling (AC-11.3.6 tests 8-9)                                #
# --------------------------------------------------------------------------- #


def test_no_warning_when_detected_version_is_none() -> None:
    """`detected_version=None` → silent no-op (the adapter's own _assert_binary_version
    would have raised already if the binary was unparseable)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version=None,
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is False
    assert not any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


def test_no_warning_when_versions_unparseable() -> None:
    """Non-semver strings → silent no-op."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="not-a-version",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert emitted is False
    assert not any(issubclass(w.category, AdapterVersionDriftWarning) for w in caught)


# --------------------------------------------------------------------------- #
# Test helper (AC-11.3.6 test 10)                                               #
# --------------------------------------------------------------------------- #


def test_reset_session_drift_dedupe_clears_state() -> None:
    """`reset_session_drift_dedupe()` re-enables emission of the same triple."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        first = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
        reset_session_drift_dedupe()
        second = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.100.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    assert first is True
    assert second is True
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 2


# --------------------------------------------------------------------------- #
# Cross-major drift                                                              #
# --------------------------------------------------------------------------- #


def test_drift_across_major_versions_fires_warning_with_clear_message() -> None:
    """Detected on previous major (e.g., 1.x when tested is 2.x) → warning fires
    with a major-boundary descriptor, NOT the pre-edit synthetic "99 minor
    versions" sentinel leakage (Story 11.3 copilot MED-2 review 2026-05-26)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="example",
            detected_version="1.99.0",
            tested_up_to="2.0.0",
            compat_min="1.0.0",
            compat_max="3.0.0",
        )
    assert emitted is True
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 1
    # Story 11.3 copilot MED-2: assert the synthetic "99 minor versions"
    # sentinel does NOT leak into user-visible text.
    msg = str(drift_warnings[0].message)
    assert "99 minor versions" not in msg
    assert "major version" in msg


def test_boundary_drift_exactly_at_threshold_fires() -> None:
    """Boundary case (Story 11.3 copilot LOW-2 review 2026-05-26): drift = 2
    exactly. Per Story 11.3 D-7 decision interpreting epics.md L2076 as
    `drift >= _DRIFT_MINOR_THRESHOLD (=2)` — the threshold value itself
    fires. This pins the boundary so future refactors don't silently
    flip the semantic to strict ">2"."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.131.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    # Per Story 11.3 D-7: `drift >= 2` fires; `drift = 2` is the threshold.
    assert emitted is True
    drift_warnings = [w for w in caught if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 1
    assert "2 minor versions" in str(drift_warnings[0].message)


# --------------------------------------------------------------------------- #
# `parse_binary_version` helper                                                 #
# --------------------------------------------------------------------------- #


def test_parse_binary_version_extracts_semver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substring-extract from prefixed/suffixed output (codex-cli + copilot patterns)."""

    def _fake(cmd: Any, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex-cli 0.133.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake)
    assert parse_binary_version("codex") == "0.133.0"


def test_parse_binary_version_returns_none_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing binary → None (not a raise; caller's _assert_binary_version handles raising)."""

    def _missing(cmd: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("not found")

    monkeypatch.setattr(subprocess, "run", _missing)
    assert parse_binary_version("missing-binary") is None


# --------------------------------------------------------------------------- #
# Integration: each Tier-1 CLI adapter calls the helper in __init__             #
# --------------------------------------------------------------------------- #


def test_codex_cli_calls_drift_helper_in_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.3 AC-11.3.2: `CodexCLIAdapter.__init__` MUST call
    `emit_adapter_version_drift_warning_if_applicable` after `_assert_binary_version`."""
    spy = MagicMock(return_value=False)
    monkeypatch.setattr(
        "AgentEval._kernel.version_drift.emit_adapter_version_drift_warning_if_applicable", spy
    )
    # Also mock the version probe so it doesn't shell out.
    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["codex", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex-cli 0.133.0\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    from AgentEval.coding_agent.codex_cli import CodexCLIAdapter

    CodexCLIAdapter()
    assert spy.call_count == 1
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["adapter_name"] == "codex-cli"
    assert call_kwargs["tested_up_to"] == "0.133.0"


def test_copilot_cli_calls_drift_helper_in_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.3 AC-11.3.2: same for CopilotCLIAdapter."""
    spy = MagicMock(return_value=False)
    monkeypatch.setattr(
        "AgentEval._kernel.version_drift.emit_adapter_version_drift_warning_if_applicable", spy
    )

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["copilot", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="GitHub Copilot CLI 1.0.54.\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    from AgentEval.coding_agent.copilot_cli import CopilotCLIAdapter

    CopilotCLIAdapter()
    assert spy.call_count == 1
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["adapter_name"] == "copilot-cli"
    assert call_kwargs["tested_up_to"] == "1.0.54"


def test_claude_code_cli_calls_drift_helper_in_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.3 AC-11.3.2: same for ClaudeCodeCLIAdapter."""
    spy = MagicMock(return_value=False)
    monkeypatch.setattr(
        "AgentEval._kernel.version_drift.emit_adapter_version_drift_warning_if_applicable", spy
    )

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="2.1.144 (Claude Code)\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    from AgentEval.coding_agent.claude_code_cli import ClaudeCodeCLIAdapter

    ClaudeCodeCLIAdapter()
    assert spy.call_count == 1
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["adapter_name"] == "claude-code-cli"
    assert call_kwargs["tested_up_to"] == "2.1.144"
