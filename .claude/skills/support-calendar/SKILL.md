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
- GWS and FreshDesk write operations go through the dry-run/nonce/confirmation flow described by each wrapper. CRM write operations execute directly.

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
- `crm-safe contacts create` (write)
- `crm-safe companies list` (read)
- `crm-safe companies create` (write)
- `crm-safe tickets list` (read)
- `crm-safe tickets create` (write)
- `crm-safe meetings list` (read)
- `crm-safe meetings create` (write)
- `crm-safe meetings update` (write)

## Step 1: Get upcoming calendar events

List events for the next 7 days using the primary calendar:
```bash
gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"YYYY-MM-DDT00:00:00Z","timeMax":"YYYY-MM-DDT23:59:59Z","singleEvents":true,"orderBy":"startTime"}'
```

Replace the first `YYYY-MM-DD` with today's date and the second with the date 7 days from today.

From the results, filter to only events where `colorId` is `"4"` or `"11"`. If no matching events are found, report "No support calendar events found for the next 7 days" and stop.

## Step 2: Get active support tickets

Read and follow `.claude/skills/freshdesk-active/SKILL.md`.

Expected output: a list of non-closed, agent-assigned FreshDesk tickets.

If no tickets are returned, report "No assigned non-closed tickets found" and stop.

## Step 3: Match events to tickets

For each filtered calendar event:

1. **Get attendee emails:** Extract emails from the event's `attendees` array. Exclude any attendee with `self: true` (that is the calendar owner).

2. **Resolve CRM entities for each attendee:** Read and follow `.claude/skills/crm-resolve/SKILL.md` with these inputs:
   - email: the attendee's email address

   Expected outputs: `company_id`, `company_name`, `contact_id`, `matched_by`

3. **From resolved entities, find matching tickets:**
   - If `matched_by` is `"contact"` or `"domain"` (a company was resolved), list tickets for that company: `crm-safe tickets list --company-id <COMPANY_ID>`
   - Prefer tickets with status 2 (Open) or 9 (Scheduled) over other statuses.
   - Match the most relevant ticket for the event.

4. **If `matched_by` is `"not_found"`:** Try to find a matching FreshDesk ticket by domain, then create the missing CRM company.

   **4a. Find a matching FreshDesk ticket via the attendee email:**

   1. Extract the domain from the attendee email (the part after `@`, e.g., `"cspire.com"` from `"tecarter@cspire.com"`).
   2. From the active tickets list (Step 2 output), collect all unique `requester_id` values.
   3. For each unique `requester_id`, look up the contact:
      ```bash
      freshdesk-safe contacts view <REQUESTER_ID>
      ```
   4. Check if the contact's email domain matches the attendee's email domain (case-insensitive).
   5. If a match is found, the corresponding FreshDesk ticket is the match. Stop searching.

   To avoid excessive API calls:
   - Only look up requester_ids not already checked in this session.
   - Stop searching once a match is found.
   - If no match is found after checking all requesters, mark the event as unmatched and present it to the user at the end.

   **4b. Create a CRM company for the domain:**

   If a FreshDesk ticket match was found in 4a:

   1. Create a CRM company using the domain as the company name:
      ```bash
      crm-safe companies create --json '{"name":"<DOMAIN>","domains":"[\"<DOMAIN>\"]"}'
      ```
      For example, for domain `cspire.com`: `--json '{"name":"cspire.com","domains":"[\"cspire.com\"]"}'`

   2. Use the newly created company's `id` as `company_id` and proceed to Step 4 (crm-ensure) with this company_id to create the contact and ticket records.

## Step 4: Ensure CRM records exist

For each matched event-ticket pair, ensure the CRM has contact and ticket records. Get the requester details from the matched FreshDesk ticket:
```bash
freshdesk-safe contacts view <REQUESTER_ID>
```

Then read and follow `.claude/skills/crm-ensure/SKILL.md` with these inputs:
- freshdesk_ticket_id: the FreshDesk ticket ID
- freshdesk_ticket_subject: the ticket subject
- freshdesk_ticket_status: the ticket status
- freshdesk_ticket_priority: the ticket priority
- requester_email: the requester's email
- requester_name: the requester's full name
- requester_first_name: the requester's first name
- requester_last_name: the requester's last name
- requester_freshdesk_id: the FreshDesk ticket's `requester_id`
- company_id: the CRM company ID from Step 3

Expected outputs: `crm_contact_id`, `crm_ticket_id`, `created_contact`, `created_ticket`

## Step 5: Create CRM meeting records

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
   Use `crm_ticket_id` and `crm_contact_id` from Step 4.

## Step 6: Update FreshDesk ticket notes

For each matched ticket:

1. **Check for existing support-notes note:** Read and follow `.claude/skills/freshdesk-notes/SKILL.md` with these inputs:
   - ticket_id: the FreshDesk ticket ID
   - search_pattern: `Support notes:`

   Expected outputs: `found`, `note_id`, `note_body`

2. **If `found` is true (existing support-notes note):**
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

3. **If `found` is false (no existing support-notes note):**
   Create a new private note with the calendar event line:
   ```bash
   freshdesk-safe tickets note <FRESHDESK_TICKET_ID> --body "Calendar event <Mon D>: <EVENT_LINK>" --private true
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

4. **Store the note ID:** After creating or updating the note, update the CRM meeting record with the FreshDesk note ID:
   ```bash
   crm-safe meetings update <MEETING_ID> --json '{"freshdesk_note_id":<NOTE_ID>}'
   ```

## Step 7: Update calendar events

For each matched event, update the description and conditionally update the summary.

**Summary rule:** Only update the summary if the current summary matches the default booking pattern `<N>min Support Session (...)` (e.g., "60min Support Session (Tim Carter)"). If the summary has already been customized to something else, leave it as-is.

**Description:** Always update the description with the FreshDesk ticket link. If a support doc exists (found in Step 6 from the existing "Support notes:" note body), include the Support Doc link as well. If no support doc exists, omit that line.

If the summary should be updated:
```bash
gws-safe calendar events patch --params '{"calendarId":"primary","eventId":"EVENT_ID"}' --json '{"summary":"<company-name> | miarec - [<ticket-id>] - <ticket-subject>","description":"FreshDesk: https://miarec.freshdesk.com/a/tickets/<FRESHDESK_TICKET_ID>\nSupport Doc: https://docs.google.com/document/d/<DOC_ID>/edit"}'
```

If the summary should NOT be updated (non-default name):
```bash
gws-safe calendar events patch --params '{"calendarId":"primary","eventId":"EVENT_ID"}' --json '{"description":"FreshDesk: https://miarec.freshdesk.com/a/tickets/<FRESHDESK_TICKET_ID>\nSupport Doc: https://docs.google.com/document/d/<DOC_ID>/edit"}'
```

- **summary format (when updating):** `<company-name> | miarec - [<ticket-id>] - <ticket-subject>` where `ticket-id` is the FreshDesk ticket ID.

This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

## Step 8: Report results

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
