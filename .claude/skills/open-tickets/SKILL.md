---
name: open-tickets
description: Updates the Open Tickets section of today's daily log entry with current FreshDesk open tickets.
---

You are executing the Open Tickets sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Fetch current open FreshDesk tickets and update the Open Tickets section of today's daily log entry. Designed to run quickly without doc-existence or archive checks.

## Inputs

None required. Reads configuration from the config file.

## Outputs

Report what was updated: number of tickets added/removed.

## Constants

- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **FreshDesk wrapper:** `/home/timothylytle/agent-team/bin/freshdesk-safe`
- **Config file:** `/home/timothylytle/agent-team/config/daily_log.json`
- **Config fields used:** `documentId`
- **FreshDesk ticket URL pattern:** `https://miarec.freshdesk.com/a/tickets/<TICKET_ID>`
- **Cache wrapper:** `/home/timothylytle/agent-team/bin/daily-log-cache`
- **Style config:** `/home/timothylytle/agent-team/config/doc_styles.json`
- **Date format for headings:** `DayOfWeek Mon DD, YYYY` (e.g., `Friday Mar 27, 2026`) — generate with `date +'%A %b %-d, %Y'`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.

## Allowed Operations

- `gws-safe docs documents get` (read)
- `gws-safe docs documents batchUpdate` (write, dry-run enforced)
- `freshdesk-safe tickets search` (read)
- `freshdesk-safe contacts view` (read)
- `daily-log-cache get` (read)
- `daily-log-cache populate` (write)

## Blocked Operations

- Any other write operations (create, delete, trash, note, note-update)

## Step 1: Read config

Read the config file to get `documentId`.

Read the style config at `/home/timothylytle/agent-team/config/doc_styles.json`. Use these values for all document formatting.

## Step 2: Check cache

```bash
daily-log-cache get <DOC_ID> <TODAY_DATE>
```
Where `<TODAY_DATE>` is today in `YYYY-MM-DD` format.

If the cache returns data (not `{"cached": false}`), extract the `open_tickets` section boundaries (`start_index`, `end_index`). Skip to Step 4 (fetch open tickets). You still need the doc content for comparison but you already know where to look.

If the cache misses, proceed to Step 3.

## Step 3: Fetch doc and parse structure

Fetch the document:
```bash
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```

If the read fails, report the error and stop.

Find today's HEADING_1 entry. If not found, report: "No entry for today. Run /daily-log first to create the entry." and stop.

Identify section boundaries within today's entry (from today's HEADING_1 to the next HEADING_1 or end of doc):

- **Open Tickets section start:** The HEADING_2 paragraph with text "Open Tickets:". The content starts on the next paragraph.
- **Open Tickets section end:** The `startIndex` of the next HEADING_2 paragraph after "Open Tickets:" (which should be "Thoughts / Ideas:").

Populate the cache with the full document structure:
```bash
daily-log-cache populate --json '{"document_id":"<DOC_ID>","revision_id":"<REVISION_ID>","entries":[...]}'
```
Include ALL entries and their sections/subsections from the document, not just today's.

## Step 4: Fetch open tickets

```bash
freshdesk-safe tickets search --query "status:2"
```

From the results, extract each ticket's `id`, `subject`, and `requester_id`. For each unique requester, look up the contact:
```bash
freshdesk-safe contacts view <REQUESTER_ID>
```
Use the contact's `name` as the customer name. If the contact lookup fails, use "Unknown" as the customer name.

## Step 5: Compare and identify new tickets

Compare the fetched tickets with the current Open Tickets content in the doc. Extract the ticket IDs from existing entries by looking for `[<number>]` patterns at the start of each line in the section.

Identify only tickets from the FreshDesk results whose ID does not appear in the existing entries. These are new tickets to append.

Do NOT remove, modify, or reorder existing entries. The user manually updates these throughout the day (checking them complete, changing status, converting to tasks).

## Step 6: Apply updates via batchUpdate

If there are new tickets to add, build a batchUpdate request that appends them to the end of the Open Tickets section.

1. Insert new ticket lines at the end of the existing Open Tickets content (just before the next HEADING_2 paragraph). The insert index is the `startIndex` of the next HEADING_2 after "Open Tickets:" (i.e., the section `end_index` from the cache or parsed structure).
2. Format each new ticket as: `[<ticket-id>] customer - subject - https://miarec.freshdesk.com/a/tickets/<ticket-id>` followed by a newline
3. Apply `createParagraphBullets` with `bulletPreset: "<bulletPresets.checkbox from style config>"` on the new ticket items
4. Apply `updateTextStyle` with `weightedFontFamily: {"fontFamily": "<fonts.body from style config>"}` on the new ticket items
   - If `colors.bodyText` in the style config is not null, include `foregroundColor: {"color": {"rgbColor": <colors.bodyText>}}` in the `updateTextStyle` request (add `"foregroundColor"` to the `fields` mask)

Execute the batchUpdate:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

If there are no new tickets to add, report "Open Tickets is already up to date" and stop without executing a batchUpdate.

Report how many new tickets were appended and their IDs.

## Step 7: Update cache

After a successful batchUpdate, re-read the document and repopulate the cache:
```bash
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```
Parse the full document structure (all entries and their sections/subsections) and run:
```bash
daily-log-cache populate --json '{"document_id":"<DOC_ID>","revision_id":"<REVISION_ID>","entries":[...]}'
```
Include ALL entries with their updated indices and the new revision_id.

## Error Handling

- If any gws-safe or freshdesk-safe command fails, report the error and stop.
- If the user declines a write operation, stop and report that the operation was cancelled.
- If the FreshDesk search returns empty results, update the section to show "None".
