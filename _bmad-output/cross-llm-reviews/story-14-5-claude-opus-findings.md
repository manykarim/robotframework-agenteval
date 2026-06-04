# Story 14.5 — Cross-LLM Adversarial Review (Tier 1: Claude Opus)

**Reviewer:** Claude Opus (Tier 1)
**Date:** 2026-06-04
**Scope:** `Skill.Get Activation Pass At K` dedicated keyword — C59 / DF-7.3-S1 closure
**Verdict:** Implementation is sound. **0 HIGH, 1 MED, 3 LOW.** All HIGH-class checklist items verified CLEAN with empirical commands. The one MED is a numeric-count drift in persistent closure docs; LOWs are framing/precision nits.

---

## Verification log (commands run)

| Check | Command | Result |
| --- | --- | --- |
| libdoc render exit | `uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary /tmp/...html` | EXIT 0 ✓ |
| libdoc name byte-match | `grep -oE '"name": ?"Skill\.[^"]+"'` | `"name": "Skill.Get Activation Pass At K"` exact ✓ |
| new + baseline tests | `pytest test_activation_pass_at_k.py test_activation_decision.py` | 29 passed ✓ |
| no predicate kwarg | `inspect.signature(...).parameters` | `['runs', 'k']` ✓ |
| catalog gate | `scripts/check-catalog-references.py --all-tracked` | EXIT 0 ✓ |
| math delegation | `grep _compute_pass_at_k` in method body | present; no raw HumanEval math leaked ✓ |
| D-5 docstring unchanged | `git diff HEAD~5 -- stats/library.py` | 0 lines changed ✓ |
| libdoc HTML regen | `grep -c "Skill.Get Activation Pass At K" docs/keywords/SkillsLibrary.html` | 1 ✓ |
| ruff | `ruff check` (3 files) | All checks passed ✓ |
| mypy | `mypy` (2 src files) | Success ✓ |
| conventions suite | `pytest tests/unit/conventions/` | 272 passed ✓ |
| Epic 12 L164 Action #5 | `sed` | content matches "Close DF-7.3-S1 / C59" ✓ |
| Epic 13 L182 Action #5 | `sed` | content matches "Close DF-7.3-S1 / C59 (carried)" ✓ |
| C59 row status | `grep docs/phase-1-5-carry-overs.md` | "DONE 2026-06-04" + FULL closure ✓ |

---

## HIGH

**None.** Every HIGH-class checklist item passed empirical re-verification:

- **libdoc keyword-name rendering match** — `Skill.Get Activation Pass At K` renders byte-for-byte against the `@keyword(name=...)` decorator (`src/AgentEval/skills/library.py:369`). The Change Log empirical claim holds. (Sibling `Skill.Compare Discoverability` also renders clean, corroborating the multi-word-immunity finding.)
- **predicate semantics** — `_activation_pass_predicate` (`src/AgentEval/skills/_internal.py:335`) returns `True` iff `isinstance(run.result, ActivationDecision) and run.result.activated`; short-circuit safe on `None`/non-AD results. Both regression-guard tests pass: default `Stat.Get Pass At K` → 0.0 on 5 activated runs; dedicated keyword → 1.0.
- **no `predicate=` kwarg leak** — signature is `['runs', 'k']`; docstring + stability surface both document "no `predicate=` kwarg by design"; test asserts `TypeError` on the kwarg.
- **math delegation** — `get_activation_pass_at_k` (`library.py:420-421`) is `c = sum(...); return _compute_pass_at_k(c, len(runs), k)`. No HumanEval estimator reimplementation. ValueError validation delegated to `_compute_pass_at_k` (`stats/_internal.py:192`).
- **citation drift** — Epic 12 retro L164 Action #5, Epic 13 retro L182 Action #5, C59 row status, and Story 7.3 D-1 origin all re-derived from source and match.

---

## MED

### MED-1 — Test-count drift: persistent closure docs say "13 unit tests"; file has 14

`tests/unit/skills/test_activation_pass_at_k.py` contains **14** `def test_*` functions (machine-counted: `grep -cE "^def test_"` → 14), not 13. The 14th — `test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path` (L222) — was added in response to "Codex MED-2" during this review chain (it exercises the real `Stat.Run N Times` → `_extract_completeness` path, a genuinely stronger regression guard than the hand-built one). But the count was never reconciled in the persistent artifacts:

