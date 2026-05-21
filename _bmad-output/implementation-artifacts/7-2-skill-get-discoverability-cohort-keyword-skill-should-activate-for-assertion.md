# Story 7.2: Skill.Get Discoverability Cohort Keyword + Skill Should Activate For Assertion

Status: done

## Story

As **Devon (Agent Surface Author — skill author mode)**,
I want `Skill.Get Discoverability` cohort keyword (FR4b) that runs a task set against my skill across configurable models/trials, returning per-task Pass@k of correct activation + false-activation rate + missed-activation rate + competing-skills-picked attribution; plus `Skill Should Activate For` single-prompt assertion (FR4d) mirroring `Tool Call Should Have Occurred`,
So that I can claim "my skill is reliably discovered and activated across a representative task distribution" with cohort evidence — not just per-prompt anecdotes — symmetric to what Mei gets for MCP tools via FR10a.

## Pre-create-story drift check (32nd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-21)

**4 drifts caught + resolved pre-authoring** (per `fix-the-losing-source-NOW` pattern):

- **(D-1 MED)** **Epic AC says `[Tier 3 — Non-Deterministic]` libdoc badge.** The `tier.py` badge constant for level 3 is `[Tier 3 — Stochastic Fan-Out]` (ratified Story 6.3 via `tier_badge(3)`). "Non-Deterministic" does not appear in the tier badge dictionary. Convention test `test_keyword_docstrings_contain_tier_badge` would fail. **Resolution**: `Skill.Get Discoverability` docstring must use `[Tier 3 — Stochastic Fan-Out]`. Additionally, `Skill Should Activate For` is a **single-prompt assertion** (single LLM call, no fan-out) → **Tier-2**, so its badge is `[Tier 2 — Stochastic Single-Shot]`. All story ACs amended accordingly.

