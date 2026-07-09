I've now read the adapter, its tests, all five fixtures, the `SubprocessAdapter` base, the codex sibling, `version_drift.py`, the conftest mocks, and the pyproject entry-point. Here are my findings, each re-derived from source.

## Findings

### 1. Category 4 (test-name vs assertion-body) — **MED**: `test_finalize_nonzero_exit_with_text_does_not_emit_diagnostic` does **not** isolate the clause it claims to test

`tests/unit/coding_agent/test_opencode_cli.py:323-329`. The test's docstring says it proves "*response_text wins*" — i.e. that the `not response_text` sub-clause of the 3-condition guard (`opencode_cli.py:369`) suppresses the diagnostic. But it loads `simple_prompt.jsonl`, which contains a terminal `step_finish reason=stop`. So `terminal is None` is **also** False. The guard is suppressed by *two* independent conditions, and the test can't tell which.

Concretely: if a refactor dropped the `not response_text` clause entirely — `if exit_code != 0 and terminal is None:` — this test would **still pass** (terminal is present → guard still False). So the clause it purports to guard is unprotected. Compare `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic` (lines 332-341), which *does* genuinely protect the `terminal is None` clause (drop that clause → it emits the marker → assertion fails). The `not response_text` clause has no isolating regression guard anywhere in the file.

**Fix:** add a fixture/event list with **text present, NO terminal, nonzero exit** and assert `response_text == "<the text>"` and `"[SUBPROCESS_NONZERO_EXIT" not in response_text`. That is the only configuration that isolates the `not response_text` clause. (This is exactly the `feedback_test_name_assertion_match` fake-green pattern.)

### 2. Category 3 (tool-error detection) — **MED**: the `metadata.exit != 0` OR-arm is never exercised; only the `status` arm is tested

`opencode_cli.py:386-389`:
```python
if status not in (None, "completed"):
    error_marker = str(state.get("error") or status)
elif isinstance(cmd_exit, int) and cmd_exit != 0:
    error_marker = f"exit_code={cmd_exit}"
```
The prompt frames detection as "`status != "completed"` **OR** `metadata.exit != 0`". `tool_error.jsonl` sets `status:"error"` **and** `metadata.exit:1`, so the **first** branch fires and the `elif` is shadowed. There is **no** fixture or test where `status == "completed"` but `metadata.exit != 0` (a tool that ran a shell command which exited non-zero while the tool call itself "completed" — the common case for `bash`). That entire `elif` branch is dead in the test suite. Because it's an `elif`, a status-`completed`/exit-`1` event is the *only* way to reach it, and nothing covers it.

**Fix:** add a `tool_use` event with `state.status:"completed"`, `state.metadata.exit:1` and assert `tool_calls[0].error == "exit_code=1"`. (Worth doing — `bash` returning non-zero while the tool "completes" is the realistic failure shape, more common than the `status:"error"` case.)

### 3. Category 3 / robustness — **LOW**: any non-`completed`/non-`None` status is coerced to an error; no completed-only filter like the codex precedent

`opencode_cli.py:386`. The sibling `codex_cli.py:188` deliberately processes **only** `item.completed` command executions and skips in-progress ones. The opencode adapter has no such gate: it synthesizes a `ToolCallTrace` from *every* `tool_use` event and marks `error = str(... or status)` for any status not in `{None, "completed"}`. The empirical ground truth only lists `"completed"|"error"`, so this is latent — but if opencode ever streams an interim `"running"`/`"pending"` tool part (streaming JSON commonly emits a part on start *and* completion), this code would (a) emit a spurious `ToolCallTrace` with `error="running"`, and (b) potentially **double-count** the same `callID` as two tool calls. There's no dedup by `callID`.

**Fix:** either filter to terminal tool states (`status in {"completed","error"}`) mirroring codex's completed-only discipline, or dedup by `callID` keeping the last state. At minimum add a `DF-OPENCODE-*` carry-over noting the single-emission assumption.

### 4. Category 5 (argv / prompt injection) — **MED**: no `--` end-of-options sentinel; a prompt beginning with `-` is parsed as a flag

`opencode_cli.py:310-321`. The prompt is appended as the trailing positional with no `--` guard. A dataset/agent-supplied prompt like `--help`, `-v`, or `--model attacker/model` is consumed by opencode's arg parser instead of being treated as the message. In an eval harness the prompt is frequently adversarial/dataset-controlled, so this is a real argv-injection surface (model override, flag injection, or just a silently-empty run → `completeness="truncated"` with no diagnostic). The codex sibling shares this gap, but it documented *why* (`codex exec` requires the flag to precede and `-` means stdin) — the opencode adapter just silently inherits the limitation with no probe of whether `opencode run -- <prompt>` is supported.

