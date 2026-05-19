# ADR-015: Cost + Runtime Guardrail as `@guarded_fanout` Decorator

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A5 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A5. Renumbered to ADR-015 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

The cost guardrail (FR11 / AC-DISCOVER-02) and runtime guardrail (FR11b / NFR-PERF-06) apply only to **Tier-3 fan-out keywords** — keywords that issue many provider calls per invocation (e.g., `Stat.Run N Times`, `MCP.Get Tool Discoverability`). They don't apply to kernel-level operations or single-call keywords.

Phase-1 Tier-3 fan-out keywords (3 known): `MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`. Phase 2 adds more (`Stat.Mann Whitney U` comparison flows, `Stat.Pass At K` runs). Without a shared mechanism, each fan-out keyword re-implements pre-flight estimation + mid-run metering, with high risk of divergent semantics: one keyword measures cost per-token, another per-request; one enforces wall-clock timeout, another enforces total-runtime budget.

## Decision

agenteval implements a single decorator at `src/AgentEval/_kernel/guardrails.py`:

```python
@guarded_fanout(estimator=callable)
def fanout_keyword(*args, **kwargs):
    ...
```

The decorator wraps any Tier-3 fan-out keyword. Decorator behavior:

1. **Pre-flight estimation** — calls the user-supplied `estimator(kwargs: dict) -> (cost_estimate_usd: float, runtime_estimate_seconds: float)` BEFORE entering the keyword body. If either estimate exceeds the configured budget (`AGENTEVAL_MAX_COST_USD`, `AGENTEVAL_MAX_RUNTIME_SECONDS`), the decorator raises `CostExceededError` or `RuntimeBudgetExceededError` without entering the keyword body.

2. **Mid-run cost meter** — starts a USD meter (per `agenteval.providers` registered provider's cost-tracking API). Polls every N seconds (configurable; default 5s) and re-checks against the budget. On breach, the decorator raises `CostExceededError` and triggers cooperative cancellation of in-flight provider calls.

3. **Mid-run wall-clock meter** — starts a wall-clock timer. Same polling cadence. On breach, raises `RuntimeBudgetExceededError`.

Both errors are leaves of `AgentEvalBudgetError` per ADR-014 → FR50 exit code 2.

The `estimator` callable signature is documented for community adapter authors who add custom fan-out keywords via `plugins=[...]` (FR48): `estimator(kwargs) -> (cost_usd, runtime_sec)`. The decorator handles meter setup/teardown; the keyword author just provides the estimator + the work.

## Consequences

- Single decorator in `src/AgentEval/_kernel/guardrails.py`; one source of truth for guardrail semantics across all Tier-3 fan-out keywords.
- Estimator interface documented in `docs/contributor-api.md`; community contributors who write custom fan-out keywords via `plugins=[...]` get the same guardrail pattern for free.
- Conformance suite (ADR-017) validates the decorator against a deterministic mock provider with known cost/runtime characteristics: estimator + meter + breach detection all tested.
- Cross-cutting concern #8 from the architecture's Project Context Analysis — selectively-applied shared pattern, NOT kernel-level mandatory.
- Default budgets are configured via env vars (`AGENTEVAL_MAX_COST_USD` defaults to 5.0; `AGENTEVAL_MAX_RUNTIME_SECONDS` defaults to None = unlimited) and can be overridden per-keyword via decorator argument.
- Cooperative cancellation hint: on budget breach, the meter sets a `threading.Event` exposed via the `_cancel_event_var` ContextVar (accessible from inside fan-out keyword bodies via `current_cancel_event()`). This works for both sync-frame and `_run_async`-fallback worker-thread frames thanks to Story 1b.1's `contextvars.copy_context()` propagation. Provider implementations that target asyncio Tasks (Story 4.1's LiteLLM streaming integration) layer `asyncio.CancelledError`-emitting cancellation on top of this Event; non-cooperative providers run to natural completion of the current call before the budget error surfaces. The pre-Story-1b.3-code-review wording mentioned only `asyncio.CancelledError thrown by the meter` — Codex's cross-LLM citation re-derivation caught that the shipped Phase-1 mechanism is the threading.Event ContextVar; amended here per the fix-the-losing-source norm.

## Alternatives

- **Per-keyword guardrail re-implementation** — rejected. Duplication; high risk of divergent semantics (one keyword measures cost per-token, another per-request). A user setting `AGENTEVAL_MAX_COST_USD=5.0` would observe different effective budgets depending on which fan-out keyword they hit.
- **Base-class `GuardedFanoutKeyword`** — rejected. RF keyword decoration is method-level (via `@keyword` from RF's DynamicLibrary API), not class-level; doesn't fit agenteval's `DynamicCore` composition model. A base class would force inheritance, which doesn't compose cleanly with the `@keyword` decoration step.
- **Kernel-level mandatory guardrails on all keywords** — rejected. Over-applies. Static-inspection keywords (e.g., `Skill.Get Activation Decision`) issue zero provider calls; gating them on cost/runtime budget adds runtime overhead with no benefit.
- **Runtime-only guardrail (no pre-flight estimation)** — rejected. Pre-flight rejection of obviously-over-budget calls saves real money and time. Mid-run-only enforcement still runs the first N% of the workload before the budget breach surfaces.

## References

- Architecture L429-434 (renumbering plan) + §Cross-Cutting Concerns
- FR11 + FR11b + AC-DISCOVER-02 + NFR-PERF-06 (PRD) — the functional + non-functional requirements this decorator serves
- ADR-014 (Error-Class Hierarchy) — `CostExceededError` + `RuntimeBudgetExceededError` are leaves of `AgentEvalBudgetError`
- ADR-017 (Conformance Suite Organization) — `test_ac_discover_02_cost_guardrail.py` tests this decorator's enforcement path
- `AGENTEVAL_MAX_COST_USD` + `AGENTEVAL_MAX_RUNTIME_SECONDS` env-var conventions (`.env.example` from Story 1a.1)
