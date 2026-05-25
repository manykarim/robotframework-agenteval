# Story 8b.2: `agenteval new-adapter` Scaffolding + Terminal Run Summary + Cohort Heatmap

Status: done

## Story

As a **custom adapter author** or **post-run reviewer**,
I want `agenteval new-adapter` to scaffold a new adapter package skeleton + a terminal run summary (FR54) + `CohortHeatmap.as_ascii()` and `.as_dict()` methods,
so that authoring custom adapters is friction-free and post-run results land legibly in terminal output (CI logs) or programmatic consumers.

## Pre-create-story drift check (38th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-25)

100% catch rate intact. 4 drifts caught:

- **D-1 (MED):** FR54 (PRD L1583) prescribes the terminal summary contents (total tests + pass/fail count + total cost USD + p95 latency + warnings count + 3 most-fired error types). Format pinned in story spec via 1 visual contract block.
- **D-2 (MED):** `CohortHeatmap` is a new public type — `Get Cohort Heatmap` keyword name + return shape NOT in any existing module. Add to a new `src/AgentEval/_heatmap/` module (mirror Story 8b.1 `_init/` pattern); ship `CohortHeatmap` dataclass + `as_ascii()` + `as_dict()` methods + RF keyword wrapper.
- **D-3 (LOW):** `new-adapter --type` flag values: per Story 1b.4 there are 2 base classes (`SubprocessAdapter`, `InProcessAdapter`). Accept both; default `subprocess`.
- **D-4 (LOW):** Terminal summary trigger — story spec says "When the suite completes, stdout displays". The Listener's `end_suite` hook is the natural fire point. Phase-1: write to stdout via `print()` (separate from `_log.info()` which goes to stderr). Phase-1.5 may add a CLI flag to opt out.

## Acceptance Criteria

### AC-8b.2.1 — `agenteval new-adapter` subcommand

**Given** the CLI from Story 8b.1,
**When** `agenteval new-adapter --name my-adapter [--type subprocess|inprocess] [--output-dir <dir>] [--force]`,
**Then** the CLI scaffolds:
- `<output-dir>/my_adapter/pyproject.toml` — declares the `agenteval.coding_agents` entry-points group registration per FR17a.
- `<output-dir>/my_adapter/my_adapter/__init__.py`
- `<output-dir>/my_adapter/my_adapter/adapter.py` — subclass of `SubprocessAdapter` (or `InProcessAdapter`) with abstract methods stubbed + TODO comments.
- `<output-dir>/my_adapter/tests/test_my_adapter.py` — Mock conformance test.

Name normalization: `--name my-adapter` produces module `my_adapter` (kebab → snake).

### AC-8b.2.2 — `CohortHeatmap` class with `.as_ascii()` + `.as_dict()`

**Given** a `DiscoverabilityResult` from Story 4.4,
**When** `CohortHeatmap.from_discoverability(result)` is called,
**Then** returns a `CohortHeatmap` instance with:
- `.as_ascii() -> str` — rows = tasks, columns = models (Phase-1 single-model: 1 column), cells = Pass@k value formatted as 2-decimal float. Box-drawing characters (`│`, `┼`, `─`) for readability.
- `.as_dict() -> dict[str, dict[str, float]]` — nested dict `{task_id: {model_name: pass_at_k}}`.
- `.tasks: tuple[str, ...]` + `.models: tuple[str, ...]` exposed for programmatic consumers.

Phase-1: single-`DiscoverabilityResult` input (single model). Multi-model heatmap is Phase-2 (Epic 13).

### AC-8b.2.3 — `Get Cohort Heatmap` keyword on a new `HeatmapLibrary`

**Given** the new `src/AgentEval/_heatmap/library.py::HeatmapLibrary` (registered in `_SUB_LIBRARIES`),
**When** `${heatmap}=    Get Cohort Heatmap    ${discoverability_result}` in a `.robot` test,
**Then** the keyword returns a `CohortHeatmap` instance. Tier-1 (deterministic projection — no LLM calls).

### AC-8b.2.4 — Terminal run summary via Listener `end_suite`

**Given** the Listener at `src/AgentEval/telemetry/listener.py`,
**When** `end_suite(data, result)` fires at the top-level suite end,
**Then** the Listener writes a 1-block FR54 summary to stdout (when env var `AGENTEVAL_TERMINAL_SUMMARY=1` is set, default-off to avoid disrupting non-CI consumers):

```
╔════════════════ agenteval run summary ════════════════╗
║ Tests:    N total / N passed / N failed              ║
║ Cost:     $X.XX                                       ║
║ Latency:  N.NNs p95                                   ║
║ Warnings: N                                           ║
║ Top errors:                                           ║
║   1. ErrorType (N occurrences)                        ║
║   2. ...                                              ║
╚═══════════════════════════════════════════════════════╝
```

Failure-mode: any exception during summary computation is logged at WARN; the suite outcome is NOT masked.

### AC-8b.2.5 — Scaffolded adapter test uses MockProvider conformance pattern

