# Research: Ticket Resolution Skill

**Objective:** Research requirements for a skill that updates the support Google Doc and CRM database when a FreshDesk ticket is resolved or closed. Ticket #1866 used as concrete test case throughout.

**Date:** 2026-04-07

---

## 1. FreshDesk Ticket Data for Resolved Tickets

### Status Codes

| Status ID | Name |
|-----------|------|
| 2 | Open |
| 3 | Pending |
| 4 | Resolved |
| 5 | Closed |

Ticket #1866 has `status: 4` (Resolved).

### Key Fields on the Ticket Object

| Field | Ticket #1866 Value | Notes |
|-------|-------------------|-------|
| `id` | 1866 | FreshDesk ticket ID |
| `status` | 4 | Resolved |
| `subject` | "Daily calls summary report" | |
| `responder_id` | 156002503386 | The assigned agent's FreshDesk ID |
| `requester_id` | 156003698648 | |
| `created_at` | 2026-04-07T15:35:54Z | |
| `updated_at` | 2026-04-07T20:01:20Z | |

### Resolution Timestamps via `--include stats`

The `stats` include adds critical resolution timing data:

```json
"stats": {
  "agent_responded_at": "2026-04-07T16:32:17Z",
  "requester_responded_at": "2026-04-07T18:12:44Z",
  "first_responded_at": "2026-04-07T16:32:17Z",
  "status_updated_at": "2026-04-07T20:01:14Z",
  "reopened_at": null,
  "resolved_at": "2026-04-07T20:01:14Z",
  "closed_at": null,
  "pending_since": null
}
```

**Key finding:** `resolved_at` and `closed_at` are only available via `freshdesk-safe tickets view <ID> --include stats`. They are NOT present in the base ticket response or in search results. The `--include` flag can accept multiple comma-separated values (e.g., `--include stats,conversations,requester`).

### Agent Name Resolution

**Blocker:** `freshdesk-safe agents view` is NOT in the allowlist. The current freshdesk-safe allowlist is:

- `tickets:list`
- `tickets:view`
- `tickets:search`
- `tickets:note`
- `tickets:note-update`
- `contacts:list`
- `contacts:view`

The `responder_id` on ticket #1866 is `156002503386`. To get the agent's name, the options are:

1. **Add `agents view` to freshdesk-safe allowlist** -- requires modifying the wrapper
2. **Use the `--include requester` approach** -- this only gives requester info, not agent info
3. **Hardcode a lookup table** -- small team, could map known agent IDs to names
4. **Check outgoing conversation `user_id`** -- The reply conversation (id: 156056191233) has `user_id: 156002503386` and `from_email: "MiaRec Support" <support@miarec.com>`, but the actual agent name is only in the `body` as a signature ("Timothy Lytle"). This is fragile.

**Recommendation:** Add `agents:view` to the freshdesk-safe allowlist (read-only, low risk). Or, if the resolving agent is always the same small set of people, a config-based mapping from agent ID to name would work without API changes.

### Requester Details via `--include requester`

```json
"requester": {
  "id": 156003698648,
  "name": "Cesar Rojas",
  "email": "cesarojs@lgcns.com",
  "mobile": null,
  "phone": null
}
```

---

## 2. Conversation Thread for Ticket #1866

Four conversations exist on this ticket, in chronological order:

### Conversation 1: Agent Reply (outgoing)
- **ID:** 156056191233
- **Time:** 2026-04-07T16:32:17Z
- **user_id:** 156002503386 (the assigned agent)
- **private:** false
- **Direction:** outgoing (`incoming: false`)
- **body_text:** "Hey Cesar! You have a few options, 1. The Dashboard will show you total calls, you just have to adjust the filter to Yesterday 2. If this is something you need often, like every day, then I would suggest a Call Summary Report From the Reports page, select +Create Set Report Type to Call Summary Report Set the default period to Yesterday Then Save and Run, then Run Report You have other options, like scheduling the report to run on a schedule, deliver to an email, or change the filters, like only report inbound calls, etc Thanks! Timothy Lytle"

### Conversation 2: Private Note (support-bot placeholder)
- **ID:** 156056199389
- **Time:** 2026-04-07T17:16:08Z
- **private:** true
- **body_text:** "Support notes:"
- (Placeholder note before doc was linked)

