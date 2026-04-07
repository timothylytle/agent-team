# Research: Strategy B — insertText Inheritance for Bullet Lists

**Date:** 2026-04-07
**Status:** Research complete, test verified
**Document tested:** `1CUXjfdhY_D3PrpvpTx_vC1guLDhWmqS5xt0Og4uTY9I`

## Objective

Determine whether inserting text (with embedded newlines) before the trailing `\n` of an existing bulleted paragraph causes new paragraphs to automatically inherit the bullet list membership, eliminating the need for `createParagraphBullets` calls that create orphaned list definitions.

## Findings

### 1. Exact Insertion Point

**Confirmed by live test: insert at `endIndex - 1` of the existing bullet paragraph (i.e., before its trailing `\n`).**

For a paragraph occupying indices [653-746] where index 745 is the `\n`:
- Insert at index **745** (before the newline)
- The inserted `\n` characters split the paragraph into multiple paragraphs
- All resulting paragraphs inherit the bullet membership

**Do NOT insert at `endIndex` (746) or at the startIndex of the next element.** Inserting at 746 would place text in the next paragraph (the HEADING_2 "Random Fact:"), which is a different paragraph context.

The `find_last_bullet_end_in_section()` function currently returns `element.get("endIndex")`, which is 746 (exclusive end). For Strategy B, the insertion point must be `endIndex - 1` to land before the `\n`.

### 2. What Gets Inherited

All of the following are inherited automatically (confirmed by API response):

| Property | Inherited? | Evidence |
|----------|-----------|----------|
| `listId` (bullet list membership) | **Yes** | New paragraphs showed `listId=kix.na8z1sl73t6r`, same as parent |
| `nestingLevel` | **Yes** | Inherited as `0`, matching parent |
| `bullet.textStyle.weightedFontFamily` | **Yes** | Inherited `{"fontFamily": "Roboto", "weight": 400}` |
| `paragraphStyle.namedStyleType` | **Yes** | Inherited as `NORMAL_TEXT` |
| Text run `textStyle.weightedFontFamily` | **Yes** | Content showed `{"fontFamily": "Roboto", "weight": 400}` |

No `createParagraphBullets` call was needed. No `updateTextStyle` call was needed for font. No `updateParagraphStyle` call was needed to set NORMAL_TEXT.

### 3. List Definition Count Verification

- **Before insert:** 15 list definitions
- **After single-line insert:** 15 list definitions (no new definition created)
- **After multi-line insert (3 lines):** 15 list definitions (no new definition created)

This is the core goal: `createParagraphBullets` always creates a new list definition. Strategy B creates zero.

### 4. Multi-Line Insert Behavior

Inserting `\nLINE A\nLINE B\nLINE C` at index 745 (before the existing `\n`) produced:

```
[653-746] original bullet text...  \n      <- original paragraph (unchanged)
[746-758] TEST LINE A\n                    <- new paragraph, inherited bullet
[758-770] TEST LINE B\n                    <- new paragraph, inherited bullet
[770-782] TEST LINE C<original next text>  <- MERGED with next paragraph (no trailing \n!)
```

**Critical finding:** The last inserted segment (after the final `\n` in the inserted text) merges with whatever follows the insertion point. In this test, "TEST LINE C" merged with "Random Fact:\n" because the inserted text did not end with `\n`.

**Rule: the inserted text MUST be structured as `\nline1\nline2\nline3` (leading `\n`, NO trailing `\n`).** The leading `\n` splits the current paragraph. Each embedded `\n` creates a new paragraph. The last line ends up in the portion before the original paragraph's `\n`, which terminates it correctly.

### 5. What Needs to Change in Each Script

#### Current flow (all three updater scripts):
1. `insertText` at `section_end` or `find_last_bullet_end_in_section()`
2. `updateParagraphStyle` to set `NORMAL_TEXT`
3. `createParagraphBullets` with checkbox preset
4. `updateTextStyle` for font styling

#### Strategy B flow:
1. `insertText` at `find_last_bullet_end_in_section() - 1` (before the `\n`)
2. ~~`updateParagraphStyle`~~ -- **NOT NEEDED** (inherits `NORMAL_TEXT` from parent)
3. ~~`createParagraphBullets`~~ -- **NOT NEEDED** (inherits bullet + listId from parent)
4. ~~`updateTextStyle`~~ -- **NOT NEEDED** for font (inherits `weightedFontFamily` from parent)

Formatting requests that MAY still be needed:
- `updateTextStyle` for **links** (e.g., FreshDesk ticket URLs, Gmail message links) -- links are content-specific and won't be inherited
- `updateTextStyle` for **foreground color** if it differs from the inherited color -- but currently `bodyText` color is `null` in `doc_styles.json`, so this is not needed

#### Text format change:

Current format (when inserting at a boundary):
```python
insert_text = "\n".join(lines) + "\n"
```

Strategy B format (when inserting before existing `\n`):
```python
insert_text = "\n" + "\n".join(lines)  # leading \n, NO trailing \n
```

The leading `\n` splits the existing paragraph. The final line ends before the existing paragraph's `\n`.

#### Index calculation change:

```python
# Current:
last_bullet = find_last_bullet_end_in_section(doc, section_start, section_end)
insert_index = last_bullet if last_bullet else section_end

# Strategy B:
last_bullet = find_last_bullet_end_in_section(doc, section_start, section_end)
if last_bullet:
    insert_index = last_bullet - 1  # before the \n
else:
    insert_index = section_end  # fallback: no existing bullets
```

