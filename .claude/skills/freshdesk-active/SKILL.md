---
name: freshdesk-active
description: Active FreshDesk Tickets — retrieves all non-closed, agent-assigned FreshDesk tickets.
---

You are executing the Active FreshDesk Tickets sub-skill. Follow these steps in order. Be functional and direct.

## Purpose

Retrieve all non-closed FreshDesk tickets that are assigned to an agent.

## Inputs

None required.

## Outputs

Return the following to the calling skill:

- **tickets**: List of FreshDesk ticket objects where status is not closed and `agent_id` is not null. If no tickets match, return an empty list.

## Constants

- **FreshDesk wrapper:** `/home/timothylytle/agent-team/bin/freshdesk-safe`

## Command Rules

- Always pass JSON directly inline to `--json` and `--params` flags. Never use command substitution like `"$(cat /tmp/file.json)"` — pass the JSON string directly.

## Allowed Operations

- `freshdesk-safe tickets search` (read)

## Blocked Operations

- Any write operations (note, note-update, create, update, delete)

## Step 1: Search for non-closed tickets

```bash
freshdesk-safe tickets search --query "status:2 OR status:3 OR status:4 OR status:6 OR status:7 OR status:9"
```

## Step 2: Filter to agent-assigned tickets

From the results, filter to only tickets where `agent_id` is not null (assigned to an agent).

If no assigned tickets are found, return an empty list.
