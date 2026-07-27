## ADDED Requirements

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
