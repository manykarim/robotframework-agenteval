# ADR-019: AssertionEngine Adoption + Polling Ban + Validate Disabled by Default

- **Status:** Accepted
- **Date:** 2026-05-20
- **Story:** Epic 6 Story 6.3 (Statistical Primitives + Tier ACL + Determinism Enforcement)
- **Author:** Many Kasiriha

## Context

`robotframework-assertion-engine` is the canonical Robot Framework library
for `Should *` assertion keywords — providing `equal_to`, `contains`,
`matches_regexp`, `validate`, `>=`, `<=`, etc. operators with consistent
error messages + libdoc rendering.

`agentguard` (the inspiration project per `docs/adr/ADR-001-architectural-influences-catalog.md`
catalog row L87) adopted AssertionEngine via its own ADR-022. The catalog
row marks the agentguard pattern as **adapt** for agenteval.

PRD FR28 + FR43 + FR56 + FR42 explicitly require:
- A polling-ban gate (FR28) raising `PollingDisallowedError` when a
  Tier-2/3 keyword receives a `polling=` argument, with FR56 actionable
  message format (keyword name + path:line + remediation snippet + ADR link).
- A `validate` operator gate (FR43) raising `ValidateOperatorDisallowed`
  unless `allow_validate_operator=True` is set on the library (default
  `False` per FR42, because the operator uses `eval()`).

Until Story 6.3, the agenteval `Should *` keyword surfaces (Story 6.2
`AssertionsLibrary` 5 keywords + Story 2.1 `Skill.Should Be Valid Frontmatter`)
shipped as plain `@keyword`-decorated methods using stdlib primitives
(`==`, `in`, `re.search`, `jsonschema.validate`) per `_PHASE_1_SHOULD_CARVE_OUTS`
registry. Architecture L138/L266/L304/L496/L647 forward-referenced
AssertionEngine adoption to Story 6.3.

## Decision

Story 6.3 ships:

1. **Dependency pin** — `robotframework-assertion-engine>=4.0,<5.0` added
   to `pyproject.toml` (pre-approved via Story 6.2 epic L1629 amendment
   for the dev-story HALT condition "new dependencies need user approval").

2. **`_assertions/adapter.py`** with a free function:

   ```python
   def assert_value(
       actual: Any,
       operator: str | None,
       expected: Any,
       *,
       keyword_name: str,
       tier: int,
       polling: float | None = None,
       validate: bool = False,
       allow_validate_operator: bool = False,
       message: str | None = None,
   ) -> None
   ```

   Three sequential gates (fail-fast):

   - **Gate 1 (FR28 polling-ban):** `tier >= 2 and polling is not None`
     → `PollingDisallowedError(build_polling_disallowed_message(...))`.
   - **Gate 2 (FR43 validate-gate):** `validate is True and not allow_validate_operator`
     → `ValidateOperatorDisallowed(...)`.
   - **Gate 3 (dispatch):** delegates to `assertionengine.verify_assertion(actual, op_enum, expected, message=...)`.
     `operator=None` skips dispatch (gating-only mode for keywords doing
     their own matching).

3. **`_kernel/tier_acl.py`** with the FR56 message builders:

   - `build_polling_disallowed_message(keyword_name, keyword_args)` — FR56
     verbatim format (keyword name + RF path:line via stack walk + verbatim
     `Stat.Run N Times` remediation snippet + ADR-019 link).
   - `enforce_validate_operator_disallowed(allow_validate_operator, keyword_name)`
     — FR43 gate companion (D-8 resolution: FR56-style template applied to
     `ValidateOperatorDisallowed` for sibling consistency, not FR59 Tier-1
     setup-failure format).
   - `enforce_tier1_no_llm()` — FR30b: walks the Python call stack; raises
     `TierViolationError` if the topmost `@keyword`-decorated frame has
     `_agenteval_tier == 1`. Called from `LiteLLMAdapter.chat()` +
     `MockProvider.chat()` (and future provider entries) BEFORE token-
     consuming actions.

