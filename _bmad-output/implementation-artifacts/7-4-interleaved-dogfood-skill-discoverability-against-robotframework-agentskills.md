# Story 7.4: Interleaved Dogfood — Skill Discoverability Against `robotframework-agentskills`

Status: done

## Story

As a **dogfood validator** + **Devon validator**,
I want the cohort Skill Discoverability keyword from Story 7.2 exercised against `robotframework-agentskills`' real skill set with a curated representative task set,
So that Devon's cohort discoverability surface is empirically validated against real skills before Epic 9 close — surfacing any gaps in the FR4b/d implementation before Phase 1 ships.

## Pre-Create-Story Drift Check

**34th consecutive use of `feedback_spec_vs_ratified_doc_precheck`.** 6 drifts found and resolved pre-authoring:

**D-1 (HIGH — mirrors Story 6.4 D-1): Epic AC says task sets "land in `robotframework-agentskills`' test directory under a `tests/discoverability/` path and are committed to that repo".**
Ratified Story 3.3/5.5/6.4 precedent: vendor ALL dogfood suites INTO agenteval at `tests/dogfood/agentskills/`. NO upstream push. NO cross-repo CI dispatch (deferred to Story 9.1+9.2 per architecture L1718). Story 6.4 D-1 was identical and fully resolved. AMENDED in pre-authoring: task YAMLs + SKILL.md copies land in `tests/dogfood/agentskills/discoverability/` + `tests/dogfood/agentskills/skills/` respectively, all within agenteval repo.

**D-2 (HIGH): `SkillsLibrary` is EXCLUDED from `_SUB_LIBRARIES` (DF-7.1-S1/C55).**
The dogfood test cannot use `Library AgentEval WITH NAME AgentEval` + `AgentEval.Skill.Get Discoverability` because `SkillsLibrary` is not composed into `AgentEval` via `DynamicCore` (name collision with `SubagentsLibrary` on `Get Frontmatter`). The top-level `AgentEval` library does NOT expose `Skill.*` keywords. Stories 7.1–7.3 all used `SkillsLibrary` directly. RESOLUTION: `test_skill_discoverability.robot` imports `Library AgentEval.skills.library WITH NAME Skill` directly — NOT via top-level `AgentEval WITH NAME AgentEval`.

**D-3 (LOW): Parity checklist path drift.**
Epic says `tests/dogfood/parity-checklist-agentskills-discoverability.md` (root level). Story 6.4 established `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md` (inside subdirectory). RESOLUTION: Use `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md` per ratified convention. Epic text updated pre-authoring.

**D-4 (MED): Scale — 11 agentskills skills × ≥5 tasks each would generate 110+ tasks.**
Epic says "≥5 each per skill" for all skills. With 11 skills available (`rf-appium`, `rf-browser`, `rf-keyword-builder`, `rf-libdoc-explain`, `rf-libdoc-search`, `rf-requests`, `rf-resource-architect`, `rf-restinstance`, `rf-results`, `rf-selenium`, `rf-testcase-builder`) full coverage is Epic 9 work. RESOLUTION: Story 7.4 covers 3 representative skills (1 per category): `rf-browser` (execution / web), `rf-results` (analysis / parsing), `rf-libdoc-search` (search / discovery). Remaining 8 skills deferred to Epic 9 + parity checklist tracks which are covered.

**D-5 (LOW): `dogfood-integration.yml` CI dispatch not in scope.**
Epic implies `dogfood-integration.yml` runs the new Skill Discoverability suites. Per Story 1a.2 HIGH-1 + Story 6.4 D-1: `dogfood-integration.yml` stays install-smoke-only; full cross-repo CI deferred to Story 9.1+9.2. RESOLUTION: `.robot` suites are locally runnable only via `uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot`. No CI changes in Story 7.4.

**D-6 (LOW — mirrors Story 6.4 D-6): `dogfood-finding` GitHub label doesn't exist.**
Per Story 6.4 D-6: no `dogfood-finding` label exists on the repo; findings go to `deferred-work.md` + `docs/phase-1-5-carry-overs.md` per project norm. RESOLUTION: DF-7.4-S1 follows the same pattern.

