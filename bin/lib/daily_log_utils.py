"""Shared utilities for daily log scripts.

Contains common functions used by create-daily-log, update-task-list,
and update-open-tickets: config loading, subprocess execution, cache
database access, document parsing, batchUpdate execution, and index
calculation.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Paths ---

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "daily_log.json"
STYLE_CONFIG_PATH = REPO_ROOT / "config" / "doc_styles.json"
CACHE_DB_PATH = REPO_ROOT / "db" / "daily_log_cache.db"
CRM_DB_PATH = REPO_ROOT / "db" / "crm.db"
CACHE_SCHEMA_PATH = REPO_ROOT / "db" / "daily_log_cache_schema.sql"
GWS_SAFE = REPO_ROOT / "bin" / "gws-safe"
FRESHDESK_SAFE = REPO_ROOT / "bin" / "freshdesk-safe"
CRM_SAFE = REPO_ROOT / "bin" / "crm-safe"
DAILY_LOG_CACHE = REPO_ROOT / "bin" / "daily-log-cache"

FRESHDESK_TICKET_URL = "https://miarec.freshdesk.com/a/tickets/{}"

SUPPORT_DOC_RE = re.compile(
    r"Support Doc:\s*(https://docs\.google\.com/document/d/[^\s]+)"
)

CACHE_TTL_SECONDS = 300  # 5 minutes

SECTION_MAP = {
    "Task List:": "task_list",
    "Open Tickets:": "open_tickets",
    "Random Fact:": "random_fact",
    "Email:": "email",
    "Thoughts / Ideas:": "thoughts_ideas",
    "Notes:": "notes",
}


# --- Core utilities ---


def utf16_len(text):
    """Google Docs API uses UTF-16 code unit indices."""
    return len(text.encode("utf-16-le")) // 2


def load_json_file(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: config file not found: {path}", file=sys.stderr)
        sys.exit(1)


def run_cmd(args, check=True):
    """Run a subprocess and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode not in (0, 2):
        print(
            f"ERROR: command failed with exit code {result.returncode}",
            file=sys.stderr,
        )
        print(f"  command: {' '.join(str(a) for a in args)}", file=sys.stderr)
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}", file=sys.stderr)
        if result.stdout:
            print(f"  stdout: {result.stdout.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout, result.stderr, result.returncode


# --- Database ---


def get_cache_db():
    """Open the daily_log_cache database, creating it from schema if needed."""
    if not CACHE_DB_PATH.is_file():
        if not CACHE_SCHEMA_PATH.is_file():
            print(
                f"ERROR: cache schema not found: {CACHE_SCHEMA_PATH}",
                file=sys.stderr,
            )
            sys.exit(1)
        os.makedirs(CACHE_DB_PATH.parent, exist_ok=True)
        conn = sqlite3.connect(str(CACHE_DB_PATH))
        with open(CACHE_SCHEMA_PATH) as f:
            conn.executescript(f.read())
        conn.close()
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Ensure cache tables exist
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_events_cache (
            event_id TEXT PRIMARY KEY,
            summary TEXT,
            start_time TEXT,
            end_time TEXT,
            all_day INTEGER,
            color_id TEXT,
            event_type TEXT,
            description TEXT,
            html_link TEXT,
            support_doc_url TEXT,
            fetched_at TEXT NOT NULL
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks_cache (
            task_id TEXT PRIMARY KEY,
            title TEXT,
            list_type TEXT CHECK (list_type IN ('in_progress', 'waiting')),
            due TEXT,
            web_view_link TEXT,
            sort_order INTEGER,
            fetched_at TEXT NOT NULL
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS open_tickets_snapshot (
            freshdesk_ticket_id INTEGER PRIMARY KEY,
            subject TEXT,
            requester_id INTEGER,
            requester_name TEXT,
            status INTEGER,
            priority INTEGER,
            fetched_at TEXT NOT NULL
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_tickets_cache (
            freshdesk_ticket_id INTEGER PRIMARY KEY,
            subject TEXT,
            requester_id INTEGER,
            requester_name TEXT,
            status INTEGER,
            priority INTEGER,
            fetched_at TEXT NOT NULL
        )
    """
    )
    # Migrate: add status/priority columns if missing (pre-existing databases)
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(open_tickets_snapshot)").fetchall()
    }
    if "status" not in cols:
        conn.execute("ALTER TABLE open_tickets_snapshot ADD COLUMN status INTEGER")
    if "priority" not in cols:
        conn.execute("ALTER TABLE open_tickets_snapshot ADD COLUMN priority INTEGER")
    conn.commit()
    return conn


def get_crm_db():
    """Open the CRM database."""
    if not CRM_DB_PATH.is_file():
        print(f"ERROR: CRM database not found: {CRM_DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(CRM_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# --- Config ---


def read_configs():
    """Read daily_log.json and doc_styles.json config files."""
    print("Reading configuration...")
    config = load_json_file(CONFIG_PATH)
    style = load_json_file(STYLE_CONFIG_PATH)

    # Validate required keys in daily_log config
    if "documentId" not in config:
        print("ERROR: daily_log config missing required key: documentId", file=sys.stderr)
        sys.exit(1)

    # Validate required keys in style config
    for key in ("fonts", "colors", "bulletPresets"):
        if key not in style:
            print(f"ERROR: style config missing required key: {key}", file=sys.stderr)
            sys.exit(1)

    return config, style


# --- Cache freshness ---


def _is_cache_fresh(db, table):
    """Check if a cache table has data less than CACHE_TTL_SECONDS old."""
    row = db.execute(f"SELECT MIN(fetched_at) as oldest FROM {table}").fetchone()
    if row and row["oldest"]:
        oldest = datetime.fromisoformat(row["oldest"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - oldest).total_seconds()
        return age < CACHE_TTL_SECONDS
    return False


# --- Data fetching with caching ---


def fetch_calendar_events(config, today_str, tz_offset):
    """Fetch today's calendar events. Uses cache if fresh."""
    db = get_cache_db()
    if _is_cache_fresh(db, "calendar_events_cache"):
        print("Using cached calendar events (less than 5 minutes old)")
        rows = db.execute(
            "SELECT event_id, summary, start_time, end_time, all_day, "
            "color_id, event_type, description, html_link, support_doc_url "
            "FROM calendar_events_cache"
        ).fetchall()
        db.close()
        return [dict(r) for r in rows]
    db.close()

    print("Fetching calendar events...")
    exclude_colors = set(config.get("excludeEventColorIds", []))
    params = {
        "calendarId": "primary",
        "timeMin": f"{today_str}T00:00:00{tz_offset}",
        "timeMax": f"{today_str}T23:59:59{tz_offset}",
        "singleEvents": True,
        "orderBy": "startTime",
    }
    stdout, _, _ = run_cmd(
        [GWS_SAFE, "calendar", "events", "list", "--params", json.dumps(params)]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("ERROR: failed to parse calendar events output as JSON", file=sys.stderr)
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)

    items = data.get("items", [])
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = []
    for item in items:
        if item.get("eventType") == "workingLocation":
            continue
        if item.get("colorId") in exclude_colors:
            continue

        all_day = "date" in item.get("start", {})
        start_time = item["start"].get("date") or item["start"].get("dateTime", "")
        end_time = item["end"].get("date") or item["end"].get("dateTime", "")
        description = item.get("description", "")
        support_doc_match = SUPPORT_DOC_RE.search(description)
        support_doc_url = support_doc_match.group(1) if support_doc_match else None

        events.append(
            {
                "event_id": item["id"],
                "summary": item.get("summary", "(No title)").strip(),
                "start_time": start_time,
                "end_time": end_time,
                "all_day": 1 if all_day else 0,
                "color_id": item.get("colorId"),
                "event_type": item.get("eventType"),
                "description": description,
                "html_link": item.get("htmlLink", ""),
                "support_doc_url": support_doc_url,
                "fetched_at": now_iso,
            }
        )

    # Update cache
    db = get_cache_db()
    db.execute("DELETE FROM calendar_events_cache")
    for e in events:
        db.execute(
            "INSERT INTO calendar_events_cache "
            "(event_id, summary, start_time, end_time, all_day, color_id, "
            "event_type, description, html_link, support_doc_url, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e["event_id"],
                e["summary"],
                e["start_time"],
                e["end_time"],
                e["all_day"],
                e["color_id"],
                e["event_type"],
                e["description"],
                e["html_link"],
                e["support_doc_url"],
                e["fetched_at"],
            ),
        )
    db.commit()
    db.close()

    return events


def fetch_tasks(config, today_str):
    """Fetch in-progress and waiting tasks. Uses cache if fresh."""
    db = get_cache_db()
    if _is_cache_fresh(db, "tasks_cache"):
        print("Using cached tasks (less than 5 minutes old)")
        in_progress = db.execute(
            "SELECT task_id, title, web_view_link, sort_order "
            "FROM tasks_cache WHERE list_type = 'in_progress' ORDER BY sort_order"
        ).fetchall()
        waiting = db.execute(
            "SELECT task_id, title, due, web_view_link, sort_order "
            "FROM tasks_cache WHERE list_type = 'waiting' ORDER BY sort_order"
        ).fetchall()
        db.close()
        return [dict(r) for r in in_progress], [dict(r) for r in waiting]
    db.close()

    in_progress_list_id = config["inProgressTaskListId"]
    waiting_list_id = config["waitingTaskListId"]
    today_due = f"{today_str}T00:00:00.000Z"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch in-progress tasks
    print("Fetching in-progress tasks...")
    params = {"tasklist": in_progress_list_id, "showAssigned": True}
    stdout, _, _ = run_cmd(
        [GWS_SAFE, "tasks", "tasks", "list", "--params", json.dumps(params)]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(
            "ERROR: failed to parse in-progress tasks output as JSON", file=sys.stderr
        )
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)

    in_progress = []
    for i, item in enumerate(data.get("items", [])):
        in_progress.append(
            {
                "task_id": item["id"],
                "title": item.get("title", "(No title)").strip(),
                "list_type": "in_progress",
                "due": item.get("due"),
                "web_view_link": item.get("webViewLink", ""),
                "sort_order": i,
                "fetched_at": now_iso,
            }
        )

    # Fetch waiting tasks
    print("Fetching waiting tasks...")
    params = {"tasklist": waiting_list_id, "showAssigned": True}
    stdout, _, _ = run_cmd(
        [GWS_SAFE, "tasks", "tasks", "list", "--params", json.dumps(params)]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("ERROR: failed to parse waiting tasks output as JSON", file=sys.stderr)
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)

    waiting = []
    for i, item in enumerate(data.get("items", [])):
        if item.get("due") == today_due:
            waiting.append(
                {
                    "task_id": item["id"],
                    "title": item.get("title", "(No title)").strip(),
                    "list_type": "waiting",
                    "due": item.get("due"),
                    "web_view_link": item.get("webViewLink", ""),
                    "sort_order": i,
                    "fetched_at": now_iso,
                }
            )

    # Update cache
    db = get_cache_db()
    db.execute("DELETE FROM tasks_cache")
    for t in in_progress + waiting:
        db.execute(
            "INSERT INTO tasks_cache "
            "(task_id, title, list_type, due, web_view_link, sort_order, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                t["task_id"],
                t["title"],
                t["list_type"],
                t["due"],
                t["web_view_link"],
                t["sort_order"],
                t["fetched_at"],
            ),
        )
    db.commit()
    db.close()

    return in_progress, waiting


def fetch_open_tickets():
    """Fetch open tickets. Uses snapshot cache if less than 5 minutes old."""
    db = get_cache_db()

    # Check if cache is fresh (less than 5 minutes old)
    row = db.execute(
        "SELECT MIN(fetched_at) as oldest FROM open_tickets_snapshot"
    ).fetchone()
    if row and row["oldest"]:
        oldest = datetime.fromisoformat(row["oldest"].replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - oldest).total_seconds()
        if age_seconds < CACHE_TTL_SECONDS:
            print("Using cached ticket data (less than 5 minutes old)")
            cached = db.execute(
                "SELECT freshdesk_ticket_id, subject, requester_id, requester_name "
                "FROM open_tickets_snapshot WHERE freshdesk_ticket_id != -1"
            ).fetchall()
            db.close()
            return [dict(r) for r in cached]

    db.close()

    # Cache is stale or empty -- fetch from FreshDesk
    print("Fetching open tickets from FreshDesk...")
    stdout, stderr, rc = run_cmd(
        [FRESHDESK_SAFE, "tickets", "search", "--query", "status:2"]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(
            "ERROR: failed to parse FreshDesk ticket search output as JSON",
            file=sys.stderr,
        )
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)

    # FreshDesk search returns {"total": N, "results": [...]}
    results = data.get("results", [])
    if not results:
        # Store sentinel row so MIN(fetched_at) returns a valid timestamp
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db = get_cache_db()
        db.execute("DELETE FROM open_tickets_snapshot")
        db.execute(
            "INSERT INTO open_tickets_snapshot "
            "(freshdesk_ticket_id, subject, requester_id, requester_name, "
            "status, priority, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (-1, "__empty__", 0, "", None, None, now_iso),
        )
        db.commit()
        db.close()
        return []

    # Resolve requester names
    tickets = []
    requester_names = {}
    for ticket in results:
        tid = ticket["id"]
        subject = ticket["subject"]
        requester_id = ticket.get("requester_id")
        tickets.append(
            {
                "freshdesk_ticket_id": tid,
                "subject": subject,
                "requester_id": requester_id,
            }
        )
        if requester_id and requester_id not in requester_names:
            requester_names[requester_id] = None  # placeholder

    # Resolve names: CRM first, then FreshDesk API for unknowns
    _resolve_requester_names(requester_names)

    # Attach names to tickets
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result_tickets = []
    for t in tickets:
        name = requester_names.get(t["requester_id"], "Unknown") or "Unknown"
        t["requester_name"] = name
        t["fetched_at"] = now_iso
        result_tickets.append(t)

    # Update snapshot cache
    db = get_cache_db()
    db.execute("DELETE FROM open_tickets_snapshot")
    for t in result_tickets:
        db.execute(
            "INSERT INTO open_tickets_snapshot "
            "(freshdesk_ticket_id, subject, requester_id, requester_name, "
            "status, priority, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                t["freshdesk_ticket_id"],
                t["subject"],
                t["requester_id"],
                t["requester_name"],
                t.get("status"),
                t.get("priority"),
                t["fetched_at"],
            ),
        )
    db.commit()
    db.close()

    return result_tickets


def _resolve_requester_names(requester_names):
    """Resolve requester_id -> name. Checks CRM DB first, falls back to FreshDesk API.
    Modifies requester_names dict in place."""
    if not requester_names:
        return

    crm_db = get_crm_db()
    unknown_ids = []

    for rid in requester_names:
        row = crm_db.execute(
            "SELECT name FROM contacts WHERE freshdesk_id = ?", (rid,)
        ).fetchone()
        if row and row["name"]:
            requester_names[rid] = row["name"]
        else:
            unknown_ids.append(rid)
    crm_db.close()

    # Fetch unknown contacts from FreshDesk and create CRM records
    for rid in unknown_ids:
        print(f"  Looking up FreshDesk contact {rid}...")
        stdout, stderr, rc = run_cmd(
            [FRESHDESK_SAFE, "contacts", "view", str(rid)],
            check=False,
        )
        if rc != 0:
            requester_names[rid] = "Unknown"
            continue
        try:
            contact = json.loads(stdout)
        except json.JSONDecodeError:
            print(
                f"ERROR: failed to parse FreshDesk contact {rid} output as JSON",
                file=sys.stderr,
            )
            print(f"  raw output: {stdout}", file=sys.stderr)
            sys.exit(1)
        name = contact.get("name", "Unknown") or "Unknown"
        requester_names[rid] = name

        # Create CRM contact record
        if name != "Unknown":
            crm_data = {"name": name, "freshdesk_id": rid}
            if contact.get("email"):
                crm_data["email"] = contact["email"]
            print(f"  Creating CRM contact for {name} (FreshDesk ID: {rid})")
            run_cmd(
                [CRM_SAFE, "contacts", "create", "--json", json.dumps(crm_data)],
                check=False,
            )


# --- Document fetching and parsing ---


def fetch_doc(doc_id):
    """Fetch the Google Doc."""
    print("Fetching Google Doc...")
    stdout, _, _ = run_cmd(
        [
            GWS_SAFE,
            "docs",
            "documents",
            "get",
            "--params",
            json.dumps({"documentId": doc_id}),
        ]
    )
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError:
        print("ERROR: failed to parse Google Docs output as JSON", file=sys.stderr)
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)
    return doc


