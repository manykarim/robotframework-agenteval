## 1. Extend the Usage record

- [ ] 1.1 In `src/AgentEval/_core/types.py`, add to `Usage` (after `cached_input_tokens`, L42): `cache_creation_input_tokens: int = 0`, `cache_creation_1h_input_tokens: int = 0`, `cache_creation_5m_input_tokens: int = 0`.
- [ ] 1.2 Add the three new names to the `__post_init__` non-negativity check (L44-48).
- [ ] 1.3 Docstring the new fields: the flat count is total cache-write tokens; the 1h/5m split exists because those buckets price differently (2× vs 1.25×); `total == 1h + 5m` per Anthropic; `0` on an adapter without a native count means "not reported," not "no cache writes."

## 2. Populate in the claude-code adapter + assert the identity

- [ ] 2.1 In `src/AgentEval/_core/cli_adapters/claude_code.py::_usage_from` (L225-232), read `cache_creation_input_tokens` (flat) and the `cache_creation` sub-dict's `ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`, each through `_int()` (missing → 0), and pass them to `Usage(...)`.
- [ ] 2.2 When all three creation counts are reported non-zero, assert `cache_creation_input_tokens == cache_creation_1h_input_tokens + cache_creation_5m_input_tokens` (defensive; skip the check when the split is absent). Place it in `_usage_from` or `Usage.__post_init__` — decide during apply.
- [ ] 2.3 Confirm `_pick_usage` still prefers the settled result event (L235-245) so the creation counts come from the terminal event, consistent with `cached_input_tokens`.

## 3. Surface in the metrics readers (each in its own key convention)

- [ ] 3.1 In `src/MetricsLibrary/__init__.py::get_token_usage` (def L72; dict L81-83), add three **short** keys matching its existing convention (`cached` → add `cache_creation`, `cache_creation_1h`, `cache_creation_5m`).
- [ ] 3.2 In `src/MetricsLibrary/_record.py` `to_dict` usage block (L126-130), add three **long** keys matching its existing convention (`cached_input_tokens` → add `cache_creation_input_tokens`, `cache_creation_1h_input_tokens`, `cache_creation_5m_input_tokens`). NB: the reader and export use different key conventions today; keep each internally consistent rather than unifying them here.

## 4. Tests

- [ ] 4.1 Extend `tests/surfaces/cli_adapters/test_claude_code_adapter.py:113-116` to assert `cache_creation_input_tokens == 300` from the fixture; add a fixture (or a second fixture case) that carries the `cache_creation.ephemeral_1h/5m_input_tokens` sub-dict and assert the split + the `total == 1h + 5m` identity.
- [ ] 4.2 Update **both** exact-equality usage assertions in `tests/surfaces/metrics/test_metrics_library.py`: the reader dict at L81 (short keys) and the export dict at L260 (long keys), each to include its three new keys.
- [ ] 4.3 Add a `Usage(...)` non-negativity test for the new fields; a default-0 test confirming a payload without a cache-creation breakdown (and a non-Anthropic adapter) yields 0; and an identity-mismatch test asserting a reported `total != 1h + 5m` fails.

## 5. Docs + close out

- [ ] 5.1 Update `docs/recipes/11-e2e-agent-metrics-cli-adapters.md`: the reader example (~L103-105, add the new short keys) and the exact exported-JSON block (~L129-151, add the new long keys) so the recipe stays runnable/consistent.
- [ ] 5.2 Note the additive fields + reader/export keys in `CHANGELOG.md` as an allowed `provisional` minor **shape change**, with a one-line migration note for strict dict/JSON consumers; regenerate the affected libdocs and update the README metrics summary if it enumerates the usage keys.
- [ ] 5.3 (Optional) Amend the `agent-run-metrics` "Read token usage" scenario parenthetical `(input, output, cached)` to mention cache-creation.
- [ ] 5.4 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest / robot).
- [ ] 5.5 `openspec validate add-usage-cache-creation --strict`; archive after implementation lands + gates green.
