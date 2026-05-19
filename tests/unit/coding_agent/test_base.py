"""Unit tests for `src/AgentEval/coding_agent/base.py` (AC-1b.4.1 through AC-1b.4.10)."""

from __future__ import annotations

import dataclasses
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval import coding_agent as coding_agent_pkg
from AgentEval._kernel import discovery
from AgentEval.coding_agent import (
    AgentRunResult,
    CodingAgentAdapter,
    InProcessAdapter,
    SubprocessAdapter,
)
from AgentEval.coding_agent import base as base_module
from AgentEval.errors import (
    AgentEvalCompatError,
    AgentEvalError,
    UnsupportedBinaryVersionError,
)
from AgentEval.types import AgentRunMetadata, ToolCallTrace, Usage
from AgentEval.types import AgentRunResult as TypesAgentRunResult
from AgentEval.types import CodingAgentAdapter as TypesProtocol

# ============================================================ #
# AC-1b.4.1 + AC-1b.4.2 — Protocol identity + re-export        #
# ============================================================ #


def test_protocol_re_export_identity_through_package() -> None:
    """`AgentEval.coding_agent.CodingAgentAdapter` IS `AgentEval.types.CodingAgentAdapter`."""
    assert CodingAgentAdapter is TypesProtocol
    assert coding_agent_pkg.CodingAgentAdapter is TypesProtocol


def test_agent_run_result_re_export_identity_through_package() -> None:
    """`AgentEval.coding_agent.AgentRunResult` IS `AgentEval.types.AgentRunResult`."""
    assert AgentRunResult is TypesAgentRunResult
    assert coding_agent_pkg.AgentRunResult is TypesAgentRunResult


def test_protocol_is_runtime_checkable() -> None:
    """`@runtime_checkable` enables `isinstance(obj, CodingAgentAdapter)`."""

    class StubAdapter:
        name = "stub"
        version = "1.0"

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:  # noqa: ARG002
            raise NotImplementedError

    stub = StubAdapter()
    assert isinstance(stub, CodingAgentAdapter)


def test_protocol_rejects_missing_method_at_runtime() -> None:
    """A class missing `run` does NOT satisfy `isinstance(CodingAgentAdapter)`."""

    class NoRun:
        name = "noop"
        version = "1.0"

    # Missing `run` → runtime_checkable Protocol isinstance returns False.
    assert not isinstance(NoRun(), CodingAgentAdapter)


# ============================================================ #
# AC-1b.4.3 — InProcessAdapter direct-override pattern         #
# ============================================================ #


def test_inprocess_adapter_no_abstract_hooks_instantiates() -> None:
    """ADR-003 L22-23: InProcessAdapter has NO `@abstractmethod` members."""
    adapter = InProcessAdapter()
    # No TypeError on instantiation = no abstract methods.
    assert adapter is not None


def test_inprocess_adapter_default_name_property() -> None:
    """Default `name` returns `type(self).__name__`."""

    class MyAdapter(InProcessAdapter):
        pass

    assert MyAdapter().name == "MyAdapter"


def test_inprocess_adapter_default_version_fallback_to_unknown() -> None:
    """When the top-level package has no metadata, `version` falls back to 'unknown'."""

    class MyAdapter(InProcessAdapter):
        pass

    # Tests live in a non-distribution module path; importlib.metadata won't
    # find a matching package, so the fallback fires.
    assert MyAdapter().version == "unknown"


def test_inprocess_adapter_init_kwargs_capture() -> None:
    """`__init__(**kwargs)` captures into `_adapter_config: dict[str, Any]`."""
    adapter = InProcessAdapter(model="gpt-5", temperature=0.0)
    assert adapter._adapter_config == {"model": "gpt-5", "temperature": 0.0}


def test_inprocess_adapter_subclass_overrides_run() -> None:
    """Subclasses MUST override `run()` to return AgentRunResult."""

    class StubInProcess(InProcessAdapter):
        def run(
            self, prompt: str, tools: list[str] | None = None, mcp_servers: Any = None, **kwargs: Any
        ) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"echo: {prompt}",
                tool_calls=[],
                usage=Usage(input_tokens=5, output_tokens=10),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.05,
                trace_id="trace-xyz",
            )

    result = StubInProcess().run("hello")
    assert result.response_text == "echo: hello"
    assert result.metadata.completeness == "complete"
    # Verify the stub satisfies the Protocol.
    assert isinstance(StubInProcess(), CodingAgentAdapter)


