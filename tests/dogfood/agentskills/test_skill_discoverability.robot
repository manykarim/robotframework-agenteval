*** Settings ***
Documentation    Story 7.4 dogfood — exercises ``Skill.Get Discoverability`` (Story 7.2 / FR4b)
...              against 3 representative ``robotframework-agentskills`` skills with stub adapters.
...
...              D-2 LOAD-BEARING: Uses ``Library AgentEval.skills.library.SkillsLibrary WITH NAME Skill``
...              directly — SkillsLibrary is EXCLUDED from _SUB_LIBRARIES (DF-7.1-S1/C55).
...              Cannot use ``Library AgentEval WITH NAME AgentEval`` for Skill.* keywords.
...
...              Stub adapters always activate target skill (DF-7.4-S1 constraint):
...                  activation_accuracy=0.625 (15/24), false_activation_rate=1.0 by design.
...              Real activation-quality evidence deferred to Epic 9 (C60).
...
...              Run locally:
...                  uv run robot tests/dogfood/agentskills/test_skill_discoverability.robot
...
...              CI wiring deferred per Phase-1 norm (Story 1a.2 HIGH-1 / D-5):
...              ``dogfood-integration.yml`` is install-smoke-only by design.

Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
Library    ${CURDIR}/fixtures/agentskills_discoverability.py

Suite Setup    Register Skill Stubs

Force Tags    slow    dogfood    epic-7

*** Variables ***
${SKILLS_DIR}       ${CURDIR}/skills
${DISC_DIR}         ${CURDIR}/discoverability

*** Test Cases ***

Skill.Get Discoverability: rf-browser cohort (5+3 tasks, 3 trials each)
    [Documentation]    FR4b AC-7.4.4 — rf-browser skill discoverability with stub adapter.
    ...                5 should_activate + 3 should_not_activate tasks, trials_per_task=3.
    ...                Expected: activation_accuracy=0.625 (15/24 correct trials),
    ...                false_activation_rate=1.0 (decoy tasks always activate — DF-7.4-S1),
    ...                missed_activation_rate=0.0 (stubs never miss should_activate tasks).
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
    ...                5 should_activate + 3 should_not_activate tasks, trials_per_task=3.
    ...                Expected: activation_accuracy=0.625, false_activation_rate=1.0 (DF-7.4-S1),
    ...                missed_activation_rate=0.0.
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
    Should Be Equal As Numbers    ${result.summary.missed_activation_rate}    0.0
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be Equal As Numbers    ${task_result.pass_at_k}    1.0
        END
    END

Skill.Get Discoverability: rf-libdoc-search cohort (5+3 tasks, 3 trials each)
    [Documentation]    FR4b AC-7.4.4 — rf-libdoc-search skill discoverability.
    ...                5 should_activate + 3 should_not_activate tasks, trials_per_task=3.
    ...                Expected: activation_accuracy=0.625, false_activation_rate=1.0 (DF-7.4-S1),
    ...                missed_activation_rate=0.0.
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
    Should Be Equal As Numbers    ${result.summary.missed_activation_rate}    0.0
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be Equal As Numbers    ${task_result.pass_at_k}    1.0
        END
    END

Dogfood Finding: stub reveals false-activation blindspot (DF-7.4-S1)
    [Documentation]    AC-7.4.5 — DOGFOOD-FINDING-1 documentation test.
    ...                With stub adapters, ALL decoy tasks (should_activate=False) activate —
    ...                false_activation_rate=1.0 by design. The stub always embeds the target
    ...                skill name in response_text, so the Phase-1 activation heuristic
    ...                (substring check) fires for every trial regardless of prompt content.
    ...                This finding documents that stub-based dogfood cannot distinguish real
    ...                activation behavior from false positives.
    ...
    ...                Phase-1 coverage: infrastructure correctness (task YAML parsing,
    ...                per-skill aggregation, summary statistics). Real activation-quality
    ...                evidence (false-positive discrimination) requires a live provider run
    ...                deferred to Epic 9 per DF-7.4-S1/C60 in deferred-work.md.
    ...
    ...                DOGFOOD-FINDING-1 is filed as DF-7.4-S1 in deferred-work.md / C60.
    ${skill}=    Set Variable    ${SKILLS_DIR}/rf-browser-skill.md
    ${tasks}=    Set Variable    ${DISC_DIR}/rf-browser-tasks.yaml
    ${result}=    Skill.Get Discoverability
    ...    skill=${skill}
    ...    tasks=${tasks}
    ...    adapter=stub_rf_browser
    ...    trials_per_task=3
    # FINDING: stub always activates → decoy tasks get false positive (pass_at_k=1.0)
    # This is the expected Phase-1 stub limitation, not a bug.
    Should Be Equal As Numbers    ${result.summary.false_activation_rate}    1.0
    # FINDING: missed_activation_rate=0.0 (stub never misses — vacuous with stub)
    Should Be Equal As Numbers    ${result.summary.missed_activation_rate}    0.0
