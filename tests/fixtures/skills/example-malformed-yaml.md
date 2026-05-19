---
name: example-malformed-yaml
description: A skill with broken YAML frontmatter. The mapping/list mix on the next line is invalid YAML so `yaml.safe_load` raises `YAMLError`.
allowed-tools:
  - read_file
   bogus_indent: this is bogus
disable-model-invocation: false
---

# Example Malformed YAML Skill

The body content here is irrelevant; the parser raises before it ever
reaches this section because the YAML block above fails `yaml.safe_load`
on the line with `bogus_indent` (which mixes a list item and a mapping
at the same level).
