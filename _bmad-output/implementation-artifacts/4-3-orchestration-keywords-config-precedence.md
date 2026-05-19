# Story 4.3: Orchestration Keywords + Config Precedence

Status: done

## Story

As **Raj (Agent Developer)**,
I want `Send Prompt`, `Run Scenario`, and `Get Effective Config` keywords,
So that I can run agent flows from a `.robot` test (single prompt or multi-eval YAML scenario), connect any adapter via the entry-points-resolved factory, and audit the FR41 4-level config precedence chain.

## Pre-create-story drift check (20th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

5 drifts caught + resolved pre-authoring:

- **(D-A HIGH)** epics.md L1387 stated 5-level precedence chain (`defaults < library kwargs < environment < scenario YAML < per-keyword kwargs`). PRD FR41 L1563 specifies 4 levels (`library __init__ args → environment variables → .env file at project root → defaults`). epics.md amended.
- **(D-B HIGH)** epics.md L1388 described "_provenance sub-dict" pattern; PRD FR41 specifies `dict[str, ConfigValue]` with `value` + `source` fields. Pragmatic Phase-1 resolution: ship ConfigValue via `Get Effective Config setting=key` form + new `Get Effective Config With Provenance` keyword (additive, preserves Story 1a.6 tier1 tests). Full PRD-FR41 dict-shape migration deferred → **DF-4.3-S1**.
- **(D-C MED)** `InvalidScenarioYAMLError` not in 17-leaf catalog. Added as 18th leaf, Tier-1 setup-failure semantics paralleling `InvalidMCPServerConfigError`. `error_code = "INVALID_SCENARIO_YAML"`; exit code 65.
- **(D-D MED)** `mcp_servers=` resolution mechanism (name-list → handle) not specified in epics.md. Phase-1 ratification: dict-form passes through directly; string-form (comma-separated names) raises `NotImplementedError` with DF-4.3-S2 pointer (full name-resolution Phase-1.5).
- **(D-E LOW)** `Get Effective Config setting=key` single-key form not in PRD FR41 verbatim wording. Added as implementation-friendly extension; no PRD amendment needed.

## Acceptance Criteria

### AC-4.3.1 — `Send Prompt` keyword (PRD FR14)

**Given** an adapter registered via the `agenteval.coding_agents` entry-points group (Stories 4.1 + 4.2),
**When** I call `${result}=    Send Prompt    adapter=generic    prompt=Hello    provider=mock` in a `.robot` test,
**Then** the keyword:
1. Resolves the adapter class via Story 1b.3 `get_adapter(name)`.
2. Constructs the adapter instance with ALL keyword kwargs forwarded (Phase-1: `provider`, `model`, etc. → constructor; **DF-4.3-S5** carry-over for signature-introspection-based split).
3. Calls `adapter.run(prompt, mcp_servers=...)` per Story 1b.4 ratified FR12 single-method Protocol.
4. Returns `AgentRunResult` with the Story 1b.4 ratified shape.

**Tier 2 (Stochastic Single-Shot)** per Story 1b.6 determinism contract.

### AC-4.3.2 — `Run Scenario` keyword (PRD FR15)

**And Given** a scenario YAML file matching the PRD FR15 schema,
**When** I call `${results}=    Run Scenario    adapter=generic    scenario=<path>`,
**Then** the keyword:
1. Loads + validates the YAML via `scenarios.loader.load_scenario()` (raises `InvalidScenarioYAMLError` per AC-4.3.4 on parse/schema failure).
2. Resolves the adapter (caller `adapter=` kwarg wins over scenario YAML `agent:` field).
3. Iterates `evals[]`; for each eval, calls `adapter.run(eval.prompt, ...)` `eval.repeat` times.
4. Returns `list[AgentRunResult]` of length `sum(eval.repeat for eval in evals)`.

**Tier 3 (Stochastic Fan-Out)** per Story 1b.6.

### AC-4.3.3 — `Load Scenario` keyword

**And** a separate `Load Scenario` keyword loads + validates a YAML without executing — for `.robot` tests that need to inspect the parsed `Scenario` shape before deciding to `Run Scenario`.

### AC-4.3.4 — `InvalidScenarioYAMLError` (18th leaf)

**And** the scenario YAML loader raises `InvalidScenarioYAMLError` on:
- File missing OR wrong extension (`.yaml` / `.yml` only).
- Malformed YAML (yaml.YAMLError wrapped).
- Top-level not a mapping.
- Required `evals: list[Scenario]` missing OR empty.
- Per-eval required `prompt: str` missing OR wrong-type.
- Per-eval `repeat: int` < 1 OR wrong-type (including `bool` rejected).
- Per-eval `expect` / `judge` not a mapping when present.
- Top-level `mcp_servers` not a list of strings.
- Top-level `model` / `provider` / `agent` not string when present.

