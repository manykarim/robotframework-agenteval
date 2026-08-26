# documentation-rendering Specification

## Purpose
TBD - created by archiving change prepare-v0-1-0-release. Update Purpose after archive.
## Requirements
### Requirement: Keyword documentation is generated from the shipped libraries

`docs/keywords/*.html` SHALL be regenerated via RF libdoc for `HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, and the `AgentEval` composite, and SHALL match the keywords the built libraries expose. No libdoc file SHALL exist for a library that is no longer shipped.

#### Scenario: Every shipped library has current libdoc

- **WHEN** the keyword docs are generated
- **THEN** exactly the five expected `docs/keywords/*.html` files exist, each non-empty, and each lists the keywords its library actually exposes

### Requirement: Documented keyword counts match libdoc

The keyword count stated in `README.md` and `docs/index.md` SHALL equal the libdoc-derived count across the four surface libraries (44 across 4), enforced by the existing count check.

#### Scenario: Counts agree

- **WHEN** the doc keyword-count check runs
- **THEN** README and `docs/index.md` agree with the libdoc-derived total and the check passes

### Requirement: Generated documentation renders correctly

A repeatable validation SHALL assert that generated docs render correctly: every `<table>` in `docs/keywords/*.html` is well-formed (has a header, balanced rows/cells) and non-empty; every GitHub-flavored markdown table in `README.md` and `docs/index.md` is well-formed (consistent column counts with a separator row); and internal documentation links (relative links under `docs/**` and in `README.md`) resolve to existing files. This validation SHALL run in `docs-build.yml` and be runnable locally.

#### Scenario: Malformed table fails the check

- **WHEN** a keyword-doc HTML table or a README markdown table is malformed (unbalanced columns, missing header/separator)
- **THEN** the rendering validation fails and names the offending file + table

#### Scenario: Broken internal link fails the check

- **WHEN** a doc links to a path that does not exist (e.g. a deleted recipe)
- **THEN** the validation fails and names the broken link

#### Scenario: Clean docs pass

- **WHEN** the docs are current and well-formed
- **THEN** the rendering validation passes

### Requirement: The docs build import-sweeps every shipped package

`docs-build.yml` SHALL import-walk all shipped packages — `HooksLibrary`, `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, and `AgentEval` — so a broken import in any surface library fails the docs build, not just a break under `AgentEval.*`.

#### Scenario: A broken surface import fails the docs build

- **WHEN** any module in a surface library fails to import
- **THEN** the docs-build sweep reports the failure and the build fails

### Requirement: Generated keyword docs are verified to render in a real browser

A gate SHALL verify that each generated `docs/keywords/*.html` actually renders its
documentation in a headless browser — not merely that its embedded model is valid
JSON. Because the pages render client-side and ES modules do not execute from
`file://`, the gate SHALL serve the files over HTTP, load each in headless Chromium,
wait for the client-side render, and assert that every keyword name present in the
page's embedded libdoc model appears in the rendered DOM, that no uncaught console
error occurred, and that the failure fallback (e.g. "Opening library documentation
failed" / "JavaScript disabled") is not displayed. This gate SHALL run in
`docs-build.yml` and SHALL be runnable locally; locally it MAY skip with a clear
message when no browser is available, but in CI it SHALL run and fail the build on a
render failure.

#### Scenario: A page that renders passes

- **WHEN** a keyword-doc page loads in the headless browser and its client-side
  script populates the keyword list
- **THEN** every keyword name from the page's model is found in the rendered DOM, no
  console error is reported, and the gate passes for that file

#### Scenario: A page whose script throws fails the gate

- **WHEN** a keyword-doc page's client-side render throws (e.g. a malformed type
  crashes the renderer) so the keyword list is empty or the failure fallback shows
- **THEN** the gate fails and names the offending file (and, when available, the
  console error), rather than passing on a valid-but-unrendered model

#### Scenario: The gate runs in CI and is runnable locally

- **WHEN** `docs-build.yml` runs
- **THEN** the browser is installed and the render gate executes (it does not skip);
  and a developer can run the same gate locally after installing the browser driver

