# Story 7.3: Devon's Stacked Validation Recipe + Integration Test

Status: done

## Story

As **Devon (Agent Surface Author)**,
I want a documented Recipe Gallery #4 entry showing the full Devon validation pattern (static + activation reliability stacked) plus an integration test proving the recipe works end-to-end against a real skill file fixture,
so that other skill authors can copy the pattern + Phase 2's Epic 12 Judge can plug in as the Tier-2 layer to complete the three-tier flow.

## Acceptance Criteria

**AC-7.3.1**: Integration test file `tests/integration/skills/test_devon_stacked_validation.py` is created and runs to completion without errors using a stub adapter.

**AC-7.3.2**: The integration test exercises **Tier-1 frontmatter validation**: calls `Skill.Get Frontmatter` + `Skill.Should Be Valid Frontmatter` on the `tests/fixtures/skills/example-search.md` fixture — both pass.

**AC-7.3.3**: The integration test exercises **Tier-3 cohort Discoverability**: calls `Skill.Get Discoverability(skill, tasks, adapter=..., trials_per_task=10)` — for all `should_activate=True` tasks in `skill-tasks-basic.yaml`, `task_result.pass_at_k >= 0.8`.

**AC-7.3.4**: The integration test exercises **Stat.* composition**: calls `Stat.Run N Times(10, Skill.Get Activation Decision, ...)` → `Stat.Get Pass At K(runs, k=5, predicate=lambda r: isinstance(r.result, ActivationDecision) and r.result.activated)` ≥ 0.8 for a representative spot-check prompt. (Stronger form required per DF-7.3-S1/C59 — `ActivationDecision` has no `metadata.completeness` → default predicate always False; `isinstance` guard added in-flight 2026-05-21.)

**AC-7.3.5**: The integration test exercises **`Skill Should Activate For`** spot-check: calls `skills.should_activate_for(prompt, skill, adapter=...)` for ≥2 representative prompts — returns None (no assertion error raised).

**AC-7.3.6**: Recipe stub `docs/recipes/04-skill-author-stacked-validation.md` is created with:
- A brief "Devon's Stacked Validation Pattern" header
- Three-tier flow documented: Tier-1 static → Tier-2 TODO → Tier-3 cohort
- Working Robot Framework `.robot` code block showing the full pattern
- `# TODO Phase 2: Judge.Get Score here` marker in the Tier-2 slot

**AC-7.3.7**: The integration test verifies the recipe stub exists AND contains the Phase-2 Judge placeholder (`"TODO Phase 2: Judge.Get Score here"` string).

**AC-7.3.8**: The full test suite (`uv run pytest tests/ -x -q --ignore=tests/dogfood`) continues to pass with zero regressions — all 1258 existing tests still green.

## Pre-Create-Story Drift Check

**33rd consecutive use of `feedback_spec_vs_ratified_doc_precheck`.** 4 drifts found and resolved pre-authoring:

**D-1 (HIGH — empirically confirmed): `Stat.Get Pass At K` default predicate breaks with `Skill.Get Activation Decision`.**
Epic AC says "Pass@5 estimate" via `Stat.*` keywords. But `Stat.Get Pass At K`'s default predicate is `lambda r: r.completeness == "complete"`. When `Stat.Run N Times` wraps `Skill.Get Activation Decision`, the underlying `ActivationDecision` dataclass has no `metadata.completeness` field → `_extract_completeness()` returns `"n/a"` → default predicate always returns False → `Stat.Get Pass At K` returns 0.0 with default predicate.
**Empirically verified:** `runs[0].completeness = "n/a"` (not `"complete"`), `_default_pass_predicate(run) = False` for all runs.
**Resolution:** Integration test MUST use custom predicate: `predicate=lambda r: r.result.activated`. The `r.result` field of `KeywordRun` is the raw `ActivationDecision` return value; `.activated` is the bool. Documented as DF-7.3-S1/C59. NO amendment to planning artifacts needed — this is an implementation-level constraint not covered by epic AC.

**D-2 (MED): Integration tests do NOT currently use `@pytest.mark.live`.**
Architecture L1364 says integration tests should be `@pytest.mark.live`, nightly CI per NFR-REL-03. But in practice: (a) no `live` marker is registered in `pyproject.toml` or any `conftest.py`; (b) existing integration tests (`tests/integration/mcp/test_observer.py`, `tests/integration/static_inspection/test_real_world_samples.py`) do NOT have `@pytest.mark.live`; (c) the regular pytest sweep includes `tests/integration/` (no exclusion beyond `tests/dogfood`). The Story 7.3 integration test uses a stub adapter (no live LLM calls), so `@pytest.mark.live` would be misleading.
**Resolution:** Do NOT use `@pytest.mark.live`. Match the existing integration test pattern (no marker). The test runs in the normal sweep. Architecture L1364 reflects a planned future state — Phase-1.5 carry-over per story pattern.

