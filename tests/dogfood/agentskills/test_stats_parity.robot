*** Settings ***
Documentation    Story 6.4 dogfood — exercises agenteval's Story 6.3 `StatsLibrary`
...              + top-level `Get Keyword Tier` surface against fixtures parallel-
...              derived from agentskills' batch-Pass@k scoring domain.
...
...              Coverage: 4 Stat keywords + Get Keyword Tier introspection +
...              FR28 PollingDisallowedError gate empirical verification.
...
...              Run locally:
...                  uv run robot tests/dogfood/agentskills/test_stats_parity.robot

Library    AgentEval    WITH NAME    AgentEval
Library    ${CURDIR}/fixtures/agentskills_sessions.py

Force Tags    slow    dogfood    epic-6

*** Test Cases ***

Get Keyword Tier returns 1 for Get Tool Call Count
    [Documentation]    FR30a — `Get Keyword Tier` introspection against a Tier-1 metric keyword.
    ...                NOTE: Story 6.1 `MetricsLibrary` keywords don't carry a `Metric.`
    ...                namespace prefix in their `@keyword(name=...)` registration —
    ...                only Story 6.3 `Stat.*` keywords use a namespace prefix. PRD
    ...                documentation calls them `Metric.Get Tool Call Count`
    ...                semantically (sub-library scope) but the actual RF surface is
    ...                un-prefixed. Tracked as DF-6.4-S2 documentation drift.
    ${tier}=    AgentEval.Get Keyword Tier    Get Tool Call Count
    Should Be Equal As Integers    ${tier}    1

Get Keyword Tier returns 1 for Tool Call Should Have Occurred
    [Documentation]    FR30a — Tier-1 assertion keyword introspection.
    ${tier}=    AgentEval.Get Keyword Tier    Tool Call Should Have Occurred
    Should Be Equal As Integers    ${tier}    1

Get Keyword Tier returns 3 for Stat.Run N Times
    [Documentation]    FR30a — Tier-3 fan-out keyword per D-14 amendment.
    ${tier}=    AgentEval.Get Keyword Tier    Stat.Run N Times
    Should Be Equal As Integers    ${tier}    3

Get Keyword Tier raises on unknown keyword
    [Documentation]    FR30a — unknown keyword raises ValueError with sorted-list hint.
    Run Keyword And Expect Error    ValueError: *not found in AgentEval library*
    ...    AgentEval.Get Keyword Tier    Definitely Not A Real Keyword

Stat Get Pass At K k=1 computes c/n correctly with explicit predicate
    [Documentation]    FR27 — 6/10 pass at k=1 → 0.6 (Pass@1 = c/n trivial branch).
    ${runs_data}=    Get Runs With Mixed Outcomes    n=10    pass_count=6
    @{keyword_runs}=    Run Trials From Fixture Runs    ${runs_data}
    ${pred}=    Get Complete Predicate
    ${pass_at_1}=    AgentEval.Stat.Get Pass At K    ${keyword_runs}    k=1    predicate=${pred}
    Should Be Equal As Numbers    ${pass_at_1}    0.6

Stat Get Pass At K k=3 exercises HumanEval combinatoric formula
    [Documentation]    FR27 — Pass@3 with c=6/n=10 exercises the unbiased estimator's
    ...                actual combinatoric formula `1 - C(n-c, k) / C(n, k)`.
    ...                Story 6.4 code-review HIGH-δ fix 2026-05-20 (Edge HIGH-5): pre-edit
    ...                only tested k=1 (trivial c/n branch); the formula's combinatoric
    ...                branch was untested via the dogfood surface. Math: 1 - C(4,3)/C(10,3)
    ...                = 1 - 4/120 = 116/120 ≈ 0.9667.
    ${runs_data}=    Get Runs With Mixed Outcomes    n=10    pass_count=6
    @{keyword_runs}=    Run Trials From Fixture Runs    ${runs_data}
    ${pred}=    Get Complete Predicate
    ${pass_at_3}=    AgentEval.Stat.Get Pass At K    ${keyword_runs}    k=3    predicate=${pred}
    Should Be Equal As Numbers    ${{round(${pass_at_3}, 4)}}    0.9667

Stat Get Pass At K with default predicate now matches operator PRD-verbatim form
    [Documentation]    Story 6.4 code-review DOGFOOD-FINDING-1 fix-NOW 2026-05-20: Story 6.3
    ...                `_default_pass_predicate` flipped from `r.completeness == "full"`
    ...                (fake-green; never True for AgentRunResult-derived KeywordRun) to
    ...                `r.completeness == "complete"` (operator-correct). PRD-verbatim
    ...                2-arg form `Stat.Get Pass At K ${runs} k=${k}` (no explicit
    ...                predicate) now computes the right number.
    ${runs_data}=    Get Runs With Mixed Outcomes    n=10    pass_count=6
    @{keyword_runs}=    Run Trials From Fixture Runs    ${runs_data}
    # No `predicate=` arg — relies on Story 6.3 default predicate post-fix.
    ${pass_at_1}=    AgentEval.Stat.Get Pass At K    ${keyword_runs}    k=1
    Should Be Equal As Numbers    ${pass_at_1}    0.6

