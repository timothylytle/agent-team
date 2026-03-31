---
name: freshdesk-notes
description: FreshDesk Ticket Note Scanner — fetches a ticket's conversations and searches for specific content in note bodies.
---

You are executing the FreshDesk Note Scanner sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Fetch a FreshDesk ticket's conversations and search for specific content in note bodies.

## Inputs

- **ticket_id** (required): The FreshDesk ticket ID
- **search_pattern** (required): Text to search for in note bodies (e.g., `"docs.google.com/document"`, `"Support notes:"`)

## Outputs

Return the following to the calling skill:

- **found**: boolean, true if any note body contains the search pattern
- **note_id**: The ID of the matching note (if found)
- **note_body**: The full body text of the matching note (if found)
- **matched_content**: The matched text or line from the note body (if found)

If multiple notes match, return the first match.

## Constants

- **FreshDesk wrapper:** `/home/timothylytle/agent-team/bin/freshdesk-safe`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.

## Allowed Operations

- `freshdesk-safe tickets view` (read)

## Blocked Operations

- Any write operations (note, note-update, create, update, delete)

## Step 1: Fetch ticket conversations

```bash
freshdesk-safe tickets view <TICKET_ID> --include conversations
```

## Step 2: Search note bodies

Iterate through the conversations in the response. For each note/conversation, search the `body` (or `body_text`) field for the given `search_pattern`.

- **If found:** Return:
  - `found`: true
  - `note_id`: the matching note's `id`
  - `note_body`: the full body text of the matching note
  - `matched_content`: the matched text or line containing the search pattern

- **If not found after checking all conversations:** Return:
  - `found`: false
