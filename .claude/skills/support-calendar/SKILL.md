---
name: support-calendar
description: Matches calendar events to FreshDesk tickets, creates CRM meeting records, updates ticket notes and calendar event details.
---

You are executing the Support Calendar skill.

## How to Run

Run the deterministic Python script:

```bash
bin/update-support-calendar --auto-confirm
```

### Flags

- `--auto-confirm` — Automatically confirm all write operations (GWS calendar patches, FreshDesk note creates/updates). Without this flag, dry-run nonces are printed but not confirmed.
- `--dry-run` — Show what would be done without making any changes. Implies no auto-confirm.

### What It Does

1. Runs `update-support-notes` to ensure support doc links and private notes exist for all active tickets
2. Fetches calendar events for the next 7 days filtered to support color IDs (`4` = Flamingo/Support, `11` = Tomato/After hours)
3. Fetches active FreshDesk tickets (non-closed, agent-assigned)
4. For each support-colored event:
   - Extracts attendee emails (excluding self)
   - Resolves each attendee to a CRM company/contact
   - Matches the event to the most relevant FreshDesk ticket for that company (prefers Open > Scheduled > most recent)
   - If CRM entity not found, tries domain fallback against FreshDesk ticket requesters and creates CRM company
   - Ensures CRM contact and ticket records exist
   - Creates a CRM meeting record (idempotent — skips if google_event_id already exists)
   - Updates FreshDesk ticket note with calendar event link (appends to existing "Support notes:" note, or creates new note)
   - Updates calendar event summary (if still default pattern) and description (prepends FreshDesk/Support Doc links if not already present)
5. Prints a summary report

### Prerequisites

- `bin/update-support-notes` is automatically run at the start to ensure support docs and private notes exist before processing.

Report the script output to the user.
