---
description: A sub-agent with valid YAML but missing the required `name` field. The structural validator raises `InvalidSubagentDefinitionError` listing `name` as the missing field.
tools:
  - read_file
---

# Example Missing-Fields Sub-Agent

YAML parses, but PRD FR3's required-field contract is violated.
