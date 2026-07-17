## 1. Version + metadata

- [x] 1.1 Branch `release/v0.1.0` off `main`.
- [x] 1.2 Bump `pyproject.toml` `version` to `0.1.0` and the classifier to `Development Status :: 3 - Alpha`.
- [x] 1.3 Audit the rest of `pyproject.toml` release metadata (name, description, keywords, classifiers, URLs, license, readme, `requires-python`) — ensure the description names the four testing surfaces and nothing references deleted modules/adapters.

## 2. Changelog

- [x] 2.1 Remove the dead `_bmad-output/`-provenance preamble from `CHANGELOG.md`.
- [x] 2.2 Replace the stale `[Unreleased]` (`compose-single-library-import`) block with a `## [0.1.0] - <date>` section (Keep a Changelog Added/Changed/Removed) describing: the four independently importable libraries + `AgentEval` composite, the 44-keyword surface, the base + `[mcp]`/`[llm]`/`[all]` extras layout, the RF-voice docs reframe, and the notable dogfood fixes (skills optional fields, subagent comma-string tools, MCP coverage bridge + warm session, hooks event/command checks).
- [x] 2.3 Verify `pyproject` version == changelog heading (`0.1.0`).

## 3. Keyword documentation

- [x] 3.1 Regenerate `docs/keywords/*.html` via `robot.libdoc` for `HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, and `AgentEval`; confirm exactly those five files exist (no stale libdoc for a deleted library).
- [x] 3.2 Reconcile `README.md` + `docs/index.md` keyword tables + counts against libdoc; run `scripts/check_doc_keyword_count.py` green (44/4).

## 4. Generated-doc rendering validation

- [x] 4.1 Add `scripts/check-doc-rendering.py`: (a) parse each `docs/keywords/*.html`, assert every `<table>` is well-formed (header + balanced rows/cells) and non-empty; (b) assert README + `docs/index.md` GFM tables are well-formed (consistent column counts + separator row); (c) assert internal doc links (relative links under `docs/**` + in README) resolve to existing files; (d) assert the five expected libdoc files exist and are non-empty. Exit non-zero naming the offending file/table/link.
- [x] 4.2 Run the rendering check locally; fix any malformed table, broken link, or stale reference it surfaces.
- [x] 4.3 Wire `check-doc-rendering.py` into `docs-build.yml` and the `.pre-commit-config.yaml` + CLAUDE.md local gate.

## 5. docs-build + release workflow currency

- [x] 5.1 Fix the `docs-build.yml` sweep-import step to import-walk all five shipped packages (`Hooks/MCP/Skills/Subagents Library` + `AgentEval`), not only `AgentEval.*`.
- [x] 5.2 Verify `release.yml`: builds wheel+sdist for the four-package project; publishes via PyPI OIDC trusted publishing gated on `TRUSTED_PUBLISHER_CONFIGURED` (dry-run otherwise); prune any retired Story-9.1 / `release-pending label` Phase-1 placeholder that no longer applies.
- [x] 5.3 Add/verify a GitHub Release step in `release.yml`: on the tag, create the release with notes derived from the `[0.1.0]` changelog section, attach the built wheel + sdist, and mark it pre-release (Alpha).

## 6. Pre-tag verification

- [x] 6.1 Full local gate green: ruff, ruff format, mypy, license, contract-sections, doc-keyword-count, **doc-rendering**, pytest (224), robot smoke (tests/robot).
- [x] 6.2 Build the wheel (`uv build`) and install it into a FRESH venv; assert `import HooksLibrary, MCPLibrary, SkillsLibrary, SubagentsLibrary` works on the base install and that `[mcp]`/`[llm]` gate correctly.
- [x] 6.3 Rendering backstop: covered by the automated `check-doc-rendering.py` (validates every libdoc HTML table + keyword args are well-formed and non-empty); no manual browser step available in this environment.

## 7. Release

- [ ] 7.1 PR `release/v0.1.0` → `main`; wait for CI green (test matrix + docs-build + CodeQL); merge.
- [ ] 7.2 On updated `main`, confirm CI green, then create + push the tag: `git tag -a v0.1.0 -m "v0.1.0" && git push origin v0.1.0`.
- [ ] 7.3 Watch the release workflow: confirm the GitHub Release is created (assets attached), and — if `TRUSTED_PUBLISHER_CONFIGURED` is set — the PyPI publish succeeds and `pip install robotframework-agenteval==0.1.0` resolves. Record dry-run vs live honestly.

## 8. Spec archive

- [ ] 8.1 `openspec validate prepare-v0-1-0-release` passes; archive the change so `release-packaging` + `documentation-rendering` join the baseline.
