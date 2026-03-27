# Handoff Document — Agent Team Project

**Date:** 2026-03-26
**Session:** Project initialization + GWS-CLI security lockdown

---

## 1. Goal / Problem Statement

Building a personal AI assistant team for Timothy. The orchestrator is "Michael" who delegates all work to specialized agents with distinct personalities. The repo (`agent-team`) houses agent definitions, skills, and workflows to assist with daily briefing, note curation, calendar management, and task management.

The immediate initiative is integrating Google Workspace via `gws-cli` with strict security guardrails to prevent accidental data deletion or unauthorized modifications.

---

## 2. Current Status

### Done
- Project initialized with `CLAUDE.md` (Michael orchestrator definition)
- 6 agents created and onboarded:
  - **Oscar** — Senior Researcher
  - **Toby** — HR / Agent Creator
  - **Dwight** — Organization & Enforcement (security/compliance)
  - **Jim** — Communication Specialist
  - **Pam** — Executive Assistant (calendar, tasks, notes)
  - **Ryan** — Implementation Specialist
- Full security research on gws-cli completed (Oscar)
- Full security requirements document produced (Dwight) — covers 3-layer defense, approved/blocked operations, wrapper script spec, escalation policy
- GWS-CLI setup guide written and corrected (`docs/gws-cli-setup-guide.md`)
- Guide corrected for proper syntax: `gws auth logout` (not `revoke`), full scope URLs required for `--scopes` flag

