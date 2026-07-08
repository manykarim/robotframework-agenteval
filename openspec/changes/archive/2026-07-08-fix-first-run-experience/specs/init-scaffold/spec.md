# Spec: init-scaffold

## ADDED Requirements

### Requirement: Scaffolded example suites run green without edits
The templates shipped in `src/AgentEval/_init/templates/` SHALL produce a project in which every
scaffolded `.robot` example suite passes when executed with the documented run command, the mock
provider, and the bundled echo MCP server, with zero user edits.

#### Scenario: Fresh init runs green
- **WHEN** a user runs `agenteval init` in an empty directory and then runs the run command
  documented in the scaffolded README
- **THEN** Robot Framework exits 0 with all scaffolded example tests passing

#### Scenario: MCP example imports the library it uses
- **WHEN** the scaffolded `example_mcp_runtime.robot` is parsed
- **THEN** it imports `AgentEval.mcp.library.MCPLibrary` with name `MCP` (in addition to
  `AgentEval`), so every `MCP.*` keyword it calls resolves

#### Scenario: MCP example calls the tool that actually exists
- **WHEN** the scaffolded MCP example invokes the bundled echo server
- **THEN** it calls tool `echo_back` with argument name `text` (matching
  `src/AgentEval/mcp/bundled/echo.py`), and the call form used is one `MCP.Call Tool` accepts

#### Scenario: MCP example asserts real result attributes
- **WHEN** the scaffolded MCP example asserts on the tool-call result
- **THEN** it references only attributes that exist on `MCPToolResult` (`is_error`,
  `error_message`, `content`, `latency_ms`) — never `success`

### Requirement: Scaffolded scenario.yaml validates against the shipped schema
The `scenario.yaml` template SHALL load without error through the library's own `Load Scenario`
keyword, including declaring `mcp_servers` as a list of strings as required by
`src/AgentEval/scenarios/loader.py`.

#### Scenario: Load Scenario accepts the scaffolded file
- **WHEN** `Load Scenario` is called on a freshly scaffolded `tests/fixtures/scenario.yaml`
- **THEN** it returns a `Scenario` object without raising `InvalidScenarioYAMLError`

### Requirement: CI executes the scaffold end-to-end
The project SHALL run an automated integration test on every CI push that performs `agenteval
init` in a temporary directory, executes the scaffolded suites to completion, and validates the
scaffolded `scenario.yaml`, using only keyless deterministic dependencies (mock provider, bundled
echo server).

#### Scenario: Smoke test gates scaffold rot
- **WHEN** a change breaks any scaffolded template (missing import, wrong keyword shape, invalid
  YAML)
- **THEN** the CI scaffold smoke test fails on that change's push, before merge

#### Scenario: Smoke test needs no credentials
- **WHEN** the scaffold smoke test runs in CI
- **THEN** it completes without any API key or network-dependent provider, within a bounded
  timeout

### Requirement: Scaffolded files are free of internal process jargon
Templates SHALL NOT contain internal project-management identifiers (Story/Epic/FR/ADR/DF-X-SY/
C-number references, review-provenance notes, persona-journey slot labels) in any user-visible
content, including comments.

#### Scenario: Template comments read as user documentation
- **WHEN** any file under `src/AgentEval/_init/templates/` is scaffolded
- **THEN** its content and comments explain usage in product terms and contain no
  Story/Epic/FR/ADR/DF-X-SY/C-number identifiers