# ============================================================ #
# AC-1b.4.4 — SubprocessAdapter abstract enforcement + template-method #
# ============================================================ #


def test_subprocess_adapter_cannot_instantiate_without_hooks() -> None:
    """Direct instantiation fails: 3 abstract methods un-implemented."""
    with pytest.raises(TypeError, match="abstract"):
        SubprocessAdapter()  # type: ignore[abstract]


def test_subprocess_adapter_partial_implementation_still_fails() -> None:
    """Subclass implementing only 2 of 3 hooks still fails to instantiate."""

    class PartialAdapter(SubprocessAdapter):
        def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
            raise NotImplementedError

        def _parse_event(self, line: str) -> Any:
            raise NotImplementedError

        # Missing _finalize → still abstract.

    with pytest.raises(TypeError, match="abstract"):
        PartialAdapter()  # type: ignore[abstract]


class _FakeStream:
    """List-iterator with a .close() method (matches subprocess.Popen[str].stdout shape)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = iter(lines)
        self.close = MagicMock()

    def __iter__(self) -> Any:
        return self

    def __next__(self) -> str:
        return next(self._lines)


def _make_fake_popen(stdout_lines: list[str], returncode: int = 0, pid: int = 12345) -> Any:
    """Build a MagicMock that quacks like `subprocess.Popen[str]` for tests."""
    fake = MagicMock(spec=subprocess.Popen)
    fake.stdout = _FakeStream(stdout_lines)
    fake.stderr = _FakeStream([])
    fake.wait.return_value = returncode
    fake.returncode = returncode
    fake.pid = pid
    fake.terminate = MagicMock()
    fake.kill = MagicMock()
    return fake


class _FakeSubprocessAdapter(SubprocessAdapter):
    """Test fixture: deterministic 3-hook implementation."""

    def __init__(self, stdout_lines: list[str], returncode: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._stdout_lines = stdout_lines
        self._returncode = returncode

    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:  # noqa: ARG002
        return _make_fake_popen(self._stdout_lines, returncode=self._returncode)

    def _parse_event(self, line: str) -> str | None:
        stripped = line.strip()
        # Skip blank lines + lines that don't start with 'event:'.
        if not stripped or not stripped.startswith("event:"):
            return None
        return stripped[len("event:") :].strip()

    def _finalize(self, events: list[str], exit_code: int) -> AgentRunResult:
        return AgentRunResult(
            response_text=" | ".join(events),
            tool_calls=[],
            usage=Usage(input_tokens=1, output_tokens=len(events)),
            metadata=AgentRunMetadata(
                completeness="complete" if exit_code == 0 else "truncated",
                mcp_coverage="subprocess_with_observer",
            ),
            cost_usd=0.0,
            latency_seconds=0.0,
            trace_id="fake-trace",
        )


def test_subprocess_adapter_template_method_orchestrates_hooks() -> None:
    """`run()` orchestrates spawn → iterate _parse_event → _finalize."""
    adapter = _FakeSubprocessAdapter(
        stdout_lines=[
            "event: alpha\n",
            "\n",  # blank line, skipped
            "progress: 50%\n",  # not an event, skipped
            "event: beta\n",
            "event: gamma\n",
        ],
        returncode=0,
    )
    result = adapter.run("hi")
    assert result.response_text == "alpha | beta | gamma"
    assert result.usage.output_tokens == 3
    assert result.metadata.completeness == "complete"


def test_subprocess_adapter_run_propagates_nonzero_exit_code_to_finalize() -> None:
    """`_finalize` receives the subprocess exit code; fake fixture sets completeness."""
    adapter = _FakeSubprocessAdapter(stdout_lines=["event: only-one\n"], returncode=1)
    result = adapter.run("hi")
    assert result.metadata.completeness == "truncated"


def test_subprocess_adapter_run_terminates_process_group_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `_parse_event` raises, the SUBPROCESS PROCESS GROUP is SIGTERMed in cleanup.

    Story 1b.4 code-review D1 patch: cleanup uses `os.killpg(os.getpgid(pid), SIGTERM)`
    (Story 1b.1 MCPLifecycleManager precedent), NOT bare `proc.terminate()`.
    """
    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(base_module.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig)))
    monkeypatch.setattr(base_module.os, "getpgid", lambda pid: pid)  # identity mapping for the test

    class CrashingAdapter(_FakeSubprocessAdapter):
        def _parse_event(self, line: str) -> str | None:
            raise RuntimeError("parse exploded")

    adapter = CrashingAdapter(stdout_lines=["event: x\n"])
    with pytest.raises(RuntimeError, match="parse exploded"):
        adapter.run("hi")
    # SIGTERM the process group of the spawned subprocess (pgid == pid due to test stub).
    assert killpg_calls, "expected os.killpg to be called during cleanup"
    pgid, sig = killpg_calls[0]
    assert pgid == 12345  # default pid from _make_fake_popen
    assert sig == base_module.signal.SIGTERM


