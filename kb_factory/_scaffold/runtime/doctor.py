from __future__ import annotations

import subprocess

from .config import load_config
from .db import connect_readonly
from .schema import hardening_enabled
from .paths import DB_PATH, KB_ROOT, KB_ROOT_INFO, ensure_dirs, missing_db_message
from .sources import compute_file_hash, resolve_stored_path


def _db_tracked_in_git() -> bool | None:
    """True/False when the project is a Git checkout, None otherwise."""
    project = KB_ROOT.parent
    try:
        relative = DB_PATH.relative_to(project).as_posix()
        proc = subprocess.run(
            ["git", "-C", str(project), "ls-files", "--error-unmatch", relative],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if proc.returncode == 0:
        return True
    if "not a git repository" in (proc.stderr or "").lower():
        return None
    return False


def get_storage_checks() -> dict:
    tracked = _db_tracked_in_git()
    warnings: list[str] = []
    if KB_ROOT_INFO.get("shadowed_local_db"):
        warnings.append(
            "this linked worktree has its own .kb/kb.db; commands use the main "
            "worktree KB instead so sessions do not diverge"
        )
    if tracked:
        warnings.append(
            "kb.db is tracked in Git: per-branch copies of a binary database cannot "
            "be merged; keep one live KB in the main worktree"
        )
    return {
        "kb_root": str(KB_ROOT),
        "db_path": str(DB_PATH),
        "resolution": KB_ROOT_INFO.get("resolution"),
        "runtime_kb_root": KB_ROOT_INFO.get("runtime_kb_root"),
        "main_worktree_root": KB_ROOT_INFO.get("main_worktree_root"),
        "worktree_scope": KB_ROOT_INFO.get("worktree_scope"),
        "shadowed_local_db": bool(KB_ROOT_INFO.get("shadowed_local_db")),
        "db_tracked_in_git": tracked,
        "warnings": warnings,
    }


def get_doctor_checks(config: dict | None = None) -> dict:
    config = config or load_config()
    ensure_dirs(config)
    storage = get_storage_checks()
    if not DB_PATH.is_file():
        return {"db_exists": False, "storage": storage, "error": missing_db_message()}
    conn = connect_readonly()
    source_rows = conn.execute(
        "SELECT source_id, filename, stored_path, content_hash FROM sources"
    ).fetchall()
    missing_files = 0
    hash_drift = 0
    for src in source_rows:
        stored = resolve_stored_path(src["stored_path"], src["source_id"], src["filename"])
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
        "storage": storage,
    }


def cmd_doctor(args, *, emit) -> None:
    emit(get_doctor_checks(), True)