**D-3 (LOW): `tests/integration/skills/` subdirectory does not exist.**
The AC specifies the test at `tests/integration/skills/test_devon_stacked_validation.py` but no `skills/` subdirectory exists under `tests/integration/`.
**Resolution:** Create `tests/integration/skills/__init__.py` (empty) as part of this story. Standard Python package init, matching the pattern in `tests/integration/mcp/__init__.py` and `tests/integration/static_inspection/__init__.py`.

**D-4 (LOW): `docs/recipes/04-skill-author-stacked-validation.md` does not exist.**
The `docs/recipes/` directory exists but contains only `.gitkeep` — no recipe files authored yet (all Phase-1 recipes are deferred to their per-story + Epic 8b work).
**Resolution:** Create the stub during this story per epics.md L1759 verbatim: "drafted as a stub during Story 7.3." The stub is 30-50 lines with working code examples + TODO markers. Epic 8b polishes it.

## Tasks / Subtasks

- [x] Task 1: Create `tests/integration/skills/` package (AC: 7.3.1)
  - [x] 1.1: Create `tests/integration/skills/__init__.py` (empty, license header)

- [x] Task 2: Implement `tests/integration/skills/test_devon_stacked_validation.py` (AC: 7.3.1–7.3.5, 7.3.7, 7.3.8)
  - [x] 2.1: Define module-level fixtures: `SKILL_PATH`, `TASKS_PATH`, `SKILL_NAME`, `_make_stub()`, `_register_devon_stub` module fixture
  - [x] 2.2: Write `TestDevonStackedValidation` class with `@pytest.mark.live` NOT used — plain class grouping
  - [x] 2.3: Implement `test_tier1_frontmatter_validation` — `Skill.Get Frontmatter` + `Skill.Should Be Valid Frontmatter`
  - [x] 2.4: Implement `test_tier3_cohort_discoverability` — `Skill.Get Discoverability(trials_per_task=10)` + per-task `pass_at_k >= 0.8`
  - [x] 2.5: Implement `test_stat_run_n_times_with_activation_decision` — `Stat.Run N Times` + custom predicate + `Stat.Get Pass At K(k=5)` ≥ 0.8
  - [x] 2.6: Implement `test_skill_should_activate_for_spot_check` — `Skill.Should Activate For` for ≥2 representative prompts
  - [x] 2.7: Implement `test_recipe_stub_exists_with_phase2_placeholder` — assert recipe file exists + contains "TODO Phase 2"
  - [x] 2.8: Run tests; confirm all 5 pass (5 test methods total); no regressions in full suite (1263 tests pass)

- [x] Task 3: Create recipe stub `docs/recipes/04-skill-author-stacked-validation.md` (AC: 7.3.6)
  - [x] 3.1: Write stub with: title, persona (Devon), three-tier description, `.robot` code block showing full pattern, TODO Phase 2 Judge slot

- [x] Task 4: Catalog carry-overs + update sprint status (AC: gate, before code review)
  - [x] 4.1: Run `grep -rn "DF-7.3-S" tests/integration/skills/ docs/recipes/` — confirmed: DF-7.3-S1 in test docstring + recipe NOTE comment
  - [x] 4.2: Add DF-7.3-S1/C59 to `_bmad-output/implementation-artifacts/deferred-work.md`
  - [x] 4.3: Add C59 row to `docs/phase-1-5-carry-overs.md`, updated catalog total 58 → 59
  - [x] 4.4: Update sprint status for 7-3 → `review`

## Dev Notes

### Architecture Context

**Integration test location**: `tests/integration/` — Python pytest tests that run in the normal sweep (no `@pytest.mark.live` per D-2 drift resolution). [Source: `tests/integration/mcp/test_observer.py` + architecture.md L1364]

**Recipe Gallery location**: `docs/recipes/` — 8 recipes planned per PRD Appendix. Story 7.3 authors the `04-skill-author-stacked-validation.md` stub. Epic 8b polishes it. [Source: architecture.md L1467–1475]

