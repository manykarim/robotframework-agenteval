# Recipe #5: Dogfood — replacing custom Python tests with `.robot` suites

**Persona:** Raj (Library Maintainer) — anyone who maintains an MCP server / skill / sub-agent library and wants to retire bespoke Python conformance tests in favor of `.robot` suites using `agenteval` keywords.

**FR coverage:** AC-DOGFOOD-01 (interleaved-dogfood ratification per `feedback_interleaved_dogfood_load_bearing` Epic 3 retro).

## TL;DR

The agenteval interleaved-dogfood pattern: every epic ships a "port" story
that rewrites a real downstream library's Python conformance tests as
`.robot` suites — proving the keyword surface is production-grade.

Three reference ports landed in Epics 3, 5, 6, 7:

- **Story 3.3** — `rf-mcp` MCP-surface tests → `tests/dogfood/rf-mcp/test_mcp_surface_parity.robot` (15 tests).
- **Story 5.5** — `rf-mcp` trace-observability tests → `tests/dogfood/rf-mcp/test_trace_observability_parity.robot` (8 tests).
- **Story 6.4** — `robotframework-agentskills` metrics tests → `tests/dogfood/agentskills/test_*.robot` (36 tests).
- **Story 7.4** — `robotframework-agentskills` skill-discoverability → `tests/dogfood/agentskills/test_skill_discoverability.robot` (4 tests).

## Step-by-step

### 1. Pick a target library

Choose a downstream library that uses MCP / skills / sub-agents. Reference
targets: `rf-mcp`, `robotframework-agentskills` (the project's two
canonical dogfood targets per the Epic 0 strategy).

### 2. Inventory the existing Python tests

List the library's `tests/test_*.py` files + categorize each test:

- **Static-inspection tests** (frontmatter validation, MCP config schema):
  → port to Epic 2 keywords (`Skill.Get Frontmatter`, `MCP.Get Server Config`).
- **Runtime tests** (MCP tool roundtrip): → port to Epic 3 keywords
  (`MCP.Start Server`, `MCP.Call Tool`).
- **Agent-call tests** (single-shot prompts): → port to Epic 4 keywords
  (`Send Prompt`).
- **Statistical tests** (Pass@k, cohort discoverability): → port to Epic 6
  (`Stat.*`) + Epic 4.4 (`MCP.Get Tool Discoverability`).

### 3. Write the parity checklist

`tests/dogfood/<target>/parity-checklist.md` documents:

```markdown
**VALIDATION-CEILING:** this dogfood verifies <X, Y, Z>; it does NOT verify
<live LLM provider quality, multi-turn behavior, ...>.

| Original Python test | `.robot` port | Status |
| --- | --- | --- |
| `test_echo_tool_roundtrip` | `test_mcp_surface_parity.robot::Echo Tool Roundtrips` | ✓ |
| `test_skill_frontmatter_valid` | `test_skill_validation.robot::Frontmatter Is Valid` | ✓ |
| ... | ... | deferred / TODO |
```

The `VALIDATION-CEILING:` line is a ratified norm (Epic 7 retro
`feedback_dogfood_validation_ceiling`).

### 4. Run the parity suite

```bash
robot --listener AgentEval.telemetry.listener.Listener \
      --xunit junit.xml \
      tests/dogfood/<target>/
```

Compare against the upstream library's pytest run — both should be green
+ functionally equivalent.

### 5. Catalog dogfood-findings

Per the Epic 5 retro `feedback_dogfood_finding_severity_differentiation`
norm, any finding from the port is classified as:

- **(a) doc-fix / contract clarification** — no catalog entry.
- **(b) same-PR code-fix** — close in the dogfood-port PR.
- **(c) Phase-1.5 carry-over** — add to `docs/phase-1-5-carry-overs.md`.
- **(d) Epic 9+ Phase-2 work** — defer with explicit rationale.

## Why interleave?

Per `feedback_interleaved_dogfood_load_bearing` (Epic 3 retro ratification):
real downstream libraries are the highest-yield bug-finding surface.
Story 3.3's dogfood caught DOGFOOD-FINDING-1 (stdio `errlog=sys.__stderr__`
crash) that Story 3.1's own 4-reviewer code review missed.

## Worked example — rf-mcp MCP-surface port (Story 3.3 / 9.1)

**Original Python test** (excerpted from rf-mcp's `tests/test_mcp_simple.py`):

```python
@pytest.mark.asyncio
async def test_echo_tool_roundtrip(mcp_session):
    """Verify that the `echo` tool returns the input message."""
    result = await mcp_session.call_tool("echo", {"message": "hello"})
    assert result.isError is False
    assert "hello" in str(result.content)
```

**Ported `.robot` equivalent** (`tests/dogfood/rf-mcp/test_mcp_surface_parity.robot`):

```robotframework
*** Settings ***
Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP

*** Test Cases ***
Echo Tool Roundtrips A Message
    [Documentation]    Calls the `echo` tool + asserts the response.
    ${result}=    MCP.Call Tool    ${HANDLE}    echo    message=hello
    Should Be True    ${result.success}
    Should Contain    ${result.text_content}    hello
```

**Dogfood-finding surfaced by the port** (DOGFOOD-FINDING-1, HIGH severity, fixed in Story 3.3 — see `tests/dogfood/rf-mcp/parity-checklist-rf-mcp-mcp-surface.md` L58):

The MCP SDK's `stdio_client(server, errlog=sys.stderr)` default crashes under `robot` execution because RF's listener replaces `sys.stderr` with a non-fd capture buffer + the SDK calls `.fileno()` on the errlog handle. Pre-fix: 11 of 15 parity tests failed at startup. Fix: pass `errlog=sys.__stderr__` (the un-wrapped real stderr that Python stashes at interpreter startup) at `src/AgentEval/mcp/transport.py::open_stdio_session`. **This bug existed since Story 3.1 ship + escaped Story 3.1's 4-reviewer cross-LLM code review** because the unit tests used the `in_memory` transport (which doesn't call `stdio_client`). The interleaved-dogfood port was the empirical surface that exposed it.

**Story 9.1 closure (2026-05-25):** the gap-analysis synthesis at `tests/dogfood/rf-mcp/parity-checklist-rf-mcp-FULL.md` documents the full 58-test classification (17 ported / 4 stays-custom / 38 Phase-2-batch). The agenteval-side cross-repo CI wiring ships in `.github/workflows/dogfood-integration.yml::parity-suite-smoke` job.

## Cross-references

- `feedback_interleaved_dogfood_load_bearing.md` — Epic 3 retro norm.
- `feedback_dogfood_validation_ceiling.md` — Epic 7 retro norm.
- `feedback_dogfood_finding_severity_differentiation.md` (Epic 5 retro #4).
- `tests/dogfood/rf-mcp/parity-checklist*.md` — reference parity checklists.
- `tests/dogfood/rf-mcp/parity-checklist-rf-mcp-FULL.md` (Story 9.1) — synthesis + closure status.
