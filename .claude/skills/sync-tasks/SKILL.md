---
name: sync-tasks
description: Syncs Google Tasks state to CRM database — creates missing records, updates changed status/list/title.
---

You are executing the Sync Tasks skill. This skill is implemented as a deterministic Python script.

## Execution

```bash
bin/sync-tasks
```

Use `--dry-run` to preview changes without writing:

```bash
bin/sync-tasks --dry-run
```

## What it does

Fetches all tasks from all Google Tasks lists (in-progress, waiting, backlog, todo, done) and reconciles with the CRM database:
- Creates CRM records for tasks not yet tracked
- Updates CRM records where status, list, title, or notes have changed
- Reports a summary of changes

## After execution

Report the script output to the user.
