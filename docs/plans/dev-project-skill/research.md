# Dev Project Skill - Document Structure Research

## Objective

Analyze two existing Google Docs project documents to identify the common template structure, section types, content patterns, and workflow stages. This research will inform the creation of a new skill for managing development projects.

**Documents analyzed:**
- Document 1: `2026q1-MSTeams-queue-testing` (ID: `1Q7ATHUXBSoOWnVhnFK9-ZLFyRus21xDAOWCefj9cCh4`)
- Document 2: `2026q1_ansible-miarec-tls` (ID: `1JU-NkJ_N15anJiRcUlBJ2jhPCOx7kzhT1cuZlMjSC3o`)

---

## Findings

### 1. Common Document Template Structure

Both documents share an identical top-level structure. The document title is "Scope" (styled as TITLE), followed by a standard subtitle: *"This document outlines the scope, objectives, deliverables, and constraints for the project."*

#### Metadata Table (Present in Both)

A 4-row, 2-column table at the top of every document:

| Field | Example Values |
|-------|---------------|
| **Project Title** | `2026q1-MSTeams-queue-testing`, `2026q1_ansible-miarec-tls` |
| **Project Code** | `msteams_queue-rec`, `ansible-miarec-tls` |
| **Author** | Timothy Lytle (as a Google Docs @mention / person chip) |
| **Issue Date** | (empty in both documents) |

**Naming convention observed:**
- Project Title format: `{year}q{quarter}-{descriptive-name}` or `{year}q{quarter}_{descriptive-name}` (inconsistent separator: hyphen vs underscore)
- Project Code format: shorter identifier, sometimes matching the descriptive name portion

#### Section Hierarchy (Full Template)

The complete section hierarchy observed across both documents (HEADING_1 = H1, HEADING_2 = H2):

```
TITLE: Scope
  H1: Overview
    H2: Problem Statement
    H2: Desired Outcome
  H1: Scope
    H2: In Scope
    H2: Out of Scope
    H2: Constraints / Assumptions
  H1: Current State
  H1: Success Criteria
  H1: References
  H1: Deliverables / Milestones
  H1: Implementation Log
```

**Confidence: HIGH** -- Document 2 contains all sections. Document 1 contains a subset (Overview, References, Deliverables). The full template is Document 2's structure.

### 2. Section-by-Section Content Analysis

#### Overview > Problem Statement
- **Content type:** Free-text description of the problem being solved
- **Style:** Narrative, can be rough/informal
- **Example (Doc 1):** "Call Queue Compliance Recording for Microsoft Teams with Conference mode, It is unknown if this will work with miarec currently"
- **Example (Doc 2):** "Ansible based installation playbook needs to be updated for new improvements in submodules for TLS support"

#### Overview > Desired Outcome
- **Content type:** Bulleted list of what success looks like
- **Style:** Short declarative statements
- **Example (Doc 2):**
  - Playbooks successfully install miarec applications with TLS (when variable defined)
  - Molecule testing that deploys entire miarec suite with TLS
  - MakeFile that can be used to generate all needed TLS certificates when called

#### Scope > In Scope
- **Content type:** Brief statement of what is included
- **Example:** "updating/testing ansible-miarec playbook"

#### Scope > Out of Scope
- **Content type:** Brief statement of what is excluded
- **Example:** "updating submodules"

#### Scope > Constraints / Assumptions
- **Content type:** Any known constraints
- **Example:** "none" (can be minimal)

#### Current State
- **Content type:** Structured bullet list with sub-categories:
  - Existing tools / systems:
  - Known pain points:
  - Gaps or limitations:
- **Observation:** These are often left partially empty as placeholder prompts

#### Success Criteria
- **Content type:** Structured bullet list with sub-categories:
  - Functional Success:
  - Operational Success:
  - Security / Compliance Success:
- **Observation:** Also often left as placeholder prompts (values empty in Doc 2)

