## Context

Post-refocus, `robotframework-agenteval` has a clean `_core` spine — `Usage(input_tokens, output_tokens, cached_input_tokens)`, `ToolCallTrace(name, args, result, error, latency_ms, source)`, `AgentRunResult(usage, cost_usd, latency_seconds, trace_id, tool_calls, metadata)`, and `stats.{run_n, pass_at_k, wilson_interval}`. `MCPLibrary` records live `MCP.Call Tool` invocations and exposes coverage keywords (count/names/hit-rate/success-rate). But: the only adapter (`GenericAdapter`) hard-codes `tool_calls=[]` and drops cached tokens; none of the token/cost/latency data is exposed as keywords; `stats` is not a Library (its docstring example `Stat.Run N Times` is a phantom); and the refocus deliberately deleted the old vendor CLI adapters. Research (four streams: rf-mcp harness, coding-agent CLIs, eval frameworks, current-repo gaps) informs the decisions below.

## Goals / Non-Goals

**Goals:**
- Real-world usage numbers from real agent runs: per-run and per-tool tool-call counts, passed/failed calls, token usage, cost, latency, pass@k.
- End-to-end runs through real coding-agent CLIs (claude-code, gemini, codex, opencode; kilo, copilot best-effort) via one lean seam, normalized into `AgentRunResult`.
- A normalized, exportable metrics record (rf-mcp `ScenarioResult` shape) so numbers can be collected + compared.
- Every keyword doc carries a runnable example; README documents live LLM + CLI-agent setup; all examples run.

**Non-Goals:**
- Re-creating the old per-vendor adapter sprawl — one seam + thin parse strategies only.
- Trajectory (order/argument) matching, Tool-Call F1, and trajectory-aware Task-Completion judges — valuable (P3), but out of this change.
- RAG metrics, academic benchmarks, a standing OTel/dashboard backend, multimodal red-team, simulated-user autopilot.
- Packaging the agent CLIs — they are externally installed; adapters shell out and are documented.

## Decisions

### D1 — Fix `GenericAdapter` first (P0); it blocks everything
`_map_completion` (adapter.py:137) reads tokens + computes cost but sets `tool_calls=[]`. Parse `response.choices[0].message.tool_calls` into `ToolCallTrace` records and populate `cached_input_tokens`. Record on `AgentRunMetadata` whether cost/tokens are *native* or *derived*. **Why:** every metric over an agent run is empty until tool calls are actually captured. **Note:** a one-shot litellm chat is not agentic; the `GenericAdapter` captures the model's *requested* tool calls, which is the honest limit of a non-loop adapter — documented as such.

### D2 — Metrics are thin readers over existing fields, plus two data holes filled
Add per-tool `input_tokens`/`output_tokens`/`cost_usd` to `ToolCallTrace` (the only missing home for per-tool numbers) and expose Tier-1 reader keywords (`Get Token Usage`, `Get Cost USD`, `Get Latency Seconds`, `Get Tool Call Metrics`) + budget assertions (`Tokens Used Should Be Below`, `Cost Should Be Below`). Passed/failed tool calls are already derivable (`error is None`). **Why:** the data model already carries almost everything; the gap is surface, not substance. **Alternative:** a heavyweight metrics subsystem — rejected; keep it as readers over `AgentRunResult`.

### D3 — Ship `stats` as a real `StatLibrary`
Wrap `stats.py` in `Stat.Run N Times` / `Stat.Get Pass At K` / `Stat.Wilson Interval`. **Why:** the estimators exist but are unreachable from `.robot`, and `Skill.Get Activation Pass At K`'s example references the phantom `Stat.Run N Times`. This fixes a broken example *and* unlocks statistical rigor for stochastic (agent/judge) runs.

### D4 — One normalized metrics record + JSON export (adopt rf-mcp's shape)
Define a run-metrics record modeled on rf-mcp's `ScenarioResult` — `{tool_calls[], total_tool_calls, tool_hit_rate, expected_met/total, errors[], execution_time, usage, cost}` — with a **declarative expected-tool contract** (`ExpectedToolCall{tool, min_calls, max_calls, required_args}`) and a keyword to write it to JSON. Every adapter (LiteLLM or CLI) normalizes *into* this one record. **Why:** rf-mcp proved one schema across in-process + subprocess runs is what makes real-world numbers comparable; ground-truth capture (not model self-report) satisfies the honest-framing norm.

### D5 — One `SubprocessCLIAdapter` seam; per-agent parse strategies; honest fidelity tiers
`SubprocessCLIAdapter` template: `build_argv(prompt)` → `subprocess.run` (timeout, secrets from `os.environ` never logged, `start_new_session`) → `parse_output(stdout, stderr, exit_code, session_file)`. Each concrete adapter overrides only argv + parse. Fidelity is uneven and **must be labeled**:

