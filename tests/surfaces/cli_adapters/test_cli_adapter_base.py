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

"""Base-seam tests for ``SubprocessCLIAdapter``.

Covers the shared machinery every concrete adapter inherits: missing-binary
fail-loud, version probing + drift warning, the stubbed end-to-end run path,
timeout surfacing, cost precedence, and the newest-transcript helper. Real CLIs
are never invoked - ``subprocess.run`` and ``shutil.which`` are stubbed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
import warnings
from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval._core import cli_adapter as cli_adapter_mod
from AgentEval._core.adapter import Adapter
from AgentEval._core.cli_adapter import SubprocessCLIAdapter
from AgentEval._core.errors import AdapterError, AdapterVersionDriftWarning
from AgentEval._core.types import AgentRunResult


class _FakeCLIAdapter(SubprocessCLIAdapter):
    """A concrete adapter that exercises the full base run path deterministically."""

    slug = "fake-cli"
    binary_name = "fakebin"
    fidelity = "FULL"
    validation_ceiling = "fake ceiling"
    install_hint = "pip install fakebin"
    pinned_version_range = ("1.0.0", "2.0.0")

    def build_argv(self, prompt: str) -> list[str]:
        return [self.binary_name, "-p", prompt]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        return AgentRunResult(response_text=stdout.strip() or "ok")


def _install_fake_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    *,
    version_output: str = "fakebin 1.5.0",
    main_stdout: str = "hello world",
    main_stderr: str = "",
    returncode: int = 0,
    timeout_on_main: bool = False,
) -> None:
    """Stub ``cli_adapter.subprocess.run`` for both the version probe and main run."""

    def fake_run(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        if "--version" in argv[1:]:
            return SimpleNamespace(stdout=version_output, stderr="", returncode=0)
        if timeout_on_main:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))
        return SimpleNamespace(stdout=main_stdout, stderr=main_stderr, returncode=returncode)

    monkeypatch.setattr(cli_adapter_mod.subprocess, "run", fake_run)


def _install_which(monkeypatch: pytest.MonkeyPatch, result: str | None) -> None:
    monkeypatch.setattr(cli_adapter_mod.shutil, "which", lambda name: result)


# --------------------------------------------------------------------------- #
# Missing binary                                                              #
# --------------------------------------------------------------------------- #


def test_missing_binary_raises_adapter_error_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_which(monkeypatch, None)
    adapter = _FakeCLIAdapter()
    with pytest.raises(AdapterError) as excinfo:
        adapter.run("do a thing")
    message = str(excinfo.value)
    assert "fakebin" in message
    assert "pip install fakebin" in message


# --------------------------------------------------------------------------- #
# Version drift                                                               #
# --------------------------------------------------------------------------- #


def test_version_in_range_does_not_warn_and_stamps_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, version_output="fakebin 1.5.0")
    adapter = _FakeCLIAdapter()
    with warnings.catch_warnings():
        warnings.simplefilter("error", AdapterVersionDriftWarning)
        result = adapter.run("prompt")
    assert result.metadata.agent_version == "1.5.0"


def test_version_out_of_range_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, version_output="fakebin 3.9.0")
    adapter = _FakeCLIAdapter()
    with pytest.warns(AdapterVersionDriftWarning):
        result = adapter.run("prompt")
    # Parse still runs despite drift - the warning does not abort the run.
    assert result.metadata.agent_version == "3.9.0"


def test_no_pinned_range_never_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, version_output="fakebin 99.0.0")

    class _Unpinned(_FakeCLIAdapter):
        pinned_version_range = None

    with warnings.catch_warnings():
        warnings.simplefilter("error", AdapterVersionDriftWarning)
        result = _Unpinned().run("prompt")
    assert result.metadata.agent_version == "99.0.0"


# --------------------------------------------------------------------------- #
# End-to-end stubbed run                                                      #
# --------------------------------------------------------------------------- #


def test_run_end_to_end_returns_parsed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, main_stdout="  the answer  ")
    result = _FakeCLIAdapter().run("prompt")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "the answer"


def test_run_passes_session_dir_and_exit_code_to_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, main_stdout="x", main_stderr="warn", returncode=3)
    captured: dict[str, Any] = {}

    class _Capturing(_FakeCLIAdapter):
        def parse_output(
            self,
            stdout: str,
            stderr: str,
            exit_code: int,
            session_dir: str | None,
        ) -> AgentRunResult:
            captured.update(stdout=stdout, stderr=stderr, exit_code=exit_code, session_dir=session_dir)
            return AgentRunResult(response_text=stdout)

    _Capturing().run("prompt", session_dir="/tmp/sessions")
    assert captured == {
        "stdout": "x",
        "stderr": "warn",
        "exit_code": 3,
        "session_dir": "/tmp/sessions",
    }


def test_timeout_surfaces_as_adapter_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, timeout_on_main=True)
    with pytest.raises(AdapterError) as excinfo:
        _FakeCLIAdapter().run("prompt", timeout=5)
    assert "timeout" in str(excinfo.value).lower()


def test_env_inherits_os_environ_without_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SECRET_KEY", "sk-super-secret")
    seen_env: dict[str, str] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        if "--version" in argv[1:]:
            return SimpleNamespace(stdout="fakebin 1.5.0", stderr="", returncode=0)
        seen_env.update(kwargs["env"])
        return SimpleNamespace(stdout="ok", stderr="", returncode=0)

    _install_which(monkeypatch, "/usr/bin/fakebin")
    monkeypatch.setattr(cli_adapter_mod.subprocess, "run", fake_run)
    _FakeCLIAdapter().run("prompt")
    # The child inherits the secret via env, but it is never placed on argv.
    assert seen_env["FAKE_SECRET_KEY"] == "sk-super-secret"


# --------------------------------------------------------------------------- #
# Adapter protocol conformance                                                #
# --------------------------------------------------------------------------- #


def test_base_subclass_satisfies_adapter_protocol() -> None:
    adapter = _FakeCLIAdapter()
    assert isinstance(adapter, Adapter)
    assert adapter.name == "fake-cli"


# --------------------------------------------------------------------------- #
# Cost precedence helper                                                      #
# --------------------------------------------------------------------------- #


def test_resolve_cost_native_wins() -> None:
    cost, source = SubprocessCLIAdapter.resolve_cost(0.42)
    assert cost == pytest.approx(0.42)
    assert source == "native"


def test_resolve_cost_none_when_no_native_and_no_litellm_kwargs() -> None:
    cost, source = SubprocessCLIAdapter.resolve_cost()
    assert cost == 0.0
    assert source == "none"


def test_resolve_cost_derived_via_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_litellm = types.ModuleType("litellm")
    fake_litellm.completion_cost = lambda **kwargs: 0.75  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    cost, source = SubprocessCLIAdapter.resolve_cost(None, model="gpt-4o", prompt="hi", completion="yo")
    assert cost == pytest.approx(0.75)
    assert source == "derived"


def test_resolve_cost_litellm_error_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_litellm = types.ModuleType("litellm")

    def _boom(**kwargs: Any) -> float:
        raise RuntimeError("no pricing metadata")

    fake_litellm.completion_cost = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    cost, source = SubprocessCLIAdapter.resolve_cost(None, model="mystery")
    assert cost == 0.0
    assert source == "none"


# --------------------------------------------------------------------------- #
# Newest-transcript helper                                                    #
# --------------------------------------------------------------------------- #


def test_find_newest_session_file(tmp_path: Any) -> None:
    older = tmp_path / "a.jsonl"
    newer = tmp_path / "nested" / "b.jsonl"
    newer.parent.mkdir()
    older.write_text("old")
    newer.write_text("new")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))
    found = SubprocessCLIAdapter.find_newest_session_file(tmp_path)
    assert found == newer


def test_find_newest_session_file_none_when_missing_or_empty(tmp_path: Any) -> None:
    assert SubprocessCLIAdapter.find_newest_session_file(None) is None
    assert SubprocessCLIAdapter.find_newest_session_file(tmp_path / "nope") is None
    assert SubprocessCLIAdapter.find_newest_session_file(tmp_path) is None


# --------------------------------------------------------------------------- #
# Fail loud on a failed invocation (no silent-empty result)                   #
# --------------------------------------------------------------------------- #


class _EmptyResultAdapter(_FakeCLIAdapter):
    """An adapter whose parse yields nothing usable (simulates a refused CLI run)."""

    slug = "empty-cli"

    def parse_output(self, stdout: str, stderr: str, exit_code: int, session_dir: str | None) -> AgentRunResult:
        return AgentRunResult(response_text="")  # no response, no tool calls, no tokens


def test_failed_run_with_no_usable_output_raises_with_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(
        monkeypatch,
        main_stdout="",
        main_stderr="Not inside a trusted directory and --skip-git-repo-check was not specified.",
        returncode=1,
    )
    with pytest.raises(AdapterError, match=r"exited 1 with no usable output.*trusted directory"):
        _EmptyResultAdapter().run("go")


def test_failed_run_with_partial_but_usable_output_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    # A non-zero exit that still parsed something usable is returned, not raised.
    _install_which(monkeypatch, "/usr/bin/fakebin")
    _install_fake_subprocess(monkeypatch, main_stdout="a partial answer", returncode=1)
    result = _FakeCLIAdapter().run("go")
    assert result.response_text == "a partial answer"


def test_run_closes_child_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-interactive: the child must never block waiting on stdin.
    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        if "--version" in argv[1:]:
            return SimpleNamespace(stdout="fakebin 1.5.0", stderr="", returncode=0)
        seen["stdin"] = kwargs.get("stdin")
        return SimpleNamespace(stdout="ok", stderr="", returncode=0)

    _install_which(monkeypatch, "/usr/bin/fakebin")
    monkeypatch.setattr(cli_adapter_mod.subprocess, "run", fake_run)
    _FakeCLIAdapter().run("go")
    assert seen["stdin"] is subprocess.DEVNULL