**Fix:** probe whether `opencode run --format json -- "<prompt>"` is accepted (opencode is a Bun/TS CLI and very likely uses a parser that honors `--`); if so, insert `"--"` before `cmd.append(prompt)`. Add a regression test with a leading-dash prompt asserting it reaches argv as the message, not a flag. If `--` is unsupported, document that explicitly like codex does.

### 5. Category 5 (pipe/stdin hygiene) — **LOW**: `stdin` left inheriting the parent

`opencode_cli.py:322-328`. `stdout=PIPE`, `stderr=STDOUT` are correct and there is **no** pipe-deadlock on the output side (single drained pipe — good). But `stdin` is not set, so the child inherits the parent's stdin. With `--dangerously-skip-permissions` and a positional message opencode shouldn't read stdin, but a defensive `stdin=subprocess.DEVNULL` removes any chance of a non-TTY read blocking under pabot/CI. Matches the "never let a subprocess block on inherited stdin" intent of the Story 4.2 D-1 lesson the docstring cites.

### 6. Category 6 (drift wiring) — **LOW / informational**: your "empty within-range drift window" claim is **correct**, and the consequence is that FR60 drift can never fire for this adapter

Verified against `version_drift.py:165-181`: same-major path computes `drift = tested.minor - detected.minor` and fires on `drift >= 2`. `_TESTED_UP_TO=1.15.12` → `tested.minor=15`. Every in-range binary (floor `MIN_VERSION=1.15.0`) has `minor >= 15`, so `drift <= 0 < 2` always; anything `>= 2` minors behind 15 is below the floor and rejected by `_assert_binary_version` first. **Claim confirmed: the within-range drift window is empty.** Cross-major can't fire either (major must equal 1 to be in range).

Net: the FR60 `AdapterVersionDriftWarning` wiring is structurally a **no-op** for opencode until `_TESTED_UP_TO` advances to minor ≥ 17. This is honestly documented in `test_in_range_binary_constructs_without_spurious_drift_warning` (lines 109-128), so it's not a defect — but flag it so a future `_TESTED_UP_TO` bump remembers to add a real firing test, and consider whether pinning `MIN_VERSION` to the same minor as `_TESTED_UP_TO` defeats the feature's purpose for this adapter.

### 7. Categories 1, 2, 7, 8, 9 — **no substantive findings**

- **(1) Terminal identification / completeness:** `next((e for e in reversed(events) if e.is_terminal), None)` (line 361) correctly takes the *last* `step_finish reason=="stop"`; `completeness` (line 437) correctly gates on `terminal is not None and exit_code == 0`. Verified against all five fixtures (tool_use's two `step_finish` → picks the `reason="stop"` second one; truncated → `None` → "truncated").
- **(2) Per-step token summing:** lines 413-422 sum across **every** `step_finish`, matching the per-step (non-cumulative) ground truth. tool_use: input `37+234=271`, output `63+3=66`, reasoning `21+21=42`, cache.read `17280+17280=34560` — all match the test. No double-count, no under-count. (Minor note: `cache.write` is intentionally dropped from accounting; correct for `cached_input_tokens` semantics but worth a one-line comment.)
- **(7) mcp_coverage:** `_detect_mcp_coverage` (458-472) — empty/None→`hosted_in_process`, non-empty→`external_mixed`, matching ADR-016 §L33 and the codex precedent exactly.
- **(8) Thread-safety:** `_last_mcp_servers` is set before `super().run()` and reset in `finally` *after* it returns; `_finalize` runs *inside* `super().run()` while the value is live, so single-threaded reads are correct. The not-concurrent-safe invariant is documented inline (class docstring 207-215). No undocumented concurrency bug.
- **(9) Null-safety:** the `_as_dict` helper (101-107) plus `step_cost`'s try/except (191-194) make the `part.state.metadata.exit` descent fully null/type-safe and mypy-clean. `isinstance(cmd_exit, int)` correctly guards the `exit` read. No null hole found.

**Highest-leverage fixes:** #1 (add the text-present/no-terminal/nonzero-exit isolation test) and #2 (add the `status=completed`/`exit!=0` tool-error test) — both close genuine coverage gaps where the suite would stay green through a real regression. #4 is the one I'd escalate if prompts in your eval sets are untrusted.
