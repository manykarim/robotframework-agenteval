OpenAI Codex v0.133.0
--------
workdir: /home/many/workspace/robotframework-agenteval
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019e8320-3527-7940-b323-653efb2ffdb7
--------
user
# Adversarial Code Review — Story 13.4: CohortHeatmap.as_html() + write_html() (PRD FR55)

You are a SENIOR REVIEWER. Find REAL bugs, REAL spec drift, REAL correctness defects in Story 13.4.

## Project context

- robotframework-agenteval — Python 3.12+, RF 7.x.
- Story 13.4 ships Phase-2 `CohortHeatmap.as_html() -> str` + `write_html(path) -> Path` methods + `_PASS_RATE_PALETTE` constant + `_color_for_pass_rate` helper.
- Story file: `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md`
- Builds on Story 8b.2 (`CohortHeatmap` + `as_ascii` + `as_dict`) + Story 13.3 (`from_comparison` multi-column).
- Stories 13.1-13.3 reviews each produced 3-6 HIGH findings; review Story 13.4 at same rigor.

## Review prompt (re-derive cited facts)

Re-derive every dev claim: PRD L1583 (FR55 amendment), epics.md L2193-2205 (Story 13.4 spec), existing `src/AgentEval/_heatmap/models.py`. Flag drift as HIGH.

## Specific behavioral probes

1. **HTML validity**: parse the as_html output via `html.parser.HTMLParser` with strict mode + browser-like tolerance. Probe edge cases: empty heatmap, single-row, 3+ adapters, missing cells.
2. **Color palette boundary correctness**: verify each boundary (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) maps to expected hex. Verify edge case `rate == 1.0` doesn't fall through to gray missing-cell.
3. **HTML escaping (security)**: probe injection attempts: `task_id="<script>alert(1)</script>"`, model name with `&` `<` `>` `"`, model name with `javascript:` URL prefix. Are any unescaped in the output?
4. **write_html path edge cases**: empty string, relative path with `..`, absolute path with symlinks, read-only filesystem (mock via temp + chmod), path pointing to a directory (not a file).
5. **Baseline regression test stability**: are the recorded baselines reproducible across Python versions? Does the `{value:.2f}` formatting produce locale-dependent decimal separators on non-en-US locales? Float-to-str roundtrip stability?
6. **CSS embedding completeness**: verify NO external URLs (`url(http://...)`, `@import`, `src=`, `href=` to external). Verify the inline `style` attributes can be safely scraped by external tooling.
7. **`_color_for_pass_rate` performance**: O(N) linear scan vs O(1) binary search. For 5 entries, no issue, but probe with synthetic large palettes (edge case).
8. **L-4 structural-regression claim**: dev claims byte-equality vs recorded baselines + manual inspection. Are the baselines actually committed? Verify with `ls tests/fixtures/heatmap/`.
9. **Empty heatmap edge cases**: `tasks=()` but `models=("m0",)` (asymmetric empty). Does as_html handle this consistently?
10. **PRD amendment verification**: was the FR55 wording actually amended per D-2 + AC-13.4.8?

## Categorization

- **HIGH**: Real bug / spec drift / correctness defect.
- **MED**: Significant quality issue / test gap.
- **LOW**: Minor improvement / style.

## Output format

```
### [HIGH/MED/LOW]-N: <title>
**File:** `<path>:<line>`
**Issue:** <2-3 sentences>
**Evidence:** <code/test output>
**Fix:** <concrete suggestion>
```

End with: `**Total: X HIGH + Y MED + Z LOW**`.

Diff at `/tmp/story-13-4-review.diff`.

---

## Diff to review:

```diff
diff --git a/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
new file mode 100644
index 0000000..aa90bd9
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
@@ -0,0 +1,304 @@
+# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
+
+Status: review
+
+## Story
+
+As a **post-run reviewer** sharing results outside the terminal,
+I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
+So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
+
+## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
+
+- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
+
+- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
+
+- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
+
+- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
+  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
+  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
+  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
+  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
+  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
+  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
+  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
+
+- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
+
+- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
+
+- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
+
+- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
+
+- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
+
+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
+  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
+  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
+  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
+
+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
+
+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
+
+- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
+- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
+- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
+- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
+- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
+
+## Acceptance Criteria
+
+### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
+
+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
+
+```python
+def as_html(self) -> str:
+    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
+
+    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
+    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
+    `<style>`), and `<body>` containing a `<table>` with header row +
+    one row per task. Each cell carries inline `style="background-color: <hex>;
+    color: <text-hex>;"` for the Pass@k color gradient.
+
+    All styling embedded in `<head><style>...</style>`. NO external
+    stylesheet links, NO external image references, NO `<script>`
+    elements — operators can email the file or save to shared storage
+    and view offline.
+
+    Empty heatmap (no tasks OR no models): returns a minimal valid
+    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
+    `as_ascii()`'s `"(empty heatmap)"` sentinel).
+
+    Color gradient (Pass@k → background hex; text hex chosen for
+    readable contrast per WCAG AA):
+        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
+        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
+        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
+        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
+        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
+        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
+
+    Returns:
+        Standalone HTML5 document as a string.
+    """
+```
+
+Implementation outline:
+1. Empty case: return minimal document.
+2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
+3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
+4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
+5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
+
+### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
+
+`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
+
+```python
+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
+    # (lower_bound_inclusive, background_hex, text_hex)
+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
+    (0.2, "#f97316", "#ffffff"),  # orange
+    (0.4, "#eab308", "#0f172a"),  # yellow
+    (0.6, "#84cc16", "#0f172a"),  # lime
+    (0.8, "#22c55e", "#ffffff"),  # green — high success
+)
+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
+```
+
+Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
+- `rate is None` → `_MISSING_CELL_STYLE`.
+- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
+
+The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
+
+### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
+
+`src/AgentEval/_heatmap/models.py` adds after `as_html`:
+
+```python
+def write_html(self, path: str | Path) -> Path:
+    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
+
+    Args:
+        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
+            paths resolve against `Path.cwd()`. Empty string raises
+            `ValueError`. Parent directories created with
+            `parents=True, exist_ok=True`.
+
+    Returns:
+        The resolved write path (post-`Path.resolve()`).
+
+    Raises:
+        ValueError: When `path` is the empty string.
+        OSError: When the filesystem write fails (read-only, permission, etc.).
+            NOT caught — propagates to the caller.
+    """
+```
+
+Implementation:
+- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
+- `resolved = Path(path).resolve()`.
+- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
+- `resolved.write_text(self.as_html(), encoding="utf-8")`.
+- `return resolved`.
+
+### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
+
+NEW file. Coverage:
+
+- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
+- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
+- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
+- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
+- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
+- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
+
+### AC-13.4.5 — Baseline HTML fixtures for structural regression test
+
+NEW files:
+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
+
+Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
+
+### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
+
+NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
+
+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
+- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
+
+### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
+
+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
+- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
+- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
+- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
+
+### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
+
+`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
+
+### AC-13.4.9 — All-gates pass
+
+- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
+- `uv run ruff check src/ tests/` clean.
+- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
+- `uv run mypy src/` clean (≥107 src files).
+
+### AC-13.4.10 — Sprint-status
+
+`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
+
+## Tasks / Subtasks
+
+- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
+- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
+- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
+- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
+- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
+- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
+- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
+- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
+
+## Dev Notes
+
+Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
+
+- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
+- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
+
+**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
+
+**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
+
+**Cross-story lesson application:**
+- L-1: stability-surface MUST register the new methods (AC-13.4.6).
+- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
+- L-3: not RF `@keyword`-decorated; no `@tier` classification.
+- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
+- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
+
+### Project Structure Notes
+
+- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
+- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
+- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
+- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
+
+### References
+
+- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
+- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
+- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
+- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
+- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
+
+## Dev Agent Record
+
+### Agent Model Used
+
+claude-opus-4-7[1m]
+
+### Debug Log References
+
+2 mid-dev catches:
+1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
+2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.
+
+### Completion Notes List
+
+Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.
+
+- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
+- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
+- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
+- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
+- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
+- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
+- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
+- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
+- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
+- **AC-13.4.10**: sprint-status flipped to `review`.
+
+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)
+
+- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
+- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
+- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
+- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
+- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).
+
+### In-flight spec amendments
+
+1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.
+
+2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.
+
+### File List
+
+**New files:**
+- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.
+
+**Modified files:**
+- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method.
+- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
+- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
+- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
index 2f6c828..99f4117 100644
--- a/_bmad-output/implementation-artifacts/deferred-work.md
+++ b/_bmad-output/implementation-artifacts/deferred-work.md
@@ -390,6 +390,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
 
 - **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
 
+## Deferred from: story-13.4 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
+
+- **DF-13.4-S1 (Phase-2.5 image-based visual regression test for `as_html()`)** — Story 13.4 D-7 in-flight amendment 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baselines) instead of the epic L2205-mandated image-based visual regression. Image regression requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) — heavy deps. Phase-2.5 evaluates whether structural baselines + manual inspection suffice OR whether image regression has empirical value warranting the deps. Catalogued as C92. Effort: M. Phase-2.5.
+
+- **DF-13.4-S2 (Phase-2.5 color-blind-safe palette mode for `as_html()`)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4's default 5-stop red-orange-yellow-lime-green palette is NOT WCAG 2.1 AA color-blind safe (~8% of males have red-green color blindness). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). Catalogued as C93. Effort: M. Phase-2.5.
+
+- **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
+
 ---
 
 *Update this file as new deferred items emerge from future reviews.*
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index 24798b7..be01029 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -154,6 +154,6 @@ development_status:
   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
-  13-4-cohort-heatmap-html-rendering: backlog
+  13-4-cohort-heatmap-html-rendering: review
   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
   epic-13-retrospective: optional
diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
index 604fb45..a8e6c7d 100644
--- a/_bmad-output/planning-artifacts/prd.md
+++ b/_bmad-output/planning-artifacts/prd.md
@@ -1580,7 +1580,7 @@ Each FR states the testable, observable capability the library must provide. For
 - **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
 - **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
 - **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
-- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
+- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
 - **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
 - **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
 - **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
index 051e962..df97c10 100644
--- a/docs/contracts/stability-surface.md
+++ b/docs/contracts/stability-surface.md
@@ -122,6 +122,15 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
 - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 
+### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
+
+Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
+
+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
+- `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
+- `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
+
 ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
 
 Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
index 05247b2..d4e41d9 100644
--- a/docs/phase-1-5-carry-overs.md
+++ b/docs/phase-1-5-carry-overs.md
@@ -116,7 +116,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
 | **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
 | **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
 
-**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
+| **C92** | **Phase-2.5: Image-based visual regression test for `as_html()` (`DF-13.4-S1`).** Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baseline fixtures); epic L2205 mandated "visual regression test against a recorded baseline image" using headless browser + pixel-diff. Headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) are heavy deps; Phase-2.5 evaluates whether the structural baseline + manual browser inspection is sufficient OR whether image regression has empirical value. *Surfaced via Story 13.4 spec D-10 + D-7 in-flight amendment 2026-06-01.* | Story 13.4 D-7 in-flight amendment — Phase-2 structural-baseline ceiling | maintainability | M | TBD | Headless browser screenshot capture + image-diff vs recorded baseline; integration into `dogfood-integration.yml` CI matrix. |
+| **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
+| **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
+
+**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL (Story 13.4 adds 3 M).
 
 ## Execution policy
 
diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
index 9be3020..bcc13aa 100644
--- a/src/AgentEval/_heatmap/models.py
+++ b/src/AgentEval/_heatmap/models.py
@@ -12,12 +12,14 @@
 # See the License for the specific language governing permissions and
 # limitations under the License.
 
-"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
+"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
 
 from __future__ import annotations
 
+import html
 from dataclasses import dataclass
-from typing import TYPE_CHECKING
+from pathlib import Path
+from typing import TYPE_CHECKING, Final
 
 if TYPE_CHECKING:
     from AgentEval.discoverability.schema import (
@@ -28,6 +30,55 @@ if TYPE_CHECKING:
 __all__ = ["CohortHeatmap"]
 
 
+# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
+# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
+# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
+#   [0.0, 0.2) → red (high failure)
+#   [0.2, 0.4) → orange
+#   [0.4, 0.6) → yellow
+#   [0.6, 0.8) → lime
+#   [0.8, 1.0] → green (high success)
+# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
+# mode (viridis/magma sequential per WCAG 2.1 AA).
+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
+    # (lower_bound_inclusive, background_hex, text_hex)
+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
+    (0.2, "#f97316", "#ffffff"),  # orange
+    (0.4, "#eab308", "#0f172a"),  # yellow
+    (0.6, "#84cc16", "#0f172a"),  # lime
+    (0.8, "#22c55e", "#ffffff"),  # green — high success
+)
+# Missing cell (cell[(task, model)] not present in `cells`): light gray.
+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
+
+
+def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
+    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
+
+    Args:
+        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
+
+    Returns:
+        ``(background_hex, text_hex)`` tuple.
+
+    Edge cases:
+        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
+        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
+        - ``rate < 0.0`` → first stop (red); not validated upstream so
+          defensively clamps to the bottom rather than raising.
+    """
+    if rate is None:
+        return _MISSING_CELL_STYLE
+    # Linear scan: walk the palette + return the HIGHEST entry whose lower
+    # bound is `<=` the rate. The palette is sorted ascending by lower bound
+    # so we walk forward and remember the last match.
+    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
+    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
+        if rate >= lower:
+            bg, txt = candidate_bg, candidate_txt
+    return (bg, txt)
+
+
 @dataclass(frozen=True)
 class CohortHeatmap:
     """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
@@ -162,3 +213,128 @@ class CohortHeatmap:
             body_lines.append("│ " + " │ ".join(cells) + " │")
 
         return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
+
+    def as_html(self) -> str:
+        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
+
+        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
+        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
+        `<style>`), and `<body>` containing a `<table>` with header row +
+        one row per task. Each Pass@k cell carries inline
+        `style="background-color: <hex>; color: <text-hex>;"` for the
+        color gradient.
+
+        All styling embedded in `<head><style>...</style>`. NO external
+        stylesheet links, NO external image references, NO `<script>`
+        elements — operators can email the file or save to shared
+        storage and view offline.
+
+        Empty heatmap (no tasks OR no models): returns a minimal valid
+        document with `<body><p>(empty heatmap)</p></body>` (symmetric
+        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
+
+        Pass@k color gradient (5-stop hue palette; text color chosen for
+        WCAG AA contrast):
+            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
+            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
+            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
+            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
+            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
+            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
+              with text "—" (em-dash, matching `as_ascii()` fallback).
+
+        See module-level `_PASS_RATE_PALETTE` constant for the canonical
+        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
+        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
+        alternative palette.
+
+        Security: all user-provided strings (task IDs, model names)
+        pass through ``html.escape`` before insertion to prevent HTML
+        injection. Float Pass@k values are formatted via
+        ``f"{value:.2f}"`` (safe — no escape needed).
+
+        Returns:
+            Standalone HTML5 document as a string.
+        """
+        if not self.tasks or not self.models:
+            return (
+                "<!DOCTYPE html>\n"
+                '<html lang="en">\n'
+                "<head>\n"
+                '  <meta charset="utf-8">\n'
+                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
+                "</head>\n"
+                "<body>\n"
+                "  <p>(empty heatmap)</p>\n"
+                "</body>\n"
+                "</html>\n"
+            )
+
+        data = self.as_dict()
+        # Build header row.
+        header_cells = ["<th>Task</th>"]
+        for model in self.models:
+            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
+        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
+
+        # Build body rows.
+        body_rows: list[str] = []
+        for task in self.tasks:
+            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
+            for model in self.models:
+                value = data.get(task, {}).get(model)
+                bg, txt_color = _color_for_pass_rate(value)
+                cell_text = "—" if value is None else f"{value:.2f}"
+                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
+            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
+
+        return (
+            "<!DOCTYPE html>\n"
+            '<html lang="en">\n'
+            "<head>\n"
+            '  <meta charset="utf-8">\n'
+            "  <title>AgentEval Cohort Heatmap</title>\n"
+            "  <style>\n"
+            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
+            "    table { border-collapse: collapse; }\n"
+            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
+            "    th { background-color: #0f172a; color: #ffffff; }\n"
+            "  </style>\n"
+            "</head>\n"
+            "<body>\n"
+            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
+            "</body>\n"
+            "</html>\n"
+        )
+
+    def write_html(self, path: str | Path) -> Path:
+        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
+
+        Args:
+            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
+                Relative paths resolve against ``Path.cwd()``. Empty
+                string raises ``ValueError``. Parent directories are
+                created with ``parents=True, exist_ok=True``.
+
+        Returns:
+            The resolved write path (post-``Path.resolve()``).
+
+        Raises:
+            ValueError: When ``path`` is the empty string.
+            OSError: When the filesystem write fails (read-only,
+                permission denied, etc.). NOT caught — propagates to
+                the caller.
+
+        Notes:
+            - Convenience companion to ``as_html`` per Story 13.4 D-2.
+            - Writes UTF-8 encoded text.
+            - Story 13.4 D-5: empty-string path rejected up-front
+              instead of relying on ``Path("").write_text`` which
+              would write to the current directory's empty filename.
+        """
+        if isinstance(path, str) and path == "":
+            raise ValueError("write_html requires a non-empty path; got empty string")
+        resolved = Path(path).resolve()
+        resolved.parent.mkdir(parents=True, exist_ok=True)
+        resolved.write_text(self.as_html(), encoding="utf-8")
+        return resolved
diff --git a/tests/fixtures/heatmap/baseline_2_adapter.html b/tests/fixtures/heatmap/baseline_2_adapter.html
new file mode 100644
index 0000000..ac48555
--- /dev/null
+++ b/tests/fixtures/heatmap/baseline_2_adapter.html
@@ -0,0 +1,21 @@
+<!DOCTYPE html>
+<html lang="en">
+<head>
+  <meta charset="utf-8">
+  <title>AgentEval Cohort Heatmap</title>
+  <style>
+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
+    table { border-collapse: collapse; }
+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
+    th { background-color: #0f172a; color: #ffffff; }
+  </style>
+</head>
+<body>
+<table>
+  <tr><th>Task</th><th>adapter_red</th><th>adapter_green</th></tr>
+  <tr><td>task_alpha</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
+  <tr><td>task_beta</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #eab308; color: #0f172a;">0.50</td></tr>
+  <tr><td>task_gamma</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
+</table>
+</body>
+</html>
diff --git a/tests/fixtures/heatmap/baseline_3_adapter.html b/tests/fixtures/heatmap/baseline_3_adapter.html
new file mode 100644
index 0000000..5987ff9
--- /dev/null
+++ b/tests/fixtures/heatmap/baseline_3_adapter.html
@@ -0,0 +1,21 @@
+<!DOCTYPE html>
+<html lang="en">
+<head>
+  <meta charset="utf-8">
+  <title>AgentEval Cohort Heatmap</title>
+  <style>
+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
+    table { border-collapse: collapse; }
+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
+    th { background-color: #0f172a; color: #ffffff; }
+  </style>
+</head>
+<body>
+<table>
+  <tr><th>Task</th><th>a</th><th>b</th><th>c</th></tr>
+  <tr><td>t0</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
+  <tr><td>t1</td><td style="background-color: #84cc16; color: #0f172a;">0.70</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td><td style="background-color: #f97316; color: #ffffff;">0.30</td></tr>
+  <tr><td>t2</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
+</table>
+</body>
+</html>
diff --git a/tests/unit/_heatmap/test_models_html.py b/tests/unit/_heatmap/test_models_html.py
new file mode 100644
index 0000000..8bfd92e
--- /dev/null
+++ b/tests/unit/_heatmap/test_models_html.py
@@ -0,0 +1,402 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
+
+Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
+SPECIFIC structural counts (table count, tr count, td count, palette
+hex presence) — NOT just "html.parser doesn't crash."
+
+Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
+anchor test asserts the required strings appear in the docstring.
+"""
+
+from __future__ import annotations
+
+from html.parser import HTMLParser
+from pathlib import Path
+
+import pytest
+
+from AgentEval._heatmap.models import (
+    _MISSING_CELL_STYLE,
+    CohortHeatmap,
+    _color_for_pass_rate,
+)
+
+# --------------------------------------------------------------------------- #
+# `_color_for_pass_rate` helper (4 tests)                                     #
+# --------------------------------------------------------------------------- #
+
+
+@pytest.mark.parametrize(
+    "rate,expected_bg",
+    [
+        (0.0, "#ef4444"),  # red — bottom stop
+        (0.19, "#ef4444"),  # still red
+        (0.2, "#f97316"),  # orange boundary
+        (0.39, "#f97316"),
+        (0.4, "#eab308"),  # yellow
+        (0.5, "#eab308"),
+        (0.6, "#84cc16"),  # lime
+        (0.79, "#84cc16"),
+        (0.8, "#22c55e"),  # green
+        (1.0, "#22c55e"),  # top stop
+    ],
+)
+def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
+    """Each color stop boundary maps to the correct background hex."""
+    bg, _txt = _color_for_pass_rate(rate)
+    assert bg == expected_bg
+
+
+def test_color_for_pass_rate_none_returns_missing_style() -> None:
+    """None input → missing-cell light-gray + slate-900 text."""
+    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
+
+
+def test_color_for_pass_rate_exactly_one_returns_green() -> None:
+    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
+    bg, txt = _color_for_pass_rate(1.0)
+    assert bg == "#22c55e"
+    assert txt == "#ffffff"
+
+
+def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
+    """Defensive: negative rate → bottom stop (red) rather than raising."""
+    bg, _txt = _color_for_pass_rate(-0.1)
+    assert bg == "#ef4444"
+
+
+# --------------------------------------------------------------------------- #
+# `as_html` happy paths (5 tests)                                             #
+# --------------------------------------------------------------------------- #
+
+
+def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
+    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
+    h = CohortHeatmap(tasks=(), models=(), cells=())
+    html = h.as_html()
+    assert "<!DOCTYPE html>" in html
+    assert "(empty heatmap)" in html
+    assert "</html>" in html
+
+
+def test_as_html_single_model_3_tasks() -> None:
+    """1 column × 3 rows produces correctly-shaped HTML."""
+    h = CohortHeatmap(
+        tasks=("t0", "t1", "t2"),
+        models=("m0",),
+        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
+    )
+    html = h.as_html()
+    # Header row: <th>Task</th><th>m0</th>
+    assert html.count("<th>") == 2
+    # Body rows: 3 <tr>
+    assert html.count("<tr>") == 4  # 1 header + 3 body rows
+    # Body cells: 6 <td> (3 task names + 3 values)
+    assert html.count("<td") == 6
+    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
+    assert "#22c55e" in html
+    assert "#eab308" in html
+    assert "#ef4444" in html
+
+
+def test_as_html_3_adapter_3_tasks() -> None:
+    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
+    h = CohortHeatmap(
+        tasks=("t0", "t1", "t2"),
+        models=("a", "b", "c"),
+        cells=(
+            ("t0", "a", 1.0),
+            ("t0", "b", 0.5),
+            ("t0", "c", 0.0),
+            ("t1", "a", 1.0),
+            ("t1", "b", 0.5),
+            ("t1", "c", 0.0),
+            ("t2", "a", 1.0),
+            ("t2", "b", 0.5),
+            ("t2", "c", 0.0),
+        ),
+    )
+    html = h.as_html()
+    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
+    assert html.count("<td") == 12
+    # 4 header <th>: Task + a + b + c.
+    assert html.count("<th>") == 4
+
+
+def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
+    """A cell missing from the input → em-dash + light-gray background."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0", "m1"),
+        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
+    )
+    html = h.as_html()
+    assert "—" in html
+    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
+
+
+def test_as_html_pass_rates_formatted_two_decimals() -> None:
+    """Pass@k values rendered as 2-decimal floats."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 0.123456),),
+    )
+    html = h.as_html()
+    assert "0.12" in html
+    # NOT showing the unrounded version.
+    assert "0.123456" not in html
+
+
+# --------------------------------------------------------------------------- #
+# HTML validity (3 tests)                                                     #
+# --------------------------------------------------------------------------- #
+
+
+class _StructuralHTMLParser(HTMLParser):
+    """Count opening tags + collect script data for defense-in-depth tests."""
+
+    def __init__(self) -> None:
+        super().__init__()
+        self.tag_open_counts: dict[str, int] = {}
+        self.script_data: list[str] = []
+        self._in_script = False
+
+    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
+        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
+        if tag == "script":
+            self._in_script = True
+
+    def handle_endtag(self, tag: str) -> None:
+        if tag == "script":
+            self._in_script = False
+
+    def handle_data(self, data: str) -> None:
+        if self._in_script:
+            self.script_data.append(data)
+
+
+def test_as_html_parses_via_stdlib_html_parser() -> None:
+    """`html.parser.HTMLParser` parses the output without raising."""
+    h = CohortHeatmap(
+        tasks=("t0", "t1"),
+        models=("m0", "m1"),
+        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
+    )
+    parser = _StructuralHTMLParser()
+    parser.feed(h.as_html())
+    parser.close()
+    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
+    assert parser.tag_open_counts.get("table", 0) == 1
+    # tr = 1 (header) + 2 (body rows) = 3.
+    assert parser.tag_open_counts.get("tr", 0) == 3
+    # th = 1 (Task header) + 2 (model headers).
+    assert parser.tag_open_counts.get("th", 0) == 3
+    # td = 2 tasks × (1 task name + 2 models) = 6.
+    assert parser.tag_open_counts.get("td", 0) == 6
+
+
+def test_as_html_has_no_external_resources() -> None:
+    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 1.0),),
+    )
+    html = h.as_html()
+    # NO external stylesheet link.
+    assert "<link" not in html
+    # NO script element (D-3 explicit prohibition for offline-safety).
+    assert "<script" not in html.lower()
+    # NO external image / font URLs.
+    assert 'src="http' not in html.lower()
+    assert 'href="http' not in html.lower()
+    # NO external `url(...)` references in styles.
+    assert "url(http" not in html.lower()
+
+
+def test_as_html_no_script_data_under_html_parser() -> None:
+    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 1.0),),
+    )
+    parser = _StructuralHTMLParser()
+    parser.feed(h.as_html())
+    parser.close()
+    assert parser.script_data == []
+    assert parser.tag_open_counts.get("script", 0) == 0
+
+
+# --------------------------------------------------------------------------- #
+# HTML escaping (2 tests)                                                     #
+# --------------------------------------------------------------------------- #
+
+
+def test_as_html_escapes_script_tags_in_task_ids() -> None:
+    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
+    malicious = "<script>alert(1)</script>"
+    h = CohortHeatmap(
+        tasks=(malicious,),
+        models=("m0",),
+        cells=((malicious, "m0", 1.0),),
+    )
+    html = h.as_html()
+    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
+    assert "<script>alert(1)</script>" not in html
+    assert "&lt;script&gt;" in html
+
+
+def test_as_html_escapes_special_characters_in_model_names() -> None:
+    """Model names with `&`, `<`, `>` get HTML-escaped."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("A&B<C>D",),
+        cells=(("t0", "A&B<C>D", 0.5),),
+    )
+    html = h.as_html()
+    assert "A&amp;B&lt;C&gt;D" in html
+    # Original unescaped form must NOT appear.
+    assert "A&B<C>D" not in html
+
+
+# --------------------------------------------------------------------------- #
+# `write_html` file ops (4 tests)                                             #
+# --------------------------------------------------------------------------- #
+
+
+def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
+    """write_html writes the same content as as_html + returns the resolved path."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 1.0),),
+    )
+    target = tmp_path / "heatmap.html"
+    result = h.write_html(target)
+    assert result == target.resolve()
+    assert result.exists()
+    assert result.read_text(encoding="utf-8") == h.as_html()
+
+
+def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
+    """write_html creates non-existent parent directories via mkdir(parents=True)."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 0.5),),
+    )
+    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
+    assert not target.parent.exists()
+    result = h.write_html(target)
+    assert result.exists()
+    assert target.parent.is_dir()
+
+
+def test_write_html_empty_string_path_raises_value_error() -> None:
+    """write_html('') raises ValueError per D-5."""
+    h = CohortHeatmap(tasks=(), models=(), cells=())
+    with pytest.raises(ValueError, match="non-empty path"):
+        h.write_html("")
+
+
+def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
+    """Both `str` and `Path` inputs work + return identical resolved paths."""
+    h = CohortHeatmap(
+        tasks=("t0",),
+        models=("m0",),
+        cells=(("t0", "m0", 1.0),),
+    )
+    str_path = str(tmp_path / "a.html")
+    path_obj = tmp_path / "b.html"
+    r1 = h.write_html(str_path)
+    r2 = h.write_html(path_obj)
+    assert r1.exists()
+    assert r2.exists()
+    assert r1 == Path(str_path).resolve()
+    assert r2 == path_obj.resolve()
+
+
+# --------------------------------------------------------------------------- #
+# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
+# --------------------------------------------------------------------------- #
+
+
+def test_as_html_docstring_carries_anchors() -> None:
+    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
+    doc = CohortHeatmap.as_html.__doc__ or ""
+    assert "as_html" in doc.lower() or "AS_HTML" in doc
+    assert "FR55" in doc
+    assert "Phase-2" in doc or "Phase 2" in doc
+    assert "embedded CSS" in doc or "embedded `<style>" in doc
+
+
+# --------------------------------------------------------------------------- #
+# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
+# --------------------------------------------------------------------------- #
+
+
+def _build_2_adapter_baseline() -> CohortHeatmap:
+    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
+    return CohortHeatmap(
+        tasks=("task_alpha", "task_beta", "task_gamma"),
+        models=("adapter_red", "adapter_green"),
+        cells=(
+            ("task_alpha", "adapter_red", 1.0),
+            ("task_alpha", "adapter_green", 0.0),
+            ("task_beta", "adapter_red", 0.5),
+            ("task_beta", "adapter_green", 0.5),
+            ("task_gamma", "adapter_red", 0.0),
+            ("task_gamma", "adapter_green", 1.0),
+        ),
+    )
+
+
+def _build_3_adapter_baseline() -> CohortHeatmap:
+    """Deterministic 3-adapter × 3-task input."""
+    return CohortHeatmap(
+        tasks=("t0", "t1", "t2"),
+        models=("a", "b", "c"),
+        cells=(
+            ("t0", "a", 1.0),
+            ("t0", "b", 0.5),
+            ("t0", "c", 0.0),
+            ("t1", "a", 0.7),
+            ("t1", "b", None),  # missing cell on purpose
+            ("t1", "c", 0.3),
+            ("t2", "a", 0.0),
+            ("t2", "b", 0.0),
+            ("t2", "c", 0.0),
+        ),
+    )
+
+
+def test_html_matches_recorded_baseline_2_adapter() -> None:
+    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
+    expected = fixture.read_text(encoding="utf-8")
+    actual = _build_2_adapter_baseline().as_html()
+    assert actual == expected
+
+
+def test_html_matches_recorded_baseline_3_adapter() -> None:
+    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
+    expected = fixture.read_text(encoding="utf-8")
+    actual = _build_3_adapter_baseline().as_html()
+    assert actual == expected
```

codex
Reviewing Story 13.4 against the actual code, tests, and ratified spec first. I’m checking the shipped `CohortHeatmap` surface, the PRD/epic wording, and then probing the HTML/output edge cases the diff claims to cover.
  → Read shipped CohortHeatmap implementation and ratified Story 13.4 spec sources
  • Run targeted probes for HTML validity, escaping, palette boundaries, and write_html path behavior
  • Draft findings with severity, evidence, and fixes; save review to /tmp/story-13-4-review.diff
exec
/bin/bash -lc 'rg -n "FR55|Story 13.4|L2203|L2205|write_html|as_html|CohortHeatmap" _bmad-output/planning-artifacts/prd.md _bmad-output/planning-artifacts/epics.md src/AgentEval/_heatmap/models.py docs/contracts/stability-surface.md tests/unit/_heatmap/test_models_html.py' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: rg: command not found

exec
/bin/bash -lc 'ls -la tests/fixtures/heatmap && git status --short' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
total 16
drwxrwxr-x  2 many many 4096 Jun  1 14:12 .
drwxrwxr-x 16 many many 4096 Jun  1 14:10 ..
-rw-rw-r--  1 many many  985 Jun  1 14:12 baseline_2_adapter.html
-rw-rw-r--  1 many many 1141 Jun  1 14:12 baseline_3_adapter.html
 A _bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
 M _bmad-output/implementation-artifacts/deferred-work.md
 M _bmad-output/implementation-artifacts/sprint-status.yaml
 M _bmad-output/planning-artifacts/prd.md
 M docs/contracts/stability-surface.md
 M docs/phase-1-5-carry-overs.md
 M src/AgentEval/_heatmap/models.py
 A tests/fixtures/heatmap/baseline_2_adapter.html
 A tests/fixtures/heatmap/baseline_3_adapter.html
 A tests/unit/_heatmap/test_models_html.py
?? _bmad-output/cross-llm-reviews/13-4-claude-opus-findings.md
?? _bmad-output/cross-llm-reviews/13-4-claude-sonnet-findings.md
?? _bmad-output/cross-llm-reviews/13-4-codex-findings.md

codex
The patch is present in the worktree, and the claimed baseline fixtures do exist. I’m switching to direct file reads and runtime probes now since `rg` isn’t available in this environment.
exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/prd.md | sed -n '1578,1588p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  1578	- **FR50 (non-zero exit codes):** RF execution exits with sysexits.h-style per-leaf codes (ratified 2026-05-18 per Story 1a.4 code-review HIGH-6; PRD draft used family codes 1/2/3 — superseded). Phase-1 pinned: `1` = generic assertion failure; `65` = `PollingDisallowedError`; `66` = `CostExceededError`; `67` = `IncompleteTraceError`; `68` = `UnsupportedMCPVersionError`. Remaining `AgentEvalError` leaves get sysexits.h-aligned codes assigned by Epic 8a Story 8a.1 (canonical table at `docs/contracts/error-class-hierarchy.md`). Verifiable via subprocess invocation + exit-code assertion in conformance suite.
  1579	- **FR51 (trace ID in report):** Every test's RF report line includes a `trace_id=<uuid>` attribute linking to the trace artifact at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl`. Verifiable via parsing `output.xml` and asserting every `<test>` element has a `trace_id` attribute.
  1580	- **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
  1581	- **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
  1582	- **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
  1583	- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
  1584	- **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
  1585	- **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
  1586	- **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
  1587	- **FR59 (Tier-1 setup-failure diagnostics):** All Tier-1 keyword setup failures (file not found, parse errors, schema errors, missing MCP server config) raise structured errors with (a) the input path + filename, (b) the offending line number when applicable, (c) a one-sentence remediation hint. Verifiable via conformance fixtures injecting each error class + asserting all 3 elements present.
  1588	

