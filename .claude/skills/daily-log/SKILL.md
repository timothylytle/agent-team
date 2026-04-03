---
name: daily-log
description: Creates and updates a daily log entry in a Google Doc with calendar events, tasks, and note sections.
---

You are executing the Daily Log skill. This skill is implemented as a deterministic Python script.

## Execution

Run the script:

```bash
bin/create-daily-log --auto-confirm
```

Optionally pass a historical fact about today's date:

```bash
bin/create-daily-log --auto-confirm --fact "On this day in 1969, the Apollo 11 mission launched."
```

If `--fact` is not provided, a placeholder is used.

## What the script does

1. Checks if today's daily log entry already exists (via the cache)
2. **If the entry exists:** runs `bin/update-task-list --auto-confirm` and `bin/update-open-tickets --auto-confirm` to refresh dynamic sections
3. **If the entry does not exist:** fetches calendar events, tasks, and open FreshDesk tickets, composes the full entry, inserts it into the Google Doc with formatting, populates the cache, then runs the update sub-scripts

## After execution

Report the script output to the user. If the script exits with a non-zero code, report the error.

## Archive (not yet automated)

Archiving old entries to the archive document is not handled by this script. If archiving is needed, follow the manual archive steps from the previous SKILL.md version or wait for the archive script to be built.
