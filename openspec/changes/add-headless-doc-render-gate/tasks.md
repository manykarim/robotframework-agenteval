## 1. Browser driver dependency

- [ ] 1.1 Add the browser driver to a dev/docs dependency group in `pyproject.toml` (recommended: `playwright`); do NOT add it to the shipped/base install. Re-lock.
- [ ] 1.2 Confirm `uv run playwright install chromium` provisions a self-contained Chromium (so CI needs no system Chrome).

## 2. The render gate (`scripts/check-doc-render-headless.py`)

- [ ] 2.1 Serve `docs/keywords/` over a threaded `http.server` on `127.0.0.1:0` (ephemeral port); tear it down at the end.
- [ ] 2.2 For each expected libdoc file, parse its embedded `libdoc` model to derive the expected keyword names.
- [ ] 2.3 Load `http://127.0.0.1:<port>/<Lib>.html` in headless Chromium; capture `pageerror`/console `error`; wait (bounded) until `#keywords-container` is populated.
- [ ] 2.4 Assert per file: every expected keyword name is present in the rendered DOM; no console error fired; the "Opening library documentation failed" / visible "JavaScript disabled" fallback is absent. On failure, name the file + the captured console error.
- [ ] 2.5 Local-skip vs CI-hard-fail: if no browser is available, skip locally with a clear `playwright install chromium` hint, but hard-fail when `CI` is set so CI never silently skips.

## 3. CI wiring

- [ ] 3.1 `.github/workflows/docs-build.yml`: add a browser-install step (`uv run playwright install --with-deps chromium`, cached) and a step `uv run python scripts/check-doc-render-headless.py`.
- [ ] 3.2 Add `scripts/check-doc-render-headless.py` (and the workflow file) to the workflow `paths:` triggers.

## 4. Prove it (the forcing-function check)

- [ ] 4.1 Negative test: temporarily regenerate one HTML with a `Callable[[], Any]`-style null-nested arg type (or inject a render-throwing model) and confirm the gate FAILS naming that file + the `renderTypeInfo`/`union` console error.
- [ ] 4.2 Positive: the gate PASSES on the current 8 shipped pages.
- [ ] 4.3 (belt-and-suspenders) Confirm the gate also catches a page whose keyword list renders partially (some expected names missing), not only a fully-blank page.

## 5. Docs + close out

- [ ] 5.1 Add a CONTRIBUTING/README note: run the render gate locally via `uv run playwright install chromium` then the script; note it also runs in `docs-build`.
- [ ] 5.2 Full local gate (ruff/format/mypy/license/contract/doc-count/doc-render/keyword-examples/pytest/robot) + the new render gate.
- [ ] 5.3 `openspec validate add-headless-doc-render-gate --strict`; archive after implementation lands + gates green + the negative test demonstrably fails on a bad page.
