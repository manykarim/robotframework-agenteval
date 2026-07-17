## ADDED Requirements

### Requirement: An in-process agent adapter runs on only an LLM key and base_url

The library SHALL provide an `in-process` adapter, on the existing `Adapter` seam, that runs a prompt through an in-process agent loop (pydantic-ai) against any OpenAI-compatible endpoint configured by `base_url` + API key (and `AGENTEVAL_MODEL`), requiring no coding-agent CLI. It SHALL ship behind an optional `[agent]` extra; when the extra is not installed, the adapter SHALL fail with a clear error naming `[agent]`.

#### Scenario: Resolve the adapter by slug

- **WHEN** a user calls `get_adapter("in-process", model=..., base_url=..., api_key=...)`
- **THEN** an adapter instance is returned that satisfies the `Adapter` protocol

#### Scenario: Missing extra fails loud

- **WHEN** the `in-process` adapter runs without the `[agent]` extra installed
- **THEN** it raises an error naming the `[agent]` extra to install, not an opaque ImportError

### Requirement: Executed MCP tool calls are captured into the run result

When driving an MCP server, the adapter SHALL record every EXECUTED tool call — name, arguments, and result (or error) — into `AgentRunResult.tool_calls` as `ToolCallTrace` entries with `result`/`error`/`latency_ms` populated (unlike `GenericAdapter`, which records only requested calls), sourced from the run's message history with no monkeypatching.

#### Scenario: MCP tool execution is measured

- **WHEN** the adapter runs a prompt against an MCP server and the agent calls a tool
- **THEN** `AgentRunResult.tool_calls` contains a `ToolCallTrace` with the tool name, the arguments sent, and the tool's returned result, and MetricsLibrary reads it unchanged

### Requirement: Real skill activation is measured, not judged

Given a Claude `SKILL.md` loaded as a deferred capability, the adapter SHALL report which skill(s) the model actually activated during a run (from the model-emitted activation, e.g. `load_capability` + `ctx.loaded_capability_ids`), as a deterministic signal — not an LLM-judge inference.

#### Scenario: The model activates a matching skill

- **WHEN** a prompt whose need matches a skill's description is run with that skill loaded
- **THEN** the result reports that skill as activated (its id appears in the loaded-capabilities signal)

#### Scenario: The model does not activate an unrelated skill

- **WHEN** a prompt unrelated to a loaded skill's description is run
- **THEN** that skill is reported as NOT activated

### Requirement: SubAgent routing is measured in-process

Given Claude-style subagent definitions loaded into the harness, the adapter SHALL report which named subagent the model delegated to and how many delegations occurred, from the delegation tool call (`delegate_task` args) in the run's message history.

#### Scenario: Delegation to a named subagent is observable

- **WHEN** a task that should route to the `researcher` subagent is run
- **THEN** the result shows a delegation whose target is `researcher`

### Requirement: PreToolUse-style hook decisions are measurable (partial)

The adapter SHALL support measuring allow/deny decisions on tool calls via pydantic-ai tool-approval (a PreToolUse-style gate), reporting whether a guarded tool call was allowed or denied. This capability SHALL be documented as PARTIAL — it gates in-process tool calls, not external command-script hooks.

#### Scenario: A denied tool call is observable

- **WHEN** a tool guarded by an approval policy is requested and the policy denies it
- **THEN** the result reports the tool call as denied (not executed)

### Requirement: Results are labeled a proxy, never vendor-runtime truth

The adapter SHALL carry a `validation_ceiling` marker stating that it measures a generic in-process agent (a proxy), not a specific coding agent's runtime, and SHALL surface that `allowed-tools`/`disable-model-invocation` are not enforced. No metric it produces SHALL be presented as "how &lt;a named coding agent&gt; behaves."

#### Scenario: The proxy nature is discoverable

- **WHEN** a user inspects the adapter or its result metadata/docs
- **THEN** the proxy framing + the unenforced-fields caveat are stated explicitly
