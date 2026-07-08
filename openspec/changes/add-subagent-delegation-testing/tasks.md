## 1. Empirical probe + shared types

- [ ] 1.1 Probe a captured real Claude Code CLI trace (or capture one) to
      confirm the delegation-tool name and `args` identity keys emitted for
      subagent delegation (`Task` / `subagent_type` / `prompt`), per
      `feedback_listener_hook_api_surface_empirical_check`; record findings in
      the design doc's Open Questions and adjust the Decision 1 probe order if
      the observed shape differs
- [ ] 1.2 Create `src/AgentEval/subagents/types.py` with frozen dataclasses
      `DelegationRecord` (subagent, prompt, description, sequence_index,
      latency_ms, error, raw args mapping with defensive copy),
      `DelegationDecision` (delegated, delegations, reasoning, cost_usd,
      latency_seconds), and `SubagentRoutingResult` (per_task_results +
      summary), following the `stats/types.py` / `discoverability/schema.py`
      conventions
- [ ] 1.3 Add the three error classes to `src/AgentEval/errors.py`:
      `SubagentDelegationAssertionError(AgentEvalIntegrityError)`,
      `SubagentConfigDriftError(AgentEvalIntegrityError)`,
      `InvalidSubagentRoutingTasksError` (FR59 Tier-1 setup-failure base),
      each with the FR59 diagnostic layout + `fix_suggestion`, and export them

## 2. Delegation extraction internals

- [ ] 2.1 Create `src/AgentEval/subagents/_internal.py` with
      `extract_delegations(tool_calls, delegation_tools) -> list[DelegationRecord]`
      implementing case-insensitive tool-name matching (default `{"Task"}`),
      the `subagent_type → agent_type → agent → name` identity probe, empty-string
      degradation for unrecognized shapes, and sequence_index ordering
- [ ] 2.2 Add the routing pass-predicate helper
      (`isinstance(run.result, DelegationDecision) and run.result.delegated`)
      mirroring `skills/_internal._activation_pass_predicate`
- [ ] 2.3 Create `src/AgentEval/subagents/_tasks.py` — routing-tasks YAML
      loader validating `tasks: [{id, prompt, expected_subagent}]`, raising
      `InvalidSubagentRoutingTasksError` on structural failures (mirror the
      skill-discoverability tasks loader shape)

## 3. Tier-1 keywords (trace assertions + statistics)

- [ ] 3.1 Implement `Subagent.Get Delegations` (`@tier(1)`) in
      `subagents/library.py` with `delegation_tool=` override, returning
      ordered `DelegationRecord`s; Browser-style docstring with runnable example
- [ ] 3.2 Implement `Subagent.Should Have Delegated To` (`@tier(1)`) —
      case-sensitive exact match, `SubagentDelegationAssertionError` with
      expected/observed/fix_suggestion diagnostics on failure
- [ ] 3.3 Implement `Subagent.Should Not Have Delegated` (`@tier(1)`) with the
      optional-subagent-name semantics (targeted vs any-delegation)
- [ ] 3.4 Implement `Subagent.Get Routing Pass At K` (`@tier(1)`) delegating to
      `stats._internal._compute_pass_at_k` with the hard-coded predicate and NO
      `predicate` kwarg (C59 lesson), including the ValueError paths

## 4. Tier-2/3 keywords (routing probe + cohort)

- [ ] 4.1 Implement `Subagent.Should Delegate To` (`@tier(2)`) — single adapter
      run via the same `get_adapter` discovery path `SkillsLibrary` uses,
      `adapter=`/`model=`/`**kwargs` forwarding, FR28 `polling` guard,
      `SubagentDelegationAssertionError` with prompt/reasoning diagnostics
- [ ] 4.2 Implement `Subagent.Get Delegation Decision` (`@tier(3)` +
      `@guarded_fanout()`) returning `DelegationDecision`; never raises on a
      routing miss; FR28 polling guard
- [ ] 4.3 Implement `Subagent.Get Routing Accuracy` (`@tier(3)` +
      `@guarded_fanout()`) — tasks YAML × `trials_per_task` cohort producing
      `SubagentRoutingResult` with per-task Pass@k + summary
      `routing_accuracy`; `trials_per_task` validation + FR28 guard; reuse the
      skills cohort-runner structure (and decide the Wilson-CI open question)
- [ ] 4.4 Ensure `SubagentsLibrary` inherits/wires the `_HostBudgetPlumbing`
      budget attributes needed by `@guarded_fanout` (mirror `SkillsLibrary`)

## 5. Config-validation keywords + parser extension

- [ ] 5.1 Extend `subagents/_parser.py::validate_subagent_structure` with the
      optional `skills` field type check (list of non-empty strings, mirroring
      `tools`), raising `InvalidSubagentDefinitionError` with
      `field_name="skills"`
- [ ] 5.2 Implement `Subagent.Should Declare Skills` (`@tier(1)`) — absent or
      empty `skills:` fails loud with the no-inheritance `fix_suggestion`;
      missing members named in the `SubagentConfigDriftError`
- [ ] 5.3 Implement `Subagent.Tools Should Be Subset Of` (`@tier(1)`) — absent
      or empty `tools:` fails loud as inherit-everything; offending tools named
      in the error

## 6. Tests

- [ ] 6.1 Unit tests for `extract_delegations` — tool-name case-insensitivity,
      custom delegation tool, identity-probe order, empty-string degradation,
      sequence ordering (constructed `ToolCallTrace` fixtures, no adapter)
- [ ] 6.2 Unit tests for the three Tier-1 assertion/getter keywords covering
      every spec scenario (pass, fail-with-observed-listing, no-delegation,
      targeted absence)
- [ ] 6.3 Unit tests for `Subagent.Get Routing Pass At K` — parity with
      `_compute_pass_at_k`, foreign-result-type counts as non-pass, ValueError
      paths
- [ ] 6.4 Stub adapter fixture emitting synthetic Task `ToolCallTrace`s; unit
      tests for `Should Delegate To` + `Get Delegation Decision` (pass, miss,
      polling rejection) using the monkeypatch decorator-chain-walk pattern
      where `get_adapter` patching is needed
- [ ] 6.5 Unit tests for `Get Routing Accuracy` — 2-task cohort scenario from
      the spec (routing_accuracy == 0.5), malformed-YAML
      `InvalidSubagentRoutingTasksError`, `trials_per_task=0` ValueError,
      polling rejection; routing-tasks YAML fixtures under `tests/fixtures/`
- [ ] 6.6 Unit tests for parser `skills` type check + both config-drift
      keywords covering every spec scenario (incl. the
      InvalidSubagentDefinitionError-vs-SubagentConfigDriftError split)
- [ ] 6.7 Pre-review gates: grep new files for `DF-X-SY` markers and catalog
      them (`feedback_carry_over_catalog_gate`); caller-count check on new
      internal helpers (`feedback_caller_count_check`)

## 7. Docs + verification

- [ ] 7.1 Browser-style docstrings on all new keywords (the library carries
      `_BROWSER_STYLE_MIGRATED = True`, so conventions tests enforce structure
      + example dryrun); mark Tier-2/3 keywords as adapter-dependent (mock
      provider emits no Task calls)
- [ ] 7.2 Add the new keywords to the README keyword table + regenerate libdoc;
      run the libdoc-render smoke to confirm no `Subagent.`-name auto-split
      (multi-word post-dot norm)
- [ ] 7.3 Full gate: `uv run pytest tests/`, `uv run ruff check src/ tests/`,
      `uv run mypy src/` all green
