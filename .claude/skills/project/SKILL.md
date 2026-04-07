---
name: project
description: Development Project Manager — creates, researches, and tracks development projects through scoping, research, and spec generation.
---

You are executing the Project skill. This is an interactive, multi-mode skill. Determine the mode from the user's command and follow the corresponding procedure.

## Modes

Parse the user's input to determine the mode:

- `/project new [description]` — Start a new project
- `/project research <project-code>` — Research topics for a project
- `/project spec <project-code>` — Generate a spec.md from the project doc
- `/project status [project-code]` — Show project status
- `/project update <project-code> [section-or-topic]` — Update a section or research topic

If no mode is recognized, show the list of available modes and ask the user what they want to do.

## Constants

- **CRM wrapper:** `/home/timothylytle/agent-team/bin/crm-safe`
- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **Project doc creator:** `/home/timothylytle/agent-team/bin/create-project-doc`
- **Project plans directory:** `/home/timothylytle/agent-team/docs/plans/`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"`.
- For multiline Python scripts, use heredoc syntax (`python3 << 'PYEOF' ... PYEOF`) instead of `python3 -c "..."`.
- CRM write operations execute directly (no dry-run/confirmation needed).
- All GWS write operations called from scripts must use `--auto-confirm`. Only use `--auto-confirm` after the user has explicitly approved the content to be written. Never auto-confirm a GWS write with content the user has not reviewed.

## Allowed Operations

### CRM (via crm-safe)
- `crm-safe projects list` (read)
- `crm-safe projects list --company-id ID` (read)
- `crm-safe projects list --status-id ID` (read)
- `crm-safe projects view ID` (read)
- `crm-safe projects create --json '{...}'` (write)
- `crm-safe projects update ID --json '{...}'` (write)

### GWS (via gws-safe)
- `gws-safe docs documents get --params '{"documentId":"DOC_ID"}'` (read)
- `gws-safe docs documents batchUpdate --json '{...}' --params '{"documentId":"DOC_ID"}' --auto-confirm` (write, after user approval)

### Scripts
- `bin/create-project-doc --name "..." --project-code "..." --auto-confirm` (write)

## Blocked Operations
- Direct database access
- Any delete operations
- Any CRM operations on non-project entities (companies, contacts, tickets, meetings, emails, files)
- GWS operations outside of Docs (no Drive, Gmail, Calendar, etc. directly)

## Behavioral Rules

1. **Always look up projects by project_code in the CRM first.** Never ask the user for doc IDs or CRM IDs.
2. **Interview one section at a time.** Do not dump all questions at once.
3. **Suggest content.** Based on the user's answers, propose draft text for each section. Don't just ask questions — help write.
4. **Project code format is strict:** `{year}q{quarter}_{kebab-name}` (e.g., `2026q2_api-refactor`).
5. **Deliverables use bracket prefix:** `[{project-code}] deliverable name` for tasks, `[{project-code}-phase] sub-deliverable` for sub-tasks.
6. **Research uses the Oscar to Dwight pipeline.** Delegate research to Oscar (subagent_type=Oscar), have Dwight review (subagent_type=Dwight), then present findings to the user.
7. **Google Doc is the source of truth** for project scope and research. CRM tracks metadata and status.
8. **CRM status transitions:** Scoping (1) -> Researching (2) -> Implementing (3) -> Complete (4). Only move forward, never backward.

---

## Mode: `/project new`

### Purpose

Start a new project. Interview the user to scope it, then create a Google Doc and CRM record.

### Step 1: Get the brief description

If the user provided a description after `/project new`, use it as starting context. If not, ask:

> What project are you thinking about? Give me a brief description.

### Step 2: Interview to fill out project sections

Walk through each section one at a time. For each section:
- Ask the question
- Based on the user's answer, propose draft text for that section
- Ask the user to confirm or adjust the draft before moving on

Sections to fill out in order:

1. **Problem Statement** — "What problem are you trying to solve?"
2. **Desired Outcome** — "What does success look like?"
3. **In Scope / Out of Scope** — "What's included? What's explicitly excluded?"
4. **Constraints / Assumptions** — "Any limitations or things we're assuming?"
5. **Current State** — "What exists today?"
6. **Success Criteria** — "How will we measure success?"
7. **References** — "Any relevant links, docs, or resources?"

