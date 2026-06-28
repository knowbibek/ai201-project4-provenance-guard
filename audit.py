"""Structured audit log backed by SQLite.

One row per attribution decision. Extended in M4 (stylometry score, real confidence) and M5
(appeals table). Kept structured — never print()-only — so the log is queryable and auditable.
"""
import json
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH


def _utc_now() -> str:
    """ISO 8601 UTC with a trailing Z, e.g. 2025-04-01T14:32:10.123Z."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                content_id       TEXT PRIMARY KEY,
                creator_id       TEXT,
                title            TEXT,
                timestamp        TEXT NOT NULL,
                content_excerpt  TEXT,
                attribution      TEXT NOT NULL,
                confidence       REAL,
                llm_score        REAL,
                stylometry_score REAL,
                label_variant    TEXT,
                label_text       TEXT,
                signals_json     TEXT,
                status           TEXT NOT NULL DEFAULT 'classified'
            )
            """
        )


def log_decision(record: dict) -> None:
    """Insert one decision row and print a one-line console summary (RepairSafe style)."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO decisions (
                content_id, creator_id, title, timestamp, content_excerpt,
                attribution, confidence, llm_score, stylometry_score,
                label_variant, label_text, signals_json, status
            ) VALUES (
                :content_id, :creator_id, :title, :timestamp, :content_excerpt,
                :attribution, :confidence, :llm_score, :stylometry_score,
                :label_variant, :label_text, :signals_json, :status
            )
            """,
            record,
        )
    excerpt = (record.get("content_excerpt") or "")[:40]
    print(
        f"[DECISION] {record['attribution']} conf={record.get('confidence')} "
        f"llm={record.get('llm_score')} id={record['content_id'][:8]} \"{excerpt}…\"",
        flush=True,
    )


def get_log(limit: int = 50) -> list[dict]:
    """Return the most recent decision rows as plain dicts, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        if entry.get("signals_json"):
            try:
                entry["signals"] = json.loads(entry.pop("signals_json"))
            except json.JSONDecodeError:
                entry["signals"] = None
        else:
            entry.pop("signals_json", None)
        entries.append(entry)
    return entries
