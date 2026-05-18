# Stability Surface

**Status:** accepted (Story 1a.6 initial registry; expanded incrementally by future epic stories).
**Owning epic:** Story 1a.6 (initial registry) + Epic 6 (sandbox surface evolution)
**Related ADRs:** ADR-018 (Sandbox Phase 1 Policy — `SandboxBackend` Protocol), ADR-013 (Entry-Points Discovery — registration mechanism), ADR-014 (Error-Class Hierarchy — error-class stability labels)
**Related FRs:** FR64 (Stability Surface metadata), NFR-MAINT-05 (per-element stability labels)

## Purpose

Defines agenteval's **per-API-element stability label scheme** (`stable` / `provisional` / `experimental`) + the rules for promoting/demoting elements between labels. The **registry** of currently-labeled elements is filled **incrementally**: Story 1a.6 lands the initial Phase-1 labels; each subsequent epic-owning story registers its public elements as they ship. Phase-1 baseline contains the AgentEval Library surface (Story 1a.6 — class + 9 `__init__` params + `Get Effective Config` keyword; see `### AgentEval Library Surface` subsection) AND the sandbox surface (Story 1a.4 — `SandboxBackend` Protocol + related entry-point group; see `### Sandbox Protocol Surface` subsection); other public elements are added to the registry by the owning stories as they ship. Release notes link here so consumers know what is safe to depend on across versions.

## Scope

### In-scope

- The 3 stability labels + their semantics (consumer-facing guarantee per label).
- Label-change policy (when is a `provisional` element promoted to `stable`? when must a `stable` element be deprecated?).
- The Phase-1-baseline registry entries: the AgentEval Library surface (Story 1a.6 — `### AgentEval Library Surface` subsection) AND the sandbox surface (Story 1a.4 — `### Sandbox Protocol Surface` subsection). Each epic-owning story registers additional elements as they ship.
- The procedure for adding a new public element to the registry (per-story checklist in Maintenance section).

### Out-of-scope

- Internal helpers + private surfaces (`_kernel/`, `_assertions/`) — labels don't apply.
- Backend implementations that consumers ship in their own packages (e.g., a `docker-sandbox` package implementing `SandboxBackend`) — those packages manage their own stability.

## Contract

**Stability labels:**

- `stable` — semver-protected across major version. Breaking changes require major-version bump + deprecation cycle (≥1 minor before removal).
- `provisional` — likely to stabilize but may break across minor versions. Document the next breaking change in CHANGELOG.
- `experimental` — explicitly unstable. May break or be removed any minor release. Use with `pin >=X.Y.Z,<X.Y.(Z+1)`.

**Per-element registry:** Filled INCREMENTALLY. Phase-1 baseline (Story 1a.6) registers the `AgentEval` library entry point + its 9 FR42/FR11b config params + the `Get Effective Config` keyword + the sandbox surface (Story 1a.4 baseline). Subsequent epic-owning stories MUST register their public elements (keywords, Protocols, error-class names, entry-point group names) at the time of shipping. FR64/NFR-MAINT-05 enforcement (the docs-build CI check that warns on unlabeled elements) lands in a future story; the registry's incremental fill begins here.

### AgentEval Library Surface (Story 1a.6 Phase-1 registry)

Per `src/AgentEval/__init__.py` (Story 1a.6 ratification):

- `AgentEval` class at `src/AgentEval/__init__.py` — `provisional` label in Phase 1. Public RF Library entry point invoked via `Library    AgentEval    <kwargs>`. FR41 precedence chain (kwarg → env-var → `.env` → defaults) is wired by Story 1b.1 via `_kernel.context.resolve_config`; signature may continue to evolve as sub-libraries land their config knobs. `provisional` label warns consumers that the kwarg set may grow.
- `AgentEval.__init__` 9 keyword-only parameters — all `provisional` label in Phase 1 (parameter names + types stable; default values may tighten via ADR amendment as empirical data accumulates). Default values per PRD FR42 + FR11b + ratified ADRs:
  - `provider: str = "litellm"` (FR42 + ADR-013)
  - `telemetry: bool = True` (FR42 + FR44)
  - `trace_backend: str = "memory"` (FR42 + FR33b)
  - `allow_validate_operator: bool = False` (FR42 + FR43; NFR-SEC-02)
  - `default_temperature: float = 0.0` (FR42)
  - `mcp_per_test: bool | Literal["suite"] = True` (FR42 + ADR-009 for True/False; architecture L314 + NFR-PERF-03d for `"suite"` mode — `"suite"` is NOT ratified by ADR-009 proper)
  - `allow_external_mcp_blind: bool = False` (FR42 + ADR-016)
  - `max_cost_usd: float = 5.00` (FR42 + ADR-015)
  - `max_runtime_seconds: float | None = None` (FR11b + ADR-015)
