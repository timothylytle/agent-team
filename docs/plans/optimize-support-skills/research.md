# Research: Deterministic Replacement for support-calendar and support-notes Skills

## Objective

Document every behavior of the `support-calendar` and `support-notes` skills in sufficient detail for Ryan to build deterministic Python scripts that replace the LLM orchestration. Identify what is mechanical, what requires LLM judgment, and how to handle judgment steps.

---

## Skill 1: support-calendar

### Current Flow

The skill matches Google Calendar events to FreshDesk tickets, creates CRM meeting records, updates FreshDesk ticket notes with calendar event links, and updates calendar event descriptions with FreshDesk/Support Doc links.

#### Step 1: Get upcoming calendar events
- **API call:** `gws-safe calendar events list --params '{"calendarId":"primary","timeMin":"<today>T00:00:00Z","timeMax":"<today+7>T23:59:59Z","singleEvents":true,"orderBy":"startTime"}'`
- **Processing:** Filter to events where `colorId` is `"4"` (Flamingo/Support) or `"11"` (Tomato/After hours)
- **LLM judgment:** None. Pure filter on a fixed set of color IDs.

#### Step 2: Get active support tickets
- **Delegates to:** `freshdesk-active` sub-skill
- **API call:** `freshdesk-safe tickets search --query "status:2 OR status:3 OR status:4 OR status:6 OR status:7 OR status:9"`
- **Processing:** Filter to tickets where `agent_id` is not null
- **LLM judgment:** None. Deterministic filter.

#### Step 3: Match events to tickets (THE COMPLEX STEP)
For each filtered calendar event:

**3.1: Extract attendee emails**
- Parse `attendees` array, exclude entries with `self: true`
- **LLM judgment:** None. Deterministic field extraction.

**3.2: CRM entity resolution (crm-resolve sub-skill)**
For each attendee email:
- **API call 1:** `crm-safe contacts list` -- search all contacts for email match (case-insensitive)
- If contact found: return `company_id`, `company_name`, `contact_id`, `matched_by: "contact"`
- **API call 2 (if no contact):** `crm-safe companies list` -- search all companies' `domains` JSON arrays for email domain match
- If company found: return `company_id`, `company_name`, `matched_by: "domain"`
- If neither: return `matched_by: "not_found"`
- **LLM judgment:** None. This is exact string matching on email and domain. Fully deterministic.

**3.3: Find matching CRM tickets**
- **API call:** `crm-safe tickets list --company-id <COMPANY_ID>`
- Prefer tickets with status 2 (Open) or 9 (Scheduled)
- **LLM judgment: LOW.** The "match the most relevant ticket" language is vague, but in practice the matching heuristic is: prefer Open/Scheduled status tickets for the same company. If there's only one, it's obvious. If there are multiple, the skill picks the most relevant one.
  - **Can be deterministic:** Pick the first ticket with status 2 or 9. If none, pick the first ticket. This covers the typical case where a company has 1-2 active tickets.

**3.4: Handle `matched_by: "not_found"` (domain fallback)**
- Extract domain from attendee email
- For each active FreshDesk ticket's `requester_id`, call `freshdesk-safe contacts view <REQUESTER_ID>`
- Compare contact's email domain against attendee's email domain (case-insensitive)
- If match found, that FreshDesk ticket is the match
- Then create CRM company: `crm-safe companies create --json '{"name":"<DOMAIN>","domains":["<DOMAIN>"]}'`
- **LLM judgment:** None. Exact domain comparison. The only "fuzzy" part is using the raw domain as the company name, which is a fixed rule.

#### Step 4: Ensure CRM records (crm-ensure sub-skill)
For each matched event-ticket pair:
- **API call:** `freshdesk-safe contacts view <REQUESTER_ID>` (get requester details)
- **API call:** `crm-safe contacts list --company-id <COMPANY_ID>` (check if contact exists by `freshdesk_id` or `email`)
- If not found: `crm-safe contacts create --json '{"name":"...","first_name":"...","last_name":"...","email":"...","freshdesk_id":...,"company_id":...}'`
- **API call:** `crm-safe tickets list --company-id <COMPANY_ID>` (check if ticket exists by `freshdesk_id`)
- If not found: `crm-safe tickets create --json '{"subject":"...","status":...,"priority":...,"freshdesk_id":...,"company_id":...,"requester_id":...}'`
- **LLM judgment:** None. Pure existence checks and record creation with fixed field mappings.

