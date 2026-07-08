# Design: fix-first-run-experience

## Context

`agenteval init` (implemented in `src/AgentEval/_init/`, templates under
`src/AgentEval/_init/templates/`) scaffolds a starter project whose example MCP suite fails five
distinct ways and whose `scenario.yaml` is rejected by the library's own loader (dossier E1). The
only test coverage (`tests/unit/test_init_cli.py`) verifies files get written, not that they run.
Separately, the doc surface has drifted from the shipped keyword surface (E3) and lacks the four
pieces of information every fresh-user trial needed (E4): skill frontmatter fields, hook config
input schema, the mock-to-live-model path, and API-key env vars. User-facing prose — including
comments inside scaffolded starter files — is saturated with internal process jargon
(Story/FR/ADR/DF-X-SY identifiers, cross-LLM-review provenance notes).

Constraints:

- `MCP.Call Tool` (`src/AgentEval/mcp/library.py`, `call_tool`) currently takes
  `arguments: dict[str, Any] | None = None`. Existing callers (recipes, dogfood, tests) use the
  `arguments=` dict form and must keep working.
- The bundled echo server (`src/AgentEval/mcp/bundled/echo.py`) exposes `echo_back(text)` — the
  smoke test can run keyless and deterministic.
- Sibling changes own adjacent problems: `accept-real-claude-hook-config` (real Claude Code hook
  schema parsing) and `compose-single-library-import` (import sprawl / `Get Frontmatter`
  collision). This change documents current behavior; it does not alter either surface.

## Goals / Non-Goals

**Goals:**

- A clean-dir `agenteval init` followed by the documented run command executes green with zero
  edits, and CI proves it on every push.
- `MCP.Call Tool` accepts the natural RF call shape (`text=hello`) that the scaffold and docs
  teach.
- Every keyword count, keyword table, recipe code block, and README link points at something true.
- A first-run user can find skill frontmatter fields, the hook config input schema, and the
  mock-to-live-model path without reading libdoc HTML source or test fixtures.
- User-facing surfaces read as product documentation, not project archaeology.

**Non-Goals:**

- Parsing real Claude Code `settings.json` hook format (sibling: `accept-real-claude-hook-config`).
- Composing SkillsLibrary/SubagentsLibrary/HooksLibrary/MCPLibrary into the top-level import
  (sibling: `compose-single-library-import`) — templates and docs keep explicit `WITH NAME`
  imports until that lands.
- Any new evaluation capability, keyword surface beyond the `Call Tool` kwargs form, or removal of
  internal machinery.
- Rewriting libdoc docstrings (jargon strip targets README, recipes, `docs/index.md`, and scaffold
  templates only; docstring jargon is tracked debt, not first-run-blocking).

## Decisions

### D1 — `Call Tool` kwargs: merge-free union, dict form stays canonical

Signature becomes:

```python
def call_tool(
    self,
    handle: MCPServerHandle,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    **kwargs: Any,
) -> MCPToolResult:
```

- If only `**kwargs` are given, they become the arguments dict.
- If only `arguments=` is given, behavior is unchanged.
- If **both** are given, raise a structured error (existing `errors.py` File/Line/Field/Fix style)
  telling the user to pick one form — merging invites silent-override bugs.
- `arguments` remains a reserved name: a tool whose own parameter is literally named `arguments`
  (or `handle`/`tool_name`) must use the dict form. Documented in the keyword docstring.

*Alternative considered:* merge kwargs into `arguments` with kwargs winning — rejected; collision
semantics are invisible at the call site and the two-form union covers every real case.

*Known trade-off accepted:* RF free named args arrive as strings unless the user annotates
(`count=${5}`). The docstring shows the `${}` form for non-string values and keeps the dict form
as the escape hatch. The `@tier(1)` decorator chain must pass `**kwargs` through — verify with a
unit test on the wrapped keyword, not just the inner function (per the project's decorator-chain
lesson).

