## Context

Every path to *run* an agent goes through `Evaluate
AgentEval._core.adapter.get_adapter(...)` + `Evaluate $adapter.run(...)`. The three
adapter families already share one seam — `get_adapter(slug_or_object, **kwargs)`
returns anything satisfying the `Adapter` protocol (`name`; `run(prompt) ->
AgentRunResult`), and `get_adapter` already resolves a slug **or** a pass-through
object (`adapter.py:287-298`). What is missing is a **keyword** surface over that
seam, and a **stable public import** for it (the `_core` namespace is declared
non-public in `docs/contracts/stability-surface.md`).

This design was shaped by a 3-perspective design panel and a 3-lens adversarial
review, and grounded by probing the installed wheels (pydantic-ai 2.12.0, openai
2.46.0, litellm). Verified facts that drive the classifier:

- `pydantic_ai.exceptions`: `UsageLimitExceeded`, `ModelHTTPError(status_code,
  model_name, body)` — **carries `.status_code`** and **subclasses `ModelAPIError`**
  — `ModelAPIError(model_name, message)`, `UnexpectedModelBehavior`. All subclass
  `AgentRunError`. In the in-process family, openai/httpx errors do **not** reach
  the caller as their own types — pydantic-ai wraps them as `ModelHTTPError` /
  `ModelAPIError`.
