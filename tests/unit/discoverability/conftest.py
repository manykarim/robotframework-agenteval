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

"""Test fixtures for `tests/unit/discoverability/`.

Story 4.4 code-review LOW-C fix 2026-05-20 (Blind LOW-4): the keyword
tests register stub adapters via `register_adapter("stub_disco_*", ...)`
which mutates the module-global `_registered_adapters` dict in
`AgentEval._kernel.discovery`. Without cleanup, those names persist
across the test session and a future test re-registering the same name
would hit `UserWarning("entry-point override detected")` or shadow the
fresh class. Snapshot + restore the registry post-test for isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from AgentEval._kernel import discovery


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    """Snapshot + restore the programmatic adapter registry per test."""
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001