#### Step 5: Create CRM meeting records
- **API call:** `crm-safe meetings list --ticket-id <TICKET_ID>` (check for existing meeting by `google_event_id`)
- If not found: `crm-safe meetings create --json '{"google_event_id":"...","ticket_id":...,"contact_id":...,"company_id":...,"summary":"...","start_time":"...","end_time":"...","html_link":"...","freshdesk_ticket_id":...,"color_id":"..."}'`
- **LLM judgment:** None. Existence check plus record creation.

#### Step 6: Update FreshDesk ticket notes
- **Delegates to:** `freshdesk-notes` sub-skill to check for existing "Support notes:" note
- **API call:** `freshdesk-safe tickets view <TICKET_ID> --include conversations`
- Search conversations for `body` containing `Support notes:`
- **If found:** Parse existing note body, append new "Calendar event Mon D: <EVENT_LINK>" line, call `freshdesk-safe tickets note-update <TICKET_ID> <NOTE_ID> --body "<UPDATED_BODY>"`
- **If not found:** Create new note: `freshdesk-safe tickets note <TICKET_ID> --body "Calendar event Mon D: <EVENT_LINK>" --private true`
- Then: `crm-safe meetings update <MEETING_ID> --json '{"freshdesk_note_id":<NOTE_ID>}'`
- **LLM judgment:** None. Date formatting (`Mon D` from ISO datetime) and string concatenation are deterministic. The note body structure is fixed.
- **Write operation:** Requires dry-run/nonce/confirmation flow for FreshDesk.

#### Step 7: Update calendar events
- **Summary rule:** Only update if current summary matches pattern `<N>min Support Session (...)`. Check with regex.
- **Description rule:** If description does NOT contain `miarec.freshdesk.com/a/tickets/`, prepend FreshDesk URL and optional Support Doc URL. Preserve existing description.
- **API call:** `gws-safe calendar events patch --params '{"calendarId":"primary","eventId":"..."}' --json '{"summary":"...","description":"..."}'`
- **LLM judgment:** None. Regex check on summary, string contains check on description, fixed format string construction.
- **Write operation:** Requires dry-run/nonce/confirmation flow for GWS.

#### Step 8: Report results
- Summary of what was processed
- **LLM judgment:** None in a script -- just print structured output.

### support-calendar: API Call Summary

| Step | API Calls | Count |
|------|----------|-------|
| 1 | `gws-safe calendar events list` | 1 |
| 2 | `freshdesk-safe tickets search` | 1 |
| 3.2 | `crm-safe contacts list` | 1 per unique attendee (or 1 total if fetching all) |
| 3.2 | `crm-safe companies list` | 0-1 per attendee (only if no contact match) |
| 3.3 | `crm-safe tickets list --company-id` | 1 per resolved company |
| 3.4 | `freshdesk-safe contacts view` | 0-N per unmatched attendee (requester lookups) |
| 3.4 | `crm-safe companies create` | 0-1 per unmatched domain |
| 4 | `freshdesk-safe contacts view` | 1 per matched ticket (requester details) |
| 4 | `crm-safe contacts list --company-id` | 1 per matched ticket |
| 4 | `crm-safe contacts create` | 0-1 per matched ticket (if contact missing) |
| 4 | `crm-safe tickets list --company-id` | 1 per matched ticket |
| 4 | `crm-safe tickets create` | 0-1 per matched ticket (if CRM ticket missing) |
| 5 | `crm-safe meetings list --ticket-id` | 1 per matched ticket |
| 5 | `crm-safe meetings create` | 0-1 per matched event (if no existing meeting) |
| 6 | `freshdesk-safe tickets view --include conversations` | 1 per matched ticket |
| 6 | `freshdesk-safe tickets note-update` OR `tickets note` | 1 per matched ticket (write, dry-run + confirm) |
| 6 | `crm-safe meetings update` | 1 per matched ticket |
| 7 | `gws-safe calendar events patch` | 1 per matched event (write, dry-run + confirm) |

**Typical run with 3 support events:** ~20-35 API calls total. Most are CRM (local SQLite, instant). External API calls: 1 GWS read, 1 FreshDesk search, 3-6 FreshDesk contact/conversation reads, 3 FreshDesk writes, 3 GWS writes.

### support-calendar: LLM Judgment Assessment

