# Proposal: fix-first-run-experience

## Why

The documented 5-minute first-run path is broken end-to-end: `agenteval init` scaffolds an example suite that fails five distinct ways plus a `scenario.yaml` the library's own `Load Scenario` rejects (findings dossier E1, empirically reproduced in a clean directory), and no CI executes scaffold output so the rot went undetected. Around that broken core, docs drift (README claims 51 keywords, `docs/index.md` claims 49, actual is 56; three empty doc dirs linked from the README; 4 known-broken recipe code blocks) and doc gaps (skill frontmatter fields, hook config input schema, mock-to-live-LLM path all undocumented outside JS-rendered libdoc HTML) caused all four independent fresh-user CLI trials to burn iterations (E3, E4). First impressions are unrecoverable; this must be fixed before wider adoption.

## What Changes

- **Fix all 6 scaffold defects** in `src/AgentEval/_init/templates/`:
  1. `example_mcp_runtime.robot` uses `MCP.*` keywords but imports only `Library    AgentEval` — add the `MCPLibrary` import (`Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP`).
  2. `MCP.Call Tool    ${HANDLE}    echo    message=hello` passes a free RF kwarg the keyword rejects — template updated to a working call form (see next bullet).
  3. Template asserts `${result.success}` — `MCPToolResult` has `is_error`, not `success`.
  4. Tool name `echo` — bundled server exposes `echo_back` (`src/AgentEval/mcp/bundled/echo.py`).
  5. Argument name `message` — actual param is `text`.
  6. `scenario.yaml` declares `mcp_servers` as a list of dicts — loader (`src/AgentEval/scenarios/loader.py`) requires `list[str]`; template rewritten to a schema-valid scenario.
- **`MCP.Call Tool` accepts natural RF kwargs** (e.g. `text=hello`) in addition to the existing `arguments=` dict form, so the natural scaffold/recipe call shape works. Existing `arguments=` callers unaffected.
- **End-to-end scaffold smoke test in CI**: run `agenteval init` in a temp dir and execute the scaffolded suite to green (mock provider, bundled echo server — no API keys), so scaffold rot cannot recur silently.
- **Fix doc drift (E3)**: reconcile keyword counts across README and `docs/index.md` to the actual count; add the 6 missing keywords to README tables (`Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap Confidence Interval`, `MCP.Compare Tool Discoverability`, `Skill.Get Activation Pass At K`, `Skill.Compare Discoverability`); populate `docs/troubleshooting/` (aggregating per-recipe Symptom/Cause/Fix tables) and populate-or-unlink `docs/coming-from/` + `docs/scenarios/`; fix persona mislabels in the README recipe table; fix the 4 known-broken recipe code blocks skip-listed in `_KNOWN_BROKEN_BLOCKS` (`docs/recipes/README.md`, DF-14.3-S1) and remove them from the skip list.
- **Close doc gaps (E4)**: document the 4 required skill frontmatter fields (`name`, `description`, `allowed-tools`, `disable-model-invocation`) in the README with a minimal `SKILL.md` example; document the hook `settings.json` input schema `HooksLibrary.Get Config` expects; add a "Running against a real model" page (provider/model string + API key env vars); add API-key lines (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) to `.env.example`.
- **Strip internal jargon from user-facing surfaces**: remove Story/FR/ADR/DF-X-SY/C-number references and persona-journey slots from README, recipes, and scaffold templates (keep them in ADRs, contracts, and maintainer docs). De-emphasize the determinism-tier system in first-run docs to a short note with a link.

Not breaking: `MCP.Call Tool` change is additive; all other changes are template/doc/CI fixes.

## Capabilities

### New Capabilities

- `init-scaffold`: the `agenteval init` scaffold — templates must produce a suite and scenario that run green out of the box, verified by a CI end-to-end smoke test.
- `mcp-tool-invocation`: `MCP.Call Tool` argument-passing contract — natural RF kwargs and the `arguments=` dict form both work.
- `documentation-accuracy`: user-facing docs match the shipped surface — keyword counts, keyword tables, recipe code blocks, linked directories, persona labels.
- `onboarding-documentation`: the docs a first-run user needs that exist nowhere readable today — skill frontmatter fields, hook config input schema, mock-to-live-model guide, API-key env vars, jargon-free user-facing prose.

### Modified Capabilities

_None — `openspec/specs/` currently contains only `opencode-cli-adapter`, which is untouched._

## Impact

- **Code**: `src/AgentEval/_init/templates/` (all scaffold templates touched by fixes + jargon strip), `src/AgentEval/mcp/library.py` (`call_tool` signature gains `**kwargs` routing).
- **Tests**: new end-to-end init smoke test (CI); existing `tests/unit/test_init_cli.py` stays (file-writing checks); `tests/integration/recipes/test_all_recipes_dryrun.py` `_KNOWN_BROKEN_BLOCKS` shrinks to empty for the 4 fixed blocks.
- **Docs**: `README.md`, `docs/index.md`, `docs/recipes/*` (4 broken blocks + jargon), `docs/troubleshooting/` (populated), `docs/coming-from/` + `docs/scenarios/` (populated or unlinked), new "Running against a real model" page, `.env.example`.
- **Related sibling changes (NOT in scope here)**: `accept-real-claude-hook-config` (parsing real Claude Code hook `settings.json` — this change only *documents* the currently-accepted schema), `compose-single-library-import` (fixing the 4-library import sprawl — this change keeps the explicit `WITH NAME` imports in templates/docs until that lands). No new capabilities (multi-turn, red-team, etc.) are added here.
