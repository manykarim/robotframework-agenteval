# Story 13.4: Cohort Heatmap HTML Rendering (FR55 `as_html()`)

Status: done

## Story

As a **post-run reviewer** sharing results outside the terminal,
I want `CohortHeatmap.as_html()` + `CohortHeatmap.write_html(path)` rendering the same cohort data as a standalone HTML file with embedded CSS color-coded by Pass@k,
So that I can share rich cohort visualizations with stakeholders who don't read ASCII tables — completing the FR55 trio `as_ascii() + as_dict() + as_html()` originally specified in PRD L1583.

## Pre-create-story drift check (54th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)

10 drifts caught — 6 fresh decisions from spec analysis + 4 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 reviews. **100% real-drift catch rate maintained through 53 prior uses.**

- **D-1 (HIGH — return-type discipline, PRD canonical):** PRD L1583 says `as_html() -> str` (Phase 2). Epic AC L2202 says "`${html}=    ${heatmap.as_html()}`" returning a string. **Decision:** ship `as_html() -> str` per PRD verbatim (returns the FULL standalone HTML document, NOT a fragment). `write_html(path: str | Path) -> Path` is the file-write companion; returns the resolved write path for confirmation. This matches Story 13.1's discipline (PRD wins; methods return what PRD says).

- **D-2 (HIGH — `write_html` not in PRD; epic L2203 introduces it):** PRD L1583 only mentions `as_html()`. Epic AC L2203 adds "file write via `${heatmap.write_html("/tmp/heatmap.html")}` produces a viewable file." **Decision:** ship `write_html(path)` as a thin wrapper around `as_html()` + filesystem write — straightforward; no PRD amendment needed since PRD didn't EXCLUDE write_html, just didn't enumerate it. Same-commit ratification: add a clarification comment in PRD L1583 noting "`write_html(path)` is a thin file-write convenience companion per epic L2203" without changing the FR core.

- **D-3 (HIGH — embedded CSS vs external `<link>`):** Epic AC L2203: "standalone HTML string with embedded CSS rendering the heatmap as a color-coded table." **Decision:** ALL styling embedded in `<style>` inside `<head>`. NO external stylesheet links, NO external image references, NO external font URLs — operators MUST be able to email the file or save to a shared drive and view offline. Per-test verification: `assert "<link" not in html and 'src="http' not in html.lower()`.

- **D-4 (HIGH — Pass@k color gradient mapping, no PRD canonical):** Epic AC L2203: "color-coded table (Pass@k → color gradient)." PRD doesn't pin the specific gradient. **Decision:** ship a 5-stop hue gradient mapping `pass_rate ∈ [0.0, 1.0]` → color:
  - `0.0 ≤ p < 0.2` → `#ef4444` (red — high failure).
  - `0.2 ≤ p < 0.4` → `#f97316` (orange).
  - `0.4 ≤ p < 0.6` → `#eab308` (yellow).
  - `0.6 ≤ p < 0.8` → `#84cc16` (lime).
  - `0.8 ≤ p ≤ 1.0` → `#22c55e` (green — high success).
  - Missing cell (None) → `#e5e7eb` (light gray) with text `"—"` (em-dash matching ASCII fallback).
  Text color: `#0f172a` (slate-900) on light backgrounds (yellow/lime/light-gray); `#ffffff` (white) on dark backgrounds (red/green/orange). Document the gradient in the dataclass docstring + a `_PASS_RATE_PALETTE` `Final[tuple[tuple[float, str, str], ...]]` constant at module level for testability.

- **D-5 (MED — file path canonicalization for `write_html`):** epic AC L2203 example uses `"/tmp/heatmap.html"`. **Decision:** `write_html(path: str | Path) -> Path` accepts `str` OR `Path`, normalizes to `Path(path).resolve()`, creates parent directories (`parent.mkdir(parents=True, exist_ok=True)`), writes via `path.write_text(self.as_html(), encoding="utf-8")`, returns the resolved Path. Rejects empty-string path with `ValueError`. **Per `feedback_listener_hook_api_surface_empirical_check` Story 13.2 L-2 lesson**: ImportError surface N/A here (no extras dependency), but the path-handling edge cases ARE the analog — empty string + missing parent directory + read-only filesystem.

