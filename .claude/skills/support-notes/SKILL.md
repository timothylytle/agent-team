---
name: support-notes
description: Creates support note documents in Google Drive for open FreshDesk tickets, linking them back to the ticket via a private note.
---

You are executing the Support Notes skill. Follow these steps in order. Be functional and direct.

## Constants

- **GWS wrapper:** `/home/timothylytle/agent-team/bin/gws-safe`
- **FreshDesk wrapper:** `/home/timothylytle/agent-team/bin/freshdesk-safe`
- **CRM wrapper:** `/home/timothylytle/agent-team/bin/crm-safe`
- **FreshDesk ticket URL pattern:** `https://miarec.freshdesk.com/a/tickets/<TICKET_ID>`
- **Shared Drive name:** `Customers`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.
- For multiline Python scripts, use heredoc syntax (`python3 << 'PYEOF' ... PYEOF`) instead of `python3 -c "..."` to avoid triggering security prompts from `#` characters in inline code.
- GWS and FreshDesk write operations go through the dry-run/nonce/confirmation flow described by each wrapper. CRM write operations execute directly.

## Blocked Operations

The following operations are FORBIDDEN and must NEVER be attempted by this skill:

- `gws-safe drive files delete` — deleting files from the Shared Drive
- `gws-safe drive files trash` — trashing files in the Shared Drive
- `gws-safe drive files update` with a `removeParents` or parent-change that moves files out of the Shared Drive
- Any `delete`, `trash`, or `remove` operation against the Customers Shared Drive

This skill may ONLY use the following operations:

### GWS (Drive/Docs)
- `gws-safe drive drives list` (read)
- `gws-safe drive files list` (read)
- `gws-safe drive files create` (write, dry-run enforced)
- `gws-safe docs documents batchUpdate` (write, dry-run enforced)

### FreshDesk
- `freshdesk-safe contacts view` (read)
- `freshdesk-safe tickets note` (write, dry-run enforced)

### CRM
- `crm-safe companies create` (write)
- `crm-safe files create` (write)
- `crm-safe files link` (write)

## Step 1: Gather non-closed tickets

Read and follow `.claude/skills/freshdesk-active/SKILL.md`.

Expected output: a list of non-closed, agent-assigned FreshDesk tickets.

If no tickets are returned, report "No assigned non-closed tickets found" and stop.

## Step 2: Check for existing support notes (duplicate detection)

For each ticket from Step 1, read and follow `.claude/skills/freshdesk-notes/SKILL.md` with these inputs:
- ticket_id: the FreshDesk ticket ID
- search_pattern: `docs.google.com/document`

If `found` is true, that ticket already has a support notes doc. Skip it.

Collect the remaining tickets that need support notes. If none remain, report "All assigned tickets already have support notes" and stop.

## Step 3: Look up requestor details

For each ticket that needs a support notes doc, get the requestor's contact information:
```bash
freshdesk-safe contacts view <REQUESTER_ID>
```

Extract the `email` field from the response.

## Step 4: Resolve CRM entities

For each ticket, read and follow `.claude/skills/crm-resolve/SKILL.md` with these inputs:
- email: the requester's email from Step 3

Expected outputs: `company_id`, `company_name`, `contact_id`, `matched_by`

**If `matched_by` is `"not_found"`:** Before asking the user, search the Customers Shared Drive for a folder matching the domain. Extract a keyword from the domain by taking the domain name without the TLD (e.g., "granitenet" from "granitenet.com"), then stripping common suffixes like "net", "tech", "corp", "inc", "telecom" to get the core name (e.g., "granite").

Search the Shared Drive (you will need the Drive ID from Step 7a — run that lookup early if needed):
```bash
gws-safe drive files list --params '{"q":"name contains '\''KEYWORD'\'' and mimeType='\''application/vnd.google-apps.folder'\'' and '\''DRIVE_ID'\'' in parents","driveId":"DRIVE_ID","corpora":"drive","includeItemsFromAllDrives":true,"supportsAllDrives":true}'
```

- If exactly one folder is found, present it to the user for confirmation (e.g., "Found folder 'Granite Telecom' — use this?"). If confirmed, use that folder name as the company name for this ticket.
- If multiple folders are found, present them as options for the user to choose from.
- If no folders are found, THEN ask the user to specify the target directory in the Shared Drive or create a new one.

Continue processing other tickets that do have matches.

## Step 5: Create CRM company record for unmatched domains

If any ticket's domain was NOT found in the CRM but was resolved via Shared Drive folder search or user input in Step 4, create a CRM company record so future lookups work automatically.

```bash
crm-safe companies create --json '{"name":"COMPANY_NAME","domains":["DOMAIN"]}'
```

Replace `COMPANY_NAME` with the folder name confirmed in Step 4 (e.g., "Granite Telecom") and `DOMAIN` with the requestor's email domain (e.g., "granitenet.com").

Skip this step for tickets whose domains already had a CRM match. If multiple tickets share the same unmatched domain, create only one company record and apply it to all of them.

## Step 6: Ensure contact and ticket exist in CRM

For each ticket being processed, read and follow `.claude/skills/crm-ensure/SKILL.md` with these inputs:
- freshdesk_ticket_id: the FreshDesk ticket ID
- freshdesk_ticket_subject: the ticket subject
- freshdesk_ticket_status: the ticket status
- freshdesk_ticket_priority: the ticket priority
- requester_email: the requester's email from Step 3
- requester_name: the requester's full name
- requester_first_name: the requester's first name
- requester_last_name: the requester's last name
- requester_freshdesk_id: the FreshDesk ticket's `requester_id`
- company_id: the CRM company ID from Step 4 or Step 5

