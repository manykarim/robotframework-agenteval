# Story 1b.5: Conformance Harness + Loader + Fixture Schema + 6 Reference Fixtures

Status: ready-for-dev

## Story

As a **conformance-suite-respecting epic author** (Epics 2-8b — every Tier-2/3 keyword needs a fixture per AC-CONFORMANCE-01) **and Tier-1 community adapter author** (Phase-1 contract publication per PRD L520-533),
I want **the conformance suite scaffolding at `tests/conformance/{harness.py, loader.py, types.py, fixture-schema.json}` complete + 6 reference fixtures shipped at `fixtures/<adapter>/<scenario>.json` per architecture L738-739 + 10 per-AC skeleton test files at `test_ac_*.py` per ADR-017 L21-33 + `conformance.yml` workflow upgraded from `--collect-only` placeholder to real `pytest tests/conformance -q`**,
So that **subsequent epics can drop in new fixture files + populate per-AC test bodies + the harness loads/runs them without modification; AC-CONFORMANCE-01 (fidelity oracles) is publishable from Phase 1 Week 2 onward as the runnable contract community Tier-1 adapter authors implement against (NOT enforced from Phase 1 since P1 has only 2 adapters yet to land in Epic 4); and Story 1b.4's signature-shape hand-off resolves to a concrete `assert_adapter_signature` helper exercised by `test_structural_shape.py`**.

## Acceptance Criteria

