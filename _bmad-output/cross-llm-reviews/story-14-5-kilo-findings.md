# Story 14.5 Kilo/M2.7 Findings — Tier 3 Fallback Review

**Reviewed:** `Skill.Get Activation Pass At K` dedicated keyword (C59 / DF-7.3-S1 closure)
**Date:** 2026-06-04
**Reviewer:** kilo/minimax-M2.7 (Tier 3 fallback)

---

## HIGH

### HIGH-1: libdoc keyword-name rendering match — PASS ✅

- **Check:** `uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary /tmp/story-14-5-libdoc-probe.html` exits 0.
- **Check:** `"name": "Skill.Get Activation Pass At K"` present in libdoc JSON keywords array.
- **Check:** `@keyword(name="Skill.Get Activation Pass At K")` at `src/AgentEval/skills/library.py:369` matches byte-for-byte.
- **Result:** PASS. Decorator name === rendered name. Multi-word post-dot immunity confirmed empirically.

---

### HIGH-2: predicate semantics correctness — PASS ✅

- **File:** `src/AgentEval/skills/_internal.py:352`
- **Code:** `return isinstance(run.result, ActivationDecision) and run.result.activated`
- **Edge cases verified:**
  - `result is None` → `isinstance(None, ActivationDecision)` is `False` → short-circuits, `.activated` never accessed. ✅
  - `result` is non-ActivationDecision (string, dict, AgentRunResult) → `isinstance` returns `False`. ✅
  - `ActivationDecision(activated=True)` → `isinstance` True + `.activated` True → returns `True`. ✅
  - `ActivationDecision(activated=False)` → `isinstance` True + `.activated` False → returns `False`. ✅
- **C59 regression-guard test:** `test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59` PASSES. Confirmed: `stats.get_pass_at_k(runs, k=1) == 0.0` (bug present) and `skills.get_activation_pass_at_k(runs, k=1) == 1.0` (fix works). ✅
- **Real-path regression test:** `test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path` PASSES. Exercises `Stat.Run N Times` → `_extract_completeness` pipeline end-to-end. ✅

---

### HIGH-3: no `predicate=` kwarg leaks into API — PASS ✅

- **Check:** `inspect.signature(lib.get_activation_pass_at_k).parameters` — no `predicate` key. ✅
- **Check:** `lib.get_activation_pass_at_k(runs, k=1, predicate=lambda r: True)` raises `TypeError`. ✅ (verified by `test_get_activation_pass_at_k_does_not_accept_predicate_kwarg`)
- **Docstring explicitly states:** "No `predicate` kwarg by design — removing the predicate-customization pitfall is the whole purpose." (`library.py:405-407`) ✅
- **Stability surface entry documents:** "no `predicate=` kwarg by design" rationale. (`stability-surface.md:138`) ✅

---

### HIGH-4: math delegation correctness (no reimplementation) — PASS ✅

- **Check:** `grep -nE "_compute_pass_at_k" src/AgentEval/skills/library.py` returns 4 hits (L388 docstring ref, L396 docstring ref, L418 import, L421 call). ✅
- **Check:** No raw HumanEval math (`1 - C(n-c, k) / C(n, k)` or equivalent) in `get_activation_pass_at_k`. ✅
- **Check:** `from AgentEval.stats._internal import _compute_pass_at_k` at `library.py:418` — delegated import. ✅
- **Check:** `return _compute_pass_at_k(c, len(runs), k)` at `library.py:421` — single call, no local reimplementation. ✅
- **ValueError validation:** delegated entirely to `_compute_pass_at_k` (not duplicated in the keyword). ✅

---

### HIGH-5: citation drift — PASS ✅

| Citation | Claimed location | Actual content | Status |
|---|---|---|---|
| Epic 12 retro Action #5 | L164 | `\| 5 \| **Close DF-7.3-S1 / C59**...` | ✅ MATCH |
| Epic 13 retro Action #5 | L182 | `\| 5 \| **Close DF-7.3-S1 / C59 (Action #5 carried)...` | ✅ MATCH |
| C59 row | `phase-1-5-carry-overs.md` L83 | `**DONE 2026-06-04** — Phase-1.5: Stat.Get Pass At K default predicate...` | ✅ MATCH |
| Story 7.3 D-1 | `7-3-*.md` L37-40 + `epic-7-retro-2026-05-25.md` L58 | `Stat.Get Pass At K default predicate...returns 0.0 for ActivationDecision` | ✅ MATCH |
| Story 12.2 libdoc bug | `epic-12-retro-2026-06-01.md` L116-125 | Libdoc auto-split for single-word post-dot names (`Judge.Calibrate` → `Judge. Calibrate`) | ✅ MATCH |
| Epic 12 retro L223 multi-word immunity | `epic-12-retro-2026-06-01.md` L223 | Norm `feedback_libdoc_namespace_keyword_must_be_multiword` ratified | ✅ MATCH |

All line citations re-derived from source. Zero drift detected.

---

## MED

### MED-1: process discipline — PASS ✅

- `uv run python scripts/check-catalog-references.py --all-tracked` → EXIT 0. ✅
- `uv run ruff check src/ tests/` → "All checks passed!". ✅
- `uv run mypy src/AgentEval/skills/library.py src/AgentEval/skills/_internal.py` → "Success: no issues found". ✅
- `uv run pytest tests/unit/skills/test_activation_pass_at_k.py` → 14 passed in 0.44s. ✅
- Stability surface entry at `stability-surface.md:134-138`: complete (RF keyword + Python method + Tier-1 + delegation + no-kwarg rationale). ✅
- C59 row at `phase-1-5-carry-overs.md L83`: Owner set to `Story 14.5 (closed 2026-06-04)` with FULL closure note + implementation refs. ✅
- Sprint status at `sprint-status.yaml L166`: `14-5-*: done` with FULL-closure note. ✅

