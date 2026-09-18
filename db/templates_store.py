"""Per-path shared email template persistence (D-05).

Follows db/prospects.py's connection lifecycle convention exactly: a fresh
sqlite3.connect() per call, wrapped in try/finally so the connection always
closes. All SQL uses `?` placeholders exclusively -- teammate-edited
subject/body text is free-text user input and must never be interpolated
into a SQL string (Phase 1 Security Domain rule, T-02-01).
"""
from __future__ import annotations

import sqlite3

from personalization.templates import PATH_TEMPLATES


def get_template(path_slug: str, db_path: str = "db/outreach.db") -> tuple[str, str]:
    """Return (subject, body) -- an override if one exists, else the
    PATH_TEMPLATES default for path_slug.

    Lazy fallback only -- this function must NOT write a seed row on read
    (04-RESEARCH.md Assumption A4), so merely viewing the queue never
    creates a permanent override.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT subject, body FROM template_override WHERE path = ?",
            (path_slug,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row:
        return row[0], row[1]
    default = PATH_TEMPLATES[path_slug]
    return default["subject"], default["body"]


def save_template_override(
    path_slug: str, subject: str, body: str, db_path: str = "db/outreach.db"
) -> None:
    """Persist an edited template as the new permanent default for path_slug
    (D-05), surviving app restarts.

    Caller (pages/review_queue_page.py) is responsible for running
    validate_template_fields() first -- this function deliberately does not
    re-validate. This upsert is the one new SQL shape in the codebase (every
    other write here is a plain INSERT or UPDATE); kept inside this single
    function rather than generalized into a helper.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO template_override (path, subject, body, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(path) DO UPDATE SET "
            "subject = excluded.subject, body = excluded.body, "
            "updated_at = CURRENT_TIMESTAMP",
            (path_slug, subject, body),
        )
        conn.commit()
    finally:
        conn.close()
