# /project Skill — Implementation Plan

## Overview

A new `/project` skill that helps Timothy scope, research, and plan development projects. The skill manages a Google Doc as the human-facing planning document and tracks projects in the CRM for querying.

### Workflow

1. **`/project new`** — Timothy provides a brief description. The skill interviews him to fill out a project document (Problem Statement, Desired Outcome, Scope, etc.). Creates a Google Doc + CRM project record.
2. **`/project research <code>`** — Agree on research topics, then research and populate them in the Google Doc. Timothy reviews and adds notes/questions.
3. **`/project spec <code>`** — When research is complete, generates a `spec.md` file suitable for `/mr_create_spec` or `/mr_plan`.
4. **`/project status [code]`** — Shows status of one or all projects from CRM.
5. **`/project update <code>`** — Review/update specific research questions or sections.

### Google Doc Template Structure

```
[Project Title]
Scope — [Project Code]

+------------------+---------------------------+
| Project Title    | {name}                    |
| Project Code     | {project_code}            |
| Author           | Timothy Lytle             |
| Issue Date       | {date}                    |
+------------------+---------------------------+

H1: Overview
  H2: Problem Statement
  H2: Desired Outcome

H1: Scope
  H2: In Scope
  H2: Out of Scope
  H2: Constraints / Assumptions

H1: Current State

H1: Success Criteria

H1: References

H1: Deliverables / Milestones
  - [{project-code}] deliverable 1
  - [{project-code}-phase] sub-deliverable

H1: Research Topics
  H2: Topic 1 — {title}
    {research content}
  H2: Topic 2 — {title}
    {research content}

H1: Implementation Log
  H3: {date}
    {log entry}
```

---

## Implementation Phases

### Phase 1: CRM Extension — Add `projects` entity

**Assigned to:** Ryan
**Reviewed by:** Dwight

Files to modify:
1. **`db/schema.sql`** — Add `project_statuses` lookup table (scoping=1, researching=2, implementing=3, complete=4) and `projects` table with fields: id, name, project_code (unique), status_id (FK), company_id (FK), summary, google_doc_id, google_doc_url, priority (1-4), tags (JSON), start_date, due_date, created_at, updated_at
2. **`bin/crm-safe`** — Add `cmd_projects_list`, `cmd_projects_view`, `cmd_projects_create`, `cmd_projects_update` handlers following the `meetings` pattern. Add `'projects'` to argparse choices. Add `--status-id` argument. Add four ROUTES entries.
3. **`db/crm.db`** — Run migration SQL to add new tables to existing database (do NOT use init_db.sh which drops all data)
4. **`.claude/skills/crm/SKILL.md`** — Document new projects operations and schema

### Phase 2: Google Doc Creation Script

**Assigned to:** Ryan
**Reviewed by:** Dwight

Create `bin/create-project-doc` — Python script that:
1. Creates a Google Doc in Shared Drive "Devops" > `projects` > `<project-code>` subfolder using `gws-safe drive files create`
2. Populates the template structure (metadata table, all section headings) using `gws-safe docs documents batchUpdate`
3. Returns the doc ID and URL
4. Uses existing utilities from `bin/lib/support_utils.py` (auto_confirm_gws, build_paragraph_style_request, etc.)
5. Accepts arguments: `--name`, `--project-code`, `--author` (optional, defaults to Timothy)

### Phase 3: Skill Definition

**Assigned to:** Ryan
**Reviewed by:** Dwight

Create `.claude/skills/project/SKILL.md` — Procedural skill (Category 3) defining:

**`/project new`**
- Ask for brief description
- Interview to fill out: Problem Statement, Desired Outcome, In Scope, Out of Scope, Constraints, Current State, Success Criteria
- Generate project code from title (e.g., `2026q2_api-refactor`)
- Suggest research topics based on the scope
- Run `bin/create-project-doc` to create Google Doc
- Run `crm-safe projects create` to create CRM record
- Present Google Doc link

**`/project research <code>`**
- Look up project in CRM to get Google Doc ID
- Read current doc state via `gws-safe docs documents get`
- Show current research topics and their status
- Delegate research to Oscar (subagent_type=Oscar), who researches topics using web search, docs, etc.
- Dwight reviews Oscar's findings for accuracy and completeness
- Update Google Doc with reviewed findings via batchUpdate
- Update CRM project status to "researching" if not already

**`/project spec <code>`**
- Look up project in CRM
- Read Google Doc to extract: Problem Statement, Desired Outcome, Scope, Success Criteria, Research findings
- Generate a `spec.md` file in `docs/plans/<project-code>/`
- Format for compatibility with `/mr_plan` workflow

**`/project status [code]`**
- If code given: `crm-safe projects view` + show details
- If no code: `crm-safe projects list` + show summary table

**`/project update <code> [section]`**
- Look up project, read doc, allow targeted updates to specific sections or research topics

### Phase 4: Registration

**Assigned to:** Ryan

1. Update `CLAUDE.md` Skills table with new `/project` skill
2. Test full workflow: new → research → spec → status

---

## Dependencies

- Phase 2 depends on Phase 1 (CRM record needed for doc linkage)
- Phase 3 depends on Phase 1 + Phase 2 (skill references both)
- Phase 4 depends on all prior phases

## Decisions

1. **Google Doc location:** Shared Drive "Devops" > `projects` folder > `<project-code>` subfolder > Doc
2. **Project code format:** `2026q2_project-name` — year + quarter + underscore + kebab name
3. **Research execution:** Oscar handles research, followed by Dwight review of findings
