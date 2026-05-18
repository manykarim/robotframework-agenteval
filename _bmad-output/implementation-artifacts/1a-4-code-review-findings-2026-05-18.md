# Story 1a.4 Code Review Findings (2026-05-18)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1.

**Verdict:** **Changes Requested** — 6 HIGH + 3 MED + 1 LOW findings, all CONTENT-ACCURACY issues (no structural ratification problems). Several findings expose **pre-existing inter-document drift between PRD + epics + ratified ADRs** that Story 1a.4 surfaces but did not cause.

---

## Methodology

1. **Claude independent re-verification** of Story 1a.4's 7 dev gates (file count, 4-section assertion, cross-ref resolution, README sort, 11-leaf table consistency, sub-section convention, status banner format). All 7 PASSED.

2. **Codex CLI adversarial pass** via GitHub MCP — Codex fetched every contract + the PRD + epics + ADR-014 + ADR-016 + ADR-018 and cross-checked claims against ratified sources. Codex found **10 findings**; Claude solo found **0** (4th time the same-family blind spot pattern has emerged).

3. **Claude spot-verified all 10 Codex findings locally** via grep against PRD/epics/ratified-ADR contents. **All 10 confirmed real.**

---

## Findings

### HIGH

#### HIGH-1: Listener class path + hook surface inconsistent across PRD + epics + contracts

**Files:** `docs/contracts/listener-integration.md` L16/21/36/41; `docs/contracts/junit-xml-enrichment.md` L17; `_bmad-output/planning-artifacts/prd.md` L1545; `_bmad-output/planning-artifacts/epics.md` L1288-1292, L1628-1659

**Drift:** 3 different listener class paths cited (`Library AgentEval.telemetry.Listener` vs `robot --listener AgentEval.telemetry.Listener` vs `agenteval.telemetry.Listener`) + 2 different hook names (`output_xml` per my contract vs `xunit_file(path)` per epics.md/PRD). Implementing epic (Epic 5 Story 5.1 + Epic 8a Story 8a.1) cannot satisfy both simultaneously.

**Recommended fix:** Architect ratifies ONE canonical listener path + hook list. Probably `AgentEval.telemetry.Listener` (matches the `src/AgentEval/` package convention) + `xunit_file(path)` (the documented RF Listener v3 hook for xUnit emission). Update both contracts + PRD FR33a/FR49 + Epic 5/8a stories.

---

#### HIGH-2: `mcp_coverage` enum has 3 values in ratified ADR-016 vs 4 values in PRD (pre-existing drift surfaced)

**Files:** `docs/contracts/mcp-coverage-detection.md` L10/16-20/31-35 (cites 3-value enum per ADR-016); `_bmad-output/planning-artifacts/prd.md` L551/922/1364 (cites 4-value enum); `docs/adr/ADR-016-mcp-coverage-detection-default.md` (ratified Epic 0 — 3-value enum); ADR-007 (also 3-value per my Story 1a.3 ratification)

**Drift:** PRD uses `Literal["complete", "library_only", "external_mixed", "no_mcp"]` (4 values). Ratified ADR-016 (Story 0.3 Epic 0) uses `Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` (3 values). Story 1a.4's contract correctly cites the ratified ADR-016 enum — **Story 1a.4 is not the source of this drift; the PRD predates Epic 0 ratification.**

**Recommended fix (architect decision):**
- **Option A (Recommended):** PRD stale text update — ADR-016 is the ratified source-of-truth post-2026-05-17. Update PRD L551/922/1364 to cite the 3-value enum. Sprint-status note + CHANGELOG entry.
- **Option B:** Re-ratify ADR-016 back to a 4-value enum (and update Story 1a.3 ADR-001 catalog row + this contract). Heavier; questions Story 0.3 spike findings.

---

#### HIGH-3: `error-class-hierarchy.md` Integrity exit codes "2 or 3 (per-leaf override)" never resolves per-leaf

**Files:** `docs/contracts/error-class-hierarchy.md` L49-52 (Integrity row says "2 or 3 (per-leaf override)"); L113-116 (FR50 mapping cites family codes); `_bmad-output/planning-artifacts/prd.md` L144 (PRD FR50 pins specific per-leaf codes)

**Drift:** PRD FR50 pins: `IncompleteTraceError` → 2 (Integrity family with override); `PollingDisallowedError` → 3 (family default). My contract's "2 or 3" hedge is not actionable for Epic 8a Story 8a.1 implementers.

**Recommended fix:** Add a per-leaf exit-code column to the per-leaf inventory tables in error-class-hierarchy.md. Specifically: `IncompleteTraceError → 2`; `PollingDisallowedError → 3`; `TierViolationError → 3` (default family value; document explicit override pattern).

