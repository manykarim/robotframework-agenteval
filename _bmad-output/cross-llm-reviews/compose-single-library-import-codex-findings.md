# compose-single-library-import Codex Review Findings

## Findings

### HIGH — `tests/dogfood/rf-mcp/test_trace_observability_parity.robot:30` re-imports `MCPLibrary` after `AgentEval`, making every `MCP.*` call ambiguous

`Library    AgentEval` now composes `MCPLibrary`, but this suite still also imports `AgentEval.mcp.library.MCPLibrary` directly:

```robotframework
29  Library          AgentEval    WITH NAME    AgentEval
30  Library          AgentEval.mcp.library.MCPLibrary
```

That creates two Robot libraries exposing the same baked names (`MCP.Get Server Config`, `MCP.Start Server`, `MCP.Stop Server`, etc.). The suite setup calls the unqualified `MCP.Get Server Config` / `MCP.Start Server`, so Robot cannot choose a library and fails before any test body runs.

Concrete failure reproduced with:

```bash
uv run robot --dryrun --outputdir /tmp/agenteval-dryrun-trace-only tests/dogfood/rf-mcp/test_trace_observability_parity.robot
```

Robot reports:

```text
Multiple keywords with name 'MCP.Get Server Config' found.
    AgentEval.MCP.Get Server Config
    AgentEval.mcp.library.MCPLibrary.MCP.Get Server Config

Multiple keywords with name 'MCP.Start Server' found.
    AgentEval.MCP.Start Server
    AgentEval.mcp.library.MCPLibrary.MCP.Start Server
```

and teardown likewise fails on duplicate `MCP.Stop Server`. Remove the standalone `MCPLibrary` import from this suite, or fully qualify every MCP call with one chosen library prefix. Given the refactor goal, removing line 30 is the consistent fix.

## Other Checks

I did not find other substantive correctness regressions in the requested areas.

- Composed `AgentEval().get_keyword_names()` reports 56 unique keywords and all 11 components loaded.
- `uv run pytest tests/unit/test_composition.py tests/unit/conventions/test_keyword_namespace_prefix.py -q` passed: 17 passed.
- Targeted composition checks passed for union-of-parts, duplicate detector behavior, and budget forwarding to all `_HostBudgetPlumbing` components.
- Libdoc inspection for `AgentEval`, Skills, Subagents, Hooks, MCP, Stats, and Judge found no rendered `. ` auto-split keyword names.
- Renamed tier lookups work for representative renamed keywords, and old bare names such as `Get Frontmatter`, `Get Config`, `Get Server Config`, and `Call Tool` are absent from the composed keyword set.
- Named Robot imports with budget kwargs still load for Stats/Judge/Skills/MCP, and top-level `AgentEval(max_cost_usd=7.0, max_runtime_seconds=8.0)` forwards those values to Orchestration, Stats, Judge, Skills, and MCP.
- Scaffold templates dry-run cleanly under plain `Library    AgentEval`.
