---
name: daily-log
description: Creates and updates a daily log entry in a Google Doc with calendar events, tasks, and note sections.
---

You are executing the Daily Log skill. Follow these steps in order. Be functional and direct.

## Constants

- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **Config file:** `/home/timothylytle/agent-team/config/daily_log.json`
- **In-progress task list ID:** `TG16TWFNTkNRblVkdHdhbQ`
- **Waiting task list ID:** `ZGRjdFdTV19KWGkxVTdMbg`
- **Date format for headings:** `DayOfWeek Mon DD, YYYY` (e.g., `Friday Mar 27, 2026`) — generate with `date +'%A %b %-d, %Y'`

## Step 1: Ensure the daily log doc exists

Read the config file at `/home/timothylytle/agent-team/config/daily_log.json`.

**If the config file does not exist or has no `documentId`:**

1. Create a new Google Doc:
   ```bash
   gws-safe docs documents create --json '{"title":"_daily_log"}'
   ```
   This is a write operation. gws-safe will return a dry-run with a nonce. Present it to the user and ask for confirmation. After approval, re-run with `--confirmed <nonce>`.

2. Extract the `documentId` from the response.

3. Write the config file:
   ```json
   {
     "documentId": "<DOC_ID>"
   }
   ```

**If the config file exists and has a `documentId`:**

Verify the doc is accessible by reading it (used in Step 2 anyway):
```bash
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```

If the read fails (404 or 403), inform the user: "The configured document is not accessible. Would you like to create a new one?" If the user approves, delete the config file and restart from Step 1 (which will create a new doc).

## Step 2: Check if today's entry exists