4. **`ValidateOperatorDisallowed` class** declared in `errors.py` under
   the newly-minted `AgentEvalSafetyError` sub-base (ADR-014 sub-base #4).
   Class name verbatim per ADR-014 ratification (NO `Error` suffix; Story
   1a.4 code-review HIGH-4 2026-05-18). `error_code = "VALIDATE_OPERATOR_DISALLOWED"`;
   exit code 77 (EX_NOPERM) per `docs/contracts/error-class-hierarchy.md:67`.

## Consequences

### Positive

- PRD FR28 + FR43 + FR56 + FR30b are no longer documentation-only; the
  raise sites are wired + tested.
- AssertionEngine becomes the canonical assertion dispatcher — future
  `Should *` keywords route through `adapter.assert_value()` instead of
  raising `AssertionError` directly from stdlib matchers.
- The `validate` operator's `eval()` execution is gated behind explicit
  operator opt-in, matching agentguard's safety posture.
- Tier-1 keywords are structurally prevented from invoking LLM providers
  (FR30b enforcement) — eliminates a class of test-author mistakes where
  a "deterministic getter" silently calls an LLM under the hood.

### Negative

- New runtime dep `robotframework-assertion-engine>=4.0,<5.0` (~5 KB
  install footprint, no transitive deps beyond `robotframework` which is
  already pinned).
- Tier-1 LLM-invocation enforcement uses `inspect.stack()` — small
  per-call overhead. Provider entry points already do non-trivial work
  (network I/O), so the overhead is amortized.

### Deferred to Phase-1.5 (Carry-overs catalog C49+C50)

- **DF-6.3-S1 (existing):** Swap stdlib matching backends in `AssertionsLibrary`
  to AssertionEngine matchers (`equal_to`, `contains`, `matches_regexp`).
  Backend refactor only; no operator-facing surface change.
- **DF-6.3-S2 (new):** Wire the 5 `AssertionsLibrary` keywords + 1
  `Skill.Should Be Valid Frontmatter` through `adapter.assert_value()` for
  polling-ban + validate-gate. Story 6.3 defers because all 6 are Tier-1
  (both gates are no-ops at that tier — wrapping adds `polling=` /
  `validate=` kwargs for no behavior change).

These two waves are bundled — when DF-6.3-S2 lands the gating wrap,
DF-6.3-S1 lands the matching swap in the same PR.

## Alternatives Considered

1. **Skip AssertionEngine entirely** — ship the polling-ban + validate-gate
   without the dispatch wiring. Rejected: PRD FR43 specifically mentions
   the `validate` operator (AssertionEngine-native concept); without
   AssertionEngine the operator can't exist + FR43 becomes a no-op gate
   against an unreachable trigger.

2. **Vendor a minimal AssertionEngine substitute** — write our own
   `verify_assertion()` instead of taking the dep. Rejected: maintenance
   burden + libdoc rendering loses the AssertionEngine-standard message
   format that RF users already recognize from other libraries.

3. **Defer to Phase-2** — keep `robotframework-assertion-engine` unpinned
   through Phase-1 close. Rejected: PRD FR28+FR43+FR56 are Phase-1 scope
   per epics.md L1633-1665 + architecture L138/L1646 verbatim pin.

## References

- ADR-001 catalog row L87 (agentguard ADR-022 AssertionEngine Adoption — adapt source).
- ADR-014 (error-class hierarchy — `AgentEvalSafetyError` + `ValidateOperatorDisallowed`).
- ADR-015 (cost-runtime guardrail decorator — sibling enforcement model for `@guarded_fanout`).
- PRD `_bmad-output/planning-artifacts/prd.md`:1534-1543 + 1565 + 1584 + 1587 (FR26-31a + FR43 + FR56 + FR59).
- Architecture `_bmad-output/planning-artifacts/architecture.md`:138 + 266 + 304 + 496 + 599-654 + 806-846 + 920-931 + 1646.
- Story 6.3 spec: `_bmad-output/implementation-artifacts/6-3-statistical-primitives-tier-acl-determinism-enforcement.md`.
- `docs/contracts/error-class-hierarchy.md`:51 + 62 + 67 + 150.
- `docs/contracts/determinism-contract.md`:55-56 + 101-102.
- `robotframework-assertion-engine` upstream: https://github.com/MarketSquare/robotframework-assertion-engine (>= 4.0 pin; 4.0.0 was the released version at Story 6.3 close).
