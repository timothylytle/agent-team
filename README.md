# agent-team
AI agent assistant and PKM

## Guides

| Guide | Description |
|-------|-------------|
| [GWS CLI Setup](docs/guides/gws-cli-setup.md) | Install and configure gws-cli with restricted OAuth scopes for AI agent use |
| [FreshDesk Setup](docs/guides/freshdesk-setup.md) | Create a FreshDesk collaborator account and configure API access for AI agent use |

## Audit Logs

Both security wrappers log every operation to structured JSON files:

| Log | Location |
|-----|----------|
| GWS | `~/.local/log/gws-safe/audit.log` |
| FreshDesk | `~/.local/log/freshdesk-safe/audit.log` |

Each line is a JSON object with `timestamp`, `command`, `decision`, and `exit_code`:

```json
{"timestamp":"2026-03-27T22:07:36Z","command":"freshdesk tickets list --per_page 2","decision":"ALLOWED","exit_code":0}
```

Decisions are one of: `ALLOWED`, `BLOCKED`, `DRY-RUN-ENFORCED`, `HUMAN-APPROVED`.

### Useful commands

```bash
# View recent activity
tail -20 ~/.local/log/freshdesk-safe/audit.log | jq .

# View only blocked attempts
cat ~/.local/log/freshdesk-safe/audit.log | jq 'select(.decision == "BLOCKED")'

# View all write operations that were approved
cat ~/.local/log/freshdesk-safe/audit.log | jq 'select(.decision == "HUMAN-APPROVED")'

# Count operations by decision type
cat ~/.local/log/freshdesk-safe/audit.log | jq -r .decision | sort | uniq -c | sort -rn

# Same commands work for gws-safe — just swap the path
tail -20 ~/.local/log/gws-safe/audit.log | jq .
```
