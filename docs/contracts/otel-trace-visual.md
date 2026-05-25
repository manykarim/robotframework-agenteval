# OTel Trace Visualization

**Status:** Phase-1 stable (Story 8b.3 / FR58 — content authored 2026-05-25).
**Owning epic:** Epic 8b Story 8b.3.
**Related ADRs:** ADR-016 (MCP coverage detection), ADR-009 (per-test MCP scope), ADR-012 (catalog row: agentguard ADR-012 OTel RF Listener `adapt`).
**Related FRs:** FR32 (OTel GenAI spans), FR58 (OTel trace visual doc), FR33b (JSONL backend).

## Purpose

Describes how to load agenteval's JSONL trace artifacts into the canonical
OTel trace viewers (Jaeger, Honeycomb, Tempo) for visualization of the
`invoke_agent → chat → execute_tool` hierarchy + `gen_ai.*` + `agenteval.*`
attributes. The JSONL format itself is governed by
[`docs/contracts/listener-integration.md`](listener-integration.md);
this doc covers the *ingestion + visualization* side.

## Span hierarchy

agenteval emits 3 canonical OTel GenAI span types per the
`gen_ai.*` semantic conventions:

```
invoke_agent (root span, per agent.run() call)
├── chat (LLM round-trip; per provider.chat() call)
│   ├── chat (multi-turn conversation; subsequent turns)
│   └── execute_tool (per tool-call, child of the issuing chat)
│       └── (tool-internal spans if the tool emits any)
└── execute_tool (sibling tool-calls from the same agent step)
```

Each span carries:

| Attribute | Source | Example value |
| --- | --- | --- |
| `agenteval.test_id` | RF `full_name` per Story 5.1 listener | `MyTests.Test Echo Roundtrip` |
| `agenteval.tier` | `@tier(N)` decorator (Story 1b.2 H_R11) | `1` / `2` / `3` |
| `agenteval.tool.success` | Per-tool-call success flag | `True` / `False` |
| `agenteval.tool.duration_ms` | Per-tool-call wall-clock duration | `42.5` |
| `agenteval.tool.source` | `"adapter"` or `"hosted_mcp"` per FR35 | `"hosted_mcp"` |
| `gen_ai.system` | Provider identifier | `"anthropic"` / `"openai"` / `"mcp"` |
| `gen_ai.request.model` | Model identifier | `"claude-sonnet-4-6"` |
| `gen_ai.usage.input_tokens` | LLM prompt tokens | `3421` |
| `gen_ai.usage.output_tokens` | LLM completion tokens | `512` |
| `gen_ai.tool.name` | Tool name on `execute_tool` spans | `"echo"` |

All attribute names route through
[`src/AgentEval/telemetry/semconv.py`](../../src/AgentEval/telemetry/semconv.py)
per NFR-COMPAT-06 (single-file-update facade for attribute churn).

## JSONL artifact format

When `AGENTEVAL_TRACE_BACKEND=jsonl` is set (or `agenteval.yaml::trace_backend: jsonl`),
the listener emits one JSONL file per test at:

```
${OUTPUTDIR}/agenteval/trace__<suite_full_name>__<test_full_name>.jsonl
```

Each line is one JSON-serialized OTel span dict with the standard
`SpanData` fields (`name`, `context`, `parent`, `start_time`, `end_time`,
`attributes`, `events`, `links`).

## Loading into Jaeger

The canonical Phase-1 viewer. Jaeger does NOT natively ingest agenteval's
JSONL format — but the standalone `jaeger-all-in-one` Docker container
accepts OTLP HTTP traces. Pipe the JSONL through `otel-cli`:

```bash
# Spin up Jaeger.
docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest

# Replay the JSONL trace.
cat ${OUTPUTDIR}/agenteval/trace__MyTests__Test_Echo.jsonl | \
  otel-cli span replay - --endpoint http://localhost:4318/v1/traces

# Open the Jaeger UI.
open http://localhost:16686/search?service=robotframework-agenteval
```

The `invoke_agent → chat → execute_tool` hierarchy renders as the
trace-detail-view's flame graph. Each `execute_tool` span's `agenteval.tool.*`
attributes appear in the right-hand attribute panel.

**Phase-1 limitation:** `otel-cli span replay` is a community tool, not
distributed with agenteval. Future Phase-1.5 work may ship an
`agenteval trace replay` CLI subcommand wrapping the conversion + replay
step (DF-8b.3-S1 / C64 carry-over candidate).

## Loading into Honeycomb

Honeycomb accepts OTLP JSON via `https://api.honeycomb.io/v1/traces`. Pipe
the JSONL through `curl`:

```bash
cat trace__MyTests__Test_Echo.jsonl | \
  jq -s '{resourceSpans: [{scopeSpans: [{spans: .}]}]}' | \
  curl -X POST https://api.honeycomb.io/v1/traces \
    -H "x-honeycomb-team: $HONEYCOMB_API_KEY" \
    -H "Content-Type: application/json" \
    -d @-
```

The trace appears in Honeycomb's "robotframework-agenteval" dataset (the
agenteval `OTelResource.service.name`). Use Honeycomb's BubbleUp on
`agenteval.tier` to see Tier-3 fan-out latency distributions.

## Loading into Tempo

Tempo (Grafana) accepts OTLP via the Tempo Distributor's gRPC / HTTP
endpoint:

```bash
otel-cli span replay trace__MyTests__Test_Echo.jsonl \
  --endpoint http://tempo-distributor:4318/v1/traces
```

The trace ID (canonical RF `full_name`) lets you cross-link from RF's
`output.xml` `<tag>trace_id:...</tag>` (Story 8a.2 FR51) directly to the
Tempo trace-detail view.

## ASCII span-hierarchy preview

For pipeline runs that don't want to round-trip through a viewer, the
JSONL itself can be rendered as ASCII via stdlib tools:

```bash
jq -r '"\(.name) (\(.attributes."agenteval.tier" // "?")) \(.attributes."gen_ai.request.model" // "")"' \
  trace__MyTests__Test_Echo.jsonl
```

Sample output:

```
invoke_agent (3) anthropic/claude-sonnet-4-6
chat (3) anthropic/claude-sonnet-4-6
execute_tool (3) echo
chat (3) anthropic/claude-sonnet-4-6
```

## Cross-references

- [`listener-integration.md`](listener-integration.md) — JSONL backend contract + Listener v3 lifecycle.
- [`junit-xml-enrichment.md`](junit-xml-enrichment.md) — JUnit XML side of the trace_id linkage.
- [`mcp-coverage-detection.md`](mcp-coverage-detection.md) — `agenteval.tool.source` literal enum.
- ADR-007: `mcp_coverage` enum + `IncompleteTraceError` semantics.
- Story 5.1 — OTel listener + span generation + JSONL backend.
- Story 5.4 — `DegradedTraceWarning` (surfaces in `output.xml` + xunit `<system-err>`).
- Recipe #8 (CI integration) — JUnit XML enrichment + exit codes that pair with the trace data.

## Stability surface

Per FR64. The 3 canonical span names (`invoke_agent`, `chat`, `execute_tool`)
+ the `agenteval.*` attribute namespace (governed by `semconv.py`) are
`stable` from Phase-1 onward. Changes require ADR amendment per ADR-014.
The `gen_ai.*` attribute namespace tracks the upstream OTel GenAI
semantic-conventions spec (NFR-COMPAT-06 single-file-update facade).
