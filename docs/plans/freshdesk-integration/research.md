# FreshDesk API Research Report

**Date:** 2026-03-27
**Researcher:** Oscar
**Source:** https://developers.freshdesk.com/api/ (v2 API)

---

## 1. Objective

Research the FreshDesk REST API to determine: authentication model (especially collaborator-level access), ticket read/write capabilities, conversation/note operations, search/filter functionality, rate limits, data model, and webhook support. The goal is to assess feasibility of building a skill that reads tickets, adds private notes, and searches/filters tickets using a collaborator-level API key.

---

## 2. Findings

### 2.1 Authentication

**Mechanism:** HTTP Basic Authentication only. No OAuth support.

- The API key is used as the username; the password is `X` (literal character).
- Format: `curl -v -u YOUR_API_KEY:X -H "Content-Type: application/json" https://domain.freshdesk.com/api/v2/tickets`
- When using an Authorization header directly, the credentials (`apikey:X`) must be Base64-encoded.

**API Key Location:** Each user finds their personal key at Profile Settings > below the password change section.

**Per-User Keys:** Yes. Each user (agent, collaborator, admin) has their own API key. The key inherits that user's role permissions.

**Permission Model:** The docs state: "your ability to access data depends on the permissions available to your Freshdesk user profile." A restricted agent attempting admin-level API calls receives `access_denied` errors.

### 2.2 Agent Types and the Collaborator Model

FreshDesk has three agent types, identified by `agent_type` (numeric) and `type` (string):

| agent_type | type             | Description        |
|------------|------------------|--------------------|
| 1          | support_agent    | Full support agent |
| 2          | field_agent      | Field service agent|
| 3          | collaborator     | Collaborator       |

**Key agent fields that control access:**

| Field                    | Type             | Description |
|--------------------------|------------------|-------------|
| `occasional`             | boolean          | `true` = occasional agent, `false` = full-time |
| `ticket_scope`           | number           | 1 = Global Access, 2 = Group Access, 3 = Restricted Access |
| `agent_type`             | number           | 1 = Support Agent, 2 = Field Agent, 3 = Collaborator |
| `type`                   | string           | `support_agent`, `field_agent`, `collaborator` |
| `role_ids`               | array of numbers | Role IDs (must match agent type, e.g., "Ticket collaborator" role for collaborator agents) |
| `group_ids`              | array of numbers | Groups the agent belongs to |
| `contribution_group_ids` | array of numbers | Groups with view-only access (when ticket_scope = 2) |

**Collaborator vs. Full Agent -- What the API docs reveal:**

- Collaborators have their own API key (confirmed: all agent types do).
- Collaborators are assigned the "Ticket collaborator" role (not "Agent" or "Admin" roles).
- The `ticket_scope` field applies to collaborators the same way: 1 = Global, 2 = Group, 3 = Restricted.
- Role IDs must correspond to agent type: "Role IDs should be corresponding to the type of agents. For example: Ticket collaborator for collaborator agent, Agent or admin for support agent."

**Confidence: MEDIUM on collaborator-specific API restrictions.** The API documentation does not explicitly enumerate what API endpoints collaborators cannot use. The permission model is role-based and inherited from the Freshdesk admin UI. What a collaborator can do via API mirrors what they can do in the UI.

**What this likely means in practice (requires verification against your actual FreshDesk instance):**
- A collaborator with Global ticket_scope (1) should be able to view all tickets via API.
- A collaborator with Group ticket_scope (2) can view tickets in their assigned groups.
- A collaborator with Restricted scope (3) can only see tickets assigned to them.
- Note/reply creation permissions depend on the collaborator's role configuration in admin.

### 2.3 Tickets API

#### List All Tickets
```
GET /api/v2/tickets
```

**Filters (query params):**

| Parameter        | Description |
|------------------|-------------|
| `filter`         | Predefined: `new_and_my_open`, `watching`, `spam`, `deleted` |
| `requester_id`   | Filter by requester ID |
| `email`          | Filter by requester email (URL-encoded) |
| `unique_external_id` | Filter by requester external ID |
| `company_id`     | Filter by company |
| `updated_since`  | ISO 8601 datetime -- tickets modified after this date |
| `order_by`       | `created_at`, `due_by`, `updated_at`, `status` |
| `order_type`     | `asc` or `desc` (default: `desc`) |
| `page`           | Page number (starts at 1) |
| `per_page`       | Results per page (default: 30, max: 100) |

**Embeds (query param `include`):**

