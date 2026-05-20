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

"""End-to-end Listener + RunManifest sidecar integration test (Story 5.3).

Story 5.3 code-review 2-way HIGH-C fix 2026-05-20 (Edge-cases H3 + Codex MED):
pre-edit unit tests covered the `EvidenceBlockEmitter` + `RunManifestEmitter`
in isolation but no test exercised the full
`start_test → adapter.run() → record_active_run_metadata → end_test → sidecar
appears on disk` flow. That's exactly why HIGH-B (JSONL backend silently
skipping the manifest) was a real Story 5.3 regression. This module pins
the integration contract.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.providers.base import ChatResponse, ProviderUsage
from AgentEval.providers.mock import MockProvider
from AgentEval.telemetry.listener import Listener, _active_listeners


@pytest.fixture(autouse=True)
def isolated_tracer_state() -> Iterator[None]:
    """Fully reset OTel + agenteval listener state pre + post each test."""
    snapshot_listeners = list(_active_listeners)
    _active_listeners[:] = []
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()
    yield
    _active_listeners[:] = snapshot_listeners
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()


class _MockData:
    def __init__(self, *, full_name: str, parent: Any | None = None) -> None:
        self.full_name = full_name
        self.parent = parent


def _mock_provider() -> MockProvider:
    return MockProvider(
        responses=[
            ChatResponse(
                text="hello",
                tool_calls=[],
                usage=ProviderUsage(input_tokens=10, output_tokens=5),
                cost_usd=0.001,
            )
        ]
    )


def test_e2e_listener_emits_manifest_sidecar_with_adapter_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full flow: start_suite → start_test → adapter.run() → end_test → sidecar exists.

    Story 5.3 code-review 2-way HIGH-C fix 2026-05-20 (Edge-cases H3 + Codex
    MED): no prior test exercised the full Listener + adapter integration
    path for the RunManifest sidecar. This test fills that gap.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="MySuite")
    test = _MockData(full_name="MySuite.test_e2e", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Real adapter call — should call record_active_run_metadata internally.
    adapter = GenericAdapter(provider_instance=_mock_provider())
    adapter.run("hi")
    listener.end_test(test, None)
    # HIGH-E path: PRD FR39 verbatim manifest__<suite>__<test>.json (NOT run-manifest__).
    expected_path = tmp_path / "agenteval" / "manifest__MySuite__MySuite.test_e2e.json"
    assert expected_path.exists(), (
        f"HIGH-C regression: full Listener + adapter integration must produce a manifest sidecar at {expected_path}"
    )
    payload = json.loads(expected_path.read_text(encoding="utf-8"))
    # Adapter metadata flowed through record_active_run_metadata → record_run_metadata.
    assert payload.get("adapter_name") == "GenericAdapter"
    assert payload.get("total_cost_usd") == 0.001
    assert payload.get("completeness") == "complete"
    assert len(payload.get("prompt_hashes", [])) == 1


def test_e2e_listener_emits_manifest_sidecar_even_with_jsonl_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.3 code-review 3-way HIGH-B fix 2026-05-20 (Codex empirical +
    Edge-cases E2 + Blind MED-2): pre-edit `flush_test() is None` (legitimate
    "no spans captured" case) caused early-return BEFORE sidecar emission.
    Codex empirically reproduced `memory exists True; jsonl exists False`.
    Now the listener always emits the manifest regardless of JSONL outcome.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.test_jsonl_no_spans", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Adapter call — no spans emitted (mock provider doesn't drive OTel).
    adapter = GenericAdapter(provider_instance=_mock_provider())
    adapter.run("hi")
    listener.end_test(test, None)
    # HIGH-B regression: sidecar must exist even when JSONL backend skipped
    # (zero-spans case → flush_test returned None pre-fix → sidecar suppressed).
    expected_path = tmp_path / "agenteval" / "manifest__S__S.test_jsonl_no_spans.json"
    assert expected_path.exists(), (
        "HIGH-B regression: sidecar must be written even when JSONL backend returns None (zero-spans no-phantom case)"
    )


def test_e2e_multi_adapter_metadata_merge_does_not_clobber_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.3 code-review 2-way HIGH-D fix 2026-05-20 (Blind H4 + Codex
    empirical): pre-edit last-wins merge clobbered adapter_name + model
    when a second adapter passed None. Now skip-None for scalars + sum cost.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.test_multi", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # First adapter: real model name + cost.
    listener.record_run_metadata(
        adapter_name="GenericAdapter",
        model="gpt-4o",
        total_cost_usd=0.01,
        prompt_hashes=["a" * 64],
    )
    # Second adapter: model=None (would clobber pre-fix); cost adds.
    listener.record_run_metadata(
        adapter_name="ClaudeCodeCLI",
        model=None,
        total_cost_usd=0.005,
        prompt_hashes=["b" * 64],
    )
    listener.end_test(test, None)
    expected_path = tmp_path / "agenteval" / "manifest__S__S.test_multi.json"
    assert expected_path.exists()
    payload = json.loads(expected_path.read_text(encoding="utf-8"))
    # HIGH-D regression: `model` not clobbered to None; cost summed.
    assert payload["model"] == "gpt-4o", (
        f"HIGH-D regression: model clobbered to {payload.get('model')!r}; expected 'gpt-4o' (skip-None semantics)"
    )
    # adapter_name last-wins is intentional (most-recent identifier).
    assert payload["adapter_name"] == "ClaudeCodeCLI"
    # total_cost_usd is sum of both calls.
    assert abs(payload["total_cost_usd"] - 0.015) < 1e-9
    # Both prompt hashes preserved.
    assert payload["prompt_hashes"] == ["a" * 64, "b" * 64]
