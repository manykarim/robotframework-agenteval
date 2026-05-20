# Story 6.2: Trajectory + Tool Call + Response Assertions

Status: review

## Story

As **Raj (Agent Developer)**,
I want **5 assertion keywords** — `Trajectory Should Match` (4 modes: exact / subsequence / set / regex per PRD FR23a + FR23b), `Tool Call Should Have Occurred` (PRD FR24 dict-subset arg matching), and 3 response variants `Agent Response Should Contain` / `Should Match Regex` / `Should Match Schema` (PRD FR25) — each with `@tier(1)` badges, `IncompleteTraceError` gating on tool-call-bearing assertions, and RF builtins as the Phase-1 assertion backend (AssertionEngine integration deferred to Story 6.3),
So that I can assert on agent behavior at the trajectory, tool-call, and response levels — covering the three falsifiable evidence layers per BFCL methodology + closing PRD FR23a/FR23b/FR24/FR25.

## Pre-create-story drift check (28th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

**4 drifts caught + resolved pre-authoring** (per fix-the-losing-source-NOW pattern):

- **(D-1 HIGH)** **Epic AC promised "AssertionEngine integration for `==`/`!=`/`contains`/`matches` operator surface" but `robotframework-assertion-engine` is NOT pinned in `pyproject.toml` + `src/AgentEval/_assertions/adapter.py` doesn't exist yet.** Verified: `grep "robotframework-assertion-engine" pyproject.toml` → 0 hits; `ls src/AgentEval/_assertions/` → only `__init__.py` placeholder (Story 1a.1). Architecture L138 cites the planned `robotframework-assertion-engine>=4.0,<5.0` pin (from agentguard ADR-022) but Phase-1 hasn't added it. Story 6.3's spec (epic L1649) explicitly mentions `_assertions/adapter.py` scaffolding as Story 6.3 work. Per dev-story HALT condition "new dependencies need user approval", Story 6.2 ships the keyword surface using RF builtins (`Should Be Equal`, `Should Contain`, `Should Match Regexp` + stdlib `jsonschema.validate`) + Story 6.3 ratifies the dep + wires AssertionEngine. **Resolution**: epic AC amended pre-authoring; Story 6.2 spec documents Phase-1 RF-builtins backend + Story 6.3 forward-ref. No new deps in Story 6.2.

- **(D-2 MED)** **PRD FR24 says `args=<dict>` but epic AC L1618 example uses `arguments={...}`.** RF kwarg flexibility — both names work syntactically. Story 3.2 already established the `arguments=` kwarg name on `MCP.Call Tool` (mirroring MCP spec). PRD FR24's `args=` is the abbreviated form. **Resolution**: Story 6.2 ships `args=<dict>` per PRD FR24 verbatim. The pattern "agent's tool-call args" maps directly to `ToolCallTrace.args` (Story 1b.2 dataclass) — naming alignment with the field.

- **(D-3 MED)** **PRD FR23b says regex mode matches "tool-call name + serialized args" but epic AC L1615 says "matches each expected entry as a regex" (silent on args).** Verbatim PRD: "match each step against a regex pattern over the tool-call name + serialized args." So `mode=regex` regex string is matched against the concatenation `"<tool_name>:<json.dumps(args, sort_keys=True)>"` per step. **Resolution**: spec documents the FR23b verbatim concatenation contract.

- **(D-4 MED)** **PRD FR25 says `Agent Response Should Match Schema <run> <jsonschema>` accepting a JSON Schema dict; epic AC L1622 says `schema=path.json` accepting a file path.** Both should be supported (operator convenience). **Resolution**: keyword accepts EITHER `schema=<dict>` (inline JSON Schema) OR `schema=<path-or-string>` auto-detecting file paths via `Path(schema).is_file()`. Documented in AC-6.2.5.

## Acceptance Criteria

### AC-6.2.1 — `AssertionsLibrary` ships 5 `@keyword`-decorated assertion methods

**Given** the existing `_SUB_LIBRARIES` registration pattern + the Story 6.1 `MetricsLibrary` precedent,
**When** Story 6.2 ships `src/AgentEval/_assertions/library.py`,
**Then** a new class `AssertionsLibrary` exposes exactly these 5 keywords (matching PRD FR23a/FR23b/FR24/FR25 verbatim):

