# FreshDesk API Setup Guide: Secure, Least-Privilege Access

How to create a dedicated FreshDesk collaborator account for AI agent use and configure API access with the minimum permissions needed. Every step is designed to limit blast radius if credentials are compromised.

---

## Prerequisites

Before you start, make sure you have:

- A **FreshDesk account** with **admin access** (needed to create agents)
- **jq** installed (for reading config files safely)
- **curl** installed
- A terminal you're comfortable in

---

## Step 1: Create a Collaborator Account

A collaborator is the most restricted agent type in FreshDesk. Use it instead of a full support agent.

FreshDesk has three agent types:

| Type | `agent_type` | What It Can Do |
|---|---|---|
| Support Agent | 1 | Full ticket management, assignments, automations |
| Field Agent | 2 | Field service operations |
| Collaborator | 3 | Limited ticket access — can view and add notes, but not run the help desk |

**Create the account:**

1. Go to **Admin > Agents > New Agent**.

2. Set the following:
   - **Agent Type:** Collaborator
   - **Name:** Something descriptive like `AI Agent Bot` or `Claude Integration`
   - **Email:** A dedicated address (not your personal email). If it shares your domain, great — but don't reuse an account that does other things.

3. Set **Ticket Scope** — this controls which tickets the collaborator can see:

   | `ticket_scope` | Value | What It Means | Security Tradeoff |
   |---|---|---|---|
   | Global | 1 | Can see every ticket in the account | Maximum visibility. Use only if the agent genuinely needs cross-team context. |
   | Group | 2 | Can see tickets in assigned groups only | **Recommended starting point.** Limits exposure to relevant tickets. |
   | Restricted | 3 | Can see only tickets explicitly assigned to or involving this agent | Tightest scope, but may be too narrow for workflows that need to search or triage. |

   **Start with Group or Restricted.** You can widen later if the agent needs it. You can't un-see data.

4. Save the agent.

---

## Step 2: Get the API Key

Every FreshDesk agent has their own API key. Permissions are inherited from their role — the key can't do anything the account can't do.

**Option A: Log in as the collaborator**

1. Log in to FreshDesk as the collaborator account.
2. Click the profile icon (top right) > **Profile Settings**.
3. The API key is on the right side panel.

**Option B: Admin retrieves the key**

1. Go to **Admin > Agents**.
2. Click the collaborator account.
3. The API key is shown in the agent details.

Copy the key. You'll need it in the next step.

---

## Step 3: Store the API Key Securely

**Never store API keys in the repo, in `.env` files that could be committed, or in shell commands that land in your history.**

1. Create the config directory:
   ```bash
   mkdir -p ~/.config/freshdesk
   ```

2. Create the config file:
   ```bash
   cat > ~/.config/freshdesk/config.json << 'EOF'
   {
     "domain": "yourdomain",
     "api_key": "your-api-key-here"
   }
   EOF
   ```
   Replace `yourdomain` with your FreshDesk subdomain (the part before `.freshdesk.com`). Replace the API key with the real one.

3. Lock down permissions:
   ```bash
   chmod 700 ~/.config/freshdesk/
   chmod 600 ~/.config/freshdesk/*
   ```

4. Verify:
   ```bash
   ls -la ~/.config/freshdesk/
   ```
   Owner should have `rwx` on the directory and `rw-` on files. No group or other access.

**Known limitation:** Anyone with filesystem access to `~/.config/freshdesk/` can read the API key in plain text. The chmod above mitigates this for multi-user machines, but it's not a substitute for full-disk encryption or dedicated secrets management on shared infrastructure.

---

## Step 4: Verify the Setup

FreshDesk uses HTTP Basic Auth: your API key is the username, `X` (literal) is the password.

**First, set up a helper so your API key never appears in shell history:**

```bash
# Load credentials into shell variables (run this once per session)
FD_KEY=$(jq -r .api_key ~/.config/freshdesk/config.json)
FD_DOMAIN=$(jq -r .domain ~/.config/freshdesk/config.json)
FD_BASE="https://${FD_DOMAIN}.freshdesk.com/api/v2"
```

Now run these checks:

### 1. Verify your identity

```bash
curl -s -u "${FD_KEY}:X" "${FD_BASE}/agents/me" | jq '{id, type, ticket_scope, role_ids}'
```

Confirm:
- `type` is `3` (collaborator)
- `ticket_scope` matches what you set in Step 1
- `role_ids` looks reasonable (should contain the "Ticket collaborator" role)

### 2. List tickets

```bash
curl -s -u "${FD_KEY}:X" "${FD_BASE}/tickets" | jq '.[0:2]'
```

Should return a JSON array of tickets (limited to the first 2 for sanity).

### 3. View a ticket with conversations

```bash
curl -s -u "${FD_KEY}:X" "${FD_BASE}/tickets/1?include=conversations" | jq '{id, subject, status}'
```

Replace `1` with an actual ticket ID from the previous step.

### 4. Search tickets

```bash
curl -s -u "${FD_KEY}:X" "${FD_BASE}/search/tickets?query=\"status:2\"" | jq '.total'
```

Should return a count of open tickets (status 2 = Open).

### 5. Add a private note (writes data)

```bash
curl -s -u "${FD_KEY}:X" -X POST \
  -H "Content-Type: application/json" \
  -d '{"body": "Test note from API setup verification. Safe to delete.", "private": true}' \
  "${FD_BASE}/tickets/TICKET_ID/notes" | jq '{id, private, body_text}'
```

**This actually writes to the ticket.** Replace `TICKET_ID` with a test ticket you don't mind annotating. The note is private (not visible to the customer), but it's real. Delete it manually after verifying.

If all reads succeed and the note posts correctly, your setup is working.

---

