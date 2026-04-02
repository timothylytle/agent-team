# Support Notes: Ticket Note Import

## Summary

Enhance the `support-notes` skill so that when a FreshDesk ticket has a private note mentioning "support-bot", the note's content (text, links, images) is extracted and appended as a new section at the bottom of the ticket's support Google Doc.

## Section Format

Each injected note becomes:

```
YYYYMMDD-ticket-note                    <- HEADING_2
Created: YYYY-MM-DD HH:MM (UTC)        <- NORMAL_TEXT (metadata)
Author: [Name]                          <- NORMAL_TEXT (metadata)
                                        <- blank line
[Content from the note]                 <- NORMAL_TEXT with formatting (links, etc.)
```

Where `YYYYMMDD` is the date the note was created in FreshDesk.

## Changes to SKILL.md

### 1. Allowed Operations

Add to the GWS section:
- `gws-safe docs documents get` (read) — needed to read the existing doc to find the end-of-document insertion point
- `freshdesk-safe tickets view` (read) — needed to fetch conversations (already used via freshdesk-notes sub-skill, but should be explicitly listed)

### 2. Modify Step 2: Track existing doc links

Currently, Step 2 skips tickets that already have support docs. Change it to:
- Still collect tickets that need new docs (no change)
- Also collect tickets that already have docs, along with the doc URL extracted from the matching note body
- Both sets are needed: new docs proceed through Steps 3-9, existing docs go to the new step

### 3. New Step (after Step 9d): Inject support-bot tagged notes

For ALL tickets that have a support doc (both newly created and pre-existing):

#### 3a. Fetch conversations
```bash
freshdesk-safe tickets view <TICKET_ID> --include conversations
```

#### 3b. Find tagged notes
Filter conversations where:
- `private` is true (or `source` is 2 for notes)
- `body_text` contains "support-bot" (case-insensitive)

#### 3c. Duplicate detection
For each matching note, check if it has already been injected:
- Read the support doc via `gws-safe docs documents get`
- Search the doc text for the note's `created_at` timestamp (formatted as the YYYYMMDD in the heading plus the time in metadata). If a section with a matching "Created:" timestamp exists, skip this note.

#### 3d. Resolve author
Look up the note's `user_id`:
```bash
freshdesk-safe contacts view <USER_ID>
```
Use the `name` field. If the lookup fails (agent IDs may not be contacts), use "Unknown" or the `from_email` if available.

#### 3e. Extract content from HTML
Use a Python heredoc script to parse the note's `body` HTML:
- Strip the "@support-bot" or "support-bot" mention text
- Extract plain text (strip HTML tags, preserve line breaks from `<br>`, `<p>`, `<div>`)
- Extract links: `<a href="URL">text</a>` -> track text range and URL for later `updateTextStyle`
- Extract inline image URLs from `<img src="...">` tags
- Note: FreshDesk attachment/image URLs may not work with Google Docs `insertInlineImage` due to authentication. If image insertion fails, skip the image and report it. Text content must still be inserted.

#### 3f. Build and execute batchUpdate
1. Read the doc to find the end index: last element's `endIndex` in `body.content`
2. Insert at `endIndex - 1` (before the trailing newline)
3. Build requests:
   - `insertText` with the full section text (heading + metadata + blank line + content + trailing newline)
   - `updateParagraphStyle` for HEADING_2 on the heading line
   - `updateParagraphStyle` for NORMAL_TEXT on all other lines
   - `updateTextStyle` with Lexend font on the heading
   - `updateTextStyle` with Roboto font on normal text
   - `updateTextStyle` with `link.url` for each extracted link
   - `insertInlineImage` for each image (highest-index-first, skip on failure)
4. Execute via `gws-safe docs documents batchUpdate` (write, dry-run enforced)

### 4. Update Step 10: Report injected notes

Add to the report:
- Number of notes injected per ticket
- For each: ticket ID, note date, and whether images were included or skipped

## Risks

1. **Image URLs**: FreshDesk attachment URLs are authenticated and may not work with Google Docs `insertInlineImage`. Plan to gracefully skip failed images.
2. **10-conversation limit**: `tickets view --include conversations` returns max 10 conversations. Tagged notes beyond this limit will be missed. Acceptable for now since tagged notes are typically recent.
3. **Agent user IDs**: The `user_id` on a note may be an agent, not a contact. `contacts view` may fail for agents. Fall back to "Unknown" or email.
