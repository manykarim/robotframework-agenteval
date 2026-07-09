# Story 14.5 Findings

## HIGH

None.

## MED

1. Test-count evidence is internally inconsistent across the shipped audit trail.
   - Files/lines: `tests/unit/skills/test_activation_pass_at_k.py:17-24`, `_bmad-output/implementation-artifacts/14-5-skill-get-activation-pass-at-k-or-docstring-warnings-c59-close.md:213`, `:221`, `:299`, `:322`, `:338`, `docs/phase-1-5-carry-overs.md:83`.
   - Evidence: the test file defines 14 tests (`grep -nE '^def test_' ...` returns 14 defs; `uv run pytest tests/unit/skills/test_activation_pass_at_k.py -q` reports `14 passed`), but several story artifacts and the C59 closure row still claim “13 unit tests / 13-test count / 4 + 8 + 1”. `sprint-status.yaml:166` already reflects the real total as 14, so the repo currently disagrees with itself on the closure evidence.
   - Concrete fix: update every stale “13 tests” reference to `14` and revise the breakdown to `4 predicate + 8 keyword + 2 C59 regression-guards`, or remove the exact breakdown/count where it is not load-bearing.

2. The story artifact overclaims novelty on the libdoc result and conflicts with its own cited Epic 12 evidence.
   - Files/lines: `_bmad-output/implementation-artifacts/14-5-skill-get-activation-pass-at-k-or-docstring-warnings-c59-close.md:31`, `:173`, `:217`, `:289`, `:338`.
   - Evidence: those lines describe Story 14.5 as the “first empirical test of the multi-word case” / “first dev-time empirical confirmation” that the libdoc bug is single-word-only. But `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md:80` already records an empirical reproduction that `Foo.Bar Quux` renders correctly, and `:223` ratifies the multi-word rule from that evidence. Story 14.5 does add a valuable re-confirmation on a real shipping keyword during development, but it is not the first empirical confirmation.
   - Concrete fix: reword the Story 14.5 artifact to “re-confirmed on a real shipping keyword during dev-time” (or equivalent) and drop the “first empirical” language.

## LOW

None.

## Verification Notes

- `uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary /tmp/story-14-5-libdoc-probe.html` succeeded.
- `grep -oE '"name": ?"Skill\.[^"]+"' /tmp/story-14-5-libdoc-probe.html` included `"name": "Skill.Get Activation Pass At K"` exactly.
- `inspect.signature(SkillsLibrary().get_activation_pass_at_k)` showed no `predicate` parameter; passing `predicate=` raises `TypeError`.
- Live probe reproduced the C59 rationale: `StatsLibrary().get_pass_at_k(runs, k=1) == 0.0` and `SkillsLibrary().get_activation_pass_at_k(runs, k=1) == 1.0` on activated `ActivationDecision` runs.
- `uv run pytest tests/unit/skills/test_activation_pass_at_k.py -q` passed (`14 passed`).
- `uv run pytest tests/unit/skills/test_activation_decision.py -q` passed (`15 passed`).
- `uv run pytest tests/unit/conventions/test_keyword_name_idiom.py -q` passed.
- `uv run pytest tests/unit/conventions/test_docstring_browser_style.py -q -k citation_bidirectional_consistency` passed.
- `uv run pytest tests/unit/conventions/test_docstring_examples_dryrun.py -q -k example_block_dryruns_clean` passed.
- `uv run python scripts/check-catalog-references.py --all-tracked` exited 0.
