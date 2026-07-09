# Story 14.5 Cross-LLM Adversarial Review — `Skill.Get Activation Pass At K` (C59 closure)

You are an adversarial code reviewer. Be critical. Look for real bugs, not surface-level style issues.

Working directory: /home/many/workspace/robotframework-agenteval

## What was shipped

- **NEW method:** `SkillsLibrary.get_activation_pass_at_k(runs, k) -> float` at `src/AgentEval/skills/library.py:369`. `@keyword(name="Skill.Get Activation Pass At K") + @tier(1)`. Hard-coded predicate `isinstance(run.result, ActivationDecision) and run.result.activated`. No `predicate=` kwarg by design.
- **NEW helper:** `_activation_pass_predicate(run) -> bool` at `src/AgentEval/skills/_internal.py:332` with deferred `ActivationDecision` import (avoids circular).
- **NEW file:** `tests/unit/skills/test_activation_pass_at_k.py` — 14 unit tests (4 predicate semantics + 8 keyword behaviour + 1 C59 regression-guard + 1 real-path Stat.Run N Times regression-guard — LIVING TESTS).
- **Modified:** `docs/contracts/stability-surface.md` — NEW `### Skill Activation Pass@k Surface (Phase-2.5 — Story 14.5 / C59 closure)` section at line 134.
- **Modified:** `docs/phase-1-5-carry-overs.md` — C59 row closed with `DONE 2026-06-04` prefix + full attribution.
- **Modified:** `docs/keywords/SkillsLibrary.html` — libdoc regenerated.
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml` — `14-5-*: done`.

## Source code (read these files adversarially)

### src/AgentEval/skills/library.py lines 365-422

```python
    # ----------------------------------------------------------------- #
    # FR27 specialised — Story 14.5 / C59 / DF-7.3-S1 closure             #
    # ----------------------------------------------------------------- #

    @keyword(name="Skill.Get Activation Pass At K")
    @tier(1)
    def get_activation_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
    ) -> float:
        """[Tier 1 — Deterministic] HumanEval Pass@k unbiased estimator over activation-decision trials.

        Specialised sibling of ``Stat.Get Pass At K`` with the
        activation-decision pass-predicate HARD-CODED in. Returns
        ``float ∈ [0, 1]`` — same HumanEval estimator math as
        ``Stat.Get Pass At K`` (delegates to the same internal helper).

        | =Arguments= | =Description= |
        | ``runs`` | ``list[KeywordRun]`` — typically the result of ``Stat.Run N Times`` wrapping ``Skill.Get Activation Decision``. |
        | ``k`` | Top-k parameter. Must satisfy ``1 <= k <= len(runs)``. |

        Raises ``ValueError`` when ``k < 1``, ``k > len(runs)``, or
        ``len(runs) == 0`` (delegated to ``_compute_pass_at_k`` validation).

        Example:
        | ${pass_at_5} =    `Skill.Get Activation Pass At K`    ${RUNS}    k=5
        | Should Be True    ${pass_at_5} >= 0.7

        Notes:
        - PRD FR27 — Pass@k unbiased estimator math reused via
          ``AgentEval.stats._internal._compute_pass_at_k``.
        - Pass-predicate is HARD-CODED to
          ``isinstance(run.result, ActivationDecision) and
          run.result.activated``. The default ``Stat.Get Pass At K``
          predicate (``completeness == "complete"``) returns ``False``
          for ``ActivationDecision`` results because
          ``ActivationDecision`` has no ``metadata.completeness``
          attribute — the silent-zero failure mode Story 7.3 D-1
          empirically confirmed (closes C59 / DF-7.3-S1).
        - No ``predicate`` kwarg by design — removing the
          predicate-customization pitfall is the whole purpose. Operators
          needing a custom predicate call ``Stat.Get Pass At K`` directly.
        - Sibling keyword: ``Stat.Get Pass At K`` (Tier-1) for generic
          Pass@k on ``AgentRunResult`` runs.
        - Closes Epic 12 retro Action #5 + Epic 13 retro Action #5 (the
          C59 closure ratified 6 epics later in Story 14.5). The multi-word
          post-dot keyword name complies with the ratified norm
          ``feedback_libdoc_namespace_keyword_must_be_multiword``
          (Epic 12 retro 2026-06-01) — single-word post-dot names trigger
          the RF libdoc auto-split bug; multi-word names are immune.
        """
        from AgentEval.skills._internal import _activation_pass_predicate
        from AgentEval.stats._internal import _compute_pass_at_k

        c = sum(1 for r in runs if _activation_pass_predicate(r))
        return _compute_pass_at_k(c, len(runs), k)
