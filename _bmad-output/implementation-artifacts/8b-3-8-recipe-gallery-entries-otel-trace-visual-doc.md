# Story 8b.3: 8 Recipe Gallery Entries + OTel Trace Visual Doc

Status: done

## Story

As **any persona** (Priya, Devon, Mei, Raj),
I want 8 recipe gallery entries documenting the headline user journeys + the OTel trace visualization document per FR58,
so that I have copy-pasteable patterns for the most common workflows and can visualize trace data in a familiar viewer.

## Pre-create-story drift check (39th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-25)

100% catch rate intact. 3 drifts caught:

- **D-1 (LOW):** Recipe #1 already shipped by Story 8b.1 + Recipe #4 stub by Story 7.3. Story 8b.3 authors the remaining 6 (#2, #3, #5, #6, #7, #8) + polishes #4.
- **D-2 (MED):** All recipe code blocks MUST use the explicit class-path listener invocation per Story 8a.2 D-6 (`AgentEval.telemetry.listener.Listener`). Story 7.3 recipe #4 stub was authored BEFORE this drift was caught — needs an amendment pass.
- **D-3 (LOW):** AC L1931 says "all 8 recipes pass as executable examples (each recipe's code block is extracted by CI + run as a smoke test)". This is ambitious. **Decision (path-of-least-amendment):** Phase-1 ships recipes as documentation only; the "executable extraction" CI step is deferred to Phase-1.5 (DF-8b.3-S1 / C64). Each recipe is hand-verified by the author for syntactic correctness; the integration test gates a 1-recipe smoke per `feedback_executable_doc_precheck` norm.

## Acceptance Criteria

### AC-8b.3.1 — Recipe #2: Pass@k over polling (Priya)

`docs/recipes/02-pass-at-k-over-polling.md` documents:
- Story 6.3 `Stat.Run N Times` + `Stat.Get Pass At K` pattern.
- Why polling is banned (FR28 / ADR-019).
- A working RF code block.

### AC-8b.3.2 — Recipe #3: Tool Discoverability cohort (Mei)

`docs/recipes/03-tool-discoverability-cohort.md` documents Story 4.4's `MCP.Get Tool Discoverability` + Story 8b.2's `Get Cohort Heatmap` + `.as_ascii()` rendering.

### AC-8b.3.3 — Recipe #4 polish (Devon)

`docs/recipes/04-skill-author-stacked-validation.md` (existing stub from Story 7.3) is amended:
- Listener invocation uses explicit class path per D-2.
- Cross-references Recipe #2 (Pass@k) for the stat layer.
- Documents the Phase-2 Judge layer placeholder.

### AC-8b.3.4 — Recipe #5: Dogfood replacing custom tests (Raj)

`docs/recipes/05-dogfood-replacing-custom-tests.md` documents the parallel-derivation pattern from Stories 3.3 (rf-mcp) + 5.5 (trace observability) + 6.4 (metrics) + 7.4 (skill discoverability) dogfood ports.

### AC-8b.3.5 — Recipe #6: Custom Protocol adapter

`docs/recipes/06-custom-protocol-adapter.md` documents the `agenteval new-adapter` flow from Story 8b.2 + how to register an adapter via the `agenteval.coding_agents` entry-points group.

### AC-8b.3.6 — Recipe #7: First MCP server test Tier-1

`docs/recipes/07-first-mcp-server-test-tier-1.md` documents Story 2.3 MCP static-inspection keywords (`MCP.Get Server Config`, `MCP.Get Tool Schema`).

### AC-8b.3.7 — Recipe #8: CI integration with enriched xunit + JUnit XML + exit codes

`docs/recipes/08-ci-integration.md` documents:
- Stories 8a.1 + 8a.2 enriched xunit properties.
- The `agenteval.*` namespace example.
- GitHub Actions workflow snippet showing how to consume the enriched xunit.

### AC-8b.3.8 — OTel trace visual doc at `docs/contracts/otel-trace-visual.md`

