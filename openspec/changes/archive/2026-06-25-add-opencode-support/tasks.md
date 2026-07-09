## 1. Empirical probe (do FIRST, per feedback_listener_hook_api_surface_empirical_check)

- [x] 1.1 Confirm `opencode` is on PATH and capture `opencode --version` output; record the detected version string and the semver substring `_SEMVER_RE` extracts
- [x] 1.2 Run `opencode run --help` and record the exact non-interactive invocation, the prompt-passing form, the model-selection flag, and any machine-readable/JSON output flag
- [x] 1.3 Run a real `opencode run "<trivial prompt>"` and determine the event source: Case A (JSONL streamed to stdout) vs Case B (output written to a session/state file). Record the decision in design.md if it differs from the assumption
- [x] 1.4 Capture sample output (stdout and/or session file) into `tests/fixtures/opencode_cli/` for fixture-driven unit tests
- [x] 1.5 Set the pinned `MIN_VERSION`, `MAX_VERSION`, and `_TESTED_UP_TO` constants from the probed version

## 2. Adapter implementation

- [x] 2.1 Create `src/AgentEval/coding_agent/opencode_cli.py` with the Apache license header and module docstring (cite ADR-003, FR12, FR47, FR60, ADR-016 §L33)
- [x] 2.2 Define the `OpenCodeEvent` frozen dataclass intermediate event type (discriminator + raw payload + convenience accessors), mirroring `CopilotEvent`/`CodexEvent`
- [x] 2.3 Implement `OpenCodeCLIAdapter(SubprocessAdapter)` with `__init__` calling `_assert_binary_version("opencode", MIN_VERSION, MAX_VERSION)` and `emit_adapter_version_drift_warning_if_applicable(...)`
- [x] 2.4 Implement the `name` property returning `"opencode-cli"`
- [x] 2.5 Implement `_spawn` launching `opencode run` non-interactively with prompt + optional model, `stdout=PIPE`, `stderr=STDOUT`, `text=True`, `start_new_session=True`
- [x] 2.6 Implement `_parse_event` (skip blank/non-JSON lines; build `OpenCodeEvent`)
- [x] 2.7 Implement `_finalize` projecting events into `AgentRunResult` (response_text, tool_calls, usage, completeness); emit `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` fail-loud diagnostic on silent non-zero exit
- [x] 2.8 Implement `_detect_mcp_coverage` per ADR-016 §L33 (empty → `hosted_in_process`; non-empty → `external_mixed`)
- [x] 2.9 If probe selected Case B, override `run()` for post-hoc session-file read with the documented thread-safety + newest-dir-race invariants; wire `record_active_run_metadata`
- [x] 2.10 Add `DF-<story>-S<N>` carry-over markers for any unexposed `cost_usd`/`latency_seconds`/`input_tokens`/`trace_id` placeholder fields

## 3. Registration & exports

- [x] 3.1 Register `OpenCodeCLIAdapter` under the stable name `opencode-cli` in the `agenteval.coding_agents` entry-points group (`pyproject.toml`) + add the `opencode = []` optional-extra
- [x] 3.2 ~~Re-export from `__init__.py`~~ AMENDED (in-flight): follow the ratified convention — concrete adapters are imported from their submodule, NOT re-exported from the package `__init__` (6 siblings precedent). No `__init__.py` change; importability verified via the submodule path.
- [x] 3.3 Add the new public adapter to `docs/contracts/stability-surface.md`

## 4. Tests

- [x] 4.1 Create `tests/unit/coding_agent/test_opencode_cli.py` driven by the committed fixtures
- [x] 4.2 Test Protocol conformance + `name`/`version` properties
- [x] 4.3 Test `_spawn` builds the correct command line (prompt + model forwarded; stderr multiplex)
- [x] 4.4 Test successful run → response text + `ToolCallTrace[]` populated
- [x] 4.5 Test non-zero-exit-with-no-output → `[SUBPROCESS_NONZERO_EXIT ...]` + `truncated` completeness; terminal+exit-0 → `complete`
- [x] 4.6 Test version pin: below-min / at-or-above-max → `UnsupportedBinaryVersionError`; missing binary → unavailable-version error. AMENDED (honest-framing): the drift helper fires only when the binary is OLDER than tested (≥2 minors) — newer never fires, and given MIN/TESTED share minor 15 the within-range drift window is empty; so the testable assertion is "in-range version constructs without a spurious `AdapterVersionDriftWarning`".
- [x] 4.7 Test `mcp_coverage`: empty → `hosted_in_process`; non-empty → `external_mixed`
- [x] 4.8 Test discovery resolves `"opencode-cli"` to the adapter class
- [x] 4.9 Add gated live smoke test `tests/integration/test_opencode_cli_live.py` mirroring `test_codex_cli_live.py` (env-flag gated; credentials read via `os.environ.get` helper, never RF `Get Environment Variable`)

## 5. Quality gates & review

- [x] 5.1 `uv run ruff check src/ tests/` clean
- [x] 5.2 `uv run mypy src/` clean
- [x] 5.3 `uv run pytest tests/` green (no regressions)
- [x] 5.4 Carry-over catalog gate: grep new file for `DF-X-SY` and verify each entry is in `docs/phase-1-5-carry-overs.md`
- [x] 5.5 Run the cross-LLM review chain (Tiers 1+2, escalate to Tier 3 if degraded) per CLAUDE.md; apply HIGH findings inline before marking done. DONE: Tier 1 (Claude) ✅ 3 MED+3 LOW; Tier 2 (Codex) ❌ degraded (hung on stdin) → Tier 3 (kilo) ✅ invoked per fallback. Applied 3 new regression tests + `--` argv sentinel + `stdin=DEVNULL` + doc-accuracy fixes; rejected kilo HIGH-1/MED-2 (false positive, probe-verified) + kilo MED-3 (semantic divergence) with documented rationale. Synthesis: `_bmad-output/cross-llm-reviews/add-opencode-support-synthesis.md`.
