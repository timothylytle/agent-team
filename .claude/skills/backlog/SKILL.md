---
name: backlog
description: Agent work queue processor — reads backlog Google Tasks list, routes tasks to skills/agents, processes in batch, marks complete.
---

You are executing the Backlog skill. This skill is implemented as a deterministic Python script.

## Execution

Run the script:

```bash
bin/process-backlog --auto-confirm
```

Use `--dry-run` to preview what would be processed without executing:

```bash
bin/process-backlog --dry-run
```

## Routing conventions

Tasks on the backlog list are routed by title keywords:
- `[skill:X]` — runs skill X (e.g., `[skill:kpi]`, `[skill:daily-log]`)
- `[ideas]` — logs an idea from the task title and notes
- `[project]` — creates a follow-up task (projects need user scoping)
- `[support]` — creates a follow-up task (support actions are varied)
- No keyword — creates a follow-up task for clarification

## After execution

Report the script output to the user. The script prints a summary of processed, failed, and follow-up tasks.