Using the doc content from Step 1 (or fetch it now if you haven't), look through `body.content` for a paragraph with `paragraphStyle.namedStyleType` of `HEADING_1` whose text content matches today's date.

Today's date format: day of week, abbreviated month, day, year (e.g., `Friday Mar 27, 2026`).

- If a HEADING_1 with today's date is found: skip to **Step 4** (update).
- If not found: proceed to **Step 3** (create).

## Step 3: Create new daily entry

### 3a: Gather data

Run these commands to collect today's data:

**Calendar events:**
Determine the local timezone offset by running `date +%:z`. Use this offset in the time parameters instead of `Z`. For example, if the offset is `-04:00`, use `timeMin: <TODAY>T00:00:00-04:00` and `timeMax: <TODAY>T23:59:59-04:00`.

```bash
gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"<TODAY>T00:00:00<TZ_OFFSET>","timeMax":"<TODAY>T23:59:59<TZ_OFFSET>","singleEvents":true,"orderBy":"startTime"}'
```
Replace `<TODAY>` with today's date in `YYYY-MM-DD` format and `<TZ_OFFSET>` with the result of `date +%:z`.

Extract from each event: `summary` (title) and `start.dateTime` or `start.date` (time).

**In-progress tasks:**
```bash
gws-safe tasks tasks list --params '{"tasklist":"TG16TWFNTkNRblVkdHdhbQ"}'
```

**Waiting tasks:**
```bash
gws-safe tasks tasks list --params '{"tasklist":"ZGRjdFdTV19KWGkxVTdMbg"}'
```
After fetching waiting tasks, filter the results to only include tasks where `due` matches today's date (format: `YYYY-MM-DDT00:00:00.000Z`). Tasks with future or past due dates should be excluded from the Waiting / Blockers section.

**Random fact:** Generate a quirky or funny historical fact about today's date from your own knowledge. Keep it to 1-2 sentences.

### 3b: Build the entry text

Compose the full entry as a single text block. The structure is:

```
[Today's Date]
🎯 Priorities:
(event) [event title] [formatted time]
(event) [next event] [formatted time]
(task) [task title]
(task) [next task title]
⏳ Waiting / Blockers:
[waiting task title]
[or "None" if no waiting tasks are due today]
🎲 Random Fact:
[Your generated fact about today's date]
Thoughts / Ideas:

Notes
[Task/Event 1 title]
[Task/Event 2 title]
```

For event times, format as `h:mm AM/PM` (e.g., `9:00 AM`). For all-day events, use `all day`.

Create one HEADING_3 sub-section under Notes for each calendar event and each in-progress task.

### 3c: Insert via batchUpdate

Build a `batchUpdate` request that inserts the entry at the TOP of the document (index 1). Structure the requests as follows:

1. **Insert all text first** at index 1 as a single `insertText` request. Include newlines to separate each line. Add a trailing newline at the end.

2. **Apply formatting** with subsequent requests. After the text is inserted, calculate the character indices and apply:
   - `updateParagraphStyle` for HEADING_1 on the date line
   - `updateParagraphStyle` for HEADING_2 on "Thoughts / Ideas:" and "Notes"
   - `updateParagraphStyle` for HEADING_3 on each task/event sub-heading under Notes
   - `createParagraphBullets` on the priority items and waiting/blocker items
   - `updateTextStyle` with `weightedFontFamily: {"fontFamily": "Lexend"}` and `fields: "weightedFontFamily"` on all HEADING_1, HEADING_2, and HEADING_3 paragraphs
   - `updateTextStyle` with `weightedFontFamily: {"fontFamily": "Roboto"}` and `fields: "weightedFontFamily"` on all NORMAL_TEXT paragraphs (section labels, random fact text, bullet items)

**Index calculation:** After inserting text at index 1, count characters from index 1 to determine the start and end index of each line. Remember that each newline character (`\n`) counts as 1 character.

Execute the batchUpdate:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

After the batchUpdate succeeds, re-read the document using `docs documents get` and verify:
- The date heading is styled as HEADING_1
- The Thoughts / Ideas and Notes lines are styled as HEADING_2
- Task/event sub-headings are styled as HEADING_3
- Priority and waiting items are bulleted

If formatting is incorrect, report the discrepancy to the user rather than attempting to fix it automatically.

After successful verification, report what was created: number of events, tasks, and the random fact.

## Step 4: Update existing entry

If today's entry already exists:

### 4a: Re-fetch current data

Run the same calendar, in-progress tasks, and waiting tasks commands from Step 3a to get fresh data.

### 4b: Compare and identify changes

Read the current doc content. Find today's entry: it starts at today's HEADING_1 paragraph. The end of today's entry is the `startIndex` of the next HEADING_1 paragraph, or if no next HEADING_1 exists, the `endIndex` of the last element in `body.content`. Identify:

- New calendar events not already listed in Priorities
- New tasks not already listed in Priorities
- Tasks that have been completed (in the doc but no longer in the in-progress list)
- Changes to the waiting/blockers list
- New events/tasks that need HEADING_3 sub-sections under Notes

### 4c: Apply updates via batchUpdate

Build a batchUpdate request that:

- Adds new priority items to the Priorities bullet list
- Updates the Waiting / Blockers section with current data
- Adds new HEADING_3 sub-sections at the end of the Notes section for any new tasks/events

**Do NOT overwrite or modify:**
- Any text the user has typed under existing HEADING_3 sections
- The Thoughts / Ideas section content
- The Random Fact section

Execute the batchUpdate with dry-run and confirmation flow.

Report what was updated.

## Step 5: Archive old entries

Check the document for entries (HEADING_1 paragraphs with date text) that are from before the Monday of the current week.

**Determine the Monday of the current week:** Calculate the date of the most recent Monday (or today if today is Monday).

**If old entries exist:**

1. Check the config file for an `archiveDocumentId`. If it does not exist, create a new Google Doc named `_daily_log_archive_YYYY` (where YYYY is the current year):
   ```bash
   gws-safe docs documents create --json '{"title":"_daily_log_archive_YYYY"}'
   ```
   This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`. Save the new document's `documentId` as `archiveDocumentId` in the config file.

   Updated config file schema:
   ```json
   {
     "documentId": "<MAIN_DOC_ID>",
     "archiveDocumentId": "<ARCHIVE_DOC_ID>"
   }
   ```

2. For each old entry (oldest first), copy its full text and formatting to the TOP of the archive doc via batchUpdate (insert at index 1), maintaining newest-to-oldest order in the archive.

3. After successfully inserting into the archive, delete the old entries from the main doc using `deleteContentRange` in a batchUpdate. Process deletions from bottom to top (highest indices first) to avoid index shifting issues.

**If no old entries exist:** Skip this step silently.

## Error Handling

- If any gws-safe command fails, report the error and stop. Do not attempt to recover automatically.
- If the user declines a write operation, stop and report that the operation was cancelled.
- If calendar or tasks APIs return empty results, proceed with empty lists (show "None" for those sections).