#### Range calculations for post-insert formatting:

When inserting before the `\n`, the new text starts at `insert_index + 1` (after the `\n` we inserted) and ends at `insert_index + utf16_len(insert_text)`. The original `\n` is now at `insert_index + utf16_len(insert_text)`.

For link styling on individual lines, the cursor math needs to account for the leading `\n`.

### 6. Edge Cases

#### Empty section (no existing bullets) -- FIRST CREATION

When `find_last_bullet_end_in_section()` returns `None`, there are no existing bullets to inherit from. This happens on first creation or if the section was emptied.

**Fallback:** Use the current approach (insert at `section_end`, use `createParagraphBullets`). This creates one new list definition, which is acceptable -- it only happens once per section per daily log entry.

`create-daily-log` always creates from scratch at index 1, so it must keep using `createParagraphBullets` for the initial entry. The updater scripts only need Strategy B for subsequent additions.

#### Checked checkboxes

If the existing bullet is a checkbox that has been checked, the new paragraph inherits the **unchecked** state. The checked state is a UI-level property not exposed in the API (confirmed in open-tickets-uncheck research). The `\n`-split creates fresh paragraphs that default to unchecked. This is the desired behavior.

#### Different font styling

If the existing bullet has a different font than what we want to apply, the new paragraphs inherit the existing font. Since all our bullet items use the same body font (`Roboto`), this is not an issue. If we needed a different style, we would need explicit `updateTextStyle` calls.

#### The original paragraph after split

The original paragraph retains its full content and formatting. The split happens cleanly: content before the inserted `\n` stays in the original paragraph, content after the `\n` (our new lines) becomes new paragraphs, and the original trailing `\n` terminates the last new paragraph.

### 7. Per-Script Change Summary

#### `bin/update-open-tickets` -- `build_batch_update()`
- Change `insert_index` from `section_end` to `last_bullet - 1` (when bullets exist)
- Change `insert_text` from `"\n".join(lines) + "\n"` to `"\n" + "\n".join(lines)`
- Remove `createParagraphBullets` request (when using inheritance path)
- Remove `updateParagraphStyle` request (when using inheritance path)
- Remove `updateTextStyle` for font (when using inheritance path)
- Keep: nothing extra needed (ticket URLs are plain text, not links)

#### `bin/update-email` -- `build_batch_update()`
- Same `insert_index` and `insert_text` changes
- Remove `createParagraphBullets` and `updateParagraphStyle` and font `updateTextStyle`
- **Keep:** `updateTextStyle` for Gmail link URLs on each line (links are content-specific)
- Adjust link range calculations for the leading `\n` offset

#### `bin/update-task-list` -- `build_batch_update()`
- Priority items: same changes as above
- Waiting/Blockers: currently does delete+re-insert. After deletion there may be no preceding bullet, so this sub-section may still need `createParagraphBullets` as fallback. OR: find a bullet in the priorities sub-section above and use inheritance from there.
- Notes HEADING_3 entries: these are headings, not bullets. No change needed.
- **Keep:** `updateTextStyle` for [event]/[task] inline links

#### `bin/create-daily-log` -- `build_batch_update()`
- No change. Initial creation inserts at index 1 with no existing bullets to inherit from. Must continue using `createParagraphBullets`.

#### `bin/lib/daily_log_utils.py` -- `find_last_bullet_end_in_section()`
- No change to the function itself. Callers will subtract 1 from the return value.
- Alternatively: add a new helper `find_last_bullet_newline_in_section()` that returns `endIndex - 1`.

### 8. Verification Approach

After implementing, verify with this procedure:

1. Fetch doc, count entries in `doc["lists"]` -- record as `before_count`
2. Run the updater script
3. Fetch doc again, count entries in `doc["lists"]` -- record as `after_count`
4. Assert `after_count == before_count` (no new list definitions)
5. Verify new paragraphs have `bullet.listId` matching existing bullets in the same section

## Recommendations

1. **Implement Strategy B in all three updater scripts** (`update-open-tickets`, `update-email`, `update-task-list`). The approach is proven by live testing.

2. **Keep `createParagraphBullets` as fallback** for the empty-section case (`find_last_bullet_end_in_section()` returns `None`). This is a rare case that only adds one list definition.

3. **Keep `create-daily-log` unchanged** -- it creates the initial entry with no existing bullets to inherit from.

4. **The `build_batch_update` functions need two code paths:** inheritance path (when existing bullets found) and fallback path (when no existing bullets). The fallback path is the current code.

5. **Simplification opportunity:** When using the inheritance path, most formatting requests (paragraph style, bullet creation, font styling) can be dropped entirely. Only content-specific styling (links) needs to remain.

## Risks / Caveats

1. **Trailing `\n` omission is critical.** If the inserted text ends with `\n`, it creates an empty paragraph that inherits the bullet, and the original paragraph's `\n` starts a new non-bulleted paragraph. The text format must be `"\n" + "\n".join(lines)` (no trailing newline).

2. **Index math changes.** All range calculations for post-insert formatting (links) must account for the `+1` offset from the leading `\n` and the `-1` from inserting before the existing `\n` rather than at the boundary.

3. **`update-task-list` waiting/blockers** is the most complex case because it does delete+re-insert. After deleting all waiting items, there may be no bullet to inherit from in that sub-section. Need careful handling.

4. **Testing must verify the actual daily log** (not just a test document) since the document structure, existing list definitions, and checked states are all factors.
