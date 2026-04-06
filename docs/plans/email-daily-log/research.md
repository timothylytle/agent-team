# Email Daily Log — Research

## Objective

Create a new "Email" section on the daily log that shows important inbox emails, filtered and prioritized. The section surfaces emails that need attention, excludes automated noise, and classifies senders by their relationship to the business using CRM data.

## Requirements (from Timothy)

- Read all emails in Inbox without the "Ack'd" label
- Filter out: automated notifications, marketing/newsletters, calendar invites, mailing lists, social notifications
- Checkbox list format: sender name + subject line
- Priority ordering: VIP companies > Customers (CRM match) > Internal (miarec.com) > Unknown
- Unknown senders should appear with a note asking if they should be added to CRM
- Section positioned after "Random Fact:" and before "Thoughts / Ideas:"
- No auto-labeling of emails (skip for now)
- No AI summary (not available via API)

## Gmail API Capabilities

### Available Operations

- `messages list` and `messages get` are available via the `gws-safe` wrapper
- Listing supports Gmail search queries (e.g., `in:inbox -label:Ack'd`)
- `messages get` returns full message metadata including headers and labels

### Category Labels (Primary Classification Signal)

Gmail automatically assigns category labels that provide the strongest filtering signal:

| Label | Meaning | Action |
|-------|---------|--------|
| `CATEGORY_PROMOTIONS` | Marketing, newsletters | Filter out |
| `CATEGORY_UPDATES` | Automated notifications | Filter out |
| `CATEGORY_FORUMS` | Mailing lists, group discussions | Filter out |
| `CATEGORY_SOCIAL` | Social network notifications | Filter out |
| `CATEGORY_PERSONAL` | Direct personal email | Keep |

### Header-Based Filtering (Secondary Signal)

For emails that lack category labels or need additional classification:

- `List-Unsubscribe` header — indicates marketing/newsletter
- `Auto-Submitted` header — indicates automated system email
- `List-Id` header — indicates mailing list
- `text/calendar` MIME parts — indicates calendar invites

### Other Relevant Fields

- `To` / `Cc` headers — detect whether Timothy is a direct recipient or CC'd
- `snippet` field — ~200 character preview available but not being used per Timothy's preference
- Gmail AI summaries — NOT available via API (UI-only feature, confirmed)

## CRM Integration

### Sender Classification

Email classification uses CRM data to determine sender priority:

1. **VIP** — sender's domain matches a CRM company with `vip = TRUE`, or sender's email matches a contact with `vip = TRUE`
2. **Customer** — sender's domain matches any CRM company record
3. **Internal** — sender's domain is `miarec.com`
4. **Unknown** — no CRM match found; display with a note suggesting CRM addition

### Schema Change Required

The `companies` table needs a new `vip` boolean field. The `contacts.vip` field already exists, so this follows an established pattern.

**Files requiring changes for the VIP field:**

| File | Change |
|------|--------|
| `db/schema.sql` | Add `vip` column to `companies` table |
| `bin/crm-safe` | Expose `vip` in company operations |
| `.claude/skills/crm/SKILL.md` | Document new field |
| `db/crm.db` | Run ALTER TABLE migration |

## Architecture

### Pattern: Follow `open-tickets`

The email section follows the same architecture as the existing open-tickets feature:

- **New section type** `'email'` added to `SECTION_MAP` in `daily_log_utils.py`
- **New script** `bin/update-email` following the `bin/update-open-tickets` pattern
- **Section creation** via `build_entry_text()` in `bin/create-daily-log`
- **Cache boundary tracking** for incremental updates (avoids re-fetching all emails)
- **All Gmail operations** through the `gws-safe` wrapper

### Cache Schema

The daily log cache schema at `db/daily_log_cache_schema.sql` needs:

- A new `'email'` value in the section type CHECK constraint
- Cache table for email section content and boundaries

## Key Files

| File | Purpose |
|------|---------|
| `bin/create-daily-log` | Daily log entry creation; add email section to `build_entry_text()` |
| `bin/update-open-tickets` | Pattern to follow for the update script |
| `bin/lib/daily_log_utils.py` | Shared utilities, `SECTION_MAP`, cache operations |
| `db/daily_log_cache_schema.sql` | Cache schema (CHECK constraint needs `'email'` added) |
| `db/schema.sql` | CRM schema (add `companies.vip`) |
| `bin/crm-safe` | CRM CLI wrapper (expose `companies.vip`) |
| `.claude/skills/crm/SKILL.md` | CRM operations reference (document `vip` field) |
| `.claude/skills/gws/SKILL.md` | Gmail operations reference |
| `config/daily_log.json` | Doc ID configuration |
| `config/doc_styles.json` | Formatting configuration |

## Labeling Decision

Auto-labeling emails (e.g., marking as "Ack'd" after display) is deferred. Adding it later would require:

- `gmail.modify` OAuth scope (not currently granted)
- Unblocking `messages.modify` in `gws-safe`
- Security review by Dwight

This can be added as a separate initiative without affecting the core email section feature.

## Risks / Caveats

- **Gmail category accuracy** — Gmail's automatic categorization is not perfect. Some legitimate emails may land in CATEGORY_UPDATES or CATEGORY_PROMOTIONS. The header-based secondary filtering helps but edge cases will exist.
- **CRM data completeness** — sender classification quality depends on how complete the CRM company records are. Unknown senders will be flagged for potential CRM addition, which should improve accuracy over time.
- **Rate limits** — fetching individual messages via `messages get` for each inbox email could hit Gmail API rate limits if the inbox is large. The cache boundary approach mitigates this for incremental updates.
- **No write-back** — without auto-labeling, there is no mechanism to mark emails as "seen" by the daily log. The same unack'd emails will appear on subsequent runs until manually labeled.
