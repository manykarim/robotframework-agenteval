# Story 11.3 — Kilo Adversarial Review Findings
**Artifact:** story-11-3  
**Reviewer:** kilo/minimax-M2.7 (Tier 3 fallback)  
**Date:** 2026-05-26

---

## HIGH — correctness, regression risk, FR60 compliance

### H-1 — D-2 catalog gate violation: `DF-11.3-S1` in code but NOT in carry-overs catalog

**File:line:**
- `src/AgentEval/coding_agent/claude_code_cli.py:456` (comment)
- `src/AgentEval/coding_agent/codex_cli.py:491` (comment)
- `src/AgentEval/coding_agent/copilot_cli.py:528` (comment)

**Finding:** All 3 adapter files contain the inline comment `DF-11.3-S1 tracks automated upstream-probe` referencing the Phase-1.5 carry-over for automated `_TESTED_UP_TO` upstream-probing. Per D-2 from the Story 11.3 spec (47th `feedback_spec_vs_ratified_doc_precheck` use): "Any new `DF-X-SY` reference MUST be in `docs/phase-1-5-carry-overs.md` BEFORE merge." `grep "DF-11.3-S1" docs/phase-1-5-carry-overs.md` returns zero results. The reference exists in live code but the catalog row does not.

**Concrete fix:** Add `DF-11.3-S1` to `docs/phase-1-5-carry-overs.md` before merge — the row can reference the description from the Story 11.3 spec L68: automated probe of upstream npm/PyPI for latest release to auto-bump `_TESTED_UP_TO`.

**Severity:** HIGH — catalog gate is a per-story hard contract (28th consecutive application); deviation is a process violation.

---

### H-2 — `AdapterVersionDriftWarning` docstring inaccurate after re-use

**File:line:** `src/AgentEval/mcp/observer.py:98-107`

**Finding:** The class docstring reads: "Warned when the installed **mcp SDK version** is outside the tested range." Story 11.3 re-uses this same class for CLI binary version drift (a structurally different concern — tested CLI binary vs tested SDK version). The docstring does not mention the CLI-binary-drift use case. An operator reading the docstring would not understand why a `claude-code-cli` adapter construction emits this warning.

**Concrete fix:** Amend the docstring to cover both surfaces. Suggested rewrite at `observer.py:98`:
```python
class AdapterVersionDriftWarning(UserWarning):
    """Warned when a version outside the tested range is detected.

    Two use cases:
    - **MCP SDK drift** (Story 5.2): installed `mcp` SDK version is outside
      the observer's tested range (`_TESTED_MCP_VERSION_FLOOR/CEILING`).
    - **CLI binary drift** (Story 11.3 / PRD FR60): detected CLI binary version
      is within the adapter's pinned compat range but >=2 minor versions
      behind the adapter's `_TESTED_UP_TO` constant.

    Per ADR-004 Consequences + Story 0.1 spike findings §Limitations: the
    observer accesses ``Server.request_handlers`` + ``FastMCP._mcp_server``,
    both technically internal in the mcp SDK. A major-version bump could
    replace dict-dispatch with a closed registration mechanism. This
    warning gives operators advance notice + a paper trail when the
    coupling breaks in production.
    """
```

**Severity:** HIGH — FR60 mandates accurate messaging; a docstring that misleads about warning scope is a correctness defect.

---

## MED — process discipline, hygiene

### M-1 — `parse_binary_version` causes 4 subprocess calls per adapter construction in integration tests

**File:line:** `tests/unit/kernel/test_version_drift.py:909-928` (copilot test body); general architectural concern

**Finding:** The three integration tests (`test_codex_cli_calls_drift_helper_in_init` + copilot + claude_code) call `parse_binary_version(binary)` to populate `detected_version`. In production, each adapter `__init__` chains:
1. `_assert_binary_version()` → 1 subprocess call
2. `parse_binary_version()` → 1 more subprocess call

Each integration test must therefore mock BOTH calls. The tests implement this correctly — `_fake_run` intercepts `[binary, "--version"]` and returns the mock. However, this establishes a fragile pattern: if any future adapter adds a third `--version` caller (e.g., a health-check in `run()`), the tests silently miss it.