---

### MED-2: test-name vs assertion-body match — PASS ✅

All 14 tests verified:

| Test | Promise | Assertion | Match |
|---|---|---|---|
| `test_predicate_true_when_activation_decision_activated_true` | predicate TRUE on activated AD | `_activation_pass_predicate(run) is True` | ✅ |
| `test_predicate_false_when_activation_decision_activated_false` | predicate FALSE on not-activated AD | `_activation_pass_predicate(run) is False` | ✅ |
| `test_predicate_false_when_result_not_activation_decision` | predicate FALSE on non-AD result | `_activation_pass_predicate(run) is False` | ✅ |
| `test_predicate_false_when_result_is_none` | predicate FALSE on None result | `_activation_pass_predicate(run) is False` | ✅ |
| `test_get_activation_pass_at_k_returns_1_0_when_all_activated_k_equals_n` | 5/5 activated → Pass@5 = 1.0 | `lib.get_activation_pass_at_k(runs, k=5) == 1.0` | ✅ |
| `test_get_activation_pass_at_k_returns_0_0_when_none_activated` | 0/5 activated → Pass@1 = 0.0 | `lib.get_activation_pass_at_k(runs, k=1) == 0.0` | ✅ |
| `test_get_activation_pass_at_k_matches_humaneval_math_for_mixed_runs` | 3/5 activated → Pass@1 = 0.6 | `lib.get_activation_pass_at_k(runs, k=1) == pytest.approx(0.6)` | ✅ |
| `test_get_activation_pass_at_k_raises_value_error_when_k_lt_1` | k=0 raises ValueError | `pytest.raises(ValueError)` | ✅ |
| `test_get_activation_pass_at_k_raises_value_error_when_k_gt_len_runs` | k=4 on 3 runs raises ValueError | `pytest.raises(ValueError)` | ✅ |
| `test_get_activation_pass_at_k_raises_value_error_when_runs_empty` | empty runs raises ValueError | `pytest.raises(ValueError)` | ✅ |
| `test_get_activation_pass_at_k_ignores_non_activation_results` | mixed-type runs → c=2, n=5, Pass@1=0.4 | `lib.get_activation_pass_at_k(runs, k=1) == pytest.approx(0.4)` | ✅ |
| `test_get_activation_pass_at_k_does_not_accept_predicate_kwarg` | no predicate kwarg | `assert "predicate" not in sig.parameters` + `pytest.raises(TypeError)` | ✅ |
| `test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59` | default → 0.0, new keyword → 1.0 | `assert default_result == 0.0` + `assert fixed_result == 1.0` | ✅ |
| `test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path` | real pipeline produces n/a completeness + 0.0 default + 1.0 fix | 3 assertions on real-path runs | ✅ |

---

### MED-3: script edge cases — PASS ✅

| Edge case | Expected | Verified |
|---|---|---|
| `runs=[]` | `ValueError` via `_compute_pass_at_k` | `test_get_activation_pass_at_k_raises_value_error_when_runs_empty` PASS |
| `k=0` | `ValueError` | `test_get_activation_pass_at_k_raises_value_error_when_k_lt_1` PASS |
| `k > len(runs)` | `ValueError` | `test_get_activation_pass_at_k_raises_value_error_when_k_gt_len_runs` PASS |
| all `runs[i].result is None` | `c=0` → `_compute_pass_at_k(0, n, k)` → 0.0 | implicit via `test_predicate_false_when_result_is_none` + `test_get_activation_pass_at_k_returns_0_0_when_none_activated` |
| `isinstance` short-circuit on non-AD | `.activated` never accessed if `isinstance` returns False | verified in `test_predicate_false_when_result_not_activation_decision` + `test_predicate_false_when_result_is_none` |

---

## LOW

### LOW-1: docstring Notes section verbosity

- **File:** `src/AgentEval/skills/library.py:394-416`
- **Notes section has 6 bullets.** Per review criteria: "Could be tighter (3-4 critical ones)."
- **Assessment:** All 6 bullets are substantive (PRD FR27 citation, predicate rationale with C59 attribution, custom-predicate operators note, no-kwarg rationale, sibling keyword reference, Epic 12/13 retro closure note). None is clearly discardable. LOW severity; no fix required.

### LOW-2: C59 row acceptance criteria verbosity

- **File:** `docs/phase-1-5-carry-overs.md L83`
- **Acceptance criteria column is a single verbose paragraph.** Per review criteria: "Could be split into bullets."
- **Assessment:** Row is correctly closed with full attribution. The verbosity is a style preference, not a correctness issue. LOW severity; no fix required.

### LOW-3: multi-word immunity finding could be promoted to memory

- **Note:** The empirical finding that "multi-word post-dot keyword names are immune to the Story 12.2 libdoc auto-split bug" is a project-level insight worth capturing in `~/.claude/projects/.../memory/feedback_libdoc_multiword_immunity.md`.
- **Assessment:** Out of scope for Story 14.5 (flagged in review criteria). No action required.

---

## Summary

**All HIGH checks: PASS (5/5)**
**All MED checks: PASS (3/3)**
**LOW items: 3 (all style/process, no fixes required)**

**Verdict:** Story 14.5 implementation is sound. No blockers. The C59 closure is complete and correct — the dedicated keyword properly addresses the 6-epic-old silent-zero failure mode with the correct hard-coded predicate, no API leakage, and a living regression guard that will fail if the default predicate ever changes.

---

*Findings produced by kilo/minimax-M2.7 (Tier 3 fallback reviewer) on 2026-06-04.*