# ============================================================ #
# AC-1b.4.7 — _assert_binary_version + FR47 exact format       #
# ============================================================ #


def _stub_subprocess_run(
    monkeypatch: pytest.MonkeyPatch, *, stdout: str = "", stderr: str = "", returncode: int = 0
) -> None:
    """Patch subprocess.run inside the base module with a deterministic stub."""

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(base_module.subprocess, "run", fake_run)


class _BareSubprocess(SubprocessAdapter):
    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:  # pragma: no cover
        raise NotImplementedError

    def _parse_event(self, line: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    def _finalize(self, events: list[Any], exit_code: int) -> AgentRunResult:  # pragma: no cover
        raise NotImplementedError


def test_assert_binary_version_in_range_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-range version passes silently."""
    _stub_subprocess_run(monkeypatch, stdout="claude version 1.0.9\n")
    _BareSubprocess()._assert_binary_version("claude", "1.0.0", "2.0.0")


def test_assert_binary_version_below_min_raises_with_fr47_exact_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Below-min raises with FR47-EXACT message format on `str(exc)`.

    Story 1b.4 code-review D6 patch: UnsupportedBinaryVersionError overrides
    `__str__` to skip the H_R7 prefix; `str(exc)` matches PRD FR47 verbatim
    `<binary> version <X> outside tested range <range>`. The `error_code`
    ClassVar remains available for FR49/FR50 machine-readable consumers.
    """
    _stub_subprocess_run(monkeypatch, stdout="claude version 0.9.5\n")
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("claude", "1.0.0", "2.0.0")
    # FR47-EXACT on str(exc) — NO `UNSUPPORTED_BINARY_VERSION:` prefix.
    assert str(exc_info.value) == ("claude version 0.9.5 outside tested range >=1.0.0, <2.0.0")
    # error_code remains accessible via ClassVar for FR49/FR50.
    assert exc_info.value.error_code == "UNSUPPORTED_BINARY_VERSION"
    # Structured attrs (D7 patch) exposed.
    assert exc_info.value.binary == "claude"
    assert exc_info.value.detected == "0.9.5"
    assert exc_info.value.min_version == "1.0.0"
    assert exc_info.value.max_version == "2.0.0"


def test_assert_binary_version_at_or_above_max_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At-or-above-max raises (max is exclusive)."""
    _stub_subprocess_run(monkeypatch, stdout="copilot 2.0.0\n")
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("copilot", "1.0.9", "2.0.0")
    assert "2.0.0 outside tested range >=1.0.9, <2.0.0" in str(exc_info.value)


def test_assert_binary_version_with_max_none_uses_open_upper_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max=None` composes `<range>` as `>={min}` (no upper bound)."""
    _stub_subprocess_run(monkeypatch, stdout="some-cli 0.5.0\n")
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("some-cli", "1.0.0", None)
    assert "outside tested range >=1.0.0" in str(exc_info.value)
    assert "<" not in str(exc_info.value).split("range")[1]


def test_assert_binary_version_unparseable_output_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Output without a semver substring raises with `<unparseable>` placeholder."""
    _stub_subprocess_run(monkeypatch, stdout="no version info here\n")
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("weird-cli", "1.0.0", "2.0.0")
    assert "<unparseable>" in str(exc_info.value)


def test_assert_binary_version_missing_binary_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FileNotFoundError on `--version` invocation → typed UnsupportedBinaryVersionError."""

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(base_module.subprocess, "run", fake_run)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("missing-cli", "1.0.0", None)
    assert "<unavailable>" in str(exc_info.value)


# ============================================================ #
# AC-1b.4.5 + AC-1b.4.6 — AgentRunResult + AgentRunMetadata    #
# ============================================================ #


def test_agent_run_result_constructs_with_all_fields() -> None:
    arr = AgentRunResult(
        response_text="hi",
        tool_calls=[
            ToolCallTrace(
                name="search",
                args={"q": "test"},
                result=None,
                error=None,
                latency_ms=10.0,
                source="adapter",
                gen_ai_tool_call_id="t1",
                sequence_index=0,
            ),
        ],
        usage=Usage(input_tokens=5, output_tokens=10),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="external_mixed"),
        cost_usd=0.01,
        latency_seconds=1.0,
        trace_id="t1",
    )
    assert arr.response_text == "hi"
    assert arr.metadata.mcp_coverage == "external_mixed"