---

#### HIGH-4: `ValidateOperator*` exception class has 3 different names across the corpus

**Files:** ratified `docs/adr/ADR-014-error-class-hierarchy.md` L23 (uses `ValidateOperatorDisallowed` — no `Error` suffix); `_bmad-output/planning-artifacts/prd.md` L1562 (uses `ValidateOperatorDisabledError`); `_bmad-output/planning-artifacts/epics.md` L1490 (uses `ValidateOperatorDisallowedError` — with `Error` suffix)

**Drift:** ADR-014 (ratified Story 1a.3) is the canonical source → name = `ValidateOperatorDisallowed`. My contract follows ADR-014 correctly. **PRD + epics need to be updated to match the ratified ADR-014 name.**

**Recommended fix:** Confirm `ValidateOperatorDisallowed` (no `Error` suffix; matches ADR-014 + my contract + determinism-contract). Update PRD L1562 + epics.md L1490 to match.

---

#### HIGH-6: PRD FR50 (family codes 1/2/3) vs epics.md (sysexits-style 65/66/67/68) contradict each other

**Files:** `_bmad-output/planning-artifacts/prd.md` L144 (FR50 says `1 = assertion fail; 2 = CostExceededError or IncompleteTraceError; 3 = UnsupportedMCPVersion... / PollingDisallowed...`); `_bmad-output/planning-artifacts/epics.md` L1660 (Epic 8a Story 8a.1 says `PollingDisallowedError → 65, CostExceededError → 66, IncompleteTraceError → 67, UnsupportedMCPVersionError → 68, etc.`)

**Drift:** PRD freezes a 1/2/3 family scheme; epics.md Story 8a.1 freezes a sysexits-style 65-68 per-leaf scheme. **My contract followed PRD's family scheme.** Cannot satisfy both. Epic 8a Story 8a.1 cannot be implemented against an authoritative table until one wins.

**Recommended fix (architect decision):**
- **Option A:** PRD wins — family codes 1/2/3 stay; update epics.md L1660 to use family codes.
- **Option B:** Epics wins — sysexits 65-68 per-leaf; update PRD FR50 + my contract to match. **More conventional Unix CLI behavior** (sysexits.h codes 64-78 are standard).
- **Option C (Recommended):** Use sysexits-style (Option B) because it's the conventional CLI exit-code scheme + provides finer-grained signal to CI consumers. Update all 3 sources.

---

#### HIGH-8: `stability-surface.md` Contract section labels only 4 sandbox elements; promised public-element registry is empty

**Files:** `docs/contracts/stability-surface.md` L10/17/36-45 (claims to label all public elements); `_bmad-output/planning-artifacts/prd.md` L1595/1648 (FR64 + NFR-MAINT-05 require per-element labels); other contracts' Change Policy sections all reference stability-surface.md labels

**Drift:** Other contracts (`evidence-block-format.md`, `determinism-contract.md`, etc.) reference `stability-surface.md` labels in their Change Policy sections, but stability-surface's Contract section only labels 4 sandbox-related elements. The "every public element has a label" claim doesn't hold; FR64/NFR-MAINT-05 not meaningfully satisfied.

**Recommended fix (architect decision):**
- **Option A (Recommended):** Narrow stability-surface.md's contract scope to honest Phase-1 stub posture — explicitly state "the per-element registry is filled by Story 1a.6 + each epic-owning story as elements are wired"; the only Phase-1 entries are the sandbox surface (which Story 1a.1 baseline already shipped). Other contracts' Change Policy references stay valid; they just point to a known-stub registry.
- **Option B:** Story 1a.4 dev populates the full registry now — requires enumerating every public element from Story 1a.1 baseline + each ratified ADR. ~50-100-line table addition.

---

### MEDIUM

#### MED-5: `error-class-hierarchy.md` per-leaf owning-epic table has at least 2 wrong assignments

**File:** `docs/contracts/error-class-hierarchy.md` L76, L85; verified against `_bmad-output/planning-artifacts/epics.md`

**Wrong assignments:**

- `UnsupportedMCPVersionError`: my contract says "Epic 5 Story 5.2"; epics.md Story 3.1 (L1078-1080) actually owns it via FR46 + AC-MCP-OBSERVE-02.
- `PollingDisallowedError`: my contract says "Epic 1b (AssertionEngine wiring) + Phase-2 full ADR-022 adoption"; epics.md Epic 6 (L486-490) actually owns the enforcement via FR28.

Other leaves' assignments should also be re-audited.

