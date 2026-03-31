#!/usr/bin/env python3
"""Simple CRM web viewer using Python's built-in http.server."""

import json
import os
import re
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "crm.db")

PRIORITY_LABELS = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def layout(title, content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} - CRM</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">
    <style>body{{max-width:900px;margin:40px auto;padding:0 20px;font-family:sans-serif}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #ddd}}nav{{margin-bottom:20px}}a{{color:#0366d6}}</style>
</head>
<body>
    <nav>
        <a href="/">Dashboard</a> |
        <a href="/companies">Companies</a> |
        <a href="/contacts">Contacts</a> |
        <a href="/tickets">Tickets</a>
    </nav>
    <h1>{title}</h1>
    {content}
</body>
</html>"""


def page_dashboard():
    db = get_db()
    companies = db.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
    contacts = db.execute("SELECT COUNT(*) c FROM contacts").fetchone()["c"]
    tickets = db.execute("SELECT COUNT(*) c FROM tickets").fetchone()["c"]
    files = db.execute("SELECT COUNT(*) c FROM drive_files").fetchone()["c"]
    db.close()
    content = f"""
    <table>
        <tr><td>Companies</td><td>{companies}</td></tr>
        <tr><td>Contacts</td><td>{contacts}</td></tr>
        <tr><td>Tickets</td><td>{tickets}</td></tr>
        <tr><td>Drive Files</td><td>{files}</td></tr>
    </table>"""
    return layout("Dashboard", content)


def page_companies():
    db = get_db()
    rows = db.execute("""
        SELECT c.id, c.name, c.domains,
            (SELECT COUNT(*) FROM contacts WHERE company_id = c.id) AS contact_count,
            (SELECT COUNT(*) FROM tickets WHERE company_id = c.id) AS ticket_count
        FROM companies c ORDER BY c.name
    """).fetchall()
    db.close()
    table_rows = ""
    for r in rows:
        domains = ", ".join(json.loads(r["domains"])) if r["domains"] else ""
        table_rows += f'<tr><td><a href="/companies/{r["id"]}">{r["name"]}</a></td><td>{domains}</td><td>{r["contact_count"]}</td><td>{r["ticket_count"]}</td></tr>\n'
    content = f"""
    <table>
        <thead><tr><th>Name</th><th>Domains</th><th>Contacts</th><th>Tickets</th></tr></thead>
        <tbody>{table_rows}</tbody>
    </table>"""
    return layout("Companies", content)


def page_company_detail(company_id):
    db = get_db()
    company = db.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not company:
        db.close()
        return None
    contacts = db.execute("SELECT id, name, email, job_title FROM contacts WHERE company_id = ? ORDER BY name", (company_id,)).fetchall()
    tickets = db.execute("""
        SELECT t.id, t.subject, ts.name AS status_name, t.priority
        FROM tickets t LEFT JOIN ticket_statuses ts ON t.status = ts.status_id
        WHERE t.company_id = ? ORDER BY t.created_at DESC
    """, (company_id,)).fetchall()
    files = db.execute("""
        SELECT df.name, df.mime_type, df.web_view_link
        FROM drive_files df JOIN company_files cf ON df.id = cf.file_id
        WHERE cf.company_id = ? ORDER BY df.name
    """, (company_id,)).fetchall()
    db.close()

    domains = ", ".join(json.loads(company["domains"])) if company["domains"] else "None"
    info = f"""
    <dl>
        <dt>Description</dt><dd>{company["description"] or "N/A"}</dd>
        <dt>Domains</dt><dd>{domains}</dd>
        <dt>Health Score</dt><dd>{company["health_score"] or "N/A"}</dd>
        <dt>Account Tier</dt><dd>{company["account_tier"] or "N/A"}</dd>
        <dt>Industry</dt><dd>{company["industry"] or "N/A"}</dd>
    </dl>"""

    contact_rows = ""
    for c in contacts:
        contact_rows += f'<tr><td>{c["name"]}</td><td>{c["email"] or ""}</td><td>{c["job_title"] or ""}</td></tr>\n'
    contact_table = f"""
    <h2>Contacts ({len(contacts)})</h2>
    <table>
        <thead><tr><th>Name</th><th>Email</th><th>Title</th></tr></thead>
        <tbody>{contact_rows}</tbody>
    </table>""" if contacts else "<h2>Contacts (0)</h2><p>No contacts.</p>"

    ticket_rows = ""
    for t in tickets:
        priority = PRIORITY_LABELS.get(t["priority"], "")
        ticket_rows += f'<tr><td><a href="/tickets/{t["id"]}">{t["subject"]}</a></td><td>{t["status_name"] or ""}</td><td>{priority}</td></tr>\n'
    ticket_table = f"""
    <h2>Tickets ({len(tickets)})</h2>
    <table>
        <thead><tr><th>Subject</th><th>Status</th><th>Priority</th></tr></thead>
        <tbody>{ticket_rows}</tbody>
    </table>""" if tickets else "<h2>Tickets (0)</h2><p>No tickets.</p>"

    file_rows = ""
    for f in files:
        link = f'<a href="{f["web_view_link"]}">{f["name"]}</a>' if f["web_view_link"] else f["name"]
        file_rows += f'<tr><td>{link}</td><td>{f["mime_type"] or ""}</td></tr>\n'
    file_table = f"""
    <h2>Files ({len(files)})</h2>
    <table>
        <thead><tr><th>Name</th><th>Type</th></tr></thead>
        <tbody>{file_rows}</tbody>
    </table>""" if files else "<h2>Files (0)</h2><p>No files linked.</p>"

    return layout(company["name"], info + contact_table + ticket_table + file_table)


def page_contacts():
    db = get_db()
    rows = db.execute("""
        SELECT co.id, co.name, co.email, c.name AS company_name,
            (SELECT COUNT(*) FROM tickets WHERE requester_id = co.id) AS ticket_count
        FROM contacts co LEFT JOIN companies c ON co.company_id = c.id
        ORDER BY co.name
    """).fetchall()
    db.close()
    table_rows = ""
    for r in rows:
        table_rows += f'<tr><td>{r["name"]}</td><td>{r["email"] or ""}</td><td>{r["company_name"] or ""}</td><td>{r["ticket_count"]}</td></tr>\n'
    content = f"""
    <table>
        <thead><tr><th>Name</th><th>Email</th><th>Company</th><th>Tickets</th></tr></thead>
        <tbody>{table_rows}</tbody>
    </table>"""
    return layout("Contacts", content)


def page_tickets():
    db = get_db()
    rows = db.execute("""
        SELECT t.id, t.subject, ts.name AS status_name, co.name AS requester_name, c.name AS company_name
        FROM tickets t
        LEFT JOIN ticket_statuses ts ON t.status = ts.status_id
        LEFT JOIN contacts co ON t.requester_id = co.id
        LEFT JOIN companies c ON t.company_id = c.id
        ORDER BY t.created_at DESC
    """).fetchall()
    db.close()
    table_rows = ""
    for r in rows:
        table_rows += f'<tr><td><a href="/tickets/{r["id"]}">{r["subject"]}</a></td><td>{r["status_name"] or ""}</td><td>{r["requester_name"] or ""}</td><td>{r["company_name"] or ""}</td></tr>\n'
    content = f"""
    <table>
        <thead><tr><th>Subject</th><th>Status</th><th>Requester</th><th>Company</th></tr></thead>
        <tbody>{table_rows}</tbody>
    </table>"""
    return layout("Tickets", content)


def page_ticket_detail(ticket_id):
    db = get_db()
    ticket = db.execute("""
        SELECT t.*, ts.name AS status_name, co.name AS requester_name, co.email AS requester_email,
            c.name AS company_name
        FROM tickets t
        LEFT JOIN ticket_statuses ts ON t.status = ts.status_id
        LEFT JOIN contacts co ON t.requester_id = co.id
        LEFT JOIN companies c ON t.company_id = c.id
        WHERE t.id = ?
    """, (ticket_id,)).fetchone()
    db.close()
    if not ticket:
        return None

    priority = PRIORITY_LABELS.get(ticket["priority"], "N/A")
    content = f"""
    <dl>
        <dt>Subject</dt><dd>{ticket["subject"] or "N/A"}</dd>
        <dt>Status</dt><dd>{ticket["status_name"] or "N/A"}</dd>
        <dt>Priority</dt><dd>{priority}</dd>
        <dt>Type</dt><dd>{ticket["type"] or "N/A"}</dd>
        <dt>Company</dt><dd>{ticket["company_name"] or "N/A"}</dd>
        <dt>Requester</dt><dd>{ticket["requester_name"] or "N/A"} ({ticket["requester_email"] or "N/A"})</dd>
        <dt>Created</dt><dd>{ticket["created_at"]}</dd>
        <dt>Updated</dt><dd>{ticket["updated_at"]}</dd>
        <dt>Due By</dt><dd>{ticket["due_by"] or "N/A"}</dd>
        <dt>Escalated</dt><dd>{"Yes" if ticket["is_escalated"] else "No"}</dd>
    </dl>"""
    return layout(f"Ticket #{ticket['id']}: {ticket['subject']}", content)


class CRMHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        # Route matching
        html = None
        status = 200

        if path == "/":
            html = page_dashboard()
        elif path == "/companies":
            html = page_companies()
        elif m := re.match(r"^/companies/(\d+)$", path):
            html = page_company_detail(int(m.group(1)))
            if html is None:
                status = 404
                html = layout("Not Found", "<p>Company not found.</p>")
        elif path == "/contacts":
            html = page_contacts()
        elif path == "/tickets":
            html = page_tickets()
        elif m := re.match(r"^/tickets/(\d+)$", path):
            html = page_ticket_detail(int(m.group(1)))
            if html is None:
                status = 404
                html = layout("Not Found", "<p>Ticket not found.</p>")
        else:
            status = 404
            html = layout("Not Found", "<p>Page not found.</p>")

        encoded = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except BrokenPipeError:
            pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), CRMHandler)
    print("CRM server running at http://localhost:8080")
    server.serve_forever()