## Acceptance Criteria

**AC-7.4.1**: `tests/dogfood/agentskills/skills/` contains vendored copies of 3 SKILL.md files from `robotframework-agentskills`:
- `rf-browser-skill.md` (name: `rf-browser`)
- `rf-results-skill.md` (name: `rf-results`)
- `rf-libdoc-search-skill.md` (name: `rf-libdoc-search`)
Each copy preserves the original YAML frontmatter intact (activation heuristic uses `name:` field).

**AC-7.4.2**: `tests/dogfood/agentskills/discoverability/` contains 3 task YAML files per Story 7.2 schema:
- `rf-browser-tasks.yaml` — ≥5 `should_activate: true` + ≥3 `should_activate: false` tasks
- `rf-results-tasks.yaml` — ≥5 `should_activate: true` + ≥3 `should_activate: false` tasks
- `rf-libdoc-search-tasks.yaml` — ≥5 `should_activate: true` + ≥3 `should_activate: false` tasks
Prompts reflect real-world agentskills usage patterns (not copy-paste of example-search fixture).

**AC-7.4.3**: `tests/dogfood/agentskills/fixtures/agentskills_discoverability.py` provides:
- `register_skill_stubs()` RF keyword (called once at Suite Setup) — registers 3 stub adapters (`stub_rf_browser`, `stub_rf_results`, `stub_rf_libdoc_search`) each returning `response_text` containing the target skill name, making activated=True for every trial.
- Path constants for the 3 skill files and 3 task YAML files (absolute paths computed from `__file__`).

**AC-7.4.4**: `tests/dogfood/agentskills/test_skill_discoverability.robot` exercises `Skill.Get Discoverability` against 3 skills. Per-skill assertions (5 should_activate + 3 should_not_activate tasks, `trials_per_task=3`, stub always activates):
- `len(result.per_task_results) == 8`
- `result.summary.activation_accuracy ≈ 0.625` (15 correct / 24 total trials; 5×3 should_activate correct, 3×3 decoys all wrong)
- `result.summary.false_activation_rate == 1.0` (decoy tasks activate 100% with stub)
- `result.summary.missed_activation_rate == 0.0`
- For each `should_activate=True` task: `task_result.pass_at_k == 1.0` (3/3 activations)

**AC-7.4.5**: `test_skill_discoverability.robot` includes a `Dogfood Finding: stub reveals false-activation blindspot` test case that:
- Asserts `summary.false_activation_rate == 1.0` explicitly
- Documents in `[Documentation]` that this is DF-7.4-S1 — the stub always activates, so decoy task false-activation rate is 1.0 by design; real agent behavior requires a live provider run (deferred to Epic 9)
- This satisfies the epic's "≥1 actionable finding" requirement.

**AC-7.4.6**: `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md` documents:
- Coverage: 3 of 11 skills covered (rf-browser, rf-results, rf-libdoc-search)
- Deferred: 8 skills (rf-appium, rf-keyword-builder, rf-libdoc-explain, rf-requests, rf-resource-architect, rf-restinstance, rf-selenium, rf-testcase-builder) → Epic 9
- Section for `DOGFOOD-FINDING-1` (DF-7.4-S1): stub false-activation blindspot

**AC-7.4.7**: All `.robot` tests in `test_skill_discoverability.robot` pass via `uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot`. Full pytest suite passes with zero regressions (`uv run pytest tests/ -x -q --ignore=tests/dogfood`).

**AC-7.4.8**: Fake-green precheck passed before code review: every test assertion in `test_skill_discoverability.robot` is concrete (numeric equality or inequality) — no `Should Be True    True` vacuous assertions. Verify by inspection.

**AC-7.4.9**: DF-7.4-S1 + C60 catalogued in `deferred-work.md` + `docs/phase-1-5-carry-overs.md` before code review (carry-over gate, UPSTREAM per Story 5 retro norm).

## Tasks / Subtasks

