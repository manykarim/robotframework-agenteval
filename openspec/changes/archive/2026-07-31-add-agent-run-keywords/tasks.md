## 1. Shared run-exception classifier (`src/AgentEval/_core/`)

- [x] 1.1 Add `_core/run_classifier.py` with `classify_run_exception(exc) -> Literal["budget_exceeded","provider_error","timeout"] | None`. Lazily import `pydantic_ai.exceptions`, `openai`, `litellm`, and `subprocess` INSIDE the function (no module-scope third-party import — dependency direction).
- [x] 1.2 In-process branch: `UsageLimitExceeded` → `budget_exceeded`; check `ModelHTTPError` BEFORE `ModelAPIError` (it subclasses it) and branch on `.status_code` (retryable {408,409,429,500,502,503,504} → `provider_error`; else → `None`/raise); `ModelAPIError` → `provider_error`; `UnexpectedModelBehavior` → `provider_error` only if message contains `"Invalid response from"`, else `None`.
- [x] 1.3 Generic branch: `isinstance` against litellm/openai transient bases (`RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`; `APIStatusError` retryable-status) → `provider_error`. Pin the exact tuple against the installed wheels.
- [x] 1.4 CLI branch: `AdapterError` whose `__cause__` is `subprocess.TimeoutExpired` → `timeout`. Everything else (binary-missing `AdapterError`, `MissingExtraError`, `TierViolationError`, unknown) → `None` (caller raises).

## 2. New `AgentLibrary` + two keywords (`src/AgentLibrary/`)

- [x] 2.1 Create `src/AgentLibrary/__init__.py` (DynamicCore `@library`, prefix `Agent.`, Apache header, module docstring in the RF voice).
- [x] 2.2 `@keyword(name="Agent.Get Adapter") @tier(1)` `get_adapter(self, adapter="generic", **config)`: coerce scalar `toolsets=`/`capabilities=` to a 1-element list; strip `None`-valued explicit params; forward to `AgentEval.get_adapter(adapter, **config)`; return the adapter. Runnable pipe-table Example.
- [x] 2.3 `@keyword(name="Agent.Run Agent") @tier(3)` `run_agent(self, adapter, prompt, skip_on="", **run_kwargs)`: call `enforce_no_model()` first; resolve slug-or-object via `AgentEval.get_adapter`; `try adapter.run(prompt, **run_kwargs)`; on exception classify → if category in `skip_on` set → `BuiltIn().skip(...)`; `budget_exceeded` not skipped → raise `BudgetExceededError` from exc; unlisted transient → re-raise; `None` → re-raise. Never fabricate a result. Runnable Example.

## 3. Public entrypoint + doc sweep

- [x] 3.1 `src/AgentEval/__init__.py`: re-export `get_adapter` and `Adapter` from `_core.adapter`; add both to `__all__`. Confirm `import AgentEval` still loads with litellm/pydantic_ai absent from `sys.modules`.
- [x] 3.2 Sweep prose/examples off both `_core` spellings (`AgentEval._core.adapter.get_adapter` and `AgentEval._core.get_adapter`) onto `AgentEval.get_adapter` / the `Agent.*` keywords: `grep -rn` README.md, docs/**, and library docstrings. EXCLUDE functional internal imports (e.g. `MCPLibrary/_discoverability.py`, `SkillsLibrary/_internal.py`) — those keep their `_core` import.
- [x] 3.3 Regenerate the affected keyword-doc HTML after docstring edits (`python -m robot.libdoc`).

## 4. Packaging + count gate + stability contract

- [x] 4.1 `pyproject.toml`: add `src/AgentLibrary` to BOTH `[tool.hatch.build.targets.wheel].packages` AND `[tool.hatch.build.targets.sdist].include`.
- [x] 4.2 `scripts/check_doc_keyword_count.py`: `_LIBRARY_COUNT` 6 → 7; add `"AgentLibrary"` to `_COUNTED_LIBRARIES`; fix any stale `_SUB_LIBRARIES`/composite docstring the gate relies on.
- [x] 4.3 Update the keyword total 65 → 67 and libraries 6 → 7 in `README.md` and `docs/index.md` (totals + a new AgentLibrary section/row + its 2-keyword table). Add the AgentLibrary keyword docs.
- [x] 4.4 `docs/contracts/stability-surface.md`: register AgentLibrary (+ Metrics/Stat) `provisional`; add `AgentEval.get_adapter`/`Adapter` `provisional`; correct the stale per-library counts, the "42 keywords across 4 libraries" line, and the superseded "CLI adapters SHALL NOT be shipped" note. Keep the contract-sections gate green.

## 5. Tests

- [x] 5.1 `tests/` classifier unit tests: `ModelHTTPError(401)` → None(raise) vs `(429)` → `provider_error`; `UsageLimitExceeded` → `budget_exceeded`; `ModelAPIError` → `provider_error`; `UnexpectedModelBehavior` with/without `"Invalid response from"`; a CLI `AdapterError` chained from `subprocess.TimeoutExpired` → `timeout` and a binary-missing `AdapterError` (`__cause__` None) → None; litellm `RateLimitError` → `provider_error`.
- [x] 5.2 `Agent.Get Adapter` / `Agent.Run Agent` unit tests with fake adapters: slug-or-object resolution; scalar→list coercion; `**run_kwargs` reach `adapter.run`; `skip_on` skips a classified category (assert `robot.api.SkipExecution`/skip), budget-not-skipped raises `BudgetExceededError`, config fault always raises, no fabricated result; `enforce_no_model` rejects a Tier-1 scope.
- [x] 5.3 Non-breaking test: the `Evaluate AgentEval._core.adapter.get_adapter(...)` path still resolves, and `AgentEval.get_adapter` returns the same adapter class.
- [x] 5.4 Clean-venv packaging smoke: build the wheel and `python -c "import AgentLibrary"` (or a one-keyword `robot --dryrun`) in a fresh env so a missing `pyproject` entry fails loud.

## 6. Close out

- [x] 6.1 Run the full local gate mirroring CI: `uv run ruff check src/ tests/` · `ruff format --check` · `mypy src/` · `check-license-headers` · `check-contract-sections` · `check_doc_keyword_count` (now 67/7) · `check-doc-rendering` · `check-keyword-examples` · `pytest tests/` · `robot tests/robot`. Fix at root cause.
- [x] 6.2 (evidence) Rewrite `rf-mcp/tests/agenteval/agentic_scenarios.robot` core to the 2-keyword form (`Agent.Get Adapter` + `Agent.Run Agent  ... skip_on=budget_exceeded,provider_error,timeout`) and confirm the ~12-line error block collapses — the change's motivating payoff.
- [ ] 6.3 `openspec validate add-agent-run-keywords --strict`, then archive after implementation lands and gates are green; confirm `agent-execution` + the `evaluation-core` delta absorb cleanly.
