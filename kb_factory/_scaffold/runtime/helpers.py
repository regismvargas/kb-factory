from __future__ import annotations

import datetime as dt
import json
import sqlite3

__all__ = [
    "log_action",
    "now_iso",
    "record_exists",
    "row_to_dict",
    "upsert_fts",
]


def now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["tags"] = json.loads(data.pop("tags_json"))
    return data


def record_exists(conn: sqlite3.Connection, record_id: str) -> bool:
    found = conn.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone()
    return found is not None


def log_action(conn: sqlite3.Connection, record_id: str, action: str, details: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log(record_id, action, happened_at, details_json) VALUES(?, ?, ?, ?)",
        (record_id, action, now_iso(), json.dumps(details, ensure_ascii=False)),
    )


def upsert_fts(conn: sqlite3.Connection, record_id: str) -> None:
    row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    conn.execute("DELETE FROM records_fts WHERE id = ?", (record_id,))
    if row is None:
        return
    data = row_to_dict(row)
    conn.execute(
        "INSERT INTO records_fts(id, title, content, tags, source, domain) VALUES(?, ?, ?, ?, ?, ?)",
        (
            data["id"],
            data["title"],
            data["content"],
            " ".join(data["tags"]),
            data["source"],
            data["domain"],
        ),
    )
