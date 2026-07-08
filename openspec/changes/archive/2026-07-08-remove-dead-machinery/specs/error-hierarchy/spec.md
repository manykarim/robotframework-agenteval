# error-hierarchy

The consolidated `errors.py` surface: all six abstract catch-point bases preserved, `DuplicateRegistrationError` folded into `AdapterDiscoveryError`, exit-code table synchronized with the contract doc, and the File/Line/Field/Fix message format preserved verbatim.

## ADDED Requirements

### Requirement: Abstract catch-point bases preserved
`errors.py` SHALL retain all six abstract bases — `AgentEvalError`, `AgentEvalIntegrityError`, `AgentEvalSafetyError`, `_FR59Tier1SetupFailureError`, `AgentEvalBudgetError`, `AgentEvalCompatError` — as the documented catch points, and every concrete error SHALL remain catchable via its family base and via `AgentEvalError`.

#### Scenario: Family-level catch still works
- **WHEN** a consumer wraps a call in `except AgentEvalCompatError`
- **THEN** an adapter-discovery failure raised inside is caught by that handler

### Requirement: DuplicateRegistrationError folded into AdapterDiscoveryError
`errors.py` SHALL NOT define `DuplicateRegistrationError`. A duplicate entry-point name during adapter discovery SHALL raise `AdapterDiscoveryError` whose message names the colliding entry-point name and both registration sources, preserving the structured fix-suggestion content of the former leaf.

**Reason**: Single raise site, no dedicated exit code (already exited through `ADAPTER_DISCOVERY_ERROR`), and callers were verified to catch only the parent — the leaf distinction bought nothing.

**Migration**: `except DuplicateRegistrationError` → `except AdapterDiscoveryError`.

#### Scenario: Duplicate registration raises the parent
- **WHEN** two entry points register the same adapter name
- **THEN** discovery raises `AdapterDiscoveryError` and the message names the duplicate entry-point name

### Requirement: Kept single-raise-site leaves
`errors.py` SHALL retain `ValidateOperatorDisallowed` (dedicated exit code 77, ratified safety-gate name), `RuntimeBudgetExceededError` (dedicated exit code 75, distinct from `CostExceededError` 66), and `SkillDidNotActivateError` (user-catchable assertion with structured diagnostic attrs) despite each having a single raise site.

#### Scenario: Budget-breach kind remains distinguishable
- **WHEN** a Tier-3 keyword breaches the runtime budget rather than the cost budget
- **THEN** the raised error is `RuntimeBudgetExceededError`, mapping to exit code 75 (not 66)

### Requirement: Exit-code table synchronized
`cli._ERROR_EXIT_CODES` SHALL contain no entry for a class that does not exist in `errors.py` — in particular, the planned-only `SANDBOX_REQUIRED` row SHALL be removed — and `docs/contracts/error-class-hierarchy.md` SHALL list exactly the implemented leaves (22 after this change) with an ADR-014 amendment note recorded in the same change.

#### Scenario: No phantom exit-code rows
- **WHEN** the exit-code table keys are checked against the `error_code` attributes of classes defined in `errors.py`
- **THEN** every table key corresponds to an existing class (or the documented warning-class row) and no key references a never-shipped class

### Requirement: Diagnostic message format preserved
Every error retaining a structured diagnostic block SHALL keep the File/Line/Field/Fix message format and `fix_suggestion` mechanics byte-compatible with the pre-change format; docstring trimming SHALL remove only internal story/review narration, never behavioral contract text.

#### Scenario: Setup-failure diagnostics unchanged
- **WHEN** a Tier-1 setup file fails validation (for example an invalid skill frontmatter)
- **THEN** the raised error message still carries the File/Line/Field/Fix block identifying the offending file, location, field, and suggested fix