**Devon's three-tier validation flow** (Journey 4, architecture skills/ docstring L1271–1275):
- Tier 1 (static, deterministic): `Skill.Get Frontmatter` + `Skill.Should Be Valid Frontmatter` (Epic 2 Story 2.1)
- Tier 2 (judge, LLM, Phase 2): `Judge.Get Score` (Epic 12 Story 12.3 — NOT shipped yet; slot is `# TODO Phase 2: Judge.Get Score here`)
- Tier 3 (cohort, stochastic): `Skill.Get Discoverability` + `Skill.Should Activate For` (Stories 7.1 + 7.2)
- Stat.* layer: `Stat.Run N Times` + `Stat.Get Pass At K` (Story 6.3) — stacked on top of Tier-3 keywords

### Available Fixtures

**`tests/fixtures/skills/example-search.md`**: Skill with `name: example-search-skill`, `description: "Search for information across the web and knowledge base."`, `allowed-tools: [web_search, knowledge_base_search]`, `disable-model-invocation: false`.

**`tests/fixtures/discoverability/skill-tasks-basic.yaml`**: 5 tasks — 3 `should_activate: true` (search_simple, search_knowledge_base, search_web_query), 2 `should_activate: false` (decoy_greeting, decoy_calculation).

```
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILL_PATH = FIXTURES_DIR / "skills" / "example-search.md"
TASKS_PATH = FIXTURES_DIR / "discoverability" / "skill-tasks-basic.yaml"
SKILL_NAME = "example-search-skill"
```

`parents[2]` from `tests/integration/skills/` = `tests/` ← same depth computation as `tests/unit/skills/test_discoverability.py`.

### Stub Adapter Pattern (from Stories 7.1 + 7.2)

Use the exact same `InProcessAdapter` subclass pattern from unit tests. The stub must return `response_text` containing the skill name to trigger activation.

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import ActivationDecision
from AgentEval.stats.library import StatsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILL_PATH = FIXTURES_DIR / "skills" / "example-search.md"
TASKS_PATH = FIXTURES_DIR / "discoverability" / "skill-tasks-basic.yaml"
SKILL_NAME = "example-search-skill"
ADAPTER_NAME = "devon_integration_stub"


def _make_stub() -> type[InProcessAdapter]:
    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"I activated the {SKILL_NAME} skill for this search request.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.002,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture(autouse=True, scope="module")
def _register_stub() -> None:
    register_adapter(ADAPTER_NAME, _make_stub())


@pytest.fixture
def skills() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def stats() -> StatsLibrary:
    return StatsLibrary()
