## 1. Spine — `AgentEval._core`

- [x] 1.1 Freeze the small internal import surface the rest of the tree uses (`tier`, `get_adapter`/adapter protocol, `resolve_config`) so later deletions can migrate against a stable seam
- [x] 1.2 Create `_core/tier.py` — port the `@tier(1|2|3)` marker; drop the `inspect.stack()` tier-ACL, replace with a cheap explicit check
- [x] 1.3 Create `_core/types.py` — port `AgentRunResult` + the handful of shared frozen dataclasses actually used by the four surfaces; drop unused `RunManifest` placeholder fields
- [x] 1.4 Create `_core/errors.py` — collapse the 44-class hierarchy to ~12 leaves under one base; keep the `error_code` prefix and sync the CLI exit-code table
- [x] 1.5 Create `_core/adapter.py` — `run(prompt) -> AgentRunResult` protocol + one LiteLLM `GenericAdapter`; port the async bridge (`run_async`); gate on the `[llm]` extra with a clear missing-extra error
- [x] 1.6 Create `_core/stats.py` — port run-N / pass@k / Wilson CI; fix the pass@k predicate default so surface-specific `Get *Pass At K` band-aid keywords are unnecessary
- [x] 1.7 Create `_core/judge.py` — port rubric/criteria parse + prompt compose + strict-JSON score; drop the calibration subsystem and uncalibrated-warning machinery
- [x] 1.8 Create `_core/trace.py` — port span + tool-call emission and the deterministic tool-call projection; drop OTLP/JSONL/JUnit/EvidenceBlock/run-manifest export and the god-listener
- [x] 1.9 Port/write `_core` unit tests; run the full local CI gate green before touching surfaces

## 2. Surface libraries (on the spine, smallest first)

- [x] 2.1 `HooksLibrary` — port config parse (nested only; drop legacy-flat + deprecation path + inline-skill extraction), the shared matcher engine, subprocess firing (sanitized env, enforced timeout, normalized decisions), and the assertion keywords; collapse the triple env-sanitization to one allowlist; reduce the SIGALRM ReDoS guard to a length cap
- [x] 2.2 `HooksLibrary` — verify it loads and runs Tier-1 with zero LLM/MCP deps; port/rewrite its tests
- [x] 2.3 `SubagentsLibrary` — port frontmatter parse, `extract_delegations`, config-drift checks; merge near-duplicate tier keywords (raise-vs-return) into one parameterized keyword; route accuracy through one `_run_adapter_once`; port tests
- [x] 2.4 `SkillsLibrary` — port `_parser` + the Tier-1 getters/validator + activation/discoverability; collapse the 4× substring-activation heuristic into one helper; add the Tier-2 judge-based activation mode; port tests
- [x] 2.5 `MCPLibrary` — port config/schema getters + validate, lifecycle (slim `MCPLifecycleManager`, drop pabot/atexit ceremony), `Call Tool` (kwargs + dict, conflict = error), coverage metrics, and single-adapter discoverability; gate live keywords on `[mcp]`; port tests
- [x] 2.6 Run the full local CI gate green with all four libraries importable independently

## 3. Delete dropped modules and their tests

- [x] 3.1 Remove `baseline`, `redteam`, `conversation`, `conformance`, `_heatmap`, `scenarios` and their `tests/unit/<module>/` suites
- [x] 3.2 Remove the five vendor coding-agent adapters + FR47 version-range machinery; keep only the generic adapter in `_core`
- [x] 3.3 Remove the dead `_kernel` cost-meter, `host_budget_plumbing`, `version_drift`, and the stats A/B trio (+ scipy/numpy) and discoverability cross-adapter comparison
- [x] 3.4 Delete the old flat `AgentEval` DynamicCore composition, collision detector, and namespace-prefix baking; migrate any remaining imports to `_core`
- [x] 3.5 Run the code gate green (ruff, format, mypy 32 files, license 32 files, pytest 198 passed); confirm no import references dead modules. NOTE: `check_doc_keyword_count.py` is intentionally red here — README/docs/index.md still describe the old 98-keyword surface and the check still introspects the gutted 14-lib composition; both are fixed in Phase 5 (task 5.1/5.2 + repoint the check at the four new libraries).

