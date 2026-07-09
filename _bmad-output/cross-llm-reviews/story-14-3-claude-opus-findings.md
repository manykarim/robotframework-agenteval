# Story 14.3 — Claude Opus (Tier 1b) adversarial review findings — CONSOLIDATED

**Reviewer:** Claude Opus 4.8, in-session (Tier-1b substitute). The background
`claude -p --model {opus,sonnet}` CLI invocations both returned **0 bytes**
(`Warning: no stdin data received in 3s` in both `.stderr.log` — the documented
Claude-CLI empty-output/stdin failure mode). Codex (Tier 2) produced a 1.4 MB
file dominated by prompt/diff echo but DID run the harness (its `.stderr.log`
shows the real `FAIL …::block-0 EXIT 1` lines). Per CLAUDE.md 3-tier chain step 3,
both Claude tiers degrading → produce findings directly + escalate to Tier 3
(kilo). This file consolidates two independent in-session Opus passes (the
detailed probe log is preserved at `story-14-3-opus-inline-findings.md`).

**Method:** every finding empirically re-derived — harness executed (17 passed /
16 skipped), each `_KNOWN_BROKEN_BLOCKS` entry dryrun'd to confirm its real
failure, classification probed, retro citation lines grep'd, catalog gate run
(EXIT 0).

**Bottom line:** **no code-correctness defect** — the
extraction/classify/wrap/dryrun machinery is sound and the skip-list is *exact*
(4 genuinely fail, 4 genuinely pass, zero unaccounted, zero stale). The findings
are **closure-framing / citation / count drift** — precisely the class this chain
targets. The single most load-bearing issue: **the carryover chain is marked
fully closed, but the retro's own "≥6 passing" bar is unmet (4 pass).**

---

## HIGH

### HIGH-1 — Retro "≥6 **passing**" bar is genuinely UNMET; 3-epic carryover closure is overclaimed
**Files:** spec Change Log + Retro-debt mini-pass + C64 closure note; `docs/phase-1-5-carry-overs.md` C64 row.
**Evidence (re-derived from source):**
- Epic 11 retro **L157** Action #7: "…returns **≥6 passed** at HEAD CI."
- Epic 12 retro L168 Action #9: "**≥6** fenced robotframework blocks **pass** dryrun in CI."
- Epic 13 retro L186 Action #9: "ships with **≥6** fenced blocks **tested**."

Empirical dryrun over `_ELIGIBLE_BLOCKS`: **4 pass** (02::0, 04::0, 04::1, 06::0),
**4 skip-listed-broken** (03::0, 05::0, 05::1, 07::0). Only **4** blocks pass —
below the ≥6 bar Epic 11 + Epic 12 set in *passing* terms. The story marks all
three actions "✅ Closing this" and C64 "**DONE** 2026-06-04".
**Why it matters:** per `feedback_honest_framing`, the harness *shipping* is one
half of each criterion; the "≥6 pass" half is deferred to DF-14.3-S1 and is not
satisfied. This is the evaluative-vs-factual misframing class the chain exists to
catch.
**Fix:** reframe as **partial** closure — C64 + the three retro actions should read
"harness ships; full ≥6-passing closure blocked on DF-14.3-S1 (fix-recipe-rot)"
rather than DONE/✅-fully-closed.

### HIGH-2 — AC-14.3.3 "≥6→≥4" amendment conflates *eligible* with *passing*; the original AC was already met
**Files:** spec AC-14.3.3 (L97-101) + Debug Log amendment note (L227); `test_all_recipes_dryrun.py` L173-229.
**Evidence:** AC-14.3.3 as written measures "≥6 dryrun-**eligible** blocks"
(impl note: `assert len(_collect_eligible_blocks()) >= 6`). There are **8
eligible** → the original AC is satisfied **without any amendment**. The dev
instead lowered ≥6→≥4 *and silently switched the measured quantity* from
*eligible* to *passing* (`_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT -
len(_KNOWN_BROKEN_BLOCKS)`). So the amendment narrative relaxes a threshold the
story's own AC never required, while the bar that actually fails is the retro's
"≥6 passing" (HIGH-1).
**Fix:** keep AC-14.3.3's eligible bar (8 ≥ 6, unchanged — no amendment) and track
*passing* as a separate, explicitly-named metric honestly reporting 4 < 6 as a
known gap tied to DF-14.3-S1.

### HIGH-3 — Citation drift: Epic 11 retro Action #7 is at L157, not L158
**Files:** spec L23, L68, L204, L252 (review prompt L36/L40 inherit the lineage).
**Evidence:** `epic-11-retro-2026-05-27.md:157` = Action #7 (C64 recipe CI);
**`:158` = Action #8** (Story 7.1 Change Log backfill). The spec cites "Epic 11
retro **L158** Action #7" — right action number, wrong line, points at the wrong
action. Epic 12 L168 + Epic 13 L186 re-derived and **confirmed correct**.
**Why it matters:** exact off-by-one citation class `feedback_citation_drift_first_class`
exists to catch; spec L-1 claims "citations re-derived from source via grep
before writing" — falsified for this ref.
**Fix:** `L158` → `L157` at spec L23, L68, L204, L252.

---

## MED