| Include       | Description | Extra cost |
|---------------|-------------|------------|
| `stats`       | Adds `closed_at`, `resolved_at`, `first_responded_at` | +2 credits |
| `requester`   | Adds requester email, id, mobile, name, phone | +2 credits |
| `description` | Adds `description` and `description_text` | +2 credits |

**Important notes:**
- Default returns only tickets created in the past 30 days. Use `updated_since` for older tickets.
- Maximum 300 pages (30,000 tickets) returned.
- For accounts created after 2018-11-30, description requires `include=description`.

#### View a Ticket
```
GET /api/v2/tickets/[id]
```

**Embeds:**

| Include          | Description | Cost |
|------------------|-------------|------|
| `conversations`  | Up to 10 conversations | +2 credits |
| `requester`      | Requester details | +2 credits |
| `company`        | Company id and name | +2 credits |
| `stats`          | Resolution timestamps | +2 credits |

#### Filter/Search Tickets
```
GET /api/v2/search/tickets?query="[query]"
```

**Query syntax:** `"(field:value OR field:'string') AND field:boolean"`

**Supported search fields:**

| Field        | Type    | Description |
|--------------|---------|-------------|
| `agent_id`   | integer | Assigned agent |
| `group_id`   | integer | Assigned group |
| `priority`   | integer | 1-4 |
| `status`     | integer | 2-5 |
| `tag`        | string  | Tag name |
| `type`       | string  | Ticket type/category |
| `due_by`     | date    | Due date (YYYY-MM-DD) |
| `fr_due_by`  | date    | First response due date |
| `created_at` | date    | Creation date |
| `updated_at` | date    | Last update date |
| `closed_at`  | date    | Close date |
| Custom fields | various | Text, number, checkbox, dropdown, date |

**Operators:** `:>` (gte), `:<` (lte), `AND`, `OR`, `()` grouping, `null` keyword.

**Constraints:**
- Query must be URL-encoded.
- Max 512 characters.
- Max 10 pages of results (300 results total at 30/page).
- Archived tickets excluded.
- Index updates take a few minutes (not real-time).

**Example queries:**
- `"priority:3 AND status:2"` -- High priority, open tickets
- `"created_at:>'2026-03-01' AND status:2"` -- Open tickets since March 1
- `"agent_id:1234 AND status:<4"` -- Agent's non-resolved tickets
- `"tag:'billing' AND priority:>2"` -- High+ priority billing tickets

#### Update a Ticket
```
PUT /api/v2/tickets/[id]
```

**Updatable fields:** `name`, `email`, `subject`, `type`, `status`, `priority`, `description`, `responder_id`, `group_id`, `company_id`, `product_id`, `due_by`, `fr_due_by`, `cc_emails`, `tags`, `custom_fields`.

Cannot update deleted/spam tickets or description/subject on outbound emails.

### 2.4 Conversations API (Replies and Notes)

#### Conversation Object

| Field               | Type             | Description |
|---------------------|------------------|-------------|
| `id`                | number           | Conversation ID |
| `body`              | string           | HTML content |
| `body_text`         | string           | Plain text content |
| `structured_body`   | object           | Structured body with `body_contents` array |
| `incoming`          | boolean          | True if created from outside (not web portal) |
| `private`           | boolean          | True if only visible to agents |
| `source`            | number           | See source values below |
| `ticket_id`         | number           | Parent ticket ID |
| `user_id`           | number           | Creator's user ID |
| `support_email`     | string           | Email address reply was sent from (null for notes) |
| `to_emails`         | array of strings | Recipient emails |
| `cc_emails`         | array of strings | CC emails |
| `bcc_emails`        | array of strings | BCC emails |
| `from_email`        | string           | Sender email |
| `attachments`       | array            | Attached files |
| `created_at`        | datetime         | Creation timestamp |
| `updated_at`        | datetime         | Last update timestamp |
| `last_edited_at`    | datetime         | Last edit timestamp |
| `last_edited_user_id` | number         | ID of last editor |

**Conversation source values:**

| Source | Value |
|--------|-------|
| Reply  | 0     |
| Note   | 2     |
| Created from tweets | 5 |
| Created from survey feedback | 6 |
| Created from Facebook post | 7 |
| Created from Forwarded Email | 8 |
| Created from Phone | 9 |
| E-Commerce | 11 |

#### List All Conversations of a Ticket
```
GET /api/v2/tickets/[id]/conversations
```

Returns all conversations (replies + notes) for a ticket. Paginated.

