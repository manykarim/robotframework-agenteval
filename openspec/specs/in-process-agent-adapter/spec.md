# in-process-agent-adapter Specification

## Purpose
TBD - created by archiving change add-in-process-agent-adapter. Update Purpose after archive.
## Requirements
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

### Requirement: The caller can raise the in-process agent's usage/request limit

The `in-process` adapter SHALL let the caller override the underlying agent
loop's usage limit so that legitimately long scenarios are measurable rather than
failing on the library's default request cap. It SHALL accept, keyword-only on
BOTH the constructor (`get_adapter("in-process", ...)`) and `run()`, a
`request_limit: int | None` shortcut and a full `usage_limits: <UsageLimits> | None`
escape hatch. Precedence SHALL be a single rule: a value provided to `run()`
overrides one provided to the constructor as a whole, and within a level the full
`usage_limits` object takes precedence over the `request_limit` shortcut. When
neither is provided at either level, the adapter SHALL apply no override, so the
underlying library default is used unchanged (non-breaking). The adapter SHALL NOT
import the agent library at module scope; the concrete limit object SHALL be
constructed only inside `run()`, behind the `[agent]` extra.

#### Scenario: Raising the request limit lets a long scenario run

- **WHEN** a caller sets `request_limit` to a value above the default and runs a
  scenario whose agent loop needs more than the default number of requests
- **THEN** the run proceeds up to the new limit instead of failing at the default

#### Scenario: The default path is unchanged

- **WHEN** a caller runs a prompt without setting `request_limit` or `usage_limits`
- **THEN** the adapter applies no usage-limit override and behavior is identical to
  before this change

#### Scenario: run() overrides the constructor and the object beats the shortcut

- **WHEN** a `request_limit` is passed to `run()` while a `usage_limits` object was
  passed to the constructor
- **THEN** the run-level `request_limit` takes effect (run overrides the constructor),
  and when both a `usage_limits` object and a `request_limit` are given at the same
  level the full object takes effect

### Requirement: The caller can inject instructions that reach the model

The `in-process` adapter SHALL accept an `instructions: str | None` argument,
keyword-only on BOTH the constructor and `run()`, and SHALL surface that string to
the model as the agent's run-level instructions. A value passed to `run()` SHALL
override one passed to the constructor. The injected instructions SHALL compose
with (not replace) any deferred-skill/capability instructions, so skill activation
via `load_capability` continues to work. When `instructions` is not provided, the
adapter SHALL inject nothing (non-breaking). The adapter SHALL treat the string as
caller-composed content and SHALL NOT auto-read it from any MCP server.

#### Scenario: Injected instructions are delivered to the model

- **WHEN** a caller passes `instructions="<server or task guidance>"`
- **THEN** that guidance is delivered to the model as run-level instructions for
  that run

#### Scenario: Injection does not break skill activation

- **WHEN** a caller passes `instructions=...` together with one or more deferred
  skills loaded as capabilities
- **THEN** the model can still activate a matching skill (the injected instructions
  are added to, not substituted for, the capability teaching)

#### Scenario: No instructions means no injection

- **WHEN** a caller runs a prompt without passing `instructions`
- **THEN** no run-level instructions are injected and behavior is unchanged

### Requirement: The proxy framing survives instruction injection

The adapter's `validation_ceiling` SHALL continue to state that it measures a
generic in-process agent (a PROXY), not a specific coding agent's runtime. It
SHALL additionally state that caller-supplied `instructions` are injected only when
the caller passes them (the adapter never auto-reads a server's instructions) and
that `allowed-tools`/`disable-model-invocation` remain NOT enforced. Injecting
instructions SHALL NOT be presented as making the adapter a faithful vendor client.

#### Scenario: The steered-proxy caveat is discoverable

- **WHEN** a user inspects the adapter's `validation_ceiling`
- **THEN** it states the PROXY nature, that instructions are injected only on caller
  request (never auto-read), and that `allowed-tools`/`disable-model-invocation` are
  not enforced