### Step 3: Generate a project code

Derive a project code from the project name and the current date:
- Format: `{year}q{quarter}_{kebab-name}`
- Example: `2026q2_api-refactor`

Present the suggested code to the user for confirmation.

### Step 4: Suggest research topics

Based on the scope discussion, suggest initial research topics. These are questions or areas that need investigation before implementation — architecture decisions, technology choices, key concepts, API capabilities, etc.

Present the list and ask the user to confirm, modify, add, or remove topics.

### Step 5: Generate deliverables

Based on the scope, suggest a deliverables list using the bracket prefix notation:
- `[{project-code}] deliverable name`
- `[{project-code}-phase] sub-deliverable`

Present to the user for confirmation.

### Step 6: Create the Google Doc and CRM record

Once the user approves the full scope:

1. Create the Google Doc:
   ```bash
   /home/timothylytle/agent-team/bin/create-project-doc --name "PROJECT NAME" --project-code "CODE" --auto-confirm
   ```
   This outputs JSON with `document_id`, `url`, and `folder_id`.

2. Create the CRM project record. Ask the user if this project is associated with a company (optional). If so, look up the company_id from `crm-safe companies list`:
   ```bash
   crm-safe projects create --json '{"name":"PROJECT NAME","project_code":"CODE","status_id":1,"summary":"BRIEF SUMMARY","start_date":"YYYY-MM-DD","company_id":COMPANY_ID}'
   ```
   Omit `company_id` if no company association. Note the returned project `id`.

3. Update the CRM record with the Google Doc info:
   ```bash
   crm-safe projects update ID --json '{"google_doc_id":"DOC_ID","google_doc_url":"DOC_URL"}'
   ```

4. Populate the interview content into the Google Doc. The `create-project-doc` script creates the template headings but leaves sections empty. To populate:
   - Read the doc to find insertion points: `gws-safe docs documents get --params '{"documentId":"DOC_ID"}'`
   - Find the end index of each section heading (Problem Statement, Desired Outcome, etc.)
   - Use `gws-safe docs documents batchUpdate` to insert the approved content after each heading
   - Insert content in reverse document order (highest index first) so earlier insertions don't shift later indices
   - **CRITICAL: Inserted text inherits the paragraph style of the heading it follows.** After inserting content, you MUST apply `updateParagraphStyle` with `namedStyleType: "NORMAL_TEXT"` to every inserted content paragraph. Without this, all content will render as headings. Only research topic sub-headings should retain `HEADING_2` style.
   - Use `auto_confirm_gws()` from `lib/support_utils` for all GWS write operations (not `--auto-confirm` as a CLI flag)

5. Present the Google Doc link to the user.

---

## Mode: `/project research`

### Purpose

Research topics for a project and populate findings in the Google Doc.

### Step 1: Look up the project

```bash
crm-safe projects list
```

Find the project matching the given project_code. Extract the CRM project `id`, `google_doc_id`, and `google_doc_url`.

If no project is found, tell the user and stop.

### Step 2: Read the current doc state

```bash
gws-safe docs documents get --params '{"documentId":"DOC_ID"}'
```

Parse the doc content to find the "Research Topics" section. Identify any existing topic headings (H2 under Research Topics) and whether they have content below them.

### Step 3: Show current research topics

Present the user with a list of current research topics and their status:
- Topics with content: mark as "populated"
- Topics without content: mark as "empty"

Ask which topic to research, or if they want to add a new topic.

### Step 4: Research the topic

Delegate research to Oscar using the Agent tool with `subagent_type=Oscar`. Provide Oscar with:
- The topic title and any context from the project scope
- Instructions to research thoroughly using WebSearch, WebFetch, and other available tools
- The specific questions or areas to investigate

### Step 5: Review findings

Have Dwight review Oscar's findings using the Agent tool with `subagent_type=Dwight`. Dwight should review for:
- Accuracy and completeness
- Any security or policy concerns
- Whether the findings actually address the research topic

### Step 6: Present to the user

Present the reviewed findings to the user for approval. Allow them to request changes or accept as-is.

### Step 7: Update the Google Doc

Once the user approves:

