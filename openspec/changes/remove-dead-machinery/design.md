# Design: remove-dead-machinery

## Context

Pre-1.0 subtractive simplification. The proposal verified (grep, 2026-07-08) four classes of dead weight: a caller-less `security/` package, an empty `reporting/` package, a byte-for-byte-equivalent Wilson CI duplicate, and a config-resolution chain executed twice per library import behind twin functions and twin keywords. Two contracts constrain the work: `docs/contracts/error-class-hierarchy.md` (ADR-014, exit-code table mirrored in `cli._ERROR_EXIT_CODES`) and `docs/contracts/stability-surface.md` (registers `Get Effective Config` and the `SandboxBackend` Protocol). Test baseline at HEAD: 1605 passed + 10 skipped.

## Goals / Non-Goals

**Goals:**

- Remove the four verified dead-weight classes with zero behavior change for every surface that has real callers.
- One config-precedence implementation; one config keyword; one resolution pass per `AgentEval.__init__`.
- Zero background threads for `@guarded_fanout` calls that have nothing to enforce.
- Contracts (`error-class-hierarchy.md`, `stability-surface.md`, ADR-018) updated in the same change so no drift window opens.

**Non-Goals:**

- No user-facing doc/README/recipe work (`fix-first-run-experience`).
- No library composition changes (`compose-single-library-import`).
- No cuts to adapters, stats primitives, redaction, or version_drift (audited as justified).
- No redesign of the budget engine beyond the no-budget fast path (`_HostBudgetPlumbing`, tier ACL, and the budgeted metering path stay as-is).
- No deprecation shims — pre-1.0, deletions are hard.

## Decisions

### D1 — Delete `security/` whole; keep the entry-point seam

Delete all four files. Keep the empty `agenteval.sandboxes` entry-point group in `pyproject.toml` and `_kernel/discovery.discover_sandboxes()` — they cost ~0 LOC, are tested, do not import the deleted package, and remain the documented Phase-3 extension seam (ADR-018). Also delete the never-shipped `"SANDBOX_REQUIRED": 77` planned row from `cli._ERROR_EXIT_CODES` (the `SandboxRequiredError` class was never added to `errors.py`; `NullSandbox` still raises placeholder `NotImplementedError`).

- *Alternative — keep `protocols.py` (the `SandboxBackend` Protocol) as contributor-facing API*: rejected. A Protocol with zero implementations and zero importers is speculative API; re-adding it in Phase 3 is trivial and lets it be shaped by the real backend's needs instead of a 2026-05 guess. `stability-surface.md` gets its Sandbox Protocol subsection replaced by a one-line "withdrawn pre-1.0; re-ratified when Phase-3 sandbox lands" note.

### D2 — Wilson dedup keeps `stats/wilson.py`

`stats/wilson.py` is the keeper: it is the more defensive implementation (full input validation), is exported via `AgentEval.stats` and backs the `Stat.*` keyword surface. `discoverability/wilson_ci.py` has an identical public signature (`wilson_score_interval(successes, trials, confidence=0.95) -> tuple[float, float]`) and one production caller (`discoverability/_internal.py:41`), which is repointed. Both compute the same closed-form Wilson formula, so discoverability CI numbers are bit-identical; the folded test file proves it (any `test_wilson_ci.py` assertion not already in `test_wilson.py` moves over, including one run against the discoverability call path).

### D3 — One precedence chain; `resolve_config` becomes a value projection

`resolve_config_with_provenance` becomes the single implementation of the 4-layer precedence chain (kwarg > env > `.env` > default, including dotenv load and unknown-`AGENTEVAL_*`-key warnings). `resolve_config` keeps its name, signature, and `dict[str, Any]` return shape but is reduced to a projection: `{k: cv.value for k, cv in resolve_config_with_provenance(...).items()}`. This dedupes the ~96-LOC duo to one chain plus ~5 lines and closes the in-code TODO DF-4.3-S1.

