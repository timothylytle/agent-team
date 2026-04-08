---
name: ideas
description: Processes ideas from the Google Chat "Thoughts/Ideas" space, analyzes them, logs to CRM and daily log.
---

You are executing the Ideas skill. This skill processes new ideas from the Google Chat "Thoughts/Ideas" space.

## Configuration

Read the space ID from `config/ideas.json`.

## Workflow

For each run:

### Step 1: Fetch new messages

```bash
bin/chat-safe spaces messages list SPACE_ID --page-size 100
```

Filter out:
- Messages from bots (sender type is not `HUMAN`)
- Empty messages
- Already-processed messages (have a ✅ in `emojiReactionSummaries`)

If no new messages remain, report "No new ideas to process" and exit.

### Step 2: Analyze each idea

For each message:
1. Read the message text and any URLs
2. If the message contains a URL, use WebFetch to read the page and understand what it's about
3. Perform a high-level analysis:
   - What is the idea/concept?
   - Pros (2-3 bullet points)
   - Cons (2-3 bullet points)
   - Rough time to implement (small/medium/large)
   - Brief recommendation

### Step 3: Create CRM record

```bash
bin/crm-safe ideas create --json '{"title": "...", "source_text": "original message text", "source_url": "https://...", "analysis": "formatted analysis", "status_id": 2, "chat_message_id": "spaces/.../messages/..."}'
```

### Step 4: Add to daily log

```bash
bin/update-ideas-log --title "Idea Title" --analysis "One-line summary with recommendation" [--source-url "..."] --auto-confirm
```

### Step 5: Mark the Chat message as processed

React with a checkmark so you know it's been handled:
```bash
bin/chat-safe spaces messages reactions create MESSAGE_NAME --emoji ✅
```
(confirm the nonce)

Messages with a ✅ reaction should be skipped on future runs.

### Step 6: Report

After processing all messages, report:
- Number of ideas processed
- For each: title, one-line summary, CRM ID
