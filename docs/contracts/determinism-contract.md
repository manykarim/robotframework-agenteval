# Determinism Contract

**Status:** Phase-1 stable (Story 1b.6 2026-05-19 filled the contract per PRD FR63 verbatim coverage).
**Owning epic:** Epic 1b — Foundational Kernel
**Related ADRs:** ADR-012 (Async-to-Sync Bridge — `_run_async`), ADR-014 (Error-Class Hierarchy — `PollingDisallowedError`, `TierViolationError`), ADR-015 (Cost + Runtime Guardrails — `@guarded_fanout`), ADR-022 catalog row (AssertionEngine adoption — polling-ban + validate-disabled negative-consequence clauses)
**Related FRs:** FR26-31 (Statistical primitives + Tier model + ACL gates), FR43 (`allow_validate_operator`), FR63 (this Determinism Contract document)

## Purpose

Governs the **determinism guarantees** agenteval offers (and explicitly does NOT offer) for evaluation runs. Specifically: which keywords are deterministic by construction, which are stochastic and how their non-determinism is bounded (`Stat.Run N Times`, `Stat.Pass At K`), which keyword families forbid retry-style polling (`PollingDisallowedError`), and which Tier of model is allowed at each ACL gate (`TierViolationError`).

## Scope

### In-scope

- The 3-tier model (Tier-1 static inspection / Tier-2 single-LLM-call / Tier-3 fan-out + statistical) — see `### Tier Model` subsection.
- Polling-ban policy on Tier-2/3 keywords (raises `PollingDisallowedError` per ADR-014).
- `validate`-operator disabled by default (raises `ValidateOperatorDisallowed`; opt-in via `allow_validate_operator=True` per FR43).
- ACL gates: which user-supplied callable/keyword combinations are blocked at each tier.

### Out-of-scope

- Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap) — that's the `Stat.` library docstrings + `stability-surface.md`.
- The specific seed-management strategy for `Stat.Run N Times` — Epic 6 Story 6.x owns the seed contract.

## Contract

### (a) Tier-1 keyword bit-identical determinism guarantee (PRD FR31a L1542)

Library guarantees **bit-identical output across runs of any Tier-1 keyword given identical inputs**. Same input → same output, no randomness, no time-dependence, no environmental dependence beyond what is captured in the explicit input set. Verifiable via the `Assert Run Determinism <keyword> <args> expect=byte_identical` conformance keyword (Phase-2 deliverable: Epic 6 Story 6.x ships this in the Tier-3 cost-guardrail family alongside `Stat.Run N Times`).

Tier-1 keywords MUST therefore:
- Issue zero LLM calls per invocation.
- Read no clock / system time / random source.
- Read no environment variable not declared as an explicit input parameter.
- Read no filesystem path not declared as an explicit input parameter.
- Return values whose `dataclasses.asdict()` serialization is byte-stable across Python interpreter sessions.

Phase-1 enforcement is implicit (no Tier-1 keyword exists at end-of-Epic-1b; Epic 2 lands the first `Skill.Get Activation Decision` Tier-1 keyword + the determinism conformance asserter lands Epic 6). Phase-2 wires `Assert Run Determinism` into the per-AC conformance test files (Story 1b.5 baseline).

### (b) Tier-2/3 statistical interpretability requirement (PRD FR31b L1543)

Library does NOT promise:
- Bit-identical traces across runs of a Tier-2/3 keyword.
- Cross-model-version reproducibility (e.g., results from `claude-3-5-sonnet-20241022` are NOT comparable to `claude-3-5-sonnet-20250101`).
- Cross-provider equivalence (e.g., results from `litellm` are NOT comparable to direct `anthropic` SDK).

Library DOES guarantee that non-deterministic results are **characterizable via statistical primitives** at higher tiers:
- `Stat.Run N Times <keyword> n=K seed=S` (Epic 6 Story 6.x) — runs a Tier-2 keyword K times, returns a sequence of `AgentRunResult` records.
- `Stat.Get Pass At K <runs> threshold=T` (Epic 6) — computes pass@K per HumanEval methodology; returns `(passed: int, total: int, rate: float)`.

