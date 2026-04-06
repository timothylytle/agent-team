---
name: support-notes
description: Creates support note documents in Google Drive for open FreshDesk tickets, linking them back to the ticket via a private note.
---

You are executing the Support Notes skill. Run the deterministic Python script and report the output.

## Execution

```bash
/home/timothylytle/agent-team/bin/update-support-notes --auto-confirm
```

If the user wants to skip tickets whose requester domain can't be matched to a CRM company or Drive folder, add `--skip-unmatched`:

```bash
/home/timothylytle/agent-team/bin/update-support-notes --auto-confirm --skip-unmatched
```

To preview what would be created without making changes:

```bash
/home/timothylytle/agent-team/bin/update-support-notes --dry-run
```

## What the script does

1. Fetches all active (non-closed, agent-assigned) FreshDesk tickets
2. Checks each ticket for an existing support doc (scans notes for `docs.google.com/document`)
3. For tickets needing new docs:
   - Looks up the requester's email and resolves to a CRM company
   - For unmatched domains, searches the Customers Shared Drive for matching folders
   - Ensures CRM contact and ticket records exist
   - Creates a Google Doc in the company's `support` subfolder
   - Populates the doc with ticket details
   - Adds a private FreshDesk note linking to the doc
   - Links the doc in the CRM
4. For ALL tickets with support docs (new and existing):
   - Injects any support-bot tagged private notes into the doc

## Report the output

After the script completes, report what it printed. The script outputs a full summary including:
- Number of support notes created (with ticket IDs, subjects, and doc links)
- Number of tagged notes injected
- Any skipped tickets (with reasons)
- Any errors encountered