## Step 5: Verify Collaborator Permissions

FreshDesk does not document exactly which API operations collaborators can and cannot perform. You need to test empirically.

Run through this checklist and record results:

| Operation | Endpoint | Expected | Actual |
|---|---|---|---|
| List tickets | `GET /tickets` | Works | |
| Search tickets | `GET /search/tickets` | Works | |
| View ticket | `GET /tickets/[id]` | Works | |
| View conversations | `GET /tickets/[id]?include=conversations` | Works | |
| Add private note | `POST /tickets/[id]/notes` | Works | |
| Update ticket fields | `PUT /tickets/[id]` | Uncertain | |
| Delete ticket | `DELETE /tickets/[id]` | Should fail | |
| Create ticket | `POST /tickets` | Uncertain | |
| List agents | `GET /agents` | Uncertain | |
| Access admin endpoints | `GET /settings/helpdesk` | Should fail | |

**If a needed operation fails (403 Forbidden):**

1. Check if the collaborator's role can be adjusted in **Admin > Roles** to allow that specific operation.
2. If collaborator limitations are hard-coded by FreshDesk and can't be adjusted, upgrade to a **full Support Agent** (type 1) with a **custom restricted role** instead. Create the custom role with only the specific permissions the agent needs.
3. Re-run the verification steps after any changes.

---

## Permission Reference Table

Based on FreshDesk documentation and typical collaborator behavior:

### Collaborators CAN (expected)

| Capability | Notes |
|---|---|
| View tickets in their scope | Controlled by `ticket_scope` setting |
| View ticket conversations | Including private notes |
| Add private notes | Primary write operation for AI agents |
| Be mentioned/CC'd on tickets | |

### Collaborators CANNOT (expected)

| Capability | Notes |
|---|---|
| Delete tickets | Admin-level operation |
| Access admin settings | No admin API endpoints |
| Manage other agents | No agent management |
| Configure automations/triggers | Admin-level operation |
| Manage canned responses | Full agent feature |

### Uncertain (must test)

| Capability | Why It Matters |
|---|---|
| Update ticket fields (status, priority, etc.) | Needed if the agent should triage or categorize |
| Create new tickets | Needed if the agent should file tickets from other channels |
| View contacts/companies | Needed for customer context |
| Access knowledge base | Needed for reference lookups |

**Test these against your instance.** Results may vary by FreshDesk plan and account configuration.

---

## Permissions to NEVER Grant

These settings give broad, dangerous access. Do not use them for agent workflows.

| Setting | Why It's Dangerous |
|---|---|
| Admin account for API access | Full access to everything: billing, settings, agent management, data deletion. |
| Full agent with Administrator role | Same as above, but looks less obvious. |
| "Account Administrator" privilege on the collaborator | Elevates the collaborator beyond its intended restrictions. |
| Global `ticket_scope` by default | Exposes every ticket in the account. Start narrow, widen only with justification. |
| Shared API key across multiple integrations | Makes revocation impossible without breaking everything. One integration, one key. |

**If an agent asks for admin access, the answer is no.** Re-evaluate the workflow instead.

---

## Rate Limit Awareness

FreshDesk rate limits are **account-wide, not per-key**. Every API call from every integration counts toward the same pool.

| Plan | Requests/Hour |
|---|---|
| Blossom / Garden | 3,000 |
| Estate / Forest | 5,000 |

**What this means in practice:**

- If you have other integrations hitting FreshDesk (Zapier, custom scripts, other bots), they all share this budget.
- A runaway polling loop can lock out your entire account for the remainder of the hour.

**How to stay safe:**

1. Check the `X-RateLimit-Remaining` header in every API response:
   ```bash
   curl -s -D - -u "${FD_KEY}:X" "${FD_BASE}/tickets" -o /dev/null 2>&1 | grep -i ratelimit
   ```

2. Use conservative polling intervals. If you're checking for new tickets, every 2-5 minutes is plenty. Don't poll every 10 seconds.

3. Use search with filters instead of listing all tickets and filtering client-side. Fewer API calls, same result.

4. If you get a `429 Too Many Requests` response, back off. Check the `Retry-After` header for how long to wait.

---

## Troubleshooting

### 401 Unauthorized
The API key is wrong, not activated, or the account is disabled. Double-check:
- The key in `~/.config/freshdesk/config.json` matches what FreshDesk shows
- The collaborator account is active (not deactivated or suspended)
- You're using the key as the username and `X` as the password (not the other way around)

### 403 Forbidden
The collaborator account doesn't have permission for that operation. This is the expected response when collaborator restrictions are working. Check:
- Whether the operation is something collaborators can do at all (see the permission reference table above)
- Whether `ticket_scope` is preventing access to that specific ticket
- Whether the collaborator's role needs adjustment in Admin > Roles

### 429 Too Many Requests
You've hit the account-wide rate limit. Check the `Retry-After` header and wait. If this happens during normal usage, audit all integrations hitting the FreshDesk API — something else may be burning through the quota.

### SSL/TLS Errors
Make sure you're using `https://`, not `http://`. FreshDesk requires TLS. If you're behind a corporate proxy, you may need to configure curl's CA bundle:
```bash
curl --cacert /path/to/your/ca-bundle.crt -u "${FD_KEY}:X" "${FD_BASE}/agents/me"
```

### "Account suspended" or Domain Not Found
- Verify the domain in your config file matches your FreshDesk subdomain exactly (no `.freshdesk.com` suffix, just the subdomain)
- Check that the FreshDesk account is active and not in a suspended state due to billing

### Empty Response or HTML Instead of JSON
You're probably hitting the wrong URL. Common mistakes:
- Missing `/api/v2/` in the path
- Typo in the domain name
- Using `http://` instead of `https://`
