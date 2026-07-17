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

"""One subprocess seam for every externally-installed coding-agent CLI.

``SubprocessCLIAdapter`` is the single template that contains the vendor sprawl:
a concrete adapter overrides only ``build_argv(prompt)`` (the command line) and
``parse_output(...)`` (normalize stdout/transcript into an ``AgentRunResult``).
The base owns everything shared - resolving the binary on ``PATH``, probing
``--version`` for drift, running the subprocess with a timeout and a fresh
session group, sourcing secrets from ``os.environ`` without ever logging them,
and the cost-precedence + newest-transcript helpers the parse strategies lean on.

Fidelity is uneven across CLIs and is labeled per adapter (``FULL`` / ``PARTIAL``
/ ``DEGRADED``) with a ``validation_ceiling`` string so a degraded run can never
read as fake-green. Secrets are never placed on argv (they come from the child's
environment), never logged, and never written to the returned result.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Any, ClassVar, Literal

from AgentEval._core.errors import AdapterError, AdapterVersionDriftWarning
from AgentEval._core.types import AgentRunResult

__all__ = ["SubprocessCLIAdapter"]

Fidelity = Literal["FULL", "PARTIAL", "DEGRADED"]
MetricSource = Literal["native", "derived", "none"]

# Default wall-clock ceiling for one CLI invocation. Live agent runs are slow;
# 300s is generous without letting a wedged CLI hang a suite indefinitely.
DEFAULT_TIMEOUT_SECONDS = 300.0

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")


class SubprocessCLIAdapter:
    """Abstract base: run a coding-agent CLI as a subprocess, normalize the result.

    Concrete adapters set the class attributes below and override the two
    template methods. The base is not usable on its own - ``build_argv`` and
    ``parse_output`` raise ``NotImplementedError`` until a subclass fills them.

    Class attributes:
        slug: Registry key (e.g. ``"claude-code"``); also the adapter ``name``.
        binary_name: Executable resolved on ``PATH`` via ``shutil.which``.
        fidelity: ``"FULL"`` | ``"PARTIAL"`` | ``"DEGRADED"`` - honest label of
            how completely this CLI's output can be normalized.
        validation_ceiling: One line naming what this adapter *cannot* reliably
            report, so downstream metrics never read a gap as complete.
        version_flag: Argv tail that prints the version (default ``["--version"]``).
        pinned_version_range: Optional ``(min, max)`` inclusive version strings
            the parse logic was verified against; drift outside it warns.
        install_hint: Shown when the binary is missing on ``PATH``.
    """

    slug: ClassVar[str] = ""
    binary_name: ClassVar[str] = ""
    fidelity: ClassVar[Fidelity] = "DEGRADED"
    validation_ceiling: ClassVar[str] = ""
    version_flag: ClassVar[list[str]] = ["--version"]
    pinned_version_range: ClassVar[tuple[str, str] | None] = None
    install_hint: ClassVar[str] = ""

    @property
    def name(self) -> str:
        """Adapter identity for the ``Adapter`` protocol - the slug."""
        return self.slug

    # ------------------------------------------------------------------ #
    # Template methods - a concrete adapter overrides exactly these two.  #
    # ------------------------------------------------------------------ #

    def build_argv(self, prompt: str) -> list[str]:
        """Return the full argv (starting with the binary) for ``prompt``.

        Secrets MUST NOT be placed here; they are sourced from ``os.environ`` by
        the child process. Override in a concrete adapter.
        """
        raise NotImplementedError(f"{type(self).__name__} must override build_argv()")

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        """Normalize a finished CLI run into an ``AgentRunResult``.

        ``session_dir`` is where on-disk session/rollout transcripts live for
        the fallback path; ``None`` when the caller supplied none. Override in a
        concrete adapter.
        """
        raise NotImplementedError(f"{type(self).__name__} must override parse_output()")

    # ------------------------------------------------------------------ #
    # The one entry point every Tier-3 keyword drives.                    #
    # ------------------------------------------------------------------ #

    def run(
        self,
        prompt: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session_dir: str | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Resolve the binary, probe version, run the CLI, and normalize output.

        Raises ``AdapterError`` when the binary is missing (message names the
        binary + install hint) or when the subprocess exceeds ``timeout``.
        Emits ``AdapterVersionDriftWarning`` when the probed ``--version`` falls
        outside ``pinned_version_range``. The child inherits ``os.environ`` (so
        secrets flow without appearing on argv), started in a fresh session.
        """
        binary_path = self._resolve_binary()

        agent_version = self._probe_version(binary_path)
        self._warn_on_version_drift(agent_version)

        argv = self.build_argv(prompt)
        run_env = self._build_env(env)

        try:
            completed = subprocess.run(  # noqa: S603 - argv built by the adapter, not shell
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                start_new_session=True,
                cwd=cwd,
                env=run_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"{self.slug!r} CLI ({self.binary_name}) exceeded the {timeout:g}s timeout") from exc

        result = self.parse_output(
            completed.stdout or "",
            completed.stderr or "",
            completed.returncode,
            session_dir,
        )
        return self._stamp_version(result, agent_version)

    # ------------------------------------------------------------------ #
    # Shared machinery - binary resolution, version probe, drift check.   #
    # ------------------------------------------------------------------ #

    def _resolve_binary(self) -> str:
        """Return the resolved binary path or raise a loud, actionable error."""
        resolved = shutil.which(self.binary_name)
        if resolved is None:
            hint = f" {self.install_hint}" if self.install_hint else ""
            raise AdapterError(
                f"{self.slug!r} adapter needs the {self.binary_name!r} CLI on PATH, but it was not found.{hint}"
            )
        return resolved

    def _probe_version(self, binary_path: str) -> str:
        """Best-effort ``--version`` probe; returns the extracted version or ''.

        Never raises: a CLI that has no version flag, times out, or prints an
        unparseable banner simply yields an empty version (drift check no-ops).
        """
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
                [binary_path, *self.version_flag],
                capture_output=True,
                text=True,
                timeout=30,
                start_new_session=True,
                env=self._build_env(None),
                check=False,
            )
        except (subprocess.SubprocessError, OSError):
            return ""
        blob = f"{completed.stdout or ''}\n{completed.stderr or ''}"
        match = _VERSION_RE.search(blob)
        return match.group(1) if match else ""

    def _warn_on_version_drift(self, version: str) -> None:
        """Emit ``AdapterVersionDriftWarning`` if ``version`` is out of range."""
        if not version or self.pinned_version_range is None:
            return
        low, high = self.pinned_version_range
        detected = _parse_version(version)
        if not detected:
            return
        if _parse_version(low) <= detected <= _parse_version(high):
            return
        warnings.warn(
            AdapterVersionDriftWarning(
                f"{self.slug!r} adapter parse logic was verified against "
                f"{self.binary_name} {low}..{high}; detected {version}. "
                f"Results may drift."
            ),
            stacklevel=2,
        )

    def _stamp_version(self, result: AgentRunResult, version: str) -> AgentRunResult:
        """Return ``result`` with ``metadata.agent_version`` set when the adapter left it blank."""
        if not version or result.metadata.agent_version:
            return result
        from dataclasses import replace

        new_metadata = replace(result.metadata, agent_version=version)
        return replace(result, metadata=new_metadata)

    @staticmethod
    def _build_env(overrides: dict[str, str] | None) -> dict[str, str]:
        """Child environment: inherit ``os.environ`` (secrets included), apply overrides.

        Kept in one place so no code path ever logs the returned mapping.
        """
        import os

        env = dict(os.environ)
        if overrides:
            env.update(overrides)
        return env

    # ------------------------------------------------------------------ #
    # Helpers the concrete parse strategies share.                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def resolve_cost(
        native_cost: float | None = None,
        **litellm_kwargs: Any,
    ) -> tuple[float, MetricSource]:
        """Cost precedence: native value if the CLI supplied one, else litellm.

        Returns ``(cost_usd, metric_source)`` where ``metric_source`` is
        ``"native"`` (the CLI reported it), ``"derived"`` (computed via
        ``litellm.completion_cost`` from tokens + a price table), or ``"none"``
        (neither available). ``litellm_kwargs`` are forwarded verbatim to
        ``litellm.completion_cost`` (e.g. ``model=..., prompt=..., completion=...``
        or ``completion_response=...``). A missing litellm install or any pricing
        error degrades quietly to ``(0.0, "none")``.
        """
        if native_cost is not None:
            return float(native_cost), "native"
        if not litellm_kwargs:
            return 0.0, "none"
        try:
            import litellm

            cost: Any = litellm.completion_cost(**litellm_kwargs)
        except Exception:  # noqa: BLE001 - no install / no pricing metadata / bad input
            return 0.0, "none"
        if cost is None:
            return 0.0, "none"
        return float(cost), "derived"

    @staticmethod
    def find_newest_session_file(
        session_dir: str | Path | None,
        pattern: str = "*",
    ) -> Path | None:
        """Return the newest (by mtime) file under ``session_dir`` matching ``pattern``.

        Recurses. Returns ``None`` when the directory is absent or empty - the
        thin-stdout transcript fallback path uses this to locate a run's rollout.
        """
        if session_dir is None:
            return None
        directory = Path(session_dir)
        if not directory.is_dir():
            return None
        candidates = [p for p in directory.rglob(pattern) if p.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)


def _parse_version(text: str) -> tuple[int, ...]:
    """Extract the first dotted numeric run from ``text`` as an int tuple.

    ``"claude 1.2.3 (build 9)"`` -> ``(1, 2, 3)``; no match -> ``()``. Bounds
    are compared as zero-padded tuples so ``(0, 6) < (0, 6, 1)`` holds.
    """
    match = _VERSION_RE.search(text)
    if not match:
        return ()
    parts = match.group(1).split(".")
    return tuple(int(p) for p in parts)