Expected outputs: `crm_contact_id`, `crm_ticket_id`, `created_contact`, `created_ticket`

## Step 7: Locate the Shared Drive and customer folders

### 7a: Find the Customers Shared Drive

```bash
gws-safe drive drives list
```

Find the drive named "Customers" and extract its `id`.

### 7b: Find customer folders

For each unique customer name from Step 4 (or Step 5, if the company was resolved via Shared Drive search), find the customer's top-level folder in the Shared Drive:
```bash
gws-safe drive files list --params '{"q":"name=\"CUSTOMER_NAME\" and mimeType=\"application/vnd.google-apps.folder\" and \"DRIVE_ID\" in parents","driveId":"DRIVE_ID","corpora":"drive","includeItemsFromAllDrives":true,"supportsAllDrives":true}'
```

Replace `CUSTOMER_NAME` with the company name from the CRM and `DRIVE_ID` with the Customers Shared Drive ID.

### 7c: Find or create the "support" subfolder

For each customer folder, look for a "support" subfolder:
```bash
gws-safe drive files list --params '{"q":"name=\"support\" and mimeType=\"application/vnd.google-apps.folder\" and \"CUSTOMER_FOLDER_ID\" in parents","driveId":"DRIVE_ID","corpora":"drive","includeItemsFromAllDrives":true,"supportsAllDrives":true}'
```

If the "support" folder does not exist, create it:
```bash
gws-safe drive files create --params '{"supportsAllDrives":true}' --json '{"name":"support","mimeType":"application/vnd.google-apps.folder","parents":["CUSTOMER_FOLDER_ID"]}'
```
This is a write operation. Present the dry-run to the user and ask for confirmation. After approval, re-run with `--confirmed <nonce>`.

## Step 8: Present summary and confirm

Before creating any documents, present a summary table to the user showing:

- Ticket ID and subject
- Requestor name and email
- Company name
- Proposed doc name (`YYYYMMDD-<ID>-<short-description>`)
- Target folder path (Customers > {Company} > support)

Ask the user: "Should I proceed with creating these support notes?"

If the user declines, stop and report that the operation was cancelled.

### Doc naming format

`YYYYMMDD-<ID>-<short-description>` where:
- `YYYYMMDD` is today's date
- `<ID>` is the FreshDesk ticket ID (e.g., `1850`)
- `<short-description>` is derived from the ticket subject: lowercase, replace spaces with hyphens, strip special characters, truncate to ~50 characters max

## Step 9: Create support note documents

Process each ticket sequentially.

### 9a: Create the Google Doc

```bash
gws-safe drive files create --params '{"supportsAllDrives":true}' --json '{"name":"YYYYMMDD-ID-short-description","mimeType":"application/vnd.google-apps.document","parents":["SUPPORT_FOLDER_ID"]}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

Extract the `id` (documentId) and `webViewLink` from the response.

### 9b: Populate the document

Build a `batchUpdate` request to populate the doc with content. The document structure:

```
[Ticket Subject]                    <- HEADING_1
FreshDesk Ticket                    <- NORMAL_TEXT, with link to ticket URL
[1-2 sentence description of the issue, derived from the ticket subject/description]
Key Facts                           <- HEADING_2
Requestor: [Name] ([email])        <- NORMAL_TEXT
Company: [Company Name]            <- NORMAL_TEXT
```

Build the batchUpdate:

1. **Insert all text** at index 1 as a single `insertText` request. Include newlines to separate each line. Add a trailing newline at the end.

2. **Apply formatting** with subsequent requests. After text is inserted, calculate character indices and apply:
   - `updateParagraphStyle` for HEADING_1 on the ticket subject line
   - `updateParagraphStyle` for HEADING_2 on the "Key Facts" line
   - `updateTextStyle` with `link.url` set to `https://miarec.freshdesk.com/a/tickets/<TICKET_ID>` on the "FreshDesk Ticket" text

Execute:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

### 9c: Add private note to FreshDesk ticket

After the doc is created and populated, add a private note to the FreshDesk ticket linking to the new doc:

```bash
freshdesk-safe tickets note <TICKET_ID> --body "Support notes: <WEB_VIEW_LINK>" --private true
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

### 9d: Link the doc to the company in the CRM

After the FreshDesk note is added, create a drive file record in the CRM and link it to the company. Use the `id` (google_file_id) and `webViewLink` from the Step 9a doc creation response, and the `COMPANY_ID` from Step 4/5.

1. Create the drive file record:
```bash
crm-safe files create --json '{"google_file_id":"DOC_ID","name":"DOC_NAME","mime_type":"application/vnd.google-apps.document","web_view_link":"WEB_VIEW_LINK"}'
```
Extract the `id` from the response to use as `FILE_ID` below.

2. Link the file to the company:
```bash
crm-safe files link --company-id COMPANY_ID --file-id FILE_ID
```

## Step 10: Report results

After all tickets have been processed, report:

- Number of support notes created
- For each: ticket ID, subject, company, and link to the created Google Doc
- Any tickets that were skipped (already had notes, or no CRM match)
- Any errors encountered

## Error Handling

- If any wrapper command fails, report the error and stop processing the current ticket. Continue with the next ticket if possible.
- If the user declines a write operation, skip that ticket and continue with the next.
- If the Customers Shared Drive is not found, stop and report the error.
- If a customer folder is not found in the Shared Drive, stop processing tickets for that customer and report the issue.
