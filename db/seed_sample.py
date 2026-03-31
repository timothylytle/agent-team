#!/usr/bin/env python3
"""Insert sample records into crm.db for testing."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "crm.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

# Companies
cur.executemany(
    "INSERT INTO companies (name, domains, description, health_score, account_tier, industry) VALUES (?, ?, ?, ?, ?, ?)",
    [
        ("Momentum Telecom", '["gomomentum.com"]', "UCaaS and CCaaS provider", "Happy", "Premium", "Telecommunications"),
        ("BACO Properties", '["bacoproperties.com"]', "Commercial real estate management", "Neutral", "Standard", "Real Estate"),
        ("iPFone", '["ipfone.com"]', "Cloud communications platform", "Happy", "Premium", "Telecommunications"),
    ],
)

# Contacts
cur.executemany(
    "INSERT INTO contacts (company_id, name, first_name, last_name, email, phone, job_title) VALUES (?, ?, ?, ?, ?, ?, ?)",
    [
        (1, "Sarah Chen", "Sarah", "Chen", "sarah.chen@gomomentum.com", "555-0101", "VP of Operations"),
        (1, "Mike Torres", "Mike", "Torres", "mike.torres@gomomentum.com", "555-0102", "IT Director"),
        (2, "Lisa Park", "Lisa", "Park", "lisa.park@bacoproperties.com", "555-0201", "Office Manager"),
        (3, "James Wilson", "James", "Wilson", "james.wilson@ipfone.com", "555-0301", "CTO"),
        (3, "Amy Nguyen", "Amy", "Nguyen", "amy.nguyen@ipfone.com", "555-0302", "Support Lead"),
    ],
)

# Tickets
cur.executemany(
    "INSERT INTO tickets (subject, status, priority, company_id, requester_id, source, type) VALUES (?, ?, ?, ?, ?, ?, ?)",
    [
        ("Phone system dropping calls intermittently", 2, 3, 1, 1, 1, "Problem"),
        ("Need additional user licenses", 3, 2, 1, 2, 1, "Request"),
        ("Email forwarding not working", 2, 2, 2, 3, 1, "Problem"),
        ("SIP trunk configuration review", 4, 1, 3, 4, 1, "Request"),
        ("Voicemail to email delay", 2, 3, 3, 5, 1, "Problem"),
    ],
)

# Drive files
cur.executemany(
    "INSERT INTO drive_files (google_file_id, name, mime_type, web_view_link) VALUES (?, ?, ?, ?)",
    [
        ("1aBcDeFgHiJkLmNoPqRsT", "Momentum Telecom - Service Agreement.pdf", "application/pdf", "https://drive.google.com/file/d/1aBcDeFgHiJkLmNoPqRsT/view"),
        ("2uVwXyZaBcDeFgHiJkLmN", "Momentum Telecom - Network Diagram.drawio", "application/xml", "https://drive.google.com/file/d/2uVwXyZaBcDeFgHiJkLmN/view"),
    ],
)

# Company-file links (both files linked to Momentum Telecom)
cur.executemany(
    "INSERT INTO company_files (company_id, file_id) VALUES (?, ?)",
    [
        (1, 1),
        (1, 2),
    ],
)

conn.commit()
conn.close()
print(f"Sample data inserted into {DB_PATH}")
