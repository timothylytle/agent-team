# Research: Daily Log Archive Functionality

## Objective

Document every behavior required to build a deterministic Python script (`bin/archive-daily-log`) that archives old daily log entries from the main document to a tabbed archive document. This covers the full process from the original SKILL.md Step 5, including all complex element handling (richLinks, inlineObjects, person chips), tab management, index arithmetic, and the exact API calls needed.

Source material: the original SKILL.md (commit `da953bf`), the tab-structure version (commit `e8d6a28`), the existing `bin/create-daily-log`, `bin/lib/daily_log_utils.py`, `bin/gws-safe`, and `config/daily_log.json`.

---

## 1. When Archiving Triggers

### Condition

Archiving triggers when the main daily log document contains entries (HEADING_1 paragraphs with parseable date text) from **before the Monday of the current week**.

### Defining "Monday of the Current Week"

- If today is Monday, the cutoff is today's date.
- If today is Tuesday through Sunday, the cutoff is the most recent Monday.
- Python: `today - timedelta(days=today.weekday())` (since Monday is weekday 0).

### What Gets Archived

Every entry whose parsed date is **strictly before** the Monday of the current week. Entries from the current week (Monday through today) remain in the main document.

### Integration Point

The archive script should be invocable standalone:

```bash
bin/archive-daily-log --auto-confirm
```

The `create-daily-log` script could optionally call it after creating/updating today's entry, but given the complexity the SKILL.md deferred it, so it should remain a separate script.

---

## 2. Source Document Reading

### Identifying Old Entries

The existing `parse_doc_entries()` function in `bin/lib/daily_log_utils.py` already handles this:

1. Fetches the document via `docs documents get`
2. Walks `body.content` for HEADING_1 paragraphs
3. Parses dates from heading text using `parse_date_from_heading()`
4. Returns entries with `entry_date`, `heading_text`, `start_index`, `end_index`

