---
name: tasks
description: Google Tasks management — creates, lists, completes, and moves tasks across all lists with CRM tracking.
---

You are executing the Tasks skill. This skill is implemented as a deterministic Python script.

## Execution

Run the script with one of these subcommands:

### Create a task
```bash
bin/manage-tasks create --list backlog --title "Task title" --auto-confirm
```

Optional flags: `--notes "details"`, `--due "2026-04-15"`

### List tasks
```bash
bin/manage-tasks list --list backlog
```

### Complete a task
```bash
bin/manage-tasks complete --list backlog --task-id "TASK_ID" --auto-confirm
```

### Move a task between lists
```bash
bin/manage-tasks move --task-id "TASK_ID" --from backlog --to in_progress --auto-confirm
```

## Valid list names
- `todo` — tasks to do
- `in_progress` — tasks currently being worked on
- `waiting` — tasks waiting on something
- `backlog` — tasks queued for future processing
- `done` — completed tasks

## After execution

Report the script output to the user. If the script exits with a non-zero code, report the error.

After any write operation (create, complete, move), also run the task list update:

```bash
bin/update-task-list --auto-confirm
```