| Step | Judgment Required? | Explanation |
|------|--------------------|-------------|
| 1. Filter events by color | No | Fixed color ID set `["4", "11"]` |
| 2. Get active tickets | No | Fixed query + null check |
| 3.1 Extract attendee emails | No | JSON field access |
| 3.2 CRM resolve by email/domain | No | Exact string matching |
| 3.3 Match CRM ticket to company | **Low** | Preference for status 2/9, then pick first. Ambiguous only with multiple active tickets per company. |
| 3.4 Domain fallback matching | No | Exact domain comparison |
| 4. Ensure CRM records | No | Existence check + fixed field mapping |
| 5. Create meeting records | No | Existence check + fixed field mapping |
| 6. Update FreshDesk notes | No | String parsing + concatenation |
| 7. Update calendar events | No | Regex check + string formatting |
| 8. Report | No | Print structured data |

**Verdict: 100% scriptable.** The one "Low" judgment (Step 3.3) can be handled with a simple priority rule: prefer status 2 (Open), then status 9 (Scheduled), then any status. If multiple matches remain, pick the most recently created.

---

## Skill 2: support-notes

### Current Flow

The skill creates Google Docs for support notes in a Shared Drive, links them to FreshDesk tickets via private notes, records them in the CRM, and injects tagged FreshDesk notes into the docs.

#### Step 0: Read style config
- Read `/home/timothylytle/agent-team/config/doc_styles.json`
- **LLM judgment:** None. File read.

#### Step 1: Gather non-closed tickets
- **Delegates to:** `freshdesk-active` sub-skill
- **API call:** `freshdesk-safe tickets search --query "status:2 OR status:3 OR status:4 OR status:6 OR status:7 OR status:9"`
- Filter to `agent_id` not null
- **LLM judgment:** None.

#### Step 2: Check for existing support notes (duplicate detection)
- **Delegates to:** `freshdesk-notes` sub-skill for each ticket
- **API call:** `freshdesk-safe tickets view <TICKET_ID> --include conversations` (per ticket)
- Search each note's `body` for `docs.google.com/document`
- Separate tickets into "needs new doc" vs "has existing doc"
- Parse Google Doc ID from URL in note body
- **LLM judgment:** None. Regex/string search.

#### Step 3: Look up requester details
- **API call:** `freshdesk-safe contacts view <REQUESTER_ID>` (per ticket needing new doc)
- Extract `email` field
- **LLM judgment:** None.

#### Step 4: Resolve CRM entities
- **Delegates to:** `crm-resolve` sub-skill (same as support-calendar Step 3.2)
- For `matched_by: "not_found"`:
  - Extract keyword from domain (strip TLD, strip common suffixes like "net", "tech", "corp", "inc", "telecom")
  - Search Shared Drive for folder matching keyword: `gws-safe drive files list --params '{"q":"name contains '\''KEYWORD'\'' and mimeType='\''application/vnd.google-apps.folder'\'' and '\''DRIVE_ID'\'' in parents",...}'`
  - **LLM judgment: MEDIUM.** Three scenarios:
    1. Exactly one folder found -- present to user for confirmation
    2. Multiple folders found -- present options for user to choose
    3. No folders found -- ask user to specify target directory
  - **This is a genuine interactive decision point.** The user must confirm which folder to use for an unrecognized domain.

#### Step 5: Create CRM company for unmatched domains
- `crm-safe companies create --json '{"name":"COMPANY_NAME","domains":["DOMAIN"]}'`
- Only if domain was resolved via Shared Drive search or user input in Step 4
- **LLM judgment:** None after Step 4 resolution.

#### Step 6: Ensure CRM records (crm-ensure sub-skill)
- Same as support-calendar Step 4
- **LLM judgment:** None.

#### Step 7: Locate Shared Drive and customer folders
**7a:** `gws-safe drive drives list` -- find "Customers" drive
**7b:** `gws-safe drive files list --params '{"q":"name=\"CUSTOMER_NAME\"..."}'` -- find customer folder
**7c:** Look for "support" subfolder, create if missing: `gws-safe drive files create --params '{"supportsAllDrives":true}' --json '{"name":"support","mimeType":"application/vnd.google-apps.folder","parents":["CUSTOMER_FOLDER_ID"]}'`
- **LLM judgment:** None. Fixed folder structure. Write requires dry-run/confirm.

#### Step 8: Present summary and confirm
- Show table of tickets to process (ticket ID, subject, requester, company, proposed doc name, target folder)
- Ask user to confirm
- **LLM judgment: MEDIUM.** This is a user confirmation gate. In a script, this maps to either `--auto-confirm` or printing a summary and requiring a flag.

