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

"""RunManifest JSON sidecar emitter (Story 5.3 / PRD FR39).

Per PRD FR39 + architecture L669: every agenteval run produces a JSON sidecar
at ``<output_dir>/agenteval/run-manifest__<suite>__<test>.json`` describing
the run's reproducibility metadata (library version + adapter + model + MCP
servers + cost + coverage + completeness + redaction policy hash + tier
breakdown + warnings + seed + prompt hashes).

Architecture L1248-1251 telemetry project tree gets a new sibling file
``run_manifest.py`` (Story 5.3 D-3 path-shape fix: sidecar lives under the
same ``agenteval/`` subdirectory as Story 5.1's JSONL trace artifacts).

The emitter is invoked by ``Listener.end_test`` after ``trace_store.clear_spans``
but before ``unbind_context``. The manifest itself is built by
``_kernel/trace_store.get_run_manifest(test_id)`` (the 7 ratified fields per
architecture L896) + augmented with operational data the Listener accumulated
via adapter ``record_active_run_metadata`` calls during the test (the new
Story 5.3 Optional fields per epics.md L1502 + FR39).

Failure-mode contract: write failures emit ``UserWarning`` (DF-5.3-S1
forward-ref to Story 5.4's ``DegradedTraceWarning``) and do NOT raise.
Test outcomes must not be masked by sidecar-write hygiene — same pattern
as Story 5.1's ``JSONLBackend.flush_test``.

References:
    - PRD FR39: RunManifest JSON sidecar contents + path convention
    - architecture L669 + L896: ratified RunManifest dataclass shape
    - epics.md L1502: operational field set (Story 5.3 D-2 drift fix
      extends the dataclass to a union of all three sources)
    - `docs/contracts/run-manifest-schema.json`: published JSON schema
    - `docs/contracts/mcp-coverage-detection.md`: mcp_coverage Literal values
"""

from __future__ import annotations

import dataclasses
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from AgentEval._kernel.redaction import redact_dict
from AgentEval.telemetry.backends import _sanitize_path_segment

if TYPE_CHECKING:
    from AgentEval.types import RunManifest

__all__ = ["RunManifestEmitter"]


class RunManifestEmitter:
    """JSON sidecar emitter for `RunManifest` artifacts.

    Per AC-5.3.2: writes ``<output_dir>/agenteval/run-manifest__<suite>__<test>.json``
    using the same sanitization + path-shape pattern as Story 5.1's
    `JSONLBackend`. On write failure: emits `UserWarning` and returns ``None``;
    does not raise (test outcomes are not masked by sidecar hygiene).

    On a ``None`` manifest input: skips writing (avoids the phantom 0-byte
    file pattern caught by Story 5.2 Codex HIGH-J).
    """

    name = "run_manifest"

    def emit(
        self,
        manifest: RunManifest | None,
        *,
        output_dir: Path | None,
        suite_id: str,
        test_id: str,
    ) -> Path | None:
        """Serialize `manifest` to JSON at the canonical sidecar path.

        Args:
            manifest: The `RunManifest` to serialize, or ``None`` to skip.
            output_dir: Directory to write the artifact into; defaults to
                ``Path.cwd()``. The function creates
                ``<output_dir>/agenteval/`` if missing.
            suite_id: RF Listener v3 suite identifier (used in the filename).
            test_id: RF Listener v3 test identifier (used in the filename).

        Returns:
            The written file path on success; ``None`` when skipped (manifest
            is None) or on write failure (warning emitted).
        """
        if manifest is None:
            # Story 5.3 phantom-file avoidance per Story 5.2 Codex HIGH-J
            # pattern: don't create an empty file when there's nothing to
            # record.
            return None

        target_dir = (output_dir if output_dir is not None else Path.cwd()) / "agenteval"
        safe_suite = _sanitize_path_segment(suite_id or "_suite")
        safe_test = _sanitize_path_segment(test_id or "_test")
        # Story 5.3 code-review 1-way Auditor HIGH-E fix 2026-05-20:
        # PRD L1558 FR39 mandates the path filename `manifest__<suite>__<test>.json`
        # (NOT `run-manifest__...`). Pre-edit Story 5.3 spec D-3 only
        # justified parity with Story 5.1's `trace__<suite>__<test>.jsonl`
        # path-shape; never reconciled against the PRD-pinned filename.
        # PRD wins per fix-the-losing-source-NOW.
        target_path = target_dir / f"manifest__{safe_suite}__{safe_test}.json"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            payload = self._manifest_to_redacted_dict(manifest)
            with target_path.open("w", encoding="utf-8") as fp:
                # Story 5.3 code-review MED-E4 fix 2026-05-20 (Edge-cases):
                # `default=str` emits `"2026-05-20 00:00:00"` (space sep) for
                # datetimes, but JSON Schema `format: date-time` is RFC 3339
                # which mandates the `T` separator. Use `.isoformat()` via a
                # narrow default callable.
                json.dump(payload, fp, ensure_ascii=False, default=_json_default)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            # Story 5.3: same widened-except pattern as Story 5.1
            # `JSONLBackend.flush_test` (Story 5.1 code-review Edge-cases H2
            # widening — catch JSON-serialization failures too). DF-5.3-S1
            # forward-ref: replace `UserWarning` with `DegradedTraceWarning`
            # once Story 5.4 lands the class.
            warnings.warn(
                f"AgentEval RunManifest JSON sidecar write failed at {target_path}: {exc}; "
                "test outcome NOT masked — sidecar artifact missing for this run only "
                "(DF-5.3-S1 upgrade to DegradedTraceWarning when Story 5.4 lands)",
                UserWarning,
                stacklevel=2,
            )
            return None
        return target_path

    @staticmethod
    def _manifest_to_redacted_dict(manifest: RunManifest) -> dict[str, Any]:
        """Convert a `RunManifest` to a JSON-serializable dict + apply redaction.

        Per AC-5.3.7: defense-in-depth redaction at the emit boundary so
        even if upstream producers (adapters, observer) leaked a credential
        into a manifest field (e.g., a model identifier containing an API
        key), the sidecar never carries the raw secret.

        `datetime` fields are serialized via `default=str` at the `json.dump`
        level downstream; here we keep the dict shape intact for redaction.
        """
        raw = dataclasses.asdict(manifest)
        # Walk top-level string fields through `redact()` via the dict variant.
        return redact_dict(raw)


def _json_default(obj: Any) -> str:
    """JSON serialization fallback — RFC 3339 ISO format for datetime, str() otherwise."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
