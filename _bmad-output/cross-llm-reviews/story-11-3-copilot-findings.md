# Story 11.3 — AdapterVersionDriftWarning Fully Wired — Copilot Adversarial Review Findings

**Reviewer:** GitHub Copilot (Claude Sonnet 4.6)
**Date:** 2026-05-26
**Diff source:** `_bmad-output/cross-llm-reviews/story-11-3-diff.patch`

---

## HIGH

### HIGH-1: Catalog gate violated — DF-11.3-S1 referenced in production code but C78 row is absent from `docs/phase-1-5-carry-overs.md`

**Files + lines:**
- `src/AgentEval/coding_agent/codex_cli.py` — comment `DF-11.3-S1 tracks automated upstream-probe.`
- `src/AgentEval/coding_agent/claude_code_cli.py` — same comment
- `src/AgentEval/coding_agent/copilot_cli.py` — same comment
- `docs/contracts/stability-surface.md` L113 — "Promotion to `stable` after Phase-1.5 settles the automated `_TESTED_UP_TO` upstream-probe path (DF-11.3-S1)."

**Problem:** The story spec itself (Task 10, `11-3-adapterversiondriftwarning-fully-wired.md:132`) mandates "Carry-over catalog gate UPSTREAM (28th consecutive): surface DF-11.3-S1 if added." `DF-11.3-S1` is referenced in 3 production files + 1 contract doc, but `docs/phase-1-5-carry-overs.md` contains **zero** matches for `DF-11.3` and the total-row count remains 77 (the Story 11.2 close count). The `feedback_carry_over_catalog_gate` rule (27 consecutive prior applications, 100% catch rate) is violated.

**Fix:** Add C78 row to `docs/phase-1-5-carry-overs.md`:
```
| **C78** | **Phase-1.5: Automated `_TESTED_UP_TO` upstream-probe for Tier-1 CLI adapters (`DF-11.3-S1`).** Story 11.3 hardcodes `_TESTED_UP_TO` to the version current at story-authoring time. Phase-1.5: poll npm/PyPI for the latest release cadence of each CLI binary + auto-bump `_TESTED_UP_TO` in a CI-gate script to keep drift warnings accurate. | Story 11.3 `_TESTED_UP_TO` constants — story-authoring-time pins | maintainability | S | TBD | CI script probes each CLI's package registry + opens a PR to bump `_TESTED_UP_TO` + `_DRIFT_MINOR_THRESHOLD` trigger window; confirm via unit test that bumped constants produce sensible drift-threshold behaviour. |
```
Update the total-row count from 77 to 78.

---

### HIGH-2: Drift threshold off-by-one vs epics.md root AC (D-7)

**File + line:** `src/AgentEval/_kernel/version_drift.py`, line 66 (`_DRIFT_MINOR_THRESHOLD = 2`) + line 151 (`if drift < _DRIFT_MINOR_THRESHOLD`).

**Problem:** `epics.md` L2076 (the root AC) reads: "the detected CLI version is within the pinned compat range **BUT more than 2 minor versions behind**". Natural reading: `drift > 2` i.e., fires at drift ≥ 3. The implementation sets `_DRIFT_MINOR_THRESHOLD = 2` and fires when `drift >= 2` — meaning it **fires at drift = 2** (e.g., `detected = 0.131.0`, `tested = 0.133.0`), which the root AC says should be silent.

The story spec D-7 re-states the threshold as `>= 2`, but D-7 is a derived interpretation: it cites the same L2076 text and resolves it as `>= 2`. The module docstring + `stability-surface.md` both reflect `>=2`. There is an observable gap: no test exercises `drift = 2` exactly, so the off-by-one is not caught by the test suite either way.

**Concrete fix options:**
1. If intent is truly `>= 2` (fire at drift of 2 or more): amend `epics.md` L2076 to read "**at least 2** minor versions behind" to remove the ambiguity, and add a test that confirms the warning fires at `drift = 2`.
2. If intent is `> 2` (strict): change `_DRIFT_MINOR_THRESHOLD = 2` → `_DRIFT_MINOR_THRESHOLD = 3` and add a test confirming silence at `drift = 2`.

Either way, add `test_no_warning_when_drift_is_exactly_at_threshold_boundary` (or `test_warning_fires_at_exact_threshold`) to pin the boundary behaviour.

---

## MED

### MED-1: `AdapterVersionDriftWarning` class docstring is MCP-SDK-specific after Story 11.3 re-use (D-6 follow-through gap)

**File + line:** `src/AgentEval/mcp/observer.py`, lines 98–107.

**Problem:** D-6 decision is that Story 5.2's `AdapterVersionDriftWarning` is re-used for CLI binary drift, "differentiated by message text." The `version_drift.py` module docstring documents this dual-use correctly. However, the class docstring at `mcp/observer.py:99–107` still reads entirely as MCP-SDK-drift specific:

> "Warned when the installed mcp SDK version is outside the tested range. … the observer accesses `Server.request_handlers` + `FastMCP._mcp_server`, both technically internal in the mcp SDK."

A consumer catching `AdapterVersionDriftWarning` and reading its docstring via `help()` or IDE hover gets a misleading picture — there is no mention of CLI binary drift. The `__doc__` string is the canonical consumer-facing API description per FR64.

**Fix:** Amend the class docstring to cover both use cases, e.g.:

```python
class AdapterVersionDriftWarning(UserWarning):
    """Warned when a version dependency is outside the adapter's tested range.

    Two use cases share this class (Story 11.3 D-6 decision):

    1. **MCP SDK drift** (Story 5.2): the installed `mcp` SDK version differs from
       the tested range; the observer's ``request_handlers`` dict-wrap pattern
       may be invalidated by a major-version SDK bump (per ADR-004 Consequences).

    2. **CLI binary drift** (Story 11.3 / FR60): a Tier-1 CLI adapter's detected
       binary version is ≥N minor versions behind its ``_TESTED_UP_TO`` constant;
       conformance fidelity may degrade.

    Both cases: exit-code 0 (informational warning, not a failure per
    ``docs/contracts/error-class-hierarchy.md``).
    """
```

---

### MED-2: Cross-major drift message reports synthetic "99 minor versions behind" — misleading to consumers

**File + line:** `src/AgentEval/_kernel/version_drift.py`, lines 188–192 (`_drift_across_major`) + line 164 (message f-string uses `{drift}`).

**Problem:** When `detected.major < tested.major` (e.g., `detected = 1.99.0`, `tested = 2.0.0`), `_drift_across_major` returns the sentinel `99` "conservatively". The warning message then renders as:

> `"example: detected CLI version '1.99.0' is 99 minor versions behind the adapter's tested-up-to version '2.0.0' …"`

"99 minor versions behind" is factually wrong (only 1 minor version ago within the major) and will confuse operators who attempt to understand the urgency of the drift. The sentinel value is visible in the warning message, leaking an implementation detail as user-visible text.

**Fix:** Add a cross-major code path in `emit_adapter_version_drift_warning_if_applicable` that produces a distinct message when majors differ, instead of letting the sentinel flow into the generic format string:

```python
if tested[0] != detected[0]:
    is_cross_major = True
    drift_desc = f"on major version {detected[0]} while adapter is tested against major version {tested[0]}"
else:
    is_cross_major = False
    drift = tested[1] - detected[1]
    drift_desc = f"{drift} minor versions behind"
```

Or at minimum, suppress the sentinel from the numeric slot and spell it out as "a previous major version".

---

## LOW

### LOW-1: Double subprocess call — `parse_binary_version` re-runs `<binary> --version` after `_assert_binary_version` already ran it

**File + line:** `src/AgentEval/_kernel/version_drift.py`, lines 195–225; call sites at `claude_code_cli.py:204`, `codex_cli.py:253`, `copilot_cli.py:222`.

**Problem:** Each adapter `__init__` makes **two** `<binary> --version` subprocess calls: one inside `_assert_binary_version`, one inside `parse_binary_version`. The docstring acknowledges this and defers refactoring to Phase-1.5. The risk of a version change between calls is negligible. However, on slow filesystems or PATH-resolution edge cases this doubles the construction latency + doubles the attack surface for `FileNotFoundError`/`TimeoutExpired` during init. Flagged for Phase-1.5 tracking.

**Fix (Phase-1.5, already in DF-11.3-S1 / C78 scope):** Refactor `_assert_binary_version` to return the parsed version string. Adapters receive it directly, eliminating the second subprocess call. Remove `parse_binary_version` once all call sites are updated.

---

### LOW-2: Missing boundary test for drift = 2 (the exact threshold value)

**File + line:** `tests/unit/kernel/test_version_drift.py` — no test covers `drift = 2` exactly.

**Problem:** The test suite covers `drift = 1` (no-op), `drift = 3` (fires), and `drift = 33` (fires across-adapter dedupe). The exact boundary — `drift = 2` — is untested. Given the ambiguity in the root AC ("more than 2" vs `>= 2`), this is the most important case to pin.

**Fix:** Add:

```python
def test_boundary_drift_exactly_2() -> None:
    """tested.minor - detected.minor = 2 — confirms the exact threshold boundary."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", AdapterVersionDriftWarning)
        emitted = emit_adapter_version_drift_warning_if_applicable(
            adapter_name="codex-cli",
            detected_version="0.131.0",
            tested_up_to="0.133.0",
            compat_min="0.100.0",
            compat_max="1.0.0",
        )
    # Fix the expected value after resolving HIGH-2 threshold ambiguity:
    assert emitted is True   # if threshold is >= 2
    # assert emitted is False  # if threshold is > 2 (>= 3)
```

---

## Checklist Verdicts (per review prompt)

| D-# | Verdict |
|-----|---------|
| D-2 (catalog-gate) | **FAIL** — `DF-11.3-S1` inline in 3 adapter files + 1 doc, C78 row absent. See HIGH-1. |
| D-3 (thread-safety paragraph) | **PASS** — module docstring §"Thread safety + process scope" is present and substantive. |
| D-4 (≥10 tests grep) | **PASS** — `grep "^def test_"` yields 16 functions. |
| D-6 (AdapterVersionDriftWarning re-use, not duplicate) | **PASS (class)** — correct re-export from `mcp/observer.py`. **PARTIAL FAIL (docstring)** — class docstring not updated. See MED-1. |
| D-7 (drift threshold) | **AMBIGUOUS** — implementation is internally consistent at `>= 2`, but epics.md L2076 reads "more than 2" (strict `> 2`). See HIGH-2. |
| D-10 (helper after `_assert_binary_version`) | **PASS** — all 3 adapters call `emit_adapter_version_drift_warning_if_applicable` on the line immediately after `_assert_binary_version`. |