### Conversation 3: Customer Reply (incoming)
- **ID:** 156056210016
- **Time:** 2026-04-07T18:12:44Z
- **user_id:** 156003698648 (requester)
- **private:** false
- **Direction:** incoming (`incoming: true`)
- **body_text:** "Timothy, Thanks for your help. We were able to generate the report requested by the final customer. Thank you"

### Conversation 4: Private Note (support doc link)
- **ID:** 156056224166
- **Time:** 2026-04-07T19:26:09Z
- **private:** true
- **body_text:** "Support notes: https://docs.google.com/document/d/1s4N9rRqa2oVvjpspaJRvUJduRlG4xpBUy4DhTaMFk3U"

### Summary Generation Assessment

For ticket #1866, a good summary would be:

> "Customer needed to generate a daily call recording count report but was limited by the 10,000 record cap in the built-in report tool. Resolved by guiding them to use the Dashboard with a Yesterday filter for quick counts, and the Call Summary Report feature for scheduled daily reports."

**What information is needed to write a summary:**
- `description_text` -- the original issue
- `body_text` from each non-private conversation -- the back-and-forth
- The ticket subject for context

**Confidence: HIGH** -- An LLM can reliably generate a 2-3 sentence summary from the description + conversation thread. The conversation data provides enough context. Private notes and support-bot notes should be excluded from summary input to avoid noise.

---

## 3. Support Doc Structure

### Current Document Structure (ticket #1866)

Document ID: `1s4N9rRqa2oVvjpspaJRvUJduRlG4xpBUy4DhTaMFk3U`

```
[Index 1-27]   "Daily calls summary report"     <- HEADING_1 (Lexend font)
[Index 28-44]  "FreshDesk Ticket"                <- NORMAL_TEXT with link to FreshDesk
[Index 45-86]  "Support issue: Daily calls..."   <- NORMAL_TEXT (Roboto font)
[Index 87-96]  "Key Facts"                       <- HEADING_2 (Lexend font)
[Index 97-140] "Requestor: Cesar Rojas (cesarojs@lgcns.com)"  <- NORMAL_TEXT
[Index 141-156] "Company: LG CNS"               <- NORMAL_TEXT
[Index 157]    empty line
[Index 158]    end of document
```

### Where to Insert the Resolution Section

The "Resolution" heading should be inserted **after the last line of Key Facts content and before the trailing empty line**. Based on the document structure from `populate_doc`, the Key Facts section is the last structured content in the doc.

The insertion point for ticket #1866 is at index **157** (the empty newline at the end of the Key Facts content). Insert new content there:

```
Resolution                           <- HEADING_2
Resolved: 2026-04-07                 <- NORMAL_TEXT
Agent: Timothy Lytle                 <- NORMAL_TEXT
[2-3 sentence summary]              <- NORMAL_TEXT
```

### How populate_doc Works (Pattern to Follow)

The `populate_doc` function in `bin/update-support-notes` (line 327) uses this pattern:

1. Build all text as a single string joined by `\n`
2. `insertText` at a specific index
3. Calculate line ranges by iterating through lines and tracking `utf16_len`
4. Apply `updateParagraphStyle` for headings (HEADING_1, HEADING_2)
5. Apply `updateTextStyle` for fonts (Lexend for headings, Roboto for body)
6. Apply `updateTextStyle` with `link` for hyperlinks
7. Execute all as a single `batchUpdate`

The style config (`config/doc_styles.json`):
- Heading font: **Lexend**
- Body font: **Roboto**
- Colors: all null (defaults)
- Bullet presets: BULLET_DISC_CIRCLE_SQUARE, BULLET_CHECKBOX

### Finding the Insertion Point

To find where "Key Facts" content ends, the skill must:

1. Fetch the doc via `gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'`
2. Locate the HEADING_2 paragraph with text "Key Facts"
3. Find all NORMAL_TEXT paragraphs that follow it (before the next heading or end of doc)
4. The insertion index is the `endIndex` of the last content paragraph in the Key Facts section

For ticket #1866: the last Key Facts line "Company: LG CNS\n" ends at index 157. The insertion point is index 157.