The Determinism Contract document is published with each library release per FR63; consumers verify the file's required sections exist via the doc-build CI step (Phase-2 carry-over from Story 1a.x doc-build infra).

### (c) Polling ban on Tier-2/3 (PRD FR28 L1536)

Library raises `PollingDisallowedError` (error_code `POLLING_DISALLOWED`; exit code 65 EX_DATAERR per `docs/contracts/error-class-hierarchy.md` L89) whenever a Tier-2 or Tier-3 keyword receives a `polling=` argument.

Rationale (per ADR-022 catalog row + AssertionEngine adoption): polling masks non-determinism by retrying-until-pass, defeating the statistical-interpretability requirement of FR31b. Tier-1 keywords MAY accept `polling=` (Phase-2 deliverable; no current Tier-1 keyword uses it). Tier-2/3 keywords MUST NOT.

Phase-1 enforcement: direct `raise PollingDisallowedError(...)` from the Tier-2/3 `_assertions/adapter.py` raise site (Story 1b.6 conventions test `test_no_bare_async_keywords.py` is a related but distinct enforcement layer). Phase-2 enforcement: `robotframework-assertion-engine` adopts the negative-consequence clause from ADR-022.

### Tier Model

agenteval keywords belong to one of three tiers (formalized 2026-05-18 per ADR-011 + this contract):

- **Tier-1 (static inspection):** zero LLM calls per invocation. Examples: `Skill.Get Activation Decision` (parses skill YAML), `MCP.List Tools` (reads schema). Deterministic by construction per §(a) above.
- **Tier-2 (single LLM call):** one provider call per invocation. Examples: `Run Scenario` (one agent run), `Trajectory.Compare`. Non-determinism bounded by provider temperature + seed where supported, characterizable per §(b) above.
- **Tier-3 (fan-out + statistical):** N provider calls per invocation, statistical aggregation. Examples: `Stat.Run N Times`, `Stat.Pass At K`, `MCP.Get Tool Discoverability`. Cost + runtime guardrails per ADR-015 `@guarded_fanout` decorator.

ACL gates per-tier: Tier-1 may not call Tier-2/3 internally; Tier-2 may not embed Tier-3 fan-outs; Tier-3 may compose any tier. Violations raise `TierViolationError` per ADR-014.

Phase-1 enforcement: subject to ADR-022 catalog row (`adapt`) + AssertionEngine adoption ADR (Phase 2). Phase-1 enforces via direct raise from `_kernel/`; Phase-2 adoption of `robotframework-assertion-engine` formalizes the contract surface.

### (d) Reproducibility checklist for bug reports

When filing a bug report against an agenteval evaluation result, capture the following 6 items in the report body. Reports missing any item may be deferred until the missing data is provided:

