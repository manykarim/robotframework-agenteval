# Codex adversarial review: add-budget-assertion-keywords

Result: no HIGH / MED / LOW correctness findings.

## Scope reviewed

- Working-tree diff on branch `implement-explore-findings`.
- OpenSpec change under `openspec/changes/add-budget-assertion-keywords/`.
- New assertion implementation in:
  - `src/AgentEval/_assertions/library.py`
  - `src/AgentEval/_assertions/_internal.py`
- Getter/helper parity in:
  - `src/AgentEval/metrics/library.py`
  - `src/AgentEval/metrics/_internal.py`
- Focused tests and documentation/count gates.

## Checks performed

- Aggregation parity:
  - `Cost Should Be Below` uses `_compute_cost_total` / `_aggregate_cost_total`, matching `Get Cost Total` single-run pass-through and list sum.
  - `Latency Should Be Below` uses `_compute_latency_mean` / `_aggregate_latency_mean`, matching `Get Latency`, including no-tool-call `latency_seconds * 1000.0` fallback and list union-then-mean.
  - `Latency P95 Should Be Below` uses `_compute_latency_p95` / `_aggregate_latency_p95`, matching `Get Latency P95`, including union-P95 for list input.
  - `Token Usage Should Be Below` derives total as `input_tokens + output_tokens` from `_compute_token_usage` / `_aggregate_token_usage`, matching the stated budget formula and avoiding cached/reasoning double-counting.
- Strict boundary:
  - Direct probes confirmed values exactly equal to threshold fail for all four keywords through AssertionEngine `<`.
- Validation/guards:
  - Empty list raises `ValueError`.
  - `0`, `-0.0`, negative values, `nan`, `inf`, and `-inf` raise `ValueError`.
  - Monkeypatched direct probes confirmed invalid thresholds raise before assertion dispatch and before pass logging.
- Failure message:
  - Existing tests and direct probes confirm failure messages include observed value, threshold, and unit via the AssertionEngine message prefix plus comparison body.
- Multi-trial:
  - Direct probes compared list aggregation against `MetricsLibrary` getters for cost, latency, P95, and token usage.
- Coverage:
  - Direct probes used `mcp_coverage="external_mixed"` with `allow_external_mcp_blind=False`; the scalar budget assertions evaluated normally and did not raise `IncompleteTraceError`.
- Count/doc gate:
  - `derive_keyword_count() == 59` passes.
  - README and libdoc contain all four new keywords.

## Commands run

```bash
git diff -- src/AgentEval/_assertions/library.py tests openspec/changes/add-budget-assertion-keywords pyproject.toml
rg -n "Get Cost Total|Get Latency P95|Get Latency|Get Token Usage|Cost Should Be Below|Latency Should Be Below|Latency P95 Should Be Below|Token Usage Should Be Below|composed keyword|59|IncompleteTraceError" -S src tests openspec/changes/add-budget-assertion-keywords
nl -ba src/AgentEval/_assertions/_internal.py | sed -n '180,330p'
nl -ba src/AgentEval/metrics/_internal.py | sed -n '1,330p'
nl -ba src/AgentEval/metrics/library.py | sed -n '300,460p'
nl -ba src/AgentEval/_assertions/adapter.py | sed -n '1,180p'
uv run pytest tests/unit/_assertions/test_assertions_library.py -k "budget or external_mixed"
uv run pytest tests/unit/metrics/test_metrics_library.py -k "token_usage or latency or cost_total"
uv run pytest tests/integration/docs/test_keyword_count_drift.py tests/unit/conventions/test_docstring_libdoc_badge_alignment.py tests/unit/conventions/test_keyword_name_idiom.py
uv run python - <<'PY'
# Direct aggregation/strict-boundary/external_mixed probes.
PY
uv run python - <<'PY'
# Invalid-threshold-before-dispatch probes.
PY
grep -RIn "Cost Should Be Below\|Latency Should Be Below\|Latency P95 Should Be Below\|Token Usage Should Be Below\|derive_keyword_count() == 59" src tests README.md docs/keywords/AgentEval.html | head -80
```

## Non-finding note

I noticed an existing getter-layer quirk: `_aggregate_token_usage()` does not preserve `reasoning_output_tokens` in the returned aggregate `Usage`. I am not filing this as a finding for this change because the new budget assertion's specified comparison is explicitly `input_tokens + output_tokens`, and the new assertion stays in parity with the current `Get Token Usage` aggregate before applying that formula.