- **D-6 (MED — HTML validity test approach, epic AC L2205 mandate):** Epic L2205: "unit tests verify HTML validity (parseable by html.parser)." **Decision:** use Python's stdlib `html.parser.HTMLParser` (NOT third-party `bs4` or `lxml` — keeps the test surface stdlib-only per project's no-extras-for-tests discipline). Subclass `HTMLParser` + count `<table>` / `<tr>` / `<td>` opens + verify counts match expected row/column structure + verify NO `handle_data` from inside `<script>` (defense-in-depth — no scripts allowed). Per Story 13.1 L-4 + Story 13.3 L-4 lessons: assert SPECIFIC structural counts, not just "parses without error."

- **D-7 (MED — visual regression test scope deferral):** Epic L2205 mandates "visual regression test against a recorded baseline image." Image-based regression testing requires headless browser (Playwright / Selenium) + image diff library (Pillow + structural similarity OR pixel hash). Both are HEAVY new deps. **Decision (in-flight amendment):** defer image-based visual regression to Phase-2.5 carry-over DF-13.4-S1; ship STRUCTURAL regression test instead — compare the generated HTML byte-by-byte against a recorded baseline `.html` fixture at `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`. Operators can manually inspect the recorded baselines via browser. This honors the "regression against baseline" intent (structural equality) without the heavy deps. The dev-record's in-flight amendment explicitly cites this trade-off.

- **D-8 (MED — `_heatmap` underscore-prefix surface vs public-API stability):** The existing `CohortHeatmap` lives at `src/AgentEval/_heatmap/models.py` (underscore-prefixed package). Adding public methods `as_html` + `write_html` to a class that operators consume via the public re-export raises a stability question. **Decision:** the public consumption path is via `HeatmapLibrary.Get Cohort Heatmap` (Story 8b.2 shipped this) which RETURNS a `CohortHeatmap` instance to RF callers. Once the operator holds the instance, calling `.as_html()` on it is the public surface. Document in `docs/contracts/stability-surface.md` that `CohortHeatmap.{as_html, write_html, as_ascii, as_dict}` are `provisional`-labeled per Story 8b.2 precedent — `as_html` joins the existing renderer trio at the same stability tier.

- **D-9 (LOW — empty heatmap HTML rendering):** `as_ascii()` returns `"(empty heatmap)"` placeholder when `not self.tasks or not self.models` (per `_heatmap/models.py:118`). **Decision:** `as_html()` returns a minimal but valid HTML document with `<body><p>(empty heatmap)</p></body>` for the empty case. Symmetric semantics with the ASCII renderer + still passes `html.parser` validation.

- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3, 35th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.4:
  - **DF-13.4-S1 (Phase-2.5):** Image-based visual regression test (headless browser + pixel-diff). D-7 amendment defers from this story.
  - **DF-13.4-S2 (Phase-2.5):** `as_html()` color-blind-safe palette mode (e.g., viridis or magma matplotlib-style sequential colormaps for accessibility per WCAG 2.1 AA).
  - **DF-13.4-S3 (Phase-2.5):** Interactive HTML (embedded JavaScript for cell hover tooltips showing trials/cost/Wilson-CI) — currently embedded CSS only; D-3 explicitly rules out scripts for Phase-2 safety.
  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C92 + C93 + C94 BEFORE invoking `/bmad-code-review`.

## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 reviews

Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; Story 13.3 → 13.4 same-epic transition):

