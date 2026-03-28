# Daily Log Skill — Research

**Date:** 2026-03-27
**Researcher:** Oscar
**Status:** Complete

---

## Objective

Research the existing daily log document structure, GWS wrapper capabilities, and feasibility of building an automated daily log skill that creates/updates entries in a Google Doc.

---

## 1. Existing Daily Log Document

**Document:** `_daily_notes`
**Document ID:** `17xlRG9n2NovwrdSrz1-nJwjDaxRRyF3a5Z2MQzxIkUA`
**Format:** Google Doc (no tabs — single body)

### Current Structure (per daily entry)

Each day's entry follows this pattern, inserted at the top of the document:

```
--- (horizontal rule)
# [Date as smart chip, e.g. "Mar 27, 2026"]     ← HEADING_1

Greetings Humans!
Here are Timothy Lytle's daily tasks for [M/DD/YYYY]

Priorities:                                       ← plain text label
  - (event) - [calendar event title]              ← bulleted list
  - (event) - [calendar event title]
  - (task) - [task title]
  - (task) - [task title]

Waiting / Blockers:                               ← plain text label
  - (items or "None found" placeholder)           ← bulleted list

Random Fact:                                      ← plain text label
[paragraph with a quirky fact about the date]

## Thoughts / Ideas:                              ← HEADING_2
  - (empty bullet for user to fill in)

## Notes:                                         ← HEADING_2

### [Meeting/task sub-heading]                    ← HEADING_3 (one per task/event)
[User fills in notes during the day]
```

### Observed Patterns

1. **Entry order:** Newest entry is at the top of the document, preceded by a horizontal rule separator.
2. **Date heading:** Uses a Google Docs date smart chip (`dateElement`) formatted as `DATE_FORMAT_MONTH_DAY_YEAR_ABBREVIATED`. Also has the date in plain text `[M/DD/YYYY]` in the intro line.
3. **Priorities section:** Mixes calendar events (prefixed `(event)`) and tasks (prefixed `(task)`) in a single bulleted list.
4. **Waiting/Blockers section:** Shows items from a "waiting" task list, or a placeholder if none found.
5. **Random Fact:** A paragraph about a historical event on that date.
6. **Thoughts/Ideas section:** Empty bullets for the user to fill in during the day. HEADING_2.
7. **Notes section:** HEADING_2, followed by HEADING_3 sub-headings for each task/event. Some sub-headings match calendar event names, others are ad-hoc topics. User writes freeform notes under each.
8. **Meeting notes template:** Some entries include a structured template with `Attendees:`, `Notes:`, `Action items:` sections under a date-stamped HEADING_2 (format: `## Mar 27, 2026 |`). These appear to be auto-generated meeting note stubs.
9. **No archiving:** All entries live in the same document body. No tab-based separation. The document has accumulated many list definitions (100+ `kix.*` list IDs), suggesting significant document growth over time.

### Formatting Details

| Element | Google Docs Style |
|---------|------------------|
| Date heading | HEADING_1 |
| Section headers (Thoughts, Notes) | HEADING_2 |
| Task/event sub-headings | HEADING_3 |
| Priority items | Bulleted list (unordered) |
| Waiting/blocker items | Bulleted list (unordered) |
| Body text | NORMAL_TEXT with 12pt space below |
| Separator between days | Horizontal rule |

---

## 2. GWS Wrapper Capabilities

### Available Commands by Service

#### Google Docs

| Command | Access | Notes |
|---------|--------|-------|
| `gws-safe docs documents get --params '{"documentId":"..."}'` | READ | Returns full document structure (body, lists, styles, etc.) |
| `gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"..."}'` | WRITE | Confirmed-eligible in gws-safe. Requires `--json` flag for request body. |
| `gws-safe docs documents create --json '{"title":"..."}'` | WRITE | Confirmed-eligible in gws-safe. Creates a new doc. |

**Key finding:** The `--json` flag is used for request bodies (not `--body` or `--requestBody`). The `--params` flag is for URL/query parameters.

#### Google Calendar

| Command | Access | Notes |
|---------|--------|-------|
| `gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"...","timeMax":"...","singleEvents":true,"orderBy":"startTime"}'` | READ | Works. Confirmed functional. |
| `gws-safe calendar calendarList list` | READ | Works. Lists all calendars. |
| `gws-safe calendar events get --params '{"calendarId":"primary","eventId":"..."}'` | READ | Available. |
| `gws-safe calendar events insert` | WRITE | Confirmed-eligible. |
| `gws-safe calendar events update` | WRITE | Confirmed-eligible. |

