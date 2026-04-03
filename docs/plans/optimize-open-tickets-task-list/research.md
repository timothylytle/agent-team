# Optimization Research: open-tickets and task-list Skills

## Current System Architecture

Both skills follow the same pattern:
1. LLM reads config files and style config
2. LLM checks the daily-log-cache SQLite DB for section boundaries
3. LLM fetches the Google Doc via `gws-safe docs documents get`
4. LLM fetches external data (FreshDesk tickets, calendar events, Google Tasks)
5. LLM compares fetched data against doc content (text parsing, diff logic)
6. LLM constructs a `batchUpdate` JSON request with formatting
7. `gws-safe` enforces dry-run; user must approve; LLM re-runs with `--confirmed <nonce>`
8. LLM re-reads the doc and repopulates the cache

The LLM is doing everything: reading JSON files, making HTTP calls via wrappers, parsing document structure, diffing lists, computing character indices, building formatting requests. Most of this is mechanical.

---

## Skill 1: open-tickets

### Current Flow (per run)

| Step | What happens | API calls | LLM decisions | Approval prompts |
|------|-------------|-----------|---------------|-----------------|
| 1 | Read `daily_log.json` and `doc_styles.json` | 0 (local file reads) | 0 | 0 |
| 2 | Check cache: `daily-log-cache get` | 0 (local SQLite) | 0 | 0 |
| 3 | Fetch Google Doc: `gws-safe docs documents get` | 1 GWS API call | LLM parses entire doc structure, identifies sections, builds cache JSON | 0 |
| 4 | Fetch open tickets: `freshdesk-safe tickets search --query "status:2"` | 1 FreshDesk API call | 0 | 0 |
| 4b | For each unique requester: `freshdesk-safe contacts view <ID>` | N FreshDesk API calls (1 per unique requester) | 0 | 0 |
| 5 | Compare tickets against doc content | 0 | LLM extracts ticket IDs from doc text via regex, diffs against fetched list | 0 |
| 6 | Build batchUpdate JSON with formatting | 0 | LLM calculates character indices, constructs insertText + createParagraphBullets + updateTextStyle requests | 1 (dry-run approval) |
| 7 | Re-read doc, repopulate cache | 1 GWS API call | LLM re-parses entire doc, builds cache JSON | 0 |

**Totals per run:**
- GWS API calls: 2 (get doc) or 1 (if cache hit skips Step 3 on first run, but Step 7 always re-reads)
- FreshDesk API calls: 1 (search) + N (contact lookups, typically 5-15 unique requesters)
- LLM invocations: The LLM is orchestrating the entire flow. It makes every decision.
- Approval prompts: 1 (batchUpdate dry-run) or 0 (if no new tickets)

### What's Wasteful

1. **Contact lookups are repeated every run.** Every time the skill runs, it fetches every unique requester's contact info from FreshDesk. If there are 10 open tickets from 8 unique requesters, that's 8 API calls to get names that haven't changed since last run. The CRM database already has 28 contacts with `freshdesk_id` mapped, but open-tickets ignores it entirely.

2. **The LLM parses the Google Doc structure every time.** Even with the cache, the LLM still has to fetch the doc to read the current Open Tickets text content for comparison. The doc content (current ticket list) could be cached locally.

3. **The LLM computes batchUpdate character indices.** This is pure arithmetic -- count characters, compute start/end ranges, apply formatting. No judgment needed.

4. **The LLM constructs the entire batchUpdate JSON.** The formatting rules are fixed: checkbox bullets, Roboto font, specific bullet preset. This is a template, not a creative task.

5. **Post-update doc re-read.** Step 7 fetches the entire doc again just to update the cache. The skill already knows exactly what it inserted and where.

6. **The full doc is fetched even when only a small section is needed.** The Open Tickets section is typically ~400 characters in a doc that's 15,000+ characters.

### What Can Be Cached

| Data | Change frequency | Cache location |
|------|-----------------|----------------|
| FreshDesk contact names (requester_id -> name) | Rarely changes | CRM database (contacts table, already has freshdesk_id) |
| Current ticket IDs in the doc | Changes when user checks off tickets or skill adds new ones | daily_log_cache or a local JSON file |
| Doc section boundaries | Changes on every edit | daily_log_cache (already cached) |
| Style config, daily_log config | Almost never changes | Already on disk, could be embedded in script |
| Open ticket list from FreshDesk | Changes when tickets open/close | Short-lived cache (5 min TTL) in SQLite or temp file |

### What Can Be Deterministic

**Everything except "should I run at all" and "approve the write."**

