---
name: ideas
description: Analyzes ideas with pros/cons executive summary, logs to CRM and daily log card format.
---

You are executing the Ideas skill. This skill analyzes ideas and produces executive summaries.

## Input

The user provides an idea — either a title, a description, or a URL to research.

## Workflow

### Step 1: Research

If the idea references a product, technology, or URL:
- Use WebSearch or WebFetch to understand the topic
- Gather enough context to form an informed opinion

### Step 2: Analyze

Produce a brief executive summary:
- 2-3 Pros (benefits, opportunities)
- 2-3 Cons (risks, challenges, costs)
- Brief recommendation (pursue, defer, or dismiss — with reasoning)

### Step 3: Create CRM record

```bash
bin/crm-safe ideas create --json '{"title": "...", "source_text": "original input", "source_url": "https://...", "analysis": "Pros: ... Cons: ... Recommendation: ...", "status_id": 2}'
```

### Step 4: Add card to daily log

```bash
bin/update-ideas-log --json '{"title": "Idea Title", "pros": ["Pro 1", "Pro 2"], "cons": ["Con 1", "Con 2"], "recommendation": "Brief recommendation", "source_url": "https://..."}' --auto-confirm
```

### Step 5: Report

Report the idea title, one-line summary, and CRM ID to the user.
