# Codex adversarial review: add-subagent-delegation-testing

Reviewed working tree on branch `implement-explore-findings` against `openspec/changes/add-subagent-delegation-testing/`.

## Findings

### MED: Delegation extraction counts hosted/user tools named `task` as subagent delegations

- Location: `src/AgentEval/subagents/_internal.py:116-128`
- Concrete scenario: an `AgentRunResult` contains a real hosted MCP/user tool call with `ToolCallTrace(name="task", source="hosted_mcp", args={"name": "code-reviewer"})`. `extract_delegations()` lowercases only the tool name and treats this as a delegation record to `code-reviewer`. `Subagent.Should Have Delegated To(..., "code-reviewer")` can therefore pass even though the orchestrator never invoked Claude Code's built-in `Task` delegation tool. With `args={"input": "not delegation"}`, `Subagent.Should Not Have Delegated` fails because it sees a delegation with `subagent=""`.
- Why this is real: the shared `ToolCallTrace` type carries `source` (`adapter` vs `hosted_mcp`), but the extractor ignores it. The default `Task` tool is a Claude adapter delegation surface, while arbitrary hosted/user tools can legally have a lower-case `task` name. The current exact-but-case-insensitive name match avoids substring overmatch, but still overmatches this literal tool-name collision.
- Repro command run:

```bash
uv run python - <<'PY'
from AgentEval.subagents.library import SubagentsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

trace = ToolCallTrace(
    name="task",
    args={"input": "not delegation"},
    result=None,
    error=None,
    latency_ms=0,
    source="hosted_mcp",
    gen_ai_tool_call_id="mcp-1",
    sequence_index=0,
)
result = AgentRunResult(
    response_text="ok",
    tool_calls=[trace],
    usage=Usage(1, 1),
    metadata=AgentRunMetadata("complete", "hosted_in_process"),
    cost_usd=0,
    latency_seconds=0,
    trace_id="x" * 32,
)
lib = SubagentsLibrary()
print(lib.get_delegations(result))
lib.should_not_have_delegated(result)
PY
```

Observed: `get_delegations()` returned one `DelegationRecord(subagent='')`; `should_not_have_delegated()` raised `SubagentDelegationAssertionError`.

### LOW: Empty expected skill list makes `Should Declare Skills` vacuously pass on any non-empty `skills:` declaration

- Location: `src/AgentEval/subagents/library.py:578-615`
- Concrete scenario: a Robot author accidentally calls `Subagent.Should Declare Skills    agents/researcher.md` with no expected skill names. If the file has any non-empty `skills:` list, the keyword returns successfully because `missing = [s for s in skills if s not in declared]` is empty. The OpenSpec says the keyword takes "one or more skill names" (`openspec/changes/add-subagent-delegation-testing/specs/subagent-config-validation/spec.md:34-36`), so this should fail loud rather than silently certifying nothing.
- Repro command run:

```bash
uv run python - <<'PY'
from pathlib import Path
from AgentEval.subagents.library import SubagentsLibrary

p = Path("/tmp/sub-noexpected.md")
p.write_text("---\nname: r\ndescription: d\nskills:\n  - pdf-tools\n---\n")
SubagentsLibrary().should_declare_skills(p)
print("NO_ERROR")
PY
```

Observed: `NO_ERROR`.

### LOW: Empty-string delegation identities are hidden in the structured error rendering

- Location: `src/AgentEval/errors.py:971-981`
- Concrete scenario: the extractor intentionally degrades unrecognized Task shapes to `DelegationRecord(subagent="")` so the mismatch is visible. But `SubagentDelegationAssertionError.__str__()` renders a non-empty observed list containing `""` as a blank `Observed:` line because `", ".join([""]) == ""`. This makes the diagnostic look malformed rather than showing an unresolved delegation identity.
- Why this matters: this is exactly the fallback path required by the spec ("unrecognized shape yields `subagent=""` visible non-match"). The record is retained, but the human-facing diagnostic loses the visibility.
- Repro is included in the first finding: the rendered error contained `Observed:` with nothing after it.

## Non-findings checked

- Identity-key order is implemented as `subagent_type -> agent_type -> agent -> name`; missing keys degrade to `subagent=""`.
- `Should Have Delegated To` / `Should Not Have Delegated` polarity is correct for multiple/repeated delegations; targeted absence ignores other subagents.
- `Subagent.Get Routing Pass At K` uses `_compute_pass_at_k` with a hard-coded `_routing_pass_predicate`; no `predicate` kwarg is exposed, and foreign/`None` results count as non-pass.
- `Should Declare Skills` fails on absent/empty `skills:`; `Tools Should Be Subset Of` fails on absent/empty `tools:` and names offending tools.
- FR28 polling rejection is present before adapter invocation in Tier-2/3 keywords.
- `SubagentsLibrary` inherits `_HostBudgetPlumbing`, and composed `AgentEval(max_cost_usd=1.23, max_runtime_seconds=4.56)` forwards those values to the sub-library.
- Keyword-count gate is updated to 75 and targeted convention tests pass.

## Verification commands

```bash
uv run pytest tests/unit/subagents -q
uv run pytest -k 'subagent and (delegation or routing or config)' -q
uv run pytest tests/integration/docs/test_keyword_count_drift.py tests/unit/conventions/test_keyword_name_idiom.py tests/unit/conventions/test_tier_annotation_present.py tests/unit/conventions/test_keyword_namespace_prefix.py -q
rg -n "DF-[0-9]+\.[0-9]+-S[0-9]+|DF-X-SY|TODO\(|FIXME" src/AgentEval/subagents openspec/changes/add-subagent-delegation-testing tests/unit/subagents
uv run python - <<'PY'
from AgentEval import AgentEval
lib = AgentEval(max_cost_usd=1.23, max_runtime_seconds=4.56)
for component in lib._build_components():
    if component.__class__.__name__ == "SubagentsLibrary":
        print(component._max_cost_usd, component._max_runtime_seconds)
        break
PY
```

Results:

- `tests/unit/subagents`: 100 passed.
- `-k 'subagent and (delegation or routing or config)'`: 115 passed, 2309 deselected.
- count/convention subset: 11 passed.
- DF grep found only pre-existing/design references plus docstring TODO footers; no `DF-X-SY` implementation marker.
- budget forwarding probe printed `1.23 4.56`.
