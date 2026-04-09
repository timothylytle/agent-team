---
name: task-list
description: Updates the Task List section of today's daily log entry with current calendar events, in-progress tasks, and waiting/blockers.
---

You are executing the Task List sub-skill. This skill delegates to a deterministic Python script.

## Purpose

Fetch current calendar events, in-progress tasks, and waiting tasks, then update the Task List section of today's daily log entry.

## Execution

Run the update script:
```bash
/home/timothylytle/agent-team/bin/update-task-list --auto-confirm
```

If it exits with code 0, report its output (number of items added, what changed).

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Reads config files (`daily_log.json`, `doc_styles.json`)
2. Checks the daily-log-cache for today's Task List section boundaries
3. Fetches calendar events for today (with 5-minute local cache)
4. Fetches in-progress and waiting tasks (with 5-minute local cache)
5. Filters events (excludes `workingLocation` type and excluded colorIds) and waiting tasks (only today's due date)
6. Fetches the Google Doc and extracts current Task List section content
7. Parses existing priority items and waiting/blockers
8. Computes diffs: new priorities, updated waiting/blockers
9. Sorts new entries: all-day events first (alphabetically), timed events (by start time), tasks (list order)
10. Builds and executes a batchUpdate with formatting (bullets, fonts, link lines)
11. Updates the daily-log-cache after a successful write
12. Publishes a summary note to the Notes section via publish-to-notes

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)
- The daily-log-cache must have today's section boundaries populated

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/update-task-list
```