Each entry spans from its HEADING_1 `startIndex` to the next HEADING_1 `startIndex` (or the document body's last `endIndex` for the final entry).

### API Call: Read Source Document

```
gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'
```

- **Service:** `docs`
- **Method:** `documents get`
- **Parameters:** `documentId` (from `config/daily_log.json`)
- **Auth:** Read-only, no dry-run enforcement

The response contains `body.content` (paragraph elements with indices) and `inlineObjects` (image metadata keyed by `inlineObjectId`).

---

## 3. Archive Document Structure

### Tab Hierarchy

The archive document uses a three-level tab hierarchy:

```
Archive Document
  2026                          (Year tab)
    2026-Q1                     (Quarter tab, child of year)
      Week 1 (Jan 5-9)         (Week tab, child of quarter)
      Week 2 (Jan 12-16)
      ...
    2026-Q2
      Week 1 (Apr 6-10)
      ...
```

### Tab Title Formats

**Year tab:** `YYYY` (e.g., `2026`)

**Quarter tab:** `YYYY-QN` where N is 1-4 (e.g., `2026-Q1`)

- Q1: January-March
- Q2: April-June
- Q3: July-September
- Q4: October-December

**Week tab:** Two formats depending on whether the week spans months:

- Same month: `Week N (Mon D-D)` (e.g., `Week 3 (Jan 19-23)`)
- Cross-month: `Week N (Mon D - Mon D)` (e.g., `Week 10 (Sep 29 - Oct 3)`)

### Week Number Calculation

The week number is calculated **relative to the quarter**, not the ISO year:

1. Determine the quarter start date: Jan 1, Apr 1, Jul 1, or Oct 1
2. Find the first Monday on or after the quarter start date
3. Week 1 starts on that Monday
4. Count forward in 7-day increments to determine the entry's week number

Python implementation:

```python
from datetime import date, timedelta

def get_quarter_info(d):
    """Returns (quarter_number, quarter_start_date) for a given date."""
    q = (d.month - 1) // 3 + 1
    quarter_start = date(d.year, (q - 1) * 3 + 1, 1)
    return q, quarter_start

def get_first_monday_on_or_after(d):
    """Returns the first Monday on or after date d."""
    days_ahead = (7 - d.weekday()) % 7  # Monday is 0
    return d + timedelta(days=days_ahead) if d.weekday() != 0 else d

def get_week_info(entry_date):
    """Returns (year, quarter, week_number, week_monday, week_friday)."""
    year = entry_date.year
    quarter, quarter_start = get_quarter_info(entry_date)
    first_monday = get_first_monday_on_or_after(quarter_start)

    # Find the Monday of the entry's week
    week_monday = entry_date - timedelta(days=entry_date.weekday())

    # Calculate week number (1-based)
    week_number = ((week_monday - first_monday).days // 7) + 1

    week_friday = week_monday + timedelta(days=4)
    return year, quarter, week_number, week_monday, week_friday

def format_week_tab_title(week_number, week_monday, week_friday):
    """Format the week tab title."""
    if week_monday.month == week_friday.month:
        # Same month: "Week 3 (Jan 19-23)"
        mon_str = week_monday.strftime("%b")
        return f"Week {week_number} ({mon_str} {week_monday.day}-{week_friday.day})"
    else:
        # Cross-month: "Week 10 (Sep 29 - Oct 3)"
        mon_str = week_monday.strftime("%b")
        fri_str = week_friday.strftime("%b")
        return f"Week {week_number} ({mon_str} {week_monday.day} - {fri_str} {week_friday.day})"
```

### Edge Case: Entries Before Quarter's First Monday

If an entry's date falls before the quarter's first Monday (e.g., the quarter starts on a Wednesday and the entry is from that Wednesday), its `week_monday` will be before `first_monday`. The week number calculation could yield 0 or negative. The SKILL.md does not explicitly address this. Practical impact is low since entries are typically archived weekly, but the script should handle it by assigning week number 1 to any entry in the gap before the first full week.

---

## 4. Archive Document Management

### 4a. Ensure Archive Document Exists

**Config key:** `archiveDocumentId` in `config/daily_log.json`

Current config already has this:
```json
{
  "documentId": "1c6V1yEE4HpNWZqh-pIe76VuoPif2zJZGOVoEkw8xvN0",
  "archiveDocumentId": "1AEtrPba0eLawxKFe3tvBUYScI1A-_5phQ8NGl8PkD2M"
}
```

**If `archiveDocumentId` is missing:** Create a new document:

```
gws-safe docs documents create --json '{"title":"_daily_log_archive"}'
```

- Write operation: dry-run enforced, nonce returned, must confirm
- Extract `documentId` from response
- Save to config file as `archiveDocumentId`

**If `archiveDocumentId` exists:** Read the archive document with tabs:

```
gws-safe docs documents get --params '{"documentId":"<ARCHIVE_DOC_ID>","includeTabsContent":true}'
```

- The `includeTabsContent: true` parameter is required to get tab structure
- If the read fails (404/403), report error and offer to create a new archive doc

### 4b. Build Existing Tab Map

Walk the archive document's `tabs` array recursively to build a map of existing tabs:

```python
def build_tab_map(tabs, tab_map=None):
    """Recursively build {tab_title: tab_id} from the tabs array."""
    if tab_map is None:
        tab_map = {}
    for tab in tabs:
        props = tab.get("tabProperties", {})
        title = props.get("title", "")
        tab_id = props.get("tabId", "")
        if title:
            tab_map[title] = tab_id
        # Recurse into child tabs
        for child in tab.get("childTabs", []):
            build_tab_map([child], tab_map)
    return tab_map
```

The response structure for a tabbed document:
```json
{
  "documentId": "...",
  "title": "_daily_log_archive",
  "tabs": [
    {
      "tabProperties": {"tabId": "t.abc123", "title": "2026", "index": 0},
      "childTabs": [
        {
          "tabProperties": {"tabId": "t.def456", "title": "2026-Q1", "parentTabId": "t.abc123", "index": 0},
          "childTabs": [
            {
              "tabProperties": {"tabId": "t.ghi789", "title": "Week 3 (Jan 19-23)", "parentTabId": "t.def456", "index": 0},
              "documentTab": {"body": {"content": [...]}}
            }
          ]
        }
      ]
    }
  ]
}
```

### 4c. Create Missing Tabs

Tabs must be created in dependency order because child tabs require their parent's tab ID. Three separate batchUpdate calls, one per level:

**Level 1: Year tabs**

```
gws-safe docs documents batchUpdate --json '{"requests":[
  {"addDocumentTab":{"tabProperties":{"title":"2026","index":0}}}
]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
```

- Write operation: dry-run/nonce flow
- Extract new tab IDs from `replies[N].addDocumentTab.tabProperties.tabId`
- `index` determines position among sibling tabs (0 = first)

**Level 2: Quarter tabs**

```
gws-safe docs documents batchUpdate --json '{"requests":[
  {"addDocumentTab":{"tabProperties":{"title":"2026-Q1","parentTabId":"<YEAR_TAB_ID>","index":0}}}
]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
```

- `parentTabId` is the year tab's ID (from Level 1 creation or existing tab map)
- `index` for quarter ordering: Q1=0, Q2=1, Q3=2, Q4=3

**Level 3: Week tabs**

```
gws-safe docs documents batchUpdate --json '{"requests":[
  {"addDocumentTab":{"tabProperties":{"title":"Week 3 (Jan 19-23)","parentTabId":"<QUARTER_TAB_ID>","index":0}}}
]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'
```

- `parentTabId` is the quarter tab's ID
- `index` should place weeks in chronological order among existing sibling week tabs

**Skip any batchUpdate that would have zero requests** (all tabs at that level already exist).

**Important:** After each level's batchUpdate, merge the newly created tab IDs into the tab map so the next level can reference them as parents.

---

## 5. Extracting Entry Content from Source Document

This is the most complex part of the archive process. Each entry's content must be extracted with full fidelity, handling four types of paragraph elements.

### 5a. Element Types in Google Docs

When iterating `body.content[].paragraph.elements[]`, each element is one of:

#### textRun

Standard text content. The most common element type.

```json
{
  "startIndex": 10,
  "endIndex": 25,
  "textRun": {
    "content": "Some text here\n",
    "textStyle": {
      "weightedFontFamily": {"fontFamily": "Roboto"},
      "link": {"url": "https://example.com"}
    }
  }
}
```

- `content` contains the actual text including any trailing `\n`
- `textStyle` may include font, color, bold, italic, link, etc.
- UTF-16 length of `content` = `endIndex - startIndex`

#### inlineObjectElement

Embedded images. Each occupies exactly 1 character position.

```json
{
  "startIndex": 25,
  "endIndex": 26,
  "inlineObjectElement": {
    "inlineObjectId": "kix.abc123",
    "textStyle": {}
  }
}
```

The actual image data is in the document's top-level `inlineObjects` dictionary:

```json
{
  "inlineObjects": {
    "kix.abc123": {
      "objectId": "kix.abc123",
      "inlineObjectProperties": {
        "embeddedObject": {
          "imageProperties": {
            "contentUri": "https://lh7-us.googleusercontent.com/..."
          },
          "size": {
            "height": {"magnitude": 200, "unit": "PT"},
            "width": {"magnitude": 300, "unit": "PT"}
          },
          "embeddedObjectBorder": {...}
        }
      }
    }
  }
}
```

Key properties to extract:
- `contentUri`: temporary authenticated URL for the image (valid during the session)
- `size.height` and `size.width`: original dimensions with magnitude and unit

#### richLink

Smart chips linking to Google Workspace files (Docs, Sheets, Slides, etc.). Each occupies exactly 1 character position in the source document.

```json
{
  "startIndex": 30,
  "endIndex": 31,
  "richLink": {
    "richLinkId": "rl.abc123",
    "richLinkProperties": {
      "title": "Meeting Notes - Q1 Review",
      "uri": "https://docs.google.com/document/d/abc123/edit",
      "mimeType": "application/vnd.google-apps.document"
    },
    "textStyle": {}
  }
}
```

**Critical constraint:** There is no `insertRichLink` batchUpdate request in the Google Docs API. Rich links cannot be recreated as smart chips in the archive. Instead, the title text is substituted with a hyperlink applied via `updateTextStyle`.

Key properties to extract:
- `richLinkProperties.title`: display text (may be empty/missing)
- `richLinkProperties.uri`: the link URL

#### person

Person chips (smart chips representing a person by email). Each occupies exactly 1 character position.

```json
{
  "startIndex": 35,
  "endIndex": 36,
  "person": {
    "personId": "p.abc123",
    "personProperties": {
      "name": "John Smith",
      "email": "john@example.com"
    },
    "textStyle": {}
  }
}
```

Person chips **can** be recreated in the archive via `insertPerson` batchUpdate requests.

Key property to extract:
- `personProperties.email`: used to recreate the person chip

### 5b. Paragraph Metadata to Extract

For each paragraph in the entry, extract:

1. **Named style type**: `paragraph.paragraphStyle.namedStyleType` (HEADING_1, HEADING_2, HEADING_3, NORMAL_TEXT)
2. **Bullet status**: Whether the paragraph has a `bullet` property in `paragraphStyle` (indicates it's a bulleted item)
3. **Bullet preset**: Not directly available from the paragraph -- bullets are recreated using `createParagraphBullets` with the known presets from style config

### 5c. Building the Insertion Text

For each entry, build a single text string by walking all paragraphs and their elements:

```python
def extract_entry_content(doc, entry_start, entry_end):
    """Extract text, formatting metadata, and special elements from an entry.

    Returns:
        text: The full text string to insert (with richLink titles substituted,
              person positions excluded)
        paragraphs: List of paragraph metadata dicts
        rich_links: List of (archive_start, archive_end, uri) tuples
        images: List of (archive_index, content_uri, height, width) tuples
        persons: List of (archive_index, email) tuples
    """
    body_content = doc.get("body", {}).get("content", [])
    inline_objects = doc.get("inlineObjects", {})

    text_parts = []
    paragraphs = []
    rich_links = []
    images = []
    persons = []

    # Track cumulative offset caused by richLink expansion
    # (1 source char -> N archive chars) and person exclusion
    # (1 source char -> 0 chars in insertText, added via insertPerson)
    cumulative_offset = 0

    for element in body_content:
        el_start = element.get("startIndex", 0)
        el_end = element.get("endIndex", 0)
        if el_end <= entry_start or el_start >= entry_end:
            continue

        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        pstyle = paragraph.get("paragraphStyle", {})
        named_style = pstyle.get("namedStyleType", "NORMAL_TEXT")
        has_bullet = "bullet" in pstyle

        para_text_parts = []
        para_start_in_archive = len("".join(text_parts))  # archive index

        for pe in paragraph.get("elements", []):
            pe_start = pe.get("startIndex", 0)
            pe_end = pe.get("endIndex", 0)

            if "textRun" in pe:
                content = pe["textRun"].get("content", "")
                para_text_parts.append(content)

            elif "richLink" in pe:
                rl_props = pe["richLink"].get("richLinkProperties", {})
                title = rl_props.get("title") or rl_props.get("uri", "")
                uri = rl_props.get("uri", "")
                # Record position in archive text
                archive_pos = len("".join(text_parts)) + len("".join(para_text_parts))
                rich_links.append((archive_pos, archive_pos + len(title), uri))
                # Substitute title text for the 1-char richLink
                para_text_parts.append(title)

            elif "inlineObjectElement" in pe:
                obj_id = pe["inlineObjectElement"].get("inlineObjectId", "")
                obj_data = inline_objects.get(obj_id, {})
                embedded = obj_data.get("inlineObjectProperties", {}).get("embeddedObject", {})
                content_uri = embedded.get("imageProperties", {}).get("contentUri", "")
                size = embedded.get("size", {})
                height = size.get("height", {})
                width = size.get("width", {})
                # Record position -- image occupies 1 char in archive too
                archive_pos = len("".join(text_parts)) + len("".join(para_text_parts))
                images.append((archive_pos, content_uri, height, width))
                # Placeholder char that will be replaced by insertInlineImage
                # Do NOT include in text -- the image insertion adds its own character
                # Actually: include a placeholder newline or skip?
                # Per SKILL.md: inlineObjectElement is 1 char in source and 1 in dest
                # But it's inserted via insertInlineImage, not insertText
                # So do NOT include it in the text string
                pass

            elif "person" in pe:
                p_props = pe["person"].get("personProperties", {})
                email = p_props.get("email", "")
                archive_pos = len("".join(text_parts)) + len("".join(para_text_parts))
                persons.append((archive_pos, email))
                # Do NOT include in text -- inserted via insertPerson
                pass

        paragraphs.append({
            "text": "".join(para_text_parts),
            "named_style": named_style,
            "has_bullet": has_bullet,
            "archive_start": len("".join(text_parts)),
        })
        text_parts.append("".join(para_text_parts))

    full_text = "".join(text_parts)
    return full_text, paragraphs, rich_links, images, persons
```

**Note on the pseudocode above:** This is illustrative. The actual index arithmetic needs to account for the insertion base index (1 for top-of-tab) added to all archive positions. The positions tracked above are relative to the start of the inserted text; the actual document indices are `base_index + relative_position`.

---

## 6. Index Arithmetic for Archive Insertions

This is the hardest part to get right. There are three sources of index complexity:

### 6a. richLink Expansion

Source document: A richLink occupies 1 character (indices N to N+1).
Archive document: The richLink's title text occupies `utf16_len(title)` characters.

This means every richLink causes a cumulative expansion. When calculating archive indices for elements that come after a richLink, add `utf16_len(title) - 1` per preceding richLink.

### 6b. Person and Image Exclusion from insertText

Person chips and inline images are NOT included in the `insertText` string. They are inserted separately via `insertPerson` and `insertInlineImage` requests. This means:

- Each person/image element that would have occupied 1 character in the text causes a **-1 offset** in the `insertText` string compared to the source.
- When the `insertPerson` or `insertInlineImage` request executes, it inserts 1 character at the specified index, pushing all subsequent content forward by 1.

**The SKILL.md specifies:** Person and image insertions must be sorted by index **highest to lowest** (descending) and placed at the end of the batchUpdate. This ensures each insertion only shifts content below it, so earlier (higher-index) insertions don't affect later (lower-index) ones.

### 6c. Practical Index Tracking Strategy

The recommended approach from the SKILL.md:

1. Build the `insertText` string WITHOUT person or image placeholders, but WITH richLink title text substituted.
2. Track the "archive-relative" position of each element as you build the text string.
3. For richLinks: record `(archive_start, archive_end, uri)` where positions are relative to the insertText string start.
4. For images: record `(archive_position, content_uri, height, width)` where `archive_position` is where the image should be inserted (relative to insertText start). Since images are not in the text, their position is "between" surrounding text characters.
5. For persons: record `(archive_position, email)` similarly.
6. Add the tab's base index (1) to all positions.
7. After text insertion and formatting, process image and person insertions highest-index-first.

### 6d. UTF-16 Length Considerations

All index calculations must use `utf16_len()` not Python `len()`. The daily log entries contain emojis:

| Character | Python len | UTF-16 code units |
|-----------|-----------|-------------------|
| `\U0001f3af` (Target) | 1 | 2 |
| `\u23f3` (Hourglass) | 1 | 1 |
| `\U0001f3b2` (Die) | 1 | 2 |
| Regular ASCII | 1 | 1 |

The existing `utf16_len()` function in `daily_log_utils.py` handles this correctly.

---

## 7. Building the Archive batchUpdate

### 7a. Request Ordering (within a single week tab)

The full sequence of requests for inserting one or more entries into a week tab:

1. **`insertText`** -- Insert all entry text at index 1 of the week tab
2. **`updateParagraphStyle`** -- Reset all inserted text to NORMAL_TEXT
3. **`updateParagraphStyle`** -- Apply HEADING_1, HEADING_2, HEADING_3 to appropriate paragraphs
4. **`updateTextStyle`** -- Apply heading font (Lexend) to all heading paragraphs
5. **`updateTextStyle`** -- Apply body font (Roboto) to all NORMAL_TEXT paragraphs
6. **`createParagraphBullets`** -- Apply bullet presets to bulleted paragraphs
7. **`updateTextStyle`** -- Apply hyperlinks for richLink substitutions
8. **`insertInlineImage`** and **`insertPerson`** -- Combined into a single list, sorted by index descending

### 7b. insertText Request

```json
{
  "insertText": {
    "location": {"index": 1, "tabId": "<WEEK_TAB_ID>"},
    "text": "<full entry text>"
  }
}
```

- Entries within the same week are concatenated oldest-to-newest in text, but inserted at index 1 so they appear newest-first when the tab already has content
- Actually: the SKILL.md says "insert entries newest-first within each week so they appear newest-to-oldest" -- meaning if archiving multiple entries for the same week, insert the newest entry text first, then the older ones. Since all go at index 1, each push pushes previous content down. Result: oldest entry ends up at the top, newest at the bottom? No -- if you insert newest first at index 1, then insert next-newest at index 1, the next-newest pushes the newest down. So final order top-to-bottom is: oldest, next-oldest, ..., newest. That is chronological order.

**Correction after re-reading:** The SKILL.md says "insert entries newest-first within each week so they appear newest-to-oldest." If entries are inserted newest-first at index 1, the insertion sequence is:
1. Insert Friday's entry at index 1 -> Friday at top
2. Insert Thursday's entry at index 1 -> Thursday at top, Friday pushed down
3. Insert Wednesday's entry at index 1 -> Wednesday at top, Thursday/Friday pushed down

Result: Wednesday (oldest) at top, Friday (newest) at bottom. That's chronological (oldest-to-newest), NOT newest-to-oldest.

To achieve newest-to-oldest (newest at top), entries should be inserted **oldest-first**:
1. Insert Wednesday at index 1 -> Wednesday at top
2. Insert Thursday at index 1 -> Thursday at top, Wednesday pushed down
3. Insert Friday at index 1 -> Friday at top, Thursday/Wednesday pushed down

Result: Friday (newest) at top, Wednesday (oldest) at bottom. This is newest-to-oldest.

**The SKILL.md wording is ambiguous.** The instruction says "insert entries newest-first ... so they appear newest-to-oldest." This likely means: process/insert in newest-first order, which (due to each insertion happening at index 1) results in the oldest ending up at the top. Re-reading more carefully: "insert entries newest-first within each week so they appear newest-to-oldest" -- this seems to be saying the desired result is newest-to-oldest, and the method to achieve it is inserting newest-first. But as shown above, inserting newest-first at index 1 actually produces oldest-to-newest.

**Recommendation for Ryan:** Insert entries **oldest-first** at index 1 so the final order in the tab is newest-to-oldest (matching the main document's order where today's entry is at the top). This matches the main doc pattern.

### 7c. Tab-Aware Ranges

All range-based requests (updateParagraphStyle, updateTextStyle, createParagraphBullets) must include `tabId`:

```json
{
  "updateParagraphStyle": {
    "range": {
      "startIndex": 1,
      "endIndex": 50,
      "tabId": "<WEEK_TAB_ID>"
    },
    "paragraphStyle": {"namedStyleType": "HEADING_1"},
    "fields": "namedStyleType"
  }
}
```

Location-based requests (insertText, insertInlineImage, insertPerson) also include `tabId` in the `location` object.

### 7d. Paragraph Style Requests

Same pattern as `create-daily-log`:

```json
{
  "updateParagraphStyle": {
    "range": {"startIndex": <start>, "endIndex": <end>, "tabId": "<TAB_ID>"},
    "paragraphStyle": {"namedStyleType": "<STYLE>"},
    "fields": "namedStyleType"
  }
}
```

Styles to apply:
- HEADING_1: date heading lines
- HEADING_2: section headings (Task List, Open Tickets:, Thoughts / Ideas:, Notes)
- HEADING_3: Notes sub-section titles

### 7e. Font Style Requests

From `config/doc_styles.json`:
- Heading font: `Lexend`
- Body font: `Roboto`
- Colors: both `null` (no color override currently)

```json
{
  "updateTextStyle": {
    "range": {"startIndex": <start>, "endIndex": <end>, "tabId": "<TAB_ID>"},
    "textStyle": {"weightedFontFamily": {"fontFamily": "Lexend"}},
    "fields": "weightedFontFamily"
  }
}
```

If `colors.headingText` or `colors.bodyText` become non-null, add `foregroundColor` to the textStyle and append `,foregroundColor` to the fields mask.

### 7f. Bullet Requests

```json
{
  "createParagraphBullets": {
    "range": {"startIndex": <start>, "endIndex": <end>, "tabId": "<TAB_ID>"},
    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
  }
}
```

Presets from config:
- `bulletPresets.default` = `"BULLET_DISC_CIRCLE_SQUARE"` (priority items, waiting/blockers)
- `bulletPresets.checkbox` = `"BULLET_CHECKBOX"` (open ticket items)

**Determining bullet type:** The source document's paragraph elements have a `bullet` property when bulleted. However, the bullet preset type is not directly readable from the paragraph. The script must infer the preset:
- Items under "Open Tickets:" section use checkbox preset
- All other bulleted items use default preset

This can be determined by tracking which section each paragraph belongs to during extraction.

### 7g. RichLink Hyperlink Requests

After text insertion and formatting, apply hyperlinks where richLinks were substituted:

```json
{
  "updateTextStyle": {
    "range": {"startIndex": <start>, "endIndex": <end>, "tabId": "<TAB_ID>"},
    "textStyle": {"link": {"url": "<URI>"}},
    "fields": "link"
  }
}
```

Where `<start>` and `<end>` correspond to the title text that replaced the 1-character richLink in the insertText string.

### 7h. Image Insertion Requests

```json
{
  "insertInlineImage": {
    "uri": "<CONTENT_URI>",
    "objectSize": {
      "height": {"magnitude": <MAG>, "unit": "<UNIT>"},
      "width": {"magnitude": <MAG>, "unit": "<UNIT>"}
    },
    "location": {"index": <N>, "tabId": "<TAB_ID>"}
  }
}
```

- `uri` is the `contentUri` from the source document's `inlineObjects`
- `objectSize` preserves original dimensions
- The `contentUri` is a temporary authenticated URL -- it works as long as the source doc was read in the same session

**Error handling:** If a batchUpdate fails due to an image insertion error (e.g., expired `contentUri`), retry the request without the failing `insertInlineImage` requests so that text and formatting are still archived. Report the missing images to the user.

### 7i. Person Insertion Requests

```json
{
  "insertPerson": {
    "personProperties": {"email": "<EMAIL>"},
    "location": {"index": <N>, "tabId": "<TAB_ID>"}
  }
}
```

### 7j. Combining Image and Person Requests

Per the SKILL.md, image and person insertion requests are:
1. Combined into a **single list**
2. Sorted by index **highest to lowest** (descending)
3. Placed **after** all other requests in the batchUpdate

This descending order is critical because each insertion adds 1 character at the specified index, shifting all content after it. Processing highest-index-first ensures earlier insertions don't affect later ones.

### 7k. Size Limits

If the batchUpdate JSON exceeds approximately 500KB, split into multiple batchUpdates -- one per week tab. Each batchUpdate is a separate dry-run/confirm cycle.

---

## 8. Deleting Archived Entries from Main Document

### 8a. Safety Gate

**Only proceed with deletion if Step 7 (archive insertion) completed successfully for ALL entries.** If any archive insertion failed, stop and report the error. Do not delete entries that were not successfully archived.

### 8b. Deletion Request

```json
{
  "deleteContentRange": {
    "range": {
      "startIndex": <START>,
      "endIndex": <END>
    }
  }
}
```

Each entry's range:
- `startIndex`: the HEADING_1 element's `startIndex`
- `endIndex`: the next HEADING_1's `startIndex`, or the body's last `endIndex` for the final entry

### 8c. Deletion Order

Process deletions from **bottom to top** (highest `startIndex` first). This prevents index shifting from affecting subsequent deletions.

```python
entries_to_delete = sorted(old_entries, key=lambda e: e["start_index"], reverse=True)
requests = []
for entry in entries_to_delete:
    requests.append({
        "deleteContentRange": {
            "range": {
                "startIndex": entry["start_index"],
                "endIndex": entry["end_index"],
            }
        }
    })
```

All deletions can be batched into a single batchUpdate:

```
gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<DOC_ID>"}'
```

### 8d. Post-Deletion Cache Update

After successful deletion, invalidate and repopulate the cache:

```python
update_cache(doc_id)  # from daily_log_utils.py
```

This re-reads the main document and repopulates the cache with the remaining entries.

---

## 9. Complete API Call Inventory

### Read Operations (no dry-run)

| # | Purpose | Command |
|---|---------|---------|
| 1 | Read main document | `gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'` |
| 2 | Read archive document with tabs | `gws-safe docs documents get --params '{"documentId":"<ARCHIVE_DOC_ID>","includeTabsContent":true}'` |

### Write Operations (dry-run + nonce confirmation)

| # | Purpose | Command |
|---|---------|---------|
| 3 | Create archive doc (if missing) | `gws-safe docs documents create --json '{"title":"_daily_log_archive"}'` |
| 4 | Create year tabs | `gws-safe docs documents batchUpdate --json '{"requests":[{"addDocumentTab":{...}}]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'` |
| 5 | Create quarter tabs | Same as #4, with `parentTabId` set to year tab ID |
| 6 | Create week tabs | Same as #4, with `parentTabId` set to quarter tab ID |
| 7 | Insert entries into week tabs | `gws-safe docs documents batchUpdate --json '{"requests":[...]}' --params '{"documentId":"<ARCHIVE_DOC_ID>"}'` |
| 8 | Delete entries from main doc | `gws-safe docs documents batchUpdate --json '{"requests":[{"deleteContentRange":{...}}]}' --params '{"documentId":"<DOC_ID>"}'` |

### Post-Operation (no dry-run)

| # | Purpose | Command |
|---|---------|---------|
| 9 | Re-read main doc for cache update | `gws-safe docs documents get --params '{"documentId":"<DOC_ID>"}'` |

**Worst case:** 2 reads + 1 create + 3 tab creations + 1 entry insertion + 1 deletion + 1 cache read = 9 API calls, 6 of which require dry-run/nonce confirmation.

**Typical case** (archive doc and tabs already exist): 2 reads + 0-1 tab creations + 1 entry insertion + 1 deletion + 1 cache read = 5-6 API calls, 1-2 requiring confirmation.

---

## 10. Existing Reusable Code

From `bin/lib/daily_log_utils.py`, the archive script can reuse:

| Function | Purpose |
|----------|---------|
| `read_configs()` | Loads `daily_log.json` and `doc_styles.json` |
| `fetch_doc(doc_id)` | Fetches a Google Doc (but does NOT pass `includeTabsContent` -- may need extension) |
| `parse_doc_entries(doc)` | Parses HEADING_1 entries with sections/subsections |
| `parse_date_from_heading(text)` | Parses "Friday Mar 27, 2026" into "2026-03-27" |
| `execute_batch_update(doc_id, batch_json, auto_confirm)` | Handles dry-run/nonce/confirm flow |
| `update_cache(doc_id)` | Re-reads doc and repopulates cache |
| `utf16_len(text)` | UTF-16 code unit length for index calculation |
| `run_cmd(args, check)` | Subprocess runner with error handling |

### New Functions Needed

| Function | Purpose |
|----------|---------|
| `fetch_doc_with_tabs(doc_id)` | Like `fetch_doc` but passes `includeTabsContent: true` |
| `build_tab_map(tabs)` | Recursively builds `{title: tab_id}` from document tabs |
| `get_week_info(entry_date)` | Computes year/quarter/week/tab-title for a date |
| `extract_entry_for_archive(doc, start, end)` | Extracts text, paragraphs, richLinks, images, persons |
| `build_archive_batch_update(entries, tab_map, style)` | Constructs the full batchUpdate for archive insertion |
| `build_deletion_requests(entries)` | Constructs deleteContentRange requests |

---

## 11. Risks and Caveats

### High Confidence

1. **Tab creation API.** The `addDocumentTab` request is well-documented and already proven in the LLM-orchestrated version of this skill. The tab hierarchy (year > quarter > week) is straightforward.

2. **Text insertion and formatting.** The `insertText` + `updateParagraphStyle` + `updateTextStyle` + `createParagraphBullets` pattern is identical to what `create-daily-log` already does. Proven in production.

3. **Deletion safety.** The bottom-to-top deletion strategy avoids index shifting. The safety gate (only delete after successful archive) prevents data loss.

4. **gws-safe dry-run flow.** The `execute_batch_update()` function handles this reliably.

### Medium Confidence

5. **Image contentUri lifetime.** The `contentUri` from `inlineObjects` is a temporary authenticated URL. It works within the same session but may expire if there is significant delay between reading the source doc and executing the archive batchUpdate. The SKILL.md includes fallback logic: retry without failing image insertions. Mitigation: read the source doc immediately before building the archive batchUpdate.

6. **Week number edge cases.** Entries from before the quarter's first Monday could produce week number 0 or negative. The script should clamp to week 1.

7. **Insertion order for multi-entry weeks.** The SKILL.md wording about "newest-first" insertion order is ambiguous (see analysis in Section 7b). Recommend inserting oldest-first at index 1 to achieve newest-at-top ordering.

### Low Confidence / Open Questions

8. **Bullet preset detection.** The source document does not explicitly identify which bullet preset was used -- only that a paragraph is bulleted. The script must infer the preset from the section context (checkbox for Open Tickets, default for everything else). This is reliable for the known document structure but would break if new bullet types were added.

9. **Mixed element paragraphs.** A paragraph could theoretically contain a mix of textRun, richLink, inlineObject, and person elements. The extraction logic must handle interleaved elements correctly, maintaining insertion order. In practice, daily log entries are unlikely to have complex mixed paragraphs, but the script should handle them correctly.

10. **Archive document tab limit.** Google Docs has a tab limit (exact number undocumented, observed to be around 200). Over multiple years, the number of week tabs could approach this limit. Not an immediate concern but worth noting for long-term use.

---

## 12. Recommended Implementation Approach

1. Build `bin/archive-daily-log` as a standalone Python script
2. Accept `--auto-confirm` flag matching existing scripts
3. Import shared utilities from `bin/lib/daily_log_utils.py`
4. Add new archive-specific functions to a new module or extend `daily_log_utils.py`
5. Process flow:
   a. Read configs
   b. Fetch main document
   c. Identify old entries (before Monday of current week)
   d. If none, exit silently
   e. Fetch archive document with tabs
   f. Build tab map
   g. Compute target tabs for each old entry
   h. Create missing tabs (year, quarter, week) in dependency order
   i. Extract entry content with special element handling
   j. Build and execute archive batchUpdate(s)
   k. Build and execute deletion batchUpdate on main doc
   l. Update cache
   m. Report summary (N entries archived, tabs created, any image failures)