- `Get Effective Config` RF keyword (Python method `AgentEval.get_effective_config`) — `provisional` label in Phase 1. Returns a `dict[str, Any]` keyed by the 9 `__init__` parameter names. **Story 1b.1 update**: returns FR41 precedence-resolved values (kwarg → env-var → `.env` → defaults) via `_kernel.context.resolve_config`, not just kwarg-resolved values. Phase-2 may evolve to a structured `EffectiveConfig` dataclass for stronger typing on the consumer side; `provisional` label warns consumers that the return-type may evolve from `dict[str, Any]` to a typed structure (the keys + value types per key will remain `stable`).
- `AgentEval.__version__` module attribute — `stable` label. PyPI distribution + import metadata convention. Bump per semver per NFR-MAINT-03.

### Kernel public surface (Story 1b.1 — Phase-1 registry, exception to the `_kernel/` opacity rule)

`_kernel/` is normally out-of-scope for the stability registry (Scope section above). The following exceptions are explicit per Story 1b.1 AC-1b.1.1 because they're consumed by sub-libraries + tests + the OTel listener (Epic 5 Story 5.1) and need a stable contract for those consumers:

- `_kernel.context._resolve_scope(mcp_per_test) -> Scope` — `provisional` label. The SINGLE canonical translator between the user-facing `bool | Literal["suite"]` kwarg vocabulary and the internal `Literal["test", "suite", "process"]` Scope vocabulary. Truth table: True→"test" / False→"process" / "suite"→"suite". Signature may evolve if a 4th scope mode lands (no current plan).
- `_kernel.context.Scope` type alias — `provisional` label. `Literal["test", "suite", "process"]`. Adding a value is a minor bump; renaming a value is a major bump.
- `_kernel.context.TestContext` dataclass — `provisional` label. `(test_id: str, suite_id: str, scope: Scope)`. ContextVar-backed accessor via `current_context()`/`bind_context()`/`unbind_context()`/`set_current_test_id()`.
- `_kernel.context.MCPLifecycleManager` class — `provisional` label. Per-pabot-worker MCP server lifecycle per Story 0.2 spike findings §`_kernel/context.py` draft (LOAD-BEARING). Scope-aware idempotent `acquire()` + scope-aware `release_test()`/`release_suite()` + `shutdown_all()` + `close()` (M2 review fix — `close()` unregisters atexit + restores prior SIGTERM handler).
- `_kernel.context.{ServerSpec, ServerHandle, ReleaseResult}` dataclasses — `provisional` label. Field set may evolve as Phase-2 sub-libraries consume them; field renames require a major bump.
- `_kernel.context.resolve_config(kwarg_overrides, *, dotenv_path) -> dict` — `provisional` label. FR41 precedence resolver. Layer order is `stable`; per-key type coercion vocabulary (e.g., `_parse_bool` accepting true/false/1/0/yes/no/on/off) is `provisional`.
- `_kernel.tier.{tier, get_keyword_tier, tier_badge}` — `provisional` label. Decorator + accessors; `_agenteval_tier` attribute name is `stable` (consumers can depend on it directly).
- `_kernel.run_async._run_async[T](coro) -> T` — `provisional` label. The `architecture.md` §Async-to-Sync Bridge Convention is `stable`; the worker-thread fallback mechanism is `provisional` (Phase-2 may add cancellation/timeout knobs).
- `_kernel.trace_store.{get_run_spans, get_tool_calls, get_usage, get_latency, get_run_manifest}` — `provisional` label (Story 1b.2 baseline). The 5 projection accessors per architecture L664-669 / Decision-2. The "no direct span access by sub-libraries" rule (architecture L853) is `stable`; sub-libraries MUST consume these accessors, NOT touch spans directly. Phase-2 may add OTLP-specific projection variants.
- `_kernel.trace_store.clear_spans(test_id) -> int` — `provisional` label. Per-test cleanup hook called by the Listener (Epic 5 Story 5.1).
- `_kernel.trace_store._configure_tracer_provider()` — `provisional` label. Phase-1 placeholder; Epic 5 Story 5.1 lands the full TracerProvider configuration (resource attributes + SpanProcessor chain).
- `_kernel.redaction.{redact, redact_dict, register_pattern, redaction_policy_hash}` — `provisional` label. Primitive scrubbing surface; `DEFAULT_PATTERNS` set is `provisional` (additions/removals are minor-version bumps with CHANGELOG entry).
- `_kernel.redaction.RedactionProcessor` (OTel `SpanProcessor`) — `provisional` label. Wires `redact()` into the OTel pipeline per architecture L679. `_SENSITIVE_ATTRIBUTE_KEYS` covered set is `provisional` (additions are minor-bump; consumers can subclass + override).
- `_kernel.coverage._check_mcp_coverage(run, *, allow_external_mcp_blind) -> None` — `provisional` label. FR37 + ADR-016 L44 enforcement gate. Behavior matrix (3 mcp_coverage values × 2 allow_external_mcp_blind values = 6 cells) is `stable`; the raised `IncompleteTraceError` `error_code="INCOMPLETE_TRACE"` is `stable`.

