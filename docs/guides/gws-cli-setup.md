# gws-cli Setup Guide: Secure, Restricted Permissions

How to install and configure [gws-cli](https://github.com/googleworkspace/cli) (the Google Workspace CLI) with the minimum scopes needed for AI agent use. Every step is designed to limit blast radius if credentials are compromised.

---

## Prerequisites

Before you start, make sure you have:

- A **Google Workspace account** (not a free Gmail account)
- **Admin access** to [Google Workspace Admin Console](https://admin.google.com)
- **Access** to [Google Cloud Platform Console](https://console.cloud.google.com)
- **Node.js** (v18+) and **npm** installed
- A terminal you're comfortable in

---

## Step 1: Install gws-cli

1. Install globally via npm:
   ```bash
   npm install -g @googleworkspace/cli
   ```

2. Verify the install:
   ```bash
   gws --version
   ```
   You should see a version number. If you get "command not found," check that your npm global bin is on your PATH.

---

## Step 2: Create or Configure a GCP Project

The GCP project controls which Google APIs the CLI can talk to. Fewer enabled APIs = smaller attack surface.

1. Go to [GCP Console](https://console.cloud.google.com).

2. Create a new project (or select an existing one). Give it a descriptive name like `workspace-cli-agents`.

3. Go to **APIs & Services > Library** and enable **only** these APIs:
   - Google Drive API
   - Gmail API
   - Google Calendar API
   - Google Docs API
   - Google Sheets API
   - Google Slides API
   - People API
   - Google Tasks API
   - Google Keep API

4. **Do NOT enable other APIs.** Each enabled API is attack surface. If you don't need it, don't turn it on.

**Verify:** Go to **APIs & Services > Enabled APIs** and confirm exactly 9 APIs are listed.

---

## Step 3: Set Up OAuth Credentials

1. In GCP Console, go to **APIs & Services > Credentials**.

2. Click **Create Credentials > OAuth client ID**.
   - Application type: **Desktop application**
   - Name: something identifiable like `gws-cli-agent`

3. Under **API restrictions**, select **Restrict key** and check only the 9 APIs from Step 2.

4. Download the client configuration JSON (or note the **Client ID** and **Client Secret** — you'll need them for auth).

5. Configure the **OAuth consent screen** (APIs & Services > OAuth consent screen):
   - **Internal** (preferred): limits auth to users within your organization only. Use this if your Workspace edition supports it.
   - **External** in **Testing** mode (fallback): limits auth to explicitly added test users (max 100). Add only the accounts that need access.
   - Under **Scopes**, add only the scopes listed in Step 4 below. Do not add broad or sensitive scopes you don't need.

**Verify:** The consent screen shows your app name and the restricted scope list.

---

## Step 4: Authenticate with Restricted Scopes

This is the most important security step. The scopes you request here define what the CLI can actually do.

**Important:** The `--scopes` flag requires full Google OAuth scope URLs, not shorthand names.

### Option A: Read-Only (safest, recommended as starting point)

```bash
gws auth login --readonly
```

This grants read-only access to Drive, Gmail, Calendar, Docs, Sheets, Slides, and Tasks. No write or delete access to anything.

### Option B: Read-Only + Narrow Write Scopes (for agent workflows that need to send email, create events, or create files)

```bash
gws auth login --scopes "https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/documents.readonly,https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/presentations.readonly,https://www.googleapis.com/auth/contacts.readonly,https://www.googleapis.com/auth/tasks.readonly"
```

### After authenticating (either option):

1. A browser window opens. Sign in and approve the requested permissions.

2. Verify the auth:
   ```bash
   gws auth status
   ```
   Confirm the scopes listed match what you requested. No more.

### What Each Scope Does

| Scope | What It Allows |
|---|---|
| `drive.readonly` | Read any Drive file and metadata. No write or delete. |
| `drive.file` | Write/modify ONLY files the app itself creates. Cannot touch pre-existing files. |
| `gmail.readonly` | Read email messages and metadata. No modify or delete. |
| `gmail.send` | Send email only. Cannot read, modify, or delete. |
| `calendar.readonly` | Read calendar events. No write or delete. |
| `calendar.events` | Create and modify events. Cannot delete calendars or clear all events. |
| `documents.readonly` | Read Google Docs content. No write. |
| `spreadsheets.readonly` | Read Google Sheets content. No write. |
| `presentations.readonly` | Read Google Slides content. No write. |
| `contacts.readonly` | Read contacts. No write or delete. |
| `tasks.readonly` | Read task lists and tasks. No write or delete. |

---

## Step 5: Configure Workspace Admin OAuth Restrictions

This server-side enforcement means even if someone tampers with the local CLI config, the scopes are capped at the admin level.

**Requires Google Workspace Business Standard or higher.** If you're on a lower tier, skip to the note at the end of this section — Steps 2-4 still provide meaningful protection.

1. Go to [admin.google.com](https://admin.google.com).

2. Navigate to **Security > Access and data control > API controls > App access control**.

3. Click **Manage Third-Party App Access** (or equivalent in your console version).

4. Find the app by its GCP project name or OAuth Client ID.

5. Set the app to **Limited**.

6. Allow **only** these 11 scopes (use the full URL format):
   ```
   https://www.googleapis.com/auth/drive.readonly
   https://www.googleapis.com/auth/drive.file
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/calendar.readonly
   https://www.googleapis.com/auth/calendar.events
   https://www.googleapis.com/auth/documents.readonly
   https://www.googleapis.com/auth/spreadsheets.readonly
   https://www.googleapis.com/auth/presentations.readonly
   https://www.googleapis.com/auth/contacts.readonly
   https://www.googleapis.com/auth/tasks.readonly
   ```

7. Save the configuration.

**If you don't have Business Standard or higher:** You can't enforce scopes at the admin level, but the OAuth consent screen restrictions (Step 3) and the scopes requested at login (Step 4) still limit what the token can do. It's defense in depth — you're missing one layer, not all of them.

---

## Step 6: Secure Credential Storage

gws-cli stores credentials in `~/.config/gws/`. Lock down the permissions so other users on the machine can't read them.

1. Restrict directory and file permissions:
   ```bash
   chmod 700 ~/.config/gws/
   chmod 600 ~/.config/gws/*
   ```

2. Verify:
   ```bash
   ls -la ~/.config/gws/
   ```
   Owner should have `rwx` on the directory and `rw-` on files. No group or other access.

**Known limitation:** gws-cli stores its encryption key in the same directory as the encrypted credentials. This means anyone with filesystem access to `~/.config/gws/` can decrypt the tokens. The chmod above mitigates this for multi-user machines, but it's not a substitute for full-disk encryption or dedicated secrets management on shared infrastructure.

---

## Step 7: Verify the Setup

Run these checks to confirm everything works as expected.

1. Confirm scopes:
   ```bash
   gws auth status
   ```

2. Confirm Drive read works:
   ```bash
   gws drive files list
   ```

3. Confirm Gmail read works:
   ```bash
   gws gmail users messages list --params '{"userId":"me","maxResults":1}'
   ```

4. Confirm a blocked operation actually fails. For example, if you didn't grant `spreadsheets` (full write), try writing to an existing sheet — it should return a permissions error.

If all reads succeed and unauthorized writes fail, you're set.

---

## Scope Reference Table

| Scope | Access Level | Can Read | Can Write | Can Delete |
|---|---|---|---|---|
| `drive.readonly` | Read-only | Yes (all files) | No | No |
| `drive.file` | App-created files only | Yes (app files) | Yes (app files only) | Yes (app files only) |
| `gmail.readonly` | Read-only | Yes | No | No |
| `gmail.send` | Send-only | No | Yes (new emails) | No |
| `calendar.readonly` | Read-only | Yes | No | No |
| `calendar.events` | Events only | Yes | Yes (events) | Yes (individual events) |
| `documents.readonly` | Read-only | Yes | No | No |
| `spreadsheets.readonly` | Read-only | Yes | No | No |
| `presentations.readonly` | Read-only | Yes | No | No |
| `contacts.readonly` | Read-only | Yes | No | No |
| `tasks.readonly` | Read-only | Yes | No | No |

---

## Scopes to NEVER Grant

These scopes give broad, destructive access. Do not use them for agent workflows.

| Scope | Why It's Dangerous |
|---|---|
| `drive` | Full access to ALL files in Drive, including permanent deletion. |
| `gmail.modify` | Can delete, trash, and modify all email in the account. |
| `calendar` | Can delete entire calendars and clear all events. |
| `documents` | Full write access to every Google Doc in the account. |
| `spreadsheets` | Full write access to every Google Sheet in the account. |
| `mail.google.com` | Full Gmail access including permanent delete — the nuclear option. |

**If an agent asks for broader scopes, the answer is no.** Re-evaluate the workflow instead.

---

## Troubleshooting

### "Consent screen not configured" error
Go to GCP Console > APIs & Services > OAuth consent screen and complete the setup. You need at minimum an app name and support email.

### "API not enabled" error
Go to GCP Console > APIs & Services > Library, search for the API mentioned in the error, and enable it. Only enable APIs from the list in Step 2.

### "Wrong project" or credentials don't work
Check that your OAuth client ID was created in the same GCP project where you enabled the APIs. A common mistake is having multiple projects and configuring credentials in one but APIs in another.

### Need to change scopes
Re-run the auth command. Use `--readonly` for read-only, or `--scopes` with full URLs for custom scopes (see Step 4).
You'll re-authorize in the browser with the new set.

### Need to start completely over
Clear credentials and re-authenticate:
```bash
gws auth logout
gws auth login --readonly
```

### Token expired or "invalid_grant"
Tokens expire. Re-run `gws auth login` with the same scope list to refresh.
