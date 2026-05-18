# Story 1a.6: Wire FR42 + FR43 + FR44 Library Defaults + Stability/Exit-Criteria Doc Stubs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **library consumer**,
I want **the `AgentEval` Robot Framework Library `__init__` wired with the 9 PRD FR42 + FR11b defaults** (incl. `allow_validate_operator=False` per FR43 + `telemetry=False` opt-out per FR44 + `mcp_per_test=True` per ADR-009), **a `Get Effective Config` accessor keyword that returns the resolved config**, **substantive Phase-1 initial labels in `docs/contracts/stability-surface.md`** (`AgentEval` class + its public keyword surface so far), and **substantive Phase-1 stub content in `docs/contracts/exit-criteria-0x-to-1x.md`** (the 4 promotion criteria placeholders with rationale),
so that **the library has a coherent first-import experience from Day 1, the `stability-surface.md` + `exit-criteria-0x-to-1x.md` contracts (skeleton + initial content) become consumable to contributors, and the wiring + accessor is in place for Epic 5 (telemetry enforcement) + Epic 6 (validate-operator gate enforcement) to build on**.

## Acceptance Criteria

> **Pre-create-story drift check (6th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-18):** 5 drifts caught in Story 1a.6 spec vs ratified sources. Per Many's 2026-05-18 ratification, ALL 5 resolved by honoring ratified sources (PRD FR42 + ADR-009 + Story 1a.4 stability-surface.md + architecture L1423 + FR11b). Updated `epics.md` Story 1a.6 AC (L812-822) + `.env.example` `AGENTEVAL_MCP_PER_TEST` pre-authoring. Canonical defaults set, label vocabulary, slug all locked.

1. **AC-1a.6.1 — `AgentEval` class wired with 9 FR42 + FR11b defaults in `__init__`.** Update `src/AgentEval/__init__.py` (currently empty per Story 1a.1 baseline) to define the `AgentEval` Robot Framework Library class with `__init__(self, *, provider="litellm", telemetry=True, trace_backend="memory", allow_validate_operator=False, default_temperature=0.0, mcp_per_test=True, allow_external_mcp_blind=False, max_cost_usd=5.00, max_runtime_seconds=None)`. All 9 parameters MUST be **keyword-only** (`*` before them). Type annotations on all parameters per `docs/contracts/coding-conventions.md`. Type signature for `mcp_per_test`: `bool | Literal["suite"]` per architecture L314's 3-mode design.

2. **AC-1a.6.2 — Configuration precedence: kwarg → env var → `.env` → defaults (FR41).** When the library is instantiated:
   - Phase-1 implementation supports kwarg-only precedence (highest wins).
   - Env var precedence (FR41) lands via Epic 1b's `_kernel/context.py` (FR42 wiring here; env precedence wiring there).
   - Phase-1 status: kwarg-only effective resolution — document this Phase-1 boundary in the Library docstring + `stability-surface.md`.

3. **AC-1a.6.3 — `Get Effective Config` keyword exposed.** The `AgentEval` class MUST expose a `Get Effective Config` RF keyword that returns a `dict` containing all 9 resolved config values. Verifiable via:
   ```robot
   Library    AgentEval    allow_validate_operator=True    telemetry=False
   ${config}=    Get Effective Config
   Should Be Equal    ${config["allow_validate_operator"]}    ${True}
   Should Be Equal    ${config["telemetry"]}    ${False}
   Should Be Equal    ${config["provider"]}    litellm
   ```

