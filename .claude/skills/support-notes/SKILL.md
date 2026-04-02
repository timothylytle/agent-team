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
- **Style config:** `/home/timothylytle/agent-team/config/doc_styles.json`
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
- `gws-safe docs documents get` (read)
- `gws-safe docs documents batchUpdate` (write, dry-run enforced)

### FreshDesk
- `freshdesk-safe contacts view` (read)
- `freshdesk-safe tickets view` (read)
- `freshdesk-safe tickets note` (write, dry-run enforced)

### CRM
- `crm-safe companies create` (write)
- `crm-safe files create` (write)
- `crm-safe files link` (write)

## Step 0: Read style config

Read the style config at `/home/timothylytle/agent-team/config/doc_styles.json`. Use these values for all document formatting.

## Step 1: Gather non-closed tickets

Read and follow `.claude/skills/freshdesk-active/SKILL.md`.

Expected output: a list of non-closed, agent-assigned FreshDesk tickets.

If no tickets are returned, report "No assigned non-closed tickets found" and stop.

## Step 2: Check for existing support notes (duplicate detection)

For each ticket from Step 1, read and follow `.claude/skills/freshdesk-notes/SKILL.md` with these inputs:
- ticket_id: the FreshDesk ticket ID
- search_pattern: `docs.google.com/document`

Separate the tickets into two lists:

- **Tickets without docs** (`found` is false): these need new support notes and proceed through Steps 3-9.
- **Tickets with existing docs** (`found` is true): extract the Google Doc URL from the matching note's `body` field. Parse the Google Doc ID from the URL — the segment after `/document/d/` and before the next `/`. Collect these tickets with their doc IDs for processing in Step 9e.

If no tickets need new docs AND no tickets have existing docs, report "No assigned non-closed tickets found" and stop. If no tickets need new docs but some have existing docs, skip to Step 9e.

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
   - `updateTextStyle` with `weightedFontFamily: {"fontFamily": "<fonts.heading from style config>"}` and `fields: "weightedFontFamily"` on all HEADING_1 and HEADING_2 paragraphs
   - If `colors.headingText` in the style config is not null, include `foregroundColor: {"color": {"rgbColor": <colors.headingText>}}` in the heading `updateTextStyle` request (add `"foregroundColor"` to the `fields` mask)
   - `updateTextStyle` with `weightedFontFamily: {"fontFamily": "<fonts.body from style config>"}` and `fields: "weightedFontFamily"` on all NORMAL_TEXT paragraphs
   - If `colors.bodyText` in the style config is not null, include `foregroundColor: {"color": {"rgbColor": <colors.bodyText>}}` in the body `updateTextStyle` request (add `"foregroundColor"` to the `fields` mask)
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

### 9e: Inject support-bot tagged notes

For ALL tickets that have a support doc — both newly created in Step 9 and pre-existing from Step 2 — perform the following. For newly created tickets, the doc ID comes from the Step 9a response. For pre-existing tickets, the doc ID was parsed from the note body in Step 2.

#### 9e-i: Fetch conversations

```bash
freshdesk-safe tickets view <TICKET_ID> --include conversations
```

#### 9e-ii: Find tagged notes

Filter conversations where:
- `private` is true (or `source` is 2)
- `body_text` contains "support-bot" or "support bot" (case-insensitive)

If no tagged notes are found for this ticket, skip to the next ticket.

#### 9e-iii: Read the support doc

```bash
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```

#### 9e-iv: Duplicate detection

For each matching note, check if it has already been injected. Parse the note's `created_at` field (e.g., `"2026-04-02T14:30:00Z"`) and format it as `YYYY-MM-DD HH:MM:SS (UTC)`. Search through the doc's text content for this exact string. If found, skip this note.

#### 9e-v: Resolve author

Look up the note's `user_id`:
```bash
freshdesk-safe contacts view <USER_ID>
```
Use the `name` field. If the lookup fails, use "Unknown".

#### 9e-vi: Extract content from HTML

Use a Python heredoc script to parse the note's `body` HTML. The script should:
- Strip/remove the "support-bot" mention text (and any "@" prefix)
- Extract plain text: strip HTML tags, convert `<br>`, `</p>`, `</div>` to newlines, collapse excessive blank lines (3+ consecutive newlines become 2)
- Track links: for each `<a href="URL">text</a>`, record the text, URL, and character offset within the extracted text
- Track inline images: for each `<img src="URL">`, record the URL and character offset
- Output as JSON: `{"text": "...", "links": [{"start": N, "end": N, "url": "..."}], "images": [{"offset": N, "url": "..."}]}`

