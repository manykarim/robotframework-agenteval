# Error Class Hierarchy

**Status:** Phase-1 skeleton — substantive content authored 2026-05-18 by Story 1a.4 (FR59 requirement + 11-leaf ADR-014 table). Class implementations land in Epic 1b + each cross-cutting epic.
**Owning epic:** authored by Story 1a.4; implementations by Epic 1b + each cross-cutting epic
**Related ADRs:** ADR-014 (Error-Class Hierarchy — the canonical 4 sub-bases + 11 leaves)
**Related FRs:** FR59 (Tier-1 setup-failure error format), FR49 (JUnit XML emission via `error_code`), FR50 (Exit-code mapping)

## Purpose

Documents agenteval's **unified error hierarchy** as a publishable consumer-facing contract. Every error agenteval raises inherits from `AgentEvalError` (a common base with a structured `error_code: str` class attribute). 4 semantic sub-bases enable selective programmatic catch (`try/except AgentEvalBudgetError` to retry with smaller scope; `try/except AgentEvalIntegrityError` to fail fast). 19 leaves at 4 sub-bases (incremented to 12 by Story 2.1, 14 by Story 2.2, 16 by Story 2.3, 17 by Story 3.2, 18 by Story 4.3, 19 by Story 4.4 pre-authoring amendments). The contract is the single source contributors + consumers consult when (a) catching agenteval errors, (b) authoring the JUnit XML emitter, (c) implementing the `agenteval` CLI exit-code mapping per FR50.

## Scope

### In-scope

