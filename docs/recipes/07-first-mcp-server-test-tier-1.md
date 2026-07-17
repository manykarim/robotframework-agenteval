# Recipe 2: First MCP server test

**I want to** validate my MCP server — its `.mcp.json` config and its tool
schemas — before I trust it in a live agent session.

Start deterministic. Tier-1 MCP keywords parse the config and check schemas
with **no server spawned and no model called** — perfect for a fast CI gate.
Then, when you want it, the same library drives the real server.

## The config

Save this as `.mcp.json`:

```json
{
  "mcpServers": {
    "search": {
      "command": "python",
      "args": ["-m", "my_search_server"],
      "transport": "stdio",
      "tools": {
        "web_search": {
          "type": "object",
          "properties": {
            "query": {"type": "string"}
          },
          "required": ["query"]
        }
      }
    }
  }
}
```

## Tier 1 — static inspection, no server, no keys

```robotframework
*** Settings ***
Library    MCPLibrary

*** Test Cases ***
Search Server Config Is Well-Formed
    ${servers}=    MCP.Get Server Config    ${CURDIR}/.mcp.json
    Should Be Equal    ${servers}[search][command]      python
    Should Be Equal    ${servers}[search][transport]    stdio

Web Search Tool Schema Is Declared And Valid
    ${schema}=    MCP.Get Tool Schema    ${CURDIR}/.mcp.json    web_search    search
    Should Be Equal    ${schema}[type]    object
    MCP.Validate Tool Schema    ${CURDIR}/.mcp.json    web_search    search
```

- `MCP.Get Server Config` parses `.mcp.json` into a `{server_name: entry}` dict.
  A malformed config fails loud with a JSON Pointer to the offending field.
- `MCP.Get Tool Schema` returns a declared tool's input JSON Schema. Leave the
  server name off and every server is searched in order.
- `MCP.Validate Tool Schema` checks the schema against JSON Schema Draft
  2020-12 — a malformed schema fails, again pointing at the exact field.

These three run with no MCP SDK installed. Schema validity is a static property
of the config, so this is the cheapest possible drift gate.

## Tier 1, live — actually drive the server

The live keywords need the `[mcp]` extra:

```bash
pip install 'robotframework-agenteval[mcp]'
```

They are still Tier 1 — deterministic, no model — but they spawn the real
server and speak MCP to it:

```robotframework
*** Settings ***
Library    MCPLibrary

*** Test Cases ***
Search Server Advertises And Answers
    ${handle}=    MCP.Start Server    search    stdio
    ...    command=python    args=${{['-m', 'my_search_server']}}

    ${session}=    MCP.Connect To Server    ${handle}
    Should Not Be Empty    ${session.protocol_version}

    @{tools}=    MCP.List Tools    ${handle}
    Should Contain    ${{[t.name for t in $tools]}}    web_search

    ${result}=    MCP.Call Tool    ${handle}    web_search    query=robot framework
    Should Be Equal    ${result.is_error}    ${False}

    [Teardown]    MCP.Stop Server    ${handle}
```

`MCP.Start Server` builds a handle; nothing spawns until the first operation.
`MCP.Connect To Server` runs the handshake and checks the negotiated protocol
version. `MCP.List Tools` and `MCP.Call Tool` do what they say. Pass tool
arguments inline (`query=robot framework`) for simple strings, or as a single
`arguments=` dict for anything non-string.

## Measuring tool coverage

When you run an agent against the server (Tier 3), `MCPLibrary` also projects
tool-call coverage out of the run: `MCP.Get Tool Call Count`, `MCP.Get Tool
Call Names`, `MCP.Get Tool Hit Rate`, `MCP.Get Tool Success Rate`, `MCP.Get
Unnecessary Call Rate`, and `MCP.Was Tool Called`. They answer "did the agent
call the tools it should have, and nothing it shouldn't?" over a captured
`AgentRunResult`.

## Next steps

- **Validate a Skill instead** — [Recipe 1](./01-first-eval-in-five-minutes.md).
- **Wire this into CI** — [Recipe 6](./08-ci-integration.md).