**Alternative approach:** Since the doc structure is deterministic (created by `populate_doc`), and the "Resolution" section is always added after Key Facts, the skill could also just append at the end of the document content (before the final newline). This is simpler and works if no other content has been added after Key Facts.

---

## 4. CRM Schema for Resolution Data

### Current Tickets Table

```sql
CREATE TABLE tickets (
    id              INTEGER PRIMARY KEY,
    freshdesk_id    INTEGER UNIQUE,
    subject         TEXT,
    status          INTEGER REFERENCES ticket_statuses(status_id),
    priority        INTEGER CHECK (priority BETWEEN 1 AND 4),
    source          INTEGER,
    type            TEXT,
    company_id      INTEGER REFERENCES companies(id),
    requester_id    INTEGER REFERENCES contacts(id),
    responder_id    INTEGER,
    group_id        INTEGER,
    product_id      INTEGER,
    tags            TEXT,           -- JSON array
    custom_fields   TEXT,           -- JSON object
    due_by          TEXT,           -- ISO 8601
    is_escalated    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
```

### Current CRM Record for Ticket #1866

```json
{
  "id": 40,
  "freshdesk_id": 1866,
  "subject": "Daily calls summary report",
  "status": 6,
  "priority": 1,
  "company_id": 31,
  "requester_id": 36,
  "responder_id": null,
  "created_at": "2026-04-07T17:15:54Z",
  "updated_at": "2026-04-07T17:15:54Z"
}
```

**Observation:** The CRM ticket status is `6` (Custom 1) while FreshDesk shows `4` (Resolved). The status was not updated when the ticket was resolved. Also, `responder_id` is null -- this field exists in the schema but was never populated.

### Schema Changes Needed

New columns for the `tickets` table:

| Column | Type | Purpose |
|--------|------|---------|
| `resolved_at` | TEXT | ISO 8601 timestamp from FreshDesk `stats.resolved_at` |
| `closed_at` | TEXT | ISO 8601 timestamp from FreshDesk `stats.closed_at` |
| `resolution_summary` | TEXT | LLM-generated 2-3 sentence summary |

These would be added via `ALTER TABLE`:
```sql
ALTER TABLE tickets ADD COLUMN resolved_at TEXT;
ALTER TABLE tickets ADD COLUMN closed_at TEXT;
ALTER TABLE tickets ADD COLUMN resolution_summary TEXT;
```

### CRM Update Path

`crm-safe tickets update` already exists and accepts these allowed fields: `subject`, `status`, `priority`, `source`, `type`, `company_id`, `requester_id`, `responder_id`, `group_id`, `product_id`, `tags`, `custom_fields`, `due_by`, `is_escalated`, `freshdesk_id`.

**Blocker:** The new columns (`resolved_at`, `closed_at`, `resolution_summary`) are NOT in the `crm-safe` allowed fields list (line 421 of `bin/crm-safe`). The allowlist must be updated to include them after the schema migration.

The update command pattern:
```bash
bin/crm-safe tickets update 40 --json '{"status": 4, "resolved_at": "2026-04-07T20:01:14Z", "resolution_summary": "...", "responder_id": 156002503386}'
```

### What Needs to Change in crm-safe

In `bin/crm-safe` at line 421, the allowed tuple must include the new fields:
```python
allowed = ('subject', 'status', 'priority', 'source', 'type', 'company_id',
           'requester_id', 'responder_id', 'group_id', 'product_id', 'tags',
           'custom_fields', 'due_by', 'is_escalated', 'freshdesk_id',
           'resolved_at', 'closed_at', 'resolution_summary')
```

---

## 5. Existing Patterns and Reusable Code

### Support Doc Discovery

The existing pattern for finding a ticket's support doc (from `scan_ticket_notes` in `bin/lib/support_utils.py` line 331):

1. Call `freshdesk-safe tickets view <ID> --include conversations`
2. Iterate through conversations
3. Search for `docs.google.com/document` in `body` or `body_text`
4. Extract the doc URL/ID from the matching note

For ticket #1866, the matching note is conversation ID 156056224166 with body:
```
Support notes: https://docs.google.com/document/d/1s4N9rRqa2oVvjpspaJRvUJduRlG4xpBUy4DhTaMFk3U
```

The Google Doc ID can be extracted with a regex: `docs.google.com/document/d/([a-zA-Z0-9_-]+)`.