1. **`library_version`** — output of `import AgentEval; print(AgentEval.__version__)` from the affected environment.
2. **`redaction_policy_hash`** — output of `AgentEval._kernel.redaction.redaction_policy_hash()` (Story 1b.2 surface). Captures the active pattern set so consumers can verify their tests ran under the same redaction policy.
3. **Full RF report `output.xml`** — generated by `robot` at evaluation time. Includes the per-test `trace_id=<uuid>` attributes per FR51 needed to correlate with the jsonl trace.
4. **JSONL trace artifact** at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` — the per-test agent-run trace including `AgentRunResult` snapshots + `ToolCallTrace` sequence per FR35.
5. **Python + RF + agenteval versions** — `python --version`; `robot --version`; `pip show robotframework-agenteval | grep Version`.
6. **Adapter + MCP server versions** — for each `coding_agent=` adapter in use, capture `adapter.version` (the Story 1b.4 surface). For each MCP server in use, capture the server's reported version + the `mcp_spec_version` negotiated (Epic 3 Story 3.1 exposes this).

### `validate`-operator disabled by default (PRD FR43)

The `validate` operator is disabled by default (raises `ValidateOperatorDisallowed`; opt-in via `AgentEval(allow_validate_operator=True)` per FR43 + Story 1a.6 wiring). Rationale: `validate` invokes user-supplied callables, which can execute arbitrary Python — a sandbox / safety risk for shared CI environments. Opt-in is explicit per-instance (NOT environment-level), so a misuse cannot accidentally leak across CI jobs.

agenteval keywords belong to one of three tiers (formalized 2026-05-18 per ADR-011 + this contract):

- **Tier-1 (static inspection):** zero LLM calls per invocation. Examples: `Skill.Get Activation Decision` (parses skill YAML), `MCP.List Tools` (reads schema). Deterministic by construction.
- **Tier-2 (single LLM call):** one provider call per invocation. Examples: `Run Scenario` (one agent run), `Trajectory.Compare`. Non-determinism bounded by provider temperature + seed where supported.
- **Tier-3 (fan-out + statistical):** N provider calls per invocation, statistical aggregation. Examples: `Stat.Run N Times`, `Stat.Pass At K`, `MCP.Get Tool Discoverability`. Cost + runtime guardrails per ADR-015 `@guarded_fanout` decorator.

ACL gates per-tier: Tier-1 may not call Tier-2/3 internally; Tier-2 may not embed Tier-3 fan-outs; Tier-3 may compose any tier. Violations raise `TierViolationError` per ADR-014.

Phase-1 enforcement: subject to ADR-022 catalog row (`adapt`) + AssertionEngine adoption ADR (Phase 2). Phase-1 enforces via direct raise from `_kernel/`; Phase-2 adoption of `robotframework-assertion-engine` formalizes the contract surface.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-tier model is `stable` from Phase-1 onward — changes to tier definitions require major-version bump per NFR-MAINT-03. ACL gate additions are minor-version-bump safe; loosening an existing gate requires major bump (it weakens a documented guarantee).

## Phase-1 limitations

- `Assert Run Determinism <keyword> <args> expect=byte_identical` conformance keyword: **deferred to Epic 6 Story 6.x** (Tier-3 cost-guardrail family ships the determinism asserter alongside `Stat.Run N Times`).
- `Stat.Run N Times` + `Stat.Get Pass At K` statistical primitives: **deferred to Epic 6 Story 6.x**.
- Per-AC conformance test for `Assert Run Determinism`: skeleton at `tests/conformance/test_ac_dogfood_01_replacement.py` (Story 1b.5 baseline) SKIPs until owning epic ships.
- Doc-build CI step that asserts this file's required sections exist + the single-paragraph summary is byte-identical to the PRD source per FR63 final clause: **deferred to Phase-1.5 hygiene story** (no `mkdocs-build` workflow exists yet at Phase-1 close).

## References

- ADR-012: Async-to-Sync Bridge (`_run_async` — why `@keyword` functions are NOT `async def`; `_kernel/run_async.py` Story 1b.1)
- ADR-014: Error-Class Hierarchy (`PollingDisallowedError`, `TierViolationError`, `ValidateOperatorDisallowed`)
- ADR-011: Three-Persona Model (the tier model serves the QA Engineer + Agent Developer personas)
- ADR-015: Cost + Runtime Guardrails (`@guarded_fanout` decorator wraps Tier-3 fan-out keywords)
- ADR-022 catalog row in `docs/adr/ADR-001-architectural-influences-catalog.md`: AssertionEngine adoption (negative-consequence clauses encode polling-ban + validate-disabled)
- PRD FR26-31: Statistical primitives + Tier-1/2/3 model + ACL gates + determinism contract (FR28 polling ban; FR31a/b determinism + statistical interpretability)
- PRD FR43: `allow_validate_operator` opt-in (Story 1a.6 wired the default)
- PRD FR63: this document's publication requirement
- Story 1a.6 `src/AgentEval/__init__.py` `allow_validate_operator=False` default
- Story 1b.1 `src/AgentEval/_kernel/tier.py` `@tier` decorator + `_agenteval_tier` attribute