**Example response:**
```json
[
  {
    "body_text": "Please reply as soon as possible.",
    "body": "<div>Please reply as soon as possible.</div>",
    "id": 3,
    "incoming": false,
    "private": true,
    "user_id": 1,
    "support_email": null,
    "source": 2,
    "ticket_id": 20,
    "created_at": "2015-08-24T11:59:05Z",
    "updated_at": "2015-08-24T11:59:05Z",
    "from_email": "agent2@yourcompany.com",
    "to_emails": ["agent1@yourcompany.com"],
    "cc_emails": ["example@ccemail.com"],
    "bcc_emails": ["example@bccemail.com"],
    "attachments": [],
    "last_edited_at": "2015-08-24T11:59:59Z",
    "last_edited_user_id": 2
  }
]
```

#### Create a Note (Private or Public)
```
POST /api/v2/tickets/[ticket_id]/notes
```

**THIS IS THE KEY ENDPOINT FOR ADDING PRIVATE NOTES.**

**Request body parameters:**

| Parameter       | Type             | Required | Description |
|-----------------|------------------|----------|-------------|
| `body`          | string           | Yes*     | HTML content of the note |
| `structured_body` | object         | Yes*     | Alternative structured content |
| `private`       | boolean          | No       | **Default: true**. Set to false for public note |
| `incoming`      | boolean          | No       | Default: false. Set true if appears from outside |
| `notify_emails` | array of strings | No       | Agents/users to notify |
| `user_id`       | number           | No       | ID of user creating the note |
| `attachments`   | array            | No       | Files (total ticket attachments max 20MB) |

*One of `body` or `structured_body` is mandatory.

**Critical detail: Notes are private by default.** You only need to set `private: false` to make a note public.

**Example -- add a private note:**
```bash
curl -v -u YOUR_API_KEY:X \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"body":"<p>Internal: Customer called about this issue.</p>"}' \
  'https://domain.freshdesk.com/api/v2/tickets/3/notes'
```

**Example -- add a public note:**
```bash
curl -v -u YOUR_API_KEY:X \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"body":"Hi tom, Still Angry","private":false,"notify_emails":["tom@yourcompany.com"]}' \
  'https://domain.freshdesk.com/api/v2/tickets/3/notes'
```

#### Create a Reply
```
POST /api/v2/tickets/[id]/reply
```

Parameters: `body` (required), `attachments`, `from_email`, `user_id`, `cc_emails`, `bcc_emails`.

#### Other Conversation Endpoints
```
PUT  /api/v2/conversations/[id]     -- Update a conversation
DELETE /api/v2/conversations/[id]   -- Delete a conversation
```

### 2.5 Contacts and Companies

#### Contacts API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/contacts` | GET | List all contacts |
| `/api/v2/contacts/[id]` | GET | View a contact |
| `/api/v2/contacts` | POST | Create a contact |
| `/api/v2/contacts/[id]` | PUT | Update a contact |
| `/api/v2/contacts/autocomplete?term=[keyword]` | GET | Search contacts |
| `/api/v2/search/contacts?query=[query]` | GET | Filter contacts (BETA) |
| `/api/v2/contacts/[id]` | DELETE | Soft delete |
| `/api/v2/contacts/[id]/hard_delete` | DELETE | Hard delete |
| `/api/v2/contacts/merge` | POST | Merge contacts |

**Key contact fields:** name, email, phone, mobile, company_id, custom_fields, address, description, tags.

#### Companies API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/companies` | GET | List all companies |
| `/api/v2/companies/[id]` | GET | View a company |
| `/api/v2/companies` | POST | Create |
| `/api/v2/companies/[id]` | PUT | Update |
| `/api/v2/companies/[id]` | DELETE | Delete |
| `/api/v2/companies/autocomplete?name=[keyword]` | GET | Search |
| `/api/v2/search/companies?query=[query]` | GET | Filter (BETA) |

**Key company fields:** name, description, domains, custom_fields, industry, website.

### 2.6 Rate Limits

**Current plans (per hour):**

| Plan     | Calls/Hour |
|----------|------------|
| Blossom  | 3,000      |
| Garden   | 3,000      |
| Estate   | 5,000      |
| Forest   | 5,000      |

**Legacy plans (per minute):**

| Plan     | Calls/Minute |
|----------|-------------|
| Blossom  | 100         |
| Garden   | 200         |
| Estate   | 400         |
| Forest   | 700         |

**Rate limit is account-wide** -- not per agent, not per IP. All API users share the same pool.

**Response headers:**

