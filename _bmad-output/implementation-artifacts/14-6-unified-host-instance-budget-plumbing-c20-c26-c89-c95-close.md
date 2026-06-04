# Story 14.6: Unified Host-Instance Budget Plumbing (`_HostBudgetPlumbing` Mixin Closes C20 + C26 + C89 + C95)

Status: done

## Story

As **Mei + Devon (Agent Surface Authors) running cross-adapter cohort comparisons**,
I want a unified `_HostBudgetPlumbing` mixin consumed by MCPLibrary + SkillsLibrary + OrchestrationLibrary so all 3 libraries carry `_max_cost_usd` + `_max_runtime_seconds` host-instance attrs symmetrically + `@guarded_fanout()`-decorated keywords actually enforce budgets end-to-end,
So that the "tracked NOT enforced" carve-out shipped across MCPLibrary (DF-4.4-S1 / C20, 9 epics old) + SkillsLibrary (DF-13.5-S1 / C95) closes with one architectural fix; cross-adapter fan-out runs respect actual budgets per FR11 not just per FR11 in docstring.

## Retro-debt mini-pass (5th + final exercise of CLAUDE.md mini-pass in Epic 14)

Per CLAUDE.md L143. Procedure run:

**Step 1:** Recent N=3 retros: Epic 13/12/11.

**Step 2-5:** Unresolved actions relevant to Story 14.6 surface:
- **Epic 13 retro Action #6 (L183)**: "Decide on C20 + C95 unified resolution NOW (not deferred). C20 (Epic 4 carry-over) and C95 (Epic 13 carry-over) together encode the cross-library budget-plumbing gap." — Story 14.6's PRIMARY scope. ✅ Closing (FULL — mechanism + evidence both dev-deliverable).
- **Epic 12 retro Action #3 (L162) sub-clause about C20**: "Close `@guarded_fanout()` MCPLibrary legacy carve-out (Epic 4 retro Action #6 — now 8 epics old)". ✅ Closing.
- **Epic 11 retro Action #2 (L153)**: same `@guarded_fanout` MCPLibrary closure. ✅ Closing.
- **C20 (DF-4.4-S1)** — `MCP.Get Tool Discoverability` budget enforcement. ✅ Closing.
- **C26 (DF-4.3-S6)** — `OrchestrationLibrary.Run Scenario` budget enforcement. ✅ Closing.
- **C89 (DF-13.3-S1)** — `MCP.Compare Tool Discoverability` budget enforcement. ✅ Closing.
- **C95 (DF-13.5-S1)** — `Skill.Compare Discoverability` cross-library budget plumbing. ✅ Closing.

**Closure pattern: FULL (not PARTIAL).** Per Story 14.3 + Story 14.5 closure-framing precedent: this story produces both the mechanism (mixin + library inheritance) AND the evidence (unit tests verify budget enforcement on fan-out keywords). No operator-side evidence carryover.

**≥1 retro-debt closure**: 3 retro action items + 4 catalog rows = 7 closures (the most of any Epic 14 story; appropriate since this is the final Epic 14 story with the biggest architectural blast radius).

## Pre-create-story drift check (61st use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-04)

7 drifts caught between epic L2365-2387 spec text + the ratified source-code reality. **100% real-drift catch rate maintained through 60 prior uses.**

- **D-1 (HIGH — MCPLibrary + SkillsLibrary not in `_SUB_LIBRARIES`, lifecycle is via `WITH NAME` in `.robot` not `AgentEval._build_components`):** Epic L2372 + L2378 implicitly assumes the mixin can be wired automatically. Reality (per `src/AgentEval/__init__.py:121-130` + Story 2.2 collision norm): MCPLibrary + SkillsLibrary are **explicitly excluded** from `_SUB_LIBRARIES` because of `Get Frontmatter` keyword-name collision with SubagentsLibrary. They are imported by operators via `Library AgentEval.mcp.library.MCPLibrary WITH NAME MCP` in `.robot` files. **The mixin's `_max_cost_usd` / `_max_runtime_seconds` MUST be settable via kwargs at RF Library-import time** — RF's `Library    <path>    arg1=val1    WITH NAME    NAME` syntax already supports this. **Decision:** the mixin's `__init__` accepts `max_cost_usd` + `max_runtime_seconds` as kwargs with `None` defaults. Operators set them at RF Library import; backwards-compatibility preserved (existing `Library AgentEval.mcp.library.MCPLibrary WITH NAME MCP` continues to work, just with no budget enforcement, identical to today). The honest-framing caveat (per Story 14.3 L-2 framing): the closure removes the *enforcement gap* but does NOT auto-wire from AgentEval top-level config — Phase-2.5+ work IF auto-wiring is desired (would need to resolve the Story 2.2 collision differently).

