---
name: crm-ensure
description: CRM Ensure Records — ensures CRM contact and ticket records exist for a FreshDesk ticket, creating them if missing.
---

You are executing the CRM Ensure sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Given a FreshDesk ticket and a resolved CRM company, ensure CRM contact and ticket records exist. Create any that are missing.

## Inputs

- **freshdesk_ticket_id** (required): The FreshDesk ticket ID
- **freshdesk_ticket_subject** (required): The ticket subject
- **freshdesk_ticket_status** (required): The ticket status (numeric)
- **freshdesk_ticket_priority** (required): The ticket priority (1-4)
- **requester_email** (required): The requester's email address
- **requester_name** (required): The requester's full name
- **requester_first_name** (required): The requester's first name
- **requester_last_name** (required): The requester's last name
- **requester_freshdesk_id** (required): The requester's FreshDesk contact ID
- **company_id** (required): The CRM company ID

## Outputs

Return the following values to the calling skill:

- **crm_contact_id**: CRM contact ID (existing or newly created)
- **crm_ticket_id**: CRM ticket ID (existing or newly created)
- **created_contact**: boolean, true if a new contact was created
- **created_ticket**: boolean, true if a new ticket was created

## Constants

- **CRM wrapper:** `/home/timothylytle/agent-team/bin/crm-safe`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.
- For multiline Python scripts, use heredoc syntax (`python3 << 'PYEOF' ... PYEOF`) instead of `python3 -c "..."` to avoid triggering security prompts from `#` characters in inline code.
- CRM write operations execute directly (no dry-run/confirmation needed).

## Allowed Operations

- `crm-safe contacts list` (read)
- `crm-safe contacts create` (write)
- `crm-safe tickets list` (read)
- `crm-safe tickets create` (write)

## Blocked Operations

- Any delete operations
- Direct database access
- Modifying existing contacts or tickets (update)

## Step 1: Ensure contact exists in CRM

Check if the contact already exists by listing contacts for the company and filtering client-side by `freshdesk_id` or `email`:
```bash
crm-safe contacts list --company-id <COMPANY_ID>
```

Search the results for a contact matching the requester's `freshdesk_id` (the `requester_freshdesk_id` input) or `email` (the `requester_email` input).

- **If found:** Use the existing contact's CRM `id` as `crm_contact_id`. Set `created_contact` to false.
- **If NOT found:** Create the contact:
  ```bash
  crm-safe contacts create --json '{"name":"FULL_NAME","first_name":"FIRST","last_name":"LAST","email":"EMAIL","freshdesk_id":FRESHDESK_ID,"company_id":COMPANY_ID}'
  ```
  Use the newly created contact's `id` as `crm_contact_id`. Set `created_contact` to true.

## Step 2: Ensure ticket exists in CRM

Check if the ticket already exists by listing tickets for the company and filtering client-side by `freshdesk_id`:
```bash
crm-safe tickets list --company-id <COMPANY_ID>
```

Search the results for a ticket matching the `freshdesk_ticket_id` input as `freshdesk_id`.

- **If found:** Use the existing ticket's CRM `id` as `crm_ticket_id`. Set `created_ticket` to false.
- **If NOT found:** Create the ticket:
  ```bash
  crm-safe tickets create --json '{"subject":"SUBJECT","status":STATUS,"priority":PRIORITY,"freshdesk_id":FRESHDESK_TICKET_ID,"company_id":COMPANY_ID,"requester_id":CRM_CONTACT_ID}'
  ```
  Map FreshDesk status values directly (2=Open, 3=Pending). Use the `crm_contact_id` from Step 1 as `requester_id`. Use the newly created ticket's `id` as `crm_ticket_id`. Set `created_ticket` to true.