Per FR58, the doc describes how to load JSONL trace files into Jaeger / Honeycomb / Tempo:
- ASCII span-hierarchy diagram (`invoke_agent → chat → execute_tool`).
- `gen_ai.*` + `agenteval.*` attribute display table.
- Step-by-step instructions for loading a JSONL trace into Jaeger (the canonical Phase-1 viewer).

### AC-8b.3.9 — 1 integration smoke test for Recipe #2 (representative)

`tests/integration/recipes/test_pass_at_k_recipe.py` extracts the RF code block from Recipe #2 + runs it via `robot --dryrun` to verify keyword resolution. This is the path-of-least-amendment for D-3 (CI extraction of ALL 8 recipes deferred to Phase-1.5).

### AC-8b.3.10 — DF-8b.3-S1 / C64 catalogued

Phase-1.5 work: extend CI to extract + smoke-execute ALL 8 recipes (currently only #1 is end-to-end-tested via Story 8b.1's `test_init_5min_path.py`; this story adds #2; recipes #3-#8 are hand-verified only).

### AC-8b.3.11 — All-gates pass

- `uv run pytest tests/ -q` all green; +1 net new test.
- ruff/format clean.

## Tasks / Subtasks

- [x] **Task 1**: author `docs/recipes/02-pass-at-k-over-polling.md`.
- [x] **Task 2**: author `docs/recipes/03-tool-discoverability-cohort.md`.
- [x] **Task 3**: amend `docs/recipes/04-skill-author-stacked-validation.md` (listener class path).
- [x] **Task 4**: author `docs/recipes/05-dogfood-replacing-custom-tests.md`.
- [x] **Task 5**: author `docs/recipes/06-custom-protocol-adapter.md`.
- [x] **Task 6**: author `docs/recipes/07-first-mcp-server-test-tier-1.md`.
- [x] **Task 7**: author `docs/recipes/08-ci-integration.md`.
- [x] **Task 8**: author `docs/contracts/otel-trace-visual.md` (FR58).
- [x] **Task 9**: create `tests/integration/recipes/__init__.py` + `tests/integration/recipes/test_pass_at_k_recipe.py`.
- [x] **Task 10**: catalog DF-8b.3-S1 / C64 (Phase-1.5 CI extraction for all 8 recipes).
- [x] **Task 11**: all-gates run.
- [x] **Task 12**: sprint-status story → done.

## Dev Notes

### Architecture compliance

- **PRD FR58** (OTel trace visualization doc): satisfied by `docs/contracts/otel-trace-visual.md`.
- **PRD NFR-UX-01** (recipe gallery): satisfied by 8 recipes (#1 from Story 8b.1; #2-#8 here; #4 polished from Story 7.3 stub).

### Recipe format conventions

- All recipes use the explicit `--listener AgentEval.telemetry.listener.Listener` invocation.
- All RF code blocks are syntactically correct (verified by hand + smoke-execute for #2 via the integration test).
- Each recipe carries a 1-line TL;DR + step-by-step + troubleshooting (where applicable).

### Files to create / modify

**CREATE:**
- `docs/recipes/02-pass-at-k-over-polling.md`
- `docs/recipes/03-tool-discoverability-cohort.md`
- `docs/recipes/05-dogfood-replacing-custom-tests.md`
- `docs/recipes/06-custom-protocol-adapter.md`
- `docs/recipes/07-first-mcp-server-test-tier-1.md`
- `docs/recipes/08-ci-integration.md`
- `docs/contracts/otel-trace-visual.md`
- `tests/integration/recipes/__init__.py`
- `tests/integration/recipes/test_pass_at_k_recipe.py`

**MODIFY:**
- `docs/recipes/04-skill-author-stacked-validation.md` — explicit class-path listener invocation.
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-8b.3-S1 entry.
- `docs/phase-1-5-carry-overs.md` — C64 row.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

### File List

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-25 | 0.1.0 | Initial story creation. 39th use of `feedback_spec_vs_ratified_doc_precheck` (100% catch rate intact). 3 drifts caught (D-1 ship-only recipes 2/3/5/6/7/8; D-2 listener class path everywhere; D-3 CI executable extraction deferred Phase-1.5 via DF-8b.3-S1/C64). 11 ACs. Closes FR58 + NFR-UX-01. | Bob |
