# package-pruning

What the shipped `AgentEval` package must no longer contain — the caller-less `security/` package, the empty `reporting/` package, and the duplicate Wilson CI implementation — plus the seams and numbers that must survive the pruning.

## ADDED Requirements

### Requirement: security package removed
The distribution SHALL NOT ship `AgentEval.security` (the `SandboxBackend` Protocol, `NullSandbox`, and sandbox policy modules). The `agenteval.sandboxes` entry-point group in `pyproject.toml` and `_kernel/discovery.discover_sandboxes()` SHALL remain as the Phase-3 extension seam.

**Reason**: Zero functional callers verified across `src/` and `tests/` (docs-only references); `NullSandbox` still raised the placeholder `NotImplementedError` because nothing ever invoked it. The Protocol is re-added when a real Phase-3 backend shapes it.

**Migration**: None for users (nothing could call it). Phase-3 re-introduces a `SandboxBackend` Protocol alongside the first real backend; `docs/contracts/stability-surface.md` carries a "withdrawn pre-1.0" note until then.

#### Scenario: Import fails cleanly
- **WHEN** Python evaluates `import AgentEval.security`
- **THEN** it raises `ModuleNotFoundError`

#### Scenario: Sandbox discovery seam intact
- **WHEN** `discover_sandboxes()` is called with no sandbox entry points installed
- **THEN** it returns an empty mapping without error

### Requirement: reporting package removed
The distribution SHALL NOT ship `AgentEval.reporting` (a docstring-only `__init__.py` whose promised modules landed elsewhere). JUnit XML emission, run summary, and exit-code behavior (FR49-51, FR54) SHALL remain available from their actual homes.

#### Scenario: Empty package gone, functionality intact
- **WHEN** Python evaluates `import AgentEval.reporting`
- **THEN** it raises `ModuleNotFoundError`, while the CLI exit-code channel and existing reporting keywords continue to pass their existing tests

### Requirement: Single Wilson CI implementation
The package SHALL contain exactly one Wilson score interval implementation, `AgentEval.stats.wilson.wilson_score_interval`; `AgentEval.discoverability.wilson_ci` SHALL NOT exist, and all discoverability CI computation SHALL route through the stats implementation.

**Reason**: `discoverability/wilson_ci.py` was a signature-identical duplicate of `stats/wilson.py` with one production caller.

**Migration**: `from AgentEval.discoverability.wilson_ci import wilson_score_interval` → `from AgentEval.stats.wilson import wilson_score_interval`.

#### Scenario: Duplicate module gone
- **WHEN** Python evaluates `import AgentEval.discoverability.wilson_ci`
- **THEN** it raises `ModuleNotFoundError`

#### Scenario: Discoverability CI numbers bit-identical
- **WHEN** a discoverability comparison computes `wilson_ci_lower` / `wilson_ci_upper` for a known (successes, trials) fixture that had pinned expected values before the dedup
- **THEN** the computed bounds equal the pinned pre-dedup values exactly

### Requirement: Test coverage consolidated, not dropped
Assertions from the deleted duplicate's test file (`tests/unit/discoverability/test_wilson_ci.py`) that are not already present in `tests/unit/stats/test_wilson.py` SHALL be folded into the surviving test file, including at least one test exercising the Wilson computation through the discoverability call path.

#### Scenario: Discoverability call path stays covered
- **WHEN** the unit test suite runs after the dedup
- **THEN** at least one test asserts Wilson CI bounds produced via the discoverability internals (not only via direct `stats.wilson` calls)

### Requirement: Dev tooling retained in the package
`AgentEval.conformance`, `AgentEval._new_adapter`, and `AgentEval._init` SHALL remain in the shipped package and off the runtime import path (imported only inside CLI subcommand handlers or via `python -m`), so that `pip install robotframework-agenteval` alone suffices for `agenteval init`.

#### Scenario: Headline onboarding command works from a bare install
- **WHEN** `agenteval init` runs in an environment with only the base package installed
- **THEN** the scaffold is produced without requiring any extra installation

#### Scenario: Library import does not load dev tooling
- **WHEN** `import AgentEval` completes
- **THEN** `sys.modules` contains none of `AgentEval.conformance`, `AgentEval._new_adapter`, `AgentEval._init`
