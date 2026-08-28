## 1. Extend the Usage record

- [x] 1.1 In `src/AgentEval/_core/types.py`, add to `Usage`: `cache_creation_input_tokens: int = 0`, `cache_creation_1h_input_tokens: int = 0`, `cache_creation_5m_input_tokens: int = 0`.
- [x] 1.2 Add the three new names to the `__post_init__` non-negativity check.
- [x] 1.3 Docstring the new fields: flat count authoritative; 1h/5m price differently (2× vs 1.25×); `total == 1h + 5m` per Anthropic when the split is reported; `0` on an adapter without a native count means "not reported."

## 2. Populate in the claude-code adapter + assert the identity

- [x] 2.1 In `_usage_from`, read the flat `cache_creation_input_tokens` and the `cache_creation.ephemeral_1h/5m_input_tokens` sub-dict via `_int()` (missing → 0), and pass them to `Usage(...)`.
- [x] 2.2 When the split is reported, reconcile: derive a missing total from the split; a reported total that contradicts the split fails in `Usage.__post_init__` (identity check).
- [x] 2.3 `_pick_usage` still prefers the settled result event, so creation counts come from the terminal event.

## 3. Surface in the metrics readers (each in its own key convention)

- [x] 3.1 `get_token_usage` gains **short** keys `cache_creation` / `cache_creation_1h` / `cache_creation_5m`.
- [x] 3.2 `_record.to_dict` usage block gains **long** keys `cache_creation_input_tokens` / `cache_creation_1h_input_tokens` / `cache_creation_5m_input_tokens`. Each surface keeps its own convention.

## 4. Tests

- [x] 4.1 `test_claude_code_adapter.py` asserts `cache_creation_input_tokens == 300` from the fixture; direct `_usage_from` unit tests cover the `ephemeral_1h/5m` split, deriving the total from a split, and the default-0 path.
- [x] 4.2 Both exact-equality usage assertions in `test_metrics_library.py` updated: the reader dict (short keys) and the export dict (long keys), each with the three new keys.
- [x] 4.3 `Usage` non-negativity covered; a default-0 test; and an identity-mismatch test asserting a reported `total != 1h + 5m` fails.

## 5. Docs + close out

- [x] 5.1 Updated `docs/recipes/11-e2e-agent-metrics-cli-adapters.md`: the reader example (added `cache_creation`) and the exact exported-JSON block (added the three long keys).
- [x] 5.2 `CHANGELOG.md` documents the additive fields + reader/export keys as an allowed `provisional` minor shape change with a strict-consumer note. (Narrowing the SHALL to Anthropic/claude payloads means no opencode change was needed; opencode `cache.write` stays a noted fast-follow.)
- [x] 5.3 Spec's "Read token usage" enumeration left illustrative; the new dedicated cache-creation requirement carries the contract.
- [x] 5.4 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest). Robot dogfood is a separate live-LLM smoke.
- [x] 5.5 `openspec validate add-usage-cache-creation --strict`; archive after implementation lands + gates green.
