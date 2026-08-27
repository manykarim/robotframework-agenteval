## Context

Confirmed against source and Anthropic's docs:

- `types.py:36-48` — `@dataclass(frozen=True) class Usage` has exactly `input_tokens`
  (L40), `output_tokens` (L41), `cached_input_tokens: int = 0` (L42); `__post_init__`
  (L44-48) validates non-negativity over those three. **No `__add__`, no aggregation,
  no `to_dict`/`asdict`.**
- `claude_code.py:225-232` — `_usage_from()` reads `cache_read_input_tokens` but never
  `cache_creation_input_tokens` nor the `cache_creation` sub-dict; `_int()` (L217-222)
  coerces missing/null/malformed → 0. Native cost is `total_cost_usd` (L290-293).
  Fixture `claude_code_stream.jsonl:7` carries flat `cache_creation_input_tokens: 300`
  but **no** `cache_creation` TTL sub-dict.
- Surfacing sites use **different** key conventions: `get_token_usage`
  (`MetricsLibrary/__init__.py:72`, dict L81-83) returns **short** keys
  `{input, output, cached}`; `_record.to_dict` (`_record.py:116`, usage block L126-130)
  uses **long** keys `{input_tokens, output_tokens, cached_input_tokens}`.
- Two tests assert usage dicts by **exact equality** (both break on any added key):
  `test_metrics_library.py:81` on the reader output, `:260` on the export.
- `Usage`/`MetricsLibrary` are `provisional` — field additions are minor bumps
  (`docs/contracts/stability-surface.md`).
- Anthropic documents that `cache_creation_input_tokens` equals the sum of its 1h and
  5m ephemeral members, priced 2× (1h) and 1.25× (5m) of the base input rate.
- Other adapters: `opencode.py:283-284` reads `tokens.cache` and **explicitly excludes**
  `cache.write` by comment; `codex`/`gemini`/`copilot`/`kilo` carry no write count.

**Four-surface-refocus note (F-USAGE-3):** the target files exist on `main` (so this
change is valid there), but `docs/contracts/metrics-contract.md` on main already
declares the `Metric.Get *` getters **removed** by the 2026-07 refocus, and an unpushed
`refactor/simplify-and-cleanup` branch relocates `MetricsLibrary`/`cli_adapters`. See
Migration Plan.

## Goals / Non-Goals

**Goals:**

- `Usage` can represent cache-creation (write) tokens, including the 1h/5m TTL split.
- The claude-code adapter populates them; the identity `total == 1h + 5m` is documented
  and (where all reported) asserted.
- The token-usage reader and JSON export surface them.

**Non-Goals:**

- Cost re-computation — native `cost_usd` is already correct; this is attribution.
- A `Usage.__add__` (none exists; noted for the future).
- Changing opencode's cache accounting (its `cache.write` exclusion is a prior decision).

## Decisions

### D1 — Three flat fields + the documented ledger identity (chosen)

Add three flat, defaulted fields to `Usage` and extend the `__post_init__`
non-negativity tuple:

```python
cache_creation_input_tokens: int = 0        # total cache-write tokens
cache_creation_1h_input_tokens: int = 0     # ephemeral 1h bucket (prices at 2x)
cache_creation_5m_input_tokens: int = 0     # ephemeral 5m bucket (prices at 1.25x)
```

**Why flat, not a nested struct or `int | None`.** A nested `CacheCreation` dataclass or
`int | None` presence-typing would break the flat `asdict`/export shape, both
exact-equality tests, JSON cleanliness, and the simplicity of every `Usage(...)` call
site — for a presence signal rarely needed here (the flat total is authoritative and is
always carried by the payload even when the TTL split is absent, and native `cost_usd`
is already correct). Three flat ints keep the shape simple and priceable.

**The ledger identity is documented and defensively asserted.** Anthropic defines
`cache_creation_input_tokens == 1h + 5m`. The field docstrings state this, plus that a
`0` on an adapter without a native count means "not reported," not "no cache writes."
When all three are reported non-zero, `_usage_from` (or `__post_init__`) asserts
`total == 1h + 5m` as a defensive check; when the split is absent (the current fixture),
the record is `(total=300, 1h=0, 5m=0)` and the identity check is skipped (the flat total
stands alone). This honors the flat-fields choice while giving the honest accounting
caveat.

