# JUnit XML Enrichment

**Status:** Phase-1 stable (Story 8a.1 closed 2026-05-25).
**Owning epic:** Epic 8a Story 8a.1
**Related ADRs:** ADR-014 (Error-Class Hierarchy — `error_code` class attribute drives the FR50 exit code mapping)
**Related FRs:** FR49 (JUnit XML emission), FR50 (Exit-code mapping — sysexits-style per-leaf ratified 2026-05-18), FR64 (Stability Surface)

## Purpose

Governs the **enrichment of RF's standard JUnit-XML output** (`xunit.xml`, written when the user passes `--xunit junit.xml`) with agenteval-specific structured metadata. RF's default xUnit output is minimal (per-testcase `name`, `classname`, `time`, `failure`, `skipped`); agenteval injects per-testcase `<properties>` + `<system-out>` evidence block + `<system-err>` warning content via the Story 5.1 Regular Listener's `xunit_file(path)` hook.

This lets mainstream CI tooling that already consumes JUnit XML (GitHub Actions test-reporter, GitLab CI, Jenkins JUnit plugin, Allure) surface AgentEval cost, coverage, trace-id, and agent telemetry alongside standard pass/fail — without parallel CI-tool integrations.

## Required listener invocation

**The user MUST pass `--listener AgentEval.telemetry.listener` for xunit enrichment to function.** Without the listener:

- RF still writes the standard `--xunit junit.xml` file (no error).
- The `xunit_file(path)` hook never fires, so no `<properties>` are injected.
- The file looks like a stock-RF xunit output (no agenteval enrichment).

Canonical invocation:

```bash
robot --listener AgentEval.telemetry.listener --xunit junit.xml tests/
```

`agenteval init` (Story 8b.1) generates a sample command-line that includes the flag. Smoke-test the listener wiring during local development with `robot --dryrun --listener AgentEval.telemetry.listener --xunit /tmp/junit.xml tests/<dir>/`.

## Property table (9 ratified `agenteval.*` properties)

All property names are sourced from `src/AgentEval/telemetry/semconv.py` (`XUNIT_PROP_*` constants) per NFR-COMPAT-06's single-facade rule. Alphabetical for diff stability.

| Property name | Source on the listener | Value type | Empty/missing fallback |
| --- | --- | --- | --- |
| `agenteval.adapter` | `_completed_run_metadata[test_id]["adapter"]` (via `record_active_run_metadata(adapter_name=...)`) | string | property omitted |
| `agenteval.completeness` | `_completed_run_metadata[test_id]["completeness"]` (Literal `"complete"` / `"truncated"` / `"partial"` per `types.py` L314) | string | property omitted |
| `agenteval.cost_usd` | `_completed_run_metadata[test_id]["cost_usd"]` | string (decimal, 4-place precision, e.g., `"0.0247"`) | property omitted |
| `agenteval.latency_seconds` | `trace_store.get_latency(test_id)` snapshot at `end_test` | string (decimal, 3-place precision, e.g., `"2.800"`) | property omitted if no spans |
| `agenteval.mcp_coverage` | `_completed_run_metadata[test_id]["mcp_coverage"]` (per ADR-016) | string | property omitted |
| `agenteval.model` | `_completed_run_metadata[test_id]["model"]` | string | property omitted |
| `agenteval.tier_breakdown` | `trace_store.get_run_manifest(test_id).agenteval_tier_breakdown` | JSON string (e.g., `'{"1": 2, "3": 5}'` — keys sorted) | property omitted if no spans |
| `agenteval.total_tokens` | `trace_store.get_usage(test_id).total_tokens` | string (integer) | property omitted if no spans |
| `agenteval.trace_id` | `trace_store.get_run_manifest(test_id).test_id` (canonical) | string | property omitted if no spans |

**Value-type convention:** all `<property value="...">` attribute values are strings per the JUnit XML schema. Numeric properties (`cost_usd`, `latency_seconds`, `total_tokens`) carry their string-formatted decimal/integer representation.

## Example before/after

