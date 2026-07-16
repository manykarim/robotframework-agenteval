## ADDED Requirements

### Requirement: HooksLibrary parses the real nested hook config

`HooksLibrary` SHALL parse the nested Claude Code hooks configuration format into a canonical in-memory shape and expose typed access to a hook's fields. The legacy flat-entry format and its deprecation path SHALL NOT be supported, and inline-skill frontmatter extraction SHALL NOT be included.

#### Scenario: Nested config parses into canonical entries

- **WHEN** a user calls `Hook.Get Config` on a valid nested hooks file
- **THEN** the library returns the parsed hooks keyed by event with each entry in one canonical shape

#### Scenario: Invalid config fails with a pointer

- **WHEN** a user parses a config with a malformed entry
- **THEN** the library raises a structured error pointing at the offending location in the real nesting

### Requirement: HooksLibrary is deterministic — Tier-1 only

Every `HooksLibrary` keyword SHALL be Tier-1. The library SHALL require no LLM or agent dependency and SHALL function on the base install. LLM-judge and agent modes SHALL NOT be offered for hooks, because hook outputs are deterministic programs.

#### Scenario: Library loads without extras

- **WHEN** a user installs the base distribution and declares `Library    HooksLibrary`
- **THEN** all Hook keywords load with no litellm or MCP SDK present

### Requirement: Static simulation and live firing share one matcher engine

`HooksLibrary` SHALL provide a static "which hooks would fire for this event" simulation and a live "fire a synthetic hook event" execution, and both SHALL resolve matchers through the same matcher engine so their results agree. The library SHALL also validate matcher syntax and check that a hook command resolves on disk.

#### Scenario: Simulation predicts what firing does

- **WHEN** a user calls `Hook.Get Hooks For Event` and then `Hook.Fire Hook Event` for the same event and payload
- **THEN** the set of hooks reported by the simulation matches the set actually executed

#### Scenario: Matcher syntax is validated

- **WHEN** a user calls `Hook.Validate Matcher Syntax` on a malformed matcher
- **THEN** the keyword fails with a message describing the syntax error

### Requirement: Firing a hook synthesizes a payload and normalizes decisions

`Hook.Fire Hook Event` SHALL synthesize a schema-aware event payload (with a full-override escape hatch), execute the matched hook commands in a sanitized environment under an enforced timeout, and normalize each result into a stable decision vocabulary. Execution failures SHALL be recorded per hook, not raised. Assertion keywords SHALL check the normalized decision, the process exit code, and named output fields.

#### Scenario: A blocking hook yields a block decision

- **WHEN** a user fires an event whose matched hook exits with a blocking status
- **THEN** `Hook.Decision Should Be    block` passes and `Hook.Exit Code Should Be` reports the process exit code

#### Scenario: A hook crash is recorded, not raised

- **WHEN** a matched hook command errors during execution
- **THEN** the failure is captured in that hook's result record and the keyword still returns results for the other hooks
