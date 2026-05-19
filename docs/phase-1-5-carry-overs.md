# Phase-1.5 Carry-Overs Catalog

**Status:** Active tracking catalog. Updated as items land OR new Phase-1.5 carry-overs surface during Phase-1 work.
**Last updated:** 2026-05-19 (Story 1-5-1).
**Owning epic:** mini-epic 1.5 (Phase-1.5: Hygiene + Carry-overs); tracking story `1-5-1`.
**Related artifacts:** `_bmad-output/implementation-artifacts/deferred-work.md` (by-source-story breakdown), `_bmad-output/planning-artifacts/epics.md` Epic 9 (Phase-1 closeout — final consolidation point).

## Purpose

This catalog is the **single execution-facing view** of every Phase-1.5 carry-over. The companion `deferred-work.md` is indexed by source story (which story flagged the item); this catalog is indexed by execution priority + ownership + acceptance criteria. The two docs coexist: source-of-record in `deferred-work.md`; the actionable cleanup catalog here.

The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1a Action #5 → Epic 2 Action #4 (ratified 2026-05-19 by Many) — this catalog **closes** the chain.

## How to use this catalog

- **Picking up an item:** Assign yourself in the `owner` column. If the item is XS/S (under 2h), close it as a drive-by during related epic work; no separate story needed. If M/L (≥half-day), create a sibling story under `epic-1-5` with key `1-5-<N>-<short-name>`.
- **Verifying completion:** The `acceptance criteria` column describes HOW to assert done — usually a test, a file existence check, OR a contract-doc state.
- **Adding new items:** When a code review or story retro surfaces a Phase-1.5 carry-over, add a row here AND in `deferred-work.md` (under the appropriate source-story heading). Don't drop items; the chain stays unbroken.

## Catalog

