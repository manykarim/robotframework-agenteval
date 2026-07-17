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

"""Registry wiring + stub-adapter metadata for the six CLI adapters."""

from __future__ import annotations

import pytest

from AgentEval._core.adapter import Adapter, get_adapter
from AgentEval._core.cli_adapter import SubprocessCLIAdapter
from AgentEval._core.cli_adapters import SLUG_MAP
from AgentEval._core.errors import AdapterError

EXPECTED = {
    "claude-code": ("claude", "FULL"),
    "gemini": ("gemini", "FULL"),
    "codex": ("codex", "PARTIAL"),
    "opencode": ("opencode", "PARTIAL"),
    "kilo": ("kilo", "DEGRADED"),
    "copilot": ("copilot", "DEGRADED"),
}


def test_slug_map_covers_exactly_the_six_slugs() -> None:
    assert set(SLUG_MAP) == set(EXPECTED)


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_get_adapter_resolves_each_cli_slug(slug: str) -> None:
    adapter = get_adapter(slug)
    assert isinstance(adapter, SubprocessCLIAdapter)
    assert isinstance(adapter, Adapter)
    assert adapter.slug == slug
    assert adapter.name == slug


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_stub_metadata_matches_documented_capability(slug: str) -> None:
    binary, fidelity = EXPECTED[slug]
    cls = SLUG_MAP[slug]
    assert cls.binary_name == binary
    assert cls.fidelity == fidelity
    assert cls.validation_ceiling  # every adapter names what it cannot report
    assert cls.install_hint  # missing-binary path can always give guidance


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_template_methods_are_stub_or_implemented(slug: str) -> None:
    """Each adapter's template methods are either both filled or both still stubs.

    As concrete parse strategies land (claude-code first), an adapter graduates
    from raising ``NotImplementedError`` to returning a real argv/result. This
    test stays green across that transition: a stub raises on both overrides; an
    implemented adapter must not half-implement (build_argv done, parse_output
    stubbed, or vice versa).
    """
    adapter = SLUG_MAP[slug]()
    try:
        argv = adapter.build_argv("prompt")
    except NotImplementedError:
        # Still a stub - parse_output must also be a stub.
        with pytest.raises(NotImplementedError):
            adapter.parse_output("", "", 0, None)
        return
    # Implemented build_argv: argv must start with the binary and parse_output
    # must be a real override (empty input normalizes without raising).
    assert argv and argv[0] == adapter.binary_name
    result = adapter.parse_output("", "", 0, None)
    assert result is not None


def test_generic_slug_still_resolves() -> None:
    from AgentEval._core.adapter import GenericAdapter

    assert isinstance(get_adapter("generic"), GenericAdapter)


def test_unknown_slug_lists_cli_slugs_in_error() -> None:
    with pytest.raises(AdapterError) as excinfo:
        get_adapter("nope-not-real")
    message = str(excinfo.value)
    for slug in EXPECTED:
        assert slug in message
    assert "generic" in message
