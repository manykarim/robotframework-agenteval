## ADDED Requirements

### Requirement: Version and release metadata are correct for v0.1.0

`pyproject.toml` SHALL declare `version = "0.1.0"` and `Development Status :: 3 - Alpha`, and its release metadata (name, description, keywords, classifiers, URLs, license, readme) SHALL describe the four-surface library. The declared version SHALL match the changelog heading and the release tag.

#### Scenario: Version is consistent across sources

- **WHEN** the release is prepared
- **THEN** `pyproject.toml` version, the `CHANGELOG.md` release heading, and the git tag all read `0.1.0` / `v0.1.0`

#### Scenario: Classifier reflects a real release

- **WHEN** metadata is audited
- **THEN** the Development Status classifier is `3 - Alpha` (not `2 - Pre-Alpha`) and the description names the four testing surfaces

### Requirement: The distribution ships all four libraries and the extras layout

The built wheel and sdist SHALL include the `AgentEval` spine plus the four top-level packages (`HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`), and SHALL declare the `[mcp]`, `[llm]`, and `[all]` extras with a minimal deterministic base. A clean-environment install of the built wheel SHALL import all four libraries.

#### Scenario: Clean-venv install imports every library

- **WHEN** the built wheel is installed into a fresh virtual environment
- **THEN** `import HooksLibrary, MCPLibrary, SkillsLibrary, SubagentsLibrary` succeeds with only the base dependencies

#### Scenario: Extras are declared

- **WHEN** the wheel metadata is inspected
- **THEN** `mcp`, `llm`, and `all` optional-dependency groups are present

### Requirement: The changelog is an accurate v0.1.0 release record

`CHANGELOG.md` SHALL carry a `## [0.1.0]` section (Keep a Changelog Added/Changed/Removed headings) describing the four-library architecture, the 44-keyword surface, the extras layout, and the notable fixes, and SHALL NOT reference deleted `_bmad-output/` paths or the superseded `compose-single-library-import` change as unreleased.

#### Scenario: Changelog describes what ships

- **WHEN** a reader opens `CHANGELOG.md`
- **THEN** the `[0.1.0]` section describes the four importable libraries + extras and contains no dead `_bmad-output/` provenance link

### Requirement: A semver tag publishes to PyPI and cuts a GitHub Release

Pushing a `v0.1.0` tag SHALL trigger the release workflow to build the wheel + sdist and publish to PyPI via OIDC trusted publishing when `TRUSTED_PUBLISHER_CONFIGURED` is set (otherwise dry-run), and SHALL create a GitHub Release for the tag with notes derived from the `[0.1.0]` changelog section and the built artifacts attached.

#### Scenario: Tag triggers the release workflow

- **WHEN** `v0.1.0` is pushed
- **THEN** the release workflow builds the distribution and creates the GitHub Release with changelog-derived notes

#### Scenario: PyPI publish is gated

- **WHEN** the release workflow runs and `TRUSTED_PUBLISHER_CONFIGURED` is unset
- **THEN** the PyPI publish step is skipped (dry-run) while the build + GitHub Release still complete