### D2 — Scaffold templates fixed to the natural form the library now supports

`example_mcp_runtime.robot` after the fix:

- `Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP` added alongside
  `Library    AgentEval`.
- Call: `MCP.Call Tool    ${HANDLE}    echo_back    text=hello` (natural kwargs form — D1 makes
  the previously-broken shape the working shape).
- Assert: `Should Be Equal    ${result.is_error}    ${FALSE}` and content check on
  `${result.content}`.

`scenario.yaml`: `mcp_servers` becomes a list of strings (schema-valid per
`src/AgentEval/scenarios/loader.py`), and the template is validated by the smoke test via
`Load Scenario`.

All template comments rewritten jargon-free (see D6) — the current templates carry "Epic 3 /
Story 8b.1" and "kilo/minimax cross-LLM review FINDING-1" provenance in user-facing files.

### D3 — E2E scaffold smoke test: pytest subprocess harness in `ci.yml`

New `tests/integration/test_init_scaffold_e2e.py`:

1. Run `agenteval init` in `tmp_path` (subprocess, same entry point users hit).
2. Run `robot` on the scaffolded `tests/` with the mock provider and bundled echo server.
3. Assert RF exit code 0 (all scaffolded example suites green).
4. Additionally `Load Scenario` the scaffolded `scenario.yaml` (covers defect 6 even though
   `Run Scenario` isn't in the scaffold's default run).

Keyless + deterministic (mock provider, bundled stdio echo server), so it runs in the standard
`ci.yml` matrix — not the live/nightly workflows. Timeout-bounded to contain stdio-subprocess
hangs.

*Alternative considered:* extending `tests/unit/test_init_cli.py` — rejected; it's a unit surface
and the point is executing the scaffold end-to-end as a forcing function (same rationale as the
recipe dryrun harness).

### D4 — Doc drift: fix to actual, then pin with a count check

- Recount the shipped keyword surface (source of truth: libdoc over the 6 libraries) and write the
  real number into both `README.md` and `docs/index.md` (currently 51 vs 49 vs actual 56); fix
  `docs/index.md`'s "5 libraries" to 6.
- Add the 6 missing keywords to the README tables.
- Add a drift check to the docs-build CI path asserting the README/index counts match the libdoc
  count, so the third divergence can't happen. (Cheap: the recipe-dryrun harness already
  establishes the extract-and-verify pattern in `tests/integration/recipes/`.)
- Persona labels in the README recipe table corrected to match the recipe files (Priya for 2 and
  8, Mei for 3) — but note D6 removes persona-journey framing from the README table entirely, so
  the correction lands as "describe recipes by what they do", which fixes the mislabel as a
  side effect.
- The 4 `_KNOWN_BROKEN_BLOCKS` recipe blocks (DF-14.3-S1, `docs/recipes/README.md`) are fixed
  until they pass `robot --dryrun`, then removed from the skip list. The skip list ends empty and
  stays as the mechanism for any future triage.

### D5 — Empty doc dirs: populate troubleshooting, unlink the other two

- `docs/troubleshooting/README.md`: aggregate the per-recipe Symptom/Cause/Fix tables (already
  written, already good — dossier E4 "judged genuinely good") into one browsable page organized by
  symptom, each entry linking back to its recipe.
- `docs/coming-from/` and `docs/scenarios/`: no content exists and none is in scope — remove the
  README links and the empty dirs rather than shipping placeholder pages. A dead link is worse
  than no link; the dirs can return when real content exists.

*Alternative considered:* stub pages ("coming soon") — rejected per the project's honest-framing
norm; stubs are drift seeds.

### D6 — Onboarding docs: README-first, one new page

- **Skill frontmatter**: README gains a short "Writing a skill file" subsection listing the 4
  required fields (`name`, `description`, `allowed-tools`, `disable-model-invocation`) with a
  minimal complete `SKILL.md` example (adapted from `src/AgentEval/_init/templates/example-skill.md`,
  which already exists — the scaffold and README teach the same shape).
