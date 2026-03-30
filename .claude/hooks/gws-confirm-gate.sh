#!/usr/bin/env bash
# Gate for gws-safe and freshdesk-safe commands:
# - Auto-approve reads and dry-runs (no --confirmed flag)
# - Require user approval for confirmed write operations
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

# Only gate gws-safe and freshdesk-safe commands
if echo "$COMMAND" | grep -qE '(gws-safe|freshdesk-safe)'; then
  if echo "$COMMAND" | grep -q -- '--confirmed'; then
    echo '{"decision":"ask","reason":"Write operation requires approval"}'
  else
    echo '{"decision":"allow"}'
  fi
else
  # Not a gws-safe/freshdesk-safe command, pass through to normal permission handling
  echo '{}'
fi
