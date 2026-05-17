# Story 0.2 Spike — Per-Test MCP Cleanup Under Pabot

**Scratch directory.** All code here is discarded after Story 0.3 ratifies ADR-A6 + ADR-A8 (no amendments required from Story 0.2 — see findings doc §AC-0.2.3.d) and Epic 1b Story 1b.1 implements the production `_kernel/context.py` against the API surface drafted in the findings doc.

The deliverable that survives is `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md`.

## What this spike validates

| Scope | Lifecycle | Validated under |
|---|---|---|
| `test` | spawn in `start_test`, kill in `end_test` | `pabot --testlevelsplit --processes 8`, 1 suite × 16 tests |
| `suite` | spawn lazy on first `start_test`, kill in `end_suite` | `pabot --processes 4` (no testlevelsplit), 4 suites × 4 tests |
| `process` | spawn lazy on first `start_test`, kill in listener `close()` | `pabot --processes 4` (no testlevelsplit), 4 suites × 4 tests |

Plus: 3 MCP server types (echo, rf-mcp-substitute, slow_server with `time.sleep(2)` startup), 5 iterations per cell = 45-iter smoke matrix, all targets met by ≥120×.

## Re-running

```bash
cd _bmad-output/spikes/0-2-pabot-mcp-cleanup/
uv venv --python 3.12 .venv
uv sync

# 5-iter × 9-cell smoke matrix (~2 min total)
./run_smoke_matrix.sh

# Single-shot timeout probe (Task 7)
rm -rf pabot_results measurements/timeout_probe measurements/raw_*.jsonl
mkdir -p measurements/timeout_probe
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD" .venv/bin/pabot \
    --testlevelsplit --processes 4 \
    --listener "mcp_listener.MCPCleanupListener:test:slow_server" \
    --outputdir measurements/timeout_probe/pabot_results \
    suites/timeout_probe.robot > measurements/timeout_probe/pabot_stdout.log 2>&1
mv measurements/raw_*.jsonl measurements/timeout_probe/
```

## Output artifacts

- `measurements/aggregated.csv` — one row per `release_*` event across all iterations (~360 rows)
- `measurements/cell_summary.csv` — one row per (scope × server × iter) = 45 rows
- `measurements/cell_<scope>_<server>/iter_<i>/` — per-iter raw JSONL + RF output.xml + pabot stdout
- `measurements/leak_diffs/` — `ps -eo pid,args | grep SPIKE-0-2` snapshots before + after each iter
- `measurements/timeout_probe/` — Task 7 evidence (RF `[Timeout]` vs Listener v3 reliability)

## Caveats

- **LLM-driven autonomous spike** — Story 0.3 blocked on D5 independent reproduction per the Story 0.1 review.
- **Linux only** — macOS untested, Phase-1 carry-over per `_bmad-output/implementation-artifacts/deferred-work.md`.
- **rf-mcp substituted** — `servers/rf_mcp_substitute.py` mimics the real rf-mcp's profile (multi-tool + moderate startup + per-call CPU) since no git access in environment. See `servers/rf_mcp_pin.txt`.
- **Architecture.md L710 hypothesis disproven** — Listener v3 `end_test` fires reliably even on RF `[Timeout]` failures in RF 7.4.2 / pabot 5.2.2. atexit failsafe is documented as defense-in-depth, NOT primary.
