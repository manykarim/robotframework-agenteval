## Context

`robotframework-agenteval` is post-refocus on `main`: four independently importable RF libraries (`HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`) on the `AgentEval._core` spine, 44 keywords, deterministic base install with `[mcp]`/`[llm]`/`[all]` extras. It has never been released. Existing release infra: `release.yml` (semver-tag → `uv build` + `uv publish` via PyPI OIDC trusted publishing, gated by the `TRUSTED_PUBLISHER_CONFIGURED` repo variable) and `docs-build.yml` (libdoc + `check_doc_keyword_count.py` + contract-sections; GitHub Pages deploys `docs/`). Both were authored for the old architecture and carry stale assumptions. Version `0.0.1`, `Development Status :: 2 - Pre-Alpha`.

## Goals / Non-Goals

**Goals:**
- Ship v0.1.0 (Alpha) to PyPI + GitHub with correct metadata and an accurate changelog.
- Keyword documentation regenerated from the shipped code and **validated to render correctly** — HTML libdoc tables well-formed, README/`docs/index.md` markdown tables render, internal links resolve, documented counts match libdoc.
- The release path (tag → build → publish → GitHub Release) verified end to end, degrading safely to dry-run when the trusted-publisher variable is unset.

**Non-Goals:**
- Any change to library behavior or the 44-keyword surface.
- Committing to a stable 1.0 API (this is pre-1.0 Alpha).
- Setting up the PyPI-side trusted-publisher claim itself (external, owner-only) — the workflow already supports it; this change documents + gates on it.
- A docs-site theme/tooling overhaul — validate the existing libdoc + Pages output, don't rebuild it.

## Decisions

### D1 — v0.1.0 (Alpha), not 1.0.0
First real publish of a from-scratch rewrite with no external users yet. `0.1.0` signals "usable, API may still evolve"; classifier `3 - Alpha`. Semver tag `v0.1.0` matches `release.yml`'s `v[0-9]+.[0-9]+.[0-9]+*` trigger. **Alternative:** 1.0.0 — rejected: prematurely freezes the surface as a compatibility promise.

### D2 — Rewrite the changelog around the release, drop BMAD provenance
The `[Unreleased]` block documents the superseded `compose-single-library-import` change and opens with a `_bmad-output/...` story-provenance preamble that points at deleted paths. Replace with a clean `## [0.1.0] - <date>` section (Keep a Changelog headings: Added / Changed / Removed) describing the four-library architecture, extras, and the dogfood fixes, and delete the dead provenance preamble. **Why:** the changelog is user-facing release notes; it must describe what actually ships.

### D3 — Validate generated docs with a script, not by eye
Add `scripts/check-doc-rendering.py` (wired into `docs-build.yml` and the local gate) that asserts, over the generated artifacts: (a) each `docs/keywords/*.html` parses as HTML and every `<table>` is well-formed (balanced rows/cells, has a header) and non-empty; (b) README + `docs/index.md` GitHub-flavored markdown tables are well-formed (consistent column counts, present separator row); (c) internal doc links (`docs/**` + README relative links) resolve to existing files/anchors; (d) the five expected libdoc files exist and are non-empty. **Why:** "render correctly" must be machine-checkable and repeatable, not a one-time manual look. **Alternative:** headless-browser screenshot diffing — rejected as overkill for libdoc tables. Keyword-count correctness stays owned by the existing `check_doc_keyword_count.py`.

### D4 — Fix docs-build to sweep every shipped package
`docs-build.yml` walks only `AgentEval.__path__`, so the four top-level `*Library` packages are never import-checked. Extend the sweep to import-walk `HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, and `AgentEval`. Regenerate `docs/keywords/*.html` for those five as part of the docs build (and commit the regenerated HTML so Pages serves current docs).

### D5 — Keep release.yml's trusted-publishing + dry-run gate; verify, don't rewrite
`release.yml` already does OIDC trusted publishing with a `TRUSTED_PUBLISHER_CONFIGURED` dry-run gate and `id-token: write`. Keep that. Add/verify a **GitHub Release** step (create the release from the tag with changelog-derived notes + the built wheel/sdist as assets). Prune any remaining "Story 9.1"/`release-pending label` Phase-1 placeholder that references retired process. **Why:** the mechanism is sound; it needs currency + the GitHub-Release half, not a rebuild.

### D6 — Tag from a green main, publish gated externally
Sequence: land all prep on a branch → PR → merge to `main` → confirm `main` CI green → `git tag v0.1.0 && git push origin v0.1.0`. The tag triggers `release.yml`; PyPI publish happens only if `TRUSTED_PUBLISHER_CONFIGURED` is set (else the run dry-runs and still produces artifacts + the GitHub Release). **Why:** never tag off unverified state; keep the irreversible PyPI push behind an explicit, owner-controlled gate.

## Risks / Trade-offs

- **[PyPI publish is irreversible + name-squats the version]** → gate on `TRUSTED_PUBLISHER_CONFIGURED`; dry-run by default; a re-release needs a new version. Verify the built wheel installs the four libraries in a clean venv before tagging.
- **[Regenerated HTML committed to the repo can drift from code]** → the `check_doc_keyword_count.py` gate + the new rendering check run in CI, so drift fails the build.
- **[docs-build sweep now imports `[mcp]`/`[llm]` surfaces]** → CI installs `--all-extras`, so imports resolve; the libraries lazy-import heavy deps so a base sweep would still pass.
- **[Changelog/version mismatch]** → a task cross-checks `pyproject` version == changelog heading == tag before pushing.
- **[GitHub Release notes drift from changelog]** → derive the release body from the `## [0.1.0]` changelog section programmatically.

## Migration Plan

1. Branch `release/v0.1.0`.
2. Version + classifier bump; metadata audit.
3. Rewrite `CHANGELOG.md` for 0.1.0.
4. Regenerate libdoc; reconcile README/index tables + counts.
5. Add `scripts/check-doc-rendering.py`; wire into `docs-build.yml` + local gate; fix the sweep-import.
6. Verify `release.yml` (build + GitHub Release + dry-run gate); prune stale placeholders.
7. Full gate green (incl. the new rendering check) + clean-venv install smoke of the built wheel.
8. PR → review → merge to `main`; confirm `main` CI green.
9. `git tag v0.1.0 && git push origin v0.1.0`; watch the release run; confirm the GitHub Release (and PyPI, if configured).

**Rollback:** everything before the tag is a normal PR revert. After a live PyPI publish, roll forward with `0.1.1` (PyPI disallows re-uploading a version).

## Open Questions

- Is the `TRUSTED_PUBLISHER_CONFIGURED` repo variable + the PyPI trusted-publisher claim already set up? If not, the v0.1.0 tag dry-runs on PyPI (still cutting the GitHub Release) until the owner configures it, then a `v0.1.0` re-tag or a `v0.1.1` publishes.
- Should the GitHub Release be marked "pre-release" (fits Alpha)? Leaning yes.
