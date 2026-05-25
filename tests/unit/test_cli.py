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

"""Unit tests for `AgentEval.cli` FR50 exit-code mapping (Story 8a.1 AC-8a.1.7).

Covers the 6 enumerated unit-test cases plus a coverage assertion:

1. Each of the 4 epics.md L1660 pinned codes.
2. Sysexits-aligned codes (77/78/75/70/65/69).
3. Unknown error_code → fallback (70).
4. Empty / None error_code → fallback (70).
5. AdapterVersionDriftWarning (warning class) → 0.
6. Coverage: every leaf in error-class-hierarchy.md has an entry.
"""

from __future__ import annotations

import pytest

from AgentEval.cli import (
    _ERROR_EXIT_CODES,
    EXIT_CODE_FALLBACK,
    error_code_to_exit_code,
)


@pytest.mark.parametrize(
    ("error_code", "expected_exit"),
    [
        # 4 epics.md L1660 pinned codes (AC-8a.1.7 #1).
        ("POLLING_DISALLOWED", 65),
        ("COST_EXCEEDED", 66),
        ("INCOMPLETE_TRACE", 67),
        ("UNSUPPORTED_MCP_VERSION", 68),
    ],
)
def test_pinned_codes(error_code: str, expected_exit: int) -> None:
    """AC-8a.1.7 #1: the 4 codes pinned by epics.md L1660 resolve correctly."""
    assert error_code_to_exit_code(error_code) == expected_exit


@pytest.mark.parametrize(
    ("error_code", "expected_exit"),
    [
        # Sysexits-aligned codes (AC-8a.1.7 #2).
        ("SANDBOX_REQUIRED", 77),  # EX_NOPERM
        ("VALIDATE_OPERATOR_DISALLOWED", 77),  # EX_NOPERM — Story 6.3 IMPLEMENTED leaf
        ("RUNTIME_BUDGET_EXCEEDED", 75),  # EX_TEMPFAIL
        ("UNSUPPORTED_BINARY_VERSION", 78),  # EX_CONFIG
        ("ADAPTER_DISCOVERY_ERROR", 78),  # EX_CONFIG
        ("MCP_CONNECTION_LOST", 69),  # sysexits-extended
        ("TIER_VIOLATION", 70),  # EX_SOFTWARE
        ("INVALID_SKILL_FRONTMATTER", 65),  # EX_DATAERR
        ("INVALID_SUBAGENT_DEFINITION", 65),
        ("INVALID_HOOK_CONFIG", 65),
        ("INVALID_MCP_SERVER_CONFIG", 65),
        ("INVALID_MCP_TOOL_SCHEMA", 65),
        ("INVALID_SCENARIO_YAML", 65),
        ("INVALID_DISCOVERABILITY_TASKS", 65),
        # Story 7.2 leaves (drift caught by Story 8a.1 self-review 2026-05-25).
        ("INVALID_SKILL_DISCOVERABILITY_TASKS", 65),  # EX_DATAERR.
        ("SKILL_DID_NOT_ACTIVATE", 70),  # EX_SOFTWARE — Integrity family default.
    ],
)
def test_sysexits_aligned_codes(error_code: str, expected_exit: int) -> None:
    """AC-8a.1.7 #2: sysexits-aligned codes for the remaining 16 leaves."""
    assert error_code_to_exit_code(error_code) == expected_exit


def test_unknown_error_code_falls_back() -> None:
    """AC-8a.1.7 #3: unknown error_code → fallback (70 EX_SOFTWARE)."""
    assert error_code_to_exit_code("TOTALLY_UNKNOWN_CODE") == EXIT_CODE_FALLBACK
    assert EXIT_CODE_FALLBACK == 70


def test_empty_and_none_fallback() -> None:
    """AC-8a.1.7 #4: empty / None error_code → fallback."""
    assert error_code_to_exit_code("") == EXIT_CODE_FALLBACK
    assert error_code_to_exit_code(None) == EXIT_CODE_FALLBACK