**Doc naming format:** `YYYYMMDD-<ID>-<short-description>` where short-description is: lowercase, replace spaces with hyphens, strip special characters, truncate to ~50 chars.
- **LLM judgment: LOW.** The "short description derived from ticket subject" could be interpreted differently by an LLM each time, but the rules are explicit enough to be deterministic: lowercase, hyphenate, strip special chars, truncate.

#### Step 9a: Create the Google Doc
- `gws-safe drive files create --params '{"supportsAllDrives":true}' --json '{"name":"...","mimeType":"application/vnd.google-apps.document","parents":["SUPPORT_FOLDER_ID"]}'`
- **LLM judgment:** None. Write requires dry-run/confirm.

#### Step 9b: Populate the document
Build a `batchUpdate` with:
1. `insertText` at index 1 with structured content:
   ```
   [Ticket Subject]\n
   FreshDesk Ticket\n
   [1-2 sentence description of the issue]\n
   Key Facts\n
   Requestor: [Name] ([email])\n
   Company: [Company Name]\n
   ```
2. `updateParagraphStyle` for HEADING_1 (subject), HEADING_2 ("Key Facts")
3. `updateTextStyle` for heading font (Lexend), body font (Roboto)
4. `updateTextStyle` with link URL on "FreshDesk Ticket" text

- **LLM judgment: MEDIUM.** The "[1-2 sentence description of the issue, derived from the ticket subject/description]" is the one free-text generation step. The LLM is asked to summarize the ticket into 1-2 sentences.
- Everything else in the batchUpdate is deterministic: heading styles, font families, link insertion, index arithmetic.

#### Step 9c: Add private note to FreshDesk ticket
- `freshdesk-safe tickets note <TICKET_ID> --body "Support notes: <WEB_VIEW_LINK>" --private true`
- **LLM judgment:** None. Write requires dry-run/confirm.

#### Step 9d: Link doc to company in CRM
- `crm-safe files create --json '{"google_file_id":"...","name":"...","mime_type":"...","web_view_link":"..."}'`
- `crm-safe files link --company-id ... --file-id ...`
- **LLM judgment:** None.

#### Step 9e: Inject support-bot tagged notes (THE COMPLEX STEP)
This step processes ALL tickets with support docs (new and existing).

**9e-i:** Fetch conversations: `freshdesk-safe tickets view <TICKET_ID> --include conversations`

**9e-ii:** Filter to private notes containing "support-bot" or "support bot" (case-insensitive)
- **LLM judgment:** None. String search.

**9e-iii:** Read support doc: `gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'`

**9e-iv:** Duplicate detection: Parse note's `created_at`, format as `YYYY-MM-DD HH:MM:SS (UTC)`, search doc text for exact string.
- **LLM judgment:** None. Exact string match.

**9e-v:** Resolve author: `freshdesk-safe contacts view <USER_ID>` -- use `name` field
- **LLM judgment:** None.

**9e-vi:** Extract content from HTML: Python script to parse HTML, strip tags, extract links and images, output JSON.
- **LLM judgment:** None. The SKILL.md includes the exact Python script. This is already a deterministic script embedded in the skill definition.

**9e-vii:** Build and execute batchUpdate:
- Insert section heading (`YYYYMMDD-ticket-note`), metadata lines, extracted content
- Apply HEADING_2 style, heading/body fonts, link styles, inline images
- Sort image insertions by index descending
- Handle image insertion failures gracefully
- **LLM judgment:** None. Fixed formatting rules, index arithmetic, error handling.

#### Step 10: Report results
- **LLM judgment:** None.

### support-notes: API Call Summary

