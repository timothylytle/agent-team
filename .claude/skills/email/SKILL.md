---
name: email
description: Updates the Email section of today's daily log entry with filtered, prioritized inbox emails.
---

You are executing the Email sub-skill. This skill delegates to a deterministic Python script.

## Purpose

Fetch inbox emails, filter out noise, classify senders by CRM data, and update the Email section of today's daily log entry.

## Execution

Run the update script:
```bash
/home/timothylytle/agent-team/bin/update-email --auto-confirm
```

If it exits with code 0, report its output (number of emails added).

If it exits with a non-zero code, report the error output.

## What the Script Does

1. Reads config files (`daily_log.json`, `doc_styles.json`)
2. Checks the daily-log-cache for today's Email section boundaries
3. Fetches inbox messages without the "Ack'd" label via Gmail API
4. Fetches metadata for each message (From, Subject, labels, headers)
5. Filters out: category promotions/updates/forums/social, List-Unsubscribe, List-Id, Auto-Submitted, calendar invites, no-reply senders
6. Classifies remaining emails by CRM data: VIP > Customer > Internal > Unknown
7. Formats as checkbox lines: `[Sender Name] Subject` (unknown senders get "Add to CRM?" note)
8. Fetches the Google Doc and deduplicates against existing entries
9. Builds and executes a batchUpdate with checkbox formatting
10. Updates the daily-log-cache after a successful write

## Prerequisites

- Today's daily log entry must already exist (run `/daily-log` first if needed)
- The daily-log-cache must have today's section boundaries populated

## Manual Override

To run without auto-confirm (dry-run only):
```bash
/home/timothylytle/agent-team/bin/update-email
```
