## Why

The four-surface refocus is merged to `main`, the tree is clean, and CI is green — but the project has never shipped. It still carries `version = "0.0.1"` / `Development Status :: 2 - Pre-Alpha`, the `CHANGELOG.md` `[Unreleased]` section describes the *superseded* `compose-single-library-import` work (not the refocus) and cites deleted `_bmad-output/` paths, and the docs-generation pipeline is stale: `docs-build.yml` sweep-imports only `AgentEval.*`, so it never checks the four top-level surface libraries at all. Before the first real release we need the metadata, changelog, and — the requester's emphasis — the **generated documentation (libdoc keyword docs + README/site tables) to be current and to render correctly**.

This change prepares and cuts the **v0.1.0 (Alpha)** first release to PyPI and GitHub: correct version/metadata, an accurate changelog, regenerated + validated keyword documentation, and a verified release-automation path, ending in a pushed `v0.1.0` tag.

## What Changes

- **Version + metadata**: bump `0.0.1 → 0.1.0`; `Development Status :: 2 - Pre-Alpha → 3 - Alpha`; verify `pyproject.toml` release metadata (name, description, keywords, classifiers, URLs, license, readme) reflects the four-surface library.
- **CHANGELOG**: replace the stale `[Unreleased]` (old `compose-single-library-import` + `_bmad-output` provenance) with a real `## [0.1.0]` entry documenting the four-surface refocus, the 44-keyword surface, the extras layout, and the dogfood fixes. Drop the dead `_bmad-output`-provenance preamble.
- **Keyword documentation**: regenerate `docs/keywords/*.html` (libdoc) for `HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, and the `AgentEval` composite from the shipped code; ensure README + `docs/index.md` keyword tables and counts match the built libraries.
- **Generated-doc rendering validation** (requester emphasis): validate that generated docs render correctly — libdoc HTML tables are well-formed, README/`docs/index.md` markdown tables render, internal doc links resolve, and the documented keyword count matches libdoc. Add a repeatable validation step rather than eyeballing.
- **docs-build fix**: update the `docs-build.yml` sweep-import to cover **all** shipped packages (the four `*Library` packages + `AgentEval`), not just `AgentEval.*`.
- **Release automation**: verify `release.yml` builds the four-package wheel + sdist and publishes via PyPI OIDC trusted publishing; ensure the tag push creates a **GitHub Release** with notes derived from the changelog. Document the one-time PyPI trusted-publisher setup + the `TRUSTED_PUBLISHER_CONFIGURED` gate.
- **Cut the release**: after the above land and CI is green on `main`, create and push the `v0.1.0` semver tag (triggers the release workflow; PyPI publish occurs iff the trusted-publisher variable is set, else dry-run).

## Capabilities

### New Capabilities
- `release-packaging`: A tagged v0.1.0 release to PyPI + GitHub — correct version/metadata, a wheel+sdist that ships all four libraries and the extras layout, an accurate changelog, semver-tag → PyPI OIDC trusted-publishing, and a GitHub Release with changelog-derived notes.
- `documentation-rendering`: Generated documentation for the four-library surface is current and renders correctly — regenerated libdoc keyword docs, README/site keyword tables and counts matching the built libraries, a validation that HTML/markdown tables render and internal links resolve, and a docs-build import-sweep that covers every shipped package.

### Modified Capabilities
<!-- None. evaluation-core owns library packaging/voice at the design level; this change adds the release + doc-rendering concerns as new capabilities rather than altering evaluation-core's requirements. -->

## Impact

- **Files**: `pyproject.toml` (version, classifier), `CHANGELOG.md` (rewrite), `docs/keywords/*.html` (regenerated), `README.md` + `docs/index.md` (table/count reconciliation if needed), `.github/workflows/docs-build.yml` (sweep-import fix), possibly a new `scripts/check-doc-rendering.py`.
- **Release surface**: a `v0.1.0` git tag; a PyPI release of `robotframework-agenteval` 0.1.0 (gated on trusted-publisher config); a GitHub Release.
- **No source/behavior change** to the four libraries — this is packaging, docs, and release only.
- **Prerequisite (external)**: PyPI project + trusted-publisher claim configured, and the `TRUSTED_PUBLISHER_CONFIGURED` repo variable set, for the tag push to publish live rather than dry-run.
