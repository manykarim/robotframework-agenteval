# Determinism Contract

**Status:** accepted.
**Related ADRs:** ADR-014 (Error-Class Hierarchy — `TierViolationError`).

> Superseded by the four-surface refocus (2026-07) where the details drifted. The
> heart is intact: agenteval promises bit-identical reproducibility for Tier-1 and
> honest statistical interpretability above it, and it never hides flakiness behind
> silent retries. What changed is the tier vocabulary — Tier-3 is now "drive a real
> coding agent," not "fan-out + statistics" — and the retired specifics (the
> `Stat.*` library, `@guarded_fanout`, the polling-ban and validate-operator error
> classes) are gone.

## Purpose

Governs the **determinism guarantees** agenteval offers (and explicitly does NOT offer) for evaluation runs. Specifically: which keywords are deterministic by construction, which are stochastic and why, and which tier of test mode is allowed at each ACL gate (`TierViolationError`).

## Summary

> agenteval promises bit-identical reproducibility for Tier-1 (deterministic, no model), statistical interpretability for the judge and coding-agent tiers via reproducibility footers, and no automatic retry/flake hiding. It does not promise cross-version or cross-provider reproducibility, bit-equality above Tier-1, or magical flake elimination. Honest statistical reporting beats false-confidence determinism in every keyword decision.

## Scope

### In-scope

- The 3-tier model (Tier-1 deterministic / Tier-2 LLM judge / Tier-3 coding agent) — see `### Tier Model` subsection.
- ACL gates: which tier a keyword may invoke internally.

### Out-of-scope

- The internals of the LLM-judge and coding-agent surfaces — those have their own docs.

## Contract

### (a) Tier-1 keyword bit-identical determinism guarantee

agenteval guarantees **bit-identical output across runs of any Tier-1 keyword given identical inputs**. Same input → same output: no randomness, no time-dependence, no environmental dependence beyond what is captured in the explicit input set.

Tier-1 keywords MUST therefore:
- Issue zero model calls per invocation.
- Read no clock / system time / random source.
- Read no environment variable not declared as an explicit input parameter.
- Read no filesystem path not declared as an explicit input parameter.
- Return values whose serialization is byte-stable across Python interpreter sessions.

This is the deterministic mode that all four libraries offer on the base install — no model, no network, just the file you handed them.

### (b) Tier-2 / Tier-3 statistical interpretability requirement

agenteval does NOT promise:
- Bit-identical results across runs of a Tier-2 (LLM judge) or Tier-3 (coding agent) keyword.
- Cross-model-version reproducibility — results from one model snapshot are not comparable to another.
- Cross-provider equivalence.

agenteval DOES guarantee that non-deterministic results are **characterizable**: judge and coding-agent runs carry reproducibility footers (model, timestamps, versions) so a result can always be traced back to the conditions that produced it. agenteval never retries-until-green to hide a flaky result.

### Tier Model

Every agenteval keyword declares one of three tiers — the three test modes:

- **Tier-1 (deterministic, no model):** zero model calls. Examples: `Skill.Get Activation Decision` (parses a skill file), `MCP.List Tools` (reads a schema). Deterministic by construction per §(a). Available on the base install.
- **Tier-2 (LLM judge):** one model call to grade a result against a rubric. Non-determinism bounded by temperature/seed where supported, characterizable per §(b). Needs the `[llm]` extra.
- **Tier-3 (coding agent):** drives a real coding agent end-to-end and observes what it did. Needs the `[llm]` extra (and `[mcp]` when the agent talks to MCP servers).

ACL gates per tier: a Tier-1 keyword may not reach up into Tier-2/3 internally; Tier-2 may not embed a Tier-3 agent run; Tier-3 may compose any tier. Violations raise `TierViolationError`. Enforcement is a direct raise from the `@tier` decorator surface.

### (c) Reproducibility checklist for bug reports

When filing a bug report against an agenteval evaluation result, capture:

1. **Versions** — `python --version`; `robot --version`; `pip show robotframework-agenteval | grep Version`.
2. **Full RF report `output.xml`** — includes the per-test `trace_id` attributes needed to correlate with the trace.
3. **The trace artifact** — the per-test run trace including the `ToolCallTrace` sequence.
4. **Model + MCP server versions** — for a coding-agent run, the model id; for each MCP server, the reported version + the negotiated MCP spec version.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-tier model is `stable` — changes to tier definitions require a major-version bump. ACL gate additions are minor-version-bump safe; loosening an existing gate requires a major bump (it weakens a documented guarantee).

## References

- ADR-014: Error-Class Hierarchy (`TierViolationError`).
- `src/AgentEval/_core/tier.py` — the `@tier` decorator that carries a keyword's tier.