**Given** the scaffolded `tests/test_my_adapter.py`,
**When** the user runs `pytest tests/test_my_adapter.py`,
**Then** the test instantiates the new adapter against `MockProvider` and verifies the `AgentRunResult` contract (`response_text`, `metadata.completeness`).

### AC-8b.2.6 — Unit tests at `tests/unit/test_new_adapter_cli.py` (≥5)

1. `new-adapter --name x` creates the 4 scaffolded files.
2. Name normalization (kebab → snake).
3. `--type subprocess` scaffolds `SubprocessAdapter` subclass.
4. `--type inprocess` scaffolds `InProcessAdapter` subclass.
5. Exit 0 on success.

### AC-8b.2.7 — Unit tests at `tests/unit/_heatmap/test_cohort_heatmap.py` (≥5)

1. `CohortHeatmap.from_discoverability(result)` with empty per_task_results → empty heatmap.
2. Single-task / single-model heatmap → 1x1 ASCII table.
3. Multi-task / single-model → Nx1 table with all task IDs as rows.
4. `.as_dict()` round-trips back to readable dict.
5. ASCII output contains box-drawing chars + Pass@k 2-decimal format.

### AC-8b.2.8 — Unit tests at `tests/unit/telemetry/test_terminal_summary.py` (≥3)

1. `end_suite` writes FR54 summary to stdout when `AGENTEVAL_TERMINAL_SUMMARY=1`.
2. No summary written when env var unset.
3. Failure during summary computation is logged at WARN + does NOT raise.

### AC-8b.2.9 — `feedback_carry_over_catalog_gate` UPSTREAM (17th consecutive)

No new carry-overs anticipated. Story 8b.2 closes 3 PRD FRs (FR54, FR55-ASCII, FR18-new-adapter).

### AC-8b.2.10 — All-gates pass

- `uv run pytest tests/ -q` all green; +13 net new tests (5+5+3).
- ruff/format/mypy clean.

## Tasks / Subtasks

- [x] **Task 1**: extend `cli.py::main` — `new-adapter` subcommand routing (currently a stub from Story 8b.1).
- [x] **Task 2**: create `src/AgentEval/_new_adapter/` module + scaffold writer + 4 template files (pyproject.toml, __init__.py, adapter.py — both subprocess + inprocess variants, test_my_adapter.py).
- [x] **Task 3**: create `src/AgentEval/_heatmap/` module — `__init__.py`, `models.py` (CohortHeatmap dataclass), `library.py` (HeatmapLibrary with `Get Cohort Heatmap` keyword).
- [x] **Task 4**: register `HeatmapLibrary` in `src/AgentEval/__init__.py::_SUB_LIBRARIES`.
- [x] **Task 5**: extend `Listener.end_suite` for FR54 terminal summary (env-var-gated).
- [x] **Task 6**: write 5+5+3 = 13 unit tests across `test_new_adapter_cli.py` + `test_cohort_heatmap.py` + `test_terminal_summary.py`.
- [x] **Task 7**: all-gates run.
- [x] **Task 8**: sprint-status → done after code-review.

## Dev Notes

### Architecture compliance

- **PRD FR18** (custom adapter scaffolding): satisfied by `new-adapter` CLI.
- **PRD FR54** (terminal run summary): satisfied by env-var-gated Listener end_suite output.
- **PRD FR55** (ASCII + dict cohort heatmap): satisfied by `CohortHeatmap.as_ascii()` + `.as_dict()`.
- **PRD FR17a** (entry-points group registration): scaffolded pyproject.toml includes the group.

### Files to create / modify

**CREATE:**
- `src/AgentEval/_new_adapter/__init__.py`
- `src/AgentEval/_new_adapter/scaffold.py`
- `src/AgentEval/_new_adapter/templates/pyproject.toml.tmpl`
- `src/AgentEval/_new_adapter/templates/__init__.py.tmpl`
- `src/AgentEval/_new_adapter/templates/adapter_subprocess.py.tmpl`
- `src/AgentEval/_new_adapter/templates/adapter_inprocess.py.tmpl`
- `src/AgentEval/_new_adapter/templates/test_adapter.py.tmpl`
- `src/AgentEval/_heatmap/__init__.py`
- `src/AgentEval/_heatmap/models.py`
- `src/AgentEval/_heatmap/library.py`
- `tests/unit/test_new_adapter_cli.py`
- `tests/unit/_heatmap/__init__.py`
- `tests/unit/_heatmap/test_cohort_heatmap.py`
- `tests/unit/telemetry/test_terminal_summary.py`

**MODIFY:**
- `src/AgentEval/cli.py` — wire `new-adapter` subcommand args.
- `src/AgentEval/__init__.py` — register `HeatmapLibrary` in `_SUB_LIBRARIES`.
- `src/AgentEval/telemetry/listener.py::end_suite` — extend with FR54 terminal summary.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

### File List

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-25 | 0.1.0 | Initial story creation. 38th use of `feedback_spec_vs_ratified_doc_precheck` (100% catch rate intact). 4 drifts caught (D-1 through D-4). 10 ACs. Closes FR18 + FR54 + FR55-ASCII. | Bob |
