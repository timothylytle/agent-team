---
name: task-list
description: Updates the Task List section of today's daily log entry with current calendar events, in-progress tasks, and waiting/blockers.
---

You are executing the Task List sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Fetch current calendar events, in-progress tasks, and waiting tasks, then update the Task List section of today's daily log entry. Designed to run quickly without doc-existence or archive checks.

## Inputs

None required. Reads configuration from the config file.

## Outputs

Report what was updated: number of events added/removed, tasks added/removed, waiting items changed.

## Constants

- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **Config file:** `/home/timothylytle/agent-team/config/daily_log.json`
- **Config fields used:** `documentId`, `inProgressTaskListId`, `waitingTaskListId`, `excludeEventColorIds`
- **Cache wrapper:** `/home/timothylytle/agent-team/bin/daily-log-cache`
- **Date format for headings:** `DayOfWeek Mon DD, YYYY` (e.g., `Friday Mar 27, 2026`) — generate with `date +'%A %b %-d, %Y'`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.
- For large JSON payloads, construct the full JSON and pass it as a single inline argument.

## Allowed Operations

- `gws-safe docs documents get` (read)
- `gws-safe calendar events list` (read)
- `gws-safe tasks tasks list` (read)
- `gws-safe docs documents batchUpdate` (write, dry-run enforced)
- `daily-log-cache get` (read)
- `daily-log-cache populate` (write)

## Blocked Operations

- Any other write operations (create, delete, trash, update on drive/calendar/tasks)

## Step 1: Read config

Read the config file to get `documentId`, `inProgressTaskListId`, `waitingTaskListId`, and `excludeEventColorIds`.

## Step 2: Check cache

```bash
daily-log-cache get <DOC_ID> <TODAY_DATE>
```
Where `<TODAY_DATE>` is today in `YYYY-MM-DD` format.

If the cache returns data (not `{"cached": false}`), extract the `task_list` section boundaries (`start_index`, `end_index`) and the `notes` section with its subsections. Skip to Step 4 (fetch fresh data). You still need the doc content for comparison but you already know where to look.

If the cache misses, proceed to Step 3.

## Step 3: Fetch doc and parse structure

Fetch the document:
```bash
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```

If the read fails, report the error and stop.

Find today's HEADING_1 entry. If not found, report: "No entry for today. Run /daily-log first to create the entry." and stop.

Identify section boundaries within today's entry (from today's HEADING_1 to the next HEADING_1 or end of doc):

- **Task List section start:** The HEADING_2 paragraph with text "Task List". The content starts on the next paragraph.
- **Task List section end:** The `startIndex` of the next HEADING_2 paragraph after "Task List" (which should be "Open Tickets:" or "Thoughts / Ideas:").
- **Notes section:** The HEADING_2 paragraph with text "Notes". Identify existing HEADING_3 sub-sections under Notes.

Populate the cache with the full document structure:
```bash
daily-log-cache populate --json '{"document_id":"<DOC_ID>","revision_id":"<REVISION_ID>","entries":[...]}'
```
Include ALL entries and their sections/subsections from the document, not just today's.

## Step 4: Fetch fresh data

Determine the local timezone offset by running `date +%:z`.

**Calendar events:**
```bash
gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"<TODAY>T00:00:00<TZ_OFFSET>","timeMax":"<TODAY>T23:59:59<TZ_OFFSET>","singleEvents":true,"orderBy":"startTime"}'
```
Filter out events with `eventType` of `workingLocation` and events whose `colorId` matches any value in `excludeEventColorIds` from the config.

**In-progress tasks:**
```bash
gws-safe tasks tasks list --params '{"tasklist":"<IN_PROGRESS_TASK_LIST_ID>","showAssigned":true}'
```

**Waiting tasks:**
```bash
gws-safe tasks tasks list --params '{"tasklist":"<WAITING_TASK_LIST_ID>","showAssigned":true}'
```
Filter to only tasks where `due` matches today's date (format: `YYYY-MM-DDT00:00:00.000Z`).

## Step 5: Compare and build updates

Compare the fetched data with the current doc content in the Task List section. Identify:

- New calendar events not already listed in Priorities
- New tasks not already listed in Priorities
- Tasks that have been completed (in the doc but no longer in the task list)
- Changes to the Waiting / Blockers list
- New events/tasks that need HEADING_3 sub-sections under Notes

## Step 6: Apply updates via batchUpdate

Build a batchUpdate request that:

- Adds new priority items to the Priorities bullet list (format: `(event) title time` or `(task) title`)
- Updates the Waiting / Blockers content with current data
- Adds new HEADING_3 sub-sections at the end of the Notes section for any new tasks/events
- Apply `updateTextStyle` with `weightedFontFamily: {"fontFamily": "Lexend"}` on new HEADING_3 paragraphs
- Apply `updateTextStyle` with `weightedFontFamily: {"fontFamily": "Roboto"}` on new NORMAL_TEXT paragraphs
- Apply `createParagraphBullets` on new bullet items

For event times, format as `h:mm AM/PM` (e.g., `9:00 AM`). For all-day events, use `all day`.

**Do NOT overwrite or modify:**
- Any text the user has typed under existing HEADING_3 sections
- The Thoughts / Ideas section content
- The Random Fact line

Execute the batchUpdate:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

If there are no changes to make, report "Task List is already up to date" and stop without executing a batchUpdate.

Report what was updated.

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

- If any gws-safe command fails, report the error and stop.
- If the user declines a write operation, stop and report that the operation was cancelled.
- If calendar or tasks APIs return empty results, proceed with empty lists.
