# Global Document Style Guide

## Summary

Create a centralized style config file (`config/doc_styles.json`) that defines fonts, colors, and formatting for all Google Docs created or updated by skills. Refactor all skills to read from this config instead of hardcoding style values.

## Config File

**Path:** `config/doc_styles.json`
**Committed to repo:** Yes (no secrets or resource IDs)

### Schema

```json
{
  "fonts": {
    "heading": "Lexend",
    "body": "Roboto"
  },
  "colors": {
    "headingText": null,
    "bodyText": null,
    "background": null
  },
  "bulletPresets": {
    "default": "BULLET_DISC_CIRCLE_SQUARE",
    "checkbox": "BULLET_CHECKBOX"
  }
}
```

- `null` values mean "don't apply" (use Google Docs defaults)
- Colors use Google Docs RGB format when set: `{"red": 0.0, "green": 0.0, "blue": 0.0}` (each 0.0-1.0)

## Skills to Refactor

### 1. daily-log/SKILL.md
- **Step 3c** (create entry): Replace hardcoded "Lexend"/"Roboto" with config reference
- **Step 5d** (archive): Replace hardcoded "Lexend"/"Roboto" with config reference

### 2. open-tickets/SKILL.md
- **Step 6** (update tickets section): Replace hardcoded "Roboto" with config reference

### 3. task-list/SKILL.md
- **Step 6** (update task list): Replace hardcoded "Lexend"/"Roboto" with config reference

### 4. support-notes/SKILL.md
- **Step 9b** (populate new doc): ADD font styling (currently missing — gap fix)
- **Step 9e-vii** (inject tagged notes): Replace hardcoded "Lexend"/"Roboto" with config reference

## Refactoring Pattern

Each skill that applies styles needs:

1. A new constant in the Constants section:
   ```
   - **Style config:** `/home/timothylytle/agent-team/config/doc_styles.json`
   ```

2. An early step (or addition to an existing step) to read the config:
   ```
   Read the style config at `config/doc_styles.json`. Use these values for all document formatting:
   - Heading font: `fonts.heading`
   - Body font: `fonts.body`
   - Heading text color: `colors.headingText` (skip if null)
   - Body text color: `colors.bodyText` (skip if null)
   - Default bullet preset: `bulletPresets.default`
   - Checkbox bullet preset: `bulletPresets.checkbox`
   ```

3. Replace every hardcoded font name and bullet preset with a reference to the config value.

4. Add conditional color application: if a color value is not null, include `foregroundColor` in the `updateTextStyle` request.
