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

"""Unit tests for `src/AgentEval/mcp/version_gate.py` (Story 3.1)."""

from __future__ import annotations

import pytest

from AgentEval.errors import (
    AgentEvalCompatError,
    AgentEvalError,
    UnsupportedMCPVersionError,
)
from AgentEval.mcp.version_gate import SUPPORTED_RANGE, check_protocol_version


def test_supported_range_constant() -> None:
    assert SUPPORTED_RANGE == "mcp>=1.0,<2.0"


def test_check_passes_for_latest_protocol_version() -> None:
    from mcp.types import LATEST_PROTOCOL_VERSION

    # SDK's latest version IS in the supported set.
    check_protocol_version(LATEST_PROTOCOL_VERSION)  # no raise


def test_check_passes_for_known_supported_versions() -> None:
    """Every string in the SDK's SUPPORTED_PROTOCOL_VERSIONS passes."""
    from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS

    for version in SUPPORTED_PROTOCOL_VERSIONS:
        check_protocol_version(version)


def test_check_raises_on_none() -> None:
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        check_protocol_version(None)
    assert exc_info.value.server_version is None
    assert exc_info.value.supported_range == SUPPORTED_RANGE


def test_check_raises_on_empty_string() -> None:
    with pytest.raises(UnsupportedMCPVersionError):
        check_protocol_version("")


def test_check_raises_on_future_unsupported_version() -> None:
    with pytest.raises(UnsupportedMCPVersionError) as exc_info:
        check_protocol_version("2099-12-31")
    assert exc_info.value.server_version == "2099-12-31"


def test_check_raises_on_garbage_version_string() -> None:
    with pytest.raises(UnsupportedMCPVersionError):
        check_protocol_version("not-a-version-at-all")


def test_unsupported_mcp_version_error_inherits_compat() -> None:
    assert issubclass(UnsupportedMCPVersionError, AgentEvalCompatError)
    assert issubclass(UnsupportedMCPVersionError, AgentEvalError)


def test_unsupported_mcp_version_error_code() -> None:
    assert UnsupportedMCPVersionError.error_code == "UNSUPPORTED_MCP_VERSION"


def test_unsupported_mcp_version_error_str_matches_fr8_format() -> None:
    """PRD FR8 verbatim wording: `MCP server version <X> outside library tested range <range>`."""
    exc = UnsupportedMCPVersionError(
        "MCP server version 2099-01-01 outside library tested range mcp>=1.0,<2.0",
        server_version="2099-01-01",
        supported_range="mcp>=1.0,<2.0",
    )
    assert str(exc) == "MCP server version 2099-01-01 outside library tested range mcp>=1.0,<2.0"


def test_unsupported_mcp_version_error_structured_attrs() -> None:
    exc = UnsupportedMCPVersionError(
        "boom",
        server_version="2099-12-31",
        supported_range="mcp>=1.0,<2.0",
    )
    assert exc.server_version == "2099-12-31"
    assert exc.supported_range == "mcp>=1.0,<2.0"


def test_unsupported_mcp_version_error_does_not_inherit_fr59_intermediate() -> None:
    """Story 3.1 design: this leaf does NOT inherit `_FR59Tier1SetupFailureError`.

    Per Epic 2 retro Action #3 ratified 2026-05-19: runtime errors
    inherit `AgentEvalCompatError` DIRECTLY. The FR59 5-line setup-
    failure layout doesn't fit runtime negotiation context.
    """
    from AgentEval.errors import _FR59Tier1SetupFailureError

    assert not issubclass(UnsupportedMCPVersionError, _FR59Tier1SetupFailureError)
