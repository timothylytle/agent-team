#!/usr/bin/env bash
# Gate for gws-safe and freshdesk-safe commands:
# - Auto-approve reads and dry-runs (no --confirmed flag)
# - Require user approval for confirmed write operations
# Auto-approve date commands (local, read-only)
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

if echo "$COMMAND" | grep -qE '(gws-safe|freshdesk-safe)'; then
  if echo "$COMMAND" | grep -q -- '--confirmed'; then
    echo '{"decision":"ask","reason":"Write operation requires approval"}'
  else
    echo '{"decision":"allow"}'
  fi
elif echo "$COMMAND" | grep -qE '^date\b'; then
  echo '{"decision":"allow"}'
else
  # Not a recognized command, pass through to normal permission handling
  echo '{}'
fi
