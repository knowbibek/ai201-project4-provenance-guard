"""Structured audit log backed by SQLite.

Two tables: `decisions` (one row per attribution) and `appeals` (one row per appeal, linked by
content_id). On appeal we also denormalize the latest reasoning/status onto the decision row so a
single `GET /log` entry shows everything a reviewer needs. Kept structured — never print()-only.
"""
import json
import sqlite3
import uuid
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
                ai_likelihood    REAL,
                llm_score        REAL,
                stylometry_score REAL,
                lexical_score    REAL,
                label_variant    TEXT,
                label_text       TEXT,
                signals_json     TEXT,
                status           TEXT NOT NULL DEFAULT 'classified',
                appeal_id        TEXT,
                appeal_reasoning TEXT,
                appealed_at      TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appeals (
                appeal_id   TEXT PRIMARY KEY,
                content_id  TEXT NOT NULL,
                reasoning   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )


def log_decision(record: dict) -> None:
    """Insert one decision row and print a one-line console summary."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO decisions (
                content_id, creator_id, title, timestamp, content_excerpt,
                attribution, confidence, ai_likelihood, llm_score, stylometry_score, lexical_score,
                label_variant, label_text, signals_json, status
            ) VALUES (
                :content_id, :creator_id, :title, :timestamp, :content_excerpt,
                :attribution, :confidence, :ai_likelihood, :llm_score, :stylometry_score, :lexical_score,
                :label_variant, :label_text, :signals_json, :status
            )
            """,
            record,
        )
    excerpt = (record.get("content_excerpt") or "")[:40]
    print(
        f"[DECISION] {record['attribution']} conf={record.get('confidence')} "
        f"llm={record.get('llm_score')} sty={record.get('stylometry_score')} "
        f"lex={record.get('lexical_score')} id={record['content_id'][:8]} \"{excerpt}…\"",
        flush=True,
    )


def log_appeal(content_id: str, reasoning: str) -> dict | None:
    """Record an appeal: insert an appeal row, flip the decision to 'under_review', and
    denormalize the reasoning onto the decision. Returns the appeal confirmation, or None
    if no decision exists for `content_id`.
    """
    appeal_id = str(uuid.uuid4())
    now = _utc_now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT content_id FROM decisions WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "INSERT INTO appeals (appeal_id, content_id, reasoning, created_at) VALUES (?, ?, ?, ?)",
            (appeal_id, content_id, reasoning, now),
        )
        conn.execute(
            """
            UPDATE decisions
               SET status = 'under_review', appeal_id = ?, appeal_reasoning = ?, appealed_at = ?
             WHERE content_id = ?
            """,
            (appeal_id, reasoning, now, content_id),
        )
    print(
        f"[APPEAL] content_id={content_id[:8]} -> under_review "
        f"\"{(reasoning or '')[:40]}…\"",
        flush=True,
    )
    return {
        "appeal_id": appeal_id,
        "content_id": content_id,
        "status": "under_review",
        "logged_at": now,
    }


def get_log(limit: int = 50) -> list[dict]:
    """Return the most recent decision rows as plain dicts, newest first.

    Each entry includes its status and (if appealed) the appeal_reasoning, so a single log view
    shows both the original decision and any appeal filed against it.
    """
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
