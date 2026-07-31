## Why

To actually *run* an agent, every user — and the framework's own recipes — must
drop into `Evaluate AgentEval._core.adapter.get_adapter('in-process', ...)` and
`Evaluate $adapter.run(...)`. Two problems:

1. **No keyword returns a raw `AgentRunResult` or offers general-purpose
   construct-and-run.** Several keywords *do* run an adapter internally (e.g.
   `Skill.Get Activation Decision`, `Subagent.Get Delegation Decision`,
   `Skill.Get Discoverability`) — but only to compute a narrow domain result, never
   to hand back the run itself for measurement. So the one general path to "run
   this prompt and read the trace/metrics" is `Evaluate` + Python.
2. **The one documented path is the explicitly-unstable one.**
   `docs/contracts/stability-surface.md` declares everything under `_core/`
   *internal and not part of the stable surface*, yet the headline in-process
   feature is reachable only through `AgentEval._core.adapter.get_adapter(...)` —
   taught across README, recipes, `running-against-a-real-model.md`, and library
   docstrings. Users are told to depend on a path the contract says can break.

The cost shows up in real dogfood suites. `rf-mcp`'s `agentic_scenarios.robot`
carries a **12-line** `Run Keyword And Ignore Error` + `IF FAIL` block that
**string-matches exception class names** (`UsageLimitExceeded`,
`UnexpectedModelBehavior`, `ModelHTTPError`, `RateLimit`, `ReadTimeout`, …) to skip
on budget/transient-provider errors but fail on real ones. That taxonomy is
AgentEval/pydantic-ai domain knowledge being copy-pasted — and fragilely — into a
user `.robot` file.

## What Changes

- **A new `AgentLibrary`** (namespace `Agent.`, Tier-3, gated behind the adapters'
  existing lazy `[agent]`/`[llm]` imports), with **two keywords** that span **all
  three adapter families** (in-process pydantic-ai, generic LiteLLM, and the six
  coding-agent CLI slugs) uniformly via the existing `Adapter` protocol:
  - `Agent.Get Adapter    adapter=generic    **config` → an `Adapter` object.
    RF-native construction config (`toolsets=`, `capabilities=`, `instructions=`,
    `request_limit=`, `model=`, `base_url=`, …); a scalar `toolsets=`/`capabilities=`
    is coerced to a one-element list. Accepts a slug **or** an already-built adapter
    object (pass-through, so a user's custom adapter works too).
  - `Agent.Run Agent    adapter    prompt    skip_on=    **run_kwargs` →
    `AgentRunResult`. `adapter` is a slug **or** object; `**run_kwargs` forward to
    `adapter.run()` (CLI `timeout=`/`cwd=`/`session_dir=`/`env=`; per-run overrides).
- **One shared, robust run-exception classifier** (in `_core`) — the single home
  for the transient/budget taxonomy, keyed on **structured signals**
  (`ModelHTTPError.status_code`, `__cause__` type, `isinstance`) not class-name
  strings. `Agent.Run Agent` uses it: a category listed in `skip_on`
  (`budget_exceeded` / `provider_error` / `timeout`) calls Robot's `Skip`; budget
  not listed re-raises as the existing `BudgetExceededError`; an unlisted transient
  re-raises the original; a **genuine config/auth fault always raises** (never
  skipped, never a fabricated result). `Agent.Run Agent` also calls
  `enforce_no_model()` so the Tier-3 gate is uniform across families.
- **A stable public entrypoint** `AgentEval.get_adapter` (+ the `Adapter` protocol)
  re-exported from the package top level, and a **sweep of the teaching sites** off
  the `_core` path onto it — resolving the stability-contract contradiction.
- **Reconcile `docs/contracts/stability-surface.md`** in the same change (register
  Metrics/Stat/Agent, correct the stale per-library counts and the superseded
  "no CLI adapters" note), since this change edits the library registry.

Purely additive: the `Evaluate`/`_core` path keeps working; every adapter
`run()`/`__init__` signature is frozen; no new provider or slug.

## Capabilities

### New Capabilities

- `agent-execution`: first-class keywords to construct an adapter and run a prompt
  through it (any of the three families), with a centralized transient/budget
  classifier and honest raise-or-skip semantics — no fabricated results.

### Modified Capabilities

- `evaluation-core`: ADD a requirement that the adapter seam is reachable through a
  **stable public entrypoint** (`AgentEval.get_adapter`), not only the internal
  `_core` path; and MODIFY the "one adapter seam" requirement to reflect the built-in
  in-process + coding-agent-CLI adapters shipped since (correcting the superseded
  "CLI adapters SHALL NOT be shipped" clause).

## Impact

- **New package** `src/AgentLibrary` (added to `pyproject` wheel + sdist lists).
  Keyword total **65 → 67**; **6 → 7** libraries — update
  `scripts/check_doc_keyword_count.py` (`_LIBRARY_COUNT`, `_COUNTED_LIBRARIES`),
  `README.md`, `docs/index.md`, and register the library in `stability-surface.md`.
- **New** `_core` classifier module (lazy-imports pydantic-ai/openai/litellm inside
  the function — dependency direction preserved).
- **`AgentEval/__init__.py`** gains the `get_adapter`/`Adapter` re-export.
- **Docs**: replace `AgentEval._core.adapter.get_adapter(...)` in prose/examples
  (both `_core` spellings) with `AgentEval.get_adapter` / the new keywords —
  leaving legitimate *functional* internal `_core` imports untouched.
- **Tests**: unit tests for the classifier (incl. `ModelHTTPError(401)` → raise vs
  `(429)` → provider_error; CLI timeout `__cause__` chain), `Get Adapter`/`Run
  Agent` across families with fakes, a clean-venv `import AgentLibrary` smoke, and a
  non-breaking check that the `Evaluate` path still resolves.
