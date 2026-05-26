# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Binary version-drift detection for CLI adapters (Story 11.3 / PRD FR60).

Provides `emit_adapter_version_drift_warning_if_applicable()` — the shared
helper called by all 3 Tier-1 CLI adapters (`claude_code_cli`, `codex_cli`,
`copilot_cli`) at construction time AFTER `_assert_binary_version()` passes,
to fire a one-shot `AdapterVersionDriftWarning` when the detected CLI
binary is N>=2 minor versions behind the adapter's `_TESTED_UP_TO` constant.

Reuses the `AdapterVersionDriftWarning` class from Story 5.2's
`mcp/observer.py` (Story 11.3 drift check D-6 decision): single
warning class serves both MCP-SDK-drift and CLI-binary-drift use cases
— differentiated by message text. This module re-exports the class for
clean adapter import paths.

## Thread safety + process scope

The module-level `_session_drift_warned` dedupe set is **single-process
+ intra-test-session**. Concurrent pytest workers (e.g., under
`pabot --processes N` per FR40) have process-local sets — each worker
fires its own warning at most once per `(adapter_name, detected, tested_up_to)`
triple. This is acceptable per FR60 semantics: the warning is informational
+ per-process; downstream tooling (Story 5.4 WarningRecord buffers) keys
records by test_id, so duplicates across workers are naturally deduplicated
at the test-id level.

## References

- PRD FR60 (binary version drift warning).
- `docs/contracts/error-class-hierarchy.md:83` (`AdapterVersionDriftWarning`
  exit-code 0; warning, not failure).
- Story 5.2 `AdapterVersionDriftWarning` class at `mcp/observer.py:98`.
- Story 4.2 (Claude Code CLI) + Story 11.1 (Codex CLI) + Story 11.2
  (Copilot CLI) — the 3 Tier-1 CLI adapters this helper wires.
- ADR-016 §Decision L33 (no relation; cited here only to be consistent
  with the Story 11.1 + 11.2 citation discipline established in their
  reviews).
