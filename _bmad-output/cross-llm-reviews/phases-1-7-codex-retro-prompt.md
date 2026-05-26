# Phases 1-7 — Browser-Library-style docstring refresh — Codex retro-review

## Why this review exists

We just shipped a 7-phase docstring refresh across 11 RF library modules. Each
phase had its own commit + cross-LLM review at the time. However, **Phase 7
codex review was missed** (quota outage 12:05-13:01 UTC). Kilo (`MiniMax-M2.7`)
caught 2 real bugs in Phase 7 (`Call Tool` `${result.text_content}` AttributeError
+ undefined `${{echo_factory}}` fixture across 4 examples) and they were fixed
pre-commit. This retro-review is the codex pair-of-eyes pass.

The full diff (Phases 1-7 src + conventions tests) is at
`_bmad-output/cross-llm-reviews/phases-1-8-src-tests-diff.patch`.

Per-phase commit refs:
- Phase 1 (`2b3f562`): SubagentsLibrary + HooksLibrary
- Phase 2 (`ad11126`): OrchestrationLibrary + StatsLibrary
- Phase 3 (`8ba299f`): MetricsLibrary + AssertionsLibrary
- Phase 4 (`ce4fe8a`): TelemetryLibrary
- Phase 5 (`ee55012`): top-level AgentEval config keywords + HeatmapLibrary
- Phase 6 (`11e9614`): SkillsLibrary
- Phase 7 (`d3bc758`): MCPLibrary

## Browser-Library style — convention summary

Every refactored keyword docstring carries:

1. Line 1: one-line summary (verb-leading, ends with PRD-ref).
2. Line 3: `[Tier N — Label]` tier badge + behavior-shape blurb.
3. `| =Arguments= | =Description= |` pipe-table with one row per arg.
4. Body paragraphs (NOT Google-style `Args:` / `Returns:` / `Raises:`).
5. `Example:` (or `Example (illustrative — ...):`) block — pipe-prefixed `|`
   lines that the Phase-8a executable-doc test (`test_docstring_examples_dryrun.py`)
   executes via `sys.executable -m robot --dryrun`.
6. `Notes:` tail — every `FR\d+`, `ADR-\d+`, `Story \d+\.\d+` mentioned in the
   body MUST be echoed.

## Conventions test layer (already enforced)

`tests/unit/conventions/test_docstring_browser_style.py` enforces:
- arguments-table-present
- example-block-present
- notes-section-present
- citation-bidirectional-consistency

`tests/unit/conventions/test_docstring_examples_dryrun.py` runs every Example
block through `robot --dryrun` to catch syntax + keyword resolution + arg-count
errors. **Dryrun does NOT catch attribute access or undefined variables** —
Phase 7's `${result.text_content}` slipped through (caught only by kilo
adversarial review).

Both test files: 1605 passed, 10 skipped at HEAD.

## What you should focus on

The conventions tests catch the static-shape stuff. Your job is the
semantic-truth audit that static checks miss. Per
`feedback_citation_drift_first_class` (project norm): re-derive each cited fact
from source, not just check the citation exists.

### HIGH-priority audit

1. **Hidden AttributeErrors in examples** — Phase 7 had `${result.text_content}`
   where `MCPToolResult` has no such field. Sweep every refactored example for
   `${object.attr}` / `${object[key]}` patterns and verify the attr/key exists
   on the documented return type. Cross-reference the dataclasses in:
   - `src/AgentEval/types.py`
   - `src/AgentEval/mcp/lifecycle.py` (MCPToolResult, MCPTool, MCPSession,
     MCPServerHandle, ServerInfo)
   - `src/AgentEval/discoverability/schema.py` (DiscoverabilityResult,
     TaskResult, DiscoverabilitySummary)
   - `src/AgentEval/skills/schema.py` (SkillResult, SkillFrontmatter, etc.)
   - `src/AgentEval/_assertions/schema.py`

2. **Undefined RF variables** — `${{var_name}}` is Python expression
   evaluation. Sweep for `${{some_name}}` where `some_name` is not a defined
   Python builtin / literal / inline expression. Phase 7 had `${{echo_factory}}`
   undefined.

3. **Mock-provider semantics violation** — `adapter=generic provider=mock`
   means mock-provider semantics (empty tool_calls, zero usage, zero cost,
   echo-style text). Any Example asserting non-empty tool_calls, non-zero
   cost, or specific text content against this combination is broken UNLESS
   tagged `Example (illustrative — assumes a real adapter)`.

4. **Citation drift** — re-derive each `FR\d+` / `ADR-\d+` / `Story \d+\.\d+`
   from source. PRD lives at `_bmad-output/planning-artifacts/prd.md`,
   architecture at `_bmad-output/planning-artifacts/architecture.md`, stories
   at `_bmad-output/implementation-artifacts/<story-key>.md`. Note: the
   `L96-104` reference for `docs/contracts/error-class-hierarchy.md` is a
   pre-existing project-wide convention (14+ places) — flag but do NOT include
   in HIGH unless it represents a fresh Phase 1-7 introduction outside that
   convention.

5. **Test-name vs assertion-body match** — per
   `feedback_test_name_assertion_match`: does every Example's assertion body
   deliver on the keyword's stated promise? E.g., a keyword promising "returns
   Pass@k with Wilson CI bounds" — does the example actually verify a Pass@k
   value with CI bounds?

### MED-priority

- Cross-ref shape: backticked siblings (e.g., ``\`Start Server\```) in `Notes:`
  resolve to keywords on the SAME library, OR a clearly labeled
  cross-/downstream-library ref.
- Carve-out accuracy: `DF-X-Y-Z` IDs cited in carve-outs must exist in BOTH
  `docs/phase-1-5-carry-overs.md` AND
  `_bmad-output/implementation-artifacts/deferred-work.md`.

### LOW-priority

- Wording, ordering, optional sibling additions.

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.
Be specific — vague findings ("inconsistent tone") get downgraded.

CRITICAL: When finished, save the findings to:
`_bmad-output/cross-llm-reviews/phases-1-7-codex-findings.md`

If the file isn't written, the review is invalid.