- **L-1 applied (stability-surface UPSTREAM)**: register `CohortHeatmap.as_html` + `CohortHeatmap.write_html` methods in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.4.6. Verify via grep before flipping to done.
- **L-2 applied (no extras-gate split needed for THIS story)**: Story 13.4 introduces NO new extras dependency (HTML rendering uses stdlib `html.parser`). The L-2 split pattern doesn't apply.
- **L-3 applied (Tier classification rationale)**: `as_html()` + `write_html()` are pure-Python instance methods on a frozen dataclass; not RF `@keyword`-decorated. No `@tier` classification applies. Document the rationale in the docstring.
- **L-4 applied (empirical correctness verification)**: HTML validity tests assert SPECIFIC structural counts (`<table>` count == 1; `<tr>` count == N+1 for N tasks + 1 header; `<td>` count == N*M for N tasks × M models). NOT just "html.parser doesn't crash."
- **L-5 applied (docstring precision)**: docstring names exact color palette + the 5-stop boundaries explicitly + cites the `_PASS_RATE_PALETTE` testability constant. Browser-Library-convention anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" appear in the docstring.

## Acceptance Criteria

### AC-13.4.1 — `CohortHeatmap.as_html() -> str` method

`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with `as_html()` method (placed AFTER `as_ascii`):

```python
def as_html(self) -> str:
    """Render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).

    Returns a complete HTML document with `<!DOCTYPE html>` declaration,
    `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
    `<style>`), and `<body>` containing a `<table>` with header row +
    one row per task. Each cell carries inline `style="background-color: <hex>;
    color: <text-hex>;"` for the Pass@k color gradient.

    All styling embedded in `<head><style>...</style>`. NO external
    stylesheet links, NO external image references, NO `<script>`
    elements — operators can email the file or save to shared storage
    and view offline.

    Empty heatmap (no tasks OR no models): returns a minimal valid
    document with `<body><p>(empty heatmap)</p></body>` (symmetric with
    `as_ascii()`'s `"(empty heatmap)"` sentinel).

    Color gradient (Pass@k → background hex; text hex chosen for
    readable contrast per WCAG AA):
        - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
        - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
        - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
        - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)
        - [0.8, 1.0] → green (#22c55e bg / #ffffff text)
        - missing cell (None) → light gray (#e5e7eb bg / #0f172a text) with text "—"

    Returns:
        Standalone HTML5 document as a string.
    """
```

Implementation outline:
1. Empty case: return minimal document.
2. Non-empty: build via string template containing `<!DOCTYPE html>` + `<head>` (with `<style>` containing table border + padding base CSS) + `<body>` (with `<table>`).
3. Header `<tr>` has `<th>Task</th>` + one `<th>{model}</th>` per model (HTML-escaped via `html.escape`).
4. Body: one `<tr>` per task; first `<td>` is the task ID; subsequent `<td>` cells carry inline `style="background-color: <hex>; color: <text-hex>;"` + 2-decimal Pass@k value OR em-dash for missing.
5. All user-provided strings (task IDs, model names) escaped via `html.escape` to prevent injection.

### AC-13.4.2 — `_PASS_RATE_PALETTE` module-level constant

`src/AgentEval/_heatmap/models.py` adds at module top (near `__all__`):

```python
_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
    # (lower_bound_inclusive, background_hex, text_hex)
    (0.0, "#ef4444", "#ffffff"),  # red — high failure
    (0.2, "#f97316", "#ffffff"),  # orange
    (0.4, "#eab308", "#0f172a"),  # yellow
    (0.6, "#84cc16", "#0f172a"),  # lime
    (0.8, "#22c55e", "#ffffff"),  # green — high success
)
_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")
```

Helper `_color_for_pass_rate(rate: float | None) -> tuple[str, str]`:
- `rate is None` → `_MISSING_CELL_STYLE`.
- otherwise: linear walk + return the highest entry whose lower bound `<= rate`. Edge case: `rate == 1.0` → the [0.8, 1.0] entry (green).

The helper is unit-tested independently of the full HTML render — Story 13.1 D-5 + Story 13.3 D-5 precedent (pure helpers tested directly).

### AC-13.4.3 — `CohortHeatmap.write_html(path) -> Path` method

`src/AgentEval/_heatmap/models.py` adds after `as_html`:

```python
def write_html(self, path: str | Path) -> Path:
    """Write `as_html()` output to a file; return the resolved path (Story 13.4 / epic L2203).

    Args:
        path: Filesystem path. Accepts `str` OR `pathlib.Path`. Relative
            paths resolve against `Path.cwd()`. Empty string raises
            `ValueError`. Parent directories created with
            `parents=True, exist_ok=True`.

    Returns:
        The resolved write path (post-`Path.resolve()`).

    Raises:
        ValueError: When `path` is the empty string.
        OSError: When the filesystem write fails (read-only, permission, etc.).
            NOT caught — propagates to the caller.
    """
