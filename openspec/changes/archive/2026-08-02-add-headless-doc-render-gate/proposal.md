## Why

The keyword-doc pages are rendered **client-side** (jQuery + Handlebars + a Parcel
ES-module bundle read the embedded `libdoc` model into the DOM). A page can carry a
perfectly valid JSON model yet display **nothing** if the render JS throws — which is
exactly what happened: `Callable[[], Any]` serialized a `null` nested type, RF's
`renderTypeInfo` crashed on `null.union`, and `MCPLibrary.html` + `AgentEval.html`
went blank in production for a full release cycle.

The existing `check-doc-rendering.py` gate — and a follow-up model-level guard added
with that fix — parse the **JSON model**; they never **render** the page. So they
are structurally blind to render-time failures: the fix guards the one crash
*pattern* we found (null nested arg types), but any *other* JS error that blanks a
page would still ship green. Only a real browser catches the whole class.

## What Changes

- **A CI gate that actually renders each keyword-doc page in a headless browser** and
  asserts it displays. For every `docs/keywords/*.html`, the gate SHALL:
  - serve the file over **http** (ES modules do not execute from `file://`),
  - load it in headless Chromium and wait for the client-side render,
  - assert **every keyword name from the embedded model appears in the rendered DOM**,
  - assert **no uncaught console error** occurred and the *"Opening library
    documentation failed"* / *"JavaScript disabled"* fallback is not shown.
- **Wired into `docs-build.yml`** (browser installed in the job) and **runnable
  locally**; it SHALL skip with a clear message when no browser is available locally,
  but SHALL run (not skip) in CI.
- The existing fast, stdlib-only model/table/link checks stay — this is an
  additional, stronger gate, not a replacement.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `documentation-rendering`: ADD a requirement that generated keyword-doc HTML is
  verified to render in a real browser (keywords appear, no client-side error), in CI
  and runnable locally — closing the model-validates-but-page-is-blank gap.

## Impact

- **New script** `scripts/check-doc-render-headless.py` (serve + headless render +
  assert), plus a dev/docs dependency for the browser driver
  (**Playwright (Python)** recommended — it bundles its own Chromium via
  `playwright install chromium`, so CI does not depend on system Chrome; a
  `chrome --headless --dump-dom` variant is the zero-dependency fallback).
- **`.github/workflows/docs-build.yml`**: a browser-install step + a step running the
  new gate; add its path to the workflow's `paths:` triggers.
- **`pyproject.toml`**: the browser-driver dependency in a dev/docs group.
- **Docs/contributing note**: how to run the render gate locally
  (`playwright install chromium` once).
- **Out of scope:** visual/screenshot regression; adding a browser to the main test
  job; reconciling the stale "44 across 4 libraries" prose already present in the
  `documentation-rendering` spec (separate cleanup).
