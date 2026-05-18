"""Test fixtures for tests/acceptance/tier1/.

Added by Story 1b.1 FR41 wiring: the Story 1a.6 FR42 acceptance tests assert
default values like `provider == "litellm"`. Now that `AgentEval.__init__`
consults `AGENTEVAL_*` env-vars (Story 1b.1's resolve_config), a developer
with `AGENTEVAL_PROVIDER=...` set in their shell would break these tests.
This conftest clears all `AGENTEVAL_*` env-vars at fixture entry AND fixture
exit (the entry/exit symmetry was added by L3 review fix to catch tests
that set env-vars via `os.environ[...]=...` directly — those wouldn't be
caught by `monkeypatch.undo`).

L3 review fix: removed the previous `monkeypatch.chdir(tmp_path)` line. The
repo doesn't have a `.env` file (only `.env.example`, which `_load_dotenv`
correctly ignores), so the chdir was unnecessary; it was also a footgun for
future tier1 tests that resolve fixture data via relative paths.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


def _strip_agenteval_env() -> None:
    for key in list(os.environ):
        if key.startswith("AGENTEVAL_"):
            del os.environ[key]


@pytest.fixture(autouse=True)
def _isolate_agenteval_env() -> Iterator[None]:
    """Strip all AGENTEVAL_* env-vars at entry AND exit.

    Entry/exit symmetry catches tests that set env-vars via direct
    `os.environ` mutation (which `monkeypatch.undo` does not unwind).
    """
    _strip_agenteval_env()
    try:
        yield
    finally:
        _strip_agenteval_env()