```

Implementation:
- `if path == ""` → `raise ValueError("write_html requires a non-empty path; got empty string")`.
- `resolved = Path(path).resolve()`.
- `resolved.parent.mkdir(parents=True, exist_ok=True)`.
- `resolved.write_text(self.as_html(), encoding="utf-8")`.
- `return resolved`.

### AC-13.4.4 — Unit tests at `tests/unit/heatmap/test_models_html.py` (≥15 tests)

NEW file. Coverage:

- **`as_html` happy paths (5 tests)**: single-model (1 col × 3 rows); 3-adapter (3 cols × 3 rows); empty heatmap → `"(empty heatmap)"` paragraph; missing cell → em-dash + gray background; rate exactly at boundaries (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) → correct color stops.
- **HTML validity (3 tests)**: `html.parser.HTMLParser` parses without raising; structural counts (1 `<table>`, `(n_tasks + 1)` `<tr>`, `n_tasks * (1 + n_models)` `<td>` for the body — 1 per task label + n_models per row + `(n_models + 1)` `<th>` for the header); NO `<script>` + NO `<link>` + NO `src="http`. Story 13.4 code-review LOW-1 fix 2026-06-01 (Codex LOW-1 + Opus LOW-3): pre-fix prose said `n_tasks * n_models` but the implementation emits 1 task-label `<td>` per row in addition to model-value cells; tests already asserted the larger count, prose was stale.
- **`_color_for_pass_rate` helper (4 tests)**: each color stop boundary maps correctly; None → gray; rate == 1.0 → green (top stop); rate just above each boundary maps to the next stop.
- **`write_html` file ops (4 tests)**: write to tmp_path → file exists + content matches `as_html()`; write to nested non-existent parent → creates dirs; empty-string path → `ValueError`; `Path` input accepted same as `str`; resolved path is `Path.resolve()`-form.
- **HTML escaping (2 tests)**: task ID with `<script>alert(1)</script>` content gets escaped (NOT executed when parsed); model name with `&` + `<` + `>` escaped.
- **Browser-Library docstring anchors (1 test)**: docstring contains "as_html" + "FR55" + "Phase-2" + "embedded CSS" per L-5 lesson.

### AC-13.4.5 — Baseline HTML fixtures for structural regression test

NEW files:
- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded output for a deterministic 2-adapter × 3-task input.
- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded output for a deterministic 3-adapter × 3-task input.

Test `test_html_matches_recorded_baseline_2_adapter` + `test_html_matches_recorded_baseline_3_adapter` build the same input + assert `heatmap.as_html() == baseline_html.read_text()`. Both fixtures committed via the dev (operator can manually inspect them in a browser to verify visual fidelity per the "visual regression" intent). If the baseline drifts (color palette change, structural change), the test fires + dev re-records + commits new baseline. Per D-7: structural regression replaces image-based regression (DF-13.4-S1 deferred).

### AC-13.4.6 — `docs/contracts/stability-surface.md` registry per L-1 lesson

NEW subsection `### Cohort Heatmap HTML Surface (Phase-2 — FR55 `as_html()`)`:

