# Story 14.5 — Claude Sonnet In-Session Findings (Tier 1a Fallback, v2)

**Reviewed:** `Skill.Get Activation Pass At K` dedicated keyword (C59 / DF-7.3-S1 closure)
**Date:** 2026-06-04
**Reviewer:** Claude Sonnet 4.6 — in-session fallback (CLI rate-limited, 0 bytes)  
**v2 note:** Second independent pass (same session, fresh context window). Adds MED-1 (dangling norm citation) + LOW-4 (test module docstring still stale for C59 guard count) not caught in the first pass. All HIGH/MED/LOW items from v1 re-verified.  
**Note:** `claude -p --model sonnet` produced 0 bytes (rate-limited per Stories 14-2/14-3/14-4 pattern). In-session review substituted per `feedback_integration_test_forcing_function` + Story 14.3 in-session precedent. All source files, tests, and retro citations read and re-derived from the actual repository.

---

## HIGH

### HIGH-1: libdoc keyword-name rendering match — PASS ✅

Re-ran empirically:
```
$ uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary /tmp/story-14-5-final-libdoc-probe.html
$ grep -oE '"name": ?"Skill\.[^"]+"' /tmp/story-14-5-final-libdoc-probe.html
"name": "Skill.Compare Discoverability"
"name": "Skill.Get Activation Pass At K"
$ grep -nE '@keyword\(name=' src/AgentEval/skills/library.py | grep -i "activation pass"
369:    @keyword(name="Skill.Get Activation Pass At K")
```

Rendered name `Skill.Get Activation Pass At K` == decorator name byte-for-byte. Multi-word post-dot immunity confirmed. ✅

### HIGH-2: predicate semantics correctness — PASS ✅

`_activation_pass_predicate` at `src/AgentEval/skills/_internal.py:335-352`:
```python
from AgentEval.skills.types import ActivationDecision
return isinstance(run.result, ActivationDecision) and run.result.activated
```

`ActivationDecision` fields verified: `activated: bool`, `reasoning: str`, `cost_usd: float`, `latency_seconds: float` (read from `src/AgentEval/skills/types.py:63-66`).

C59 regression-guard (`test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59`): `default → 0.0` ✅ + `fix → 1.0` ✅. Real-path guard (`test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path`): verifies `_extract_completeness` produces `"n/a"` for `ActivationDecision` results via the actual `Stat.Run N Times` pipeline. ✅

All 14 tests: PASSED.

### HIGH-3: no `predicate=` kwarg leaks into API — PASS ✅

```python
sig = inspect.signature(SkillsLibrary().get_activation_pass_at_k)
# API sig: (runs: 'list[KeywordRun]', k: 'int') -> 'float'
# 'predicate' not in sig.parameters: True
# lib.get_activation_pass_at_k(..., predicate=...) → TypeError
```
Verified programmatically. `test_get_activation_pass_at_k_does_not_accept_predicate_kwarg` PASSES. ✅

### HIGH-4: math delegation correctness (no reimplementation) — PASS ✅

Source of `get_activation_pass_at_k` (`library.py:417-421`):
```python
from AgentEval.skills._internal import _activation_pass_predicate
from AgentEval.stats._internal import _compute_pass_at_k
c = sum(1 for r in runs if _activation_pass_predicate(r))
return _compute_pass_at_k(c, len(runs), k)
```
No HumanEval math (`1 - C(n-c,k)/C(n,k)`) in this method. Delegates entirely. ✅

### HIGH-5: citation drift — PASS ✅

Re-derived from source:
- Epic 12 retro `L164` Action #5: `| 5 | **Close DF-7.3-S1 / C59**... EITHER add the docstring warning... OR ship the dedicated keyword...` ✅
- Epic 13 retro `L182` Action #5: `| 5 | **Close DF-7.3-S1 / C59 (Action #5 carried).** Ship Skill.Get Activation Pass At K keyword...` ✅
- `docs/phase-1-5-carry-overs.md` L83: `**DONE 2026-06-04** — Phase-1.5: Stat.Get Pass At K default predicate incompatible...` ✅
- Story 7.3 D-1: verified in `epic-7-retro-2026-05-25.md:58` + `7-3-devons-stacked-validation-recipe-integration-test.md` ✅

---

## MED

### MED-1: `feedback_libdoc_namespace_keyword_must_be_multiword` norm citation — INVESTIGATED, FALSE POSITIVE ✅

A second-pass (v2 hook) raised this as a potential dangling citation. Empirically verified:

```
ls ~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/ | grep libdoc
→ feedback_libdoc_namespace_keyword_must_be_multiword.md   EXISTS ✅

MEMORY.md entry: "memory file written Story 14.5 2026-06-04 closing phantom-norm debt (opus MED-1)"
```

The memory file exists, is indexed in MEMORY.md, and was formalized during Story 14.5 dev. The docstring citation at `library.py:413` is accurate. **No fix required.**

---