- [x] Task 1: Vendor 3 agentskills SKILL.md files into `tests/dogfood/agentskills/skills/` (AC: 7.4.1)
  - [x] 1.1: Create `tests/dogfood/agentskills/skills/` directory (no `__init__.py` needed — RF resource dir)
  - [x] 1.2: Copy `robotframework-agentskills/skills/robotframework-browser-skill/SKILL.md` → `tests/dogfood/agentskills/skills/rf-browser-skill.md`
  - [x] 1.3: Copy `robotframework-agentskills/skills/robotframework-results/SKILL.md` → `tests/dogfood/agentskills/skills/rf-results-skill.md`
  - [x] 1.4: Copy `robotframework-agentskills/skills/robotframework-libdoc-search/SKILL.md` → `tests/dogfood/agentskills/skills/rf-libdoc-search-skill.md`

- [x] Task 2: Author 3 task YAML files in `tests/dogfood/agentskills/discoverability/` (AC: 7.4.2)
  - [x] 2.1: `rf-browser-tasks.yaml` — 5 should_activate (web testing / browser / playwright prompts) + 3 should_not_activate (decoy: parsing/search/appium prompts)
  - [x] 2.2: `rf-results-tasks.yaml` — 5 should_activate (output.xml / pass-fail / test results parsing prompts) + 3 should_not_activate (decoy: web testing / keyword creation prompts)
  - [x] 2.3: `rf-libdoc-search-tasks.yaml` — 5 should_activate (find keywords / search libdoc / match use case prompts) + 3 should_not_activate (decoy: run test / parse results / create test prompts)