`AgentEval.__init__` calls `resolve_config_with_provenance` exactly ONCE, stores the map, and derives bare values from it — fixing the double resolution and the doubled unknown-key warnings at `src/AgentEval/__init__.py:265`/`:269`. The hand-maintained 10-key literal dict inside `get_effective_config` (drift-prone shadow copy of the config keys) is replaced by a derivation from the stored provenance map.

- *Alternative — single function returning `dict[str, ConfigValue]` under the `resolve_config` name*: rejected; it ripples through `telemetry/listener.py:898` and ~30 call sites in `tests/unit/kernel/test_context.py` for zero user-visible gain. One chain + one projection satisfies the merge intent.

**Keyword fate (BREAKING):** delete `Get Effective Config With Provenance`. `Get Effective Config` keeps both existing forms unchanged: no-arg → plain `dict[str, Any]` (the common RF case, `${config}[max_cost_usd]` keeps working), `setting=<key>` → `ConfigValue(value, source)`. The per-key form already covers the only real provenance use case ("why isn't my .env value applied?"), so the full-provenance-map keyword had no distinct job. DF-4.3-S1's proposed migration of the no-arg form to `dict[str, ConfigValue]` is explicitly REJECTED rather than deferred — it would degrade the common case (`.value` suffix everywhere) to serve a debugging case the `setting=` form already serves; the carry-over entry in `docs/phase-1-5-carry-overs.md` is closed with this rationale. `stability-surface.md` registers `Get Effective Config` (kept intact) — the deleted twin was never the stable headline surface. FR41's ConfigValue contract remains satisfied via the `setting=` form.

### D4 — `errors.py`: fold exactly one leaf; keep all six bases