| CLI | invocation | tool calls | tokens | cost | tier |
|---|---|---|---|---|---|
| claude-code | `claude -p --output-format stream-json` | ✅ | ✅ +cache | ✅ native | FULL |
| gemini | `gemini -p --output-format json` | ✅ | ✅ | derive | FULL |
| codex | `codex exec --json` | ✅ | ✅ (de-cumulate) | derive | PARTIAL |
| opencode | `opencode run --format json` | ✅ | ✅ | ✅ native | PARTIAL |
| kilo | `kilo run --auto --json` | ⚠️ probe | ⚠️ | est. | DEGRADED |
| copilot | `copilot -p` (no JSON stdout) | session-log | log/OTel | premiumRequests | DEGRADED |

Read stdout JSON when present; fall back to the newest on-disk session/rollout transcript (`~/.claude/projects/…`, `~/.codex/sessions/…`) when thin (the only path for copilot). Cost precedence: native → else `litellm.completion_cost` (the path the repo already uses), recording which. **Why:** one seam contains the sprawl; per-adapter VALIDATION-CEILING markers prevent DEGRADED adapters from reading as fake-green. **Alternative:** an SDK-per-vendor integration — rejected as the old sprawl.

### D6 — Version drift is first-class
Each adapter probes `--version` into `AgentRunMetadata` and raises `AdapterVersionDriftWarning` outside a pinned range; each ships a live E2E smoke as the empirical-truth check. **Why:** research found version-gated behavior everywhere (codex token de-cumulation post-2025-09-06, gemini JSON ≥~0.6.1, claude stream-json fix). Field spellings for opencode/kilo are **confirmed by running the CLI locally** before parse code is committed.

### D7 — Keyword examples are executable, not decorative
Add runnable examples to the four `SkillsLibrary` keywords missing them, and add a gate that extracts + runs every doc example (RF `--dryrun` for keyword-resolution + a minimal execute where feasible). **Why:** the phantom `Stat.Run N Times` proves examples silently rot; the project's executable-doc precheck norm applies.

## Risks / Trade-offs

- **[Re-adding vendor adapters risks the old sprawl]** → one `SubprocessCLIAdapter` seam, thin per-agent parse only, no SDK dependencies, no per-vendor extras. This is the central design guardrail.
- **[DEGRADED adapters overstate real-world numbers]** → per-adapter VALIDATION-CEILING marker on the result + in docs; derived (non-native) cost/tokens flagged in metadata.
- **[Version drift breaks parse code]** → version probe + `AdapterVersionDriftWarning` + per-adapter live E2E smoke; pin tested versions in docs.
- **[CLI adapters need the binaries installed + API keys]** → not packaged; documented setup; adapters fail loud with install guidance when the binary is missing.
- **[Live agent runs are slow/costly/non-deterministic]** → keep them env-gated + off the default CI gate (mirror the existing live-provider gating); the deterministic metric keywords + StatLibrary carry the CI value.
- **[GenericAdapter is not a real agent loop]** → documented; it captures requested tool calls, not an executed trajectory. A looping adapter is future work.

## Migration Plan

Phased, each phase independently valuable and CI-green:
1. **P0** — `GenericAdapter` tool-call + cached-token fix + `metric_source` metadata (unblocks metrics; small).
2. **P1** — `ToolCallTrace` token/cost fields; metric-reader keywords + budget assertions; `StatLibrary`; normalized metrics record + JSON export; the four missing keyword examples + the run-all-examples gate; README/real-model CLI-agent setup section. *Mostly deterministic, cheap, high-value.*
3. **P2** — `SubprocessCLIAdapter` + claude-code (reference, FULL) → gemini → codex → opencode; then kilo + copilot DEGRADED; version-drift + per-adapter E2E smoke; the end-to-end metrics recipe.
4. **(future, separate change)** P3 — trajectory/argument matching, Tool-Call F1, Task-Completion judge.

**Rollback:** additive; revert per phase. No stable-API commitment beyond 0.x.

## Open Questions

- Do the metric keywords live in a new `MetricsLibrary`, in `StatLibrary`, or fold into the existing surface libraries? (Leaning: a small `MetricsLibrary` + `StatLibrary`, both spine-only, imported à la carte like the four surfaces.)
- Confirm exact JSON field spellings for opencode + kilo by running each locally before committing parse code (research flagged these as uncertain).
- Ship copilot + kilo in this change (DEGRADED) or defer to a follow-up once FULL/PARTIAL adapters prove the seam? (User chose: include as best-effort DEGRADED.)
- Should the JSON metrics export schema match rf-mcp's `ScenarioResult` field-for-field (cross-tool comparability) or a superset with token/cost that rf-mcp lacks? (Leaning: superset, documented.)
