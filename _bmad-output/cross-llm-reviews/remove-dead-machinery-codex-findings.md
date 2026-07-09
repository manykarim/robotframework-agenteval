# remove-dead-machinery Codex Review Findings

## Findings

No substantive regressions found. No HIGH/MED/LOW findings to report.

## Verification Notes

- Removed packages/modules: `AgentEval.security`, `AgentEval.reporting`, and `AgentEval.discoverability.wilson_ci` now raise `ModuleNotFoundError`. Grep found no live imports, entry points, or `__init__` re-exports still depending on them; remaining hits are docs/comments/tests describing the removal or the retained `agenteval.sandboxes` entry-point seam.
- Wilson dedup: discoverability now imports `wilson_score_interval` from `AgentEval.stats.wilson`; supported old discoverability confidence levels `0.90`, `0.95`, and `0.99`, plus edge cases `n=0`, `p=0`, and `p=1`, match the pinned values in the folded tests. The new implementation accepts arbitrary `0 < confidence < 1` (including `0.50`), but discoverability has no confidence parameter and no call site relies on the old enum rejection.
- Config resolver merge: `resolve_config` is a value projection over `resolve_config_with_provenance`, and `AgentEval.__init__` resolves once. `Get Effective Config` no-arg still returns plain values, not `ConfigValue` records. The no-arg map now has 11 keys including `trace_path`; I found no consumer iterating the old exact key set, and the resolver/default map already treats `trace_path` as a real config key.
- `DuplicateRegistrationError` fold: no remaining `except DuplicateRegistrationError` or import sites in `src/`/tests. The collision path now raises `AdapterDiscoveryError` and the message includes the colliding name plus both entry-point groups.
- `@guarded_fanout` no-budget fast path: all production decorator sites use bare `@guarded_fanout()` with no estimator. `current_cancel_event()` has no production consumers outside `guardrails.py`; tests now pin the no-budget body seeing `None`. A budget set after method entry would not have been observed before either, because the old wrapper copied budget attrs into locals before starting the meter.
- Counts: libdoc reports 55 composed keywords, with `Get Effective Config` present and `Get Effective Config With Provenance` absent. Implemented error-code leaf count is 22, matching the reconciled doc claim.

## Commands Run

- `git diff --stat`, `git diff --name-status`, and focused `git diff` on changed runtime files.
- `rg` sweeps for removed modules, deleted keyword, `DuplicateRegistrationError`, Wilson confidence/call sites, config key-set consumers, and guardrail cancellation usage.
- `uv run python` probes for removed imports, Wilson edge values, config key shape, keyword presence, and implemented error-code class count.
- `uv run pytest -q tests/unit/stats/test_wilson.py tests/unit/discoverability/test_keyword.py tests/unit/discoverability/test_comparison.py tests/unit/kernel/test_discovery.py tests/unit/orchestration/test_config_provenance.py tests/unit/kernel/test_guardrails.py tests/unit/test_cli.py tests/unit/test_errors.py tests/integration/docs/test_keyword_count_drift.py` -> `165 passed`.
- `uv run pytest -q -k "wilson or discovery or guardrails or config_provenance or keyword_count or cli or errors"` -> `384 passed, 3 skipped, 1770 deselected, 1 warning`.
- `uv run python` libdoc probe -> `keyword_count 55`.