#### References
- **Content type:** Categorized link list
- **Sub-categories observed:** Docs, Blog posts, GitHub repos
- **Style:** Bulleted with URLs, sometimes with links to FreshDesk tickets

#### Deliverables / Milestones
- **Content type:** Structured task list using bracket-prefix notation
- **Bracket notation format:** `[project-code] task description` or `[project-code-phase] subtask`
- **Nesting:** Uses indentation for sub-tasks
- **Example (Doc 2):**
  ```
  - [ansible-miarec-tls] scope project
  - [ansible-miarec-tls] implement
    - [ansible-miarec-tls-implement] Create Spec
    - [ansible-miarec-tls-implement] Create Plan
    - [ansible-miarec-tls-implement] phase 1 - variables for tls and makefile
    - [ansible-miarec-tls-implement] phase 2 - update playbooks
    - [ansible-miarec-tls-implement] phase 3 - molecule TLS test
  - [ansible-miarec-tls-testing] test new deployment (in AWS)
  - [ansible-miarec-tls-testing] test upgrade deployment (in AWS)
  ```
- **Key observation:** The bracket prefix acts as a task code / work breakdown structure (WBS) identifier. Parent tasks use the project code; sub-tasks append a phase suffix.

#### Implementation Log
- **Content type:** Chronological work journal / lab notebook
- **Structure:** H3 headings appear to be date-based (though the heading text is empty in the extracted content -- likely dates rendered differently or styled without text in the heading)
- **Entry style:** Stream-of-consciousness narrative mixed with:
  - Terminal/CLI output (commands and results)
  - Screenshots (inline images)
  - AI agent session summaries (structured blocks with "What Changed", "Root Cause Analysis", "Files Affected", "Tests Run", "Non-Resolved Issues", "Next Steps")
  - Config file snippets
  - Test results (pass/fail output)
  - Debugging notes and troubleshooting traces
- **Tone:** Very informal, includes frustration ("codex is trippin...", "chatgpt is full of shit", "you have got to be shitting me..."), victory ("great success!", "vundava!", "Hell yeah"), and real-time thinking

### 3. How Research Topics and Questions Are Structured

Research does not have a dedicated section. Instead, research activity appears in two locations:

1. **References section** -- Links to external documentation, blog posts, tickets, and repos that informed the project
2. **Implementation Log** -- Research happens inline during implementation. When a question arises (e.g., "does package include tls support?"), the answer is recorded immediately ("according to chatgpt it does, just need to specify in config file") and then validated through testing

**Research workflow pattern observed:**
1. Encounter a question during implementation
2. Look up the answer (ChatGPT, docs, direct testing)
3. Record the question and answer inline in the log
4. If the answer was wrong, note that too ("chatgpt is full of shit")
5. Record the actual validated finding

### 4. Differences Between the Two Documents

| Aspect | Doc 1 (MSTeams) | Doc 2 (Ansible TLS) |
|--------|-----------------|---------------------|
| **Completeness** | Minimal -- only Overview, References, Deliverables populated | Extensive -- all template sections present, massive Implementation Log |
| **Sections present** | 3 of 7 H1 sections | All 7 H1 sections |
| **Implementation Log** | Absent | ~3,500 lines of detailed work journal |
| **Scope section** | Missing entirely | Present with In Scope, Out of Scope, Constraints |
| **Current State** | Missing | Present (with empty sub-items) |
| **Success Criteria** | Missing | Present (with empty sub-items) |
| **Project stage** | Early scoping / planning | Deep into implementation and testing |
| **Title separator** | Hyphen (`-`) | Underscore (`_`) |
| **Deliverable granularity** | High-level (5 items) | Detailed phases (8 items with nesting) |

**Interpretation:** Document 1 represents an early-stage project (just scoped, not yet started). Document 2 represents a mature project deep into implementation and testing. The template sections that are empty or missing in Doc 1 would presumably be filled in as the project progresses.

### 5. Project Document Lifecycle Stages

Based on the evidence from both documents, a project document progresses through these stages:

