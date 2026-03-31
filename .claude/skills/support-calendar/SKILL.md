---
name: support-calendar
description: Matches calendar events to FreshDesk tickets, creates CRM meeting records, updates ticket notes and calendar event details.
---

You are executing the Support Calendar skill. Follow these steps in order. Be functional and direct.

## Constants

- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **FreshDesk wrapper:** `/home/timothylytle/agent-team/bin/freshdesk-safe`
- **CRM wrapper:** `/home/timothylytle/agent-team/bin/crm-safe`
- **Support color IDs:** `["4", "11"]` (Flamingo = Support, Tomato = After hours)
- **Scheduled status ID:** `9`
- **Config file:** `config/support_calendar.json`
- **FreshDesk ticket URL pattern:** `https://miarec.freshdesk.com/a/tickets/<TICKET_ID>`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.
- For multiline Python scripts, use heredoc syntax (`python3 << 'PYEOF' ... PYEOF`) instead of `python3 -c "..."` to avoid triggering security prompts from `#` characters in inline code.
- All write operations go through the dry-run/nonce/confirmation flow described by each wrapper.

## Blocked Operations

The following operations are FORBIDDEN and must NEVER be attempted by this skill:

- `gws-safe drive files delete` — deleting files
- `gws-safe drive files trash` — trashing files
- `gws-safe drive files update` with `removeParents` or parent-change
- Any `delete`, `trash`, or `remove` operation

This skill may ONLY use the following operations:

### GWS (Calendar)
- `gws-safe calendar events list` (read)
- `gws-safe calendar events patch` (write, dry-run enforced)

### FreshDesk
- `freshdesk-safe tickets search` (read)
- `freshdesk-safe tickets view` (read)
- `freshdesk-safe contacts view` (read)
- `freshdesk-safe tickets note` (write, dry-run enforced)
- `freshdesk-safe tickets note-update` (write, dry-run enforced)

### CRM
- `crm-safe contacts list` (read)
- `crm-safe companies list` (read)
- `crm-safe companies view` (read)
- `crm-safe tickets list` (read)
- `crm-safe meetings list` (read)
- `crm-safe meetings create` (write, dry-run enforced)
- `crm-safe meetings update` (write, dry-run enforced)

## Step 1: Get today's calendar events

List events for today using the primary calendar:
```bash
gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"YYYY-MM-DDT00:00:00Z","timeMax":"YYYY-MM-DDT23:59:59Z","singleEvents":true,"orderBy":"startTime"}'
```

Replace `YYYY-MM-DD` with today's date.

From the results, filter to only events where `colorId` is `"4"` or `"11"`. If no matching events are found, report "No support calendar events found for today" and stop.

## Step 2: Get active support tickets

Search FreshDesk for non-closed tickets assigned to an agent:
```bash
freshdesk-safe tickets search --query "status:2 OR status:3 OR status:4 OR status:6 OR status:7 OR status:9"
```

From the results, filter to only tickets where `agent_id` is not null. If no assigned tickets are found, report "No assigned non-closed tickets found" and stop.

## Step 3: Match events to tickets

For each filtered calendar event:

1. **Get attendee emails:** Extract emails from the event's `attendees` array. Exclude any attendee with `self: true` (that is the calendar owner).

2. **Look up attendees in CRM contacts by email:**
   - Fetch all contacts: `crm-safe contacts list`
   - For each attendee email, find a matching CRM contact by `email` field.

3. **From matched contacts, find their associated tickets:**
   - For each matched contact's `company_id`, list tickets: `crm-safe tickets list --company-id <COMPANY_ID>`
   - Prefer tickets with status 2 (Open) or 9 (Scheduled) over other statuses.
   - Match the most relevant ticket for the event.

4. **If no CRM contact match, try domain matching:**
   - Extract the domain from the attendee email (part after `@`).
   - Fetch all companies: `crm-safe companies list`
   - Check if the domain appears in any company's `domains` JSON array.
   - If a company matches, find tickets for that company: `crm-safe tickets list --company-id <COMPANY_ID>`
   - Prefer tickets with status 2 (Open) or 9 (Scheduled).