exec
/bin/bash -lc "nl -ba src/AgentEval/_heatmap/models.py | sed -n '1,360p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
    16	
    17	from __future__ import annotations
    18	
    19	import html
    20	from dataclasses import dataclass
    21	from pathlib import Path
    22	from typing import TYPE_CHECKING, Final
    23	
    24	if TYPE_CHECKING:
    25	    from AgentEval.discoverability.schema import (
    26	        DiscoverabilityComparisonResult,
    27	        DiscoverabilityResult,
    28	    )
    29	
    30	__all__ = ["CohortHeatmap"]
    31	
    32	
    33	# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
    34	# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
    35	# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
    36	#   [0.0, 0.2) → red (high failure)
    37	#   [0.2, 0.4) → orange
    38	#   [0.4, 0.6) → yellow
    39	#   [0.6, 0.8) → lime
    40	#   [0.8, 1.0] → green (high success)
    41	# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
    42	# mode (viridis/magma sequential per WCAG 2.1 AA).
    43	_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
    44	    # (lower_bound_inclusive, background_hex, text_hex)
    45	    (0.0, "#ef4444", "#ffffff"),  # red — high failure
    46	    (0.2, "#f97316", "#ffffff"),  # orange
    47	    (0.4, "#eab308", "#0f172a"),  # yellow
    48	    (0.6, "#84cc16", "#0f172a"),  # lime
    49	    (0.8, "#22c55e", "#ffffff"),  # green — high success
    50	)
    51	# Missing cell (cell[(task, model)] not present in `cells`): light gray.
    52	_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
    53	
    54	
    55	def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
    56	    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
    57	
    58	    Args:
    59	        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
    60	
    61	    Returns:
    62	        ``(background_hex, text_hex)`` tuple.
    63	
    64	    Edge cases:
    65	        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
    66	        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
    67	        - ``rate < 0.0`` → first stop (red); not validated upstream so
    68	          defensively clamps to the bottom rather than raising.
    69	    """
    70	    if rate is None:
    71	        return _MISSING_CELL_STYLE
    72	    # Linear scan: walk the palette + return the HIGHEST entry whose lower
    73	    # bound is `<=` the rate. The palette is sorted ascending by lower bound
    74	    # so we walk forward and remember the last match.
    75	    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
    76	    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
    77	        if rate >= lower:
    78	            bg, txt = candidate_bg, candidate_txt
    79	    return (bg, txt)
    80	
    81	
    82	@dataclass(frozen=True)
    83	class CohortHeatmap:
    84	    """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
    85	
    86	    Phase-1: single-model heatmap (rows = tasks, single column = model).
    87	    Multi-model comparison (rows = tasks, columns = models) is Phase-2.
    88	
    89	    The model name in Phase-1 defaults to ``"default"`` unless the caller
    90	    provides one via ``from_discoverability(result, model_name=...)``.
    91	    """
    92	
    93	    tasks: tuple[str, ...]
    94	    models: tuple[str, ...]
    95	    # Mapping: cell[(task_id, model_name)] = pass_at_k.
    96	    # Stored as a frozen-friendly tuple of (task, model, value) triples so the
    97	    # dataclass remains hashable.
    98	    cells: tuple[tuple[str, str, float], ...]
    99	
   100	    @classmethod
   101	    def from_discoverability(
   102	        cls,
   103	        result: DiscoverabilityResult,
   104	        *,
   105	        model_name: str = "default",
   106	    ) -> CohortHeatmap:
   107	        """Build a single-model heatmap from a ``DiscoverabilityResult``.
   108	
   109	        Args:
   110	            result: Story 4.4 ``DiscoverabilityResult``.
   111	            model_name: Column label for the single-model column.
   112	
   113	        Returns:
   114	            ``CohortHeatmap`` instance with one column.
   115	        """
   116	        tasks = tuple(t.task_id for t in result.per_task_results)
   117	        cells = tuple((t.task_id, model_name, t.pass_rate) for t in result.per_task_results)
   118	        return cls(tasks=tasks, models=(model_name,), cells=cells)
   119	
   120	    @classmethod
   121	    def from_comparison(
   122	        cls,
   123	        result: DiscoverabilityComparisonResult,
   124	    ) -> CohortHeatmap:
   125	        """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).
   126	
   127	        Columns = adapter names (preserving input order from ``result.adapters``).
   128	        Rows = task IDs (union across all per-adapter results, preserving
   129	        first-encounter order — defensively handles the edge case where a
   130	        stub adapter dropped a task; in production all adapters run the
   131	        SAME task set so the union equals each adapter's task list).
   132	
   133	        Args:
   134	            result: Story 13.3 ``DiscoverabilityComparisonResult``.
   135	
   136	        Returns:
   137	            ``CohortHeatmap`` with one column per adapter + one row per task.
   138	        """
   139	        # Build the row list as the union preserving first-encounter order.
   140	        seen: set[str] = set()
   141	        tasks_list: list[str] = []
   142	        for adapter in result.adapters:
   143	            for task_result in result.per_adapter_results[adapter].per_task_results:
   144	                if task_result.task_id not in seen:
   145	                    seen.add(task_result.task_id)
   146	                    tasks_list.append(task_result.task_id)
   147	        tasks = tuple(tasks_list)
   148	        models = result.adapters
   149	        cells = tuple(
   150	            (task_result.task_id, adapter, task_result.pass_rate)
   151	            for adapter in result.adapters
   152	            for task_result in result.per_adapter_results[adapter].per_task_results
   153	        )
   154	        return cls(tasks=tasks, models=models, cells=cells)
   155	
   156	    def as_dict(self) -> dict[str, dict[str, float]]:
   157	        """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
   158	        out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
   159	        for task, model, value in self.cells:
   160	            out.setdefault(task, {})[model] = value
   161	        return out
   162	
   163	    def as_ascii(self) -> str:
   164	        """ASCII heatmap with box-drawing characters.
   165	
   166	        Rows = tasks, columns = models, cells = Pass@k as 2-decimal float.
   167	        Empty input → ``"(empty heatmap)"`` placeholder.
   168	        """
   169	        if not self.tasks or not self.models:
   170	            return "(empty heatmap)"
   171	
   172	        data = self.as_dict()
   173	        # Story 8b.2 v0.2.0 kilo/minimax cross-LLM review HIGH-1 patch
   174	        # (2026-05-26): missing cells render as " — " sentinel (em-dash with
   175	        # spaces) instead of silently substituting 0.0, which was
   176	        # indistinguishable from a genuine 0% pass-rate. Operators can now
   177	        # tell missing-from-data apart from real-zero.
   178	        _missing = " — "
   179	
   180	        def _fmt(task: str, model: str) -> str:
   181	            value = data.get(task, {}).get(model)
   182	            return _missing if value is None else f"{value:.2f}"
   183	
   184	        # Compute column widths.
   185	        task_col_width = max(len("Task"), *(len(t) for t in self.tasks))
   186	        model_widths: dict[str, int] = {}
   187	        for model in self.models:
   188	            cells = [_fmt(task, model) for task in self.tasks]
   189	            model_widths[model] = max(len(model), *(len(c) for c in cells))
   190	
   191	        # Render header row.
   192	        header_cells = [
   193	            "Task".ljust(task_col_width),
   194	            *(model.ljust(model_widths[model]) for model in self.models),
   195	        ]
   196	        header_line = "│ " + " │ ".join(header_cells) + " │"
   197	
   198	        # Separator line (top + below header + bottom).
   199	        sep_parts = [
   200	            "─" * (task_col_width + 2),
   201	            *("─" * (model_widths[model] + 2) for model in self.models),
   202	        ]
   203	        top_line = "┌" + "┬".join(sep_parts) + "┐"
   204	        mid_line = "├" + "┼".join(sep_parts) + "┤"
   205	        bot_line = "└" + "┴".join(sep_parts) + "┘"
   206	
   207	        # Body rows.
   208	        body_lines: list[str] = []
   209	        for task in self.tasks:
   210	            cells = [task.ljust(task_col_width)]
   211	            for model in self.models:
   212	                cells.append(_fmt(task, model).ljust(model_widths[model]))
   213	            body_lines.append("│ " + " │ ".join(cells) + " │")
   214	
   215	        return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
   216	
   217	    def as_html(self) -> str:
   218	        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
   219	
   220	        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
   221	        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
   222	        `<style>`), and `<body>` containing a `<table>` with header row +
   223	        one row per task. Each Pass@k cell carries inline
   224	        `style="background-color: <hex>; color: <text-hex>;"` for the
   225	        color gradient.
   226	
   227	        All styling embedded in `<head><style>...</style>`. NO external
   228	        stylesheet links, NO external image references, NO `<script>`
   229	        elements — operators can email the file or save to shared
   230	        storage and view offline.
   231	
   232	        Empty heatmap (no tasks OR no models): returns a minimal valid
   233	        document with `<body><p>(empty heatmap)</p></body>` (symmetric
   234	        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
   235	
   236	        Pass@k color gradient (5-stop hue palette; text color chosen for
   237	        WCAG AA contrast):
   238	            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
   239	            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
   240	            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
   241	            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
   242	            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
   243	            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
   244	              with text "—" (em-dash, matching `as_ascii()` fallback).
   245	
   246	        See module-level `_PASS_RATE_PALETTE` constant for the canonical
   247	        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
   248	        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
   249	        alternative palette.
   250	
   251	        Security: all user-provided strings (task IDs, model names)
   252	        pass through ``html.escape`` before insertion to prevent HTML
   253	        injection. Float Pass@k values are formatted via
   254	        ``f"{value:.2f}"`` (safe — no escape needed).
   255	
   256	        Returns:
   257	            Standalone HTML5 document as a string.
   258	        """
   259	        if not self.tasks or not self.models:
   260	            return (
   261	                "<!DOCTYPE html>\n"
   262	                '<html lang="en">\n'
   263	                "<head>\n"
   264	                '  <meta charset="utf-8">\n'
   265	                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
   266	                "</head>\n"
   267	                "<body>\n"
   268	                "  <p>(empty heatmap)</p>\n"
   269	                "</body>\n"
   270	                "</html>\n"
   271	            )
   272	
   273	        data = self.as_dict()
   274	        # Build header row.
   275	        header_cells = ["<th>Task</th>"]
   276	        for model in self.models:
   277	            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
   278	        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
   279	
   280	        # Build body rows.
   281	        body_rows: list[str] = []
   282	        for task in self.tasks:
   283	            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
   284	            for model in self.models:
   285	                value = data.get(task, {}).get(model)
   286	                bg, txt_color = _color_for_pass_rate(value)
   287	                cell_text = "—" if value is None else f"{value:.2f}"
   288	                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
   289	            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
   290	
   291	        return (
   292	            "<!DOCTYPE html>\n"
   293	            '<html lang="en">\n'
   294	            "<head>\n"
   295	            '  <meta charset="utf-8">\n'
   296	            "  <title>AgentEval Cohort Heatmap</title>\n"
   297	            "  <style>\n"
   298	            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
   299	            "    table { border-collapse: collapse; }\n"
   300	            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
   301	            "    th { background-color: #0f172a; color: #ffffff; }\n"
   302	            "  </style>\n"
   303	            "</head>\n"
   304	            "<body>\n"
   305	            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
   306	            "</body>\n"
   307	            "</html>\n"
   308	        )
   309	
   310	    def write_html(self, path: str | Path) -> Path:
   311	        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
   312	
   313	        Args:
   314	            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
   315	                Relative paths resolve against ``Path.cwd()``. Empty
   316	                string raises ``ValueError``. Parent directories are
   317	                created with ``parents=True, exist_ok=True``.
   318	
   319	        Returns:
   320	            The resolved write path (post-``Path.resolve()``).
   321	
   322	        Raises:
   323	            ValueError: When ``path`` is the empty string.
   324	            OSError: When the filesystem write fails (read-only,
   325	                permission denied, etc.). NOT caught — propagates to
   326	                the caller.
   327	
   328	        Notes:
   329	            - Convenience companion to ``as_html`` per Story 13.4 D-2.
   330	            - Writes UTF-8 encoded text.
   331	            - Story 13.4 D-5: empty-string path rejected up-front
   332	              instead of relying on ``Path("").write_text`` which
   333	              would write to the current directory's empty filename.
   334	        """
   335	        if isinstance(path, str) and path == "":
   336	            raise ValueError("write_html requires a non-empty path; got empty string")
   337	        resolved = Path(path).resolve()
   338	        resolved.parent.mkdir(parents=True, exist_ok=True)
   339	        resolved.write_text(self.as_html(), encoding="utf-8")
   340	        return resolved

exec
/bin/bash -lc 'grep -nE "FR55|as_html|write_html|L2203|L2205|CohortHeatmap" _bmad-output/planning-artifacts/prd.md _bmad-output/planning-artifacts/epics.md src/AgentEval/_heatmap/models.py docs/contracts/stability-surface.md tests/unit/_heatmap/test_models_html.py' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
_bmad-output/planning-artifacts/prd.md:731:          (agenteval init), FR54 (terminal run summary), FR55 (cohort heatmap
_bmad-output/planning-artifacts/prd.md:1583:- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
_bmad-output/planning-artifacts/epics.md:25:  ux_design_requirements: 0  # library has no UI; visual contracts captured as FR34b/FR55/FR58
_bmad-output/planning-artifacts/epics.md:34:This document provides the complete epic and story breakdown for `robotframework-agenteval`, decomposing the requirements from the PRD, Architecture (including ADRs from both PRD-originated and architecture-originated sidecars), and Implementation Readiness Report into implementable stories. UX Design Specification is intentionally absent (library has no UI; visual contracts captured as FR34b / FR55 / FR58 in PRD).
_bmad-output/planning-artifacts/epics.md:149:- **FR55 [P1+P2]:** `Metric.Get Cohort Heatmap <ToolDiscoverabilityResult>` returns `CohortHeatmap` with `as_ascii()` / `as_dict()` (P1); `as_html()` (P2).
_bmad-output/planning-artifacts/epics.md:299:**N/A** — `robotframework-agenteval` is a Python Robot Framework PyPI library with no UI surface. UX-adjacent visual contracts (evidence-block format, cohort heatmap format, OTel trace visualization, terminal run summary, polling-error message text) are captured as first-class FRs in PRD: FR34b, FR55, FR58, FR54, FR56 respectively. `/bmad-create-ux-design` was intentionally skipped per PRD scope.
_bmad-output/planning-artifacts/epics.md:353:| FR55 ASCII + dict | Epic 8b | Cohort heatmap (relocated from dissolved Epic 8 per Winston) |
_bmad-output/planning-artifacts/epics.md:354:| FR55 HTML | Epic 13 [P2] | Cohort heatmap HTML rendering |
_bmad-output/planning-artifacts/epics.md:524:**Goal:** New users bootstrap via `agenteval init` scaffolding (FR52) and add custom adapters via `agenteval new-adapter` (FR18). Terminal run summary (FR54) closes the first-run loop. Cohort heatmap rendering (ASCII + dict) from FR55 lives here (relocated from dissolved Epic 8 per Winston). 8 recipe gallery entries authored here covering all primary user journeys (Recipes 1-8 distributed per source journey). OTel trace visualization doc (FR58) included.
_bmad-output/planning-artifacts/epics.md:526:**FRs covered:** FR18 (`agenteval new-adapter`), FR52 (`agenteval init`), FR53 (cross-ref to FR18), FR54 (terminal run summary), FR55 ASCII + dict (cohort heatmap), FR58 (OTel trace visual doc).
_bmad-output/planning-artifacts/epics.md:584:**Goal:** Phase 2 maturity surface: Mann-Whitney U + Cliff's δ + Bootstrap CI behind `[agenteval-advanced]` extra (FR29a/b/c); OTLP trace export to production observability backends (FR33b OTLP); `Compare Tool Discoverability` cross-adapter with statistical significance (FR10b, requires ≥2 fully-shipped Tier-1 runtimes from Epic 11); HTML cohort heatmap rendering (FR55 HTML).
_bmad-output/planning-artifacts/epics.md:586:**FRs covered:** FR10b (Compare Tool Discoverability cross-adapter), FR29a (Mann Whitney U), FR29b (Cliff Delta), FR29c (Bootstrap CI), FR33b OTLP, FR55 `as_html()`.
_bmad-output/planning-artifacts/epics.md:1894:I want `agenteval new-adapter` to scaffold a new adapter package skeleton + a terminal run summary (FR54) + `CohortHeatmap.as_ascii()` and `.as_dict()` methods for rendering cohort comparison results,
_bmad-output/planning-artifacts/epics.md:2196:I want `CohortHeatmap.as_html()` rendering the same cohort data as a standalone HTML file with embedded CSS,
_bmad-output/planning-artifacts/epics.md:2201:**Given** a `CohortHeatmap` from Story 4.4 (MVP single-runtime), Story 13.3 (cross-adapter Tool Discoverability), or Story 13.5 (cross-adapter Skill Discoverability),
_bmad-output/planning-artifacts/epics.md:2202:**When** I call `${html}=    ${heatmap.as_html()}`,
_bmad-output/planning-artifacts/epics.md:2203:**Then** the variable receives a standalone HTML string with embedded CSS rendering the heatmap as a color-coded table (Pass@k → color gradient); file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file.
src/AgentEval/_heatmap/models.py:15:"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
src/AgentEval/_heatmap/models.py:30:__all__ = ["CohortHeatmap"]
src/AgentEval/_heatmap/models.py:33:# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
src/AgentEval/_heatmap/models.py:83:class CohortHeatmap:
src/AgentEval/_heatmap/models.py:84:    """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
src/AgentEval/_heatmap/models.py:106:    ) -> CohortHeatmap:
src/AgentEval/_heatmap/models.py:114:            ``CohortHeatmap`` instance with one column.
src/AgentEval/_heatmap/models.py:124:    ) -> CohortHeatmap:
src/AgentEval/_heatmap/models.py:137:            ``CohortHeatmap`` with one column per adapter + one row per task.
src/AgentEval/_heatmap/models.py:217:    def as_html(self) -> str:
src/AgentEval/_heatmap/models.py:218:        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
src/AgentEval/_heatmap/models.py:310:    def write_html(self, path: str | Path) -> Path:
src/AgentEval/_heatmap/models.py:311:        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
src/AgentEval/_heatmap/models.py:329:            - Convenience companion to ``as_html`` per Story 13.4 D-2.
src/AgentEval/_heatmap/models.py:336:            raise ValueError("write_html requires a non-empty path; got empty string")
src/AgentEval/_heatmap/models.py:339:        resolved.write_text(self.as_html(), encoding="utf-8")
docs/contracts/stability-surface.md:125:### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
docs/contracts/stability-surface.md:127:Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
docs/contracts/stability-surface.md:129:- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
docs/contracts/stability-surface.md:130:- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
docs/contracts/stability-surface.md:139:- `AgentEval.discoverability.schema.DiscoverabilityComparisonResult` frozen dataclass — `provisional` label. 5 fields: `adapters: tuple[str, ...]`, `per_adapter_results: Mapping[str, DiscoverabilityResult]`, `cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]`, `heatmap: CohortHeatmap`, `summary: DiscoverabilityComparisonSummary`. `__post_init__` cross-consistency validators (`adapters ↔ per_adapter_results.keys()` + `adapters ↔ heatmap.models`) are `stable`.
docs/contracts/stability-surface.md:142:- `CohortHeatmap.from_comparison(result: DiscoverabilityComparisonResult)` classmethod — `provisional` label. Multi-column heatmap with one column per adapter + one row per task. Mirrors `from_discoverability` discipline.
tests/unit/_heatmap/test_models_html.py:15:"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
tests/unit/_heatmap/test_models_html.py:34:    CohortHeatmap,
tests/unit/_heatmap/test_models_html.py:83:# `as_html` happy paths (5 tests)                                             #
tests/unit/_heatmap/test_models_html.py:87:def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
tests/unit/_heatmap/test_models_html.py:89:    h = CohortHeatmap(tasks=(), models=(), cells=())
tests/unit/_heatmap/test_models_html.py:90:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:96:def test_as_html_single_model_3_tasks() -> None:
tests/unit/_heatmap/test_models_html.py:98:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:103:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:116:def test_as_html_3_adapter_3_tasks() -> None:
tests/unit/_heatmap/test_models_html.py:118:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:133:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:140:def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
tests/unit/_heatmap/test_models_html.py:142:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:147:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:152:def test_as_html_pass_rates_formatted_two_decimals() -> None:
tests/unit/_heatmap/test_models_html.py:154:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:159:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:193:def test_as_html_parses_via_stdlib_html_parser() -> None:
tests/unit/_heatmap/test_models_html.py:195:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:201:    parser.feed(h.as_html())
tests/unit/_heatmap/test_models_html.py:213:def test_as_html_has_no_external_resources() -> None:
tests/unit/_heatmap/test_models_html.py:215:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:220:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:232:def test_as_html_no_script_data_under_html_parser() -> None:
tests/unit/_heatmap/test_models_html.py:234:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:240:    parser.feed(h.as_html())
tests/unit/_heatmap/test_models_html.py:251:def test_as_html_escapes_script_tags_in_task_ids() -> None:
tests/unit/_heatmap/test_models_html.py:254:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:259:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:265:def test_as_html_escapes_special_characters_in_model_names() -> None:
tests/unit/_heatmap/test_models_html.py:267:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:272:    html = h.as_html()
tests/unit/_heatmap/test_models_html.py:279:# `write_html` file ops (4 tests)                                             #
tests/unit/_heatmap/test_models_html.py:283:def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
tests/unit/_heatmap/test_models_html.py:284:    """write_html writes the same content as as_html + returns the resolved path."""
tests/unit/_heatmap/test_models_html.py:285:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:291:    result = h.write_html(target)
tests/unit/_heatmap/test_models_html.py:294:    assert result.read_text(encoding="utf-8") == h.as_html()
tests/unit/_heatmap/test_models_html.py:297:def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
tests/unit/_heatmap/test_models_html.py:298:    """write_html creates non-existent parent directories via mkdir(parents=True)."""
tests/unit/_heatmap/test_models_html.py:299:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:306:    result = h.write_html(target)
tests/unit/_heatmap/test_models_html.py:311:def test_write_html_empty_string_path_raises_value_error() -> None:
tests/unit/_heatmap/test_models_html.py:312:    """write_html('') raises ValueError per D-5."""
tests/unit/_heatmap/test_models_html.py:313:    h = CohortHeatmap(tasks=(), models=(), cells=())
tests/unit/_heatmap/test_models_html.py:315:        h.write_html("")
tests/unit/_heatmap/test_models_html.py:318:def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
tests/unit/_heatmap/test_models_html.py:320:    h = CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:327:    r1 = h.write_html(str_path)
tests/unit/_heatmap/test_models_html.py:328:    r2 = h.write_html(path_obj)
tests/unit/_heatmap/test_models_html.py:340:def test_as_html_docstring_carries_anchors() -> None:
tests/unit/_heatmap/test_models_html.py:341:    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
tests/unit/_heatmap/test_models_html.py:342:    doc = CohortHeatmap.as_html.__doc__ or ""
tests/unit/_heatmap/test_models_html.py:343:    assert "as_html" in doc.lower() or "AS_HTML" in doc
tests/unit/_heatmap/test_models_html.py:344:    assert "FR55" in doc
tests/unit/_heatmap/test_models_html.py:354:def _build_2_adapter_baseline() -> CohortHeatmap:
tests/unit/_heatmap/test_models_html.py:356:    return CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:370:def _build_3_adapter_baseline() -> CohortHeatmap:
tests/unit/_heatmap/test_models_html.py:372:    return CohortHeatmap(
tests/unit/_heatmap/test_models_html.py:393:    actual = _build_2_adapter_baseline().as_html()
tests/unit/_heatmap/test_models_html.py:401:    actual = _build_3_adapter_baseline().as_html()

exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/epics.md | sed -n '2188,2212p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  2188	
  2189	**And** integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero).
  2190	
  2191	---
  2192	
  2193	#### Story 13.4: Cohort Heatmap HTML Rendering
  2194	
  2195	As a **post-run reviewer** sharing results outside the terminal,
  2196	I want `CohortHeatmap.as_html()` rendering the same cohort data as a standalone HTML file with embedded CSS,
  2197	So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables.
  2198	
  2199	**Acceptance Criteria:**
  2200	
  2201	**Given** a `CohortHeatmap` from Story 4.4 (MVP single-runtime), Story 13.3 (cross-adapter Tool Discoverability), or Story 13.5 (cross-adapter Skill Discoverability),
  2202	**When** I call `${html}=    ${heatmap.as_html()}`,
  2203	**Then** the variable receives a standalone HTML string with embedded CSS rendering the heatmap as a color-coded table (Pass@k → color gradient); file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file.
  2204	
  2205	**And** unit tests verify HTML validity (parseable by html.parser) + visual regression test against a recorded baseline image.
  2206	
  2207	---
  2208	
  2209	#### Story 13.5: Compare Skill Discoverability Cross-Adapter (FR4c)
  2210	
  2211	As **Devon (Agent Surface Author)** doing cross-runtime skill activation analysis,
  2212	I want `Skill.Compare Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per FR4c,

codex
I’ve confirmed the core spec text: `as_html()` is in FR55 now, `write_html()` was added only as an epic/story companion, and epic L2205 still literally requires a recorded baseline image. Next I’m validating whether the shipped code and tests actually satisfy those contracts or just restate them.
exec
/bin/bash -lc 'uv run pytest tests/unit/_heatmap/test_models_html.py -q' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import tempfile, os, stat
from AgentEval._heatmap.models import CohortHeatmap, _color_for_pass_rate

cases = []
# HTML edge cases
h_empty_asym = CohortHeatmap(tasks=(), models=('m0',), cells=())
cases.append(('empty_asym_html', h_empty_asym.as_html()))
h_inject = CohortHeatmap(tasks=('<script>alert(1)</script>',), models=('A&B<C>D\" javascript:foo',), cells=(('<script>alert(1)</script>','A&B<C>D\" javascript:foo',1.0),))
cases.append(('inject_html', h_inject.as_html()))

print('BOUNDARIES', {x:_color_for_pass_rate(x)[0] for x in (0.0,0.2,0.4,0.6,0.8,1.0)})
print('EMPTY_ASYM_CONTAINS_TABLE', '<table' in cases[0][1])
print('INJECT_HAS_RAW_SCRIPT', '<script>alert(1)</script>' in cases[1][1])
print('INJECT_HAS_ESCAPED_SCRIPT', '&lt;script&gt;alert(1)&lt;/script&gt;' in cases[1][1])
print('INJECT_HTML_SNIPPET')
print(cases[1][1])

# write_html path probes
h = CohortHeatmap(tasks=('t0',), models=('m0',), cells=(('t0','m0',1.0),))
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    target = base / 'a' / '..' / 'b' / 'hm.html'
    out = h.write_html(target)
    print('REL_DOTDOT_RESOLVED_EXISTS', out.exists(), str(out))

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    real = base / 'real'
    real.mkdir()
    link = base / 'link'
    link.symlink_to(real, target_is_directory=True)
    out = h.write_html(link / 'hm.html')
    print('SYMLINK_TARGET', out, out.parent.samefile(real))

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    try:
        h.write_html(base)
    except Exception as e:
        print('DIR_PATH_EXCEPTION', type(e).__name__, str(e))

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    ro = base / 'ro'
    ro.mkdir()
    ro.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        h.write_html(ro / 'x.html')
        print('READONLY_WRITE', 'succeeded')
    except Exception as e:
        print('READONLY_WRITE_EXCEPTION', type(e).__name__, str(e))
    finally:
        ro.chmod(stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 341ms:
BOUNDARIES {0.0: '#ef4444', 0.2: '#f97316', 0.4: '#eab308', 0.6: '#84cc16', 0.8: '#22c55e', 1.0: '#22c55e'}
EMPTY_ASYM_CONTAINS_TABLE False
INJECT_HAS_RAW_SCRIPT False
INJECT_HAS_ESCAPED_SCRIPT True
INJECT_HTML_SNIPPET
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentEval Cohort Heatmap</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
    table { border-collapse: collapse; }
    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
    th { background-color: #0f172a; color: #ffffff; }
  </style>
</head>
<body>
<table>
  <tr><th>Task</th><th>A&amp;B&lt;C&gt;D" javascript:foo</th></tr>
  <tr><td>&lt;script&gt;alert(1)&lt;/script&gt;</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
</table>
</body>
</html>

REL_DOTDOT_RESOLVED_EXISTS True /tmp/tmp2r0n15u8/b/hm.html
SYMLINK_TARGET /tmp/tmpvn6n2f0a/real/hm.html True
DIR_PATH_EXCEPTION IsADirectoryError [Errno 21] Is a directory: '/tmp/tmpfj9qo5lh'
READONLY_WRITE_EXCEPTION PermissionError [Errno 13] Permission denied: '/tmp/tmpm58ca6xi/ro/x.html'

 succeeded in 1014ms:
..............................                                           [100%]
30 passed in 0.29s

codex
Two concrete spec drifts are clear now: the epic still mandates image-based visual regression, and FR55’s canonical row/column orientation still does not match the renderer being extended here. I’m checking whether there are any additional correctness defects beyond those drifts before I write up the findings.
exec
/bin/bash -lc "nl -ba tests/unit/_heatmap/test_models_html.py | sed -n '1,420p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
    16	
    17	Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
    18	SPECIFIC structural counts (table count, tr count, td count, palette
    19	hex presence) — NOT just "html.parser doesn't crash."
    20	
    21	Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
    22	anchor test asserts the required strings appear in the docstring.
    23	"""
    24	
    25	from __future__ import annotations
    26	
    27	from html.parser import HTMLParser
    28	from pathlib import Path
    29	
    30	import pytest
    31	
    32	from AgentEval._heatmap.models import (
    33	    _MISSING_CELL_STYLE,
    34	    CohortHeatmap,
    35	    _color_for_pass_rate,
    36	)
    37	
    38	# --------------------------------------------------------------------------- #
    39	# `_color_for_pass_rate` helper (4 tests)                                     #
    40	# --------------------------------------------------------------------------- #
    41	
    42	
    43	@pytest.mark.parametrize(
    44	    "rate,expected_bg",
    45	    [
    46	        (0.0, "#ef4444"),  # red — bottom stop
    47	        (0.19, "#ef4444"),  # still red
    48	        (0.2, "#f97316"),  # orange boundary
    49	        (0.39, "#f97316"),
    50	        (0.4, "#eab308"),  # yellow
    51	        (0.5, "#eab308"),
    52	        (0.6, "#84cc16"),  # lime
    53	        (0.79, "#84cc16"),
    54	        (0.8, "#22c55e"),  # green
    55	        (1.0, "#22c55e"),  # top stop
    56	    ],
    57	)
    58	def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
    59	    """Each color stop boundary maps to the correct background hex."""
    60	    bg, _txt = _color_for_pass_rate(rate)
    61	    assert bg == expected_bg
    62	
    63	
    64	def test_color_for_pass_rate_none_returns_missing_style() -> None:
    65	    """None input → missing-cell light-gray + slate-900 text."""
    66	    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
    67	
    68	
    69	def test_color_for_pass_rate_exactly_one_returns_green() -> None:
    70	    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
    71	    bg, txt = _color_for_pass_rate(1.0)
    72	    assert bg == "#22c55e"
    73	    assert txt == "#ffffff"
    74	
    75	
    76	def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
    77	    """Defensive: negative rate → bottom stop (red) rather than raising."""
    78	    bg, _txt = _color_for_pass_rate(-0.1)
    79	    assert bg == "#ef4444"
    80	
    81	
    82	# --------------------------------------------------------------------------- #
    83	# `as_html` happy paths (5 tests)                                             #
    84	# --------------------------------------------------------------------------- #
    85	
    86	
    87	def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
    88	    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
    89	    h = CohortHeatmap(tasks=(), models=(), cells=())
    90	    html = h.as_html()
    91	    assert "<!DOCTYPE html>" in html
    92	    assert "(empty heatmap)" in html
    93	    assert "</html>" in html
    94	
    95	
    96	def test_as_html_single_model_3_tasks() -> None:
    97	    """1 column × 3 rows produces correctly-shaped HTML."""
    98	    h = CohortHeatmap(
    99	        tasks=("t0", "t1", "t2"),
   100	        models=("m0",),
   101	        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
   102	    )
   103	    html = h.as_html()
   104	    # Header row: <th>Task</th><th>m0</th>
   105	    assert html.count("<th>") == 2
   106	    # Body rows: 3 <tr>
   107	    assert html.count("<tr>") == 4  # 1 header + 3 body rows
   108	    # Body cells: 6 <td> (3 task names + 3 values)
   109	    assert html.count("<td") == 6
   110	    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
   111	    assert "#22c55e" in html
   112	    assert "#eab308" in html
   113	    assert "#ef4444" in html
   114	
   115	
   116	def test_as_html_3_adapter_3_tasks() -> None:
   117	    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
   118	    h = CohortHeatmap(
   119	        tasks=("t0", "t1", "t2"),
   120	        models=("a", "b", "c"),
   121	        cells=(
   122	            ("t0", "a", 1.0),
   123	            ("t0", "b", 0.5),
   124	            ("t0", "c", 0.0),
   125	            ("t1", "a", 1.0),
   126	            ("t1", "b", 0.5),
   127	            ("t1", "c", 0.0),
   128	            ("t2", "a", 1.0),
   129	            ("t2", "b", 0.5),
   130	            ("t2", "c", 0.0),
   131	        ),
   132	    )
   133	    html = h.as_html()
   134	    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
   135	    assert html.count("<td") == 12
   136	    # 4 header <th>: Task + a + b + c.
   137	    assert html.count("<th>") == 4
   138	
   139	
   140	def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
   141	    """A cell missing from the input → em-dash + light-gray background."""
   142	    h = CohortHeatmap(
   143	        tasks=("t0",),
   144	        models=("m0", "m1"),
   145	        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
   146	    )
   147	    html = h.as_html()
   148	    assert "—" in html
   149	    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
   150	
   151	
   152	def test_as_html_pass_rates_formatted_two_decimals() -> None:
   153	    """Pass@k values rendered as 2-decimal floats."""
   154	    h = CohortHeatmap(
   155	        tasks=("t0",),
   156	        models=("m0",),
   157	        cells=(("t0", "m0", 0.123456),),
   158	    )
   159	    html = h.as_html()
   160	    assert "0.12" in html
   161	    # NOT showing the unrounded version.
   162	    assert "0.123456" not in html
   163	
   164	
   165	# --------------------------------------------------------------------------- #
   166	# HTML validity (3 tests)                                                     #
   167	# --------------------------------------------------------------------------- #
   168	
   169	
   170	class _StructuralHTMLParser(HTMLParser):
   171	    """Count opening tags + collect script data for defense-in-depth tests."""
   172	
   173	    def __init__(self) -> None:
   174	        super().__init__()
   175	        self.tag_open_counts: dict[str, int] = {}
   176	        self.script_data: list[str] = []
   177	        self._in_script = False
   178	
   179	    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
   180	        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
   181	        if tag == "script":
   182	            self._in_script = True
   183	
   184	    def handle_endtag(self, tag: str) -> None:
   185	        if tag == "script":
   186	            self._in_script = False
   187	
   188	    def handle_data(self, data: str) -> None:
   189	        if self._in_script:
   190	            self.script_data.append(data)
   191	
   192	
   193	def test_as_html_parses_via_stdlib_html_parser() -> None:
   194	    """`html.parser.HTMLParser` parses the output without raising."""
   195	    h = CohortHeatmap(
   196	        tasks=("t0", "t1"),
   197	        models=("m0", "m1"),
   198	        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
   199	    )
   200	    parser = _StructuralHTMLParser()
   201	    parser.feed(h.as_html())
   202	    parser.close()
   203	    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
   204	    assert parser.tag_open_counts.get("table", 0) == 1
   205	    # tr = 1 (header) + 2 (body rows) = 3.
   206	    assert parser.tag_open_counts.get("tr", 0) == 3
   207	    # th = 1 (Task header) + 2 (model headers).
   208	    assert parser.tag_open_counts.get("th", 0) == 3
   209	    # td = 2 tasks × (1 task name + 2 models) = 6.
   210	    assert parser.tag_open_counts.get("td", 0) == 6
   211	
   212	
   213	def test_as_html_has_no_external_resources() -> None:
   214	    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
   215	    h = CohortHeatmap(
   216	        tasks=("t0",),
   217	        models=("m0",),
   218	        cells=(("t0", "m0", 1.0),),
   219	    )
   220	    html = h.as_html()
   221	    # NO external stylesheet link.
   222	    assert "<link" not in html
   223	    # NO script element (D-3 explicit prohibition for offline-safety).
   224	    assert "<script" not in html.lower()
   225	    # NO external image / font URLs.
   226	    assert 'src="http' not in html.lower()
   227	    assert 'href="http' not in html.lower()
   228	    # NO external `url(...)` references in styles.
   229	    assert "url(http" not in html.lower()
   230	
   231	
   232	def test_as_html_no_script_data_under_html_parser() -> None:
   233	    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
   234	    h = CohortHeatmap(
   235	        tasks=("t0",),
   236	        models=("m0",),
   237	        cells=(("t0", "m0", 1.0),),
   238	    )
   239	    parser = _StructuralHTMLParser()
   240	    parser.feed(h.as_html())
   241	    parser.close()
   242	    assert parser.script_data == []
   243	    assert parser.tag_open_counts.get("script", 0) == 0
   244	
   245	
   246	# --------------------------------------------------------------------------- #
   247	# HTML escaping (2 tests)                                                     #
   248	# --------------------------------------------------------------------------- #
   249	
   250	
   251	def test_as_html_escapes_script_tags_in_task_ids() -> None:
   252	    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
   253	    malicious = "<script>alert(1)</script>"
   254	    h = CohortHeatmap(
   255	        tasks=(malicious,),
   256	        models=("m0",),
   257	        cells=((malicious, "m0", 1.0),),
   258	    )
   259	    html = h.as_html()
   260	    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
   261	    assert "<script>alert(1)</script>" not in html
   262	    assert "&lt;script&gt;" in html
   263	
   264	
   265	def test_as_html_escapes_special_characters_in_model_names() -> None:
   266	    """Model names with `&`, `<`, `>` get HTML-escaped."""
   267	    h = CohortHeatmap(
   268	        tasks=("t0",),
   269	        models=("A&B<C>D",),
   270	        cells=(("t0", "A&B<C>D", 0.5),),
   271	    )
   272	    html = h.as_html()
   273	    assert "A&amp;B&lt;C&gt;D" in html
   274	    # Original unescaped form must NOT appear.
   275	    assert "A&B<C>D" not in html
   276	
   277	
   278	# --------------------------------------------------------------------------- #
   279	# `write_html` file ops (4 tests)                                             #
   280	# --------------------------------------------------------------------------- #
   281	
   282	
   283	def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
   284	    """write_html writes the same content as as_html + returns the resolved path."""
   285	    h = CohortHeatmap(
   286	        tasks=("t0",),
   287	        models=("m0",),
   288	        cells=(("t0", "m0", 1.0),),
   289	    )
   290	    target = tmp_path / "heatmap.html"
   291	    result = h.write_html(target)
   292	    assert result == target.resolve()
   293	    assert result.exists()
   294	    assert result.read_text(encoding="utf-8") == h.as_html()
   295	
   296	
   297	def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
   298	    """write_html creates non-existent parent directories via mkdir(parents=True)."""
   299	    h = CohortHeatmap(
   300	        tasks=("t0",),
   301	        models=("m0",),
   302	        cells=(("t0", "m0", 0.5),),
   303	    )
   304	    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
   305	    assert not target.parent.exists()
   306	    result = h.write_html(target)
   307	    assert result.exists()
   308	    assert target.parent.is_dir()
   309	
   310	
   311	def test_write_html_empty_string_path_raises_value_error() -> None:
   312	    """write_html('') raises ValueError per D-5."""
   313	    h = CohortHeatmap(tasks=(), models=(), cells=())
   314	    with pytest.raises(ValueError, match="non-empty path"):
   315	        h.write_html("")
   316	
   317	
   318	def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
   319	    """Both `str` and `Path` inputs work + return identical resolved paths."""
   320	    h = CohortHeatmap(
   321	        tasks=("t0",),
   322	        models=("m0",),
   323	        cells=(("t0", "m0", 1.0),),
   324	    )
   325	    str_path = str(tmp_path / "a.html")
   326	    path_obj = tmp_path / "b.html"
   327	    r1 = h.write_html(str_path)
   328	    r2 = h.write_html(path_obj)
   329	    assert r1.exists()
   330	    assert r2.exists()
   331	    assert r1 == Path(str_path).resolve()
   332	    assert r2 == path_obj.resolve()
   333	
   334	
   335	# --------------------------------------------------------------------------- #
   336	# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
   337	# --------------------------------------------------------------------------- #
   338	
   339	
   340	def test_as_html_docstring_carries_anchors() -> None:
   341	    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
   342	    doc = CohortHeatmap.as_html.__doc__ or ""
   343	    assert "as_html" in doc.lower() or "AS_HTML" in doc
   344	    assert "FR55" in doc
   345	    assert "Phase-2" in doc or "Phase 2" in doc
   346	    assert "embedded CSS" in doc or "embedded `<style>" in doc
   347	
   348	
   349	# --------------------------------------------------------------------------- #
   350	# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
   351	# --------------------------------------------------------------------------- #
   352	
   353	
   354	def _build_2_adapter_baseline() -> CohortHeatmap:
   355	    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
   356	    return CohortHeatmap(
   357	        tasks=("task_alpha", "task_beta", "task_gamma"),
   358	        models=("adapter_red", "adapter_green"),
   359	        cells=(
   360	            ("task_alpha", "adapter_red", 1.0),
   361	            ("task_alpha", "adapter_green", 0.0),
   362	            ("task_beta", "adapter_red", 0.5),
   363	            ("task_beta", "adapter_green", 0.5),
   364	            ("task_gamma", "adapter_red", 0.0),
   365	            ("task_gamma", "adapter_green", 1.0),
   366	        ),
   367	    )
   368	
   369	
   370	def _build_3_adapter_baseline() -> CohortHeatmap:
   371	    """Deterministic 3-adapter × 3-task input."""
   372	    return CohortHeatmap(
   373	        tasks=("t0", "t1", "t2"),
   374	        models=("a", "b", "c"),
   375	        cells=(
   376	            ("t0", "a", 1.0),
   377	            ("t0", "b", 0.5),
   378	            ("t0", "c", 0.0),
   379	            ("t1", "a", 0.7),
   380	            ("t1", "b", None),  # missing cell on purpose
   381	            ("t1", "c", 0.3),
   382	            ("t2", "a", 0.0),
   383	            ("t2", "b", 0.0),
   384	            ("t2", "c", 0.0),
   385	        ),
   386	    )
   387	
   388	
   389	def test_html_matches_recorded_baseline_2_adapter() -> None:
   390	    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
   391	    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
   392	    expected = fixture.read_text(encoding="utf-8")
   393	    actual = _build_2_adapter_baseline().as_html()
   394	    assert actual == expected
   395	
   396	
   397	def test_html_matches_recorded_baseline_3_adapter() -> None:
   398	    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
   399	    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
   400	    expected = fixture.read_text(encoding="utf-8")
   401	    actual = _build_3_adapter_baseline().as_html()
   402	    assert actual == expected

exec
/bin/bash -lc "python - <<'PY'
from html.parser import HTMLParser
from AgentEval._heatmap.models import CohortHeatmap

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[]
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

samples = {
    'single_row': CohortHeatmap(tasks=('t0',), models=('m0','m1','m2'), cells=(('t0','m0',0.0),('t0','m1',0.2),('t0','m2',1.0))).as_html(),
    'missing_cell': CohortHeatmap(tasks=('t0','t1'), models=('m0','m1','m2'), cells=(('t0','m0',0.0),('t0','m1',0.2),('t1','m2',1.0))).as_html(),
    'empty_asym': CohortHeatmap(tasks=(), models=('m0',), cells=()).as_html(),
}
for name, html in samples.items():
    p=P(); p.feed(html); p.close()
    print(name, len(p.tags), p.tags[:10])
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 353ms:
single_row 17 [('html', [('lang', 'en')]), ('head', []), ('meta', [('charset', 'utf-8')]), ('title', []), ('style', []), ('body', []), ('table', []), ('tr', []), ('th', []), ('th', [])]
missing_cell 22 [('html', [('lang', 'en')]), ('head', []), ('meta', [('charset', 'utf-8')]), ('title', []), ('style', []), ('body', []), ('table', []), ('tr', []), ('th', []), ('th', [])]
empty_asym 6 [('html', [('lang', 'en')]), ('head', []), ('meta', [('charset', 'utf-8')]), ('title', []), ('body', []), ('p', [])]

exec
/bin/bash -lc "nl -ba _bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md | sed -n '1,260p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
     2	
     3	Status: review
     4	
     5	## Story
     6	
     7	As a **post-run reviewer** sharing results outside the terminal,
     8	I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
     9	So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
    10	
    11	## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
    12	
    13	10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
    14	
    15	- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
    16	
    17	- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
    18	
    19	- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
    20	
    21	- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
    22	  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
    23	  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
    24	  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
    25	  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
    26	  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
    27	  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
    28	  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
    29	
    30	- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
    31	
    32	- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
    33	
    34	- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
    35	
    36	- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
    37	
    38	- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
    39	
    40	- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
    41	  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
    42	  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
    43	  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
    44	  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
    45	
    46	## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
    47	
    48	Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
    49	
    50	- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
    51	- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
    52	- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
    53	- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
    54	- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
    55	
    56	## Acceptance Criteria
    57	
    58	### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
    59	
    60	`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
    61	
    62	```python
    63	def as_html(self) -> str:
    64	    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
    65	
    66	    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
    67	    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
    68	    `<style>`), and `<body>` containing a `<table>` with header row +
    69	    one row per task. Each cell carries inline `style="background-color: <hex>;
    70	    color: <text-hex>;"` for the Pass@k color gradient.
    71	
    72	    All styling embedded in `<head><style>...</style>`. NO external
    73	    stylesheet links, NO external image references, NO `<script>`
    74	    elements — operators can email the file or save to shared storage
    75	    and view offline.
    76	
    77	    Empty heatmap (no tasks OR no models): returns a minimal valid
    78	    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
    79	    `as_ascii()`'s `"(empty heatmap)"` sentinel).
    80	
    81	    Color gradient (Pass@k → background hex; text hex chosen for
    82	    readable contrast per WCAG AA):
    83	        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
    84	        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
    85	        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
    86	        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
    87	        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
    88	        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
    89	
    90	    Returns:
    91	        Standalone HTML5 document as a string.
    92	    """
    93	```
    94	
    95	Implementation outline:
    96	1. Empty case: return minimal document.
    97	2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
    98	3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
    99	4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
   100	5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
   101	
   102	### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
   103	
   104	`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
   105	
   106	```python
   107	_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
   108	    # (lower_bound_inclusive, background_hex, text_hex)
   109	    (0.0, "#ef4444", "#ffffff"),  # red — high failure
   110	    (0.2, "#f97316", "#ffffff"),  # orange
   111	    (0.4, "#eab308", "#0f172a"),  # yellow
   112	    (0.6, "#84cc16", "#0f172a"),  # lime
   113	    (0.8, "#22c55e", "#ffffff"),  # green — high success
   114	)
   115	_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
   116	```
   117	
   118	Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
   119	- `rate is None` → `_MISSING_CELL_STYLE`.
   120	- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
   121	
   122	The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
   123	
   124	### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
   125	
   126	`src/AgentEval/_heatmap/models.py` adds after `as_html`:
   127	
   128	```python
   129	def write_html(self, path: str | Path) -> Path:
   130	    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
   131	
   132	    Args:
   133	        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
   134	            paths resolve against `Path.cwd()`. Empty string raises
   135	            `ValueError`. Parent directories created with
   136	            `parents=True, exist_ok=True`.
   137	
   138	    Returns:
   139	        The resolved write path (post-`Path.resolve()`).
   140	
   141	    Raises:
   142	        ValueError: When `path` is the empty string.
   143	        OSError: When the filesystem write fails (read-only, permission, etc.).
   144	            NOT caught — propagates to the caller.
   145	    """
   146	```
   147	
   148	Implementation:
   149	- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
   150	- `resolved = Path(path).resolve()`.
   151	- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
   152	- `resolved.write_text(self.as_html(), encoding="utf-8")`.
   153	- `return resolved`.
   154	
   155	### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
   156	
   157	NEW file. Coverage:
   158	
   159	- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
   160	- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
   161	- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
   162	- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
   163	- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
   164	- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
   165	
   166	### AC-13.4.5 — Baseline HTML fixtures for structural regression test
   167	
   168	NEW files:
   169	- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
   170	- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
   171	
   172	Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
   173	
   174	### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
   175	
   176	NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
   177	
   178	- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
   179	- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
   180	- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
   181	
   182	### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
   183	
   184	`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
   185	- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
   186	- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
   187	- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
   188	
   189	### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
   190	
   191	`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
   192	
   193	### AC-13.4.9 — All-gates pass
   194	
   195	- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
   196	- `uv run ruff check src/ tests/` clean.
   197	- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
   198	- `uv run mypy src/` clean (≥107 src files).
   199	
   200	### AC-13.4.10 — Sprint-status
   201	
   202	`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
   203	
   204	## Tasks / Subtasks
   205	
   206	- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
   207	- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
   208	- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
   209	- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
   210	- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
   211	- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
   212	- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
   213	- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
   214	
   215	## Dev Notes
   216	
   217	Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
   218	
   219	- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
   220	- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
   221	
   222	**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
   223	
   224	**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
   225	
   226	**Cross-story lesson application:**
   227	- L-1: stability-surface MUST register the new methods (AC-13.4.6).
   228	- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
   229	- L-3: not RF `@keyword`-decorated; no `@tier` classification.
   230	- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
   231	- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
   232	
   233	### Project Structure Notes
   234	
   235	- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
   236	- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
   237	- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
   238	- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
   239	
   240	### References
   241	
   242	- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
   243	- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
   244	- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
   245	- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
   246	- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
   247	- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
   248	- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
   249	
   250	## Dev Agent Record
   251	
   252	### Agent Model Used
   253	
   254	claude-opus-4-7[1m]
   255	
   256	### Debug Log References
   257	
   258	2 mid-dev catches:
   259	1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
   260	2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.

exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
from AgentEval._heatmap.models import CohortHeatmap

# Probe explicit None vs omitted cell semantics
h_none = CohortHeatmap(tasks=('t1',), models=('m0',), cells=(('t1','m0',None),))
h_missing = CohortHeatmap(tasks=('t1',), models=('m0',), cells=())
print('NONE_EQ_MISSING_HTML', h_none.as_html() == h_missing.as_html())
print(h_none.as_html())
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 347ms:
NONE_EQ_MISSING_HTML True
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentEval Cohort Heatmap</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
    table { border-collapse: collapse; }
    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
    th { background-color: #0f172a; color: #ffffff; }
  </style>
</head>
<body>
<table>
  <tr><th>Task</th><th>m0</th></tr>
  <tr><td>t1</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td></tr>
</table>
</body>
</html>


codex
I have the review findings. I’m writing them to `/tmp/story-13-4-review.diff` now, then I’ll return the same findings here in the requested format.
apply patch
patch: completed
/tmp/story-13-4-review.diff
diff --git a//tmp/story-13-4-review.diff b//tmp/story-13-4-review.diff
index f1647d5ee4d95a1e620089fa1ac368a33d5f5da8..44c31a4f06c051cbd67babaabb1a071c6938ed94
--- a//tmp/story-13-4-review.diff
+++ b//tmp/story-13-4-review.diff
@@ -1,1059 +1,25 @@
-diff --git a/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-new file mode 100644
-index 0000000..aa90bd9
---- /dev/null
-+++ b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-@@ -0,0 +1,304 @@
-+# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
-+
-+Status: review
-+
-+## Story
-+
-+As a **post-run reviewer** sharing results outside the terminal,
-+I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
-+So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
-+
-+## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
-+
-+10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
-+
-+- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
-+
-+- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
-+
-+- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
-+
-+- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
-+  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
-+  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
-+  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
-+  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
-+  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
-+  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
-+  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
-+
-+- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
-+
-+- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
-+
-+- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
-+
-+- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
-+
-+- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
-+
-+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
-+  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
-+  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
-+  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
-+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
-+
-+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
-+
-+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
-+- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
-+- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
-+- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
-+- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
-+
-+## Acceptance Criteria
-+
-+### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
-+
-+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
-+
-+```python
-+def as_html(self) -> str:
-+    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
-+    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+    `<style>`), and `<body>` containing a `<table>` with header row +
-+    one row per task. Each cell carries inline `style="background-color: <hex>;
-+    color: <text-hex>;"` for the Pass@k color gradient.
-+
-+    All styling embedded in `<head><style>...</style>`. NO external
-+    stylesheet links, NO external image references, NO `<script>`
-+    elements — operators can email the file or save to shared storage
-+    and view offline.
-+
-+    Empty heatmap (no tasks OR no models): returns a minimal valid
-+    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
-+    `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+    Color gradient (Pass@k → background hex; text hex chosen for
-+    readable contrast per WCAG AA):
-+        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
-+
-+    Returns:
-+        Standalone HTML5 document as a string.
-+    """
-+```
-+
-+Implementation outline:
-+1. Empty case: return minimal document.
-+2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
-+3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
-+4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
-+5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
-+
-+### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
-+
-+`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
-+
-+```python
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+```
-+
-+Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
-+- `rate is None` → `_MISSING_CELL_STYLE`.
-+- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
-+
-+The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
-+
-+### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
-+
-+`src/AgentEval/_heatmap/models.py` adds after `as_html`:
-+
-+```python
-+def write_html(self, path: str | Path) -> Path:
-+    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
-+
-+    Args:
-+        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
-+            paths resolve against `Path.cwd()`. Empty string raises
-+            `ValueError`. Parent directories created with
-+            `parents=True, exist_ok=True`.
-+
-+    Returns:
-+        The resolved write path (post-`Path.resolve()`).
-+
-+    Raises:
-+        ValueError: When `path` is the empty string.
-+        OSError: When the filesystem write fails (read-only, permission, etc.).
-+            NOT caught — propagates to the caller.
-+    """
-+```
-+
-+Implementation:
-+- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
-+- `resolved = Path(path).resolve()`.
-+- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
-+- `resolved.write_text(self.as_html(), encoding="utf-8")`.
-+- `return resolved`.
-+
-+### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
-+
-+NEW file. Coverage:
-+
-+- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
-+- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
-+- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
-+- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
-+- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
-+- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
-+
-+### AC-13.4.5 — Baseline HTML fixtures for structural regression test
-+
-+NEW files:
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
-+
-+Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
-+
-+### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
-+
-+NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
-+- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
-+
-+### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
-+
-+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
-+- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
-+- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
-+- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
-+
-+### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
-+
-+`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
-+
-+### AC-13.4.9 — All-gates pass
-+
-+- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
-+- `uv run ruff check src/ tests/` clean.
-+- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
-+- `uv run mypy src/` clean (≥107 src files).
-+
-+### AC-13.4.10 — Sprint-status
-+
-+`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
-+
-+## Tasks / Subtasks
-+
-+- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
-+- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
-+- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
-+- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
-+- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
-+- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
-+- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
-+- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-+
-+## Dev Notes
-+
-+Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
-+
-+- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
-+- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
-+
-+**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
-+
-+**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
-+
-+**Cross-story lesson application:**
-+- L-1: stability-surface MUST register the new methods (AC-13.4.6).
-+- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
-+- L-3: not RF `@keyword`-decorated; no `@tier` classification.
-+- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
-+- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
-+
-+### Project Structure Notes
-+
-+- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
-+- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
-+- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
-+- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
-+
-+### References
-+
-+- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
-+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
-+- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
-+- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
-+- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
-+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
-+- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
-+
-+## Dev Agent Record
-+
-+### Agent Model Used
-+
-+claude-opus-4-7[1m]
-+
-+### Debug Log References
-+
-+2 mid-dev catches:
-+1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
-+2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.
-+
-+### Completion Notes List
-+
-+Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.
-+
-+- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
-+- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
-+- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
-+- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
-+- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
-+- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
-+- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
-+- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
-+- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
-+- **AC-13.4.10**: sprint-status flipped to `review`.
-+
-+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
-+- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
-+- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
-+- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
-+- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).
-+
-+### In-flight spec amendments
-+
-+1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.
-+
-+2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.
-+
-+### File List
-+
-+**New files:**
-+- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.
-+
-+**Modified files:**
-+- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method.
-+- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
-+- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
-+- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
-+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
-+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
-index 2f6c828..99f4117 100644
---- a/_bmad-output/implementation-artifacts/deferred-work.md
-+++ b/_bmad-output/implementation-artifacts/deferred-work.md
-@@ -390,6 +390,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
- 
- - **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
- 
-+## Deferred from: story-13.4 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
-+
-+- **DF-13.4-S1 (Phase-2.5 image-based visual regression test for `as_html()`)** — Story 13.4 D-7 in-flight amendment 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baselines) instead of the epic L2205-mandated image-based visual regression. Image regression requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) — heavy deps. Phase-2.5 evaluates whether structural baselines + manual inspection suffice OR whether image regression has empirical value warranting the deps. Catalogued as C92. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S2 (Phase-2.5 color-blind-safe palette mode for `as_html()`)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4's default 5-stop red-orange-yellow-lime-green palette is NOT WCAG 2.1 AA color-blind safe (~8% of males have red-green color blindness). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). Catalogued as C93. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
-+
- ---
- 
- *Update this file as new deferred items emerge from future reviews.*
-diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
-index 24798b7..be01029 100644
---- a/_bmad-output/implementation-artifacts/sprint-status.yaml
-+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
-@@ -154,6 +154,6 @@ development_status:
-   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
-   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
-   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
--  13-4-cohort-heatmap-html-rendering: backlog
-+  13-4-cohort-heatmap-html-rendering: review
-   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
-   epic-13-retrospective: optional
-diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
-index 604fb45..a8e6c7d 100644
---- a/_bmad-output/planning-artifacts/prd.md
-+++ b/_bmad-output/planning-artifacts/prd.md
-@@ -1580,7 +1580,7 @@ Each FR states the testable, observable capability the library must provide. For
- - **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
- - **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
- - **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
--- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
-+- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
- - **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
- - **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
- - **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
-diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
-index 051e962..df97c10 100644
---- a/docs/contracts/stability-surface.md
-+++ b/docs/contracts/stability-surface.md
-@@ -122,6 +122,15 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
- - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- 
-+### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
-+
-+Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
-+- `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
-+- `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
-+
- ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
- 
- Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
-diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
-index 05247b2..d4e41d9 100644
---- a/docs/phase-1-5-carry-overs.md
-+++ b/docs/phase-1-5-carry-overs.md
-@@ -116,7 +116,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
- | **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
- | **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
- 
--**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
-+| **C92** | **Phase-2.5: Image-based visual regression test for `as_html()` (`DF-13.4-S1`).** Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baseline fixtures); epic L2205 mandated "visual regression test against a recorded baseline image" using headless browser + pixel-diff. Headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) are heavy deps; Phase-2.5 evaluates whether the structural baseline + manual browser inspection is sufficient OR whether image regression has empirical value. *Surfaced via Story 13.4 spec D-10 + D-7 in-flight amendment 2026-06-01.* | Story 13.4 D-7 in-flight amendment — Phase-2 structural-baseline ceiling | maintainability | M | TBD | Headless browser screenshot capture + image-diff vs recorded baseline; integration into `dogfood-integration.yml` CI matrix. |
-+| **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
-+| **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
-+
-+**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL (Story 13.4 adds 3 M).
- 
- ## Execution policy
- 
-diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
-index 9be3020..bcc13aa 100644
---- a/src/AgentEval/_heatmap/models.py
-+++ b/src/AgentEval/_heatmap/models.py
-@@ -12,12 +12,14 @@
- # See the License for the specific language governing permissions and
- # limitations under the License.
- 
--"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
-+"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
- 
- from __future__ import annotations
- 
-+import html
- from dataclasses import dataclass
--from typing import TYPE_CHECKING
-+from pathlib import Path
-+from typing import TYPE_CHECKING, Final
- 
- if TYPE_CHECKING:
-     from AgentEval.discoverability.schema import (
-@@ -28,6 +30,55 @@ if TYPE_CHECKING:
- __all__ = ["CohortHeatmap"]
- 
- 
-+# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
-+# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
-+# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
-+#   [0.0, 0.2) → red (high failure)
-+#   [0.2, 0.4) → orange
-+#   [0.4, 0.6) → yellow
-+#   [0.6, 0.8) → lime
-+#   [0.8, 1.0] → green (high success)
-+# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
-+# mode (viridis/magma sequential per WCAG 2.1 AA).
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+# Missing cell (cell[(task, model)] not present in `cells`): light gray.
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+
-+
-+def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
-+    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
-+
-+    Args:
-+        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
-+
-+    Returns:
-+        ``(background_hex, text_hex)`` tuple.
-+
-+    Edge cases:
-+        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
-+        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
-+        - ``rate < 0.0`` → first stop (red); not validated upstream so
-+          defensively clamps to the bottom rather than raising.
-+    """
-+    if rate is None:
-+        return _MISSING_CELL_STYLE
-+    # Linear scan: walk the palette + return the HIGHEST entry whose lower
-+    # bound is `<=` the rate. The palette is sorted ascending by lower bound
-+    # so we walk forward and remember the last match.
-+    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
-+    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
-+        if rate >= lower:
-+            bg, txt = candidate_bg, candidate_txt
-+    return (bg, txt)
-+
-+
- @dataclass(frozen=True)
- class CohortHeatmap:
-     """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
-@@ -162,3 +213,128 @@ class CohortHeatmap:
-             body_lines.append("│ " + " │ ".join(cells) + " │")
- 
-         return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
-+
-+    def as_html(self) -> str:
-+        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
-+        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+        `<style>`), and `<body>` containing a `<table>` with header row +
-+        one row per task. Each Pass@k cell carries inline
-+        `style="background-color: <hex>; color: <text-hex>;"` for the
-+        color gradient.
-+
-+        All styling embedded in `<head><style>...</style>`. NO external
-+        stylesheet links, NO external image references, NO `<script>`
-+        elements — operators can email the file or save to shared
-+        storage and view offline.
-+
-+        Empty heatmap (no tasks OR no models): returns a minimal valid
-+        document with `<body><p>(empty heatmap)</p></body>` (symmetric
-+        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+        Pass@k color gradient (5-stop hue palette; text color chosen for
-+        WCAG AA contrast):
-+            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
-+              with text "—" (em-dash, matching `as_ascii()` fallback).
-+
-+        See module-level `_PASS_RATE_PALETTE` constant for the canonical
-+        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
-+        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
-+        alternative palette.
-+
-+        Security: all user-provided strings (task IDs, model names)
-+        pass through ``html.escape`` before insertion to prevent HTML
-+        injection. Float Pass@k values are formatted via
-+        ``f"{value:.2f}"`` (safe — no escape needed).
-+
-+        Returns:
-+            Standalone HTML5 document as a string.
-+        """
-+        if not self.tasks or not self.models:
-+            return (
-+                "<!DOCTYPE html>\n"
-+                '<html lang="en">\n'
-+                "<head>\n"
-+                '  <meta charset="utf-8">\n'
-+                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
-+                "</head>\n"
-+                "<body>\n"
-+                "  <p>(empty heatmap)</p>\n"
-+                "</body>\n"
-+                "</html>\n"
-+            )
-+
-+        data = self.as_dict()
-+        # Build header row.
-+        header_cells = ["<th>Task</th>"]
-+        for model in self.models:
-+            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
-+        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
-+
-+        # Build body rows.
-+        body_rows: list[str] = []
-+        for task in self.tasks:
-+            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
-+            for model in self.models:
-+                value = data.get(task, {}).get(model)
-+                bg, txt_color = _color_for_pass_rate(value)
-+                cell_text = "—" if value is None else f"{value:.2f}"
-+                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
-+            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
-+
-+        return (
-+            "<!DOCTYPE html>\n"
-+            '<html lang="en">\n'
-+            "<head>\n"
-+            '  <meta charset="utf-8">\n'
-+            "  <title>AgentEval Cohort Heatmap</title>\n"
-+            "  <style>\n"
-+            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
-+            "    table { border-collapse: collapse; }\n"
-+            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
-+            "    th { background-color: #0f172a; color: #ffffff; }\n"
-+            "  </style>\n"
-+            "</head>\n"
-+            "<body>\n"
-+            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
-+            "</body>\n"
-+            "</html>\n"
-+        )
-+
-+    def write_html(self, path: str | Path) -> Path:
-+        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
-+
-+        Args:
-+            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
-+                Relative paths resolve against ``Path.cwd()``. Empty
-+                string raises ``ValueError``. Parent directories are
-+                created with ``parents=True, exist_ok=True``.
-+
-+        Returns:
-+            The resolved write path (post-``Path.resolve()``).
-+
-+        Raises:
-+            ValueError: When ``path`` is the empty string.
-+            OSError: When the filesystem write fails (read-only,
-+                permission denied, etc.). NOT caught — propagates to
-+                the caller.
-+
-+        Notes:
-+            - Convenience companion to ``as_html`` per Story 13.4 D-2.
-+            - Writes UTF-8 encoded text.
-+            - Story 13.4 D-5: empty-string path rejected up-front
-+              instead of relying on ``Path("").write_text`` which
-+              would write to the current directory's empty filename.
-+        """
-+        if isinstance(path, str) and path == "":
-+            raise ValueError("write_html requires a non-empty path; got empty string")
-+        resolved = Path(path).resolve()
-+        resolved.parent.mkdir(parents=True, exist_ok=True)
-+        resolved.write_text(self.as_html(), encoding="utf-8")
-+        return resolved
-diff --git a/tests/fixtures/heatmap/baseline_2_adapter.html b/tests/fixtures/heatmap/baseline_2_adapter.html
-new file mode 100644
-index 0000000..ac48555
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_2_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>adapter_red</th><th>adapter_green</th></tr>
-+  <tr><td>task_alpha</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>task_beta</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #eab308; color: #0f172a;">0.50</td></tr>
-+  <tr><td>task_gamma</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/fixtures/heatmap/baseline_3_adapter.html b/tests/fixtures/heatmap/baseline_3_adapter.html
-new file mode 100644
-index 0000000..5987ff9
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_3_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>a</th><th>b</th><th>c</th></tr>
-+  <tr><td>t0</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>t1</td><td style="background-color: #84cc16; color: #0f172a;">0.70</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td><td style="background-color: #f97316; color: #ffffff;">0.30</td></tr>
-+  <tr><td>t2</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/unit/_heatmap/test_models_html.py b/tests/unit/_heatmap/test_models_html.py
-new file mode 100644
-index 0000000..8bfd92e
---- /dev/null
-+++ b/tests/unit/_heatmap/test_models_html.py
-@@ -0,0 +1,402 @@
-+# Copyright 2026 Many Kasiriha
-+#
-+# Licensed under the Apache License, Version 2.0 (the "License");
-+# you may not use this file except in compliance with the License.
-+# You may obtain a copy of the License at
-+#
-+#     http://www.apache.org/licenses/LICENSE-2.0
-+#
-+# Unless required by applicable law or agreed to in writing, software
-+# distributed under the License is distributed on an "AS IS" BASIS,
-+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-+# See the License for the specific language governing permissions and
-+# limitations under the License.
-+
-+"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
-+
-+Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
-+SPECIFIC structural counts (table count, tr count, td count, palette
-+hex presence) — NOT just "html.parser doesn't crash."
-+
-+Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
-+anchor test asserts the required strings appear in the docstring.
-+"""
-+
-+from __future__ import annotations
-+
-+from html.parser import HTMLParser
-+from pathlib import Path
-+
-+import pytest
-+
-+from AgentEval._heatmap.models import (
-+    _MISSING_CELL_STYLE,
-+    CohortHeatmap,
-+    _color_for_pass_rate,
-+)
-+
-+# --------------------------------------------------------------------------- #
-+# `_color_for_pass_rate` helper (4 tests)                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+@pytest.mark.parametrize(
-+    "rate,expected_bg",
-+    [
-+        (0.0, "#ef4444"),  # red — bottom stop
-+        (0.19, "#ef4444"),  # still red
-+        (0.2, "#f97316"),  # orange boundary
-+        (0.39, "#f97316"),
-+        (0.4, "#eab308"),  # yellow
-+        (0.5, "#eab308"),
-+        (0.6, "#84cc16"),  # lime
-+        (0.79, "#84cc16"),
-+        (0.8, "#22c55e"),  # green
-+        (1.0, "#22c55e"),  # top stop
-+    ],
-+)
-+def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
-+    """Each color stop boundary maps to the correct background hex."""
-+    bg, _txt = _color_for_pass_rate(rate)
-+    assert bg == expected_bg
-+
-+
-+def test_color_for_pass_rate_none_returns_missing_style() -> None:
-+    """None input → missing-cell light-gray + slate-900 text."""
-+    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
-+
-+
-+def test_color_for_pass_rate_exactly_one_returns_green() -> None:
-+    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
-+    bg, txt = _color_for_pass_rate(1.0)
-+    assert bg == "#22c55e"
-+    assert txt == "#ffffff"
-+
-+
-+def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
-+    """Defensive: negative rate → bottom stop (red) rather than raising."""
-+    bg, _txt = _color_for_pass_rate(-0.1)
-+    assert bg == "#ef4444"
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `as_html` happy paths (5 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
-+    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    html = h.as_html()
-+    assert "<!DOCTYPE html>" in html
-+    assert "(empty heatmap)" in html
-+    assert "</html>" in html
-+
-+
-+def test_as_html_single_model_3_tasks() -> None:
-+    """1 column × 3 rows produces correctly-shaped HTML."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
-+    )
-+    html = h.as_html()
-+    # Header row: <th>Task</th><th>m0</th>
-+    assert html.count("<th>") == 2
-+    # Body rows: 3 <tr>
-+    assert html.count("<tr>") == 4  # 1 header + 3 body rows
-+    # Body cells: 6 <td> (3 task names + 3 values)
-+    assert html.count("<td") == 6
-+    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
-+    assert "#22c55e" in html
-+    assert "#eab308" in html
-+    assert "#ef4444" in html
-+
-+
-+def test_as_html_3_adapter_3_tasks() -> None:
-+    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 1.0),
-+            ("t1", "b", 0.5),
-+            ("t1", "c", 0.0),
-+            ("t2", "a", 1.0),
-+            ("t2", "b", 0.5),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+    html = h.as_html()
-+    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
-+    assert html.count("<td") == 12
-+    # 4 header <th>: Task + a + b + c.
-+    assert html.count("<th>") == 4
-+
-+
-+def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
-+    """A cell missing from the input → em-dash + light-gray background."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
-+    )
-+    html = h.as_html()
-+    assert "—" in html
-+    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
-+
-+
-+def test_as_html_pass_rates_formatted_two_decimals() -> None:
-+    """Pass@k values rendered as 2-decimal floats."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.123456),),
-+    )
-+    html = h.as_html()
-+    assert "0.12" in html
-+    # NOT showing the unrounded version.
-+    assert "0.123456" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML validity (3 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+class _StructuralHTMLParser(HTMLParser):
-+    """Count opening tags + collect script data for defense-in-depth tests."""
-+
-+    def __init__(self) -> None:
-+        super().__init__()
-+        self.tag_open_counts: dict[str, int] = {}
-+        self.script_data: list[str] = []
-+        self._in_script = False
-+
-+    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
-+        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
-+        if tag == "script":
-+            self._in_script = True
-+
-+    def handle_endtag(self, tag: str) -> None:
-+        if tag == "script":
-+            self._in_script = False
-+
-+    def handle_data(self, data: str) -> None:
-+        if self._in_script:
-+            self.script_data.append(data)
-+
-+
-+def test_as_html_parses_via_stdlib_html_parser() -> None:
-+    """`html.parser.HTMLParser` parses the output without raising."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1"),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
-+    assert parser.tag_open_counts.get("table", 0) == 1
-+    # tr = 1 (header) + 2 (body rows) = 3.
-+    assert parser.tag_open_counts.get("tr", 0) == 3
-+    # th = 1 (Task header) + 2 (model headers).
-+    assert parser.tag_open_counts.get("th", 0) == 3
-+    # td = 2 tasks × (1 task name + 2 models) = 6.
-+    assert parser.tag_open_counts.get("td", 0) == 6
-+
-+
-+def test_as_html_has_no_external_resources() -> None:
-+    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # NO external stylesheet link.
-+    assert "<link" not in html
-+    # NO script element (D-3 explicit prohibition for offline-safety).
-+    assert "<script" not in html.lower()
-+    # NO external image / font URLs.
-+    assert 'src="http' not in html.lower()
-+    assert 'href="http' not in html.lower()
-+    # NO external `url(...)` references in styles.
-+    assert "url(http" not in html.lower()
-+
-+
-+def test_as_html_no_script_data_under_html_parser() -> None:
-+    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    assert parser.script_data == []
-+    assert parser.tag_open_counts.get("script", 0) == 0
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML escaping (2 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_escapes_script_tags_in_task_ids() -> None:
-+    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
-+    malicious = "<script>alert(1)</script>"
-+    h = CohortHeatmap(
-+        tasks=(malicious,),
-+        models=("m0",),
-+        cells=((malicious, "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
-+    assert "<script>alert(1)</script>" not in html
-+    assert "&lt;script&gt;" in html
-+
-+
-+def test_as_html_escapes_special_characters_in_model_names() -> None:
-+    """Model names with `&`, `<`, `>` get HTML-escaped."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("A&B<C>D",),
-+        cells=(("t0", "A&B<C>D", 0.5),),
-+    )
-+    html = h.as_html()
-+    assert "A&amp;B&lt;C&gt;D" in html
-+    # Original unescaped form must NOT appear.
-+    assert "A&B<C>D" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `write_html` file ops (4 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
-+    """write_html writes the same content as as_html + returns the resolved path."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    target = tmp_path / "heatmap.html"
-+    result = h.write_html(target)
-+    assert result == target.resolve()
-+    assert result.exists()
-+    assert result.read_text(encoding="utf-8") == h.as_html()
-+
-+
-+def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
-+    """write_html creates non-existent parent directories via mkdir(parents=True)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.5),),
-+    )
-+    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
-+    assert not target.parent.exists()
-+    result = h.write_html(target)
-+    assert result.exists()
-+    assert target.parent.is_dir()
-+
-+
-+def test_write_html_empty_string_path_raises_value_error() -> None:
-+    """write_html('') raises ValueError per D-5."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    with pytest.raises(ValueError, match="non-empty path"):
-+        h.write_html("")
-+
-+
-+def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
-+    """Both `str` and `Path` inputs work + return identical resolved paths."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    str_path = str(tmp_path / "a.html")
-+    path_obj = tmp_path / "b.html"
-+    r1 = h.write_html(str_path)
-+    r2 = h.write_html(path_obj)
-+    assert r1.exists()
-+    assert r2.exists()
-+    assert r1 == Path(str_path).resolve()
-+    assert r2 == path_obj.resolve()
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_docstring_carries_anchors() -> None:
-+    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
-+    doc = CohortHeatmap.as_html.__doc__ or ""
-+    assert "as_html" in doc.lower() or "AS_HTML" in doc
-+    assert "FR55" in doc
-+    assert "Phase-2" in doc or "Phase 2" in doc
-+    assert "embedded CSS" in doc or "embedded `<style>" in doc
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def _build_2_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
-+    return CohortHeatmap(
-+        tasks=("task_alpha", "task_beta", "task_gamma"),
-+        models=("adapter_red", "adapter_green"),
-+        cells=(
-+            ("task_alpha", "adapter_red", 1.0),
-+            ("task_alpha", "adapter_green", 0.0),
-+            ("task_beta", "adapter_red", 0.5),
-+            ("task_beta", "adapter_green", 0.5),
-+            ("task_gamma", "adapter_red", 0.0),
-+            ("task_gamma", "adapter_green", 1.0),
-+        ),
-+    )
-+
-+
-+def _build_3_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 3-adapter × 3-task input."""
-+    return CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 0.7),
-+            ("t1", "b", None),  # missing cell on purpose
-+            ("t1", "c", 0.3),
-+            ("t2", "a", 0.0),
-+            ("t2", "b", 0.0),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+
-+
-+def test_html_matches_recorded_baseline_2_adapter() -> None:
-+    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_2_adapter_baseline().as_html()
-+    assert actual == expected
-+
-+
-+def test_html_matches_recorded_baseline_3_adapter() -> None:
-+    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_3_adapter_baseline().as_html()
-+    assert actual == expected
+### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`
+**Issue:** Epic 13.4 still requires a “visual regression test against a recorded baseline image”, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not an implementation choice the story can unilaterally make, because neither `epics.md` nor any ratified contract was amended to remove the image-baseline requirement.
+**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures are `.html` files under `tests/fixtures/heatmap/`, not images.
+**Fix:** Either implement the image-based regression now, or ratify an amendment to `epics.md`/the governing spec before closing Story 13.4.
+
+### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
+**File:** `src/AgentEval/_heatmap/models.py:275`
+**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the new HTML acceptance criteria and baseline fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.
+**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the existing renderer docs say `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus model headers and `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `13-4-cohort-heatmap-html-rendering.md:98-99`.
+**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns` before shipping more surface area on the opposite orientation.
+
+### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
+**File:** `tests/unit/_heatmap/test_models_html.py:370`
+**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract beyond the dataclass/type surface: `cells` is declared as `tuple[tuple[str, str, float], ...]` and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on `None` values being accepted and treated as missing.
+**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as floats only; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` explicitly accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. A runtime probe showed that explicit `None` and omitting the tuple generate identical HTML.
+**Fix:** Keep the original contract and represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None` and document that explicit `None` is supported input.
+
+### LOW-1: The story artifact’s stated `<td>` structural count is internally inconsistent with the shipped renderer
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`
+**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s L-4/AC prose is already stale and misleading.
+**Evidence:** The story says `<td>` count == `N*M` at `13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.
+**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if the intended invariant is `N*M` data cells only.
+
+**Total: 2 HIGH + 1 MED + 1 LOW**

diff --git a//tmp/story-13-4-review.diff b//tmp/story-13-4-review.diff
index f1647d5ee4d95a1e620089fa1ac368a33d5f5da8..44c31a4f06c051cbd67babaabb1a071c6938ed94
--- a//tmp/story-13-4-review.diff
+++ b//tmp/story-13-4-review.diff
@@ -1,1059 +1,25 @@
-diff --git a/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-new file mode 100644
-index 0000000..aa90bd9
---- /dev/null
-+++ b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-@@ -0,0 +1,304 @@
-+# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
-+
-+Status: review
-+
-+## Story
-+
-+As a **post-run reviewer** sharing results outside the terminal,
-+I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
-+So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
-+
-+## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
-+
-+10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
-+
-+- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
-+
-+- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
-+
-+- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
-+
-+- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
-+  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
-+  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
-+  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
-+  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
-+  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
-+  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
-+  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
-+
-+- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
-+
-+- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
-+
-+- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
-+
-+- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
-+
-+- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
-+
-+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
-+  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
-+  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
-+  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
-+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
-+
-+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
-+
-+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
-+- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
-+- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
-+- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
-+- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
-+
-+## Acceptance Criteria
-+
-+### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
-+
-+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
-+
-+```python
-+def as_html(self) -> str:
-+    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
-+    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+    `<style>`), and `<body>` containing a `<table>` with header row +
-+    one row per task. Each cell carries inline `style="background-color: <hex>;
-+    color: <text-hex>;"` for the Pass@k color gradient.
-+
-+    All styling embedded in `<head><style>...</style>`. NO external
-+    stylesheet links, NO external image references, NO `<script>`
-+    elements — operators can email the file or save to shared storage
-+    and view offline.
-+
-+    Empty heatmap (no tasks OR no models): returns a minimal valid
-+    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
-+    `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+    Color gradient (Pass@k → background hex; text hex chosen for
-+    readable contrast per WCAG AA):
-+        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
-+
-+    Returns:
-+        Standalone HTML5 document as a string.
-+    """
-+```
-+
-+Implementation outline:
-+1. Empty case: return minimal document.
-+2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
-+3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
-+4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
-+5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
-+
-+### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
-+
-+`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
-+
-+```python
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+```
-+
-+Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
-+- `rate is None` → `_MISSING_CELL_STYLE`.
-+- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
-+
-+The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
-+
-+### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
-+
-+`src/AgentEval/_heatmap/models.py` adds after `as_html`:
-+
-+```python
-+def write_html(self, path: str | Path) -> Path:
-+    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
-+
-+    Args:
-+        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
-+            paths resolve against `Path.cwd()`. Empty string raises
-+            `ValueError`. Parent directories created with
-+            `parents=True, exist_ok=True`.
-+
-+    Returns:
-+        The resolved write path (post-`Path.resolve()`).
-+
-+    Raises:
-+        ValueError: When `path` is the empty string.
-+        OSError: When the filesystem write fails (read-only, permission, etc.).
-+            NOT caught — propagates to the caller.
-+    """
-+```
-+
-+Implementation:
-+- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
-+- `resolved = Path(path).resolve()`.
-+- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
-+- `resolved.write_text(self.as_html(), encoding="utf-8")`.
-+- `return resolved`.
-+
-+### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
-+
-+NEW file. Coverage:
-+
-+- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
-+- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
-+- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
-+- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
-+- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
-+- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
-+
-+### AC-13.4.5 — Baseline HTML fixtures for structural regression test
-+
-+NEW files:
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
-+
-+Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
-+
-+### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
-+
-+NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
-+- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
-+
-+### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
-+
-+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
-+- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
-+- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
-+- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
-+
-+### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
-+
-+`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
-+
-+### AC-13.4.9 — All-gates pass
-+
-+- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
-+- `uv run ruff check src/ tests/` clean.
-+- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
-+- `uv run mypy src/` clean (≥107 src files).
-+
-+### AC-13.4.10 — Sprint-status
-+
-+`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
-+
-+## Tasks / Subtasks
-+
-+- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
-+- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
-+- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
-+- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
-+- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
-+- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
-+- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
-+- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-+
-+## Dev Notes
-+
-+Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
-+
-+- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
-+- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
-+
-+**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
-+
-+**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
-+
-+**Cross-story lesson application:**
-+- L-1: stability-surface MUST register the new methods (AC-13.4.6).
-+- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
-+- L-3: not RF `@keyword`-decorated; no `@tier` classification.
-+- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
-+- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
-+
-+### Project Structure Notes
-+
-+- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
-+- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
-+- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
-+- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
-+
-+### References
-+
-+- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
-+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
-+- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
-+- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
-+- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
-+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
-+- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
-+
-+## Dev Agent Record
-+
-+### Agent Model Used
-+
-+claude-opus-4-7[1m]
-+
-+### Debug Log References
-+
-+2 mid-dev catches:
-+1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
-+2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.
-+
-+### Completion Notes List
-+
-+Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.
-+
-+- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
-+- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
-+- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
-+- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
-+- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
-+- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
-+- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
-+- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
-+- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
-+- **AC-13.4.10**: sprint-status flipped to `review`.
-+
-+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
-+- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
-+- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
-+- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
-+- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).
-+
-+### In-flight spec amendments
-+
-+1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.
-+
-+2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.
-+
-+### File List
-+
-+**New files:**
-+- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.
-+
-+**Modified files:**
-+- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method.
-+- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
-+- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
-+- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
-+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
-+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
-index 2f6c828..99f4117 100644
---- a/_bmad-output/implementation-artifacts/deferred-work.md
-+++ b/_bmad-output/implementation-artifacts/deferred-work.md
-@@ -390,6 +390,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
- 
- - **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
- 
-+## Deferred from: story-13.4 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
-+
-+- **DF-13.4-S1 (Phase-2.5 image-based visual regression test for `as_html()`)** — Story 13.4 D-7 in-flight amendment 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baselines) instead of the epic L2205-mandated image-based visual regression. Image regression requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) — heavy deps. Phase-2.5 evaluates whether structural baselines + manual inspection suffice OR whether image regression has empirical value warranting the deps. Catalogued as C92. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S2 (Phase-2.5 color-blind-safe palette mode for `as_html()`)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4's default 5-stop red-orange-yellow-lime-green palette is NOT WCAG 2.1 AA color-blind safe (~8% of males have red-green color blindness). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). Catalogued as C93. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
-+
- ---
- 
- *Update this file as new deferred items emerge from future reviews.*
-diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
-index 24798b7..be01029 100644
---- a/_bmad-output/implementation-artifacts/sprint-status.yaml
-+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
-@@ -154,6 +154,6 @@ development_status:
-   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
-   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
-   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
--  13-4-cohort-heatmap-html-rendering: backlog
-+  13-4-cohort-heatmap-html-rendering: review
-   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
-   epic-13-retrospective: optional
-diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
-index 604fb45..a8e6c7d 100644
---- a/_bmad-output/planning-artifacts/prd.md
-+++ b/_bmad-output/planning-artifacts/prd.md
-@@ -1580,7 +1580,7 @@ Each FR states the testable, observable capability the library must provide. For
- - **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
- - **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
- - **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
--- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
-+- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
- - **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
- - **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
- - **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
-diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
-index 051e962..df97c10 100644
---- a/docs/contracts/stability-surface.md
-+++ b/docs/contracts/stability-surface.md
-@@ -122,6 +122,15 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
- - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- 
-+### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
-+
-+Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
-+- `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
-+- `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
-+
- ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
- 
- Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
-diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
-index 05247b2..d4e41d9 100644
---- a/docs/phase-1-5-carry-overs.md
-+++ b/docs/phase-1-5-carry-overs.md
-@@ -116,7 +116,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
- | **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
- | **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
- 
--**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
-+| **C92** | **Phase-2.5: Image-based visual regression test for `as_html()` (`DF-13.4-S1`).** Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baseline fixtures); epic L2205 mandated "visual regression test against a recorded baseline image" using headless browser + pixel-diff. Headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) are heavy deps; Phase-2.5 evaluates whether the structural baseline + manual browser inspection is sufficient OR whether image regression has empirical value. *Surfaced via Story 13.4 spec D-10 + D-7 in-flight amendment 2026-06-01.* | Story 13.4 D-7 in-flight amendment — Phase-2 structural-baseline ceiling | maintainability | M | TBD | Headless browser screenshot capture + image-diff vs recorded baseline; integration into `dogfood-integration.yml` CI matrix. |
-+| **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
-+| **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
-+
-+**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL (Story 13.4 adds 3 M).
- 
- ## Execution policy
- 
-diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
-index 9be3020..bcc13aa 100644
---- a/src/AgentEval/_heatmap/models.py
-+++ b/src/AgentEval/_heatmap/models.py
-@@ -12,12 +12,14 @@
- # See the License for the specific language governing permissions and
- # limitations under the License.
- 
--"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
-+"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
- 
- from __future__ import annotations
- 
-+import html
- from dataclasses import dataclass
--from typing import TYPE_CHECKING
-+from pathlib import Path
-+from typing import TYPE_CHECKING, Final
- 
- if TYPE_CHECKING:
-     from AgentEval.discoverability.schema import (
-@@ -28,6 +30,55 @@ if TYPE_CHECKING:
- __all__ = ["CohortHeatmap"]
- 
- 
-+# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
-+# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
-+# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
-+#   [0.0, 0.2) → red (high failure)
-+#   [0.2, 0.4) → orange
-+#   [0.4, 0.6) → yellow
-+#   [0.6, 0.8) → lime
-+#   [0.8, 1.0] → green (high success)
-+# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
-+# mode (viridis/magma sequential per WCAG 2.1 AA).
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+# Missing cell (cell[(task, model)] not present in `cells`): light gray.
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+
-+
-+def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
-+    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
-+
-+    Args:
-+        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
-+
-+    Returns:
-+        ``(background_hex, text_hex)`` tuple.
-+
-+    Edge cases:
-+        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
-+        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
-+        - ``rate < 0.0`` → first stop (red); not validated upstream so
-+          defensively clamps to the bottom rather than raising.
-+    """
-+    if rate is None:
-+        return _MISSING_CELL_STYLE
-+    # Linear scan: walk the palette + return the HIGHEST entry whose lower
-+    # bound is `<=` the rate. The palette is sorted ascending by lower bound
-+    # so we walk forward and remember the last match.
-+    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
-+    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
-+        if rate >= lower:
-+            bg, txt = candidate_bg, candidate_txt
-+    return (bg, txt)
-+
-+
- @dataclass(frozen=True)
- class CohortHeatmap:
-     """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
-@@ -162,3 +213,128 @@ class CohortHeatmap:
-             body_lines.append("│ " + " │ ".join(cells) + " │")
- 
-         return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
-+
-+    def as_html(self) -> str:
-+        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
-+        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+        `<style>`), and `<body>` containing a `<table>` with header row +
-+        one row per task. Each Pass@k cell carries inline
-+        `style="background-color: <hex>; color: <text-hex>;"` for the
-+        color gradient.
-+
-+        All styling embedded in `<head><style>...</style>`. NO external
-+        stylesheet links, NO external image references, NO `<script>`
-+        elements — operators can email the file or save to shared
-+        storage and view offline.
-+
-+        Empty heatmap (no tasks OR no models): returns a minimal valid
-+        document with `<body><p>(empty heatmap)</p></body>` (symmetric
-+        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+        Pass@k color gradient (5-stop hue palette; text color chosen for
-+        WCAG AA contrast):
-+            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
-+              with text "—" (em-dash, matching `as_ascii()` fallback).
-+
-+        See module-level `_PASS_RATE_PALETTE` constant for the canonical
-+        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
-+        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
-+        alternative palette.
-+
-+        Security: all user-provided strings (task IDs, model names)
-+        pass through ``html.escape`` before insertion to prevent HTML
-+        injection. Float Pass@k values are formatted via
-+        ``f"{value:.2f}"`` (safe — no escape needed).
-+
-+        Returns:
-+            Standalone HTML5 document as a string.
-+        """
-+        if not self.tasks or not self.models:
-+            return (
-+                "<!DOCTYPE html>\n"
-+                '<html lang="en">\n'
-+                "<head>\n"
-+                '  <meta charset="utf-8">\n'
-+                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
-+                "</head>\n"
-+                "<body>\n"
-+                "  <p>(empty heatmap)</p>\n"
-+                "</body>\n"
-+                "</html>\n"
-+            )
-+
-+        data = self.as_dict()
-+        # Build header row.
-+        header_cells = ["<th>Task</th>"]
-+        for model in self.models:
-+            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
-+        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
-+
-+        # Build body rows.
-+        body_rows: list[str] = []
-+        for task in self.tasks:
-+            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
-+            for model in self.models:
-+                value = data.get(task, {}).get(model)
-+                bg, txt_color = _color_for_pass_rate(value)
-+                cell_text = "—" if value is None else f"{value:.2f}"
-+                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
-+            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
-+
-+        return (
-+            "<!DOCTYPE html>\n"
-+            '<html lang="en">\n'
-+            "<head>\n"
-+            '  <meta charset="utf-8">\n'
-+            "  <title>AgentEval Cohort Heatmap</title>\n"
-+            "  <style>\n"
-+            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
-+            "    table { border-collapse: collapse; }\n"
-+            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
-+            "    th { background-color: #0f172a; color: #ffffff; }\n"
-+            "  </style>\n"
-+            "</head>\n"
-+            "<body>\n"
-+            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
-+            "</body>\n"
-+            "</html>\n"
-+        )
-+
-+    def write_html(self, path: str | Path) -> Path:
-+        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
-+
-+        Args:
-+            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
-+                Relative paths resolve against ``Path.cwd()``. Empty
-+                string raises ``ValueError``. Parent directories are
-+                created with ``parents=True, exist_ok=True``.
-+
-+        Returns:
-+            The resolved write path (post-``Path.resolve()``).
-+
-+        Raises:
-+            ValueError: When ``path`` is the empty string.
-+            OSError: When the filesystem write fails (read-only,
-+                permission denied, etc.). NOT caught — propagates to
-+                the caller.
-+
-+        Notes:
-+            - Convenience companion to ``as_html`` per Story 13.4 D-2.
-+            - Writes UTF-8 encoded text.
-+            - Story 13.4 D-5: empty-string path rejected up-front
-+              instead of relying on ``Path("").write_text`` which
-+              would write to the current directory's empty filename.
-+        """
-+        if isinstance(path, str) and path == "":
-+            raise ValueError("write_html requires a non-empty path; got empty string")
-+        resolved = Path(path).resolve()
-+        resolved.parent.mkdir(parents=True, exist_ok=True)
-+        resolved.write_text(self.as_html(), encoding="utf-8")
-+        return resolved
-diff --git a/tests/fixtures/heatmap/baseline_2_adapter.html b/tests/fixtures/heatmap/baseline_2_adapter.html
-new file mode 100644
-index 0000000..ac48555
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_2_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>adapter_red</th><th>adapter_green</th></tr>
-+  <tr><td>task_alpha</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>task_beta</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #eab308; color: #0f172a;">0.50</td></tr>
-+  <tr><td>task_gamma</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/fixtures/heatmap/baseline_3_adapter.html b/tests/fixtures/heatmap/baseline_3_adapter.html
-new file mode 100644
-index 0000000..5987ff9
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_3_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>a</th><th>b</th><th>c</th></tr>
-+  <tr><td>t0</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>t1</td><td style="background-color: #84cc16; color: #0f172a;">0.70</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td><td style="background-color: #f97316; color: #ffffff;">0.30</td></tr>
-+  <tr><td>t2</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/unit/_heatmap/test_models_html.py b/tests/unit/_heatmap/test_models_html.py
-new file mode 100644
-index 0000000..8bfd92e
---- /dev/null
-+++ b/tests/unit/_heatmap/test_models_html.py
-@@ -0,0 +1,402 @@
-+# Copyright 2026 Many Kasiriha
-+#
-+# Licensed under the Apache License, Version 2.0 (the "License");
-+# you may not use this file except in compliance with the License.
-+# You may obtain a copy of the License at
-+#
-+#     http://www.apache.org/licenses/LICENSE-2.0
-+#
-+# Unless required by applicable law or agreed to in writing, software
-+# distributed under the License is distributed on an "AS IS" BASIS,
-+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-+# See the License for the specific language governing permissions and
-+# limitations under the License.
-+
-+"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
-+
-+Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
-+SPECIFIC structural counts (table count, tr count, td count, palette
-+hex presence) — NOT just "html.parser doesn't crash."
-+
-+Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
-+anchor test asserts the required strings appear in the docstring.
-+"""
-+
-+from __future__ import annotations
-+
-+from html.parser import HTMLParser
-+from pathlib import Path
-+
-+import pytest
-+
-+from AgentEval._heatmap.models import (
-+    _MISSING_CELL_STYLE,
-+    CohortHeatmap,
-+    _color_for_pass_rate,
-+)
-+
-+# --------------------------------------------------------------------------- #
-+# `_color_for_pass_rate` helper (4 tests)                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+@pytest.mark.parametrize(
-+    "rate,expected_bg",
-+    [
-+        (0.0, "#ef4444"),  # red — bottom stop
-+        (0.19, "#ef4444"),  # still red
-+        (0.2, "#f97316"),  # orange boundary
-+        (0.39, "#f97316"),
-+        (0.4, "#eab308"),  # yellow
-+        (0.5, "#eab308"),
-+        (0.6, "#84cc16"),  # lime
-+        (0.79, "#84cc16"),
-+        (0.8, "#22c55e"),  # green
-+        (1.0, "#22c55e"),  # top stop
-+    ],
-+)
-+def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
-+    """Each color stop boundary maps to the correct background hex."""
-+    bg, _txt = _color_for_pass_rate(rate)
-+    assert bg == expected_bg
-+
-+
-+def test_color_for_pass_rate_none_returns_missing_style() -> None:
-+    """None input → missing-cell light-gray + slate-900 text."""
-+    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
-+
-+
-+def test_color_for_pass_rate_exactly_one_returns_green() -> None:
-+    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
-+    bg, txt = _color_for_pass_rate(1.0)
-+    assert bg == "#22c55e"
-+    assert txt == "#ffffff"
-+
-+
-+def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
-+    """Defensive: negative rate → bottom stop (red) rather than raising."""
-+    bg, _txt = _color_for_pass_rate(-0.1)
-+    assert bg == "#ef4444"
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `as_html` happy paths (5 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
-+    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    html = h.as_html()
-+    assert "<!DOCTYPE html>" in html
-+    assert "(empty heatmap)" in html
-+    assert "</html>" in html
-+
-+
-+def test_as_html_single_model_3_tasks() -> None:
-+    """1 column × 3 rows produces correctly-shaped HTML."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
-+    )
-+    html = h.as_html()
-+    # Header row: <th>Task</th><th>m0</th>
-+    assert html.count("<th>") == 2
-+    # Body rows: 3 <tr>
-+    assert html.count("<tr>") == 4  # 1 header + 3 body rows
-+    # Body cells: 6 <td> (3 task names + 3 values)
-+    assert html.count("<td") == 6
-+    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
-+    assert "#22c55e" in html
-+    assert "#eab308" in html
-+    assert "#ef4444" in html
-+
-+
-+def test_as_html_3_adapter_3_tasks() -> None:
-+    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 1.0),
-+            ("t1", "b", 0.5),
-+            ("t1", "c", 0.0),
-+            ("t2", "a", 1.0),
-+            ("t2", "b", 0.5),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+    html = h.as_html()
-+    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
-+    assert html.count("<td") == 12
-+    # 4 header <th>: Task + a + b + c.
-+    assert html.count("<th>") == 4
-+
-+
-+def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
-+    """A cell missing from the input → em-dash + light-gray background."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
-+    )
-+    html = h.as_html()
-+    assert "—" in html
-+    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
-+
-+
-+def test_as_html_pass_rates_formatted_two_decimals() -> None:
-+    """Pass@k values rendered as 2-decimal floats."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.123456),),
-+    )
-+    html = h.as_html()
-+    assert "0.12" in html
-+    # NOT showing the unrounded version.
-+    assert "0.123456" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML validity (3 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+class _StructuralHTMLParser(HTMLParser):
-+    """Count opening tags + collect script data for defense-in-depth tests."""
-+
-+    def __init__(self) -> None:
-+        super().__init__()
-+        self.tag_open_counts: dict[str, int] = {}
-+        self.script_data: list[str] = []
-+        self._in_script = False
-+
-+    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
-+        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
-+        if tag == "script":
-+            self._in_script = True
-+
-+    def handle_endtag(self, tag: str) -> None:
-+        if tag == "script":
-+            self._in_script = False
-+
-+    def handle_data(self, data: str) -> None:
-+        if self._in_script:
-+            self.script_data.append(data)
-+
-+
-+def test_as_html_parses_via_stdlib_html_parser() -> None:
-+    """`html.parser.HTMLParser` parses the output without raising."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1"),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
-+    assert parser.tag_open_counts.get("table", 0) == 1
-+    # tr = 1 (header) + 2 (body rows) = 3.
-+    assert parser.tag_open_counts.get("tr", 0) == 3
-+    # th = 1 (Task header) + 2 (model headers).
-+    assert parser.tag_open_counts.get("th", 0) == 3
-+    # td = 2 tasks × (1 task name + 2 models) = 6.
-+    assert parser.tag_open_counts.get("td", 0) == 6
-+
-+
-+def test_as_html_has_no_external_resources() -> None:
-+    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # NO external stylesheet link.
-+    assert "<link" not in html
-+    # NO script element (D-3 explicit prohibition for offline-safety).
-+    assert "<script" not in html.lower()
-+    # NO external image / font URLs.
-+    assert 'src="http' not in html.lower()
-+    assert 'href="http' not in html.lower()
-+    # NO external `url(...)` references in styles.
-+    assert "url(http" not in html.lower()
-+
-+
-+def test_as_html_no_script_data_under_html_parser() -> None:
-+    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    assert parser.script_data == []
-+    assert parser.tag_open_counts.get("script", 0) == 0
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML escaping (2 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_escapes_script_tags_in_task_ids() -> None:
-+    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
-+    malicious = "<script>alert(1)</script>"
-+    h = CohortHeatmap(
-+        tasks=(malicious,),
-+        models=("m0",),
-+        cells=((malicious, "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
-+    assert "<script>alert(1)</script>" not in html
-+    assert "&lt;script&gt;" in html
-+
-+
-+def test_as_html_escapes_special_characters_in_model_names() -> None:
-+    """Model names with `&`, `<`, `>` get HTML-escaped."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("A&B<C>D",),
-+        cells=(("t0", "A&B<C>D", 0.5),),
-+    )
-+    html = h.as_html()
-+    assert "A&amp;B&lt;C&gt;D" in html
-+    # Original unescaped form must NOT appear.
-+    assert "A&B<C>D" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `write_html` file ops (4 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
-+    """write_html writes the same content as as_html + returns the resolved path."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    target = tmp_path / "heatmap.html"
-+    result = h.write_html(target)
-+    assert result == target.resolve()
-+    assert result.exists()
-+    assert result.read_text(encoding="utf-8") == h.as_html()
-+
-+
-+def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
-+    """write_html creates non-existent parent directories via mkdir(parents=True)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.5),),
-+    )
-+    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
-+    assert not target.parent.exists()
-+    result = h.write_html(target)
-+    assert result.exists()
-+    assert target.parent.is_dir()
-+
-+
-+def test_write_html_empty_string_path_raises_value_error() -> None:
-+    """write_html('') raises ValueError per D-5."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    with pytest.raises(ValueError, match="non-empty path"):
-+        h.write_html("")
-+
-+
-+def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
-+    """Both `str` and `Path` inputs work + return identical resolved paths."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    str_path = str(tmp_path / "a.html")
-+    path_obj = tmp_path / "b.html"
-+    r1 = h.write_html(str_path)
-+    r2 = h.write_html(path_obj)
-+    assert r1.exists()
-+    assert r2.exists()
-+    assert r1 == Path(str_path).resolve()
-+    assert r2 == path_obj.resolve()
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_docstring_carries_anchors() -> None:
-+    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
-+    doc = CohortHeatmap.as_html.__doc__ or ""
-+    assert "as_html" in doc.lower() or "AS_HTML" in doc
-+    assert "FR55" in doc
-+    assert "Phase-2" in doc or "Phase 2" in doc
-+    assert "embedded CSS" in doc or "embedded `<style>" in doc
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def _build_2_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
-+    return CohortHeatmap(
-+        tasks=("task_alpha", "task_beta", "task_gamma"),
-+        models=("adapter_red", "adapter_green"),
-+        cells=(
-+            ("task_alpha", "adapter_red", 1.0),
-+            ("task_alpha", "adapter_green", 0.0),
-+            ("task_beta", "adapter_red", 0.5),
-+            ("task_beta", "adapter_green", 0.5),
-+            ("task_gamma", "adapter_red", 0.0),
-+            ("task_gamma", "adapter_green", 1.0),
-+        ),
-+    )
-+
-+
-+def _build_3_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 3-adapter × 3-task input."""
-+    return CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 0.7),
-+            ("t1", "b", None),  # missing cell on purpose
-+            ("t1", "c", 0.3),
-+            ("t2", "a", 0.0),
-+            ("t2", "b", 0.0),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+
-+
-+def test_html_matches_recorded_baseline_2_adapter() -> None:
-+    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_2_adapter_baseline().as_html()
-+    assert actual == expected
-+
-+
-+def test_html_matches_recorded_baseline_3_adapter() -> None:
-+    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_3_adapter_baseline().as_html()
-+    assert actual == expected
+### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`
+**Issue:** Epic 13.4 still requires a “visual regression test against a recorded baseline image”, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not an implementation choice the story can unilaterally make, because neither `epics.md` nor any ratified contract was amended to remove the image-baseline requirement.
+**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures are `.html` files under `tests/fixtures/heatmap/`, not images.
+**Fix:** Either implement the image-based regression now, or ratify an amendment to `epics.md`/the governing spec before closing Story 13.4.
+
+### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
+**File:** `src/AgentEval/_heatmap/models.py:275`
+**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the new HTML acceptance criteria and baseline fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.
+**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the existing renderer docs say `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus model headers and `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `13-4-cohort-heatmap-html-rendering.md:98-99`.
+**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns` before shipping more surface area on the opposite orientation.
+
+### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
+**File:** `tests/unit/_heatmap/test_models_html.py:370`
+**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract beyond the dataclass/type surface: `cells` is declared as `tuple[tuple[str, str, float], ...]` and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on `None` values being accepted and treated as missing.
+**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as floats only; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` explicitly accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. A runtime probe showed that explicit `None` and omitting the tuple generate identical HTML.
+**Fix:** Keep the original contract and represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None` and document that explicit `None` is supported input.
+
+### LOW-1: The story artifact’s stated `<td>` structural count is internally inconsistent with the shipped renderer
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`
+**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s L-4/AC prose is already stale and misleading.
+**Evidence:** The story says `<td>` count == `N*M` at `13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.
+**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if the intended invariant is `N*M` data cells only.
+
+**Total: 2 HIGH + 1 MED + 1 LOW**

Validated the diff against the live worktree, ran targeted runtime probes for HTML/escaping/path behavior, and saved the review findings to /tmp/story-13-4-review.diff.
  ✓ Read shipped CohortHeatmap implementation and ratified Story 13.4 spec sources
  ✓ Run targeted probes for HTML validity, escaping, palette boundaries, and write_html path behavior
  ✓ Draft findings with severity, evidence, and fixes; save review to /tmp/story-13-4-review.diff
diff --git a//tmp/story-13-4-review.diff b//tmp/story-13-4-review.diff
index f1647d5ee4d95a1e620089fa1ac368a33d5f5da8..44c31a4f06c051cbd67babaabb1a071c6938ed94
--- a//tmp/story-13-4-review.diff
+++ b//tmp/story-13-4-review.diff
@@ -1,1059 +1,25 @@
-diff --git a/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-new file mode 100644
-index 0000000..aa90bd9
---- /dev/null
-+++ b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-@@ -0,0 +1,304 @@
-+# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
-+
-+Status: review
-+
-+## Story
-+
-+As a **post-run reviewer** sharing results outside the terminal,
-+I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
-+So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
-+
-+## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
-+
-+10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
-+
-+- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
-+
-+- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
-+
-+- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
-+
-+- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
-+  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
-+  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
-+  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
-+  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
-+  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
-+  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
-+  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
-+
-+- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
-+
-+- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
-+
-+- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
-+
-+- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
-+
-+- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
-+
-+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
-+  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
-+  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
-+  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
-+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
-+
-+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
-+
-+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
-+- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
-+- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
-+- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
-+- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
-+
-+## Acceptance Criteria
-+
-+### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
-+
-+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
-+
-+```python
-+def as_html(self) -> str:
-+    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
-+    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+    `<style>`), and `<body>` containing a `<table>` with header row +
-+    one row per task. Each cell carries inline `style="background-color: <hex>;
-+    color: <text-hex>;"` for the Pass@k color gradient.
-+
-+    All styling embedded in `<head><style>...</style>`. NO external
-+    stylesheet links, NO external image references, NO `<script>`
-+    elements — operators can email the file or save to shared storage
-+    and view offline.
-+
-+    Empty heatmap (no tasks OR no models): returns a minimal valid
-+    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
-+    `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+    Color gradient (Pass@k → background hex; text hex chosen for
-+    readable contrast per WCAG AA):
-+        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
-+
-+    Returns:
-+        Standalone HTML5 document as a string.
-+    """
-+```
-+
-+Implementation outline:
-+1. Empty case: return minimal document.
-+2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
-+3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
-+4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
-+5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
-+
-+### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
-+
-+`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
-+
-+```python
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+```
-+
-+Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
-+- `rate is None` → `_MISSING_CELL_STYLE`.
-+- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
-+
-+The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
-+
-+### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
-+
-+`src/AgentEval/_heatmap/models.py` adds after `as_html`:
-+
-+```python
-+def write_html(self, path: str | Path) -> Path:
-+    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
-+
-+    Args:
-+        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
-+            paths resolve against `Path.cwd()`. Empty string raises
-+            `ValueError`. Parent directories created with
-+            `parents=True, exist_ok=True`.
-+
-+    Returns:
-+        The resolved write path (post-`Path.resolve()`).
-+
-+    Raises:
-+        ValueError: When `path` is the empty string.
-+        OSError: When the filesystem write fails (read-only, permission, etc.).
-+            NOT caught — propagates to the caller.
-+    """
-+```
-+
-+Implementation:
-+- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
-+- `resolved = Path(path).resolve()`.
-+- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
-+- `resolved.write_text(self.as_html(), encoding="utf-8")`.
-+- `return resolved`.
-+
-+### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
-+
-+NEW file. Coverage:
-+
-+- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
-+- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
-+- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
-+- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
-+- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
-+- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
-+
-+### AC-13.4.5 — Baseline HTML fixtures for structural regression test
-+
-+NEW files:
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
-+
-+Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
-+
-+### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
-+
-+NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
-+- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
-+
-+### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
-+
-+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
-+- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
-+- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
-+- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
-+
-+### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
-+
-+`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
-+
-+### AC-13.4.9 — All-gates pass
-+
-+- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
-+- `uv run ruff check src/ tests/` clean.
-+- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
-+- `uv run mypy src/` clean (≥107 src files).
-+
-+### AC-13.4.10 — Sprint-status
-+
-+`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
-+
-+## Tasks / Subtasks
-+
-+- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
-+- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
-+- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
-+- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
-+- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
-+- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
-+- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
-+- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-+
-+## Dev Notes
-+
-+Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
-+
-+- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
-+- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
-+
-+**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
-+
-+**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
-+
-+**Cross-story lesson application:**
-+- L-1: stability-surface MUST register the new methods (AC-13.4.6).
-+- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
-+- L-3: not RF `@keyword`-decorated; no `@tier` classification.
-+- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
-+- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
-+
-+### Project Structure Notes
-+
-+- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
-+- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
-+- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
-+- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
-+
-+### References
-+
-+- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
-+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
-+- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
-+- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
-+- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
-+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
-+- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
-+
-+## Dev Agent Record
-+
-+### Agent Model Used
-+
-+claude-opus-4-7[1m]
-+
-+### Debug Log References
-+
-+2 mid-dev catches:
-+1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
-+2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.
-+
-+### Completion Notes List
-+
-+Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.
-+
-+- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
-+- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
-+- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
-+- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
-+- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
-+- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
-+- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
-+- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
-+- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
-+- **AC-13.4.10**: sprint-status flipped to `review`.
-+
-+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
-+- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
-+- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
-+- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
-+- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).
-+
-+### In-flight spec amendments
-+
-+1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.
-+
-+2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.
-+
-+### File List
-+
-+**New files:**
-+- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.
-+
-+**Modified files:**
-+- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method.
-+- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
-+- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
-+- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
-+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
-+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
-index 2f6c828..99f4117 100644
---- a/_bmad-output/implementation-artifacts/deferred-work.md
-+++ b/_bmad-output/implementation-artifacts/deferred-work.md
-@@ -390,6 +390,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
- 
- - **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
- 
-+## Deferred from: story-13.4 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
-+
-+- **DF-13.4-S1 (Phase-2.5 image-based visual regression test for `as_html()`)** — Story 13.4 D-7 in-flight amendment 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baselines) instead of the epic L2205-mandated image-based visual regression. Image regression requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) — heavy deps. Phase-2.5 evaluates whether structural baselines + manual inspection suffice OR whether image regression has empirical value warranting the deps. Catalogued as C92. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S2 (Phase-2.5 color-blind-safe palette mode for `as_html()`)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4's default 5-stop red-orange-yellow-lime-green palette is NOT WCAG 2.1 AA color-blind safe (~8% of males have red-green color blindness). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). Catalogued as C93. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
-+
- ---
- 
- *Update this file as new deferred items emerge from future reviews.*
-diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
-index 24798b7..be01029 100644
---- a/_bmad-output/implementation-artifacts/sprint-status.yaml
-+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
-@@ -154,6 +154,6 @@ development_status:
-   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
-   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
-   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
--  13-4-cohort-heatmap-html-rendering: backlog
-+  13-4-cohort-heatmap-html-rendering: review
-   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
-   epic-13-retrospective: optional
-diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
-index 604fb45..a8e6c7d 100644
---- a/_bmad-output/planning-artifacts/prd.md
-+++ b/_bmad-output/planning-artifacts/prd.md
-@@ -1580,7 +1580,7 @@ Each FR states the testable, observable capability the library must provide. For
- - **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
- - **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
- - **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
--- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
-+- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
- - **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
- - **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
- - **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
-diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
-index 051e962..df97c10 100644
---- a/docs/contracts/stability-surface.md
-+++ b/docs/contracts/stability-surface.md
-@@ -122,6 +122,15 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
- - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- 
-+### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
-+
-+Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
-+- `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
-+- `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
-+
- ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
- 
- Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
-diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
-index 05247b2..d4e41d9 100644
---- a/docs/phase-1-5-carry-overs.md
-+++ b/docs/phase-1-5-carry-overs.md
-@@ -116,7 +116,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
- | **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
- | **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
- 
--**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
-+| **C92** | **Phase-2.5: Image-based visual regression test for `as_html()` (`DF-13.4-S1`).** Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baseline fixtures); epic L2205 mandated "visual regression test against a recorded baseline image" using headless browser + pixel-diff. Headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) are heavy deps; Phase-2.5 evaluates whether the structural baseline + manual browser inspection is sufficient OR whether image regression has empirical value. *Surfaced via Story 13.4 spec D-10 + D-7 in-flight amendment 2026-06-01.* | Story 13.4 D-7 in-flight amendment — Phase-2 structural-baseline ceiling | maintainability | M | TBD | Headless browser screenshot capture + image-diff vs recorded baseline; integration into `dogfood-integration.yml` CI matrix. |
-+| **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
-+| **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
-+
-+**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL (Story 13.4 adds 3 M).
- 
- ## Execution policy
- 
-diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
-index 9be3020..bcc13aa 100644
---- a/src/AgentEval/_heatmap/models.py
-+++ b/src/AgentEval/_heatmap/models.py
-@@ -12,12 +12,14 @@
- # See the License for the specific language governing permissions and
- # limitations under the License.
- 
--"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
-+"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
- 
- from __future__ import annotations
- 
-+import html
- from dataclasses import dataclass
--from typing import TYPE_CHECKING
-+from pathlib import Path
-+from typing import TYPE_CHECKING, Final
- 
- if TYPE_CHECKING:
-     from AgentEval.discoverability.schema import (
-@@ -28,6 +30,55 @@ if TYPE_CHECKING:
- __all__ = ["CohortHeatmap"]
- 
- 
-+# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
-+# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
-+# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
-+#   [0.0, 0.2) → red (high failure)
-+#   [0.2, 0.4) → orange
-+#   [0.4, 0.6) → yellow
-+#   [0.6, 0.8) → lime
-+#   [0.8, 1.0] → green (high success)
-+# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
-+# mode (viridis/magma sequential per WCAG 2.1 AA).
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+# Missing cell (cell[(task, model)] not present in `cells`): light gray.
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+
-+
-+def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
-+    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
-+
-+    Args:
-+        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
-+
-+    Returns:
-+        ``(background_hex, text_hex)`` tuple.
-+
-+    Edge cases:
-+        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
-+        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
-+        - ``rate < 0.0`` → first stop (red); not validated upstream so
-+          defensively clamps to the bottom rather than raising.
-+    """
-+    if rate is None:
-+        return _MISSING_CELL_STYLE
-+    # Linear scan: walk the palette + return the HIGHEST entry whose lower
-+    # bound is `<=` the rate. The palette is sorted ascending by lower bound
-+    # so we walk forward and remember the last match.
-+    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
-+    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
-+        if rate >= lower:
-+            bg, txt = candidate_bg, candidate_txt
-+    return (bg, txt)
-+
-+
- @dataclass(frozen=True)
- class CohortHeatmap:
-     """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
-@@ -162,3 +213,128 @@ class CohortHeatmap:
-             body_lines.append("│ " + " │ ".join(cells) + " │")
- 
-         return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
-+
-+    def as_html(self) -> str:
-+        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
-+        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+        `<style>`), and `<body>` containing a `<table>` with header row +
-+        one row per task. Each Pass@k cell carries inline
-+        `style="background-color: <hex>; color: <text-hex>;"` for the
-+        color gradient.
-+
-+        All styling embedded in `<head><style>...</style>`. NO external
-+        stylesheet links, NO external image references, NO `<script>`
-+        elements — operators can email the file or save to shared
-+        storage and view offline.
-+
-+        Empty heatmap (no tasks OR no models): returns a minimal valid
-+        document with `<body><p>(empty heatmap)</p></body>` (symmetric
-+        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+        Pass@k color gradient (5-stop hue palette; text color chosen for
-+        WCAG AA contrast):
-+            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
-+              with text "—" (em-dash, matching `as_ascii()` fallback).
-+
-+        See module-level `_PASS_RATE_PALETTE` constant for the canonical
-+        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
-+        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
-+        alternative palette.
-+
-+        Security: all user-provided strings (task IDs, model names)
-+        pass through ``html.escape`` before insertion to prevent HTML
-+        injection. Float Pass@k values are formatted via
-+        ``f"{value:.2f}"`` (safe — no escape needed).
-+
-+        Returns:
-+            Standalone HTML5 document as a string.
-+        """
-+        if not self.tasks or not self.models:
-+            return (
-+                "<!DOCTYPE html>\n"
-+                '<html lang="en">\n'
-+                "<head>\n"
-+                '  <meta charset="utf-8">\n'
-+                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
-+                "</head>\n"
-+                "<body>\n"
-+                "  <p>(empty heatmap)</p>\n"
-+                "</body>\n"
-+                "</html>\n"
-+            )
-+
-+        data = self.as_dict()
-+        # Build header row.
-+        header_cells = ["<th>Task</th>"]
-+        for model in self.models:
-+            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
-+        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
-+
-+        # Build body rows.
-+        body_rows: list[str] = []
-+        for task in self.tasks:
-+            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
-+            for model in self.models:
-+                value = data.get(task, {}).get(model)
-+                bg, txt_color = _color_for_pass_rate(value)
-+                cell_text = "—" if value is None else f"{value:.2f}"
-+                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
-+            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
-+
-+        return (
-+            "<!DOCTYPE html>\n"
-+            '<html lang="en">\n'
-+            "<head>\n"
-+            '  <meta charset="utf-8">\n'
-+            "  <title>AgentEval Cohort Heatmap</title>\n"
-+            "  <style>\n"
-+            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
-+            "    table { border-collapse: collapse; }\n"
-+            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
-+            "    th { background-color: #0f172a; color: #ffffff; }\n"
-+            "  </style>\n"
-+            "</head>\n"
-+            "<body>\n"
-+            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
-+            "</body>\n"
-+            "</html>\n"
-+        )
-+
-+    def write_html(self, path: str | Path) -> Path:
-+        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
-+
-+        Args:
-+            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
-+                Relative paths resolve against ``Path.cwd()``. Empty
-+                string raises ``ValueError``. Parent directories are
-+                created with ``parents=True, exist_ok=True``.
-+
-+        Returns:
-+            The resolved write path (post-``Path.resolve()``).
-+
-+        Raises:
-+            ValueError: When ``path`` is the empty string.
-+            OSError: When the filesystem write fails (read-only,
-+                permission denied, etc.). NOT caught — propagates to
-+                the caller.
-+
-+        Notes:
-+            - Convenience companion to ``as_html`` per Story 13.4 D-2.
-+            - Writes UTF-8 encoded text.
-+            - Story 13.4 D-5: empty-string path rejected up-front
-+              instead of relying on ``Path("").write_text`` which
-+              would write to the current directory's empty filename.
-+        """
-+        if isinstance(path, str) and path == "":
-+            raise ValueError("write_html requires a non-empty path; got empty string")
-+        resolved = Path(path).resolve()
-+        resolved.parent.mkdir(parents=True, exist_ok=True)
-+        resolved.write_text(self.as_html(), encoding="utf-8")
-+        return resolved
-diff --git a/tests/fixtures/heatmap/baseline_2_adapter.html b/tests/fixtures/heatmap/baseline_2_adapter.html
-new file mode 100644
-index 0000000..ac48555
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_2_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>adapter_red</th><th>adapter_green</th></tr>
-+  <tr><td>task_alpha</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>task_beta</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #eab308; color: #0f172a;">0.50</td></tr>
-+  <tr><td>task_gamma</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/fixtures/heatmap/baseline_3_adapter.html b/tests/fixtures/heatmap/baseline_3_adapter.html
-new file mode 100644
-index 0000000..5987ff9
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_3_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>a</th><th>b</th><th>c</th></tr>
-+  <tr><td>t0</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>t1</td><td style="background-color: #84cc16; color: #0f172a;">0.70</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td><td style="background-color: #f97316; color: #ffffff;">0.30</td></tr>
-+  <tr><td>t2</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/unit/_heatmap/test_models_html.py b/tests/unit/_heatmap/test_models_html.py
-new file mode 100644
-index 0000000..8bfd92e
---- /dev/null
-+++ b/tests/unit/_heatmap/test_models_html.py
-@@ -0,0 +1,402 @@
-+# Copyright 2026 Many Kasiriha
-+#
-+# Licensed under the Apache License, Version 2.0 (the "License");
-+# you may not use this file except in compliance with the License.
-+# You may obtain a copy of the License at
-+#
-+#     http://www.apache.org/licenses/LICENSE-2.0
-+#
-+# Unless required by applicable law or agreed to in writing, software
-+# distributed under the License is distributed on an "AS IS" BASIS,
-+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-+# See the License for the specific language governing permissions and
-+# limitations under the License.
-+
-+"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
-+
-+Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
-+SPECIFIC structural counts (table count, tr count, td count, palette
-+hex presence) — NOT just "html.parser doesn't crash."
-+
-+Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
-+anchor test asserts the required strings appear in the docstring.
-+"""
-+
-+from __future__ import annotations
-+
-+from html.parser import HTMLParser
-+from pathlib import Path
-+
-+import pytest
-+
-+from AgentEval._heatmap.models import (
-+    _MISSING_CELL_STYLE,
-+    CohortHeatmap,
-+    _color_for_pass_rate,
-+)
-+
-+# --------------------------------------------------------------------------- #
-+# `_color_for_pass_rate` helper (4 tests)                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+@pytest.mark.parametrize(
-+    "rate,expected_bg",
-+    [
-+        (0.0, "#ef4444"),  # red — bottom stop
-+        (0.19, "#ef4444"),  # still red
-+        (0.2, "#f97316"),  # orange boundary
-+        (0.39, "#f97316"),
-+        (0.4, "#eab308"),  # yellow
-+        (0.5, "#eab308"),
-+        (0.6, "#84cc16"),  # lime
-+        (0.79, "#84cc16"),
-+        (0.8, "#22c55e"),  # green
-+        (1.0, "#22c55e"),  # top stop
-+    ],
-+)
-+def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
-+    """Each color stop boundary maps to the correct background hex."""
-+    bg, _txt = _color_for_pass_rate(rate)
-+    assert bg == expected_bg
-+
-+
-+def test_color_for_pass_rate_none_returns_missing_style() -> None:
-+    """None input → missing-cell light-gray + slate-900 text."""
-+    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
-+
-+
-+def test_color_for_pass_rate_exactly_one_returns_green() -> None:
-+    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
-+    bg, txt = _color_for_pass_rate(1.0)
-+    assert bg == "#22c55e"
-+    assert txt == "#ffffff"
-+
-+
-+def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
-+    """Defensive: negative rate → bottom stop (red) rather than raising."""
-+    bg, _txt = _color_for_pass_rate(-0.1)
-+    assert bg == "#ef4444"
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `as_html` happy paths (5 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
-+    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    html = h.as_html()
-+    assert "<!DOCTYPE html>" in html
-+    assert "(empty heatmap)" in html
-+    assert "</html>" in html
-+
-+
-+def test_as_html_single_model_3_tasks() -> None:
-+    """1 column × 3 rows produces correctly-shaped HTML."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
-+    )
-+    html = h.as_html()
-+    # Header row: <th>Task</th><th>m0</th>
-+    assert html.count("<th>") == 2
-+    # Body rows: 3 <tr>
-+    assert html.count("<tr>") == 4  # 1 header + 3 body rows
-+    # Body cells: 6 <td> (3 task names + 3 values)
-+    assert html.count("<td") == 6
-+    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
-+    assert "#22c55e" in html
-+    assert "#eab308" in html
-+    assert "#ef4444" in html
-+
-+
-+def test_as_html_3_adapter_3_tasks() -> None:
-+    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 1.0),
-+            ("t1", "b", 0.5),
-+            ("t1", "c", 0.0),
-+            ("t2", "a", 1.0),
-+            ("t2", "b", 0.5),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+    html = h.as_html()
-+    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
-+    assert html.count("<td") == 12
-+    # 4 header <th>: Task + a + b + c.
-+    assert html.count("<th>") == 4
-+
-+
-+def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
-+    """A cell missing from the input → em-dash + light-gray background."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
-+    )
-+    html = h.as_html()
-+    assert "—" in html
-+    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
-+
-+
-+def test_as_html_pass_rates_formatted_two_decimals() -> None:
-+    """Pass@k values rendered as 2-decimal floats."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.123456),),
-+    )
-+    html = h.as_html()
-+    assert "0.12" in html
-+    # NOT showing the unrounded version.
-+    assert "0.123456" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML validity (3 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+class _StructuralHTMLParser(HTMLParser):
-+    """Count opening tags + collect script data for defense-in-depth tests."""
-+
-+    def __init__(self) -> None:
-+        super().__init__()
-+        self.tag_open_counts: dict[str, int] = {}
-+        self.script_data: list[str] = []
-+        self._in_script = False
-+
-+    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
-+        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
-+        if tag == "script":
-+            self._in_script = True
-+
-+    def handle_endtag(self, tag: str) -> None:
-+        if tag == "script":
-+            self._in_script = False
-+
-+    def handle_data(self, data: str) -> None:
-+        if self._in_script:
-+            self.script_data.append(data)
-+
-+
-+def test_as_html_parses_via_stdlib_html_parser() -> None:
-+    """`html.parser.HTMLParser` parses the output without raising."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1"),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
-+    assert parser.tag_open_counts.get("table", 0) == 1
-+    # tr = 1 (header) + 2 (body rows) = 3.
-+    assert parser.tag_open_counts.get("tr", 0) == 3
-+    # th = 1 (Task header) + 2 (model headers).
-+    assert parser.tag_open_counts.get("th", 0) == 3
-+    # td = 2 tasks × (1 task name + 2 models) = 6.
-+    assert parser.tag_open_counts.get("td", 0) == 6
-+
-+
-+def test_as_html_has_no_external_resources() -> None:
-+    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # NO external stylesheet link.
-+    assert "<link" not in html
-+    # NO script element (D-3 explicit prohibition for offline-safety).
-+    assert "<script" not in html.lower()
-+    # NO external image / font URLs.
-+    assert 'src="http' not in html.lower()
-+    assert 'href="http' not in html.lower()
-+    # NO external `url(...)` references in styles.
-+    assert "url(http" not in html.lower()
-+
-+
-+def test_as_html_no_script_data_under_html_parser() -> None:
-+    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    assert parser.script_data == []
-+    assert parser.tag_open_counts.get("script", 0) == 0
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML escaping (2 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_escapes_script_tags_in_task_ids() -> None:
-+    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
-+    malicious = "<script>alert(1)</script>"
-+    h = CohortHeatmap(
-+        tasks=(malicious,),
-+        models=("m0",),
-+        cells=((malicious, "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
-+    assert "<script>alert(1)</script>" not in html
-+    assert "&lt;script&gt;" in html
-+
-+
-+def test_as_html_escapes_special_characters_in_model_names() -> None:
-+    """Model names with `&`, `<`, `>` get HTML-escaped."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("A&B<C>D",),
-+        cells=(("t0", "A&B<C>D", 0.5),),
-+    )
-+    html = h.as_html()
-+    assert "A&amp;B&lt;C&gt;D" in html
-+    # Original unescaped form must NOT appear.
-+    assert "A&B<C>D" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `write_html` file ops (4 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
-+    """write_html writes the same content as as_html + returns the resolved path."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    target = tmp_path / "heatmap.html"
-+    result = h.write_html(target)
-+    assert result == target.resolve()
-+    assert result.exists()
-+    assert result.read_text(encoding="utf-8") == h.as_html()
-+
-+
-+def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
-+    """write_html creates non-existent parent directories via mkdir(parents=True)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.5),),
-+    )
-+    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
-+    assert not target.parent.exists()
-+    result = h.write_html(target)
-+    assert result.exists()
-+    assert target.parent.is_dir()
-+
-+
-+def test_write_html_empty_string_path_raises_value_error() -> None:
-+    """write_html('') raises ValueError per D-5."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    with pytest.raises(ValueError, match="non-empty path"):
-+        h.write_html("")
-+
-+
-+def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
-+    """Both `str` and `Path` inputs work + return identical resolved paths."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    str_path = str(tmp_path / "a.html")
-+    path_obj = tmp_path / "b.html"
-+    r1 = h.write_html(str_path)
-+    r2 = h.write_html(path_obj)
-+    assert r1.exists()
-+    assert r2.exists()
-+    assert r1 == Path(str_path).resolve()
-+    assert r2 == path_obj.resolve()
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_docstring_carries_anchors() -> None:
-+    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
-+    doc = CohortHeatmap.as_html.__doc__ or ""
-+    assert "as_html" in doc.lower() or "AS_HTML" in doc
-+    assert "FR55" in doc
-+    assert "Phase-2" in doc or "Phase 2" in doc
-+    assert "embedded CSS" in doc or "embedded `<style>" in doc
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def _build_2_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
-+    return CohortHeatmap(
-+        tasks=("task_alpha", "task_beta", "task_gamma"),
-+        models=("adapter_red", "adapter_green"),
-+        cells=(
-+            ("task_alpha", "adapter_red", 1.0),
-+            ("task_alpha", "adapter_green", 0.0),
-+            ("task_beta", "adapter_red", 0.5),
-+            ("task_beta", "adapter_green", 0.5),
-+            ("task_gamma", "adapter_red", 0.0),
-+            ("task_gamma", "adapter_green", 1.0),
-+        ),
-+    )
-+
-+
-+def _build_3_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 3-adapter × 3-task input."""
-+    return CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 0.7),
-+            ("t1", "b", None),  # missing cell on purpose
-+            ("t1", "c", 0.3),
-+            ("t2", "a", 0.0),
-+            ("t2", "b", 0.0),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+
-+
-+def test_html_matches_recorded_baseline_2_adapter() -> None:
-+    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_2_adapter_baseline().as_html()
-+    assert actual == expected
-+
-+
-+def test_html_matches_recorded_baseline_3_adapter() -> None:
-+    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_3_adapter_baseline().as_html()
-+    assert actual == expected
+### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`
+**Issue:** Epic 13.4 still requires a “visual regression test against a recorded baseline image”, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not an implementation choice the story can unilaterally make, because neither `epics.md` nor any ratified contract was amended to remove the image-baseline requirement.
+**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures are `.html` files under `tests/fixtures/heatmap/`, not images.
+**Fix:** Either implement the image-based regression now, or ratify an amendment to `epics.md`/the governing spec before closing Story 13.4.
+
+### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
+**File:** `src/AgentEval/_heatmap/models.py:275`
+**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the new HTML acceptance criteria and baseline fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.
+**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the existing renderer docs say `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus model headers and `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `13-4-cohort-heatmap-html-rendering.md:98-99`.
+**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns` before shipping more surface area on the opposite orientation.
+
+### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
+**File:** `tests/unit/_heatmap/test_models_html.py:370`
+**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract beyond the dataclass/type surface: `cells` is declared as `tuple[tuple[str, str, float], ...]` and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on `None` values being accepted and treated as missing.
+**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as floats only; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` explicitly accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. A runtime probe showed that explicit `None` and omitting the tuple generate identical HTML.
+**Fix:** Keep the original contract and represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None` and document that explicit `None` is supported input.
+
+### LOW-1: The story artifact’s stated `<td>` structural count is internally inconsistent with the shipped renderer
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`
+**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s L-4/AC prose is already stale and misleading.
+**Evidence:** The story says `<td>` count == `N*M` at `13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.
+**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if the intended invariant is `N*M` data cells only.
+
+**Total: 2 HIGH + 1 MED + 1 LOW**

codex
Saved to [story-13-4-review.diff](/tmp/story-13-4-review.diff).

### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`  
**Issue:** Epic 13.4 still requires a visual regression test against a recorded baseline image, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not a local implementation choice, because no ratified source was amended to remove the image-baseline requirement.  
**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures under `tests/fixtures/heatmap/` are `.html`, not images.  
**Fix:** Implement the image-based regression now, or ratify an amendment to `epics.md` before closing Story 13.4.

### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
**File:** `src/AgentEval/_heatmap/models.py:275`  
**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the HTML AC and fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.  
**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the code says `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:98-99`.  
**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns`.

### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
**File:** `tests/unit/_heatmap/test_models_html.py:370`  
**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract: `cells` is typed as floats only and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on explicit `None` values being accepted and treated as missing.  
**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as `float`; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. Runtime probe: explicit `None` and omitting the tuple produce identical HTML.  
**Fix:** Represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None`.

### LOW-1: The story artifact’s stated `<td>` structural count is inconsistent with the shipped renderer
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`  
**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s own L-4/AC prose is already stale.  
**Evidence:** The story says `<td>` count == `N*M` at `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.  
**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if `N*M` data cells was the intended invariant.

**Total: 2 HIGH + 1 MED + 1 LOW**
diff --git a//tmp/story-13-4-review.diff b//tmp/story-13-4-review.diff
index f1647d5ee4d95a1e620089fa1ac368a33d5f5da8..44c31a4f06c051cbd67babaabb1a071c6938ed94
--- a//tmp/story-13-4-review.diff
+++ b//tmp/story-13-4-review.diff
@@ -1,1059 +1,25 @@
-diff --git a/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-new file mode 100644
-index 0000000..aa90bd9
---- /dev/null
-+++ b/_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md
-@@ -0,0 +1,304 @@
-+# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)
-+
-+Status: review
-+
-+## Story
-+
-+As a **post-run reviewer** sharing results outside the terminal,
-+I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
-+So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.
-+
-+## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
-+
-+10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**
-+
-+- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).
-+
-+- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.
-+
-+- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.
-+
-+- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
-+  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
-+  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
-+  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
-+  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
-+  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
-+  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
-+  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.
-+
-+- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.
-+
-+- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."
-+
-+- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.
-+
-+- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.
-+
-+- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.
-+
-+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
-+  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
-+  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
-+  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
-+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.
-+
-+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews
-+
-+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
-+- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
-+- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
-+- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
-+- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.
-+
-+## Acceptance Criteria
-+
-+### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method
-+
-+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):
-+
-+```python
-+def as_html(self) -> str:
-+    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
-+    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+    `<style>`), and `<body>` containing a `<table>` with header row +
-+    one row per task. Each cell carries inline `style="background-color: <hex>;
-+    color: <text-hex>;"` for the Pass@k color gradient.
-+
-+    All styling embedded in `<head><style>...</style>`. NO external
-+    stylesheet links, NO external image references, NO `<script>`
-+    elements — operators can email the file or save to shared storage
-+    and view offline.
-+
-+    Empty heatmap (no tasks OR no models): returns a minimal valid
-+    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
-+    `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+    Color gradient (Pass@k → background hex; text hex chosen for
-+    readable contrast per WCAG AA):
-+        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"
-+
-+    Returns:
-+        Standalone HTML5 document as a string.
-+    """
-+```
-+
-+Implementation outline:
-+1. Empty case: return minimal document.
-+2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
-+3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
-+4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
-+5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.
-+
-+### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant
-+
-+`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):
-+
-+```python
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+```
-+
-+Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
-+- `rate is None` → `_MISSING_CELL_STYLE`.
-+- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).
-+
-+The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).
-+
-+### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method
-+
-+`src/AgentEval/_heatmap/models.py` adds after `as_html`:
-+
-+```python
-+def write_html(self, path: str | Path) -> Path:
-+    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).
-+
-+    Args:
-+        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
-+            paths resolve against `Path.cwd()`. Empty string raises
-+            `ValueError`. Parent directories created with
-+            `parents=True, exist_ok=True`.
-+
-+    Returns:
-+        The resolved write path (post-`Path.resolve()`).
-+
-+    Raises:
-+        ValueError: When `path` is the empty string.
-+        OSError: When the filesystem write fails (read-only, permission, etc.).
-+            NOT caught — propagates to the caller.
-+    """
-+```
-+
-+Implementation:
-+- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
-+- `resolved = Path(path).resolve()`.
-+- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
-+- `resolved.write_text(self.as_html(), encoding="utf-8")`.
-+- `return resolved`.
-+
-+### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)
-+
-+NEW file. Coverage:
-+
-+- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
-+- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * n_models` `<td>` for the body + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`.
-+- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
-+- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
-+- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
-+- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.
-+
-+### AC-13.4.5 — Baseline HTML fixtures for structural regression test
-+
-+NEW files:
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.
-+
-+Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).
-+
-+### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson
-+
-+NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
-+- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.
-+
-+### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)
-+
-+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
-+- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
-+- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
-+- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.
-+
-+### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)
-+
-+`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.
-+
-+### AC-13.4.9 — All-gates pass
-+
-+- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
-+- `uv run ruff check src/ tests/` clean.
-+- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
-+- `uv run mypy src/` clean (≥107 src files).
-+
-+### AC-13.4.10 — Sprint-status
-+
-+`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.
-+
-+## Tasks / Subtasks
-+
-+- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
-+- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
-+- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
-+- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
-+- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
-+- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
-+- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
-+- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-+
-+## Dev Notes
-+
-+Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:
-+
-+- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
-+- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).
-+
-+**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.
-+
-+**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).
-+
-+**Cross-story lesson application:**
-+- L-1: stability-surface MUST register the new methods (AC-13.4.6).
-+- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
-+- L-3: not RF `@keyword`-decorated; no `@tier` classification.
-+- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
-+- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.
-+
-+### Project Structure Notes
-+
-+- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
-+- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
-+- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
-+- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).
-+
-+### References
-+
-+- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
-+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
-+- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
-+- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
-+- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
-+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
-+- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.
-+
-+## Dev Agent Record
-+
-+### Agent Model Used
-+
-+claude-opus-4-7[1m]
-+
-+### Debug Log References
-+
-+2 mid-dev catches:
-+1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
-+2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.
-+
-+### Completion Notes List
-+
-+Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.
-+
-+- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
-+- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
-+- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
-+- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
-+- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
-+- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
-+- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
-+- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
-+- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
-+- **AC-13.4.10**: sprint-status flipped to `review`.
-+
-+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)
-+
-+- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
-+- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
-+- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
-+- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
-+- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).
-+
-+### In-flight spec amendments
-+
-+1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.
-+
-+2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.
-+
-+### File List
-+
-+**New files:**
-+- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
-+- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
-+- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.
-+
-+**Modified files:**
-+- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method.
-+- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
-+- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
-+- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
-+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
-+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
-diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
-index 2f6c828..99f4117 100644
---- a/_bmad-output/implementation-artifacts/deferred-work.md
-+++ b/_bmad-output/implementation-artifacts/deferred-work.md
-@@ -390,6 +390,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
- 
- - **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
- 
-+## Deferred from: story-13.4 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
-+
-+- **DF-13.4-S1 (Phase-2.5 image-based visual regression test for `as_html()`)** — Story 13.4 D-7 in-flight amendment 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baselines) instead of the epic L2205-mandated image-based visual regression. Image regression requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) — heavy deps. Phase-2.5 evaluates whether structural baselines + manual inspection suffice OR whether image regression has empirical value warranting the deps. Catalogued as C92. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S2 (Phase-2.5 color-blind-safe palette mode for `as_html()`)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4's default 5-stop red-orange-yellow-lime-green palette is NOT WCAG 2.1 AA color-blind safe (~8% of males have red-green color blindness). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). Catalogued as C93. Effort: M. Phase-2.5.
-+
-+- **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
-+
- ---
- 
- *Update this file as new deferred items emerge from future reviews.*
-diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
-index 24798b7..be01029 100644
---- a/_bmad-output/implementation-artifacts/sprint-status.yaml
-+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
-@@ -154,6 +154,6 @@ development_status:
-   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
-   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
-   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
--  13-4-cohort-heatmap-html-rendering: backlog
-+  13-4-cohort-heatmap-html-rendering: review
-   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
-   epic-13-retrospective: optional
-diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
-index 604fb45..a8e6c7d 100644
---- a/_bmad-output/planning-artifacts/prd.md
-+++ b/_bmad-output/planning-artifacts/prd.md
-@@ -1580,7 +1580,7 @@ Each FR states the testable, observable capability the library must provide. For
- - **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
- - **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
- - **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
--- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
-+- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <DiscoverabilityResult>` (and equivalent for any multi-cohort metric, including `DiscoverabilityComparisonResult` per Story 13.3) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2 — Story 13.4 ships this; standalone HTML5 document with embedded CSS color-coded by Pass@k), `as_dict() -> dict` (machine-readable). `write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface. Verifiable via fixture matching the documented ASCII format. Story 13.3 D-1 + Opus LOW-1 fix-the-losing-source-NOW 2026-06-01: stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
- - **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
- - **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
- - **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
-diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
-index 051e962..df97c10 100644
---- a/docs/contracts/stability-surface.md
-+++ b/docs/contracts/stability-surface.md
-@@ -122,6 +122,15 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
- - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
- 
-+### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)
-+
-+Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatmap`:
-+
-+- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same stability tier as `as_ascii()` + `as_dict()` (Story 8b.2). Document structure (`<!DOCTYPE html>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` IS `stable` (operators may scrape colors from the HTML for downstream tooling). "Standalone document" guarantee (no external `<link>` / no external `src="http"` / no `<script>`) is `stable` per D-3.
-+- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`. Resolved-Path return + UTF-8 encoding contract are `stable`.
-+- `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
-+- `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
-+
- ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
- 
- Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
-diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
-index 05247b2..d4e41d9 100644
---- a/docs/phase-1-5-carry-overs.md
-+++ b/docs/phase-1-5-carry-overs.md
-@@ -116,7 +116,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
- | **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
- | **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
- 
--**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
-+| **C92** | **Phase-2.5: Image-based visual regression test for `as_html()` (`DF-13.4-S1`).** Story 13.4 ships STRUCTURAL regression (byte-equality vs recorded `.html` baseline fixtures); epic L2205 mandated "visual regression test against a recorded baseline image" using headless browser + pixel-diff. Headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash) are heavy deps; Phase-2.5 evaluates whether the structural baseline + manual browser inspection is sufficient OR whether image regression has empirical value. *Surfaced via Story 13.4 spec D-10 + D-7 in-flight amendment 2026-06-01.* | Story 13.4 D-7 in-flight amendment — Phase-2 structural-baseline ceiling | maintainability | M | TBD | Headless browser screenshot capture + image-diff vs recorded baseline; integration into `dogfood-integration.yml` CI matrix. |
-+| **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
-+| **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
-+
-+**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL (Story 13.4 adds 3 M).
- 
- ## Execution policy
- 
-diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
-index 9be3020..bcc13aa 100644
---- a/src/AgentEval/_heatmap/models.py
-+++ b/src/AgentEval/_heatmap/models.py
-@@ -12,12 +12,14 @@
- # See the License for the specific language governing permissions and
- # limitations under the License.
- 
--"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
-+"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""
- 
- from __future__ import annotations
- 
-+import html
- from dataclasses import dataclass
--from typing import TYPE_CHECKING
-+from pathlib import Path
-+from typing import TYPE_CHECKING, Final
- 
- if TYPE_CHECKING:
-     from AgentEval.discoverability.schema import (
-@@ -28,6 +30,55 @@ if TYPE_CHECKING:
- __all__ = ["CohortHeatmap"]
- 
- 
-+# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
-+# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
-+# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
-+#   [0.0, 0.2) → red (high failure)
-+#   [0.2, 0.4) → orange
-+#   [0.4, 0.6) → yellow
-+#   [0.6, 0.8) → lime
-+#   [0.8, 1.0] → green (high success)
-+# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
-+# mode (viridis/magma sequential per WCAG 2.1 AA).
-+_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
-+    # (lower_bound_inclusive, background_hex, text_hex)
-+    (0.0, "#ef4444", "#ffffff"),  # red — high failure
-+    (0.2, "#f97316", "#ffffff"),  # orange
-+    (0.4, "#eab308", "#0f172a"),  # yellow
-+    (0.6, "#84cc16", "#0f172a"),  # lime
-+    (0.8, "#22c55e", "#ffffff"),  # green — high success
-+)
-+# Missing cell (cell[(task, model)] not present in `cells`): light gray.
-+_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
-+
-+
-+def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
-+    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.
-+
-+    Args:
-+        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.
-+
-+    Returns:
-+        ``(background_hex, text_hex)`` tuple.
-+
-+    Edge cases:
-+        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
-+        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
-+        - ``rate < 0.0`` → first stop (red); not validated upstream so
-+          defensively clamps to the bottom rather than raising.
-+    """
-+    if rate is None:
-+        return _MISSING_CELL_STYLE
-+    # Linear scan: walk the palette + return the HIGHEST entry whose lower
-+    # bound is `<=` the rate. The palette is sorted ascending by lower bound
-+    # so we walk forward and remember the last match.
-+    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
-+    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
-+        if rate >= lower:
-+            bg, txt = candidate_bg, candidate_txt
-+    return (bg, txt)
-+
-+
- @dataclass(frozen=True)
- class CohortHeatmap:
-     """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
-@@ -162,3 +213,128 @@ class CohortHeatmap:
-             body_lines.append("│ " + " │ ".join(cells) + " │")
- 
-         return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])
-+
-+    def as_html(self) -> str:
-+        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).
-+
-+        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
-+        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
-+        `<style>`), and `<body>` containing a `<table>` with header row +
-+        one row per task. Each Pass@k cell carries inline
-+        `style="background-color: <hex>; color: <text-hex>;"` for the
-+        color gradient.
-+
-+        All styling embedded in `<head><style>...</style>`. NO external
-+        stylesheet links, NO external image references, NO `<script>`
-+        elements — operators can email the file or save to shared
-+        storage and view offline.
-+
-+        Empty heatmap (no tasks OR no models): returns a minimal valid
-+        document with `<body><p>(empty heatmap)</p></body>` (symmetric
-+        with `as_ascii()`'s `"(empty heatmap)"` sentinel).
-+
-+        Pass@k color gradient (5-stop hue palette; text color chosen for
-+        WCAG AA contrast):
-+            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
-+            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
-+            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
-+            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
-+            - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
-+            - missing cell (None) → light gray (#e5e7eb bg / #0f172a text)
-+              with text "—" (em-dash, matching `as_ascii()` fallback).
-+
-+        See module-level `_PASS_RATE_PALETTE` constant for the canonical
-+        boundaries + hex values. Story 13.4 D-4 ratifies the gradient.
-+        Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe
-+        alternative palette.
-+
-+        Security: all user-provided strings (task IDs, model names)
-+        pass through ``html.escape`` before insertion to prevent HTML
-+        injection. Float Pass@k values are formatted via
-+        ``f"{value:.2f}"`` (safe — no escape needed).
-+
-+        Returns:
-+            Standalone HTML5 document as a string.
-+        """
-+        if not self.tasks or not self.models:
-+            return (
-+                "<!DOCTYPE html>\n"
-+                '<html lang="en">\n'
-+                "<head>\n"
-+                '  <meta charset="utf-8">\n'
-+                "  <title>AgentEval Cohort Heatmap (empty)</title>\n"
-+                "</head>\n"
-+                "<body>\n"
-+                "  <p>(empty heatmap)</p>\n"
-+                "</body>\n"
-+                "</html>\n"
-+            )
-+
-+        data = self.as_dict()
-+        # Build header row.
-+        header_cells = ["<th>Task</th>"]
-+        for model in self.models:
-+            header_cells.append(f"<th>{html.escape(model, quote=False)}</th>")
-+        header_row = "  <tr>" + "".join(header_cells) + "</tr>\n"
-+
-+        # Build body rows.
-+        body_rows: list[str] = []
-+        for task in self.tasks:
-+            cells = [f"<td>{html.escape(task, quote=False)}</td>"]
-+            for model in self.models:
-+                value = data.get(task, {}).get(model)
-+                bg, txt_color = _color_for_pass_rate(value)
-+                cell_text = "—" if value is None else f"{value:.2f}"
-+                cells.append(f'<td style="background-color: {bg}; color: {txt_color};">{cell_text}</td>')
-+            body_rows.append("  <tr>" + "".join(cells) + "</tr>\n")
-+
-+        return (
-+            "<!DOCTYPE html>\n"
-+            '<html lang="en">\n'
-+            "<head>\n"
-+            '  <meta charset="utf-8">\n'
-+            "  <title>AgentEval Cohort Heatmap</title>\n"
-+            "  <style>\n"
-+            "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }\n"
-+            "    table { border-collapse: collapse; }\n"
-+            "    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }\n"
-+            "    th { background-color: #0f172a; color: #ffffff; }\n"
-+            "  </style>\n"
-+            "</head>\n"
-+            "<body>\n"
-+            "<table>\n" + header_row + "".join(body_rows) + "</table>\n"
-+            "</body>\n"
-+            "</html>\n"
-+        )
-+
-+    def write_html(self, path: str | Path) -> Path:
-+        """Write `as_html()` output to `path`; return the resolved path (Story 13.4 / epic L2203).
-+
-+        Args:
-+            path: Filesystem path. Accepts ``str`` OR ``pathlib.Path``.
-+                Relative paths resolve against ``Path.cwd()``. Empty
-+                string raises ``ValueError``. Parent directories are
-+                created with ``parents=True, exist_ok=True``.
-+
-+        Returns:
-+            The resolved write path (post-``Path.resolve()``).
-+
-+        Raises:
-+            ValueError: When ``path`` is the empty string.
-+            OSError: When the filesystem write fails (read-only,
-+                permission denied, etc.). NOT caught — propagates to
-+                the caller.
-+
-+        Notes:
-+            - Convenience companion to ``as_html`` per Story 13.4 D-2.
-+            - Writes UTF-8 encoded text.
-+            - Story 13.4 D-5: empty-string path rejected up-front
-+              instead of relying on ``Path("").write_text`` which
-+              would write to the current directory's empty filename.
-+        """
-+        if isinstance(path, str) and path == "":
-+            raise ValueError("write_html requires a non-empty path; got empty string")
-+        resolved = Path(path).resolve()
-+        resolved.parent.mkdir(parents=True, exist_ok=True)
-+        resolved.write_text(self.as_html(), encoding="utf-8")
-+        return resolved
-diff --git a/tests/fixtures/heatmap/baseline_2_adapter.html b/tests/fixtures/heatmap/baseline_2_adapter.html
-new file mode 100644
-index 0000000..ac48555
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_2_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>adapter_red</th><th>adapter_green</th></tr>
-+  <tr><td>task_alpha</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>task_beta</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #eab308; color: #0f172a;">0.50</td></tr>
-+  <tr><td>task_gamma</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/fixtures/heatmap/baseline_3_adapter.html b/tests/fixtures/heatmap/baseline_3_adapter.html
-new file mode 100644
-index 0000000..5987ff9
---- /dev/null
-+++ b/tests/fixtures/heatmap/baseline_3_adapter.html
-@@ -0,0 +1,21 @@
-+<!DOCTYPE html>
-+<html lang="en">
-+<head>
-+  <meta charset="utf-8">
-+  <title>AgentEval Cohort Heatmap</title>
-+  <style>
-+    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 1em; }
-+    table { border-collapse: collapse; }
-+    th, td { border: 1px solid #94a3b8; padding: 0.4em 0.6em; text-align: center; }
-+    th { background-color: #0f172a; color: #ffffff; }
-+  </style>
-+</head>
-+<body>
-+<table>
-+  <tr><th>Task</th><th>a</th><th>b</th><th>c</th></tr>
-+  <tr><td>t0</td><td style="background-color: #22c55e; color: #ffffff;">1.00</td><td style="background-color: #eab308; color: #0f172a;">0.50</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+  <tr><td>t1</td><td style="background-color: #84cc16; color: #0f172a;">0.70</td><td style="background-color: #e5e7eb; color: #0f172a;">—</td><td style="background-color: #f97316; color: #ffffff;">0.30</td></tr>
-+  <tr><td>t2</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td><td style="background-color: #ef4444; color: #ffffff;">0.00</td></tr>
-+</table>
-+</body>
-+</html>
-diff --git a/tests/unit/_heatmap/test_models_html.py b/tests/unit/_heatmap/test_models_html.py
-new file mode 100644
-index 0000000..8bfd92e
---- /dev/null
-+++ b/tests/unit/_heatmap/test_models_html.py
-@@ -0,0 +1,402 @@
-+# Copyright 2026 Many Kasiriha
-+#
-+# Licensed under the Apache License, Version 2.0 (the "License");
-+# you may not use this file except in compliance with the License.
-+# You may obtain a copy of the License at
-+#
-+#     http://www.apache.org/licenses/LICENSE-2.0
-+#
-+# Unless required by applicable law or agreed to in writing, software
-+# distributed under the License is distributed on an "AS IS" BASIS,
-+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-+# See the License for the specific language governing permissions and
-+# limitations under the License.
-+
-+"""Unit tests for `CohortHeatmap.as_html` + `write_html` + helpers (Story 13.4 / PRD FR55).
-+
-+Per Story 13.3 L-4 lesson (empirical correctness verification): asserts
-+SPECIFIC structural counts (table count, tr count, td count, palette
-+hex presence) — NOT just "html.parser doesn't crash."
-+
-+Per Story 13.1 + 13.3 L-5 lesson (docstring precision): docstring
-+anchor test asserts the required strings appear in the docstring.
-+"""
-+
-+from __future__ import annotations
-+
-+from html.parser import HTMLParser
-+from pathlib import Path
-+
-+import pytest
-+
-+from AgentEval._heatmap.models import (
-+    _MISSING_CELL_STYLE,
-+    CohortHeatmap,
-+    _color_for_pass_rate,
-+)
-+
-+# --------------------------------------------------------------------------- #
-+# `_color_for_pass_rate` helper (4 tests)                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+@pytest.mark.parametrize(
-+    "rate,expected_bg",
-+    [
-+        (0.0, "#ef4444"),  # red — bottom stop
-+        (0.19, "#ef4444"),  # still red
-+        (0.2, "#f97316"),  # orange boundary
-+        (0.39, "#f97316"),
-+        (0.4, "#eab308"),  # yellow
-+        (0.5, "#eab308"),
-+        (0.6, "#84cc16"),  # lime
-+        (0.79, "#84cc16"),
-+        (0.8, "#22c55e"),  # green
-+        (1.0, "#22c55e"),  # top stop
-+    ],
-+)
-+def test_color_for_pass_rate_boundaries(rate: float, expected_bg: str) -> None:
-+    """Each color stop boundary maps to the correct background hex."""
-+    bg, _txt = _color_for_pass_rate(rate)
-+    assert bg == expected_bg
-+
-+
-+def test_color_for_pass_rate_none_returns_missing_style() -> None:
-+    """None input → missing-cell light-gray + slate-900 text."""
-+    assert _color_for_pass_rate(None) == _MISSING_CELL_STYLE
-+
-+
-+def test_color_for_pass_rate_exactly_one_returns_green() -> None:
-+    """rate == 1.0 falls into the [0.8, 1.0] green stop (NOT a missing-cell fallthrough)."""
-+    bg, txt = _color_for_pass_rate(1.0)
-+    assert bg == "#22c55e"
-+    assert txt == "#ffffff"
-+
-+
-+def test_color_for_pass_rate_below_zero_clamps_to_red() -> None:
-+    """Defensive: negative rate → bottom stop (red) rather than raising."""
-+    bg, _txt = _color_for_pass_rate(-0.1)
-+    assert bg == "#ef4444"
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `as_html` happy paths (5 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_empty_heatmap_returns_empty_sentinel() -> None:
-+    """Empty (no tasks AND no models) → minimal document with `(empty heatmap)` paragraph."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    html = h.as_html()
-+    assert "<!DOCTYPE html>" in html
-+    assert "(empty heatmap)" in html
-+    assert "</html>" in html
-+
-+
-+def test_as_html_single_model_3_tasks() -> None:
-+    """1 column × 3 rows produces correctly-shaped HTML."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0), ("t1", "m0", 0.5), ("t2", "m0", 0.0)),
-+    )
-+    html = h.as_html()
-+    # Header row: <th>Task</th><th>m0</th>
-+    assert html.count("<th>") == 2
-+    # Body rows: 3 <tr>
-+    assert html.count("<tr>") == 4  # 1 header + 3 body rows
-+    # Body cells: 6 <td> (3 task names + 3 values)
-+    assert html.count("<td") == 6
-+    # Color hex presence: green (1.0), yellow (0.5), red (0.0).
-+    assert "#22c55e" in html
-+    assert "#eab308" in html
-+    assert "#ef4444" in html
-+
-+
-+def test_as_html_3_adapter_3_tasks() -> None:
-+    """3-column × 3-row heatmap from a Story 13.3-style cross-adapter input."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 1.0),
-+            ("t1", "b", 0.5),
-+            ("t1", "c", 0.0),
-+            ("t2", "a", 1.0),
-+            ("t2", "b", 0.5),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+    html = h.as_html()
-+    # Body cells: 3 tasks × (1 task name + 3 models) = 12 <td>.
-+    assert html.count("<td") == 12
-+    # 4 header <th>: Task + a + b + c.
-+    assert html.count("<th>") == 4
-+
-+
-+def test_as_html_missing_cell_renders_emdash_and_gray() -> None:
-+    """A cell missing from the input → em-dash + light-gray background."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0),),  # NO cell for (t0, m1)
-+    )
-+    html = h.as_html()
-+    assert "—" in html
-+    assert _MISSING_CELL_STYLE[0] in html  # #e5e7eb
-+
-+
-+def test_as_html_pass_rates_formatted_two_decimals() -> None:
-+    """Pass@k values rendered as 2-decimal floats."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.123456),),
-+    )
-+    html = h.as_html()
-+    assert "0.12" in html
-+    # NOT showing the unrounded version.
-+    assert "0.123456" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML validity (3 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+class _StructuralHTMLParser(HTMLParser):
-+    """Count opening tags + collect script data for defense-in-depth tests."""
-+
-+    def __init__(self) -> None:
-+        super().__init__()
-+        self.tag_open_counts: dict[str, int] = {}
-+        self.script_data: list[str] = []
-+        self._in_script = False
-+
-+    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
-+        self.tag_open_counts[tag] = self.tag_open_counts.get(tag, 0) + 1
-+        if tag == "script":
-+            self._in_script = True
-+
-+    def handle_endtag(self, tag: str) -> None:
-+        if tag == "script":
-+            self._in_script = False
-+
-+    def handle_data(self, data: str) -> None:
-+        if self._in_script:
-+            self.script_data.append(data)
-+
-+
-+def test_as_html_parses_via_stdlib_html_parser() -> None:
-+    """`html.parser.HTMLParser` parses the output without raising."""
-+    h = CohortHeatmap(
-+        tasks=("t0", "t1"),
-+        models=("m0", "m1"),
-+        cells=(("t0", "m0", 1.0), ("t0", "m1", 0.5), ("t1", "m0", 0.0), ("t1", "m1", 0.7)),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    # Structural assertions (Story 13.3 L-4: specific counts, not just "parses").
-+    assert parser.tag_open_counts.get("table", 0) == 1
-+    # tr = 1 (header) + 2 (body rows) = 3.
-+    assert parser.tag_open_counts.get("tr", 0) == 3
-+    # th = 1 (Task header) + 2 (model headers).
-+    assert parser.tag_open_counts.get("th", 0) == 3
-+    # td = 2 tasks × (1 task name + 2 models) = 6.
-+    assert parser.tag_open_counts.get("td", 0) == 6
-+
-+
-+def test_as_html_has_no_external_resources() -> None:
-+    """No `<link>`, no `<script>`, no external `src="http..."` (D-3 standalone requirement)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # NO external stylesheet link.
-+    assert "<link" not in html
-+    # NO script element (D-3 explicit prohibition for offline-safety).
-+    assert "<script" not in html.lower()
-+    # NO external image / font URLs.
-+    assert 'src="http' not in html.lower()
-+    assert 'href="http' not in html.lower()
-+    # NO external `url(...)` references in styles.
-+    assert "url(http" not in html.lower()
-+
-+
-+def test_as_html_no_script_data_under_html_parser() -> None:
-+    """Defense-in-depth: even if a `<script>` slipped in, `html.parser` collects no data inside it."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    parser = _StructuralHTMLParser()
-+    parser.feed(h.as_html())
-+    parser.close()
-+    assert parser.script_data == []
-+    assert parser.tag_open_counts.get("script", 0) == 0
-+
-+
-+# --------------------------------------------------------------------------- #
-+# HTML escaping (2 tests)                                                     #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_escapes_script_tags_in_task_ids() -> None:
-+    """Operator-controlled task IDs with `<script>` content get escaped (NOT executed)."""
-+    malicious = "<script>alert(1)</script>"
-+    h = CohortHeatmap(
-+        tasks=(malicious,),
-+        models=("m0",),
-+        cells=((malicious, "m0", 1.0),),
-+    )
-+    html = h.as_html()
-+    # The literal `<script>` text in the task ID must be escaped, NOT rendered as a tag.
-+    assert "<script>alert(1)</script>" not in html
-+    assert "&lt;script&gt;" in html
-+
-+
-+def test_as_html_escapes_special_characters_in_model_names() -> None:
-+    """Model names with `&`, `<`, `>` get HTML-escaped."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("A&B<C>D",),
-+        cells=(("t0", "A&B<C>D", 0.5),),
-+    )
-+    html = h.as_html()
-+    assert "A&amp;B&lt;C&gt;D" in html
-+    # Original unescaped form must NOT appear.
-+    assert "A&B<C>D" not in html
-+
-+
-+# --------------------------------------------------------------------------- #
-+# `write_html` file ops (4 tests)                                             #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_write_html_writes_file_and_returns_resolved_path(tmp_path: Path) -> None:
-+    """write_html writes the same content as as_html + returns the resolved path."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    target = tmp_path / "heatmap.html"
-+    result = h.write_html(target)
-+    assert result == target.resolve()
-+    assert result.exists()
-+    assert result.read_text(encoding="utf-8") == h.as_html()
-+
-+
-+def test_write_html_creates_nested_parent_dirs(tmp_path: Path) -> None:
-+    """write_html creates non-existent parent directories via mkdir(parents=True)."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 0.5),),
-+    )
-+    target = tmp_path / "deep" / "nested" / "dir" / "heatmap.html"
-+    assert not target.parent.exists()
-+    result = h.write_html(target)
-+    assert result.exists()
-+    assert target.parent.is_dir()
-+
-+
-+def test_write_html_empty_string_path_raises_value_error() -> None:
-+    """write_html('') raises ValueError per D-5."""
-+    h = CohortHeatmap(tasks=(), models=(), cells=())
-+    with pytest.raises(ValueError, match="non-empty path"):
-+        h.write_html("")
-+
-+
-+def test_write_html_accepts_str_and_path(tmp_path: Path) -> None:
-+    """Both `str` and `Path` inputs work + return identical resolved paths."""
-+    h = CohortHeatmap(
-+        tasks=("t0",),
-+        models=("m0",),
-+        cells=(("t0", "m0", 1.0),),
-+    )
-+    str_path = str(tmp_path / "a.html")
-+    path_obj = tmp_path / "b.html"
-+    r1 = h.write_html(str_path)
-+    r2 = h.write_html(path_obj)
-+    assert r1.exists()
-+    assert r2.exists()
-+    assert r1 == Path(str_path).resolve()
-+    assert r2 == path_obj.resolve()
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Browser-Library docstring anchors (L-5 lesson; 1 test)                      #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def test_as_html_docstring_carries_anchors() -> None:
-+    """Docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per Story 13.4 L-5."""
-+    doc = CohortHeatmap.as_html.__doc__ or ""
-+    assert "as_html" in doc.lower() or "AS_HTML" in doc
-+    assert "FR55" in doc
-+    assert "Phase-2" in doc or "Phase 2" in doc
-+    assert "embedded CSS" in doc or "embedded `<style>" in doc
-+
-+
-+# --------------------------------------------------------------------------- #
-+# Structural-regression baseline tests (AC-13.4.5; 2 tests)                   #
-+# --------------------------------------------------------------------------- #
-+
-+
-+def _build_2_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 2-adapter × 3-task input for the baseline fixture."""
-+    return CohortHeatmap(
-+        tasks=("task_alpha", "task_beta", "task_gamma"),
-+        models=("adapter_red", "adapter_green"),
-+        cells=(
-+            ("task_alpha", "adapter_red", 1.0),
-+            ("task_alpha", "adapter_green", 0.0),
-+            ("task_beta", "adapter_red", 0.5),
-+            ("task_beta", "adapter_green", 0.5),
-+            ("task_gamma", "adapter_red", 0.0),
-+            ("task_gamma", "adapter_green", 1.0),
-+        ),
-+    )
-+
-+
-+def _build_3_adapter_baseline() -> CohortHeatmap:
-+    """Deterministic 3-adapter × 3-task input."""
-+    return CohortHeatmap(
-+        tasks=("t0", "t1", "t2"),
-+        models=("a", "b", "c"),
-+        cells=(
-+            ("t0", "a", 1.0),
-+            ("t0", "b", 0.5),
-+            ("t0", "c", 0.0),
-+            ("t1", "a", 0.7),
-+            ("t1", "b", None),  # missing cell on purpose
-+            ("t1", "c", 0.3),
-+            ("t2", "a", 0.0),
-+            ("t2", "b", 0.0),
-+            ("t2", "c", 0.0),
-+        ),
-+    )
-+
-+
-+def test_html_matches_recorded_baseline_2_adapter() -> None:
-+    """2-adapter × 3-task output matches the recorded baseline byte-for-byte (per D-7)."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_2_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_2_adapter_baseline().as_html()
-+    assert actual == expected
-+
-+
-+def test_html_matches_recorded_baseline_3_adapter() -> None:
-+    """3-adapter × 3-task output matches the recorded baseline byte-for-byte."""
-+    fixture = Path(__file__).parent.parent.parent / "fixtures" / "heatmap" / "baseline_3_adapter.html"
-+    expected = fixture.read_text(encoding="utf-8")
-+    actual = _build_3_adapter_baseline().as_html()
-+    assert actual == expected
+### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`
+**Issue:** Epic 13.4 still requires a “visual regression test against a recorded baseline image”, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not an implementation choice the story can unilaterally make, because neither `epics.md` nor any ratified contract was amended to remove the image-baseline requirement.
+**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures are `.html` files under `tests/fixtures/heatmap/`, not images.
+**Fix:** Either implement the image-based regression now, or ratify an amendment to `epics.md`/the governing spec before closing Story 13.4.
+
+### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
+**File:** `src/AgentEval/_heatmap/models.py:275`
+**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the new HTML acceptance criteria and baseline fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.
+**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the existing renderer docs say `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus model headers and `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `13-4-cohort-heatmap-html-rendering.md:98-99`.
+**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns` before shipping more surface area on the opposite orientation.
+
+### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
+**File:** `tests/unit/_heatmap/test_models_html.py:370`
+**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract beyond the dataclass/type surface: `cells` is declared as `tuple[tuple[str, str, float], ...]` and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on `None` values being accepted and treated as missing.
+**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as floats only; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` explicitly accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. A runtime probe showed that explicit `None` and omitting the tuple generate identical HTML.
+**Fix:** Keep the original contract and represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None` and document that explicit `None` is supported input.
+
+### LOW-1: The story artifact’s stated `<td>` structural count is internally inconsistent with the shipped renderer
+**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`
+**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s L-4/AC prose is already stale and misleading.
+**Evidence:** The story says `<td>` count == `N*M` at `13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.
+**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if the intended invariant is `N*M` data cells only.
+
+**Total: 2 HIGH + 1 MED + 1 LOW**

tokens used
94,699
Saved to [story-13-4-review.diff](/tmp/story-13-4-review.diff).

### HIGH-1: Epic-mandated image regression was deferred without a ratified spec change
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:34`  
**Issue:** Epic 13.4 still requires a visual regression test against a recorded baseline image, but this story explicitly defers that requirement and ships only HTML text fixtures. That is spec drift, not a local implementation choice, because no ratified source was amended to remove the image-baseline requirement.  
**Evidence:** `_bmad-output/planning-artifacts/epics.md:2205` says `visual regression test against a recorded baseline image`; this story says `defer image-based visual regression to Phase-2.5` and `ship STRUCTURAL regression test instead` (`13-4-cohort-heatmap-html-rendering.md:34`, `:172`), and the committed fixtures under `tests/fixtures/heatmap/` are `.html`, not images.  
**Fix:** Implement the image-based regression now, or ratify an amendment to `epics.md` before closing Story 13.4.

