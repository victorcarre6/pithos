---
name: pithos-continuity
description: Finalize every autonomous run with the validated Pithos Context, Work and Next items report.
---

# Pithos continuity report

Write `.pithos/report.md` before ending a run. Use YAML frontmatter followed by exactly one occurrence of each
required section:

```markdown
---
schema_version: "1.0"
run_id: <PITHOS_RUN_ID>
experiment_id: <project experiment id>
micro_rush_id: <rush-id-or-null>
status: <completed|failed|interrupted|timed_out|paused>
started_at: <ISO-8601 timestamp>
finished_at: <ISO-8601 timestamp>
branch: <agent/rush-* or null>
commit_before: <sha or null>
commit_after: <sha or null>
stop_reason: <text or null>
next_wake: <scheduled|local_resume|none>
---

## Context

State required by a fresh session, including the current micro-rush and relevant constraints.

## Work

Concrete changes, commands, tests, observations, decisions, failures and remaining uncertainty.

## Next items

- Actionable candidate with its verification condition.
```

Do not claim success from prose alone. Record measured results and distinguish process, protocol, task and
report success. Rewrite `Next items` freely when evidence changes priorities.
