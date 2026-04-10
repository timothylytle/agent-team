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
- `[ideas]` or `[idea]` — skipped for Claude to analyze (see Ideas tasks below)
- `[project]` — creates a follow-up task (projects need user scoping)
- `[support]` — creates a follow-up task (support actions are varied)
- No keyword — creates a follow-up task for clarification

## After execution

Report the script output to the user. The script prints a summary of processed, failed, and follow-up tasks.

## Ideas tasks

If the script output lists ideas requiring analysis, process each one:

1. Read the idea title and notes from the script output
2. Research the idea — if it references a product or technology, use WebSearch to understand it
3. Analyze the idea:
   - 2-3 pros (benefits, opportunities)
   - 2-3 cons (risks, challenges, costs)
   - Brief recommendation (pursue, defer, or dismiss — with reasoning)
4. Create a CRM record:
   ```bash
   bin/crm-safe ideas create --json '{"title": "...", "source_text": "original task text", "analysis": "formatted analysis", "status_id": 2}'
   ```
5. Add a card to the daily log:
   ```bash
   bin/update-ideas-log --json '{"title": "...", "pros": ["...", "..."], "cons": ["...", "..."], "recommendation": "..."}' --auto-confirm
   ```
6. Mark the backlog task complete:
   ```bash
   bin/manage-tasks complete --list backlog --task-id "TASK_ID" --auto-confirm
   ```
