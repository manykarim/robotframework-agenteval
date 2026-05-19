---
description: A skill with valid YAML but missing the required `name` field. The structural validator raises `InvalidSkillFrontmatterError` listing `name` as the missing field.
allowed-tools:
  - read_file
disable-model-invocation: false
---

# Example Missing-Fields Skill

The YAML block above is structurally valid (parses to a dict without
errors) but omits the required `name` field. `parse_frontmatter()`
succeeds; `validate_frontmatter_structure()` raises with `field_name="name"`.