**Before enrichment** (RF's minimal output):

```xml
<testcase classname="Sample" name="Test Alpha" time="12.4"/>
```

**After enrichment**:

```xml
<testcase classname="Sample" name="Test Alpha" time="12.4">
    <properties>
        <property name="agenteval.adapter" value="generic"/>
        <property name="agenteval.completeness" value="complete"/>
        <property name="agenteval.cost_usd" value="0.0247"/>
        <property name="agenteval.latency_seconds" value="2.800"/>
        <property name="agenteval.mcp_coverage" value="hosted_in_process"/>
        <property name="agenteval.model" value="anthropic/claude-sonnet-4-6"/>
        <property name="agenteval.tier_breakdown" value='{"1": 2, "3": 5}'/>
        <property name="agenteval.total_tokens" value="3421"/>
        <property name="agenteval.trace_id" value="01HRMK0123456789ABCDEFGHJK"/>
    </properties>
    <system-out>evidence: cost=$0.0247 tokens=3421</system-out>
    <system-err>[DegradedTraceWarning] missing longname</system-err>
</testcase>
```

## test_id derivation

The xunit `<testcase classname="..." name="...">` pair maps to RF Listener v3's `data.full_name` via:

```python
test_id = f"{classname}.{name}"
```

This works for both flat and nested RF suites (RF nested suites use dotted `classname`).

## Idempotency contract

Re-running enrichment on an already-enriched file is **safe**:
- `<property>` elements with `name=` starting with `agenteval.` are removed first, then the new set is appended.
- Non-`agenteval.*` properties (user-added or CI-tool-added) are preserved.
- `<system-out>` and `<system-err>` children are replaced in place (not duplicated).

Byte-for-byte identical re-enrichment with identical metadata produces a byte-identical file.

## Failure-mode contract

Any exception during parse / inject / write is **logged at WARN** level and the function returns `False` **without raising**. The original file is preserved via atomic write (`tree.write(path.with_suffix(path.suffix + ".tmp"))` → `os.replace(<tmp>, path)`).

Symmetric to the Story 5.3 `RunManifestEmitter` warning-and-return-None pattern. Test outcomes are never masked by enrichment failures.

## FR50 sysexits-style exit-code mapping

Cross-reference: `docs/contracts/error-class-hierarchy.md` L73-L94 (per-leaf table).

The `agenteval` CLI's exit-code translation layer consults the lookup table at `src/AgentEval/cli.py::_ERROR_EXIT_CODES` (keyed by leaf `error_code` string). Unknown / None / empty `error_code` → `EXIT_CODE_FALLBACK` (70 EX_SOFTWARE).

Pinned codes (epics.md L1660):

- `POLLING_DISALLOWED` → 65 (EX_DATAERR)
- `COST_EXCEEDED` → 66
- `INCOMPLETE_TRACE` → 67
- `UNSUPPORTED_MCP_VERSION` → 68

Phase-1.5: a per-leaf `exit_code: ClassVar[int]` attribute will replace the string-keyed lookup (tracked at DF-8a.1-S1 / C62). The lookup-table approach is functionally equivalent for FR50 and isolates the change to one new file (path-of-least-amendment decision per Story 8a.1 D-2).

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels:

- **Adding new `agenteval.*` enrichment property names** is minor-version-safe (additive — non-agenteval consumers ignore unknown properties).
- **Removing a property** or **changing a property's value semantics** is a breaking change requiring major-version bump + a documented migration path.
- **FR50 exit-code mapping** is `stable` from Phase-1 onward — changes require ADR amendment + CI-consumer migration notice (consumers may pin specific exit codes in pipelines).

## References

- ADR-014: Error-Class Hierarchy (the `error_code` class attribute that drives FR50)
- FR49 (PRD): JUnit XML emission
- FR50 (PRD): Exit-code mapping (sysexits-style per-leaf)
- FR64 (PRD): Stability Surface
- `listener-integration.md`: the `xunit_file(path)` hook contract
- `error-class-hierarchy.md`: per-leaf `error_code` → exit code authoritative table
- `src/AgentEval/telemetry/semconv.py`: `XUNIT_PROP_*` constants (single-facade rule per NFR-COMPAT-06)
- `src/AgentEval/telemetry/_xunit_enrichment.py`: implementation
- `src/AgentEval/cli.py`: `error_code_to_exit_code` + `_ERROR_EXIT_CODES` lookup
- Story 5.1 (commit `95d96b2`): Regular Listener v3 entry point
- Story 5.3 (commit `fff1b6c`): `record_active_run_metadata` adapter callback
- Story 5.4 (commit `3fdce01`): per-test `WarningRecord` buffer
- Story 8a.1 (commit pending): contract authoring + Listener enrichment