| Header | Description |
|--------|-------------|
| `X-RateLimit-Total` | Total allowed calls per window |
| `X-RateLimit-Remaining` | Remaining calls in current window |
| `X-RateLimit-Used-CurrentRequest` | Calls consumed by this request |
| `Retry-After` | Seconds to wait (only on 429 response) |

When exceeded: HTTP 429 response with `Retry-After` header. Invalid requests also count toward the limit.

### 2.7 Ticket Data Model

**Status values:**

| Status   | Value |
|----------|-------|
| Open     | 2     |
| Pending  | 3     |
| Resolved | 4     |
| Closed   | 5     |

**Priority values:**

| Priority | Value |
|----------|-------|
| Low      | 1     |
| Medium   | 2     |
| High     | 3     |
| Urgent   | 4     |

**Source values:**

| Source           | Value |
|------------------|-------|
| Email            | 1     |
| Portal           | 2     |
| Phone            | 3     |
| Chat             | 7     |
| Feedback Widget  | 9     |
| Outbound Email   | 10    |

**Full ticket object:**
```json
{
  "id": 1,
  "subject": "Please help",
  "description": "<div>HTML content</div>",
  "description_text": "Plain text content",
  "status": 2,
  "priority": 1,
  "source": 2,
  "type": "Question",
  "requester_id": 5,
  "responder_id": 1,
  "group_id": 2,
  "company_id": 1,
  "email": "user@example.com",
  "name": "Requester Name",
  "phone": null,
  "cc_emails": ["user@cc.com"],
  "fwd_emails": [],
  "reply_cc_emails": ["user@cc.com"],
  "to_emails": ["support@domain.freshdesk.com"],
  "product_id": null,
  "email_config_id": null,
  "due_by": "2026-04-01T12:00:00Z",
  "fr_due_by": "2026-03-28T12:00:00Z",
  "is_escalated": false,
  "fr_escalated": false,
  "spam": false,
  "deleted": false,
  "tags": ["billing", "urgent"],
  "custom_fields": {
    "cf_category": "Billing",
    "cf_subcategory": "Refund",
    "cf_account_number": "12345"
  },
  "attachments": [],
  "created_at": "2026-03-27T10:00:00Z",
  "updated_at": "2026-03-27T14:30:00Z",
  "association_type": null,
  "associated_tickets_list": null
}
```

**Custom fields** are in a flat dictionary under `custom_fields`. Keys are prefixed with `cf_` followed by the field name. Types include string, integer, boolean, date.

**Fields useful for categorization/summarization:** `type`, `status`, `priority`, `tags`, `custom_fields`, `group_id`, `subject`, `description_text`.

### 2.8 Webhook / Event Support

**Webhooks are NOT configured via the API.** They are set up through the FreshDesk admin UI.

**Configuration path:** Admin > Workflows > Automations > Ticket Creation or Ticket Updates tab > New Rule > Action: "Trigger Webhook"

**Triggerable events:**
- Ticket creation
- Ticket updates (status, field, assignment changes)
- Customer replies
- Satisfaction feedback

**Payload format:** JSON, XML, or XML-encoded. Supports dynamic placeholders: `{{ticket.id}}`, `{{ticket.requester.email}}`, `{{ticket.custom_fields.fieldname}}`, `{{Triggered event}}`.

**Authentication:** Webhooks can include Basic Auth credentials and custom headers.

**Limitations:**
- 1,000 webhook requests per hour
- Failed webhooks retry every 30 minutes (48 total attempts)
- Success: 2xx status codes. Failure: anything else.
- "Trigger API" (synchronous, uses response) requires Pro/Estate plan or higher.
- GET calls via webhook are async and cannot use responses for subsequent automations.

### 2.9 Pagination

- All list endpoints are paginated.
- `page` parameter starts at 1.
- `per_page` defaults to 30, max 100.
- The `link` response header contains the next page URL if more pages exist.
- Max 300 pages (30,000 objects) for list endpoints.
- Search endpoint (`/search/tickets`) max 10 pages (300 results).

### 2.10 Other Relevant Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/ticket_fields` | GET | List all ticket fields (including custom fields) |
| `/api/v2/agents/me` | GET | View currently authenticated agent |
| `/api/v2/roles` | GET | List all roles |
| `/api/v2/roles/[id]` | GET | View a role |
| `/api/v2/groups` | GET | List all groups |

---

## 3. Recommendations

### 3.1 Feasibility Assessment: Collaborator API Key

**Verdict: FEASIBLE with caveats.**