def extract_section_text(doc, section_start, section_end):
    """Extract plain text from a section of the doc between start and end indices."""
    text = ""
    body_content = doc.get("body", {}).get("content", [])
    for element in body_content:
        el_start = element.get("startIndex", 0)
        el_end = element.get("endIndex", 0)
        if el_end <= section_start or el_start >= section_end:
            continue
        paragraph = element.get("paragraph", {})
        for pe in paragraph.get("elements", []):
            tr = pe.get("textRun", {})
            content = tr.get("content", "")
            text += content
    return text


def parse_doc_entries(doc):
    """Parse the Google Doc to extract all entries with their sections and subsections."""
    body_content = doc.get("body", {}).get("content", [])

    heading1_paragraphs = []
    for element in body_content:
        paragraph = element.get("paragraph", {})
        pstyle = paragraph.get("paragraphStyle", {})
        if pstyle.get("namedStyleType") == "HEADING_1":
            text = ""
            for pe in paragraph.get("elements", []):
                text += pe.get("textRun", {}).get("content", "")
            text = text.strip()
            heading1_paragraphs.append(
                {
                    "text": text,
                    "start_index": element.get("startIndex", 0),
                }
            )

    if not heading1_paragraphs:
        return []

    doc_end = body_content[-1].get("endIndex", 0) if body_content else 0
    entries_raw = []
    for i, h1 in enumerate(heading1_paragraphs):
        end_index = (
            heading1_paragraphs[i + 1]["start_index"]
            if i + 1 < len(heading1_paragraphs)
            else doc_end
        )
        entries_raw.append(
            {
                "heading_text": h1["text"],
                "start_index": h1["start_index"],
                "end_index": end_index,
            }
        )

    result = []
    for entry_info in entries_raw:
        entry_date = parse_date_from_heading(entry_info["heading_text"])
        if not entry_date:
            continue
        sections = parse_entry_sections(
            body_content, entry_info["start_index"], entry_info["end_index"]
        )
        result.append(
            {
                "entry_date": entry_date,
                "heading_text": entry_info["heading_text"],
                "start_index": entry_info["start_index"],
                "end_index": entry_info["end_index"],
                "sections": sections,
            }
        )

    return result


