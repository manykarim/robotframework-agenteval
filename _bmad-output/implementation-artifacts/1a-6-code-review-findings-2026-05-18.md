# Story 1a.6 Code Review Findings (2026-05-18)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1.

**Verdict:** **Changes Requested** — 1 HIGH + 4 MED + 4 LOW. The HIGH is critical: ci.yml's `--collect-only` sweep means the new FR42 acceptance tests get *collected* but never *executed* in CI. Locally the tests pass; the CI gate is a fake-green for assertions.

---

## Methodology

1. **Claude independent re-verification** of dev-story's 6 gates — all PASSED.
2. **Codex CLI adversarial pass** via GitHub MCP against commit `3c0d505` — fetched all 6 changed files + cross-referenced epics.md + PRD + ADRs + the actual ci.yml workflow. Caught **9 findings**.
3. **Claude spot-verified the top 3 Codex findings locally** — all confirmed.

**6th consecutive cross-LLM review where Claude solo found 0 substantive issues + Codex caught real ones.** The same-family blind spot pattern continues to be load-bearing — particularly stark this round because the HIGH-1 finding is exactly the kind of "fake-green via collect-only" issue Many's CI-log-forensics norm exists to catch.

---

## Findings

### HIGH

#### HIGH-1: ci.yml's pytest sweep still uses `--collect-only` for `tests/acceptance/tier1` — FR42 tests never execute in CI

**File:** `.github/workflows/ci.yml` — the "pytest Phase-1 collect-only sweep" step (~L80-110) iterates all 4 test dirs with `--collect-only`.

**Issue:** Story 1a.6's FR42 acceptance test landed at `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` with 6 real assertions. Locally `uv run pytest tests/acceptance/tier1 -q` runs all 6 and reports `6 passed in 0.27s`. But CI's sweep step uses `--collect-only` for ALL 4 dirs — including tier1. Result: CI **COLLECTS** the 6 tests (which is reported as "exit 0 — real tests now" by the local sweep simulation) but **NEVER RUNS THEIR ASSERTIONS**. A regression in `AgentEval.__init__` would pass CI silently.

**Why dev missed it:** local simulation `pytest --collect-only` against `tests/acceptance/tier1` exits 0 once a test file is present (collection succeeds). I interpreted exit 0 as "real test now runs" — wrong reading. Exit 0 just means "collection succeeded"; the assertions are skipped under `--collect-only`.

**Recommended fix:** Update `ci.yml` sweep step to:
- Drop `--collect-only` for `tests/acceptance/tier1` AND remove exit-5 leniency for that dir (now-required to find real tests). Continue using `--collect-only` for the other 3 dirs (they remain empty placeholders).
- Or restructure: split the sweep into 2 steps — (1) `pytest tests/unit tests/acceptance/smoke tests/unit/conventions --collect-only -q` with exit-5 leniency (3 placeholder dirs); (2) `pytest tests/acceptance/tier1 -q` without leniency (real tests).

---

### MEDIUM

#### MED-2: `_get_rf_test_id()` method defined but never called

**File:** `src/AgentEval/__init__.py` L142-152 (the `_get_rf_test_id` method)

**Issue:** AC-1a.6.8 says: "The `AgentEval.__init__` MUST internally call `_get_rf_test_id()` lazily". But `__init__` (L114-130) never references the method. It's defined as a public-ish (underscored) method but completely unreachable from the class's own constructor flow. AC-1a.6.8 not satisfied.

