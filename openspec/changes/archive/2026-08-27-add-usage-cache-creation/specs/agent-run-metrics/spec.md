## ADDED Requirements

### Requirement: Usage carries prompt-cache-creation tokens with a TTL split

`Usage` SHALL carry prompt-cache **creation** (write) token counts in addition to the
existing cache **read** count (`cached_input_tokens`): a flat total
`cache_creation_input_tokens`, and the two ephemeral-TTL buckets
`cache_creation_1h_input_tokens` and `cache_creation_5m_input_tokens`. All three SHALL
default to `0`, so existing `Usage` construction is unaffected, and SHALL be validated
as non-negative. The `claude-code` adapter (and other Anthropic-shaped CLI payloads that
report a cache-creation breakdown) SHALL populate them from ground-truth CLI output;
adapters that do not report an Anthropic-shaped cache-creation count SHALL leave them at
`0`, which means "not reported," not "no cache writes" (this SHALL be documented on the
fields). When all three creation counts are reported non-zero, the total SHALL equal the
sum of the 1h and 5m buckets (`cache_creation_input_tokens == cache_creation_1h_input_tokens
+ cache_creation_5m_input_tokens`), matching Anthropic's accounting; when the split is
absent the flat total stands alone and the identity check is skipped. The Tier-1
token-usage reader and the JSON metrics export SHALL surface these fields (each in its
existing key convention) so cache-write spend can be attributed and priced (the 1h and
5m buckets price at different multipliers, which is why the split is preserved). No model
self-reported number SHALL be used; the counts come from the recorded run.

#### Scenario: Cache-creation tokens are populated from the claude-code payload

- **WHEN** the claude-code adapter runs against a CLI whose settled usage reports
  `cache_creation_input_tokens` (and, when present, a `cache_creation` TTL breakdown)
- **THEN** the resulting `AgentRunResult.usage` carries that flat creation count and the
  1h/5m split, rather than dropping them

#### Scenario: Adapters without an Anthropic-shaped count default to zero

- **WHEN** a run comes from an adapter whose output carries no Anthropic-shaped
  cache-creation breakdown
- **THEN** the three cache-creation fields on `Usage` are `0`, not fabricated

#### Scenario: The reported split matches the total

- **WHEN** a payload reports the flat total and both the 1h and 5m buckets as non-zero
- **THEN** the total equals the sum of the 1h and 5m buckets, and a mismatch fails
  validation rather than being silently accepted

#### Scenario: The token-usage reader and export surface cache-creation

- **WHEN** a test calls `Get Token Usage` on a recorded run, or exports the run-metrics
  record to JSON
- **THEN** the returned usage / exported JSON includes the cache-creation total and the
  1h/5m split alongside the input, output, and cached (read) counts

#### Scenario: Cache-creation counts are non-negative

- **WHEN** a `Usage` is constructed with any negative cache-creation value
- **THEN** construction fails validation, consistent with the other token fields