- `CohortHeatmap.as_html() -> str` method — `provisional` label. Same tier as the existing `CohortHeatmap.as_ascii()` and `CohortHeatmap.as_dict()` (Story 8b.2). The HTML structure (`<!DOCTYPE>` + `<html>` + `<head>` with embedded `<style>` + `<body>` with `<table>`) is `provisional`; the per-cell inline `style="background-color: <hex>"` is `stable` (operators may scrape colors from the HTML).
- `CohortHeatmap.write_html(path: str | Path) -> Path` method — `provisional` label. Signature stable; the empty-string `ValueError` + parent-directory `mkdir(parents=True, exist_ok=True)` semantics are `stable`.
- `_PASS_RATE_PALETTE` module-level constant — `provisional` label per the Phase-2.5 DF-13.4-S2 color-blind palette carry-over. The 5-stop boundaries (0.0/0.2/0.4/0.6/0.8) are `stable`; the specific hex values are `provisional`.

### AC-13.4.7 — Phase-1.5 carry-over catalog UPSTREAM (35th consecutive)

`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
- **C92** `DF-13.4-S1` — Phase-2.5: Image-based visual regression test for `as_html()` (headless browser + pixel-diff).
- **C93** `DF-13.4-S2` — Phase-2.5: Color-blind-safe palette mode for `as_html()` (viridis/magma sequential per WCAG 2.1 AA).
- **C94** `DF-13.4-S3` — Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips.

### AC-13.4.8 — PRD amendment per D-2 (write_html clarification)

`_bmad-output/planning-artifacts/prd.md` L1583 amended (same commit) to note: "`write_html(path: str | Path) -> Path` is a thin file-write convenience companion per epic L2203 + Story 13.4 D-2; not a new contract surface." Per `feedback_in_flight_spec_amendment` Story 13.1 + 13.3 precedent.

### AC-13.4.9 — All-gates pass

- `uv run pytest tests/`: ≥15 net new tests; existing 1879+16 still pass. Net delta ≥15 added.
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/AgentEval/_heatmap/ tests/unit/heatmap/ tests/fixtures/heatmap/` clean (the fixtures dir is `.html` files; format check doesn't apply to non-Python).
- `uv run mypy src/` clean (≥107 src files).

### AC-13.4.10 — Sprint-status

`13-4-cohort-heatmap-html-rendering: done` (after review); `last_updated: 2026-06-01`.

## Tasks / Subtasks

- [x] **Task 1: PRD amendment (D-2 + AC-13.4.8)** — `_bmad-output/planning-artifacts/prd.md` L1583 amended with `write_html` clarification.
- [x] **Task 2: `src/AgentEval/_heatmap/models.py` extension** — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method shipped.
- [x] **Task 3: `tests/unit/_heatmap/test_models_html.py` (AC-13.4.4)** — 30 unit tests shipped (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline regression). NOTE: spec said `tests/unit/heatmap/` but existing dir is `tests/unit/_heatmap/` matching the source's underscore prefix — in-flight path amendment.
- [x] **Task 4: `tests/fixtures/heatmap/baseline_*.html` (AC-13.4.5)** — 2 baseline HTML files generated + committed for structural regression (`baseline_2_adapter.html` + `baseline_3_adapter.html`).
- [x] **Task 5: `docs/contracts/stability-surface.md` (AC-13.4.6)** — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection added with 4 entries.
- [x] **Task 6: Phase-1.5 carry-over catalog UPSTREAM (35th consecutive) (AC-13.4.7)** — C92 + C93 + C94 added to both `phase-1-5-carry-overs.md` (91 → 94 total) + `deferred-work.md` UPSTREAM of code review.
- [x] **Task 7: All-gates pass (AC-13.4.9)** — `uv run pytest tests/` reports **1909 passed + 16 skipped + 0 failed** (+30 net vs 1879 + 16 Story 13.3 baseline). ruff/format/mypy/license clean.
- [x] **Task 8: Sprint-status flip (AC-13.4.10)** — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.

## Dev Notes

Building on Story 8b.2's `CohortHeatmap` foundation + Stories 13.1/13.2/13.3 cross-story lessons:

- **Story 8b.2** shipped `CohortHeatmap` frozen dataclass + `as_ascii()` + `as_dict()` + `from_discoverability` classmethod + the `HeatmapLibrary.Get Cohort Heatmap` keyword surface.
- **Story 13.3** added `CohortHeatmap.from_comparison` for multi-column cross-adapter input. Story 13.4's `as_html` MUST render multi-column correctly (the regression test fixtures cover the 2-adapter + 3-adapter cases).

**Key implementation detail — html.escape for injection prevention.** Task IDs + model names are operator-controlled strings. A malicious YAML could declare `task_id: "<script>alert(1)</script>"`. ALL user-provided strings MUST pass through `html.escape(s, quote=False)` before insertion into the HTML — even though the Pass@k values themselves are floats (safe). The unit test `test_html_escapes_script_tags_in_task_ids` verifies this.

**Key implementation detail — pure-function `_color_for_pass_rate` helper.** Per Story 13.1 + 13.3 pattern (pure helpers tested directly). The helper takes `float | None` and returns `tuple[str, str]` (bg_hex, text_hex). Linear scan over `_PASS_RATE_PALETTE` (O(5)); not a bottleneck. Edge case at exactly `1.0` → must hit the `[0.8, 1.0]` green stop (NOT fall through to the implicit None branch).

**Cross-story lesson application:**
- L-1: stability-surface MUST register the new methods (AC-13.4.6).
- L-2: NO extras-gate split needed (no scipy/numpy/opentelemetry dep introduced).
- L-3: not RF `@keyword`-decorated; no `@tier` classification.
- L-4: SPECIFIC structural counts asserted (Story 13.3's "ranking + p-value sign" analog — for HTML, the analog is "table count + tr count + td count").
- L-5: docstring names exact palette + boundaries + helper constant; anchor test enforces grep-discoverability.

### Project Structure Notes

- **NO new sub-library.** Story 13.4 EXTENDS the existing `CohortHeatmap` class at `src/AgentEval/_heatmap/models.py`.
- **NEW test file:** `tests/unit/heatmap/test_models_html.py`.
- **NEW fixture files:** `tests/fixtures/heatmap/baseline_2_adapter.html` + `baseline_3_adapter.html`.
- **EXTENDED files:** `src/AgentEval/_heatmap/models.py`; `docs/contracts/stability-surface.md` (subsection); `docs/phase-1-5-carry-overs.md` (3 carry-overs); `_bmad-output/implementation-artifacts/deferred-work.md` (3 carry-overs); `_bmad-output/planning-artifacts/prd.md` L1583 (per D-2 amendment).

### References

- PRD: `_bmad-output/planning-artifacts/prd.md` L1583 (FR55 cohort heatmap format — `as_html() -> str` Phase 2).
- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1300 (`CohortHeatmap` file home in `metrics/types.py` per architecture — but actual shipping location is `_heatmap/models.py` per Story 8b.2; honor the implementation file home, per `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
- Epic: `_bmad-output/planning-artifacts/epics.md` L2193-2205 (Story 13.4 detailed).
- Prior stories: `_bmad-output/implementation-artifacts/8b-2-cohort-heatmap-ascii-and-dict.md` (Story 8b.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (immediately-prior — multi-column heatmap input source via `CohortHeatmap.from_comparison`).
- Existing source: `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` + `as_ascii` + `as_dict` + `from_discoverability` + `from_comparison` Story 13.3 addition).
- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry).
- Norms: 54th use of `feedback_spec_vs_ratified_doc_precheck`; 35th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.3 → 13.4 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 PRD addition + D-7 visual-regression deferral.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

2 mid-dev catches:
1. **Docstring anchor test**: my initial as_html docstring opened with "Render the heatmap as a standalone HTML document with embedded CSS..." which contains "HTML" and "embedded CSS" but NOT the literal substring "as_html". The L-5 docstring-anchor test fired. Amended docstring opening to `"`as_html` — render the heatmap..."` so the literal name appears.
2. **ruff SIM108 suggestion**: initial `if value is None: cell_text = "—" else: ...` reformulated to ternary `cell_text = "—" if value is None else f"{value:.2f}"` per ruff suggestion.

### Completion Notes List

Story 13.4 dev complete. Phase-2 standalone HTML rendering shipped on `CohortHeatmap`.

- **AC-13.4.1**: `as_html()` returns a full HTML5 document with `<!DOCTYPE>` + `<head>` (embedded `<style>`) + `<body>` containing `<table>`. Empty heatmap → minimal valid document with `(empty heatmap)` paragraph.
- **AC-13.4.2**: `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` + `_color_for_pass_rate` helper all live at module top; 5-stop hue palette with linear-walk dispatch.
- **AC-13.4.3**: `write_html(path)` accepts str|Path; rejects empty string; creates parent dirs; returns resolved Path. UTF-8 encoding.
- **AC-13.4.4**: 30 unit tests at `tests/unit/_heatmap/test_models_html.py`. 10-row parametrize covers color-stop boundaries; structural assertions on `<table>`/`<tr>`/`<th>`/`<td>` counts per L-4 lesson; HTML escaping verified against `<script>alert(1)</script>` injection attempt.
- **AC-13.4.5**: 2 baseline `.html` fixtures committed; structural regression tests pass byte-for-byte.
- **AC-13.4.6**: stability-surface registry NEW `### Cohort Heatmap HTML Surface` subsection with 4 entries.
- **AC-13.4.7**: C92 + C93 + C94 catalogued UPSTREAM (35th consecutive).
- **AC-13.4.8**: PRD L1583 amended with `write_html` clarification + "Story 13.4 ships this" note.
- **AC-13.4.9**: All gates pass — 1909+16 final, ruff/format/mypy/license clean.
- **AC-13.4.10**: sprint-status flipped to `review`.

### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 reviews → Story 13.4)

- **L-1 applied (stability-surface UPSTREAM)**: registered all 4 Story 13.4 surface entries (as_html + write_html + _PASS_RATE_PALETTE + _color_for_pass_rate) before flipping to review.
- **L-2 applied (NO extras-gate split needed)**: stdlib-only (`html` + `pathlib`); no new optional extra.
- **L-3 applied (@tier classification rationale)**: not RF `@keyword`-decorated; methods on a frozen dataclass; no `@tier` applies.
- **L-4 applied (SPECIFIC structural counts)**: HTML validity tests assert `<table>` count == 1, `<tr>` count == (n_tasks + 1), `<th>` count == (n_models + 1), `<td>` count == n_tasks * (1 + n_models). Defense-in-depth `_StructuralHTMLParser` confirms NO `<script>` elements.
- **L-5 applied (docstring precision)**: `as_html` docstring opens with literal "`as_html` — render..."; anchor test asserts "as_html" + "FR55" + "Phase-2" + "embedded CSS" all appear (caught the initial drift during dev).

### In-flight spec amendments

1. **Task 3 test path**: spec said `tests/unit/heatmap/test_models_html.py` but the existing dir matching the source's underscore-prefix convention is `tests/unit/_heatmap/`. Amended path to `tests/unit/_heatmap/test_models_html.py` for consistency.

2. **D-7 visual regression deferral**: per the spec, image-based regression deferred to DF-13.4-S1 / C92; structural byte-equality regression ships instead. Two baseline HTML files capture deterministic 2-adapter + 3-adapter snapshots that operators can manually inspect in a browser.

### File List

**New files:**
- `tests/unit/_heatmap/test_models_html.py` — 30 unit tests covering helper + as_html + write_html + baselines.
- `tests/fixtures/heatmap/baseline_2_adapter.html` — recorded baseline for 2-adapter × 3-task structural regression.
- `tests/fixtures/heatmap/baseline_3_adapter.html` — recorded baseline for 3-adapter × 3-task structural regression.

### 3-Tier Cross-LLM Code Review (2026-06-01)

3-tier review applied 3 HIGH + 4 MED + 5 LOW deduped findings.

**HIGH-A (Codex HIGH-1)**: Epic L2205 mandated image-based visual regression; story shipped structural-baseline. Spec drift not ratified. → FIXED: epics.md L2205 amended with the structural-baseline ratification + DF-13.4-S1 / C92 deferral note.

**HIGH-B (Codex HIGH-2)**: PRD FR55 wording said "model rows × task-cluster columns" but implementation orients tasks-as-rows since Story 8b.2. Pre-existing drift Story 13.4 propagated. → FIXED: PRD L1583 amended to flip orientation per fix-the-losing-source-NOW + retire the stale "✓/✗/•" terminal glyph claim (shipped surface emits 2-decimal floats).

**HIGH-C (Opus HIGH-1)**: Carry-over effort-breakdown line summed to 86 (not 94); pre-existing Story 13.3 drift (83≠91) propagated by Story 13.4's only-M-bucket-increment. → FIXED: removed the misleading breakdown line; replaced with the canonical `grep -c "^| \\*\\*C"` machine-derivable command per `feedback_honest_framing`.

**MED-A (3-way: Codex MED-1 + Opus LOW-2 + Sonnet MED-1)**: `_build_3_adapter_baseline()` passed `None` as a `float` cell, violating the public `cells: tuple[tuple[str, str, float], ...]` type contract. → FIXED: baseline now represents missing cells via OMISSION (matches `as_dict()` type contract + existing `as_ascii()` precedent). HTML byte-identical pre/post since the renderer treats omitted == None identically.

**MED-B (2-way: Opus MED-1 + Sonnet LOW-1)**: `write_html(Path(""))` fell through the str-only empty-path guard + later raised `IsADirectoryError`. → FIXED: extended guard to detect Path objects with empty `name`; new test `test_write_html_empty_path_object_raises_value_error`.

**MED-C (Sonnet MED-2)**: Asymmetric empty heatmap cases (tasks=() but models=("m0",), or vice versa) not tested. → FIXED: 2 new tests `test_as_html_tasks_empty_but_models_non_empty_returns_sentinel` + `test_as_html_models_empty_but_tasks_non_empty_returns_sentinel`.

**LOW-A (Codex LOW-1 + Opus LOW-3)**: Story prose claimed `<td>` count == `N*M` but implementation emits `N*(1+M)` (each task label is a `<td>`). Tests already asserted the correct count. → FIXED: story prose updated.

**LOW-B (Opus LOW-1)**: missing-cell em-dash sentinel asymmetry between `as_ascii` (" — " with surrounding spaces) and `as_html` ("—" alone). Intentional — HTML cells have padding so don't need spacing — but undocumented. → ACCEPTED: documented in the dev-record as intentional; no code change.

**LOW-C (Sonnet LOW-2)**: stability-surface entry for `_color_for_pass_rate` underscore-prefixed helper described as "consumable by Phase-2.5 plugins" — anti-pattern (private name suggests internal). → ACCEPTED: defer to Phase-2.5 when the plugin API materializes; this is documentation polish only.

**Modified files:**
- `src/AgentEval/_heatmap/models.py` — `_PASS_RATE_PALETTE` + `_MISSING_CELL_STYLE` constants + `_color_for_pass_rate` helper + `as_html` method + `write_html` method + extended empty-path validator covering `Path("")` (Opus MED-1 + Sonnet LOW-1).
- `_bmad-output/planning-artifacts/prd.md` — L1583 FR55 amended with `as_html()` Story 13.4 ship + `write_html(path)` companion note (per D-2 + AC-13.4.8).
- `docs/contracts/stability-surface.md` — `### Cohort Heatmap HTML Surface (Phase-2 — FR55 as_html())` subsection (4 entries).
- `docs/phase-1-5-carry-overs.md` — C92 + C93 + C94 entries; total 91 → 94.
- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.4 dev" section with 3 entries.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-4-cohort-heatmap-html-rendering: review`; `last_updated: 2026-06-01`.