- The generic (LiteLLM) family raises **litellm** exception types
  (`litellm.RateLimitError`, `litellm.Timeout`, …). `litellm.RateLimitError is not
  openai.RateLimitError` — litellm has its own classes (which subclass openai's), so
  the classifier keys on litellm/openai transient bases via `isinstance`, per family.
- The CLI family raises `AdapterError`; a **timeout** `AdapterError` chains from
  `subprocess.TimeoutExpired` via `from exc` (`cli_adapter.py:157`), so `__cause__`
  discriminates timeout from binary-missing with **no adapter change**.

Constraints: additive/non-breaking (frozen adapter signatures; the `Evaluate` path
keeps working); dependency direction (surface libs may import `_core`; `_core` must
not import a surface lib; pydantic-ai/litellm stay lazy behind `[agent]`/`[llm]`);
libdoc namespace keywords must be multi-word after the dot; honest framing.

## Goals / Non-Goals

**Goals:**

- Two keywords that construct and run an adapter of **any** family and return a raw
  `AgentRunResult`, replacing the `Evaluate`-into-`_core` boilerplate.
- One central, **robust** transient/budget classifier so a real dogfood suite drops
  its ~12-line exception-string-match block to a single `skip_on=` argument.
- A stable public `AgentEval.get_adapter` that ends the "docs teach an unstable
  path" contradiction.

**Non-Goals:**

- **No adapter-internal change**: `get_adapter`, `GenericAdapter`,
  `InProcessAgentAdapter`, `SubprocessCLIAdapter` and their `__init__`/`run()`
  signatures stay frozen. Classification lives entirely in the keyword/`_core`
  classifier layer; adapters raise exactly what they raise today.
- **No new adapter family, provider, or slug**; **no new error leaf** for provider
  errors (budget reuses the existing `BudgetExceededError`; provider/timeout
  re-raise the original).
- **No fabricated `AgentRunResult`** on failure (the fake-green hazard). A failed
  run either skips or raises.
- **Keep the `Evaluate`/`_core` path working** — purely additive; no removals.
- **No** scenario tool-call min/max bound assertions, multi-turn, or A/B — existing
  `MCP.*`/`Metric.*` readers own downstream assertions; the test author composes.
- **No** `run_status` field on `AgentRunResult` (see Decisions → Status model).

## Decisions

### D1 — Two keywords in a new `AgentLibrary` (`Agent.` prefix)

```
Agent.Get Adapter    adapter=generic    **config          -> Adapter        [Tier-1 construction]
Agent.Run Agent      adapter    prompt    skip_on=    **run_kwargs -> AgentRunResult  [Tier-3]
```

- `Agent.Get Adapter` forwards `**config` to `AgentEval.get_adapter(adapter,
  **config)`. `adapter` is a slug or a pass-through object. A scalar
  `toolsets=`/`capabilities=` is coerced to a one-element list so callers avoid
  `${{ [$x] }}`. Construction-time config (`toolsets`, `capabilities`,
  `instructions`, `request_limit`, `usage_limits`, `model`, `base_url`, `api_key`,
  litellm knobs) lives here. Tier-1 because construction touches no model and the
  heavy extras stay lazy until `run()`.
- `Agent.Run Agent` accepts a slug **or** an object; `**run_kwargs` forward verbatim
  to `adapter.run(prompt, **run_kwargs)` (CLI `timeout`/`cwd`/`session_dir`/`env`;
  per-run in-process/generic overrides). A bare slug gives the zero-config families
  (CLI, one-shot generic) a one-liner; in-process rich config (object-valued
  toolsets/capabilities) uses the two-step, because those objects belong at
  construction.
- *Why two and only two* (the review flagged keyword-count drift): the panel's
  proposed `Agent.Get Run Status` and `Agent.Run Should Have Completed` both depend
  on a per-result status; with no fabricated result (D2) that status is always `ok`
  on a returned result (vestigial), and a reader over an already-stringified caught
  error would **reintroduce** the string-matching this change removes. So they are
  dropped; robust classification stays inside `Agent.Run Agent`.
- *Naming*: `Run Agent` (not bare `Run`, which is single-word-after-dot and trips
  the DynamicCore+libdoc auto-split norm; `run()`/`Stat.Run N Times` already
  establish `Run` as the project verb). Both names are multi-word after the dot.

### D2 — Status model: classify + raise/skip, never fabricate

`Agent.Run Agent`:

```
enforce_no_model()                       # uniform Tier-3 gate across all families (review MED)
try:
    return adapter.run(prompt, **run_kwargs)
except Exception as exc:
    category = classify_run_exception(exc)      # -> "budget_exceeded" | "provider_error" | "timeout" | None
    if category is None:
        raise                                    # genuine config/auth/harness fault -> fail loud
    if category in skip_on:
        BuiltIn().skip(f"{category}: {adapter.name} - {exc}")
    if category == "budget_exceeded":
        raise BudgetExceededError(...) from exc   # unify budget under the existing leaf (exit 66)
    raise                                         # unlisted transient -> re-raise original
```

No new field on `AgentRunResult`/`AgentRunMetadata`; the existing `completeness`
already covers "returned but degraded", and a *failed* run returns nothing to stamp.
This eliminates the fabricated-result fake-green hazard the review flagged.

### D3 — The classifier keys on structured signals, per family (review HIGHs)

`_core` gains a pure `classify_run_exception(exc)` that lazily imports
pydantic-ai/openai/litellm inside the function (dependency direction preserved). It
must **not** blanket-map on class name — the review proved that silently skips real
faults. The verified taxonomy:

| Family | Signal | Category |
|---|---|---|
| in-process | `UsageLimitExceeded` | `budget_exceeded` |
| in-process | `ModelHTTPError` (check **before** `ModelAPIError` — it is a subclass) with `status_code ∈ {408,409,429,500,502,503,504}` | `provider_error` |
| in-process | `ModelHTTPError` with any other status (401/403/404/422/400) | **None → raise** (auth/config) |
| in-process | `ModelAPIError` (timeout/connection carrier) | `provider_error` |
| in-process | `UnexpectedModelBehavior` **only if** message contains `"Invalid response from"` | `provider_error` |
| in-process | `UnexpectedModelBehavior` otherwise | **None → raise** (genuine) |
| generic | `isinstance` litellm/openai `RateLimitError`/`APITimeoutError`/`APIConnectionError`/`InternalServerError`; `APIStatusError` with a retryable status | `provider_error` |
| CLI | `AdapterError` whose `__cause__` is `subprocess.TimeoutExpired` | `timeout` |
| CLI / core | `AdapterError` (binary-missing/other), `MissingExtraError`, `TierViolationError`, unknown | **None → raise** |

`skip_on` accepts only `budget_exceeded` / `provider_error` / `timeout`;
`binary_missing`/config faults are **not** skippable categories (they always raise),
which is why they are absent — the review showed `binary_missing` can't be told
apart from other config `AdapterError`s without a marker, so it's out of v1.

### D4 — Stable public `AgentEval.get_adapter`

Re-export `get_adapter` and `Adapter` from `AgentEval/__init__.py` (add to
`__all__`), listed `provisional` in `stability-surface.md`. Verified import-cheap:
`import AgentEval` and `from AgentEval._core.adapter import get_adapter` both load
with litellm/pydantic-ai absent from `sys.modules` — the extras stay lazy inside
`run()`, so the re-export adds no import cost and creates no cycle (`adapter.py`
imports only `errors`/`tier`/`types`). Then sweep the teaching sites (both `_core`
spellings) in **prose/examples only** onto `AgentEval.get_adapter` / the keywords —
leaving legitimate *functional* internal imports (e.g. `MCPLibrary/_discoverability.py`,
`SkillsLibrary/_internal.py`) untouched, since surface→`_core` is the correct
dependency direction.

### D5 — Reconcile the stability contract holistically

Because this change edits the library registry (adds the 7th), reconcile
`docs/contracts/stability-surface.md` in the same change: register
Metrics/Stat/Agent, correct the stale per-library counts and the superseded "CLI
adapters SHALL NOT be shipped" note, and add `get_adapter`/`Adapter` at
`provisional`. This also clears the pre-existing drift the review surfaced.

## Risks / Trade-offs

- **Classifier drifts from the SDKs' exception taxonomy** → Mitigation: it's one
  module with unit tests pinning the load-bearing cases (`ModelHTTPError(401)` →
  raise, `(429)` → `provider_error`, CLI timeout `__cause__` chain, litellm
  `RateLimitError` → `provider_error`); a new SDK exception simply falls through to
  "raise", which is the safe default (fail loud, never a false skip).
- **`skip_on` can mask a chronic outage as a perpetual skip** → Mitigation: the skip
  message names category + adapter for auditability; genuine faults never skip.
- **A 7th library adds doc-gate surface** (`_LIBRARY_COUNT`, `_COUNTED_LIBRARIES`,
  README/index totals, stability registry) → Mitigation: the docs-build gate fails
  loud if any is missed; all are enumerated in tasks.
- **`Agent.Get Adapter` forwarding a ctor kwarg to a no-ctor CLI adapter** would
  `TypeError` → Mitigation: strip `None`-valued explicit params before forwarding;
  document that CLI slugs take no construction config.

## Migration Plan

Additive, non-breaking — no migration. New library + two keywords + one re-export +
one classifier module + a default-behavior-preserving doc sweep. Existing suites and
the `Evaluate`/`_core` path are unaffected. Rollback is a straight revert.

## Open Questions

- **litellm-vs-openai isinstance set (generic family):** the exact transient base
  tuple is pinned at implementation time against the installed wheels (litellm
  subclasses openai, so `isinstance` against openai bases likely suffices, but the
  tests assert the concrete litellm types).
- **A future `Agent.Get Run Status` / typed provider error** could return if a
  robust, non-fabricating data path emerges (e.g. a typed `ProviderError` leaf) —
  deliberately deferred to keep v1 minimal and honest.