## LOW

### LOW-1: Test count mismatch — documentation inaccuracy (`feedback_honest_framing`)

**File:** `docs/phase-1-5-carry-overs.md:83` + `_bmad-output/implementation-artifacts/sprint-status.yaml`

The C59 closure column in `carry-overs.md` and the sprint-status comment both claim "13 unit tests (4 predicate + 8 keyword behaviour + 1 C59 regression-guard test)". The actual file has **14 tests**:

```
$ pytest tests/unit/skills/test_activation_pass_at_k.py -v → 14 passed
```

The 14th test (`test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path`) is a stronger C59 regression-guard exercising the real `Stat.Run N Times` → `_extract_completeness` production path. Its docstring attributes it to "Codex MED-2 (Story 14.5 cross-LLM review)" — pre-emptively added by the dev agent before formal review.

**Severity:** LOW — implementation over-delivers (14 > 13). No correctness impact. But `feedback_honest_framing` requires accurate numeric claims in permanent record documents.

**Resolution:** Partially resolved in working tree — `carry-overs.md` L83 and `sprint-status.yaml` were pre-emptively updated to "14 unit tests". However, the test file's own module docstring (`tests/unit/skills/test_activation_pass_at_k.py:23`) is still stale — see LOW-4 below.

### LOW-2: `_internal.py:339-342` docstring conflates two deferral mechanisms

**File:** `src/AgentEval/skills/_internal.py:339-342`

Docstring says: "Local imports defer the dependency on `stats.types.KeywordRun` + `skills.types.ActivationDecision` until call time." Only `ActivationDecision` is deferred via a local call-time import. `KeywordRun` is handled via `if TYPE_CHECKING:` (never imported at runtime — type-only annotation deferral via `from __future__ import annotations`). The docstring conflates the two mechanisms.

**Severity:** LOW — functionally correct. Deferred; fix in a later PR touching this module.

### LOW-4: Test module docstring still says "C59 regression-guard (1)" — residual stale artifact

**File:** `tests/unit/skills/test_activation_pass_at_k.py:23`

The module docstring at lines 15-25 says:
```
- C59 regression-guard (1): default Stat.Get Pass At K returns 0.0 on all-activated
  runs → empirically proves the silent-zero failure mode the dedicated keyword closes.
```

The actual file has **2 C59 regression-guard tests** (4+8+2=14 total, not 13). LOW-1 noted `carry-overs.md` and `sprint-status.yaml` were updated to 14, but missed that the test file's own docstring was not updated. The correct text should be:
```
- C59 regression-guard (2): (a) hand-built KeywordRun objects; (b) real-path via
  Stat.Run N Times → _extract_completeness, added per Codex MED-2.
```

**Severity:** LOW — documentation-only; all 14 tests pass correctly. **Applied as v2 patch** to `tests/unit/skills/test_activation_pass_at_k.py:23`.

### LOW-3: Process — Codex session truncated without structured findings

**File:** `_bmad-output/cross-llm-reviews/story-14-5-codex-findings.md` (135KB terminal log)

Codex ran extensive verification and all checks passed, but the session ended before writing a structured findings summary. For future stories, add to the Codex review prompt: "When finished, **Write** your structured HIGH/MED/LOW findings to `<path>`" (mirrors kilo `--auto` pattern).

---

## Reviewer chain status

| Tier | Reviewer | Status | Findings |
|---|---|---|---|
| 1a | Claude CLI sonnet | empty / rate-limited | — |
| 1b | Claude CLI opus | empty / rate-limited | — |
| 1a fallback | Claude Sonnet 4.6 in-session v1+v2 | complete | 0 HIGH, 0 MED, 4 LOW (MED-1 false positive) |
| 2 | Codex CLI | ran; no structured summary | 0 HIGH inferred from evidence |
| 3 | kilo/minimax-M2.7 | complete | 0 HIGH, 0 MED, 3 LOW |

**Combined final: 0 HIGH, 0 MED (MED-1 false positive), 4 LOW.**
- MED-1: false positive — memory file exists, citation accurate.
- LOW-1: resolved pre-emptively (carry-overs.md + sprint-status.yaml already say "14 unit tests").
- LOW-4 (test module docstring "C59 regression-guard (1)" → "(2)"): applied as v2 patch.
- LOW-5 (sprint-status gate count 2003 → 2004, +18 → +19): applied as v2 patch.
- LOW-2 and LOW-3 deferred.

---

## Verdict

Story 14.5 passes adversarial review with 0 HIGH, 0 MED. The C59 closure is complete and correct. The dedicated `Skill.Get Activation Pass At K` keyword uses the correct hard-coded predicate, delegates math to `_compute_pass_at_k`, exposes no `predicate=` kwarg, and ships two C59 living regression tests (one hand-built, one via real `Stat.Run N Times` path). Final gate: **pytest 2004+32** (confirmed by re-run); ruff+mypy clean; catalog-gate EXIT 0.
