# Phase 7 — MCPLibrary docstring review — Kilo findings

## HIGH — citation drift, false invariant claim, broken example

**H1 — `Call Tool` example uses `result.text_content` which does not exist on `MCPToolResult`**
- File: `src/AgentEval/mcp/library.py:401`
- `MCPToolResult` (lifecycle.py:162) has fields: `content: list[dict]`, `is_error`, `error_message`, `latency_ms`, `correlation_id`. No `text_content` property exists.
- The example assertion `${result.text_content}` would raise `AttributeError` at runtime.
- Concrete fix: Change line 401 to `${result.content[0]["text"] if result.content else ""}` and add a comment explaining the content block structure. Or add a `text_content: str` property to `MCPToolResult` at lifecycle.py:207 that returns the first text block's text (or `""` if none).

---

**H2 — Error format citation drift in `Get Server Config` Notes**
- File: `src/AgentEval/mcp/library.py:127`
- Cited: `docs/contracts/error-class-hierarchy.md L96-104`
- Actual: Error-format contract (FR59) is at `error-class-hierarchy.md:128-138`. Lines 96-104 are in the middle of the FR50 exit-code table (header row + rows for `InvalidMCPServerConfigError`, `InvalidMCPToolSchemaError`, `InvalidScenarioYAMLError`).
- Concrete fix: Change `L96-104` to `L128-138` (or `L128+` since the FR59 section is a single block).

---

**H3 — Error format citation drift in `Get Tool Schema` Notes** (same pattern as H2)
- File: `src/AgentEval/mcp/library.py:163`
- Cited: `docs/contracts/error-class-hierarchy.md L96-104` (same incorrect range)
- Concrete fix: Change `L96-104` to `L128-138`.

---

**H4 — Error format citation drift in `Validate Tool Schema` Notes** (same pattern as H2/H3)
- File: `src/AgentEval/mcp/library.py:200`
- Cited: `docs/contracts/error-class-hierarchy.md L96-104` (same incorrect range)
- Concrete fix: Change `L96-104` to `L128-138`.

---

**H5 — `Start Server` and `Connect To Server` examples use undefined `echo_factory`**
- Files: `src/AgentEval/mcp/library.py:248` (Start Server), `src/AgentEval/mcp/library.py:281` (Connect To Server), `src/AgentEval/mcp/library.py:352` (List Tools), `src/AgentEval/mcp/library.py:398` (Call Tool)
- All four examples use `server_factory=${{echo_factory}}` but no `echo_factory` fixture is defined anywhere in the codebase.
- In contrast, `Get Server Config`, `Validate Tool Schema`, and `Stop Server` examples correctly use `transport=stdio` with actual command/args.
- Concrete fix: Replace `server_factory=${{echo_factory}}` with `transport=stdio command=python args=${{['-m', 'AgentEval.mcp.bundled.echo']}}` across all four examples, OR add a defined `echo_factory` fixture stub to the example block header.

---

## MED — missing carve-out / inconsistent style / cross-ref shape issue

**M1 — `Get Tool Discoverability` Notes cross-refs `HeatmapLibrary.Get Cohort Heatmap` as a "sibling keyword"**
- File: `src/AgentEval/mcp/library.py:494`
- `HeatmapLibrary` is a separately composed sub-library (via `AgentEval._heatmap.library` in `__init__.py:_SUB_LIBRARIES`). It is NOT a sibling of `MCPLibrary` (which is excluded from `_SUB_LIBRARIES` per Story 2.2 norm).
- The phrase "sibling keywords" implies same library; `downstream:` would be more accurate for a cross-library dependency.
- Concrete fix: Change line 494 from `Sibling keywords: ... downstream: \`HeatmapLibrary.Get Cohort Heatmap\`` to `Downstream keyword: \`HeatmapLibrary.Get Cohort Heatmap\` (consumes \`DiscoverabilityResult\` from this library to render the cohort heatmap per FR55).`

---

