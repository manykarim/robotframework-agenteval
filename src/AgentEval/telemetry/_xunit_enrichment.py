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

"""JUnit XML enrichment for the Story 5.1 Listener (Story 8a.1).

Private helper used exclusively by ``telemetry/listener.Listener.xunit_file``.
The 9 ratified ``agenteval.*`` ``<property>`` names + injection semantics +
idempotency + atomic-write contract are documented at
``docs/contracts/junit-xml-enrichment.md`` (filled by Story 8a.1).

Design constraints:

1. The xunit XML is enriched in place via atomic write
   (``write to {path}.tmp → os.replace``) so any failure preserves the
   original file (no partial-write corruption).
2. Re-enrichment is idempotent: properties are matched by ``name=`` and
   replaced in place, never duplicated.
3. ``test_id`` derivation is ``f"{classname}.{name}"`` to match the RF
   Listener v3 ``data.full_name`` shape (canonical RF dotted path).
4. The 9 property names use the alphabetical ordering for diff stability.

References:
    - ``docs/contracts/junit-xml-enrichment.md`` (Phase-1 stable per Story 8a.1)
    - ``docs/contracts/error-class-hierarchy.md`` L73-L94 (FR50 exit codes,
      consulted by ``AgentEval.cli.error_code_to_exit_code`` rather than this
      module — but the same per-leaf table)
    - architecture L1248: ``telemetry/listener.py``
"""

from __future__ import annotations

import json
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from AgentEval.telemetry.semconv import (
    XUNIT_PROP_ADAPTER,
    XUNIT_PROP_COMPLETENESS,
    XUNIT_PROP_COST_USD,
    XUNIT_PROP_LATENCY_SECONDS,
    XUNIT_PROP_MCP_COVERAGE,
    XUNIT_PROP_MODEL,
    XUNIT_PROP_TIER_BREAKDOWN,
    XUNIT_PROP_TOTAL_TOKENS,
    XUNIT_PROP_TRACE_ID,
)

__all__ = [
    "PROPERTY_NAMES",
    "enrich_xunit_file",
]

_logger = logging.getLogger("AgentEval.telemetry.xunit_enrichment")

# 9 ratified property names (alphabetical for diff stability per
# `docs/contracts/junit-xml-enrichment.md`). Sourced from `semconv.py`
# per NFR-COMPAT-06 single-facade rule.
PROPERTY_NAMES: tuple[str, ...] = (
    XUNIT_PROP_ADAPTER,
    XUNIT_PROP_COMPLETENESS,
    XUNIT_PROP_COST_USD,
    XUNIT_PROP_LATENCY_SECONDS,
    XUNIT_PROP_MCP_COVERAGE,
    XUNIT_PROP_MODEL,
    XUNIT_PROP_TIER_BREAKDOWN,
    XUNIT_PROP_TOTAL_TOKENS,
    XUNIT_PROP_TRACE_ID,
)


def _format_value(name: str, raw: Any) -> str | None:
    """Format a metadata value for the JUnit XML ``value=`` attribute.

    Returns ``None`` to signal the property should be omitted (per the
    fallback rule in AC-8a.1.2 / contract: empty/missing → property omitted).
    """
    if raw is None:
        return None
    if name == XUNIT_PROP_COST_USD:
        try:
            return f"{float(raw):.4f}"
        except (TypeError, ValueError):
            return None
    if name == XUNIT_PROP_LATENCY_SECONDS:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        # latency_seconds is omitted when 0.0 only if no spans existed; the
        # caller decides whether to pass 0.0 (real but zero) or None (missing).
        return f"{value:.3f}"
    if name == XUNIT_PROP_TOTAL_TOKENS:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return None
        # Zero tokens is a legitimate value when an adapter ran but used no
        # tokens; still emit. The caller passes None to omit.
        return str(n)
    if name == XUNIT_PROP_TIER_BREAKDOWN:
        # Expect a dict[int, int] from `get_run_manifest(test_id).agenteval_tier_breakdown`.
        if not isinstance(raw, dict) or not raw:
            return None
        # Sort by integer key for deterministic output; serialize keys as
        # strings (JSON object keys must be strings).
        try:
            sorted_dict = {str(k): int(v) for k, v in sorted(raw.items())}
        except (TypeError, ValueError):
            return None
        return json.dumps(sorted_dict, sort_keys=True)
    # Default: stringify anything else (strings, ints, floats).
    text = str(raw).strip()
    return text or None


def _build_property_elements(metadata: dict[str, Any]) -> list[ET.Element]:
    """Build the ``<property>`` child elements for a single ``<testcase>``.

    ``metadata`` is the frozen snapshot stored on the Listener's
    ``_completed_run_metadata[test_id]`` dict (see
    ``telemetry/listener.Listener._snapshot_completed_run_metadata``). Keys
    are the source-attribute names listed in AC-8a.1.2; this function maps
    them to ``agenteval.*`` property names + applies the per-name formatting.
    """
    # Map: property name -> source key in the metadata snapshot dict.
    source_map: dict[str, str] = {
        XUNIT_PROP_ADAPTER: "adapter",
        XUNIT_PROP_COMPLETENESS: "completeness",
        XUNIT_PROP_COST_USD: "cost_usd",
        XUNIT_PROP_LATENCY_SECONDS: "latency_seconds",
        XUNIT_PROP_MCP_COVERAGE: "mcp_coverage",
        XUNIT_PROP_MODEL: "model",
        XUNIT_PROP_TIER_BREAKDOWN: "tier_breakdown",
        XUNIT_PROP_TOTAL_TOKENS: "total_tokens",
        XUNIT_PROP_TRACE_ID: "trace_id",
    }
    elements: list[ET.Element] = []
    for name in PROPERTY_NAMES:
        raw = metadata.get(source_map[name])
        formatted = _format_value(name, raw)
        if formatted is None:
            continue
        elem = ET.Element("property", {"name": name, "value": formatted})
        elements.append(elem)
    return elements