def parse_date_from_heading(heading_text):
    """Parse a date string like 'Friday Mar 27, 2026' into 'YYYY-MM-DD'.
    strptime with %d handles both zero-padded and non-padded days."""
    for fmt in ["%A %b %d, %Y", "%A %B %d, %Y"]:
        try:
            dt = datetime.strptime(heading_text.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_entry_sections(body_content, entry_start, entry_end):
    """Parse HEADING_2 sections within an entry."""
    heading2_paragraphs = []
    for element in body_content:
        el_start = element.get("startIndex", 0)
        if el_start < entry_start or el_start >= entry_end:
            continue
        paragraph = element.get("paragraph", {})
        pstyle = paragraph.get("paragraphStyle", {})
        if pstyle.get("namedStyleType") == "HEADING_2":
            text = ""
            for pe in paragraph.get("elements", []):
                text += pe.get("textRun", {}).get("content", "")
            text = text.strip()
            heading2_paragraphs.append(
                {
                    "text": text,
                    "start_index": el_start,
                }
            )

    sections = []
    for i, h2 in enumerate(heading2_paragraphs):
        end = (
            heading2_paragraphs[i + 1]["start_index"]
            if i + 1 < len(heading2_paragraphs)
            else entry_end
        )
        section_type = SECTION_MAP.get(h2["text"])
        if not section_type:
            continue

        subsections = []
        if section_type == "notes":
            subsections = parse_subsections(body_content, h2["start_index"], end)

        section = {
            "section_type": section_type,
            "heading_text": h2["text"],
            "start_index": h2["start_index"],
            "end_index": end,
        }
        if subsections:
            section["subsections"] = subsections
        sections.append(section)

    return sections


def parse_subsections(body_content, section_start, section_end):
    """Parse HEADING_3 subsections within a section."""
    heading3_paragraphs = []
    for element in body_content:
        el_start = element.get("startIndex", 0)
        if el_start <= section_start or el_start >= section_end:
            continue
        paragraph = element.get("paragraph", {})
        pstyle = paragraph.get("paragraphStyle", {})
        if pstyle.get("namedStyleType") == "HEADING_3":
            text = ""
            for pe in paragraph.get("elements", []):
                text += pe.get("textRun", {}).get("content", "")
            text = text.strip()
            heading3_paragraphs.append(
                {
                    "text": text,
                    "start_index": el_start,
                }
            )

    subsections = []
    for i, h3 in enumerate(heading3_paragraphs):
        end = (
            heading3_paragraphs[i + 1]["start_index"]
            if i + 1 < len(heading3_paragraphs)
            else section_end
        )
        subsections.append(
            {
                "heading_text": h3["text"],
                "start_index": h3["start_index"],
                "end_index": end,
                "sort_order": i,
            }
        )

    return subsections


# --- batchUpdate execution ---


def execute_batch_update(doc_id, batch_json, auto_confirm):
    """Execute the batchUpdate via gws-safe. Handles dry-run and auto-confirm."""
    json_str = json.dumps(batch_json)
    params_str = json.dumps({"documentId": doc_id})

    cmd = [
        GWS_SAFE,
        "docs",
        "documents",
        "batchUpdate",
        "--json",
        json_str,
        "--params",
        params_str,
    ]

    print("Executing batchUpdate (dry-run)...")
    stdout, stderr, rc = run_cmd(cmd, check=False)

    if rc == 2:
        # Dry-run enforced -- parse nonce from stderr
        nonce_match = re.search(r"--confirmed\s+([a-f0-9]+)", stderr)
        if not nonce_match:
            print(
                "ERROR: could not parse nonce from dry-run output", file=sys.stderr
            )
            print(f"stderr: {stderr}", file=sys.stderr)
            sys.exit(1)

        nonce = nonce_match.group(1)

        if stdout.strip():
            print("Dry-run output:")
            print(stdout.strip())

        if auto_confirm:
            print(f"Auto-confirming with nonce {nonce}...")
            confirm_cmd = cmd + ["--confirmed", nonce]
            stdout2, stderr2, rc2 = run_cmd(confirm_cmd, check=False)
            if rc2 != 0:
                print(
                    f"ERROR: confirmed batchUpdate failed with exit code {rc2}",
                    file=sys.stderr,
                )
                if stderr2:
                    print(f"  stderr: {stderr2.strip()}", file=sys.stderr)
                sys.exit(1)
            print("batchUpdate confirmed and applied successfully.")
            return True
        else:
            print(
                f"\nDry-run enforced. To confirm, re-run with --auto-confirm or manually run:"
            )
            print(f"  {' '.join(str(a) for a in cmd)} --confirmed {nonce}")
            return False
    elif rc == 0:
        print("batchUpdate applied successfully.")
        return True
    else:
        print(f"ERROR: batchUpdate failed with exit code {rc}", file=sys.stderr)
        if stderr:
            print(f"  stderr: {stderr.strip()}", file=sys.stderr)
        sys.exit(1)


# --- Cache update ---


def update_cache(doc_id):
    """Re-read the doc and repopulate the daily-log-cache."""
    print("Updating cache...")

    stdout, _, _ = run_cmd(
        [
            GWS_SAFE,
            "docs",
            "documents",
            "get",
            "--params",
            json.dumps({"documentId": doc_id}),
        ]
    )
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError:
        print(
            "ERROR: failed to parse Google Docs output as JSON during cache update",
            file=sys.stderr,
        )
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)
    revision_id = doc.get("revisionId", "")

    entries = parse_doc_entries(doc)

    populate_data = {
        "document_id": doc_id,
        "revision_id": revision_id,
        "entries": entries,
    }

    run_cmd([DAILY_LOG_CACHE, "populate", "--json", json.dumps(populate_data)])
    print("Cache updated.")


