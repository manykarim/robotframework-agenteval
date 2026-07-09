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

"""Arm-execution + grading engine tests (add-skill-ab-benchmark / Task 2.4).

Covers: two-arm run counts (2 x N x trials), prompt-injection presence/absence
per arm, expected_content pass/fail, judge pass_threshold_met mapping,
judge-prompt blindness (candidate vs baseline prompts differ only in
response_text; no harness-added arm label or skill name), and deterministic
shuffle for a fixed seed.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("scipy")
pytest.importorskip("numpy")

from AgentEval._kernel import discovery  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.skills._benchmark import (  # noqa: E402
    compose_arm_prompt,
    grade_expected_content,
    load_skill_benchmark_tasks,
    run_skill_benchmark,
)

from ._benchmark_helpers import (  # noqa: E402
    SKILL_MARKER,
    make_conditional_stub,
    make_content_sensitive_judge,
    make_judge_stub,
    make_recording_stub,
)

_SKILL = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
_TASKS_EC = Path(__file__).parent.parent.parent / "fixtures" / "benchmark" / "tasks-expected-content.yaml"


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


def _run(adapter: str, *, judge_adapter: str = "generic", tasks_path: Path = _TASKS_EC, trials: int = 2, **kw):
    tasks = load_skill_benchmark_tasks(tasks_path)
    return run_skill_benchmark(
        skill=str(_SKILL),
        tasks=tasks,
        baseline="none",
        trials=trials,
        adapter=adapter,
        model=None,
        seed=42,
        alpha=0.05,
        obsolescence_threshold=0.9,
        judge_adapter=judge_adapter,
        judge_model=None,
        extra_adapter_kwargs={},
        t_start=0.0,
        **kw,
    )


# --------------------------------------------------------------------------- #
# Deterministic grading + prompt composition units                            #
# --------------------------------------------------------------------------- #


def test_grade_expected_content_all_present() -> None:
    assert grade_expected_content("The ROOT CAUSE was X", ("root cause",)) is True
    assert grade_expected_content("has one", ("one", "two")) is False


def test_compose_arm_prompt_injects_and_bare() -> None:
    injected = compose_arm_prompt("do a thing", "SKILL BODY")
    assert SKILL_MARKER in injected
    assert "SKILL BODY" in injected
    assert "do a thing" in injected
    bare = compose_arm_prompt("do a thing", None)
    assert bare == "do a thing"
    assert SKILL_MARKER not in bare


# --------------------------------------------------------------------------- #
# Two-arm run counts + injection presence/absence                             #
# --------------------------------------------------------------------------- #


def test_two_arm_run_counts_2x_n_trials() -> None:
    register_adapter("eng_cnt", make_conditional_stub(with_skill_text="root cause", without_skill_text="nope"))
    result = _run("eng_cnt", trials=3)
    # 4 tasks x 3 trials x 2 arms = 24 evidence entries.
    assert len(result.evidence) == 24
    assert result.candidate.trials_run == 12
    assert result.baseline.trials_run == 12


def test_candidate_arm_sees_skill_baseline_does_not() -> None:
    """baseline=none arm sends bare prompts; candidate arm injects the skill."""
    sink: list[str] = []
    register_adapter("eng_rec", make_recording_stub(sink, "root cause"))
    _run("eng_rec", trials=1)
    # 4 candidate prompts (with marker) + 4 baseline prompts (bare) = 8.
    assert len(sink) == 8
    with_marker = [p for p in sink if SKILL_MARKER in p]
    without_marker = [p for p in sink if SKILL_MARKER not in p]
    assert len(with_marker) == 4  # candidate arm
    assert len(without_marker) == 4  # baseline arm (no-skill)


def test_expected_content_pass_fail_split() -> None:
    """Candidate (skill helps) passes; baseline (no skill) fails."""
    register_adapter(
        "eng_split",
        make_conditional_stub(
            with_skill_text="the root cause is a runbook table order id",  # matches all task substrings
            without_skill_text="i don't know",
        ),
    )
    result = _run("eng_split", trials=3)
    assert result.candidate.pass_rate == pytest.approx(1.0)
    assert result.baseline.pass_rate == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Per-trial failure isolation (codex MED)                                     #
# --------------------------------------------------------------------------- #


def test_failed_trial_recorded_as_non_passing_evidence() -> None:
    """codex MED regression: one runtime adapter failure does NOT abort the benchmark.

    A single trial that raises must be recorded as a FAILED, non-passing evidence
    entry (with an `error` reason) while every other completed trial survives —
    the benchmark still returns a `SkillBenchmarkComparisonResult`.
    """
    from AgentEval.skills.types import SkillBenchmarkComparisonResult

    from ._benchmark_helpers import make_flaky_stub

    register_adapter(
        "eng_flaky",
        make_flaky_stub(fail_on_call=2, text="root cause runbook table order id"),
    )
    result = _run("eng_flaky", trials=3)
    assert isinstance(result, SkillBenchmarkComparisonResult)

    # 4 tasks x 3 trials x 2 arms = 24 evidence entries — NONE lost to the abort.
    assert len(result.evidence) == 24
    failed = [e for e in result.evidence if e.error is not None]
    assert len(failed) == 1
    assert failed[0].passed is False  # counted as NON-passing
    assert failed[0].error is not None
    assert "RuntimeError" in failed[0].error
    # The other 23 trials executed cleanly and are still present.
    survivors = [e for e in result.evidence if e.error is None]
    assert len(survivors) == 23
    assert all(e.passed for e in survivors)


def test_unresolvable_adapter_still_fails_loud() -> None:
    """Setup/config error (unknown adapter) must NOT be swallowed as a failed trial."""
    from AgentEval.errors import AdapterDiscoveryError

    with pytest.raises(AdapterDiscoveryError):
        _run("eng_no_such_adapter", trials=1)


# --------------------------------------------------------------------------- #
# Judge grading + blindness                                                   #
# --------------------------------------------------------------------------- #


def test_judge_pass_threshold_met_mapping(tmp_path: Path) -> None:
    """A judge score >= threshold → passed; below → fail (rubric threshold 7.0)."""
    rubric = (Path(__file__).parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md").resolve()
    tasks_yaml = tmp_path / "j.yaml"
    tasks_yaml.write_text(f"defaults:\n  rubric: {rubric}\ntasks:\n  - id: t1\n    prompt: do it\n", encoding="utf-8")
    register_adapter("eng_j_adapter", make_conditional_stub(with_skill_text="ok", without_skill_text="ok"))
    register_adapter("eng_j_judge_pass", make_judge_stub(score=9.0))
    result = _run("eng_j_adapter", judge_adapter="eng_j_judge_pass", tasks_path=tasks_yaml, trials=2)
    # All judged trials scored 9.0 >= 7.0 → all pass.
    assert all(e.passed for e in result.evidence)
    assert all(e.grading_mode == "judge" for e in result.evidence)
    assert all(e.judge_score == 9.0 for e in result.evidence)
    assert all(e.judge_reasoning is not None for e in result.evidence)
    # Judge cost broken out (0.0 here) and included in total.
    assert result.judge_cost_usd == pytest.approx(0.0)


def test_judge_prompt_carries_no_arm_metadata(tmp_path: Path) -> None:
    """Judge prompts contain NO arm label + NO harness-injected skill name."""
    rubric = (Path(__file__).parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md").resolve()
    tasks_yaml = tmp_path / "j.yaml"
    tasks_yaml.write_text(
        f"defaults:\n  rubric: {rubric}\ntasks:\n  - id: t1\n    prompt: neutral task text\n",
        encoding="utf-8",
    )
    judge_prompts: list[str] = []
    # Adapter returns a NEUTRAL response with no skill name so the only place a
    # skill name could appear is if the harness leaked it — it must not.
    register_adapter(
        "eng_bl_adapter", make_conditional_stub(with_skill_text="neutral answer", without_skill_text="neutral answer")
    )
    register_adapter("eng_bl_judge", make_judge_stub(score=8.0, prompt_sink=judge_prompts))
    _run("eng_bl_adapter", judge_adapter="eng_bl_judge", tasks_path=tasks_yaml, trials=1)

    assert len(judge_prompts) == 2  # candidate + baseline, 1 task, 1 trial each
    for jp in judge_prompts:
        low = jp.lower()
        assert "candidate" not in low
        assert "baseline" not in low
        assert "with skill" not in low
        assert "without skill" not in low
        # The harness must not inject the skill name into the judge prompt.
        assert "example-search-skill" not in low
        assert SKILL_MARKER not in jp
        # But it MUST contain the rubric + the task prompt + the response.
        assert "neutral task text" in jp
        assert "neutral answer" in jp


def test_judge_prompts_differ_only_in_response_text(tmp_path: Path) -> None:
    """Same task, both arms same response → judge prompts are IDENTICAL.

    Proves the composed prompt carries no arm-varying content beyond the
    response section (spec scenario "differ ONLY in the response_text section").
    """
    rubric = (Path(__file__).parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md").resolve()
    tasks_yaml = tmp_path / "j.yaml"
    tasks_yaml.write_text(
        f"defaults:\n  rubric: {rubric}\ntasks:\n  - id: t1\n    prompt: identical task\n", encoding="utf-8"
    )
    judge_prompts: list[str] = []
    register_adapter("eng_id_adapter", make_conditional_stub(with_skill_text="same", without_skill_text="same"))
    register_adapter("eng_id_judge", make_judge_stub(score=8.0, prompt_sink=judge_prompts))
    _run("eng_id_adapter", judge_adapter="eng_id_judge", tasks_path=tasks_yaml, trials=1)
    assert len(judge_prompts) == 2
    assert judge_prompts[0] == judge_prompts[1]


def test_content_sensitive_judge_scores_via_response_only(tmp_path: Path) -> None:
    """A judge that keys off a response marker grades candidate > baseline.

    The differentiation flows ONLY through legitimate response content (never an
    arm label), demonstrating blind grading still discriminates real quality.
    """
    rubric = (Path(__file__).parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md").resolve()
    tasks_yaml = tmp_path / "j.yaml"
    tasks_yaml.write_text(
        f"defaults:\n  rubric: {rubric}\ntasks:\n  - id: t1\n    prompt: solve\n  - id: t2\n    prompt: solve2\n",
        encoding="utf-8",
    )
    register_adapter(
        "eng_cs_adapter",
        make_conditional_stub(with_skill_text="ANSWERED CORRECTLY", without_skill_text="i give up"),
    )
    register_adapter("eng_cs_judge", make_content_sensitive_judge(pass_marker="ANSWERED CORRECTLY"))
    result = _run("eng_cs_adapter", judge_adapter="eng_cs_judge", tasks_path=tasks_yaml, trials=3)
    assert result.candidate.pass_rate == pytest.approx(1.0)
    assert result.baseline.pass_rate == pytest.approx(0.0)


def test_grading_order_is_seed_shuffled_across_arms(tmp_path: Path) -> None:
    """Grading order interleaves both arms (not arm-A-then-arm-B) + is deterministic."""
    rubric = (Path(__file__).parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md").resolve()
    tasks_yaml = tmp_path / "j.yaml"
    tasks_yaml.write_text(
        f"defaults:\n  rubric: {rubric}\ntasks:\n" + "".join(f"  - id: t{i}\n    prompt: p{i}\n" for i in range(4)),
        encoding="utf-8",
    )
    register_adapter("eng_so_adapter", make_conditional_stub(with_skill_text="a", without_skill_text="a"))
    register_adapter("eng_so_judge", make_judge_stub(score=8.0))
    result = _run("eng_so_adapter", judge_adapter="eng_so_judge", tasks_path=tasks_yaml, trials=2)

    grading_order = result.blinding["grading_order"]
    # 4 tasks x 2 trials x 2 arms = 16 judged trials.
    assert len(grading_order) == 16
    # Map each blinded id → arm via the evidence.
    id_to_arm = {e.blinded_grading_id: e.arm for e in result.evidence}
    arms_in_order = [id_to_arm[gid] for gid in grading_order]
    # Not simply all-candidate-then-all-baseline.
    first_half = arms_in_order[:8]
    assert not (all(a == "candidate" for a in first_half)), "grading order not interleaved"

    # Determinism: a second identical run reproduces the same order.
    result2 = _run("eng_so_adapter", judge_adapter="eng_so_judge", tasks_path=tasks_yaml, trials=2)
    id_to_arm2 = {e.blinded_grading_id: e.arm for e in result2.evidence}
    arms_in_order2 = [id_to_arm2[gid] for gid in result2.blinding["grading_order"]]
    assert arms_in_order == arms_in_order2


def test_blinding_record_and_evidence_auditable(tmp_path: Path) -> None:
    """Blinding record exposes mode+seed; every evidence entry maps id → true arm."""
    register_adapter("eng_aud", make_conditional_stub(with_skill_text="root cause", without_skill_text="x"))
    result = _run("eng_aud", trials=2)
    assert result.blinding["mode"] == "arm_label_blind"
    assert result.blinding["seed"] == 42
    # Every evidence entry carries a blinded id + a true arm coordinate.
    for e in result.evidence:
        assert e.blinded_grading_id.startswith("g-")
        assert e.arm in ("candidate", "baseline")
    # Blinded ids are unique across all trials.
    ids = [e.blinded_grading_id for e in result.evidence]
    assert len(set(ids)) == len(ids)