| Step | API Calls | Count |
|------|----------|-------|
| 1 | `freshdesk-safe tickets search` | 1 |
| 2 | `freshdesk-safe tickets view --include conversations` | 1 per ticket |
| 3 | `freshdesk-safe contacts view` | 1 per ticket needing new doc |
| 4 | `crm-safe contacts list` | 1 per ticket (or 1 total) |
| 4 | `crm-safe companies list` | 0-1 per ticket (domain fallback) |
| 4 | `gws-safe drive files list` | 0-1 per unmatched domain (folder search) |
| 5 | `crm-safe companies create` | 0-1 per unmatched domain |
| 6 | `crm-safe contacts list --company-id` | 1 per ticket |
| 6 | `crm-safe contacts create` | 0-1 per ticket |
| 6 | `crm-safe tickets list --company-id` | 1 per ticket |
| 6 | `crm-safe tickets create` | 0-1 per ticket |
| 7a | `gws-safe drive drives list` | 1 |
| 7b | `gws-safe drive files list` | 1 per unique company |
| 7c | `gws-safe drive files list` + optional `create` | 1-2 per unique company |
| 9a | `gws-safe drive files create` | 1 per new doc (write) |
| 9b | `gws-safe docs documents batchUpdate` | 1 per new doc (write) |
| 9c | `freshdesk-safe tickets note` | 1 per new doc (write) |
| 9d | `crm-safe files create` + `crm-safe files link` | 2 per new doc |
| 9e-i | `freshdesk-safe tickets view --include conversations` | 1 per ticket with doc (may duplicate Step 2) |
| 9e-iii | `gws-safe docs documents get` | 1 per ticket with tagged notes |
| 9e-v | `freshdesk-safe contacts view` | 1 per unique note author |
| 9e-vii | `gws-safe docs documents batchUpdate` | 1 per note injection (write) |

**Typical run with 10 active tickets, 2 needing new docs, 5 with tagged notes:** ~40-60 API calls. Most CRM calls are local SQLite. External API calls: 1 FreshDesk search, 10-12 FreshDesk reads, 2-3 FreshDesk writes, 1 GWS drive list, 2-4 GWS drive file lists, 2 GWS file creates, 2 GWS doc batchUpdates, 5 GWS doc gets, 5+ GWS doc batchUpdates for note injection.

### support-notes: LLM Judgment Assessment

| Step | Judgment Required? | Explanation |
|------|--------------------|-------------|
| 0. Read config | No | File read |
| 1. Get active tickets | No | Fixed query + filter |
| 2. Check existing notes | No | String search in conversations |
| 3. Look up requester | No | API call + field extraction |
| 4. CRM resolve | No (for matches) | Exact email/domain matching |
| 4. Unmatched domain folder search | **Medium** | User must confirm folder choice |
| 5. Create CRM company | No | Fixed fields |
| 6. Ensure CRM records | No | Existence checks |
| 7. Find/create folders | No | Fixed folder structure |
| 8. Summary + confirm | **Medium** | User confirmation gate |
| 9a. Create doc | No | Fixed params |
| 9b. Populate doc (issue description) | **Medium** | 1-2 sentence summary from ticket subject/description |
| 9b. Populate doc (everything else) | No | Fixed structure, index arithmetic |
| 9c. Add FreshDesk note | No | Fixed body template |
| 9d. Link in CRM | No | Fixed fields |
| 9e. Inject tagged notes | No | HTML parsing + batchUpdate construction |
| 10. Report | No | Print structured data |

---

## Judgment Steps: Detailed Analysis

### Judgment Step 1: Ticket-to-CRM-ticket matching (support-calendar Step 3.3)

**Current behavior:** "Match the most relevant ticket for the event." Prefer status 2 (Open) or 9 (Scheduled).

**Deterministic replacement:** Sort CRM tickets for the company by: status 2 first, then status 9, then others. Within same status, prefer most recently created. Take the first one.

**Edge case:** Company has multiple active tickets (e.g., one Open, one Scheduled). The script picks the Open one. If both are Open, it picks the newest. This matches what the LLM would do 95%+ of the time.

**Fallback:** If the heuristic picks wrong, the user sees it in the Step 8 report and can manually correct. Low risk.

**Verdict: Replace with deterministic rule.** No LLM needed.

### Judgment Step 2: Unmatched domain folder search (support-notes Step 4)

**Current behavior:** Extract keyword from domain, search Shared Drive, present results to user.

**The keyword extraction logic is explicit:** Take domain name, strip TLD, strip common suffixes (`net`, `tech`, `corp`, `inc`, `telecom`). E.g., `granitenet.com` -> `granitenet` -> strip `net` -> `granite`.

**Deterministic replacement:**
- The keyword extraction is fully scriptable.
- The Drive search is a single API call.
- The three outcomes (1 result, multiple results, no results) all currently require user interaction.

**Options:**
1. **Auto-confirm single match:** If exactly one folder matches, use it automatically (skip the confirmation). Only prompt when ambiguous (0 or 2+ matches).
2. **Defer to report:** Skip unmatched domains entirely, list them in the output report for manual handling later.
3. **Interactive prompt in script:** The script could prompt on stdin for ambiguous cases, matching the current UX.

