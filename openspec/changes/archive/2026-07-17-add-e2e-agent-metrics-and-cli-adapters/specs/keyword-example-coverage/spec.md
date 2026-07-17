## ADDED Requirements

### Requirement: Every shipped keyword's documentation carries a runnable usage example

Every keyword exported by an `AgentEval` library SHALL carry, in its libdoc
documentation, at least one runnable usage example written in Robot Framework
syntax that references only keywords, namespaces, and arguments that actually
exist. The four `SkillsLibrary` keywords that currently lack an example —
`Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation`, and
`Get Activation Decision` — SHALL each be given one, and no phantom reference
(such as the current `Stat.Run N Times` mention that names a keyword which does
not exist as a Library) SHALL remain in any shipped keyword's documentation.

#### Scenario: The four SkillsLibrary keywords gain runnable examples

- **WHEN** libdoc documentation is generated for `SkillsLibrary`
- **THEN** each of `Get Description`, `Get Allowed Tools`,
  `Get Disable Model Invocation`, and `Get Activation Decision` contains a
  usage example block written in Robot Framework syntax
- **AND** each example references only keywords and arguments that resolve
  against the shipped libraries

#### Scenario: No documented example references a phantom keyword

- **WHEN** every shipped keyword's documentation is scanned for the keywords it
  invokes
- **THEN** every referenced keyword (including namespace-prefixed references
  such as `Stat.Run N Times`) resolves to a keyword that a corresponding
  shipped Library actually exports
- **AND** any example that references a non-existent keyword is treated as a
  failure to be fixed, not shipped

### Requirement: A gate extracts and runs every documented keyword example

The project SHALL provide a gate that extracts every usage example from every
shipped keyword's libdoc documentation and verifies that it runs. The gate
SHALL, for each extracted example, perform Robot Framework keyword resolution
via `--dryrun` and, where feasible, a minimal execution. The gate SHALL fail
when any example is a phantom (references an unresolvable keyword) or is
otherwise broken, and SHALL be runnable as part of the local/CI doc gate
sequence.

#### Scenario: Gate fails on a phantom example

- **WHEN** the gate runs against a keyword whose documented example references a
  keyword that no shipped Library exports
- **THEN** the gate exits non-zero
- **AND** the failure names the offending keyword and the unresolvable
  reference

#### Scenario: Gate fails on a broken example

- **WHEN** the gate runs against a keyword whose documented example does not
  pass Robot Framework `--dryrun` keyword resolution (for example an argument
  or namespace that does not exist)
- **THEN** the gate exits non-zero
- **AND** the failure identifies which example failed resolution

#### Scenario: Gate passes when every example resolves and runs

- **WHEN** the gate runs and every shipped keyword's documented example passes
  `--dryrun` keyword resolution and any feasible minimal execution
- **THEN** the gate exits zero

#### Scenario: Gate covers every shipped keyword, not a sampled subset

- **WHEN** the gate enumerates the keywords whose examples it checks
- **THEN** it includes every keyword exported by every shipped `AgentEval`
  library, so that a keyword shipped without a runnable example causes the gate
  to fail