def test_agent_run_result_frozen_blocks_attribute_rebind() -> None:
    """`frozen=True` prevents `arr.response_text = ...` rebinding."""
    arr = AgentRunResult(
        response_text="hi",
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="t1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        arr.response_text = "rebound"  # type: ignore[misc]


def test_agent_run_result_defensive_copy_blocks_source_mutation() -> None:
    """M_R6 pattern: mutating the source `tool_calls` list does NOT leak."""
    source_list: list[ToolCallTrace] = []
    arr = AgentRunResult(
        response_text="hi",
        tool_calls=source_list,
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="t1",
    )
    # Mutate the original list.
    source_list.append(
        ToolCallTrace(
            name="leak",
            args={},
            result=None,
            error=None,
            latency_ms=0.0,
            source="adapter",
            gen_ai_tool_call_id="leak",
            sequence_index=0,
        )
    )
    assert len(arr.tool_calls) == 0  # defensive copy held


def test_agent_run_result_asdict_round_trips() -> None:
    """`dataclasses.asdict()` serializes cleanly (jsonl backend invariant)."""
    arr = AgentRunResult(
        response_text="hi",
        tool_calls=[],
        usage=Usage(input_tokens=5, output_tokens=10, cached_input_tokens=2),
        metadata=AgentRunMetadata(completeness="partial", mcp_coverage="subprocess_with_observer"),
        cost_usd=0.05,
        latency_seconds=2.5,
        trace_id="t-abc",
    )
    d = dataclasses.asdict(arr)
    assert d["metadata"]["completeness"] == "partial"
    assert d["usage"]["cached_input_tokens"] == 2


def test_agent_run_metadata_value_spaces_per_adr_006_and_adr_016() -> None:
    """3-state value spaces are exhaustive per ADR-006 + ADR-016."""
    for completeness in ("complete", "truncated", "partial"):
        for mcp_coverage in (
            "hosted_in_process",
            "subprocess_with_observer",
            "external_mixed",
        ):
            arm = AgentRunMetadata(completeness=completeness, mcp_coverage=mcp_coverage)  # type: ignore[arg-type]
            assert arm.completeness == completeness
            assert arm.mcp_coverage == mcp_coverage


# ============================================================ #
# AC-1b.4.7 — UnsupportedBinaryVersionError hierarchy + error_code #
# ============================================================ #


def test_unsupported_binary_version_error_hierarchy_and_code() -> None:
    """Inherits AgentEvalCompatError + AgentEvalError; `error_code` per FR47."""
    assert issubclass(UnsupportedBinaryVersionError, AgentEvalCompatError)
    assert issubclass(UnsupportedBinaryVersionError, AgentEvalError)
    assert UnsupportedBinaryVersionError.error_code == "UNSUPPORTED_BINARY_VERSION"


def test_unsupported_binary_version_error_str_skips_h_r7_prefix_per_fr47() -> None:
    """Story 1b.4 code-review D6: this leaf overrides `__str__` to honor FR47-exact
    format on `str(exc)`. The H_R7 prefix is NOT applied — `error_code` ClassVar
    remains the machine-readable signal for FR49 JUnit XML / FR50 exit-code
    mapping.
    """
    e = UnsupportedBinaryVersionError("claude version 0.5.0 outside tested range >=1.0.0, <2.0.0")
    assert str(e) == "claude version 0.5.0 outside tested range >=1.0.0, <2.0.0"
    assert e.error_code == "UNSUPPORTED_BINARY_VERSION"


# ============================================================ #
# Story 1b.4 code-review patches P10-P13                       #
# ============================================================ #


def test_parse_version_tuple_pads_short_versions_to_arity_3() -> None:
    """D3 patch: `"1.0"` → `(1, 0, 0)`, NOT `(1, 0)` — fixes the `(1,0) < (1,0,0)` bug."""
    assert base_module._parse_version_tuple("1.0") == (1, 0, 0)
    assert base_module._parse_version_tuple("2.0") == (2, 0, 0)
    assert base_module._parse_version_tuple("1.0.5") == (1, 0, 5)
    # Equality across short + full forms — boundary bug fix verification.
    assert base_module._parse_version_tuple("1.0") == base_module._parse_version_tuple("1.0.0")


def test_parse_version_tuple_rejects_prerelease(monkeypatch: pytest.MonkeyPatch) -> None:
    """D3 patch: prerelease strings raise ValueError (defer to packaging.version per DF8)."""
    with pytest.raises(ValueError, match="prerelease"):
        base_module._parse_version_tuple("1.0.0a1")
    with pytest.raises(ValueError, match="prerelease"):
        base_module._parse_version_tuple("1.0.0-rc1")
    with pytest.raises(ValueError, match="prerelease"):
        base_module._parse_version_tuple("1.0.0+build123")


def test_parse_version_tuple_rejects_too_many_components() -> None:
    """4+ component versions are rejected."""
    with pytest.raises(ValueError, match="more than 3 components"):
        base_module._parse_version_tuple("1.0.0.0")


def test_assert_binary_version_2_part_vs_3_part_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """D3 patch + Codex STAR catch: `"2.0"` reported by binary, `max="2.0.0"` →
    correctly REJECTED (was incorrectly accepted pre-edit because `(2,0) < (2,0,0)`).
    """
    _stub_subprocess_run(monkeypatch, stdout="copilot 2.0\n")
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("copilot", "1.0.9", "2.0.0")
    assert exc_info.value.detected == "2.0"


def test_assert_binary_version_nonzero_returncode_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P4 patch: non-zero exit from `<binary> --version` raises with exit-status placeholder."""
    _stub_subprocess_run(monkeypatch, stderr="license expired\n", returncode=1)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("claude", "1.0.0", "2.0.0")
    assert "<exit-status-1>" in str(exc_info.value)


def test_assert_binary_version_permission_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P5 patch: PermissionError (binary present, not executable) → typed error."""

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise PermissionError("Permission denied")

    monkeypatch.setattr(base_module.subprocess, "run", fake_run)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        _BareSubprocess()._assert_binary_version("noexec-cli", "1.0.0", None)
    assert "<unavailable>" in str(exc_info.value)


def test_default_version_uses_packages_distributions(monkeypatch: pytest.MonkeyPatch) -> None:
    """D5 patch + Codex STAR catch: in-tree adapter `module=AgentEval.foo.adapter`
    resolves via `packages_distributions()` to `robotframework-agenteval`, NOT
    falling back to `"unknown"` via the module-name heuristic.
    """
    monkeypatch.setattr(
        base_module.importlib.metadata,
        "packages_distributions",
        lambda: {"AgentEval": ["robotframework-agenteval"]},
    )
    monkeypatch.setattr(
        base_module.importlib.metadata,
        "version",
        lambda dist: "9.9.9" if dist == "robotframework-agenteval" else "wrong",
    )
    assert base_module._default_version("AgentEval.coding_agent.base") == "9.9.9"


def test_default_version_swallows_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3 patch: corrupt metadata raises OSError → fallback to 'unknown'."""

    def raises_oserror() -> dict[str, list[str]]:
        raise OSError("metadata corrupt")

    monkeypatch.setattr(base_module.importlib.metadata, "packages_distributions", raises_oserror)
    assert base_module._default_version("AgentEval.foo") == "unknown"


def test_agent_run_metadata_rejects_invalid_completeness() -> None:
    """D7 patch: `__post_init__` Literal validation raises on out-of-set inputs."""
    with pytest.raises(ValueError, match="completeness"):
        AgentRunMetadata(completeness="bogus", mcp_coverage="hosted_in_process")  # type: ignore[arg-type]


def test_agent_run_metadata_rejects_invalid_mcp_coverage() -> None:
    """D7 patch: `mcp_coverage` rejects pre-ADR-016 'none' 4th value."""
    with pytest.raises(ValueError, match="mcp_coverage"):
        AgentRunMetadata(completeness="complete", mcp_coverage="none")  # type: ignore[arg-type]


def test_unsupported_binary_version_error_structured_attrs() -> None:
    """D7 patch: structured attrs (binary/detected/min_version/max_version) exposed."""
    e = UnsupportedBinaryVersionError(
        "claude version 0.5.0 outside tested range >=1.0.0, <2.0.0",
        binary="claude",
        detected="0.5.0",
        min_version="1.0.0",
        max_version="2.0.0",
    )
    assert e.binary == "claude"
    assert e.detected == "0.5.0"
    assert e.min_version == "1.0.0"
    assert e.max_version == "2.0.0"


def test_unsupported_binary_version_error_structured_attrs_default_none() -> None:
    """Backward-compat: bare message-only construction defaults all structured attrs to None."""
    e = UnsupportedBinaryVersionError("legacy bare message")
    assert e.binary is None
    assert e.detected is None
    assert e.min_version is None
    assert e.max_version is None


def test_subprocess_run_closes_stdout_and_stderr_on_success() -> None:
    """P2 patch: PIPE fds are closed in the success path (no leak)."""
    adapter = _FakeSubprocessAdapter(stdout_lines=["event: a\n"], returncode=0)
    # Capture the proc to inspect close-call after run() returns.
    captured: dict[str, Any] = {}
    original_spawn = adapter._spawn

    def capturing_spawn(prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
        proc = original_spawn(prompt, **kwargs)
        captured["proc"] = proc
        return proc

    adapter._spawn = capturing_spawn  # type: ignore[method-assign]
    adapter.run("hi")
    captured["proc"].stdout.close.assert_called_once()
    captured["proc"].stderr.close.assert_called_once()


def test_subprocess_adapter_raises_typeerror_when_stdout_is_none() -> None:
    """P1 patch: explicit raise (NOT `assert`) when `_spawn` returns stdout=None."""

    class BadSpawnAdapter(_FakeSubprocessAdapter):
        def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
            fake = MagicMock(spec=subprocess.Popen)
            fake.stdout = None
            return fake

    with pytest.raises(TypeError, match="stdout=None"):
        BadSpawnAdapter(stdout_lines=[]).run("hi")


def test_catching_agenteval_error_catches_unsupported_binary_version() -> None:
    """Consumers can `try / except AgentEvalError` to catch the new leaf."""
    with pytest.raises(AgentEvalError):
        raise UnsupportedBinaryVersionError("x")


# ============================================================ #
# AC-1b.4.9 — _kernel/discovery.py integration smoke           #
# ============================================================ #


def test_discovery_get_adapter_returns_protocol_satisfying_class() -> None:
    """`discover_adapters` / `register_adapter` / `get_adapter` round-trip
    works with a class that satisfies the Protocol — Story 1b.4 unblocks
    the discovery API's `dict[str, type[CodingAgentAdapter]]` return type.
    """

    class StubAdapter:
        name = "stub"
        version = "1.0"

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:  # noqa: ARG002
            return AgentRunResult(
                response_text="ok",
                tool_calls=[],
                usage=Usage(input_tokens=0, output_tokens=0),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id="t",
            )

    discovery._clear_discovery_cache()
    discovery.register_adapter("stub", StubAdapter)
    resolved_cls = discovery.get_adapter("stub")
    instance = resolved_cls()
    assert isinstance(instance, CodingAgentAdapter)
    discovery._clear_discovery_cache()