**Recommendation:** Option 3 for the script (prompt on stdin when needed). Add `--skip-unmatched` flag to silently skip unmatched domains and include them in the report.

### Judgment Step 3: User confirmation before doc creation (support-notes Step 8)

**Current behavior:** Present summary table, ask "Should I proceed?"

**Deterministic replacement:** `--auto-confirm` flag (same pattern as existing `update-open-tickets` and `update-task-list` scripts). Without the flag, print the summary and exit. The gws-safe/freshdesk-safe wrappers still enforce dry-run/nonce on individual write operations.

**Recommendation:** Follow established pattern. Use `--auto-confirm` for non-interactive mode.

### Judgment Step 4: Issue description generation (support-notes Step 9b)

**Current behavior:** LLM writes "1-2 sentence description of the issue, derived from the ticket subject/description."

**Analysis of what the LLM actually does:** It reads the ticket subject (e.g., "MiaRec upgrade to 2025.2.0") and produces a sentence like "Customer is requesting an upgrade of their MiaRec installation to version 2025.2.0." This is a minor rephrasing of the subject.

**Options:**
1. **Use the ticket subject verbatim:** Just use `subject` as-is. The doc already has the subject as the HEADING_1. Using it again as the description is redundant but not harmful.
2. **Use a template:** "Support ticket regarding: {subject}" or "Issue: {subject}".
3. **Omit it entirely:** The doc has the subject as heading and Key Facts below. The description line adds minimal value.
4. **Call the LLM for just this line:** Make a minimal API call to generate 1-2 sentences per ticket. This defeats the purpose of optimization.

**Recommendation:** Option 2 -- use a fixed template. The description line is cosmetic. Suggested template: `"Support issue: {subject}"` or simply leave it as an empty line for Timothy to fill in. The value added by LLM-generated descriptions here is minimal.

---

## Dependencies Between the Two Skills

### Shared Data

| Data | support-calendar | support-notes | Notes |
|------|-----------------|---------------|-------|
| Active FreshDesk tickets | Step 2 (reads) | Step 1 (reads) | Same query, same data |
| CRM companies | Steps 3-4 (reads + creates) | Steps 4-6 (reads + creates) | Same DB, same operations |
| CRM contacts | Steps 3-4 (reads + creates) | Steps 4-6 (reads + creates) | Same DB, same operations |
| CRM tickets | Steps 3-5 (reads + creates) | Step 6 (reads + creates) | Same DB, same operations |
| CRM meetings | Step 5 (creates) | Not used | Calendar-specific |
| CRM files | Not used | Step 9d (creates + links) | Notes-specific |
| FreshDesk ticket conversations | Step 6 (reads "Support notes:" notes) | Step 2 + 9e (reads doc links + "support-bot" notes) | Both read the same conversations API |
| Google Drive (Shared Drive) | Not used | Steps 7-9a (reads + creates folders/docs) | Notes-specific |
| Google Calendar events | Steps 1, 7 (reads + patches) | Not used | Calendar-specific |
| Support Doc URLs | Step 7 (reads from existing note body to include in event description) | Step 9 (creates the docs) | **Critical dependency:** support-notes creates the docs that support-calendar references |

### Execution Order

**support-notes should run BEFORE support-calendar.**

Reason: support-notes creates the Support Doc Google Docs and adds "Support notes: <DOC_LINK>" private notes to FreshDesk tickets. support-calendar then reads those notes (Step 6) to find the doc link, and includes the Support Doc URL in the calendar event description (Step 7). If support-calendar runs first, it won't have the Support Doc link to include.

This order is already the natural order in practice -- support-notes sets up the infrastructure, support-calendar enriches calendar events with that infrastructure.

### Should They Share a Script?

**Recommendation: Two separate scripts with shared utility functions.**

Reasons:
1. They serve different purposes (doc creation vs. calendar enrichment)
2. They have different execution frequencies (support-notes runs when new tickets appear; support-calendar runs when new calendar events appear)
3. They share sub-operations (CRM resolve, CRM ensure, FreshDesk active tickets) that should be extracted into shared functions
4. A combined script would be too complex and harder to debug

### Shared Functions to Extract

The following operations are used by both skills and should be in a shared module (extend `lib/daily_log_utils.py` or create `lib/support_utils.py`):