Verified census: 30 classes = 1 root + 5 family bases (all never raised — they are the documented catch points) + 23 concrete leaves (ALL have ≥1 raise site; the dossier's "~15 ever raised" was wrong) + `DegradedTraceWarning` (warned 8x). Of the 4 leaves with exactly 1 raise site, only `DuplicateRegistrationError` folds: it has no dedicated row in `cli._ERROR_EXIT_CODES` (callers already exit through `ADAPTER_DISCOVERY_ERROR`), its single raise site is in `_kernel/discovery.py`, and "duplicate entry-point name" is expressible in the `AdapterDiscoveryError` message without losing the File/Line/Field/Fix block. The kept single-raise leaves and why:

| Leaf | Kept because |
|---|---|
| `ValidateOperatorDisallowed` | dedicated exit code 77; ADR-014-ratified name; safety opt-in gate users catch |
| `RuntimeBudgetExceededError` | dedicated exit code 75 vs `CostExceededError` 66 — CI scripts branch on the distinction |
| `SkillDidNotActivateError` | user-catchable assertion class with structured diagnostic attrs (FR4d) |

Docstring narration trim: story-numerology walkthroughs (review-finding citations, epic timelines) inside class docstrings are cut to the behavioral contract; every File/Line/Field/Fix format description and `fix_suggestion` mechanic stays verbatim. `error-class-hierarchy.md` leaf count goes 24 → 22 (drop planned-only `SandboxRequiredError` per D1, fold `DuplicateRegistrationError`) with an ADR-014 amendment note in the same commit (fix-the-losing-source-NOW).

### D5 — `@guarded_fanout` no-budget fast path

At wrapper entry, after popping the test-only `_TEST_BUDGET_KWARG` override and resolving `max_cost_usd`/`max_runtime_seconds` from the host instance: if BOTH are `None`, call `func` directly — no meter thread, no `_BreachState`, no cancel-event ContextVar binding, no Layer-1 comparisons (they compare against `None` and can never fire). `current_cancel_event()` returns `None` on this path, which is already its documented out-of-frame behavior and has zero consumers outside `guardrails.py`. The budgeted path is byte-for-byte unchanged: Layer-1 pre-flight estimation, non-daemon meter thread, fail-closed cost-source handling, post-body breach raise.

Verified blast radius: 9 decorator sites, all bare `@guarded_fanout()`, 0 pass `estimator`. The fast path is the default for the 5 sites whose budget kwargs default to `None` (stats fan-out, orchestration, judge x2, StatsLibrary); the 4 MCP/Skills sites default to non-None budgets and keep metering.

- *Alternative — also delete the unused `estimator` parameter*: rejected for this change; it is ADR-015's documented Layer-1 surface and is exercised by unit tests. Cheap to keep, and removing it is an ADR amendment this subtractive pass does not need.
- *Alternative — daemon-ize or pool the meter thread*: out of scope; budgeted-path redesign is a non-goal.

### D6 — Dev tooling stays in the package (evaluated, no-op)

`conformance/` (404 LOC), `_new_adapter/` (146), `_init/` (119) all stay. Verification showed the premise of "move out of the runtime import path" is already satisfied: `_init` and `_new_adapter` are lazily imported inside `cli.py` subcommand handlers; `conformance` is reachable only via `python -m AgentEval.conformance` and its own tests. Remaining costs are wheel bytes (trivial) — against which `agenteval init` is the headline onboarding command, so a `[dev]` extra would break `pip install robotframework-agenteval && agenteval init` for exactly the first-run users `fix-first-run-experience` is courting. Alternatives (dev extra; separate `agenteval-devtools` package) rejected on that ground. This decision is recorded so the E5 audit line is answered, not silently dropped.

## Risks / Trade-offs

- [Discoverability CI numbers shift after dedup] → Same closed-form formula in both files; folded tests include an assertion through the discoverability call path (`_internal.py`) pinning known input/output pairs before and after.
- [Hidden dynamic importers of deleted modules (string-based imports, entry points)] → grep for module paths as strings (`"AgentEval.security"`, `"wilson_ci"`, `"AgentEval.reporting"`) in `src/`, `tests/`, `pyproject.toml` before deletion; full test suite + `uv run mypy src/` + libdoc-render smoke as gates.
- [Someone catches `DuplicateRegistrationError` outside src] → verified 1 raise site and 0 catch sites in `src/`; tests referencing it are updated to `AdapterDiscoveryError` in the same commit. Pre-1.0: acceptable break, listed in proposal Impact.
- [`Get Effective Config With Provenance` removal breaks RF suites] → grep shows usage only in `src/AgentEval/__init__.py`, its own tests, and libdoc output; contract docs updated same commit. Pre-1.0 hard delete per Non-Goals.
- [No-budget fast path masks a latent dependency on the cancel-event binding] → `current_cancel_event()` has zero consumers outside `guardrails.py` (verified); add a unit test asserting no `agenteval-guarded-fanout-meter` thread is spawned on the no-budget path AND an existing-behavior test that budgeted calls still spawn/join it.
- [Docstring trim in errors.py accidentally cuts contract text] → trim rule is mechanical: keep everything describing runtime behavior, message format, attrs, exit codes; cut only review/story citations. Reviewer diff-checks `File:`/`Line:`/`Field:`/`Fix:` blocks are untouched.
- [Contract-count drift between `cli._ERROR_EXIT_CODES` and `error-class-hierarchy.md`] → both edited in the same commit; the existing exit-code unit tests enforce the mirror.

## Migration Plan

1. Deletions with no API ripple first: `reporting/`, `security/` (+ `SANDBOX_REQUIRED` row + `stability-surface.md`/ADR-018 notes), `wilson_ci.py` (+ repoint + test fold). Full suite green.
2. Resolver merge (D3): context.py, `__init__.py` single-pass, keyword deletion, `test_context.py`/tier-1 test updates, carry-over closure. Full suite + libdoc smoke green.
3. `errors.py` fold + trim (D4) + contract doc sync. Full suite green.
4. Guardrails fast path (D5) + new thread-absence tests. Full suite + `ruff` + `mypy` green.

Rollback: each step is an independent commit; revert the offending commit. No data or schema migration exists.

## Open Questions

None — the one genuinely open call (dev-tooling placement, D6) is resolved as keep-in-package with rationale recorded.
