---
name: open-tickets
description: Updates the Open Tickets section of today's daily log entry with current FreshDesk open tickets.
---

You are executing the Open Tickets sub-skill. This skill delegates to a deterministic Python script.

## Purpose

Fetch current open FreshDesk tickets and update the Open Tickets section of today's daily log entry.

## Execution

Run the update script:
```bash
/home/timothylytle/agent-team/bin/update-open-tickets --auto-confirm
```

If it exits with code 0, report its output (number of tickets added, ticket IDs).

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Reads config files (`daily_log.json`, `doc_styles.json`)
2. Checks the daily-log-cache for today's Open Tickets section boundaries
3. Fetches open tickets from FreshDesk (with 5-minute local cache)
4. Resolves requester names via CRM database (falls back to FreshDesk API for unknowns)
5. Fetches the Google Doc and extracts the current Open Tickets section
6. Compares fetched tickets against existing entries (by ticket ID)
7. If new tickets exist, builds and executes a batchUpdate with checkbox formatting
8. Updates the daily-log-cache after a successful write

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)
- The daily-log-cache must have today's section boundaries populated

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/update-open-tickets
```
