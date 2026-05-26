# Phase 7 — MCPLibrary docstring refresh — Cross-LLM review prompt

## Context

We are migrating all RF library docstrings to **Browser-Library style** across an
8-phase plan (`_bmad-output/planning-artifacts/docstring-refresh-proposal-2026-05-26.md`).
**Phase 7** refactors `src/AgentEval/mcp/library.py` — the MCPLibrary keyword
surface. 9 keywords total. The file already carries:

- `# ruff: noqa: E501` file-level pragma (Browser-Library tables routinely exceed
  120-char per-line)
- `_BROWSER_STYLE_MIGRATED = True` module flag (consumed by
  `tests/unit/conventions/test_docstring_browser_style.py` to scope its allow-list)

## Browser-Library style — convention summary

Every refactored keyword docstring MUST carry:

1. **Line 1** — one-line summary (verb-leading, ends with PRD-ref).
2. **Line 2** — blank.
3. **Line 3** — `[Tier N — Label]` tier badge + behavior-shape blurb.
4. **Arguments table** — `| =Arguments= | =Description= |` pipe-table with one
   row per arg (incl. defaults). RF libdoc renders this as `<table border="1">`.
5. **Body paragraphs** — invariants, carve-outs, raises (free-form prose, NOT
   `Args:` / `Returns:` / `Raises:` Google-style — those are explicitly REMOVED
   per the proposal).
6. **`Example:` block** (or `Example (illustrative — ...):` for mock-incompatible
   cases) — pipe-prefixed `|` lines that RF libdoc renders as `<pre>` and that the
   Phase-8a executable-doc test (`test_docstring_examples_dryrun.py`) executes
   via `sys.executable -m robot --dryrun`.
7. **`Notes:` tail** — bullet list. Every `FR\d+`, `ADR-\d+`, and `Story \d+\.\d+`
   identifier mentioned in the body MUST be echoed in `Notes:` per the
   bidirectional-consistency conventions test.

## What changed in Phase 7

Refactored all 9 MCPLibrary keywords:

1. `Get Server Config` — Tier 1 — declarative `.mcp.json` server-config getter.
2. `Get Tool Schema` — Tier 1 — declarative `.mcp.json` tool-schema getter.
3. `Validate Tool Schema` — Tier 1 — JSON Schema Draft-07 validator.
4. `Start Server` — Tier 1 — handle construction (3-transport enum).
5. `Connect To Server` — Tier 1 — per-call session-internal handshake.
6. `Stop Server` — Tier 1 — Phase-1 no-op cleanup.
7. `List Tools` — Tier 1 — `list_tools` over per-call MCP session.
8. `Call Tool` — Tier 1 — invoke a tool by name (tool-error-as-data).
9. `Get Tool Discoverability` — Tier 3 — N-trial Pass@k discoverability.

The diff is at `_bmad-output/cross-llm-reviews/phase-7-mcp-diff.patch`. Open both
the diff and the current file `src/AgentEval/mcp/library.py` to verify intent.

## Gate evidence (already verified in main agent)

- `uv run pytest tests/ -q` → **1605 passed, 10 skipped, 5 warnings** (incl. all
  conventions + Phase-8a executable-doc tests).
- `uv run ruff check src/ tests/` → **All checks passed**.
- `uv run mypy src/` → **Success: no issues found in 96 source files**.

## Review checklist (be adversarial — caller-attestation is mid-trust)

Reviewer MUST act on the **citation-drift first-class** norm
(`feedback_citation_drift_first_class`): re-derive each cited fact from source
files, not just check that citations exist. For every FR / ADR / Story citation
in a refactored docstring:

1. Open the source (`_bmad-output/planning-artifacts/prd.md`,
   `_bmad-output/planning-artifacts/architecture.md`, or
   `_bmad-output/implementation-artifacts/<story>.md`) and **verify the citation
   matches what's there**.
2. Flag any citation that drifted (wrong number, wrong claim, no such reference).

In addition, audit the docstrings for:

- **Test-name vs assertion-body match** — every `Example:` assertion delivers on
  what the keyword summary promises. Mock-incompatible examples MUST be marked
  `Example (illustrative — ...):`. Per `feedback_test_name_assertion_match`.
- **Mock-provider semantics** — examples using `adapter=generic    provider=mock`
  MUST be compatible with mock semantics (empty tool_calls, zero usage, zero
  cost) OR be tagged `Example (illustrative — assumes a real adapter):`.
- **Probe fitness** — when a docstring claims an invariant (e.g., "fresh
  per-call session"), is the invariant testable via a behavioral probe that a
  set-introspection / type-checker can't catch? Flag any blind spot. Per
  `feedback_codex_probe_fitness`.
- **Carve-out accuracy** — Phase-1 carve-outs cite `DF-X-Y-Z` deferred-work IDs.
  Verify each `DF-` ID actually exists in `docs/phase-1-5-carry-overs.md` AND
  `_bmad-output/planning-artifacts/deferred-work.md`. Per
  `feedback_carry_over_catalog_gate`.
- **Notes-echo coverage** — every `FR\d+` / `ADR-\d+` / `Story \d+\.\d+` mentioned
  in the body is echoed in `Notes:`. (The conventions test catches this; verify
  it actually fires by sampling 1-2 keywords.)
- **Bidirectional cross-refs** — backticked siblings (e.g., ``\`Start Server\```)
  in `Notes:` resolve to **real** keywords on the same library OR a clearly
  composed sibling library. Flag any broken or composed-only ref that won't link
  in libdoc.

## Output format

Group findings as:
- **HIGH** — citation drift, false invariant claim, broken example.
- **MED** — missing carve-out / inconsistent style / cross-ref shape issue.
- **LOW** — wording, ordering, optional sibling.

For each finding cite file + line + concrete fix.
