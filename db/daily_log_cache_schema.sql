-- Daily Log Document Structure Cache
-- Caches section boundaries from the Google Doc so sub-skills
-- can locate their target sections without parsing the full document.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE documents (
    document_id     TEXT PRIMARY KEY,
    revision_id     TEXT NOT NULL,
    fetched_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE entries (
    id              INTEGER PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    entry_date      TEXT NOT NULL,
    heading_text    TEXT NOT NULL,
    start_index     INTEGER NOT NULL,
    end_index       INTEGER NOT NULL,
    UNIQUE (document_id, entry_date)
);

CREATE INDEX idx_entries_document_date ON entries(document_id, entry_date);

CREATE TABLE sections (
    id              INTEGER PRIMARY KEY,
    entry_id        INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    section_type    TEXT NOT NULL CHECK (section_type IN (
                        'task_list', 'open_tickets', 'thoughts_ideas', 'notes'
                    )),
    heading_text    TEXT NOT NULL,
    start_index     INTEGER NOT NULL,
    end_index       INTEGER NOT NULL,
    UNIQUE (entry_id, section_type)
);

CREATE INDEX idx_sections_entry_id ON sections(entry_id);

CREATE TABLE subsections (
    id              INTEGER PRIMARY KEY,
    section_id      INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    heading_text    TEXT NOT NULL,
    start_index     INTEGER NOT NULL,
    end_index       INTEGER NOT NULL,
    sort_order      INTEGER NOT NULL
);

CREATE INDEX idx_subsections_section_id ON subsections(section_id);
