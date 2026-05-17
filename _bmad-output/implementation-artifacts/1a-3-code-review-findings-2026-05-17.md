# Story 1a.3 Code Review Findings (2026-05-17)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1.

**Verdict:** **Changes Requested** — 2 HIGH + 2 MED + 1 LOW findings. None block story acceptance once patched; all are content-accuracy issues, no structural ratification problems.

---

## Methodology

1. **Claude independent re-verification** of dev-story's 8 gates (sha256, MADR sections, renumbering history, cross-ref resolution, README accuracy, catalog coverage, sidecar cleanup, CI forensics).
2. **Codex CLI adversarial review** of all 14 new ADRs + ADR-001 catalog + README + sidecars + story spec. Codex used GitHub MCP to fetch agentguard's source ADRs and cross-check catalog classifications against agentguard's actual text.
3. **All Codex findings spot-verified by Claude** before triage.

Claude's 8 gates all PASSED on re-verification:
- §Amendments Log sha256 `9ff36b0b...` matched byte-identical
- 14/14 new ADRs have 4 strict-match MADR sections
- 14/14 have renumbering history lines
- 14/14 README rows match in-file renumbering history
- Cross-reference resolution 100%
- Sidecar L117 + L51 cleanups correct
- CI runs post-push (ci + security-scan) green with no hidden warnings (cache 400 is GHA transient, not our code)

## Findings (Codex caught 5; Claude solo found 0 — same-family blind spot demonstrated again)

### HIGH

#### HIGH-1: agentguard ADR-013 row in catalog overstates inheritance (`adopt-verbatim` is wrong)

**File:** `docs/adr/ADR-001-architectural-influences-catalog.md` (agentguard ADR-013 row in §Body)

**Codex claim, Claude-verified:**

agentguard ADR-013 (`/home/many/workspace/robotframework-agentguard/docs/adr/ADR-013-sandbox-policy.md`) explicitly requires:
- **Inspect AI sandbox toolkit integration** (Docker / K8s pods-per-sample / Proxmox)
- **`--allow-code-execution`** flag (Library `allow_code_execution=${TRUE}` opt-in)
- `CodeExecutionDeniedError` as the gate error
- `agentguard[sandbox]` extras for the Inspect AI dep