- **(D-2 MED)** **`mcp_coverage` field name on `SkillDiscoverabilityResult`.** The existing `DiscoverabilityResult` (Story 4.4) uses `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` for MCP-specific server coverage. For skill discoverability, the concept is about **adapter** coverage (was the adapter's response correctly evaluated?), not MCP server coverage. Using `mcp_coverage` on a skill result is semantically wrong per ADR-016 §Scope ("mcp_coverage field is exclusively for MCP instrumentation state"). **Resolution**: `SkillDiscoverabilityResult` uses `adapter_coverage: str` (Phase-1 always `"in_process"` since skills use InProcessAdapter from Story 1b.4). Symmetry with `DiscoverabilityResult.mcp_coverage` is intentional divergence, not a bug.

- **(D-3 LOW)** **`competing_skills_picked` in `SkillTaskResult`.** FR4b spec says "competing-skills-picked attribution per task". The Phase-1 activation heuristic (`skill_name.lower() in response_text.lower()`) cannot detect WHICH other skill was activated — it only detects if the TARGET skill was mentioned. **Resolution**: Phase-1 implementation always populates `competing_skills_picked = {}`. Document as explicit Phase-1 limitation in docstring and carry-over (DF-7.2-S1 / C56). Phase-2 will use a structured response schema or classifier.

- **(D-4 HIGH)** **Task YAML schema needs `should_activate: bool` field.** Existing `discoverability/tasks-basic.yaml` has `expected_tools` (MCP-specific). Skill discoverability tasks need `should_activate: bool` to distinguish prompts that SHOULD trigger the skill from decoys. No existing loader or schema type handles this. **Resolution**: New `SkillDiscoverabilityTask` dataclass in `skills/_internal.py` with `should_activate: bool` field; new YAML fixture at `tests/fixtures/discoverability/skill-tasks-basic.yaml`; new loader `load_skill_discoverability_tasks()` in `skills/_internal.py`; new error type `InvalidSkillDiscoverabilityTasksError` reusing `_FR59Tier1SetupFailureError` pattern for consistent FR59 error format. **WAIT**: checking the existing error catalog — `InvalidDiscoverabilityTasksError` already exists for MCP tasks. The skill variant should be its own leaf to avoid conflation. Add `InvalidSkillDiscoverabilityTasksError` to `errors.py`.

## Acceptance Criteria

### AC-7.2.1 — `SkillDiscoverabilityTask` dataclass + `load_skill_discoverability_tasks()` loader

**Given** a YAML file at path with schema:
```yaml
tasks:
  - id: search_simple
    prompt: "Help me search for X"
    should_activate: true
  - id: decoy_generic
    prompt: "Just say hello"
    should_activate: false
```
**When** `load_skill_discoverability_tasks(path)` is called,
**Then** it returns `list[SkillDiscoverabilityTask]` with frozen dataclass instances having:
- `id: str` — unique task identifier
- `prompt: str` — natural-language prompt for the agent
- `should_activate: bool` — whether the target skill SHOULD activate for this prompt

**And** the loader raises `InvalidSkillDiscoverabilityTasksError` with RFC 6901 `field_name` for:
- File not found / wrong extension / unreadable
- Malformed YAML
- Missing `tasks:` key / empty task list
- Per-task missing `id` or `prompt`
- Per-task `should_activate` missing or not bool
- Duplicate `id` values across tasks

### AC-7.2.2 — `SkillTaskResult` + `SkillDiscoverabilityTaskSummary` + `SkillDiscoverabilityResult` dataclasses

**Given** Story 7.2 ships extensions to `src/AgentEval/skills/types.py`,
**When** a caller imports from `AgentEval.skills.types`,
**Then** they get frozen dataclasses:

`SkillTaskResult(frozen=True)`:
- `task_id: str`
- `task_prompt: str`
- `should_activate: bool`
- `trials_run: int`
- `activations_observed: int`
- `pass_at_k: float` — Phase-1: simple activation rate (`activations_observed / trials_run`, 0.0 if trials_run=0); Phase-2: Wilson CI lower bound per Story 6.3 stats (DF-7.2-S3 / C58)
- `competing_skills_picked: dict[str, int]` — Phase-1 always `{}` (D-3)
- `cost_per_trial_usd: float`

`SkillDiscoverabilityTaskSummary(frozen=True)`:
- `activation_accuracy: float` — correct activations / total trials across all tasks
- `false_activation_rate: float` — activated when `should_activate=False` / total decoy trials
- `missed_activation_rate: float` — NOT activated when `should_activate=True` / total should-activate trials
- `total_cost_usd: float`
- `total_runtime_seconds: float`

`SkillDiscoverabilityResult(frozen=True)`:
- `per_task_results: tuple[SkillTaskResult, ...]` — one entry per task in YAML order
- `summary: SkillDiscoverabilityTaskSummary`
- `adapter_coverage: str` — Phase-1 always `"in_process"` (D-2 fix; no `mcp_coverage`)

All three are `@dataclass(frozen=True)` per the project pattern.

### AC-7.2.3 — `SkillDidNotActivateError` in `errors.py`

**Given** `Skill Should Activate For` runs and the skill does NOT activate,
**When** `SkillDidNotActivateError` is raised,
**Then** it is a leaf under `AgentEvalIntegrityError` with:
- `error_code = "SKILL_DID_NOT_ACTIVATE"` (ClassVar[str])
- Structured attrs: `prompt: str`, `skill_path: str`, `skill_name: str`, `competing_skill: str | None`, `reasoning: str | None`, `fix_suggestion: str`
- `__str__` format:
  ```
  SKILL_DID_NOT_ACTIVATE: Skill '<name>' did not activate for prompt.
    Prompt: <prompt>
    Skill: <path> (name: <name>)
    Competing: <competing_skill or 'none detected'>
    Reasoning: <reasoning or 'N/A'>
    Fix: <fix_suggestion>
  ```
- Added to `errors.__all__`

### AC-7.2.4 — `Skill.Get Discoverability` keyword on `SkillsLibrary` — Tier-3 + `@guarded_fanout()`

**Given** `Library    AgentEval.skills.library    WITH NAME    Skill` loaded,
**When** caller invokes:
```
${result}=    Skill.Get Discoverability
...    skill=tests/fixtures/skills/example-search.md
...    tasks=tests/fixtures/discoverability/skill-tasks-basic.yaml
...    adapter=generic
...    trials_per_task=3
...    max_cost_usd=5.00
```
**Then** the variable receives a `SkillDiscoverabilityResult` instance.

**And** the keyword is decorated `@keyword(name="Get Discoverability") @tier(3) @guarded_fanout()`,
with `get_keyword_tier(lib.get_discoverability) == 3`.

**And** docstring contains `[Tier 3 — Stochastic Fan-Out]` badge (D-1 fix).

**And** the Phase-1 implementation:
1. Loads + validates skill file → extracts `skill_name` (null/empty → all activations False, no error)
2. Loads + validates tasks YAML via `load_skill_discoverability_tasks()`
3. For each task × `trials_per_task` trials: calls adapter once with `task.prompt`; infers `activated` via case-insensitive substring match (same heuristic as Story 7.1)
4. Aggregates per-task: `activations_observed`, `pass_at_k` (Phase-1: simple rate `activations/trials`; Phase-2: Wilson CI — DF-7.2-S3/C58), `cost_per_trial_usd`
5. Aggregates summary: `activation_accuracy`, `false_activation_rate`, `missed_activation_rate`, `total_cost_usd`, `total_runtime_seconds`
6. `adapter_coverage = "in_process"` (Phase-1 constant — D-2)
7. `competing_skills_picked = {}` for every task (Phase-1 constant — D-3)

**And** `model=` kwarg (optional) is forwarded to adapter constructor (same pattern as Story 7.1).

### AC-7.2.5 — `Skill Should Activate For` assertion keyword — Tier-2

**Given** `Library    AgentEval.skills.library    WITH NAME    Skill` loaded,
**When** caller invokes:
```
Skill.Should Activate For
...    prompt=Help me search for X
...    skill=tests/fixtures/skills/example-search.md
...    adapter=generic
...    model=anthropic/claude-sonnet-4-6
```
**And** the agent response contains the skill name,
**Then** the assertion passes (returns `None`).

**And Given** the agent does NOT activate the skill,
**Then** `SkillDidNotActivateError` is raised with all 5 fields populated.

**And** the keyword is decorated `@keyword(name="Should Activate For") @tier(2)`,
with `get_keyword_tier(lib.should_activate_for) == 2`.

**And** docstring contains `[Tier 2 — Stochastic Single-Shot]` badge.

**Note:** `Skill Should Activate For` is **NOT** `@guarded_fanout()` — it is a single-shot Tier-2 assertion. No budget guardrail. Uses `polling: float | None = None` for explicit FR28 polling-ban enforcement (identical to Story 7.1 pattern).

### AC-7.2.6 — `polling=` raises `PollingDisallowedError` on both keywords (FR28)

**Given** either `Skill.Get Discoverability` or `Skill.Should Activate For` called with `polling=1.0`,
**When** the call is made,
**Then** `PollingDisallowedError` is raised BEFORE any adapter call.

### AC-7.2.7 — `SkillDidNotActivateError` carries 5 fields per FR4d spec

**Given** `Skill Should Activate For` raises `SkillDidNotActivateError`,
**Then** the instance has:
- `prompt` = verbatim prompt passed to keyword
- `skill_path` = str(skill) passed to keyword
- `skill_name` = parsed from frontmatter (or `""` if null/missing)
- `competing_skill = None` (Phase-1 — competing skill detection deferred to Phase-2 with Phase-1 always `None`)
- `reasoning` = full adapter `response_text` (or `None` if not available)
- `fix_suggestion` = "Rephrase prompt to match the skill description, or revise the skill description to better match this prompt pattern."

### AC-7.2.8 — Fixtures: `example-search.md` + `skill-tasks-basic.yaml`

**Given** Story 7.2 ships:
- `tests/fixtures/skills/example-search.md` — a valid skill fixture with `name: example-search-skill`, `description: Search for information across the web and knowledge base.`, `allowed-tools: [web_search, knowledge_base_search]`, `disable-model-invocation: false`
- `tests/fixtures/discoverability/skill-tasks-basic.yaml` — ≥3 should_activate=true tasks + ≥2 should_activate=false tasks (decoys)

**Then** both are valid and pass their respective parsers.

### AC-7.2.9 — `InvalidSkillDiscoverabilityTasksError` in `errors.py`

**Given** a new error leaf for skill-discoverability YAML validation failures,
**Then** `InvalidSkillDiscoverabilityTasksError(_FR59Tier1SetupFailureError)` is added with `error_code = "INVALID_SKILL_DISCOVERABILITY_TASKS"` and added to `errors.__all__`.

### AC-7.2.10 — ≥12 unit tests in `tests/unit/skills/test_discoverability.py`

**Given** Story 7.2's test suite,
**Then** ≥12 unit tests covering:
1. `SkillTaskResult` frozen dataclass shape
2. `SkillDiscoverabilityResult` frozen dataclass shape
3. `get_discoverability` returns `SkillDiscoverabilityResult` instance
4. `get_discoverability` has tier-3 annotation
5. `activations_observed` correct count when stub response contains skill name
6. `activations_observed` correct count when stub response does NOT contain skill name
7. `should_activate_for` passes when skill activates
8. `should_activate_for` has tier-2 annotation
9. `should_activate_for` raises `SkillDidNotActivateError` when skill does not activate
10. `SkillDidNotActivateError` carries `prompt` + `skill_name` + `reasoning`
11. `polling=` raises `PollingDisallowedError` on `get_discoverability`
12. `polling=` raises `PollingDisallowedError` on `should_activate_for`
13. `InvalidSkillDiscoverabilityTasksError` raised for missing `should_activate` field
14. `load_skill_discoverability_tasks` returns correct `SkillDiscoverabilityTask` list

### AC-7.2.11 — Carry-over catalog gate (UPSTREAM, Epic 5 retro norm)

**Given** Story 7.2 ships before invoking code-review,
**When** grep for new `DF-7.2-S*` entries in new files,
**Then** each is catalogued in `deferred-work.md` + `docs/phase-1-5-carry-overs.md`:
- DF-7.2-S1 (D-3): `competing_skills_picked` always `{}` — Phase-2 need structured response schema or classifier to detect competing skill name
- DF-7.2-S2: `adapter_coverage` Phase-1 constant `"in_process"` — Phase-2 should detect real adapter coverage state

## Dev Notes

### Architecture + Existing Patterns

**Key pattern: follow Story 4.4 (`discoverability/`) for skill discoverability**

Story 4.4 at `src/AgentEval/discoverability/` is the direct parallel:
- `schema.py` → `DiscoverabilityTask`, `TaskResult`, `DiscoverabilitySummary`, `DiscoverabilityResult`
- `loader.py` → `load_discoverability_tasks(path)` → `list[DiscoverabilityTask]`
- `library.py` → `get_tool_discoverability()` @tier(3) @guarded_fanout()

Story 7.2 replicates this pattern in `src/AgentEval/skills/`:
- `_internal.py` (NEW) → `SkillDiscoverabilityTask` + `load_skill_discoverability_tasks()`
- `types.py` (EXTEND) → `SkillTaskResult` + `SkillDiscoverabilityTaskSummary` + `SkillDiscoverabilityResult`
- `library.py` (EXTEND) → `get_discoverability()` @tier(3) + `should_activate_for()` @tier(2)
- `errors.py` (EXTEND) → `SkillDidNotActivateError` + `InvalidSkillDiscoverabilityTasksError`

**Why `_internal.py` not `_loader.py`?** Parallel to how `stats/_internal.py` holds internal helpers for the stats sub-library. Skill-specific internals (task type + loader) are not part of the public `types.py` surface.

### Types Design

**`SkillDiscoverabilityTask` in `skills/_internal.py`:**
```python
@dataclass(frozen=True)
class SkillDiscoverabilityTask:
    id: str
    prompt: str
    should_activate: bool
```

**`SkillTaskResult` in `skills/types.py`:**
```python
@dataclass(frozen=True)
class SkillTaskResult:
    task_id: str
    task_prompt: str
    should_activate: bool
    trials_run: int
    activations_observed: int
    pass_at_k: float
    competing_skills_picked: dict[str, int]  # Phase-1 always {}
    cost_per_trial_usd: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "competing_skills_picked", dict(self.competing_skills_picked))
```

**`SkillDiscoverabilityTaskSummary` in `skills/types.py`:**
```python
@dataclass(frozen=True)
class SkillDiscoverabilityTaskSummary:
    activation_accuracy: float
    false_activation_rate: float
    missed_activation_rate: float
    total_cost_usd: float
    total_runtime_seconds: float
```

**`SkillDiscoverabilityResult` in `skills/types.py`:**
```python
@dataclass(frozen=True)
class SkillDiscoverabilityResult:
    per_task_results: tuple[SkillTaskResult, ...]
    summary: SkillDiscoverabilityTaskSummary
    adapter_coverage: str  # Phase-1: always "in_process"; NOT mcp_coverage (D-2)

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))
```

### `get_discoverability` implementation sketch

```python
@keyword(name="Get Discoverability")
@tier(3)
@guarded_fanout()
def get_discoverability(
    self,
    skill: str | Path,
    tasks: str | Path,
    adapter: str = "generic",
    model: str | None = None,
    trials_per_task: int = 3,
    polling: float | None = None,
    **kwargs: Any,
) -> SkillDiscoverabilityResult:
    """[Tier 3 — Stochastic Fan-Out]..."""
    if polling is not None:
        raise PollingDisallowedError(build_polling_disallowed_message("Get Discoverability", {...}))
    fm = parse_frontmatter(skill)
    name_raw = fm.get("name")
    skill_name = name_raw if isinstance(name_raw, str) else ""
    skill_tasks = load_skill_discoverability_tasks(tasks)
    adapter_cls = get_adapter(adapter)
    ctor_kwargs: dict[str, Any] = dict(kwargs)
    if model is not None:
        ctor_kwargs["model"] = model
    
    import time
    t_start = time.perf_counter()
    task_results = []
    for task in skill_tasks:
        activations = 0
        trial_costs = []
        for _ in range(trials_per_task):
            adapter_instance = adapter_cls(**ctor_kwargs)
            result = adapter_instance.run(task.prompt)
            activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
            if activated:
                activations += 1
            trial_costs.append(result.cost_usd)
        pass_at_k = _wilson_ci_point(activations, trials_per_task)
        cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
        task_results.append(SkillTaskResult(
            task_id=task.id,
            task_prompt=task.prompt,
            should_activate=task.should_activate,
            trials_run=trials_per_task,
            activations_observed=activations,
            pass_at_k=pass_at_k,
            competing_skills_picked={},  # D-3: Phase-1 always empty
            cost_per_trial_usd=cost_per_trial,
        ))
    total_runtime = time.perf_counter() - t_start
    summary = _build_summary(task_results, total_runtime)
    return SkillDiscoverabilityResult(
        per_task_results=tuple(task_results),
        summary=summary,
        adapter_coverage="in_process",
    )
```

**Wilson CI point estimate**: reuse `_wilson_lower_bound` from `stats/_internal.py` (which already implements Story 6.3's Wilson CI). Import it to avoid duplication.

```python
from AgentEval.stats._internal import _wilson_lower_bound  # use lower bound as pass_at_k

# Actually, pass_at_k should be the mid-point estimate, not just the lower bound.
# Use (lower + upper) / 2 or just successes/trials as Phase-1.
# For Phase-1 simplicity: pass_at_k = activations / trials if trials > 0 else 0.0
```

Wait — let me check how Story 4.4 computed `pass_at_k` for `TaskResult`. It used Wilson CI. For Phase-1 simplicity and consistency, let me use `activations / trials_per_task` (simple rate). If trials_per_task > 0. For Phase-2, Wilson CI can be the upgrade path.

Actually, looking at the epic AC: "pass_at_k (Wilson CI per HumanEval estimator)". This matches Story 6.3's `_wilson_lower_bound`. Let me use `_wilson_lower_bound(activations, trials_per_task)` from the stats module.

**`_build_summary` helper:**
```python
def _build_summary(task_results: list[SkillTaskResult], total_runtime: float) -> SkillDiscoverabilityTaskSummary:
    should_activate_trials = [(r.activations_observed, r.trials_run) for r in task_results if r.should_activate]
    decoy_trials = [(r.activations_observed, r.trials_run) for r in task_results if not r.should_activate]
    
    total_correct = sum(
        obs if sh else (tr - obs)
        for r in task_results
        for obs, tr, sh in [(r.activations_observed, r.trials_run, r.should_activate)]
    )
    total_trials = sum(r.trials_run for r in task_results)
    activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0
    
    false_act_total = sum(obs for obs, tr in decoy_trials)
    false_act_denom = sum(tr for obs, tr in decoy_trials)
    false_activation_rate = false_act_total / false_act_denom if false_act_denom > 0 else 0.0
    
    missed_total = sum(tr - obs for obs, tr in should_activate_trials)
    missed_denom = sum(tr for obs, tr in should_activate_trials)
    missed_activation_rate = missed_total / missed_denom if missed_denom > 0 else 0.0
    
    total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)
    
    return SkillDiscoverabilityTaskSummary(
        activation_accuracy=activation_accuracy,
        false_activation_rate=false_activation_rate,
        missed_activation_rate=missed_activation_rate,
        total_cost_usd=total_cost,
        total_runtime_seconds=total_runtime,
    )
```

### `should_activate_for` implementation sketch

```python
@keyword(name="Should Activate For")
@tier(2)
def should_activate_for(
    self,
    prompt: str,
    skill: str | Path,
    adapter: str = "generic",
    model: str | None = None,
    polling: float | None = None,
    **kwargs: Any,
) -> None:
    """[Tier 2 — Stochastic Single-Shot]..."""
    if polling is not None:
        raise PollingDisallowedError(build_polling_disallowed_message("Should Activate For", {...}))
    fm = parse_frontmatter(skill)
    name_raw = fm.get("name")
    skill_name = name_raw if isinstance(name_raw, str) else ""
    adapter_cls = get_adapter(adapter)
    ctor_kwargs: dict[str, Any] = dict(kwargs)
    if model is not None:
        ctor_kwargs["model"] = model
    adapter_instance = adapter_cls(**ctor_kwargs)
    result = adapter_instance.run(prompt)
    activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
    if not activated:
        raise SkillDidNotActivateError(
            f"Skill '{skill_name}' did not activate for prompt.",
            prompt=prompt,
            skill_path=str(skill),
            skill_name=skill_name,
            competing_skill=None,
            reasoning=result.response_text,
            fix_suggestion=(
                "Rephrase prompt to match the skill description, or revise the skill "
                "description to better match this prompt pattern."
            ),
        )
```

### `SkillDidNotActivateError` design

This is a leaf under `AgentEvalIntegrityError`. It is NOT a Tier-1 setup failure (it's a Tier-2 runtime assertion failure), so it does NOT use `_FR59Tier1SetupFailureError`. Custom `__init__` + `__str__`:

```python
class SkillDidNotActivateError(AgentEvalIntegrityError):
    error_code: ClassVar[str] = "SKILL_DID_NOT_ACTIVATE"
    
    def __init__(
        self,
        message: str,
        *,
        prompt: str,
        skill_path: str,
        skill_name: str,
        competing_skill: str | None = None,
        reasoning: str | None = None,
        fix_suggestion: str = "",
    ) -> None:
        super().__init__(message)
        self.prompt = prompt
        self.skill_path = skill_path
        self.skill_name = skill_name
        self.competing_skill = competing_skill
        self.reasoning = reasoning
        self.fix_suggestion = fix_suggestion
    
    def __str__(self) -> str:
        message = Exception.__str__(self)
        return (
            f"{self.error_code}: {message}\n"
            f"  Prompt: {self.prompt}\n"
            f"  Skill: {self.skill_path} (name: {self.skill_name or 'N/A'})\n"
            f"  Competing: {self.competing_skill or 'none detected'}\n"
            f"  Reasoning: {self.reasoning[:120] + '...' if self.reasoning and len(self.reasoning) > 120 else (self.reasoning or 'N/A')}\n"
            f"  Fix: {self.fix_suggestion or 'N/A'}"
        )
```

### `InvalidSkillDiscoverabilityTasksError` design

This IS a Tier-1 setup failure (parsing a config file before LLM call). Inherits `_FR59Tier1SetupFailureError`:

```python
class InvalidSkillDiscoverabilityTasksError(_FR59Tier1SetupFailureError):
    error_code: ClassVar[str] = "INVALID_SKILL_DISCOVERABILITY_TASKS"
```

### Critical: `_internal.py` loader pattern (follow `discoverability/loader.py` exactly)

The loader should validate:
1. File exists + readable + UTF-8
2. Extension `.yaml` / `.yml`
3. `yaml.safe_load()` succeeds; result is a dict
4. `tasks:` key exists and is a non-empty list
5. Each task has `id: str`, `prompt: str`, `should_activate: bool`
6. No duplicate `id` values (raise with `field_name="/tasks"`)

Raise `InvalidSkillDiscoverabilityTasksError` at every failure point with `file_path`, `field_name` (RFC 6901 pointer), `fix_suggestion`.

### Test stub pattern

Follow Story 7.1's stub pattern exactly (InProcessAdapter subclass):
```python
def _make_stub(response_text: str, cost: float = 0.001, latency: float = 0.002) -> type[InProcessAdapter]:
    class _Stub(InProcessAdapter):
        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=latency,
                trace_id="a" * 32,
            )
    return _Stub
```

Register unique names: `register_adapter("stub_disc_NNN", StubClass)`.

### Wilson CI import

`stats/_internal.py` exports `_wilson_lower_bound(successes: int, n: int) -> float`. For `pass_at_k` in Phase-1, use `activations_observed / trials_run` (simple rate) if `trials_run > 0` else `0.0`. This avoids importing from stats (cross-module dep within AgentEval) for Phase-1 simplicity. Document as Phase-1 simplification — Phase-2 can wire the Wilson CI.

Actually, re-reading AC-7.2.2: `pass_at_k: float — Wilson CI per HumanEval estimator`. Let me check whether `stats._internal` exports this. The module is internal (`_internal.py`). Importing across sub-packages (`skills` importing from `stats`) creates a coupling that's hard to manage. For Phase-1: use `k / n if n > 0 else 0.0`. File the divergence as DF-7.2-S3 if needed. Actually — Phase-1 "Wilson CI per HumanEval estimator" likely means the `_wilson_lower_bound` from Story 6.3. Let me just implement it inline or import it.

Safest: import `_wilson_lower_bound` from `AgentEval.stats._internal` directly (it already exists, and stories can import from each other's internals). If convention tests catch it, file DF-7.2-S3.

Use the Wilson lower bound as `pass_at_k`: `pass_at_k = _wilson_lower_bound(activations, trials_per_task)`. This is the conservative estimate.

### `tests/fixtures/skills/example-search.md` content

```markdown
---
name: example-search-skill
description: Search for information across the web and knowledge base.
allowed-tools:
  - web_search
  - knowledge_base_search
disable-model-invocation: false
---

# Search Skill

A skill for performing web and knowledge base searches.
Use this skill when the user needs to find information from external sources.
```

### `tests/fixtures/discoverability/skill-tasks-basic.yaml` content

```yaml
# Skill discoverability tasks fixture for Story 7.2 unit tests.
# Tests the example-search-skill.
tasks:
  - id: search_simple
    prompt: "Help me search for information about Python performance."
    should_activate: true
  - id: search_knowledge_base
    prompt: "Look up the latest research on neural networks in your knowledge base."
    should_activate: true
  - id: search_web_query
    prompt: "Search the web for recent news about AI developments."
    should_activate: true
  - id: decoy_greeting
    prompt: "Hello, how are you doing today?"
    should_activate: false
  - id: decoy_calculation
    prompt: "What is 42 multiplied by 17?"
    should_activate: false
```

### Carry-over catalog entries to create (UPSTREAM gate)

Before invoking code-review:
- **DF-7.2-S1 / C56**: `competing_skills_picked` Phase-1 always `{}` — Phase-2 structured response schema for competing skill detection
- **DF-7.2-S2 / C57**: `adapter_coverage` Phase-1 always `"in_process"` — Phase-2 detect real adapter state

### Fake-green precheck (dogfood fake-green precheck norm, Epic 5 retro)

Before flipping to code-review:
1. All `test_discoverability.py` tests actually CALL the keyword (not just import it)
2. Assertion tests verify the actual assertion body matches the test name's promise
3. No placeholder stub patterns where the stub response matches every test indiscriminately

### Caller-count check (Epic 5 retro norm)

`SkillDiscoverabilityTask` is used by `load_skill_discoverability_tasks()` (1 caller) and `get_discoverability()` (1 caller via loader) = 2 callers ✓
`SkillTaskResult` is used by `get_discoverability()` (1 caller) and test stubs (1+ callers) = 2+ callers ✓
`SkillDiscoverabilityResult` is used by `get_discoverability()` + tests = 2+ callers ✓
`SkillDidNotActivateError` is used by `should_activate_for()` + tests = 2+ callers ✓

## Tasks/Subtasks

- [x] **Task 1: Add `InvalidSkillDiscoverabilityTasksError` + `SkillDidNotActivateError` to `errors.py`**
  - [x] 1.1 Add `InvalidSkillDiscoverabilityTasksError(_FR59Tier1SetupFailureError)` with `error_code = "INVALID_SKILL_DISCOVERABILITY_TASKS"` + add to `__all__`
  - [x] 1.2 Add `SkillDidNotActivateError(AgentEvalIntegrityError)` with 6 structured attrs + custom `__str__` + `error_code = "SKILL_DID_NOT_ACTIVATE"` + add to `__all__`

- [x] **Task 2: Create `src/AgentEval/skills/_internal.py`** — `SkillDiscoverabilityTask` + `load_skill_discoverability_tasks()`
  - [x] 2.1 `SkillDiscoverabilityTask` frozen dataclass with `id`, `prompt`, `should_activate`
  - [x] 2.2 `load_skill_discoverability_tasks(path)` → `list[SkillDiscoverabilityTask]` with full validation + `InvalidSkillDiscoverabilityTasksError` raises

- [x] **Task 3: Extend `src/AgentEval/skills/types.py`** — 3 new frozen dataclasses
  - [x] 3.1 `SkillTaskResult` with 8 fields + `__post_init__` for `competing_skills_picked` defensive copy
  - [x] 3.2 `SkillDiscoverabilityTaskSummary` with 5 fields
  - [x] 3.3 `SkillDiscoverabilityResult` with 3 fields + `__post_init__` for `per_task_results` tuple conversion

- [x] **Task 4: Create test fixtures**
  - [x] 4.1 `tests/fixtures/skills/example-search.md` — valid skill with name `example-search-skill`
  - [x] 4.2 `tests/fixtures/discoverability/skill-tasks-basic.yaml` — 3 should_activate=true + 2 should_activate=false

- [x] **Task 5: Extend `src/AgentEval/skills/library.py`** — 2 new keywords
  - [x] 5.1 `get_discoverability()` @keyword @tier(3) @guarded_fanout() with Phase-1 implementation (per-task per-trial loop + summary + adapter_coverage + competing_skills_picked={})
  - [x] 5.2 `should_activate_for()` @keyword @tier(2) with SkillDidNotActivateError raise site

- [x] **Task 6: Write `tests/unit/skills/test_discoverability.py`** — ≥14 tests (RED → GREEN)
  - [x] 6.1 Write all tests FIRST (RED phase)
  - [x] 6.2 Verify tests fail appropriately against skeleton
  - [x] 6.3 Run tests after implementation (GREEN phase)

- [x] **Task 7: Carry-over catalog gate (UPSTREAM)**
  - [x] 7.1 Grep for `DF-7.2-S` in new files; add to `deferred-work.md` + `docs/phase-1-5-carry-overs.md`

- [x] **Task 8: Full test suite + all-gates validation**
  - [x] 8.1 `uv run pytest tests/unit/skills/test_discoverability.py -v`
  - [x] 8.2 `uv run pytest tests/ -x -q` — no regressions
  - [x] 8.3 `uv run ruff check src/ tests/` — clean
  - [x] 8.4 `uv run ruff format --check src/ tests/` — clean
  - [x] 8.5 `uv run mypy src/` — clean

- [x] **Task 9: Fake-green precheck (dogfood norm)**
  - [x] 9.1 Verify all tests have non-trivial assertions (test name promise delivered)
  - [x] 9.2 Verify `should_activate_for` failure test actually checks `SkillDidNotActivateError` not just `Exception`

## Dev Agent Record

### Debug Log

- Convention test `test_no_unauthorized_sub_library_should_keywords` failed: `Should Activate For` not in carve-out registry. Fixed: added `("SkillsLibrary", "Should Activate For")` to `_PHASE_1_SHOULD_CARVE_OUTS` + `architecture.md` L838 carve-out registry per the test's enforcement contract.
- Ruff `I001` import-sort: `import time` placed after third-party imports in `library.py`. Fixed: moved to stdlib section.
- Ruff `E501` line too long in `_internal.py` L182. Fixed: extracted `got = type(should_activate).__name__` to intermediate variable.

### Completion Notes

**Implemented Story 7.2 fully:**

- **4 new source files**: `src/AgentEval/skills/_internal.py` (SkillDiscoverabilityTask + loader), `tests/fixtures/skills/example-search.md`, `tests/fixtures/discoverability/skill-tasks-basic.yaml`, `tests/unit/skills/test_discoverability.py` (15 tests)
- **3 modified source files**: `src/AgentEval/skills/types.py` (+3 dataclasses), `src/AgentEval/skills/library.py` (+2 keywords + 1 helper), `src/AgentEval/errors.py` (+2 error classes)
- **2 carry-over catalog entries**: DF-7.2-S1 (C56 competing_skills_picked) + DF-7.2-S2 (C57 adapter_coverage Phase-1 constant)
- **Pre-create drift D-1 fixed**: `Should Activate For` = Tier-2 (not Tier-3); `Get Discoverability` docstring uses `[Tier 3 — Stochastic Fan-Out]`
- **Pre-create drift D-2 fixed**: `adapter_coverage` field (not `mcp_coverage`) on `SkillDiscoverabilityResult`
- **Pre-create drift D-3**: `competing_skills_picked = {}` Phase-1 constant; DF-7.2-S1/C56
- **Pre-create drift D-4 fixed**: `should_activate: bool` field in task YAML + `InvalidSkillDiscoverabilityTasksError` leaf
- **15/15 unit tests pass**; 1253/1261 (excluding 8 skipped) full suite passes; ruff/mypy/format clean

## File List

### New Files
- `src/AgentEval/skills/_internal.py`
- `tests/fixtures/skills/example-search.md`
- `tests/fixtures/discoverability/skill-tasks-basic.yaml`
- `tests/unit/skills/test_discoverability.py`

### Modified Files
- `src/AgentEval/skills/types.py`
- `src/AgentEval/skills/library.py`
- `src/AgentEval/errors.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `docs/phase-1-5-carry-overs.md`

## Change Log

- 2026-05-21: Story created (32nd consecutive pre-create drift check; 4 drifts resolved pre-authoring)
- 2026-05-21: Implementation complete; 15 tests pass; all gates clean; carry-over catalog updated (C56+C57); status → review
- 2026-05-21: Code review complete (Codex + Claude Blind Hunter + Auditor); 5 MED + 3 LOW applied; 5 new tests (20 total); DF-7.2-S3/C58 catalogued (pass_at_k Wilson CI deferral); AC-7.2.2 amended; status → done
