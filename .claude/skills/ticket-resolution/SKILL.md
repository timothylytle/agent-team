---
name: ticket-resolution
description: Updates support docs and CRM records when a FreshDesk ticket is resolved or closed.
---

You are executing the Ticket Resolution skill. This skill generates a resolution summary and runs a deterministic script to update the support doc and CRM.

## Input

The user provides a FreshDesk ticket ID (or URL). Extract the numeric ticket ID.

## Steps

### 1. Fetch ticket conversations

```bash
bin/freshdesk-safe tickets view <TICKET_ID> --include conversations
```

Review the ticket subject, description_text, and the non-private conversation body_text entries to understand the issue and how it was resolved.

### 2. Generate a resolution summary

Write a 2-3 sentence summary covering:
- What the customer's issue was
- How it was resolved

Do NOT include private notes or support-bot notes in your analysis. Focus on the customer-facing conversation thread.

### 3. Run the script

```bash
/home/timothylytle/agent-team/bin/update-ticket-resolution --ticket <TICKET_ID> --summary "<summary>" --auto-confirm
```

To preview without making changes:

```bash
/home/timothylytle/agent-team/bin/update-ticket-resolution --ticket <TICKET_ID> --summary "<summary>" --dry-run
```

### 4. Report results

After the script completes, report what it printed. The script outputs a summary including:
- Whether the support doc was updated with a Resolution section
- Whether the CRM ticket record was updated with resolution data
- Any warnings or skipped steps
