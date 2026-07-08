# Recipe #5: Replacing custom Python tests with `.robot` suites

**Use case:** you maintain an MCP server, skill, or sub-agent library and want
to retire bespoke Python conformance tests in favor of `.robot` suites built
from agenteval keywords.

## TL;DR

Most custom agent-testing Python falls into a few categories, and each maps to
an agenteval keyword:

| What the Python test does | agenteval keyword |
| --- | --- |
| Validate a skill / MCP config file | `Skill.Get Frontmatter`, `MCP.Get Server Config` |
| Round-trip an MCP tool call | `MCP.Start Server`, `MCP.Call Tool` |
| Run a single-shot prompt | `Send Prompt` |
| Measure Pass@k / cohort discoverability | `Stat.Get Pass At K`, `MCP.Get Tool Discoverability` |

## Step-by-step

### 1. Inventory the existing Python tests

List the library's `tests/test_*.py` files and categorize each test as
static-inspection, runtime, agent-call, or statistical using the table above.

### 2. Port a runtime test

A typical Python MCP round-trip test:

```python
@pytest.mark.asyncio
async def test_echo_tool_roundtrip(mcp_session):
    """Verify that the echo tool returns the input message."""
    result = await mcp_session.call_tool("echo_back", {"text": "hello"})
    assert result.isError is False
    assert "hello" in str(result.content)
```

Ports to a `.robot` suite:

```robotframework
*** Settings ***
Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
Suite Setup       Start Echo Server
Suite Teardown    Stop Echo Server

*** Variables ***
${HANDLE}    ${NONE}

*** Test Cases ***
Echo Tool Roundtrips A Message
    [Documentation]    Calls the echo_back tool and asserts the response.
    ${result}=    MCP.Call Tool    ${HANDLE}    echo_back    text=hello
    Should Be Equal    ${result.is_error}    ${FALSE}
    Should Contain    ${result.content}[0][text]    hello

*** Keywords ***
Start Echo Server
    ${handle}=    MCP.Start Server    bundled-echo    stdio    python
    ...    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
    Set Suite Variable    ${HANDLE}

Stop Echo Server
    Run Keyword If    $HANDLE is not None    MCP.Stop Server    ${HANDLE}
```

### 3. Port a discoverability test

A cohort-discoverability test ports to `Skill.Get Discoverability`:

```robotframework
*** Settings ***
Library    AgentEval
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill

*** Test Cases ***
Skill Cohort Discoverability
    ${result}=    Skill.Get Discoverability
    ...    skill=${CURDIR}/skills/example-skill.md
    ...    tasks=${CURDIR}/discoverability/example-tasks.yaml
    ...    adapter=generic    provider=mock    trials_per_task=1    max_cost_usd=1.0
    Should Be True    ${result.summary.activation_accuracy} >= 0.0
```

### 4. Run the ported suite

```bash
robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
```

Compare against the upstream library's pytest run — both should be green and
functionally equivalent.

## Document what the port does and does not verify

When your suite runs against deterministic fixtures or the mock provider,
write down what it verifies (task parsing, per-task aggregation, summary
statistics) and what it does not (live-LLM answer quality, multi-turn
behavior). A short "this suite verifies X, not Y" note at the top of the file
keeps future readers honest.

## Cross-references

- Recipe #3 (Tool Discoverability cohort) — the cohort-evidence pattern.
- Recipe #7 (First MCP server test) — Tier-1 static inspection of `.mcp.json`.