### Top-level errors + types surface (Story 1b.2 — Phase-1 registry)

Per architecture L853 (top-level shared types) + L1184 (top-level errors module):

- `AgentEval.errors.AgentEvalError` base — `stable` label. The 4-sub-base scheme (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`) is `stable` per ADR-014; consumers can `try / except AgentEvalError` to catch all agenteval errors. Story 1b.2 ships only `AgentEvalIntegrityError`; the other 3 sub-bases land as future stories need them.
- `AgentEval.errors.AgentEvalIntegrityError` sub-base — `stable` label.
- `AgentEval.errors.IncompleteTraceError` leaf — `stable` label. `error_code = "INCOMPLETE_TRACE"` is `stable` per ADR-014.
- `AgentEval.types.{ToolCallTrace, Usage, RunManifest}` dataclasses — `provisional` label. Phase-1 stdlib `@dataclass(frozen=True)` (deviation from architecture's "Pydantic dataclasses" wording — documented in `types.py` docstring + Phase-1.5 carry-over). Field set is `provisional` (field additions are minor bumps; field renames are major bumps).

### Sandbox Protocol Surface

Per ADR-018 (`adopt` from agentguard ADR-013 with significant divergence — see `docs/adr/ADR-001-architectural-influences-catalog.md` agentguard ADR-013 row):

- `SandboxBackend(Protocol)` at `src/AgentEval/security/protocols.py` — `provisional` label in Phase 1. Methods: `execute(code, language, timeout) -> SandboxResult`. Signature may evolve in Phase 2 as real backends ship; `provisional` label warns consumers.
- `NullSandbox` default backend at `src/AgentEval/security/null_sandbox.py` — `stable` label. Refuses every `execute()` call by raising `SandboxRequiredError`. Backwards-compat guarantee: a `NullSandbox()` instance always raises; never silently executes.
- `agenteval.sandboxes` entry-points group — `stable` label. The discovery mechanism for backends is fixed; the Protocol surface backends MUST implement is `provisional`.
- `SandboxRequiredError(AgentEvalSafetyError)` at `src/AgentEval/errors.py` — `stable` label. `error_code = "SANDBOX_REQUIRED"`; FR50 exit code 3.

Phase-3 sandbox backend implementations (Docker, ephemeral worktree, gVisor optionally) live in separate packages and manage their own stability.

## Change Policy

This contract evolves per its own labels (the meta-rule: this contract is `stable` from Phase-1 onward). Adding new elements to the registry is minor-version-bump safe. Changing an existing element's label requires:

- `experimental → provisional`: minor-version bump + CHANGELOG entry.
- `provisional → stable`: minor-version bump + CHANGELOG entry + a documented deprecation policy for the prior `provisional` surface.
- `stable → provisional` (a downgrade): major-version bump per NFR-MAINT-03. Document the reason in CHANGELOG + offer a migration path.

## References

- ADR-018: Sandbox Phase 1 Policy — the `SandboxBackend` Protocol + `NullSandbox` default
- ADR-013: Entry-Points Discovery Infrastructure — `agenteval.sandboxes` registration
- ADR-014: Error-Class Hierarchy — `SandboxRequiredError` leaf
- FR64 (PRD): Stability Surface metadata; NFR-MAINT-05: per-element labels
- `agentguard ADR-013` row in `docs/adr/ADR-001-architectural-influences-catalog.md`: the `adapt` decision for sandbox policy