#### Stage 1: Initial Scoping
- **Sections populated:** Metadata table, Problem Statement, Desired Outcome, References
- **Sections empty/absent:** Scope boundaries, Current State, Success Criteria, Deliverables (rough), Implementation Log
- **Example:** Document 1 is at this stage

#### Stage 2: Scope Definition
- **Sections populated:** In Scope, Out of Scope, Constraints/Assumptions added
- **Current State and Success Criteria:** Placeholders created with sub-category prompts, possibly still empty
- **Deliverables:** Fleshed out with phased task list and bracket codes

#### Stage 3: Active Implementation
- **Implementation Log:** Begins accumulating entries
- **Entry pattern per session:**
  1. Date heading (H3)
  2. Narrative of what was done
  3. Commands run and their output
  4. AI agent summaries (structured blocks)
  5. Screenshots of results
  6. Debugging notes when things fail

#### Stage 4: Testing / Validation
- **Implementation Log:** Contains test execution output, verification results, pass/fail summaries
- **Sub-headings (H4)** appear for test categories (e.g., "ubuntu2404", "rhel9", "Install in AWS")
- **Document 2 is at this stage** -- testing across platforms and environments

#### Stage 5: Completion
- **Not observed** in either document, but would presumably involve:
  - All deliverable items checked off
  - Final test results recorded
  - PR merged

### 6. Document Formatting and Style Details

- **Font:** Urbanist (primary font for headings and body)
- **Heading styles:** Standard Google Docs named styles (TITLE, HEADING_1 through HEADING_4)
- **Line spacing:** 115% for normal text
- **Table style:** Simple 2-column table for metadata, no special border styling
- **Code/terminal output:** Appears to be pasted as plain text (not code-formatted)
- **Images:** Inline images (screenshots of CI results, error messages, terminal output)
- **Links:** Mix of raw URLs and Google Docs @mentions

### 7. AI Agent Integration Pattern

Document 2 contains structured summaries from AI coding agents (Codex). These follow a consistent format:

```
What Changed
  - [bullet points of changes with file paths]

Root Cause Analysis
  - [explanation of why something failed]

Files Affected
  - [list of files]

Tests Run
  - [checkmark or X] test command (log location)

Non-Resolved Issues
  - [warning] description

Next Steps
  1. [numbered list]
```

These appear to be pasted directly from agent session outputs into the Implementation Log.

---

## Recommendations

1. **Template creation:** The skill should be able to create a new project document from a standard template containing all 7 H1 sections plus the metadata table. Empty sections should include their sub-category prompts (e.g., "Existing tools / systems:", "Functional Success:").

2. **Bracket task notation:** The `[project-code]` prefix system for deliverables is a key pattern. The skill should understand and generate this notation, using the Project Code from the metadata table.

3. **Implementation Log management:** The Implementation Log is the most-used section and the most complex. The skill should be able to append dated entries to this section. Entries may include plain text, structured agent summaries, and references to commands/output.

4. **Stage awareness:** The skill should recognize what stage a project is at based on which sections are populated, and prompt for missing sections appropriate to the current stage.

5. **Project naming convention:** Standardize on one separator (suggest underscore based on Doc 2 being the more complete example): `{year}q{quarter}_{descriptive-name}`.

---

## Risks / Caveats

- **Sample size:** Only two documents analyzed. There may be variations in other project documents not represented here.
- **Implementation Log complexity:** The log contains extremely varied content types (narrative, code, structured summaries, images). Programmatically generating or parsing this section will require flexible handling.
- **Empty sections:** Several template sections (Current State, Success Criteria) appear to be frequently left as placeholders. The skill should not enforce completion of every section.
- **Image content:** Multiple screenshots are embedded in Doc 2. The skill cannot generate or read these, so image-dependent context will be lost.
- **Date headings:** The H3 headings in the Implementation Log appear empty in the extracted content. They may use a date format that does not render as plain text, or they may literally be blank (with dates implied by document edit history). This needs clarification from Timothy.
