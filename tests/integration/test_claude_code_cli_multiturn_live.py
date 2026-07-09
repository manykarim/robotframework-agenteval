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

"""Live multi-turn `--resume` smoke for `ClaudeCodeCLIAdapter` (add-multi-turn-conversation-testing Task 6.3 / 6.1 probe).

Skipped by default. Runs only when:

- ``AGENTEVAL_INTEGRATION_TESTS=1`` env var is set, AND
- the pinned `claude` binary (`>=2.0.0,<3.0.0`) is on ``$PATH``.

This is the EMPIRICAL PROBE mandated by design Risk
[CLI `--resume` semantics drift across claude versions] +
`feedback_listener_hook_api_surface_empirical_check`: verify that turn 2 with
`--resume <session_id>` actually continues the session against the real binary.
The fixture-driven unit tests
(`tests/unit/coding_agent/test_claude_code_cli_run_turn.py`) cover the parsing;
this proves the real invocation. Manual-validation-only — CI does NOT run this.
"""

from __future__ import annotations

import os
import shutil

import pytest

_INTEGRATION_ENABLED = os.environ.get("AGENTEVAL_INTEGRATION_TESTS") == "1"
_HAS_CLAUDE = shutil.which("claude") is not None


@pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason="Set AGENTEVAL_INTEGRATION_TESTS=1 to opt in to live integration tests.",
)
@pytest.mark.skipif(
    not _HAS_CLAUDE,
    reason="Live multi-turn smoke requires the `claude` binary on $PATH.",
)
def test_claude_code_cli_multiturn_resume_live() -> None:
    """Two-turn conversation on the real `claude` binary; turn 2 resumes natively.

    Asserts: both turns return non-empty text, turn 2 records
    ``continuation="native_session"`` (the session id was captured + resumed).
    If the pinned binary's `-p` mode surfaces no session id, the adapter
    honestly degrades to ``replayed_history`` — this test then documents that
    reality rather than failing (the honesty field is the contract).
    """
    from AgentEval.coding_agent.claude_code_cli import ClaudeCodeCLIAdapter
    from AgentEval.conversation.state import ConversationState
    from AgentEval.types import ConversationTurn

    adapter = ClaudeCodeCLIAdapter()

    # Turn 1.
    state1 = ConversationState(prior_turns=())
    r1 = adapter.run_turn("My name is Robin. Remember it.", conversation_state=state1)
    assert r1.response_text.strip()

    # Turn 2 — resume the captured session and ask a question that requires
    # the prior turn's context.
    prior = (
        ConversationTurn(index=0, role="user", content="My name is Robin. Remember it."),
        ConversationTurn(index=1, role="agent", content=r1.response_text),
    )
    state2 = ConversationState(prior_turns=prior, session_ref=state1.session_ref)
    r2 = adapter.run_turn("What is my name?", conversation_state=state2)
    assert r2.response_text.strip()

    # Honest-degradation contract: the mode is whatever actually happened.
    assert state2.continuation in ("native_session", "replayed_history")
    if state1.session_ref:
        # A session id was captured on turn 1 → turn 2 must be native.
        assert state2.continuation == "native_session"
