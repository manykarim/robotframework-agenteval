# Parity Checklist: `robotframework-agentskills` Skill Discoverability

Story 7.4 — Interleaved Dogfood port. Tracks coverage of `robotframework-agentskills`'
skill-discoverability domain by `.robot` suites exercising agenteval's Story 7.2
`Skill.Get Discoverability` keyword (FR4b).

**Source corpus:** `/home/many/workspace/robotframework-agentskills/skills/` (11 skills)
**Vendored skill files:** `tests/dogfood/agentskills/skills/`
**Task YAML files:** `tests/dogfood/agentskills/discoverability/`
**Dogfood suite:** `tests/dogfood/agentskills/test_skill_discoverability.robot`
**Fixture helper:** `tests/dogfood/agentskills/fixtures/agentskills_discoverability.py`

## Scope

Story 7.4 validates the `Skill.Get Discoverability` infrastructure (task YAML parsing,
per-skill aggregation, summary statistics) with stub adapters. 3 of 11 agentskills
skills are covered as representative samples (1 per domain category). Remaining 8
skills deferred to Epic 9 per D-4 scale constraint.

## CI wiring deferred per Phase-1 norm

`dogfood-integration.yml` stays smoke-only (Story 1a.2 HIGH-1 ratification).
Full cross-repo CI dispatch deferred to **Story 9.1+9.2** per architecture L1718 +
epic L1564. Story 7.4 ships suites locally runnable via:

    uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot

## Coverage matrix (Story 7.4 scope)

### Covered skills (3 of 11)

| Skill | Domain | Task YAML | Vendored skill file | Tests | Status |
| --- | --- | --- | --- | --- | --- |
| `rf-browser` | Web execution / Browser Library / Playwright | `rf-browser-tasks.yaml` | `rf-browser-skill.md` | "rf-browser cohort (5+3 tasks, 3 trials each)" | ✓ |
| `rf-results` | Analysis / output.xml parsing | `rf-results-tasks.yaml` | `rf-results-skill.md` | "rf-results cohort (5+3 tasks, 3 trials each)" | ✓ |
| `rf-libdoc-search` | Search / keyword discovery | `rf-libdoc-search-tasks.yaml` | `rf-libdoc-search-skill.md` | "rf-libdoc-search cohort (5+3 tasks, 3 trials each)" | ✓ |

### Deferred skills (8 of 11 → Epic 9)

| Skill | Domain | Deferral reason |
| --- | --- | --- |
| `rf-appium` | Mobile / Appium | D-4 scale constraint — representative coverage by rf-browser (execution domain) |
| `rf-keyword-builder` | Keyword authoring | D-4 scale constraint |
| `rf-libdoc-explain` | Keyword explanation | D-4 scale constraint — similar domain to rf-libdoc-search |
| `rf-requests` | HTTP / REST | D-4 scale constraint |
| `rf-resource-architect` | Resource file design | D-4 scale constraint |
| `rf-restinstance` | REST instance testing | D-4 scale constraint |
| `rf-selenium` | Web execution / Selenium | D-4 scale constraint — similar domain to rf-browser |
| `rf-testcase-builder` | Test case authoring | D-4 scale constraint |

Full coverage of all 11 skills deferred to **Epic 9** per architecture D-4 scope reduction.

## Dogfood findings (≥1 per AC-7.4.6)

### DOGFOOD-FINDING-1 / DF-7.4-S1 — Stub false-activation blindspot

**Severity:** MEDIUM (Phase-1 infrastructure limitation, not a production bug)
**Surface:** `tests/dogfood/agentskills/test_skill_discoverability.robot` test case
"Dogfood Finding: stub reveals false-activation blindspot"

**Finding:** Stub-based dogfood cannot measure real activation quality. Each stub
adapter always returns `response_text` containing the target skill name:

    "I'll use the rf-browser skill to help with this request."

The Phase-1 activation heuristic (`skill_name.lower() in response_text.lower()`) fires
for **every trial regardless of prompt content** — including decoy tasks where
`should_activate=False`. Consequence:

- `false_activation_rate = 1.0` (all 9 decoy-task trials activate — expected with stub)
- `missed_activation_rate = 0.0` (vacuous — stub never misses)
- `activation_accuracy = 0.625` (15/24 correct — only should_activate tasks score correctly)

**Phase-1 coverage:** Infrastructure correctness is verified — task YAML parsing,
per-skill aggregation, summary statistics, pass_at_k computation all work correctly.
What the stub CANNOT measure: whether a real LLM agent discriminates between
on-topic and off-topic prompts when choosing to invoke a skill.

**Resolution path:** Epic 9 live-provider dogfood run using a real LLM adapter (not
stub) will measure genuine `false_activation_rate` discrimination quality. The stub
finding is documented as the Phase-1 baseline.

**Tracked as:** DF-7.4-S1 in `_bmad-output/implementation-artifacts/deferred-work.md` /
C60 in `docs/phase-1-5-carry-overs.md`.

## Story 7.4 execution notes

- **D-2 LOAD-BEARING:** `test_skill_discoverability.robot` imports
  `AgentEval.skills.library.SkillsLibrary WITH NAME Skill` directly.
  `SkillsLibrary` is EXCLUDED from `_SUB_LIBRARIES` (DF-7.1-S1/C55 — name collision
  with `SubagentsLibrary` on `Get Frontmatter`). Cannot use top-level `AgentEval`.
- **Stub adapter pattern:** `_make_skill_stub(skill_name)` factory in `fixtures/agentskills_discoverability.py`.
  `register_skill_stubs()` RF keyword called at Suite Setup.
- **Numeric assertions:** pre-computed before test authoring (fake-green precheck);
  all assertions are concrete equality checks (0.625, 1.0, 0.0, 8) — no vacuous
  `Should Be True    True` forms.
- **Tags:** `[Force Tags] slow dogfood epic-7` — excluded from default pytest sweep.
- **Test run:** 4/4 tests pass locally (2026-05-21).

## Status

- **Phase-1 close:** dogfood suite passes locally (4/4 tests). DF-7.4-S1 catalogued
  for Phase-1.5 / Epic 9 live-provider run.
- **Full AC-DOGFOOD-01 closure:** remaining 8 skills + live-provider activation quality
  → Epic 9 (C60 carry-over).