**Concrete fix (MED, not a patch requirement now):** Phase-1.5 AC-11.3.5 says: "refactor the base `_assert_binary_version()` to expose the parsed version + delete this re-extract helper." Tracking this in the same DF-11.3-S1 carry-over is the correct Phase-1.5 resolution. No patch now — tracked.

**Severity:** MED (architectural debt, not a bug in current tests).

---

### M-2 — Autouse fixture ordering in `tests/unit/coding_agent/conftest.py` — reset BEFORE version mocks

**File:line:** `tests/unit/coding_agent/conftest.py:82-94`

**Finding:** `_reset_version_drift_dedupe` is declared at lines 82-94, BEFORE `mock_codex_version` at lines 97-118. Pytest applies autouse fixtures in declaration order. This means `_reset_version_drift_dedupe` clears the dedupe set BEFORE `mock_codex_version` runs — correct behavior (tests always start with a clean dedupe state). However, if the ordering were ever accidentally reversed (dedupe reset as last autouse), the `mock_codex_version` output might itself trigger drift warnings in an earlier test that contaminated the dedupe state before later tests run. No actual bug today — ordering corrected.

**Concrete fix:** No immediate patch needed; add a comment to `tests/unit/_kernel/conftest.py` noting that `_reset_version_drift_dedupe` should be the FIRST autouse fixture so it runs before any version mocks that might trigger warnings.

**Severity:** MED (prevention of future ordering mistake via documentation).

---

## LOW — wording, style

### L-1 — `compat_max` param is informational but documented as non-functional

**File:line:** `src/AgentEval/_kernel/version_drift.py:129-132`

**Finding:** The `compat_max` parameter is passed to the function but never used in any gating logic. The docstring accurately describes this ("Currently informational"). The message includes it in the compat-range display (`compat range >={compat_min},<{compat_max}`), which is useful. No bug; purely informational.

**Severity:** LOW — works-as-documented; the design decision (defensive no-op on compat_max since `_assert_binary_version` handles above-ceiling) is correct. Flagged for awareness only.

---

## UPSTREAM Verification (D-1 through D-10)

| D-# | Requirement | Verdict |
|-----|-------------|---------|
| D-2 | Any `DF-X-SY` in new code → carry-overs catalog | **FAIL** — `DF-11.3-S1` found in 3 adapter files; not in catalog (H-1 above) |
| D-3 | Module-level `_session_drift_warned` has thread-safety paragraph | **PASS** — `version_drift.py:242-251` module docstring documents single-process + pabot worker isolation |
| D-4 | ≥10 tests matching `grep "^def test_"` | **PASS** — `grep "^def test_" tests/unit/kernel/test_version_drift.py` returns 16 (exceeds AC minimum) |
| D-6 | `AdapterVersionDriftWarning` re-used from `mcp/observer.py` | **PASS** — imported at `version_drift.py:274`; class re-exported in `__all__` at line 276 |
| D-7 | Drift threshold = `tested.minor - detected.minor >= 2` | **PASS** — `_DRIFT_MINOR_THRESHOLD = 2` at line 285; drift calculation at line 369 matches |
| D-10 | Helper call in `__init__` AFTER `_assert_binary_version` | **PASS** — code inspection confirms order: `_assert_binary_version` lines 463/498/535; helper call lines 470/507/542 |

---

## Summary

| # | Severity | Finding |
|---|----------|---------|
| H-1 | HIGH | `DF-11.3-S1` inline reference in 3 adapter files violates D-2 catalog gate — missing from `docs/phase-1-5-carry-overs.md` |
| H-2 | HIGH | `AdapterVersionDriftWarning` docstring at `observer.py:98` describes MCP-SDK drift only; does not acknowledge CLI binary drift re-use case |
| M-1 | MED | Double-subprocess-call architecture for version extraction documented as Phase-1.5 refactor target (no patch now) |
| M-2 | MED | Fixture ordering is currently correct but fragile; documentation addition recommended |
| L-1 | LOW | `compat_max` informational — no defect, flagged for awareness |

**Recommended patches before merge:** H-1 (add catalog row) + H-2 (update docstring). M-1 and M-2 are Phase-1.5 candidates, not merge blockers.
