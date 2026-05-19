# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AgentEval error class hierarchy (ADR-014 / was ADR-A3).

Story 1b.2 ships the MINIMAL subset of the catalog needed by
`_kernel/coverage._check_mcp_coverage()`:

- `AgentEvalError(Exception)` — common base class for all agenteval-raised
  errors. Consumers can `try / except AgentEvalError` to catch any error from
  the library.
- `AgentEvalIntegrityError(AgentEvalError)` — sub-base for errors signaling
  that a run's trace/integrity contract is compromised (e.g., uninstrumented
  MCP usage detected, span data partial). Per ADR-014's 4-sub-base scheme.
- `IncompleteTraceError(AgentEvalIntegrityError)` — raised by the kernel's
  `_check_mcp_coverage` gate per FR37 + ADR-016 L44 when a run reports
  `mcp_coverage == "external_mixed"` without `allow_external_mcp_blind=True`.

Story 1b.4 EXTENDS this module with 1 new leaf (pure addition):

- `UnsupportedBinaryVersionError(AgentEvalCompatError)` — class declaration
  per Story 1b.3 `errors.py` L59 forward-ref; raised by per-adapter pin
  enforcement in Epic 4 Story 4.2 (Claude Code CLI) + Epic 11 Story 11.3
  (Copilot CLI) per the `error-class-hierarchy.md` L81 ownership row
  (amended pre-Story-1b.4-authoring). `SubprocessAdapter._assert_binary_version`
  helper (Story 1b.4 base.py) provides the generic Phase-1 raise site.

