## Context

`robotframework-agenteval` today is a single `AgentEval` Robot Framework library (a `robotlibcore.DynamicCore` subclass) that lazily composes 14 sub-libraries into one flat 104-keyword namespace. It is ~37k LOC across 22 modules and 26 openspec capabilities. A read-only structural map (21 module readers) found that the largest modules are the least differentiated — `coding_agent` (3.7k, six vendor CLI adapters), `_kernel` (3.9k, half of it a cost-meter whose cost source is a permanent `0.0` stub), `telemetry` (3k, OTLP/JUnit/EvidenceBlock reporting) — while the modules mapping to the actual mission (`mcp`, `skills`, `subagents`, `hooks`) are small and sound. The project's own landscape survey names **Hooks and SubAgents** as testing white space.

Constraints: solo maintainer plus AI-agent-assisted development; Robot Framework 7.x; strong existing CI gate (ruff + mypy + license/contract/doc-count checks + ~1600 pytest); no backwards-compatibility requirement for this change (explicitly waived by the requester). Reference-only inspiration: `agentguard` (pattern source, never a dependency).

## Goals / Non-Goals

**Goals:**
- Four independently importable RF libraries — `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, `HooksLibrary` — each usable on its own with minimal dependencies.
- A small shared internal spine (`AgentEval._core`) implementing the `@tier(1|2|3)` = deterministic/LLM/agent model once, reused by all four surfaces.
- Aggressive LOC reduction (~37k → ~9k target) by deleting non-mission modules and rebuilding the vendor/telemetry/kernel ballast thin.
- Deterministic mode works with a tiny dependency footprint; LLM and agent modes live behind extras.
- All readable content (README, recipes, keyword docstrings, error messages) rewritten in the Robot Framework voice; mission/tagline reframed.
- An honest capability matrix: surfaces expose only the modes that genuinely apply.

**Non-Goals:**
- Cross-adapter A/B benchmarking, judge calibration, regression-baseline gating, red-teaming, and multi-turn conversation simulation. Cut now; may return as optional extras later.
- Vendor-specific coding-agent adapters (claude-code, codex, copilot, opencode, openai-agents, claude-agent-sdk). One generic LiteLLM adapter covers the dogfood path.
- Enterprise telemetry/observability export (OTLP, JSONL, JUnit-XML enrichment, EvidenceBlock markdown, run-manifest reproducibility sidecar).
- Renaming the PyPI distribution or preserving any back-compat shim for the old flat `AgentEval` keyword namespace.

## Decisions

### D1 — Four separate libraries over one flat composite
Each surface is its own `robotlibcore`-backed Library class in its own package; users write `Library    HooksLibrary`. **Why:** RF-idiomatic (Browser vs SeleniumLibrary), lets `HooksLibrary` avoid LLM/MCP deps entirely, and removes the runtime keyword-collision detector and namespace-prefix baking that the flat composite needed. **Alternatives:** (a) keep the flat `AgentEval` mega-library — rejected: forces every user to carry every dependency and keeps the composition/collision machinery; (b) entry-point plugin discovery — rejected as over-machined for four first-party libraries. **Kept as a thin convenience:** an optional `Library    AgentEval` that composes all four for users who want one import; the four separate libraries are the documented default.

### D2 — A single internal spine package, not a shared library
`AgentEval._core` holds `adapter.py` (`AgentRunResult` + `run(prompt)->AgentRunResult` protocol + one LiteLLM adapter), `judge.py`, `stats.py` (run-N / pass@k / Wilson CI), `trace.py` (spans + tool-calls projection), `tier.py` (`@tier` marker), `errors.py` (~12 classes), `types.py`. It exposes **no keywords** — it is imported by the four libraries. **Why:** the three test modes are identical machinery across surfaces; implementing them once is the core simplification. **Alternative:** duplicate per surface — rejected, that is the duplication we are removing.

### D3 — Dependency extras gate the heavy modes
`pip install robotframework-agenteval` → deterministic mode only (RF + robotlibcore + PyYAML). Extras: `[mcp]` (MCP SDK for live server testing), `[llm]` (litellm for judge + agent modes), `[all]`. **Why:** honors "four separate libraries with minimal deps"; a hook-linting CI job installs almost nothing. Keyword bodies that need an extra fail with a clear, RF-voice error naming the missing extra. **Alternative:** one fat install — rejected.

### D4 — Rebuild `coding_agent`, `_kernel`, `telemetry`; keep their load-bearing primitives
- `coding_agent` → `_core/adapter.py`: keep `AgentRunResult` + one `GenericAdapter` (LiteLLM); drop five vendor adapters and the FR47 binary-version-range machinery.
- `_kernel` → keep `tier.py` and the async bridge (`run_async`); keep a slim trace projection and a slim MCP lifecycle manager (only what live MCP testing needs); **delete** the dead cost-meter, `host_budget_plumbing`, `version_drift`, and the `inspect.stack()` tier-ACL (replace with a cheap explicit check). Preserve the few import surfaces 77 test files touch (`tier`, `get_adapter`, `resolve_config`) or migrate their imports as part of the change.
- `telemetry` → `_core/trace.py`: keep span + tool-call emission and the deterministic "was this tool called with these args" projection; delete OTLP/JSONL/JUnit/EvidenceBlock/run-manifest reporting and the 1045-line god-listener.
**Why:** the useful core is a small fraction of each; incremental trimming can't reach it. **Alternative:** simplify in place — rejected, the module shapes are wrong for the target.

### D5 — Honest mode matrix; Hooks are Tier-1 only
Hook outputs are deterministic programs, so `HooksLibrary` ships Tier-1 only; `SubagentsLibrary` has no meaningful LLM-judge mode (routing is deterministic delegation extraction + agent-mode accuracy). The "4 surfaces × 3 modes" grid is aspirational, not a mandate — cells that don't apply are documented N/A rather than filled with theater. **Why:** forcing all 12 cells reintroduces exactly the kind of speculative code this change removes.

### D6 — Delete duplication and docstring archaeology, not just modules
Within the surviving surface cores: collapse the 4× copy-pasted skill activation substring heuristic into one helper; merge near-duplicate tier keywords (raise-vs-return variants) into one parameterized keyword; remove the dedicated `Get *Pass At K` band-aid keywords once the generic `stats` pass@k predicate is fixed; strip per-keyword FR/AC/ADR/Story provenance docstrings down to terse, useful libdoc. **Why:** ~40-60 lines of provenance prose per ~5-line keyword body is the bulk of the surface LOC.

### D7 — Keep the PyPI name, reframe the mission and voice
Distribution stays `robotframework-agenteval` (preserves history/identity); the tagline moves from "evaluate AI coding agents" to testing the agentic stack. All readable content is rewritten in the Robot Framework voice (friendly, direct, dry, no fluff; ~70/30 professional/casual). A SubAgents recipe is added (currently missing). **Why:** renaming a PyPI dist is a tax with little upside; the voice/mission reframe is where the identity work pays off. **Alternative:** rename the dist — rejected.

### D8 — Spec baseline re-cut, not amended in place
The 26 existing openspec capabilities are consolidated into five (`mcp-testing`, `skills-testing`, `subagent-testing`, `hook-testing`, `evaluation-core`); the rest are removed. **Why:** the old specs encode the old architecture; a from-scratch focus is clearer as a re-cut than as 26 deltas.

## Risks / Trade-offs

- **Large test-suite churn** (~11k LOC of unit tests coupled to dropped modules) → excise per-module suites (already partitioned as `tests/unit/<module>/`) and port the surface-core tests; keep the CI gate green at each phase boundary, not just at the end.
- **`_kernel` rebuild blast radius** (77 test files + ~15 modules import from it) → freeze the small public import surface (`tier`, `get_adapter`, `resolve_config`) first, migrate imports, then gut internals behind it.
- **Cutting A/B / calibration / baseline removes real, working functionality** → this is deliberate; leave documented seams (optional `[compare]` extra) so it can return without a re-architecture.
- **Single LiteLLM adapter may not cover a future vendor's quirks** → acceptable for v1; the adapter protocol stays open for a subprocess exemplar later. Dogfood (minimax via litellm) already runs through the generic path.
- **RF-voice rewrite is subjective and broad** → treat the voice doc as the rubric; do the doc pass as one coherent phase, not scattered edits, and keep the doc-count CI gate honest.
- **"No backwards compat" breaks any existing users of the flat `AgentEval` keywords** → explicitly accepted by the requester; the project is pre-1.0 (`__version__ = "0.0.1"`).

## Migration Plan

Phased so the CI gate stays green at every boundary (no big-bang branch):
1. **Spine first** — stand up `AgentEval._core` (adapter, tier, stats, judge, trace, errors, types) with tests; keep old modules importing through shims where cheap.
2. **Surface by surface** — rebuild `HooksLibrary` (smallest, Tier-1 only, no LLM deps) → `SubagentsLibrary` → `SkillsLibrary` → `MCPLibrary`, each as an independent library on the spine, porting the sound cores and their tests.
3. **Delete** the dropped modules (`baseline`, `redteam`, `conversation`, `conformance`, `_heatmap`, `scenarios`) and their tests, plus the vendor adapters and telemetry reporting.
4. **Packaging** — pyproject extras (`[mcp]`, `[llm]`, `[all]`), optional `AgentEval` convenience composite, update CLI.
5. **Docs + voice** — reframe README/mission, rewrite surviving recipes/contracts/docstrings/errors in RF voice, add the SubAgents recipe, regenerate keyword libdoc.
6. **Spec archive** — mark the re-cut in openspec, remove superseded specs.

**Rollback:** the work lands on the `refactor/simplify-and-cleanup` branch; `main` is untouched until merge, so rollback is "don't merge."

## Open Questions

- **Convenience composite** — ship the optional `Library AgentEval` in v1, or defer until the four libraries are proven? (Leaning: ship it thin, low cost.)
- **Subprocess adapter exemplar** — keep one reference `SubprocessAdapter` alongside the LiteLLM one, or LiteLLM-only for v1? (Leaning: LiteLLM-only; document the protocol.)
- **MCP live-testing dependency** — is `[mcp]` (the MCP Python SDK) required for deterministic schema validation, or only for `Start Server`/`Call Tool`? (Determines how tiny the deterministic MCP path can be.)
- **Config precedence** — how much of the FR41 kwarg→env→`.env`→defaults chain survives per-library vs. simplified to kwarg→env?
- **Final tagline wording** — to be settled in the voice pass.
