# ADR-002: Tier-1 Adapter Ceiling Rule

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-005 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-005. Renumbered to ADR-002 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

Solo + AI-agent-assisted maintainership caps long-term CI/test-matrix capacity. Adding an adapter has marginal cost: CI cells per matrix entry, exact-pinned version drift risk, log-format regression surface, and conformance-fixture authoring effort. Adding *too few* Tier-1 adapters loses real users (a framework that supports only Claude Code CLI is not "coding-agent-agnostic"); adding *too many* turns agenteval into an adapter-maintenance project rather than an evaluation framework.

The PRD's original framing proposed a hard ceiling of 5 Tier-1 adapters. Subsequent review surfaced that the cap should be principle-based, not number-based — a hard "5" arbitrarily excludes future vendor entrants (Mistral, xAI, Anthropic V2) and doesn't generalize gracefully as the agent-vendor landscape evolves.

## Decision

The Tier-1 adapter ceiling is **"≤2 adapters per vendor + 1 generic escape hatch"** — a principle, not an absolute number.

A "vendor" is a coding-agent vendor (Anthropic, OpenAI, GitHub, ...) that publishes both a CLI agent and an SDK agent. Each vendor gets at most a CLI adapter + an SDK adapter as Tier-1 entries. The "+1 generic" is the LiteLLM-backed Generic adapter, which serves any LLM provider that doesn't have a vendor-specific adapter yet.

Concrete Phase-1 implication: 3 vendors known (Anthropic, OpenAI, GitHub) × 2 adapter styles + 1 Generic = up to 7 Tier-1 adapter slots. A 4th vendor entering the market (e.g., Mistral with both a CLI agent and an SDK agent) would extend the ceiling to 9. The ceiling tracks the principle, not a magic number.

Number-based caps are intuition-laundering: they encode "this many feels right" without a rule that explains why. The per-vendor principle is reviewable — "this adapter is the Nth from this vendor" is a fact, not a judgment.

## Consequences

- New vendor entries require explicit Tier-1 promotion via an ADR amendment to this one (documenting the new vendor + which adapter styles qualify).
- Community-contributed adapters that don't fit the per-vendor rule (e.g., a hobby fork of Claude Code CLI) default to Tier-2 (community-maintained, no agenteval CI gating).
- The Tier-3 statistical-evaluation tier is open to any registered adapter regardless of tier — the ceiling applies only to Tier-1's first-class status (CI matrix coverage + conformance-suite participation + bug-fix SLA).
- Phase-1 conformance suite needs to support `adapter_registry` parametrization (per ADR-017) so adding a Tier-1 adapter is a registration step, not a suite rewrite.

## Alternatives

- **Hard cap at 5 adapters total** — rejected. Arbitrarily excludes future vendor entrants. The "5" instantiates the principle "≤2 per vendor + 1" against the current 2-vendor reality but doesn't survive a 3rd vendor entering.
- **No cap, accept all 1st-party contributions** — rejected. Death-spiral for solo maintainership; every accepted adapter becomes a long-term CI obligation.
- **One adapter per vendor** — rejected. Loses the CLI/SDK split that's already real (Claude Code CLI and Claude Agent SDK are genuinely different surfaces — one is subprocess-driven, the other in-process — they need separate adapters).
- **Per-vendor proposal review with no fixed rule** — rejected. Every proposal becomes a debate; the principle here removes the debate by making "vendor + style" the criterion.

## References

- PRD §`Tier-1 Adapter Strategy` (sidecar source, 2026-05-15)
- ADR-003 (CodingAgentAdapter Protocol Internal Class Split) — the CLI/SDK base-class split that makes the "+2 per vendor" achievable without re-implementing subprocess lifecycle per adapter
- ADR-017 (Conformance Suite Organization) — `adapter_registry` parametrization that makes adding/removing Tier-1 adapters a registration step