### MED-1 — Claimed `extract_robotframework_blocks` unclosed-block `ValueError` path has ZERO test coverage
**File:** `test_all_recipes_dryrun.py` L120-123 (raise) vs suite.
AC-14.3.1(2) + docstring claim "unclosed blocks raise `ValueError`," and the
review prompt's diff-parser-fidelity item #2 explicitly asks for a synthetic-md
unclosed-block test. The only `pytest.raises(ValueError)` cases (L421/L427) cover
`wrap_block_for_dryrun`'s "not dryrun-eligible" path, not the parser's unclosed
branch.
**Fix:** add `test_extract__unclosed_block_raises_value_error` — write a synthetic
`.md` with a dangling ` ```robotframework ` to `tmp_path`, assert
`pytest.raises(ValueError, match="Unclosed")`.

### MED-2 — Numeric drift: "13 parametrized tests" / "10 helper" vs actual 20 / 11 (33 total)
**Files:** spec Task 1 (L156 "33 parametrizations"), File List (L258), Change Log (L274) all say "13 parametrized tests"; Completion Notes "10 helper".
**Evidence:** `pytest` collects **33** = **20** parametrized `test_recipe_block_dryruns`
IDs (one per block) + **2** negative + **11** helper-unit. "13 parametrized" is
wrong (it's 20); "10 helper" undercounts by one (11). `13+2+10=25 ≠ 33`.
**Fix:** standardize to "**20** parametrized block cases + 2 negative + **11**
helper = **33** tests."

### MED-3 — VALIDATION-CEILING line missing (ratified `feedback_dogfood_validation_ceiling`)
**File:** harness module docstring L15-47.
**Evidence:** 1 of the 4 passing blocks (`06-custom-protocol-adapter.md::block-0`)
is test-cases-only and is wrapped with a *synthetic* `Library AgentEval`. Its
green validates the *harness's* import + keyword resolution + arg arity — NOT the
recipe's *documented* import line and NOT runtime values (`adapter=my_adapter` is
never checked to exist). The docstring describes the wrap mechanic but never
frames the ceiling. The ratified norm requires every dogfood/validation harness to
carry a top-of-file VALIDATION-CEILING statement.
**Fix:** add a `VALIDATION-CEILING:` paragraph stating (a) dryrun verifies
keyword-name resolution + arg arity only, never runtime/values/network; (b)
test-cases-only blocks are validated against a synthetic `Library AgentEval`, so a
wrong *documented* import in recipe prose is out of scope.

### MED-4 — `feedback_executable_doc_precheck` norm not annotated despite Story 14.3 being its CI automation
**File:** `~/.claude/.../memory/feedback_executable_doc_precheck.md` (no 14.3 ref).
Story 14.3 IS the CI automation of this Epic-7 norm; the memory file still
describes only the manual procedure.
**Fix:** one-line note — "CI-enforced as of Story 14.3 via
`tests/integration/recipes/test_all_recipes_dryrun.py` for `docs/recipes/*`
robotframework blocks; manual precheck remains the authoring-time first line."

---

## LOW

- **LOW-1** — `_KNOWN_BROKEN_BLOCKS` reason for recipe-3 block-0 ("…`Library
  AgentEval` only") can be misread as harness-wrapper blame; the block has its own
  Settings header so it is NOT wrapped. Tighten: "recipe-3 imports bare `Library
  AgentEval` but calls `MCP.`-namespaced keywords; needs `…MCPLibrary WITH NAME
  MCP` (cf. recipes 5 & 7 block-0)."
- **LOW-2** — Module docstring split: states the eligible count without the live
  4-pass / 4-skipped reality. One-line "(4 PASSING in CI + 4 skipped per
  `_KNOWN_BROKEN_BLOCKS`)" aligns it.
- **LOW-3** — Module-load `assert` (L222) duplicates the dedicated test
  `test_collect_passable_blocks_meets_amended_ac_14_3_3_threshold` (L443) AND the
  unclosed-fence `ValueError` runs at import — either firing surfaces as a cryptic
  whole-module collection error that also takes down the 11 healthy unit tests.
  Prefer the dedicated test; soften the module-load assert.
- **LOW-4** — `test_extract…__counts_match_grep` (L375) shells out to `grep`,
  coupling a unit test to a system binary with BRE semantics. Optional: also assert
  against a pure-Python count.

---

## Verified CLEAN (probed, no finding)

- **Skip-list completeness** — dryrun over all 8 eligible: 4 skip-listed genuinely
  FAIL, 4 non-listed genuinely PASS; zero unaccounted failures, zero stale entries.
  Each reason string names the *actual* root cause (recipe-3 namespace, recipe-5
  `arguments=` dict-coercion, recipe-5 fixture dep, recipe-7 arity drift). ✓
- **Negative-guard fidelity (Story 13.5 HIGH-B)** — broken fixture ships `Library
  AgentEval` (NOT `Collections`) + `Get From Dictionary`; assertion on exact
  `No keyword with name 'Get From Dictionary'` holds empirically. Name promises
  rejection-of-class, body delivers. ✓
- **Catalog gate (Story 14.2 self-application)** — `check-catalog-references.py
  --all-tracked` EXIT 0; 4 inline `DF-14.3-S1` refs resolve to the deferred-work row. ✓
- **Fence counts (D-1)** — 20 total / 8 eligible / 2 settings-only / 10 fragment,
  matches `grep -cE '^```robotframework'`. ✓
- **Self-recursion (L-2)** — harness globs `docs/recipes/*.md` only, never `tests/`. ✓
- **Amendments 2+3** — DF-14.3-S1 row present; `wrap_block_for_dryrun` settings-only
  + fragment both raise `ValueError` (tests pass). ✓

---

## Triage recommendation

Apply **HIGH-1 / HIGH-2 / HIGH-3** before `done` — all cheap doc-only edits; HIGH-1
+ HIGH-2 go to the core claim that the carryover chain is closed. **MED-1** is a real
coverage gap on claimed behavior (add the test). MED-2/3/4 are doc/norm hygiene.
LOWs optional. No harness code-correctness defect.