4. **AC-1a.6.4 — Both Library + non-RF invocation paths work.** The `AgentEval` class is invokable as:
   - **Robot Framework Library**: `Library    AgentEval    <kwargs>` from a `.robot` file (RF discovers the class via the **static-library discovery model** — when `Library    AgentEval` is encountered, RF imports the `AgentEval` module and looks for a class with the same name as the module; `src/AgentEval/__init__.py` exports that class, which RF instantiates with the `Library` directive's kwargs; static libraries auto-register all `@keyword`-decorated methods).
   - **Direct Python instantiation**: `from AgentEval import AgentEval; agent = AgentEval(allow_validate_operator=True)` from a Python script.
   - The class MUST have a top-level export from `src/AgentEval/__init__.py` (update the existing `__all__: list[str] = []` to `__all__: list[str] = ["AgentEval"]`).

5. **AC-1a.6.5 — FR42 acceptance test in `tests/acceptance/tier1/`.** Author `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` (or `.robot` equivalent) that:
   - Instantiates `AgentEval()` with no kwargs.
   - Asserts each of the 9 defaults via `Get Effective Config`.
   - Instantiates `AgentEval(allow_validate_operator=True, telemetry=False)`.
   - Asserts the 2 kwarg overrides + the other 7 defaults still apply.
   - **Phase-1 note**: this test is the first NON-COLLECT-ONLY test under `tests/acceptance/tier1/`. Per Story 1a.6 code-review HIGH-1 (2026-05-18): the original Story 1a.2 collect-only sweep was leaving tier1 as `--collect-only`, which meant assertions were never executed in CI. ci.yml is restructured by this story to give `tests/acceptance/tier1/` its own dedicated `uv run pytest tests/acceptance/tier1 -q` step (no `--collect-only`, no exit-5 leniency); the collect-only sweep continues to cover the 2 still-empty placeholder dirs (`tests/unit`, `tests/unit/conventions`). `tests/acceptance/smoke/` gets its own dedicated `uv run robot tests/acceptance/smoke` step.

6. **AC-1a.6.6 — `docs/contracts/stability-surface.md` Phase-1 registry populated.** Update the existing skeleton (Story 1a.4 stub + Story 1a.5 scope-narrowing) to ADD substantive Phase-1 registry entries for:
   - `AgentEval` class — `provisional` (Phase-1; signature may evolve as Epic 1b kernel wires env-var precedence). Future-stability date: post Epic 1b retrospective.
   - 9 FR42 + FR11b config parameter names + types — `provisional` (semantics + type stable; default values may tighten via ADR amendment).
   - `Get Effective Config` keyword — `provisional` (Phase-1 returns a dict; Phase-2 may evolve to a structured `EffectiveConfig` dataclass).
   - Preserve the existing `### Sandbox Protocol Surface` subsection from Story 1a.4.
   - Status banner UPDATED: remove "Phase-1 skeleton — content to be filled by Story 1a.6"; replace with "Status: accepted (Story 1a.6 initial registry; expanded incrementally by future epic stories)".
   - **Critical**: preserve the 4 NFR-MAINT-04 section headers (`## Purpose`, `## Scope`, `## Contract`, `## Change Policy`) — `docs-build.yml`'s per-file assertion MUST still pass.

7. **AC-1a.6.7 — `docs/contracts/exit-criteria-0x-to-1x.md` Phase-1 stub content populated.** Update the existing skeleton (Story 1a.4) to add substantive 4-criteria-with-rationale stub content per epics.md L820 spec:
   - **Conformance coverage threshold**: TBD; rationale "filled in Phase 1 close per FR65". Placeholder text: `"≥<N>% of public keywords pass conformance suite against ≥2 Tier-1 adapters"`.
   - **Dogfood parity bar**: TBD; rationale "filled in Phase 1 close per FR65". Placeholder: `"rf-mcp + robotframework-agentskills full-parity test suites green against agenteval wheel"`.
   - **ADR completeness**: TBD; rationale "filled in Phase 1 close per FR65". Placeholder: `"all 18 ratified ADRs have epic-implementation status confirmed (no `forward-reference` banners in shipped code/docs)"`.
   - **Public API stability period**: TBD; rationale "filled in Phase 1 close per FR65". Placeholder: `"all `provisional` stability-surface entries promoted to `stable` OR demoted to `experimental`; zero `provisional` at 1.0 release"`.
   - Status banner: "Status: accepted (Story 1a.6 initial stub; concrete numeric bars filled by Epic 9 Story 9.3 at Phase 1 retrospective)".
   - **Critical**: preserve the 4 NFR-MAINT-04 section headers.

8. **AC-1a.6.8 — `__init__.py` test_id read for future Story 5.1 listener.** The `AgentEval.__init__` MUST internally call `_get_rf_test_id()` lazily (helper returns `None` if not under RF Listener v3 context per ADR-009). The accessor isn't externalized as a keyword; it's prep for Story 5.1's listener to read `test_id` when wiring per-test MCP scoping. Phase-1: helper returns `None` always (no Listener v3 wired yet); Story 5.1 connects the helper to RF context.

9. **AC-1a.6.9 — Apache 2.0 license headers preserved.** When `src/AgentEval/__init__.py` is updated, the Apache 2.0 header from Story 1a.5 MUST be preserved at file prologue. Run `uv run python scripts/check-license-headers.py` post-edit; expected output: `PASS: all 20 .py files have the canonical Apache 2.0 license header at prologue.` (count stays 20).

10. **AC-1a.6.10 — All CI checks pass post-implementation.**
    - `uv run ruff check src/ tests/` clean (incl. N801/N802/N806 per Story 1a.5 MED-6).
    - `uv run ruff format --check src/ tests/` clean.
    - `uv run mypy src/` clean — special focus on the `mcp_per_test: bool | Literal["suite"]` annotation passing strict mypy.
    - `uv run python scripts/check-license-headers.py` PASS.
    - `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` passes (real test, not collect-only).
    - `docs-build.yml` per-file 4-section assertion still passes for all 12 contract files (`coding-conventions.md` + `stability-surface.md` + `exit-criteria-0x-to-1x.md` content fills MUST NOT break their MADR structure).

11. **AC-1a.6.11 — Story 1a.5 SECURITY.md forward-reference for `telemetry=False` is now backed.** Per Story 1a.5 MED-1 patches, SECURITY.md cites `__init__(telemetry=False)` as a Story 1a.6 forward-reference. After Story 1a.6 commits, that forward-ref banner can be REMOVED (or downgraded to historical note). **Cross-story cleanup task** included in Task 9 — update SECURITY.md NFR-SEC-05 to remove the "Phase-1 status: forward-reference" banner around `telemetry=False`.

## Tasks / Subtasks

- [x] **Task 1: Pre-flight verification (AC: 1a.6.9, 1a.6.10)**
  - [x] Confirm Story 1a.5 done: `ls scripts/{apply,check}-license-headers.py` succeeds; `uv run python scripts/check-license-headers.py` returns 20/20 PASS.
  - [x] Confirm baseline: `src/AgentEval/__init__.py` is the empty-package Story 1a.1 version (with Apache 2.0 header from Story 1a.5). `__all__: list[str] = []`.
  - [x] Confirm `docs/contracts/stability-surface.md` is the Story 1a.4 skeleton (with Story 1a.5 scope-narrowing) — has 4 sandbox-related entries + the `### Sandbox Protocol Surface` subsection.
  - [x] Confirm `docs/contracts/exit-criteria-0x-to-1x.md` is the Story 1a.4 skeleton.
  - [x] Confirm `.env.example` `AGENTEVAL_MCP_PER_TEST=true` (Story 1a.6 pre-create-story cleanup landed).

- [x] **Task 2: Implement `AgentEval` class in `src/AgentEval/__init__.py` (AC: 1a.6.1, 1a.6.2, 1a.6.4, 1a.6.8, 1a.6.9)**
  - [x] **PRESERVE** the Apache 2.0 header at file prologue (existing 13 lines from Story 1a.5). Add new code AFTER the header + existing docstring.
  - [x] Import `from typing import Literal` for the `mcp_per_test` annotation.
  - [x] Define the `AgentEval` class with the documented signature. All 9 params keyword-only via `*` separator. Type-annotated.
  - [x] Store each param as `self._<name>` for `Get Effective Config` accessor.
  - [x] Add `_get_rf_test_id()` internal method that returns `None` (Phase-1 stub; Story 5.1 wires real implementation).
  - [x] Update `__all__: list[str] = ["AgentEval"]` (was `[]`).
  - [x] Class docstring: Google-style, document each of the 9 parameters per FR42 + FR43 + FR44 + FR11b. Cite ADR cross-references.
  - [x] Phase-1 limitation note in docstring: "kwarg-only precedence per AC-1a.6.2; env-var precedence lands in Epic 1b `_kernel/context.py`".

- [x] **Task 3: Implement `Get Effective Config` RF keyword (AC: 1a.6.3)**
  - [x] Wire via Robot Framework's `@keyword` decorator (`from robot.api.deco import keyword`).
  - [x] Method `get_effective_config(self) -> dict[str, Any]` — returns a dict with all 9 resolved config values.
  - [x] Document the dict shape in the keyword docstring (Google style).
  - [x] Phase-1: returns the kwarg-only-resolved values (matches AC-1a.6.2 scope).

- [x] **Task 4: Author FR42 acceptance test (AC: 1a.6.5)**
  - [x] Author `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` as a pytest test (NOT a `.robot` test for Phase-1; the conformance-suite mock-agent + RF integration tests land in Epic 1b Story 1b.5).
  - [x] Test: `def test_ac_fr42_defaults_with_no_kwargs() -> None:` — instantiate `AgentEval()`, assert `.get_effective_config()` returns the 9 documented defaults.
  - [x] Test: `def test_ac_fr42_defaults_with_kwarg_overrides() -> None:` — instantiate `AgentEval(allow_validate_operator=True, telemetry=False)`, assert the 2 overrides + 7 unchanged defaults.
  - [x] Per `docs/contracts/coding-conventions.md` test naming: `test_<what>__<when>__<then>` 3-part form for unit tests; acceptance tests use `test_<ac_label>` per the conventions doc.
  - [x] Apache 2.0 header on the test file (per Story 1a.5 enforcement)? **NO** — license-header script only requires headers under `src/AgentEval/`; `tests/` is out of scope.

- [x] **Task 5: Fill `docs/contracts/stability-surface.md` Phase-1 registry (AC: 1a.6.6)**
  - [x] Add a new subsection inside `## Contract` (BETWEEN the existing 3-label scheme docs + the `### Sandbox Protocol Surface` subsection): `### AgentEval Library Surface (Phase-1 registry)`. Lists `AgentEval` class + 9 config params + `Get Effective Config` keyword each labeled per AC-1a.6.6.
  - [x] Update status banner: stub → accepted. Reference Story 1a.6 ratification.
  - [x] Preserve the `### Sandbox Protocol Surface` subsection verbatim (Story 1a.4 ratified; Story 1a.5 narrowing applies).
  - [x] Machine-verify: `grep -c -E '^## (Purpose|Scope|Contract|Change Policy)$' docs/contracts/stability-surface.md` MUST output `4`.

- [x] **Task 6: Fill `docs/contracts/exit-criteria-0x-to-1x.md` Phase-1 stub (AC: 1a.6.7)**
  - [x] Add substantive 4-criteria table inside `## Contract`. Each row: criterion name + Phase-1 placeholder text + rationale ("filled in Phase 1 close per FR65"). Cross-ref `Epic 9 Story 9.3` as the owning story for final content.
  - [x] Update status banner: skeleton → accepted (Story 1a.6 initial stub).
  - [x] Machine-verify: 4 section headers preserved.

- [x] **Task 7: Restructure `ci.yml` to actually execute tier1 + smoke tests (AC: 1a.6.5, 1a.6.10) — REVISED per code-review HIGH-1 (2026-05-18)**
  - [x] **Original sketch (incorrect)**: relied on Story 1a.2's collect-only sweep to cover tier1, accepting exit 0 (real test passes) or exit 5 (empty). Codex flagged that `--collect-only` only verifies collection succeeded — assertions were NEVER executed in CI.
  - [x] **Revised implementation (HIGH-1 patch)**: ci.yml now has THREE test-execution steps:
    1. `uv run pytest tests/acceptance/tier1 -q` — real execution, no leniency (the 6 FR42 tests run their assertions in CI).
    2. `uv run robot tests/acceptance/smoke` — real execution of the 1 RF smoke test (MED-3 patch, adds `tests/acceptance/smoke/test_agenteval_library.robot`).
    3. Collect-only sweep across the 2 still-empty placeholder dirs (`tests/unit`, `tests/unit/conventions`) with exit-5 leniency preserved.
  - [x] Local verification: `uv run pytest tests/acceptance/tier1 -q` → 6 passed; `uv run robot tests/acceptance/smoke` → smoke test passes; collect-only sweep for the 2 placeholder dirs → exit 5 (accepted).

- [x] **Task 8: Run all post-implementation gates (AC: 1a.6.10)**
  - [x] `uv run ruff check src/ tests/` — clean.
  - [x] `uv run ruff format --check src/ tests/` — clean (run `uv run ruff format src/ tests/` if anything's off, then re-check).
  - [x] `uv run mypy src/` — clean. Pay attention to `mcp_per_test: bool | Literal["suite"]` annotation strict-mode compliance.
  - [x] `uv run python scripts/check-license-headers.py` — PASS: 20/20.
  - [x] `uv run pytest tests/acceptance/tier1 -q` — 6 tests pass (AC-1a.6.5 was satisfied with finer-grained coverage than the original 2-test sketch).

- [x] **Task 9: Cross-story cleanup — SECURITY.md NFR-SEC-05 forward-ref (AC: 1a.6.11)**
  - [x] Edit `SECURITY.md` §NFR-SEC-05 — remove the "**Phase-1 status:** **forward-reference.**" banner around `__init__(telemetry=False)` since Story 1a.6 has now wired it. Replace with current-state language: "The library `__init__(telemetry=False)` parameter is now wired by Story 1a.6 (this commit); when set, it disables the OTel listener (FR44). Full OTel-listener disable behavior (preventing all egress paths) is still gated on Epic 5 Story 5.1 which lands the listener itself."
  - [x] Keep the NFR-SEC-01 forward-ref banner intact (`config.redact_env()` + `config.add_redaction_pattern()` are Epic 5 deliverables — still forward-references).

- [x] **Task 10: CHANGELOG + commit prep**
  - [x] CHANGELOG.md `## [Unreleased]` entry: "Story 1a.6: `AgentEval` class wired with 9 FR42+FR11b defaults (`provider`, `telemetry`, `trace_backend`, `allow_validate_operator`, `default_temperature`, `mcp_per_test`, `allow_external_mcp_blind`, `max_cost_usd`, `max_runtime_seconds`); `Get Effective Config` keyword; FR42 acceptance test; stability-surface.md + exit-criteria-0x-to-1x.md Phase-1 content filled; SECURITY.md NFR-SEC-05 forward-ref retired (now backed by code)."
  - [x] Story file Dev Agent Record + File List + Change Log per BMad workflow.
  - [x] **Critical pre-commit gate**: `uv run pre-commit run --all-files` per `.pre-commit-config.yaml` (Story 1a.5 deliverable). All hooks pass before commit.

## Dev Notes

### Why this story exists

The final Epic 1a story. Closes the Phase-1 "first-import experience" gap:
- Without Story 1a.6, `Library    AgentEval` in a `.robot` file errors out (Story 1a.1 has only an empty package — no Library class).
- The 9 FR42+FR11b defaults are documented but not wired — consumers can't actually pass `allow_validate_operator=True` or `telemetry=False` to the library.
- `docs/contracts/stability-surface.md` is a Phase-1 skeleton (Story 1a.4 + Story 1a.5 narrowing) — needs the initial library-surface labels to be useful to consumers reading it.
- `docs/contracts/exit-criteria-0x-to-1x.md` is a Phase-1 skeleton — needs the 4-criteria placeholder to give Epic 9 Story 9.3 something to fill at Phase 1 close.

After Story 1a.6, `Library    AgentEval` works (with placeholder behavior for telemetry + validate gate), `Get Effective Config` is a real keyword consumers can call, stability-surface.md describes the actual public surface, and exit-criteria-0x-to-1x.md tells Epic 9 what numeric bars need filling.

### Architecture compliance

- **PRD FR42** (PRD L1564): 8 defaults. **PRD FR11b** (PRD L1502): `max_runtime_seconds=None` keyword default. **Story 1a.6 wires all 9 as Library `__init__` defaults.**
- **PRD FR43** (PRD L1565): `allow_validate_operator=True` to enable the AssertionEngine `validate` operator. Default `False`. Gate enforcement (raising `ValidateOperatorDisallowed`) is Epic 6 work — Story 1a.6 only wires the parameter + ensures it's accessible via `Get Effective Config`.
- **PRD FR44** (PRD L1566): `__init__(telemetry=False)` disables OTel listener; `Get Trace Backend Names` returns `[]`. Phase-1 wires the parameter; full enforcement (listener disable + egress prevention) is Epic 5 Story 5.1.
- **ADR-009 (ratified Story 1a.3)**: `mcp_per_test: bool = True` default. Architecture L314 extends to 3-mode (`True | "suite" | False`). Story 1a.6 wires the type signature `bool | Literal["suite"]` for the 2 documented values + Python truthiness for the third.
- **ADR-013 (Entry-Points Discovery)**: `provider="litellm"` default resolves via the `agenteval.providers` entry-points group (Phase-1: trivially returns the only registered provider; Phase-2: discovery + validation).
- **ADR-016 (`mcp_coverage` Detection)**: `allow_external_mcp_blind=False` default — opt-in via the kwarg per ADR-016 D4 adapter contract.
- **ADR-015 (`@guarded_fanout` Decorator)**: `max_cost_usd=5.00` + `max_runtime_seconds=None` are the budget defaults the decorator reads.

### Pre-create-story drift findings + ratifications (5 drifts)

| Drift | Source A (sb-of-truth) | Source B (drift) | Many's 2026-05-18 ratification |
|---|---|---|---|
| `mcp_per_test` default | PRD FR42 + ADR-009 = `True` | epics.md AC + `.env.example` = `"suite"` | Honor PRD/ADR; epics.md + `.env.example` updated. `"suite"` remains valid mode per architecture L314 but is NOT the library default. |
| FR42 defaults set count | PRD FR42 = 8 defaults | epics.md AC = 6 defaults | Honor PRD's 8 + add FR11b's `max_runtime_seconds=None` = 9 total. epics.md AC L814 updated. |
| Stability labels | PRD FR64 + Story 1a.4 ratified `stability-surface.md` = 3 labels (`stable`/`provisional`/`experimental`) | epics.md AC L820 = 4 labels (`stable`/`beta`/`experimental`/`deprecated`) | Honor PRD + Story 1a.4 (3 labels); epics.md L820 updated. |
| Exit-criteria slug | PRD FR65 + architecture L1423 + Story 1a.4 ratified = `exit-criteria-0x-to-1x.md` | epics.md AC L822 = `exit-criteria.md` | Honor PRD + arch + Story 1a.4; epics.md L822 updated. Same drift caught + fixed in Story 1a.4 ratification. |
| `max_runtime_seconds=None` | epics.md AC has it; PRD FR42 doesn't | PRD FR11b has it as keyword default (NOT Library default) | Story 1a.6 promotes it to Library `__init__` default for consistency with the other budget config. |

### File-by-file changes

**`src/AgentEval/__init__.py` (UPDATE, currently Story 1a.1 + 1a.5 baseline):**

Current state:
- Apache 2.0 header (Story 1a.5; 13 lines)
- Docstring: "Pre-alpha. Empty public surface — sub-libraries land in Epic 1b onward."
- `__version__ = "0.0.1"`
- `__all__: list[str] = []`

Story 1a.6 adds:
- `from typing import Any, Literal` import
- `from robot.api.deco import keyword` import (for `@keyword` decorator)
- `class AgentEval` definition with the 9 keyword-only `__init__` params + `Get Effective Config` keyword + `_get_rf_test_id()` helper
- Updates `__all__` to `["AgentEval"]`

What MUST be preserved:
- Apache 2.0 header (Story 1a.5 enforcement)
- `__version__ = "0.0.1"`

### Coding conventions to honor (per `docs/contracts/coding-conventions.md`)

- **Type annotations:** required on all public params. `mcp_per_test: bool | Literal["suite"]` uses PEP 695-compatible syntax for the union type (although `bool | Literal["suite"]` works in 3.10+ via PEP 604, the project pins py3.12+ so this is fine).
- **Naming:** `AgentEval` PascalCase class is the documented exception per Story 1a.5 MED-6 patch (RF Library convention; N999 suppressed in ruff.toml).
- **Docstring:** Google style. Sections: docstring summary, `Args:` (document each of the 9 params + their FR/ADR cross-references), `Examples:` (optional but encouraged).
- **Error class:** if `__init__` ever needs to raise on invalid kwarg combo (Phase-2 may add e.g. `validate(...)`-checks), use `AgentEvalCompatError` per ADR-014.

### `Get Effective Config` keyword shape (Phase-1)

Returns a dict matching exactly the 9 `__init__` param names + their resolved values:

```python
{
    "provider": str,                              # default "litellm"
    "telemetry": bool,                            # default True
    "trace_backend": str,                         # default "memory"
    "allow_validate_operator": bool,              # default False
    "default_temperature": float,                 # default 0.0
    "mcp_per_test": bool | Literal["suite"],      # default True
    "allow_external_mcp_blind": bool,             # default False
    "max_cost_usd": float,                        # default 5.00
    "max_runtime_seconds": float | None,          # default None
}
```

Phase-1: returns the kwarg-only resolved values (no env-var precedence yet — Epic 1b `_kernel/context.py` wires that).

### Robot Framework Library convention

The class `AgentEval` is exported from `src/AgentEval/__init__.py`. When RF imports `Library    AgentEval` from a `.robot` file:

1. RF looks for a module/package named `AgentEval` on `PYTHONPATH`.
2. Finds `src/AgentEval/__init__.py` (after `uv sync` installs the wheel into the project venv).
3. RF checks for a class with the SAME name as the module (`AgentEval` class within `AgentEval` package).
4. Instantiates the class with the kwargs from the Library directive.

The class is a **static library** (no `ROBOT_LIBRARY_LISTENER`) — not a Library Listener (empirically disqualified for the xunit enrichment hook per Story 1a.4 + 1a.5 listener-integration.md). The OTel Listener (Story 5.1) is a SEPARATE Regular Listener registered via `--listener AgentEval.telemetry.listener`.

### Test placement convention (per Story 1a.5 coding-conventions.md)

| Test category | Location |
|---|---|
| Unit tests | `tests/unit/<module>/test_<what>.py` |
| Convention enforcers | `tests/unit/conventions/test_<rule>.py` |
| Acceptance smoke | `tests/acceptance/smoke/test_<scenario>.py` |
| **Acceptance Tier-1 (per-AC label)** | **`tests/acceptance/tier1/test_<ac_label>.py`** ← Story 1a.6 lands here |
| Acceptance Tier-3 | `tests/acceptance/tier3/test_<scenario>.py` |
| Conformance | `tests/conformance/test_ac_<label>.py` |

Story 1a.6's FR42 acceptance test goes at `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` (6 tests covering kwarg-only enforcement, default values, kwarg overrides, the `bool | Literal["suite"]` type, and the `Get Effective Config` dict shape). This is the FIRST real-execution test in the Phase-1 baseline. Per code-review HIGH-1, `ci.yml` is restructured so `tests/acceptance/tier1/` AND `tests/acceptance/smoke/` get their own dedicated execution steps (no `--collect-only`, no exit-5 leniency); the collect-only sweep continues to cover only the 2 still-empty placeholder dirs (`tests/unit`, `tests/unit/conventions`).

### Project debt cleanup (Story 1a.5 forward-refs become current-state)

Story 1a.5 MED-1 patches added `**Phase-1 status:** **forward-reference.**` banners to SECURITY.md NFR-SEC-01 + NFR-SEC-05. Story 1a.6 wires `__init__(telemetry=False)` per FR44 — making NFR-SEC-05's banner OUT OF DATE. Task 9 retires the NFR-SEC-05 forward-ref banner.

NFR-SEC-01's banner (`config.redact_env()` + `config.add_redaction_pattern()`) stays — those are Epic 5 Story 5.3 deliverables, NOT Story 1a.6 scope.

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)**: code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)`. Expect Codex to find edge cases in: type-annotation strict-mode mypy compliance for `mcp_per_test: bool | Literal["suite"]`; RF `@keyword` decorator usage correctness; cross-reference accuracy between docstring + stability-surface.md + exit-criteria-0x-to-1x.md.
2. **Norm #2 (machine-verified numeric claims)**: 9 defaults, 4 NFR-MAINT-04 sections per file, 20 license-headered files, 6 FR42 tests — all machine-verified before commit.
3. **Pre-create-story spec-vs-ratified-doc check (Norm #4)**: applied 2026-05-18 with **5 drifts caught + ratified** (largest drift set per single story; same scale as Story 1a.4's drift). All resolved by honoring ratified sources.
4. **CI-log-forensics (Norm #5)**: post-push verification will confirm — per code-review HIGH-1 fix — that the dedicated tier1 step (`uv run pytest tests/acceptance/tier1 -q`) actually runs the 6 FR42 assertions in CI (not just collection), the dedicated smoke step runs the new `.robot` smoke test, mypy strict-mode passes the `bool | Literal["suite"]` annotation, and the collect-only sweep over the 2 still-empty placeholder dirs continues to exit-0 via exit-5 leniency.
5. **Honest framing**: Phase-1 boundaries documented (`telemetry=False` wires the param but full listener-disable lands Epic 5; `mcp_per_test` 3-mode supported but Library `__init__` precedence only — env-var precedence is Epic 1b).
6. **agentguard inspiration-only**: ratified.

### References

- **PRD §FR42** (L1564): the 8 Library defaults
- **PRD §FR43** (L1565): `allow_validate_operator=True` opt-in to AssertionEngine `validate` operator
- **PRD §FR44** (L1566): `__init__(telemetry=False)` OTel disable
- **PRD §FR11b** (L1502): `max_runtime_seconds` Tier-3 fan-out keyword arg
- **PRD §FR41** (L*) — kwarg → env-var → `.env` → defaults precedence (Phase-1 wires kwarg-only)
- **PRD §FR64** (L1598): 3-label stability surface
- **PRD §FR65** (L1599): exit-criteria-0x-to-1x.md
- **ADR-009** (`docs/adr/ADR-009-per-test-mcp-server-scope.md`): `mcp_per_test: bool = True` default + 3-mode support
- **ADR-013** (`docs/adr/ADR-013-entry-points-discovery-infrastructure.md`): `provider` resolution via entry-points
- **ADR-014** (`docs/adr/ADR-014-error-class-hierarchy.md`): error classes for future enforcement
- **ADR-015** (`docs/adr/ADR-015-cost-runtime-guardrail-decorator.md`): `max_cost_usd` + `max_runtime_seconds` budget params
- **ADR-016** (`docs/adr/ADR-016-mcp-coverage-detection-default.md`): `allow_external_mcp_blind` semantic
- **Architecture L314**: 3-mode `mcp_per_test` design (`True` / `"suite"` / `False`)
- **Architecture L1423**: `exit-criteria-0x-to-1x.md` canonical slug
- **Story 1a.4 `docs/contracts/stability-surface.md`**: 3-label scheme ratified + `### Sandbox Protocol Surface` subsection
- **Story 1a.4 `docs/contracts/exit-criteria-0x-to-1x.md`**: Phase-1 skeleton (Story 1a.6 fills)
- **Story 1a.5 `SECURITY.md` NFR-SEC-05**: forward-ref to `__init__(telemetry=False)` (Story 1a.6 retires)
- **Story 1a.5 `docs/contracts/coding-conventions.md`**: naming + type-annotation + docstring + test-naming conventions

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML/JSON will be added here by context workflow -->