1. **`fetch_active_tickets()`** -- call `freshdesk-safe tickets search`, filter by `agent_id` not null. Both skills do this identically.
2. **`resolve_crm_entity(email)`** -- the crm-resolve logic: check contacts by email, then companies by domain. Returns `(company_id, company_name, contact_id, matched_by)`.
3. **`ensure_crm_records(freshdesk_ticket, requester, company_id)`** -- the crm-ensure logic: ensure contact and ticket exist, create if missing. Returns `(crm_contact_id, crm_ticket_id, created_contact, created_ticket)`.
4. **`scan_ticket_notes(ticket_id, search_pattern)`** -- the freshdesk-notes logic: fetch conversations, search for pattern. Returns `(found, note_id, note_body)`.
5. **`auto_confirm_write(wrapper_path, args)`** -- handle the dry-run/nonce/confirmation flow for FreshDesk and GWS write operations. Parse nonce from stderr, re-run with `--confirmed`. (This pattern is already in `execute_batch_update` for GWS doc operations; generalize it for FreshDesk and GWS calendar operations.)

---

## Optimization Strategy

### Script 1: `bin/update-support-notes`

**What it replaces:** The full `support-notes` SKILL.md

**Deterministic operations (all steps except judgment points):**
1. Read style config
2. Fetch active tickets (shared function)
3. For each ticket, scan for existing doc note (shared function)
4. For tickets needing new docs: look up requester, resolve CRM entity (shared functions)
5. For unmatched domains: extract keyword, search Drive, prompt user (or skip with flag)
6. Create CRM company for unmatched (if resolved)
7. Ensure CRM records (shared function)
8. Find Customers Shared Drive, customer folders, support subfolders
9. Create Google Docs with fixed-format batchUpdate
10. Add FreshDesk private notes
11. Link in CRM
12. Inject support-bot tagged notes (HTML parsing, batchUpdate construction)

**Remaining judgment points handled by:**
- Unmatched domain folder: Interactive prompt on stdin, or `--skip-unmatched` flag
- User confirmation gate: `--auto-confirm` flag
- Issue description: Fixed template `"Support issue: {subject}"`

**Write operations requiring dry-run flow:**
- `gws-safe drive files create` (support folder creation, doc creation)
- `gws-safe docs documents batchUpdate` (doc population, note injection)
- `freshdesk-safe tickets note` (link note creation)

All of these follow the same dry-run/nonce/confirm pattern. With `--auto-confirm`, the script handles the nonce exchange automatically.

### Script 2: `bin/update-support-calendar`

**What it replaces:** The full `support-calendar` SKILL.md

**Deterministic operations (100% of steps):**
1. Fetch support-colored calendar events (7-day window)
2. Fetch active tickets (shared function)
3. For each event: extract attendees, resolve CRM entities (shared function), match to CRM tickets by company (deterministic priority rule)
4. Handle unmatched domains: domain comparison against FreshDesk ticket requesters, create CRM company
5. Ensure CRM records (shared function)
6. Create CRM meeting records
7. Update FreshDesk ticket notes (scan for existing note, append or create)
8. Update calendar event descriptions (prepend FreshDesk/Support Doc links if missing)

**Write operations requiring dry-run flow:**
- `freshdesk-safe tickets note` / `tickets note-update` (note creation/update)
- `gws-safe calendar events patch` (event description update)
- CRM writes execute directly (no dry-run needed -- local SQLite)

### Estimated Savings

#### support-calendar (per run, ~3 events)

| Metric | Current (LLM) | Optimized (Script) | Reduction |
|--------|---------------|-------------------|-----------|
| LLM token usage | ~10,000-20,000 tokens | 0 | 100% |
| Wall-clock time | 60-180 sec | 10-30 sec | 75-85% |
| External API calls | Same count | Same count | 0% (API calls are inherent) |
| CRM lookups | Same count | Same count, but instant (local SQLite) | N/A |
| Approval prompts | 6+ (each FreshDesk note + each calendar patch) | 0 with `--auto-confirm` | 100% |

#### support-notes (per run, ~10 tickets, 2 new docs)

| Metric | Current (LLM) | Optimized (Script) | Reduction |
|--------|---------------|-------------------|-----------|
| LLM token usage | ~15,000-30,000 tokens | 0 | 100% |
| Wall-clock time | 120-300 sec | 20-60 sec | 75-80% |
| External API calls | Same count | Same count | 0% |
| Approval prompts | 8+ (folder creates, doc creates, batchUpdates, FreshDesk notes) | 0 with `--auto-confirm` | 100% |

### Caching Opportunities

