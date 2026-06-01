I have read all the key files. Here is the adversarial review.

---

## Story 13.4 — Cross-LLM Adversarial Review (Claude Sonnet)

Re-derived all cited facts from source. Examined: `src/AgentEval/_heatmap/models.py`, `tests/unit/_heatmap/test_models_html.py`, both baseline fixtures, `docs/contracts/stability-surface.md`, story spec, PRD FR55 diff.

---

### [MED]-1: `_build_3_adapter_baseline()` passes `None` as a `float` cell, violating the `cells` type contract and poisoning `as_dict()`'s return type

**File:** `tests/unit/_heatmap/test_models_html.py:380`

**Issue:** `CohortHeatmap.cells` is annotated `tuple[tuple[str, str, float], ...]` — the third element of each inner tuple must be `float`. Line 380 passes `("t1", "b", None)`. When `as_dict()` iterates over cells and assigns `out["t1"]["b"] = None`, the returned `dict[str, dict[str, float]]` (line 156 in models.py) silently contains a `None` value. Any downstream caller using `as_dict()` for arithmetic on `t1` values (e.g. `sum(data["t1"].values())`) would get `TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`. The test also commits this usage pattern to the regression baseline, implicitly documenting it as valid.

**Evidence:**
```python
# models.py:98
cells: tuple[tuple[str, str, float], ...]

# models.py:156
def as_dict(self) -> dict[str, dict[str, float]]:
    for task, model, value in self.cells:
        out.setdefault(task, {})[model] = value   # stores None silently

# test_models_html.py:380
("t1", "b", None),  # missing cell on purpose
```

The correct representation of a missing cell is **tuple absence**. `data.get("t1", {}).get("b")` returns `None` in both the absent-tuple case (key not found) and the explicit-`None` case (value is `None`) — identical rendering in `as_html()`. The baseline fixture does not need to change; only the test input does.

**Fix:** Remove `("t1", "b", None)` from `_build_3_adapter_baseline()`. The `t1, b` cell will be genuinely absent from the cells tuple, producing byte-identical HTML output (gray `—` cell), and the type contract is satisfied.

---

### [MED]-2: Asymmetric empty heatmap cases not tested (probe 9 gap)

**File:** `tests/unit/_heatmap/test_models_html.py` (test suite gap)

**Issue:** `test_as_html_empty_heatmap_returns_empty_sentinel` only exercises the symmetric case `tasks=(), models=()`. The `as_html()` guard at models.py:259 is `if not self.tasks or not self.models` — an OR, meaning `tasks=("t0",), models=()` and `tasks=(), models=("m0",)` are both valid empty-heatmap inputs that hit the empty-document path. Neither is tested. The guard is correct, but the test suite doesn't verify it behaves identically to the symmetric case for these asymmetric inputs. Probe 9 calls this exact gap out by name.

**Evidence:** Test at line 87 only constructs `CohortHeatmap(tasks=(), models=(), cells=())`. No test covers `models=()` with non-empty tasks, or `tasks=()` with non-empty models.

**Fix:** Add two parametrized variants to `test_as_html_empty_heatmap_returns_empty_sentinel`:
```python
@pytest.mark.parametrize("h", [
    CohortHeatmap(tasks=(), models=(), cells=()),
    CohortHeatmap(tasks=("t0",), models=(), cells=()),
    CohortHeatmap(tasks=(), models=("m0",), cells=()),
])
def test_as_html_empty_heatmap_variants(h): ...
```

---

### [LOW]-1: `write_html(Path(""))` guard gap — gets `IsADirectoryError` not `ValueError`

**File:** `src/AgentEval/_heatmap/models.py:335`

**Issue:** The guard `isinstance(path, str) and path == ""` catches `str("")` but not `Path("")`. `Path("") == ""` evaluates to `False` in Python (pathlib's `__eq__` does not compare with raw strings), so `Path("")` bypasses the guard. `Path("").resolve()` returns the current working directory; `cwd.write_text(...)` raises `IsADirectoryError` (an `OSError` subclass), not `ValueError`. The docstring says *"ValueError: When path is the empty string"* and the spec says `if path == ""` — both imply `str` input, so this is edge-case rather than spec drift. But it creates a surprising diagnostic gap for callers who construct `Path("")` by mistake.

**Evidence:** `>>> Path("").resolve()` → `/path/to/cwd`; `Path.write_text` on a directory → `IsADirectoryError`.

**Fix:** Broaden the guard to catch both forms:
```python
if (isinstance(path, str) and path == "") or (isinstance(path, Path) and str(path) == ""):
    raise ValueError(...)
```
Or equivalently: `if not path:` works for both `str("")` and `Path("")` since `bool(Path(""))` is `False`.

---

### [LOW]-2: Stability surface documents underscore-prefixed private helper as "consumable by Phase-2.5 plugins" — anti-pattern

**File:** `docs/contracts/stability-surface.md:133`

**Issue:** The new `### Cohort Heatmap HTML Surface` section registers `AgentEval._heatmap.models._color_for_pass_rate` with a `provisional` stability label and notes it is "consumable by Phase-2.5 plugins (e.g., color-blind palette overrides)." Documenting a double-private symbol (module `_heatmap` + name `_color_for_pass_rate`) as a stable plugin extension point is an anti-pattern: stability contracts on private symbols conflict with Python's convention that underscore-prefixed names are internal. If Phase-2.5 plugins genuinely need to call this function, it should be promoted to a public name at that point (e.g., `color_for_pass_rate` exported from the public surface). Committing to stability on a private name now constrains the refactoring space unnecessarily.

**Fix:** Remove `_color_for_pass_rate` from the stability surface registry. Add a NOTE in the module comment that Phase-2.5 plugins wishing to override the palette should monkey-patch `_PASS_RATE_PALETTE` or wait for the Phase-2.5 `palette` kwarg (DF-13.4-S2 / C93). The 5-stop boundaries documented as `stable` are already captured via `_PASS_RATE_PALETTE`.

---

**Behavioral probes exhausted without additional findings:**
- Probe 1 (HTML validity): `_StructuralHTMLParser` counts are correct; CSS `th,` selectors do not produce false `<th>` tag counts since `html.parser` doesn't parse the `<style>` block for tags.
- Probe 2 (color boundaries): linear walk correctly returns the HIGHEST matching entry; `rate == 1.0` hits the green stop; `rate < 0.0` clamps to red via initialization.
- Probe 3 (XSS): `html.escape(quote=False)` is safe for TEXT CONTENT (not attribute values); model names and task IDs never appear in attribute position; palette hex values are hardcoded constants.
- Probe 5 (locale): `f"{value:.2f}"` uses the C mini-language, not `locale.format_string`; baselines are stable across locales and Python 3.7+.
- Probe 6 (CSS embedding): no `url(http`, `@import`, `<link`, or `src=http` in generated HTML; verified by test `test_as_html_has_no_external_resources`.
- Probe 8 (baselines committed): `baseline_2_adapter.html` and `baseline_3_adapter.html` are in the diff; fixture path resolution at test line 391/400 is correct relative to `tests/unit/_heatmap/` → `tests/fixtures/heatmap/`.
- Probe 10 (PRD amendment): FR55 line correctly amended with `write_html` companion note per AC-13.4.8.

---

**Total: 0 HIGH + 2 MED + 2 LOW**
