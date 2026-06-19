from __future__ import annotations

from pathlib import Path

from .config import load_config
from .db import connect
from .schema import hardening_enabled
from .paths import DB_PATH, ensure_dirs
from .sources import compute_file_hash


def get_doctor_checks(config: dict | None = None) -> dict:
    config = config or load_config()
    ensure_dirs(config)
    conn = connect()
    source_rows = conn.execute(
        "SELECT source_id, stored_path, content_hash FROM sources"
    ).fetchall()
    missing_files = 0
    hash_drift = 0
    for src in source_rows:
        stored = Path(src["stored_path"])
        if not stored.is_file():
            missing_files += 1
            continue
        if compute_file_hash(stored) != src["content_hash"]:
            hash_drift += 1
    wiki_state_rows = conn.execute(
        "SELECT page_class, state, COUNT(*) AS n FROM wiki_pages "
        "GROUP BY page_class, state"
    ).fetchall()
    wiki_pages_by_state: dict = {"live": {}, "snapshot": {}}
    wiki_pages_total = 0
    for row in wiki_state_rows:
        cls = row["page_class"] or "unknown"
        st = row["state"] or "unknown"
        wiki_pages_by_state.setdefault(cls, {})[st] = row["n"]
        wiki_pages_total += row["n"]
    snapshots_total = conn.execute(
        "SELECT COUNT(*) AS n FROM wiki_snapshots"
    ).fetchone()[0]
    return {
        "db_exists": DB_PATH.exists(),
        "append_only_hardening": "enabled" if hardening_enabled(conn) else "disabled",
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "schema_version": conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0],
        "records_table": conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'records'"
        ).fetchone()
        is not None,
        "fts_table": conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'records_fts'"
        ).fetchone()
        is not None,
        "sources_total": len(source_rows),
        "sources_missing_files": missing_files,
        "sources_hash_drift": hash_drift,
        "wiki_pages_total": wiki_pages_total,
        "wiki_pages_by_state": wiki_pages_by_state,
        "wiki_snapshots_total": snapshots_total,
    }


def cmd_doctor(args, *, emit) -> None:
    emit(get_doctor_checks(), True)
