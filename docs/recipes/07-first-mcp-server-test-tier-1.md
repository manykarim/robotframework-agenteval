# Recipe #7: First MCP server test (Tier-1 static inspection)

**Use case:** you ship an MCP server and want deterministic (no LLM calls)
validation of its `.mcp.json` config and tool schemas.

## TL;DR

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Echo Server Config Is Valid
    ${servers}=    MCP.Get Server Config    ${CURDIR}/fixtures/.mcp.json
    Should Be Equal As Strings    ${servers}[bundled-echo][command]    python
    Should Be Equal As Strings    ${servers}[bundled-echo][transport]    stdio

Echo Tool Schema Is Valid
    ${schema}=    MCP.Get Tool Schema    ${CURDIR}/fixtures/.mcp.json    echo    bundled-echo
    Should Be True    ${schema} is not None
```

## Why Tier-1 first?

Tier-1 keywords are **deterministic** — they parse files and return structured
data without any LLM call. Use them in your CI smoke suite to catch config
drift before any Tier-2 / Tier-3 runtime call:

| Keyword | Purpose |
| --- | --- |
| `MCP.Get Server Config` | Read + validate the server entries in `.mcp.json`. |
| `MCP.Get Tool Schema` | Read a tool's JSON Schema. |
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

### 2. Import the library

```robotframework
Library    AgentEval
```

`MCPLibrary` is composed into the top-level `AgentEval` library, and every MCP
keyword bakes its `MCP.` prefix into its name — so a single `Library    AgentEval`
import reaches `MCP.Get Server Config`, `MCP.Get Tool Schema`, and the rest. No
`WITH NAME` needed.

### 3. Read + assert the config

```robotframework
${servers}=    MCP.Get Server Config    ${CURDIR}/fixtures/.mcp.json
Should Be Equal As Strings    ${servers}[bundled-echo][command]    python
```

`MCP.Get Server Config` returns a dict keyed by server name. If the config is
malformed (missing required field, invalid transport, unknown JSON Pointer),
`InvalidMCPServerConfigError` raises with a structured diagnostic message.

### 4. Read + assert the tool schema

```robotframework
${schema}=    MCP.Get Tool Schema    ${CURDIR}/fixtures/.mcp.json    echo    bundled-echo
${has_message}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${schema}[properties]    message
Should Be True    ${has_message}
```

For strict validation (raises on failure), use `MCP.Validate Tool Schema`.

## What about runtime testing?

Tier-1 keywords stop at static inspection. To actually drive the MCP server,
use the runtime keywords:

```robotframework
${handle}=    MCP.Start Server    bundled-echo    stdio    python
...    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
${result}=    MCP.Call Tool    ${handle}    echo_back    text=hello
[Teardown]    MCP.Stop Server    ${handle}
```

See Recipe #3 (Tool Discoverability cohort) for the full Tier-3 cohort
evidence pattern.

## Cross-references

- [`docs/contracts/mcp-coverage-detection.md`](../contracts/mcp-coverage-detection.md)
  — the `mcp_coverage` enum.