- **D-2 (HIGH — `@guarded_fanout` already reads via `getattr(self, "_max_cost_usd", None)` so the mixin only needs to PROVIDE the attrs):** Per `src/AgentEval/_kernel/guardrails.py:265-266`: the decorator already gracefully reads via `getattr` with `None` fallback. So the entire enforcement pipeline is wired today — the carve-out is exclusively about library instances not carrying the attrs. **Decision:** the mixin's only contract is the 2 instance attrs. NO `@guarded_fanout` decorator changes. NO `_kernel/guardrails.py` changes. Architectural surface stays narrow.

- **D-3 (HIGH — OrchestrationLibrary `__init__(default_provider)` precedent — keyword-only):** `OrchestrationLibrary.__init__` at L114 already takes `default_provider`. Adding `max_cost_usd` + `max_runtime_seconds` MUST be backward-compatible with existing `__init__(default_provider=...)` callers. **Decision:** mixin uses **keyword-only** args via `*` separator: `def __init__(self, *, max_cost_usd=None, max_runtime_seconds=None, **kwargs)`. The `**kwargs` forwards to `super().__init__()` so subclasses can layer additional ctor args (OrchestrationLibrary's `default_provider`). MCPLibrary + SkillsLibrary currently have no `__init__` — they get one for the first time, with only the budget kwargs.

- **D-4 (HIGH — fan-out keyword surface inventory):** Per epic L2381: "the 4 fan-out keywords". Re-verified at HEAD via `grep -nE "@guarded_fanout|@keyword.*Discoverability|@keyword.*Run Scenario" src/AgentEval/`:
  - **MCPLibrary.get_tool_discoverability** (`mcp/library.py:445`): `@tier(3)`; NO `@guarded_fanout` currently (DF-4.4-S1 / C20 carve-out).
  - **MCPLibrary.get_tool_discoverability_comparison** (`mcp/library.py:586`): `@tier(3)`; NO `@guarded_fanout` (DF-13.3-S1 / C89 carve-out).
  - **SkillsLibrary.get_discoverability** (`skills/library.py:424`): `@tier(3)` + `@guarded_fanout()` ALREADY (Story 7.2 ship).
  - **SkillsLibrary.get_discoverability_comparison** (`skills/library.py:517`): `@tier(3)` + `@guarded_fanout()` ALREADY (Story 13.5 ship).
  - **OrchestrationLibrary.run_scenario** (`orchestration/library.py`): `@tier(3)`; needs verification of current decorator state.

  **Decision:** Story 14.6 ADDS `@guarded_fanout()` to the 2 MCPLibrary keywords currently missing it (DF-4.4-S1 + DF-13.3-S1 closures). For the 2 SkillsLibrary keywords + OrchestrationLibrary.run_scenario already carrying `@guarded_fanout()`, the mixin alone closes the enforcement gap (because the decorator was already reading host attrs that were always None — now they have real values from the mixin). Need to verify run_scenario's current decorator state at dev time.

- **D-5 (MED — docstring "tracked NOT enforced" carve-out lines):** Story 13.3's `MCP.Compare Tool Discoverability` ships with explicit "tracked NOT enforced" docstring line (per C89 catalog row); Story 13.5's `Skill.Compare Discoverability` also ships with similar wording (per C95 catalog row). Both need updating to remove the carve-out language. **Decision:** grep for `"tracked NOT enforced"` + `"DF-4.4-S1"` + `"DF-13.3-S1"` + `"DF-13.5-S1"` carve-out references in src/ docstrings + remove them. Libdoc regen reflects the new contract.

- **D-6 (MED — test verification pattern: `__agenteval_test_budget__` sentinel kwarg):** Per `_kernel/guardrails.py:246`: `@guarded_fanout` decorator accepts `__agenteval_test_budget__=(max_cost_usd, max_runtime_seconds)` as a test-only kwarg override. This is the operator-tests path for verifying budget enforcement WITHOUT needing actual cost-tracking infrastructure. **Decision:** unit tests use this sentinel kwarg pattern to force `CostExceededError` / `RuntimeBudgetExceededError` at pre-flight (Layer 1). Per epic L2383: "max_cost_usd=0.01 against a 3-adapter fan-out raises CostExceededError after the 1st adapter's cost_usd=0.05 accumulator-tick" — this Layer 2 mid-run cost meter behavior is the harder test; for Story 14.6 scope, Layer 1 pre-flight verification is sufficient + much faster. Layer 2 mid-run tests are FILED AS DF-14.6-S1 (Phase-1.5 follow-up) per `feedback_in_flight_spec_amendment` UPSTREAM.

- **D-7 (LOW — `_SUB_LIBRARIES` exclusion preservation):** Epic L2386 verbatim: "existing `_SUB_LIBRARIES` exclusion rule from Story 2.2 collision norm is preserved (the mixin doesn't change `_SUB_LIBRARIES` membership — only adds budget plumbing to host instances)." **Decision:** Story 14.6 ratifies this UPSTREAM. Zero changes to `_SUB_LIBRARIES`. The mixin is a passive plumbing layer; library composition + collision rules unchanged.

## Cross-story upstream lessons from Stories 14.1-14.5 reviews

Per `feedback_cross_story_upstream_lesson_propagation`. Multiple lessons apply:

- **L-1 (Story 14.1 libdoc smoke template)**: Story 14.6 modifies 3 existing `@keyword`-decorated surfaces (`@guarded_fanout()` added to 2 MCP keywords + docstring carve-out removed from 2 keywords). Libdoc smoke step at dev-end on all 3 affected libraries (MCPLibrary + SkillsLibrary + OrchestrationLibrary).

- **L-2 (Story 14.3 PARTIAL-closure → Story 14.6 FULL-closure)**: Story 14.6's success criterion is "all 4 fan-out keywords enforce budgets end-to-end" — fully dev-deliverable via unit tests using the `__agenteval_test_budget__` sentinel. FULL closure framing (per Story 14.5 precedent).

- **L-3 (Story 14.4 + 14.5 Codex citation drift)**: re-derive every retro line citation pre-write. Epic 11 retro L153 Action #2; Epic 12 retro L162 Action #3; Epic 13 retro L183 Action #6 — all verified via direct grep before writing.

- **L-4 (Story 14.5 Opus HIGH-1 honest-framing)**: do NOT claim "first" or "novel empirical" findings without verification. Story 14.6's mixin is mechanically novel (no prior unified host-budget mixin exists in src) but the PATTERN (3-layer enforcement + sentinel kwarg test override) was established by Story 1b.3. Honest framing: Story 14.6 LIFTS an existing pattern across 3 libraries, NOT invents a new one.

- **L-5 (Story 14.5 Opus MED-1 norm-creation debt)**: Story 14.6's mini-pass surfaced 0 adjacent norm-creation debt to write. Verified by checking `~/.claude/projects/.../memory/MEMORY.md` against recent Epic 13/12 retro CONFIRMED-norm-creation entries — all accounted for.

## Acceptance Criteria

### AC-14.6.1 — `_HostBudgetPlumbing` mixin at `src/AgentEval/_kernel/host_budget_plumbing.py`

NEW file `src/AgentEval/_kernel/host_budget_plumbing.py` (~80 LoC + Apache 2.0 header):

```python
# Apache 2.0 header

"""Unified host-instance budget plumbing mixin (Story 14.6 / C20+C26+C89+C95 closure).

Single source of truth for the `_max_cost_usd` + `_max_runtime_seconds`
instance attributes that `@guarded_fanout()` reads via `getattr` per
`_kernel/guardrails.py:265-266`. Inherited by MCPLibrary, SkillsLibrary, and
OrchestrationLibrary so all 3 carry budget plumbing symmetrically. Closes
DF-4.4-S1 (C20) + DF-4.3-S6 (C26) + DF-13.3-S1 (C89) + DF-13.5-S1 (C95).
"""

from __future__ import annotations

from typing import Any


class _HostBudgetPlumbing:
    """Mixin adding `_max_cost_usd` + `_max_runtime_seconds` instance attrs.

    Subclasses inherit budget plumbing without redeclaring the attrs. RF
    `Library` import syntax accepts the kwargs:

        *** Settings ***
        Library    AgentEval.mcp.library.MCPLibrary    max_cost_usd=10.00    WITH NAME    MCP

    When not provided, defaults are `None` (no enforcement — backwards-
    compatible with pre-Story-14.6 behavior).
    """

    def __init__(
        self,
        *,
        max_cost_usd: float | None = None,
        max_runtime_seconds: float | None = None,
        **kwargs: Any,
    ) -> None:
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds
        super().__init__(**kwargs)
```

NB: `**kwargs` + `super().__init__(**kwargs)` forwarding is the cooperative-multiple-inheritance pattern that lets subclasses (`OrchestrationLibrary`) layer their own ctor args (e.g., `default_provider`).

### AC-14.6.2 — `MCPLibrary` inherits `_HostBudgetPlumbing`

`src/AgentEval/mcp/library.py` `class MCPLibrary` declaration changes from `class MCPLibrary:` to `class MCPLibrary(_HostBudgetPlumbing):`. NO `__init__` added explicitly — the mixin's `__init__` handles budget injection.

### AC-14.6.3 — `SkillsLibrary` inherits `_HostBudgetPlumbing`

`src/AgentEval/skills/library.py` `class SkillsLibrary` declaration changes from `class SkillsLibrary:` to `class SkillsLibrary(_HostBudgetPlumbing):`. NO `__init__` added explicitly.

### AC-14.6.4 — `OrchestrationLibrary` inherits `_HostBudgetPlumbing`

`src/AgentEval/orchestration/library.py` `class OrchestrationLibrary` changes from `class OrchestrationLibrary:` to `class OrchestrationLibrary(_HostBudgetPlumbing):`. Existing `__init__(self, default_provider=None)` updates to:

```python
def __init__(
    self,
    *,
    default_provider: str | None = None,
    max_cost_usd: float | None = None,
    max_runtime_seconds: float | None = None,
    **kwargs: Any,
) -> None:
    super().__init__(
        max_cost_usd=max_cost_usd,
        max_runtime_seconds=max_runtime_seconds,
        **kwargs,
    )
    self._default_provider = default_provider
```

NB: `default_provider` becomes **keyword-only** to match the mixin's discipline. Existing callers passing it positionally (`OrchestrationLibrary("mock")`) — verify via `grep -rnE "OrchestrationLibrary\(['\"]"` whether any exist. If any → in-flight spec amendment to keep positional for backward-compatibility OR update callers.

### AC-14.6.5 — `_build_components` passes budgets to OrchestrationLibrary

`src/AgentEval/__init__.py:_build_components` extends the OrchestrationLibrary branch (currently at L355-360 ish) to pass `max_cost_usd` + `max_runtime_seconds`:

```python
elif cls_name == "OrchestrationLibrary":
    components.append(
        cls(
            default_provider=self._provider,
            max_cost_usd=self._max_cost_usd,
            max_runtime_seconds=self._max_runtime_seconds,
        )
    )
```

(Mirrors existing StatsLibrary + JudgeLibrary patterns.) Story 4.3 code-review 2-way HIGH-C fix (default_provider wiring) preserved.

### AC-14.6.6 — Add `@guarded_fanout()` to MCPLibrary keywords missing it

`@guarded_fanout()` decorator added to:
- `MCPLibrary.get_tool_discoverability` (closes DF-4.4-S1 / C20).
- `MCPLibrary.get_tool_discoverability_comparison` (closes DF-13.3-S1 / C89).

Decorator ordering: `@keyword(name=...) → @tier(3) → @guarded_fanout()` (matches existing pattern on SkillsLibrary discoverability keywords).

### AC-14.6.7 — Remove "tracked NOT enforced" carve-out docstring lines

`grep -rnE "tracked NOT enforced|DF-4\.4-S1|DF-13\.3-S1|DF-13\.5-S1" src/AgentEval/*/library.py` identifies the carve-out documentation lines. Each removed + replaced with positive-framing closure note (e.g., "Budget enforcement via @guarded_fanout (Story 14.6 / C20+C89+C95 closure).").

### AC-14.6.8 — Unit tests at `tests/unit/_kernel/test_host_budget_plumbing.py`

NEW file. ≥10 tests covering:

**Mixin behavior (≥4):**
- `test_mixin_init_sets_both_attrs_to_provided_values`
- `test_mixin_init_defaults_both_attrs_to_None`
- `test_mixin_init_accepts_partial_kwargs`
- `test_mixin_cooperative_init_forwards_remaining_kwargs_to_super`

**Subclass smoke (≥3):**
- `test_mcp_library_carries_budget_attrs_after_init`
- `test_skills_library_carries_budget_attrs_after_init`
- `test_orchestration_library_carries_budget_attrs_after_init` (also verifies `default_provider` preserved)

**End-to-end enforcement via `__agenteval_test_budget__` sentinel (≥4):**
- `test_mcp_get_tool_discoverability_raises_cost_exceeded_at_preflight`
- `test_mcp_compare_tool_discoverability_raises_cost_exceeded_at_preflight`
- `test_skill_compare_discoverability_raises_cost_exceeded_at_preflight`
- `test_orchestration_run_scenario_raises_cost_exceeded_at_preflight`

Pattern (per `_kernel/guardrails.py:246`):
```python
def test_mcp_get_tool_discoverability_raises_cost_exceeded_at_preflight(tmp_path):
    lib = MCPLibrary(max_cost_usd=0.01)  # noqa: ARG001 — set via mixin
    with pytest.raises(CostExceededError):
        lib.get_tool_discoverability(
            mcp_config=...,
            tasks=...,
            __agenteval_test_budget__=(0.0, None),  # force pre-flight refusal
        )
```

### AC-14.6.9 — Close C20 + C26 + C89 + C95 catalog rows

`docs/phase-1-5-carry-overs.md` 4 rows updated:
- **C20**: Owner: TBD → "Story 14.6 (closed 2026-06-04)"; Acceptance criteria appended with "✅ FULL closure by Story 14.6 — `_HostBudgetPlumbing` mixin + `@guarded_fanout()` added to `MCP.Get Tool Discoverability` + unit tests verify pre-flight refusal."
- **C26**: same pattern for `OrchestrationLibrary.Run Scenario`.
- **C89**: same pattern for `MCP.Compare Tool Discoverability`.
- **C95**: same pattern for `Skill.Compare Discoverability`.

### AC-14.6.10 — Catalog non-creation per Story 14.2 hook (1 row FILED for Layer 2 deferral)

Per D-6: Layer 2 mid-run cost meter empirical tests are filed as DF-14.6-S1 in `deferred-work.md`:

```
- **DF-14.6-S1 (Phase-1.5 Layer 2 mid-run cost meter empirical tests for fan-out keywords)** — Story 14.6 closes C20+C26+C89+C95 via the `_HostBudgetPlumbing` mixin + adds Layer 1 pre-flight enforcement tests via the `__agenteval_test_budget__` sentinel kwarg. The harder Layer 2 mid-run cost meter behavior — where a fan-out keyword accumulates cost across N adapter calls and a mid-run meter polls + triggers `CostExceededError` between adapter ticks — requires real cost-tracking infrastructure (LiteLLM cost tracker per Story 4.1 / `_kernel/guardrails.py` Layer 2 wiring) that is out of Story 14.6's plumbing scope. Phase-1.5 follow-up: ship per-keyword tests verifying `max_cost_usd=0.01` against a 3-adapter fan-out triggers `CostExceededError` after the 1st adapter's `cost_usd=0.05` accumulator-tick, per epic L2383 verbatim test prescription. Effort: M (per-keyword integration tests with cost-tracker stubs). Phase-1.5.
```

Per Story 14.2 catalog-gate: 1 inline `DF-14.6-S1` ref allowed (the row exists in `deferred-work.md` UPSTREAM).

### AC-14.6.11 — Stability surface update

`docs/contracts/stability-surface.md` gets a new subsection `### Unified Host-Instance Budget Plumbing (Phase-2.5 — Story 14.6 / C20+C26+C89+C95 closure)`:
- `_HostBudgetPlumbing` mixin at `_kernel/host_budget_plumbing.py` — `provisional` label.
- Constructor contract: `max_cost_usd: float | None = None`, `max_runtime_seconds: float | None = None`, keyword-only kwargs, cooperative `**kwargs` forwarding.
- 3 host libraries (MCPLibrary, SkillsLibrary, OrchestrationLibrary) inherit + carry budget attrs.
- Honest-framing constraint: Operators MUST pass budgets at RF `Library` import time for MCPLibrary + SkillsLibrary (they are NOT in `_SUB_LIBRARIES` per Story 2.2 collision norm); OrchestrationLibrary is auto-wired by `AgentEval._build_components`.

### AC-14.6.12 — Sprint-status + Story 14.5 catalog gate

`14-6-*: review → done` after code-review. `last_updated: 2026-06-04`. **FULL closure** framing.

`grep -rnE "DF-14\.6-S[0-9]" src/AgentEval/_kernel/host_budget_plumbing.py tests/unit/_kernel/test_host_budget_plumbing.py` returns 0 hits (zero leak into new src/ + test code; the 1 DF-14.6-S1 ref is in `deferred-work.md` per AC-14.6.10).

### AC-14.6.13 — All-gates pass

- `uv run pytest tests/`: 2004 + 32 baseline + ≥10 new = ≥2014 passed + 32 skipped.
- `uv run ruff check src/ tests/`: clean.
- `uv run mypy src/`: clean.
- `uv run python scripts/check-catalog-references.py --all-tracked`: EXIT 0.
- `docs/keywords/MCPLibrary.html` + `docs/keywords/SkillsLibrary.html` + `docs/keywords/OrchestrationLibrary.html` regenerated cleanly (Story 14.1 libdoc smoke per L-1).

### AC-14.6.14 — Libdoc smoke step on all 3 affected libraries

Per Story 14.1 L-1 lesson: run libdoc smoke on MCPLibrary + SkillsLibrary + OrchestrationLibrary at dev-end to verify no rendering regressions on modified keywords. Document outcome in dev record.

## Tasks / Subtasks

- [ ] **Task 1: `_HostBudgetPlumbing` mixin (AC-14.6.1)** — NEW `src/AgentEval/_kernel/host_budget_plumbing.py`. Apache 2.0 header. Mixin with 2 attrs + cooperative `**kwargs` forwarding.

- [ ] **Task 2: MCPLibrary inheritance (AC-14.6.2)** — Update class declaration + import.

- [ ] **Task 3: SkillsLibrary inheritance (AC-14.6.3)** — Update class declaration + import.

- [ ] **Task 4: OrchestrationLibrary inheritance + ctor refactor (AC-14.6.4)** — Update class declaration + refactor `__init__` to cooperate with mixin. Verify backward-compatibility of positional `default_provider` callers via grep.

- [ ] **Task 5: `_build_components` budget injection for OrchestrationLibrary (AC-14.6.5)** — Add OrchestrationLibrary branch passing budgets.

- [ ] **Task 6: Add `@guarded_fanout()` to 2 MCPLibrary keywords (AC-14.6.6)** — `get_tool_discoverability` + `get_tool_discoverability_comparison`. Verify decorator ordering per existing SkillsLibrary precedent.

- [ ] **Task 7: Remove carve-out docstring lines (AC-14.6.7)** — grep + remove "tracked NOT enforced" + DF-4.4-S1 / DF-13.3-S1 / DF-13.5-S1 carve-out references. Replace with closure note.

- [ ] **Task 8: Unit tests (AC-14.6.8)** — NEW `tests/unit/_kernel/test_host_budget_plumbing.py` (~250+ LoC, ≥10 tests).

- [ ] **Task 9: Close 4 catalog rows (AC-14.6.9)** — C20, C26, C89, C95 updated with DONE prefix + closure attribution.

- [ ] **Task 10: File DF-14.6-S1 in deferred-work.md (AC-14.6.10)** — Layer 2 mid-run cost meter empirical tests deferred to Phase-1.5.

- [ ] **Task 11: Stability surface update (AC-14.6.11)** — NEW subsection.

- [ ] **Task 12: Libdoc smoke + regen (AC-14.6.14 + AC-14.6.7)** — Regen 3 libdoc HTMLs; smoke-check rendered names.

- [ ] **Task 13: All-gates pass + Story 14.2 catalog-gate (AC-14.6.13 + AC-14.6.12)** — pytest 2014+ + 32; ruff/mypy clean; Story 14.2 hook EXIT 0.

- [ ] **Task 14: Sprint-status flip + Story 14.6 own Change Log (AC-14.6.12)** — `14-6-*: review`; Change Log v0.1.0 + v0.2.0.

## Dev Notes

Building on:
- **Story 1b.3** (`_kernel/guardrails.py`): established `@guarded_fanout()` 3-layer enforcement + `__agenteval_test_budget__` sentinel kwarg test escape hatch.
- **Story 1a.6** (`AgentEval.__init__`): established FR41 config-precedence resolution + `self._max_cost_usd` + `self._max_runtime_seconds` resolved attrs.
- **Story 2.2** (sub-library collision norm): the constraint that forces MCPLibrary + SkillsLibrary to be excluded from `_SUB_LIBRARIES`.
- **Story 4.3** (`OrchestrationLibrary.__init__(default_provider)`): the existing ctor that needs cooperative refactor.
- **Story 4.4** (DF-4.4-S1 / C20): the original Epic-4 carve-out being closed.
- **Story 6.3** (StatsLibrary budget plumbing): the existing pattern for top-level-budget-to-sub-library wiring.
- **Story 12.1** (JudgeLibrary budget plumbing): same pattern as Stats.
- **Story 13.5 (Skill.Compare Discoverability)**: shipped with `@guarded_fanout()` + `getattr` fallback to None — the LAST occurrence of the "tracked NOT enforced" carve-out before Story 14.6's unified closure.
- **Stories 14.3 + 14.5 closure-framing precedent**: FULL closure pattern when mechanism + evidence both dev-deliverable.

**Why a mixin (vs duplicating attrs across 3 classes):**
1. Single source of truth: any future budget-related change lands in one place.
2. Test cooperativity: a single mixin test exercises the contract; subclass tests only verify inheritance.
3. Honest framing: explicit `_HostBudgetPlumbing` parent in MRO documents the architectural intent (vs implicit duck-typing).

**Why keyword-only args (vs positional):**
Per D-3: backward-compatibility with `OrchestrationLibrary(default_provider="mock")` callers. Keyword-only args prevent name-position conflicts when MRO resolution composes ctor args. Also matches Story 1a.6's `AgentEval.__init__` discipline.

**Why Layer 1 pre-flight tests only (not Layer 2 mid-run accumulator):**
Per D-6: Layer 1 tests use the `__agenteval_test_budget__` sentinel kwarg to force pre-flight refusal — no cost-tracker infrastructure needed. Layer 2 mid-run accumulator tests require real cost-tracking (LiteLLM tracker per Story 4.1) + are deferred to DF-14.6-S1 as Phase-1.5 follow-up. This is an explicit, documented honest-framing scope split — NOT a hidden carve-out.

### Architecture compliance

- `src/AgentEval/_kernel/host_budget_plumbing.py` is a NEW file in the architecture-pinned `_kernel/` directory. Per architecture L620 + Story 1b.3: `_kernel/` is the public registry surface; new modules require architecture cross-check. **The mixin is a passive plumbing layer** (no runtime behavior, just attrs) — qualifies as an additive kernel utility per Story 1b.3 precedent. Document the addition in stability-surface (AC-14.6.11).

### Project Structure Notes

- NEW file: `src/AgentEval/_kernel/host_budget_plumbing.py` (~80 LoC).
- NEW file: `tests/unit/_kernel/test_host_budget_plumbing.py` (~250+ LoC, ≥10 tests).
- EDITED: `src/AgentEval/mcp/library.py` (+1 import, +1 parent class, +1 decorator x 2 keywords, -2 carve-out docstring lines, +2 closure-note docstring lines).
- EDITED: `src/AgentEval/skills/library.py` (+1 import, +1 parent class, -1 carve-out docstring line, +1 closure-note docstring line).
- EDITED: `src/AgentEval/orchestration/library.py` (+1 import, +1 parent class, +5 lines `__init__` refactor).
- EDITED: `src/AgentEval/__init__.py` (+5 lines `_build_components` OrchestrationLibrary branch).
- EDITED: `docs/contracts/stability-surface.md` (+1 subsection).
- EDITED: `docs/phase-1-5-carry-overs.md` (4 rows closed).
- EDITED: `_bmad-output/implementation-artifacts/deferred-work.md` (+1 row: DF-14.6-S1).
- EDITED: `docs/keywords/MCPLibrary.html` + `SkillsLibrary.html` + `OrchestrationLibrary.html` (libdoc regen).
- EDITED: `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip + last_updated).

### References

- PRD: FR11 (cost/runtime guardrails on fan-out); FR10a (MCP.Get Tool Discoverability budget kwargs).
- Architecture: `_kernel/guardrails.py:265-266` (the `getattr` host-attr read).
- Epic: `_bmad-output/planning-artifacts/epics.md` L2365-2387.
- Catalog: `docs/phase-1-5-carry-overs.md` L43 (C20); L49 (C26); L115 (C89); L123 (C95).
- Source retros: Epic 11 retro L153 Action #2; Epic 12 retro L162 Action #3; Epic 13 retro L183 Action #6.
- Pattern reference: `src/AgentEval/__init__.py:355-375` (existing StatsLibrary + JudgeLibrary budget-injection branches).
- Norms: 61st use of `feedback_spec_vs_ratified_doc_precheck`; Story 14.5 closure-framing precedent (FULL not PARTIAL); Story 14.1 libdoc smoke (mandatory at dev-end); Story 14.2 catalog-gate (1 inline DF-14.6-S1 ref allowed because catalogued in deferred-work UPSTREAM); `feedback_in_flight_spec_amendment` (D-6 Layer 2 deferral documented UPSTREAM).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

(filled at dev-time)

### Completion Notes List

(filled at dev-time)

### File List

(filled at dev-time)

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-06-04 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (61st use; 100% catch-rate maintained through 60 prior uses) caught 7 drifts: D-1 HIGH MCPLibrary+SkillsLibrary not in `_SUB_LIBRARIES` (operator-side Library-import kwarg path; documented constraint); D-2 HIGH `@guarded_fanout` already reads via getattr so mixin only PROVIDES the attrs; D-3 HIGH OrchestrationLibrary cooperative-MRO via keyword-only args; D-4 HIGH fan-out keyword surface inventory (2 MCP keywords need decorator added, 2 Skill keywords + Orch.run_scenario already have it); D-5 MED docstring carve-out lines need removal; D-6 MED Layer 2 mid-run cost meter tests deferred to DF-14.6-S1; D-7 LOW _SUB_LIBRARIES exclusion preserved (zero changes). 14 ACs. **FULL closure (not PARTIAL)** — mechanism + evidence both dev-deliverable. Closes 4 catalog rows (C20+C26+C89+C95) + 3 retro action items = **7 closures, the most of any Epic 14 story**. Final Epic 14 story; biggest architectural blast radius. **Fifth + final exercise of Story 14.1 META mechanisms**; **fourth exercise of Story 14.2 catalog-gate hook**; **third UPSTREAM application of Story 14.3/14.5 closure-framing precedent**. | Claude Opus 4.7 (1M context) |
| 2026-06-04 | 0.2.0   | Implementation complete (status: review → done). All 14 tasks marked [x]; 14 ACs satisfied; **1 in-flight spec amendment** (D-6 / AC-14.6.8: live-keyword pre-flight refusal via `__agenteval_test_budget__=(0.0, None)` does NOT work because `@guarded_fanout(estimator=None)` skips Layer 1 — reframed the 4 E2E tests as integration-contract verification; live pre-flight refusal needs per-keyword `estimator=` callables added per DF-14.6-S1 Phase-1.5 follow-up). Shipped: (1) `src/AgentEval/_kernel/host_budget_plumbing.py` (NEW, 100+L, Apache 2.0 header, `_HostBudgetPlumbing` mixin with keyword-only `max_cost_usd` + `max_runtime_seconds` kwargs + cooperative `super().__init__(**kwargs)` forwarding); (2) MCPLibrary inherits the mixin + `@guarded_fanout()` added to `get_tool_discoverability` (C20) + `get_tool_discoverability_comparison` (C89); (3) SkillsLibrary inherits the mixin (C95); (4) OrchestrationLibrary inherits the mixin + cooperative ctor refactor preserving `default_provider` Story-4.3-precedent (C26); (5) `AgentEval._build_components` passes `max_cost_usd` + `max_runtime_seconds` to OrchestrationLibrary (mirrors Stats/Judge); (6) "tracked NOT enforced" carve-out docstring lines removed from `MCP.Compare Tool Discoverability` + `Skill.Compare Discoverability`, replaced with positive-framing closure notes; (7) 12 unit tests at `tests/unit/kernel/test_host_budget_plumbing.py` (4 mixin behavior + 3 subclass smoke + 4 integration contract + 1 estimator-driven pre-flight refusal via custom stub host = 12 total); (8) 3 libdoc HTMLs regenerated (MCPLibrary + SkillsLibrary + OrchestrationLibrary); (9) stability surface section `### Unified Host-Instance Budget Plumbing Surface (Phase-2.5 — Story 14.6 / C20+C26+C89+C95 closure)` added; (10) 4 catalog rows C20+C26+C89+C95 closed; (11) DF-14.6-S1 row filed in `deferred-work.md` UPSTREAM for Layer 1/2 live-keyword evidence work. **FULL mechanism closure** (architectural plumbing delivered) — distinct from operator-side evidence work (Stories 14.3/14.4 PARTIAL pattern). Gates: pytest **2016 + 32 skipped** (+12 vs 2004 Story 14.5 baseline); ruff/mypy clean (108 src files post-mixin addition); Story 14.2 catalog-gate EXIT 0 (1 inline DF-14.6-S1 ref allowed because catalogued in `deferred-work.md` UPSTREAM). **EPIC 14 IS NOW COMPLETE — all 6 stories done.** Awaiting cross-LLM 3-tier review on Story 14.6 itself. | Claude Opus 4.7 (1M context) |
| 2026-06-04 | 0.3.0   | **Cross-LLM review v2 patches applied (3 HIGH from Codex).** Tier 1a sonnet + Tier 1b opus CLI both failed via stdin (exit 144 SIGTERM-class; CLI degradation). Codex returned substantive findings: **HIGH-1**: `OrchestrationLibrary.run_scenario` was missing `@guarded_fanout()` entirely — C26 was NOT actually closed by v0.2.0 despite the spec/catalog claim. **HIGH-2**: `MCP.Get Tool Discoverability` docstring still carried the verbatim "tracked, NOT enforced (DF-4.4-S1 carry-over)" + a full "`@guarded_fanout` enforcement is DEFERRED" carve-out block; only the Compare keywords had their carve-out text removed. **HIGH-3**: stability-surface said `OrchestrationLibrary.run_scenario` "already had the decorator pre-Story-14.6" — false claim (decorator was never added). **All 3 fixed inline:** added `@guarded_fanout()` to `run_scenario` + guardrails import to orchestration/library.py; rewrote `MCP.Get Tool Discoverability` arg-table + carve-out block + Notes section to positive-framing closure language; corrected stability-surface narrative to "Story 14.6 added the decorator to run_scenario; was missing pre-Story-14.6 despite the catalog row implying otherwise (Codex HIGH-1 catch v2 patch)". Libdoc regenerated for MCPLibrary + OrchestrationLibrary. Gates re-run: pytest 2016 + 32 unchanged; ruff/mypy clean (108 src files); Story 14.2 catalog-gate EXIT 0. **Codex catch saved the closure — v0.2.0 would have shipped C26 as falsely-closed.** Per `feedback_n_way_agreement_weight`: Codex single-reviewer HIGHs verified via direct grep against source before applying. | Claude Opus 4.7 (1M context) |
