"""Test fixtures for tests/acceptance/tier1/.

Added by Story 1b.1 FR41 wiring: the Story 1a.6 FR42 acceptance tests assert
default values like `provider == "litellm"`. Now that `AgentEval.__init__`
consults `AGENTEVAL_*` env-vars (Story 1b.1's resolve_config), a developer
with `AGENTEVAL_PROVIDER=...` set in their shell would break these tests.
This conftest clears all `AGENTEVAL_*` env-vars + makes `.env` resolution
look at a nonexistent path, keeping the tests hermetic.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_agenteval_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Strip all AGENTEVAL_* env-vars and point `.env` resolution at tmp_path.

    Ensures Story 1a.6's FR42 default assertions are not affected by a
    developer's local shell env. Run via pytest's autouse fixture mechanism.
    """
    for key in list(os.environ):
        if key.startswith("AGENTEVAL_"):
            monkeypatch.delenv(key, raising=False)

    # Chdir to a tmp_path so the .env auto-loaded by resolve_config doesn't
    # accidentally pick up the repo's .env.example or a developer .env.
    monkeypatch.chdir(tmp_path)
    yield
