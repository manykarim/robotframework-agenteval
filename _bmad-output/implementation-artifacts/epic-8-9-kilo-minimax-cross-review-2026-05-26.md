# Epic 8 + 9 retro-cross-LLM review via kilocode CLI (minimax-M2.7)

**Date:** 2026-05-26
**Reviewer:** `~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7`
**Driver:** user `/goal` directive — third-LLM cross-review for Epic 8 + 9 stories shipped without substantive cross-LLM review.

## Why this happened

Per Epic 8 retro + Epic 9 retro: 7 stories across Epic 8 (8a.2, 8b.1, 8b.2, 8b.3) + Epic 9 (9.1, 9.2, 9.3) shipped under degraded cross-LLM conditions — Claude CLI returned 0-byte output on long prompts; Codex CLI rate-limited from Story 8a.1 onward. Per `feedback_integration_test_forcing_function` (Epic 8 retro NEW norm) the integration-test suite substituted as forcing function, but the 30+ STAR catch streak from Epics 2-7 was broken.

Story 10.2 demonstrated kilocode CLI (`kilo/minimax-m2.7`) as a viable third-LLM-family fallback per Epic 8 retro Action #1 step (iii). This retro-batch applies the same fallback to the 7 historically-degraded stories.

## Findings summary

| Story | Verdict | HIGH count | Real | False+ | MED+LOW | Patches applied |
| --- | --- | --- | --- | --- | --- | --- |
| 8a.2 | ratify-with-patches | 2 | 2 | 0 | 6 | HIGH-1 + HIGH-2 |
| 8b.1 | ratify-with-patches | 1 | 1 | 0 | 8 (most rescinded by kilo) | HIGH-1 |
| 8b.2 | ratify-with-patches | 2 | 2 | 0 | 5 | HIGH-1 + HIGH-2 |
| 8b.3 | ratify-with-patches | 1 | 1 | 0 | 6 | HIGH-1 |
| 9.1 | ratify-with-patches | 2 | 2 | 0 | 5 | HIGH-2 (HIGH-1 doc-quality deferred) |
| 9.2 | ratify-with-patches | 2 | 0 (citation drift; doc quality) | 0 | 5 | HIGH-2 propagated (workflow trigger) |
| 9.3 | ratify-with-patches | 0 (3 MED) | n/a | n/a | 6 | none (doc-quality deferred) |
| **Total** | — | **10 HIGH** | **8 real** | **0** | **41 MED/LOW** | **8 HIGH patches** |

## HIGH patches applied (verbatim summary)

### Story 8a.2