A collaborator-level API key will work for the target use cases (reading tickets, adding private notes, searching/filtering). The specific capabilities depend on:

1. **ticket_scope setting** on the collaborator account. For full visibility, the collaborator needs `ticket_scope: 1` (Global Access).
2. **Role configuration** in FreshDesk admin. The "Ticket collaborator" role must include permissions for viewing tickets and adding notes.

**Recommended first step:** Hit `GET /api/v2/agents/me` with the collaborator's API key to confirm the agent's `type`, `ticket_scope`, `role_ids`, and `group_ids`. This will immediately reveal what access level is available.

### 3.2 Implementation Priorities

For a skill that reads tickets, adds private notes, and searches/filters:

1. **Search/filter tickets:** `GET /api/v2/search/tickets?query="..."` -- most flexible, supports date ranges, status, priority, custom fields. Limited to 300 results.
2. **List tickets:** `GET /api/v2/tickets?updated_since=...&order_by=...` -- for bulk listing with simpler filters. Limited to 30,000 results.
3. **View ticket detail:** `GET /api/v2/tickets/[id]?include=conversations,requester,stats` -- single ticket with embedded data. Costs 7 credits (1 base + 2 per include).
4. **List conversations:** `GET /api/v2/tickets/[id]/conversations` -- when more than 10 conversations exist.
5. **Add private note:** `POST /api/v2/tickets/[id]/notes` with `{"body": "...", "private": true}` -- private is the default, so the `private` field can be omitted.
6. **Look up requester:** `GET /api/v2/contacts/[id]` or search via `/api/v2/contacts/autocomplete?term=...`.

### 3.3 Rate Limit Strategy

At 3,000-5,000 calls/hour (depending on plan), and with the account-wide limit:
- Viewing a ticket with all includes costs ~7 credits.
- Simple list/search calls cost 1 credit each.
- Budget approximately 400-700 "rich" ticket views per hour, or 3,000-5,000 simple list/search calls.
- Implement `Retry-After` header handling for 429 responses.
- Cache ticket data locally when possible.

### 3.4 Skill Design Considerations

- Use `/api/v2/ticket_fields` on initialization to discover custom field names and types for the specific FreshDesk instance.
- The search API indexes are not real-time (few-minute delay). For just-created tickets, use the list endpoint with `updated_since`.
- Notes default to private. For safety, always explicitly pass `"private": true` when adding internal notes to prevent accidental public exposure.
- The `description` field is not included in list responses by default (for accounts after 2018-11-30). Must use `include=description`.

---

## 4. Risks / Caveats

1. **Collaborator permissions are not fully documented in the API reference.** The exact capabilities depend on role configuration in the FreshDesk admin UI. The API docs only state that "your ability to access data depends on the permissions available to your Freshdesk user profile." There is no explicit list of which endpoints collaborators can/cannot call. **Mitigation:** Test with the actual API key using `GET /api/v2/agents/me` and then attempt each required operation.

2. **Rate limits are account-wide.** If other integrations or users also use the API, they share the same pool. There is no way to reserve capacity for a specific integration.

3. **Search results are capped at 300.** The search endpoint returns max 10 pages x 30 results. For broader data pulls, use the list endpoint with `updated_since`.

4. **Search indexing delay.** The filter/search endpoint does not reflect changes in real-time. Recently created or updated tickets may take minutes to appear in search results.

5. **Webhook configuration is admin-only via UI.** There is no API to programmatically create webhook automations. Someone with admin access must configure them manually.

6. **No explicit "collaborator cannot do X" documentation exists.** The API docs reference collaborators only in the context of agent creation/conversion. All permission enforcement is through the role system, which is configured in the admin UI, not documented per-endpoint in the API reference.

---

## 5. Open Questions (Require Verification Against Live Instance)

- [ ] What specific role(s) are assigned to the collaborator account that will be used?
- [ ] What is the `ticket_scope` of the collaborator account (1=Global, 2=Group, 3=Restricted)?
- [ ] Can the collaborator role add notes via API? (Test: `POST /api/v2/tickets/[id]/notes`)
- [ ] Can the collaborator role update ticket fields via API? (Test: `PUT /api/v2/tickets/[id]`)
- [ ] Can the collaborator role use the search endpoint? (Test: `GET /api/v2/search/tickets?query="status:2"`)
- [ ] What FreshDesk plan is active? (Determines rate limit tier)
- [ ] Are there existing integrations consuming API credits from the shared pool?
- [ ] What custom fields exist on tickets? (Check: `GET /api/v2/ticket_fields`)