| # | Keyword | Args | Backend (Phase-1 stdlib per D-1) | Gates? |
| --- | --- | --- | --- | --- |
| 1 | `Trajectory Should Match` | `result`, `expected: list[str]`, `mode="exact"\|"subsequence"\|"set"\|"regex"` | `==` (exact) / list-traversal (subsequence) / `set()` cmp / `re.fullmatch` (regex) | yes (tool-call-bearing) |
| 2 | `Tool Call Should Have Occurred` | `result`, `tool: str`, `args: dict \| None = None`, `match_mode="subset"\|"exact" = "subset"` | iterate `result.tool_calls`, match by name + dict-subset OR exact equality | yes |
| 3 | `Agent Response Should Contain` | `result`, `substring: str` | `in` operator on `response_text` (Python stdlib) | no (response-text-only) |
| 4 | `Agent Response Should Match Regex` | `result`, `pattern: str` | `re.search` (Python stdlib) | no |
| 5 | `Agent Response Should Match Schema` | `result`, `schema: dict \| str \| Path` | `jsonschema.validate` (already a project dep per Story 5.3) | no |

**Phase-1 backend ratification per code-review HIGH-ζ fix (Auditor 1-way spec-drift):** Phase-1 backend is **Python stdlib**, NOT RF builtins. AssertionEngine wrapping (which routes through RF `Should Be Equal` / `Should Contain` / `Should Match Regexp`) is deferred to Story 6.3 per D-1. The previous "RF builtins backend" framing was an aspirational label — actual library code raises `AssertionError` from pure-Python primitives. Documented here to prevent operator-confusion about exception sources.

Each keyword:
- `@keyword(name="...")` with verbatim PRD name (spaces matter).
- `@tier(1)` annotation + `[Tier 1 — Deterministic]` docstring badge per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- Tool-call-bearing keywords (1-2): gate on `mcp_coverage` via `_check_mcp_coverage(result, allow_external_mcp_blind=self._allow_external_mcp_blind, metric_keyword="<verbatim keyword name>")` per FR37. Response keywords (3-5): NO gate — response text is provider-reported scalar.

### AC-6.2.2 — `Trajectory Should Match` mode semantics per PRD FR23a + FR23b

**Given** an `AgentRunResult` with tool calls `[search, search, fetch]`,
**When** Story 6.2 implements the 4 modes:

- **`mode="exact"`** (DEFAULT per FR23a): `result.tool_calls[*].name == expected` (ordered list equality). Pass on `[search, search, fetch]`; fail on `[search, fetch]` or `[fetch, search, search]`.
- **`mode="subsequence"`**: `expected` appears as a subsequence of `result.tool_calls[*].name` (order preserved, extras allowed). Pass on `[a, search, b, search, c, fetch]`; fail on `[search, fetch, search]` (wrong order).
- **`mode="set"`**: `set(result.tool_calls[*].name) == set(expected)`. Pass on any permutation; fail if any expected tool missing or unexpected tool present.
- **`mode="regex"`** per FR23b: each `expected[i]` is a regex; matched via `re.fullmatch(expected[i], f"{tc.name}:{json.dumps(tc.args, sort_keys=True)}")` per the verbatim FR23b "concatenation of tool-call name + serialized args" contract. List-length equality required.

Invalid `mode` raises `ValueError("mode must be one of: exact, subsequence, set, regex")`.

### AC-6.2.3 — `Tool Call Should Have Occurred` dict-subset arg-matching per PRD FR24

**Given** an `AgentRunResult` with `tool_calls=[ToolCallTrace(name="search", args={"query": "foo", "limit": 10})]`,
**When** the assertion runs with various arg specs:

- `tool="search"` (no args) → passes (name match sufficient).
- `tool="search", args={"query": "foo"}` → passes (dict-subset; `{"query": "foo"}` ⊆ `{"query": "foo", "limit": 10}`).
- `tool="search", args={"query": "foo", "limit": 10}` → passes (exact subset).
- `tool="search", args={"query": "bar"}` → fails (value mismatch).
- `tool="search", args={"query": "foo"}, match_mode="exact"` → fails (actual has extra `limit` key).
- `tool="missing"` → fails.

`match_mode` default is `"subset"` per FR24 verbatim ("dict-subset semantics (extra args allowed)"). `match_mode="exact"` requires `tc.args == args` exact equality.