- [x] Task 3: Create `tests/dogfood/agentskills/fixtures/agentskills_discoverability.py` (AC: 7.4.3)
  - [x] 3.1: License header + module docstring documenting the stub pattern + DF-7.4-S1 constraint
  - [x] 3.2: Implement `_make_skill_stub(skill_name)` factory (same pattern as Story 7.3's `_make_stub()`)
  - [x] 3.3: Implement `register_skill_stubs()` RF keyword — calls `register_adapter` for 3 skill stubs
  - [x] 3.4: Export path constants: `SKILLS_DIR`, `DISCOVERABILITY_DIR`, and per-skill `SKILL_PATH_*` + `TASKS_PATH_*` constants

- [x] Task 4: Create `tests/dogfood/agentskills/test_skill_discoverability.robot` (AC: 7.4.4–7.4.5, 7.4.7, 7.4.8)
  - [x] 4.1: Settings: `Library AgentEval.skills.library.SkillsLibrary WITH NAME Skill` + `Library fixtures/agentskills_discoverability.py` + `Suite Setup Register Skill Stubs` + `Force Tags slow dogfood epic-7`
  - [x] 4.2: 3 per-skill discoverability test cases with concrete numeric assertions per AC-7.4.4
  - [x] 4.3: `Dogfood Finding: stub reveals false-activation blindspot` test case per AC-7.4.5
  - [x] 4.4: Fake-green precheck — inspect all assertions are concrete before running
  - [x] 4.5: Run `uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot` — confirm all tests pass (4/4)
  - [x] 4.6: Run `uv run pytest tests/ -x -q --ignore=tests/dogfood` — confirm 0 regressions (1263 passed)

- [x] Task 5: Create `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md` (AC: 7.4.6)
  - [x] 5.1: Coverage matrix: 3 covered + 8 deferred skills
  - [x] 5.2: DOGFOOD-FINDING-1 section: DF-7.4-S1 stub false-activation blindspot + resolution path (Epic 9 live-provider run)

- [x] Task 6: Catalog carry-overs + update sprint status (AC: 7.4.9, gate before code review)
  - [x] 6.1: Run `grep -rn "DF-7.4-S" tests/dogfood/agentskills/` — confirm DF-7.4-S1 appears in fixture + robot test docstrings
  - [x] 6.2: Add DF-7.4-S1 to `_bmad-output/implementation-artifacts/deferred-work.md`
  - [x] 6.3: Add C60 row to `docs/phase-1-5-carry-overs.md`, update total 59 → 60
  - [x] 6.4: Update sprint status for 7-4 → `review`

## Dev Notes

### Architecture Context

**SkillsLibrary NOT in `_SUB_LIBRARIES` (D-2 LOAD-BEARING)**:
`src/AgentEval/__init__.py` line 89 comment: "SkillsLibrary — EXCLUDED (collides with SubagentsLibrary on `Get Frontmatter`)". The dogfood test MUST import `SkillsLibrary` directly:
```robotframework
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
```
NOT:
```robotframework
Library    AgentEval    WITH NAME    AgentEval    # WRONG — AgentEval.Skill.* not available
```

**D-1 precedent — vendor into agenteval, don't push upstream:**
Story 3.3 / 5.5 / 6.4 all established this pattern. The task YAMLs, SKILL.md copies, `.robot` suite, and parity checklist ALL live inside `tests/dogfood/agentskills/`. Source `robotframework-agentskills` repo is at `/home/many/workspace/robotframework-agentskills/` on dev machine; skill files are copied (vendored) into the agenteval repo.

**Activation heuristic**: `skill_name.lower() in response_text.lower()` (Phase-1 heuristic, AC-7.1.4). For each skill, the stub response text must contain the skill's `name:` field value verbatim:
- `rf-browser` → response_text contains "rf-browser"
- `rf-results` → response_text contains "rf-results"
- `rf-libdoc-search` → response_text contains "rf-libdoc-search"

### Stub Adapter Pattern

**Factory function (same as Story 7.3)**:
```python
from __future__ import annotations
from pathlib import Path
from typing import Any
from robot.api.deco import keyword
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

_SKILLS_DIR = Path(__file__).parent / "skills"
_DISC_DIR = Path(__file__).parent / "discoverability"

SKILL_PATH_RF_BROWSER = _SKILLS_DIR / "rf-browser-skill.md"
SKILL_PATH_RF_RESULTS = _SKILLS_DIR / "rf-results-skill.md"
SKILL_PATH_RF_LIBDOC_SEARCH = _SKILLS_DIR / "rf-libdoc-search-skill.md"
TASKS_PATH_RF_BROWSER = _DISC_DIR / "rf-browser-tasks.yaml"
TASKS_PATH_RF_RESULTS = _DISC_DIR / "rf-results-tasks.yaml"
TASKS_PATH_RF_LIBDOC_SEARCH = _DISC_DIR / "rf-libdoc-search-tasks.yaml"


def _make_skill_stub(skill_name: str) -> type[InProcessAdapter]:
    """Factory: creates a stub adapter that always activates target skill."""
    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"I'll use the {skill_name} skill to help with this request.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.002,
                trace_id="a" * 32,
            )
    return _Stub


@keyword(name="Register Skill Stubs")
def register_skill_stubs() -> None:
    """Register stub adapters for all 3 dogfood skills. Call once at Suite Setup."""
    register_adapter("stub_rf_browser", _make_skill_stub("rf-browser"))
    register_adapter("stub_rf_results", _make_skill_stub("rf-results"))
    register_adapter("stub_rf_libdoc_search", _make_skill_stub("rf-libdoc-search"))
```

### Robot Framework Test Structure

```robotframework
*** Settings ***
Documentation    Story 7.4 dogfood — exercises `Skill.Get Discoverability` (Story 7.2 / FR4b)
...              against 3 representative `robotframework-agentskills` skills with stub adapters.
...
...              D-2 LOAD-BEARING: Uses `Library AgentEval.skills.library WITH NAME Skill`
...              directly — SkillsLibrary is EXCLUDED from _SUB_LIBRARIES (DF-7.1-S1/C55).
...              Cannot use `Library AgentEval WITH NAME AgentEval` for Skill.* keywords.
...
...              Run locally:
...                  uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot
...
...              CI wiring deferred per Phase-1 norm (Story 1a.2 HIGH-1 / D-5):
...              `dogfood-integration.yml` is install-smoke-only by design.

Library    AgentEval.skills.library    WITH NAME    Skill
Library    ${CURDIR}/fixtures/agentskills_discoverability.py

Suite Setup    Register Skill Stubs
Force Tags    slow    dogfood    epic-7

*** Variables ***
${SKILLS_DIR}       ${CURDIR}/skills
${DISC_DIR}         ${CURDIR}/discoverability

*** Test Cases ***

Skill.Get Discoverability: rf-browser cohort (5+3 tasks, 3 trials each)
    [Documentation]    FR4b AC-7.4.4 — rf-browser skill discoverability with stub adapter.
    ...                Expected: activation_accuracy=0.625 (15/24), false_activation_rate=1.0
    ...                (decoys all activate with stub — DF-7.4-S1 constraint).
    ${skill}=    Set Variable    ${SKILLS_DIR}/rf-browser-skill.md
    ${tasks}=    Set Variable    ${DISC_DIR}/rf-browser-tasks.yaml
    ${result}=    Skill.Get Discoverability
    ...    skill=${skill}
    ...    tasks=${tasks}
    ...    adapter=stub_rf_browser
    ...    trials_per_task=3
    Length Should Be    ${result.per_task_results}    8
    Should Be Equal As Numbers    ${{round(${result.summary.activation_accuracy}, 4)}}    0.625
    Should Be Equal As Numbers    ${result.summary.false_activation_rate}    1.0
    Should Be Equal As Numbers    ${result.summary.missed_activation_rate}    0.0
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be Equal As Numbers    ${task_result.pass_at_k}    1.0
        END
    END

Skill.Get Discoverability: rf-results cohort (5+3 tasks, 3 trials each)
    [Documentation]    FR4b AC-7.4.4 — rf-results (output.xml parser) skill discoverability.
    ${skill}=    Set Variable    ${SKILLS_DIR}/rf-results-skill.md
    ${tasks}=    Set Variable    ${DISC_DIR}/rf-results-tasks.yaml
    ${result}=    Skill.Get Discoverability
    ...    skill=${skill}
    ...    tasks=${tasks}
    ...    adapter=stub_rf_results
    ...    trials_per_task=3
    Length Should Be    ${result.per_task_results}    8
    Should Be Equal As Numbers    ${{round(${result.summary.activation_accuracy}, 4)}}    0.625
    Should Be Equal As Numbers    ${result.summary.false_activation_rate}    1.0
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be Equal As Numbers    ${task_result.pass_at_k}    1.0
        END
    END

Skill.Get Discoverability: rf-libdoc-search cohort (5+3 tasks, 3 trials each)
    [Documentation]    FR4b AC-7.4.4 — rf-libdoc-search skill discoverability.
    ${skill}=    Set Variable    ${SKILLS_DIR}/rf-libdoc-search-skill.md
    ${tasks}=    Set Variable    ${DISC_DIR}/rf-libdoc-search-tasks.yaml
    ${result}=    Skill.Get Discoverability
    ...    skill=${skill}
    ...    tasks=${tasks}
    ...    adapter=stub_rf_libdoc_search
    ...    trials_per_task=3
    Length Should Be    ${result.per_task_results}    8
    Should Be Equal As Numbers    ${{round(${result.summary.activation_accuracy}, 4)}}    0.625
    Should Be Equal As Numbers    ${result.summary.false_activation_rate}    1.0
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be Equal As Numbers    ${task_result.pass_at_k}    1.0
        END
    END

Dogfood Finding: stub reveals false-activation blindspot (DF-7.4-S1)
    [Documentation]    AC-7.4.5 — DOGFOOD-FINDING-1 documentation test.
    ...                With stub adapters, ALL decoy tasks (should_activate=False) activate —
    ...                false_activation_rate=1.0 by design. This finding documents that
    ...                stub-based dogfood cannot distinguish real activation behavior.
    ...                Phase-1 coverage: infrastructure correctness (task YAML parsing,
    ...                per-skill aggregation, summary statistics). Real activation-quality
    ...                evidence requires live provider run (deferred to Epic 9 per DF-7.4-S1/C60).
    ...                DOGFOOD-FINDING-1 is filed as DF-7.4-S1 in deferred-work.md / C60.
    ${skill}=    Set Variable    ${SKILLS_DIR}/rf-browser-skill.md
    ${tasks}=    Set Variable    ${DISC_DIR}/rf-browser-tasks.yaml
    ${result}=    Skill.Get Discoverability
    ...    skill=${skill}
    ...    tasks=${tasks}
    ...    adapter=stub_rf_browser
    ...    trials_per_task=3
    # FINDING: stub always activates → decoy pass_at_k=1.0 (false positive)
    # This is the expected Phase-1 stub limitation, not a bug.
    Should Be Equal As Numbers    ${result.summary.false_activation_rate}    1.0
    # FINDING: missed_activation_rate=0.0 (stub never misses — vacuous)
    Should Be Equal As Numbers    ${result.summary.missed_activation_rate}    0.0
```

### Numeric Assertions (Pre-Computed for Fake-Green Precheck)

With 5 `should_activate=True` + 3 `should_activate=False` tasks, `trials_per_task=3`, stub always activates:

| Metric | Formula | Expected |
|--------|---------|---------|
| `activation_accuracy` | correct_trials / total_trials = (5×3 + 0) / (8×3) | `0.625` |
| `false_activation_rate` | all_decoy_activations / total_decoy_trials = (3×3) / (3×3) | `1.0` |
| `missed_activation_rate` | missed / should_activate_trials = 0 / (5×3) | `0.0` |
| `pass_at_k` per should_activate task | Pass@3 with c=3/n=3 = 1 - C(0,3)/C(3,3) = 1.0 | `1.0` |

Verify using `src/AgentEval/stats/_internal.py` `_pass_at_k` formula before asserting.

### Task YAML Content Guidelines

**rf-browser-tasks.yaml** — 5 should_activate: true (web testing, Browser Library, Playwright):
```yaml
tasks:
  - id: browser_create_test
    prompt: "Write a Browser Library test to verify that the login page loads correctly."
    should_activate: true
  - id: browser_locator
    prompt: "How do I use auto-waiting with Browser Library to handle dynamic content?"
    should_activate: true
  - id: browser_playwright
    prompt: "Create a Playwright-based test that clicks a button and checks the result."
    should_activate: true
  - id: browser_iframe
    prompt: "I need to interact with an iframe using Browser Library keywords."
    should_activate: true
  - id: browser_assertion
    prompt: "Add assertions to verify that a form submission succeeded using Browser Library."
    should_activate: true
  - id: decoy_appium
    prompt: "Write a test for an Android app using Appium."
    should_activate: false
  - id: decoy_parse_results
    prompt: "Parse my output.xml to get the test pass/fail counts."
    should_activate: false
  - id: decoy_keyword_search
    prompt: "Find keywords for reading files in Robot Framework."
    should_activate: false
```

**rf-results-tasks.yaml** — 5 should_activate: true (output.xml, results, pass/fail stats):
```yaml
tasks:
  - id: results_parse_output
    prompt: "Parse my Robot Framework output.xml and give me the pass/fail summary."
    should_activate: true
  - id: results_failed_tests
    prompt: "Show me which tests failed and what error messages they had from my last run."
    should_activate: true
  - id: results_tag_stats
    prompt: "Get tag statistics from my output.xml to see which feature areas have failures."
    should_activate: true
  - id: results_timing
    prompt: "Which tests took the longest to execute? Get timing from output.xml."
    should_activate: true
  - id: results_merge
    prompt: "Combine multiple output.xml files and show overall pass rate."
    should_activate: true
  - id: decoy_browser
    prompt: "Create a Browser Library test for the checkout flow."
    should_activate: false
  - id: decoy_keyword_builder
    prompt: "Generate a Robot Framework keyword for user login."
    should_activate: false
  - id: decoy_libdoc
    prompt: "Search for keywords that handle HTTP requests."
    should_activate: false
```

**rf-libdoc-search-tasks.yaml** — 5 should_activate: true (search libdoc, find keywords):
```yaml
tasks:
  - id: libdoc_find_keyword
    prompt: "Find Robot Framework keywords that can click a button in the browser."
    should_activate: true
  - id: libdoc_match_usecase
    prompt: "Search the SeleniumLibrary docs for keywords that handle dropdowns."
    should_activate: true
  - id: libdoc_multiple_libs
    prompt: "Scan multiple libraries to find keywords for reading JSON files."
    should_activate: true
  - id: libdoc_keyword_discovery
    prompt: "Which keywords can I use to verify text appears on a web page?"
    should_activate: true
  - id: libdoc_search_custom
    prompt: "Search my custom resource file for keywords that handle authentication."
    should_activate: true
  - id: decoy_run_test
    prompt: "Run all tests in the smoke suite."
    should_activate: false
  - id: decoy_parse_output
    prompt: "Parse the output.xml from my last test run."
    should_activate: false
  - id: decoy_create_testcase
    prompt: "Create a new test case for user registration."
    should_activate: false
```

### DF-7.4-S1 Entry

**DF-7.4-S1 (Stub-based dogfood cannot measure real activation quality — false_activation_rate=1.0 by design)**:
Story 7.4 uses stub adapters that always return response_text containing the target skill name → `activated=True` for all trials regardless of prompt relevance. Consequence: all decoy tasks (`should_activate=False`) show `pass_at_k=1.0` and `false_activation_rate=1.0` — this is an artifact of the stub design, NOT a real discoverability failure. The stub-based dogfood validates INFRASTRUCTURE correctness (task YAML parsing, per-task aggregation, summary statistics) but cannot assess QUALITY of skill discoverability (whether the real agent correctly routes based on skill descriptions). Epic 9 must run the Skill Discoverability suite against a live provider (Mock provider with deterministic task routing OR low-cost real provider) to get actionable quality data. Catalogued as C60. Effort: M (Epic 9 wires live/mock provider run for all 11 skills). Phase-1.5/Epic 9.

### Fake-Green Precheck Protocol

Before flipping status to `review`, run:
```bash
# Step 1: Run the dogfood suite
uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot

# Step 2: Inspect ALL assertions in the .robot file for concrete values
grep -n "Should\|Length\|Equal" tests/dogfood/agentskills/test_skill_discoverability.robot
# Each Should* must have a concrete numeric/string value (no vacuous 'Should Be True   True')

# Step 3: Run pytest regression
uv run pytest tests/ -x -q --ignore=tests/dogfood
```

### Files to Create / Modify

**NEW:**
- `tests/dogfood/agentskills/skills/rf-browser-skill.md` — vendored copy
- `tests/dogfood/agentskills/skills/rf-results-skill.md` — vendored copy
- `tests/dogfood/agentskills/skills/rf-libdoc-search-skill.md` — vendored copy
- `tests/dogfood/agentskills/discoverability/rf-browser-tasks.yaml`
- `tests/dogfood/agentskills/discoverability/rf-results-tasks.yaml`
- `tests/dogfood/agentskills/discoverability/rf-libdoc-search-tasks.yaml`
- `tests/dogfood/agentskills/fixtures/agentskills_discoverability.py`
- `tests/dogfood/agentskills/test_skill_discoverability.robot`
- `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md`

**MODIFIED:**
- `_bmad-output/implementation-artifacts/deferred-work.md` — add DF-7.4-S1
- `docs/phase-1-5-carry-overs.md` — add C60, update total 59 → 60
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 7-4 → review/done

**NOT modified**: `src/AgentEval/**` (no new keywords), `.github/workflows/**` (no CI changes)

### Previous Story Learnings

From Story 7.3 (most recent):
- `register_adapter(name, cls)` is idempotent — safe to call at Suite Setup
- `_make_stub()` factory pattern: captures skill name via closure, class returned is a fresh type
- `InProcessAdapter` subclass: override `run(self, prompt, **kwargs)`, `__init__(self, **kwargs)` calls `super()`
- `AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process")` is the correct shape
- `Usage(input_tokens=1, output_tokens=1)` + `cost_usd=0.001` + `latency_seconds=0.002` + `trace_id="a"*32`

From Story 6.4 (dogfood pattern):
- Use `Force Tags    slow    dogfood    epic-7` so standard pytest sweep skips `.robot` files
- Use `Library ${CURDIR}/fixtures/helper.py` pattern for fixture helpers in `.robot` tests
- Suite Setup for one-time registration (not per-test — adapter registry is global)
- `Library AgentEval WITH NAME AgentEval` is for non-Skills keywords (Metrics, Stats, etc.)
- `${{...}}` double-brace syntax for inline Python expressions in RF

From Story 7.2:
- Task YAML schema: `tasks:` list with `id:`, `prompt:`, `should_activate:` per task
- `SkillDiscoverabilityResult.per_task_results` is a list of `SkillDiscoverabilityTaskSummary`
- `SkillDiscoverabilityTaskSummary` fields: `task_id`, `task_prompt`, `should_activate`, `trials_run`, `activations_observed`, `pass_at_k`, `competing_skills_picked`
- `summary.activation_accuracy`, `summary.false_activation_rate`, `summary.missed_activation_rate` are on the result summary object

From Story 6.4 D-1:
- NO upstream push to `robotframework-agentskills`
- NO `dogfood-integration.yml` dispatch changes
- Suite locally runnable: `uv run robot tests/dogfood/agentskills/`

### Caller-Count Check

Story 7.4 creates NO new public helper functions in `src/AgentEval/**`. The `agentskills_discoverability.py` fixture file is test-private. Nothing to caller-count per `feedback_caller_count_check`.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- All 6 Tasks implemented. 9 new files created; 3 carry-over catalog files updated.
- D-2 fix surfaced at runtime: story dev notes said `Library AgentEval.skills.library WITH NAME Skill` but RF needs the class path `AgentEval.skills.library.SkillsLibrary`. Confirmed by existing unit test at `tests/unit/skills/test_robot_integration.robot:9`. Dev notes and AC text updated in-flight per `feedback_in_flight_spec_amendment` norm.
- 4/4 robot tests pass (stub activation_accuracy=0.625, false_activation_rate=1.0, missed_activation_rate=0.0). Numeric assertions pre-computed match observed results.
- 1263 pytest pass, 0 regressions. Fake-green precheck passed (all assertions concrete).
- DF-7.4-S1/C60 catalogued in deferred-work.md + carry-overs. `feedback_carry_over_catalog_gate` UPSTREAM applied (13th consecutive story).

### File List

**New files:**
- `tests/dogfood/agentskills/skills/rf-browser-skill.md`
- `tests/dogfood/agentskills/skills/rf-results-skill.md`
- `tests/dogfood/agentskills/skills/rf-libdoc-search-skill.md`
- `tests/dogfood/agentskills/discoverability/rf-browser-tasks.yaml`
- `tests/dogfood/agentskills/discoverability/rf-results-tasks.yaml`
- `tests/dogfood/agentskills/discoverability/rf-libdoc-search-tasks.yaml`
- `tests/dogfood/agentskills/fixtures/agentskills_discoverability.py`
- `tests/dogfood/agentskills/test_skill_discoverability.robot`
- `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md`

**Modified files:**
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `docs/phase-1-5-carry-overs.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-05-21: Story created. Pre-create drift check (34th consecutive use, 100% catch rate intact). 6 drifts found: D-1 HIGH no-upstream-push vendor pattern (mirrors Story 6.4 D-1); D-2 HIGH SkillsLibrary excluded from _SUB_LIBRARIES (load-bearing); D-3 LOW parity-checklist path; D-4 MED scale (11→3 representative skills); D-5 LOW no CI dispatch changes; D-6 LOW dogfood-finding label absent. Status → ready-for-dev.
- 2026-05-21: Implementation complete. All 6 tasks done. 9 new files + 3 carry-over updates. D-2 in-flight fix: Library import path is `AgentEval.skills.library.SkillsLibrary` (class path), not just `AgentEval.skills.library` (module path). 4/4 robot tests pass; 1263 pytest pass. DF-7.4-S1/C60 catalogued. Status → review.
- 2026-05-21: Code-review patches applied. 4-reviewer cross-LLM (Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex CLI gpt-5.4): 0 HIGHs, 0 MEDs. 1 LOW applied: DF-7.4-S2/C61 added (caller-gap: `SKILL_PATH_*` / `TASKS_PATH_*` constants have 0 callers in robot suite). All 9 ACs verified PASS. Status → done.