"""

from __future__ import annotations

import re
import subprocess
import warnings

# Re-export the warning class so adapters can import from this module
# without reaching into `mcp.observer` (cross-subsystem leakage).
from AgentEval.mcp.observer import AdapterVersionDriftWarning

__all__ = [
    "AdapterVersionDriftWarning",
    "emit_adapter_version_drift_warning_if_applicable",
    "reset_session_drift_dedupe",
]


# Minor-version-delta threshold per epics.md L2076 + drift check D-7.
#
# Story 11.3 copilot HIGH-2 cross-LLM review 2026-05-26 caught spec
# ambiguity: epics.md L2076 reads "more than 2 minor versions behind" —
# natural reading = `drift > 2` (= `drift >= 3`). The Story 11.3 spec
# D-7 decision resolved this as `drift >= 2` to catch more real-world
# drift (the spec author judged the spec text was imprecise + the
# practical drift-catching intent was the load-bearing semantic). The
# implementation honors the spec D-7 decision: `drift >= 2`.
#
# **Resolution recorded:** epics.md L2076 text is interpreted as "≥2
# minor versions behind" per Story 11.3 D-7. If a future operator
# prefers strict `>2`, change `_DRIFT_MINOR_THRESHOLD` to 3 + amend
# the boundary test at `test_boundary_drift_exactly_2`.
_DRIFT_MINOR_THRESHOLD = 2

# Module-level dedupe set keyed by (adapter_name, detected_version, tested_up_to).
# Single-process; pabot workers have process-local sets (see module docstring).
_session_drift_warned: set[tuple[str, str, str]] = set()

# Semver-ish regex matching the base `_assert_binary_version`'s default.
_SEMVER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _parse_version(version: str | None) -> tuple[int, int] | None:
    """Extract `(major, minor)` tuple from a version string; None on failure.

    Uses substring match (matches the base `_assert_binary_version`
    semantic) so version strings like `"codex-cli 0.133.0"` or
    `"GitHub Copilot CLI 1.0.54."` resolve correctly even with prefix
    and trailing chars.
    """
    if version is None:
        return None
    m = _SEMVER_RE.search(version)
    if m is None:
        return None
    return (int(m.group(1)), int(m.group(2)))


def reset_session_drift_dedupe() -> None:
    """Test-only helper: clear the session-dedupe set.

    Called by `tests/unit/_kernel/conftest.py` + `tests/unit/coding_agent/conftest.py`
    autouse fixtures so per-test dedupe state doesn't bleed across tests.
    Not for production use; the dedupe semantics are intentionally
    session-scoped.
    """
    _session_drift_warned.clear()


def emit_adapter_version_drift_warning_if_applicable(
    *,
    adapter_name: str,
    detected_version: str | None,
    tested_up_to: str,
    compat_min: str,
    compat_max: str | None = None,
) -> bool:
    """Emit `AdapterVersionDriftWarning` if drift exceeds threshold (Story 11.3 / FR60).

    Fires AT MOST ONCE per unique ``(adapter_name, detected_version,
    tested_up_to)`` triple per Python process — dedupe set persists
    across multiple adapter constructions in the same pytest run.

    Drift threshold (D-7): ``tested.minor - detected.minor >= 2``.
    Detected versions equal to or newer than tested do NOT fire (the
    caller likely forgot to bump ``_TESTED_UP_TO``; intentional silent
    no-op rather than a misleading "newer-than-tested" warning).

    Args:
        adapter_name: Adapter slug (e.g., ``"codex-cli"``).
        detected_version: Version string from the binary (e.g., ``"0.100.0"``).
            `None` is a no-op (the adapter's own `_assert_binary_version`
            would have raised already if the binary was unparseable).
        tested_up_to: The adapter's `_TESTED_UP_TO` constant (e.g., ``"0.133.0"``).
        compat_min: The adapter's pinned compat-range min (e.g., ``"0.100.0"``).
        compat_max: The adapter's pinned compat-range max (e.g., ``"1.0.0"``).
            Currently informational; the warning fires whenever drift
            exceeds threshold regardless of compat-max — the
            `_assert_binary_version` raise-path catches above-ceiling.

    Returns:
        ``True`` if a warning was emitted, ``False`` otherwise (under-
        threshold, dedup hit, or unparseable inputs).

    Raises:
        Never — defensive no-op on all failure modes.
    """
    if detected_version is None:
        return False
    detected = _parse_version(detected_version)
    tested = _parse_version(tested_up_to)
    if detected is None or tested is None:
        return False

    # Drift threshold check + cross-major handling (Story 11.3 copilot
    # MED-2 cross-LLM review 2026-05-26): pre-edit let the sentinel `99`
    # from `_drift_across_major` leak into the user-visible message as
    # "99 minor versions behind" — misleading. Now we branch on cross-
    # major explicitly + render a clearer drift descriptor.
    if tested[0] != detected[0]:
        if detected[0] > tested[0]:
            # Detected on a NEWER major — no warning (operator likely
            # forgot to bump _TESTED_UP_TO; intentional silent no-op).
            return False
        # Detected on a previous major — fire warning with cross-major
        # descriptor instead of the synthetic "99 minor versions" value.
        drift_descriptor = (
            f"on major version {detected[0]} while the adapter is tested "
            f"against major version {tested[0]} (drift spans a major-version "
            f"boundary; conformance fidelity may degrade significantly)"
        )
    else:
        drift = tested[1] - detected[1]
        if drift < _DRIFT_MINOR_THRESHOLD:
            return False
        drift_descriptor = f"{drift} minor versions behind the adapter's tested-up-to version"

    # Dedupe per (adapter_name, detected, tested_up_to).
    key = (adapter_name, detected_version, tested_up_to)
    if key in _session_drift_warned:
        return False

    # Compose FR60-mandated message: (a) adapter name, (b) detected,
    # (c) tested-up-to, (d) drift severity, (e) remediation.
    message = (
        f"{adapter_name}: detected CLI version {detected_version!r} is "
        f"{drift_descriptor} {tested_up_to!r} (compat range "
        f">={compat_min},<{compat_max or 'unbounded'}). "
        f"Conformance fidelity may degrade — upgrade adapter to test the "
        f"latest CLI, or pin CLI to tested version ({tested_up_to}). "
        f"Per PRD FR60 + ADR-014 (AdapterVersionDriftWarning surface)."
    )
    warnings.warn(message, AdapterVersionDriftWarning, stacklevel=3)
    _session_drift_warned.add(key)
    return True


def parse_binary_version(binary: str) -> str | None:
    """Re-run `<binary> --version` and extract the semver substring.

    Returns ``None`` on any failure (missing binary, non-zero exit,
    unparseable output). Adapters that have already passed
    `_assert_binary_version()` in `__init__` can call this safely to
    retrieve the parsed detected version for the drift-check helper.

    This is a separate Phase-1 helper because the base
    `_assert_binary_version` does the parse internally but doesn't
    return the parsed value — refactoring the base to expose it would
    touch every existing adapter. Phase-1.5: refactor the base to
    expose the parsed version + delete this re-extract helper.
    """
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    combined = (result.stdout or "") + (result.stderr or "")
    m = _SEMVER_RE.search(combined)
    if m is None:
        return None
    return m.group(0)