**Recommended fix:** Re-audit each of the 11 per-leaf rows against epics.md FR-coverage + story breakdown; correct the owning-story column.

---

#### MED-7: FR59 example invents `allow_unsafe_code_execution=True` flag that ADR-018 doesn't define

**File:** `docs/contracts/error-class-hierarchy.md` L108 (the SANDBOX_REQUIRED example's `Fix:` line)

**Issue:** My FR59 example says:
> `Fix: Configure a sandbox backend via 'agenteval.sandboxes' entry-point OR set 'allow_unsafe_code_execution=True' (not recommended).`

ADR-018 §Decision does NOT define a Library `__init__` flag called `allow_unsafe_code_execution`. It only describes the `NullSandbox` default + entry-points-plugin backend registration. The flag is fabricated.

**Recommended fix:** Replace the `Fix:` line to cite only the entry-points sandbox-backend registration (the actual ADR-018 mechanism). Drop the `allow_unsafe_code_execution=True` invention.

---

#### MED-9: `evidence-block-format.md` cross-references `listener-integration.md` for adapter population, but listener-integration.md doesn't cover that

**Files:** `docs/contracts/evidence-block-format.md` L24/37/45-47; `docs/contracts/listener-integration.md` (entire); `_bmad-output/planning-artifacts/epics.md` L1342-1344 (Epic 5.3 says implementation follows `otel-trace-visual.md`)

**Drift:** evidence-block-format.md says "How adapters populate the block — see `listener-integration.md` and per-adapter contracts in Epic 4." But listener-integration.md is about RF Listener v3 hooks, not evidence-block production. Per epics.md Epic 5.3, implementation actually follows `otel-trace-visual.md` (closer match — OTel attributes drive evidence-block content).

**Recommended fix:** Make `evidence-block-format.md` the authoritative source for block production. Cross-reference: point to OTel listener (`listener-integration.md` for the hook surface) AND otel-trace-visual.md (for the span attribute mapping). Update Epic 5.3 cross-references to land at evidence-block-format.md.

---

### LOW

#### LOW-10: `evidence-block-format.md` cites `FR60` but FR60 is `AdapterVersionDriftWarning`; evidence-block is FR34a/FR34b

**File:** `docs/contracts/evidence-block-format.md` L6 (banner cites FR60); L47 (References cites FR60+); `_bmad-output/planning-artifacts/prd.md` L1547-1548 (FR34a + FR34b are the actual evidence-block FRs); L1588 (FR60 = `AdapterVersionDriftWarning`)

**Drift:** Direct FR mis-citation. FR60 is about adapter version-drift warnings, not evidence blocks.

**Recommended fix:** Replace "FR60+" with "FR34a + FR34b" in the banner + References section.

---

## Triage summary

| Severity | Count | Findings | Scope |
|---|---|---|---|
| HIGH | 6 | HIGH-1 (listener), HIGH-2 (mcp_coverage), HIGH-3 (exit codes Integrity), HIGH-4 (ValidateOperator name), HIGH-6 (FR50 codes), HIGH-8 (stability-surface registry) | 4 cross-document, 2 contract-internal |
| MED | 3 | MED-5 (owning-epic), MED-7 (FR59 example flag), MED-9 (evidence-block cross-ref) | Contract-internal |
| LOW | 1 | LOW-10 (FR60 mis-cite) | Contract-internal |

**Cross-LLM coverage demonstration (4th time):** Claude solo PASSED all 7 dev gates on re-verification but found 0 findings. Codex caught all 10. The same-family blind spot pattern continues to be load-bearing.

**Pre-existing drift exposed but NOT caused by Story 1a.4:** HIGH-1, HIGH-2, HIGH-4, HIGH-6 — these are PRD ↔ epics ↔ ratified-ADR drifts that Story 1a.4's contract authoring surfaced. The contracts themselves are accurate against their cited authoritative source (ADR-014, ADR-016, etc.); the drift is in the OTHER source documents.

## Recommended action

Apply contract-internal fixes (HIGH-3, HIGH-8, MED-5, MED-7, MED-9, LOW-10) immediately — these are ~30-line patches within `docs/contracts/`. For cross-document drift (HIGH-1, HIGH-2, HIGH-4, HIGH-6), need Many's architect decisions on which source wins, then update PRD + epics + contract together. The "fix the losing source NOW" pattern from Story 1a.2 / 1a.3 ratifications applies.

The biggest call is HIGH-6 (FR50 1/2/3 family codes vs 65/66/67/68 sysexits). This will propagate into Epic 8a Story 8a.1's implementation; architect should ratify before that story lands.
