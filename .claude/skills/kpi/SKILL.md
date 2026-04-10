---
name: kpi
description: Generates a weekly KPI report (Friday-Thursday) with helpdesk metrics, meetings, tasks, and support summary, inserted into the daily log.
---

You are executing the KPI skill. This skill delegates to a deterministic Python script.

## Purpose

Generate a weekly KPI report covering the Friday-through-Thursday work week, collecting helpdesk metrics, calendar meeting counts, completed/upcoming tasks, and support summary data. The report is inserted under the Notes section of today's daily log.

## Execution

Run the script:
```bash
/home/timothylytle/agent-team/bin/generate-weekly-kpi --auto-confirm --responses 45 --resolved 10
```

The `--responses` and `--resolved` flags are sourced from the FreshDesk analytics report (no analytics API available). If omitted, those fields show `___` as placeholders.

To generate for a specific week (by its ending Thursday):
```bash
/home/timothylytle/agent-team/bin/generate-weekly-kpi --week-ending 2026-04-09 --auto-confirm --responses 45 --resolved 10
```

To preview without inserting into the doc:
```bash
/home/timothylytle/agent-team/bin/generate-weekly-kpi --dry-run
```

If it exits with code 0, report the generated KPI data to the user.

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Computes the Friday-through-Thursday date range (defaults to most recent Thursday)
2. Fetches helpdesk metrics from FreshDesk: opened tickets, agent responses, email requests
3. Fetches calendar events and counts by color: Support (4), After Hours (11), Sales (6), Onboarding (1)
4. Fetches completed tasks from Google Tasks (completedMin/completedMax)
5. Fetches upcoming/in-progress tasks from Google Tasks
6. Fetches support summary: assigned tickets (FreshDesk), resolved tickets (CRM)
7. Formats the report and inserts it as a HEADING_3 block in the Notes section
8. Publishes a summary note via publish-to-notes

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/generate-weekly-kpi
```
