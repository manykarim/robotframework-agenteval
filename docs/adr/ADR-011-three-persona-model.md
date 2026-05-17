# ADR-011: Three-Persona Model + Persona-Split Test

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-014 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-014. Renumbered to ADR-011 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

The project brief named QA Engineers as the primary persona. Elicitation pre-mortem during PRD authoring (2026-05-14) collapsed personas to 2: **QA Engineer** + **Agent Developer (with 3 modes)**. Subsequent party-mode review (2026-05-15, Mary's directive after considering the CLI-first agent landscape) re-split into 3 personas by adding **Agent Surface Author**.

Without a principled rule for when to split a persona, future persona decisions become vote-driven — every reviewer pulls toward their favorite subdivision, persona count inflates without product-value justification, and downstream artifacts (epics, capability surfaces, keyword libdoc structure) get cluttered with persona-specific noise that doesn't reflect real product seams.

## Decision

agenteval recognizes **three primary personas** for Phase 1:

1. **QA Engineer** — evaluates pre-existing coding agents against scenarios. Primary user of `Run Scenario`, `Trajectory.` assertions, `Stat.` tier model, and conformance reports. Doesn't author skills, MCP servers, or agent prompts.

2. **Agent Surface Author** — ships skills + MCP servers + prompts INTO pre-built coding agents (e.g., authoring a `mark_done` skill that ships with a vendor's agent). Primary user of `Skill.` keywords (Get Activation Decision, Should Activate For), `Subagent.` keywords (Get Test Plan), `MCP.` keywords (Get Tool Discoverability). Doesn't run multi-step orchestrations.

3. **Agent Developer** — builds multi-step coding-agent orchestrations from scratch (e.g., a custom agent harness that chains Claude Code CLI calls with checkpoints). Primary user of `Run Scenario`, `Trajectory.` assertions, `Stat.` tier model. Doesn't ship skills/MCP/prompts INTO existing agents.

To prevent future persona inflation, this ADR formalizes the **persona-split test**:

> A persona splits when downstream artifacts (epics, stories, capability surfaces, keyword libdoc structure) require *different capabilities* — not when *different people* happen to use *different tools*.

Concretely: if proposed persona A and B would use the same keyword surface with the same expectations, they're the same persona under different titles. If they'd use disjoint keyword surfaces with different expectations of completeness/correctness, they're different personas.

The 3-way split passes the test: `Skill.` + `MCP.` keywords (Surface Author) genuinely differ from `Run Scenario` + `Trajectory.` keywords (Agent Developer + QA Engineer share these but differ on whether they're evaluating or building).

## Consequences

- Future persona proposals MUST justify against the split test in ADR-amendment form. Reviewers can reject persona proposals that fail the test without re-litigating the philosophy each time.
- The QA Engineer / Agent Developer overlap on `Run Scenario` is real and acknowledged — they're separate personas because their *motivation* differs (one evaluates, one builds), which surfaces in different epic scoping (QA wants Pass@k confidence; Agent Developer wants trajectory introspection). This is a defensible split; the test passes.
- Reverses part of the elicitation pre-mortem's "persona inflation correction" — annotated in the PRD frontmatter as a refinement (Mary's party-mode review added new information about CLI agents that the pre-mortem didn't have).
- Epic scoping uses the 3 personas as primary swim-lanes; e.g., Epic 2 (skills + subagents + hooks + MCP static inspection) is primarily Surface Author work, Epic 4 (provider layer + adapters) is primarily QA Engineer + Agent Developer work.

## Alternatives

- **Two personas (post-elicitation-collapse state: QA Engineer + Agent Developer-with-modes)** — rejected. Loses the "consumes pre-built agent vs builds new agent" distinction; Surface Author epics for skill/MCP keyword surfaces get conflated with multi-step orchestration epics, producing muddled story scoping.
- **Four personas (brief's original: QA Engineer + Agent Developer + Skill Author + MCP Author)** — rejected. Fails the persona-split test for Skill/MCP/Multi-step authors: they share enough downstream artifacts (Skill Author and MCP Author both use static-inspection keywords; Skill Author and Multi-step Author both interact with subagents) that 3 collapses cleanly without losing product distinctions.
- **No formal persona model; freeform stakeholder list** — rejected. Without personas, epic scoping becomes "everyone's tool, no one's responsibility"; keyword libdoc loses the lens that tells contributors which audience they're writing for.

## References

- PRD §`Stakeholders + Personas` (sidecar source, 2026-05-15) + party-mode review (2026-05-15)
- Project brief §`Primary Audience` (initial scoping)
- Future epic stories reference the 3 personas as primary swim-lane labels