**Recommended fix:** Either (a) call `self._get_rf_test_id()` from `__init__` and store the result as `self._rf_test_id` (lazy-property pattern — value is `None` Phase-1, populated by Story 5.1's listener context read); (b) remove `_get_rf_test_id()` from this story's scope + update AC-1a.6.8 + the story's docstring to remove the claim. **Option (a) is recommended** — provides the hook point Story 5.1 wires.

---

#### MED-3: No `.robot` smoke test verifying RF library discovery + keyword exposure

**Files:** `tests/` (no `.robot` files); `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` (Python-only)

**Issue:** All 6 acceptance tests instantiate `AgentEval` directly in Python. Nothing verifies that:
- `Library    AgentEval` resolves in a `.robot` file.
- The `Get Effective Config` keyword name is actually discoverable via Robot Framework's keyword discovery.
- The `@keyword(name="Get Effective Config")` decorator works as expected with PythonLibCore / RF static-library discovery.

A regression in the `@keyword` decorator or class-name resolution would silently break the RF use case while Python-only tests still pass.

**Recommended fix:** Add `tests/acceptance/smoke/test_agenteval_library.robot` with one test case:
```robot
*** Settings ***
Library    AgentEval

*** Test Cases ***
AgentEval Library Loads And Get Effective Config Works
    ${config}=    Get Effective Config
    Should Be Equal    ${config["provider"]}    litellm
```

This is also a natural fit for `tests/acceptance/smoke/` (currently empty) — verifies the smoke-path that Story 1a.6 promised.

---

#### MED-6: SECURITY.md NFR-SEC-05 still says `telemetry=False` "eliminates all OTel listener egress" — but no listener exists yet

**File:** `SECURITY.md` NFR-SEC-05 section (~L86)

**Issue:** Post-Story-1a.6 update, the line "The library `__init__(telemetry=False)` eliminates all OTel listener egress" is in PRESENT TENSE. But:
- No OTel listener exists yet (Epic 5 Story 5.1 ships it).
- `telemetry=False` is stored on `self._telemetry` but does nothing else.
- The strong guarantee "eliminates all egress" only holds once Story 5.1 lands.

Codex flagged this as overstating Phase-1 reality.

**Recommended fix:** Rephrase: "The library `__init__(telemetry=False)` is wired by Story 1a.6 as a control-surface kwarg (Phase-1 stores the value; full listener-disable enforcement lands in Epic 5 Story 5.1 alongside the OTel listener itself). When fully wired, setting `telemetry=False` will eliminate all OTel listener egress."

---

#### MED-8: Story 1a.6 implementation artifact has claim-vs-reality drift on test count + CI execution

**File:** `_bmad-output/implementation-artifacts/1a-6-wire-fr42-fr43-fr44-library-defaults-stability-exit-criteria-doc-stubs.md`

**Issues:**
- Task 4 description: "Test: `def test_ac_fr42_defaults_with_no_kwargs() ...` + Test: `def test_ac_fr42_defaults_with_kwarg_overrides()`" — promises 2 tests. Actually wrote 6 tests. (Not a bug, but doc drift.)
- Dev Agent Record / File List section mentions "2 tests pass" / "FR42 6/6 pass" inconsistently — should be 6 throughout.
- Implication that CI "exercises exit-0 path for tests/acceptance/tier1" — actually CI runs `--collect-only` per HIGH-1; the exit-0 path is exercised LOCALLY only.

**Recommended fix:** Align the story file's Dev Notes + Completion Notes + Change Log with the actual 6-test + collect-only-CI reality. Update narrative once HIGH-1 is patched.

---

### LOW

#### LOW-4: `mcp_per_test` docstring cites "ADR-009 + architecture L314" but `"suite"` mode is architecture-only

**File:** `src/AgentEval/__init__.py` L75-83 (docstring) + `docs/contracts/stability-surface.md` "AgentEval Library Surface" subsection

**Issue:** ADR-009 §Decision says `mcp_per_test: bool = True` (only True/False ratified). The third mode `"suite"` is architecture L314 + NFR-PERF-03d additions — NOT in ADR-009 proper. Current citation conflates them.

**Recommended fix:** Update docstring + stability-surface entry: "True/False per ADR-009; `"suite"` mode per architecture L314 + NFR-PERF-03d (recipe-5 dogfood-CI ergonomics)".

---

#### LOW-5: stability-surface.md Purpose section says "Phase-1 baseline contains only the sandbox-related elements" — outdated post-Story-1a.6

**File:** `docs/contracts/stability-surface.md` L10 + L18 (Scope section)

**Issue:** The intro sections were written by Story 1a.4 + scoped-narrowed by Story 1a.5 to say "only sandbox surface". Story 1a.6 ADDS the AgentEval Library surface but didn't update the intro. Result: contradicts the new "AgentEval Library Surface" subsection.

**Recommended fix:** Update Purpose + Scope intros to: "Phase-1 baseline contains the AgentEval Library surface (Story 1a.6) + the sandbox surface (Story 1a.4); other public elements are added incrementally by epic-owning stories".

---

#### LOW-7: exit-criteria-0x-to-1x.md mentions "all 11 docs/contracts/ files" — should be 12

**File:** `docs/contracts/exit-criteria-0x-to-1x.md` L45 ("Additional Phase-1-close documentation requirements")

**Issue:** docs/contracts/ has 12 files (11 contracts + README.md). The criterion text was probably written before counting the README.

**Recommended fix:** Update to "all 11 contract files + README.md" OR drop the hardcoded count: "all `docs/contracts/*.md` files have populated content".

---

#### LOW-9: Story 1a.6 artifact says "PythonLibCore / dynamic-library convention" for RF discovery — wrong model

**File:** `_bmad-output/implementation-artifacts/1a-6-wire-fr42-fr43-fr44-library-defaults-stability-exit-criteria-doc-stubs.md` (Dev Notes §Robot Framework Library Convention)

**Issue:** RF's static-library discovery (class with same name as the module) is what this implementation uses — NOT PythonLibCore (which is a base class for dynamic libraries) and NOT dynamic-library convention. Misleading for future maintainers.

**Recommended fix:** Replace with: "RF's **static-library discovery model**: when `Library    AgentEval` is encountered in a `.robot` file, RF imports the `AgentEval` module and looks for a class with the same name as the module. `src/AgentEval/__init__.py` exports the `AgentEval` class; RF instantiates it with the `Library` directive's kwargs. Static libraries auto-register all `@keyword`-decorated methods as keywords."

---

## Triage summary

| Severity | Count | Findings |
|---|---|---|
| HIGH | 1 | HIGH-1 (tier1 still --collect-only in CI) |
| MED | 4 | MED-2 (_get_rf_test_id unused), MED-3 (no RF smoke test), MED-6 (SECURITY.md overstates), MED-8 (story artifact drift) |
| LOW | 4 | LOW-4 (ADR-009 cite), LOW-5 (stability-surface intro stale), LOW-7 (11 vs 12 contracts), LOW-9 (PythonLibCore wording) |

**Cross-LLM coverage:** Claude 0 / Codex 9. 6th consecutive demonstration of the same-family blind spot pattern. HIGH-1 specifically is the kind of issue the CI-log-forensics norm exists to catch — Codex caught what the dev's "local pytest passes" framing made invisible.

## Recommended action

Apply HIGH-1 + MED-2 + MED-3 + MED-6 + MED-8 + LOW-5 + LOW-7 + LOW-9 (~30-line patch set across 6 files). LOW-4 is wording-only — fix at same time as LOW-5 + LOW-7.

The biggest call is HIGH-1's CI fix — it changes Story 1a.2's `ci.yml` collect-only sweep to actually execute tier1 tests. This is the right move: tier1 now has real content; the leniency was Phase-1-stop-gap behavior + has paid off (allowed Story 1a.2 → 1a.6 to ship without empty-test-dir CI red). Time to tighten.