- `docs/phase-1-5-carry-overs.md:83` (C59 **closure row — the artifact of record**): *"13 unit tests (4 predicate + 8 keyword behaviour + 1 C59 regression-guard test...)"*
- `_bmad-output/.../14-5-*.md` spec L213, L299, L322, and Change Log L338: all say "13".

Per `feedback_honest_framing` (counts machine-verified before commit), a count in the canonical closure row should be exact even when the drift is conservative (under-counting). **Fix:** update the C59 row + spec to **"14 unit tests (4 predicate + 8 keyword behaviour + 2 C59 regression-guards — hand-built symptom test + real-`run_n_times`-path test)"**. The actual breakdown is 4 + 8 + 2 = 14.

---

## LOW

### LOW-1 — `feedback_libdoc_namespace_keyword_must_be_multiword` cited as "ratified norm" but never memorialized + was N=1 candidate-confirmed

The docstring (`library.py:413`) and C59 row (`phase-1-5-carry-overs.md:83`) call this a "ratified norm." Two precision issues:

1. **No memory file exists.** `ls ~/.claude/.../memory/ | grep -i multiword` and a body-grep both return nothing. Sibling norms ratified in the same Epic 12 retro (e.g. `feedback_monkeypatch_decorator_chain_walk`, retro item #4) were explicitly *"Memorialized at .../memory/...md + indexed in MEMORY.md"*; this one (retro item #6) was not. The cited target — Epic 12 retro 2026-06-01 **L223** — does exist and is accurate, so this is not a broken citation, but the norm lives only in the retro, not in the auto-loaded memory set.
2. The retro records it as **"CANDIDATE → CONFIRMED at N=1 case"** with an explicit *"Next-test: re-confirm at Epic 13 retro; downgrade to candidate-removed if no new namespace-prefixed keyword surfaces in Epic 13."* Flatly calling it "ratified" slightly overstates that conditional status.

**Fix (pick one):** memorialize the memory file + index it (closes the gap the docstring implies is already closed), OR soften the docstring/C59 wording to "per the Epic 12 retro L223 multi-word-keyword finding" rather than "ratified norm."

### LOW-2 — Spec / review-prompt name convention tests that don't exist

The review checklist (and the spec's process notes) reference `test_citation_bidirectional_consistency` and `test_example_block_dryruns_clean`; neither file exists under `tests/unit/conventions/`. The real files are `test_keyword_name_idiom.py`, `test_docstring_examples_dryrun.py`, and `test_docstring_browser_style.py` (the "2 mid-dev convention fixes" map to the latter two). No shipped-code impact — the full conventions suite passes 272/272 — but the spec's named test IDs are imprecise and would mislead a future reader trying to locate them. **Fix:** correct the test names in the spec's process notes.

### LOW-3 — Docstring Notes section verbosity

`get_activation_pass_at_k` docstring Notes carries 6 bullets (`library.py:394-415`), two of which (the norm-compliance bullet + the "closes Epic 12/13 Action #5" bullet) are provenance rather than user-facing contract. Optional: trim to the 3 operator-relevant bullets (predicate semantics, no-kwarg rationale, sibling keyword) and move provenance to the spec/Change Log. Style only.

---

## Notes on items checked and found correct (no action)

- **D-5 docstrings UNCHANGED** — `git diff HEAD~5 -- src/AgentEval/stats/library.py` = 0 lines; the only `-` line in `skills/library.py` is an import consolidation (`from typing import TYPE_CHECKING, Any` at L72 — `Any` still imported; mypy clean).
- **Honest framing of "first multi-word dev-time empirical test"** — defensible. The C59 row itself hedges correctly ("re-confirms ... already observable across ~10 pre-existing multi-word keywords"); the "first to ship + smoke-test in the same dev cycle" framing is accurate given Story 13.5's `Skill.Compare Discoverability` predates the Story 14.1 dev-time-libdoc-smoke mechanism.
- **Edge cases** — `runs=[]`, `k=0`, `k>n`, all-`None` results, mixed-type results all verified via passing tests + delegated `_compute_pass_at_k` validation.
- **Stability surface** — `### Skill Activation Pass@k Surface` section (`docs/contracts/stability-surface.md:134`) is complete: RF keyword + Python method + Tier-1 + delegation + no-kwarg rationale + sibling cross-reference + `provisional` label.