### HIGH-2: Story 13.4 cements a table orientation that still contradicts canonical FR55
**File:** `src/AgentEval/_heatmap/models.py:275`  
**Issue:** FR55 still describes the cohort heatmap as `model rows × task-cluster columns`, but the shipped renderer builds `Task` as the first header cell and emits one row per task with model columns. Story 13.4 then bakes that same orientation into the HTML AC and fixtures without amending FR55, so the feature is being expanded on top of an unresolved contract mismatch.  
**Evidence:** `_bmad-output/planning-artifacts/prd.md:1583` says `model rows × task-cluster columns`; the code says `Rows = tasks, columns = models` (`src/AgentEval/_heatmap/models.py:166`) and `as_html()` emits `<th>Task</th>` plus `for task in self.tasks:` rows (`src/AgentEval/_heatmap/models.py:275-289`). The story AC repeats that layout at `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:98-99`.  
**Fix:** Either transpose the HTML/ASCII renderers and fixtures to match FR55, or amend FR55 to ratify `tasks as rows / models as columns`.

### MED-1: The regression fixture relies on an undocumented `None` cell state instead of the specified “missing-by-omission” representation
**File:** `tests/unit/_heatmap/test_models_html.py:370`  
**Issue:** AC-13.4.2 defines a missing cell as an absent `(task, model)` tuple, but the 3-adapter baseline encodes a missing cell as `("t1", "b", None)`. That silently widens the effective contract: `cells` is typed as floats only and `as_dict()` returns `dict[str, dict[str, float]]`, yet this test now depends on explicit `None` values being accepted and treated as missing.  
**Evidence:** `src/AgentEval/_heatmap/models.py:95-98` types `cells` as `float`; `as_dict()` is typed `dict[str, dict[str, float]]` at `:156-160`; `_color_for_pass_rate` accepts `None` at `:55`; the baseline uses `("t1", "b", None)` at `tests/unit/_heatmap/test_models_html.py:379-381`. Runtime probe: explicit `None` and omitting the tuple produce identical HTML.  
**Fix:** Represent missing cells by omitting tuples in tests/fixtures, or formally widen the public type/docs to `float | None`.

### LOW-1: The story artifact’s stated `<td>` structural count is inconsistent with the shipped renderer
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53`  
**Issue:** The story text says HTML validity should assert `<td> == N*M`, but the implementation renders each task label in its own `<td>`, so the actual count is `N*(1+M)`. The tests correctly assert the larger count, which means the story’s own L-4/AC prose is already stale.  
**Evidence:** The story says `<td>` count == `N*M` at `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md:53` and `:160`; the shipped test asserts `2 tasks × (1 task name + 2 models) = 6` at `tests/unit/_heatmap/test_models_html.py:209`; the renderer builds the task-label cell separately at `src/AgentEval/_heatmap/models.py:283-289`.  
**Fix:** Update the story text to match the actual structure, or switch task labels to row-header `<th>` cells if `N*M` data cells was the intended invariant.

**Total: 2 HIGH + 1 MED + 1 LOW**
