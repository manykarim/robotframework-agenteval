# Recipe #8: CI integration with enriched xunit + JUnit XML + exit codes

**Persona:** Priya / CI operator — any team running agenteval suites in GitHub Actions, GitLab CI, Jenkins, Allure.
**FR coverage:** FR49 (JUnit XML enrichment), FR50 (sysexits exit-code mapping), FR51 (trace_id in output.xml), FR64 (Stability Surface).

## TL;DR

```yaml
# .github/workflows/ci.yml
jobs:
  agenteval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: |
          uv run robot \
            --listener AgentEval.telemetry.listener.Listener \
            --xunit junit.xml \
            tests/
      - uses: dorny/test-reporter@v1
        if: always()
        with:
          name: agenteval
          path: junit.xml
          reporter: java-junit
```

That's it — the `--xunit junit.xml` output is automatically enriched with
9 `agenteval.*` properties per testcase, consumed natively by GitHub
Actions' test-reporter, Jenkins JUnit plugin, GitLab CI, and Allure.

## What's in the enriched JUnit XML?

Per `docs/contracts/junit-xml-enrichment.md`, each `<testcase>` carries:

```xml
<testcase classname="Suite" name="Test Name" time="12.4">
    <properties>
        <property name="agenteval.adapter" value="generic"/>
        <property name="agenteval.completeness" value="complete"/>
        <property name="agenteval.cost_usd" value="0.0247"/>
        <property name="agenteval.latency_seconds" value="2.800"/>
        <property name="agenteval.mcp_coverage" value="hosted_in_process"/>
        <property name="agenteval.model" value="anthropic/claude-sonnet-4-6"/>
        <property name="agenteval.tier_breakdown" value='{"1": 2, "3": 5}'/>
        <property name="agenteval.total_tokens" value="3421"/>
        <property name="agenteval.trace_id" value="01HRMK..."/>
    </properties>
    <system-out><![CDATA[ evidence block (Story 5.3) ]]></system-out>
    <system-err><![CDATA[ DegradedTraceWarning content (Story 5.4) ]]></system-err>
</testcase>
```

CI tools that consume JUnit XML expose the `<properties>` block natively
— no custom-tool integration needed. **GitHub Actions test-reporter +
Allure both render properties as a key-value table in the test detail
view.**

## Exit codes (FR50)

The agenteval CLI exit-code mapping uses sysexits.h-style per-leaf codes:

| Failure scenario | Exit code | Constant |
| --- | --- | --- |
| Cost budget exceeded | 66 | `COST_EXCEEDED` (epics.md L1660 pinned) |
| Runtime budget exceeded | 75 | `RUNTIME_BUDGET_EXCEEDED` (EX_TEMPFAIL) |
| Polling-ban violation | 65 | `POLLING_DISALLOWED` (EX_DATAERR) |
| MCP version mismatch | 68 | `UNSUPPORTED_MCP_VERSION` |
| Trace data incomplete | 67 | `INCOMPLETE_TRACE` |
| Adapter discovery / config error | 78 | `EX_CONFIG` |
| Sandbox / safety violation | 77 | `EX_NOPERM` |
| Generic agenteval failure | 70 | `EX_SOFTWARE` (fallback) |

Pipe these through your CI's failure-categorization system:

```yaml
- name: Run agenteval
  run: |
    set +e
    uv run robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
    exit_code=$?
    if [ "$exit_code" = "66" ]; then
      echo "::error::Cost budget exceeded — review test fan-out + max_cost_usd"
    elif [ "$exit_code" = "67" ]; then
      echo "::error::Incomplete trace — check mcp_coverage configuration"
    fi
    exit $exit_code
```

See `docs/contracts/error-class-hierarchy.md` L66-L101 for the full per-leaf
table (21 leaves as of Story 8a.1 close).

## trace_id linkage (FR51)

Each test's `<test>` element in `output.xml` carries a
`<tag>trace_id:<full_name></tag>` for linking RF reports to JSONL trace
artifacts:

```bash
xmlstarlet sel -t -v "//test[@name='My Test']/tag" output.xml
# → trace_id:My.Suite.My Test
```

The `trace_id` value is the canonical RF `full_name` — also the filename
of the JSONL trace at `${OUTPUTDIR}/agenteval/trace__<suite>__<test>.jsonl`.
Pipe both into your observability backend (Jaeger / Honeycomb / Tempo)
for cross-reference. See Recipe #N (OTel trace visual doc — coming with
Story 8b.3 OTel doc) for the JSONL → Jaeger ingestion path.

## OTLP trace export (Phase 2 — `[otlp]` extra)

Shipping with Story 13.2 (Epic 13). The `[otlp]` optional extra wires the
canonical OpenTelemetry OTLP exporter so spans flow directly into Jaeger /
Honeycomb / Tempo / Grafana without the manual `otel-cli span replay`
round-trip step documented in `docs/contracts/otel-trace-visual.md`.

**Install the extra:**

```bash
uv pip install robotframework-agenteval[otlp]
```

**Configure via RF Library settings (HTTP to local Jaeger all-in-one):**

```robotframework
*** Settings ***
Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
```

**Configure via RF Library settings (gRPC to Grafana Tempo):**

```robotframework
*** Settings ***
Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
```

**Configure via env vars (Honeycomb HTTPS in CI):**

```bash
export AGENTEVAL_TRACE_BACKEND=otlp
export AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
uv run robot --include smoke tests/
```

URL-scheme dispatch:

- `http://` / `https://` → OTLP HTTP/protobuf exporter (default port 4318,
  `/v1/traces` path).
- `grpc://` / `grpcs://` → OTLP gRPC exporter (default port 4317). The
  `grpc://` prefix triggers `insecure=True` (plaintext); `grpcs://`
  triggers TLS.
- Default (`otlp_endpoint` unset): `http://localhost:4318/v1/traces`.
- Any other scheme: `ValueError` at Library construction; the Listener
  gracefully degrades to the `memory` backend with a `DegradedTraceWarning`.

**Phase 2 Status:** dual-export design — spans continue to populate the
in-memory store (so `Metric.*` keywords still work) AND ship out to the
configured OTLP endpoint via a `BatchSpanProcessor`. There is no
OTLP-only mode that suppresses in-memory recording. The legacy
`otel-cli span replay` JSONL-replay path (see
`docs/contracts/otel-trace-visual.md`) remains useful for ad-hoc trace
inspection without changing the `trace_backend` config.

See `docs/contracts/stability-surface.md` for the `provisional`-labeled
surface entries + Phase-2.5 carry-overs (DF-13.2-S1/S2/S3).

## Conformance report (FR57)

For a separate machine-readable conformance pass alongside the RF run:

```bash
python -m AgentEval.conformance --adapter <name> --output-dir conformance-report/
```

Emits `conformance-report.json` + `conformance-report.md` per
`docs/contracts/conformance-fixture-format.md` "Conformance Report
Schema" section.

## Allure-specific tips

Allure's JUnit XML reader auto-extracts `<properties>` and renders them in
the test detail view's metadata tab. No additional `--alluredir` flag
needed beyond the standard `allure generate junit.xml -o allure-report/`.

## Cross-references

- `docs/contracts/junit-xml-enrichment.md` — full property table + value semantics.
- `docs/contracts/error-class-hierarchy.md` L66-L101 — per-leaf exit-code mapping.
- Recipe #1 (5-min path) — the local-dev invocation that produces the same enriched output.
- Story 8a.1 — JUnit XML enrichment via Listener `xunit_file` hook.
- Story 8a.2 — `trace_id` tag + conformance CLI.