agenteval ADR-018 materially diverges:
- NO Inspect AI dependency (entry-points-plugin model via `agenteval.sandboxes`)
- NO `--allow-code-execution` flag (`NullSandbox` default + opt-in via configured backend)
- `SandboxRequiredError(AgentEvalSafetyError)` (different error class + hierarchy)
- Phase-3 backend deferral (agentguard's Phase 1 ships Inspect AI)

This is not `adopt-verbatim` — agenteval preserves the policy idea (sandbox-required gate) but reshapes the backend story. The catalog decision label is materially wrong.

**Recommended fix:** change ADR-013 row's decision column from `` `adopt-verbatim` `` to `` `adapt` ``; rewrite rationale to name what's preserved (sandbox-required posture, gate-on-refusal semantics) and what's diverged (Phase-1 backend strategy, opt-in mechanism, Protocol vs flag). Aligns with the "11 adapt + 1 adopt-verbatim" pattern (the only true `adopt-verbatim` would then be for industry standards like OTel GenAI semconv + MCP spec where agenteval implements verbatim against external spec text).

---

#### HIGH-2: ADR-017 conformance entry point path is incoherent — `tests/conformance/__init__.py` is outside the shipped wheel

**File:** `docs/adr/ADR-017-conformance-suite-organization-per-ac-test-files.md` L48 (Entry point bullet)

**Codex claim, Claude-verified:**

ADR-017 documents:
> **Entry point** — `tests/conformance/__init__.py` enables `python -m agenteval.conformance [--adapter <name>]` per FR45 + FR57.

But `pyproject.toml` line 102 sets `[tool.hatch.build.targets.wheel] packages = ["src/AgentEval"]` — `tests/` is NOT shipped in the wheel. A community adapter author who `pip install agenteval` then runs `python -m agenteval.conformance` gets `No module named 'agenteval.conformance'`. The advertised UX is impossible as written.

**Recommended fix (architect decision required):**
- **Option A (recommended for architecture honesty):** Change ADR-017 to document the conformance harness as living at `tests/conformance/` AND a Phase-2-deliverable thin proxy at `src/AgentEval/conformance/__init__.py` that re-exports or invokes the harness. Community-author UX `python -m agenteval.conformance` lands in Phase 2; Phase-1 community authors use `pytest tests/conformance --adapter <name>` (matching what `conformance.yml` actually invokes).
- **Option B (simpler):** Drop the `python -m agenteval.conformance` claim entirely. Document the entry as `python -m pytest tests/conformance` and note that a CLI proxy is out-of-scope for Phase 1.

---

### MEDIUM

#### MED-1: ADR-013 "5 `agenteval.*` entry-point groups" should be "4 in namespace + 1 legacy = 5 agenteval-owned tables"

**File:** `docs/adr/ADR-013-entry-points-discovery-infrastructure.md` Decision section + Consequences section

**Codex claim, Claude-verified:** pyproject.toml actually declares:
- `agenteval.coding_agents`
- `agenteval.providers`
- `agenteval.judges`
- `agenteval.sandboxes`

= **4 groups in the `agenteval.*` namespace** + 1 legacy `robotframework_agenteval.adapters` (agenteval-owned, pre-naming-convention) + 1 RF-owned `robot.listener` = **6 tables total**.

ADR-013 says "5 `agenteval.*` entry-point groups" → wrong on the namespace count. The "5 agenteval-owned tables" framing (used elsewhere, e.g., ADR-018) is correct but a different counting axis.

**Recommended fix:** normalize wording in ADR-013 to:
> 4 entry-point groups in the `agenteval.*` namespace (coding_agents, providers, judges, sandboxes) + 1 legacy agenteval-owned group (`robotframework_agenteval.adapters`, FR17a registration mechanism predating the namespace convention) + 1 RF-owned `robot.listener` (FR33a) = **6 entry-point tables total, of which 5 are agenteval-owned**.

This wording matches Story 1a.1's `pyproject.toml` comment + matches ADR-018's count.

---

#### MED-2: ADR-010 cites ADR-013 for "Generic LiteLLM-backed adapter" — ADR-013 is Entry-Points Discovery, not the Generic adapter

**File:** `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` L37 (Consequences section)

**Text in question:**
> Generic LiteLLM-backed adapter (ADR-013) doesn't apply this strategy — it's SDK-driven, not subprocess-driven...

**Issue:** ADR-013 is Entry-Points Discovery Infrastructure. There is no separate "Generic LiteLLM adapter" ADR in Story 1a.3's ratifications. The Generic adapter is described in ADR-003 (CodingAgentAdapter Protocol — Internal Class Split) as an SDK-style adapter inheriting from `InProcessAdapter` (no standalone ADR for it; the pattern lives in ADR-003).

**Recommended fix:** change "(ADR-013)" → "(see ADR-003 §Decision — Generic LiteLLM-backed adapter inherits from `InProcessAdapter`)" or drop the ADR-NNN citation entirely.

---

### LOW

#### LOW-1: ADR-014 "9 leaves explicitly named" but table names 11 leaves

**File:** `docs/adr/ADR-014-error-class-hierarchy.md` L32 (Decision section bullet)

**Text in question:**
> 9 leaves explicitly named above; additional leaves require an ADR amendment to keep the surface auditable.

**Actual leaf count from the table above this line:**
- AgentEvalSafetyError: 2 (`SandboxRequiredError`, `ValidateOperatorDisallowed`)
- AgentEvalBudgetError: 2 (`CostExceededError`, `RuntimeBudgetExceededError`)
- AgentEvalCompatError: 4 (`UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `AdapterDiscoveryError`, `AdapterVersionDriftWarning`)
- AgentEvalIntegrityError: 3 (`PollingDisallowedError`, `IncompleteTraceError`, `TierViolationError`)

**Total: 11 leaves.** The "9 leaves" count came from the original architecture-backlog sidecar text before agenteval added `UnsupportedBinaryVersionError` + `AdapterVersionDriftWarning` to AgentEvalCompatError.

**Why LOW (not MED):** the substance is fine — the hierarchy itself is correct + the table is authoritative. The "9" is wrong in one bullet text but doesn't affect downstream consumers. Norm #2 violation (machine-verifiable numeric claim should have been counted before commit).

**Recommended fix:** change "9 leaves explicitly named" → "11 leaves explicitly named" in ADR-014 L32.

---

## Triage summary

| Severity | Count | Findings |
| --- | --- | --- |
| HIGH | 2 | HIGH-1 (sandbox `adopt-verbatim`→`adapt`), HIGH-2 (conformance entry-point path incoherent) |
| MED | 2 | MED-1 (entry-point group count wording), MED-2 (wrong ADR cross-ref) |
| LOW | 1 | LOW-1 (numeric drift "9 leaves" → 11) |

**Cross-LLM coverage demonstration:** Claude's independent verification PASSED all 8 dev-story gates. The 5 findings are entirely from Codex's adversarial pass. Specifically: Codex caught classification accuracy issues (HIGH-1, MED-2), architecture-vs-doc coherence issues (HIGH-2, MED-1), and a numeric-claim drift (LOW-1) that Claude solo would have shipped. The cross-LLM-family pair is structurally necessary — same-family blind spots (here: Claude's "this is consistent" implicit checks didn't catch its own consistency drift) are real.

## Recommended action

Apply HIGH-1 + HIGH-2 (mandatory before `done`) + MED-1 + MED-2 + LOW-1 (high-value cleanup, near-trivial cost). Total estimated patch work: ~15-line edits across 4 files; no structural code changes.

HIGH-2 needs architect decision between Option A (Phase-2 proxy at `src/AgentEval/conformance/`) vs Option B (drop the `python -m agenteval.conformance` claim, point to `pytest tests/conformance` instead).
