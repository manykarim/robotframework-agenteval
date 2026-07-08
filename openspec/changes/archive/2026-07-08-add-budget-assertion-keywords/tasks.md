# Tasks: add-budget-assertion-keywords

## 1. Pre-implementation probes

- [x] 1.1 Empirically probe `assertionengine.verify_assertion(actual, AssertionOperator("<"), expected, message=...)` under the pinned 4.x via `_assertions/adapter.assert_value()`: confirm whether `message` prefixes or overrides the standard failure text, and capture the exact failure-message shape for a float comparison (design D3 / Risks). If `message` overrides, plan for the keywords to pre-format the complete actual-vs-threshold message.
- [x] 1.2 Confirm the four `AgentEval.metrics._internal` helper pairs to reuse (`_compute_cost_total`/`_aggregate_cost_total`, `_compute_latency_mean`/`_aggregate_latency_mean`, `_compute_latency_p95`/`_aggregate_latency_p95`, `_compute_token_usage`/`_aggregate_token_usage`) and their exact signatures.

## 2. Core implementation

- [x] 2.1 Add shared private helpers to `src/AgentEval/_assertions/library.py` (or `_internal.py`): threshold validation (`ValueError` on non-finite / `<= 0`), empty-list guard (`ValueError` on `result == []`), and evidence-message builder (observed, threshold, unit, run count).
- [x] 2.2 Implement `Cost Should Be Below` (`cost_should_be_below(result: AgentRunResult | list[AgentRunResult], max_usd: float)`) — compute via metrics `_internal` cost helpers, dispatch via `assert_value(actual, "<", max_usd, keyword_name=..., tier=1, message=...)`, no `mcp_coverage` gate, pass-side `robot.api.logger.info` evidence line; docstring notes strict `<` semantics and the mock-provider `cost_usd=0.0` trivial-pass caveat.
- [x] 2.3 Implement `Latency Should Be Below` (`max_ms: float`) — mean-latency helpers (incl. `latency_seconds * 1000.0` no-tool-calls fallback, union-then-mean multi-trial), same dispatch/evidence pattern.
- [x] 2.4 Implement `Latency P95 Should Be Below` (`max_ms: float`) — P95 helpers (AC-6.1.8 boundary rules), same dispatch/evidence pattern.
- [x] 2.5 Implement `Token Usage Should Be Below` (`max_tokens: int`) — total = `input_tokens + output_tokens` (docstring states the formula; no double-count of cached/reasoning sub-fields), same dispatch/evidence pattern.
- [x] 2.6 Write Browser-Library-style docstrings for all four keywords: `[Tier 1 — Deterministic]` badge, `=Arguments=` table, dryrun-clean RF example block, Raises section (`ValueError` + assertion failure), sibling-keyword cross-references to the wrapped getters, and the empty-list-vs-getter-vacuous-truth divergence note.

## 3. Tests

- [x] 3.1 Add unit tests in `tests/unit/_assertions/test_assertions_library.py` covering, for EACH keyword: pass under threshold; fail over threshold; fail at exactly the threshold (strict `<`); multi-trial aggregation matches the corresponding getter's semantics (sum / union-mean / union-P95 / per-field token sum); failure-message content asserts observed value + threshold + unit substrings (not full-string equality per design Risks).
- [x] 3.2 Add shared-validation tests: empty list → `ValueError`; threshold `0` / negative / `NaN` → `ValueError` fired before dispatch; `external_mixed` run does NOT raise `IncompleteTraceError`; latency no-tool-calls fallback; token cached-subset non-double-count case.
- [x] 3.3 Add pass-side evidence-log test (capture `robot.api.logger` output; assert observed/threshold/unit/run-count fields present).
- [x] 3.4 Run the auto-walking conventions suites (`uv run pytest tests/unit/conventions/`) — tier badge, docstring style, name idiom, docstring-example dryrun must all pass for the 4 new keywords.
- [x] 3.5 Full gate: `uv run pytest tests/` + `uv run ruff check src/ tests/` + `uv run mypy src/` all green.

## 4. Documentation

- [x] 4.1 Add 4 rows to the README "Keywords at a glance" `AgentEval` table (Tier 1, one-line descriptions) and increment the affected keyword counts in that section by 4 (do NOT attempt to fix the pre-existing count drift documented in dossier E3 — separate change).
- [x] 4.2 Regenerate `docs/keywords/AgentEval.html` via the documented libdoc command and verify the four keywords render with Tier-1 badges and argument tables.

## 5. Close-out gates

- [x] 5.1 Carry-over catalog gate: grep the diff for `DF-X-SY`-pattern markers and verify any new deferral is cataloged in `docs/phase-1-5-carry-overs.md` (expected: none — but if the AC-SIMPLICITY-01 retrofit gap for the 5 pre-existing assertion keywords is annotated in code, catalog it).
- [x] 5.2 Caller-count check: confirm any new private helper has ≥1 caller (no stranded helpers).
- [ ] 5.3 Cross-LLM review chain per CLAUDE.md (Tier 1 + Tier 2 in parallel; Tier 3 on degradation) before marking the change complete.
