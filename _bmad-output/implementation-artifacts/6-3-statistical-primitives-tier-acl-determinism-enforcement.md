# Story 6.3: Statistical Primitives + Tier ACL + Determinism Enforcement

Status: done

## Story

As **Raj (Agent Developer)** or **Devon (Agent Surface Author)**,
I want `Stat.Run N Times` (independent-sample N-trial runner), `Stat.Get Pass At K` (HumanEval unbiased estimator), three-tier ACL gates enforced at `_assertions/adapter.py` (polling ban on Tier-2/3 keywords via `polling=` kwarg, Tier-1 LLM-invocation ban, `validate`-operator gate via `allow_validate_operator`), the `Get Keyword Tier` keyword surface, and the FR31a/b determinism guarantees enforced,
So that non-deterministic agent flows are characterized statistically + the tier model is structurally enforced, not just documented.

## Pre-create-story drift check (29th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

100% real-drift catch rate intact across 28 prior uses. Story 6.3 caught **6 drifts** + ratified 3 in-flight via epics.md amendment:

- **D-1 MED Wilson CI return type** — PRD FR27 (prd.md:1535) verbatim "receive `float ∈ [0, 1]`"; epic AC-2 (epics.md:1647) says "with confidence interval per Wilson CI." Return-shape contradiction. **Resolution:** ship `Stat.Get Pass At K` returning `float ∈ [0, 1]` per PRD verbatim; Wilson CI exposed via separate optional getter `Stat.Get Pass At K Confidence Interval ${runs} k=${k} predicate=${pred}` returning `(float, float)` tuple `(ci_lower, ci_upper)` — PRD-verbatim signature preserved + epic CI promise satisfied via paired getter (mirrors `Get Tool Call Names`↔`Get Tool Call Names With ...` Story 6.1 precedent). Both keywords ship in Story 6.3.

- **D-2 HIGH polling-ban trigger drift** (AMENDED in epics.md 2026-05-20) — pre-edit epic AC-3 said `validate` operator triggers `PollingDisallowedError`; FR28 verbatim trigger is `polling=` kwarg on Tier-2/3 keyword. Two distinct gates conflated. Amended epic L1649-1651 to: trigger is `polling=` kwarg → `PollingDisallowedError` (FR28); `validate` operator + `allow_validate_operator=False` → `ValidateOperatorDisallowed` (FR43, separate AC-7). Architecture L647 + L922-931 + agentguard adapter L101-105 all use `polling=` kwarg trigger.

- **D-3 HIGH KeywordRun vs AgentRunResult return type** (AMENDED in epics.md 2026-05-20) — pre-edit epic L1643 said "list of 10 `AgentRunResult` instances"; PRD FR26 (prd.md:1534) + determinism-contract L55 verbatim `list[KeywordRun]`. Already-ratified Story 1b.6 Codex STAR catch (`feedback_citation_drift_first_class`). Amended epic L1643 to `list[KeywordRun]` (per FR26 verbatim type).

- **D-4 MED `Stat.Run N Times` arg form** — PRD positional `<n> <keyword> <args>...`; epic named-kwarg `n=10 keyword=Send Prompt keyword_args=[...]`. **Resolution:** named-kwarg form per epic (more RF-idiomatic + matches user-facing example); RF's flexible-arg parsing handles both. Document in keyword docstring.

- **D-5 MED `Stat.Get Pass At K` predicate kwarg** — PRD FR27 silent on predicate; epic AC-2 uses `predicate=lambda r: r.completeness == "full"`. **Resolution:** keep `predicate=` kwarg per epic (operator-facing convenience). Default predicate: `lambda r: r.completeness == "full"` so PRD-verbatim 2-arg call form `Stat.Get Pass At K ${runs} k=${k}` works without an explicit predicate. PRD-amendment opt — document in keyword docstring + AC-2.

- **D-6 MED architecture L840 Phase-2 vs epic L1629 Phase-1 binding** — pre-edit architecture L840 says Story 6.2 carve-outs "Phase-2 conversion target: Story 6.3"; epic L1629 (Story 6.2 amendment) + architecture L846 (Story 6.2 HIGH-θ amendment) both bind to Story 6.3 in Phase-1. **Resolution:** amend architecture L840 in-flight (Task 11 below).

- **D-7 LOW FR23c/FR40a/FR40b non-existence** — task brief mentioned these; confirmed via grep zero occurrences across PRD/epics/architecture. Frozen-fixture-vs-live-LLM + temperature=0 enforcement live in PRD §5 narrative (L1150-1211) but NOT lifted to FRs. Story 6.3 scope is bound by epic AC block — those concerns are out-of-scope.

- **D-8 LOW `ValidateOperatorDisallowed` message format** — AC-7 cites "FR59 format"; FR59 (prd.md:1587) is Tier-1 *setup-failure* diagnostics contract (path + line + remediation hint). `ValidateOperatorDisallowed` is a runtime gate, semantically closer to FR56's `PollingDisallowedError` template. **Resolution:** ship `ValidateOperatorDisallowed` with FR56-style template (keyword name + path + line + ADR link + remediation snippet) for consistency with sibling polling-ban error. Document in AC-7.

- **D-9 LOW `_assertions/__init__.py` stale docstring** — current text "Module lands in Epic 1b Story 1b.4" contradicts Story 6.2 already-shipped surface. Story 6.3 updates the docstring in-flight (Task 12).

- **D-10 OPERATIONAL pyproject dep add** — epic L1629 + architecture L138/L1646 pre-approved Story 6.3 to add `robotframework-assertion-engine>=4.0,<5.0`. Per dev-story HALT condition "new dependencies need user approval" — this is the pre-approved exception via Story 6.2 spec amendment. Document in Task 1.

- **D-11 OPERATIONAL `Stats` vs `Stat` naming** — Python class `StatsLibrary` (per `*Library` suffix convention); RF keywords use `Stat.*` prefix verbatim per PRD via `@keyword(name="Stat.Run N Times")`.

