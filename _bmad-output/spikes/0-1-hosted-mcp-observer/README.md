# Story 0.1 Spike — Hosted-MCP Universal Observer

**Scratch directory.** All code here is discarded after Story 0.3 ratifies ADR-007 (→ ADR-004) and ADR-A6 (→ ADR-016). The deliverable that survives the spike is `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md`.

## What this spike validates

Three transports, one observation pattern (`Server.request_handlers[CallToolRequest]` handler-wrap):

| Transport | Probe entry point | mcp_coverage outcome |
|---|---|---|
| In-memory | `run_dual_transport_probe.py` → `run_in_memory_leg()` | `hosted_in_process` |
| Stdio subprocess (handler-wrap injected at subprocess bootstrap per D2) | `transports/subprocess_observer_wrapper.py` | `subprocess_with_observer` |
| Streamable HTTP (FastMCP + uvicorn) | `run_streamable_http_probe.py` | `hosted_in_process` |

Plus: D1 trust-floor `mcp_coverage` semantic (strongest complete path wins); D2 real handler-wrap injection across process boundaries; AC-0.1.1 3-state field exercised under `pabot --processes 4`.

## Re-running

```bash
cd _bmad-output/spikes/0-1-hosted-mcp-observer/

# 0. Make sure the venv is built. uv.lock pins exact versions.
uv venv --python 3.12 .venv
uv sync

# 1. Single dual-transport probe (in-memory + stdio handler-wrap injection)
.venv/bin/python run_dual_transport_probe.py probe-X measurements/dual_transport.jsonl

# 2. Streamable HTTP probe (D3)
.venv/bin/python run_streamable_http_probe.py probe-X measurements/streamable_http.jsonl

# 3. Edge cases (5 probes including real partial-log scenario per P12)
.venv/bin/python edge_cases/external_mixed_cases.py

# 4. 5-iteration pabot smoke loop (--processes 4 × 15 tests × 5 iters = 75 runs)
#    Preserves per-iter evidence at concurrency/pabot_evidence/iter_{1..5}/
./run_smoke_loop.sh
```

Outputs:

- `measurements/dual_transport.jsonl` — one record per dual-transport probe
- `measurements/streamable_http.jsonl` — one record per streamable HTTP probe
- `measurements/edge_cases.jsonl` — 5 records (one per edge probe)
- `measurements/smoke_loop.txt` — pabot timing + pass/fail summary
- `concurrency/pabot_evidence/iter_{1..5}/` — per-iteration JSONL + output.xml

## Directory layout

```
0-1-hosted-mcp-observer/
├── pyproject.toml + uv.lock         # exact-pinned scratch deps
├── observer_prototype.py            # HostedMcpObserver + AgentRunResult + ToolCallTrace
├── run_dual_transport_probe.py      # in-memory + stdio orchestrator
├── run_streamable_http_probe.py     # D3 streamable HTTP probe
├── run_smoke_loop.sh                # 5-iteration pabot driver with per-iter evidence
├── transports/
│   ├── in_memory_server.py          # in-memory MCP server (echo + add)
│   ├── stdio_subprocess_server.py   # plain stdio MCP server (NO baked-in instrumentation per D2)
│   ├── subprocess_observer_wrapper.py  # injects HostedMcpObserver at subprocess bootstrap (D2)
│   └── streamable_http_server.py    # FastMCP-based streamable_http server (D3)
├── concurrency/
│   ├── SpikeLibrary.py              # 4 keywords: dual / hosted-only / subprocess-only / external-mixed
│   ├── test_pabot.robot             # 15-test suite covering all 3 coverage states
│   └── pabot_evidence/iter_{1..5}/  # preserved per-iteration evidence
├── edge_cases/
│   └── external_mixed_cases.py      # 5 probes: no-attach, external-blind, partial-log, baseline, trust-floor
└── measurements/                    # all JSONL output + timing
```

## Caveats

- **LLM-driven autonomous spike** (Claude Opus 4.7, ~3h cumulative across review+rework). Pending independent reproduction per D5 review decision.
- **Linux only** (Ubuntu 24.04, Python 3.12.3). macOS validation pending Story 9.x.
- **Throwaway code.** Production observer lives in `src/AgentEval/mcp/observer.py` (Epic 5 Story 5.2). See `_bmad-output/implementation-artifacts/deferred-work.md` for production carry-overs identified during review.