### In Progress
- **GWS-CLI lockdown Steps 1-3:**
  - Step 1: Re-auth with restricted scopes — **DONE (Option B: read-only + narrow write scopes)**
  - Step 2: Workspace Admin OAuth app restrictions — **NOT AVAILABLE (Workspace edition doesn't support granular per-app OAuth controls)**
  - Step 3: Disable unnecessary GCP APIs — **Timothy handling separately**

### Remaining
- Timothy needs to choose and execute auth option:
  - **Option A:** `gws auth login --readonly` (read-only everything, safest)
  - **Option B:** `gws auth login --scopes "https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/documents.readonly,https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/presentations.readonly,https://www.googleapis.com/auth/contacts.readonly"` (read-only + narrow write)
- Complete Workspace Admin + GCP Console lockdown (Steps 2-3)
- Build `gws-safe` wrapper script (Layer 2 defense) — Ryan's job
- Build gws-cli skill for agent use — Ryan's job
- Build first functional skills (daily briefing, calendar, tasks, notes)
- Nothing has been committed to git yet

### Progress Estimate
~30% — Team assembled, security requirements defined, but core integration not yet operational.

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Michael orchestrator definition + team roster + hiring process |
| `.claude/agents/oscar.md` | Senior Researcher agent |
| `.claude/agents/toby.md` | HR / Agent Creator agent |
| `.claude/agents/dwight.md` | Organization & Enforcement agent (security checklists, red flags, review procedures) |
| `.claude/agents/jim.md` | Communication Specialist agent (8 comm principles, no-AI-voice directive) |
| `.claude/agents/pam.md` | Executive Assistant agent (calendar, tasks, notes, escalation tiers, daily rhythm) |
| `.claude/agents/ryan.md` | Implementation Specialist agent (6-step impl process, quality standards) |
| `docs/gws-cli-setup-guide.md` | Complete start-to-finish guide for setting up gws-cli with secure permissions |

---

## 4. How to Run

- **gws-cli** is installed globally at `/usr/bin/gws` (npm package `@googleworkspace/cli` v0.22.3)
- Current auth: `gws auth status` to check active scopes
- Auth logout: `gws auth logout`
- Re-auth readonly: `gws auth login --readonly`
- Test read access: `gws drive files list`
- No tests, lint, or build steps exist yet — this is still project scaffolding phase
- Environment: Linux WSL2, bash shell

---

## 5. Recent Decisions

- **Agent personalities modeled after The Office characters** — each agent has a distinct personality that affects how they interact (Michael orchestrates, Oscar researches, Toby does HR, Dwight enforces, Jim communicates, Pam organizes, Ryan builds)
- **Michael does not like Toby** — this is encoded in CLAUDE.md personality. Michael still delegates to Toby but complains about it.
- **Michael never does work directly** — always delegates to the appropriate agent
- **3-layer defense for gws-cli** — (1) OAuth scope restrictions server-side, (2) `gws-safe` wrapper script blocking destructive commands, (3) agent-level instructions. Layers are independent so failure of one doesn't compromise the others.
- **"Default deny" for gws-cli operations** — only explicitly approved operations are allowed. Everything else is blocked.
- **Permanent deletion is always a human action** — no agent may ever permanently delete data, even with human approval through the wrapper. Human must use `/usr/bin/gws` directly.
- **`drive.file` scope over `drive` scope** — limits write access to only files the app creates, can't touch existing Drive files
- **Hiring process is formalized** — Oscar researches role requirements, Michael reviews, Toby creates the agent definition

---

## 6. Open Issues / Blockers

- **BLOCKER: gws-cli auth not yet locked down.** Current token still has full write/delete access (13 scopes including `drive` full access). Timothy must complete Steps 1-3 before any agent can use gws-cli.
- **Decision needed:** Option A (read-only) vs Option B (read-only + narrow write) for initial auth. Recommendation was Option A to start.
- **Google Keep API has no official public API** — may constrain what Pam can do with notes. Needs investigation when we get to note management skills.
- **Workspace Admin OAuth app controls require Business Standard or higher** — if Timothy's edition doesn't support this, Steps 1 and 3 still provide protection but we lose the server-side scope enforcement layer.
- **Credential storage weakness** — gws-cli stores encryption key in same directory as credentials (`~/.config/gws/`). chmod 700/600 mitigates but doesn't fully solve.
- **Nothing committed to git yet** — all work is local uncommitted changes.

---

## 7. Surprises & Discoveries

- **`gws auth revoke` doesn't exist** — the correct command is `gws auth logout`. Caused an error during Timothy's first attempt.
- **`--scopes` flag requires full Google OAuth URLs** — shorthand like `drive.readonly` doesn't work. Must use `https://www.googleapis.com/auth/drive.readonly`. Caused a 400 invalid_scope error.
- **gws-cli has 32 GCP APIs enabled** on Timothy's project but only uses ~11. Significant unnecessary attack surface.
- **gws-cli has ZERO confirmation prompts** for destructive operations. `files.delete` executes immediately with no undo. `emptyTrash` permanently destroys everything in trash.
- **`--dry-run` is per-command opt-in** — no way to set it as a global default. Wrapper script is the only way to enforce it.
- **gws-cli dynamically generates its command surface from Google's Discovery Service** — it exposes the FULL API surface of every enabled service, not a curated subset.
- **`--readonly` flag gives read-only scopes for 7 core services** (Drive, Sheets, Gmail, Calendar, Docs, Slides, Tasks) but does NOT include People/Contacts.
- **`--services` flag acts as a post-filter** — can combine with `--readonly` (e.g., `--readonly --services drive,gmail` gives only those two in read-only)

---

## 8. Next Steps

1. **Timothy chooses Option A or B and runs auth** — `gws auth logout` then `gws auth login --readonly` (or Option B with full URLs)
2. **Timothy completes Steps 2-3** — Workspace Admin OAuth restrictions + disable unnecessary GCP APIs (instructions in `docs/gws-cli-setup-guide.md`)
3. **Ryan builds `gws-safe` wrapper script** — Layer 2 defense per Dwight's spec (blocks destructive commands, enforces dry-run, audit logs). Spec is in Dwight's security requirements document from this session.
4. **Ryan builds gws-cli skill** — makes gws-safe callable by agents in workflows
5. **Dwight reviews the wrapper + skill** — security sign-off before any agent gets access
6. **Start building functional skills** — daily briefing, calendar management, task tracking, note curation
7. **Commit all work to git** — everything is uncommitted right now
