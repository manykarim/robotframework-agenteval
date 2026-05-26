# Codex Findings — Epic 10 Retro Draft

## HIGH

1. **Epic snapshot / What worked substantively §1-2 — Story 10.1 finding count is numerically inconsistent.**
   The draft says `6 findings (4 HIGH + 2 MED + 1 LOW)` in multiple places, including the story table and the Story 10.1 propagation section. Those buckets total 7, and the Story 10.1 record enumerates `HIGH-1..4`, `MED-1..2`, `LOW-1`.
   **Concrete fix:** change every `6 findings (4 HIGH + 2 MED + 1 LOW)` reference to either `7 findings (4 HIGH + 2 MED + 1 LOW)` or `6 substantive findings + 1 LOW`, then use the same wording everywhere.

2. **Epic snapshot — new-file totals do not reconcile with the two story records.**
   The draft claims `4 new source files + 8 new test files + 2 new fixture files across the epic.` Story 10.1 adds 1 source file, 2 test files, 1 fixture file; Story 10.2 does the same. That reconciles to `2 source + 4 test + 2 fixture`, not `4 + 8 + 2`.
   **Concrete fix:** replace that sentence with `2 new source files + 4 new test files + 2 new fixture files across the epic`, or remove the sentence if the author does not want to restate per-story file totals.

3. **What didn’t §3 / Norms ratified this retro — `feedback_retro_debt_block_forward_progress` is retired without satisfying Epic 9’s sunset test.**
   Epic 9 defines the sunset condition as: retire only if Epic 10 ships Story 10.1 without Action #1 **and** retro debt does not compound, explicitly defined there as **fewer than 4 `❌` action-items** at Epic 10 close. This draft’s own follow-through table records `5 ❌` items.
   **Concrete fix:** do not mark the norm `RETIRED`. Change it to `still CANDIDATE` or `failed sunset test`, unless the draft first amends the Epic 9 criterion and explicitly cites that amendment as a source-level change.

4. **Action items for Epic 11 — the table fails the prompt’s SMART requirement.**
   The review prompt requires every action item to have an owner **and a concrete success criterion**. The table has owners, but no success-criterion column, and several rows remain open-ended (`OR formally retire`, `early`, `finally`, `promote ... to MEMORY.md`).
   **Concrete fix:** add a `Success criterion` column and give each row a binary completion test, e.g. exact file updated, exact command run, exact carry-over IDs closed, or exact workflow/job dispatched.

5. **Honest framing — the N=9 evidence base mixes incompatible counting units.**
   Commit `16ee936` already states the evidence base as `9 consecutive substantive cross-LLM reviews` across 7 retroactive stories plus Epic 10 Stories 10.1 and 10.2. The draft instead says `7 stories + 10.1 Claude + 10.1 kilo + 10.2 kilo = 10 reviews; conservative count = 9`, which double-counts Story 10.1 and invents an unsupported deduction for Story 9.3.
   **Concrete fix:** rewrite the proof in one unit only. Preferred: story-level counting, `7 retroactive story reviews + Story 10.1 + Story 10.2 = N=9`, matching `16ee936` and the two Epic 10 story records.

6. **Honest framing — the post-Phase-1 commit count is off by one for the command shown.**
   The draft says ``git rev-list --count 297c3c4..HEAD`` equals `20`. In this repo it returns `19`. `20` is the count for ``297c3c4~..HEAD``.
   **Concrete fix:** either change the command to ``git rev-list --count 297c3c4~..HEAD`` or keep ``297c3c4..HEAD`` and change the stated count to `19`.

## MED

1. **What worked substantively §1-2 / Norms ratified this retro — norm-ratification entries are missing required ratification metadata.**
   The prompt asks each “Norm to ratify” entry to state the operational invocation if applicable, the N evidence, and the next-test condition. `feedback_cross_story_upstream_lesson_propagation` lacks an operational invocation and both inline ratification entries lack a next-test condition.
   **Concrete fix:** add one sentence per ratified norm with the exact trigger and next falsifier, e.g. for cross-story propagation: invoke it during the next same-surface `Story N -> Story N+1` pre-create drift check; for third-LLM fallback: require the kilo command on the next dual-Claude/Codex degradation and record whether it yields substantive findings again.

2. **Closure — the summary count does not match the body.**
   The body lists 7 confirmed items in `Norms ratified this retro` plus 1 retired candidate, but the closure says `4 CONFIRMED norms`.
   **Concrete fix:** either summarize as `7 confirmed/reconfirmed items + 1 retired candidate`, or rename the summary unit to something narrower like `4 newly advanced norm decisions` and make that unit explicit.

## LOW

No LOW findings.