Raises `AssertionError` (not `IncompleteTraceError` for the no-match case — that's the RF assertion-failure path) when no tool call matches.

### AC-6.2.4 — `Agent Response Should Contain` + `Should Match Regex` per PRD FR25

**Given** an `AgentRunResult` with `response_text="The capital is Paris."`,
**When** the response assertions run:

- `Agent Response Should Contain    ${result}    "Paris"` → passes.
- `Agent Response Should Contain    ${result}    "Berlin"` → fails (raises `AssertionError` from Python `in` operator check — Phase-1 stdlib backend per HIGH-ζ; AssertionEngine wrapping deferred to Story 6.3).
- `Agent Response Should Match Regex    ${result}    r"capital is (\\w+)"` → passes (uses `re.search` not `re.fullmatch` per the "match" terminology in FR25).
- `Agent Response Should Match Regex    ${result}    r"^Berlin"` → fails.

No `mcp_coverage` gate per AC-6.2.1 (response is provider-reported scalar).

### AC-6.2.5 — `Agent Response Should Match Schema` per PRD FR25 (D-4 fix: accepts dict OR path)

**Given** an `AgentRunResult.response_text` containing JSON,
**When** the assertion runs:

- `schema={"type": "object", "properties": {...}}` → uses dict directly with `jsonschema.validate(json.loads(response_text), schema)`.
- `schema="path/to/schema.json"` (str) → auto-detect via `Path(schema).is_file()`; if file, `json.loads(Path(schema).read_text())` then validate; if not, raise `ValueError("schema must be a dict OR a path to a JSON Schema file; got: <repr>")`.
- `schema=Path("path/to/schema.json")` → same path handling.

Validation failure raises `jsonschema.ValidationError` (preserves stack-trace + path info per the jsonschema convention). Response-text not parseable as JSON raises `AssertionError("response_text is not valid JSON: <prefix>")`.

### AC-6.2.6 — `IncompleteTraceError` gate for tool-call-bearing assertions per FR37

**Given** the Story 5.2 `_check_mcp_coverage` gate + AC-6.2.1 gate scope,
**When** `Trajectory Should Match` or `Tool Call Should Have Occurred` is called on an `AgentRunResult` with `metadata.mcp_coverage == "external_mixed"`:

- Default: raises `IncompleteTraceError` per FR37 (verbatim message including `metric_keyword="<keyword name>"`).
- `allow_external_mcp_blind=True` Library kwarg: gate opens, assertion proceeds normally.

Response assertions (3-5) do NOT gate — verified by integration test.

### AC-6.2.7 — `AssertionsLibrary` receives `allow_external_mcp_blind` from Library-level config

Mirrors Story 6.1 `MetricsLibrary` pattern verbatim. `_build_components` propagation:

```python
elif cls_name == "AssertionsLibrary":
    components.append(cls(allow_external_mcp_blind=self._allow_external_mcp_blind))
```

`AssertionsLibrary.__init__(self, allow_external_mcp_blind: bool = False)` stores; tool-call-bearing keywords forward to `_check_mcp_coverage`.

### AC-6.2.8 — `_SUB_LIBRARIES` registration (5th entry)

```python
_SUB_LIBRARIES: tuple[tuple[str, str], ...] = (
    ("AgentEval.hooks.library", "HooksLibrary"),
    ("AgentEval.orchestration.library", "OrchestrationLibrary"),
    ("AgentEval.telemetry.library", "TelemetryLibrary"),
    ("AgentEval.metrics.library", "MetricsLibrary"),
    ("AgentEval._assertions.library", "AssertionsLibrary"),  # NEW per Story 6.2
)
```

Story 2.2 collision-detector verifies no keyword-name collisions across all 5 sub-libraries.

### AC-6.2.9 — Internal helpers at `src/AgentEval/_assertions/_internal.py`

Per architecture L1291's `_internal.py` projection-accessor pattern (mirrored from Story 6.1):

- `_match_trajectory_exact(observed: list[str], expected: list[str]) -> bool`
- `_match_trajectory_subsequence(observed: list[str], expected: list[str]) -> bool`
- `_match_trajectory_set(observed: list[str], expected: list[str]) -> bool`
- `_match_trajectory_regex(observed_tool_calls: list[ToolCallTrace], expected: list[str]) -> bool`
- `_match_tool_call(tc: ToolCallTrace, tool: str, args: dict | None, match_mode: str) -> bool`
- `_dict_is_subset(subset: dict, superset: dict) -> bool` (recursive dict-subset matcher)
- `_resolve_schema(schema: dict | str | Path) -> dict` (D-4 dispatch helper)

Pure functions enable Story 6.3 (`Stat.*`) + future Story 6.4 dogfood to re-use without going through the keyword surface. Per Story 2.1 sub-library `__init__.py` discipline: NO re-exports from `_assertions/__init__.py`.

### AC-6.2.10 — Unit tests at `tests/unit/_assertions/test_assertions_library.py`

**Given** the Story 6.1 fixture-builder pattern,
**When** Story 6.2 ships unit tests,
**Then** coverage includes:

- **`Trajectory Should Match` (4 modes × happy + fail = 8 tests minimum)**: exact match, exact fail (wrong order), subsequence match, subsequence fail, set match, set fail, regex match (verifies the FR23b "name:args" concatenation), regex fail.
- **`Tool Call Should Have Occurred` (6 tests)**: name-only match, subset match (default), exact match, subset-fail-on-value-mismatch, exact-fail-on-extra-key, missing-tool fail.
- **`Agent Response Should Contain` (2 tests)**: pass + fail.
- **`Agent Response Should Match Regex` (3 tests)**: pass, fail, multi-line text edge.
- **`Agent Response Should Match Schema` (5 tests)**: dict-schema pass, dict-schema fail, file-path schema pass, invalid path raises ValueError, non-JSON response raises AssertionError.
- **`IncompleteTraceError` gate (4 tests)**: 2 tool-call-bearing keywords raise by default; 2 opt-out via `allow_external_mcp_blind=True`.
- **No-gate-for-response (3 tests)**: 3 response keywords do NOT raise even on `external_mixed`.
- **Invalid mode (1 test)**: `Trajectory Should Match mode=bogus` raises ValueError.

Total: **44 unit tests** (was estimated ~32; final count amended per `feedback_in_flight_spec_amendment` ratified Epic 5 retro). Breakdown: 9 trajectory + 8 tool-call + 2 contain + 3 regex + 5 schema + 4 gate + 3 no-gate + 2 boundary = 36 dev tests, **PLUS 8 code-review HIGH/MED regression tests** (HIGH-α match_mode-on-args-None + HIGH-α no-name-match; HIGH-β non-str/Path schema input + HIGH-β file-with-non-dict; HIGH-γ non-JSON arg `default=str`; HIGH-δ tool-call AssertionError redaction + HIGH-δ response AssertionError redaction; MED ordering mode-before-gate). Fixture builders mirror Story 6.1's `_trace` / `_result` helpers.

### AC-6.2.11 — Phase-1 carve-outs documented

- **AssertionEngine integration deferred to Story 6.3** per D-1 drift fix. Story 6.2 module docstring + AC-6.2.1 backend column document this. No `robotframework-assertion-engine` dep added in Story 6.2.
- **`_check_mcp_coverage` `metric_keyword=` kwarg name preserved** (Story 1b.2 ratified). Story 6.2 passes assertion-keyword names through that kwarg; no rename.
- **`Agent Response Should Match Schema` JSON Schema validation uses already-pinned `jsonschema`** (Story 5.3 deliverable). No new deps.

### AC-6.2.12 — `feedback_caller_count_check` + `feedback_carry_over_catalog_gate` UPSTREAM applied

Per Epic 5 retro NEW norms:
- Each new `_internal.py` helper has caller count > 0 (verified via grep at story-close BEFORE code-review invocation).
- Any `DF-X-SY` patterns created (e.g., AssertionEngine deferral surface) catalogued in BOTH `deferred-work.md` + `phase-1-5-carry-overs.md` BEFORE `/bmad-code-review`. 8th consecutive story applying the gate UPSTREAM.

**Post-code-review additions (HIGH-ε + HIGH-η per Edge HIGH-5 + Auditor #2 1-way PRD findings):**
- **DF-6.2-S1** — AssertionsLibrary keywords do NOT emit `EvidenceBlock` despite PRD FR34a verbatim "Every assertion keyword writes a self-contained evidence block to the Robot Framework log on both pass and fail". Same gap as Story 6.1 `MetricsLibrary`. Catalogued for Phase-1.5 sweep wiring `EvidenceBlockEmitter.emit()` into all `@tier(1)` keyword bodies.
- **DF-6.2-S2** — PRD L1104-1107 paired-getter table mandates `Trajectory Should Match`↔`Get Trajectory`, `Tool Call Should Have Occurred`↔`Get Tool Calls`, `Agent Response Should Contain`↔`Get Agent Response`, `Agent Response Should Match Schema`↔`Get Agent Response`. Story 6.2 ships the `Should *` half; paired `Get *` getters (3-4 missing) deferred per AC-SIMPLICITY-02b. `Get Tool Call Names` exists from Story 6.1 (partial coverage). Catalogued for Phase-1.5 paired-getter wave.

### AC-6.2.13 — All-gates pass

ruff/format/mypy/license-headers clean (target: ~73 src files); full `uv run pytest tests/unit tests/conformance tests/integration -q` passes with **1115 tests / 8 skipped** (was 1071 at Story 6.1 close; +44 net = 36 dev + 8 code-review regression tests per AC-6.2.10); no CWD pollution. Ratification per `feedback_in_flight_spec_amendment` Epic 5 retro: AC body amended to final post-code-review test count.

## Tasks / Subtasks

- [x] **Task 1: `src/AgentEval/_assertions/_internal.py`** — 7 pure helpers shipped (`_match_trajectory_{exact,subsequence,set,regex}` + `_dict_is_subset` + `_match_tool_call` + `_resolve_schema`). Per FR23b: regex matches `name:json.dumps(args, sort_keys=True)` concatenation. License header. Per `feedback_caller_count_check`: all 7 helpers have caller-count ≥ 2 (definition + library wrapper).
- [x] **Task 2: `src/AgentEval/_assertions/library.py`** — `AssertionsLibrary` class with 5 `@keyword + @tier(1) + [Tier 1 — Deterministic]` methods per AC-6.2.1 through AC-6.2.5. Tool-call-bearing keywords (Trajectory + Tool Call) gate via `_check_mcp_coverage(metric_keyword="<verbatim name>")`; response keywords (3) don't gate.
- [x] **Task 3: `AssertionsLibrary.__init__(self, allow_external_mcp_blind: bool = False)`** — stores Library-level config.
- [x] **Task 4: `_SUB_LIBRARIES` 5th entry + `_build_components` `elif cls_name == "AssertionsLibrary"` propagation** — added to `src/AgentEval/__init__.py`.
- [x] **Task 5: `tests/unit/_assertions/__init__.py` + `tests/unit/_assertions/test_assertions_library.py`** — 36 dev tests + 8 code-review regression tests = **44 total** (was estimated 32; AC-6.2.10 amended per `feedback_in_flight_spec_amendment`). Breakdown: 9 trajectory + 8 tool-call + 2 contain + 3 regex + 5 schema + 4 gate + 3 no-gate + 2 boundary + 8 HIGH/MED regression. All `IncompleteTraceError` gate tests use `match=r"<keyword name>"` verifying FR37 message threads metric_keyword verbatim per AC-6.2.6 (lesson from Story 6.1 code-review Edge-cases HIGH-4).
- [x] **Task 6: All-gates pass** — ruff/format/mypy clean (73 src files); license-headers PASS; **1115 unit+conformance+integration / 8 skipped** (was 1071 at Story 6.1 close; +44 net per AC-6.2.10); no CWD pollution.
- [x] **Task 7: `feedback_carry_over_catalog_gate` UPSTREAM** — 8th consecutive story applying gate. Pre-code-review: no new DF-X-SY entries from Story 6.2. **POST-code-review: 2 new DF entries catalogued (DF-6.2-S1 FR34a EvidenceBlock gap + DF-6.2-S2 paired-getter gap per Auditor #2 + Edge HIGH-5) in BOTH `deferred-work.md` AND `phase-1-5-carry-overs.md`.**
- [x] **Task 8: `feedback_caller_count_check`** — verified via `grep -rln` for each of 7 `_internal.py` helpers: all have caller-count ≥ 2 (definition + library wrapper).
- [x] **Task 9: 4-reviewer cross-LLM code review** — completed. 4 reviewers (Blind / Edge-cases / Acceptance Auditor / Codex CLI 0.117.0 with 8 behavioral probes). Triage per `feedback_n_way_agreement_weight` extended. **8 HIGH findings applied** (HIGH-α match_mode validation up-front + HIGH-β schema dispatch tightening + HIGH-γ json.dumps `default=str` + HIGH-δ AssertionError redaction + HIGH-ε DF-6.2-S1 EvidenceBlock catalog + HIGH-ζ stdlib backend spec amendment + HIGH-η DF-6.2-S2 paired-getter catalog + HIGH-θ architecture L838 carve-out registry amendment). **3 MED findings applied** (mode-validation-before-gate ordering + AC body amendment 32→44 / 1103→1115 + set-mode docstring). 8 regression tests added covering each HIGH/MED fix.

## Dev Notes

### Architecture compliance

- **PRD FR23a**: 3 default modes (`exact`, `subsequence`, `set`) — implemented verbatim.
- **PRD FR23b**: `mode=regex` matches the name+args concatenation per the D-3 drift fix.
- **PRD FR24**: dict-subset default + `match_mode=exact` opt-in.
- **PRD FR25**: 3 response assertions (Contain / Match Regex / Match Schema).
- **PRD FR37 + ADR-016 D1**: `IncompleteTraceError` gate via `_check_mcp_coverage` for tool-call-bearing assertions (Trajectory + Tool Call); response assertions don't gate (observer-independent scalar).
- **PRD FR42**: `allow_external_mcp_blind` default `False`.
- **Architecture L138**: AssertionEngine integration planned via `robotframework-assertion-engine>=4.0,<5.0` (deferred per D-1 to Story 6.3).
- **Story 2.1 `__init__.py` discipline**: `_assertions/__init__.py` UNTOUCHED beyond Story 1a.1 docstring.
- **Story 2.2 collision norm**: 5 new keywords verified non-colliding via grep.
- **Story 6.1 `MetricsLibrary` precedent**: same `@keyword + @tier(1) + [Tier 1 — Deterministic]` pattern; same `_check_mcp_coverage(metric_keyword=...)` propagation; same `_SUB_LIBRARIES` registration; same `_internal.py` projection-helper structure.

### Existing infrastructure Story 6.2 builds on

- **`src/AgentEval/types.py:79 ToolCallTrace`** — `.name`, `.args` (Mapping[str, Any]) — for tool-call matching.
- **`src/AgentEval/types.py:336 AgentRunResult`** — `.tool_calls`, `.response_text`, `.metadata.mcp_coverage`.
- **`src/AgentEval/_kernel/coverage.py:60 _check_mcp_coverage`** — same gate Story 5.2 + 6.1 use.
- **`src/AgentEval/__init__.py` `allow_external_mcp_blind` plumbing** — Story 4.3 + 6.1 precedent for propagation.
- **`jsonschema`** — already pinned via Story 5.3 (`docs/contracts/run-manifest-schema.json` validates against it in tests).
- **Story 6.1 `_compute_*` precedent**: pure functions in `_internal.py`; Story 6.2 mirrors structure.

### Phase-1 carve-outs explicitly documented

- **AssertionEngine integration deferred to Story 6.3**: per D-1 drift fix. Documented in module docstring + AC-6.2.1 backend column.
- **No `match_mode=set` for `Tool Call Should Have Occurred`**: only `subset` (default) + `exact`. FR24 doesn't specify a set-mode variant.
- **`Should Match Regex` uses `re.search` not `re.fullmatch`**: matches operator intuition (substring-match by default). Documented in AC-6.2.4 + keyword docstring.
- **`Should Match Schema` raises `jsonschema.ValidationError`** (not `AssertionError`): preserves the jsonschema convention so consumers can catch the specific exception. RF's `Run Keyword And Expect Error` handles it.

### Files to create / modify

**NEW:**
- `src/AgentEval/_assertions/library.py` — `AssertionsLibrary` with 5 `@keyword` methods.
- `src/AgentEval/_assertions/_internal.py` — 7 pure helpers.
- `tests/unit/_assertions/__init__.py` — test package marker.
- `tests/unit/_assertions/test_assertions_library.py` — ~32 unit tests.

**MODIFY:**
- `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` 5th entry + `_build_components` `elif cls_name == "AssertionsLibrary"` propagation branch.
- `tests/unit/conventions/test_keyword_name_idiom.py` — verb allowlist extended with Story 6.2 ratified verbs.
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` — verb allowlist + `_PHASE_1_SHOULD_CARVE_OUTS` registry extended.
- `tests/unit/conventions/test_violation_detection.py` — sentinel `tool` → `dance` since `tool` is now in the allowlist.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` Story 6.2 ACs — amended (D-1 deferred AssertionEngine; D-2/D-3/D-4 spec clarifications).

**SOURCE DOCS AMENDED POST-CODE-REVIEW (per `feedback_in_flight_spec_amendment` Epic 5 retro):**
- `_bmad-output/planning-artifacts/epics.md` Story 6.2 AC backend column — amended per HIGH-ζ from "RF builtins" to "stdlib backend (Phase-1)".
- `_bmad-output/planning-artifacts/architecture.md` L838 carve-out registry — amended per HIGH-θ to enumerate the 5 AssertionsLibrary `Should *` entries.
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-6.2-S1 + DF-6.2-S2 added per HIGH-ε + HIGH-η.
- `docs/phase-1-5-carry-overs.md` — DF-6.2-S1 + DF-6.2-S2 added per `feedback_carry_over_catalog_gate`.

## Dev Agent Record

### Completion Notes

All 8 dev tasks complete (Task 9 = code-review handled by next skill in `/goal` loop). 36 unit tests pass; full regression sweep at 1107 tests / 8 skipped (+36 from Story 6.1 close at 1071). 5 PRD FR23-25 keywords shipped: `Trajectory Should Match` (4 modes per FR23a+FR23b), `Tool Call Should Have Occurred` (dict-subset + exact match modes per FR24), `Agent Response Should Contain/Match Regex/Match Schema` (FR25). IncompleteTraceError gate fires on tool-call-bearing assertions only; response assertions are observer-independent.

**Phase-1 carve-out applied per D-1:** AssertionEngine integration deferred to Story 6.3 (which plans `_assertions/adapter.py` scaffolding + `robotframework-assertion-engine>=4.0,<5.0` dep). Phase-1 ships stdlib backend (`re`, `jsonschema`).

**Convention extensions ratified in same commit** per `feedback_in_flight_spec_amendment`:
- Verb allowlist extended with `trajectory`, `tool`, `agent` in BOTH `tests/unit/conventions/test_keyword_name_idiom.py` AND `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`. PRD FR23-25 keyword names are noun-verbs by domain convention (BFCL evidence-layer framing); load-bearing per PRD.
- `_PHASE_1_SHOULD_CARVE_OUTS` registry extended with 5 AssertionsLibrary `Should *` entries — these are PRD-verbatim Should-style assertion keywords; ADR-022 AssertionEngine adoption (Story 6.3) retires the carve-out.
- Meta-test `test_keyword_name_idiom_allowlist_rejects_non_verb` updated to use `dance` as the absent-verb sentinel (was `tool` which is now in the allowlist).

`feedback_caller_count_check` verified: all 7 `_internal.py` helpers have caller-count ≥ 2. `feedback_carry_over_catalog_gate` UPSTREAM applied — no new DF-X-SY entries (AssertionEngine deferral already documented via Story 6.3 forward-ref).

### File List

**NEW:**
- `src/AgentEval/_assertions/_internal.py` — 7 pure helpers (4 trajectory matchers + dict-subset + tool-call matcher + schema resolver).
- `src/AgentEval/_assertions/library.py` — `AssertionsLibrary` with 5 `@keyword + @tier(1)` methods.
- `tests/unit/_assertions/__init__.py` — test package marker.
- `tests/unit/_assertions/test_assertions_library.py` — 36 unit tests.

**MODIFIED:**
- `src/AgentEval/__init__.py` — added `("AgentEval._assertions.library", "AssertionsLibrary")` to `_SUB_LIBRARIES` (5th entry) + `elif cls_name == "AssertionsLibrary"` propagation branch in `_build_components`.
- `tests/unit/conventions/test_keyword_name_idiom.py` — verb allowlist extended with Story 6.2 ratified verbs.
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` — verb allowlist + `_PHASE_1_SHOULD_CARVE_OUTS` registry extended.
- `tests/unit/conventions/test_violation_detection.py` — sentinel `tool` → `dance` since `tool` is now in the allowlist.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` Story 6.2 ACs — amended (D-1 AssertionEngine deferral; D-2/D-3/D-4 spec clarifications).

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (28th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 4 drifts: D-1 HIGH AssertionEngine integration deferred to Story 6.3 (no robotframework-assertion-engine dep in pyproject.toml + `_assertions/adapter.py` doesn't exist; Story 6.2 ships keyword surface with RF builtins backend; AssertionEngine wiring is logically Story 6.3 scope per epic L1649); D-2 MED `args=<dict>` vs `arguments={...}` → PRD FR24 `args=` wins; D-3 MED regex mode matches FR23b "name + serialized args" concatenation (epic AC was silent on the args portion); D-4 MED `schema=<dict>` OR `schema=<path>` both supported. 13 ACs documented. Closes PRD FR23a / FR23b / FR24 / FR25. Applies Epic 5 retro NEW norms `feedback_in_flight_spec_amendment` + `feedback_caller_count_check` + UPSTREAM `feedback_carry_over_catalog_gate`. | Bob |
| 2026-05-20 | 0.3.0   | Code-review HIGH/MED fixes applied (4-reviewer cross-LLM review complete). **8 HIGH applied:** (α) `_match_tool_call` validate `match_mode` BEFORE `args is None` short-circuit (Edge HIGH-2 + Codex probe 3-way: bypass when args=None silently returned True); (β) `_resolve_schema` tighten dispatch + validate loaded JSON is dict (Edge HIGH-3 + Codex probe + Blind HIGH-3 3-way: returned `list` on file-with-list, raised bare `TypeError` on non-str/non-Path); (γ) `_match_trajectory_regex` `json.dumps(..., default=str)` (Blind HIGH-2 + Edge HIGH-1 2-way: TypeError on `datetime`/`bytes`/custom args); (δ) `redact()` all 4 keyword AssertionError messages (Edge HIGH-4 single-reviewer on FR38a Story 5.3 contract: credential leakage via tool-args/response-text); (ε) DF-6.2-S1 FR34a EvidenceBlock catalog entry (Edge HIGH-5 Auditor near-certain band: PRD verbatim "Every assertion keyword writes evidence block"); (ζ) AC-6.2.1 backend column + AC-6.2.4 fail-message amended "RF builtins" → "stdlib backend" (Auditor #1 1-way spec drift); (η) DF-6.2-S2 paired-getter catalog entry (Auditor #2 1-way PRD L1104-1107 paired-getter table + AC-SIMPLICITY-02b); (θ) architecture L838 carve-out registry extended with 5 AssertionsLibrary entries (Auditor #3 1-way architecture-vs-test allowlist drift). **3 MED applied:** mode-validation-before-gate ordering (Blind LOW-17 + Edge MED-7 + Auditor #7 3-way); AC-6.2.10 32→44 + AC-6.2.13 1103→1115 ratification (Auditor #4 + #9 `feedback_in_flight_spec_amendment`); set-mode docstring + ratification test (Edge MED-6 + Auditor #14 2-way). 8 regression tests added (44 total assertion unit tests). 1115 unit+conformance+integration tests / 8 skipped (was 1107 pre-fix; +8 regression). | Amelia |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code-review). 4 new src + test files: `_assertions/_internal.py` (7 helpers: 4 trajectory matchers + dict-subset recursive + tool-call matcher + schema resolver); `_assertions/library.py` (AssertionsLibrary 5 `@keyword + @tier(1)` methods); `tests/unit/_assertions/__init__.py`; `tests/unit/_assertions/test_assertions_library.py` (36 unit tests — was estimated 32; final 36 covering all 4 trajectory modes + 8 tool-call match variants + 3 response variants + 4 gate tests with `match=r"<keyword name>"` per AC-6.2.6 + 3 no-gate-for-response + 2 boundary + invalid-mode tests). 1 source modification: `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` 5th entry + `_build_components` propagation. **Convention extensions ratified in-flight per `feedback_in_flight_spec_amendment`**: verb allowlist extended with `trajectory` + `tool` + `agent` (PRD FR23-25 mandates noun-verb keyword names per BFCL evidence-layer framing); `_PHASE_1_SHOULD_CARVE_OUTS` registry extended with 5 AssertionsLibrary `Should *` entries (ADR-022 AssertionEngine adoption Story 6.3 retires the carve-out); `test_keyword_name_idiom_allowlist_rejects_non_verb` sentinel changed `tool` → `dance` since `tool` is now allowed. Stdlib backend (`re`, `jsonschema`) for matching; no new deps. `feedback_caller_count_check` verified — all 7 `_internal.py` helpers have caller-count ≥ 2. `feedback_carry_over_catalog_gate` UPSTREAM applied (8th consecutive story) — no new DF-X-SY entries needed. All gates green: ruff/format/mypy clean (73 src files); license-headers PASS (73 files); **1107 unit+conformance+integration** (was 1071 at Story 6.1 close; +36 net) / 8 skipped; no CWD pollution. | Amelia |
