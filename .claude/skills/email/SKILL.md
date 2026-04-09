---
name: email
description: Updates the Email section of today's daily log entry with a timestamped summary of inbox emails.
---

You are executing the Email sub-skill. This skill delegates to a deterministic Python script.

## Purpose

Fetch inbox emails, filter out noise, classify senders by CRM data, and add a timestamped summary to the Email section of today's daily log entry. Each invocation adds a new summary entry, creating a log of what was important at each point in the day.

## Execution

Run the update script:
```bash
/home/timothylytle/agent-team/bin/update-email --auto-confirm
```

If it exits with code 0, report its output.

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Reads config files (`daily_log.json`, `doc_styles.json`)
2. Checks the daily-log-cache for today's Email section boundaries
3. Fetches inbox messages without the "Ack'd" label via Gmail API
4. Fetches metadata for each message (From, Subject, labels, headers)
5. Filters out: category promotions/updates/forums/social, List-Unsubscribe, List-Id, Auto-Submitted, calendar invites, no-reply senders
6. Classifies remaining emails by CRM data: VIP > Customer > Internal > Unknown
7. Builds a timestamped summary line with email counts by category and top 3-5 suggested subjects
8. Checks for duplicate timestamp (skips if a summary for the same minute already exists)
9. Inserts the summary as a checkbox entry in the Email section
10. Saves all email records to CRM (deduplicates by message ID)
11. Updates the daily-log-cache after a successful write
12. Publishes a summary note to the Notes section via publish-to-notes

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)
- The daily-log-cache must have today's section boundaries populated

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/update-email
```