## 4. Packaging and CLI

- [x] 4.1 Update `pyproject.toml` — base deps (RF, robotlibcore, PyYAML) + extras `[mcp]`, `[llm]`, `[all]`; move `mcp`/`litellm`/`scipy`/`numpy` out of base
- [x] 4.2 Add the optional thin `Library AgentEval` convenience composite over the four surfaces (documented as non-default)
- [x] 4.3 Trim `cli.py`: exit-code table now re-exported from `_core.errors` (one source of truth); `new-adapter` subcommand dropped with the vendor adapters. NOTE: the `init` scaffold is deferred to Phase 5 (onboarding) — it must generate example suites for the four-library surface, which belongs with the doc/voice pass.
- [x] 4.4 Verify each library imports standalone with only its required extras installed

## 5. Docs and the Robot Framework voice

- [x] 5.1 Rewrite `README.md` — reframe the mission/tagline to testing MCP/Skills/SubAgents/Hooks (deterministic / LLM / agent); RF voice; four-library import story; extras matrix; honest mode matrix
- [x] 5.2 Strip per-keyword FR/AC/ADR/Story provenance docstrings across all four libraries down to terse RF-voice libdoc; regenerate `docs/keywords/*.html`
- [x] 5.3 Keep and voice-edit surviving recipes (first-eval, first-mcp-test, skill validation, hooks, CI integration); delete recipes tied to dropped modules (conversation, red-team, baseline, custom-adapter)
- [x] 5.4 Add the missing SubAgents recipe (the prime white-space surface)
- [x] 5.5 Pruned ADRs/contracts referencing dropped modules (deleted the coding-agent/telemetry/conformance/persona ones; kept + superseded-noted the MCP + infra ones). Rewrote the two onboarding stragglers (running-against-a-real-model, troubleshooting) in RF voice. NOTE: error-message strings were written terse/RF-voiced by the surface build already; no separate rewrite pass. `cli.py init` scaffold remains deferred (a follow-up).
- [x] 5.6 Run the CI-only doc gates (contract-sections, doc-keyword-count, catalog-references) green

## 6. Spec baseline re-cut

- [x] 6.1 `openspec validate refocus-four-surface-libraries` passes.
- [x] 6.2 Reconciled shipped keyword names against the five specs: no drift — every keyword named in a spec scenario ships, and MCP's coverage-metric keywords are exactly what mcp-testing requirement 3 describes. Shipped surface = 42 keywords (Hooks 8, MCP 15, Skills 10, Subagents 9).
- [x] 6.3 Baseline re-cut: deleted all 26 old capability specs, added the 5 new ones (evaluation-core, hook-testing, mcp-testing, skills-testing, subagent-testing - all validate). Change archived as 2026-07-16-refocus-four-surface-libraries (--skip-specs; baseline reconciled directly since OpenSpec cannot empty a spec via REMOVED-all).

## 7. Final verification

- [x] 7.1 Complete local gate green: ruff, ruff format, mypy (32 files), license (32), contract-sections (7), doc-keyword-count (42/4), catalog, pytest (198 passed).
- [x] 7.2 LOC: src 36,988 -> 6,566 (82.2% reduction); _core spine 1,569 LOC; keyword surface 104 -> 42. Past the ~9k target.
- [x] 7.3 Real `.robot` smoke suites under tests/robot/ - one Tier-1 suite per surface (import only that library) + a `Library AgentEval` composite suite: `robot tests/robot/` = 12 tests, 12 passed, 0 failed. NOTE: the Tier-3 live-model smoke is deferred (needs [llm] + provider credentials; the old dogfood minimax harness was deleted with the peripheral modules) - covered instead by the stub-adapter Tier-3 unit tests in tests/surfaces.
