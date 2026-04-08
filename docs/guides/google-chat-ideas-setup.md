# Google Chat Ideas Space Setup

How to set up a dedicated Google Chat space for capturing ideas, links, and quick notes from any device.

---

## Step 1: Create the Space

1. Open [Google Chat](https://chat.google.com).

2. Click **New chat > Create a space**.

3. Name it something clear like `Ideas`.

4. Leave it as just you — no other members needed. This is a personal capture space.

5. Click **Create**.

---

## Step 2: Find the Space ID

The space ID is needed for agent configuration.

1. Run:
   ```bash
   gws chat spaces list
   ```

2. Find the space named `Ideas` in the output.

3. Note the `name` field — it will look like `spaces/XXXXXXX`. This is the space ID.

---

## Step 3: Configure the Skill

The space ID will be added to the skill's config file during skill implementation. No action needed here yet.

---

## Step 4: Usage

Send quick messages to the Ideas space from Google Chat (mobile or desktop) with:

- Idea titles or short descriptions
- Links to articles, tools, or references
- Questions to research later

The agent will read messages from this space to process and organize them.
