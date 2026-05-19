---
name: example-malformed-yaml-subagent
description: A sub-agent with broken YAML frontmatter. The mapping/list mix on the next line is invalid YAML so `yaml.safe_load` raises `YAMLError`.
tools:
  - read_file
   bogus_indent: this is bogus
---

# Example Malformed YAML Sub-Agent

The body content is irrelevant; the parser raises before reaching it.