```

### src/AgentEval/skills/_internal.py lines 327-352

```python
def _activation_pass_predicate(run: KeywordRun) -> bool:
    """Pass-predicate for ``Skill.Get Activation Pass At K`` (Story 14.5 / C59).

    Returns ``True`` iff the wrapped keyword's result is an
    ``ActivationDecision`` with ``activated=True``. Avoids the default
    ``Stat.Get Pass At K`` predicate (``completeness == "complete"``)
    silently returning ``False`` for activation results (Story 7.3 D-1;
    C59 / DF-7.3-S1; documented as 6-epic-old silent-zero failure mode).

    Local imports defer the dependency on ``stats.types.KeywordRun`` +
    ``skills.types.ActivationDecision`` until call time to keep this module
    import-light + avoid circulars (``ActivationDecision`` lives in
    ``skills.types`` which is imported by ``skills.library`` which imports
    this module).
    """
    from AgentEval.skills.types import ActivationDecision

    return isinstance(run.result, ActivationDecision) and run.result.activated
```

### Key invariants to verify adversarially

1. **Predicate correctness**: `_activation_pass_predicate` MUST return `True` iff `isinstance(run.result, ActivationDecision) and run.result.activated`. What happens if `run.result` is `None`? If it is a non-`ActivationDecision`? If `.activated` is `None` vs `False`?

2. **Math delegation**: `get_activation_pass_at_k` calls `_compute_pass_at_k(c, len(runs), k)` where `c = sum(...)`. Is `c` computed CORRECTLY? What is the `c` variable in the HumanEval estimator? It should be the number of runs where the predicate is True. The `len(runs)` is `n` (total runs). Is this correct?

3. **No `predicate=` kwarg**: `inspect.signature(SkillsLibrary().get_activation_pass_at_k).parameters` should NOT have `predicate`. Check that calling with `predicate=...` raises `TypeError`.

4. **ValueError validation delegated**: `ValueError` is raised when `k < 1`, `k > len(runs)`, or `len(runs) == 0`. This is delegated to `_compute_pass_at_k`. Does `_compute_pass_at_k` actually raise `ValueError` for these cases? Verify by reading `src/AgentEval/stats/_internal.py`.

5. **Decorator order**: `@keyword(name="Skill.Get Activation Pass At K")` then `@tier(1)`. Does the `@tier(1)` decorator need to be on top or bottom? Check the convention used by other Tier-1 methods in `SkillsLibrary`.

6. **C59 regression-guard test legitimacy**: `test_default_stat_pass_at_k_returns_zero_on_activation_decisions_proves_c59` asserts `default_result == 0.0`. Is this assertion actually testing what it claims? The test builds runs with `completeness="n/a"` manually. Could this be a false-positive test (i.e., does the real `Stat.Run N Times` path ALSO produce `completeness="n/a"` for `ActivationDecision` results)?

7. **Real-path regression-guard**: `test_c59_silent_zero_reproduces_through_real_stat_run_n_times_path` — does `stats.run_n_times(n=5, keyword=_always_activate)` work? What is the signature of `run_n_times`? Does it accept a bare callable without a `skill` or `prompt` argument? Check `src/AgentEval/stats/library.py` for `run_n_times` signature.

8. **Citation drift**: 
   - `docs/phase-1-5-carry-overs.md` C59 closure note claims "13 unit tests" but the actual file has 14 tests (pytest collected 14: 4 predicate + 8 keyword + 1 C59 regression-guard + 1 real-path regression-guard). Is the "13" claim in the closure note a citation drift bug?
   - Epic 12 retro Action #5: the closure criterion was "EITHER both docstrings carry incompatibility warning OR `Skill.Get Activation Pass At K` keyword shipped with a test exercising the predicate semantics; C59 marked done". Does Story 14.5 satisfy this criterion?
   - Epic 13 retro Action #5: "Either keyword shipped with test exercising the predicate semantics, OR both docstrings carry the warning + matching anchor test; C59 marked done in catalog." Does Story 14.5 satisfy this?

9. **Stability surface label**: `stability-surface.md` labels `Skill.Get Activation Pass At K` as `provisional`. Is this correct for a new keyword? (Check what other new keywords were labeled when first shipped.)

10. **`_activation_pass_predicate` placement**: The helper lives in `skills/_internal.py`, not `stats/_internal.py`. Is this the right module? It depends on `ActivationDecision` from `skills.types`. The comment says "Lives in this module (not in `stats/_internal.py`) because the predicate is skill-domain specific". Is there a circular import risk?

## Commands to run

```bash
# Verify tests pass
uv run pytest tests/unit/skills/test_activation_pass_at_k.py -v

# Verify _compute_pass_at_k signature and ValueError behavior
grep -n "_compute_pass_at_k\|def _compute" src/AgentEval/stats/_internal.py | head -20

# Check decorator order convention
grep -B2 "@tier\|@keyword" src/AgentEval/skills/library.py | head -40

# Check run_n_times signature
grep -n "def run_n_times\|def get_pass_at_k" src/AgentEval/stats/library.py | head -10

# Check if 13 or 14 tests are in the test file
grep -c "^def test_" tests/unit/skills/test_activation_pass_at_k.py

# Check the carry-overs doc claim
grep "unit test" docs/phase-1-5-carry-overs.md | grep -i "C59\|14.5"
```

## Output format

Group findings as HIGH / MED / LOW. For each finding: cite file + line + concrete fix. Be adversarial — look for real bugs, not surface-level style. If you find no HIGH bugs, say so explicitly and explain why.

