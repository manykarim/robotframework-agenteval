# mcp-tool-invocation Specification

## Purpose
TBD - created by archiving change fix-first-run-experience. Update Purpose after archive.
## Requirements
### Requirement: Call Tool accepts natural RF kwargs
`MCP.Call Tool` SHALL accept free Robot Framework named arguments (e.g.
`MCP.Call Tool    ${handle}    echo_back    text=hello`) and pass them to the MCP tool as its
arguments dict, in addition to the existing `arguments=` dict form.

#### Scenario: Kwargs form invokes the tool
- **WHEN** a test calls `MCP.Call Tool    ${handle}    echo_back    text=hello` against the
  bundled echo server
- **THEN** the tool receives `{"text": "hello"}` and the keyword returns an `MCPToolResult` with
  `is_error == False`

#### Scenario: Kwargs pass through the decorator chain
- **WHEN** the keyword is invoked through its full `@keyword`/`@tier` decorator chain (as RF
  invokes it), not the bare inner function
- **THEN** free named arguments still reach the tool unchanged

### Requirement: Dict form remains unchanged
The existing `arguments=` dict form SHALL continue to work exactly as before; it remains the
canonical form for non-string argument values and for tool parameters whose names collide with
the keyword's own parameters (`handle`, `tool_name`, `arguments`).

#### Scenario: Existing dict callers unaffected
- **WHEN** a test calls `MCP.Call Tool    ${handle}    echo_back    arguments=${{ {"text": "hi"} }}`
- **THEN** behavior is identical to the pre-change keyword

### Requirement: Supplying both forms is a structured error
When a call provides both an `arguments=` dict and free named arguments, the keyword SHALL raise
a structured error (in the library's established File/Line/Field/Fix message style) instructing
the user to use exactly one form; it SHALL NOT silently merge them.

#### Scenario: Both forms rejected loudly
- **WHEN** a test calls `MCP.Call Tool    ${handle}    echo_back    arguments=${{ {"text": "a"} }}    text=b`
- **THEN** the keyword fails with an error naming both forms and a fix suggestion, and no tool
  call is made

### Requirement: Kwargs form is documented with its limits
The keyword documentation SHALL show the kwargs form as the primary example, state that RF free
named arguments arrive as strings unless typed syntax (e.g. `count=${5}`) is used, and name the
reserved parameter names that require the dict form.

#### Scenario: Docstring teaches both forms
- **WHEN** a user reads the `Call Tool` keyword documentation (libdoc)
- **THEN** it shows a working kwargs-form example, a working dict-form example, the string-value
  caveat, and the reserved-name caveat

