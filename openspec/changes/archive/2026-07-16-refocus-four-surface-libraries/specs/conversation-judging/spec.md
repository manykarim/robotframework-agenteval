## REMOVED Requirements

### Requirement: Judge.Get Score accepts a turn result (documented) and a transcript (extended)
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Conversation-scoped judging is cut with the conversation stack.
**Migration**: Use `evaluation-core` judge keywords against a single result instead of a transcript.

### Requirement: Judge Turn Should Pass convenience assertion
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Conversation-scoped judging is cut with the conversation stack.
**Migration**: Use `evaluation-core` judge keywords against a single result instead of a transcript.
