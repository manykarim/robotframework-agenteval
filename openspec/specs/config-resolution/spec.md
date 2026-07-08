# config-resolution Specification

## Purpose
TBD - created by archiving change remove-dead-machinery. Update Purpose after archive.
## Requirements
### Requirement: Single precedence-chain implementation
The configuration system SHALL implement the 4-layer precedence chain (`__init__` kwarg > `AGENTEVAL_*` environment variable > `.env` file > FR42 default) in exactly one function, `resolve_config_with_provenance`, returning `dict[str, ConfigValue]` where each `ConfigValue` carries `value` and `source` (one of `init_arg` / `env` / `dotenv` / `default`). `resolve_config` SHALL remain available with its existing name, signature, and `dict[str, Any]` return shape, implemented as a pure value projection over `resolve_config_with_provenance` with no independent precedence, coercion, or dotenv-loading logic.

#### Scenario: Precedence resolved identically through both entry points
- **WHEN** the same kwarg overrides, environment, and `.env` file are resolved via `resolve_config` and via `resolve_config_with_provenance`
- **THEN** for every config key, `resolve_config(...)[key]` equals `resolve_config_with_provenance(...)[key].value`

#### Scenario: Provenance reports the winning layer
- **WHEN** a key is supplied as an `__init__` kwarg while the corresponding `AGENTEVAL_*` env var is also set
- **THEN** `resolve_config_with_provenance` returns that key with `source == "init_arg"` and the kwarg value

### Requirement: One resolution pass per library import
`AgentEval.__init__` SHALL invoke the precedence chain exactly once per instantiation, storing the provenance map and deriving bare config values from it, instead of resolving the chain twice.

#### Scenario: Unknown-key warnings emitted once
- **WHEN** `AgentEval` is instantiated with an unknown `AGENTEVAL_*` key present in the environment or `.env` file
- **THEN** exactly one `UserWarning` per unknown key per source is emitted, not two

### Requirement: Single config keyword with two forms
The library SHALL expose exactly one configuration-introspection keyword, `Get Effective Config`: called with no arguments it SHALL return the resolved settings as `dict[str, Any]` (plain values); called with `setting=<key>` it SHALL return the single `ConfigValue(value, source)` for that key, raising `ValueError` with the sorted list of known keys for an unknown key. The no-arg return SHALL be derived from the stored provenance map, not from a hand-maintained key list.

#### Scenario: No-arg form returns plain values
- **WHEN** a suite imports `Library    AgentEval    max_cost_usd=5.0` and calls `Get Effective Config` with no arguments
- **THEN** `${config}[max_cost_usd]` is the plain number `5.0`

#### Scenario: Per-setting form returns provenance
- **WHEN** the suite calls `Get Effective Config    setting=max_cost_usd`
- **THEN** the result exposes `.value == 5.0` and `.source == "init_arg"`

#### Scenario: Unknown setting rejected
- **WHEN** the suite calls `Get Effective Config    setting=no_such_key`
- **THEN** the keyword fails with a `ValueError` naming the unknown key and listing the known keys

### Requirement: Provenance twin keyword removed
The library SHALL NOT expose a `Get Effective Config With Provenance` keyword. The per-key `setting=` form of `Get Effective Config` is the provenance surface.

**Reason**: The full-provenance-map keyword duplicated the resolver chain and had no distinct job — the debugging use case ("which layer won for this key?") is per-key. Pre-1.0 hard delete per design.md D3.

**Migration**: Replace `Get Effective Config With Provenance` + map indexing with `Get Effective Config    setting=<key>` per key of interest.

#### Scenario: Twin keyword absent from the library surface
- **WHEN** libdoc renders the composed `AgentEval` library
- **THEN** `Get Effective Config` is present and `Get Effective Config With Provenance` is not