- **HIGH-1**: `tests/conformance/fixtures/fix-polling-ban-error-format.json` claimed to be a `ConformanceFixture` (declared `$schema: "../fixture-schema.json"`) but its shape (`fixture_id`, `regex_contract`, `contexts`) had **none** of the schema's 7 required keys. `additionalProperties: false` would have caused `jsonschema.validate()` to reject it. The fixture was never actually loaded by any test — its name appeared only in a docstring comment. **Patch:** renamed to `_fr56_polling_ban_regex_contract.json` (underscore prefix → excluded from loader discovery) + added `_note` disclaimer + updated 2 callers (`test_polling_ban_regex_stability.py` docstring + `error-class-hierarchy.md` reference).
- **HIGH-2**: `test_exit_70_when_failures_present` (AC-8a.2.6 #6) was fake-green per `feedback_test_name_assertion_match` — it computed `EXIT_CODE_FALLBACK if (summary.failed or summary.errored) else 0` inline + asserted that equals 70, **without ever calling `main()`**. A bug in the CLI's exit branch would have been invisible to this test. **Patch:** refactored to `monkeypatch.setattr(_execute_fixture)` to return a synthetic `FixtureResult(status="failed")`, then drives `main(["--adapter", "mock", ...])` end-to-end and asserts the actual returned exit code is 70.

### Story 8b.1

- **HIGH-1 (FINDING-1)**: `src/AgentEval/_init/templates/example_mcp_runtime.robot:18` called `MCP.Start Server` with `${CURDIR}/fixtures/.mcp.json` as the first positional arg and `bundled-echo` as the second. But the keyword signature (`mcp/library.py:195`) is `start_server(name: str, transport: Transport, command, args, ...)` — so the template was passing a file path as `name` and `"bundled-echo"` as `transport` (an invalid `Transport` literal — valid values: `stdio` / `streamable_http` / `in_memory`). The template would fail at runtime if executed — but the integration test `test_init_5min_path.py:50-53` explicitly skips this template citing "flaky in CI" (FINDING-7 = real fake-green pattern). **Patch:** rewrote the template's `Setup Bundled Echo` to use the canonical signature: `MCP.Start Server    bundled-echo    stdio    python    args=${{['-m','AgentEval.mcp.bundled.echo']}}` (matches `tests/unit/mcp/test_robot_integration.robot:40` precedent).

### Story 8b.2

- **HIGH-1**: `CohortHeatmap.as_ascii()` at `_heatmap/models.py:87` + L111 used `data.get(task, {}).get(model, 0.0)` — missing cells silently rendered as `"0.00"`, **indistinguishable from a genuine 0% pass-rate**. Operators looking at heatmap output couldn't tell missing-data apart from real-zero. **Patch:** added sentinel `" — "` (em-dash with spaces) for missing cells via a `_fmt(task, model)` helper that returns `None`-sentinel-aware output. Heatmap operators can now distinguish missing from zero.
- **HIGH-2**: `_terminal_summary.render_summary()` at L41-51 **hard-coded `passed = total`**, falsifying the FR54 visual contract ("`Tests: N total / N passed / N failed`"). The displayed "passed" count was always equal to total regardless of actual test outcomes. Comment at L48-50 acknowledged "Phase-1.5 wiring" but the user-visible output line still claimed authoritative counts. **Patch:** replaced fabricated `passed`/`failed` with `"—"` (em-dash) sentinel + `[Phase-1.5 C71]` marker; documented gap as C71 (`DF-8b.2-S1`) in `phase-1-5-carry-overs.md` — Listener's `_snapshot_completed_run_metadata` must capture `result.passed: bool` per test before the sentinel can be removed.

### Story 8b.3

- **HIGH-1**: `src/AgentEval/stats/types.py:47` `KeywordRun.completeness` docstring still cited `default predicate matches completeness == "full"` — **post-Story-6.4 fix-NOW** at `stats/_internal.py:250` flipped the default predicate to `completeness == "complete"`. The `AgentRunMetadata._VALID_COMPLETENESS` literal set is `{"complete", "truncated", "partial"}` (no `"full"`). Cross-file amendment missed during Story 6.4's fix-NOW. **Patch:** amended the docstring to cite `"complete"` + added an explicit cross-reference to the Story 6.4 fix-NOW comment at `_internal.py:235-249`.

### Story 9.1

- **HIGH-2**: `.github/workflows/dogfood-integration.yml:104-106` gated `parity-suite-smoke` job (Story 9.1 / AC-9.1.3 regression gate) on `workflow_dispatch + release` only — **excluding `pull_request` entirely**. This meant the "deliberate regression verification" (AC-9.1.4) required a manual trigger, AND the domestic regression gate could never block a PR that introduced a regression. AC-9.1.3's "fails the workflow on ANY parity-suite failure" was therefore untestable on normal development PRs. **Patch:** added `pull_request` label-`release-pending` trigger matching the existing `dogfood` job pattern. Same fix propagated to `agentskills-parity-suite-smoke` (Story 9.2 AC-9.2.4) at L169-171 — both jobs now testable on labeled PRs.
- **HIGH-1 (NOT patched — deferred)**: parity-checklist classification table arithmetic inconsistency ("15 ported from test_mcp_simple.py" vs actual 12 robot tests vs 8 direct ports). Documentation drift; the underlying test count is correct, the meta-table is imprecise. Phase-1.5 hygiene work.

### Story 9.2

- HIGH findings (citation drift on test counts: "13≠11 assertions", "11≠6 stats", etc.) — **doc-quality deferred** (Phase-1.5 cleanup; story spec test counts are estimates, actual suites are correct).
- Inherited fix: `agentskills-parity-suite-smoke` workflow trigger extended to PR label-`release-pending` (same as Story 9.1 HIGH-2).

### Story 9.3

- Verdict: ratify-with-patches with 0 HIGH (3 MED + 3 LOW). **No patches applied** — all findings are doc-quality drift on the Phase-1 retrospective (e.g., "11 epics" vs "12 epic slots"). The exit-criteria-0x-to-1x.md document is substantively correct; the Phase-1 retro's table label is the minor drift.

## False positives (rescinded by kilo on re-verification OR overruled in this pass)

- Story 8b.1 FINDING-2, FINDING-3, FINDING-4, FINDING-5, FINDING-6: kilo self-corrected on re-derive (`${CURDIR}` paths are correct; scaffold's listener invocation is consistent; `metadata.completeness` dot-path is correct).
- Story 10.1 MED-3 (off-by-one citation): verified by `base.py` read — L226 IS the last statement of `InProcessAdapter.version` body; citation accurate.
- Story 10.1 MED-4 (3-branch docstring claim): re-read confirms docstring lists exactly 2 branches with aspirational C68 note.

## Gates

- **1380 pytest pass + 10 skipped** (unchanged from pre-batch state).
- **ruff check + format + mypy** all clean (96 source files).
- 8 HIGH patches applied without regression; 4 deferred or rescinded.

## Norm reinforcement

- `feedback_third_llm_family_fallback` (CANDIDATE since Story 10.2): **9 consecutive substantive cross-LLM reviews** delivered by kilo/minimax across Epic 10 (10.1 + 10.2) + Epic 8 (8a.2, 8b.1, 8b.2, 8b.3) + Epic 9 (9.1, 9.2, 9.3). Promote to **NEW (ratified)** for Phase-2 retro consideration.
- `feedback_test_name_assertion_match` (Epic 3 retro): **3 new violations caught** in this batch (8a.2 HIGH-2, 8b.1 FINDING-7, 8b.2 HIGH-2) — pattern persists across stories that ship without cross-LLM review. Reinforces the norm as load-bearing.
- `feedback_listener_hook_api_surface_empirical_check` (Epic 8 retro): **1 new violation caught** (8a.2 fixture schema mismatch — empirical schema validation would have rejected the file). Pattern persists.

## Carry-over additions

- **C71** (`DF-8b.2-S1`): terminal-summary pass/failed counts not populated. New carry-over per 8b.2 HIGH-2 honest-framing patch. Catalog total: 70 → 71.

## Significance

Epic 8 retro Action #1 step (iii) — third-LLM-family fallback — now has **9 consecutive load-bearing data points** (Story 10.1 + 10.2 + this batch of 7). The cross-LLM pipeline is **functionally restored via kilocode/minimax** — Claude CLI + Codex CLI remain degraded but kilo/minimax provides equivalent adversarial review depth. Epic 8 retro Action #1 should now be marked **resolved** at the next retrospective (pending operator confirmation).

## Commit reference

This summary is committed alongside the 8 HIGH patches in commit [TBD].
