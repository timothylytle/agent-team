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

### 5a: Ensure archive doc exists

Check the config file for an `archiveDocumentId`.

**If no `archiveDocumentId`:**
1. Create a new Google Doc:
   ```bash
   gws-safe docs documents create --json '{"title":"_daily_log_archive"}'
   ```
   This is a write operation. Present dry-run, get confirmation, execute with `--confirmed <nonce>`. Save the document ID as `archiveDocumentId` in the config file.

**If `archiveDocumentId` exists:** Read the archive doc with tabs:
```bash
gws-safe docs documents get --params '{"documentId":"<ARCHIVE_DOC_ID>","includeTabsContent":true}'
```
If the read fails (404 or 403), inform the user and offer to create a new archive doc.

### 5b: Determine target tabs for each entry

For each old entry, parse the date from its HEADING_1 text and determine:

- **Year**: e.g., `2026`
- **Quarter**: `Q1` (Jan–Mar), `Q2` (Apr–Jun), `Q3` (Jul–Sep), `Q4` (Oct–Dec)
- **Week Monday**: the Monday of the week containing the entry's date
- **Week Friday**: Week Monday + 4 days
- **Week number within the quarter**: Find the first Monday on or after the quarter's start date (Jan 1, Apr 1, Jul 1, or Oct 1). Week 1 starts on that Monday. Count forward in 7-day increments to determine the entry's week number.
- **Tab titles**:
  - Year tab: `YYYY` (e.g., `2026`)
  - Quarter tab: `YYYY-QN` (e.g., `2026-Q1`)
  - Week tab: `Week N (Mon D-D)` if Monday and Friday are the same month (e.g., `Week 3 (Jan 19-23)`), or `Week N (Mon D - Mon D)` if they span months (e.g., `Week 10 (Sep 29 - Oct 3)`)

### 5c: Create missing tabs

Using the archive doc response from step 5a, build a map of existing tabs by walking the `tabs` array and all `childTabs` recursively. Map each tab by its `tabProperties.title` to its `tabProperties.tabId`.

Identify which Year, Quarter, and Week tabs are needed but don't exist yet. Create them in dependency order, batching each level into a single batchUpdate:

1. **Create missing Year tabs** (if any):
   ```bash
   gws-safe docs documents batchUpdate --json '{"requests":[{"addDocumentTab":{"tabProperties":{"title":"<YEAR>","index":<N>}}}]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
   ```
   Extract new tab IDs from the `replies` array (`replies[N].addDocumentTab.tabProperties.tabId`).

2. **Create missing Quarter tabs** (if any), using Year tab IDs as `parentTabId`:
   ```bash
   gws-safe docs documents batchUpdate --json '{"requests":[{"addDocumentTab":{"tabProperties":{"title":"<YYYY-QN>","parentTabId":"<YEAR_TAB_ID>","index":<N>}}}]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
   ```
   Set `index` so quarters appear in order (Q1=0, Q2=1, Q3=2, Q4=3) relative to existing sibling tabs.

3. **Create missing Week tabs** (if any), using Quarter tab IDs as `parentTabId`:
   ```bash
   gws-safe docs documents batchUpdate --json '{"requests":[{"addDocumentTab":{"tabProperties":{"title":"<WEEK_TITLE>","parentTabId":"<QUARTER_TAB_ID>","index":<N>}}}]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
   ```
   Set `index` so weeks appear in chronological order among existing sibling week tabs.

Skip any batchUpdate that would have zero requests (all tabs at that level already exist).

### 5d: Insert entries into archive tabs

For each old entry, extract its full text and paragraph metadata (heading styles, bullet status) from the main doc. Group entries by target week tab.

For each week tab, build requests to insert at the top of the tab (index 1):

1. **`insertText`** at `{"tabId": "<WEEK_TAB_ID>", "index": 1}` — insert entries newest-first within each week so they appear newest-to-oldest
2. **`updateParagraphStyle`** for heading paragraphs (HEADING_1 for date lines, HEADING_2 for section labels, HEADING_3 for note sub-sections)
3. **`updateTextStyle`** with `weightedFontFamily: {"fontFamily": "Lexend"}` on all heading paragraphs, and `{"fontFamily": "Roboto"}` on all NORMAL_TEXT paragraphs
4. **`createParagraphBullets`** for bulleted paragraphs

If the week tab already has content (e.g., entries archived earlier), inserting at index 1 pushes existing content down, keeping newest entries at the top.

Execute as a single batchUpdate across all week tabs. If the JSON exceeds ~500KB, split into multiple batchUpdates (one per week tab):
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
```

### 5e: Delete archived entries from main doc

**Only proceed with deletion if Step 5d completed successfully for all entries.** If any archive insertion failed, stop and report the error — do not delete entries that were not successfully archived.

Delete the old entries from the main doc. Each entry spans from its HEADING_1 `startIndex` to the next HEADING_1 `startIndex` (or the doc body's last `endIndex` for the final entry).

Use `deleteContentRange` requests, processing deletions from bottom to top (highest indices first) to avoid index shifting:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[{"deleteContentRange":{"range":{"startIndex":<START>,"endIndex":<END>}}}]}' --params '{"documentId":"<DOC_ID>"}'
```

**If no old entries exist:** Skip this step silently.

## Error Handling

- If any gws-safe command fails, report the error and stop. Do not attempt to recover automatically.
- If the user declines a write operation, stop and report that the operation was cancelled.
- If calendar or tasks APIs return empty results, proceed with empty lists (show "None" for those sections).
