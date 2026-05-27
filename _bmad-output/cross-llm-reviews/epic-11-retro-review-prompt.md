# Epic 11 retrospective — cross-LLM critical review prompt

## Context

This is an **adversarial review of a draft retrospective document**.
The draft is at `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md`.

Per the operator `/goal` directive, this retro is reviewed by **Claude CLI**
(Tier-1 alternative) + **kilo CLI with MiniMax-M2.7** (Tier-3) — codex is
rate-limited and unavailable.

Past retro-on-retro cycles have caught:
- Numeric drift (Epic 10 retro: 6 HIGH catches by codex on test-counts, file-totals, git rev-list math).
- Citation drift (Epic 9 retro: broken git two-dot syntax was empty).
- False-positive sunset-criterion claims (Epic 9 retro `feedback_retro_debt_block_forward_progress` circular falsifier).
- Self-referential evidence claims.

Your job is to find that class of drift in THIS draft.

## What was Epic 11

Stories 11.1 (Codex CLI Adapter) + 11.2 (Copilot CLI Adapter) + 11.3
(AdapterVersionDriftWarning Fully Wired). First epic to operate fully
under the ratified 3-tier cross-LLM review chain. Headline outcome:
**N=3 orthogonal-coverage validation** of the chain at story-level +
**`feedback_cross_story_upstream_lesson_propagation` graduates from
CANDIDATE → CONFIRMED at N=3**.

## Source files to verify claims against

For each numeric claim, citation, or factual assertion in the draft, verify against:

- `_bmad-output/implementation-artifacts/11-1-codex-cli-adapter.md` (Story 11.1 record)
- `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md` (Story 11.2 record)
- `_bmad-output/implementation-artifacts/11-3-adapterversiondriftwarning-fully-wired.md` (Story 11.3 record)
- `_bmad-output/implementation-artifacts/epic-10-retro-2026-05-26.md` (immediately-prior retro; action-item follow-through source)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (epic + story statuses)
- `docs/phase-1-5-carry-overs.md` (catalog totals + new C73-C78 entries)
- `git log --oneline 229313e..577cf36` (Epic 11 commit chain)
- `_bmad-output/cross-llm-reviews/story-11-{1,2,3}-{copilot,kilo}-findings.md` (story-level review records)
- `_bmad-output/planning-artifacts/epics.md` L2083+ (Epic 12 preview)

## Adversarial review checklist

### HIGH — citation drift, numeric drift, false invariant claim

1. **Numeric drift**: every count in the draft (tests, source files, catalog,
   norm-use counts, commit counts, finding counts) must be machine-re-verifiable.
   Flag any that don't reconcile against the source files OR git.
2. **Citation drift**: every commit SHA, line number, file path, `Story X.Y`,
   `DF-X.Y-SZ`, `ADR-XX`, `Cnn` must point to a real current target.
3. **Action-item follow-through table**: verify each of the 9 Epic 10 retro
   action items got the correct ✅/❌ assignment. Edge case: Action #5
   (memory promotion) was claimed ✅ at `438b4a4` — verify the file
   actually exists at `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/`.
4. **`feedback_cross_story_upstream_lesson_propagation` N=3 claim**: verify
   the 3 transitions (10.2→11.1; 11.1→11.2; 11.2→11.3) actually applied
   the count of UPSTREAM lessons claimed (5/5, 5/5, 6/6). Re-derive each
   from the story records.
5. **`feedback_third_llm_family_fallback` N=12 claim**: 9 (Epic 10 retro) +
   3 (Epic 11 kilo) + 3 (Epic 11 copilot) = 15? or 9 + 3 substantive only
   = 12? The math should reconcile.
6. **Orthogonal-coverage matrix**: every Story 11.X cell in the "What
   worked #1" table must match the actual review records. Spot-check
   ≥2 cells per story per reviewer.
7. **Retro-debt count math**: claim is "7 ❌ at Epic 11 close vs 5 ❌ at Epic 10
   close → sunset criterion 2 fails AGAIN." Verify Epic 10 close had 5 ❌ +
   Epic 11 close has 7 ❌.
8. **`feedback_listener_hook_api_surface_empirical_check` N=4 claim**:
   verify the 4 surfaces (Listener v3 + 2 Phase-2 SDKs + Codex CLI JSONL).

### MED — style, ordering, vague framing

- Action items each need a binary success criterion (carry forward Epic 10 retro lesson).
- Norm-ratification entries should state next-test condition.

### LOW — wording, optional siblings

## Output format

For each finding cite **section + concrete fix**. Group as HIGH / MED / LOW.

CRITICAL: when finished, write the findings to:
`_bmad-output/cross-llm-reviews/epic-11-retro-{tool}-findings.md`
(replace `{tool}` with `claude` or `kilo`).

If the file isn't written, the review is invalid.
