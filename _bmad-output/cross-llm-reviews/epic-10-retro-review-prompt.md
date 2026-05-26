# Epic 10 retrospective — cross-LLM critical review prompt

## Context

This is an **adversarial review of a draft retrospective document**, not a code review.
The draft is at `_bmad-output/implementation-artifacts/epic-10-retro-2026-05-26.md`.

The project's `feedback_retro_on_retro` norm (Epic 7 retro) ratifies cross-LLM
adversarial review of non-trivial retros. Past retro-on-retro cycles have caught:

- Numeric drift (Epic 7 retro: source-file delta inflated 5×).
- Citation drift (Epic 9 retro: `297c3c4..924e20a` two-dot git syntax was empty).
- Action-item enforcement-fiction (Epic 9 retro Action #6 implied automatic
  enforcement the loop cannot deliver).
- Self-referential evidence claims (Epic 9 retro `feedback_retro_debt_block_forward_progress`
  CANDIDATE norm had circular-falsifier).

Your job is to find that class of drift in THIS draft.

## What was Epic 10

Stories 10.1 (`claude-agent-sdk` adapter) + 10.2 (`openai-agents` adapter), both
`InProcessAdapter` subclasses. The headline outcome the retro emphasises:
**third-LLM-family fallback (kilo/minimax M2.7) PROVED viable** when Claude CLI +
Codex CLI both degraded — N=9 substantive reviews across Epics 8+9+10.

## Source files to verify claims against

For each numeric claim, citation, or factual assertion in the draft, verify against:

- `_bmad-output/implementation-artifacts/10-1-claude-agent-sdk-adapter.md` (Story 10.1 record)
- `_bmad-output/implementation-artifacts/10-2-openai-agents-sdk-adapter.md` (Story 10.2 record)
- `_bmad-output/implementation-artifacts/epic-9-retro-2026-05-25.md` (immediately-prior retro, referenced for action-item follow-through)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status of records)
- `docs/phase-1-5-carry-overs.md` (catalog totals)
- `git log --oneline 297c3c4~..HEAD` (commit-chain claims)
- `_bmad-output/planning-artifacts/epics.md` L2029+ (Epic 11 preview)

## Adversarial review checklist

### HIGH — citation drift, numeric drift, false invariant claim

1. **Numeric drift**: every count in the draft (tests, source files, catalog,
   norm-use counts, commit counts, finding counts) must be machine-re-verifiable
   from the source files OR commit history. Flag any that don't reconcile.
2. **Citation drift**: every ADR-XX, FR-XX, Story X.Y, DF-X.Y, commit-SHA, line-range,
   or filename in the draft must point to a real, current target.
3. **False invariant claim**: the draft claims `feedback_third_llm_family_fallback`
   N=9 across Epics 8+9+10. Verify the count by reading commit `16ee936`'s message
   (retroactive Epic 8+9 batch) + the two Epic 10 story records' "Senior Developer
   Review (AI)" sections.
4. **Action-item SMART-ness**: each action item in the "Action items for Epic 11"
   table must have an owner + a concrete success criterion. Vague actions
   ("improve cross-LLM review") fail.
5. **Norm-ratification evidence base**: the draft promotes `feedback_third_llm_family_fallback`
   from CANDIDATE → CONFIRMED. Verify the N=9 evidence base. Flag if N<9 or if
   any of the N reviews counted as "substantive" was actually empty/deferred.
6. **Norm retirement**: the draft retires `feedback_retro_debt_block_forward_progress`.
   Verify the sunset criteria from Epic 9 retro are actually satisfied.

### MED — style, ordering, vague framing

- Each "Norm to ratify" entry should state the operational invocation if
  applicable, the N evidence, and the next-test condition.
- Action items should be ordered by impact, not by category.

### LOW — wording, optional sibling

- Style consistency, optional cross-references.

## Output format

For each finding cite **section + concrete fix**. Group as HIGH / MED / LOW.

CRITICAL: when finished, write the findings to:
`_bmad-output/cross-llm-reviews/epic-10-retro-{tool}-findings.md`
(replace `{tool}` with `codex` or `kilo` depending on which reviewer you are).

If the file isn't written, the review is invalid.
