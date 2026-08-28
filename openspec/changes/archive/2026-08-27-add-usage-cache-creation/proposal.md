## Why

`Usage` (`src/AgentEval/_core/types.py`) has no field for prompt-cache
**creation/write** tokens — only `input_tokens`, `output_tokens`, and a single
`cached_input_tokens` (cache-*read* tokens, L42). The `claude-code` adapter's
`_usage_from()` (`src/AgentEval/_core/cli_adapters/claude_code.py:225-232`) reads
`cache_read_input_tokens` but **never reads `cache_creation_input_tokens`** — it is
silently dropped, even though the module docstring advertises "the settled usage (with
a cache breakdown)" and the test fixture (`claude_code_stream.jsonl:7`) already carries
`cache_creation_input_tokens: 300`.

This is a missing-**attribution** bug, not a cost-correctness bug (native
`total_cost_usd` from the CLI is used directly, L290-293). But for anyone measuring
whether a mechanism — a routing switch, a prompt-rewrite/compression step, a RAG
injection — *destroys* the prompt cache, the **cost of re-creating** the cache is the
entire signal, and it is exactly the half of the cache ledger that is thrown away.
`cached_input_tokens` shows only the savings side; there is currently no way to see how
much a given run *spent* recreating the cache.

Claude Code further splits cache-creation into TTL buckets
(`cache_creation.ephemeral_1h_input_tokens` vs `ephemeral_5m_input_tokens`), which
Anthropic prices differently (1h writes at 2×, 5m at 1.25× the base input rate) — so a
single flattened creation count cannot be priced correctly. Both the flat count and the
TTL split are captured here so a consumer can attribute and price cache-write spend.

## What Changes

- **Add cache-creation fields to `Usage`.** `cache_creation_input_tokens: int = 0`,
  plus the TTL split `cache_creation_1h_input_tokens: int = 0` and
  `cache_creation_5m_input_tokens: int = 0` — all flat, defaulted, so every existing
  `Usage(...)` call site stays valid and the flat `asdict`/export shape is preserved
  (no nested struct, no `int | None`). Extend `__post_init__`'s non-negativity check to
  the new names. Document the fields: the flat count is authoritative,
  `total == 1h + 5m` per Anthropic, and `0` on an adapter without a native count means
  "not reported," not "no cache writes."
- **Populate them in the claude-code adapter, and assert the identity.** `_usage_from()`
  reads `cache_creation_input_tokens` (flat) and the
  `cache_creation.ephemeral_1h/5m_input_tokens` sub-dict, coerced through the existing
  `_int()` (missing → 0). When all three are reported non-zero it asserts
  `total == 1h + 5m` (skipped when the split is absent). This is the only adapter whose
  payload carries an Anthropic-shaped cache-creation count; others keep the `0` default,
  exactly as `cached_input_tokens` already does.
- **Surface them in the metrics readers.** `Metric.Get Token Usage`
  (`MetricsLibrary/__init__.py:72`, dict L81-83) and the record `to_dict` export
  (`_record.py:126-130`) include the new field(s), so the data is readable and
  exportable rather than a dead field. (The reader emits short keys — `cached` — and
  the export long keys — `cached_input_tokens`; each gains the new counts in its own
  convention.)

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `agent-run-metrics`: ADD a requirement that `Usage` carries prompt-cache-creation
  (write) token counts, including the 1h/5m TTL split with the documented
  `total == 1h + 5m` identity; that the claude-code adapter (and Anthropic-shaped
  payloads) populate them while others default to 0 (meaning "not reported"); and that
  the Tier-1 token-usage reader and the JSON export surface them.

## Impact

- **Code:** `src/AgentEval/_core/types.py` (three new `Usage` fields + `__post_init__`);
  `src/AgentEval/_core/cli_adapters/claude_code.py::_usage_from` (read flat + TTL split);
  `src/MetricsLibrary/__init__.py::get_token_usage` and `src/MetricsLibrary/_record.py`
  `to_dict` usage block (surface the new keys).
- **Tests:** `tests/surfaces/cli_adapters/test_claude_code_adapter.py:113-116` — extend
  to assert `cache_creation_input_tokens == 300` (and the TTL split) from the fixture;
  `tests/surfaces/metrics/test_metrics_library.py` — **two** usage assertions use
  **exact dict equality** (the reader at L81, the export at L260), so both must be
  updated in the same commit to include the new keys.
- **Docs:** `CHANGELOG.md` (additive fields + reader/export keys, an allowed
  `provisional` minor **shape change**, with a migration note for strict dict/JSON
  consumers); `docs/recipes/11-e2e-agent-metrics-cli-adapters.md` (the reader example
  ~L103-105 **and** the exact exported-JSON block ~L129-151 gain the new keys);
  regenerated libdocs + the README metrics summary if it enumerates usage keys. The
  new-field docstrings note the TTL split exists because 1h and 5m writes price
  differently, so a consumer prices per bucket.
- **Out of scope:** a `Usage.__add__` (none exists today — adapters sum multi-turn
  usage with local integer accumulators, not via `Usage`); populating opencode's
  deliberately-excluded `cache.write` (`opencode.py:283-284`, a prior "distinct
  write-cost" decision) — the requirement is scoped to Anthropic/claude payloads and
  this is a noted fast-follow, not reworked here; and reconciling the pre-existing
  `docs/contracts/metrics-contract.md` drift (it declares the `Metric.Get *` getters
  removed by the 2026-07 four-surface refocus while the code still ships them — flagged
  for the maintainer).

**Coordination note (four-surface refocus):** the target files exist on `main`, so this
change is valid there; `Usage` lives on the `_core/types.py` spine that survives the
refocus, so the field addition transfers regardless. If the unpushed
`refactor/simplify-and-cleanup` branch lands first, only the two surfacing edits
(`MetricsLibrary`, `claude_code.py`) re-home to their new locations.