Story 1b.3 EXTENDED this module with 2 new sub-bases + 4 new leaves (pure
addition, no refactor of Story 1b.2's classes):

- `AgentEvalBudgetError(AgentEvalError)` — sub-base for cost/runtime budget
  breaches.
- `AgentEvalCompatError(AgentEvalError)` — sub-base for environment/version
  /compat issues.
- `CostExceededError(AgentEvalBudgetError)` — raised by
  `_kernel/guardrails.@guarded_fanout` Layer 1 + Layer 2.
- `RuntimeBudgetExceededError(AgentEvalBudgetError)` — raised by Layer 1 + Layer 3.
- `AdapterDiscoveryError(AgentEvalCompatError)` — raised by
  `_kernel/discovery.{_discover_entry_point_group, get_adapter}` on partial-install
  + lookup-miss. Exposes a `loaded_so_far: dict[str, type]` attribute so
  callers can recover the successfully-loaded adapters from a partial-failure
  scan (per ADR-013 L42 verbatim contract, restored after Story 1b.3 code
  review caught the docstring vs implementation drift).
- `DuplicateRegistrationError(AdapterDiscoveryError)` — raised by
  `_kernel/discovery._cached_coding_agents` when the same adapter name is
  declared across `agenteval.coding_agents` (primary) AND
  `robotframework_agenteval.adapters` (legacy) — per ADR-013 L43's
  "agenteval refuses to silently pick one" contract. Exposes the conflicting
  source-package names via `sources: tuple[str, str]` (primary first, legacy
  second).

The remaining 6 leaves from `docs/contracts/error-class-hierarchy.md` (Story
1a.4 ratified catalog) are added to this module as subsequent stories need them:

- `UnsupportedMCPVersionError` — Epic 3 Story 3.1 (MCP transport)
- `ValidateOperatorDisallowed` — Epic 6 Story 6.2 (assertion gate enforcement)
- `AdapterVersionDriftWarning` — Epic 11 Story 11.3 (warning, not error)

Special case (separate paragraph because the Phase-1 home differs):

- `SandboxRequiredError` — currently lives at `src/AgentEval/security/policy.py`
  per Story 1a.1's pre-`errors.py` baseline; does NOT yet inherit from
  `AgentEvalError`. Re-homing into this module under `AgentEvalSafetyError`
  is a Phase-1.5 hygiene carry-over tracked in
  `_bmad-output/implementation-artifacts/deferred-work.md`.

The 3-class structure in this story is extension-friendly: future stories
ADD leaves (and, if needed, the other 3 sub-bases `AgentEvalSafetyError`,
`AgentEvalBudgetError`, `AgentEvalCompatError`) without refactoring the
existing 3 classes.

`error_code` convention (architecture L902-906):
    Every error class sets a static `error_code: ClassVar[str]` attribute
    matching the pattern `<DOMAIN>_<ACTION>` (uppercase). This is used by the
    JUnit XML emitter (FR49) + exit-code mapper (FR50) for structured
    machine-readable error identification.

References:
    - ADR-014 (was ADR-A3): `docs/adr/ADR-014-error-class-hierarchy.md`
    - ADR-016 L44: `docs/adr/ADR-016-mcp-coverage-detection-default.md`
      (defines the IncompleteTraceError raise contract)
    - docs/contracts/error-class-hierarchy.md (Story 1a.4 ratified catalog)
    - PRD FR37 — `IncompleteTraceError` on `external_mixed` runs
    - architecture L376, L902-930, L1184 — base + sub-base + leaf structure
"""

from __future__ import annotations

from typing import ClassVar

__all__ = [
    # Base (1):
    "AgentEvalError",
    # Sub-bases (3 of 4 ratified — Safety still pending):
    "AgentEvalIntegrityError",
    "AgentEvalBudgetError",
    "AgentEvalCompatError",
    # Leaves (11 implemented; 3 future per module docstring):
    "IncompleteTraceError",
    "PollingDisallowedError",
    "TierViolationError",
    "InvalidSkillFrontmatterError",
    "InvalidSubagentDefinitionError",
    "InvalidHookConfigError",
    "CostExceededError",
    "RuntimeBudgetExceededError",
    "AdapterDiscoveryError",
    "DuplicateRegistrationError",
    "UnsupportedBinaryVersionError",
    # Warnings (1):
    "DegradedTraceWarning",
]


class AgentEvalError(Exception):
    """Common base class for all errors raised by agenteval.

    Consumers can `try / except AgentEvalError` to catch any error from the
    library, then narrow with `isinstance` on the leaf class for typed
    handling.

    Subclasses MUST set `error_code: ClassVar[str]` matching `<DOMAIN>_<ACTION>`
    uppercase. The base class itself uses an empty string so consumers can
    safely read `error_code` without an AttributeError on the rare instance
    that the base is raised directly (which they shouldn't — always raise a
    leaf).

    `__str__` format (per Story 1b.2 code-review H_R7 fix): when `error_code`
    is non-empty, render as `f"{error_code}: {message}"`. This makes downstream
    FR49 JUnit XML emission + FR50 exit-code mapping pull the prefix from
    str(exc) directly. Base instances (rare; consumers shouldn't raise the
    base) keep the bare-Exception `__str__`.
    """

    error_code: ClassVar[str] = ""

    def __str__(self) -> str:
        base = super().__str__()
        if self.error_code:
            return f"{self.error_code}: {base}"
        return base


class AgentEvalIntegrityError(AgentEvalError):
    """Sub-base for errors signaling that a run's trace/integrity contract is compromised.

    Per ADR-014's 4-sub-base scheme: `AgentEvalSafetyError`,
    `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`.
    Story 1b.2 ships only the Integrity sub-base; others are added by the
    stories that need them.

    Integrity errors typically signal:
        - Partial / missing trace data (e.g., `IncompleteTraceError`)
        - Determinism violations (Story 1b.6 will add `TierViolationError`)
        - Run-state contract violations (e.g., adapter reports impossible state)
    """


class IncompleteTraceError(AgentEvalIntegrityError):
    """Raised when a run's trace coverage is insufficient to compute reliable metrics.

    Per FR37 + ADR-016 L44: the kernel's `_check_mcp_coverage()` gate raises this
    when `AgentRunResult.metadata.mcp_coverage == "external_mixed"` AND the
    Library was NOT constructed with `allow_external_mcp_blind=True`.

    The error message includes:
        - What failed (uninstrumented MCP usage detected)
        - Why it failed (the adapter reported `external_mixed`)
        - One-line remediation (pass `allow_external_mcp_blind=True` OR fix
          the adapter coverage; link to `docs/contracts/mcp-coverage-detection.md`)

    Used as the default-deny posture per ADR-016's "loud refusal beats silent
    half-truth" principle.
    """

    error_code: ClassVar[str] = "INCOMPLETE_TRACE"


class PollingDisallowedError(AgentEvalIntegrityError):
    """Raised when a Tier-2/3 keyword receives a `polling=` argument.

    Per PRD FR28 L1536 + ADR-022 catalog row (AssertionEngine adoption —
    polling-ban negative-consequence clause) + `docs/contracts/error-class-hierarchy.md`
    L89: polling masks non-determinism by retrying-until-pass, defeating
    the statistical-interpretability requirement of FR31b. Tier-1 keywords
    MAY accept `polling=`; Tier-2/3 MUST NOT.

    Phase-1 (Story 1b.6): class declaration ships in `errors.py`. The
    raise site lands when `_assertions/adapter.py` is implemented in Epic
    6 (Tier-3 fan-out + statistical keywords). Per the
    `determinism-contract.md` §(c) contract, this class is FORWARD-REFERENCED
    by the contract document; the contract publishes Day 1 + the raise
    site compounds in Epic 6.

    `error_code = "POLLING_DISALLOWED"`; exit code 65 (EX_DATAERR; pinned
    by epics.md Story 8a.1 L1660).
    """

    error_code: ClassVar[str] = "POLLING_DISALLOWED"


class TierViolationError(AgentEvalIntegrityError):
    """Raised when a Tier-N keyword embeds a forbidden Tier-M call.

    Per `docs/contracts/error-class-hierarchy.md` L91 + Story 1b.6
    `determinism-contract.md` Tier Model ACL gates: Tier-1 keywords may
    NOT call Tier-2/3 keywords internally; Tier-2 keywords may NOT embed
    Tier-3 fan-outs. Phase-1 (Story 1b.6): class declaration ships in
    `errors.py`. The raise site lands when convention enforcement reaches
    runtime in Epic 6 (alongside `PollingDisallowedError`).

    `error_code = "TIER_VIOLATION"`; exit code 70 (EX_SOFTWARE).
    """

    error_code: ClassVar[str] = "TIER_VIOLATION"


class _FR59Tier1SetupFailureError(AgentEvalIntegrityError):
    """Private intermediate base for all Tier-1 setup-failure errors.

    Story 2.2 refactor (2026-05-19): factored out from
    `InvalidSkillFrontmatterError` so siblings `InvalidSubagentDefinitionError`
    + `InvalidHookConfigError` (Story 2.2) — and future Tier-1 setup
    failures — inherit the structured `(file_path, line_number,
    field_name, fix_suggestion)` attrs + FR59 4-line `__str__` shape
    without duplicating ~40 LoC each.

    NOT in `__all__`: this is private machinery. Consumers catch the
    public sub-base (`AgentEvalIntegrityError`) OR a specific leaf;
    they should never name this intermediate class.

    Subclasses MUST override `error_code: ClassVar[str]` with their
    domain-specific identifier. The `__str__` shape is per FR59 +
    `docs/contracts/error-class-hierarchy.md` L96-104.
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        field_name: str | None = None,
        fix_suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path: str | None = file_path
        self.line_number: int | None = line_number
        self.field_name: str | None = field_name
        self.fix_suggestion: str | None = fix_suggestion

    def __str__(self) -> str:
        # FR59-exact multi-line setup-failure format per
        # `docs/contracts/error-class-hierarchy.md` L96-104; overrides
        # the base H_R7 `error_code: <message>` shape because FR59
        # specifies the verbatim layout for Tier-1 setup-failure errors.
        message = Exception.__str__(self)
        return (
            f"{self.error_code}: {message}\n"
            f"  File: {self.file_path if self.file_path else 'N/A'}\n"
            f"  Line: {self.line_number if self.line_number is not None else 'N/A'}\n"
            f"  Field: {self.field_name if self.field_name else 'N/A'}\n"
            f"  Fix: {self.fix_suggestion if self.fix_suggestion else 'N/A'}"
        )


class InvalidSkillFrontmatterError(_FR59Tier1SetupFailureError):
    """Raised when a skill `.md` file's YAML frontmatter is malformed or incomplete.

    Per `docs/contracts/error-class-hierarchy.md` L92 (12th leaf, ratified
    2026-05-19 pre-Story-2.1 catalog amendment): Tier-1 setup-failure
    semantics. Raised by `src/AgentEval/skills/_parser.py` when:
        - YAML between `---` delimiters fails `yaml.safe_load()`
        - Required fields (`name`, `description`, `allowed-tools`,
          `disable-model-invocation`) are missing
        - Type contract violations (e.g., `allowed-tools` is not a list,
          `disable-model-invocation` is not a bool)
        - File extension is not `.md` or file does not exist

    Inherits the FR59 4-line `__str__` shape + structured attrs
    (`file_path` / `line_number` / `field_name` / `fix_suggestion`)
    from `_FR59Tier1SetupFailureError`. Story 2.2 refactored the
    shared logic out so siblings (`InvalidSubagentDefinitionError`,
    `InvalidHookConfigError`) reuse it.

    `error_code = "INVALID_SKILL_FRONTMATTER"`; exit code 65 (EX_DATAERR;
    same family as other Tier-1 setup-failure errors per epics.md
    Story 8a.1 L1660).
    """

    error_code: ClassVar[str] = "INVALID_SKILL_FRONTMATTER"


class InvalidSubagentDefinitionError(_FR59Tier1SetupFailureError):
    """Raised when a sub-agent `.md` file's YAML frontmatter is malformed or incomplete.

    Per `docs/contracts/error-class-hierarchy.md` L93 (13th leaf, ratified
    2026-05-19 pre-Story-2.2 catalog amendment): Tier-1 setup-failure
    semantics. Raised by `src/AgentEval/subagents/_parser.py` when:
        - YAML between `---` delimiters fails `yaml.safe_load()`
        - Required fields (`name`, `description` per PRD FR3) are missing
        - Type contract violations (e.g., `name` is not a string)
        - File extension is not `.md` or file does not exist

    Optional fields per PRD FR3: `tools` (list[str]; per-agent tool
    allowlist), `model` (str; model-override identifier). The parser
    does NOT validate optional-field types in Phase-1 — that's deferred
    to Phase-2 schema-strict mode.

    `error_code = "INVALID_SUBAGENT_DEFINITION"`; exit code 65 (EX_DATAERR).
    """

    error_code: ClassVar[str] = "INVALID_SUBAGENT_DEFINITION"


class InvalidHookConfigError(_FR59Tier1SetupFailureError):
    """Raised when a `settings.json` hook configuration is malformed or incomplete.

    Per `docs/contracts/error-class-hierarchy.md` L94 (14th leaf, ratified
    2026-05-19 pre-Story-2.2 catalog amendment): Tier-1 setup-failure
    semantics. Raised by `src/AgentEval/hooks/_parser.py` when:
        - JSON fails `json.load()` (malformed JSON)
        - Required per-entry field `command` is missing
        - Type contract violations on `args` (must be list[str]),
          `timeout` (must be int), `matcher` (must be str)
        - File extension is not `.json` or file does not exist

    `field_name` JSON Pointer convention (Story 2.2 pre-authoring
    drift-check D-D 2026-05-19): when a nested-JSON validation fails,
    `field_name` carries an RFC 6901 JSON Pointer string into the
    offending location, e.g., `/hooks/PreToolUse/0/command`. This
    parallels FR6's `InvalidMCPToolSchemaError` JSON Pointer
    convention so consumers have one idiom for both nested-JSON
    Tier-1 setup-failure errors.

    `error_code = "INVALID_HOOK_CONFIG"`; exit code 65 (EX_DATAERR).
    """

    error_code: ClassVar[str] = "INVALID_HOOK_CONFIG"


# --------------------------------------------------------------------------- #
# Budget sub-base + leaves (Story 1b.3 — ADR-015 + contract L73/L74)          #
# --------------------------------------------------------------------------- #


class AgentEvalBudgetError(AgentEvalError):
    """Sub-base for errors signaling that a Tier-3 fan-out keyword breached a budget.

    Per ADR-014's 4-sub-base scheme. Budget errors typically signal:
        - Cost budget breach (`CostExceededError`) — total USD spent during the
          fan-out run exceeded the configured `max_cost_usd`.
        - Runtime budget breach (`RuntimeBudgetExceededError`) — wall-clock
          elapsed exceeded the configured `max_runtime_seconds`.

    Both raised by `_kernel/guardrails.@guarded_fanout` per ADR-015 §Decision.
    """


class CostExceededError(AgentEvalBudgetError):
    """Raised when a Tier-3 fan-out keyword exceeded the configured cost budget.

    Per ADR-015 §Decision L25-29 + docs/contracts/error-class-hierarchy.md L73:
    raised by `@guarded_fanout` at Layer 1 (pre-flight estimation > budget) OR
    Layer 2 (mid-run cumulative cost meter > budget). Error message includes
    the cumulative cost-at-breach so callers can size the budget for next run.

    `error_code = "COST_EXCEEDED"`; exit code 66 (sysexits-extended; pinned by
    epics.md Story 8a.1 L1660).
    """

    error_code: ClassVar[str] = "COST_EXCEEDED"


class RuntimeBudgetExceededError(AgentEvalBudgetError):
    """Raised when a Tier-3 fan-out keyword exceeded the configured runtime budget.

    Per ADR-015 §Decision L25-29 + docs/contracts/error-class-hierarchy.md L74:
    raised by `@guarded_fanout` at Layer 1 (pre-flight runtime estimate > budget)
    OR Layer 3 (mid-run wall-clock elapsed > budget). Layer 3 surfaces on the
    NEXT polling tick after the budget is exceeded — the meter wakes every
    `meter_interval_seconds` (default 5.0s; tunable per-decoration), so an
    elapsed-time breach is observed at most `meter_interval_seconds` after the
    actual budget threshold. The pre-Story-1b.3-review wording "raised at
    EXACTLY the configured budget" was retracted at code review when the
    polling-loop reality was traced through the implementation.

    `error_code = "RUNTIME_BUDGET_EXCEEDED"`; exit code 75 (EX_TEMPFAIL).
    """

    error_code: ClassVar[str] = "RUNTIME_BUDGET_EXCEEDED"


# --------------------------------------------------------------------------- #
# Compat sub-base + leaves (Story 1b.3 — ADR-013 + contract L82)              #
# --------------------------------------------------------------------------- #


class AgentEvalCompatError(AgentEvalError):
    """Sub-base for errors signaling environment / version / compat issues.

    Per ADR-014's 4-sub-base scheme. Compat errors typically signal:
        - `UnsupportedMCPVersionError` (Epic 3 Story 3.1; not yet implemented)
        - `UnsupportedBinaryVersionError` (Story 1b.4) — class declaration in
          `errors.py`; per-adapter raise sites in Epic 4 Story 4.2 (Claude
          Code CLI) + Epic 11 Story 11.3 (Copilot CLI)
        - `AdapterDiscoveryError` (Story 1b.3) — entry-points discovery failure
        - `AdapterVersionDriftWarning` (Epic 11 Story 11.3; warning, not error)
    """


class AdapterDiscoveryError(AgentEvalCompatError):
    """Raised by `_kernel/discovery.py` on entry-points discovery failures.

    Two raise sites per Story 1b.3:
        1. **Partial-install detection** (ADR-013 L42): one or more entry-points
           in `agenteval.coding_agents` (or another agenteval.* group) point at
           modules that can't be imported (e.g., the adapter package's extras
           weren't installed). The scan is RESILIENT — it continues past each
           per-entry failure, collects successes into `loaded_so_far`, and
           raises this aggregated error only after the entire group is scanned.
           Error message includes the `installed-vs-required-extras` diagnostic
           hint for each failing entry-point.
        2. **Lookup miss** in `get_adapter(name)`: no adapter registered under
           the given name across the programmatic + primary + legacy lookup
           precedence. Error message lists the known adapter names. (For this
           case `loaded_so_far` is the empty dict.)

    `UnknownAdapterError` (used in the pre-edit story spec) is NOT in the
    ratified catalog; this single leaf covers both cases per the Story 1b.3
    create-story drift-check decision (D4). Future stories may add a sub-leaf
    if the unknown-name vs broken-import distinction becomes load-bearing for
    callers (see Phase-1.5 `deferred-work.md` DF1).

    `error_code = "ADAPTER_DISCOVERY_ERROR"`; exit code 78 (EX_CONFIG).

    `loaded_so_far` attribute (Story 1b.3 code-review fix): on partial-install
    scans this holds the dict of successfully-loaded `{entry_name: cls}` so
    callers can opt into "best-effort" behavior. On lookup-miss this is `{}`.
    """

    error_code: ClassVar[str] = "ADAPTER_DISCOVERY_ERROR"

    def __init__(self, message: str, *, loaded_so_far: dict[str, type] | None = None) -> None:
        super().__init__(message)
        self.loaded_so_far: dict[str, type] = dict(loaded_so_far) if loaded_so_far else {}


class DuplicateRegistrationError(AdapterDiscoveryError):
    """Raised when the same adapter name is declared in BOTH primary + legacy groups.

    Per ADR-013 L43 verbatim: "Duplicate-name collisions across packages
    produce a `DuplicateRegistrationError(AdapterDiscoveryError)` with both
    source package names; agenteval refuses to silently pick one."

    Story 1b.3 code review caught the pre-edit implementation's drift from
    this contract — the original code used `warnings.warn` + primary-wins,
    which the ADR explicitly forbids. Cross-package collisions now raise this
    typed error fail-closed so consumers cannot accidentally depend on a
    non-deterministic resolution.

    Intra-group collisions within ONE entry-point group (same name declared
    twice in `agenteval.coding_agents`, for example) are a different
    operational class — handled by the PyPA installer's metadata uniqueness
    rules, not this exception. If the installer accepts such a duplicate
    anyway, the `_cached_coding_agents` scan emits a UserWarning + lets the
    last-wins (which is what stdlib `dict.update` semantics already do).

    `sources` attribute: 2-tuple of `(primary_dist_name, legacy_dist_name)`
    or `("primary", "legacy")` if dist names cannot be resolved from the
    entry-point metadata. Inherits `loaded_so_far` from the parent.
    """

    def __init__(
        self,
        message: str,
        *,
        sources: tuple[str, str] = ("primary", "legacy"),
        loaded_so_far: dict[str, type] | None = None,
    ) -> None:
        super().__init__(message, loaded_so_far=loaded_so_far)
        self.sources: tuple[str, str] = sources


class UnsupportedBinaryVersionError(AgentEvalCompatError):
    """Raised when a CLI adapter detects a binary version outside its pinned range.

    Per PRD FR47 + `docs/contracts/error-class-hierarchy.md` L81 (Story 1b.4
    declaration + Epic 4 Story 4.2 / Epic 11 Story 11.3 per-adapter raise
    sites). The Story 1b.4 `SubprocessAdapter._assert_binary_version` helper
    provides the generic Phase-1 raise site with the FR47-exact error
    message format ON `str(exc)` (NOT prefixed by the H_R7 `error_code:` —
    this leaf overrides `__str__` to honor FR47 verbatim per Story 1b.4
    code-review D6 ratification; the underlying `error_code` remains
    available via the class attribute for FR49/FR50 machine-readable
    consumers):

        `<binary> version <X> outside tested range <range>`

    where `<range>` is `">={min}, <{max}"` when both bounds set or
    `">={min}"` when `max=None`. Per-adapter raise sites in Epic 4 Story 4.2
    (`claude` binary outside Story 4.2's pinned range) + Epic 11 Story 11.3
    (`copilot` binary outside ADR-010's `>=1.0.9,<2.0` range) inherit this
    contract.

    Structured attrs (Story 1b.4 code-review D7 ratification): `binary`,
    `detected`, `min_version`, `max_version` are exposed alongside the
    string message so callers can react programmatically (e.g., suggest
    `pip install '<binary>>=<min_version>'`) without string-parsing the
    error message. Sibling `DuplicateRegistrationError` / `AdapterDiscoveryError`
    follow the same pattern.

    `error_code = "UNSUPPORTED_BINARY_VERSION"`; exit code 78 (EX_CONFIG).
    """

    error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"

    def __init__(
        self,
        message: str,
        *,
        binary: str | None = None,
        detected: str | None = None,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> None:
        super().__init__(message)
        self.binary: str | None = binary
        self.detected: str | None = detected
        self.min_version: str | None = min_version
        self.max_version: str | None = max_version

    def __str__(self) -> str:
        # FR47-exact str(exc): NO H_R7 prefix on this leaf (Story 1b.4 D6
        # ratification). The `error_code` ClassVar remains available for
        # FR49 JUnit XML emission + FR50 exit-code mapping via direct
        # attribute access; the human-readable str(exc) matches PRD FR47
        # verbatim format.
        return Exception.__str__(self)


# --------------------------------------------------------------------------- #
# Warnings (per architecture L997: DegradedTraceWarning + AdapterVersionDriftWarning) #
# --------------------------------------------------------------------------- #


class DegradedTraceWarning(UserWarning):
    """Emitted when trace data is recoverable-but-incomplete (architecture L997).

    Distinct from `AgentEvalError`-hierarchy errors: this is a Python `Warning`
    subclass that integrates with `warnings.warn()`. Callers can opt into
    treating warnings as errors via `warnings.filterwarnings("error", category=DegradedTraceWarning)`.

    Story 1b.2 wires this for the `get_tool_calls` missing-source case
    (H_R4 fix per code-review 2026-05-18): when an `execute_tool` span is
    missing `agenteval.tool.source`, the projection accessor defaults the
    source to `"adapter"` AND emits a `DegradedTraceWarning` so trace
    producers see the convention violation. Epic 5 Story 5.4 ratifies the
    full DegradedTraceWarning + `Get Last Warnings` keyword surface per
    FR61 (Phase-1.5 scope; Story 1b.2 ships the warning class only).

    Future code paths that emit this warning:
        - `mcp_coverage="partial"` runs (FR61, Epic 5)
        - Adapter version drift detected (separate `AdapterVersionDriftWarning`
          class, Epic 4 Story 4.2)
        - Span data missing required `agenteval.*` attributes
    """