> **Pre-create-story drift check (9th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19):** Surfaced 20 drifts (12 HIGH + 6 MED + 2 LOW) in the pre-edit Story 1b.5 epics.md spec vs ratified sources — the spec had invented a parallel design across fixture organization, fixture schema, oracle taxonomy, error classes, type names, function signatures, SKIP semantics, and PR-trigger semantics. All 20 resolved via path-of-least-amendment by honoring ratified sources per Many's 2026-05-19 ratification + "fix-the-losing-source-NOW" pattern. Key resolutions:
>
> - **(D1 HIGH)** Per-adapter `fixtures/<adapter>/<scenario>.json` layout per architecture L738 + ADR-005 L18 + ADR-017 L38 + epics.md L272 Epic 1b summary (NOT per-keyword flat layout `fix-skill-frontmatter-valid.json` etc.).
> - **(D2 HIGH)** Decision-4 ratified schema field set `_schema_version` / `adapter_name` / `scenario_name` / `agent_run_result` / `expected_tool_calls` / `expected_errors` / `reproducibility_footer` (NOT invented `id`/`tier`/`keyword_under_test`/`inputs`/`expected_outputs`/`oracle_type`).
> - **(D3 HIGH)** 10 per-AC test files per ADR-017 L21-33 + 1 `test_structural_shape.py` (NOT per-keyword fixture-named test files).
> - **(D4 HIGH)** Drop invented `oracle_type` 4-state Literal enum (`exact_match`/`contains`/`trajectory_match`/`completeness_check`) → use ADR-005 L19-22 per-field allowable-variations contract (`latency_ms > 0`, ISO-8601 + monotonic timestamps, strict `source` match).
> - **(D5 MED)** Drop `trajectory_match` — explicitly Phase-2-deferred per architecture L239 ("Phase 1 agenteval doesn't ship multi-agent trajectory scoring") + L1809 + PRD L1310 ("BFCL trajectory match. All deferred to Phase 2/3").
> - **(D6 MED)** Drop `completeness_check` oracle — collapses ADR-006 truncation-injection mechanism + ADR-005 `metadata.completeness` exact-match contract into a single label, losing the `expected_errors` consumption contract.
> - **(D7 HIGH)** `InvalidConformanceFixtureError` NOT in ratified 11-leaf catalog (`docs/contracts/error-class-hierarchy.md` L50-54) → use stdlib `jsonschema.ValidationError` (conformance harness is test infra at `tests/conformance/`, NOT library-public surface at `src/AgentEval/`); no `errors.py` extension needed.
> - **(D8 HIGH)** Drop fixture (b) `InvalidSkillFrontmatterError` — Epic 2's error class to introduce (`epics.md` L438 explicit), not Story 1b.5's.
> - **(D9 HIGH)** `load_fixture(path: Path) -> ConformanceFixture` (singular per architecture L737), NOT `load_fixtures -> list[Fixture]`. Plural enumeration is the per-AC test file's responsibility via parametrize.
> - **(D10 HIGH)** Introduce `tests/conformance/types.py` with stdlib `@dataclass(frozen=True) ConformanceFixture` + `ConformanceResult` per Story 1b.2 types.py L46-56 Pydantic-substitution precedent (`Fixture` + `ConformanceResult` are NEW types Story 1b.5 introduces; not in any ratified surface).
> - **(D11 HIGH)** Drop SKIP-with-reason "fixture gated on keyword existing" invention — use `pytest.skip("Owning epic N not yet shipped")` markers at per-AC test file level per ADR-017 pattern. The `skip` semantics ship via pytest's stdlib mechanism, NOT a custom harness-level gate.
> - **(D12 HIGH)** `conformance.yml` stays per-release per ADR-005 L31 ("Conformance suite tests are slow-by-design. They run in CI on `conformance.yml` (per-release), NOT on `ci.yml` (per-PR)") + ADR-017 L57 ("conformance workflow runs this suite on a per-release schedule, NOT per-PR"). The "trivial PR check from Story 1a.2 now exercises these 6 fixtures" framing was factually wrong — Story 1a.2's conformance.yml triggers `workflow_dispatch + release: published` only; the all-7-workflows-green-on-trivial-PR property holds via `workflow_dispatch` reachability + skeleton SKIPs.
> - **(D13 LOW confirmed)** Story 1b.4-to-1b.5 hand-off: signature-shape verification is Story 1b.5's `test_structural_shape.py` + `assert_adapter_signature` helper per `types.py` L346-356 + ADR-017 L36.
> - **(D14 HIGH)** Drop fixture (c) `InvalidMCPToolSchemaError` impl — Epic 3 Story 3.x owns the error class (alongside `UnsupportedMCPVersionError`), not Story 1b.5.
> - **(D15 MED)** Reframe AC-CONFORMANCE-01 as "contract publication from Phase 1 Week 2 onward" not "enforceable", per PRD L520-533 verbatim: "Conformance suite ships in Phase 1 as **CONTRACT PUBLICATION** (so community adapter authors have a runnable target Day 1), NOT for consistency enforcement (P1 has only 2 adapters)."
> - **(D16 LOW)** Drop Tier-3 tag from completeness fixture — tier is a keyword property (per Story 1b.1 `@tier` + architecture L620), NOT an adapter/fixture property.
> - **(D17 LOW)** Cite post-renumbering ADRs: `ADR-005-conformance-suite-fidelity-oracles.md` + `ADR-006-agent-run-result-completeness-field.md` + `ADR-017-conformance-suite-organization-per-ac-test-files.md` (NOT stale PRD ADR-008/ADR-009 references — those numbers now belong to MCP-spec-version-validation + per-test-MCP-server-scope per architecture L1418).
> - **(D18 MED)** Add `adapter_registry` fixture + truncation-injection mock-agent harness + mock provider per ADR-017 L40-43.
> - **(D19 MED)** Ratify stdlib `@dataclass(frozen=True) ConformanceFixture` Phase-1 deviation from architecture Decision-4's "Pydantic" wording — same Phase-1.5 carry-over as Story 1b.2's `ToolCallTrace`/`Usage`/`RunManifest` (`deferred-work.md`).
> - **(D20 MED)** Adopt ratified 6-fixture set per architecture L739: `generic/echo_simple.json`, `generic/echo_truncated.json`, `generic/echo_external_mcp.json` + same 3 under `claude_code_cli/`. Both adapters are forward-refs at end-of-Story-1b.4 (Generic LiteLLM lands Story 4.1; Claude Code CLI lands Story 4.2) — fixtures publish the contract.
>
> Pre-authoring fix: `_bmad-output/planning-artifacts/epics.md` L1039-1057 (Story 1b.5 spec) re-authored 2026-05-19. No ADR or contract amendments needed — the ratified sources were already correct; the Story 1b.5 spec block was the divergent surface.

### AC-1b.5.1 — Fixture JSON schema per architecture Decision-4 + ADR-005

**Given** the JSON+jsonschema format choice from architecture Step-4 Decision-4 + ADR-005 L17-22 fidelity-oracle contract,
**When** Story 1b.5 authors `tests/conformance/fixture-schema.json`,
**Then** the schema validates the Decision-4 ratified field set:

- `_schema_version: str` (semver, e.g., `"1.0.0"`; required so Phase-2 fixture-format migrations can detect old fixtures).
- `adapter_name: str` (required; the adapter identifier this fixture targets, e.g., `"generic"`, `"claude_code_cli"`).
- `scenario_name: str` (required; the scenario identifier within the adapter's fixture directory, e.g., `"echo_simple"`).
- `agent_run_result: object` (schema-validated structural shape of `AgentRunResult` with required `metadata.completeness` + `metadata.mcp_coverage` per FR36a/b + 3-state Literal value spaces per ADR-006 + ADR-016).
- `expected_tool_calls: array` (per ADR-005 L19-22 + AC-CONFORMANCE-01 — sequence of expected `ToolCallTrace` records with **allowable-variation annotations**: `latency_ms` per-record `> 0` constraint not exact match, ISO-8601 `timestamp` + monotonic-non-decreasing ordering, `source` strict match per fixture).
- `expected_errors: array` (per ADR-006 + AC-CONFORMANCE-02 — list of error-class names expected from truncation-injection scenarios; empty array for non-truncation scenarios).
- `reproducibility_footer: object` (per FR39 — captures `library_version` + `redaction_policy_hash` + `started_at` + `ended_at` for reproducibility audit).

The schema lives at `tests/conformance/fixture-schema.json`. Validation via stdlib `jsonschema` library (already a direct dep per `pyproject.toml`).

### AC-1b.5.2 — `tests/conformance/types.py` Phase-1 stdlib dataclasses

**And** `tests/conformance/types.py` (new file) exposes `ConformanceFixture` + `ConformanceResult` as stdlib `@dataclass(frozen=True)` per Story 1b.2 `src/AgentEval/types.py` L46-56 Pydantic-substitution precedent (architecture Decision-4's "Pydantic dataclasses" wording is a Phase-1.5 carry-over per `deferred-work.md`; stdlib dataclasses ship Phase-1).

`ConformanceFixture` fields mirror the AC-1b.5.1 schema:
- `schema_version: str`
- `adapter_name: str`
- `scenario_name: str`
- `agent_run_result: dict[str, Any]` (raw dict — concrete adapter-side projection deferred to per-test parsing since `AgentRunResult` validation lives in `src/AgentEval/types.py`)
- `expected_tool_calls: list[dict[str, Any]]`
- `expected_errors: list[str]`
- `reproducibility_footer: dict[str, Any]`

`ConformanceResult` fields:
- `passed: bool`
- `fixture: ConformanceFixture`
- `evidence: dict[str, Any]` (per-allowable-variation witness, diff record, expected-errors-match record, or truncation-injection-success record — schema not pinned in Story 1b.5; concrete shape evolves with the per-AC test files)
- `skip_reason: str | None` (set when `run_fixture` short-circuits without exercising the adapter, e.g., when target keyword's owning epic hasn't shipped)

### AC-1b.5.3 — `tests/conformance/loader.py` singular signature

**And** `tests/conformance/loader.py` exposes `load_fixture(path: Path) -> ConformanceFixture` (singular per architecture L737) — reads the JSON file, validates against `fixture-schema.json` via stdlib `jsonschema`, returns a populated `ConformanceFixture` instance. On schema violation raises `jsonschema.ValidationError` directly (NO new error class added to `src/AgentEval/errors.py` — conformance harness is test infra not library-public surface per D7 ratification).

### AC-1b.5.4 — `tests/conformance/harness.py` fixtures + run_fixture + assert_adapter_signature

**And** `tests/conformance/harness.py` exposes:

- `adapter_registry` pytest fixture (per ADR-017 L40-43) — yields all adapters discovered via Story 1b.3's `_kernel.discovery.discover_adapters()` + entry-points lookup. Returns an empty list at end-of-Story-1b.5 (no concrete adapter registered yet; Story 4.1 + Story 4.2 land them in Epic 4).
- `truncation_injection_harness` fixture — exposes a mock-agent subprocess controller with `kill_at` parameter (`"mid_stream"` / `"early_eof"` / `"after_first_event"`) per ADR-006 + AC-CONFORMANCE-02. Used by `test_ac_conformance_02_completeness.py` when Epic 6 lands the Tier-3 keyword infrastructure.
- `mock_provider` fixture — known cost/runtime characteristics per ADR-015 (for Tier-3 cost-guardrail conformance tests when Epic 6 Story 6.x lands).
- `run_fixture(fixture: ConformanceFixture, adapter: CodingAgentAdapter) -> ConformanceResult` — orchestrates `adapter.run(prompt, ...)` against the fixture's `scenario_name` + asserts the ADR-005 L19-22 allowable-variation contract per `expected_tool_calls` + `expected_errors`; returns structured pass/fail with evidence. **Phase-1 stub**: returns `ConformanceResult(passed=False, ..., skip_reason="No concrete adapter implementation yet")` when called against an adapter that doesn't implement the fixture's scenario (Story 4.1 + 4.2 + Epic 6 wire the real assertion logic when concrete adapters + Tier-3 keyword infrastructure land).
- `assert_adapter_signature(adapter_cls: type[CodingAgentAdapter]) -> None` — signature-shape verifier per Story 1b.4 hand-off (`src/AgentEval/types.py` L346-356) + ADR-017 L36; inspects `adapter_cls.run`'s signature via `inspect.signature` against PRD FR12's `(self, prompt: str, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` contract; raises `AssertionError` with structured diff on mismatch (parameter-name drift, missing default, missing `**kwargs`, wrong return annotation).

### AC-1b.5.5 — 10 per-AC skeleton test files + structural shape test per ADR-017

**And** 10 per-AC test files land at `tests/conformance/test_ac_*.py` per ADR-017 L21-33:
- `test_ac_simplicity_01_evidence_block.py` — owning epic: Epic 5 Story 5.x
- `test_ac_simplicity_02_keyword_idiom.py` — owning epic: Epic 1b Story 1b.6 (conventions) / Epic 2
- `test_ac_discover_01_cohort.py` — owning epic: Epic 2 Story 2.3 / Epic 3 Story 3.2
- `test_ac_discover_02_cost_guardrail.py` — owning epic: Epic 6 Story 6.x (Tier-3 fan-out keywords)
- `test_ac_dogfood_01_replacement.py` — owning epic: Epic 8b dogfood port
- `test_ac_conformance_01_fidelity_oracles.py` — owning epic: Epic 4 Story 4.1 + 4.2 (concrete adapters)
- `test_ac_conformance_02_completeness.py` — owning epic: Epic 4 Story 4.2 + Epic 6
- `test_ac_mcp_observe_01_coverage.py` — owning epic: Epic 3 Story 3.1 / Epic 5
- `test_ac_mcp_observe_02_version_gate.py` — owning epic: Epic 3 Story 3.1
- `test_ac_mcp_observe_03_per_test_scope.py` — owning epic: Story 0.2 ratified + Epic 3 / Epic 5

Each scaffolded as a skeleton parametrized over `adapter_registry` with a single test function calling `pytest.skip(f"Owning epic N Story X.Y not yet shipped — see ADR-017 + epics.md")` so `pytest tests/conformance -q` returns 0 with all-skipped at end-of-Story-1b.5. Test bodies populate as owning epics land.

**And** `tests/conformance/test_structural_shape.py` lands per ADR-017 L36 — parametrized over `adapter_registry` calling `assert_adapter_signature` against every registered adapter. SKIPs when `adapter_registry` is empty (end-of-Story-1b.5 state).

### AC-1b.5.6 — 6 reference fixtures at `fixtures/<adapter>/<scenario>.json`

**And** 6 reference fixtures land at `tests/conformance/fixtures/<adapter>/<scenario>.json` per architecture L738-739:
- `tests/conformance/fixtures/generic/echo_simple.json`
- `tests/conformance/fixtures/generic/echo_truncated.json`
- `tests/conformance/fixtures/generic/echo_external_mcp.json`
- `tests/conformance/fixtures/claude_code_cli/echo_simple.json`
- `tests/conformance/fixtures/claude_code_cli/echo_truncated.json`
- `tests/conformance/fixtures/claude_code_cli/echo_external_mcp.json`

The 3 scenarios map to ratified AC coverage:
- **`echo_simple`** — agent prompts a simple echo `"Hello, world!"` → response_text echoes the input; one `expected_tool_calls` entry (an `echo` tool invocation); `metadata.completeness = "complete"`; `metadata.mcp_coverage = "hosted_in_process"`. Covers **AC-CONFORMANCE-01** (fidelity oracles) + **AC-MCP-OBSERVE-01** (hosted_in_process coverage) + **AC-MCP-OBSERVE-02** (spec-version gate, asserted via the version field in `agent_run_result`).
- **`echo_truncated`** — same simple echo but truncation-injected mid-stream (the mock-agent harness kills the subprocess at the first tool-call boundary); `metadata.completeness = "truncated"` REQUIRED per FR36a; `expected_errors` empty (truncation alone doesn't raise — FR37's `IncompleteTraceError` is gated on `external_mixed`, NOT truncation). Covers **AC-CONFORMANCE-02** (completeness) + **FR36a**.
- **`echo_external_mcp`** — agent connects to an external (non-instrumented) MCP server; `metadata.mcp_coverage = "external_mixed"` REQUIRED; metric-keyword invocation on this fixture is expected to raise `IncompleteTraceError` unless `allow_external_mcp_blind=True`. `expected_errors` populated with `["IncompleteTraceError"]` for the gated path. Covers **AC-MCP-OBSERVE-01** (`external_mixed` coverage) + **FR37** (`IncompleteTraceError`).

All 6 fixtures publish the contract; no concrete adapter exists at end-of-Story-1b.5 to actually exercise them. Story 4.1 (Generic LiteLLM) + Story 4.2 (Claude Code CLI) populate the actual adapter implementations; the existing per-AC test files start asserting against them at that time.

### AC-1b.5.7 — `conformance.yml` workflow real invocation

**And** `.github/workflows/conformance.yml` is upgraded from the pre-Story-1b.5 `--collect-only` placeholder (Story 1a.2 baseline) to a real `pytest tests/conformance -q` invocation. Triggers unchanged per ADR-005 L31 + ADR-017 L57: `on: workflow_dispatch: {}` + `release: types: [published]` — NO `pull_request` trigger added. The all-7-workflows-green-on-trivial-PR property from Story 1a.2 holds via `workflow_dispatch` reachability + skeleton test files SKIPping until owning epics ship.

### AC-1b.5.8 — AC-CONFORMANCE-01 framing as "contract publication"

**And** the AC-CONFORMANCE-01 user-story framing is reframed from "enforceable from Phase 1 Week 2 onward" (pre-edit) to "publishable from Phase 1 Week 2 onward as the contract Tier-1 community adapter authors implement against" — verbatim per PRD L520-533: "Conformance suite ships in Phase 1 as **CONTRACT PUBLICATION** (so community adapter authors have a runnable target Day 1), NOT for consistency enforcement (P1 has only 2 adapters)." Full multi-adapter enforcement compounds in Phase 2 when the Tier-1 adapter set grows.

### AC-1b.5.9 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (still 31 source files — no new `src/` files; conformance harness lives at `tests/conformance/`).
- `uv run python scripts/check-license-headers.py` PASS (still 31/31 — tests exempt per project convention per scripts/check-license-headers.py docstring).
- `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — 263 prior tests still pass (regression).
- `uv run pytest tests/conformance -q` — harness collects + loads all 6 fixtures via `load_fixture` + 10 per-AC test files + `test_structural_shape.py` SKIP gracefully (NOT fail). `pytest` returncode 0 (skips are OK).
- `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6 FR42 regression unchanged (6 passed).
- `uv run robot tests/acceptance/smoke` — RF smoke regression unchanged.

### AC-1b.5.10 — Project norms applied

**And**:
- Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (9th consecutive use).
- Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (10 consecutive STAR-catch streak — pattern is load-bearing).
- Honest framing: Phase-1 limitations explicitly documented — (1) no concrete adapter exists at end-of-Story-1b.5 (Story 4.1 + 4.2 land them); (2) `run_fixture` returns SKIP for all calls until concrete adapters ship; (3) all 10 per-AC test files SKIP at end-of-Story-1b.5 with explicit owning-epic markers; (4) stdlib `@dataclass(frozen=True)` substituted for architecture Decision-4's "Pydantic" per Story 1b.2 precedent.

## Tasks / Subtasks

- [ ] **Task 1: Author `tests/conformance/fixture-schema.json` (AC: 1b.5.1)**
  - [ ] JSON Schema draft-07 (matches stdlib `jsonschema` default).
  - [ ] Required top-level: `_schema_version`, `adapter_name`, `scenario_name`, `agent_run_result`, `expected_tool_calls`, `expected_errors`, `reproducibility_footer`.
  - [ ] `_schema_version` semver pattern.
  - [ ] `agent_run_result` nested schema with `response_text`, `tool_calls`, `usage`, `metadata.completeness` Literal enum + `metadata.mcp_coverage` Literal enum, `cost_usd`, `latency_seconds`, `trace_id`.
  - [ ] `expected_tool_calls` array of objects with `name`, `args`, `result` / `error`, `latency_ms` (≥ 0 not exact match per ADR-005 L19-22), `source` Literal, `gen_ai_tool_call_id`, `sequence_index`.
  - [ ] `expected_errors` array of strings (error-class names).
  - [ ] `reproducibility_footer` with `library_version`, `redaction_policy_hash`, `started_at` / `ended_at` (ISO-8601).

- [ ] **Task 2: Author `tests/conformance/types.py` (AC: 1b.5.2)**
  - [ ] `ConformanceFixture` `@dataclass(frozen=True)` per AC-1b.5.2.
  - [ ] `ConformanceResult` `@dataclass(frozen=True)` per AC-1b.5.2.
  - [ ] Module docstring cites architecture Decision-4 + Story 1b.2 Pydantic-substitution precedent.

- [ ] **Task 3: Author `tests/conformance/loader.py` (AC: 1b.5.3)**
  - [ ] `load_fixture(path: Path) -> ConformanceFixture` reads JSON + validates against `fixture-schema.json` via stdlib `jsonschema.validate` + populates `ConformanceFixture`.
  - [ ] Schema validation failure raises `jsonschema.ValidationError` (NOT a new agenteval error class).
  - [ ] Module docstring cites architecture L737.

- [ ] **Task 4: Author `tests/conformance/harness.py` (AC: 1b.5.4)**
  - [ ] `adapter_registry` pytest fixture iterating `_kernel.discovery.discover_adapters()` + entry-points; empty list at end-of-Story-1b.5.
  - [ ] `truncation_injection_harness` fixture exposing mock-agent subprocess controller per ADR-006.
  - [ ] `mock_provider` fixture exposing known-cost/runtime mock per ADR-015.
  - [ ] `run_fixture(fixture, adapter) -> ConformanceResult` orchestrator (Phase-1 SKIP-on-no-adapter stub).
  - [ ] `assert_adapter_signature(adapter_cls) -> None` signature-shape verifier via `inspect.signature`.

- [ ] **Task 5: Author 10 per-AC skeleton test files + test_structural_shape.py (AC: 1b.5.5)**
  - [ ] `test_ac_simplicity_01_evidence_block.py` SKIP marker "Owning epic Epic 5 Story 5.x".
  - [ ] `test_ac_simplicity_02_keyword_idiom.py` SKIP marker "Owning epic Epic 1b Story 1b.6 / Epic 2".
  - [ ] `test_ac_discover_01_cohort.py` SKIP marker "Owning epic Epic 2 Story 2.3 / Epic 3 Story 3.2".
  - [ ] `test_ac_discover_02_cost_guardrail.py` SKIP marker "Owning epic Epic 6 Story 6.x".
  - [ ] `test_ac_dogfood_01_replacement.py` SKIP marker "Owning epic Epic 8b dogfood port".
  - [ ] `test_ac_conformance_01_fidelity_oracles.py` SKIP marker "Owning epic Epic 4 Story 4.1 + 4.2".
  - [ ] `test_ac_conformance_02_completeness.py` SKIP marker "Owning epic Epic 4 Story 4.2 + Epic 6".
  - [ ] `test_ac_mcp_observe_01_coverage.py` SKIP marker "Owning epic Epic 3 Story 3.1 / Epic 5".
  - [ ] `test_ac_mcp_observe_02_version_gate.py` SKIP marker "Owning epic Epic 3 Story 3.1".
  - [ ] `test_ac_mcp_observe_03_per_test_scope.py` SKIP marker "Owning epic Story 0.2 ratified + Epic 3 / Epic 5".
  - [ ] `test_structural_shape.py` SKIPs when `adapter_registry` empty.

- [ ] **Task 6: Author 6 reference fixtures at `fixtures/<adapter>/<scenario>.json` (AC: 1b.5.6)**
  - [ ] `fixtures/generic/echo_simple.json` — `metadata.completeness="complete"`, `metadata.mcp_coverage="hosted_in_process"`, 1 expected tool call.
  - [ ] `fixtures/generic/echo_truncated.json` — `metadata.completeness="truncated"`, `metadata.mcp_coverage="hosted_in_process"`, empty `expected_tool_calls`, empty `expected_errors`.
  - [ ] `fixtures/generic/echo_external_mcp.json` — `metadata.mcp_coverage="external_mixed"`, `expected_errors=["IncompleteTraceError"]`.
  - [ ] `fixtures/claude_code_cli/echo_simple.json` — mirrors generic but with `adapter_name="claude_code_cli"`.
  - [ ] `fixtures/claude_code_cli/echo_truncated.json` — same.
  - [ ] `fixtures/claude_code_cli/echo_external_mcp.json` — same.

- [ ] **Task 7: Upgrade `.github/workflows/conformance.yml` (AC: 1b.5.7)**
  - [ ] Replace `--collect-only` placeholder with real `uv run pytest tests/conformance -q`.
  - [ ] Triggers unchanged: `workflow_dispatch + release: published`.
  - [ ] Output assertion: all tests skip; returncode 0.

- [ ] **Task 8: All-gates pass (AC: 1b.5.9)**

- [ ] **Task 9: Apply project norms (AC: 1b.5.10)**

## Dev Notes

### Phase-1 limitations explicitly documented

- **No concrete adapter exists at end-of-Story-1b.5.** Generic LiteLLM lands Story 4.1; Claude Code CLI lands Story 4.2. The 6 fixtures publish the contract; nothing actually exercises them yet.
- **All 10 per-AC test files SKIP at end-of-Story-1b.5.** Each carries an owning-epic-and-story marker. As owning epics ship, the SKIP markers are removed + real test bodies populate.
- **`run_fixture` returns `ConformanceResult(passed=False, skip_reason="No concrete adapter implementation yet")`** for all calls until Story 4.1 + 4.2 land concrete adapters.
- **Conformance workflow is per-release, NOT per-PR** per ADR-005 L31 + ADR-017 L57. The all-7-workflows-green-on-trivial-PR property from Story 1a.2 holds via `workflow_dispatch` reachability.
- **stdlib `@dataclass(frozen=True)` substituted for architecture Decision-4's "Pydantic"** per Story 1b.2 types.py L46-56 precedent. Phase-1.5 Pydantic-migration carry-over recorded in `deferred-work.md`.

### Architecture compliance

| Architecture reference | Story 1b.5 implementation |
|---|---|
| L392 conformance organization | Per-AC test files + per-adapter fixtures |
| L724-751 Decision-4 schema | Honored: `_schema_version` + `adapter_name` + `scenario_name` + `agent_run_result` + `expected_tool_calls` + `expected_errors` + `reproducibility_footer` |
| L737 `load_fixture` signature | Honored: singular signature returning `ConformanceFixture` |
| L738-739 fixture layout + 6 initial fixtures | Honored verbatim |
| L853 cross-sub-library import | `tests/conformance/types.py` is test infra (NOT a sub-library); types live there, not in `src/AgentEval/types.py` |
| L1367-1391 conformance project tree | Honored |
| ADR-005 L17-22 fidelity oracle | Per-field allowable-variations (`latency_ms > 0`, ISO-8601 monotonic, strict `source`) |
| ADR-005 L31 per-release schedule | `conformance.yml` triggers unchanged: `workflow_dispatch + release: published` |
| ADR-006 truncation injection | `truncation_injection_harness` fixture per ADR-017 L42 |
| ADR-017 L21-33 per-AC test files | 10 files + `test_structural_shape.py` shipped per spec |
| ADR-017 L36 structural-shape test | Honored: `test_structural_shape.py` + `assert_adapter_signature` helper |
| ADR-017 L40-43 harness fixtures | `adapter_registry` + `truncation_injection_harness` + `mock_provider` shipped |
| Story 1b.4 hand-off | Signature-shape validation in `assert_adapter_signature` |

### Files List

**New files (~20):**
- `tests/conformance/fixture-schema.json` (~120L)
- `tests/conformance/types.py` (~80L)
- `tests/conformance/loader.py` (~50L)
- `tests/conformance/harness.py` (~180L)
- `tests/conformance/__init__.py` (empty)
- `tests/conformance/test_ac_simplicity_01_evidence_block.py` (~30L skeleton)
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` (~30L)
- `tests/conformance/test_ac_discover_01_cohort.py` (~30L)
- `tests/conformance/test_ac_discover_02_cost_guardrail.py` (~30L)
- `tests/conformance/test_ac_dogfood_01_replacement.py` (~30L)
- `tests/conformance/test_ac_conformance_01_fidelity_oracles.py` (~30L)
- `tests/conformance/test_ac_conformance_02_completeness.py` (~30L)
- `tests/conformance/test_ac_mcp_observe_01_coverage.py` (~30L)
- `tests/conformance/test_ac_mcp_observe_02_version_gate.py` (~30L)
- `tests/conformance/test_ac_mcp_observe_03_per_test_scope.py` (~30L)
- `tests/conformance/test_structural_shape.py` (~50L)
- `tests/conformance/fixtures/generic/echo_simple.json`
- `tests/conformance/fixtures/generic/echo_truncated.json`
- `tests/conformance/fixtures/generic/echo_external_mcp.json`
- `tests/conformance/fixtures/claude_code_cli/echo_simple.json`
- `tests/conformance/fixtures/claude_code_cli/echo_truncated.json`
- `tests/conformance/fixtures/claude_code_cli/echo_external_mcp.json`

**Modified files (1):**
- `.github/workflows/conformance.yml` — replace `--collect-only` placeholder with `pytest tests/conformance -q`.

### References

- PRD §FR12 / §FR36a / §FR36b / §FR37 / §FR39 / §FR47 / §FR51
- PRD AC-CONFORMANCE-01 (L520-533) / AC-CONFORMANCE-02 (L539-544) / AC-MCP-OBSERVE-01/02/03
- ADR-005 `docs/adr/ADR-005-conformance-suite-fidelity-oracles.md` (oracle contract + per-release schedule)
- ADR-006 `docs/adr/ADR-006-agent-run-result-completeness-field.md` (truncation injection)
- ADR-017 `docs/adr/ADR-017-conformance-suite-organization-per-ac-test-files.md` (per-AC files + harness fixtures)
- Architecture L392 + L724-751 (Decision-4) + L738-739 (6-fixture set) + L1367-1391 (project tree)
- Story 1b.2 `src/AgentEval/types.py` L46-56 (Pydantic-substitution precedent)
- Story 1b.3 `_kernel/discovery.py` (consumed by `adapter_registry` fixture)
- Story 1b.4 `src/AgentEval/types.py` L346-356 (signature-shape hand-off)
- `feedback_spec_vs_ratified_doc_precheck` (memory) — 9th consecutive use; 20 drifts resolved
- `feedback_citation_drift_first_class` (memory) — code-review prompt directive

## Dev Agent Record

### Context Reference

<!-- To be filled by dev-story workflow -->

### Agent Model Used

<!-- To be filled by dev-story workflow -->

### Debug Log References

<!-- To be filled by dev-story workflow -->

### Completion Notes List

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (9th consecutive use) caught 20 drifts (12 HIGH + 6 MED + 2 LOW) in pre-edit Story 1b.5 spec — wholesale divergence from architecture Decision-4 + ADR-005 + ADR-017 + Epic 1b L272 summary. All 20 resolved via path-of-least-amendment by honoring ratified sources per Many's 2026-05-19 ratification: per-adapter `<adapter>/<scenario>.json` layout (D1); Decision-4 schema field set (D2); per-AC test files (D3); drop invented `oracle_type` enum + `trajectory_match` (D4/D5/D6); stdlib `jsonschema.ValidationError` not new agenteval leaf (D7); drop Epic-2/Epic-3-owned error fixtures (D8/D14); singular `load_fixture -> ConformanceFixture` (D9); stdlib `@dataclass(frozen=True)` per Story 1b.2 precedent (D10/D19); `pytest.skip` markers in per-AC test files (D11); per-release CI not per-PR (D12); signature-shape verifier hand-off (D13); contract-publication framing (D15); drop Tier tag from fixture (D16); post-renumbering ADR refs (D17); `adapter_registry` + truncation-injection + mock-provider per ADR-017 L40-43 (D18); ratified 6-fixture set (D20). Pre-authoring fix: epics.md L1039-1057 re-authored 2026-05-19. NO new source files (`src/AgentEval/` unchanged); NO ADR or contract amendments needed — ratified sources were already correct; the spec was the divergent surface. | Bob |
