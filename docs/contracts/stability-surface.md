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

- `AgentEval.errors.AgentEvalError` base — `stable` label. The 4-sub-base scheme (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`) is `stable` per ADR-014; consumers can `try / except AgentEvalError` to catch all agenteval errors. Story 1b.2 shipped `AgentEvalIntegrityError`; Story 1b.3 ships `AgentEvalBudgetError` + `AgentEvalCompatError`; `AgentEvalSafetyError` lands as future stories need it.
- `AgentEval.errors.AgentEvalIntegrityError` sub-base — `stable` label.
- `AgentEval.errors.AgentEvalBudgetError` sub-base (Story 1b.3) — `stable` label.
- `AgentEval.errors.AgentEvalCompatError` sub-base (Story 1b.3) — `stable` label.
- `AgentEval.errors.IncompleteTraceError` leaf — `stable` label. `error_code = "INCOMPLETE_TRACE"` is `stable` per ADR-014.
- `AgentEval.errors.CostExceededError` leaf (Story 1b.3) — `stable` label. `error_code = "COST_EXCEEDED"` is `stable` per ADR-014; FR50 exit code 66 (sysexits-extended; pinned by epics.md Story 8a.1 L1660 + contract L73).
- `AgentEval.errors.RuntimeBudgetExceededError` leaf (Story 1b.3) — `stable` label. `error_code = "RUNTIME_BUDGET_EXCEEDED"` is `stable` per ADR-014; FR50 exit code 75 (EX_TEMPFAIL; contract L74).
- `AgentEval.errors.AdapterDiscoveryError` leaf (Story 1b.3) — `stable` label. `error_code = "ADAPTER_DISCOVERY_ERROR"` is `stable` per ADR-014; FR50 exit code 78 (EX_CONFIG; contract L82). Exposes a `loaded_so_far: dict[str, type]` attribute per ADR-013 L42 verbatim — `stable`.
- `AgentEval.errors.DuplicateRegistrationError` leaf (Story 1b.3 code-review patch per Codex STAR catch) — `stable` label. Subclass of `AdapterDiscoveryError` per ADR-013 L43 verbatim. Same `error_code` as the parent; same FR50 exit code 78. Exposes `sources: tuple[str, str]` (primary, legacy dist names) — `stable`.
- `AgentEval.errors.UnsupportedBinaryVersionError` leaf (Story 1b.4) — `stable` label. `error_code = "UNSUPPORTED_BINARY_VERSION"` is `stable` per ADR-014; FR50 exit code 78 (EX_CONFIG; contract L81). Class declaration ships in Story 1b.4; per-adapter raise sites in Epic 4 Story 4.2 (Claude Code CLI) + Epic 11 Story 11.3 (Copilot CLI). FR47 error-message format `<binary> version <X> outside tested range <range>` is `stable`.
- `AgentEval.types.{ToolCallTrace, Usage, RunManifest}` dataclasses — `provisional` label. Phase-1 stdlib `@dataclass(frozen=True)` (deviation from architecture's "Pydantic dataclasses" wording — documented in `types.py` docstring + Phase-1.5 carry-over). Field set is `provisional` (field additions are minor bumps; field renames are major bumps).
- `AgentEval.types.{AgentRunResult, AgentRunMetadata}` dataclasses (Story 1b.4) — `provisional` label. Phase-1 stdlib `@dataclass(frozen=True)`. `AgentRunResult` 7-field shape is `provisional` (subsequent stories may add optional fields like `cancellation_reason`; existing field renames are major bumps). `AgentRunMetadata` 3-state Literal value spaces (`completeness` + `mcp_coverage`) are `stable` per ADR-006 L15 + ADR-016 §Decision L24-28. The `.metadata.{completeness, mcp_coverage}` nesting itself is `stable` per ADR-006.

### Kernel discovery + guardrails surface (Story 1b.3 — Phase-1 registry)

Per ADR-013 (entry-points discovery) + ADR-015 (cost-runtime guardrail decorator):

- `_kernel.discovery.{discover_adapters, discover_providers, discover_sandboxes}` — `provisional` label. The 3 typed group accessors per ADR-013 L47. Return-type contract `dict[str, type[...]]` is `stable`; per-key adapter-class shape (`CodingAgentAdapter` Protocol) is `provisional` until Story 1b.4 ratifies the Protocol.
- `_kernel.discovery.{register_adapter, get_adapter}` — `provisional` label. FR17b composition path. Lookup precedence (programmatic > primary entry-points > legacy entry-points) is `stable`; the `legacy` group name (`robotframework_agenteval.adapters`) is `stable` per ADR-013 L18 backward-compat guarantee.
- `_kernel.discovery._clear_discovery_cache` — `experimental` label. Test-only helper; consumers MUST NOT depend on it.
- `_kernel.guardrails.guarded_fanout(estimator, *, meter_interval_seconds)` decorator — `provisional` label. 3-layer enforcement per ADR-015 §Decision L25-29 is `stable`; the `estimator` callable signature `(kwargs: dict) -> (cost_est, runtime_est)` is `provisional` (Phase-2 may add provider context).
- `_kernel.guardrails.current_cancel_event()` — `provisional` label. Cooperative-cancellation accessor returning `threading.Event | None`. The ContextVar-propagation contract (via Story 1b.1's `_run_async` copy_context) is `stable`; the Event Phase-2 may be replaced with a richer cancellation token.
- `_kernel.guardrails._current_cost_usd_for_run` — `experimental` label. Phase-1 stub returning 0.0; Story 4.1 (Generic LiteLLM adapter) wires the real cost source. Consumers MUST NOT call directly.

### Coding Agent Adapter Surface (Story 1b.4 — Phase-1 registry)

Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`) + ADR-005 (≤2 adapters per vendor + 1 universal escape hatch) + architecture L1226-1228:

