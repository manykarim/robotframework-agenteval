# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Internal engine for `Skill.Compare Against Baseline` (add-skill-ab-benchmark).

Private module — not part of the public API. Contains:

- `SkillBenchmarkTask` — one benchmark cohort task (prompt + grading spec).
- `load_skill_benchmark_tasks(path)` — load + validate the benchmark cohort YAML
  (sibling of `load_skill_discoverability_tasks`).
- `run_skill_benchmark(...)` — the two-arm execution + blind-grading +
  statistics + verdict orchestrator that `SkillsLibrary.compare_against_baseline`
  delegates to (inside the `@guarded_fanout` budget scope).

Design honesty contracts (design.md D2/D4/D6):
- **Skill delivery is prompt-context injection** (`skill_delivery="prompt_injected"`).
  The harness prepends the skill's raw `.md` content in a delimited block; it
  does NOT install the skill natively. This is stated in the result, not implied.
- **Blind grading**: the judge prompt carries ZERO arm metadata added by the
  harness (only the rubric + task prompt + the trial's `response_text`); the
  judge grading queue is seed-shuffled + interleaved across arms; the blinding
  map is recorded in the result for post-hoc audit.
- **Obsolescence is first-class**: `skill_unnecessary` is a closed-set verdict,
  computed by one documented rule — never left for the user to eyeball.
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.redaction import redact
from AgentEval.errors import CostExceededError, InvalidSkillBenchmarkTasksError
from AgentEval.skills.types import (
    SkillBenchmarkArmSummary,
    SkillBenchmarkComparisonResult,
    SkillBenchmarkTrialEvidence,
)

if TYPE_CHECKING:
    from AgentEval.types import AgentRunResult

__all__ = [
    "SkillBenchmarkTask",
    "load_skill_benchmark_tasks",
    "run_skill_benchmark",
    "compute_benchmark_verdict",
]

# Number of bootstrap resamples for the pass-rate-delta CI (design D5). Kept at
# the `compute_bootstrap_ci` floor-satisfying 1000 for a stable percentile
# estimate at typical cohort sizes.
_BOOTSTRAP_RESAMPLES = 1000

# Truncation length for the redacted response excerpt stored in evidence.
_EXCERPT_MAX_CHARS = 500


class _CostMeter:
    """Explicit cumulative-cost accounting for the benchmark fan-out (codex HIGH).

    ``@guarded_fanout()``'s cost meter reads
    ``guardrails._current_cost_usd_for_run()`` — a Phase-1 stub returning
    ``0.0`` — so it cannot see adapter-reported per-call costs. This meter
    accumulates the REAL ``run_result.cost_usd`` from every adapter run PLUS
    every judge call and raises :class:`CostExceededError` the moment the
    running total breaches the effective ``max_cost_usd`` budget (the per-call
    keyword argument, falling back to the host instance attr). Mirrors the
    ``RedTeamLibrary._enforce_cumulative_cost`` pattern.

    ``max_cost_usd is None`` = no enforcement (the no-budget fast path).
    """

    def __init__(self, max_cost_usd: float | None) -> None:
        self.max_cost_usd = max_cost_usd
        self.cumulative_cost_usd = 0.0

    def add(self, cost_usd: float, *, where: str) -> None:
        """Add a per-call cost and raise if the running total breaches the cap."""
        self.cumulative_cost_usd += cost_usd or 0.0
        if self.max_cost_usd is not None and self.cumulative_cost_usd > self.max_cost_usd:
            raise CostExceededError(
                f"Cumulative skill-benchmark cost {self.cumulative_cost_usd:.4f} USD exceeded the "
                f"max_cost_usd budget {self.max_cost_usd:.4f} USD (breached at {where}). "
                f"Raise `max_cost_usd`, reduce `trials`, or shrink the task cohort."
            )


# --------------------------------------------------------------------------- #
# Benchmark cohort task schema + loader (design D3)                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillBenchmarkTask:
    """One task entry in a skill A/B benchmark YAML (design D3).

    Exactly ONE grading mode is populated:
        - `expected_content` non-None → deterministic substring grading.
        - `rubric_path` non-None → judge-rubric grading.

    Fields:
        id: Unique string identifier for the task.
        prompt: Natural-language prompt sent to the agent (both arms).
        expected_content: Tuple of substrings that must ALL appear
            (case-insensitively) in `response_text` for a pass, or None.
        rubric_path: Filesystem path to a judge rubric `.md`, or None.
    """

    id: str
    prompt: str
    expected_content: tuple[str, ...] | None
    rubric_path: str | None

    @property
    def grading_mode(self) -> str:
        return "expected_content" if self.expected_content is not None else "judge"


def load_skill_benchmark_tasks(path: str | Path) -> list[SkillBenchmarkTask]:
    """Load + validate a skill A/B benchmark tasks YAML file (design D3).

    Args:
        path: Filesystem path to the benchmark tasks YAML file.

    Returns:
        List of validated `SkillBenchmarkTask` instances in YAML order.

    Raises:
        InvalidSkillBenchmarkTasksError: On any structural failure (file
            missing, wrong extension, malformed YAML, schema violation).
            `field_name` carries an RFC 6901 JSON Pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidSkillBenchmarkTasksError(
            f"skill benchmark tasks YAML file not found: {p}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidSkillBenchmarkTasksError(
            f"skill benchmark tasks file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidSkillBenchmarkTasksError(
            f"failed to read skill benchmark tasks YAML: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidSkillBenchmarkTasksError(
            f"skill benchmark tasks YAML is not valid UTF-8: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidSkillBenchmarkTasksError(
            f"malformed YAML in skill benchmark tasks file: {exc}",
            file_path=str(p),
            line_number=line,
            field_name="",
            fix_suggestion="Fix the YAML syntax error at the indicated line.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSkillBenchmarkTasksError(
            "skill benchmark tasks file must be a YAML mapping at the top level",
            file_path=str(p),
            field_name="",
            fix_suggestion="Add a top-level `tasks:` key with a list of task entries.",
        )

    default_rubric = _read_default_rubric(parsed, str(p))

    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise InvalidSkillBenchmarkTasksError(
            "skill benchmark tasks file must have a non-empty `tasks:` list",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add at least one task entry under `tasks:`.",
        )

    seen_ids: set[str] = set()
    tasks: list[SkillBenchmarkTask] = []
    for idx, raw_task in enumerate(raw_tasks):
        tasks.append(_parse_benchmark_task(raw_task, idx, str(p), default_rubric, seen_ids))
    return tasks


def _read_default_rubric(parsed: dict[str, Any], file_path: str) -> str | None:
    """Extract + validate the optional file-level `defaults.rubric` fallback."""
    defaults = parsed.get("defaults")
    if defaults is None:
        return None
    if not isinstance(defaults, dict):
        raise InvalidSkillBenchmarkTasksError(
            "top-level `defaults:` must be a mapping",
            file_path=file_path,
            field_name="/defaults",
            fix_suggestion="Use `defaults:\\n  rubric: <path.md>` or remove the `defaults:` block.",
        )
    rubric = defaults.get("rubric")
    if rubric is None:
        return None
    if not isinstance(rubric, str) or not rubric:
        raise InvalidSkillBenchmarkTasksError(
            f"`defaults.rubric` must be a non-empty string path; got {rubric!r}",
            file_path=file_path,
            field_name="/defaults/rubric",
            fix_suggestion="Set `defaults.rubric` to a path to a judge rubric `.md` file.",
        )
    return rubric


def _parse_benchmark_task(
    raw_task: Any,
    idx: int,
    file_path: str,
    default_rubric: str | None,
    seen_ids: set[str],
) -> SkillBenchmarkTask:
    """Validate one raw task mapping into a `SkillBenchmarkTask` (design D3)."""
    pointer_prefix = f"/tasks/{idx}"
    if not isinstance(raw_task, dict):
        raise InvalidSkillBenchmarkTasksError(
            f"task at index {idx} must be a YAML mapping",
            file_path=file_path,
            field_name=pointer_prefix,
            fix_suggestion="Each task must be a mapping with `id`, `prompt`, and a grading mode.",
        )

    task_id = raw_task.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise InvalidSkillBenchmarkTasksError(
            f"task at index {idx} is missing required string field `id`",
            file_path=file_path,
            field_name=f"{pointer_prefix}/id",
            fix_suggestion="Add a unique string `id:` field to the task.",
        )
    if task_id in seen_ids:
        raise InvalidSkillBenchmarkTasksError(
            f"duplicate task id {task_id!r} at index {idx}",
            file_path=file_path,
            field_name=f"{pointer_prefix}/id",
            fix_suggestion=f"Each task must have a unique `id`. Rename the duplicate '{task_id}'.",
        )
    seen_ids.add(task_id)

    prompt = raw_task.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise InvalidSkillBenchmarkTasksError(
            f"task '{task_id}' is missing required non-empty string field `prompt`",
            file_path=file_path,
            field_name=f"{pointer_prefix}/prompt",
            fix_suggestion="Add a non-empty string `prompt:` field to the task.",
        )

    has_expected = "expected_content" in raw_task and raw_task.get("expected_content") is not None
    has_rubric = "rubric" in raw_task and raw_task.get("rubric") is not None

    if has_expected and has_rubric:
        raise InvalidSkillBenchmarkTasksError(
            f"task '{task_id}' declares BOTH `expected_content` and `rubric`; exactly one grading mode is allowed",
            file_path=file_path,
            field_name=f"{pointer_prefix}",
            fix_suggestion="Keep either `expected_content:` OR `rubric:` on the task, not both.",
        )

    if has_expected:
        expected_raw = raw_task.get("expected_content")
        if not isinstance(expected_raw, list) or len(expected_raw) == 0:
            raise InvalidSkillBenchmarkTasksError(
                f"task '{task_id}' field `expected_content` must be a non-empty list of strings",
                file_path=file_path,
                field_name=f"{pointer_prefix}/expected_content",
                fix_suggestion="Provide `expected_content:` as a non-empty list of substrings to match.",
            )
        for j, item in enumerate(expected_raw):
            if not isinstance(item, str) or not item:
                raise InvalidSkillBenchmarkTasksError(
                    f"task '{task_id}' `expected_content[{j}]` must be a non-empty string; got {item!r}",
                    file_path=file_path,
                    field_name=f"{pointer_prefix}/expected_content/{j}",
                    fix_suggestion="Each `expected_content` entry must be a non-empty substring string.",
                )
        return SkillBenchmarkTask(
            id=task_id, prompt=prompt, expected_content=tuple(expected_raw), rubric_path=None
        )

    if has_rubric:
        rubric = raw_task.get("rubric")
        if not isinstance(rubric, str) or not rubric:
            raise InvalidSkillBenchmarkTasksError(
                f"task '{task_id}' field `rubric` must be a non-empty string path; got {rubric!r}",
                file_path=file_path,
                field_name=f"{pointer_prefix}/rubric",
                fix_suggestion="Set `rubric:` to a path to a judge rubric `.md` file.",
            )
        return SkillBenchmarkTask(id=task_id, prompt=prompt, expected_content=None, rubric_path=rubric)

    # No per-task grading mode → fall back to the file-level default rubric.
    if default_rubric is not None:
        return SkillBenchmarkTask(id=task_id, prompt=prompt, expected_content=None, rubric_path=default_rubric)

    raise InvalidSkillBenchmarkTasksError(
        f"task '{task_id}' declares no grading mode (`expected_content` or `rubric`) and there is no `defaults.rubric`",
        file_path=file_path,
        field_name=f"{pointer_prefix}",
        fix_suggestion="Add `expected_content:` or `rubric:` to the task, or set a file-level `defaults.rubric`.",
    )


# --------------------------------------------------------------------------- #
# Prompt-context skill delivery (design D2)                                    #
# --------------------------------------------------------------------------- #


def _read_skill_content(skill_path: str | Path) -> str:
    """Read a skill `.md` file's raw content (frontmatter + body) for injection."""
    return Path(skill_path).read_text(encoding="utf-8")


def compose_arm_prompt(task_prompt: str, skill_content: str | None) -> str:
    """Compose the trial prompt for one arm (design D2 — `prompt_injected`).

    For a skill arm, the skill's raw content is prepended inside a clearly
    delimited block. For the no-skill baseline (`skill_content is None`), the
    bare task prompt is returned so the two arms differ ONLY in skill
    availability.
    """
    if skill_content is None:
        return task_prompt
    return (
        "You have the following skill available. Use it if it is relevant to the task.\n"
        "----- BEGIN SKILL -----\n"
        f"{skill_content.strip()}\n"
        "----- END SKILL -----\n\n"
        f"{task_prompt}"
    )


# --------------------------------------------------------------------------- #
# Raw trial execution (design D2)                                              #
# --------------------------------------------------------------------------- #


@dataclass
class _RawTrial:
    """A single executed adapter run, pre-grading (internal accumulator).

    ``error`` is ``None`` for a clean run; when the per-trial adapter ``run()``
    RAISES at runtime it carries the string reason and the trial is recorded as
    a non-passing failed trial (codex MED) rather than aborting the benchmark.
    """

    arm: str
    task: SkillBenchmarkTask
    trial_index: int
    response_text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    error: str | None = None


def _run_arm(
    *,
    arm: str,
    skill_content: str | None,
    tasks: list[SkillBenchmarkTask],
    adapter: str,
    model: str | None,
    trials: int,
    extra_adapter_kwargs: dict[str, Any],
    cost_meter: _CostMeter,
) -> list[_RawTrial]:
    """Execute one arm: N tasks x `trials` adapter runs (design D2).

    Mirrors `run_single_adapter_skill_discoverability`'s adapter-per-trial
    construction. The skill content (or None for the no-skill baseline) is
    injected identically for every trial in this arm.

    Adapter resolution (`get_adapter`) happens ONCE up front — an unresolvable
    adapter is a setup/config error that fails LOUD before any trial. A runtime
    error raised by a per-trial `run()` is caught and recorded as a failed
    (non-passing) `_RawTrial` so the completed trials' evidence survives and
    every trial stays auditable (codex MED). Budget breaches
    (`CostExceededError` from the cost meter) propagate — they are NOT swallowed.
    """
    adapter_cls = get_adapter(adapter)
    ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
    if model is not None:
        ctor_kwargs["model"] = model

    raw: list[_RawTrial] = []
    for task in tasks:
        prompt = compose_arm_prompt(task.prompt, skill_content)
        for trial_index in range(trials):
            adapter_instance = adapter_cls(**ctor_kwargs)
            try:
                result: AgentRunResult = adapter_instance.run(prompt)
            except Exception as exc:  # noqa: BLE001 — record + continue per-trial
                # Runtime execution error for THIS trial: record a failed,
                # non-passing trial and keep going (design: evidence-bearing
                # fan-out). Setup/config errors already failed loud upstream.
                raw.append(
                    _RawTrial(
                        arm=arm,
                        task=task,
                        trial_index=trial_index,
                        response_text="",
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd=0.0,
                        latency_seconds=0.0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            # Account for real adapter spend; raises CostExceededError on breach.
            cost_meter.add(result.cost_usd, where=f"{arm} adapter run (task {task.id!r}, trial {trial_index})")
            raw.append(
                _RawTrial(
                    arm=arm,
                    task=task,
                    trial_index=trial_index,
                    response_text=result.response_text,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    cost_usd=result.cost_usd,
                    latency_seconds=result.latency_seconds,
                )
            )
    return raw


# --------------------------------------------------------------------------- #
# Grading (design D3 deterministic + D4 blind judge)                          #
# --------------------------------------------------------------------------- #


def grade_expected_content(response_text: str, expected: tuple[str, ...]) -> bool:
    """Deterministic grading: pass iff ALL substrings appear (case-insensitive)."""
    haystack = response_text.lower()
    return all(sub.lower() in haystack for sub in expected)


@dataclass
class _GradedTrial:
    """A raw trial plus its grading outcome + blinding id (internal)."""

    raw: _RawTrial
    blinded_grading_id: str
    passed: bool
    judge_score: float | None
    judge_reasoning: str | None


def _blinded_ids(n: int, seed: int) -> list[str]:
    """Deterministic opaque grading ids (`g-<hex>`); carry NO arm/task info."""
    rng = random.Random(f"blind-ids:{seed}")
    return [f"g-{rng.getrandbits(48):012x}" for _ in range(n)]


def _grade_all(
    raw_trials: list[_RawTrial],
    *,
    seed: int,
    judge_adapter: str,
    judge_model: str | None,
    judge_adapter_kwargs: dict[str, Any],
    cost_meter: _CostMeter,
) -> tuple[list[_GradedTrial], float, dict[str, Any]]:
    """Grade every trial; judge-graded trials go through a blind interleaved queue.

    Returns `(graded_trials, judge_cost_usd, blinding_record)`.

    Blinding protocol (design D4):
      - Every trial gets an opaque blinded grading id (no arm/task encoded).
      - The judge-graded subset is graded in a seed-shuffled order that
        interleaves both arms (so a stateful judge cannot correlate drift with
        arm).
      - The composed judge prompt carries ONLY rubric + task prompt +
        `response_text` — no arm label, no skill name added by the harness.
      - The grading order (blinded ids) is recorded for post-hoc audit.
    """
    blinded_ids = _blinded_ids(len(raw_trials), seed)
    graded: list[_GradedTrial | None] = [None] * len(raw_trials)

    # Deterministic grading for `expected_content` trials (trivially blind —
    # no LLM sees anything). Failed trials (adapter raised at runtime) are
    # recorded as non-passing WITHOUT invoking the judge — there is no response
    # to grade, and paying for a judge call on an empty response would be waste.
    judge_indices: list[int] = []
    for i, rt in enumerate(raw_trials):
        if rt.error is not None:
            graded[i] = _GradedTrial(
                raw=rt, blinded_grading_id=blinded_ids[i], passed=False, judge_score=None, judge_reasoning=None
            )
        elif rt.task.expected_content is not None:
            passed = grade_expected_content(rt.response_text, rt.task.expected_content)
            graded[i] = _GradedTrial(
                raw=rt, blinded_grading_id=blinded_ids[i], passed=passed, judge_score=None, judge_reasoning=None
            )
        else:
            judge_indices.append(i)

    judge_cost = 0.0
    grading_order: list[str] = []

    if judge_indices:
        # Seed-shuffle the judge-graded subset so both arms interleave.
        shuffle_rng = random.Random(f"grading-order:{seed}")
        shuffled = list(judge_indices)
        shuffle_rng.shuffle(shuffled)

        from AgentEval.judge.library import _compose_judge_prompt, _parse_judge_response
        from AgentEval.judge.rubric import load_rubric
        from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

        rubric_cache: dict[str, Any] = {}
        judge_cls = get_adapter(judge_adapter)
        judge_ctor_kwargs: dict[str, Any] = dict(judge_adapter_kwargs)
        if judge_model is not None:
            judge_ctor_kwargs["model"] = judge_model

        for i in shuffled:
            rt = raw_trials[i]
            rubric_path = rt.task.rubric_path
            assert rubric_path is not None  # judge trials always carry a rubric
            if rubric_path not in rubric_cache:
                rubric_cache[rubric_path] = load_rubric(rubric_path)
            rubric = rubric_cache[rubric_path]

            # Synthesize a judge-scoreable result from the trial output ONLY.
            synth = AgentRunResult(
                response_text=rt.response_text,
                tool_calls=[],
                usage=Usage(input_tokens=0, output_tokens=0),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id=f"benchmark-grade-{blinded_ids[i]}",
            )
            # Blind prompt: rubric + task prompt + response_text ONLY. The task
            # prompt is added as a neutral `# Task` section (NO arm label, NO
            # skill name injected by the harness).
            judge_prompt = _compose_judge_prompt(rubric, synth, extra_sections=(("Task", rt.task.prompt),))
            try:
                judge_run = judge_cls(**judge_ctor_kwargs).run(prompt=judge_prompt)
                score = _parse_judge_response(judge_run, rubric)
            except Exception as exc:  # noqa: BLE001 — record + continue per-trial
                # Runtime judge-execution error: record this trial as non-passing
                # failed evidence (mirrors the adapter-arm failure path) rather
                # than aborting the whole benchmark. `rt.error` is surfaced in
                # the evidence so the failed grading is auditable.
                rt.error = f"judge {type(exc).__name__}: {exc}"
                graded[i] = _GradedTrial(
                    raw=rt, blinded_grading_id=blinded_ids[i], passed=False, judge_score=None, judge_reasoning=None
                )
                grading_order.append(blinded_ids[i])
                continue

            judge_cost += score.cost_usd
            # Account for real judge spend; raises CostExceededError on breach.
            cost_meter.add(score.cost_usd, where=f"judge grading (task {rt.task.id!r}, {rt.arm} arm)")
            graded[i] = _GradedTrial(
                raw=rt,
                blinded_grading_id=blinded_ids[i],
                passed=score.pass_threshold_met,
                judge_score=score.numeric_score,
                judge_reasoning=score.reasoning,
            )
            grading_order.append(blinded_ids[i])

    blinding_record: dict[str, Any] = {
        "mode": "arm_label_blind",
        "seed": seed,
        "grading_order": tuple(grading_order),
    }
    # `graded` is now fully populated (every index assigned).
    return [g for g in graded if g is not None], judge_cost, blinding_record


# --------------------------------------------------------------------------- #
# Arm summary assembly                                                         #
# --------------------------------------------------------------------------- #


def _build_arm_summary(
    *,
    arm: str,
    skill_path: str | None,
    tasks: list[SkillBenchmarkTask],
    graded: list[_GradedTrial],
    trials: int,
) -> SkillBenchmarkArmSummary:
    """Aggregate one arm's graded trials into a `SkillBenchmarkArmSummary`."""
    arm_graded = [g for g in graded if g.raw.arm == arm]
    per_task_pass_rates: dict[str, float] = {}
    for task in tasks:
        task_trials = [g for g in arm_graded if g.raw.task.id == task.id]
        passed = sum(1 for g in task_trials if g.passed)
        per_task_pass_rates[task.id] = passed / len(task_trials) if task_trials else 0.0

    trials_run = len(arm_graded)
    total_passed = sum(1 for g in arm_graded if g.passed)
    pass_rate = total_passed / trials_run if trials_run > 0 else 0.0
    total_tokens = sum(g.raw.input_tokens + g.raw.output_tokens for g in arm_graded)
    mean_tokens = total_tokens / trials_run if trials_run > 0 else 0.0
    total_elapsed = sum(g.raw.latency_seconds for g in arm_graded)
    total_cost = sum(g.raw.cost_usd for g in arm_graded)

    return SkillBenchmarkArmSummary(
        arm=arm,
        skill_path=skill_path,
        pass_rate=pass_rate,
        per_task_pass_rates=per_task_pass_rates,
        total_tokens=total_tokens,
        mean_tokens=mean_tokens,
        total_elapsed_seconds=total_elapsed,
        total_cost_usd=total_cost,
        trials_run=trials_run,
    )


# --------------------------------------------------------------------------- #
# Verdict (design D6)                                                          #
# --------------------------------------------------------------------------- #


def compute_benchmark_verdict(
    *,
    candidate_pass_rate: float,
    baseline_pass_rate: float,
    p_value: float,
    alpha: float,
    baseline_is_none: bool,
    obsolescence_threshold: float,
    cliffs_delta: float,
) -> str:
    """Compute the closed-set verdict (design D6).

    Rule (single documented source of truth):
      - `skill_improves`  — candidate significantly better (p < alpha, favorable).
      - `skill_regresses` — candidate significantly worse (p < alpha, unfavorable).
      - `skill_unnecessary` — ONLY when `baseline=none` and the baseline pass
        rate is >= `obsolescence_threshold` AND there is no significant
        candidate improvement. Checked AFTER `skill_improves` so a genuinely
        significant gain over an already-high baseline still reads
        `skill_improves` (spec scenario "improvement wins over obsolescence").
      - `no_significant_difference` — everything else.

    **Direction source (codex HIGH):** the significant-direction split
    (`skill_improves` vs `skill_regresses`) is derived from the SIGNED effect
    of the SAME test that decides significance — Cliff's delta over the per-task
    pass-rate distributions (`> 0` ⇒ candidate distributionally higher,
    favorable; `< 0` ⇒ candidate lower, unfavorable). It is NOT derived from the
    aggregate arm pass rates: a few large candidate wins can raise the aggregate
    mean while the candidate is significantly WORSE on most tasks, so an
    aggregate-mean split can contradict the significance test. The aggregate
    pass rate is retained ONLY for the headline `pass_rate_delta` and the
    obsolescence (`skill_unnecessary`) threshold.

    Token/time deltas do NOT affect the verdict (design D6).
    """
    import math

    significant = (not math.isnan(p_value)) and p_value < alpha
    if significant and cliffs_delta > 0:
        return "skill_improves"
    if significant and cliffs_delta < 0:
        return "skill_regresses"
    if baseline_is_none and baseline_pass_rate >= obsolescence_threshold:
        return "skill_unnecessary"
    return "no_significant_difference"


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #


def run_skill_benchmark(
    *,
    skill: str | Path,
    tasks: list[SkillBenchmarkTask],
    baseline: str,
    trials: int,
    adapter: str,
    model: str | None,
    seed: int,
    alpha: float,
    obsolescence_threshold: float,
    judge_adapter: str,
    judge_model: str | None,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
    max_cost_usd: float | None = None,
) -> SkillBenchmarkComparisonResult:
    """Run the full two-arm benchmark (design D1-D8).

    Called by `SkillsLibrary.compare_against_baseline` INSIDE the
    `@guarded_fanout` budget scope so adapter + judge spend share one
    `max_cost_usd` cap (design D8). Assumes the caller already validated args +
    the `[agenteval-advanced]` extras gate.

    `max_cost_usd` is the effective cumulative-cost cap covering BOTH arms AND
    judge grading (codex HIGH). The `@guarded_fanout` cost meter reads a 0.0
    Phase-1 stub, so this function enforces the budget explicitly via a
    `_CostMeter` that sums the real adapter + judge per-call costs and raises
    `CostExceededError` on breach. `None` = no enforcement.
    """
    from AgentEval._heatmap.models import CohortHeatmap
    from AgentEval.stats.bootstrap import compute_bootstrap_ci
    from AgentEval.stats.cliffs_delta import compute_cliff_delta
    from AgentEval.stats.mannwhitney import compute_mann_whitney_u

    baseline_is_none = baseline == "none"
    candidate_content = _read_skill_content(skill)
    baseline_content = None if baseline_is_none else _read_skill_content(baseline)
    baseline_skill_path = None if baseline_is_none else str(baseline)

    # One cumulative-cost meter shared across BOTH arms AND judge grading
    # (design D8; codex HIGH). Enforces the effective `max_cost_usd` explicitly
    # because the guardrail cost source is a Phase-1 0.0 stub.
    cost_meter = _CostMeter(max_cost_usd)

    # Execute both arms (candidate first, then baseline — deterministic build
    # order; the judge grading queue re-shuffles this so grading is blind).
    candidate_raw = _run_arm(
        arm="candidate",
        skill_content=candidate_content,
        tasks=tasks,
        adapter=adapter,
        model=model,
        trials=trials,
        extra_adapter_kwargs=extra_adapter_kwargs,
        cost_meter=cost_meter,
    )
    baseline_raw = _run_arm(
        arm="baseline",
        skill_content=baseline_content,
        tasks=tasks,
        adapter=adapter,
        model=model,
        trials=trials,
        extra_adapter_kwargs=extra_adapter_kwargs,
        cost_meter=cost_meter,
    )
    all_raw = candidate_raw + baseline_raw

    graded, judge_cost, blinding_record = _grade_all(
        all_raw,
        seed=seed,
        judge_adapter=judge_adapter,
        judge_model=judge_model,
        judge_adapter_kwargs=extra_adapter_kwargs,
        cost_meter=cost_meter,
    )

    candidate_summary = _build_arm_summary(
        arm="candidate", skill_path=str(skill), tasks=tasks, graded=graded, trials=trials
    )
    baseline_summary = _build_arm_summary(
        arm="baseline", skill_path=baseline_skill_path, tasks=tasks, graded=graded, trials=trials
    )

    # Statistics over the two arms' per-task pass-rate distributions (design D5).
    candidate_rates = [candidate_summary.per_task_pass_rates[t.id] for t in tasks]
    baseline_rates = [baseline_summary.per_task_pass_rates[t.id] for t in tasks]
    mann_whitney = compute_mann_whitney_u(candidate_rates, baseline_rates)
    cliffs = compute_cliff_delta(candidate_rates, baseline_rates)
    # Percentile bootstrap CI on the per-task pass-rate delta (candidate − baseline).
    delta_samples = [c - b for c, b in zip(candidate_rates, baseline_rates, strict=True)]
    bootstrap_ci = compute_bootstrap_ci(
        delta_samples, statistics.mean, alpha=alpha, n_resamples=_BOOTSTRAP_RESAMPLES, seed=seed
    )

    pass_rate_delta = candidate_summary.pass_rate - baseline_summary.pass_rate
    verdict = compute_benchmark_verdict(
        candidate_pass_rate=candidate_summary.pass_rate,
        baseline_pass_rate=baseline_summary.pass_rate,
        p_value=mann_whitney.p_value,
        alpha=alpha,
        baseline_is_none=baseline_is_none,
        obsolescence_threshold=obsolescence_threshold,
        cliffs_delta=cliffs,
    )

    evidence = _build_evidence(graded)

    # Heatmap via a shim (mirrors `from_skill_comparison`'s pattern so the
    # constructor reads finalized arm summaries).
    class _BenchmarkShim:
        pass

    shim = _BenchmarkShim()
    shim.candidate = candidate_summary  # type: ignore[attr-defined]
    shim.baseline = baseline_summary  # type: ignore[attr-defined]
    shim.task_order = tuple(t.id for t in tasks)  # type: ignore[attr-defined]
    heatmap = CohortHeatmap.from_skill_benchmark(shim)

    total_adapter_cost = candidate_summary.total_cost_usd + baseline_summary.total_cost_usd
    total_runtime = time.perf_counter() - t_start

    return SkillBenchmarkComparisonResult(
        candidate=candidate_summary,
        baseline=baseline_summary,
        pass_rate_delta=pass_rate_delta,
        mann_whitney=mann_whitney,
        cliffs_delta=cliffs,
        bootstrap_ci=bootstrap_ci,
        verdict=verdict,
        skill_delivery="prompt_injected",
        blinding=blinding_record,
        evidence=evidence,
        heatmap=heatmap,
        total_runtime_seconds=total_runtime,
        total_cost_usd=total_adapter_cost + judge_cost,
        judge_cost_usd=judge_cost,
    )


def _build_evidence(graded: list[_GradedTrial]) -> tuple[SkillBenchmarkTrialEvidence, ...]:
    """Project graded trials into frozen evidence entries (redaction applied)."""
    evidence: list[SkillBenchmarkTrialEvidence] = []
    for g in graded:
        excerpt = redact(g.raw.response_text)[:_EXCERPT_MAX_CHARS]
        evidence.append(
            SkillBenchmarkTrialEvidence(
                task_id=g.raw.task.id,
                arm=g.raw.arm,
                trial_index=g.raw.trial_index,
                blinded_grading_id=g.blinded_grading_id,
                passed=g.passed,
                grading_mode=g.raw.task.grading_mode,
                judge_score=g.judge_score,
                judge_reasoning=g.judge_reasoning,
                response_excerpt=excerpt,
                input_tokens=g.raw.input_tokens,
                output_tokens=g.raw.output_tokens,
                cost_usd=g.raw.cost_usd,
                latency_seconds=g.raw.latency_seconds,
                error=g.raw.error,
            )
        )
    return tuple(evidence)
