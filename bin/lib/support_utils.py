"""Shared utilities for support scripts (support-notes, support-calendar).

Contains common functions for FreshDesk ticket fetching, CRM entity
resolution, CRM record creation, ticket note scanning, and auto-confirm
flows for write operations through safe wrappers.
"""

import json
import re
import sys
from datetime import datetime, timezone

from .daily_log_utils import (
    CACHE_TTL_SECONDS,
    CRM_SAFE,
    FRESHDESK_SAFE,
    FRESHDESK_TICKET_URL,
    GWS_SAFE,
    STYLE_CONFIG_PATH,
    get_cache_db,
    load_json_file,
    run_cmd,
    utf16_len,
)

# --- Constants ---

SHARED_DRIVE_NAME = "Customers"

# Common domain suffixes to strip when extracting a keyword for folder search
DOMAIN_SUFFIXES = ("net", "tech", "corp", "inc", "telecom", "com", "io", "co", "org")


# --- Style config ---


def read_style_config():
    """Read doc_styles.json."""
    return load_json_file(STYLE_CONFIG_PATH)


# --- Active tickets ---


def fetch_active_tickets():
    """Fetch all non-closed, agent-assigned FreshDesk tickets.

    Uses the active_tickets_cache table with a 5-min TTL to avoid
    redundant FreshDesk API calls when scripts run in sequence.
    Returns a list of ticket dicts.
    """
    db = get_cache_db()

    # Check cache freshness
    row = db.execute(
        "SELECT MIN(fetched_at) as oldest FROM active_tickets_cache"
    ).fetchone()
    if row and row["oldest"]:
        oldest = datetime.fromisoformat(row["oldest"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - oldest).total_seconds()
        if age < CACHE_TTL_SECONDS:
            print("Using cached active tickets (less than 5 minutes old)")
            cached = db.execute(
                "SELECT freshdesk_ticket_id, subject, requester_id, requester_name, "
                "status, priority "
                "FROM active_tickets_cache WHERE freshdesk_ticket_id != -1"
            ).fetchall()
            db.close()
            return [dict(r) for r in cached]
    db.close()

    # Fetch from FreshDesk: all non-closed statuses
    print("Fetching active tickets from FreshDesk...")
    stdout, stderr, rc = run_cmd(
        [FRESHDESK_SAFE, "tickets", "search",
         "--query", "status:2 OR status:3 OR status:4 OR status:6 OR status:7 OR status:9"]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("ERROR: failed to parse FreshDesk ticket search output", file=sys.stderr)
        print(f"  raw output: {stdout}", file=sys.stderr)
        sys.exit(1)

    results = data.get("results", [])

    # Filter to agent-assigned tickets (FreshDesk search returns responder_id, not agent_id)
    assigned = [t for t in results if t.get("responder_id")]

    if not assigned:
        # Store sentinel row for cache
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db = get_cache_db()
        db.execute("DELETE FROM active_tickets_cache")
        db.execute(
            "INSERT INTO active_tickets_cache "
            "(freshdesk_ticket_id, subject, requester_id, requester_name, "
            "status, priority, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (-1, "__empty__", 0, "", None, None, now_iso),
        )
        db.commit()
        db.close()
        return []

    # Build ticket list and cache
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tickets = []
    for t in assigned:
        tickets.append({
            "freshdesk_ticket_id": t["id"],
            "subject": t.get("subject", ""),
            "requester_id": t.get("requester_id"),
            "requester_name": "",
            "status": t.get("status"),
            "priority": t.get("priority"),
            "fetched_at": now_iso,
        })

    # Update cache
    db = get_cache_db()
    db.execute("DELETE FROM active_tickets_cache")
    for t in tickets:
        db.execute(
            "INSERT INTO active_tickets_cache "
            "(freshdesk_ticket_id, subject, requester_id, requester_name, "
            "status, priority, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (t["freshdesk_ticket_id"], t["subject"],
             t["requester_id"], t["requester_name"],
             t.get("status"), t.get("priority"), t["fetched_at"]),
        )
    db.commit()
    db.close()

    return tickets


# --- CRM entity resolution ---


def resolve_crm_entity(email, contacts_cache=None, companies_cache=None):
    """Resolve an email address to CRM company and contact records.

    Args:
        email: The email address to resolve.
        contacts_cache: Optional pre-fetched list of all CRM contacts.
        companies_cache: Optional pre-fetched list of all CRM companies.

    Returns:
        dict with keys: company_id, company_name, contact_id, matched_by
        matched_by is one of "contact", "domain", "not_found"
    """
    result = {
        "company_id": None,
        "company_name": None,
        "contact_id": None,
        "matched_by": "not_found",
    }

    if not email:
        return result

    email_lower = email.lower()
    domain = email_lower.split("@", 1)[-1] if "@" in email_lower else ""

    # Step 1: Search contacts by email
    if contacts_cache is None:
        stdout, _, _ = run_cmd([CRM_SAFE, "contacts", "list"])
        try:
            contacts_cache = json.loads(stdout)
        except json.JSONDecodeError:
            contacts_cache = []

    for contact in contacts_cache:
        if contact.get("email", "").lower() == email_lower:
            result["contact_id"] = contact["id"]
            result["company_id"] = contact.get("company_id")
            result["company_name"] = contact.get("company_name", "")
            result["matched_by"] = "contact"
            # If company_name is missing, look it up
            if result["company_id"] and not result["company_name"]:
                if companies_cache is None:
                    stdout, _, _ = run_cmd([CRM_SAFE, "companies", "list"])
                    try:
                        companies_cache = json.loads(stdout)
                    except json.JSONDecodeError:
                        companies_cache = []
                for co in companies_cache:
                    if co["id"] == result["company_id"]:
                        result["company_name"] = co.get("name", "")
                        break
            # If contact has a company, we're done. If not, fall through
            # to domain matching so we can still resolve the company.
            if result["company_id"]:
                return result
            break

    # Step 2: Search companies by domain
    if not domain:
        return result

    if companies_cache is None:
        stdout, _, _ = run_cmd([CRM_SAFE, "companies", "list"])
        try:
            companies_cache = json.loads(stdout)
        except json.JSONDecodeError:
            companies_cache = []

    for company in companies_cache:
        domains_raw = company.get("domains", "[]")
        if isinstance(domains_raw, str):
            try:
                domains_list = json.loads(domains_raw)
            except json.JSONDecodeError:
                domains_list = []
        else:
            domains_list = domains_raw
        for d in domains_list:
            if d.lower() == domain:
                result["company_id"] = company["id"]
                result["company_name"] = company.get("name", "")
                result["matched_by"] = "domain"
                return result

    return result


# --- CRM record creation ---


def ensure_crm_records(ticket, requester, company_id):
    """Ensure CRM contact and ticket records exist, creating if missing.

    Args:
        ticket: dict with freshdesk_ticket_id, subject, status, priority
        requester: dict with email, name, first_name, last_name, freshdesk_id
        company_id: CRM company ID

    Returns:
        dict with keys: crm_contact_id, crm_ticket_id, created_contact, created_ticket
    """
    result = {
        "crm_contact_id": None,
        "crm_ticket_id": None,
        "created_contact": False,
        "created_ticket": False,
    }

    # Check contacts for this company
    stdout, _, _ = run_cmd(
        [CRM_SAFE, "contacts", "list", "--company-id", str(company_id)]
    )
    try:
        contacts = json.loads(stdout)
    except json.JSONDecodeError:
        contacts = []

    # Find by freshdesk_id or email
    for c in contacts:
        if c.get("freshdesk_id") == requester["freshdesk_id"]:
            result["crm_contact_id"] = c["id"]
            break
        if c.get("email", "").lower() == requester["email"].lower():
            result["crm_contact_id"] = c["id"]
            break

    if not result["crm_contact_id"]:
        # Create contact
        contact_data = {
            "name": requester["name"],
            "first_name": requester.get("first_name", ""),
            "last_name": requester.get("last_name", ""),
            "email": requester["email"],
            "freshdesk_id": requester["freshdesk_id"],
            "company_id": company_id,
        }
        stdout, _, _ = run_cmd(
            [CRM_SAFE, "contacts", "create", "--json", json.dumps(contact_data)]
        )
        try:
            created = json.loads(stdout)
            result["crm_contact_id"] = created["id"]
            result["created_contact"] = True
        except (json.JSONDecodeError, KeyError):
            print(f"ERROR: failed to create CRM contact for {requester['email']}", file=sys.stderr)
            sys.exit(1)

    # Check tickets for this company
    stdout, _, _ = run_cmd(
        [CRM_SAFE, "tickets", "list", "--company-id", str(company_id)]
    )
    try:
        crm_tickets = json.loads(stdout)
    except json.JSONDecodeError:
        crm_tickets = []

    fd_ticket_id = ticket["freshdesk_ticket_id"]
    for ct in crm_tickets:
        if ct.get("freshdesk_id") == fd_ticket_id:
            result["crm_ticket_id"] = ct["id"]
            break

    if not result["crm_ticket_id"]:
        # Create ticket
        ticket_data = {
            "subject": ticket["subject"],
            "status": ticket.get("status", 2),
            "priority": ticket.get("priority", 1),
            "freshdesk_id": fd_ticket_id,
            "company_id": company_id,
            "requester_id": result["crm_contact_id"],
        }
        stdout, _, _ = run_cmd(
            [CRM_SAFE, "tickets", "create", "--json", json.dumps(ticket_data)]
        )
        try:
            created = json.loads(stdout)
            result["crm_ticket_id"] = created["id"]
            result["created_ticket"] = True
        except (json.JSONDecodeError, KeyError):
            print(f"ERROR: failed to create CRM ticket for FD#{fd_ticket_id}", file=sys.stderr)
            sys.exit(1)

    return result


# --- Ticket note scanning ---


def scan_ticket_notes(ticket_id, pattern):
    """Scan a FreshDesk ticket's conversations for a pattern.

    Returns:
        dict with keys: found, note_id, note_body, matched_content, conversations
        conversations is the raw list of conversations (cached for reuse)
    """
    result = {
        "found": False,
        "note_id": None,
        "note_body": None,
        "matched_content": None,
        "conversations": [],
    }

    stdout, _, _ = run_cmd(
        [FRESHDESK_SAFE, "tickets", "view", str(ticket_id), "--include", "conversations"]
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return result

    conversations = data.get("conversations", [])
    result["conversations"] = conversations

    for conv in conversations:
        body = conv.get("body", "") or ""
        body_text = conv.get("body_text", "") or ""
        search_text = body + " " + body_text
        if pattern.lower() in search_text.lower():
            result["found"] = True
            result["note_id"] = conv.get("id")
            result["note_body"] = body
            result["matched_content"] = body
            return result

    return result


# --- FreshDesk contact lookup ---


def lookup_freshdesk_contact(contact_id):
    """Look up a FreshDesk contact by ID. Returns dict or None."""
    stdout, stderr, rc = run_cmd(
        [FRESHDESK_SAFE, "contacts", "view", str(contact_id)],
        check=False,
    )
    if rc != 0:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


# --- Auto-confirm write operations ---


def auto_confirm_gws(cmd_args, auto_confirm, label="GWS write"):
    """Execute a GWS write operation through gws-safe with dry-run/nonce/confirm flow.

    Args:
        cmd_args: list of arguments to pass to gws-safe (without the binary path)
        auto_confirm: if True, automatically confirm with nonce
        label: descriptive label for logging

    Returns:
        (stdout, success) tuple. stdout is the final output, success is bool.
    """
    full_cmd = [GWS_SAFE] + cmd_args
    print(f"  {label} (dry-run)...")
    stdout, stderr, rc = run_cmd(full_cmd, check=False)

    if rc == 2:
        # Dry-run enforced - parse nonce
        nonce_match = re.search(r"--confirmed\s+([a-f0-9]+)", stderr)
        if not nonce_match:
            print(f"ERROR: could not parse nonce from dry-run output", file=sys.stderr)
            print(f"  stderr: {stderr}", file=sys.stderr)
            sys.exit(1)

        nonce = nonce_match.group(1)

        if auto_confirm:
            print(f"  Auto-confirming {label} (nonce {nonce})...")
            confirm_cmd = full_cmd + ["--confirmed", nonce]
            stdout2, stderr2, rc2 = run_cmd(confirm_cmd, check=False)
            if rc2 != 0:
                print(f"ERROR: {label} confirmation failed (exit {rc2})", file=sys.stderr)
                if stderr2:
                    print(f"  stderr: {stderr2.strip()}", file=sys.stderr)
                return stdout2, False
            return stdout2, True
        else:
            print(f"\n  Dry-run enforced for {label}. Re-run with --auto-confirm or:")
            print(f"    {' '.join(str(a) for a in full_cmd)} --confirmed {nonce}")
            return stdout, False
    elif rc == 0:
        return stdout, True
    else:
        print(f"ERROR: {label} failed (exit {rc})", file=sys.stderr)
        if stderr:
            print(f"  stderr: {stderr.strip()}", file=sys.stderr)
        return stdout, False


def auto_confirm_freshdesk(cmd_args, auto_confirm, label="FreshDesk write"):
    """Execute a FreshDesk write operation through freshdesk-safe with dry-run/nonce/confirm flow.

    Args:
        cmd_args: list of arguments to pass to freshdesk-safe (without the binary path)
        auto_confirm: if True, automatically confirm with nonce
        label: descriptive label for logging

    Returns:
        (stdout, success) tuple.
    """
    full_cmd = [FRESHDESK_SAFE] + cmd_args
    print(f"  {label} (dry-run)...")
    stdout, stderr, rc = run_cmd(full_cmd, check=False)

    if rc == 2:
        # Dry-run enforced - parse nonce
        nonce_match = re.search(r"--confirmed\s+([a-f0-9]+)", stderr)
        if not nonce_match:
            print(f"ERROR: could not parse nonce from dry-run output", file=sys.stderr)
            print(f"  stderr: {stderr}", file=sys.stderr)
            sys.exit(1)

        nonce = nonce_match.group(1)

        if auto_confirm:
            print(f"  Auto-confirming {label} (nonce {nonce})...")
            confirm_cmd = full_cmd + ["--confirmed", nonce]
            stdout2, stderr2, rc2 = run_cmd(confirm_cmd, check=False)
            if rc2 != 0:
                print(f"ERROR: {label} confirmation failed (exit {rc2})", file=sys.stderr)
                if stderr2:
                    print(f"  stderr: {stderr2.strip()}", file=sys.stderr)
                return stdout2, False
            return stdout2, True
        else:
            print(f"\n  Dry-run enforced for {label}. Re-run with --auto-confirm or:")
            print(f"    {' '.join(str(a) for a in full_cmd)} --confirmed {nonce}")
            return stdout, False
    elif rc == 0:
        return stdout, True
    else:
        print(f"ERROR: {label} failed (exit {rc})", file=sys.stderr)
        if stderr:
            print(f"  stderr: {stderr.strip()}", file=sys.stderr)
        return stdout, False


# --- Slugify ---


def slugify(text, max_len=50):
    """Convert text to a URL-friendly slug for doc naming.

    Lowercase, replace spaces with hyphens, strip special characters,
    truncate to max_len.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    if len(text) > max_len:
        # Truncate at last hyphen before max_len to avoid cutting words
        truncated = text[:max_len]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > max_len // 2:
            text = truncated[:last_hyphen]
        else:
            text = truncated
    return text


# --- Domain keyword extraction ---


def extract_domain_keyword(domain):
    """Extract a search keyword from a domain name.

    Takes domain without TLD, strips common suffixes.
    E.g., "granitenet.com" -> "granite"
    """
    # Remove TLD
    name = domain.split(".")[0] if "." in domain else domain
    name = name.lower()

    # Strip common suffixes (try longest first to avoid partial matches)
    # If the name itself is a known suffix, don't strip anything
    if name not in DOMAIN_SUFFIXES:
        for suffix in sorted(DOMAIN_SUFFIXES, key=len, reverse=True):
            if name.endswith(suffix) and len(name) > len(suffix):
                candidate = name[: -len(suffix)]
                if len(candidate) >= 3:
                    name = candidate
                    break

    return name


# --- Google Doc batchUpdate helpers ---


def build_text_style_request(start, end, style, is_heading=False):
    """Build an updateTextStyle request for a range.

    Args:
        start: start index
        end: end index
        style: doc_styles.json config
        is_heading: True for heading style, False for body style
    """
    font_key = "heading" if is_heading else "body"
    color_key = "headingText" if is_heading else "bodyText"

    text_style = {
        "weightedFontFamily": {
            "fontFamily": style["fonts"][font_key],
        }
    }
    fields = "weightedFontFamily"

    color = style["colors"].get(color_key)
    if color is not None:
        text_style["foregroundColor"] = {"color": {"rgbColor": color}}
        fields += ",foregroundColor"

    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": text_style,
            "fields": fields,
        }
    }


def build_paragraph_style_request(start, end, named_style):
    """Build an updateParagraphStyle request."""
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "paragraphStyle": {"namedStyleType": named_style},
            "fields": "namedStyleType",
        }
    }


def build_link_style_request(start, end, url):
    """Build an updateTextStyle request for a link."""
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": {"link": {"url": url}},
            "fields": "link",
        }
    }