**Primary calendar ID:** `timothy.lytle@miarec.com`

#### Google Tasks

| Command | Access | Notes |
|---------|--------|-------|
| `gws-safe tasks tasklists list` | READ | **BLOCKED by auth scopes.** Returns 403 `insufficientPermissions`. |
| `gws-safe tasks tasks list --params '{"tasklist":"..."}'` | READ | **BLOCKED by auth scopes.** |

#### Google Drive

| Command | Access | Notes |
|---------|--------|-------|
| `gws-safe drive files list` | READ | Available. |
| `gws-safe drive files get --params '{"fileId":"..."}'` | READ | Available. |
| `gws-safe drive files create` | WRITE | Confirmed-eligible. App-created files only (`drive.file` scope). |
| `gws-safe drive files update` | WRITE | Confirmed-eligible. App-created files only. |

### Current Auth Scopes

| Scope | Status |
|-------|--------|
| `calendar.readonly` | Active |
| `calendar.events` | Active |
| `contacts.readonly` | Active |
| `documents.readonly` | Active |
| `drive.file` | Active |
| `drive.readonly` | Active |
| `gmail.readonly` | Active |
| `gmail.send` | Active |
| `presentations.readonly` | Active |
| `spreadsheets.readonly` | Active |
| `tasks` / `tasks.readonly` | **NOT present** |

### Write Operation Flow (gws-safe)

All write operations follow this protocol:
1. First call: gws-safe auto-injects `--dry-run` and returns a confirmation nonce
2. Agent presents dry-run output to user
3. User approves
4. Second call with `--confirmed <nonce>` executes the real operation
5. Nonces expire after 5 minutes and are single-use

---

## 3. Feasibility Assessment

### Can we create/update Google Docs?

**Creating new docs: YES (with caveats)**
- `docs documents create` is confirmed-eligible in gws-safe
- `drive.file` scope allows creating new files
- New docs created by the app CAN be written to via `drive.file` scope

**Updating the EXISTING daily log doc: NO**
- The current auth has `documents.readonly` scope only
- The existing doc was NOT created by this app, so `drive.file` does not grant write access
- `docs documents batchUpdate` exists in gws-safe's confirmed-eligible list, but API calls will fail with 403 due to insufficient scopes

**Updating app-created docs: LIKELY YES (untested)**
- If the skill creates a NEW doc via `docs documents create`, subsequent `batchUpdate` calls should succeed because `drive.file` grants write access to app-created files
- This needs verification

### Can we read Google Calendar events? **YES**

Confirmed working. Returns events with summaries, start/end times, attendees, etc.

### Can we read Google Tasks? **NO**

No `tasks` or `tasks.readonly` scope in current auth. All tasks API calls return 403.

### Can we work with Doc tabs?

**The existing document has no tabs.** The API response does not include a `tabs` key. Google Docs tabs are a newer feature (2024+); this document uses the traditional single-body structure.

The Docs API does support tabs via `includeTabsContent=true` parameter and tab-specific `batchUpdate` requests. However:
- Tab creation/manipulation requires write access
- The current doc has no tabs to read from

### Can we work with specific sheets within a spreadsheet?

Not relevant to this skill, but for reference: `sheets spreadsheets values get` supports range parameters like `"Sheet1!A1:B10"`.

---

## 4. Blockers

### BLOCKER 1: Cannot write to existing daily log document
- **Cause:** `documents.readonly` scope + doc not created by app
- **Impact:** Cannot insert new daily entries into the existing `_daily_notes` doc
- **Resolution options:**
  - **Option A:** Re-auth with `documents` (full write) scope. Grants write access to ALL Google Docs in the account. High risk.
  - **Option B:** Create a NEW daily log doc via the skill. The `drive.file` scope grants write access to app-created files only. Low risk. Means abandoning or manually migrating the existing doc.
  - **Option C:** Use the `+write` helper command. **Not viable** -- the underlying gws-cli does not implement `+write` (returns "Unknown service" error).

