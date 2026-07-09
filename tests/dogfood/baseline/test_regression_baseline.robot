*** Settings ***
Documentation    add-regression-baseline-tracking dogfood — exercises the
...              snapshot -> regression-gate -> trend surface end-to-end. The
...              real Mock-provider path (NO API keys) drives Stat.Run N Times
...              -> Save Metrics Baseline -> Metrics Should Not Regress (PASS)
...              -> Get Metric Trend. The statistical FAIL / PASS-with-warning
...              bands are driven through controlled KeywordRun fixtures (the
...              Mock provider always returns completeness="complete", so a
...              mock run can only demonstrate the no-regression band). See
...              parity-checklist-baseline.md for the VALIDATION-CEILING.
...
...              Run locally:
...                  uv run robot tests/dogfood/baseline/test_regression_baseline.robot

Library    AgentEval    provider=mock    WITH NAME    AgentEval
Library    OperatingSystem
Library    _baseline_runs.py

Force Tags    slow    dogfood    baseline

*** Test Cases ***

Mock run round-trips through save -> regress -> trend
    [Documentation]    Real Mock-provider fan-out: Stat.Run N Times drives 10
    ...                Send Prompt trials, snapshots a baseline, gates the same
    ...                run against it (PASS), and reads the trend series back.
    @{runs}=    AgentEval.Stat.Run N Times    n=10    keyword=Send Prompt
    ...    keyword_args=${{ ['adapter=generic', 'prompt=hello', 'model=mock/mock'] }}
    ${base}=    AgentEval.Save Metrics Baseline    ${runs}
    ...    path=${OUTPUT DIR}/baselines/main.json    history=${OUTPUT DIR}/baselines/history.jsonl
    Should Be Equal As Integers    ${base.metrics['pass_rate'].trials}    10
    File Should Exist    ${OUTPUT DIR}/baselines/main.json
    ${report}=    AgentEval.Metrics Should Not Regress    ${runs}
    ...    baseline=${OUTPUT DIR}/baselines/main.json    tolerance=5%
    Should Be Equal    ${report.regressed}    ${FALSE}
    ${series}=    AgentEval.Get Metric Trend    metric=pass_at_1    history=${OUTPUT DIR}/baselines/history.jsonl
    Length Should Be    ${series.points}    1

Baseline JSON is deterministic and schema-versioned
    [Documentation]    Two snapshots of the same runs to two paths differ only
    ...                by run_context timestamp/git fields.
    @{runs}=    Make Keyword Runs    45    50
    AgentEval.Save Metrics Baseline    ${runs}    path=${OUTPUT DIR}/a.json    timestamp=2026-07-09T00:00:00+00:00
    AgentEval.Save Metrics Baseline    ${runs}    path=${OUTPUT DIR}/b.json    timestamp=2026-07-09T00:00:00+00:00
    ${a}=    Get File    ${OUTPUT DIR}/a.json
    ${b}=    Get File    ${OUTPUT DIR}/b.json
    Should Be Equal    ${a}    ${b}
    Should Contain    ${a}    "schema_version": 1

Real regression beyond tolerance fails the gate
    [Documentation]    Baseline 45/50 vs current 5/50 (tol 5%) -> CIs disjoint
    ...                -> Metrics Should Not Regress raises AssertionError.
    @{base_runs}=    Make Keyword Runs    45    50
    AgentEval.Save Metrics Baseline    ${base_runs}    path=${OUTPUT DIR}/reg.json
    @{bad_runs}=    Make Keyword Runs    5    50
    Run Keyword And Expect Error    *regressed*
    ...    AgentEval.Metrics Should Not Regress    ${bad_runs}    baseline=${OUTPUT DIR}/reg.json    tolerance=5%

Within-CI-overlap drop passes with a PossibleRegressionWarning
    [Documentation]    Baseline 9/10 vs current 7/10 (tol 5%) -> tolerance
    ...                breached but Wilson CIs overlap -> PASS (not a failure).
    @{base_runs}=    Make Keyword Runs    9    10
    AgentEval.Save Metrics Baseline    ${base_runs}    path=${OUTPUT DIR}/noisy.json
    @{curr_runs}=    Make Keyword Runs    7    10
    ${report}=    AgentEval.Metrics Should Not Regress    ${curr_runs}    baseline=${OUTPUT DIR}/noisy.json    tolerance=5%
    Should Be Equal    ${report.regressed}    ${FALSE}

Missing baseline raises a structured BaselineNotFoundError
    [Documentation]    The read path fails loud with the save-then-commit fix.
    @{runs}=    Make Keyword Runs    9    10
    Run Keyword And Expect Error    *BASELINE_NOT_FOUND*
    ...    AgentEval.Metrics Should Not Regress    ${runs}    baseline=${OUTPUT DIR}/does-not-exist.json

Trend series exposes an ASCII trend grid
    [Documentation]    Three appended snapshots -> 3 ordered points + a
    ...                metrics x snapshots grid reusing the heatmap renderer.
    @{r1}=    Make Keyword Runs    45    50
    @{r2}=    Make Keyword Runs    40    50
    @{r3}=    Make Keyword Runs    30    50
    AgentEval.Save Metrics Baseline    ${r1}    path=${OUTPUT DIR}/t.json    history=${OUTPUT DIR}/trend.jsonl
    AgentEval.Save Metrics Baseline    ${r2}    path=${OUTPUT DIR}/t.json    history=${OUTPUT DIR}/trend.jsonl
    AgentEval.Save Metrics Baseline    ${r3}    path=${OUTPUT DIR}/t.json    history=${OUTPUT DIR}/trend.jsonl
    ${series}=    AgentEval.Get Metric Trend    metric=pass_at_1    history=${OUTPUT DIR}/trend.jsonl
    Length Should Be    ${series.points}    3
    ${grid}=    Set Variable    ${series.grid.as_ascii()}
    Should Contain    ${grid}    pass_at_1
    Log    ${grid}