### Reusable Functions from support_utils.py

| Function | Location | Purpose |
|----------|----------|---------|
| `scan_ticket_notes(ticket_id, pattern)` | support_utils.py:331 | Find doc link in ticket notes |
| `fetch_active_tickets()` | support_utils.py:45 | Fetch non-closed tickets |
| `lookup_freshdesk_contact(contact_id)` | support_utils.py:374 | Look up FreshDesk contact by ID |
| `read_style_config()` | support_utils.py:37 | Read doc_styles.json |
| `build_paragraph_style_request(start, end, style)` | support_utils.py:574 | Google Docs paragraph formatting |
| `build_text_style_request(start, end, style, is_heading)` | support_utils.py:541 | Google Docs text formatting |
| `build_link_style_request(start, end, url)` | support_utils.py:585 | Google Docs link formatting |
| `auto_confirm_gws(cmd_args, auto_confirm, desc)` | support_utils.py | Execute GWS write with confirmation |
| `auto_confirm_freshdesk(cmd_args, auto_confirm, desc)` | support_utils.py | Execute FreshDesk write with confirmation |

### Google Docs batchUpdate Pattern

Used by `populate_doc` and the note injection code:

```python
batch = {"requests": requests}
cmd_args = [
    "docs", "documents", "batchUpdate",
    "--json", json.dumps(batch),
    "--params", json.dumps({"documentId": doc_id}),
]
_, success = auto_confirm_gws(cmd_args, auto_confirm, description)
```

---

## 6. Trigger Mechanism

### Option A: Manual Command (Recommended)

A command like `bin/update-ticket-resolution <TICKET_ID>` or `bin/update-ticket-resolution --recent` that:
- Takes a specific ticket ID, or
- Finds recently resolved/closed tickets automatically

**Pros:**
- Consistent with existing patterns (`bin/update-support-notes`, `bin/update-open-tickets`)
- No infrastructure changes
- Can be run as part of a daily workflow or on-demand
- Can also be exposed as a skill for the agent team

**Cons:**
- Requires manual trigger or integration into daily routine

### Option B: Polling via Daily Workflow

Add to the daily log/briefing workflow: search for tickets resolved since last run.

```bash
freshdesk-safe tickets search --query "status:4 OR status:5"
```

Then cross-reference with CRM records to find tickets that have been resolved but not yet processed (no `resolved_at` in CRM).

**Pros:**
- Automatic, catches all resolved tickets
- Integrates with existing daily briefing flow

**Cons:**
- FreshDesk search returns max 300 results
- Slight added complexity to the daily flow

### Option C: FreshDesk Webhook

FreshDesk supports automation rules that fire webhooks on ticket status changes. A webhook could trigger a local script.

**Pros:**
- Real-time, fires immediately on resolution
- No polling overhead

**Cons:**
- Requires external webhook endpoint (not currently set up)
- Infrastructure complexity far beyond current patterns
- Not practical for the existing local tooling

### Recommendation

**Option A (manual command) with Option B baked in.** The script should:
1. Accept an explicit `--ticket <ID>` argument for single-ticket processing
2. Accept a `--recent` flag that searches for recently resolved tickets not yet processed
3. Detection logic: CRM tickets where `resolved_at IS NULL` but FreshDesk status is 4 or 5

This matches the existing pattern where `bin/update-support-notes` can be run manually or as part of a workflow.

---

## 7. Implementation Summary for Ryan

### Prerequisites (must be done first)

1. **Schema migration:** Add `resolved_at`, `closed_at`, `resolution_summary` columns to the `tickets` table
2. **crm-safe allowlist:** Add the three new columns to the allowed update fields in `bin/crm-safe` line 421
3. **freshdesk-safe allowlist (optional):** Add `agents:view` for agent name lookup, OR provide a config-based agent ID-to-name mapping

### Skill Workflow

For a given resolved ticket:

1. **Fetch ticket data** with stats and conversations:
   ```bash
   freshdesk-safe tickets view <ID> --include stats,conversations,requester
   ```

2. **Validate** the ticket is resolved or closed (`status` 4 or 5, `stats.resolved_at` or `stats.closed_at` is not null)

3. **Find the support doc** by scanning conversations for `docs.google.com/document` URL (reuse `scan_ticket_notes` pattern)

