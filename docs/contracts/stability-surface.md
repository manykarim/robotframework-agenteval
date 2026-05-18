# Stability Surface

**Status:** Phase-1 skeleton — content to be filled by Story 1a.6 (initial labels) + Epic 6 (sandbox subsection content).
**Owning epic:** Story 1a.6 (initial labels) + Epic 6 (sandbox surface)
**Related ADRs:** ADR-018 (Sandbox Phase 1 Policy — `SandboxBackend` Protocol), ADR-013 (Entry-Points Discovery — registration mechanism), ADR-014 (Error-Class Hierarchy — error-class stability labels)
**Related FRs:** FR64 (Stability Surface metadata), NFR-MAINT-05 (per-element stability labels)

## Purpose

Defines agenteval's **per-API-element stability label scheme** (`stable` / `provisional` / `experimental`) + the rules for promoting/demoting elements between labels. The **registry** of currently-labeled elements is filled **incrementally**: Story 1a.6 lands the initial Phase-1 labels; each subsequent epic-owning story registers its public elements as they ship. Phase-1 baseline contains only the sandbox-related elements (see `### Sandbox Protocol Surface` subsection); other public elements are added to the registry by the owning stories. Release notes link here so consumers know what is safe to depend on across versions.

## Scope

### In-scope

- The 3 stability labels + their semantics (consumer-facing guarantee per label).
- Label-change policy (when is a `provisional` element promoted to `stable`? when must a `stable` element be deprecated?).
- The Phase-1-baseline registry entries (currently: the sandbox surface — `### Sandbox Protocol Surface` subsection). Story 1a.6 + each epic-owning story registers additional elements as they ship.
- The procedure for adding a new public element to the registry (per-story checklist in Maintenance section).

### Out-of-scope

- Internal helpers + private surfaces (`_kernel/`, `_assertions/`) — labels don't apply.
- Backend implementations that consumers ship in their own packages (e.g., a `docker-sandbox` package implementing `SandboxBackend`) — those packages manage their own stability.

## Contract

*Phase-1 skeleton — Story 1a.6 + Epic 6 fill in the formal specification.*

**Stability labels:**

- `stable` — semver-protected across major version. Breaking changes require major-version bump + deprecation cycle (≥1 minor before removal).
- `provisional` — likely to stabilize but may break across minor versions. Document the next breaking change in CHANGELOG.
- `experimental` — explicitly unstable. May break or be removed any minor release. Use with `pin >=X.Y.Z,<X.Y.(Z+1)`.

**Per-element registry:** Filled INCREMENTALLY. Phase-1 baseline below contains only the sandbox surface (see `### Sandbox Protocol Surface` subsection). Story 1a.6 registers the AgentEval library entry-point + initial keyword surface labels. Subsequent epic-owning stories MUST register their public elements (keywords, Protocols, error-class names, entry-point group names) at the time of shipping. The registry is intentionally NOT complete at Story 1a.4 commit time; FR64/NFR-MAINT-05 enforcement begins with Story 1a.6 + the docs-build CI check that warns on unlabeled elements (per Story 1a.6 deliverable).

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