`field_name` carries RFC 6901 JSON Pointer into the offending location.

### AC-4.3.5 — `mcp_servers=` argument resolution (PRD FR16)

**And Given** the `mcp_servers=` keyword arg on `Send Prompt` + `Run Scenario`,
**When** I pass `mcp_servers={"name": handle}` (dict-form),
**Then** the dict is forwarded directly to `adapter.run(mcp_servers=...)`.
**When** I pass `mcp_servers="name1,name2"` (string-form),
**Then** the keyword raises `NotImplementedError` with **DF-4.3-S2** pointer (Phase-1 carve-out; full name-resolution to live ServerHandle requires Library-managed registry which Story 4.3 doesn't ship).
**When** I pass `mcp_servers=None` OR empty dict OR empty string,
**Then** no error; `adapter.run(mcp_servers=None)` is forwarded.

### AC-4.3.6 — `Get Effective Config` extended forms (PRD FR41)

**And Given** the FR41 4-level precedence chain (init_arg → env → dotenv → default),
**When** I call `${config}=    Get Effective Config` (no arg),
**Then** the keyword returns `dict[str, Any]` (Story 1a.6 ratified shape, backwards-compatible).
**When** I call `${cv}=    Get Effective Config    setting=max_cost_usd`,
**Then** the keyword returns `ConfigValue(value, source)` where `source: Literal["init_arg", "env", "dotenv", "default"]` per PRD FR41 L1563.
**When** I call `${all}=    Get Effective Config With Provenance`,
**Then** the keyword returns `dict[str, ConfigValue]` (PRD-FR41-compliant full surface).

### AC-4.3.7 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (54 src files).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance -q` — 798 passed + 8 skipped (was 735 Story 4.2 close; **+63** new).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed (regression-clean).
- `uv run robot tests/acceptance/smoke + tests/unit/mcp/test_robot_integration.robot` — 9 passed.

### AC-4.3.8 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (22nd consecutive use).
- `feedback_test_name_assertion_match` applied to all 63 new tests.
- Codex CLI sandbox bypass per goal directive.
- Auditor citation-drift check on all FR14/FR15/FR16/FR17/FR41 wording.

## Tasks / Subtasks

- [x] **Task 1: `InvalidScenarioYAMLError` 18th leaf** added to `src/AgentEval/errors.py` + catalog amended.
- [x] **Task 2: `src/AgentEval/scenarios/schema.py`** — `Scenario` + `ScenarioEval` frozen dataclasses.
- [x] **Task 3: `src/AgentEval/scenarios/loader.py`** — `load_scenario()` with full schema validation + RFC 6901 JSON Pointer field_name.
- [x] **Task 4: `src/AgentEval/orchestration/library.py`** — `OrchestrationLibrary` with `Send Prompt` (Tier 2) + `Run Scenario` (Tier 3) + `Load Scenario` (Tier 1) keywords.
- [x] **Task 5: `_kernel/context.py`** — `ConfigValue` dataclass + `resolve_config_with_provenance()` function.
- [x] **Task 6: `src/AgentEval/__init__.py`** — extend `Get Effective Config` with `setting=` form + new `Get Effective Config With Provenance` keyword + register `OrchestrationLibrary` in `_SUB_LIBRARIES`.
- [x] **Task 7: Unit tests** — 25 scenario loader tests + 25 orchestration library tests + 13 config-provenance tests = 63 new.
- [x] **Task 8: All-gates pass.**
- [x] **Task 9: 4-reviewer cross-LLM code review** — 22nd consecutive cross-LLM STAR catch streak. Codex CLI `--dangerously-bypass-approvals-and-sandbox` operational. 4 reviewers returned: Blind 4 HIGH + 4 MED + 2 LOW; Edge-cases 3 HIGH + 4 MED + 7 LOW; Auditor 3 LOW (citation only); Codex 4 HIGH + 1 MED + 1 LOW. All HIGH + 2-way MEDs applied via patches below.

## Senior Developer Review (AI)

22nd consecutive cross-LLM STAR catch streak. Codex CLI sandbox bypass remains operational. Cross-reviewer overlap was unusually strong — 3-way HIGH on adapter-precedence sentinel inversion + 2-way HIGH on 3 more independent production bugs. Auditor returned 0 HIGH/MED (only 3 LOW citation hygiene) — Story 4.3 spec was PRD-compliant at the citation level; the real bugs lived in the implementation surface.

**Patches applied (priority order):**

- **3-way HIGH-A (Blind H2 + Edge-cases H1 + Codex HIGH-3)** — `Run Scenario` adapter precedence INVERTED from docstring. Pre-edit `adapter if adapter != "generic" or scenario_obj.agent is None else ...` couldn't distinguish "caller passed adapter=generic explicitly" from "default fired" — YAML always won when caller passed the default value. Replaced with `_UNSET` sentinel pattern (matching Story 1b.1 H3 ratification): `adapter: str | _Unset = _UNSET`; `if adapter is _UNSET: resolved = scenario_obj.agent or "generic"`. New tests pin the precedence in both directions.
- **2-way HIGH-B (Blind H1 + Codex HIGH-4)** — `Run Scenario` silently dropped `scenario_obj.mcp_servers` field. Loader parsed + validated; executor never read it. Fix: when caller's `mcp_servers=` is None AND scenario YAML has non-empty `mcp_servers:`, flow YAML through the same name-list resolution path (which today raises NotImplementedError per DF-4.3-S2). Loud-fail is correct; silent-drop was the bug.
- **2-way HIGH-C (Blind H3 + Codex HIGH-1 with empirical ValueError repro)** — Library-level `AgentEval(provider="mock")` bypassed by orchestration keywords. Codex behavioral probe: `AgentEval(provider="mock").send_prompt(prompt="hi")` raised ValueError because LiteLLM was hit not Mock. Fix: `OrchestrationLibrary.__init__(default_provider=None)` accepts the parent library's resolved config; `AgentEval._build_components()` forwards `self._provider`. Send Prompt + Run Scenario consult `self._default_provider` when caller doesn't pass `provider=`.
- **2-way HIGH-D (Codex HIGH-2 + DF-4.3-S5 elevation)** — per-call kwargs forwarded to adapter CONSTRUCTOR not `run()`. Pre-edit ALL `**kwargs` to ctor → strict adapters crashed (TypeError) + per-call `temperature=0.5` silently dropped. Fix: `_split_adapter_kwargs(adapter_cls, kwargs)` introspects via `inspect.signature(adapter_cls)`; adapters with `**kwargs` get everything (Story 1b.4 `InProcessAdapter._adapter_config` pattern preserved); strict-signature adapters get only their named params. Run-kwargs forwarded to `adapter.run(**run_kwargs)`. DF-4.3-S5 elevated from Phase-1.5 to in-story because Codex's probe with `StrictAdapter` proved the public surface was broken.
- **1-way HIGH-F (Edge-cases H3)** — `UnicodeDecodeError` uncaught in scenario loader (it's `ValueError` subclass, not `OSError`). Now wrapped as `InvalidScenarioYAMLError` with explicit fix_suggestion.
- **1-way HIGH-G (Blind H4)** — Fake-green precedence tests. Pre-edit `test_run_scenario_forwards_model_from_yaml` + `test_run_scenario_kwarg_overrides_scenario_model` only asserted `len(results) == 1`; Mock ignores model so precedence was unverified. Rewritten via `GenericAdapter.__init__` monkeypatch capturing actual model kwarg flow. Validates `feedback_test_name_assertion_match` 5th catch.
- **3-way MED-A (Blind M2 + Edge-cases M1 + Codex MED-1)** — Loader's `entry.get(k) or default` silently coerced `expect: []`, `expect: 0`, `expect: false`, `mcp_servers: {}` to the empty default. Fix: distinguish "absent / None" from "wrong type"; absent uses default, wrong-type raises typed error.
- **2-way MED-B (Blind M4 + Edge-cases M2)** — `ConfigValue.source` Literal type-check-only. `__post_init__` now validates against the 4-value PRD FR41 enum at runtime per M_R11 fail-loud.
- **2-way MED-C (Edge-cases M4 + Codex LOW-1)** — `field_name="/"` violates RFC 6901 §5 (root pointer is `""`). All 6 root-level error sites amended.
- **Blind MED-1** — KeyError → ValueError on `Get Effective Config setting=key` unknown name (typed-input-validation idiom matches `_resolve_scope` L162).
- **Edge-cases L2 + Codex MED-1 sub-finding** — Loader now rejects empty/whitespace-only prompts at parse time (`fail-loud` per M_R11).

**Carried to Phase-1.5 (DF-4.3-S6..S8):**

- **DF-4.3-S6 (Edge-cases H2)**: `@guarded_fanout` decorator on `Run Scenario`. ADR-015 mandates this for Tier-3; Story 4.3 ships without because the `@guarded_fanout` decorator wiring requires non-trivial estimator function + library-level kwarg threading. Phase-1.5 hygiene story. Until then, `Run Scenario` is Tier-3-annotated but cost/runtime-unsupervised — operators must enforce budgets manually.
- **DF-4.3-S7 (Edge-cases M3)**: `resolve_config` + `resolve_config_with_provenance` share precedence logic but coded twice. Phase-1.5 hygiene: refactor `resolve_config` to call `resolve_config_with_provenance` + project `.value`.
- **DF-4.3-S8 (Blind M3)**: dead `if k != "prompt"` filter in pre-edit Send Prompt removed via HIGH-D's `_split_adapter_kwargs` refactor. NOT a Phase-1.5 carry-over — already closed.

**Accepted as-is:**

- Edge-cases L1 (float repeat coercion): defensible Phase-1 strictness; document if user-friction surfaces.
- Edge-cases L3-L7: probe-confirmed clean (no bugs).
- Blind M4 (ConfigValue.value deep-copy for mutable inner values): theoretical concern; all 9 FR42 defaults are immutable scalars today. Document; revisit when a mutable-value setting lands.

**Production-validation thesis preserved**: H-B + H-D mirror Story 4.2's prompt-not-fed pattern + Story 3.3's RF↔SDK errlog pattern — fixture-only tests miss real-call-path bugs; the 4-reviewer cross-LLM pattern (with behavioral probes) catches them.

**All-gates post-patch:** ruff/format/mypy clean (54 src files); **815 unit+conformance + 8 skipped** (was 798 Story 4.3 dev close; **+17 new behavioral defenses**); 6 tier1; 9 RF integration; license headers PASS.

### Action Items

All HIGH + 2-way MED findings closed via in-line patches. 3 new Phase-1.5 carry-overs catalogued (DF-4.3-S6..S8). Codex CLI sandbox bypass remains operational per Story 4.1 + 4.2 + 4.3 precedent.

## Dev Notes

### Architecture compliance

- PRD FR14, FR15, FR16, FR17, FR41 (all verbatim re-derived pre-authoring per `feedback_citation_drift_first_class` extension).
- Story 1b.4 SubprocessAdapter/InProcessAdapter ABCs (adapter resolution).
- Story 1b.3 `_kernel/discovery.py:get_adapter()` (entry-points-backed adapter resolution).
- Story 2.2 collision-prevention norm (HooksLibrary INCLUDED; MCPLibrary EXCLUDED from `_SUB_LIBRARIES`; OrchestrationLibrary INCLUDED per no-collision check).
- Story 1b.6 tier annotations (Tier 1/2/3 + badges).

### Phase-1 limitations explicitly documented

- `mcp_servers=` name-list-string resolution → DF-4.3-S2.
- `Get Effective Config` no-arg dict[str, Any] shape → DF-4.3-S1 (full PRD FR41 migration deferred).
- Adapter constructor-kwargs vs run-kwargs split → DF-4.3-S5.
- Full multi-turn scenario conversation threading → DF-4.3-S4 (currently each eval is a separate adapter.run() call).

## Dev Agent Record

### Completion notes

Story 4.3 dev complete 2026-05-20. All ACs satisfied; full all-gates green.

Highlights:
- 18th leaf `InvalidScenarioYAMLError` ratified pre-authoring (catalog amendment).
- 63 new unit tests across 3 modules (scenarios + orchestration + config-provenance).
- New `ConfigValue` surface per PRD FR41 via additive `setting=` form + `Get Effective Config With Provenance` keyword (preserves Story 1a.6 backwards-compat).
- 5 drifts caught pre-authoring (D-A through D-E); 4 fixed in epics.md, 1 (DF-4.3-S1) tracked as Phase-1.5 carry-over.

## File List

**Source (5 new + 2 edited):**
- `src/AgentEval/scenarios/__init__.py` — sub-package init.
- `src/AgentEval/scenarios/schema.py` — Scenario + ScenarioEval dataclasses (~75 LoC).
- `src/AgentEval/scenarios/loader.py` — `load_scenario()` with schema validation (~190 LoC).
- `src/AgentEval/orchestration/__init__.py` — sub-package init.
- `src/AgentEval/orchestration/library.py` — OrchestrationLibrary with 3 keywords (~225 LoC).
- `src/AgentEval/errors.py` — added InvalidScenarioYAMLError 18th leaf.
- `src/AgentEval/_kernel/context.py` — added ConfigValue dataclass + resolve_config_with_provenance() function.
- `src/AgentEval/__init__.py` — extended Get Effective Config + new Get Effective Config With Provenance keyword + registered OrchestrationLibrary.

**Tests (3 new):**
- `tests/unit/scenarios/test_loader.py` — 25 tests (schema validation + JSON Pointer field_name).
- `tests/unit/orchestration/test_library.py` — 25 tests (Send Prompt + Run Scenario + Load Scenario).
- `tests/unit/orchestration/test_config_provenance.py` — 13 tests (ConfigValue surface).

**Docs (2 edited):**
- `docs/contracts/error-class-hierarchy.md` — 17 → 18 leaves; new InvalidScenarioYAMLError row.
- `_bmad-output/planning-artifacts/epics.md` — 4 drift fixes (D-A through D-D).

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (20th use) caught 5 drifts. | Bob |
| 2026-05-20 | 0.2.0   | Dev complete. 18th leaf + 5-new-modules + 63 new tests. All-gates green. Pending 4-reviewer code review. | Dev |
