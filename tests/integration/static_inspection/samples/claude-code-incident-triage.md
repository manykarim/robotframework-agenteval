---
name: incident-triage
description: Helps an on-call engineer triage a production incident by gathering symptoms, identifying recent deploys, and proposing 1-3 likely root causes. Used during PagerDuty alerts and reactive incident response.
allowed-tools:
  - read_file
  - search_database
  - run_shell_command
  - list_recent_deploys
disable-model-invocation: false
---

# Incident Triage Skill

When invoked, this skill walks the on-call engineer through:

1. **Capture symptoms** — error rates, latency percentiles, error messages, affected
   endpoints. Read from the observability dashboard (Grafana / Datadog).
2. **Identify recent changes** — list deploys in the last 4 hours via
   `list_recent_deploys`. Correlate with the symptom-onset timestamp.
3. **Propose hypotheses** — 1 to 3 likely root causes ranked by confidence,
   each with: a one-line description, the diagnostic command(s) to run, and
   the rollback action if confirmed.

The skill stops after proposing hypotheses; the on-call engineer decides
which hypothesis to investigate first. Tool use is restricted to read-only
operations (no destructive shell commands, no writes); this is enforced at
the `allowed-tools` allowlist level.
