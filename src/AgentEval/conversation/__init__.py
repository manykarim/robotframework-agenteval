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

"""Multi-turn conversation sub-package (add-multi-turn-conversation-testing).

Ships the `ConversationLibrary` keyword surface (`Start Conversation`,
`Send Message`, `Get Conversation Transcript`, `End Conversation`,
`Transcript Should Contain`, `Simulate User`), the test-owned
`ConversationHandle`, the `ConversationState` + optional duck-typed
`run_turn()` continuation contract, the shared transcript renderer, and the
LLM-driven user simulator + its `cache_key` disk cache.

`ConversationTurn` + `ConversationTranscript` live in `AgentEval.types` (the
cross-sub-library shared-types module) per architecture L853 — judge + metrics
+ conversation all consume them.
"""

from __future__ import annotations

from AgentEval.conversation.state import ConversationState

__all__ = ["ConversationState"]