```

### CRITICAL: `Stat.Get Pass At K` Custom Predicate (D-1 fix)

**This is the most important implementation constraint in this story.**

`Stat.Run N Times` wraps `Skill.Get Activation Decision` calls and stores the raw `ActivationDecision` return value in `KeywordRun.result`. BUT `_extract_completeness()` in `stats/_internal.py` looks for `result.metadata.completeness` — `ActivationDecision` has no `metadata` attribute → returns `"n/a"` → the default predicate (`completeness == "complete"`) always returns False → `Stat.Get Pass At K` with default predicate = 0.0.

**Empirically verified** (2026-05-21 probe):
```
runs[0].completeness = "n/a"     # NOT "complete"
_default_pass_predicate(run) = False  # always False
r.result.activated = True        # correct value is HERE
```

**REQUIRED**: Always use custom predicate when calling `Stat.Get Pass At K` with `Skill.Get Activation Decision` runs:
```python
predicate = lambda r: isinstance(r.result, ActivationDecision) and r.result.activated
pass_at_5 = stats.get_pass_at_k(runs, k=5, predicate=predicate)
```

Documented as DF-7.3-S1/C59: Phase-1.5 resolution is either a dedicated `Skill.Get Activation Pass At K` helper keyword OR a docstring amendment on both `Stat.Get Pass At K` and `Skill.Get Activation Decision`.

### Integration Test: Test Structure

**Full test implementation sketch:**

```python
class TestDevonStackedValidation:
    """Devon's stacked validation recipe integration test (Story 7.3 / AC-7.3.1–7.3.7)."""

    def test_tier1_frontmatter_validation(self, skills: SkillsLibrary) -> None:
        """Tier-1 static: frontmatter present + valid for example-search.md."""
        fm = skills.get_frontmatter(SKILL_PATH)
        skills.should_be_valid_frontmatter(fm)
        assert fm["name"] == SKILL_NAME

    def test_tier3_cohort_discoverability(self, skills: SkillsLibrary) -> None:
        """Tier-3 cohort: all should-activate tasks have pass_at_k >= 0.8 (10 trials each)."""
        result = skills.get_discoverability(
            SKILL_PATH,
            TASKS_PATH,
            adapter=ADAPTER_NAME,
            trials_per_task=10,
        )
        for task_result in result.per_task_results:
            if task_result.should_activate:
                assert task_result.pass_at_k >= 0.8, (
                    f"Task '{task_result.task_id}' pass_at_k={task_result.pass_at_k:.3f} < 0.8 "
                    f"({task_result.activations_observed}/{task_result.trials_run} activations)"
                )

    def test_stat_run_n_times_with_activation_decision(
        self, skills: SkillsLibrary, stats: StatsLibrary
    ) -> None:
        """Stat.* composition: Run N Times → custom predicate → Pass@5 >= 0.8.
        
        CRITICAL: Must use custom predicate (lambda r: r.result.activated) because
        ActivationDecision has no metadata.completeness → completeness="n/a" → default
        predicate always False (D-1 drift, DF-7.3-S1/C59).
        """
        runs = stats.run_n_times(
            n=10,
            keyword=skills.get_activation_decision,
            keyword_args={
                "skill": str(SKILL_PATH),
                "prompt": "Search for Python tutorials on the web",
                "adapter": ADAPTER_NAME,
            },
        )
        assert len(runs) == 10
        pass_at_5 = stats.get_pass_at_k(
            runs=runs,
            k=5,
            predicate=lambda r: isinstance(r.result, ActivationDecision) and r.result.activated,
            # TODO Phase 2: replace predicate with Judge.Get Score >= threshold
        )
        assert pass_at_5 >= 0.8

    def test_skill_should_activate_for_spot_check(self, skills: SkillsLibrary) -> None:
        """Tier-2/3 spot-check: Skill.Should Activate For returns None for representative prompts."""
        representative_prompts = [
            "Search for Python tutorials on the web",
            "Find information about robotframework-agenteval",
        ]
        for prompt in representative_prompts:
            result = skills.should_activate_for(prompt, SKILL_PATH, adapter=ADAPTER_NAME)
            assert result is None

    def test_recipe_stub_exists_with_phase2_placeholder(self) -> None:
        """Recipe stub at docs/recipes/04-skill-author-stacked-validation.md exists
        and contains the Phase-2 Judge placeholder per AC-7.3.6–7.3.7."""
        recipe_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "recipes"
            / "04-skill-author-stacked-validation.md"
        )
        assert recipe_path.exists(), (
            "Recipe stub must exist at docs/recipes/04-skill-author-stacked-validation.md "
            "(create it per Story 7.3 AC-7.3.6)"
        )
        content = recipe_path.read_text()
        assert "TODO Phase 2: Judge.Get Score" in content, (
            "Recipe must contain Phase-2 Judge slot placeholder per AC-7.3.7"
        )
```

Note on path for `recipe_path`:
- `tests/integration/skills/test_devon_stacked_validation.py`
- `parents[0]` = `tests/integration/skills/`
- `parents[1]` = `tests/integration/`
- `parents[2]` = `tests/`
- `parents[3]` = project root
- → `parents[3] / "docs" / "recipes" / "04-skill-author-stacked-validation.md"` ✓

### Recipe Stub: Content

`docs/recipes/04-skill-author-stacked-validation.md` — minimal stub, 30–50 lines:

```markdown
# Recipe 4: Devon's Stacked Skill Validation Pattern

**Persona:** Devon (Agent Surface Author)
**Epic:** Epic 7 (Skill Author Validation Flow)
**Status:** Stub — drafted Story 7.3; polish in Epic 8b.

## The Three-Tier Validation Stack

Devon validates a skill `.md` file using a three-tier pattern:

| Tier | Keyword | Story | Notes |
|------|---------|-------|-------|
| 1 — Static | `Skill.Should Be Valid Frontmatter` | 2.1 | Deterministic; no LLM |
| 2 — Judge | `Judge.Get Score` | Epic 12.3 | **Phase 2 only** — see TODO below |
| 3 — Cohort | `Skill.Get Discoverability` | 7.2 | 10 trials/task; Pass@5 ≥ 0.8 |

## Robot Framework Example