| ID | Description | Source | Priority | Effort | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| **C1** | macOS CI validation for the unit + acceptance-tier1 + acceptance-smoke matrix. Architecture target was `Python 3.12+3.13 × Linux+macOS`; Phase-1 ships Linux-only per D2.1 architect waiver (Story 0.2 review 2026-05-17). | Epic 0 D2.1 waiver + Story 0.2 review | hygiene | M | TBD | `.github/workflows/ci.yml` matrix extended with `os: [ubuntu-latest, macos-latest]` AND all gates pass on macOS for ≥3 consecutive CI runs |
| **C2** | Full dogfood integration with rf-mcp + robotframework-agentskills repos via cross-repo CI workflow (currently only static-inspection samples + tests cited at Story 2.4; runtime cross-repo dogfood is Phase-1.5). | Epic 0 retro + Story 9.x | correctness | L | TBD | A new `.github/workflows/dogfood-cross-repo.yml` clones rf-mcp + robotframework-agentskills, runs agenteval against their real test suites, asserts ≥1 keyword successfully invoked per repo |
| **C3** | DCO sign-off check workflow (`DCO` GitHub App OR `git-check-dco` CI step). Currently DCO compliance is convention-enforced via `git commit -s` per CLAUDE.md but not CI-gated. | Epic 0 retro carry-over | hygiene | XS | TBD | New `.github/workflows/dco.yml` enforces sign-off on every commit; CONTRIBUTING.md cites the gate |
| **C4** | Pull-request template (`.github/pull_request_template.md`) with sections for: summary, test plan, drift-check note (if applicable), cross-LLM review status. | Epic 0 retro carry-over | documentation | XS | TBD | `.github/pull_request_template.md` exists with the 4 sections + `gh pr create` picks it up automatically |
| **C5** | SHA-pin all `uses:` references in CI workflows (`actions/checkout@v4` → `actions/checkout@<commit-sha>`) per supply-chain hardening. | Epic 0 retro carry-over | correctness | S | TBD | All 7 workflows under `.github/workflows/*.yml` use `@<40-char-sha>` form for every `uses:`; `dependabot.yml` configured to bump SHAs |
| **C6** | `agenteval` CLI proxy for the conformance suite (`agenteval conformance run`) per FR50 exit-code mapping. CLI exit-code translation layer reads each leaf's `error_code` string (the catalog L60-95 lookup table), translating to sysexits.h-style integer codes. | Epic 0 retro + Story 1a.4 ratification | correctness | M | TBD | `agenteval conformance run` exits with `65` (EX_DATAERR) on `InvalidSkillFrontmatterError`, `66` on `CostExceededError`, etc., per error-class-hierarchy.md L60-95 |
| **C7** | **Pydantic migration consolidated tracker (`DF-1b.5-S2`).** types.py docstrings claim a Phase-1.5 Pydantic migration is tracked here. Trigger: when Epic 5's OTLP serialization needs validation. Affected dataclasses across stories: `ToolCallTrace` + `Usage` + `RunManifest` (Story 1b.2); `AgentRunResult` + `AgentRunMetadata` (Story 1b.4); `ConformanceFixture` + `ConformanceResult` (Story 1b.5). | Story 1b.5 Acceptance Auditor F2 | hygiene | L | TBD | All 7 `@dataclass(frozen=True)` types migrated to Pydantic `BaseModel` in one PR; mypy clean; existing tests pass |
| **C8** | **FR63 doc-build CI gate (`DF-1b.6-S1`).** Phase-1 ships the verbatim PRD L1211 summary inline in `determinism-contract.md` per H1 patch; the doc-build CI gate that ENFORCES byte-identity needs an `mkdocs-build` workflow that doesn't exist yet. | Story 1b.6 Auditor F1 + Codex H3 + Blind#8 | correctness | M | TBD | New `.github/workflows/docs-build.yml` runs `mkdocs build --strict` AND asserts `determinism-contract.md` L<N>-L<M> matches PRD L1211 byte-for-byte |
| **C9** | **Verb allowlist into `coding-conventions.md` (`DF-1b.6-S2`).** `_VERB_ALLOWLIST` in `test_keyword_name_idiom.py` is de-facto source of truth; the AC + test docstring cite `coding-conventions.md` but that doc is silent on the verb rule. | Story 1b.6 Codex MED + Auditor F4 + Blind#9 | documentation | XS | TBD | `docs/contracts/coding-conventions.md` `### Naming Conventions` table has a "Keyword names start with a verb from the allowlist" row pointing to `_VERB_ALLOWLIST` as canonical source |
| **C10** | **Long-stdout / unbounded-events memory test (`DF4`).** `events: list[ParsedEvent]` accumulator is unbounded; very long event streams could OOM. Story 4.2 (Claude Code CLI adapter) will be the first place this gets exercised in anger. | Edge Case Hunter (Story 1b.4 review) | correctness | S | TBD | A `tests/integration/cli_adapter/test_long_stdout.py` test injects a 1M-event stream + asserts peak-memory < 200MB |
| **C11** | **Convention-tests empty-set fake-green hardening (`DF-1b.6-S4`).** Phase-1 ships zero `library.py` files; even with `SRC_ROOT.exists()` guard, all 5 per-AC tests trivially pass via empty-set early return. `test_violation_detection.py` proves assertion-failure branches are reachable, but doesn't guarantee future test-loop changes preserve that property. | Story 1b.6 Edge cluster | correctness | M | TBD | Convention tests refactored to mutation-style: add a sentinel `library.py` to a tmp dir + run each conventions test against it; assertion-failure branches always exercised |
| **C12** | **Epic 2: `exit_code` ClassVar on the 16 error leaves.** Per `docs/contracts/error-class-hierarchy.md` L121 + Story 2.3 C3 ratification: per-leaf `exit_code: ClassVar[int]` was deferred to Phase-1.5 alongside the CLI implementation (C6). Pre-C6 only the contract table is authoritative; post-Phase-1.5 the leaf class attribute IS the source of truth. | Epic 2 retro Action #4 | correctness | S | TBD | All 16 leaves in `src/AgentEval/errors.py` have `exit_code: ClassVar[int] = N` matching `docs/contracts/error-class-hierarchy.md` L60-95 per-leaf table |
| **C13** | **Epic 2: `_parser.py` → `_internal.py` rename hygiene.** Architecture L843-847 pins `_internal.py` as the canonical helper module name. Stories 2.1 + 2.2 + 2.3 named the helpers `_parser.py` for clarity. Deviation tracked in 3 module docstrings. | Auditor MED-2 across Stories 2.1 + 2.2 + 2.3 | hygiene | S | TBD | `src/AgentEval/{skills,subagents,hooks,mcp}/_parser.py` renamed to `_internal.py` (or architecture L843-847 amended to allow purpose-specific helper module names); all import sites updated; deviation-tracker docstrings removed |
| **C14** | **Epic 2: `_build_pointer` duplication consolidation.** 3 copies of the RFC 6901 JSON Pointer helper currently live in `hooks/_parser.py`, `mcp/_parser.py`, and (implicitly via inheritance pattern) any future sub-library that emits JSON Pointers. | Story 2.3 spec emergent note | hygiene | S | TBD | New `src/AgentEval/_kernel/jsonptr.py` module exports `build_pointer(*segments)`; hooks + mcp + future sub-libraries import from there; the 3 local copies are removed |
| **C15** | **Epic 2: architecture L854 `MCPKeywords` → `MCPLibrary` rename.** Architecture's MCP sub-library example uses `MCPKeywords`; shipped class is `MCPLibrary` (matches Stories 2.1 + 2.2 `*Library` suffix convention). Sibling architecture references at L850-855 also drift. | Story 2.3 Auditor LOW + Story 2.4 Auditor LOW | documentation | XS | TBD | `_bmad-output/planning-artifacts/architecture.md` L850-855 updated to use `MCPLibrary` (matching shipped convention); siblings consistent |
| **C16** | **Epic 2: rf-mcp sample drift-detection (checksum gate).** `tests/integration/static_inspection/samples/rf-mcp.mcp.json` is a verbatim copy of `/home/many/workspace/rf-mcp/.mcp.json`. When rf-mcp's source changes upstream, the local copy silently drifts. | Story 2.4 Edge-cases MED-3 | correctness | S | TBD | A `scripts/sync-rf-mcp-sample.py` script computes sha256 + asserts equality with upstream OR a documented sync-cadence comment with the source-revision SHA at copy time |
| **C17** | **Epic 2: `test_loader_smoke.py` adapter allow-list dynamic discovery.** Story 2.4 side-fix hardcoded `_ADAPTER_FIXTURE_DIRS = ("generic", "claude_code_cli")` to scope the loader-smoke discovery. Future Epic 4/Epic 11 adapter dirs (`litellm`, `openai_assistants`, etc.) are silently dropped from the loader until someone remembers to edit the constant. | Story 2.4 Blind LOW | hygiene | XS | TBD | `_ADAPTER_FIXTURE_DIRS` replaced with dynamic discovery (`any subdir NOT in {"static_inspection"}`); future adapter directories auto-discovered |