- **Hook config input schema**: document the flat entry schema `HooksLibrary.Get Config` accepts
  (`command`, `args`, `timeout`, `matcher`) with a valid example JSON, plus an explicit note that
  real Claude Code `settings.json` nests differently and is NOT yet accepted (pointing at the
  sibling change). Documenting the divergence is this change's job; fixing it is not.
- **"Running against a real model"**: new page `docs/running-against-a-real-model.md` — provider
  selection (`AGENTEVAL_PROVIDER`), model string format, which API-key env vars each provider
  reads, a copy-paste minimal example, and the cost-guardrail note. Linked from README quick start
  ("start on mock, switch like this").
- **`.env.example`**: add commented `ANTHROPIC_API_KEY=` / `OPENAI_API_KEY=` lines (plus the
  litellm pass-through note). Also strip its Story/FR provenance comments (D7).

### D7 — Jargon strip: allowlist of surfaces, not a blocklist of terms

In-scope surfaces: `README.md`, `docs/index.md`, `docs/recipes/*.md`, all of
`src/AgentEval/_init/templates/`, `.env.example`. Rule: no Story/Epic/FR/ADR/DF-X-SY/C-number
identifiers, no persona-journey slot labels, no review-provenance notes. Where a reference earns
its place (e.g. an ADR genuinely explains a design), link it by topic ("why per-test MCP scope is
the default") rather than by identifier. ADRs, `docs/contracts/`, `docs/phase-1-5-carry-overs.md`,
`MAINTAINERS.md`, and `_bmad-output/` keep identifiers — they are maintainer surfaces.

Tier system in first-run docs: reduced to one short paragraph ("keywords are tagged by determinism
tier; deterministic keywords need no API key — details here") linking to the existing contract doc.

## Risks / Trade-offs

- **[RF kwarg string coercion]** Users pass `count=5` expecting an int; tool receives `"5"`. →
  Docstring + real-model page show `${5}` syntax and the `arguments=` dict escape hatch; smoke
  test uses a string-typed tool (`echo_back(text)`) so the happy path is honest.
- **[Reserved-name shadowing in kwargs form]** Tool params named `arguments`/`handle`/`tool_name`
  can't use the kwargs form. → Documented; dict form always available; structured error on the
  both-forms collision makes misuse loud.
- **[Smoke test flakiness from stdio subprocess]** MCP server startup in CI could hang. → Hard
  timeout on the pytest test; bundled echo server is already exercised by existing integration
  tests, so startup behavior is known.
- **[Keyword-count check goes stale differently]** A count check that parses README prose is
  brittle. → Anchor the check on a single well-defined marker (the table row counts / one
  canonical count sentence), not free prose.
- **[Recipe fixes exceed doc-only scope]** A `_KNOWN_BROKEN_BLOCKS` block may be broken because a
  keyword changed shape, tempting library edits. → Scope rule: fix the recipe to the shipped
  surface; if the shipped surface itself is wrong, that's a new change proposal, not scope creep
  here (Call Tool kwargs is the one sanctioned library change).
- **[Jargon strip regressions]** Rewording could break the docs-build section-presence checks or
  recipe dryrun extraction. → Run `docs-build.yml` checks and the recipe harness locally before
  review.

## Migration Plan

Additive/corrective only — no deploy or rollback machinery. `Call Tool` change is
backward-compatible (new optional forms). Users who scaffolded with the broken templates get no
auto-migration; the fix benefits new `init` runs (a troubleshooting entry covers "my
pre-<version> scaffold fails" symptoms).

## Open Questions

- Exact final keyword count must be re-derived at implementation time from libdoc (dossier says
  56; the count check in D4 makes the number self-verifying thereafter).
- Whether `docs/scenarios/` content is partially satisfied by the scenario-YAML schema section of
  the real-model page or existing contract docs — implementer picks unlink (default) unless a
  1-page schema doc falls out of the D2 scenario.yaml work nearly free.
