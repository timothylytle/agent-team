# Handoff Document — FreshDesk Integration

**Date:** 2026-03-27
**Session:** FreshDesk API research + integration planning
**Branch:** `20260327_freshdesk_skill`

---

## 1. Goal / Problem Statement

Build a FreshDesk integration skill for the agent team so agents (especially Pam) can unify support tickets, calendar events, tasks, and notes across FreshDesk and Google Workspace. Follows the same security-first pattern established by the GWS integration.

---

## 2. Current Status

### Done
- **FreshDesk API research completed (Oscar)** — authentication model, endpoints, rate limits, search constraints, webhook limitations all documented
- **Codebase analysis completed** — existing GWS skill pattern, `gws-safe` wrapper (3-layer security), agent definitions, and skill registration all understood
- **FreshDesk setup guide created** — `docs/guides/freshdesk-setup.md`, mirrors the GWS guide structure

### Remaining
- **Phase 0: Account setup (Timothy, manual)** — create collaborator account, store API key, run verification commands, fill in permission testing checklist
- **Phase 1: Build `bin/freshdesk-safe` wrapper (Ryan)** — 3-layer security wrapper modeled after `bin/gws-safe`
- **Phase 2: Create `.claude/skills/freshdesk.md` skill definition (Ryan)** — follows GWS skill pattern
- **Phase 3: Cross-platform unification** — daily ticket briefing, Google Docs from ticket context, calendar-ticket associations, ticket summaries, task sync
- **Phase 4: Security review + QA (Dwight, Creed)** — adversarial testing and security sign-off

### Progress Estimate
~15% — Research and planning complete. No implementation yet. Blocked on Phase 0 (Timothy's manual setup).

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `docs/guides/freshdesk-setup.md` | NEW — Collaborator account setup, API key storage, verification commands, permission testing checklist |
| `docs/plans/freshdesk-integration/handoff.md` | NEW — This handoff document |
| `docs/plans/freshdesk-integration/research.md` | NEW — Oscar's FreshDesk API research findings |
| `bin/gws-safe` | REFERENCE — Security wrapper pattern to follow for `freshdesk-safe` (472 lines, 3-layer security) |
| `.claude/skills/gws.md` | REFERENCE — Skill definition pattern to follow |
| `.claude/agents/pam.md` | REFERENCE — Primary consumer of the new skill |
| `.claude/agents/ryan.md` | REFERENCE — Will build the wrapper and skill definition |
| `.claude/agents/dwight.md` | REFERENCE — Security review |
| `.claude/agents/creed.md` | REFERENCE — Adversarial testing |
| `docs/plans/gws-integration/setup-guide.md` | REFERENCE — GWS setup guide pattern |

---

## 4. How to Run

- **FreshDesk API** is a standard REST API — no CLI tool, uses `curl` directly
- **Authentication:** HTTP Basic Auth with API key as username and `X` as password
- **Credential storage:** `~/.config/freshdesk/config.json` (not yet created — Phase 0)
- **No wrapper or skill exists yet** — all implementation is ahead of us
- **Environment:** Linux WSL2, bash shell

---

## 5. Recent Decisions

- **Collaborator account (agent_type: 3) over full agent** — least-privilege approach. Collaborators have restricted access by design. Pending empirical validation in Phase 0.
- **Same 3-layer security pattern as GWS** — (1) Allowlist of permitted API operations, (2) dry-run enforcement for writes, (3) nonce-based human-in-the-loop confirmation for writes. Layers are independent.
- **API key at `~/.config/freshdesk/config.json`** — follows the same filesystem pattern as GWS credentials at `~/.config/gws/`
- **curl-based wrapper** — FreshDesk is a REST API with no dedicated CLI tool (unlike GWS which has `gws-cli`), so `freshdesk-safe` will wrap `curl` calls directly
- **Blocked operations:** delete tickets, close tickets, reassign, bulk operations, admin endpoints. These require a human using the FreshDesk UI directly.
- **Private notes only for writes** — agents can add private notes to tickets (with human approval) but cannot modify ticket fields like status, priority, or assignment

---

## 6. Open Issues / Blockers

- **BLOCKER: Collaborator API permissions are undocumented.** FreshDesk does not document what API operations collaborators can and cannot perform. Phase 0 includes a permission testing checklist Timothy must complete. If collaborators are too restricted, we'll need to switch to a full agent with a custom restricted role.
- **Rate limits are account-wide** — 3,000-5,000 requests/hour shared across ALL integrations on the FreshDesk instance. If other integrations exist, the budget is shared.
- **Search capped at 300 results** with an indexing delay — not suitable for real-time or exhaustive queries. Skill design must account for this constraint.
- **Webhooks are admin-UI-only** — can't be configured via API. Push-based updates would require manual webhook setup in FreshDesk admin.
- **Phase 0 must complete before any implementation can start** — Ryan can't build `freshdesk-safe` without knowing what a collaborator can actually do via API.

---

## 7. Surprises & Discoveries

- **FreshDesk has no OAuth** — only HTTP Basic Auth with API keys. Simpler to implement but no token refresh or granular scope control.
- **Collaborator restrictions are a black box** — FreshDesk documents that collaborators have "limited permissions" but never specifies which API endpoints return 403. Must be tested empirically.
- **Rate limits are generous but shared** — 3,000-5,000/hour sounds high, but it's account-wide. A busy FreshDesk instance with multiple integrations could exhaust this.
- **Search indexing has a delay** — newly created or updated tickets may not appear in search results immediately. Skill should not rely on search for just-created items.

---

## 8. Next Steps

1. **Timothy completes Phase 0** — create collaborator account, store API key, run verification commands, and critically: **fill in the permission testing checklist** (Step 5 of `docs/freshdesk-setup-guide.md`) to determine what collaborators can actually do via API. Report which operations succeeded and which returned 403s.
2. **Ryan builds `bin/freshdesk-safe`** — 3-layer security wrapper modeled after `bin/gws-safe`. Blocked on Phase 0 results.
3. **Ryan creates `.claude/skills/freshdesk.md`** — skill definition following GWS pattern. Register in CLAUDE.md skills table.
4. **Dwight reviews `freshdesk-safe`** — security posture review before any agent gets access.
5. **Creed adversarially tests the wrapper** — attempt to bypass allowlist, dry-run, and nonce confirmation layers.
6. **Update `.claude/settings.local.json`** — add `freshdesk-safe` permission allowlist entries.
7. **Build cross-platform workflows** — daily ticket briefing, ticket-to-Docs, calendar-ticket linking, task sync.