**M2 — `Get Server Config` Notes cites "FR59 + L96-104" but FR59 is a separate section from the FR50 exit-code table where L96-104 falls**
- File: `src/AgentEval/mcp/library.py:127`
- The citation `FR59 + docs/contracts/error-class-hierarchy.md L96-104` conflates two distinct things: (a) the FR59 error-format requirement (which lives at lines 128-138), and (b) the exit-code table at lines 96-104. These are adjacent but not the same content.
- Concrete fix: Split into two citations: `FR59 (error-format requirement) + docs/contracts/error-class-hierarchy.md L128-138` for the error format, and remove the L96-104 reference unless specifically citing the exit-code table for a different purpose (which isn't the case here — the docstring is about error format, not exit codes).

---

**M3 — `Get Tool Schema` docstring says "(Story 2.3 D-D)" in body but Notes says "Story 2.3 D-D drift-check" — mild inconsistency in how the drift-check citation is named**
- File: `src/AgentEval/mcp/library.py:143`
- Body: "reads from the declarative tools extension on each server entry (Story 2.3 D-D)"
- Notes: "Phase-1 scope per Story 2.3 D-D drift-check"
- "D-D" is not a standard format. The actual story identifier pattern in other story files is `Story 2.3` (without a D-D suffix). The D-D designation appears nowhere else in the codebase (no `2-3-d-d.md` file exists in `implementation-artifacts/`).
- Concrete fix: Remove the D-D suffix from both occurrences (change to `Story 2.3` in body and `Story 2.3` in Notes) since there is no separate drift-check document for Story 2.3 — the drift-check was a pre-create-story review step, not a separate artifact.

---

**M4 — `Validate Tool Schema` docstring capitalizes "schema-VALIDITY" in tier badge but body reverts to lowercase**
- File: `src/AgentEval/mcp/library.py:177` vs `src/AgentEval/mcp/library.py:179`
- Tier badge (line 177): "schema-VALIDITY" (all caps VALidity)
- Body (line 179): "schema-VALIDITY" in `[Tier 1 — Deterministic]` line (this is fine)
- But line 179: "Does NOT validate any tool-call's ARGUMENTS" — this is the continuation, not a drift.
- The actual inconsistency is that the word "schema-VALIDITY" is capitalized only in the tier badge line but not consistently styled elsewhere. This is minor but worth noting.
- Concrete fix: Standardize capitalization — either remove the all-caps styling from the tier badge or apply it consistently throughout.

---

## LOW — wording, ordering, optional sibling

**L1 — `Get Tool Discoverability` docstring uses `Example (illustrative — assumes a real adapter or fixture stub):` which is correct per convention, but the example uses `provider=mock` alongside `adapter=generic` — this is confusing for the mock-incompatible check**
- File: `src/AgentEval/mcp/library.py:478-487`
- The `(illustrative — assumes a real adapter or fixture stub)` label correctly flags mock incompatibility.
- However, `provider=mock` together with `adapter=generic` is ambiguous — `GenericAdapter` with `provider=mock` has specific semantics (stub model, no real LLM calls).
- The label is technically correct since the example requires a fixture stub, but the `provider=mock` adds confusion.
- Concrete fix (optional): Change `provider=mock` to `provider=stub` or remove the `provider=` kwarg to signal that this is a purely illustrative example relying on an external fixture, not the `MockProvider` path.

---

**L2 — `Connect To Server` Notes says "Sibling keywords: `Start Server` (handle construction); `Stop Server` (Phase-1 no-op cleanup)" — the parenthetical descriptions are helpful but `Stop Server` is described as "Phase-1 no-op cleanup" in its own docstring — consistent, but the Notes could reference the sibling docstring for details**
- File: `src/AgentEval/mcp/library.py:290`
- Not a bug; this is a suggestion. The parentheticals are fine but don't link to the sibling docstrings.
- Concrete fix (optional): Change to `Sibling keywords: \`Start Server\` (\`Start Server\` docstring); \`Stop Server\` (\`Stop Server\` docstring — Phase-1 no-op per Story 3.1)` to signal the cross-ref explicitly.

---

**L3 — `Get Server Config` module docstring at line 22 says "Story 2.3 ships 3 Tier-1 keywords per PRD FR5 + FR6 Phase-1 scope" but MCPLibrary ships 9 keywords (3 static-inspection + 6 lifecycle/discoverability)**
- File: `src/AgentEval/mcp/library.py:22`
- The module-level overview only describes the first 3 keywords (FR5+FR6 static inspection), not the 6 lifecycle/discoverability keywords from Stories 3.1, 3.2, and 4.4.
- Concrete fix (optional): Update the module docstring to list all 9 keywords, or at minimum note that the library ships additional keywords beyond the 3 FR5+FR6 ones (Stories 3.1, 3.2, 4.4).