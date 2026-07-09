# Recipe #6: Custom Protocol adapter

**Use case:** integrate agenteval with a non-default agent runtime (custom CLI, in-process SDK, hosted API).
**What it covers:** the `CodingAgentAdapter` Protocol, the InProcessAdapter + SubprocessAdapter base classes, the entry-points group, and `new-adapter` scaffolding.

## TL;DR

```bash
agenteval new-adapter --name my-adapter --type subprocess
cd my-adapter
# Implement the TODOs in my_adapter/adapter.py
uv add --dev pytest
uv run pytest tests/
```

Then publish the package and the agent runtime is automatically discoverable
by any agenteval consumer via the `agenteval.coding_agents` entry-points group.

## Step-by-step

### 1. Scaffold

```bash
agenteval new-adapter --name my-adapter --type subprocess
```

Scaffolds:

```
my-adapter/
├── pyproject.toml          # declares the entry-points group
├── my_adapter/
│   ├── __init__.py
│   └── adapter.py          # SubprocessAdapter subclass with TODOs
└── tests/
    └── test_my_adapter.py  # Mock conformance test
```

Use `--type inprocess` if you're wrapping an in-process SDK (LiteLLM /
Anthropic SDK / OpenAI SDK) instead of spawning a CLI subprocess.

### 2. Choose the right base class

| Base class | When to use | Reference impl |
| --- | --- | --- |
| `SubprocessAdapter` | Your agent runs as a CLI (`claude`, `gh copilot`, `gemini`). | `AgentEval.coding_agent.claude_code_cli.ClaudeCodeCLIAdapter` |
| `InProcessAdapter` | Your agent runs in-process via an SDK call. | `AgentEval.coding_agent.generic.GenericAdapter` |

### 3. Implement the 3 template-method hooks (SubprocessAdapter)

`SubprocessAdapter` provides the lifecycle (spawn → stream stdout → parse
events → finalize). You implement:

- **`_spawn(prompt, **kwargs)`** — launch the CLI binary (typically
  `subprocess.Popen(...)`). Return the process handle.
- **`_parse_event(line)`** — parse one line of stdout into a structured
  event (or return None to skip). Examples: tool-call markers, token
  counts, cost annotations.
- **`_finalize(events)`** — aggregate parsed events into the final
  `AgentRunResult` (`response_text`, `tool_calls`, `metadata`).

### 4. Implement `run()` (InProcessAdapter)

`InProcessAdapter` is simpler — implement `run(prompt, **kwargs) -> AgentRunResult`
directly. See `AgentEval.coding_agent.generic.GenericAdapter.run` for the
canonical LiteLLM-backed pattern.

### 5. Register the entry-point

The scaffolded `pyproject.toml` declares:

```toml
[project.entry-points."agenteval.coding_agents"]
my_adapter = "my_adapter.adapter:Adapter"
```

Once `uv add my-adapter` (or `pip install my-adapter`) is run by a
downstream consumer, `agenteval` auto-discovers `my_adapter` via
`importlib.metadata.entry_points()` ([entry-points discovery](../adr/ADR-013-entry-points-discovery-infrastructure.md)).

### 6. Use the adapter

```robotframework
*** Test Cases ***
My Adapter Send Prompt
    ${result}=    Send Prompt    adapter=my_adapter    prompt=Hello
    Should Not Be Empty    ${result.response_text}
```

### 7. Verify via `python -m AgentEval.conformance`

Once published, run the conformance harness against your adapter (Phase-1.5
wires real adapter dispatch; current Phase-1 records all fixtures
as `skipped`):

```bash
python -m AgentEval.conformance --adapter my_adapter --output-dir ./conformance-report
```

## Phase-1.5 considerations

- The CLI `--type subprocess` scaffold raises `NotImplementedError` until
  the 3 hook TODOs are filled in — by design, so `uv run pytest` flags the
  unimplemented state.
- Real conformance fixture execution (`python -m AgentEval.conformance`)
  is deferred to Phase-1.5.

## Cross-references

- [CodingAgentAdapter Protocol + base classes](../adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md) — Protocol + InProcessAdapter / SubprocessAdapter base classes.
- [Entry-points discovery infrastructure](../adr/ADR-013-entry-points-discovery-infrastructure.md)