4. **Get agent name** from `responder_id` (via `agents view` or config mapping)

5. **Generate resolution summary** -- this is the LLM step. Feed the description_text and non-private conversation body_text to the LLM and ask for 2-3 sentences.

6. **Update the Google Doc:**
   - Fetch doc structure via `gws-safe docs documents get`
   - Find the end of the Key Facts section
   - Insert "Resolution" heading + date + agent + summary via `batchUpdate`
   - Apply HEADING_2 style to "Resolution" heading
   - Apply Roboto body style to content lines

7. **Update CRM:**
   ```bash
   crm-safe tickets update <CRM_ID> --json '{"status": 4, "resolved_at": "...", "resolution_summary": "...", "responder_id": <agent_fd_id>}'
   ```

### Test Case: Ticket #1866

| Data Point | Value |
|------------|-------|
| FreshDesk ticket ID | 1866 |
| CRM ticket ID | 40 |
| CRM company ID | 31 |
| Status | 4 (Resolved) |
| `resolved_at` | 2026-04-07T20:01:14Z |
| `closed_at` | null |
| `responder_id` | 156002503386 |
| Requester | Cesar Rojas (cesarojs@lgcns.com) |
| Support doc ID | 1s4N9rRqa2oVvjpspaJRvUJduRlG4xpBUy4DhTaMFk3U |
| Doc insert index | 157 (end of Key Facts content) |

Expected resolution section in the doc:
```
Resolution
Resolved: April 7, 2026
Agent: Timothy Lytle
Customer needed to generate a daily call recording count report but was hitting a 10,000 record limit in the built-in reporting tool. Resolved by guiding them to use the Dashboard's Yesterday filter for quick daily counts and the Call Summary Report feature for scheduled recurring reports.
```

---

## 8. Risks and Caveats

| Risk | Severity | Mitigation |
|------|----------|------------|
| Agent name lookup blocked by freshdesk-safe allowlist | Medium | Add `agents:view` to allowlist, or use a config file mapping |
| CRM status not synced (currently shows 6 instead of 4) | Low | The resolution skill should update the CRM status as part of its workflow |
| Doc structure may have been modified manually | Low | Parse doc dynamically rather than assuming fixed indices; locate Key Facts heading programmatically |
| `--include stats,conversations,requester` costs 7 API credits per call | Low | Acceptable for per-ticket processing; cache if processing in bulk |
| Summary generation requires LLM | Medium | This skill will need to be an LLM-orchestrated skill (like the original support-notes was) OR the script can call the LLM via API. Since the summary is the only non-deterministic step, consider making the script deterministic with a `--summary "text"` parameter that the LLM-based skill passes in. |
| No `resolved_at`/`closed_at` columns exist yet in CRM | Blocker | Schema migration required before implementation |
| crm-safe update allowlist missing new fields | Blocker | Must update `bin/crm-safe` line 421 before the skill can write resolution data |

---

## 9. Files Referenced

| File | Relevance |
|------|-----------|
| `/home/timothylytle/agent-team/bin/update-support-notes` | `populate_doc` pattern (line 327), batchUpdate patterns |
| `/home/timothylytle/agent-team/bin/lib/support_utils.py` | Reusable functions: `scan_ticket_notes` (331), `build_*_request` (541-593), `auto_confirm_*` |
| `/home/timothylytle/agent-team/bin/lib/daily_log_utils.py` | Constants: `FRESHDESK_SAFE`, `GWS_SAFE`, `CRM_SAFE`, `utf16_len` |
| `/home/timothylytle/agent-team/bin/crm-safe` | Ticket update allowlist (line 421), update implementation (line 409) |
| `/home/timothylytle/agent-team/bin/freshdesk-safe` | Tickets view implementation (line 219), command allowlist (line 481) |
| `/home/timothylytle/agent-team/db/schema.sql` | Tickets table schema (line 84), ticket_statuses (line 65) |
| `/home/timothylytle/agent-team/config/doc_styles.json` | Font and style configuration |
| `/home/timothylytle/agent-team/.claude/skills/support-notes/SKILL.md` | Existing skill pattern |
| `/home/timothylytle/agent-team/.claude/skills/freshdesk-notes/SKILL.md` | Note scanning skill |