5. **If still no match:** Collect the event as unmatched and present it to the user at the end.

## Step 4: Create CRM meeting records

For each matched event-ticket pair:

1. **Check for existing meeting record:**
   ```bash
   crm-safe meetings list --ticket-id <TICKET_ID>
   ```
   Search the results for a meeting with a matching `google_event_id`. If found, skip creation. Note: a ticket may have multiple meetings — only skip if this specific `google_event_id` already exists, not if the ticket has other meetings.

2. **Create meeting record:**
   ```bash
   crm-safe meetings create --json '{"google_event_id":"EVENT_ID","ticket_id":CRM_TICKET_ID,"contact_id":CRM_CONTACT_ID,"company_id":CRM_COMPANY_ID,"summary":"EVENT_SUMMARY","start_time":"START_TIME","end_time":"END_TIME","html_link":"HTML_LINK","freshdesk_ticket_id":FRESHDESK_TICKET_ID,"color_id":"COLOR_ID"}'
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

## Step 5: Update FreshDesk ticket notes

For each matched ticket:

1. **Check for existing support-notes note:**
   ```bash
   freshdesk-safe tickets view <FRESHDESK_TICKET_ID> --include conversations
   ```
   Look through conversations for a note whose body contains "Support notes:".

2. **If an existing support-notes note is found:**
   Update it to append the calendar event line. Format the date from the event's `start.dateTime` as `Mon D` (e.g., `Mar 31`). Preserve existing content — parse the current note body, keep the "Support notes:" line and any existing "Calendar event" lines, then append the new one. Each item should be on its own line:
   ```
   Support notes: <DOC_LINK>
   Calendar event <Mon D>: <EVENT_LINK>
   ```
   If the ticket has multiple meetings, each gets its own "Calendar event" line with its date:
   ```
   Support notes: <DOC_LINK>
   Calendar event Mar 31: <EVENT_LINK_1>
   Calendar event Apr 2: <EVENT_LINK_2>
   ```
   ```bash
   freshdesk-safe tickets note-update <FRESHDESK_TICKET_ID> <NOTE_ID> --body "<FULL_UPDATED_BODY>"
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

3. **If no existing support-notes note:**
   Create a new private note with the calendar event line:
   ```bash
   freshdesk-safe tickets note <FRESHDESK_TICKET_ID> --body "Calendar event <Mon D>: <EVENT_LINK>" --private true
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

4. **Store the note ID:** After creating or updating the note, update the CRM meeting record with the FreshDesk note ID:
   ```bash
   crm-safe meetings update <MEETING_ID> --json '{"freshdesk_note_id":<NOTE_ID>}'
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

## Step 6: Update calendar events

For each matched event, use `calendar events patch` to update the summary and description:

```bash
gws-safe calendar events patch --params '{"calendarId":"primary","eventId":"EVENT_ID"}' --json '{"summary":"<company-name> | miarec - [<ticket-id>] - <ticket-subject>","description":"FreshDesk: https://miarec.freshdesk.com/a/tickets/<FRESHDESK_TICKET_ID>\nSupport Doc: https://docs.google.com/document/d/<DOC_ID>/edit"}'
```

- **summary format:** `<company-name> | miarec - [<ticket-id>] - <ticket-subject>` where `ticket-id` is the FreshDesk ticket ID.
- **description:** Include the FreshDesk ticket link. If a support doc exists (found in Step 5 from the existing "Support notes:" note body), include the Support Doc link as well. If no support doc exists, omit that line from the description.

This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

## Step 7: Report results

After all events have been processed, report:

- Number of events matched and processed
- For each: event summary, matched ticket ID, company name, and what was updated
- Any events that were unmatched (list event summary, time, and attendees)
- Any errors encountered

## Error Handling

- If any wrapper command fails, report the error and stop processing the current event. Continue with the next event if possible.
- If the user declines a write operation, skip that event and continue with the next.
- If no support tickets are found, stop after Step 2 and report.
- If no calendar events match the color filter, stop after Step 1 and report.
