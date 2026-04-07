# Research: Orphaned List Definitions in Daily Log

## Problem

The daily log Google Doc accumulates orphaned list definitions from repeated `createParagraphBullets` calls in batchUpdate operations. Over time, 52+ orphaned definitions bloated the document metadata (111 KB / 50% of doc JSON), causing the Android Google Docs app to fail with "Can't open this document."

## Root Cause

`createParagraphBullets` creates a **new** list definition unless the paragraph **immediately preceding** the target range is already a member of a list with the **same bullet preset**. Our scripts always insert at section boundaries (next to HEADING_2 elements), so the auto-join condition is never met.

## Fix: Insert Adjacent to Existing Bullets

Instead of inserting at `section_end` (start of next heading), find the end index of the last existing bulleted paragraph in the section and insert there. The new paragraphs will then auto-join the existing list.

### Shared helper (add to `lib/daily_log_utils.py`):

```python
def find_last_bullet_end_in_section(doc, section_start, section_end):
    """Find the endIndex of the last bulleted paragraph in a section."""
    body_content = doc.get("body", {}).get("content", [])
    last_bullet_end = None
    for element in body_content:
        el_start = element.get("startIndex", 0)
        if el_start < section_start or el_start >= section_end:
            continue
        paragraph = element.get("paragraph", {})
        if paragraph.get("bullet"):
            last_bullet_end = element.get("endIndex")
    return last_bullet_end
```

### Per-script changes:

```python
# Before (creates orphaned list definitions):
insert_index = section_end

# After (reuses existing list):
last_bullet = find_last_bullet_end_in_section(doc, section_start, section_end)
insert_index = last_bullet if last_bullet else section_end
```

### Affected scripts:
- `bin/update-open-tickets` — ticket lines use BULLET_CHECKBOX
- `bin/update-email` — email lines use BULLET_CHECKBOX
- `bin/update-task-list` — priority items use BULLET_CHECKBOX, waiting items use BULLET_CHECKBOX
- `bin/create-daily-log` — initial creation (less critical, creates seed definitions)

### Edge cases:
1. **Empty section (no existing bullets):** Falls back to `section_end`, creates one new list definition (acceptable — only happens once per section per entry)
2. **Label lines between bullets:** "Priorities:" and "Waiting / Blockers:" labels may prevent auto-join. Must insert after the last bullet in each sub-section, not after the label.
3. **`update-task-list` waiting/blockers:** Does delete+re-insert, may have no preceding bullet after deletion. May still create one new definition per update cycle.

### API limitations:
- No API to delete list definitions
- No API to directly set `bullet.listId` on a paragraph
- No `updateBullet` request type
- Cleanup requires document copy (already done)

## One-time cleanup

Document was copied via Drive API `files.copy`. The copy only retains referenced list definitions, eliminating orphaned ones. Config updated to new document ID.