A Python script can:
1. Read config files (trivial)
2. Query `daily-log-cache` SQLite directly (no wrapper needed; it's a local DB)
3. Call `freshdesk-safe tickets search --query "status:2"` and parse the JSON output
4. Look up requester names: first check CRM SQLite (`contacts` table by `freshdesk_id`), only call `freshdesk-safe contacts view` for unknown requesters, then cache new ones in CRM
5. Call `gws-safe docs documents get` and parse the section content
6. Diff the two ticket lists deterministically
7. Compute character indices and build the `batchUpdate` JSON
8. Call `gws-safe docs documents batchUpdate` (dry-run enforced by wrapper)
9. After confirmation, call with `--confirmed <nonce>`
10. Update the cache

### What Still Needs the LLM

- **Nothing in the normal flow.** The open-tickets skill is entirely mechanical.
- **Error recovery** -- if the doc structure is unexpected or API calls fail in unusual ways, a human or LLM might need to diagnose. But the script can just report the error and exit.

---

## Skill 2: task-list

### Current Flow (per run)

| Step | What happens | API calls | LLM decisions | Approval prompts |
|------|-------------|-----------|---------------|-----------------|
| 1 | Read `daily_log.json` and `doc_styles.json` | 0 (local file reads) | 0 | 0 |
| 2 | Check cache: `daily-log-cache get` | 0 (local SQLite) | 0 | 0 |
| 3 | Fetch Google Doc: `gws-safe docs documents get` | 1 GWS API call | LLM parses entire doc, identifies HEADING_1/2/3, builds cache JSON | 0 |
| 4a | Fetch calendar events: `gws-safe calendar events list` | 1 GWS API call | LLM filters by eventType and colorId | 0 |
| 4b | Fetch in-progress tasks: `gws-safe tasks tasks list` | 1 GWS API call | 0 | 0 |
| 4c | Fetch waiting tasks: `gws-safe tasks tasks list` | 1 GWS API call | LLM filters by due date | 0 |
| 5 | Compare fetched data against doc content | 0 | LLM reads Task List section text, identifies existing items, extracts HEADING_3 titles from Notes section, diffs, determines sort order | 0 |
| 6 | Build batchUpdate JSON | 0 | LLM calculates character indices for: new priority items, waiting/blockers updates, new HEADING_3 sub-sections with link lines, font styling, bullet formatting | 1 (dry-run approval) |
| 7 | Re-read doc, repopulate cache | 1 GWS API call | LLM re-parses entire doc, builds cache JSON | 0 |

**Totals per run:**
- GWS API calls: 4-5 (doc get, calendar list, tasks list x2, post-update doc get)
- FreshDesk API calls: 0
- LLM invocations: The LLM orchestrates the entire flow
- Approval prompts: 1 (batchUpdate dry-run) or 0 (if no changes)

### What's Wasteful

1. **Calendar events and tasks are re-fetched every run.** Calendar events for today don't change frequently. Tasks in-progress and waiting lists change slowly. A 5-minute cache would eliminate most redundant fetches.

2. **The LLM reads and parses HEADING_3 sub-sections from the Notes section every time.** Even though the cache has Notes section boundaries, the skill re-reads the doc to get current HEADING_3 titles because "the user types notes throughout the day." This is correct -- subsection indices go stale -- but the heading *titles* themselves are stable. The script only needs to know *which* headings exist, not their exact indices (indices are only needed for insertions at the end of Notes).

3. **Support Doc URL extraction is repeated.** Every run, the LLM parses event descriptions for `Support Doc:` URLs. These don't change within a day.

4. **The LLM computes all batchUpdate character indices.** Same as open-tickets -- this is pure arithmetic.

5. **The batchUpdate request is complex but formulaic.** The formatting rules are fixed: Lexend for headings, Roboto for body, specific bullet presets, link styling. The LLM is doing template expansion, not creative writing.

6. **Post-update doc re-read.** Same as open-tickets.

7. **Timezone offset is computed via `date +%:z` every run.** Trivial, but symptomatic of the LLM re-deriving constants.

### What Can Be Cached

| Data | Change frequency | Cache location |
|------|-----------------|----------------|
| Calendar events for today | Changes when events are added/modified | SQLite or JSON file, 5-min TTL |
| In-progress tasks | Changes when tasks are added/completed | SQLite or JSON file, 5-min TTL |
| Waiting tasks due today | Changes when tasks are added/modified | SQLite or JSON file, 5-min TTL |
| Support Doc URLs from event descriptions | Stable for the day | SQLite keyed by event ID |
| Existing HEADING_3 titles in Notes | Changes when user adds notes (rare during auto-runs) | daily_log_cache subsections table |
| Current Task List section text | Changes on every edit | Refreshed from doc each run (necessary) |

### What Can Be Deterministic

**Everything except "approve the write."**

A Python script can:
1. Read config files
2. Query `daily-log-cache` SQLite directly
3. Call `gws-safe calendar events list`, `gws-safe tasks tasks list` (x2) and parse JSON
4. Filter events by `eventType` and `colorId` -- pure logic
5. Filter waiting tasks by due date -- pure logic
6. Call `gws-safe docs documents get` and parse the section content
7. Extract existing items from Task List text (regex for `(event)` and `(task)` patterns)
8. Extract existing HEADING_3 titles from Notes section (parse paragraph styles)
9. Extract Support Doc URLs from event descriptions (regex)
10. Diff and determine what's new
11. Sort new entries: all-day events first (alpha), timed events (by start time), tasks (list order)
12. Compute character indices and build the batchUpdate JSON
13. Call `gws-safe docs documents batchUpdate`
14. After confirmation, call with `--confirmed <nonce>`
15. Update the cache

### What Still Needs the LLM

- **Nothing in the normal flow.** Like open-tickets, this is entirely mechanical.
- **Error recovery** for unexpected doc structure.

---

## Optimization Plan

### Phase 1: Deterministic Python Scripts

Create two Python scripts that replace the LLM orchestration:

#### `bin/update-open-tickets` (Python)

**What it does:**
1. Reads `config/daily_log.json` and `config/doc_styles.json`
2. Queries `db/daily_log_cache.db` directly for today's section boundaries
3. Calls `freshdesk-safe tickets search --query "status:2"` via subprocess, parses JSON output
4. For each unique `requester_id`:
   - Queries CRM SQLite (`db/crm.db`) for contact by `freshdesk_id`
   - If found, uses cached name
   - If not found, calls `freshdesk-safe contacts view <ID>`, then creates/updates CRM contact record via `crm-safe contacts create`
5. Calls `gws-safe docs documents get`, extracts only the Open Tickets section text
6. Parses existing ticket IDs from section text (regex: `\[(\d+)\]`)
7. Computes the diff (new tickets not in doc)
8. If no new tickets, prints "Open Tickets is already up to date" and exits
9. Builds the `batchUpdate` JSON:
   - `insertText` at the section end index
   - `createParagraphBullets` with checkbox preset
   - `updateTextStyle` with Roboto font
   - Character index arithmetic is pure Python
10. Calls `gws-safe docs documents batchUpdate` (dry-run enforced by wrapper)
11. Prints the dry-run output and nonce for user approval
12. When called with `--confirm <nonce>`, re-runs `gws-safe` with `--confirmed <nonce>`
13. Re-reads doc, updates cache

**Estimated per-run savings:**
- FreshDesk contact API calls: from N (5-15) down to 0-2 (only unknown requesters)
- LLM invocations: from 1 full LLM session down to 0
- Approval prompts: stays at 1 (batchUpdate), but could be eliminated (see Phase 3)

#### `bin/update-task-list` (Python)

**What it does:**
1. Reads config files
2. Queries daily_log_cache for today's section boundaries
3. Calls `gws-safe calendar events list`, `gws-safe tasks tasks list` (x2) via subprocess
4. Filters events (excludes `workingLocation`, excluded colorIds)
5. Filters waiting tasks (only today's due date)
6. Calls `gws-safe docs documents get`, extracts Task List and Notes sections
7. Parses existing priorities from Task List text (regex: `\((event|task)\)\s+(.+)`)
8. Parses existing HEADING_3 titles from Notes section (paragraph style inspection)
9. Extracts Support Doc URLs from event descriptions (regex)
10. Computes diffs:
    - New priority items (events/tasks not in doc)
    - Updated waiting/blockers
    - New Notes HEADING_3 sub-sections needed
11. Sorts new entries: all-day events (alpha), timed events (by start), tasks (list order)
12. Builds the batchUpdate JSON:
    - New priority bullet items
    - Waiting/blockers content update
    - New HEADING_3 headings with link lines
    - All font/color/bullet formatting
    - Character index arithmetic
13. Calls `gws-safe docs documents batchUpdate` (dry-run enforced)
14. Prints dry-run output and nonce
15. When called with `--confirm <nonce>`, re-runs with `--confirmed <nonce>`
16. Re-reads doc, updates cache

**Estimated per-run savings:**
- GWS API calls: same count (these are necessary), but no redundant doc re-parsing by LLM
- LLM invocations: from 1 full LLM session down to 0
- Approval prompts: stays at 1, but could be eliminated (see Phase 3)

### Phase 2: Local Caching Layer

Add a `freshdesk_cache` table to the CRM database (or a new SQLite file) for short-lived FreshDesk data:

#### New table: `freshdesk_contacts_cache`

Not needed -- the CRM `contacts` table already has `freshdesk_id`. The Python scripts should query CRM first and only call `freshdesk-safe contacts view` for unknown requesters. When a new requester is found, the script creates the CRM contact record via `crm-safe`.

#### New table: `open_tickets_snapshot`

```sql
CREATE TABLE open_tickets_snapshot (
    freshdesk_ticket_id  INTEGER PRIMARY KEY,
    subject              TEXT,
    requester_id         INTEGER,
    requester_name       TEXT,
    fetched_at           TEXT NOT NULL
);
```

Purpose: Cache the last `freshdesk-safe tickets search --query "status:2"` result. If `fetched_at` is less than 5 minutes old, skip the FreshDesk API call entirely. This matters because FreshDesk has rate limits (not just cost) and the ticket list doesn't change minute-to-minute.

Location: `db/daily_log_cache.db` (colocated with the existing cache).

#### Calendar/tasks caching

For `update-task-list`, add similar short-lived cache tables:

```sql
CREATE TABLE calendar_events_cache (
    event_id        TEXT PRIMARY KEY,
    summary         TEXT,
    start_time      TEXT,
    end_time        TEXT,
    all_day         INTEGER,
    color_id        TEXT,
    event_type      TEXT,
    description     TEXT,
    html_link       TEXT,
    support_doc_url TEXT,   -- pre-extracted
    fetched_at      TEXT NOT NULL
);

CREATE TABLE tasks_cache (
    task_id         TEXT PRIMARY KEY,
    title           TEXT,
    list_type       TEXT CHECK (list_type IN ('in_progress', 'waiting')),
    due             TEXT,
    web_view_link   TEXT,
    sort_order      INTEGER,
    fetched_at      TEXT NOT NULL
);
```

Cache TTL: 5 minutes. On each run, check `fetched_at`. If stale, re-fetch from API. If fresh, use cached data.

**Estimated per-run savings (with caching):**
- FreshDesk API calls: from 1 + N down to 0 (if cache is fresh) or 1 + 0-2 (if cache is stale)
- GWS API calls: from 4-5 down to 1-2 (doc get is always needed; calendar/tasks use cache)

### Phase 3: Eliminating the Approval Prompt

Currently, `gws-safe` enforces dry-run on all `batchUpdate` calls. The user must approve each write. This is the right default for LLM-generated requests, but a deterministic script that always produces the same kind of output (append-only ticket lines, append-only priority items) has a lower risk profile.

**Option A: Pre-approved script path in gws-safe**

Add a mechanism to `gws-safe` where specific callers (identified by a script signature or environment variable set by a trusted launcher) can bypass the dry-run for narrow operations. For example:

```bash
# In gws-safe, check if caller is a pre-approved script
if [[ "${GWS_CALLER:-}" == "update-open-tickets" ]]; then
    # Skip dry-run for batchUpdate on the daily log doc only
    ...
fi
```

This requires careful scoping:
- Only for `docs documents batchUpdate`
- Only for the daily log document ID
- Only for append operations (insertText + formatting, no deleteContentRange)

**Option B: Auto-confirm wrapper**

Create a thin wrapper (`bin/auto-confirm-gws`) that:
1. Runs `gws-safe` with the full command
2. Captures the nonce from stderr
3. Immediately re-runs with `--confirmed <nonce>`

This eliminates the prompt entirely but trusts the calling script. Since the calling script is deterministic and checked into the repo, this is equivalent to pre-approving its output.

**Option C: Direct `gws` call from trusted scripts**

The deterministic scripts could call `/usr/bin/gws` directly (bypassing `gws-safe`) for their specific, narrow operations. This is the simplest approach but loses the audit logging.

**Recommendation: Option B** -- Auto-confirm wrapper. It preserves the audit trail (gws-safe still logs everything), the nonce mechanism still works (preventing replays), but the human doesn't have to click "approve" for a known-good script.

Implementation:
```bash
#!/usr/bin/env bash
# bin/auto-confirm-gws
# Runs gws-safe, captures the dry-run nonce, and auto-confirms.
# Only for use by trusted deterministic scripts.

set -euo pipefail

output=$(/home/timothylytle/agent-team/bin/gws-safe "$@" 2>&1) || true
nonce=$(echo "$output" | grep -oP '(?<=--confirmed )[a-f0-9]+')

if [[ -z "$nonce" ]]; then
    # No dry-run was triggered (read-only op or error)
    echo "$output"
    exit 0
fi

# Auto-confirm
/home/timothylytle/agent-team/bin/gws-safe "$@" --confirmed "$nonce"
```

**Estimated savings:** Eliminates 1 approval prompt per skill run (2 total per daily-log cycle).

### Phase 4: Updated SKILL.md Files

The SKILL.md files would become thin wrappers that invoke the Python scripts:

**open-tickets/SKILL.md** would say:
```
Run: bin/update-open-tickets
If it exits with code 0, report its output.
If it exits with a non-zero code, report the error.
```

**task-list/SKILL.md** would say:
```
Run: bin/update-task-list
If it exits with code 0, report its output.
If it exits with a non-zero code, report the error.
```

The LLM's only role becomes: invoke the script and report the result.

---

## Summary of Estimated Savings

### open-tickets (per run)

| Metric | Current | Optimized | Reduction |
|--------|---------|-----------|-----------|
| FreshDesk API calls | 1 + N (6-16 total) | 0-1 (cache hit) or 1 + 0-2 (cache miss) | 75-95% |
| GWS API calls | 2 | 1-2 | 0-50% |
| LLM token usage | ~5,000-10,000 tokens (full orchestration) | ~100 tokens (invoke script, report result) | ~98% |
| Approval prompts | 1 | 0 (with auto-confirm) | 100% |
| Wall-clock time | 30-90 sec (LLM thinking + API round-trips) | 5-15 sec (script execution) | 70-85% |

### task-list (per run)

| Metric | Current | Optimized | Reduction |
|--------|---------|-----------|-----------|
| GWS API calls | 4-5 | 1-3 (with calendar/tasks cache) | 40-75% |
| LLM token usage | ~8,000-15,000 tokens | ~100 tokens | ~98% |
| Approval prompts | 1 | 0 (with auto-confirm) | 100% |
| Wall-clock time | 45-120 sec | 5-20 sec | 75-85% |

### Combined (both skills, per daily-log update cycle)

| Metric | Current | Optimized | Reduction |
|--------|---------|-----------|-----------|
| Total API calls | 7-21 | 2-6 | 70-85% |
| LLM sessions | 2 full sessions | 0 (or 2 trivial invocations) | ~100% |
| Approval prompts | 2 | 0 | 100% |
| Wall-clock time | 75-210 sec | 10-35 sec | 80-85% |

---

## Implementation Priority

1. **Phase 1 (highest impact):** Write the two Python scripts. This eliminates the LLM from the critical path and makes runs 5-10x faster.
2. **Phase 3 (highest UX impact):** Auto-confirm wrapper. This eliminates the approval friction that makes these skills annoying to run repeatedly.
3. **Phase 2 (cost reduction):** Caching layer. Reduces API calls, especially the FreshDesk contact lookups.
4. **Phase 4 (cleanup):** Update SKILL.md files to be script invocations.

Phases 1 and 3 can be done in parallel. Phase 2 can be folded into Phase 1 (build caching into the scripts from the start). Phase 4 is trivial once the scripts work.

---

## Risks and Constraints

1. **Google Doc index arithmetic is fragile.** The batchUpdate API uses character indices that shift as content is inserted. The current LLM approach handles this by reasoning through it, but a Python script must get the arithmetic exactly right. Careful testing with actual doc content is essential.

2. **Doc structure changes break scripts.** If Timothy reorganizes the daily log format (renames sections, changes heading levels), the Python scripts will break. The LLM-based approach is more resilient to format changes. Mitigation: validate expected section structure on each run and fail gracefully with a clear error message.

3. **Auto-confirm reduces the safety net.** The dry-run approval exists to prevent bad writes. A deterministic script producing bad output (due to a bug) would auto-confirm bad data. Mitigation: the scripts should validate their own output before writing (e.g., confirm the batchUpdate only contains insertText and formatting, no deletions).

4. **gws-safe audit trail.** The auto-confirm wrapper preserves audit logging, so this is not a concern.

5. **CRM contact creation side effect.** Phase 2 has the scripts creating CRM contacts when encountering unknown FreshDesk requesters. This is actually desirable (it's what the crm-ensure skill does anyway), but it's a write operation happening silently. The CRM database doesn't require confirmation (local SQLite), so this is fine, but it should be logged.