Example:
```bash
python3 << 'PYEOF'
import json, re, sys

html = '''<NOTE_BODY_HTML>'''

# Remove support-bot mention
html = re.sub(r'@?support[- ]bot', '', html, flags=re.IGNORECASE)

# Track links and images before stripping tags
links = []
images = []

# Replace <br>, </p>, </div> with newline markers
html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)

# Extract links with positions
text_so_far = ''
result_text = ''
pos = 0
link_pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
img_pattern = re.compile(r'<img\s+[^>]*src=["\']([^"\']*)["\'][^>]*/?>', re.IGNORECASE)

# Process HTML sequentially: find all tags and text
tag_re = re.compile(r'(<a\s+[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>|<img\s+[^>]*src=["\']([^"\']*)["\'][^>]*/?>|<[^>]+>)', re.IGNORECASE | re.DOTALL)

clean_pos = 0
clean_text = ''
link_list = []
image_list = []

for m in tag_re.finditer(html):
    # Add text before this tag
    before = html[clean_pos:m.start()]
    clean_text += before

    if m.group(3) is not None:  # <a> tag
        link_text = re.sub(r'<[^>]+>', '', m.group(3))
        start = len(clean_text)
        clean_text += link_text
        end = len(clean_text)
        link_list.append({"start": start, "end": end, "url": m.group(2)})
    elif m.group(4) is not None:  # <img> tag
        offset = len(clean_text)
        image_list.append({"offset": offset, "url": m.group(4)})
    # else: other tag, skip

    clean_pos = m.end()

# Add remaining text
clean_text += html[clean_pos:]

# Collapse excessive blank lines
clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
clean_text = clean_text.strip()

print(json.dumps({"text": clean_text, "links": link_list, "images": image_list}))
PYEOF
```

Replace `<NOTE_BODY_HTML>` with the note's `body` field value (escape single quotes as needed for the heredoc).

#### 9e-vii: Build and execute batchUpdate

Build the section text for each note:
```
YYYYMMDD-ticket-note\n
Created: YYYY-MM-DD HH:MM:SS (UTC)\n
Author: [Name]\n
\n
[Extracted content text]\n
```

Where `YYYYMMDD` comes from the note's `created_at` date.

Find the insertion point: from the doc read in Step 9e-iii, take the last element's `endIndex` in `body.content` and insert at `endIndex - 1` (before the trailing newline).

**Index calculation:** After inserting text at the insertion point, count characters from that point to determine the start and end index of each line. Each newline character (`\n`) counts as 1 character. Calculate all formatting ranges relative to the insertion point.

Build batchUpdate requests:
1. `insertText` at the insertion point with all the section text
2. `updateParagraphStyle` for NORMAL_TEXT on the entire inserted range (to reset any inherited style)
3. `updateParagraphStyle` for HEADING_2 on the heading line (`YYYYMMDD-ticket-note`)
4. `updateTextStyle` with `weightedFontFamily: {"fontFamily": "<fonts.heading from style config>"}` and `fields: "weightedFontFamily"` on the heading line
   - If `colors.headingText` in the style config is not null, include `foregroundColor: {"color": {"rgbColor": <colors.headingText>}}` in the heading `updateTextStyle` request (add `"foregroundColor"` to the `fields` mask)
5. `updateTextStyle` with `weightedFontFamily: {"fontFamily": "<fonts.body from style config>"}` and `fields: "weightedFontFamily"` on normal text paragraphs (metadata lines and content)
   - If `colors.bodyText` in the style config is not null, include `foregroundColor: {"color": {"rgbColor": <colors.bodyText>}}` in the body `updateTextStyle` request (add `"foregroundColor"` to the `fields` mask)
6. `updateTextStyle` with `link.url` for each extracted link — calculate start/end indices relative to the insertion point by adding the link's offset within the content text to the absolute index where the content text begins
7. `insertInlineImage` for each image — process highest-index-first to avoid index shifting. If image insertion fails, note it in the report but still insert text and links.

Execute:
```bash
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```
This is a write operation. Present the dry-run to the user, get confirmation, then execute with `--confirmed <nonce>`.

If the batchUpdate fails due to an image insertion error, retry without the `insertInlineImage` requests so that text, formatting, and links are still injected. Report the skipped images to the user.

**Multiple notes per ticket:** If there are additional notes to process for the same ticket, re-read the document (repeat Step 9e-iii) before processing the next note to get the updated endIndex.

## Step 10: Report results

After all tickets have been processed, report:

- Number of support notes created
- For each: ticket ID, subject, company, and link to the created Google Doc
- Number of tagged notes injected per ticket
- For each injected note: ticket ID, note date, and author
- Any tickets that were skipped (no CRM match or user declined)
- Any images that failed to insert
- Any errors encountered

## Error Handling

- If any wrapper command fails, report the error and stop processing the current ticket. Continue with the next ticket if possible.
- If the user declines a write operation, skip that ticket and continue with the next.
- If the Customers Shared Drive is not found, stop and report the error.
- If a customer folder is not found in the Shared Drive, stop processing tickets for that customer and report the issue.