**Recommendation:** Option B is the safest approach. Create a new `_daily_notes` doc via `docs documents create`, then use `docs documents batchUpdate` for all subsequent writes. This stays within the `drive.file` scope and avoids granting broad write access to all docs.

### BLOCKER 2: Cannot read Google Tasks
- **Cause:** No `tasks` or `tasks.readonly` scope in current auth
- **Impact:** Cannot populate the "Priorities" or "Waiting/Blockers" sections with task data
- **Resolution:** Re-auth to add `tasks.readonly` scope. This is a narrow, read-only scope with minimal risk.

---

## 5. Recommendations

### Immediate Actions Required (before implementation)

1. **Re-authenticate to add `tasks.readonly` scope.** Without this, the skill cannot read tasks and half the daily summary will be empty. The re-auth command would be:
   ```
   gws auth login --scopes "https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/documents.readonly,https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/presentations.readonly,https://www.googleapis.com/auth/contacts.readonly,https://www.googleapis.com/auth/tasks.readonly"
   ```

2. **Decide on document strategy:** Use a new app-created doc (Option B) or grant full docs write scope to use the existing doc (Option A). See Blocker 1 above.

### Skill Architecture (proposed)

Given the constraints, the skill should:

1. **Create a new daily log doc** on first run (via `docs documents create`). Store the document ID in a local config file so subsequent runs know where to write.

2. **Read calendar events** for today via `calendar events list`.

3. **Read tasks** for today via `tasks tasks list` (requires scope fix).

4. **Build the daily entry** following the existing document structure but with improvements:
   - Use proper headings and formatting via `batchUpdate` requests
   - Insert at index 1 (top of document body, after section break)
   - Add horizontal rule separator

5. **Check for existing entry** by reading the doc first and checking if today's date heading already exists. If it does, update only the summary section (priorities, waiting, random fact) rather than creating a duplicate.

6. **Archive old entries** by reading entries older than one week, creating content in an "Archive" tab (if Docs tab API supports write via `drive.file`), and removing from the main body. This is more complex and could be a Phase 2 feature.

### Improvements Over Current Format

- **Idempotent:** Re-running the skill updates rather than duplicates
- **Structured meeting note templates:** Pre-populate HEADING_3 sections for each calendar event
- **Task list source tagging:** Indicate which task list each task comes from
- **Consistent formatting:** Use batchUpdate requests for precise control over styles rather than relying on whatever the previous tool produced

---

## 6. Technical Reference: batchUpdate Request Format

For implementation, the `docs documents batchUpdate` API accepts requests like:

```json
{
  "requests": [
    {
      "insertText": {
        "text": "Hello World\n",
        "location": { "index": 1 }
      }
    },
    {
      "updateParagraphStyle": {
        "range": { "startIndex": 1, "endIndex": 13 },
        "paragraphStyle": { "namedStyleType": "HEADING_1" },
        "fields": "namedStyleType"
      }
    },
    {
      "insertInlineImage": { ... }
    },
    {
      "createParagraphBullets": {
        "range": { "startIndex": 14, "endIndex": 50 },
        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
      }
    }
  ]
}
```

Invocation via gws-safe:
```bash
gws-safe docs documents batchUpdate \
  --json '{"requests":[...]}' \
  --params '{"documentId":"<DOC_ID>"}'
```

**Important:** Insertions shift all subsequent indices. When building multiple requests, insert in reverse order (bottom-up) or calculate cumulative offsets.

---

## 7. Open Questions

1. **Can `docs documents batchUpdate` succeed on an app-created doc with only `drive.file` + `documents.readonly` scopes?** This is the critical untested assumption. If not, we need `documents` (full write) scope, which is a broader security grant.

2. **Which task lists should be included?** The existing doc references "in-progress" and "waiting" lists. Need to know the task list structure once `tasks.readonly` scope is added.

3. **Should the skill also update the doc later in the day?** The current format has empty sections (Thoughts/Ideas, meeting notes) that the user fills in manually. The skill could potentially update these sections based on later inputs, but that adds complexity.

4. **Archive strategy:** Moving content to a different tab requires tab creation via the API. This may or may not work under `drive.file` scope for an app-created doc. Needs testing.

5. **Meeting note templates:** The existing doc has meeting note stubs with `Attendees:`, `Notes:`, `Action items:` sections. Should the skill generate these for all events, or only events with specific characteristics (e.g., events where Timothy is an attendee, not all-day events)?
