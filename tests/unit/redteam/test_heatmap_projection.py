# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for probe-result → cohort-heatmap projection (add-red-team-probes task 6.1)."""

from __future__ import annotations

from AgentEval._heatmap.models import CohortHeatmap
from AgentEval.redteam.library import RedTeamLibrary


def test_probe_results_project_to_category_by_model_grid(rt: RedTeamLibrary) -> None:
    # Two categories × two adapters, opposite safety postures.
    results = []
    for category in ("prompt_injection", "jailbreak"):
        results += rt.run_probe(adapter="refusing-mock", category=category, probe="all")
        results += rt.run_probe(adapter="compliant-mock", category=category, probe="all")

    heatmap = CohortHeatmap.from_probe_results(results)
    grid = heatmap.as_dict()

    # Rows = categories, columns = adapters.
    assert set(heatmap.tasks) == {"prompt_injection", "jailbreak"}
    assert set(heatmap.models) == {"refusing-mock", "compliant-mock"}
    # Cell value = ASR (compliance fraction). Refusing → 0.0, complying → 1.0.
    assert grid["prompt_injection"]["refusing-mock"] == 0.0
    assert grid["prompt_injection"]["compliant-mock"] == 1.0
    assert grid["jailbreak"]["refusing-mock"] == 0.0
    assert grid["jailbreak"]["compliant-mock"] == 1.0
    # Reuses the existing renderer — no red-team-specific report surface.
    assert isinstance(heatmap.as_ascii(), str)


def test_empty_probe_results_project_to_empty_heatmap() -> None:
    heatmap = CohortHeatmap.from_probe_results([])
    assert heatmap.tasks == ()
    assert heatmap.models == ()
    assert heatmap.as_ascii() == "(empty heatmap)"


# --------------------------------------------------------------------------- #
# MED fix — high ASR must NOT render in the success/green color
# --------------------------------------------------------------------------- #

_SUCCESS_GREEN = "#22c55e"  # the Pass@k high-success color
_WORST_RED = "#ef4444"  # the ASR high-compliance (worst) color


def test_high_asr_cell_not_rendered_in_success_green(rt: RedTeamLibrary) -> None:
    """A fully-complying agent (ASR=1.0) is the WORST case; it must render red, not green."""
    results = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="all")
    heatmap = CohortHeatmap.from_probe_results(results)
    assert heatmap.higher_is_worse is True
    html = heatmap.as_html()
    # The worst cell (ASR=1.0) must carry the reversed-palette red, never the
    # Pass@k success green.
    assert f"background-color: {_WORST_RED}" in html
    assert f"background-color: {_SUCCESS_GREEN}" not in html


def test_low_asr_cell_rendered_in_green(rt: RedTeamLibrary) -> None:
    """A fully-refusing agent (ASR=0.0) is the SAFE case; it renders green."""
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    heatmap = CohortHeatmap.from_probe_results(results)
    html = heatmap.as_html()
    assert f"background-color: {_SUCCESS_GREEN}" in html


def test_passk_heatmap_polarity_unchanged() -> None:
    """The Pass@k projection keeps higher=better=green (no regression)."""
    hm = CohortHeatmap(tasks=("t1",), models=("m1",), cells=(("t1", "m1", 1.0),))
    assert hm.higher_is_worse is False
    assert f"background-color: {_SUCCESS_GREEN}" in hm.as_html()
