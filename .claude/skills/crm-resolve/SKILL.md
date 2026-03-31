---
name: crm-resolve
description: CRM Entity Resolution — resolves an email address to CRM company and contact records.
---

You are executing the CRM Resolve sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Given an email address, resolve the full CRM entity chain (contact and/or company).

## Inputs

- **email** (required): The email address to resolve
- **ticket_id** (optional): A FreshDesk ticket ID for context

## Outputs

Return the following values to the calling skill:

- **contact_id**: CRM contact ID (if contact found)
- **company_id**: CRM company ID (if company or contact found)
- **company_name**: CRM company name (if company or contact found)
- **matched_by**: One of `"contact"`, `"domain"`, or `"not_found"`

## Constants

- **CRM wrapper:** `/home/timothylytle/agent-team/bin/crm-safe`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.
- For multiline Python scripts, use heredoc syntax (`python3 << 'PYEOF' ... PYEOF`) instead of `python3 -c "..."` to avoid triggering security prompts from `#` characters in inline code.

## Allowed Operations

- `crm-safe contacts list` (read)
- `crm-safe companies list` (read)

## Blocked Operations

- Any write operations (create, update, delete)
- Direct database access

## Step 1: Search CRM contacts by email

Fetch all CRM contacts:
```bash
crm-safe contacts list
```

Search the results for a contact whose `email` field matches the input email (case-insensitive).

- **If found:** Extract the contact's `id`, `company_id`, and look up the company name from the contact's company. Return:
  - `contact_id`: the contact's `id`
  - `company_id`: the contact's `company_id`
  - `company_name`: the associated company name
  - `matched_by`: `"contact"`
  - **Stop here.**

## Step 2: Extract domain and search CRM companies

If no contact was found, extract the domain from the email (the part after `@`).

Fetch all CRM companies:
```bash
crm-safe companies list
```

Each company has a `domains` field (JSON array of strings like `["acme.com"]`). Check if the extracted domain appears in any company's `domains` array.

- **If a company matches:** Return:
  - `company_id`: the company's `id`
  - `company_name`: the company's `name`
  - `matched_by`: `"domain"`
  - **Stop here.**

## Step 3: No match found

If no contact or company matched, return:
- `matched_by`: `"not_found"`
