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

"""Robot Framework Listener v3 entry point for agenteval (Story 5.1).

Implements the Regular RF Listener v3 contract per
``docs/contracts/listener-integration.md`` (Phase-1 skeleton filled by this
story). NOT a Library Listener (Library Listeners' ``close()`` fires BEFORE
RF writes xunit/output files; empirically disqualified 2026-05-17).

Canonical user-facing invocation:

    robot --listener AgentEval.telemetry.listener tests/

The ``--listener`` flag is REQUIRED (RF does NOT auto-discover listeners from
PyPA entry-points; empirically verified 2026-05-17 per
``docs/contracts/listener-integration.md`` L20). The entry-point registration
at ``[project.entry-points."robot.listener"]`` is for Phase-2 tooling that
explicitly walks the listener group.

Listener responsibilities (per Story 5.1 ACs):

1. Wire the OTel TracerProvider once with the
   ``RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter)`` chain
   (single redaction choke point per NFR-SEC-01 / FR38a + architecture
   L679 + L1193). Idempotent — only configures on first ``start_suite``.
2. On ``start_test``: extract the test's ``longname`` (canonical RF Listener
   v3 path), call ``_kernel/context.set_current_test_id(test_id, suite_id)``.
3. On ``end_test``: flush JSONL backend if enabled, then ``clear_spans(test_id)``
   for per-test isolation.
4. Reserve ``xunit_file(path)`` + ``output_file(path)`` hooks for Story 8a.1
   xunit-enrichment (Story 5.1 ships no-op signatures so Story 8a.1 can fill
   without touching this file's surface).
5. Resolve ``trace_backend`` + ``trace_path`` via Story 4.3's 4-level
   ConfigValue precedence (init_arg → env → dotenv → default).

Story 5.4 forward-ref: missing-longname graceful degradation emits a warning
(``UserWarning`` placeholder; ``DegradedTraceWarning`` upgrade tracked at
DF-5.1-S1 once Story 5.4 lands the class).

References:
    - architecture L1248: telemetry/listener.py
    - architecture L1554: Listener v3 lifecycle (start_test → set_current_test_id)
    - listener-integration.md (ratified contract Phase-1 skeleton)
    - ADR-009: Per-Test MCP Server Scope via Listener v3 ``test_id``
    - Story 1b.1: ``_kernel/context.set_current_test_id``, ``MCPLifecycleManager``
    - Story 1b.2: ``_kernel/trace_store._configure_tracer_provider``,
      ``RedactionProcessor``, ``clear_spans``
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import warnings
from datetime import UTC
from pathlib import Path
from typing import Any, Literal, cast

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace import Span as SDKSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval._kernel.redaction import RedactionProcessor
from AgentEval.errors import DegradedTraceWarning
from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend
from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID

__all__ = [
    "Listener",
    "TestIdContextSpanProcessor",
    "register_active_observer",
    "record_active_run_metadata",
]

# Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2): pre-edit
# `Listener.register_observer` was dead code — neither the Generic adapter
# nor the Claude Code CLI adapter wired its per-call observer into the
# Listener registry, so `end_test → observer.clear()` never fired in
# production. The Listener is a process singleton (registered by RF when
# `--listener AgentEval.telemetry.listener` is passed); adapters need a
# weak coupling that finds the active Listener without importing it
# directly (which would create a kernel-vs-telemetry layering violation).
# We use a module-level WeakRef set + `register_active_observer()` helper
# that adapters call from `run()`. The Listener registers itself with
# this module on instantiation; if no Listener is active (direct Python
# invocation outside RF), `register_active_observer` is a no-op.
_active_listeners: list[Any] = []


def register_active_observer(observer: Any) -> None:
    """Register an observer with every active `Listener` instance.

    Adapters call this from their `run()` method when they construct a
    per-call `HostedMcpObserver`; the Listener's `end_test` hook then
    calls `observer.clear()` on each registered observer for per-test
    cleanup per ADR-009.

    No-op when no Listener is active (direct Python invocation outside
    RF). Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2).
    """
    for listener in _active_listeners:
        register_fn = getattr(listener, "register_observer", None)
        if callable(register_fn):
            with contextlib.suppress(Exception):
                register_fn(observer)


def record_active_run_metadata(**metadata: Any) -> None:
    """Record per-run operational metadata for the RunManifest sidecar (Story 5.3).

    Adapters call this from their `run()` post-completion path with the
    operational fields the Story 5.3 RunManifest needs (adapter_name,
    adapter_version, model, mcp_servers, total_cost_usd, completeness,
    mcp_coverage, seed, prompt_hashes). The Listener accumulates these
    via `Listener.record_run_metadata` + emits the JSON sidecar on
    `end_test`.

    Helper parallels `register_active_observer` from Story 5.2 — finds
    active listeners + dispatches to each. No-op when no Listener is
    active (direct Python invocation outside RF).
    """
    for listener in _active_listeners:
        record_fn = getattr(listener, "record_run_metadata", None)
        if callable(record_fn):
            with contextlib.suppress(Exception):
                record_fn(**metadata)


_log = logging.getLogger(__name__)


class TestIdContextSpanProcessor(SpanProcessor):
    """Stamp ``agenteval.test_id`` on every span at on_start from kernel context.

    OTel SDK semantics:
        - ``Resource`` attributes are immutable per-``TracerProvider``; cannot
          be updated per-test.
        - ``set_tracer_provider`` is idempotent (logs a warning on re-set).
        - ``SpanProcessor.on_start(span, parent_context)`` IS the
          per-span hook where dynamic context can be stamped.

    Story 5.1 uses this hook to read ``_kernel/context.current_context().test_id``
    and write it as the ``agenteval.test_id`` span attribute. ``trace_store``'s
    ``_span_test_id`` falls back to ``span.attributes`` per Story 1b.2 H_R2,
    so this is the canonical Phase-1 per-test discriminator.

    Why this works under pabot: each worker process has its own TracerProvider
    + its own ``_kernel/context`` state; the SpanProcessor reads from worker-
    local state. No cross-worker contention.
    """

    def on_start(self, span: SDKSpan, parent_context: otel_context.Context | None = None) -> None:  # noqa: ARG002
        ctx = _kernel_context.current_context()
        if ctx is not None and ctx.test_id:
            span.set_attribute(AGENTEVAL_TEST_ID, ctx.test_id)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


class Listener:
    """Robot Framework Listener v3 implementation for agenteval.

    Register via ``robot --listener AgentEval.telemetry.listener tests/``.

    Phase-1 trace backend selection: reads ``trace_backend`` config value
    (``"memory"`` default per Story 1a.6) at ``start_suite``. JSONL output
    path resolved from ``trace_path`` config value; falls back to RF's
    ``${OUTPUTDIR}`` attribute on ``start_suite`` when unset.
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self) -> None:
        """Initialize the listener; defer expensive setup to ``start_suite``."""
        self._tracer_configured: bool = False
        self._backend: MemoryBackend | JSONLBackend = MemoryBackend()
        self._output_dir: Path | None = None
        self._mcp_per_test: bool | str = True
        # Story 5.2: per-test observer registry. Adapters register their
        # `HostedMcpObserver` instance via the module-level
        # `register_active_observer()` helper during `run()`; Listener's
        # `end_test` calls `observer.clear()` on every registered observer
        # for per-test cleanup per ADR-009.
        self._observers: list[Any] = []
        # Story 5.3: per-test operational-metadata accumulator. Adapters
        # call `record_active_run_metadata(...)` from `run()` post-completion;
        # Listener's `end_test` uses this to populate the extended
        # RunManifest's Optional fields per FR39 + epics.md L1502.
        self._current_run_metadata: dict[str, Any] = {}
        # Story 8a.1: per-test frozen snapshot of all data needed by the
        # `xunit_file` hook (which runs AFTER `end_test` cleared spans).
        # Keyed by `test_id` (RF `full_name`); snapshot built in `end_test`
        # BEFORE `trace_store.clear_spans` so trace projections are still
        # readable. Values are dicts with keys: adapter, model, cost_usd,
        # completeness, mcp_coverage, total_tokens, latency_seconds,
        # trace_id, tier_breakdown, evidence_block, warnings.
        self._completed_run_metadata: dict[str, dict[str, Any]] = {}
        # Register this Listener with the module-level active-listeners
        # list so `register_active_observer()` + `record_active_run_metadata()`
        # can find it.
        _active_listeners.append(self)

    # --------------------------------------------------------------- #
    # Tracer setup (idempotent)
    # --------------------------------------------------------------- #

    def _configure_tracer_provider(self) -> None:
        """Wire the TracerProvider with the agenteval SpanProcessor chain.

        Idempotent at PROCESS scope (not per-instance) — the SECOND `Listener`
        instantiated in the same process MUST NOT stack a duplicate set of
        processors onto the existing TracerProvider. Story 5.1 code-review
        3-way HIGH-A fix 2026-05-20 (Blind H1 + Codex empirical probe +
        Edge-cases M4): pre-edit checked only the per-instance
        `_tracer_configured` flag, so under pabot worker reuse OR test
        harness re-instantiation the resilient-attach branch added 3 more
        processors → 6 total → every span stamped/redacted/exported TWICE
        (Codex empirically verified processor count of 6 after 2 start_suite
        calls). Now gated by a PROCESS-GLOBAL sentinel attribute
        (`_agenteval_listener_attached`) set on the active TracerProvider;
        once True, all future calls are no-ops.
        """
        if self._tracer_configured:
            return

        # Process-scope sentinel: if any prior Listener instance (or any other
        # caller) has already attached the agenteval processor chain to the
        # active TracerProvider, do not attach again. The sentinel lives on
        # the provider object itself so it survives across Listener instances
        # but resets when the provider is replaced (e.g., test fixtures).
        existing = trace.get_tracer_provider()
        if getattr(existing, "_agenteval_listener_attached", False):
            self._tracer_configured = True
            return

        # Story 5.1 design note (ratified into listener-integration.md
        # Trace backplane section per Story 5.1 code-review Auditor H5 fix):
        # OTel TracerProvider Resource attributes are IMMUTABLE per-provider;
        # we cannot re-write `agenteval.test_id` per test. Story 1b.2's
        # `_span_test_id` falls back to span.attributes when the Resource
        # doesn't carry the key — we leverage that fallback by deliberately
        # NOT pre-populating `agenteval.test_id` on the Resource. The
        # per-test stamping happens via `TestIdContextSpanProcessor.on_start`
        # which reads `_kernel/context.current_context().test_id` and sets
        # the SPAN-level attribute. Pre-populating the Resource with an
        # empty string would defeat the fallback (trace_store would read
        # the empty Resource value and never check span attributes).
        resource = Resource.create({})
        provider = TracerProvider(resource=resource)
        # Per-test discriminator: stamps `agenteval.test_id` on every span at
        # on_start from `_kernel/context`. Must run BEFORE RedactionProcessor
        # so the test_id is set before any other processor reads attributes.
        provider.add_span_processor(TestIdContextSpanProcessor())
        # RedactionProcessor BEFORE the exporter in the chain — single choke
        # point per NFR-SEC-01.
        provider.add_span_processor(RedactionProcessor())
        # SimpleSpanProcessor wraps the InMemorySpanExporter from Story 1b.2.
        # Synchronous export over BatchSpanProcessor was a deliberate choice
        # ratified in listener-integration.md Contract section — Phase-1 trace
        # volume is small + mid-test projection-accessor queries need to see
        # spans without a force_flush plumbing trip.
        provider.add_span_processor(SimpleSpanProcessor(trace_store._get_exporter()))  # noqa: SLF001
        # OTel's `set_tracer_provider` is one-shot per process: subsequent
        # calls log a warning and are silently rejected. If a prior caller
        # set a provider that didn't carry our sentinel, attach our
        # processors to it (post-sentinel-check guards against duplicates).
        if isinstance(existing, TracerProvider) and existing is not provider:
            existing.add_span_processor(TestIdContextSpanProcessor())
            existing.add_span_processor(RedactionProcessor())
            existing.add_span_processor(
                SimpleSpanProcessor(trace_store._get_exporter())  # noqa: SLF001
            )
            target_provider: TracerProvider = existing
        else:
            trace.set_tracer_provider(provider)
            target_provider = provider
        # Mark the active provider so future Listener instances in this
        # process see the sentinel + short-circuit before stacking duplicates.
        target_provider._agenteval_listener_attached = True  # type: ignore[attr-defined]
        # Story 1b.2's `_configure_tracer_provider` is the placeholder;
        # invoke it for downstream-consumer compatibility.
        trace_store._configure_tracer_provider()  # noqa: SLF001
        self._tracer_configured = True

    # --------------------------------------------------------------- #
    # Robot Framework Listener v3 hooks
    # --------------------------------------------------------------- #

    def start_suite(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``start_suite`` hook — configure tracer on first invocation.

        Args:
            data: RF ``TestSuite`` object (Listener v3 API).
            result: RF ``TestSuiteResult`` object (Listener v3 API).
        """
        self._configure_tracer_provider()
        # Resolve trace_backend + output_dir from RF context.
        self._resolve_backend(suite=data)

    def start_test(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``start_test`` hook — set per-test scope.

        Extracts ``data.full_name`` (canonical Listener v3 path; replaces
        the v2 ``attrs["longname"]`` shape) and binds it to
        ``_kernel/context.set_current_test_id`` so MCP servers + adapters +
        spans share the test scope. Honors PRD FR40's ``mcp_per_test``
        config — resolved at ``start_suite`` and threaded through here so
        ADR-009's per-test vs. per-suite scope decision flows from config
        to kernel context.

        Story 5.1 code-review Auditor H3 fix 2026-05-20: pre-edit dropped
        the ``scope=`` argument so every test bound `Scope = "test"`
        regardless of FR40 / `mcp_per_test` config. Now resolved via
        `_kernel/context._resolve_scope(mcp_per_test)`.
        """
        # Story 5.1 code-review Blind MED-1 fix 2026-05-20: defensive
        # unbind before any early-return path — if a prior test's end_test
        # also degraded (missing full_name), the prior context can stay
        # bound across the boundary and pollute the next test's spans.
        _kernel_context.unbind_context()
        # Story 5.3: reset per-test operational metadata accumulator so a
        # prior test's adapter calls don't leak into the next test's
        # RunManifest sidecar.
        self._current_run_metadata = {}
        test_id = self._extract_longname(data)
        suite_id = self._extract_suite_id(data)
        if not test_id:
            _msg = (
                "AgentEval Listener: missing test full_name on start_test; "
                "spans will carry an empty agenteval.test_id span attribute"
            )
            # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
            # filter doesn't drop the structured channel.
            _agenteval_warnings.record_warning(
                warning_type="AgentEval.errors.DegradedTraceWarning",
                message=_msg,
                source="telemetry.listener",
                remediation=(
                    "Verify RF emits a non-empty `full_name` on TestCase; "
                    "check listener data-object shape if running outside RF runtime"
                ),
            )
            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
            return
        scope = _kernel_context._resolve_scope(  # noqa: SLF001
            cast("bool | Literal['suite']", self._mcp_per_test)
        )
        _kernel_context.set_current_test_id(test_id, suite_id=suite_id, scope=scope)
        # Story 8a.2 AC-8a.2.1 (FR51): surface `trace_id` as a `<tag>` on the
        # test in `output.xml` so CI log spelunking + observability dashboards
        # can link RF reports to JSONL trace artifacts. The tag value is the
        # canonical RF `full_name` (mirrors `RunManifest.test_id` + JSONL
        # `trace__<suite>__<test>.jsonl` naming). Failure-mode contract:
        # missing/None `result.tags` or `add()` raise must not mask the test —
        # log WARN + continue.
        #
        # IMPORTANT (Story 8a.2 dev empirical finding 2026-05-25): tags must be
        # added to `result.tags`, NOT `data.tags`. Empirical RF Listener v3
        # behavior: `data.tags.add(...)` does NOT surface in `output.xml`;
        # only `result.tags.add(...)` does. Verified via DebugListener probe.
        tags = getattr(result, "tags", None)
        if tags is not None:
            try:
                tags.add(f"trace_id:{test_id}")
            except Exception as exc:  # noqa: BLE001 — listener must never raise.
                _log.warning(
                    "start_test: failed to add trace_id tag for %s: %s",
                    test_id,
                    exc,
                )
        # Story 5.4 AC-5.4.6: merge any pre-test (suite-level) warnings
        # captured before this `start_test` into the first bound test's
        # buffer so library-bootstrap warnings surface in the first
        # test's `Get Last Warnings` output. One-way merge; sentinel is
        # cleared post-flush so subsequent start_test calls do not see
        # the same records again.
        _agenteval_warnings.flush_pre_test_buffer(test_id)

    def end_test(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``end_test`` hook — flush JSONL + clear per-test spans.

        Per Story 5.1 AC-5.1.6: flush-then-clear ordering so a write failure
        preserves spans in memory for the next attempt.
        """
        test_id = self._extract_longname(data)
        suite_id = self._extract_suite_id(data)
        if not test_id:
            return
        # OTel's SimpleSpanProcessor buffers spans asynchronously; force a
        # flush BEFORE reading via projection accessors so synchronously-
        # ended spans are guaranteed visible.
        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            provider.force_flush(timeout_millis=5000)
        # Story 5.3 code-review 3-way HIGH-B fix 2026-05-20 (Codex empirical
        # probe + Edge-cases H2 + Blind MED-2): pre-edit treated JSONLBackend
        # `flush_test() is None` as a write failure + early-returned BEFORE
        # observer cleanup + sidecar emit. But the JSONLBackend ALSO returns
        # None for the legitimate "no spans captured" path (Story 5.1
        # Edge-cases M3 fix). Codex empirically reproduced: `memory exists True;
        # jsonl exists False` for a real `GenericAdapter.run()` under the
        # listener — Story 5.3 was effectively broken on the jsonl backend.
        # Fix: NEVER skip observer cleanup + sidecar emit. JSONL flush failure
        # is independent of run-manifest emit; the manifest's `warnings` field
        # (Story 5.4) is the right surface for surfacing JSONL failures.
        if isinstance(self._backend, JSONLBackend):
            self._backend.flush_test(test_id, suite_id=suite_id, output_dir=self._output_dir)
        # Story 5.2 code-review 1-way Auditor HIGH-F fix 2026-05-20: clear
        # observers BEFORE clearing the trace_store spans per AC-5.2.5.
        for observer in self._observers:
            clear_fn = getattr(observer, "clear", None)
            if callable(clear_fn):
                with contextlib.suppress(Exception):
                    clear_fn()
        # Story 5.3: emit the RunManifest JSON sidecar BEFORE clearing
        # trace_store spans — `get_run_manifest(test_id)` reads from the
        # exporter, so the spans must still be present. Broad except so
        # sidecar-emit failure doesn't mask test outcomes (consistent with
        # Story 5.1 JSONLBackend pattern).
        with contextlib.suppress(Exception):
            self._emit_run_manifest_sidecar(test_id=test_id, suite_id=suite_id)
        # Story 8a.1: snapshot per-test data into `_completed_run_metadata`
        # BEFORE `clear_warnings` + `clear_spans` so the `xunit_file` hook
        # (which runs after `end_suite`) can read the data. Broad-catch
        # mirrors the sidecar pattern: snapshot failure must not mask test
        # outcomes.
        with contextlib.suppress(Exception):
            self._snapshot_completed_run_metadata(test_id=test_id)
        # Story 5.4 AC-5.4.6: clear the per-test warning buffer AFTER the
        # manifest sidecar has captured its serialized form. Sequence:
        # sidecar emit → snapshot completed metadata → clear_warnings(test_id)
        # → trace_store.clear_spans → unbind_context. clear_warnings is
        # best-effort + cannot raise.
        _agenteval_warnings.clear_warnings(test_id)
        # Successful flush (or memory-only backend): clear spans for per-test
        # isolation per Story 1b.2 trace_store.clear_spans contract.
        trace_store.clear_spans(test_id)
        _kernel_context.unbind_context()

    def end_suite(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``end_suite`` hook — FR54 terminal run summary (Story 8b.2).

        Writes a 1-block agenteval summary to stdout when the env var
        ``AGENTEVAL_TERMINAL_SUMMARY=1`` is set. Default-off to avoid
        disrupting non-CI consumers. Fires only at TOP-LEVEL suite end
        (skips nested suites — distinguished by ``data.parent is None``).

        Failure-mode contract: any exception during summary computation
        is logged at WARN; the suite outcome is NOT masked.
        """
        if os.environ.get("AGENTEVAL_TERMINAL_SUMMARY") != "1":
            return
        # Only fire at the top-level suite end (nested suites have parents).
        if getattr(data, "parent", None) is not None:
            return
        try:
            from AgentEval.telemetry._terminal_summary import render_summary

            summary = render_summary(
                completed_run_metadata=self._completed_run_metadata,
            )
            sys.stdout.write(summary + "\n")
        except Exception as exc:  # noqa: BLE001 — must never raise.
            _log.warning("end_suite: terminal summary render failed: %s", exc)

    def xunit_file(self, path: str) -> None:
        """RF Listener v3 ``xunit_file`` hook — enrich JUnit XML (Story 8a.1).

        Reads ``self._completed_run_metadata`` (snapshot built in
        ``end_test`` BEFORE ``clear_spans``) and injects per-testcase
        ``<properties>`` + ``<system-out>`` + ``<system-err>`` per
        ``docs/contracts/junit-xml-enrichment.md`` via the
        ``_xunit_enrichment.enrich_xunit_file`` helper.

        Failure-mode contract: any enrichment failure is logged at WARN
        level by the helper; the original xunit file is preserved via the
        helper's atomic-write pattern. No exceptions propagate.
        """
        if not self._completed_run_metadata:
            return
        # Lazy import to avoid pulling xml.etree at listener-import time.
        # `enrich_xunit_file` has its own broad-except + WARN-log + returns
        # False on failure — it does not raise. The outer try/except covers
        # ONLY the lazy import itself (e.g., SyntaxError discovered at first
        # call) so the listener still satisfies its no-raise contract.
        # Story 8a.1 code-review LOW-3 (Claude CLI 2026-05-25): the return
        # value is now logged so a False result does not pass silently.
        try:
            from AgentEval.telemetry import _xunit_enrichment
        except Exception as exc:  # noqa: BLE001 — listener must never propagate.
            _log.warning(
                "xunit_file: failed to import _xunit_enrichment; skipping enrichment for %s: %s",
                path,
                exc,
            )
            return
        ok = _xunit_enrichment.enrich_xunit_file(Path(path), self._completed_run_metadata)
        if not ok:
            _log.warning(
                "xunit_file: enrichment returned False for %s (original file preserved per failure-mode contract)",
                path,
            )

    def output_file(self, path: str) -> None:
        """RF Listener v3 ``output_file`` hook — reserved for future use.

        Phase-1 no-op. Symmetric to ``xunit_file`` for the canonical
        ``output.xml`` artifact.
        """
        _ = path

    def close(self) -> None:
        """RF Listener v3 ``close`` hook — final cleanup; idempotent."""
        # `_tracer_configured` stays True across close (cross-suite re-use
        # is correct under pabot worker reuse).

    def register_observer(self, observer: Any) -> None:
        """Register a `HostedMcpObserver` for per-test `clear()` cleanup.

        Story 5.2 / ADR-009 per-test scope: adapters that construct a
        `HostedMcpObserver` per run should register it with the Listener so
        `end_test` calls `observer.clear()` after the JSONL flush. Duck-typed
        (any object with a `clear()` method); avoids a hard import dependency
        from `telemetry` on `mcp.observer`.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def _snapshot_completed_run_metadata(self, *, test_id: str) -> None:
        """Snapshot per-test data into ``self._completed_run_metadata[test_id]``.

        Called from ``end_test`` BEFORE ``clear_spans`` so trace_store
        projections are still readable. The snapshot is consumed later
        by ``xunit_file`` for JUnit XML enrichment (Story 8a.1 AC-8a.1.5).

        Snapshot keys:

        - ``adapter``, ``model``, ``cost_usd``, ``completeness``,
          ``mcp_coverage``: from ``self._current_run_metadata`` (populated
          via Story 5.3 ``record_active_run_metadata()`` callback).
        - ``total_tokens``: from ``trace_store.get_usage(test_id).total_tokens``.
        - ``latency_seconds``: from ``trace_store.get_latency(test_id)``.
        - ``trace_id``: from ``trace_store.get_run_manifest(test_id).test_id``
          (canonical test_id, mirrors RF ``full_name``).
        - ``tier_breakdown``: from
          ``trace_store.get_run_manifest(test_id).agenteval_tier_breakdown``.
        - ``evidence_block`` (Optional[str]): Story 5.3 evidence-block
          string for ``<system-out>``; reserved for future wiring (Phase-1
          ships ``None`` here pending evidence-block API exposure).
        - ``warnings`` (Optional[str]): joined ``DegradedTraceWarning``
          messages for ``<system-err>``; ``None`` if no warnings fired.
        """
        meta_in = dict(self._current_run_metadata)
        # Real adapters (`coding_agent/generic.py` L253 + `claude_code_cli.py`
        # L249) call `record_active_run_metadata(total_cost_usd=result.cost_usd)`
        # — the metadata key is `total_cost_usd`, NOT `cost_usd`. Story 8a.1
        # code-review HIGH-1 (Claude CLI 2026-05-25): pre-edit `meta_in.get(
        # "cost_usd")` returned None in production. Fix: prefer
        # `total_cost_usd`, fall back to `cost_usd` for forward-compat.
        snapshot: dict[str, Any] = {
            "adapter": meta_in.get("adapter_name") or meta_in.get("adapter"),
            "model": meta_in.get("model"),
            "cost_usd": meta_in.get("total_cost_usd") or meta_in.get("cost_usd"),
            "completeness": meta_in.get("completeness"),
            "mcp_coverage": meta_in.get("mcp_coverage"),
        }
        # trace_store projections (read BEFORE clear_spans).
        # Story 8a.1 code-review MED-1 (Claude CLI 2026-05-25): pre-edit
        # `total if total else None` collapsed legitimate `total_tokens=0`
        # (adapter ran but used no tokens) to None — contradicted the
        # `_format_value` docstring contract. Fix: gate on `usage is not
        # None`, not on truthy `total`.
        with contextlib.suppress(Exception):
            # `get_usage` always returns a `Usage` per
            # `_kernel/trace_store.py:365`; total is 0 when no `chat` spans
            # exist. Preserve 0 as emittable per `_format_value` contract.
            usage = trace_store.get_usage(test_id)
            snapshot["total_tokens"] = usage.input_tokens + usage.output_tokens + usage.cached_input_tokens
        with contextlib.suppress(Exception):
            latency = trace_store.get_latency(test_id)
            snapshot["latency_seconds"] = latency if latency else None
        with contextlib.suppress(Exception):
            manifest = trace_store.get_run_manifest(test_id)
            snapshot["trace_id"] = manifest.test_id if manifest else None
            snapshot["tier_breakdown"] = (
                dict(manifest.agenteval_tier_breakdown) if manifest and manifest.agenteval_tier_breakdown else None
            )
        # Warnings: read from the per-test warning buffer BEFORE clear_warnings.
        # WarningRecord is a frozen dataclass; access via attributes, not .get().
        with contextlib.suppress(Exception):
            warns = _agenteval_warnings.get_warnings(test_id)
            if warns:
                snapshot["warnings"] = "\n".join(f"[{w.warning_type}] {w.message}" for w in warns)
        self._completed_run_metadata[test_id] = snapshot

    def _emit_run_manifest_sidecar(self, *, test_id: str, suite_id: str) -> None:
        """Build the extended `RunManifest` + emit the JSON sidecar (Story 5.3).

        Combines the 7 ratified fields from `_kernel/trace_store.get_run_manifest(test_id)`
        (the projection accessor — library_version, test_id, suite_id,
        redaction_policy_hash, started_at, ended_at, agenteval_tier_breakdown)
        with the accumulated operational metadata from `self._current_run_metadata`
        (the new Story 5.3 Optional fields populated by adapters via
        `record_active_run_metadata()` during `run()`).

        Failure-mode contract per AC-5.3.2: failures don't mask test outcomes.
        Outer `contextlib.suppress(Exception)` at the call site handles any
        unexpected raise here; this helper also handles its own failures
        via the `RunManifestEmitter.emit()` warning-and-return-None pattern.
        """
        # Lazy import to avoid circular dependency (run_manifest.py imports
        # from backends.py which is in the same package).
        from AgentEval.telemetry.run_manifest import RunManifestEmitter

        try:
            base_manifest = trace_store.get_run_manifest(test_id)
        except Exception:  # noqa: BLE001
            # Story 5.4 code-review 1-way Edge-cases HIGH-4 fix 2026-05-20:
            # pre-edit the no-spans branch dropped any pending
            # `DegradedTraceWarning` records because `end_test` calls
            # `clear_warnings(test_id)` AFTER this helper returns. If
            # the test recorded a warning (e.g., unknown_trace_backend
            # during start_suite → flushed into the first test) but
            # produced zero spans (config-only test), the structured
            # record was silently lost. Synthesize a minimal manifest
            # carrying just the warnings + identity fields so the
            # sidecar still captures the degradation signal.
            warning_records = _agenteval_warnings.get_warnings(test_id)
            if not warning_records:
                return
            from datetime import datetime

            from AgentEval._kernel.redaction import redaction_policy_hash
            from AgentEval.types import RunManifest

            try:
                from AgentEval import __version__ as _library_version
            except Exception:  # noqa: BLE001
                _library_version = "0.0.0"
            now = datetime.now(UTC)
            try:
                base_manifest = RunManifest(
                    library_version=_library_version,
                    test_id=test_id,
                    suite_id=suite_id,
                    redaction_policy_hash=redaction_policy_hash(),
                    started_at=now,
                    ended_at=now,
                )
            except Exception:  # noqa: BLE001
                # If even the minimal construction fails, give up
                # silently — outer `contextlib.suppress` will catch.
                return
        # Story 5.3: merge the operational metadata into the ratified
        # manifest. `dataclasses.replace` returns a new frozen instance
        # with the additional fields populated.
        import dataclasses

        accumulated = dict(self._current_run_metadata)
        if isinstance(self._backend, JSONLBackend):
            accumulated.setdefault("trace_backend", "jsonl")
        else:
            accumulated.setdefault("trace_backend", "memory")
        # Story 5.4 AC-5.4.4: pull the structured warning records for this
        # test out of the per-test buffer + serialize them to the 5-key
        # dict shape that RunManifest.warnings now expects. Read happens
        # BEFORE clear_warnings (which runs in end_test after this helper).
        # Best-effort; failure leaves accumulated["warnings"] as the
        # Story 5.3 default empty list.
        try:
            warning_records = _agenteval_warnings.get_warnings(test_id)
            accumulated["warnings"] = [_agenteval_warnings.warning_record_to_dict(r) for r in warning_records]
        except Exception:  # noqa: BLE001
            accumulated.setdefault("warnings", [])
        # Filter to fields that actually exist on RunManifest; ignore any
        # adapter-provided kwargs not in the dataclass schema.
        manifest_fields = {f.name for f in dataclasses.fields(base_manifest)}
        filtered = {k: v for k, v in accumulated.items() if k in manifest_fields}
        # Story 5.3 code-review 1-way HIGH-J fix 2026-05-20 (Blind H2 empirical):
        # `dataclasses.replace` does NOT validate field types — it accepts ANY
        # value + constructs a new frozen instance. Without coercion, an
        # adapter passing `total_cost_usd=Decimal("0.01")` flowed through to
        # `json.dump(default=str)` and produced a string in JSON, failing
        # schema validation `["number", "null"]` at consumer time. The
        # `except TypeError` was dead code. Now: coerce known numeric fields
        # to `float` BEFORE replace; coerce `seed` to `int`.
        if "total_cost_usd" in filtered and filtered["total_cost_usd"] is not None:
            try:
                filtered["total_cost_usd"] = float(filtered["total_cost_usd"])
            except (TypeError, ValueError):
                del filtered["total_cost_usd"]
        if "seed" in filtered and filtered["seed"] is not None:
            try:
                filtered["seed"] = int(filtered["seed"])
            except (TypeError, ValueError):
                del filtered["seed"]
        try:
            extended_manifest = dataclasses.replace(base_manifest, **filtered)
        except TypeError:
            # Field type mismatch — skip the operational fields, emit
            # the base manifest only.
            extended_manifest = base_manifest
        RunManifestEmitter().emit(
            extended_manifest,
            output_dir=self._output_dir,
            suite_id=suite_id,
            test_id=test_id,
        )

    def record_run_metadata(self, **metadata: Any) -> None:
        """Accumulate per-run operational metadata for the RunManifest sidecar.

        Story 5.3: adapters call `record_active_run_metadata(adapter_name=...,
        adapter_version=..., model=..., mcp_servers=..., total_cost_usd=...,
        completeness=..., mcp_coverage=..., seed=..., prompt_hashes=...)`
        from `run()` post-completion. The Listener accumulates the kwargs in
        `_current_run_metadata`; `end_test` builds an extended `RunManifest`
        from the projection accessor + these accumulated fields + emits the
        JSON sidecar via `RunManifestEmitter`.

        Merge semantics (Story 5.3 code-review 2-way HIGH-D fix 2026-05-20 —
        Blind H4 + Codex empirical probe: pre-edit last-wins clobbered
        `adapter_name`/`model` under multi-adapter runs):
        - **List fields** (mcp_servers, prompt_hashes, warnings): concat.
        - **`total_cost_usd`**: SUM across calls (was last-wins; clobbered cost).
        - **Other scalar fields** (adapter_name, adapter_version, model,
          trace_backend, completeness, mcp_coverage, seed): skip None
          updates so a second adapter passing `model=None` doesn't clobber
          a real value from the first; otherwise last-wins. Multi-adapter
          tests should still emit DF-5.3-S5 carry-over notes about identity
          provenance (the Phase-1 manifest can't honestly attribute mixed
          adapters; future per-run-entry array shape).
        """
        for key, value in metadata.items():
            if key in ("mcp_servers", "prompt_hashes", "warnings"):
                existing = self._current_run_metadata.get(key, [])
                if isinstance(existing, list) and isinstance(value, list):
                    self._current_run_metadata[key] = [*existing, *value]
                else:
                    self._current_run_metadata[key] = value
            elif key == "total_cost_usd":
                # SUM cost across multi-adapter calls (HIGH-D fix).
                existing_cost = self._current_run_metadata.get(key)
                if isinstance(existing_cost, int | float) and isinstance(value, int | float):
                    self._current_run_metadata[key] = float(existing_cost) + float(value)
                elif value is not None:
                    self._current_run_metadata[key] = value
            else:
                # Scalar fields: skip None updates so second adapter doesn't
                # clobber a real value with its own None (HIGH-D fix).
                if value is not None:
                    self._current_run_metadata[key] = value

    # --------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------- #

    def _resolve_backend(self, suite: Any) -> None:
        """Resolve ``trace_backend`` + output_dir from config + RF context.

        Story 4.3 4-level ConfigValue precedence (init_arg → env → dotenv →
        default). For the Listener (no init_arg surface yet — Listener is
        constructed by RF without kwargs), the chain reduces to env → dotenv
        → default.

        Output dir: prefers ``trace_path`` config; falls back to RF's
        ``${OUTPUTDIR}`` from suite metadata or ``Path.cwd()``.
        """
        config = _kernel_context.resolve_config({})
        backend_name = config.get("trace_backend", "memory")
        if backend_name == "jsonl":
            self._backend = JSONLBackend()
        elif backend_name == "memory":
            self._backend = MemoryBackend()
        else:
            # Story 5.1 code-review Edge-cases M2 fix 2026-05-20: unknown
            # trace_backend silently fell back to memory pre-edit — operators
            # typoing `jsnol` or `jsonl1` would lose JSONL artifacts without
            # any signal. Warn loud + fall back to memory for safety.
            _msg = (
                f"AgentEval Listener: unknown trace_backend={backend_name!r}; "
                "falling back to 'memory'. Valid values: {'memory', 'jsonl'}."
            )
            # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
            # filter doesn't drop the structured channel.
            _agenteval_warnings.record_warning(
                warning_type="AgentEval.errors.DegradedTraceWarning",
                message=_msg,
                source="telemetry.listener",
                remediation=(
                    "Set AGENTEVAL_TRACE_BACKEND to one of {'memory', 'jsonl'}; "
                    "the misspelled value silently falls back to memory backend"
                ),
            )
            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
            self._backend = MemoryBackend()
        # Story 5.1 code-review Auditor H3 fix 2026-05-20: read mcp_per_test
        # config so start_test can wire FR40 scope through set_current_test_id.
        mcp_per_test_raw = config.get("mcp_per_test", True)
        # Coerce to the kernel context's expected union (bool | Literal["suite"]).
        if isinstance(mcp_per_test_raw, str) and mcp_per_test_raw.lower() == "suite":
            self._mcp_per_test = "suite"
        else:
            self._mcp_per_test = bool(mcp_per_test_raw)
        trace_path = config.get("trace_path")
        if trace_path:
            # Story 5.1 code-review Edge-cases L2 fix 2026-05-20: resolve to
            # absolute path at suite-start so per-pabot-worker CWD divergence
            # doesn't move the output dir under us mid-suite.
            self._output_dir = Path(str(trace_path)).resolve()
        else:
            self._output_dir = self._extract_outputdir(suite)

    @staticmethod
    def _extract_longname(data: Any) -> str:
        """Read the canonical test/suite full_name from a Listener v3 data object.

        Listener v3's ``data`` is the live ``TestCase``/``TestSuite``
        instance; ``data.full_name`` is the canonical dotted path. Fallback
        chain handles older RF versions + edge cases.
        """
        for attr in ("full_name", "longname", "name"):
            value = getattr(data, attr, None)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _extract_suite_id(data: Any) -> str:
        """Read the suite-level full_name from a test or suite data object."""
        # Test data carries `parent` pointing at the suite; suite data is its
        # own ancestor. Walk up to the top-most ancestor's full_name.
        node: Any = getattr(data, "parent", data) or data
        while True:
            parent = getattr(node, "parent", None)
            if parent is None:
                break
            node = parent
        return Listener._extract_longname(node)

    @staticmethod
    def _extract_outputdir(suite: Any) -> Path | None:
        """Read RF's ``${OUTPUTDIR}`` via the canonical Listener v3 API.

        Story 5.1 code-review Blind H4 fix 2026-05-20: pre-edit read
        ``suite.output_directory`` which RF 7.x's ``TestSuite`` does NOT
        expose. Result: every call returned ``None`` and the JSONL backend
        always fell back to ``Path.cwd()``, polluting the repo root when
        ``trace_path`` was unset. Canonical access path is via
        ``robot.running.context.EXECUTION_CONTEXTS.current.output.directory``;
        we resolve it lazily to avoid forcing the listener to fail when
        invoked outside an RF runtime (e.g., direct Python invocation).
        """
        # Try the canonical RF Listener v3 execution-context path first.
        try:
            from robot.running.context import EXECUTION_CONTEXTS

            current = EXECUTION_CONTEXTS.current
            if current is not None:
                output_dir = getattr(current.output, "directory", None)
                if output_dir:
                    return Path(str(output_dir))
        except Exception:  # noqa: BLE001
            # `EXECUTION_CONTEXTS.current` may be None outside RF runtime
            # (direct unit-test invocation) or RF's API may have shifted.
            # Fall through to the legacy attribute probe + cwd fallback.
            pass
        # Legacy fallback: some RF versions / non-RF callers may set
        # ``output_directory`` on the suite object directly.
        configured = getattr(suite, "output_directory", None)
        if isinstance(configured, str | Path) and str(configured):
            return Path(str(configured))
        return None