1. Read the doc again to get current indices: `gws-safe docs documents get --params '{"documentId":"DOC_ID"}'`
2. Find the insertion point for the research topic (after the topic's H2 heading)
3. Use `gws-safe docs documents batchUpdate` via `auto_confirm_gws()` to insert the findings content
4. **CRITICAL: Inserted text inherits the heading style.** After inserting, apply `updateParagraphStyle` with `namedStyleType: "NORMAL_TEXT"` to all inserted content paragraphs so they don't render as headings.
5. If the topic is new, first insert a new H2 heading under "Research Topics", then insert the content below it

### Step 8: Update CRM status

If the project status is still "Scoping" (1), update it to "Researching" (2):
```bash
crm-safe projects update ID --json '{"status_id":2}'
```

### Step 9: Continue or finish

Ask the user if they want to research another topic or if they're done for now.

---

## Mode: `/project spec`

### Purpose

Generate a `spec.md` file from the project's Google Doc, suitable for `/mr_create_spec` or `/mr_plan`.

### Step 1: Look up the project

```bash
crm-safe projects list
```

Find the project matching the given project_code. Extract the CRM project `id`, `name`, `google_doc_id`.

If no project is found, tell the user and stop.

### Step 2: Read the Google Doc

```bash
gws-safe docs documents get --params '{"documentId":"DOC_ID"}'
```

Extract all populated sections from the doc:
- Problem Statement
- Desired Outcome
- In Scope
- Out of Scope
- Constraints / Assumptions
- Current State
- Success Criteria
- References
- Deliverables / Milestones
- Research Topics (each topic with its findings)

### Step 3: Create the spec.md

Create the plan directory if it doesn't exist, then write the spec file at `docs/plans/<project-code>/spec.md` with this structure:

```markdown
# {Project Name}

## Problem Statement
{from doc}

## Desired Outcome
{from doc}

## Scope
### In Scope
{from doc}
### Out of Scope
{from doc}

## Constraints / Assumptions
{from doc}

## Current State
{from doc}

## Success Criteria
{from doc}

## Research Findings
### {Topic 1}
{findings}
### {Topic 2}
{findings}

## Deliverables
{from doc}

## References
{from doc}
```

### Step 4: Update CRM status

Only update status to "Implementing" (3) if the current status is "Researching" (2):
```bash
crm-safe projects update ID --json '{"status_id":3}'
```
If the project is already at "Implementing" or "Complete", do not change the status. If it is still at "Scoping", warn the user that research has not been completed and ask if they want to proceed anyway.

### Step 5: Report and suggest next steps

Tell the user:
- The spec file path: `docs/plans/<project-code>/spec.md`
- Suggest running `/mr_plan` to create an implementation plan from the spec

---

## Mode: `/project status`

### Purpose

Show project status.

### With a project-code

Look up the specific project:
```bash
crm-safe projects list
```

Find the project by project_code, then view its details:
```bash
crm-safe projects view ID
```

Present the project details including:
- Name
- Project code
- Status (with human-readable label: Scoping, Researching, Implementing, Complete)
- Summary
- Google Doc link
- Start date and due date (if set)
- Priority (if set)

### Without a project-code

List all projects:
```bash
crm-safe projects list
```

Format the output as a clean summary table with columns:
- Code
- Name
- Status
- Summary

---

## Mode: `/project update`

### Purpose

Review and update specific sections or research topics in the project doc.

### Step 1: Look up the project

```bash
crm-safe projects list
```

Find the project matching the given project_code. Extract the CRM project `id`, `google_doc_id`.

If no project is found, tell the user and stop.

### Step 2: Read the Google Doc

```bash
gws-safe docs documents get --params '{"documentId":"DOC_ID"}'
```

### Step 3: Determine what to update

If the user specified a section or topic name, find that section in the doc and show its current content.

If no section was specified, show an overview of all sections with a brief summary of their content (first line or "empty"), and ask which section to work on.

### Step 4: Update the section

For **scope sections** (Problem Statement, Desired Outcome, Scope, etc.):
- Show the current content
- Ask the user what to change
- Propose updated text
- Once approved, update the Google Doc using `gws-safe docs documents batchUpdate` with `--auto-confirm`
  - Delete the old content range, then insert the new content at the same position
  - Read the doc again first to get current indices

For **research topics**:
- Follow the same Oscar -> Dwight -> User flow as `/project research` (Steps 4-7)
- This allows re-researching a topic or adding new findings

### Step 5: Continue or finish

Ask the user if they want to update another section or if they're done.
