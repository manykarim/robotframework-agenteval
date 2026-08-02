# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Headless-render gate: prove each keyword-doc page actually renders in a browser.

The libdoc pages render client-side (jQuery + Handlebars + an ES-module bundle read
the embedded ``libdoc`` model into the DOM). A page can carry a valid JSON model yet
display nothing if the render JS throws - which is exactly how ``MCPLibrary.html``
went blank once (``Callable[[], Any]`` -> a null nested type -> ``renderTypeInfo``
crashed on ``null.union``). The model-only checks in ``check-doc-rendering.py`` are
structurally blind to that; only a real browser catches it.

For each ``docs/keywords/*.html`` this gate serves it over HTTP (ES modules do not
execute from ``file://``), loads it in headless Chromium, waits for the client-side
render, and asserts every keyword name from the embedded model appears in the
rendered DOM with no uncaught console error and no failure fallback.

Locally it SKIPS with an install hint when no browser is available; in CI (``CI``
set) a missing browser is a hard failure, so CI can never silently skip.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import json
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

KEYWORDS_DIR = Path(__file__).resolve().parent.parent / "docs" / "keywords"

# The shipped libdoc files (mirrors check-doc-rendering.EXPECTED_LIBDOCS).
EXPECTED_LIBDOCS = (
    "HooksLibrary",
    "MCPLibrary",
    "SkillsLibrary",
    "SubagentsLibrary",
    "MetricsLibrary",
    "StatLibrary",
    "AgentLibrary",
    "AgentEval",
)

_LIBDOC_MODEL_RE = re.compile(r"libdoc = (\{.*?\})\n</script>", re.DOTALL)
_RENDER_TIMEOUT_MS = 20_000
_FALLBACK_TEXT = "Opening library documentation failed"


def _expected_keyword_names(html_path: Path) -> list[str]:
    """Keyword names declared in the page's embedded libdoc model."""
    m = _LIBDOC_MODEL_RE.search(html_path.read_text(encoding="utf-8"))
    if not m:
        return []
    try:
        model = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    return [kw.get("name", "") for kw in model.get("keywords", []) if kw.get("name")]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # silence request logging
        pass


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    """Serve ``directory`` on an ephemeral localhost port (ES modules need http)."""
    handler = functools.partial(_QuietHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def _skip_or_fail(reason: str) -> int:
    """Skip locally (exit 0) but hard-fail in CI (exit 1) so CI never silently skips."""
    if os.environ.get("CI"):
        print(f"::error::headless doc-render gate could not run in CI: {reason}")
        return 1
    print(f"SKIP: headless doc-render gate not run ({reason}).")
    print("      Install the browser once with: uv run playwright install chromium")
    return 0


def _render_check(port: int) -> list[str]:
    """Render each page in headless Chromium; return a list of failure messages."""
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        for name in EXPECTED_LIBDOCS:
            path = KEYWORDS_DIR / f"{name}.html"
            if not path.is_file():
                continue  # existence handled by the model-level gate
            expected = _expected_keyword_names(path)
            errors.clear()
            page.goto(f"http://127.0.0.1:{port}/{name}.html", wait_until="load")
            # A timeout here just means it never rendered; that is caught below by the
            # empty container / missing-keyword assertions.
            with contextlib.suppress(Exception):
                page.wait_for_function(
                    "() => { const c = document.getElementById('keywords-container');"
                    " return c && c.children.length > 0; }",
                    timeout=_RENDER_TIMEOUT_MS,
                )

            container_text = (
                page.eval_on_selector("#keywords-container", "el => el.innerText")
                if page.query_selector("#keywords-container")
                else ""
            )
            fallback_shown = (
                page.locator(f"text={_FALLBACK_TEXT}").count() > 0
                and page.locator(f"text={_FALLBACK_TEXT}").first.is_visible()
            )

            if errors:
                failures.append(f"docs/keywords/{name}.html: client-side error: {errors[0]}")
            elif fallback_shown:
                failures.append(f"docs/keywords/{name}.html: shows the render-failure fallback ({_FALLBACK_TEXT!r}).")
            else:
                missing = [kw for kw in expected if kw not in container_text]
                if missing:
                    failures.append(
                        f"docs/keywords/{name}.html: {len(missing)} of {len(expected)} keyword(s) did not render, "
                        f"e.g. {missing[:3]}"
                    )
        browser.close()
    return failures


def main() -> int:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return _skip_or_fail("playwright is not installed")

    if not KEYWORDS_DIR.is_dir():
        print(f"::error::{KEYWORDS_DIR} does not exist")
        return 1

    httpd, port = _serve(KEYWORDS_DIR)
    try:
        try:
            failures = _render_check(port)
        except Exception as exc:  # noqa: BLE001 - browser launch/other; skip locally, fail in CI
            if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
                return _skip_or_fail("Chromium is not installed for playwright")
            raise
    finally:
        httpd.shutdown()

    if failures:
        print("::error::Headless doc-render gate failed:")
        for f in failures:
            print(f"  - {f}")
        print(f"\n{len(failures)} page(s) did not render. Fix the keyword docs and re-run.")
        return 1

    rendered = sum(1 for n in EXPECTED_LIBDOCS if (KEYWORDS_DIR / f"{n}.html").is_file())
    print(
        f"PASS: all {rendered} keyword-doc pages render in a headless browser (keywords present, no client-side error)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