def test_adapter_version_drift_warning_exit_zero() -> None:
    """AC-8a.1.7 #5: AdapterVersionDriftWarning (warning class) → 0.

    Code is `ADAPTER_VERSION_DRIFT` per `error-class-hierarchy.md` L83 (NOT
    `ADAPTER_VERSION_DRIFT_WARNING` despite the class name — the contract
    drops the `_WARNING` suffix).
    """
    assert error_code_to_exit_code("ADAPTER_VERSION_DRIFT") == 0


def test_table_covers_all_21_error_classes() -> None:
    """AC-8a.1.7 #6: coverage — table has all 21 leaves currently in errors.py.

    Re-derived 2026-05-25 from `src/AgentEval/errors.py` `error_code` declarations
    via `grep -nE '^    error_code: ClassVar\\[str\\] = ' src/AgentEval/errors.py`:
    19 leaves in `errors.py` + `SANDBOX_REQUIRED` from
    `src/AgentEval/security/policy.py` (or planned ADR-018 stub per
    `error-class-hierarchy.md` L66) + `ADAPTER_VERSION_DRIFT` from contract L83
    (no in-tree class until Epic 11 Story 11.3). Total: 21 codes.

    `error-class-hierarchy.md` L52-L56 still says "19 leaves" — that count is
    STALE; Story 7.2 added `InvalidSkillDiscoverabilityTasksError` +
    `SkillDidNotActivateError` without amending the contract count.
    Story 8a.1 self-review caught + amended (fix-the-losing-source-NOW).

    If a new leaf lands in errors.py without updating this test + the contract
    table, this test surfaces the gap (both `missing` and `extra` assertions
    fire on mismatch).
    """
    # Sources for the expected set (re-derive at test-author time, not at
    # runtime — runtime import would defeat the cross-check):
    # - `error-class-hierarchy.md` L66 (`SANDBOX_REQUIRED`, planned).
    # - `error-class-hierarchy.md` L67 (`VALIDATE_OPERATOR_DISALLOWED`).
    # - `error-class-hierarchy.md` L73-L84 (10 Compat + Budget codes).
    # - `error-class-hierarchy.md` L90-L99 (10 Integrity codes).
    # - `errors.py` L849 + L884 (2 Story-7.2 additions; contract amended by
    #   Story 8a.1 fix-the-losing-source-NOW 2026-05-25 — `error-class-
    #   hierarchy.md` L100-L101 now lists them).
    expected_codes = {
        # Safety (2)
        "SANDBOX_REQUIRED",
        "VALIDATE_OPERATOR_DISALLOWED",
        # Budget (2)
        "COST_EXCEEDED",
        "RUNTIME_BUDGET_EXCEEDED",
        # Compat (5)
        "UNSUPPORTED_MCP_VERSION",
        "UNSUPPORTED_BINARY_VERSION",
        "ADAPTER_DISCOVERY_ERROR",
        "ADAPTER_VERSION_DRIFT",
        "MCP_CONNECTION_LOST",
        # Integrity (10 in contract + 2 Story 7.2 additions = 12)
        "POLLING_DISALLOWED",
        "INCOMPLETE_TRACE",
        "TIER_VIOLATION",
        "INVALID_SKILL_FRONTMATTER",
        "INVALID_SUBAGENT_DEFINITION",
        "INVALID_HOOK_CONFIG",
        "INVALID_MCP_SERVER_CONFIG",
        "INVALID_MCP_TOOL_SCHEMA",
        "INVALID_SCENARIO_YAML",
        "INVALID_DISCOVERABILITY_TASKS",
        "INVALID_SKILL_DISCOVERABILITY_TASKS",  # Story 7.2.
        "SKILL_DID_NOT_ACTIVATE",  # Story 7.2.
    }
    actual_codes = set(_ERROR_EXIT_CODES.keys())
    missing = expected_codes - actual_codes
    extra = actual_codes - expected_codes
    assert not missing, f"missing from _ERROR_EXIT_CODES: {missing}"
    assert not extra, f"unexpected entries in _ERROR_EXIT_CODES: {extra}"
    assert len(actual_codes) == 21
