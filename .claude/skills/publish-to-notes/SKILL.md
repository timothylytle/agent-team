---
name: publish-to-notes
description: Publishes a timestamped message to the Notes section of today's daily log.
---

You are executing the Publish to Notes skill. This skill delegates to a deterministic Python script.

## Purpose

Append a timestamped checkbox entry to the Notes section of today's daily log. Used by other skills to log their activity, making the daily log a record of both user and agent actions.

## Execution

Run the script:
```bash
/home/timothylytle/agent-team/bin/publish-to-notes --auto-confirm --text "Your message here"
```

If it exits with code 0, report its output.

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Reads config files (`daily_log.json`, `doc_styles.json`)
2. Checks the daily-log-cache for today's Notes section boundaries
3. Fetches the Google Doc
4. Inserts a timestamped checkbox line: `h:MM AM -- <text>`
5. Applies body font styling (Roboto) and checkbox bullet formatting
6. Updates the daily-log-cache after a successful write

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)
- The daily-log-cache must have today's section boundaries populated

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/publish-to-notes --text "Your message here"
```
