# Tasks: fix-first-run-experience

## 1. MCP.Call Tool natural kwargs (unblocks the scaffold's natural form)

- [x] 1.1 Extend `call_tool` in `src/AgentEval/mcp/library.py` with `**kwargs: Any`: kwargs-only
      → arguments dict; `arguments=`-only → unchanged; both → structured File/Line/Field/Fix-style
      error, no tool call made (design D1)
- [x] 1.2 Update the `Call Tool` docstring: kwargs form as primary example, dict form retained,
      string-coercion caveat with `${5}` typed syntax, reserved names (`handle`, `tool_name`,
      `arguments`) caveat
- [x] 1.3 Unit tests: kwargs form, dict form regression, both-forms error; invoke through the
      full `@keyword`/`@tier` decorator chain (walk `__wrapped__` per project monkeypatch lesson),
      not just the inner function
- [x] 1.4 Integration test against the bundled echo server:
      `Call Tool    ${handle}    echo_back    text=hello` returns `is_error == False` with the
      echoed content

## 2. Fix the scaffold templates

- [x] 2.1 `example_mcp_runtime.robot`: add
      `Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP`; call
      `MCP.Call Tool    ${HANDLE}    echo_back    text=hello`; assert on `is_error` /
      `content` (no `.success`, no `echo`, no `message`)
- [x] 2.2 `scenario.yaml`: rewrite `mcp_servers` as a list of strings; verify it loads via
      `Load Scenario` against `src/AgentEval/scenarios/loader.py`
- [x] 2.3 Strip internal jargon from ALL files in `src/AgentEval/_init/templates/` (Story/Epic/
      FR/ADR/DF-X-SY/C-numbers, review-provenance comments, persona-journey labels) — rewrite
      comments as user-facing documentation (`agenteval.yaml`, `README.md`, both example suites,
      `example-skill.md`, `example_skill_validation.robot`, `mcp.json`, `scenario.yaml`)
- [x] 2.4 Manually verify in a clean temp dir: `agenteval init` then the scaffolded README's run
      command exits 0 with zero edits

## 3. CI scaffold smoke test

- [x] 3.1 Add `tests/integration/test_init_scaffold_e2e.py`: subprocess `agenteval init` into
      `tmp_path`, run `robot` on the scaffolded suites (mock provider + bundled echo server),
      assert exit code 0; hard timeout
- [x] 3.2 Same test module: `Load Scenario` the scaffolded `tests/fixtures/scenario.yaml` and
      assert it parses
- [x] 3.3 Wire the smoke test into `ci.yml` (keyless job path) and confirm it runs on push; prove
      the gate by temporarily reverting one template fix locally and watching the test fail

## 4. Doc drift — counts, tables, links, personas, recipes

- [x] 4.1 Re-derive the true unique keyword count from libdoc across the 6 libraries; update
      `README.md` (currently "51 keywords / 6 libraries") and `docs/index.md` (currently
      "5 libraries · 49 keywords") to the derived number
- [x] 4.2 Add the 6 missing keywords to the README tables: `Stat.Mann Whitney U`,
      `Stat.Cliff Delta`, `Stat.Bootstrap Confidence Interval`,
      `MCP.Compare Tool Discoverability`, `Skill.Get Activation Pass At K`,
      `Skill.Compare Discoverability`
- [x] 4.3 Add a docs-build CI check asserting the documented counts in `README.md` +
      `docs/index.md` match the libdoc-derived count (anchor on the canonical count sentence /
      table rows, not free prose)
- [x] 4.4 Create `docs/troubleshooting/README.md` aggregating every per-recipe Symptom/Cause/Fix
      table, organized by symptom, each entry linking back to its recipe; add an entry for
      "scaffold from an older version fails"
- [x] 4.5 Remove README links to `docs/coming-from/` and `docs/scenarios/` and delete the empty
      dirs (unless D2's scenario work yields a near-free 1-page schema doc for `docs/scenarios/`
      — implementer's call per design open question)
- [x] 4.6 Rewrite the README recipe table to describe recipes by what they demonstrate (removes
      the Devon/Raj/Many vs Priya/Mei persona mislabels as a side effect)
- [x] 4.7 Fix the 4 recipe code blocks skip-listed in `_KNOWN_BROKEN_BLOCKS`
      (`tests/integration/recipes/test_all_recipes_dryrun.py`, catalogued DF-14.3-S1) against the
      shipped keyword surface until `robot --dryrun` passes; empty the skip list; run the harness
      to confirm 8/8 eligible blocks pass

## 5. Onboarding doc gaps

- [x] 5.1 README "Writing a skill file" subsection: the 4 required frontmatter fields (`name`,
      `description`, `allowed-tools`, `disable-model-invocation`) + minimal complete `SKILL.md`
      example consistent with `_init/templates/example-skill.md`; smoke-verify the example passes
      skill validation (executable-doc precheck)
- [x] 5.2 Document the hook config input schema `HooksLibrary.Get Config` accepts (flat
      `command`/`args`/`timeout`/`matcher` entries) with a valid example; add the explicit
      warning that real Claude Code nested `settings.json` is not yet accepted, pointing at the
      `accept-real-claude-hook-config` change; smoke-verify the example parses via `Get Config`
- [x] 5.3 Write `docs/running-against-a-real-model.md`: provider selection
      (`AGENTEVAL_PROVIDER`), model string format, per-provider API-key env vars, minimal
      copy-paste example, cost-guardrail note; link from README quick start
- [x] 5.4 Add commented `ANTHROPIC_API_KEY=` / `OPENAI_API_KEY=` entries to `.env.example` with a
      pointer to the real-model page

## 6. Jargon strip + tier de-emphasis (README, index, recipes)

- [x] 6.1 Strip Story/Epic/FR/ADR/DF-X-SY/C-number identifiers, persona-journey slots, and
      review-provenance notes from `README.md` and `docs/index.md`; convert load-bearing ADR
      references to topic-named links; also strip provenance comments from `.env.example`
- [x] 6.2 Same pass over `docs/recipes/*.md` (prose and code comments), preserving the
      Symptom/Cause/Fix tables and `## Use case` / `## Keywords used` / `## Walkthrough` headings
      the docs-build check requires
- [x] 6.3 Reduce the tier system in README/quick-start to one short note linking to the full
      tier documentation
- [x] 6.4 Verify no regressions: grep the in-scope surfaces for identifier patterns (expect zero
      hits), run the docs-build checks and the recipe dryrun harness locally

## 7. Full verification

- [x] 7.1 `uv run pytest tests/` green (including new smoke + Call Tool tests);
      `uv run ruff check src/ tests/` + `uv run mypy src/` clean
- [x] 7.2 End-to-end replay of dossier E1 in a clean dir: `agenteval init` → documented run
      command → green, zero edits; `Load Scenario` on the scaffolded YAML succeeds
- [x] 7.3 Confirm doc claims: README and `docs/index.md` counts match libdoc; README tables list
      all keywords; no README link targets an empty dir; recipe harness reports 0 known-broken
      blocks