# --- Sorting ---


def sort_entries(events, tasks):
    """Sort entries: all-day events (alpha), timed events (by start), tasks (list order).
    Returns a combined list of (item, type_str) tuples."""
    all_day = [(e, "event") for e in events if e["all_day"]]
    timed = [(e, "event") for e in events if not e["all_day"]]
    task_items = [(t, "task") for t in tasks]

    all_day.sort(key=lambda x: x[0]["summary"].lower())
    timed.sort(key=lambda x: x[0]["start_time"])
    task_items.sort(key=lambda x: x[0]["sort_order"])

    return all_day + timed + task_items


# --- Time formatting ---


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


def format_event_time(event):
    """Format an event's time for display. Returns 'all day' or 'h:mm AM/PM'."""
    if event["all_day"]:
        return "all day"
    start = event["start_time"]
    try:
        dt = datetime.fromisoformat(start)
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return ""


def publish_note(text, auto_confirm=False):
    """Publish a timestamped note to the Notes section of today's daily log."""
    cmd = [str(REPO_ROOT / "bin" / "publish-to-notes"), "--text", text]
    if auto_confirm:
        cmd.append("--auto-confirm")
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode not in (0, 2):
        print(f"WARNING: publish-to-notes failed: {result.stderr.strip()}", file=sys.stderr)