### D2 — Populate claude-code; the SHALL is scoped to Anthropic/claude payloads

`_usage_from()` reads `cache_creation_input_tokens` (flat) and the `cache_creation`
sub-dict's `ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`, each via `_int()`
(missing → 0). The spec requirement is **scoped to Anthropic/claude-code-shaped
payloads**, not "any adapter that reports cache creation" — because opencode's
`cache.write` is a distinct write-cost concept it deliberately excludes
(`opencode.py:283-284`), and reversing that is a separate judgment about opencode's
accounting, out of scope here. Adapters without a native Anthropic-shaped count keep the
`0` default (documented as "not reported"). Populating opencode's `cache.write` is a
noted fast-follow, not part of this change.

### D3 — Surface in the reader and export, each in its own key convention

`get_token_usage` and `_record.to_dict` both gain the new fields, but each keeps its
existing key convention (they differ — see Context): the reader adds short keys
(`cache_creation`, `cache_creation_1h`, `cache_creation_5m`, matching its `cached`), the
export adds long keys (`cache_creation_input_tokens`, `cache_creation_1h_input_tokens`,
`cache_creation_5m_input_tokens`, matching its `cached_input_tokens`). **Both**
exact-equality tests are updated in the same commit — the reader at
`test_metrics_library.py:81` and the export at `:260`. Unifying the reader/export key
names is a separate, larger cleanup out of scope here.

## Risks / Trade-offs

- **Both exact-equality tests break until updated** (reader `test_metrics_library.py:81`
  + export `:260`). Mitigation: update both in the same commit.
- **Emitted JSON + reader dict shape change** (additive keys). Under `provisional` this
  is an allowed minor **shape change**, not behaviorally invisible: a strict dict/JSON
  consumer doing exact-equality breaks on the added keys. Document the migration for
  strict consumers in `CHANGELOG.md`, and update the metrics recipe's reader example +
  its exact exported-JSON example (`docs/recipes/11-e2e-agent-metrics-cli-adapters.md`),
  the generated libdocs, and the README summary in the same change.
- **Cross-adapter asymmetry:** only claude-code populates the fields. Mitigation: field
  docstring states `0 == not reported`; SHALL scoped to Anthropic/claude payloads (D2).
- **Ledger honesty:** flat total alone is priceable only with the split. Mitigation: the
  split is included and the `total == 1h + 5m` identity is documented + asserted (D1).
- **A future `Usage.__add__`** must sum the new fields too. Noted; out of scope here.

## Migration Plan

Additive, non-breaking at the type level (three new `Usage` fields with `0` defaults
keep every call site valid); the reader/export gain keys (an allowed provisional
shape change). **Both** in-repo exact-equality tests (reader L81 + export L260) update in
the same commit, plus the metrics recipe, libdocs, and README.

**Target `main` now, with a coordination note.** `main` is the active line (these issues
+ recent merges target it); the four-surface refactor is unpushed and undated. `Usage`
lives on the `_core/types.py` spine that survives the refocus, so the field addition
transfers regardless; only the two surfacing edits (`MetricsLibrary`, `claude_code.py`)
would re-home if the refactor lands first. Separately, `docs/contracts/metrics-contract.md`
on main already declares the `Metric.Get *` getters removed while the code still ships
them — a pre-existing doc/code drift the maintainer should reconcile (out of scope here,
flagged). Rollback is a revert.

## Open Questions

- **OQ1:** Field naming — `cache_creation_input_tokens` (Anthropic's key, chosen) vs
  `cached_write_input_tokens` (symmetric with the read-side `cached_input_tokens`).
  Chosen to match the source payload key; note the read/write name asymmetry.
- **OQ2:** Populate opencode's excluded `cache.write` in a fast-follow, or leave it
  excluded per its prior decision? Out of scope here; the SHALL is scoped so this change
  does not obligate it.