def _replace_or_append_properties(
    testcase: ET.Element,
    new_properties: list[ET.Element],
) -> None:
    """Inject ``<property>`` elements into a ``<testcase>``, idempotent by name.

    If a ``<properties>`` child already exists, properties matching the
    ``agenteval.*`` namespace are removed first and then the new set is
    appended. Non-``agenteval.*`` properties (e.g., user-added or CI-tool
    additions) are preserved.

    If no ``<properties>`` child exists, one is created.
    """
    properties_elem = testcase.find("properties")
    if properties_elem is None:
        properties_elem = ET.SubElement(testcase, "properties")
        # Move to first-child position for canonical ordering (standard JUnit
        # XML places <properties> before <failure>/<system-out>/<system-err>).
        testcase.remove(properties_elem)
        testcase.insert(0, properties_elem)

    # Idempotency: drop existing agenteval.* properties.
    for child in list(properties_elem):
        if child.tag == "property" and child.get("name", "").startswith("agenteval."):
            properties_elem.remove(child)
    for elem in new_properties:
        properties_elem.append(elem)


def _replace_or_append_cdata_child(
    testcase: ET.Element,
    tag: str,
    content: str | None,
) -> None:
    """Inject (or remove) a ``<system-out>`` / ``<system-err>`` child element.

    Idempotent: re-running replaces existing content. If ``content`` is
    None or empty, the child is removed (so a test with no evidence/warnings
    doesn't carry stale child elements from a prior enrichment).

    Note: Python's ``xml.etree.ElementTree`` does not emit CDATA sections
    natively; we set ``.text`` which gets XML-escaped. The contract at
    ``docs/contracts/junit-xml-enrichment.md`` permits either CDATA or
    escaped text (both are valid JUnit XML and CI parsers handle both).
    """
    existing = testcase.find(tag)
    if not content:
        if existing is not None:
            testcase.remove(existing)
        return
    if existing is None:
        existing = ET.SubElement(testcase, tag)
    existing.text = content


def _test_id_for_testcase(testcase: ET.Element) -> str:
    """Derive the canonical ``test_id`` for a ``<testcase>`` element.

    Maps to RF Listener v3's ``data.full_name`` shape via
    ``f"{classname}.{name}"``. Flat-suite tests have ``classname`` = the
    suite's name; nested-suite tests have ``classname`` = the dotted
    parent path.
    """
    classname = testcase.get("classname", "")
    name = testcase.get("name", "")
    if classname and name:
        return f"{classname}.{name}"
    return name


def enrich_xunit_file(
    path: Path,
    metadata_by_test_id: dict[str, dict[str, Any]],
) -> bool:
    """Enrich the JUnit XML file at ``path`` with per-testcase agenteval metadata.

    Args:
        path: Path to the JUnit XML file (RF's ``--xunit junit.xml`` output).
        metadata_by_test_id: Dict keyed by ``test_id`` (RF ``full_name``),
            with snapshot dicts containing the source values for the 9
            ``agenteval.*`` properties + ``evidence_block`` (string for
            ``<system-out>``) + ``warnings`` (string for ``<system-err>``).

    Returns:
        ``True`` if enrichment succeeded; ``False`` if a failure was logged
        and the original file was preserved.

    Failure mode: any exception during parse/inject/write is logged at
    WARN level and the function returns False without raising. The original
    file is preserved via atomic write (write to ``path.tmp`` → ``os.replace``).
    """
    if not path.exists():
        _logger.warning("xunit_file does not exist; skipping enrichment: %s", path)
        return False
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # Standard JUnit XML can wrap testcases in <testsuite> or <testsuites>.
        # Walk all <testcase> descendants regardless of wrapper structure.
        for testcase in root.iter("testcase"):
            test_id = _test_id_for_testcase(testcase)
            metadata = metadata_by_test_id.get(test_id)
            if metadata is None:
                continue
            properties = _build_property_elements(metadata)
            _replace_or_append_properties(testcase, properties)
            _replace_or_append_cdata_child(testcase, "system-out", metadata.get("evidence_block"))
            _replace_or_append_cdata_child(testcase, "system-err", metadata.get("warnings"))
        # Atomic write: serialize to tmp, then os.replace.
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
            os.replace(tmp_path, path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
    except Exception as exc:  # noqa: BLE001 — failure-mode contract is broad-catch
        _logger.warning("xunit enrichment failed (file preserved): %s", exc, exc_info=True)
        return False
    return True