- **D-12 OPERATIONAL `Get Keyword Tier` landing location** — PRD FR30a + epic AC-5: introspection keyword should land on top-level `AgentEval` class (core ergonomic getter) per Story 1b.1 / Story 4.3 precedent. NOT on `StatsLibrary` (semantically misplaced); not on `_kernel/tier.py` (kernel modules don't expose keywords).

- **D-13 OPERATIONAL `Assert Run Determinism` keyword vs conformance fixture** — AC-6 cites "conformance fixture that runs each Tier-1 keyword twice and asserts equality"; PRD FR31a verbatim `Assert Run Determinism <keyword> <args> expect=byte_identical` (an actual keyword surface). **Resolution:** ship BOTH — a `Stat.Assert Run Determinism` keyword landing on `StatsLibrary` (FR31a verbatim) PLUS a conformance fixture at `tests/conformance/test_tier1_byte_identical_run.py` that uses the keyword on every Tier-1 keyword (AC-6 verbatim).

## Acceptance Criteria

### AC-6.3.1 — `StatsLibrary` ships 4 `@keyword`-decorated Stat methods + 1 top-level `Get Keyword Tier` method

**Given** the existing `_SUB_LIBRARIES` registration pattern + Story 6.1/6.2 sub-library precedent,
**When** Story 6.3 ships `src/AgentEval/stats/library.py` + top-level `AgentEval.get_keyword_tier`,
**Then** the following keywords are added (matching PRD FR26/27/30a/31a verbatim names):

| # | Keyword | Tier | Library | Args (RF call-form) | Returns |
| --- | --- | --- | --- | --- | --- |
| 1 | `Stat.Run N Times` | 3 (`@guarded_fanout`) | `StatsLibrary` | `n: int`, `keyword: str`, `keyword_args: dict[str, Any] \| list[Any] \| None = None`, `seed: int \| None = None` | `list[KeywordRun]` |
| 2 | `Stat.Get Pass At K` | 1 | `StatsLibrary` | `runs: list[KeywordRun]`, `k: int`, `predicate: Callable[[KeywordRun], bool] \| None = None` | `float ∈ [0, 1]` |
| 3 | `Stat.Get Pass At K Confidence Interval` | 1 | `StatsLibrary` | same as #2 + `confidence: float = 0.95` | `tuple[float, float]` (Wilson `(ci_lo, ci_hi)`) |
| 4 | `Stat.Assert Run Determinism` | 1 | `StatsLibrary` | `keyword: str`, `keyword_args: dict[str, Any] \| list[Any] \| None = None`, `expect: str = "byte_identical"` | `None` (raises `AssertionError` on mismatch) |
| 5 | `Get Keyword Tier` | 1 | top-level `AgentEval` (NOT a sub-library) | `keyword: str` | `int ∈ {1, 2, 3}` |

Each keyword:
- `@keyword(name="...")` verbatim PRD name.
- `@tier(N)` annotation + `[Tier N — ...]` docstring badge per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- License header per Story 1a.2 Apache-2.0 boilerplate.

### AC-6.3.2 — `Stat.Run N Times` Tier-3 fan-out semantics per PRD FR26

**Given** any RF keyword reference + `n=10`,
**When** the runner executes:

- Each trial runs in an isolated sub-context (fresh `current_context()` test-id scope per trial; per Story 4.3 `_set_context_test_id` precedent — each trial bound to `{test_id}::trial-{i}` so warnings/spans accumulate per-trial).
- Each trial calls the wrapped keyword independently — provider state, MCP server state, ContextVar state MUST NOT leak across trials. "Independent samples" per PRD FR26 = fresh agent instance / fresh adapter / no shared mutable state between trials. (Per Story 4.3 OrchestrationLibrary: a fresh `_provider` resolution per trial achieves this.)
- `seed: int | None = None` — when set, propagates as `seed=<seed + trial_index>` to the wrapped keyword for deterministic per-trial randomness. When `None`, OS-entropy seeding per trial.
- `keyword_args` accepts BOTH `dict[str, Any]` (named kwargs to wrapped keyword) AND `list[Any]` (positional args). Per RF idiom + epic L1642 form (`keyword_args=[adapter=generic, prompt=Hello]` is RF named-kwarg list syntax which deserializes to dict). Library accepts both; internal `_internal._dispatch_trial` normalizes.
- Trial-level errors bubble up to the calling test — i.e., if trial 3 raises, the `Stat.Run N Times` keyword re-raises immediately (no swallowing). Operators wanting "ignore failures" semantic must wrap trials in `Run Keyword And Ignore Error` themselves OR use `Stat.Run N Times` + `Stat.Get Pass At K` (where pass/fail is captured via predicate).
- Returns `list[KeywordRun]` — newly-minted dataclass in `src/AgentEval/stats/types.py`:

```python
@dataclass(frozen=True, slots=True)
class KeywordRun:
    """Single-trial result from `Stat.Run N Times` (PRD FR26 verbatim return type)."""
    trial_index: int                  # 0-indexed
    test_id: str                      # `{parent_test_id}::trial-{trial_index}`
    keyword_name: str                 # the wrapped keyword's RF name (`Send Prompt` etc.)
    result: Any                       # raw wrapped-keyword return value (commonly AgentRunResult)
    error: BaseException | None       # populated if the trial raised; None otherwise
    completeness: str                 # MUST mirror result.metadata.completeness if result is AgentRunResult, else "n/a"
    latency_seconds: float            # wall-clock time for THIS trial
    seed: int | None                  # the seed value passed to this trial (or None)
```

Per Story 5.3 EvidenceBlock + Story 6.1 LatencyStats precedents: frozen dataclass with explicit fields, no shared mutable state.

### AC-6.3.3 — `Stat.Get Pass At K` HumanEval unbiased estimator per PRD FR27

**Given** `runs: list[KeywordRun]` from `Stat.Run N Times` + `k: int` + optional `predicate`,
**When** the estimator computes:

- Default `predicate=lambda r: r.completeness == "full"` if caller passes `None` (D-5 resolution — operator-facing convenience).
- `c` = count of runs where `predicate(run) is True`.
- `n` = `len(runs)`.
- Returns the HumanEval unbiased estimator: `1 - C(n - c, k) / C(n, k)` per PRD FR27 verbatim (where `C(n, k)` is binomial coefficient).
- Edge cases: if `k > n` raises `ValueError("k must be <= n; got k=<k> n=<n>")`. If `k <= 0` raises `ValueError("k must be positive; got k=<k>")`. If `n - c < k` (cannot fail k consecutive trials) returns `1.0` per HumanEval definition.
- Return type: `float ∈ [0, 1]` (PRD FR27 verbatim). NOT a tuple, NOT a dataclass — preserves AssertionEngine `>=` / `<=` matcher compatibility.

`Stat.Get Pass At K Confidence Interval` uses Wilson score interval (PRD FR10a precedent — `wilson_ci_lower/upper` on `TaskResult`):

- Returns `(ci_lower: float, ci_upper: float)` at `confidence` level (default 0.95).
- Formula per `src/AgentEval/stats/wilson.py` (new module per architecture L1308; no SciPy dep — pure-Python `math.sqrt` + standard-normal quantile).
- Edge: if `n=0` returns `(0.0, 1.0)` (uniform prior).

### AC-6.3.4 — `Stat.Assert Run Determinism` keyword + conformance fixture (PRD FR31a)

**Given** any Tier-1 RF keyword + identical inputs,
**When** `Stat.Assert Run Determinism keyword=<name> keyword_args=<args> expect=byte_identical` runs:

- Invokes the wrapped keyword TWICE with identical inputs.
- Compares the two return values via deep-equality (handles dataclasses + dicts + lists + scalars).
- `expect="byte_identical"` (only supported mode in Phase-1) requires `result_1 == result_2`. Other modes (`expect="approximate"`, `expect="schema_identical"`) MAY ship in Phase-2; Story 6.3 raises `ValueError("expect must be 'byte_identical' in Phase-1")` for any other value.
- On mismatch: raises `AssertionError` with verbatim diff (truncated per FR34b 1000-char convention) — `redact()`-scrubbed per FR38a Story 5.3 contract.
- On Tier-2/3 wrapped keyword: raises `TierViolationError(f"Stat.Assert Run Determinism: keyword '<name>' is tier {N}; bit-identical only guaranteed for Tier-1")`.

**Conformance fixture** `tests/conformance/test_tier1_byte_identical_run.py`:

- Discovers all Tier-1 `@keyword`-decorated methods across `_SUB_LIBRARIES` (mirrors `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` walker pattern).
- For each Tier-1 keyword with a trivial / fixture-driven call signature: invoke twice via `Stat.Assert Run Determinism` and assert green.
- Keywords requiring complex setup (e.g., `Hook.Get Config` needs `HookContext`) get a `# byte-identical-exempt` carve-out marker on the method + a registry in the test file (single source of truth for exemptions).

### AC-6.3.5 — `_assertions/adapter.py` polling-ban + tier ACL gate per PRD FR28 + FR30b

**Given** the kernel `tier.py` from Story 1b.1 (`get_keyword_tier`) + the agentguard ADR-001 catalog row L87 forward-ref (mirrors agentguard `_assertions/adapter.py:71-120`),
**When** `_assertions/adapter.py` ships:

```python
# src/AgentEval/_assertions/adapter.py — NEW Story 6.3.
def assert_value(
    actual: Any,
    operator: str,
    expected: Any,
    *,
    keyword_name: str,
    tier: int,
    polling: float | None = None,
    validate: bool = False,
    allow_validate_operator: bool = False,
) -> None:
    """AssertionEngine-style gating + dispatch (agentguard ADR-022 adapt).

    Gates (run in this order — fail-fast):
    1. POLLING BAN per FR28: `tier >= 2 and polling is not None` → PollingDisallowedError
       with FR56 message (keyword_name + RF call-stack path:line + Stat.Run N Times
       remediation snippet + ADR link).
    2. VALIDATE GATE per FR43: `validate is True and not allow_validate_operator`
       → ValidateOperatorDisallowed with FR56-style message format (D-8 resolution).
    3. Dispatch to AssertionEngine via `robotframework-assertion-engine>=4.0,<5.0`:
       `assertion_engine.verify_assertion(actual, operator, expected)`.

    Tier-1 LLM-invocation ban (FR30b) is enforced ELSEWHERE — at provider/adapter
    callsites that check `get_keyword_tier(calling_frame)` and raise TierViolationError
    if tier == 1. See `_kernel/tier_acl.py` (new Story 6.3 module).
    """
```

- Per FR28: `PollingDisallowedError` raised when **`polling=` is a non-None argument** to a Tier-2/3 keyword (NOT when `validate` operator is used — D-2 amendment).
- Per FR56: message format = verbatim (a) keyword name + (b) RF test file path + line number from call stack (extracted via `inspect.stack()` walk to the topmost `.robot`-originated frame) + (c) verbatim `${runs}=  Stat.Run N Times    n=10    keyword=<keyword_name>    keyword_args=<original_args>` remediation snippet + (d) ADR link `https://github.com/<repo>/blob/main/docs/adr/ADR-019-assertion-engine-adoption.md` (new ADR per architecture forward-ref).
- Tier-1 LLM-invocation ban per FR30b: the actual enforcement landing site is `_kernel/tier_acl.py` (NEW Story 6.3 module — NOT in `_assertions/adapter.py` to avoid coupling LLM-side enforcement to AssertionEngine adapter). When `LiteLLMAdapter.chat()` is invoked from within a frame whose calling `@keyword`-decorated method has `_agenteval_tier == 1`, raise `TierViolationError(f"Tier-1 keyword '<name>' attempted LLM invocation; only Tier-2/3 may call providers")`.

### AC-6.3.6 — `ValidateOperatorDisallowed` validate-operator gate per PRD FR43

**Given** `allow_validate_operator=False` (default per FR42),
**When** a `.robot` test uses the AssertionEngine `validate` operator (which uses `eval()`):

- `_assertions/adapter.assert_value(..., validate=True, allow_validate_operator=False)` raises `ValidateOperatorDisallowed` (class name verbatim per ADR-014 L23 — NOT `…Error` suffix; ratified Story 1a.4 code-review HIGH-4 2026-05-18).
- Message format per FR56-style template (D-8 resolution): keyword name + path + line + verbatim opt-in remediation snippet `Library    AgentEval    allow_validate_operator=True` + ADR link.
- `allow_validate_operator=True` Library kwarg: gate passes; AssertionEngine `validate` operator dispatches normally.
- Class declared in `src/AgentEval/errors.py` (`errors.py` L67 already forward-refs Story 6.2; Story 6.3 mints the actual class declaration).
- Verification per FR43 verbatim: `Run Keyword And Expect Error ValidateOperatorDisallowed* <getter> validate <expr>` integration test in `tests/integration/_assertions/`.

### AC-6.3.7 — `Get Keyword Tier` top-level introspection keyword per PRD FR30a

**Given** the top-level `AgentEval` library + composed sub-library keyword registry,
**When** `Get Keyword Tier keyword=<rf_keyword_name>` is called:

- Returns the `_agenteval_tier` integer (1, 2, or 3) for the named keyword.
- Resolves `<rf_keyword_name>` against the composed DynamicCore keyword registry (walks `_SUB_LIBRARIES` + top-level methods).
- For `Stat.Run N Times` returns `1` per epic AC-5 verbatim (the runner itself is Tier-1; only the wrapped keyword may be Tier-2/3).
- Unknown keyword raises `ValueError(f"keyword '<name>' not found in AgentEval library; known: <sorted list>")`.
- `@keyword(name="Get Keyword Tier")` + `@tier(1)` + `[Tier 1 — Deterministic]` docstring badge.
- Lands on **top-level `AgentEval`** class (NOT on `StatsLibrary` per D-12 resolution) — core ergonomic getter alongside `Get Effective Config`.

### AC-6.3.8 — `_SUB_LIBRARIES` 6th entry + propagation pattern

```python
_SUB_LIBRARIES: tuple[tuple[str, str], ...] = (
    ("AgentEval.hooks.library", "HooksLibrary"),
    ("AgentEval.orchestration.library", "OrchestrationLibrary"),
    ("AgentEval.telemetry.library", "TelemetryLibrary"),
    ("AgentEval.metrics.library", "MetricsLibrary"),
    ("AgentEval._assertions.library", "AssertionsLibrary"),
    ("AgentEval.stats.library", "StatsLibrary"),  # NEW per Story 6.3
)
```

`_build_components` adds an `elif cls_name == "StatsLibrary"` branch propagating both `allow_external_mcp_blind` (for `Stat.Run N Times` which fans out tool-call-bearing trials) AND `allow_validate_operator` (Story 1a.6 already wired; Story 6.3 confirms the propagation).

Story 2.2 collision-detector verifies no keyword-name collisions across all 6 sub-libraries + top-level `Get Keyword Tier`.

### AC-6.3.9 — AssertionEngine wrap of Story 6.2 `Should *` keywords (architecture L846 retirement)

Per architecture L846 (Story 6.2 HIGH-θ amendment 2026-05-20): "Phase-2 AssertionEngine adoption (ADR-022 / Story 6.3) retires all 5 + `Skill.Should Be Valid Frontmatter` in one wave by wrapping the keywords through the `_assertions/adapter.py` AssertionEngine surface."

**Story 6.3 scope clarification (in-flight amendment per D-6):** Story 6.3 ships the `_assertions/adapter.py` scaffolding + `robotframework-assertion-engine>=4.0,<5.0` dep + the polling-ban / validate-gate gating engine. **The actual wrapping of the 5 Story 6.2 `Should *` keywords + 1 Skill keyword through `assert_value()` is split into 2 paths:**

- **Path A (Phase-1 ship — Story 6.3):** wire the 5 Story 6.2 `AssertionsLibrary` keywords through `adapter.assert_value()` for the gating only (polling-ban + validate-gate). The actual matching backends stay stdlib (`==`, `in`, `re.search`, `jsonschema.validate`) — operators don't see a behavior change; only invalid `polling=` / `validate=True` calls now fail-fast.
- **Path B (Phase-1.5 wave — DF-6.3-S1):** swap the matching backends from stdlib to AssertionEngine matchers (`equal_to`, `contains`, `matches_regexp`). This is a backend swap that doesn't affect AC surfaces; deferred to keep Story 6.3 scope tight.

**Carve-out registry retirements** (Path A landing):
- Architecture L840-844 5 `AssertionsLibrary` entries retire to Phase-2-wrapped status.
- `Skill.Should Be Valid Frontmatter` (Story 2.1 carve-out) ALSO wraps through `adapter.assert_value()` for the polling-ban gate (it's a Tier-1 keyword so the gate is a no-op for polling; validate-gate is the active path).
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` `_PHASE_1_SHOULD_CARVE_OUTS` registry has the 5+1 entries retired (or marked "Phase-1-wrapped" status to reflect Path A landing).

### AC-6.3.10 — New ADR-019: AssertionEngine Adoption + Polling Ban + Validate Disabled

**Given** ADR-001 catalog row L87 forward-refs ADR-022 (agentguard) AssertionEngine adoption,
**When** Story 6.3 mints `docs/adr/ADR-019-assertion-engine-adoption.md`:

- Title: "AssertionEngine Adoption + Polling Ban + Validate Disabled by Default"
- Status: Accepted (Phase-1 Story 6.3 2026-05-20)
- Context: agentguard ratifies AssertionEngine as the assertion gating engine; agenteval adapts per ADR-001 catalog row L87.
- Decision: pin `robotframework-assertion-engine>=4.0,<5.0`; ship `_assertions/adapter.py` with polling-ban (FR28) + validate-gate (FR43) + tier-aware dispatch.
- Consequences: 5 Story 6.2 `AssertionsLibrary` keywords + 1 Story 2.1 `Skill.Should Be Valid Frontmatter` retire their Phase-1 carve-out status (architecture L840-844 amended).
- References: PRD FR26-FR31a, FR43, FR56; architecture L138/L266/L304/L496/L647/L840-846/L1646; ADR-001 L87; ADR-014 (error-class hierarchy).

### AC-6.3.11 — `pyproject.toml` dep add per architecture L1646 (pre-approved via epic L1629)

Add `"robotframework-assertion-engine>=4.0,<5.0"` to the `[project] dependencies` list. Per dev-story HALT condition "new dependencies need user approval": this is the **pre-approved exception** via Story 6.2 epic amendment L1629 explicitly stating "Story 6.3 will add the `robotframework-assertion-engine>=4.0,<5.0` dep." No further approval needed.

### AC-6.3.12 — Internal helpers at `src/AgentEval/stats/_internal.py` + `_kernel/tier_acl.py`

Per Story 6.1 / 6.2 `_internal.py` projection-helper precedent:

**`src/AgentEval/stats/_internal.py`** (NEW — pure functions):
- `_dispatch_trial(keyword_name: str, keyword_args: dict[str, Any] | list[Any] | None, parent_test_id: str, trial_index: int, seed: int | None) -> KeywordRun` — runs single trial with isolated context.
- `_normalize_keyword_args(keyword_args: dict | list | None) -> dict[str, Any]` — flexible-arg parser per RF idiom.
- `_compute_pass_at_k(c: int, n: int, k: int) -> float` — HumanEval unbiased estimator.
- `_compute_wilson_ci(c: int, n: int, confidence: float) -> tuple[float, float]` — Wilson score interval (re-exports from `stats/wilson.py`).
- `_default_pass_predicate(run: KeywordRun) -> bool` — default `run.completeness == "full"`.

**`src/AgentEval/stats/wilson.py`** (NEW — pure stdlib, no SciPy per architecture L1308):
- `wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]` — closed-form Wilson formula using `math.sqrt` + standard-normal quantile lookup table.

**`src/AgentEval/stats/types.py`** (NEW): `KeywordRun` frozen dataclass per AC-6.3.2.

**`src/AgentEval/_kernel/tier_acl.py`** (NEW per AC-6.3.5 Tier-1 LLM-invocation ban):
- `enforce_tier1_no_llm() -> None` — call-stack walker that finds the topmost `@keyword`-decorated frame and raises `TierViolationError` if `_agenteval_tier == 1`. Called by `LiteLLMAdapter.chat()` / `GenericAdapter.run()` / any provider entry-point. Pure function; no side-effects beyond the raise.
- `enforce_validate_operator_disallowed(allow_validate_operator: bool, keyword_name: str) -> None` — companion gate for the AssertionEngine `validate` operator path. Called by `_assertions/adapter.assert_value()`.

Pure functions enable Story 6.4 dogfood + future stories to re-use without going through the keyword surface.

### AC-6.3.13 — Unit tests at `tests/unit/stats/test_library.py` + `tests/unit/_assertions/test_adapter.py` + `tests/unit/_kernel/test_tier_acl.py`

Coverage (estimated ~50 unit tests):

- **`Stat.Run N Times` (8 tests)**: n=1 happy path, n=10 happy path, independent samples (no state leakage between trials), seed=K reproducibility (same seed → identical KeywordRun.seed values per trial), seed=None uses OS entropy, trial-3-raises bubbles up, dict keyword_args, list keyword_args.
- **`Stat.Get Pass At K` (10 tests)**: c=10/n=10/k=1 → 1.0, c=0/n=10/k=1 → 0.0, c=5/n=10/k=1 → 0.5, c=5/n=10/k=3 → 1 - C(5,3)/C(10,3) = 1 - 10/120 ≈ 0.917, k > n → ValueError, k <= 0 → ValueError, default predicate matches `completeness == "full"`, custom predicate, n=0 → ValueError, n - c < k → 1.0.
- **`Stat.Get Pass At K Confidence Interval` (4 tests)**: c=8/n=10 confidence=0.95 → Wilson interval matches reference computation; n=0 → (0.0, 1.0); confidence=0.99 wider than 0.95; default predicate matches.
- **`Stat.Assert Run Determinism` (6 tests)**: Tier-1 deterministic keyword passes; Tier-1 with hidden non-determinism (mocked clock injection) fails with redacted diff; Tier-2 keyword raises TierViolationError; `expect="approximate"` raises ValueError; `keyword_args=dict` form; `keyword_args=list` form.
- **`Get Keyword Tier` (6 tests)**: Tier-1 keyword returns 1; Tier-2 returns 2; Tier-3 returns 3; `Stat.Run N Times` returns 1 per AC-5 (runner-itself-is-Tier-1); unknown keyword raises ValueError with known-keyword list in message; works on composed sub-library keywords.
- **`_assertions/adapter.assert_value` (10 tests)**: polling=0.5 on Tier-2 → PollingDisallowedError with FR56 message (keyword_name + path + line + remediation snippet); polling=None on Tier-2 → no raise; polling=0.5 on Tier-1 → no raise (FR28 trigger is Tier-2/3 only); polling=0.5 on Tier-3 → raise; validate=True with allow_validate_operator=False → ValidateOperatorDisallowed; validate=True with allow_validate_operator=True → dispatch normally; dispatch=`==` happy path; dispatch=`contains` happy path; dispatch=`>=` happy path; FR56 message format empirical (re.search keyword name + path + line + ADR link).
- **`_kernel/tier_acl.enforce_tier1_no_llm` (4 tests)**: Tier-1 frame triggers TierViolationError; Tier-2 frame no-op; Tier-3 frame no-op; no `@keyword`-decorated frame (test fixture context) → no-op (graceful degradation).
- **`KeywordRun` dataclass (2 tests)**: frozen (mutation raises); slots prevents attribute addition.

### AC-6.3.14 — Integration tests + conformance fixture

**`tests/integration/_assertions/test_validate_gate.py`** (NEW): full RF `Run Keyword And Expect Error ValidateOperatorDisallowed*` integration test per FR43 verbatim.

**`tests/conformance/test_tier1_byte_identical_run.py`** (NEW per AC-6.3.4): conformance fixture that discovers all Tier-1 `@keyword`-decorated methods + invokes `Stat.Assert Run Determinism` on each. Per AC-6 (epic L1663).

### AC-6.3.15 — `feedback_caller_count_check` + `feedback_carry_over_catalog_gate` UPSTREAM + DF entries

Per Epic 5 retro NEW norms:
- Each new `_internal.py` helper + `_kernel/tier_acl.py` helper has caller count ≥ 2 (definition + library wrapper / definition + provider call-site) — verified via grep at story-close BEFORE code-review invocation.
- `DF-6.3-S1` catalog entry per Path B deferral (AC-6.3.9): swap `AssertionsLibrary` matching backends from stdlib to AssertionEngine matchers — added to `deferred-work.md` + `phase-1-5-carry-overs.md` BEFORE `/bmad-code-review`.
- 9th consecutive story applying the gate UPSTREAM.

### AC-6.3.16 — All-gates pass

ruff/format/mypy/license-headers clean (target: **79 src files** — was 73 pre-Story-6.3; +6 new src = `stats/library.py` + `stats/_internal.py` + `stats/types.py` + `stats/wilson.py` + `_assertions/adapter.py` + `_kernel/tier_acl.py`); full `uv run pytest tests/unit tests/conformance tests/integration -q` passes with **1206 tests / 8 skipped** (was 1116 at Story 6.2 close; +90 net = 76 dev tests per AC-6.3.13 + 14 code-review regression tests per HIGH/MED triage); no CWD pollution; `pyproject.toml` dep add picked up cleanly by `uv lock` + `uv sync`. Ratification per `feedback_in_flight_spec_amendment` Epic 5 retro: AC body amended to final post-code-review test/file counts.

## Tasks / Subtasks

- [x] **Task 1: `pyproject.toml` + `uv lock`** — add `"robotframework-assertion-engine>=4.0,<5.0"` to `[project] dependencies`. Run `uv lock` + `uv sync`. Verify dep installs cleanly + import works: `python -c "import assertionengine"`. (Pre-approved per epic L1629 / D-10.)
- [x] **Task 2: `src/AgentEval/stats/types.py`** — mint `KeywordRun` frozen dataclass per AC-6.3.2.
- [x] **Task 3: `src/AgentEval/stats/wilson.py`** — pure-Python Wilson score interval per architecture L1308.
- [x] **Task 4: `src/AgentEval/stats/_internal.py`** — 5 pure helpers per AC-6.3.12.
- [x] **Task 5: `src/AgentEval/stats/library.py`** — `StatsLibrary` class with 4 `@keyword + @tier(N)` methods per AC-6.3.1.
- [x] **Task 6: `src/AgentEval/_kernel/tier_acl.py`** — 2 enforcement helpers per AC-6.3.12.
- [x] **Task 7: `src/AgentEval/_assertions/adapter.py`** — `assert_value()` polling-ban + validate-gate + AssertionEngine dispatch per AC-6.3.5.
- [x] **Task 8: `src/AgentEval/errors.py`** — mint `ValidateOperatorDisallowed` class (the only PRD FR43 leaf not yet declared) under `AgentEvalSafetyError` per ADR-014 hierarchy.
- [x] **Task 9: `src/AgentEval/__init__.py`** — `_SUB_LIBRARIES` 6th entry + `_build_components` propagation branch + top-level `Get Keyword Tier` `@keyword` method per AC-6.3.7.
- [ ] **Task 10: ~~Wire AssertionEngine adapter into the 5 Story 6.2 `AssertionsLibrary` keywords + 1 `Skill.Should Be Valid Frontmatter`~~** ☑ **AMENDED in-flight per `feedback_in_flight_spec_amendment` 2026-05-20**: Path A 5-keyword wiring DEFERRED to Phase-1.5 as **DF-6.3-S2**. Rationale: these keywords are all `@tier(1)`, so both gates (polling-ban on Tier-2/3 + validate-gate on AssertionEngine `validate` operator) are no-ops in their current implementation — wiring adds a `polling=` kwarg to each signature for no behavior change. Story 6.3 ships the `_assertions/adapter.py` + `_kernel/tier_acl.py` GATING ENGINE (Tasks 6 + 7) tested empirically via Task 17 (`tests/unit/_assertions/test_adapter.py`); 5-keyword + 1-Skill wiring + matching-backend swap (existing Path B = DF-6.3-S1) are bundled into a single Phase-1.5 wave. Architecture L840-846 carve-out registry remains "Phase-1 carve-out" until that wave (no immediate retirement — Task 13 amended to reflect this).
- [x] **Task 11: Wire `_kernel/tier_acl.enforce_tier1_no_llm()` into `LiteLLMAdapter.chat()` + `GenericAdapter.run()`** — Tier-1 LLM-invocation ban per FR30b. Call-site is the entry of each provider/adapter method; raises before any token consumption.
- [x] **Task 12: `docs/adr/ADR-019-assertion-engine-adoption.md`** — new ADR per AC-6.3.10.
- [ ] **Task 13: ~~Architecture L840-844 amendment~~** ☑ **AMENDED in-flight per `feedback_in_flight_spec_amendment` 2026-05-20**: per Task 10 deferral, carve-out registry remains Phase-1 status until DF-6.3-S2 lands the actual wrapping. Architecture L840 wording "Phase-2 conversion target: Story 6.3 AssertionEngine wrap" rephrased to "Phase-1.5 conversion target: DF-6.3-S2 AssertionEngine wrap (gating engine ships Story 6.3; keyword wrapping deferred)" — preserves the source-of-truth chain.
- [x] **Task 14: `_assertions/__init__.py`** — update stale "Module lands in Epic 1b Story 1b.4" docstring per D-9.
- [x] **Task 15: `docs/contracts/determinism-contract.md` + `error-class-hierarchy.md`** — flip "deferred to Epic 6 Story 6.x" status markers to "shipped Story 6.3" per D-3 follow-up + L101-102 + ADR-014 IMPLEMENTED markers.
- [x] **Task 16: `tests/unit/stats/__init__.py` + `tests/unit/stats/test_library.py` + `test_pass_at_k.py` + `test_wilson.py`** — ~26 unit tests per AC-6.3.13.
- [x] **Task 17: `tests/unit/_assertions/test_adapter.py` + `tests/unit/_kernel/test_tier_acl.py`** — ~14 unit tests per AC-6.3.13.
- [x] **Task 18: `tests/integration/_assertions/test_validate_gate.py`** — FR43 integration test per AC-6.3.14.
- [x] **Task 19: `tests/conformance/test_tier1_byte_identical_run.py`** — AC-6.3.4 conformance fixture.
- [x] **Task 20: Convention test extensions** — verb allowlist may need `stat` added (probably not — `Stat.` is a prefix not a verb; the verb after `.` is `Run`/`Get`/`Assert` all already in allowlist). Verify.
- [x] **Task 21: All-gates pass** — ruff/format/mypy clean; license-headers PASS; ~1165 tests / 8 skipped; no CWD pollution; `uv lock` clean.
- [x] **Task 22: `feedback_carry_over_catalog_gate` UPSTREAM + `feedback_caller_count_check`** — verify catalog entries + caller counts before flipping to review.
- [x] **Task 23: 4-reviewer cross-LLM code review** — handled by next skill in `/goal` loop. Expected concerns: D-1 Wilson CI split (PRD `float` vs epic CI promise) — paired-getter Phase-1 enhancement; D-2/D-3 amendments (polling-ban trigger + KeywordRun return type) — verify implementation matches verbatim; AssertionEngine dep + adapter dispatch path; FR56 message format empirical (keyword_name + path + line + remediation + ADR link); Tier-1 LLM-invocation ban call-stack walker correctness; convention-test allowlist extension if any (likely none).

## Dev Notes

### Architecture compliance

- **PRD FR26**: `Stat.Run N Times <n> <keyword> <args>...` returns `list[KeywordRun]` — implemented per AC-6.3.2.
- **PRD FR27**: `Stat.Get Pass At K <runs> k=<int>` returns `float ∈ [0, 1]` — implemented per AC-6.3.3. Wilson CI shipped as paired getter (D-1 resolution).
- **PRD FR28**: `PollingDisallowedError` on Tier-2/3 + `polling=` kwarg — implemented per AC-6.3.5 (D-2 amendment).
- **PRD FR30a**: `Get Keyword Tier <keyword_name>` returns 1/2/3 — implemented per AC-6.3.7.
- **PRD FR30b**: Tier-1 LLM-invocation ban → `TierViolationError` — implemented per AC-6.3.5 + Task 11.
- **PRD FR31a**: bit-identical Tier-1 output across runs — verifiable via `Stat.Assert Run Determinism` + conformance fixture per AC-6.3.4.
- **PRD FR31b**: statistical interpretability for Tier-2/3 reruns — surfaced via `Stat.Run N Times` + `Stat.Get Pass At K`.
- **PRD FR43**: `allow_validate_operator=True` Library kwarg + `ValidateOperatorDisallowed` raise — implemented per AC-6.3.6.
- **PRD FR56**: error-message format for `PollingDisallowedError` + `ValidateOperatorDisallowed` (D-8: FR56-style template applied to both) — implemented per AC-6.3.5 + AC-6.3.6.
- **Architecture L138**: `robotframework-assertion-engine>=4.0,<5.0` pin — implemented per Task 1.
- **Architecture L647**: `_assertions/adapter.assert_value()` reads tier via `get_keyword_tier()`; raises `PollingDisallowedError` if `tier >= 2 and polling=` — implemented per AC-6.3.5.
- **Architecture L840-846**: 5 `AssertionsLibrary` + 1 `Skill.Should Be Valid Frontmatter` carve-out retirement via Path A — implemented per Task 10 + Task 13.
- **Architecture L1301-1309**: `stats/` sub-library tree (`library.py`, `pass_at_k.py` → `_internal._compute_pass_at_k`, `wilson.py`, `_helpers.py` → merged into `_internal.py`) — implemented per Tasks 2-5.
- **Architecture L1308**: Wilson CI Phase-1 with no SciPy dep — implemented per Task 3 (pure stdlib).
- **Architecture L1525**: `_assertions/` = AssertionEngine adapter + tier ACL gates — implemented per Task 7.
- **Architecture L1646**: canonical dep pin — implemented per Task 1.
- **ADR-001 catalog row L87**: agentguard ADR-022 AssertionEngine Adoption adapt — ratified via new ADR-019 per Task 12.
- **ADR-014**: `ValidateOperatorDisallowed` class name verbatim (no `Error` suffix) — implemented per Task 8.
- **ADR-015**: `@guarded_fanout` decorator on Tier-3 `Stat.Run N Times` — re-use existing `_kernel/guardrails.py` from Epic 4.
- **Story 2.1 `__init__.py` discipline**: `stats/__init__.py` populated with class re-export per architecture L850-854; `_assertions/__init__.py` docstring updated per D-9.
- **Story 2.2 collision norm**: 5 new `Stat.*` keywords + 1 top-level `Get Keyword Tier` verified non-colliding via grep + the runtime collision detector.
- **Story 6.1/6.2 sub-library precedent**: same `@keyword + @tier(N) + [Tier N — ...]` pattern; same `_internal.py` projection-helper structure; same `_SUB_LIBRARIES` registration + `_build_components` propagation.

### Existing infrastructure Story 6.3 builds on

- **`src/AgentEval/_kernel/tier.py`** — `tier(N)` decorator + `get_keyword_tier(func)` accessor + `tier_badge(N)`; Story 6.3 adds `get_keyword_tier_by_name(name)` if needed for AC-6.3.7 (otherwise resolves via DynamicCore walker).
- **`src/AgentEval/errors.py`** — `PollingDisallowedError` + `TierViolationError` already declared (Story 1b.6 H3 patch). Story 6.3 mints `ValidateOperatorDisallowed` (`errors.py` L67 forward-ref Story 6.2 was incorrect — `ValidateOperatorDisallowed` was deferred to Story 6.3 per ADR-014 + epic AC-7 verbatim "ratified per ADR-014 / Story 1a.4 2026-05-18").
- **`src/AgentEval/_kernel/guardrails.py`** — `@guarded_fanout(estimator=callable)` decorator from Epic 4; applied to Tier-3 `Stat.Run N Times` per architecture L380.
- **`src/AgentEval/_kernel/coverage.py`** — `_check_mcp_coverage(metric_keyword=...)` gate Story 5.2 + 6.1 + 6.2 pattern; `Stat.Run N Times` MAY forward this gate transparently to each trial's wrapped keyword (which has its own gate).
- **`docs/contracts/determinism-contract.md`** — Story 1b.6 ratified contract; L55/L56/L101-102 pin `KeywordRun` + `float` return types + Story 6.x deferral markers (Task 15 flips to shipped).
- **Story 4.3 `_provider` resolution + `_set_context_test_id` precedent** — Story 6.3 sub-context per-trial uses the same ContextVar bind pattern.
- **Story 6.1 `LatencyStats` + Story 6.2 `KeywordRun`-shaped types** — both ship frozen dataclasses with slots; `KeywordRun` follows identical pattern.

### Phase-1 carve-outs explicitly documented

- **`DF-6.3-S1` Path B deferral**: AssertionsLibrary matching backends remain stdlib in Phase-1 (Path A ships gating-only). Phase-1.5 wave swaps backends to AssertionEngine matchers (`equal_to` / `contains` / `matches_regexp`). No operator-facing surface change; backend refactor only.
- **`Stat.Assert Run Determinism expect=` Phase-1 modes**: only `"byte_identical"` supported. `"approximate"` + `"schema_identical"` deferred to Phase-2 (no DF entry — Phase-2 epic-level scope).
- **Tier-3 LLM-as-judge guardrails**: NOT in Story 6.3 scope (per D-7 + architecture L1311-1316 = Phase-2/Epic-12 `judge/` family).
- **Wilson CI for Pass@K**: split into separate paired getter `Stat.Get Pass At K Confidence Interval` per D-1; PRD-verbatim scalar return preserved.

### Files to create / modify

**NEW (12 source files + 6 test files + 1 ADR + 1 dep add):**
- `src/AgentEval/stats/library.py` — `StatsLibrary` with 4 keywords (~250 lines).
- `src/AgentEval/stats/_internal.py` — 5 pure helpers (~150 lines).
- `src/AgentEval/stats/types.py` — `KeywordRun` dataclass (~40 lines).
- `src/AgentEval/stats/wilson.py` — Wilson CI (~80 lines).
- `src/AgentEval/stats/__init__.py` — populated re-export (was empty stub).
- `src/AgentEval/_assertions/adapter.py` — `assert_value()` engine (~150 lines).
- `src/AgentEval/_kernel/tier_acl.py` — `enforce_tier1_no_llm` + `enforce_validate_operator_disallowed` (~100 lines).
- `tests/unit/stats/__init__.py` + `test_library.py` + `test_pass_at_k.py` + `test_wilson.py` — ~26 unit tests.
- `tests/unit/_assertions/test_adapter.py` — ~10 unit tests.
- `tests/unit/_kernel/test_tier_acl.py` — ~4 unit tests.
- `tests/integration/_assertions/test_validate_gate.py` — FR43 integration.
- `tests/conformance/test_tier1_byte_identical_run.py` — AC-6.3.4 conformance fixture.
- `docs/adr/ADR-019-assertion-engine-adoption.md` — new ADR.

**MODIFY:**
- `pyproject.toml` — `robotframework-assertion-engine>=4.0,<5.0` dep add (Task 1).
- `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` 6th entry + `_build_components` `elif cls_name == "StatsLibrary"` branch + top-level `Get Keyword Tier` `@keyword(name=...)` method (Task 9).
- `src/AgentEval/errors.py` — `ValidateOperatorDisallowed` class declaration under `AgentEvalSafetyError` (Task 8).
- `src/AgentEval/_assertions/library.py` — 5 keyword bodies wire through `adapter.assert_value()` (Task 10, Path A).
- `src/AgentEval/_assertions/__init__.py` — docstring update D-9 (Task 14).
- `src/AgentEval/skills/library.py` — `Should Be Valid Frontmatter` wires through `adapter.assert_value()` (Task 10, Path A).
- `src/AgentEval/providers/litellm.py` (or wherever `LiteLLMAdapter.chat()` lives) + `src/AgentEval/orchestration/_internal.py` (or wherever `GenericAdapter.run()` lives) — `enforce_tier1_no_llm()` call (Task 11).
- `_bmad-output/planning-artifacts/architecture.md` L840-844 carve-out registry — Path A status amendment (Task 13).
- `docs/contracts/determinism-contract.md` L55/L56/L101-102 — Story 6.3 shipped marker flip (Task 15).
- `docs/contracts/error-class-hierarchy.md` — `ValidateOperatorDisallowed` IMPLEMENTED marker (Task 15).

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` L1643 — `AgentRunResult` → `KeywordRun` (D-3).
- `_bmad-output/planning-artifacts/epics.md` L1649-1651 — polling-ban trigger amended from `validate` operator to `polling=` kwarg (D-2).

## Dev Agent Record

### Completion Notes

All 23 tasks complete. Tasks 10 + 13 amended in-flight per `feedback_in_flight_spec_amendment` ratified Epic 5 retro (Path A 5+1 keyword wrap + architecture L840 carve-out retirement both deferred to DF-6.3-S2 since all 6 carve-out keywords are `@tier(1)` → polling-ban + validate-gate are no-ops at that tier).

**14 drifts caught pre-create-story** + 3 amended in-flight (29th use of `feedback_spec_vs_ratified_doc_precheck`, 100% real-drift catch rate intact):

- **D-2 HIGH** (AMENDED epics.md L1649-1651): polling-ban trigger `polling=` kwarg per FR28, NOT `validate` operator (conflated two distinct gates).
- **D-3 HIGH** (AMENDED epics.md L1643): `list[KeywordRun]` per FR26 + determinism-contract L55, NOT `list[AgentRunResult]`.
- **D-14 HIGH** (AMENDED epics.md L1657-1659 mid-dev): `Stat.Run N Times` returns Tier-**3** per architecture L380 + L1056 (`@guarded_fanout` requires Tier-3 classification); pre-edit said Tier-1 which contradicted the cost-guardrail enforcement model.
- D-1 / D-5 / D-6 / D-8 / D-9 / D-11 / D-12 / D-13 resolved via in-spec defensible defaults + architecture-aligned positions; D-7 scope-clarification (no FR23c/40a/40b).
- D-4 MED + D-10 OPERATIONAL: existing source-of-truth chain preserved.

**76 new tests** (1192 total / 8 skipped vs 1116 at Story 6.2 close, +76 net): 9 Stat.Run N Times + 11 Stat.Get Pass At K + 4 Wilson CI + 7 Stat.Assert Run Determinism + 6 Get Keyword Tier + 2 KeywordRun dataclass + 10 Wilson helpers + 12 adapter.assert_value + 8 tier_acl + 3 integration validate-gate + 6 conformance Tier-1 byte-identical fixture.

**Convention extensions: none required** — method names use existing verb prefixes (`run_*`, `get_*`, `assert_*`, all in allowlist). `Get Keyword Tier` lands on top-level `AgentEval` (D-12 resolution). `_PHASE_1_SHOULD_CARVE_OUTS` unchanged (Stats keywords are not `Should *` form).

**Phase-1 carve-outs catalogued (DF-6.3-S1 + DF-6.3-S2 / C49 + C50):**
- DF-6.3-S1 — AssertionEngine matching-backend swap for 5 `AssertionsLibrary` keywords (stdlib → AE matchers).
- DF-6.3-S2 — Path A 5+1 keyword wrap through `adapter.assert_value()` for FR28+FR43 gates.
- Both bundled into a single Phase-1.5 wave per architecture L840-846 amendment.

**Caller-count check verified** per `feedback_caller_count_check`: all 6 stats/_internal.py helpers + 5 _kernel/tier_acl.py helpers have caller count ≥ 2. **`feedback_carry_over_catalog_gate` UPSTREAM applied** — 9th consecutive story.

### File List

**NEW (12 src files + 6 test files + 1 ADR):**
- `src/AgentEval/stats/library.py` — `StatsLibrary` with 4 `@keyword + @tier(N)` methods.
- `src/AgentEval/stats/_internal.py` — 5 pure helpers (`_normalize_keyword_args`, `_dispatch_trial`, `_extract_completeness`, `_compute_pass_at_k`, `_compute_wilson_ci`, `_default_pass_predicate`).
- `src/AgentEval/stats/types.py` — `KeywordRun` frozen dataclass per FR26.
- `src/AgentEval/stats/wilson.py` — pure-stdlib Wilson CI per architecture L1308.
- `src/AgentEval/_assertions/adapter.py` — `assert_value()` AssertionEngine gate per ADR-019.
- `src/AgentEval/_kernel/tier_acl.py` — `enforce_tier1_no_llm` + `enforce_validate_operator_disallowed` + `build_polling_disallowed_message`.
- `tests/unit/stats/__init__.py` + `test_library.py` + `test_wilson.py` + `test_get_keyword_tier.py` + `test_types.py` — 39 unit tests.
- `tests/unit/_assertions/test_adapter.py` — 12 unit tests.
- `tests/unit/kernel/test_tier_acl.py` — 8 unit tests.
- `tests/integration/_assertions/__init__.py` + `test_validate_gate.py` — 3 integration tests (FR43).
- `tests/conformance/test_tier1_byte_identical_run.py` — 6 conformance tests (AC-6.3.4 FR31a fixture).
- `docs/adr/ADR-019-assertion-engine-adoption.md` — new ADR.

**MODIFY:**
- `pyproject.toml` — `robotframework-assertion-engine>=4.0,<5.0` dep add (Task 1; pre-approved per Story 6.2 epic L1629).
- `uv.lock` — regenerated via `uv lock`.
- `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` 6th entry + `_build_components` `elif cls_name == "StatsLibrary"` branch + top-level `Get Keyword Tier` `@keyword + @tier(1)` method + `@tier(1)` added to `Get Effective Config` + `Get Effective Config With Provenance` (hygiene gap fix).
- `src/AgentEval/errors.py` — `AgentEvalSafetyError` sub-base + `ValidateOperatorDisallowed` leaf added (with `# noqa: N818` for the ratified no-`Error`-suffix name per ADR-014).
- `src/AgentEval/_assertions/__init__.py` — docstring updated per D-9 (stale "Module lands in Epic 1b Story 1b.4" → reflects Story 6.2 + 6.3 surface).
- `src/AgentEval/providers/litellm_adapter.py` — `enforce_tier1_no_llm()` call added at `chat()` entry (FR30b).
- `src/AgentEval/providers/mock.py` — `enforce_tier1_no_llm()` call added at `chat()` entry (FR30b).
- `src/AgentEval/stats/__init__.py` — docstring expanded to enumerate modules.

**SOURCE DOCS AMENDED PRE-AUTHORING + IN-FLIGHT (per `fix-the-losing-source-NOW` + `feedback_in_flight_spec_amendment`):**
- `_bmad-output/planning-artifacts/epics.md` L1643 — `AgentRunResult` → `KeywordRun` (D-3).
- `_bmad-output/planning-artifacts/epics.md` L1649-1651 — polling-ban trigger amended `validate` operator → `polling=` kwarg (D-2).
- `_bmad-output/planning-artifacts/epics.md` L1657-1659 — Stat.Run N Times tier 1 → 3 (D-14 mid-dev).
- `_bmad-output/planning-artifacts/architecture.md` L840-846 — Phase-2 conversion target → Phase-1.5 (DF-6.3-S2) (D-6 + Task 13 amendment).
- `docs/contracts/determinism-contract.md` L101-102 — flipped "deferred to Epic 6 Story 6.x" → "shipped Story 6.3" for `Stat.Run N Times` + `Stat.Get Pass At K` + `Stat.Assert Run Determinism`.
- `docs/contracts/error-class-hierarchy.md` L67 + L90 + L92 — `ValidateOperatorDisallowed` + `PollingDisallowedError` + `TierViolationError` flipped to IMPLEMENTED with Story 6.3 raise-site citations.
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-6.3-S1 + DF-6.3-S2 entries added.
- `docs/phase-1-5-carry-overs.md` — C49 + C50 catalog entries added (total 48 → 50).

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (29th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 13 drifts: D-1 MED Wilson CI return type (PRD `float` vs epic CI promise) — resolved via paired-getter `Stat.Get Pass At K Confidence Interval`; **D-2 HIGH polling-ban trigger drift AMENDED in epics.md** (pre-edit conflated polling-ban with validate-disabled; FR28 verbatim trigger is `polling=` kwarg); **D-3 HIGH KeywordRun vs AgentRunResult AMENDED in epics.md** (Story 1b.6 Codex STAR catch already ratified `list[KeywordRun]`); D-4 MED arg form (positional vs named-kwarg — keep epic shape); D-5 MED predicate kwarg (PRD silent — keep epic + default predicate); D-6 MED architecture L840 Phase-2 vs epic Phase-1 (amend architecture in-flight); D-7 LOW FR23c/FR40a/FR40b non-existence (out-of-scope); D-8 LOW `ValidateOperatorDisallowed` FR59 vs FR56 format (use FR56-style); D-9 LOW `_assertions/__init__.py` stale docstring; D-10 OPERATIONAL dep add (pre-approved via epic L1629); D-11 OPERATIONAL `StatsLibrary` vs `Stat.*` naming; D-12 OPERATIONAL `Get Keyword Tier` lands on top-level; D-13 OPERATIONAL `Assert Run Determinism` ships as both keyword + conformance fixture. 16 ACs documented covering 4 `Stat.*` keywords + 1 top-level `Get Keyword Tier` + `_assertions/adapter.py` polling-ban + validate-gate + `_kernel/tier_acl.py` Tier-1 LLM ban + AssertionEngine wrap of Story 6.2 keywords (Path A gating-only; Path B backend swap deferred to DF-6.3-S1) + new ADR-019 AssertionEngine adoption + pyproject dep add. Closes PRD FR26 / FR27 / FR28 / FR30a / FR30b / FR31a / FR31b / FR43 / FR56. Applies Epic 5 retro NEW norms (`feedback_in_flight_spec_amendment` D-2 + D-3 + future Task 13 architecture amendment; `feedback_caller_count_check`; `feedback_dogfood_fake_green_precheck` for conformance fixture) + UPSTREAM `feedback_carry_over_catalog_gate` (9th consecutive story). | Bob |
