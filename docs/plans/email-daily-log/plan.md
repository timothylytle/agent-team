# Email Daily Log — Implementation Plan

## Overview

Add an "Email" section to the daily log that surfaces important inbox emails, filtered and prioritized by CRM data. Two parts: (A) add VIP field to CRM companies table, (B) create the email update skill.

## Part A: Add VIP to Companies Table

### A1: Schema update (`db/schema.sql`)
Add `vip INTEGER DEFAULT 0 CHECK (vip IN (0, 1))` to the companies table definition, alongside health_score/account_tier.

### A2: CRM wrapper (`bin/crm-safe`)
Add `'vip'` to the `allowed` tuples in `cmd_companies_create` and `cmd_companies_update`.

### A3: CRM skill docs (`.claude/skills/crm/SKILL.md`)
Add `vip` to the companies schema overview.

### A4: Live database migration (manual)
Run against the live database:
```sql
ALTER TABLE companies ADD COLUMN vip INTEGER DEFAULT 0 CHECK (vip IN (0, 1));
```

## Part B: Email Daily Log Skill

### B1: Cache schema (`db/daily_log_cache_schema.sql`)
Add `'email'` to the section_type CHECK constraint.

### B2: SECTION_MAP (`bin/lib/daily_log_utils.py`)
Add `"Email:": "email"` entry.

### B3: Daily log creation (`bin/create-daily-log`)
Add "Email:" section in `build_entry_text()` after "Random Fact:" and before "Thoughts / Ideas:". Register `update-email` in `run_update_path()`.

### B4: Update script (`bin/update-email`)
Deterministic Python script following the `update-open-tickets` pattern:
1. Read configs, get section boundaries from cache
2. Fetch inbox emails via gws-safe (INBOX label, filter out Ack'd)
3. Fetch message metadata for each message
4. Filter out: CATEGORY_PROMOTIONS/UPDATES/FORUMS/SOCIAL, List-Unsubscribe, List-Id, Auto-Submitted, text/calendar, no-reply senders
5. Classify by CRM: VIP > Customer > Internal > Unknown
6. Format as checkbox lines, grouped by priority
7. Deduplicate against existing section content
8. Build and execute batchUpdate
9. Refresh cache

### B5: Skill definition (`.claude/skills/email/SKILL.md`)
Define the skill following the open-tickets pattern.

### B6: CLAUDE.md
Add Email skill to the Skills table.

## Dependencies

- Part A must be complete before Part B (VIP classification depends on the field)
- Live database migration (A4) is manual — not automated by this plan