```robotframework
*** Settings ***
Library    AgentEval.skills.library    WITH NAME    Skill
Library    AgentEval.stats.library     WITH NAME    Stat

*** Test Cases ***
Devon Validates Example Search Skill
    # Tier 1: Static frontmatter validation (deterministic)
    ${fm}=    Skill.Get Frontmatter    skills/example-search.md
    Skill.Should Be Valid Frontmatter    ${fm}

    # Tier 2 (Phase 2 only — placeholder)
    # TODO Phase 2: Judge.Get Score here (Epic 12 Story 12.3)
    # ${score}=    Judge.Get Score    skills/example-search.md
    # Should Be True    ${score} >= 0.8

    # Tier 3: Cohort discoverability (10 trials per task)
    ${result}=    Skill.Get Discoverability
    ...    skill=skills/example-search.md
    ...    tasks=tests/discoverability/skill-tasks-basic.yaml
    ...    adapter=generic
    ...    trials_per_task=10

    # Assert Pass@k for all should-activate tasks
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be True    ${task_result.pass_at_k} >= 0.8
        END
    END

    # Spot-check: single-prompt activation assertion
    Skill.Should Activate For
    ...    prompt=Search for Python tutorials on the web
    ...    skill=skills/example-search.md
    ...    adapter=generic
```
```

(The markdown needs proper escaping of the inner code fence — use ` ``` ` with language tags.)

### Files to Create / Modify

**NEW:**
- `tests/integration/skills/__init__.py` — empty package init (license header)
- `tests/integration/skills/test_devon_stacked_validation.py` — integration test (5 test methods)
- `docs/recipes/04-skill-author-stacked-validation.md` — recipe stub (30–50 lines)

**MODIFIED:**
- `_bmad-output/implementation-artifacts/deferred-work.md` — add DF-7.3-S1
- `docs/phase-1-5-carry-overs.md` — add C59, update total 58 → 59
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 7-3 → review/done

**NOT modified**: `src/AgentEval/**` — this story adds NO new keywords. The integration test uses existing API surface only.

### Test Validation Commands

```bash
# Run only the new integration test
uv run pytest tests/integration/skills/test_devon_stacked_validation.py -v

# Full suite regression check
uv run pytest tests/ -x -q --ignore=tests/dogfood

# Linting
uv run ruff check tests/integration/skills/
uv run ruff format --check tests/integration/skills/
uv run mypy tests/integration/skills/ --ignore-missing-imports
```

### Carry-over Gate (UPSTREAM — must run before Task 4 / before code review)

Per `feedback_carry_over_catalog_gate` UPSTREAM norm (12th consecutive story):

```bash
grep -rn "DF-7.3-S" tests/integration/skills/ docs/recipes/
```

Expected: DF-7.3-S1 appears in integration test docstring or comment. Verify it's catalogued in `deferred-work.md` + `phase-1-5-carry-overs.md`.

### Dogfood Fake-Green Precheck (No Dogfood in This Story)

Story 7.3 has no `.robot` dogfood tests — only Python pytest integration test. Fake-green precheck: verify all 5 test methods have concrete assertions (not just `assert True` or empty bodies).

### Caller-Count Check

Story 7.3 creates NO new public helper functions. The `_make_stub()` factory is test-private. Nothing to caller-count.

### DF-7.3-S1 Entry for Deferred Work

```
**DF-7.3-S1 (`Stat.Get Pass At K` predicate incompatibility with `Skill.Get Activation Decision` results)**
— Story 7.3 D-1 empirically confirmed 2026-05-21: `Skill.Get Activation Decision` returns
`ActivationDecision` dataclass which has no `metadata.completeness` attribute.
`_extract_completeness()` in `stats/_internal.py` returns `"n/a"` for these results.
The default `Stat.Get Pass At K` predicate (`completeness == "complete"`) always returns False
for activation-decision runs → misleads users into thinking activation never succeeds.
Fix required: lambda r: r.result.activated (or isinstance(r.result, ActivationDecision) and r.result.activated).
Phase-1.5 resolution: Either (a) add dedicated `Skill.Get Activation Pass At K(runs, k)` keyword
that uses the correct predicate, OR (b) document the required custom predicate in both
`Stat.Get Pass At K` and `Skill.Get Activation Decision` docstrings. Catalogued as C59.
Effort: S (docstring amendment OR new keyword). Phase-1.5.
```

### Tier/Badge Conventions