- `AgentEval.coding_agent.CodingAgentAdapter` Protocol — `provisional` label. Single `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` method per PRD FR12 L1506 (NOT a 2-method `send_prompt + run_scenario` split — Story 1b.4 D1 drift resolution). `@runtime_checkable` enables `isinstance` for the FR17b composition path. Properties `name: str` + `version: str` are `provisional`. Method signature is `stable`; `name`/`version` are `provisional` (default-implementation fallback to `type(self).__name__` + `importlib.metadata.version()` may evolve). The Protocol class is DECLARED in `src/AgentEval/types.py` and RE-EXPORTED through `src/AgentEval/coding_agent/base.py` + `coding_agent/__init__.py` per architecture L853 cross-sub-library import discipline.
- `AgentEval.coding_agent.InProcessAdapter` — `provisional` label. Concrete-by-default base for SDK-driven adapters per ADR-003 L22-23 direct-override pattern (NO `@abstractmethod` hooks). Default `name` + `version` properties + `__init__(**kwargs)` capturing `_adapter_config` are `provisional`.
- `AgentEval.coding_agent.SubprocessAdapter(ABC)` — `provisional` label. Abstract template-method base for CLI-driven adapters per ADR-003 L24-29 + architecture L1228 with EXACTLY 3 `@abstractmethod` hooks: `_spawn(prompt, **kwargs) -> subprocess.Popen[str]` + `_parse_event(line: str) -> ParsedEvent | None` + `_finalize(events, exit_code) -> AgentRunResult`. The 3-hook contract is `stable` per ADR-003. The concrete `run()` template-method orchestration (spawn → iterate stdout through `_parse_event` → `_finalize`, with `proc.terminate()` cleanup on exception per Story 1b.1 process-group hygiene) is `provisional`.
- `AgentEval.coding_agent.SubprocessAdapter._assert_binary_version(binary, min, max)` helper — `provisional` label. Raises `UnsupportedBinaryVersionError` with FR47-exact message format `<binary> version <X> outside tested range <range>` on mismatch. The error-message format is `stable` per FR47; the regex-based version-extraction (semver-ish `r"(\d+\.\d+(?:\.\d+)?)"`) is `provisional` (subclasses MAY override for non-standard CLI version-output formats).
- `AgentEval.coding_agent.ParsedEvent` — `experimental` label. Story 1b.4 placeholder `type ParsedEvent = Any`. Concrete CLI adapters in Epic 4 Story 4.2 + Epic 11 Stories 11.x declare per-adapter concrete intermediate event types (`ClaudeCodeEvent`, `CodexEvent`, `CopilotEvent`) per architecture L1228 per-adapter pattern.
- `agenteval.coding_agents` entry-points group — already registered as `stable` in the kernel-discovery section above (Story 1b.3 baseline).

### Sandbox Protocol Surface

Per ADR-018 (`adopt` from agentguard ADR-013 with significant divergence — see `docs/adr/ADR-001-architectural-influences-catalog.md` agentguard ADR-013 row):

- `SandboxBackend(Protocol)` at `src/AgentEval/security/protocols.py` — `provisional` label in Phase 1. Methods: `execute(code, language, timeout) -> SandboxResult`. Signature may evolve in Phase 2 as real backends ship; `provisional` label warns consumers.
- `NullSandbox` default backend at `src/AgentEval/security/null_sandbox.py` — `stable` label. Refuses every `execute()` call by raising `SandboxRequiredError`. Backwards-compat guarantee: a `NullSandbox()` instance always raises; never silently executes.
- `agenteval.sandboxes` entry-points group — `stable` label. The discovery mechanism for backends is fixed; the Protocol surface backends MUST implement is `provisional`.
- `SandboxRequiredError` — `stable` label. `error_code = "SANDBOX_REQUIRED"`; FR50 exit code 77 (EX_NOPERM; contract L66). **Phase-1 home: `src/AgentEval/security/policy.py`** per Story 1a.1's pre-`errors.py` baseline; the class does NOT yet inherit from `AgentEvalSafetyError` (re-homing into `src/AgentEval/errors.py` under `AgentEvalSafetyError` is a Phase-1.5 hygiene carry-over tracked in `_bmad-output/implementation-artifacts/deferred-work.md`). The Story 1b.3 code-review caught a contract-self-disagreement where this row previously claimed the `errors.py` home was already in effect — corrected per the citation-drift fix-the-losing-source norm.

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
