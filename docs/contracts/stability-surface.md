# Stability Surface

**Status:** accepted.
**Related ADRs:** ADR-014 (Error-Class Hierarchy — error-class stability labels).

> Superseded by the four-surface refocus (2026-07). The old registry enumerated a
> sprawl of surfaces that the refocus removed — vendor CLI adapters, multi-turn
> conversation, cross-adapter A/B stats, OTLP export, the advanced `Stat.*` extra,
> judge calibration, red-team probes, regression baselines, the sandbox Protocol.
> They are gone. What stays is the part that was always the point: a small set of
> labels and honest rules for what consumers may depend on across versions. The
> registry has been trimmed to the four libraries that ship today.

## Purpose

Defines agenteval's **per-API-element stability label scheme** (`stable` /
`provisional` / `experimental`) and the rules for promoting or demoting elements
between labels. Release notes link here so consumers know what is safe to depend on
across versions. The authoritative, always-current per-keyword surface is the libdoc
for each library; this contract sets the labels and the promotion rules.

## Scope

### In-scope

- The 3 stability labels and their consumer-facing guarantees.
- The label-change policy (when a `provisional` element may be promoted; when a
  `stable` element must be deprecated before removal).
- Library-level labels for the four shipped libraries and the shared base surface.

### Out-of-scope

- Internal helpers and private surfaces (anything under `_core/`, a leading-underscore
  module or attribute) — labels don't apply; they may change at any time.
- Per-keyword signatures — those live in each library's libdoc, which is the
  authoritative surface and carries its own tier badge per keyword.

## Contract

**Stability labels:**

- `stable` — semver-protected across a major version. Breaking changes require a
  major-version bump plus a deprecation cycle (≥1 minor before removal).
- `provisional` — likely to stabilize but may break across minor versions. The next
  breaking change is documented in the CHANGELOG.
- `experimental` — explicitly unstable. May break or be removed in any minor release.

**The four libraries** — each is independently importable and, since the composite
import landed, also bundled into `Library    AgentEval`:

- `HooksLibrary` (8 keywords) — `provisional`. Deterministic (Tier-1 only): hooks are
  deterministic programs, so there is no judge or coding-agent mode here. Needs no
  LLM or MCP extra.
- `MCPLibrary` (15 keywords) — `provisional`. Server-lifecycle, schema, and tool-call
  metric keywords. Live MCP-server testing needs the `[mcp]` extra; the schema and
  metric keywords run on the base install.
- `SkillsLibrary` (10 keywords) — `provisional`. Static skill inspection on the base
  install; activation checks that call a model need `[llm]`.
- `SubagentsLibrary` (9 keywords) — `provisional`. Static subagent-definition
  inspection on the base install; delegation checks that drive a model need `[llm]`.

That is **42 keywords across 4 libraries**. Keyword *names* and *return types* are the
consumer contract at each library's declared label; the `provisional` label warns that
signatures may still tighten pre-1.0.

**Shared base surface:**

- `AgentEval.__version__` — `stable`. PyPI distribution + import metadata convention;
  bumped per semver.
- The error hierarchy (`AgentEval._core.errors.AgentEvalError` + its leaves) — `stable`
  base and `error_code` set per [`error-class-hierarchy.md`](error-class-hierarchy.md).
- The shared result types (`ToolCallTrace`, `Usage`, `AgentRunResult`,
  `AgentRunMetadata`) — `provisional`. Field additions are minor bumps; field renames
  are major bumps. The `AgentRunMetadata.mcp_coverage` Literal value space is `stable`
  per ADR-016.

## Change Policy

This contract evolves per its own labels (the meta-rule: this contract is `stable`).
Adding new elements to the registry is minor-version-bump safe. Changing an existing
element's label requires:

- `experimental → provisional`: minor-version bump + CHANGELOG entry.
- `provisional → stable`: minor-version bump + CHANGELOG entry + a documented
  deprecation policy for the prior `provisional` surface.
- `stable → provisional` (a downgrade): major-version bump. Document the reason in the
  CHANGELOG and offer a migration path.

## References

- ADR-014: Error-Class Hierarchy — error-class stability.
- [`error-class-hierarchy.md`](error-class-hierarchy.md) — the `stable` error surface.
- [`determinism-contract.md`](determinism-contract.md) — the tier model each keyword declares.
- Each library's libdoc — the authoritative per-keyword surface.
