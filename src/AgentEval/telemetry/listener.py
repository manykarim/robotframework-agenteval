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

import logging
import warnings
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
from AgentEval._kernel.redaction import RedactionProcessor
from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend
from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID

__all__ = ["Listener", "TestIdContextSpanProcessor"]

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
        test_id = self._extract_longname(data)
        suite_id = self._extract_suite_id(data)
        if not test_id:
            warnings.warn(
                "AgentEval Listener: missing test full_name on start_test; "
                "spans will carry an empty agenteval.test_id span attribute "
                "(DF-5.1-S1 upgrade to DegradedTraceWarning when Story 5.4 lands)",
                UserWarning,
                stacklevel=2,
            )
            return
        scope = _kernel_context._resolve_scope(  # noqa: SLF001
            cast("bool | Literal['suite']", self._mcp_per_test)
        )
        _kernel_context.set_current_test_id(test_id, suite_id=suite_id, scope=scope)

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
        flush_result: Path | None = None
        if isinstance(self._backend, JSONLBackend):
            flush_result = self._backend.flush_test(test_id, suite_id=suite_id, output_dir=self._output_dir)
            # On JSONL write failure: preserve spans in memory for next attempt
            # (the failure was already warned about in JSONLBackend.flush_test).
            if flush_result is None:
                # JSONL write failed (warning already emitted by backend).
                # Drop the test_id binding but PRESERVE the spans in memory
                # — the next-test query filters by test_id so they stay out
                # of subsequent tests' projection-accessor results. Story 5.1
                # code-review Blind LOW-2 fix 2026-05-20: pre-edit comment
                # claimed "operator can re-attempt via a custom hook" but
                # no such hook exists; the spans simply persist until the
                # exporter is reset (next provider configuration OR test
                # process exit).
                _kernel_context.unbind_context()
                return
        # Successful flush (or memory-only backend): clear spans for per-test
        # isolation per Story 1b.2 trace_store.clear_spans contract.
        trace_store.clear_spans(test_id)
        _kernel_context.unbind_context()

    def end_suite(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``end_suite`` hook — Phase-1 no-op.

        Story 8a.1 may grow this into a JUnit XML enrichment hand-off;
        Phase-1 the per-test work is already done in ``end_test``.
        """

    def xunit_file(self, path: str) -> None:
        """RF Listener v3 ``xunit_file`` hook — reserved for Story 8a.1 enrichment.

        Phase-1 no-op. Story 8a.1 will populate this with per-testcase
        ``<properties>`` enrichment (cost, tokens, latency, coverage,
        completeness, trace_id, adapter, model, tier, error_code) per
        ``docs/contracts/junit-xml-enrichment.md``.
        """
        _ = path

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
            warnings.warn(
                f"AgentEval Listener: unknown trace_backend={backend_name!r}; "
                "falling back to 'memory'. Valid values: {'memory', 'jsonl'}. "
                "(DF-5.1-S1 upgrade to DegradedTraceWarning when Story 5.4 lands)",
                UserWarning,
                stacklevel=2,
            )
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
