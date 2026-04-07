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

## Handle skipped tickets (No CRM company resolved)

If any tickets were skipped with reason "No CRM company resolved", present them to the user and ask if they want to create CRM company records:

1. For each skipped ticket, show: ticket ID, subject, requester name, requester email, and the email domain
2. Ask the user: "Would you like to create a CRM company for [domain]? If so, what should the company name be?"
3. If the user provides a company name, create the CRM company:
   ```bash
   bin/crm-safe companies create --json '{"name": "<company_name>", "domains": ["<domain>"]}'
   ```
4. After creating the company, re-run the support-notes script to process the previously skipped tickets:
   ```bash
   /home/timothylytle/agent-team/bin/update-support-notes --auto-confirm
   ```
