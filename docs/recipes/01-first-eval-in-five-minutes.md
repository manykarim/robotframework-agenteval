# Recipe #1: First eval in 5 minutes

**Persona:** any new agenteval user.
**Time budget:** <5 minutes (NFR-UX-01).
**Prerequisites:** `uv` ≥0.4 (or `pip` ≥24); Python ≥3.11.

## TL;DR

```bash
uv add robotframework-agenteval
agenteval init
robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
```

That's it — the third command runs three example tests (skill validation,
MCP runtime, agent run) against the Mock provider (no API keys needed) and
emits a JUnit-XML report enriched with `agenteval.*` properties.

## Step-by-step

### 1. Install

```bash
uv add robotframework-agenteval
```

### 2. Scaffold the example project

```bash
agenteval init
```

This creates:

```
tests/
├── example_skill_validation.robot
├── example_mcp_runtime.robot
├── example_agent_run.robot
└── fixtures/
    ├── example-skill.md
    ├── .mcp.json
    └── scenario.yaml
agenteval.yaml
README.md
```

To scaffold into a specific directory: `agenteval init --output-dir my-project/`.
To overwrite existing files: pass `--force`.

### 3. Run the tests

```bash
robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
```

Expected output:

```
==============================================================================
Tests
==============================================================================
Tests.Example Skill Validation                                              | PASS |
Tests.Example Mcp Runtime                                                   | PASS |
Tests.Example Agent Run                                                     | PASS |
------------------------------------------------------------------------------
3 tests, 3 passed, 0 failed
==============================================================================
```

### 4. Inspect the enriched JUnit XML

```bash
xmlstarlet sel -t -v "//testcase[@name='Mock Provider Returns A Response']/properties/property[@name='agenteval.adapter']/@value" junit.xml
# → generic

xmlstarlet sel -t -v "//testcase[@name='Mock Provider Returns A Response']/properties/property[@name='agenteval.completeness']/@value" junit.xml
# → complete
```

The 9 ratified `agenteval.*` properties (`adapter`, `completeness`, `cost_usd`,
`latency_seconds`, `mcp_coverage`, `model`, `tier_breakdown`, `total_tokens`,
`trace_id`) populate when an agent keyword fires. See
[`docs/contracts/junit-xml-enrichment.md`](../contracts/junit-xml-enrichment.md)
for the full property table + value semantics.

## Why the `Listener.Listener` class path?

**The listener flag is REQUIRED.** Use the explicit `Module.Class` form:

```
--listener AgentEval.telemetry.listener.Listener
```

The shorter `AgentEval.telemetry.listener` (module-path-only) form is accepted
by RF without error but the listener's hooks (`start_suite`, `start_test`,
`xunit_file`, `end_test`) do **not** fire on RF 7.x — RF takes the
module-as-listener resolution path which expects a top-level
`ROBOT_LISTENER_API_VERSION` attribute (not present at module scope).

This empirical resolution was caught during Story 8a.2 dev (2026-05-25) when
the trace_id-tag injection turned out not to surface in `output.xml`.

## What the listener does

- **Captures OTel spans** per test for cost / latency / token usage / tier
  breakdown projections (Story 1b.2 / 5.1 / 5.3).
- **Records the `trace_id` tag** on every test in `output.xml` (FR51) so CI
  log spelunking can link RF reports to JSONL trace artifacts (Story 8a.2).
- **Enriches the `--xunit junit.xml`** output with `agenteval.*` properties +
  `<system-out>` evidence + `<system-err>` warnings (Story 8a.1).
- **Cleans up per-test MCP servers** per ADR-009 (Story 5.2).

Without `--listener`, the library still works at the keyword level — but the
xunit enrichment + output.xml trace_id linkage + JSONL trace backend are all
inactive.

## Next steps

- **Pass@k over polling:** see Recipe #2 (Story 8b.3).
- **Tool Discoverability cohort:** see Recipe #3 (Story 8b.3).
- **Skill author stacked validation:** see Recipe #4 (Story 7.3 stub + Story 8b.3 polish).
- **Custom adapter authoring:** see Recipe #6 (Story 8b.3) + run `agenteval new-adapter` (Story 8b.2).
- **CI integration:** see Recipe #8 (Story 8b.3) for GitHub Actions / GitLab / Jenkins / Allure examples.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `agenteval init` exits with "file already exists" warnings | The target directory has prior files. | Re-run with `--force` to overwrite, or pick a fresh directory. |
| `output.xml` has no `<tag>trace_id:...</tag>` | Used the module-path-only listener form. | Switch to `AgentEval.telemetry.listener.Listener` (explicit class path). |
| `junit.xml` has no `agenteval.*` properties | Listener not loaded OR no agent keywords fired (only built-in `Log` keywords). | Verify the listener flag; check that at least one test calls an agent keyword (`Send Prompt`, `MCP.Call Tool`, etc.). |
| Mock provider raises `AdapterDiscoveryError` | `agenteval` not installed in the active env. | `uv add robotframework-agenteval` or `pip install robotframework-agenteval`. |
