-- CRM Schema: tracks companies, contacts, tickets, and drive files
-- SQLite with ISO 8601 TEXT dates, JSON arrays as TEXT, FreshDesk IDs stored separately

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- Companies
-- Central entity linking contacts, tickets, and files.
-- Can originate from FreshDesk or be created independently.
-- ============================================================
CREATE TABLE companies (
    id              INTEGER PRIMARY KEY,
    freshdesk_id    INTEGER UNIQUE,         -- FreshDesk company ID (nullable, large int)
    name            TEXT NOT NULL,
    description     TEXT,
    domains         TEXT,                   -- JSON array of email domains, e.g. ["acme.com","acme.org"]
    health_score    TEXT,
    account_tier    TEXT,
    vip             INTEGER DEFAULT 0 CHECK (vip IN (0, 1)),
    industry        TEXT,
    renewal_date    TEXT,                   -- ISO 8601
    custom_fields   TEXT,                   -- JSON object
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_companies_freshdesk_id ON companies(freshdesk_id) WHERE freshdesk_id IS NOT NULL;
CREATE INDEX idx_companies_name ON companies(name);

-- ============================================================
-- Contacts
-- People associated with companies. FreshDesk is the primary
-- source but contacts can exist without a FreshDesk record.
-- ============================================================
CREATE TABLE contacts (
    id              INTEGER PRIMARY KEY,
    freshdesk_id    INTEGER UNIQUE,         -- FreshDesk contact ID (nullable, large int)
    company_id      INTEGER REFERENCES companies(id),
    name            TEXT,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    phone           TEXT,
    mobile          TEXT,
    job_title       TEXT,
    address         TEXT,
    active          INTEGER DEFAULT 1 CHECK (active IN (0, 1)),
    vip             INTEGER DEFAULT 0 CHECK (vip IN (0, 1)),
    tags            TEXT,                   -- JSON array
    other_emails    TEXT,                   -- JSON array
    preferred_source TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_contacts_freshdesk_id ON contacts(freshdesk_id) WHERE freshdesk_id IS NOT NULL;
CREATE INDEX idx_contacts_company_id ON contacts(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX idx_contacts_email ON contacts(email) WHERE email IS NOT NULL;

-- ============================================================
-- Ticket statuses
-- Lookup table for FreshDesk ticket status codes.
-- ============================================================
CREATE TABLE ticket_statuses (
    status_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);

INSERT INTO ticket_statuses (status_id, name) VALUES
    (2, 'Open'),
    (3, 'Pending'),
    (4, 'Resolved'),
    (5, 'Closed'),
    (6, 'Custom 1'),
    (7, 'Custom 2'),
    (9, 'Scheduled');

-- ============================================================
-- Tickets
-- Support tickets from FreshDesk. Linked to companies and
-- contacts where available.
-- ============================================================
CREATE TABLE tickets (
    id              INTEGER PRIMARY KEY,
    freshdesk_id    INTEGER UNIQUE,
    subject         TEXT,
    status          INTEGER REFERENCES ticket_statuses(status_id),
    priority        INTEGER CHECK (priority BETWEEN 1 AND 4),  -- 1=Low, 2=Med, 3=High, 4=Urgent
    source          INTEGER,                                    -- 1=Email, etc.
    type            TEXT,
    company_id      INTEGER REFERENCES companies(id),
    requester_id    INTEGER REFERENCES contacts(id),
    responder_id    INTEGER,
    group_id        INTEGER,
    product_id      INTEGER,
    tags            TEXT,                   -- JSON array
    custom_fields   TEXT,                   -- JSON object
    due_by          TEXT,                   -- ISO 8601
    is_escalated    INTEGER DEFAULT 0 CHECK (is_escalated IN (0, 1)),
    resolved_at     TEXT,                   -- ISO 8601, from FreshDesk stats
    closed_at       TEXT,                   -- ISO 8601, from FreshDesk stats
    resolution_summary TEXT,                -- LLM-generated 2-3 sentence summary
    support_doc_id      TEXT,                   -- Google Drive file ID of support note doc
    support_doc_url     TEXT,                   -- Web view URL of support note doc
    freshdesk_note_id   INTEGER,               -- FreshDesk conversation ID of the private note
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_tickets_freshdesk_id ON tickets(freshdesk_id) WHERE freshdesk_id IS NOT NULL;
CREATE INDEX idx_tickets_company_id ON tickets(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX idx_tickets_requester_id ON tickets(requester_id) WHERE requester_id IS NOT NULL;
CREATE INDEX idx_tickets_status ON tickets(status);

-- ============================================================
-- Drive files
-- Google Drive file metadata. Linked to companies via the
-- company_files junction table.
-- ============================================================
CREATE TABLE drive_files (
    id              INTEGER PRIMARY KEY,
    google_file_id  TEXT UNIQUE NOT NULL,   -- Google Drive file ID (string)
    name            TEXT,
    mime_type       TEXT,
    web_view_link   TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_drive_files_google_id ON drive_files(google_file_id);

-- ============================================================
-- Company-file links
-- Junction table for many-to-many relationship between
-- companies and drive files. Supports manual linking.
-- ============================================================
CREATE TABLE company_files (
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    file_id     INTEGER NOT NULL REFERENCES drive_files(id),
    linked_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (company_id, file_id)
);

CREATE INDEX idx_company_files_file_id ON company_files(file_id);

-- ============================================================
-- Meetings
-- Calendar events linked to support tickets, contacts, and
-- companies. Google Calendar is the source of truth.
-- ============================================================
CREATE TABLE meetings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    google_event_id     TEXT UNIQUE NOT NULL,   -- Google Calendar event ID
    ticket_id           INTEGER REFERENCES tickets(id),
    contact_id          INTEGER REFERENCES contacts(id),
    company_id          INTEGER REFERENCES companies(id),
    summary             TEXT,                   -- Event title
    start_time          TEXT,                   -- ISO 8601
    end_time            TEXT,                   -- ISO 8601
    html_link           TEXT,                   -- Google Calendar web link
    freshdesk_ticket_id INTEGER,                -- FreshDesk ticket ID
    freshdesk_note_id   INTEGER,                -- FreshDesk note/conversation ID
    color_id            TEXT,                   -- Calendar event colorId
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_meetings_google_event_id ON meetings(google_event_id);
CREATE INDEX idx_meetings_ticket_id ON meetings(ticket_id) WHERE ticket_id IS NOT NULL;

-- ============================================================
-- Emails
-- Email records from the daily log's Email section. Linked to
-- contacts and companies where the sender is known in the CRM.
-- ============================================================
CREATE TABLE emails (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id    TEXT UNIQUE NOT NULL,
    contact_id          INTEGER REFERENCES contacts(id),
    company_id          INTEGER REFERENCES companies(id),
    sender_email        TEXT NOT NULL,
    sender_name         TEXT,
    subject             TEXT,
    gmail_url           TEXT,
    received_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_emails_gmail_message_id ON emails(gmail_message_id);
CREATE INDEX idx_emails_contact_id ON emails(contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX idx_emails_company_id ON emails(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX idx_emails_received_at ON emails(received_at) WHERE received_at IS NOT NULL;

-- ============================================================
-- Project statuses
-- Lookup table for project status codes.
-- ============================================================
CREATE TABLE project_statuses (
    status_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);

INSERT INTO project_statuses (status_id, name) VALUES
    (1, 'Scoping'),
    (2, 'Researching'),
    (3, 'Implementing'),
    (4, 'Complete');

-- ============================================================
-- Projects
-- Development projects linked to companies. Tracked with
-- Google Docs and tagged by priority and status.
-- ============================================================
CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    project_code    TEXT UNIQUE NOT NULL,
    status_id       INTEGER REFERENCES project_statuses(status_id),
    company_id      INTEGER REFERENCES companies(id),
    summary         TEXT,
    google_doc_id   TEXT,
    google_doc_url  TEXT,
    priority        INTEGER CHECK (priority BETWEEN 1 AND 4),
    tags            TEXT,                   -- JSON array
    start_date      TEXT,                   -- ISO 8601
    due_date        TEXT,                   -- ISO 8601
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_projects_project_code ON projects(project_code);
CREATE INDEX idx_projects_company_id ON projects(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX idx_projects_status_id ON projects(status_id) WHERE status_id IS NOT NULL;

-- ============================================================
-- Ideas
-- ============================================================

CREATE TABLE idea_statuses (
    status_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);

INSERT INTO idea_statuses (status_id, name) VALUES
    (1, 'New'),
    (2, 'Analyzed'),
    (3, 'Promoted'),
    (4, 'Dismissed');

CREATE TABLE ideas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    source_text     TEXT,
    source_url      TEXT,
    analysis        TEXT,
    status_id       INTEGER REFERENCES idea_statuses(status_id) DEFAULT 1,
    project_id      INTEGER REFERENCES projects(id),
    company_id      INTEGER REFERENCES companies(id),
    chat_message_id TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_ideas_status_id ON ideas(status_id) WHERE status_id IS NOT NULL;
CREATE INDEX idx_ideas_project_id ON ideas(project_id) WHERE project_id IS NOT NULL;

-- ============================================================
-- Tasks
-- Google Tasks tracked in the CRM. Each task belongs to a
-- single task list (in_progress, waiting, backlog). Google
-- Tasks is the source of truth for task content.
-- ============================================================
CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    google_task_id  TEXT UNIQUE NOT NULL,
    task_list       TEXT NOT NULL CHECK (task_list IN ('in_progress', 'waiting', 'backlog', 'todo')),
    title           TEXT NOT NULL,
    notes           TEXT,
    status          TEXT NOT NULL DEFAULT 'needsAction' CHECK (status IN ('needsAction', 'completed')),
    due_date        TEXT,                   -- ISO 8601
    completed_at    TEXT,                   -- ISO 8601
    parent_task_id  TEXT,                   -- Google Tasks parent ID for subtasks
    position        TEXT,                   -- Google Tasks ordering (opaque string)
    company_id      INTEGER REFERENCES companies(id),
    ticket_id       INTEGER REFERENCES tickets(id),
    project_id      INTEGER REFERENCES projects(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_tasks_google_task_id ON tasks(google_task_id);
CREATE INDEX idx_tasks_task_list ON tasks(task_list);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_company_id ON tasks(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX idx_tasks_ticket_id ON tasks(ticket_id) WHERE ticket_id IS NOT NULL;
CREATE INDEX idx_tasks_project_id ON tasks(project_id) WHERE project_id IS NOT NULL;