Stat Get Pass At K Confidence Interval returns Wilson CI tuple
    [Documentation]    FR27 — Wilson score interval at 95% confidence for c=6/n=10.
    ...                Story 6.4 code-review HIGH-ε fix 2026-05-20 (Blind HIGH-2): pre-edit
    ...                used wide-band sanity bounds (`0 < lo < 0.5` + `0.5 < hi < 1.0`);
    ...                tightened to specific Wilson values per Story 6.1 HIGH-β fake-green
    ...                precedent. Reference: Wilson(6, 10, 0.95) ≈ (0.3128, 0.8318)
    ...                computed via `AgentEval.stats.wilson.wilson_score_interval(6, 10, 0.95)`.
    ${runs_data}=    Get Runs With Mixed Outcomes    n=10    pass_count=6
    @{keyword_runs}=    Run Trials From Fixture Runs    ${runs_data}
    ${pred}=    Get Complete Predicate
    ${interval}=    AgentEval.Stat.Get Pass At K Confidence Interval
    ...    ${keyword_runs}    k=1    predicate=${pred}    confidence=0.95
    Length Should Be    ${interval}    2
    Should Be Equal As Numbers    ${{round(${interval}[0], 3)}}    0.313
    Should Be Equal As Numbers    ${{round(${interval}[1], 3)}}    0.832

Stat Run N Times executes a callable n times independently
    [Documentation]    FR26 / AC-6.4.4 — `Stat.Run N Times` Tier-3 fan-out execution.
    ...                Story 6.4 code-review HIGH-α fix 2026-05-20 (Edge HIGH-1 + Auditor HIGH-1):
    ...                pre-edit stats parity suite never executed `Stat.Run N Times` itself
    ...                (only introspected its tier number). Builds an `AgentEval()` library
    ...                instance with `max_cost_usd=None` (no budget — fan-out unbounded for
    ...                test) + invokes the keyword with a tiny Python callable that returns
    ...                a fresh `AgentRunResult` per trial.
    ${runs}=    AgentEval.Stat.Run N Times    n=5    keyword=${{getattr(__import__('agentskills_sessions'), 'get_successful_search_run')}}
    Length Should Be    ${runs}    5
    FOR    ${run}    IN    @{runs}
        Should Be Equal As Strings    ${run.completeness}    complete
    END

Stat Assert Run Determinism passes on a deterministic Tier-1 callable
    [Documentation]    FR31a / AC-6.4.4 — `Stat.Assert Run Determinism` bit-identical guarantee
    ...                on a Tier-1 keyword. Wraps `get_successful_search_run` (which returns
    ...                an identical AgentRunResult each call given identical inputs) +
    ...                manually tags it as `@tier(1)` via Python attribute injection per
    ...                Story 6.3 callable-form path. Story 6.4 code-review HIGH-α fix
    ...                (Edge HIGH-1 + Auditor HIGH-1): pre-edit stats parity suite never
    ...                executed this keyword.
    ${kw}=    Get Tier 1 Tagged Successful Search Run
    AgentEval.Stat.Assert Run Determinism    keyword=${kw}    expect=byte_identical

Get Keyword Tier returns 1 for Get Effective Config Tier-1 baseline
    [Documentation]    FR30a / AC-6.4.4 — `Get Effective Config` Tier-1 baseline introspection.
    ...                Story 6.4 code-review HIGH-α fix 2026-05-20 (Edge HIGH-1 + Auditor HIGH-1):
    ...                pre-edit stats parity suite never exercised the top-level Tier-1 baseline.
    ${tier}=    AgentEval.Get Keyword Tier    Get Effective Config
    Should Be Equal As Integers    ${tier}    1


*** Keywords ***

Run Trials From Fixture Runs
    [Documentation]    Convert a list of AgentRunResult fixtures into KeywordRun trials
    ...                by invoking each via a sequential Stat.Run N Times-equivalent
    ...                pattern. Since Stat.Run N Times wraps a CALLABLE not a list,
    ...                we synthesize KeywordRuns directly from the fixture runs via
    ...                the StatsLibrary helper API.
    [Arguments]    ${fixture_runs}
    ${keyword_runs}=    Build Keyword Runs From Fixtures    ${fixture_runs}
    RETURN    ${keyword_runs}

Get Complete Predicate
    [Documentation]    Workaround for Story 6.4 DOGFOOD-FINDING-1: explicit predicate
    ...                checking the actual `AgentRunMetadata.completeness="complete"`
    ...                value (Story 6.3 default predicate uses `"full"` which is
    ...                NEVER produced by AgentRunResult — fake-green default).
    ${pred}=    Build Complete Predicate
    RETURN    ${pred}
