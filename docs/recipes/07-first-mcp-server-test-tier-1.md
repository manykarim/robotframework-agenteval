# Recipe #7: First MCP server test (Tier-1 static inspection)

**Persona:** anyone shipping an MCP server who wants Tier-1 (deterministic, no LLM calls) validation of their `.mcp.json` config + tool schemas.
**FR coverage:** FR5 (MCP config), FR6 (MCP tool schema validation), FR7 (transport literals).

## TL;DR

```robotframework
*** Settings ***
Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP

*** Test Cases ***
Echo Server Config Is Valid
    ${config}=    MCP.Get Server Config    ${CURDIR}/fixtures/.mcp.json    bundled-echo
    Should Be Equal As Strings    ${config}[command]    python
    Should Be Equal As Strings    ${config}[transport]    stdio

Echo Tool Schema Is Valid
    ${schema}=    MCP.Get Tool Schema    ${CURDIR}/fixtures/.mcp.json    bundled-echo    echo
    Should Be True    ${schema} is not None
```

## Why Tier-1 first?

Tier-1 keywords are **deterministic** — they parse files + return
structured data without any LLM call. Use them in your CI smoke suite to
catch config drift before any Tier-2 / Tier-3 runtime call:

| Keyword | Purpose |
| --- | --- |
| `MCP.Get Server Config` | Read + validate a server entry from `.mcp.json`. |
| `MCP.Get Tool Schema` | Read + validate a tool's JSON Schema. |
| `MCP.Validate Tool Schema` | Strict-validation check (raises `InvalidMCPToolSchemaError` on failure). |

## Step-by-step

### 1. Place your `.mcp.json` config

```json
{
  "mcpServers": {
    "bundled-echo": {
      "command": "python",
      "args": ["-m", "AgentEval.mcp.bundled.echo"],
      "transport": "stdio",
      "tools": {
        "echo": {
          "type": "object",
          "properties": {
            "message": {"type": "string"}
          },
          "required": ["message"]
        }
      }
    }
  }
}
```

### 2. Import the MCP library with a prefix

```robotframework
Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
```

**Why `WITH NAME MCP`?** `MCPLibrary` is excluded from the top-level
`AgentEval` DynamicCore composition (Story 2.2 — name-collision avoidance
between `MCPLibrary.Get Frontmatter` and `SubagentsLibrary.Get Frontmatter`).
The ratified user pattern is `Library X WITH NAME prefix`.

### 3. Read + assert the config

```robotframework
${config}=    MCP.Get Server Config    ${CURDIR}/fixtures/.mcp.json    bundled-echo
Should Be Equal As Strings    ${config}[command]    python
```

If the config is malformed (missing required field, invalid transport,
unknown JSON Pointer), `InvalidMCPServerConfigError` raises with the
FR59-format diagnostic message.

### 4. Read + assert the tool schema

```robotframework
${schema}=    MCP.Get Tool Schema    ${CURDIR}/fixtures/.mcp.json    bundled-echo    echo
${has_message}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${schema}[properties]    message
Should Be True    ${has_message}
```

For strict validation (raises on failure), use `MCP.Validate Tool Schema`.

## What about runtime testing?

Tier-1 keywords stop at static inspection. To actually drive the MCP
server, use Epic 3 runtime keywords:

```robotframework
${handle}=    MCP.Start Server    ${CURDIR}/fixtures/.mcp.json    bundled-echo
${result}=    MCP.Call Tool    ${handle}    echo    message=hello
[Teardown]    MCP.Stop Server    ${handle}
```

See Recipe #3 (Tool Discoverability cohort) for the full Tier-3 +
cohort-evidence pattern.

## Cross-references

- Story 2.3 — MCP static-inspection keyword ratification.
- ADR-008 — MCP spec version validation.
- `docs/contracts/mcp-coverage-detection.md` — `mcp_coverage` enum.
