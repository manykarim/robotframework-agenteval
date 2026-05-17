# ADR-013: Entry-Points Discovery Infrastructure

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A2 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A2. Renumbered to ADR-013 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

agenteval has multiple distinct extension surfaces that all use Python's entry-points mechanism for plugin discovery at library-import time:

- `[project.entry-points."agenteval.coding_agents"]` — coding-agent adapter registrations (FR17a).
- `[project.entry-points."agenteval.providers"]` — LLM provider plugins (FR17c).
- `[project.entry-points."agenteval.judges"]` — LLM-as-judge plugins (Phase 2).
- `[project.entry-points."agenteval.sandboxes"]` — sandbox backend implementations (Phase 3, added by ADR-018 sandbox policy).
- `[project.entry-points."robot.listener"]` — Robot Framework Listener v3 entry point (FR33a) for the OTel listener.
- Plus a **direct-composition path** (`plugins=[...]` library argument per FR48 + FR17b) for testing and one-off override.

Plus a legacy `[project.entry-points."robotframework_agenteval.adapters"]` group per FR17a (kept for backward compatibility with the original PRD-defined adapter-registration mechanism — counts as one of the 5 agenteval-owned entry-point tables in ADR-018's reckoning).

Without a unified discovery layer, each sub-library independently calling `importlib.metadata.entry_points` would risk:
- **Inconsistent precedence semantics** between `__init__` direct args, entry-points-discovered registrations, and built-in defaults.
- **Divergent error handling** when a partially-installed adapter package is encountered (e.g., user installed `[claude]` extra but not `claude-agent-sdk`).
- **Discovery-order ambiguity** when multiple packages register the same name on the same entry-point group.

## Decision

agenteval centralizes entry-points discovery at `src/AgentEval/_kernel/discovery.py`. Single source of truth using **stdlib `importlib.metadata.entry_points`** (NOT deprecated `pkg_resources`).

**Precedence rule (load order, highest priority first):**

1. `__init__` direct args (`AgentEval(coding_agent=MyAdapter(), ...)`) — explicit user choice ALWAYS wins.
2. `plugins=[...]` direct-composition (FR48) — explicit composition wins over entry-points discovery.
3. Entry-points-discovered registrations — auto-loaded by package install.
4. agenteval-built-in defaults — fallback when no entry-points are installed.

Concrete behavior:

- Single `discovery.py` module handles all 5 `agenteval.*` entry-point groups + the legacy adapter group + the `robot.listener` group + the direct-composition path.
- Discovery happens lazily at first lookup, not at import. Lazy avoids paying entry-points-scan latency for users who don't trigger plugin discovery.
- Partial-install failures raise `AdapterDiscoveryError(AgentEvalCompatError)` (per ADR-014) with an `installed-vs-required-extras` diagnostic hint — e.g., "Found `agenteval.coding_agents:claude_code_cli` registration but `claude-agent-sdk` is not installed; install `pip install agenteval[claude]` or remove the registration."
- Duplicate-name collisions across packages produce a `DuplicateRegistrationError(AdapterDiscoveryError)` with both source package names; agenteval refuses to silently pick one.

## Consequences

- 5 `agenteval.*` entry-point groups + 1 legacy adapter group + 1 `robot.listener` group documented in `pyproject.toml` template + contributor docs. Story 1a.1 baseline already declares the 6 tables (`pyproject.toml` lines 79-95).
- Error path tested in conformance suite (`tests/conformance/test_ac_*_discovery.py` parametrized over installed-extras scenarios) per ADR-017.
- Community adapter authors get a single documented registration pattern (one `setup.cfg`/`pyproject.toml` snippet per adapter); they don't need to learn each sub-library's discovery quirks.
- Lazy discovery → first lookup pays the cost; subsequent lookups hit a process-lifetime cache.
- Entry-point group count (5 agenteval-owned + 1 robot.listener = 6 total Phase-1 tables) is locked here; new groups require an ADR amendment.

## Alternatives

- **Single composite entry-point** — rejected. Mixes coding_agent + provider + judge + sandbox concerns; couples discovery to namespace and complicates per-group configuration.
- **Plugin-only mechanism (no entry-points)** — rejected. Breaks org-wide auto-discovery scenarios (e.g., a corporate package that registers a private LLM provider for all consumers in the org). Entry-points are the canonical "install-and-go" mechanism for Python plugins.
- **Per-sub-library discovery** — rejected. Duplication of discovery logic across `mcp/`, `coding_agent/`, `providers/`, etc.; inconsistent precedence; divergent error messages.
- **`pkg_resources`-based discovery** — rejected. Deprecated in Python 3.12+; stdlib `importlib.metadata.entry_points` is the maintained replacement.

## References

- Architecture L429-434 (renumbering plan) + §Project Tree (entry-point group inventory)
- ADR-014 (Error-Class Hierarchy) — `AdapterDiscoveryError` is a leaf of `AgentEvalCompatError`
- ADR-018 (Sandbox Policy) — adds the `agenteval.sandboxes` 5th group; updated ADR-A2 (this one) at architecture-step ratification time
- `pyproject.toml` lines 79-95 — current entry-point table declarations (all empty in Phase-1 baseline; populated per-epic)
- FR17a + FR17b + FR17c + FR33a + FR48 (PRD) — functional requirements driving each entry-point group