Story 7.3 ships NO new keywords. The integration test file itself has no `@tier()` annotations (it's a test, not a keyword implementation). No badge conventions apply.

### Previous Story Learnings

From Story 7.2 (most recent):
- `register_adapter(name, cls)` is idempotent per test isolation — use unique stub names per module
- `InProcessAdapter` subclass pattern: subclass → override `run(self, prompt, **kwargs)` → return `AgentRunResult`
- Import pattern: `from AgentEval.coding_agent.base import InProcessAdapter`
- `AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process")` is the correct metadata shape
- `Usage(input_tokens=1, output_tokens=1)` for cost accounting
- `trace_id="a" * 32` is a valid 32-char hex stub

From Story 7.1 (module-scope fixture for adapter registration):
- `@pytest.fixture(autouse=True, scope="module")` is the right pattern for module-scoped stub registration
- Tests sharing the same stub adapter name in the same module don't need re-registration

From Stories 7.1/7.2 (NO conftest.py for skills):
- No `tests/integration/skills/conftest.py` needed — keep fixtures in the test file itself

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- D-1 (HIGH): `Stat.Get Pass At K` default predicate incompatible with `ActivationDecision` results — empirically verified, custom predicate required; documented as DF-7.3-S1/C59
- D-2 (MED): `@pytest.mark.live` not registered/used in any existing integration test — resolved by matching existing pattern (no marker)
- D-3 (LOW): `tests/integration/skills/` subdirectory missing — created `__init__.py`
- D-4 (LOW): `docs/recipes/04-skill-author-stacked-validation.md` missing — created recipe stub

### Completion Notes List

- ✅ Created `tests/integration/skills/__init__.py` (license header, one-line docstring)
- ✅ Created `tests/integration/skills/test_devon_stacked_validation.py` with 5 test methods: `test_tier1_frontmatter_validation`, `test_tier3_cohort_discoverability`, `test_stat_run_n_times_with_activation_decision`, `test_skill_should_activate_for_spot_check`, `test_recipe_stub_exists_with_phase2_placeholder`
- ✅ All 5 integration tests pass; 1263 total tests pass, 0 regressions
- ✅ Created `docs/recipes/04-skill-author-stacked-validation.md` (recipe stub with three-tier table, RF code block, `# TODO Phase 2: Judge.Get Score here`)
- ✅ Carry-over gate: DF-7.3-S1/C59 catalogued in `deferred-work.md` + `phase-1-5-carry-overs.md` (total 59)
- ✅ Custom predicate pattern documented in test docstring, recipe NOTE comment, and story dev notes (DF-7.3-S1/C59)

### File List

**New files:**
- `tests/integration/skills/__init__.py`
- `tests/integration/skills/test_devon_stacked_validation.py`
- `docs/recipes/04-skill-author-stacked-validation.md`

**Modified files:**
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `docs/phase-1-5-carry-overs.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-05-21: Story created. Pre-create drift check (33rd consecutive use, 100% catch rate intact). 4 drifts found: D-1 HIGH `Stat.Get Pass At K` default predicate breaks with `ActivationDecision` (empirically verified, requires custom predicate); D-2 MED `@pytest.mark.live` not in use by any existing integration test; D-3 LOW `tests/integration/skills/` subdirectory missing; D-4 LOW recipe stub missing from `docs/recipes/`. Epic-7 is in-progress (7-1 + 7-2 done). Status → ready-for-dev.
- 2026-05-21: Implementation complete. 3 files created, 2 files modified. 5 integration tests pass, 1263 total tests pass. DF-7.3-S1/C59 catalogued. Status → review.
- 2026-05-21: Code-review patches applied. 4-reviewer cross-LLM adversarial pair (Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex CLI gpt-5.4): 2-way HIGH (Blind Hunter + Codex): recipe RF code block had two broken syntax forms — `keyword_args=skill=X    prompt=Y    adapter=Z` (RF parses as 3 separate named args to `Run N Times`, which has no `prompt`/`adapter` params → runtime error); `${lambda r: r.result.activated}` (RF variable lookup, not Python eval → VariableNotFoundError at runtime). Fixes: `Create Dictionary` for `keyword_args` + `${{lambda r: ...}}` double-brace inline eval. Acceptance Auditor MED: AC-7.3.4 predicate not back-amended (in-flight spec amendment norm) — amended AC to reflect `isinstance(r.result, ActivationDecision) and r.result.activated`. Auditor LOW: `phase-1-5-carry-overs.md` `Last updated` not bumped — fixed to 2026-05-21. Auditor LOW: `deferred-work.md` section ordering (7.3 before 7.2) — fixed to chronological. Status → done.
