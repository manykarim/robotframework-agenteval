---
name: Feature Request
about: Propose a new keyword, configuration option, or behavioral change
title: "feat: <one-line summary>"
labels: [enhancement]
assignees: ""
---

> **Before filing:**
> - Browse [docs/adr/](../../docs/adr/README.md) — the proposal may already be decided (or rejected with rationale).
> - Browse [docs/contracts/](../../docs/contracts/README.md) — the contract for the affected surface may constrain the design.
> - For **triage expectations**, see [SUPPORT.md](../../SUPPORT.md) (best-effort 5 business days).

## Problem statement

<!-- What problem does this feature solve? Who has the problem?
     Frame in terms of the affected persona (see below). -->

## Proposed solution

<!-- A clear, concise description of what you want to happen.
     If you have a design sketch, include it (Markdown + code blocks). -->

```python
# Optional: pseudocode showing the proposed API
```

## Alternatives considered

<!-- What other approaches did you consider? Why did you reject them?
     Cite agentguard ADRs or other reviewed patterns if relevant —
     agenteval may have already evaluated + diverged via ADR-001 Catalog. -->

## Target persona

<!-- Per ADR-011 (Three-Persona Model). Pick one or multiple: -->

- [ ] **QA Engineer** — evaluates pre-existing coding agents against scenarios
- [ ] **Agent Surface Author** — ships skills + MCP servers + prompts INTO pre-built coding agents
- [ ] **Agent Developer** — builds multi-step coding-agent orchestrations from scratch

## Phase-1 vs Phase-2 fit

<!-- agenteval is in Phase 1 (Tier-1 adapter ceiling per ADR-002, kernel composition per ADR-003).
     Is this proposal Phase-1 scope (lands in epics 1a-9) or Phase-2 (Epic 10+)?
     If unsure, note "TBD". -->

- [ ] Phase 1 (epics 1a-9; 0.x release line)
- [ ] Phase 2 (Epic 10+; 1.x release line)
- [ ] TBD — needs maintainer triage

## Additional context

<!-- Related ADRs, links to similar projects' implementations, prior art, etc. -->
