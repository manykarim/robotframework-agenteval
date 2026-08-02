## Context

Established empirically while fixing the blank-page bug:

- **Keyword-doc pages render entirely client-side.** The `<body>` is ~empty (9
  bytes); jQuery + Handlebars + a Parcel ES-module bundle read the embedded
  `libdoc = {...}` model and populate `#keywords-container` etc. If the render JS
  throws, the page shows the fallback "Opening library documentation failed" and the
  container stays empty.
- **ES modules do not execute from `file://`** (origin/CORS). A render check must
  serve the files over **http**; I confirmed rendering works from a local
  `http.server` and from the live GitHub Pages URL, and fails identically (blank) on
  a bad model in both.
- **The model is valid JSON even when the page is blank**, which is precisely why
  the model-only gate is fake-green. Only a real browser distinguishes "valid data"
  from "actually renders".
- Reproduced with `chrome --headless=new --dump-dom` over http + a post-JS DOM
  assertion (keyword names present, no fallback text). Verified the live production
  page renders after the fix.

The `documentation-rendering` spec's "Generated documentation renders correctly"
requirement already promises a repeatable render validation runnable in CI + locally;
this change makes that promise real at the browser level.

## Goals / Non-Goals

**Goals:**

- A gate that loads each keyword-doc page in a real headless browser and asserts it
  displays its keywords, catching *any* client-side render failure (not just the one
  crash pattern already guarded at model level).
- Reliable in CI (self-contained browser, robust waits) and runnable locally.

**Non-Goals:**

- No visual/screenshot regression or pixel diffing — assert content presence, not
  appearance.
- No browser in the main `pytest`/`robot` job — only in `docs-build`.
- Keep the existing stdlib-only model/table/link checks — this is additive.
- Not reconciling the stale "44 across 4 libraries" prose in the
  `documentation-rendering` spec (a separate cleanup).

## Decisions

### D1 — Driver: Playwright (Python), with a zero-dep fallback documented

Recommend **Playwright for Python** as a dev/docs dependency:

- It **bundles its own Chromium** via `playwright install chromium`, so CI does not
  depend on a system Chrome being present/compatible — more reliable than
  `setup-chrome` + system binary.
- It supports **explicit waits** (`page.wait_for_function(...)` until the keyword
  list is populated) and **console-error capture** (`page.on("console"/"pageerror")`)
  — far less flaky than a fixed `--virtual-time-budget` guess.

Documented fallback (no new dependency): `chrome --headless=new --dump-dom` over the
local http server + a post-JS DOM assertion — proven during the fix, but with a
fixed render-wait and no clean console capture. Choose Playwright unless the
maintainer wants zero new dependencies.

### D2 — Serve over HTTP, one server for all files

Start a threaded `http.server` bound to `127.0.0.1:0` (ephemeral port) rooted at
`docs/keywords/`, load `http://127.0.0.1:<port>/<Lib>.html` for each expected libdoc
file, tear the server down at the end. (ES modules require an http origin.)

### D3 — Per-page assertions (content, not pixels)

For each file, from its embedded model derive the expected keyword names, then in the
rendered page assert:

1. every expected keyword name appears in the rendered `#keywords-container`
   (a partial render — some keywords missing — also fails),
2. no `pageerror` / uncaught console `error` fired during load,
3. the fallback element ("Opening library documentation failed" / a visible
   "JavaScript disabled" block) is not shown.

Waiting: poll until `#keywords-container` has children (or a fixed keyword count
matching the model), with a bounded timeout, rather than a fixed sleep.

### D4 — CI wiring + local ergonomics

- `docs-build.yml`: add a browser-install step (`uv run playwright install --with-deps
  chromium`, cached) and a step `uv run python scripts/check-doc-render-headless.py`;
  add the script to the workflow `paths:` triggers.
- Local: the script detects a missing browser and **skips with a clear install hint**
  (`playwright install chromium`) so the base local gate still works offline; in CI an
  env signal (e.g. `CI=true`) makes a missing browser a hard failure, so CI can never
  silently skip the check.
- Keep it out of the fast pre-commit set (browser-heavy); it lives in `docs-build`.

## Risks / Trade-offs

- **Browser install adds CI time (~1–2 min, cached).** Acceptable for a docs-only job
  gated on doc/spec/script paths; not on every push to `main` code.
- **Headless rendering can be flaky** if waits are wrong → Mitigation: wait on a
  concrete post-render condition (container populated) with a bounded timeout, assert
  on content, and fail with the captured console error for fast diagnosis.
- **A new dev dependency (Playwright).** → Mitigation: dev/docs group only (never
  shipped); the documented `chrome --dump-dom` fallback exists if a zero-dep gate is
  preferred.
- **Local skip could hide the check** → Mitigation: CI never skips (hard-fail on
  missing browser under `CI`), and the skip message names the one-line install.

## Migration Plan

Additive — a new gate + a dev dependency + a CI step. No product/API change. Rollback
is removing the step + script. The existing gates are untouched.

## Open Questions

- **Playwright vs the zero-dep `chrome --dump-dom` fallback** — decide at
  implementation time based on the maintainer's dependency appetite; Playwright is the
  recommended default for reliability.
- **Whether to also assert per-keyword *sections* render** (args table, doc HTML) or
  stop at "all keyword names present" — start with names + no-error (catches the whole
  blank-page class); deepen later if a subtler partial-render bug appears.
