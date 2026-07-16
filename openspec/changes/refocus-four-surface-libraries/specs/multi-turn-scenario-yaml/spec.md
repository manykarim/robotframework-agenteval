## REMOVED Requirements

### Requirement: Scenario evals accept turns as an alternative to prompt (BREAKING)
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Multi-turn scenario YAML is cut with the conversation stack.
**Migration**: Single-prompt agent runs remain via the `evaluation-core` adapter seam.

### Requirement: Run Scenario executes turns as one threaded conversation
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Multi-turn scenario YAML is cut with the conversation stack.
**Migration**: Single-prompt agent runs remain via the `evaluation-core` adapter seam.

### Requirement: Adapter capability differences degrade honestly in YAML runs
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Multi-turn scenario YAML is cut with the conversation stack.
**Migration**: Single-prompt agent runs remain via the `evaluation-core` adapter seam.

### Requirement: Multi-turn Run Scenario stays Tier-3 budget-guarded
**Reason**: Feature removed in the four-surface refocus (MCP / Skills / SubAgents / Hooks). It is orthogonal to the four target surfaces and is cut to shrink the library. Multi-turn scenario YAML is cut with the conversation stack.
**Migration**: Single-prompt agent runs remain via the `evaluation-core` adapter seam.
