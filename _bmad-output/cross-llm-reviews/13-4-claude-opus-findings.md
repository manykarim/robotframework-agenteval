I've verified the implementation, run the tests/gates, and probed the edge cases. Here are my findings.

---

### [HIGH]-1: Carry-over effort-breakdown count is numerically wrong on a line Story 13.4 edited
**File:** `docs/phase-1-5-carry-overs.md:119`
**Issue:** Story 13.4 edited the totals line to read `**Total: 94 catalog items** ... Effort breakdown: 15 XS, 26 S, 36 M, 8 L, 1 XL`. That breakdown sums to **86, not 94**, and every bucket except XL is wrong. The dev incremented only the M bucket (+3 → 36) without re-deriving the others, propagating a drift that already existed at 13.3 (83≠91). Re-deriving a machine-verifiable count you re-assert on an edited line is exactly the `feedback_citation_drift_first_class` / honest-framing obligation; prior 13.1–13.3 reviews logged this class as HIGH.
**Evidence:** Actual column counts (`awk -F'|' '{print $6}' | sort | uniq -c`): **18 XS, 31 S, 37 M, 7 L, 1 XL = 94**. Claimed: 15 XS / 26 S / 36 M / 8 L / 1 XL = 86. Every claimed bucket diverges from reality (XS 15≠18, S 26≠31, M 36≠37, L 8≠7).
**Fix:** Replace with `18 XS, 31 S, 37 M, 7 L, 1 XL` (or re-derive at edit time). Going forward, regenerate the breakdown from the table rather than hand-incrementing one bucket.

---

### [MED]-1: `write_html` empty-path guard only catches `str ""`, not `Path("")`
**File:** `src/AgentEval/_heatmap/models.py:335`
**Issue:** The signature accepts `str | Path` and the docstring/D-5 promise "Empty string raises `ValueError`." But the guard is `isinstance(path, str) and path == ""`. A caller passing `Path("")` — which Python normalizes to `PosixPath('.')` — bypasses the guard, resolves to cwd, and fails with a cryptic `IsADirectoryError` instead of the documented `ValueError`. Since `Path` is a first-class accepted input (and `write_html(Path(user_input))` with empty input is plausible), the contract is only half-delivered.
**Evidence:** Probe output: `Path('') == PosixPath('.')` → `write_html(Path(""))` raised `IsADirectoryError [Errno 21] Is a directory: '/home/many/workspace/robotframework-agenteval'`, not `ValueError`.
**Fix:** Normalize first, then guard the empty/dot case: `if str(path) in ("", "."): raise ValueError(...)`, or check `not os.fspath(path)`. The existing test `test_write_html_empty_string_path_raises_value_error` only exercises the `str` branch — add a `Path("")` case.

---

### [MED]-2: Epic-mandated image-based visual-regression AC silently downgraded via self-amendment
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md` (D-7) / epics.md:2205
**Issue:** Epic L2205 explicitly mandates "visual regression test against a recorded baseline **image**." The dev shipped byte-equality structural regression instead and deferred the mandated image test to C92/DF-13.4-S1 as an "in-flight amendment." Deferring an explicit epic *acceptance criterion* (not a dev-discretion detail) to a carry-over is the same epic-acceptance-drift class flagged MED in Story 13.3 (cost_per_call). The trade-off (heavy headless-browser deps) is reasonable, but downgrading a mandated AC is a scope decision, not a self-ratifiable in-flight amendment.
**Evidence:** epics.md:2205 "visual regression test against a recorded baseline image"; D-7 replaces it with structural byte-equality + manual inspection.
**Fix:** Acceptable to defer, but surface it as an explicit scope decision (the deferral is the right call — image-diff deps are heavy). The catalog entry C92 is good; just don't frame an epic-AC downgrade as a routine path amendment.

---

### [LOW]-1: Missing-cell em-dash sentinel differs from `as_ascii`, despite docstring claiming a match
**File:** `src/AgentEval/_heatmap/models.py:287`
**Issue:** `as_ascii` renders missing cells as `" — "` (em-dash with surrounding spaces, line 178); `as_html` uses `"—"` (no spaces). The `as_html` docstring (line 244) states the em-dash is "matching `as_ascii()` fallback," which is not literally true. Harmless visually but the "symmetric" claim is inaccurate.
**Fix:** Either align the sentinels or drop the "matching" wording.

---

### [LOW]-2: `baseline_3_adapter` fixture encodes a missing cell as an explicit `None` in the float-typed `cells` tuple
**File:** `tests/unit/_heatmap/test_models_html.py:330` (`_build_3_adapter_baseline`)
**Issue:** The missing cell is represented as `("t1", "b", None)` inside `cells: tuple[tuple[str,str,float],...]`. Production builders (`from_discoverability`/`from_comparison`) never emit a None value — real missing cells arise from *absent keys* (dropped tasks). So the 3-adapter baseline exercises a representation that can't occur via the public API (mypy doesn't catch it since tests are lint-only). The genuine missing-cell path is covered separately by `test_as_html_missing_cell_renders_emdash_and_gray`, so coverage is intact, but the baseline's input is unrepresentative.
**Fix:** Build the missing cell by omitting the `(t1,b)` triple rather than inserting `None`, matching how production produces it.

---

### [LOW]-3: Story doc's test-count breakdown sums to 31, actual is 30
**File:** `_bmad-output/implementation-artifacts/13-4-cohort-heatmap-html-rendering.md` (Task 3 / Completion Notes)
**Issue:** "30 unit tests (10 parametrized color-stop + 4 helper + 5 happy paths + 3 HTML validity + 2 escaping + 4 write_html + 1 docstring + 2 baseline)" = 31. The "4 helper" double-counts the parametrized function already counted in the "10." Real pytest count is 30 (verified: `30 passed`), and the headline 1879→1909 (+30) is correct — only the parenthetical is off by one.
**Fix:** "10 parametrized color-stop cases + 3 other helper + 5 + 3 + 2 + 4 + 1 + 2 = 30."

---

**Verification performed:** `30 passed` on the new file; `ruff check` + `mypy src/AgentEval/_heatmap/models.py` clean; boundary mapping (0.2/0.6/1.0/1.5/0.1999) confirmed correct including `rate==1.0`→green (no gray fallthrough); asymmetric-empty (`tasks=() , models=("m0",)`) correctly returns the empty sentinel; `.2f` formatting is locale-independent so baselines are reproducible; no external URLs / `<script>` / `<link>` in output; `html.escape(quote=False)` is safe here because user strings land only in element text content, never attributes. The shipped `src` rendering logic itself is correct — no correctness HIGH in the code.

**Total: 1 HIGH + 2 MED + 3 LOW**