- The `AgentEvalError(Exception)` base class + its `error_code: str` class attribute requirement.
- The 4 semantic sub-bases (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`) + which leaves attach to which sub-base.
- All 11 leaves (named below) + their `error_code` values + the epic that implements each.
- The FR59 error-format requirement: every Tier-1 setup-failure error MUST surface `(file path, line number, field name at fault, fix suggestion if applicable)` in its `__str__` representation.
- The FR50 exit-code mapping: which sub-base → which exit code.
- The FR49 `<failure type="...">` mapping: each leaf's `error_code` value drives the attribute.

### Out-of-scope

- Generic Python exceptions (`ValueError`, `KeyError`, etc.) — these are caught + re-wrapped into appropriate `AgentEvalError` leaves at module boundaries; consumers should not catch the raw Python exceptions for agenteval-owned operations.
- RF-internal errors (`RobotError` subclasses) — agenteval errors do NOT inherit from RF internals per ADR-014's "no RF coupling" decision.
- Adapter implementations' internal exception types — adapters may raise their own internal exceptions but MUST surface them as `AgentEvalError` leaves at the public-keyword boundary.

## Contract

### Base class

```python
class AgentEvalError(Exception):
    """Common base for every error agenteval raises.

    Attributes:
        error_code: Stable string identifier for this error class.
            Set as a CLASS attribute on each leaf (NOT instance).
            Drives FR49 (JUnit XML <failure type="...">) and FR50 (exit-code mapping).
    """
    error_code: str = "AGENTEVAL_ERROR"  # base default; leaves override
```

### 4 sub-bases + 11 leaves (per ADR-014; authoritative count from the leaf table, not the prose)

FR50 exit codes use **sysexits.h-style per-leaf mapping** (ratified 2026-05-18 per Story 1a.4 code-review HIGH-6; PRD draft and earlier ADR-014 prose used family codes 1/2/3 — superseded). Per-leaf codes anchored in the per-leaf inventory below.

| Sub-base | Leaves |
| --- | --- |
| `AgentEvalSafetyError(AgentEvalError)` | `SandboxRequiredError`, `ValidateOperatorDisallowed` |
| `AgentEvalBudgetError(AgentEvalError)` | `CostExceededError`, `RuntimeBudgetExceededError` |
| `AgentEvalCompatError(AgentEvalError)` | `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `AdapterDiscoveryError`, `AdapterVersionDriftWarning`, `MCPConnectionLostError` |
| `AgentEvalIntegrityError(AgentEvalError)` | `PollingDisallowedError`, `IncompleteTraceError`, `TierViolationError`, `InvalidSkillFrontmatterError`, `InvalidSubagentDefinitionError`, `InvalidHookConfigError`, `InvalidMCPServerConfigError`, `InvalidMCPToolSchemaError`, `InvalidScenarioYAMLError`, `InvalidDiscoverabilityTasksError` |

**Total: 19 leaves** (Safety: 2 + Budget: 2 + Compat: 5 + Integrity: 10). Story 2.1 added `InvalidSkillFrontmatterError`; Story 2.2 added `InvalidSubagentDefinitionError` + `InvalidHookConfigError`; Story 2.3 added `InvalidMCPServerConfigError` + `InvalidMCPToolSchemaError` (all Tier-1 setup-failure semantics, parallel to `InvalidSkillFrontmatterError`); Story 3.2 added `MCPConnectionLostError` (Compat-family runtime leaf, parallel to `UnsupportedMCPVersionError`); Story 4.3 added `InvalidScenarioYAMLError` (Tier-1 setup-failure semantics, parallel to `InvalidMCPServerConfigError` — scenario-YAML parse + schema validation failures); Story 4.4 added `InvalidDiscoverabilityTasksError` (Tier-1 setup-failure semantics, parallel to `InvalidScenarioYAMLError` — discoverability tasks YAML parse + schema validation failures). Adding additional leaves requires ADR amendment per ADR-014 §Decision.

### Per-leaf inventory (error_code + exit_code + one-line description + owning epic)

Exit codes are **sysexits.h-aligned per-leaf** (ratified 2026-05-18 per Story 1a.4 code-review HIGH-6 + epics.md Story 8a.1 L1660; PRD draft used family codes 1/2/3 — superseded). Four leaves are pinned by epics.md Story 8a.1 (`65`/`66`/`67`/`68`); the remaining seven get sysexits.h-aligned codes ratified here by Story 1a.4.

#### AgentEvalSafetyError family

| Leaf | `error_code` | Exit code | One-line description | Owning epic |
| --- | --- | --- | --- | --- |
| `SandboxRequiredError` | `SANDBOX_REQUIRED` | `77` (EX_NOPERM) | Code-execution scenario requested without a configured non-null sandbox backend. | ADR-018 / Story 1a.1 stub; Story 1a.6 wires default; Epic 6 enforces |
| `ValidateOperatorDisallowed` | `VALIDATE_OPERATOR_DISALLOWED` | `77` (EX_NOPERM) | `validate` assertion operator used without explicit `allow_validate_operator=True` opt-in (FR43). | Story 1a.6 wires the default; Epic 6 Story 6.3 enforces |

#### AgentEvalBudgetError family

| Leaf | `error_code` | Exit code | One-line description | Owning epic |
| --- | --- | --- | --- | --- |
| `CostExceededError` | `COST_EXCEEDED` | `66` (sysexits-extended; pinned by epics.md L1660) | Tier-3 fan-out keyword exceeded the configured `AGENTEVAL_MAX_COST_USD` budget (per ADR-015 `@guarded_fanout`). | **IMPLEMENTED — Story 1b.3 (`src/AgentEval/errors.py` leaf + `src/AgentEval/_kernel/guardrails.py` raise site). Story 4.1 wires the real LiteLLM cost source; Epic 6 keyword wiring extends adoption.** |
| `RuntimeBudgetExceededError` | `RUNTIME_BUDGET_EXCEEDED` | `75` (EX_TEMPFAIL) | Tier-3 fan-out keyword exceeded the configured `AGENTEVAL_MAX_RUNTIME_SECONDS` budget. | **IMPLEMENTED — Story 1b.3 (`src/AgentEval/errors.py` leaf + `src/AgentEval/_kernel/guardrails.py` raise site).** Epic 6 keyword wiring extends adoption. |

#### AgentEvalCompatError family

| Leaf | `error_code` | Exit code | One-line description | Owning epic |
| --- | --- | --- | --- | --- |
| `UnsupportedMCPVersionError` | `UNSUPPORTED_MCP_VERSION` | `68` (sysexits-extended; pinned by epics.md L1660) | Negotiated MCP spec version is outside the supported `mcp>=1.0,<2.0` range (per ADR-008). | **Epic 3 Story 3.1** (MCP server lifecycle keywords incl. spec-version gate per FR46 / AC-MCP-OBSERVE-02) |
| `UnsupportedBinaryVersionError` | `UNSUPPORTED_BINARY_VERSION` | `78` (EX_CONFIG) | CLI adapter detected a binary version outside the adapter's pinned range (e.g., `copilot` outside `>=1.0.9,<2.0` per ADR-010). | Class declaration in **Story 1b.4** (`src/AgentEval/errors.py` leaf + `_assert_binary_version` helper in `SubprocessAdapter`); per-adapter raise sites in **Epic 4 Story 4.2** (Claude Code CLI) + **Epic 11 Story 11.3** (Copilot CLI). |
| `AdapterDiscoveryError` | `ADAPTER_DISCOVERY_ERROR` | `78` (EX_CONFIG) | Entry-points discovery encountered a partially-installed adapter package (per ADR-013). | **IMPLEMENTED — Story 1b.3 (`src/AgentEval/errors.py` leaf + `src/AgentEval/_kernel/discovery._discover_entry_point_group` raise site + `get_adapter` miss path).** |
| `AdapterVersionDriftWarning` | `ADAPTER_VERSION_DRIFT` | `0` (warning, not failure — emitted via RF Listener log, no exit-fail) | Adapter shipped against an older MCP SDK; observer's `request_handlers` dict-wrap pattern may no longer match (per ADR-004 Consequences). | Epic 11 Story 11.3 |
| `MCPConnectionLostError` | `MCP_CONNECTION_LOST` | `69` (sysexits-extended; same family as `UnsupportedMCPVersionError` L80 = 68 — Compat-family runtime errors) | MCP client session lost connection mid-call (subprocess crash, transport disconnect, anyio cancel scope failure). Distinct from `IncompleteTraceError` (Integrity-family setup-time) — this is a runtime connection failure during `MCP.Call Tool` or `MCP.List Tools`. Surfaces `server_name` + `last_operation` structured attrs for diagnostic logging. | **Epic 3 Story 3.2** (MCP tool inspection keywords; first per-call-session connection-loss raise site). |

#### AgentEvalIntegrityError family

| Leaf | `error_code` | Exit code | One-line description | Owning epic |
| --- | --- | --- | --- | --- |
| `PollingDisallowedError` | `POLLING_DISALLOWED` | `65` (EX_DATAERR; pinned by epics.md L1660) | Tier-2/3 keyword called with a retry-style polling pattern; banned per `determinism-contract.md`. | **Class declaration IMPLEMENTED in Story 1b.6** (`src/AgentEval/errors.py` leaf alongside the `determinism-contract.md` FR63 publication); raise site lands in **Epic 6** (FR28 enforcement at `_assertions/adapter.py`; Phase-2 full ADR-022 AssertionEngine adoption). |
| `IncompleteTraceError` | `INCOMPLETE_TRACE` | `67` (sysexits-extended; pinned by epics.md L1660) | Metric keyword called on an `AgentRunResult` with `mcp_coverage="external_mixed"` without `allow_external_mcp_blind=True` opt-out (per ADR-007 + ADR-016). | **IMPLEMENTED — Story 1b.2 (`src/AgentEval/errors.py`); raise site at `src/AgentEval/_kernel/coverage._check_mcp_coverage`. Owning Epic 5 Story 5.2 wires it through the Metric.* keyword paths.** |
| `TierViolationError` | `TIER_VIOLATION` | `70` (EX_SOFTWARE) | A Tier-N keyword embedded a forbidden Tier-M call (Tier-1 may not call Tier-2/3; Tier-2 may not embed Tier-3 fan-out per `determinism-contract.md`). | **Class declaration IMPLEMENTED in Story 1b.6** (`src/AgentEval/errors.py` leaf alongside `determinism-contract.md` Tier Model ACL gates); raise site lands in **Epic 6** (FR30b enforcement). |
| `InvalidSkillFrontmatterError` | `INVALID_SKILL_FRONTMATTER` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | Skill `.md` file's YAML frontmatter is malformed or missing required fields. Format per FR59: `(file path, line number, field name at fault, fix suggestion)`. | **Story 2.1** (Skill static-inspection keywords); catalog amendment Story 2.1 pre-authoring 2026-05-19. 12th ratified leaf (was 11 prior). |
| `InvalidSubagentDefinitionError` | `INVALID_SUBAGENT_DEFINITION` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | Sub-agent `.md` file's YAML frontmatter is malformed or missing required fields per PRD FR3 (`name`, `description`, optionally `tools`, `model`). Format per FR59 + L96-104 (file/line/field/fix). | **Story 2.2** (Subagent + Hook static-inspection keywords); catalog amendment Story 2.2 pre-authoring 2026-05-19. 13th ratified leaf. |
| `InvalidHookConfigError` | `INVALID_HOOK_CONFIG` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | `settings.json` file is malformed JSON OR a `hooks.<event>` entry is missing required fields per PRD FR4 (`command`; optionally `args`, `timeout`, `matcher`). The `field_name` attribute carries a JSON Pointer (RFC 6901) into the offending location (e.g., `/hooks/PreToolUse/0/command`) so callers can pinpoint nested-JSON errors — this is the FR4-equivalent of FR6's JSON Pointer requirement for `InvalidMCPToolSchemaError`. Format otherwise per FR59 + L96-104. | **Story 2.2** (Subagent + Hook static-inspection keywords); catalog amendment Story 2.2 pre-authoring 2026-05-19. 14th ratified leaf. |
| `InvalidMCPServerConfigError` | `INVALID_MCP_SERVER_CONFIG` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | `.mcp.json` file is malformed JSON OR a server entry is missing required fields per PRD FR5 (`command`; optionally `args`, `env`, `transport`). The `field_name` attribute carries a JSON Pointer (RFC 6901) into the offending location (e.g., `/mcpServers/echo/command`). Transport values restricted to `stdio`, `streamable_http`, `in_memory` per FR7. Format per FR59 + L96-104. | **Story 2.3** (MCP static-inspection keywords); catalog amendment Story 2.3 pre-authoring 2026-05-19. 15th ratified leaf. |
| `InvalidMCPToolSchemaError` | `INVALID_MCP_TOOL_SCHEMA` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | An MCP tool's input JSON Schema is malformed per the jsonschema Draft 2020-12 meta-schema OR the requested tool is not declared in the `.mcp.json:tools` extension. Phase-1 reads tool schemas from a declarative `tools: { <tool_name>: <json_schema> }` extension on the server entry (Phase-2 + Epic 3 will retrieve schemas from running MCP servers per FR6). The `field_name` attribute carries a JSON Pointer (RFC 6901) into the offending location (e.g., `/mcpServers/echo/tools/search/properties/query`). The PRD-locked error: PRD FR6 names this leaf + the JSON Pointer requirement. Format per FR59 + L96-104. | **Story 2.3** (MCP static-inspection keywords); catalog amendment Story 2.3 pre-authoring 2026-05-19. 16th ratified leaf. |
| `InvalidScenarioYAMLError` | `INVALID_SCENARIO_YAML` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | A scenario YAML file passed to `Run Scenario` is malformed YAML, OR fails schema validation per PRD FR15 L1514 shape (`model`, `provider`, `agent`, `mcp_servers`, `evals[]` with `prompt`, `repeat`, `expect:`, optional `judge:`), OR a required field is missing/wrong-type. The `field_name` attribute carries a JSON Pointer (RFC 6901) into the offending location (e.g., `/evals/0/prompt`). Format per FR59 + L96-104. | **Story 4.3** (orchestration keywords); catalog amendment Story 4.3 pre-authoring 2026-05-20. 18th ratified leaf. |
| `InvalidDiscoverabilityTasksError` | `INVALID_DISCOVERABILITY_TASKS` | `65` (EX_DATAERR; same as other Tier-1 setup-failure errors) | A discoverability tasks YAML file passed to `MCP.Get Tool Discoverability` (PRD FR10a) is malformed YAML, OR fails schema validation, OR a required per-task field (`id`, `prompt`) is missing/wrong-type, OR `expected_tools` is not a list of strings when present. The `field_name` attribute carries a JSON Pointer (RFC 6901) into the offending location (e.g., `/tasks/0/prompt`). Format per FR59 + L96-104. | **Story 4.4** (MVP Tool Discoverability); catalog amendment Story 4.4 pre-authoring 2026-05-20. 19th ratified leaf. |

### FR59 error-format requirement (Tier-1 setup-failure errors)

Every Tier-1 setup-failure error MUST format its message per FR59:

```
<error-code>: <one-line summary>
  File: <absolute or repo-relative path>
  Line: <line number> (or N/A if not line-specific)
  Field: <YAML/config field name at fault> (or N/A)
  Fix: <one-line remediation hint> (optional but strongly preferred)
```

Example:

```
SANDBOX_REQUIRED: Tier-3 code-execution scenario requires a sandbox backend.
  File: tests/scenarios/code_execution.robot
  Line: 42
  Field: scenario.requires_sandbox
  Fix: Register a sandbox backend via the `agenteval.sandboxes` entry-point group (per ADR-018 + ADR-013). Phase 1 ships only the `NullSandbox` default (always refuses); real backends register via separate consumer-installed packages.
```

Tier-2 + Tier-3 errors (runtime, not setup-failure) are NOT subject to FR59 — they format per their domain (cost/runtime/MCP-coverage contexts).

### FR49 + FR50 mapping (one-stop lookup)

- **FR49 JUnit XML:** `<failure type="<error_code>">` attribute = the leaf's `error_code` class attribute. Renderers (GitHub Actions test-reporter, Jenkins JUnit plugin, Allure) surface this as the failure category.
- **FR50 exit codes (sysexits.h-style per-leaf):** the per-leaf table above is the authoritative source. The `agenteval` CLI's exit-code translation layer (Phase-1.5; not yet implemented as of Story 2.1) will read each leaf's exit-code mapping from THIS contract table — NOT yet from a `exit_code: ClassVar[int]` attribute on the leaf classes. The pre-Story-2.1 wording "set per ADR-014 on each leaf" was aspirational; Story 1b.6's leaf classes (`PollingDisallowedError`, `TierViolationError`, `InvalidSkillFrontmatterError` introduced Story 2.1) + Story 1b.3's budget/compat leaves expose `error_code` only. Adding `exit_code: ClassVar[int]` to each leaf is tracked in `deferred-work.md` as a Phase-1.5 hygiene pass to coincide with the CLI's exit-code translation layer landing (Epic 8a Story 8a.1). Until then, the CLI implementation consults THIS table by `error_code` string lookup. 4 leaves are pinned by epics.md Story 8a.1 L1660 (`PollingDisallowedError` = 65, `CostExceededError` = 66, `IncompleteTraceError` = 67, `UnsupportedMCPVersionError` = 68); the other 12 use sysexits.h-aligned codes ratified by Story 1a.4 (77 EX_NOPERM for safety errors, 78 EX_CONFIG for config errors, 75 EX_TEMPFAIL for runtime budget, 70 EX_SOFTWARE for tier violation, 65 EX_DATAERR for `InvalidSkillFrontmatterError` + `InvalidSubagentDefinitionError` + `InvalidHookConfigError` + `InvalidMCPServerConfigError` + `InvalidMCPToolSchemaError` (the 5 Tier-1 setup-failure data errors); `AdapterVersionDriftWarning` is a warning, exit 0). PRD draft FR50 used family codes 1/2/3 — superseded 2026-05-18.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels.

- The **`AgentEvalError` base class + the 4 sub-bases** are `stable` from Phase-1 onward. Renaming or restructuring requires major-version bump per NFR-MAINT-03.
- The **19 leaves' names + `error_code` values** are `stable` (Story 4.4 pre-authoring 2026-05-20: count incremented from 18 after adding `InvalidDiscoverabilityTasksError`; pre-existing "11 leaves" drifts at L5 / L18 / L45 and ADR-014 L32 acknowledged at L150 known-debt note remain pending Phase-1.5 batch amendment). Adding new leaves is minor-version-bump safe (consumers' `try/except AgentEvalError` still catches the new leaf via inheritance). Renaming a leaf or changing its `error_code` is a major-version-bump change (breaks consumers' specific catches).
- The **FR59 error-format string** is `provisional` in Phase 1 (Story 1a.1 stub provided; concrete content evolves as the implementing epics author per-error messages). Format-string changes that preserve the 4 required pieces (`File`, `Line`, `Field`, `Fix`) are minor-version-bump safe.
- The **FR50 exit-code mapping** is `stable` from Phase-1 onward — changes require ADR amendment + a documented migration path for CI consumers depending on specific exit codes.

## References

- **ADR-014: Error-Class Hierarchy** (`docs/adr/ADR-014-error-class-hierarchy.md`) — the canonical hierarchy + this contract's authoritative source.
- **FR59 (PRD)**: Tier-1 setup-failure error format requirement.
- **FR49 (PRD)**: JUnit XML emission via `error_code`.
- **FR50 (PRD)**: Exit-code mapping.
- **ADR-007**: `IncompleteTraceError` raised on `mcp_coverage="external_mixed"`.
- **ADR-008**: `UnsupportedMCPVersionError` raised on out-of-range MCP spec.
- **ADR-013**: `AdapterDiscoveryError` raised on partial-install detection.
- **ADR-015**: `CostExceededError` + `RuntimeBudgetExceededError` raised by `@guarded_fanout`.
- **ADR-018**: `SandboxRequiredError` raised by sandbox-required keywords.
- **agentguard ADR-022 row** in `docs/adr/ADR-001-architectural-influences-catalog.md`: AssertionEngine adoption → `PollingDisallowedError` + `ValidateOperatorDisallowed` enforcement.

> **Known debt (carried from Story 1a.3 LOW-1, deferred per Many's review):** ADR-014 §Decision bullet says "9 leaves explicitly named" but the table names 11. This contract's count (11) matches the table — the authoritative source. ADR-014's prose drift is registered debt for a future cleanup pass (likely Story 1a.5 hygiene or dedicated debt batch).