1. **Active tickets cache:** Both scripts fetch the same ticket list. A 5-minute TTL cache in SQLite (same pattern as `open_tickets_snapshot` in `daily_log_cache.db`) would prevent redundant FreshDesk searches when scripts run in sequence.

2. **FreshDesk contact cache:** Requester lookups by ID happen repeatedly. The CRM database already serves as a cache (contacts with `freshdesk_id`). The scripts should check CRM first, only calling FreshDesk API for unknown contacts. This pattern is already established in `daily_log_utils.py:_resolve_requester_names()`.

3. **CRM entity cache:** `crm-safe contacts list` and `crm-safe companies list` return the full dataset. The scripts should fetch these once per run and filter in-memory rather than calling `crm-safe` per attendee.

4. **Shared Drive ID cache:** The Customers Shared Drive ID doesn't change. Cache it in a config file or at the top of each run.

5. **Ticket conversations cache:** Steps 2 and 9e of support-notes both call `freshdesk-safe tickets view <ID> --include conversations` for the same ticket. Cache the conversation data in memory within a single run.

---

## Implementation Plan

### Phase 1: Shared utilities module

Create `bin/lib/support_utils.py` with:
- `fetch_active_tickets()` -- with optional SQLite cache (5-min TTL)
- `resolve_crm_entity(email, contacts_cache, companies_cache)` -- in-memory lookup
- `ensure_crm_records(...)` -- CRM existence checks + creation
- `scan_ticket_notes(ticket_id, pattern)` -- conversation search
- `auto_confirm_freshdesk(args)` -- dry-run/nonce/confirm for FreshDesk writes
- `auto_confirm_gws(args)` -- dry-run/nonce/confirm for GWS writes (generalize from `execute_batch_update`)
- `slugify(text, max_len=50)` -- for doc name generation

### Phase 2: `bin/update-support-notes`

Python script following established patterns from `bin/update-open-tickets`:
- `--auto-confirm` flag for non-interactive mode
- `--skip-unmatched` flag to skip unresolved domains
- Imports shared functions from `lib/support_utils.py` and `lib/daily_log_utils.py`
- Uses fixed template for issue description (no LLM)
- Handles the full 9e note injection flow deterministically

### Phase 3: `bin/update-support-calendar`

Python script following established patterns:
- `--auto-confirm` flag
- Imports shared functions
- Deterministic ticket matching (status priority rule)
- No LLM needed at any step

### Phase 4: Update SKILL.md files

Both SKILL.md files become thin wrappers:
```
Run: bin/update-support-notes --auto-confirm
Report the output.
```

---

## Risks and Caveats

1. **support-notes Step 9e is the most complex operation.** The HTML parsing, batchUpdate construction with inline images, and index arithmetic for injecting notes into existing docs is intricate. The SKILL.md already includes the exact Python script for HTML parsing (Step 9e-vi), which can be extracted directly. The batchUpdate construction follows the same pattern as existing scripts but adds image handling.

2. **Inline image insertion can fail.** The SKILL.md explicitly handles this: retry without failing images, report skipped images. The script must implement this retry logic.

3. **FreshDesk rate limits.** With 10+ tickets, the scripts make many FreshDesk API calls (conversations, contacts). Rate limiting (HTTP 429) is handled by the `freshdesk-safe` wrapper, but the script should implement retry-with-backoff or at minimum report the error clearly.

4. **Shared Drive permissions.** The `supportsAllDrives: true` parameter is required on all Drive API calls. Missing this causes silent failures. The script must include it everywhere.

5. **Multiple notes per ticket in Step 9e.** After injecting a note into the doc, the endIndex changes. The SKILL.md says to re-read the document before processing the next note. The script must do the same -- re-fetch the doc after each batchUpdate to get updated indices.

6. **The "1-2 sentence description" trade-off.** Using a fixed template instead of LLM-generated text is a minor quality reduction. If Timothy finds this unsatisfactory, a future enhancement could call the LLM for just this line (one minimal API call per new doc, not per run).

7. **Unmatched domain handling.** The interactive prompt for folder disambiguation is the one place where the script cannot be fully non-interactive. The `--skip-unmatched` flag provides a workaround, but some runs may require manual intervention. This is inherent to the problem -- a new customer with no CRM record and no obvious Drive folder requires human input.

8. **UTF-16 index arithmetic.** Same risk as the daily-log scripts. The `utf16_len()` function from `daily_log_utils.py` handles this correctly and should be reused.
