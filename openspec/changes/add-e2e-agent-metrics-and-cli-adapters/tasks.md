## 1. P0 — unblock metrics (fix the adapter)

- [x] 1.1 `_core/adapter.py`: parse `response.choices[0].message.tool_calls` into `ToolCallTrace` records in `_map_completion` (currently hard-coded `[]`); populate `Usage.cached_input_tokens` when the provider reports it.
- [x] 1.2 Record on `AgentRunMetadata` whether cost + tokens are `native` or `derived` (litellm-computed); document that `GenericAdapter` captures *requested* tool calls, not an executed agent loop.
- [x] 1.3 Unit tests: a stubbed litellm response with tool calls + usage yields a populated `AgentRunResult.tool_calls` + `usage` + `metric_source`.

## 2. P1 — metric surface (deterministic, high-value)

- [x] 2.1 `_core/types.py`: add `input_tokens` / `output_tokens` / `cost_usd` to `ToolCallTrace` (defaults 0; per-tool attribution home).
- [x] 2.2 New `MetricsLibrary` (spine-only, à-la-carte): `Get Token Usage`, `Get Cost USD`, `Get Latency Seconds`, `Get Tool Call Metrics` (per-task + per-tool rollup: count, passed=`error is None`, failed, tokens, cost, latency), `Tokens Used Should Be Below`, `Cost Should Be Below`. Each a Tier-1 reader over `AgentRunResult`.
- [x] 2.3 New `StatLibrary` (spine-only): `Stat.Run N Times`, `Stat.Get Pass At K`, `Stat.Wilson Interval` over `stats.py` — surfaces the estimators and fixes the phantom `Stat.Run N Times` example.
- [x] 2.4 Normalized run-metrics record (rf-mcp `ScenarioResult` superset) + `ExpectedToolCall{tool, min_calls, max_calls, required_args}` contract + `tool_hit_rate`; a keyword to compute the record from an `AgentRunResult` and one to export it to JSON.
- [x] 2.5 Add runnable examples to the four `SkillsLibrary` keywords missing them (`Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation`, `Get Activation Decision`).
- [x] 2.6 Add `scripts/check-keyword-examples.py`: extract every keyword's doc example and verify it resolves (`robot --dryrun`) + minimally executes where feasible; wire into the local gate + docs-build. Fix any broken example it surfaces.
- [x] 2.7 Regenerate libdoc for the new `MetricsLibrary` + `StatLibrary`; update README/`docs/index.md` keyword tables + counts; run the doc-keyword-count + doc-rendering gates green.

## 3. P1 — docs (LLM setup)

- [x] 3.1 README: add a "Running with a real LLM or coding agent" setup section — the `[llm]` extra + `AGENTEVAL_MODEL` + provider keys, and the coding-agent-CLI path (install the binary, adapter slug, where keys go).
- [x] 3.2 Update `docs/running-against-a-real-model.md` with the CLI-agent path; keep it in the Robot Framework voice.

## 4. P2 — coding-agent CLI adapters

- [ ] 4.1 `_core/cli_adapter.py`: `SubprocessCLIAdapter` base — `build_argv(prompt)` → `subprocess.run` (timeout, `start_new_session`, secrets from `os.environ` never logged, missing-binary fails loud with install guidance) → `parse_output(...)` → `AgentRunResult`; a `--version` probe into metadata + `AdapterVersionDriftWarning` outside a pinned range; a per-adapter `validation_ceiling` marker.
- [ ] 4.2 `claude-code` adapter (reference, FULL): `claude -p --output-format stream-json`; parse tool_use/tool_result + native cost + full/cache tokens; live E2E smoke gated on the binary + `ANTHROPIC_API_KEY`.
- [ ] 4.3 `gemini` (FULL) + `codex` (PARTIAL, de-cumulate turn tokens) + `opencode` (PARTIAL, native cost) adapters; register their slugs in `get_adapter`; each with a gated live E2E smoke. Confirm opencode's JSON field spellings by running it locally before committing the parser.
- [ ] 4.4 `kilo` + `copilot` adapters, best-effort DEGRADED with a VALIDATION-CEILING marker (copilot: session-log fallback, no JSON stdout; kilo: probe fields at runtime). Confirm field spellings locally.
- [ ] 4.5 End-to-end metrics recipe under `docs/recipes/`: a real agent run through a CLI adapter producing tool-call + token + cost metrics + a JSON export, RF voice, runnable.

## 5. Verification

- [ ] 5.1 Full local gate green: ruff, format, mypy, license, contract-sections, doc-keyword-count, doc-rendering, keyword-examples, pytest, robot smoke.
- [ ] 5.2 Live E2E smokes: run at least the `claude-code` (or an available) CLI adapter end-to-end and confirm a populated metrics record + JSON export with real tool-call + token + cost numbers; record which adapters were live-verified vs unverified honestly.
- [ ] 5.3 Confirm DEGRADED adapters + derived (non-native) numbers are marked so real-world numbers are never overstated.

## 6. Release + archive

- [ ] 6.1 PR → CI green → merge; consider a `0.2.0` minor bump (new keyword surface + adapters).
- [ ] 6.2 `openspec validate` passes; archive so the four new capabilities join the baseline.