**Total: 17 catalog items.** Effort breakdown: 4 XS (≤30 min each), 5 S (≤2h each), 5 M (half-day each), 3 L (full-day each).

## Execution policy

- **Opportunistic close** (XS/S items): drive-by fixes during related epic work. e.g., when Epic 5 lands OTLP serialization (C7's trigger), the Pydantic migration ships in the same PR.
- **Dedicated micro-story** (M/L items): create `1-5-<N>-<short-name>.md` under `_bmad-output/implementation-artifacts/`; same workflow as any other story.
- **Final consolidation**: Epic 9 Story 9.3 (Phase-1 retrospective + FR65 exit criteria) reviews this catalog at Phase-1 close; any unaddressed items either get owners assigned or get explicitly deferred to Phase-2.

## Status legend

- **TBD**: no owner assigned yet.
- **<name>**: owner assigned; expect status update on next sprint cadence.
- **DONE (date)**: closed; row stays in catalog with the closure date for audit trail.

## References

- `_bmad-output/implementation-artifacts/deferred-work.md` — by-source-story breakdown (complementary index).
- `_bmad-output/implementation-artifacts/epic-2-retro-2026-05-19.md` — Action #4 ratified this catalog's creation.
- `_bmad-output/implementation-artifacts/epic-1a-retro-2026-05-18.md` — Action #5 first flagged the Phase-1.5 backlog ownership gap.
- `_bmad-output/implementation-artifacts/epic-0-retro-2026-05-17.md` — Action #6 originated the chain.
- `_bmad-output/planning-artifacts/epics.md` Epic 9 (Phase-1 closeout) — final consolidation point.
