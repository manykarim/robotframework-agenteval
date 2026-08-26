## ADDED Requirements

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