### Agent Model Used

<!-- To be filled by dev-story workflow -->

### Debug Log References

<!-- To be filled by dev-story workflow -->

### Completion Notes List

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

Expected files (2 created + 6 updated):

**New files (2):**
- `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` (FR42 acceptance test — 6 tests, first real-execution Phase-1 test)
- `tests/acceptance/smoke/test_agenteval_library.robot` (RF smoke test — verifies `Library AgentEval` static-library discovery + `Get Effective Config` keyword exposure; added per code-review MED-3)

**Updated files (6):**
- `src/AgentEval/__init__.py` (add `AgentEval` class with 9 keyword-only `__init__` params + `Get Effective Config` keyword + `_get_rf_test_id()` helper called from `__init__` per MED-2; preserve Apache 2.0 header)
- `docs/contracts/stability-surface.md` (add Phase-1 registry entries for `AgentEval` class + 9 config params + `Get Effective Config` keyword; preserve `### Sandbox Protocol Surface` subsection; Purpose/Scope intros updated per LOW-5)
- `docs/contracts/exit-criteria-0x-to-1x.md` (fill 4-criteria-with-rationale stub content; documentation gate updated 11→12 per LOW-7)
- `SECURITY.md` (retire NFR-SEC-05 `__init__(telemetry=False)` forward-ref banner per Task 9; rephrase per MED-6 to "control-surface kwarg only" Phase-1 framing)
- `.github/workflows/ci.yml` (restructure test sweep per HIGH-1: dedicated tier1 + smoke execution steps; collect-only sweep narrowed to 2 still-empty placeholder dirs)
- `CHANGELOG.md` (Unreleased entry)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-18 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (6th consecutive use) caught 5 drifts in Story 1a.6 spec vs ratified sources: (1) `mcp_per_test` default `True` vs `"suite"`; (2) FR42 defaults set count 8 vs 6; (3) stability labels 3-label vs 4-label set; (4) exit-criteria slug `exit-criteria-0x-to-1x.md` vs `exit-criteria.md`; (5) `max_runtime_seconds` Library default vs FR11b keyword arg. All 5 resolved by honoring ratified sources (PRD FR42 + ADR-009 + Story 1a.4 stability-surface.md + architecture L1423 + FR11b); epics.md L812-822 + `.env.example` updated pre-authoring. | Bob |
| 2026-05-18 | 0.2.0   | Dev-story complete. All 11 ACs satisfied with machine-verified evidence. AgentEval class wired with 9 keyword-only __init__ params + Get Effective Config keyword + _get_rf_test_id stub. FR42 acceptance test (6 tests) passes — first non-collect-only Phase-1 test. stability-surface.md + exit-criteria-0x-to-1x.md content filled (4 NFR-MAINT-04 sections preserved in both). SECURITY.md NFR-SEC-05 forward-ref retired (telemetry=False now wired). All gates: ruff clean (incl. N801/N802/N806), ruff format 23 files, mypy 20 source files clean (incl. bool | Literal["suite"]), license-headers 20/20, FR42 6/6 pass. Phase-1 collect-only sweep: tier1 now exits 0 (real test); other 3 dirs still exit 5 (placeholder); ci.yml exit-5 leniency continues. Status: review. | Amelia |
| 2026-05-18 | 0.3.0   | Code-review patches applied (cross-LLM adversarial review — Claude Opus 4.7 + Codex CLI 0.117.0; findings doc at `1a-6-code-review-findings-2026-05-18.md`). 9 patches: HIGH-1 ci.yml restructured (tier1 + smoke now have dedicated real-execution steps; collect-only sweep narrowed to 2 placeholder dirs — assertions actually run in CI now); MED-2 `__init__` calls `self._get_rf_test_id()` + stores `self._rf_test_id`; MED-3 added `tests/acceptance/smoke/test_agenteval_library.robot` for RF static-library discovery verification; MED-6 SECURITY.md NFR-SEC-05 reframed as "control-surface kwarg only" Phase-1 (not eliminating egress until Epic 5); MED-8 + LOW-9 this artifact aligned with reality (6 tests, HIGH-1 ci patch); LOW-4 `mcp_per_test` citations split (ADR-009 True/False; architecture L314+NFR-PERF-03d for `"suite"`); LOW-5 stability-surface Purpose/Scope updated to mention both AgentEval + sandbox surfaces; LOW-7 exit-criteria doc gate updated 11→12. 6th consecutive cross-LLM review where Claude solo 0 / Codex 9 — same-family blind spot pattern continues to be load-bearing. Status: review (ready for Many's final approval). | Amelia |
| 2026-05-18 | 1.0.0   | Story 1a.6 DONE. All 9 code-review patches approved by Many; commit `344ccc1` pushed; CI forensics confirm the HIGH-1 fix landed correctly (CI run 26028176201 → `pytest tests/acceptance/tier1 -q` reports `6 passed in 0.41s`; `robot tests/acceptance/smoke` reports `1 test, 1 passed, 0 failed`; collect-only sweep covers only the 2 remaining placeholder dirs). All 3 workflows green for SHA `344ccc1`: ci (success), security-scan/CodeQL (success), docs-build (success — manually dispatched since docs-build is PR-only-triggered + this commit pushed directly to main). Senior Developer Review section added. Status: review → done. Epic 1a: 6/6 stories done. | Amelia |

## Senior Developer Review (AI)

**Reviewer:** Many Kasiriha
**Review Date:** 2026-05-18
**Review Outcome:** **APPROVED** (after applying 9 code-review patches from the cross-LLM adversarial review pair Claude Opus 4.7 + Codex CLI 0.117.0)

### Summary

Story 1a.6 wires the `AgentEval` Robot Framework Library entry point with 9 keyword-only `__init__` parameters per PRD FR42 + FR11b, exposes the `Get Effective Config` keyword for kwarg-resolved config inspection, lands the Phase-1 stability-surface registry entries for the AgentEval surface, fills substantive content for `docs/contracts/exit-criteria-0x-to-1x.md`, and retires SECURITY.md NFR-SEC-05's forward-reference banner. Story 1a.6 is the **final story of Epic 1a** — Epic 1a is now 6/6 done.

### Key Findings From Review

The `/bmad-code-review (Using current Claude + Codex CLI subagent)` pass found **1 HIGH + 4 MED + 4 LOW**:

- **HIGH-1 (critical):** `ci.yml`'s pytest sweep was using `--collect-only` for `tests/acceptance/tier1`, meaning the 6 FR42 acceptance tests got *collected* but never *executed* in CI. Locally `pytest tests/acceptance/tier1 -q` reported `6 passed`; in CI the assertions were silently skipped. A regression in `AgentEval.__init__` would have passed CI green. Patch restructures the sweep: dedicated execution step for tier1 (no `--collect-only`, no exit-5 leniency), dedicated `robot` step for smoke, collect-only sweep narrowed to the 2 still-empty placeholder dirs.
- **MED-2:** `_get_rf_test_id()` was defined but never called from `__init__`. Patched.
- **MED-3:** No `.robot` smoke test verified RF's static-library discovery model + `@keyword` exposure. Patched — added `tests/acceptance/smoke/test_agenteval_library.robot`.
- **MED-6:** SECURITY.md NFR-SEC-05 overclaimed that `telemetry=False` "eliminates" egress in present tense, but no listener exists yet. Patched to clarify the kwarg is wired as a control surface only; full egress elimination lands Epic 5 Story 5.1.
- **MED-8 + LOW-9:** Story artifact drift (2 vs 6 tests; `PythonLibCore / dynamic-library` wording). Patched.
- **LOW-4 + LOW-5 + LOW-7:** Documentation precision (ADR-009 only ratifies True/False for `mcp_per_test`; stability-surface Purpose/Scope referenced only sandbox; exit-criteria 11→12 contracts). Patched.

**6th consecutive cross-LLM review** where Claude solo found 0 substantive issues and Codex caught real ones. The same-family blind spot pattern is structurally load-bearing for this project — and HIGH-1 is precisely the class of "fake-green-via-collect-only" issue that Many's CI-log-forensics norm exists to surface.

### Acceptance Criteria Coverage

All 11 AC-1a.6.X satisfied:

- **AC-1a.6.1** (9 FR42+FR11b defaults, kwarg-only): `src/AgentEval/__init__.py` — verified by `test_ac_fr42_all_kwargs_keyword_only` + `test_ac_fr42_defaults_with_no_kwargs`.
- **AC-1a.6.2** (Phase-1 kwarg-only precedence): docstring + stability-surface registry document the Phase-1 boundary.
- **AC-1a.6.3** (`Get Effective Config` keyword): verified Python-side by `test_ac_fr42_get_effective_config_returns_dict`, RF-side by `tests/acceptance/smoke/test_agenteval_library.robot`.
- **AC-1a.6.4** (Library + Python import): both paths exercised in tests.
- **AC-1a.6.5** (tier1 FR42 acceptance test): `tests/acceptance/tier1/test_ac_fr42_library_defaults.py` — 6 tests, all green in CI (real execution post-HIGH-1).
- **AC-1a.6.6** (stability-surface Phase-1 registry): `docs/contracts/stability-surface.md` registers `AgentEval` class + 9 params + `Get Effective Config` keyword as `provisional`.
- **AC-1a.6.7** (exit-criteria-0x-to-1x.md 4-criteria stub content): 4 promotion criteria + rationale filled.
- **AC-1a.6.8** (`_get_rf_test_id()` hook): post-MED-2 patch, called from `__init__` and stored on `self._rf_test_id` (Phase-1 stub returns None).
- **AC-1a.6.9** (Apache 2.0 license header preserved): license-header script 20/20 PASS.
- **AC-1a.6.10** (gates clean): ruff + ruff format + mypy + license-headers + tier1 + smoke + CI all green.
- **AC-1a.6.11** (SECURITY.md NFR-SEC-05 forward-ref retired): banner replaced with control-surface-only Phase-1 framing.

### Test Coverage

- **Local:** `pytest tests/acceptance/tier1 -q` → 6 passed in 0.28s. `robot tests/acceptance/smoke` → 1 passed.
- **CI (SHA 344ccc1):** ci workflow → both `test (py3.12)` + `test (py3.13)` PASS; tier1 step reports `6 passed in 0.41s`; smoke step reports `1 test, 1 passed, 0 failed`; collect-only sweep over the 2 placeholder dirs → exit-5 (accepted as Phase-1 leniency).

### Action Items

None. All 9 review findings resolved; gates clean; CI forensics confirm HIGH-1 fix landed correctly.

### Outcome

**Status: review → done.** Epic 1a 6/6 stories complete. Ready for `/bmad-retrospective` on Epic 1a.
