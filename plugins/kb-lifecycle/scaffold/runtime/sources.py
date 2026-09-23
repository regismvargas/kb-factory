from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import sqlite3
from pathlib import Path, PurePosixPath, PureWindowsPath

from .config import load_config
from .db import connect, connect_readonly
from .helpers import log_action, now_iso
from .paths import KB_ROOT

__all__ = [
    "build_source_status",
    "cmd_analysis_status",
    "cmd_ingest",
    "cmd_source_content",
    "cmd_source_info",
    "cmd_source_relink",
    "cmd_source_status",
    "cmd_source_update",
    "cmd_source_verify",
    "cmd_sources",
    "cmd_summarize_status",
    "compute_file_hash",
    "portable_path",
    "register_source",
    "resolve_stored_path",
    "source_exists",
    "source_exists_by_hash",
    "update_source_record_ids",
    "verify_sources",
]

SOURCES_DIR = KB_ROOT / "sources"


def _is_absolute_text(raw: str) -> bool:
    return PureWindowsPath(raw).is_absolute() or PurePosixPath(raw).is_absolute() or (
        len(raw) >= 2 and raw[1] == ":"
    )


def _path_name(raw: str) -> str:
    return PureWindowsPath(raw).name if "\\" in raw else PurePosixPath(raw).name


def portable_path(path: Path, base: Path) -> str:
    """POSIX path relative to ``base`` when inside it, else the absolute path.

    Stored source paths are written relative to the KB root so a project keeps
    working after it is moved, cloned elsewhere, or opened from a worktree.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_stored_path(
    stored_path: str | None,
    source_id: str | None = None,
    filename: str | None = None,
) -> Path:
    """Locate a source file recorded in the `sources` table.

    Relative paths resolve against the KB root. Absolute paths written by older
    runtimes are honoured while they exist; once the project has moved they are
    re-rooted under this KB's ``sources/<source_id>/<filename>``.
    """
    raw = str(stored_path or "").strip()
    if raw and not _is_absolute_text(raw):
        return KB_ROOT.joinpath(*PurePosixPath(raw.replace("\\", "/")).parts)
    if raw:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    name = filename or (_path_name(raw) if raw else "")
    if source_id and name:
        rerooted = SOURCES_DIR / source_id / name
        if rerooted.is_file():
            return rerooted
    return Path(raw) if raw else SOURCES_DIR / str(source_id or "")


def source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    return conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone() is not None


def update_source_record_ids(conn: sqlite3.Connection, source_id: str, record_id: str) -> None:
    row = conn.execute("SELECT record_ids_json FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    if row is None:
        return
    current = json.loads(row["record_ids_json"])
    if record_id not in current:
        current.append(record_id)
        conn.execute(
            "UPDATE sources SET record_ids_json = ?, updated_at = ? WHERE source_id = ?",
            (json.dumps(current, ensure_ascii=False), now_iso(), source_id),
        )


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def source_exists_by_hash(conn: sqlite3.Connection, content_hash: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sources WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["tags"] = json.loads(data.pop("tags_json"))
    data["record_ids"] = json.loads(data.pop("record_ids_json"))
    return data


def _source_row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["tags"] = json.loads(data.pop("tags_json"))
    data["record_ids"] = json.loads(data.pop("record_ids_json"))
    return data


def register_source(conn: sqlite3.Connection, source_data: dict) -> dict:
    conn.execute(
        """
        INSERT INTO sources(
            source_id, filename, original_path, stored_path, content_hash,
            file_size, mime_type, ingested_at, updated_at, domain,
            tags_json, notes, record_ids_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_data["source_id"],
            source_data["filename"],
            source_data["original_path"],
            source_data["stored_path"],
            source_data["content_hash"],
            source_data["file_size"],
            source_data["mime_type"],
            source_data["ingested_at"],
            source_data["updated_at"],
            source_data["domain"],
            json.dumps(source_data.get("tags", []), ensure_ascii=False),
            source_data.get("notes"),
            json.dumps([], ensure_ascii=False),
        ),
    )
    log_action(
        conn,
        source_data["source_id"],
        "source_ingest",
        {"filename": source_data["filename"], "content_hash": source_data["content_hash"]},
    )
    conn.commit()
    return source_data


def cmd_ingest(
    args: argparse.Namespace,
    *,
    emit,
    log_operation=None,
    lifecycle_hook=None,
) -> None:
    import sys as _sys

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Source path is not a file: {path}")

    content_hash = compute_file_hash(path)
    conn = connect()

    existing = source_exists_by_hash(conn, content_hash)
    if existing is not None:
        if log_operation is not None:
            log_operation(
                conn, "source_ingest", "ingest",
                {"source_id": existing["source_id"], "skipped": True},
                summary=f"Skipped duplicate {path.name}",
            )
        result = {**existing, "skipped": True, "reason": "duplicate_hash"}
        emit(result, args.json)
        return

    timestamp = now_iso()
    source_id = args.source_id or f"SRC-{timestamp.replace(':', '').replace('-', '').replace('T', '-').replace('Z', '')}-{content_hash[:6]}"
    tags = [tag.strip() for tag in (args.tags or "").split(",") if tag.strip()]

    dest_dir = SOURCES_DIR / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_path = dest_dir / path.name
    shutil.copy2(path, stored_path)

    mime_type, _ = mimetypes.guess_type(path.name)

    source_data = {
        "source_id": source_id,
        "filename": path.name,
        "original_path": portable_path(path, KB_ROOT.parent),
        "stored_path": portable_path(stored_path, KB_ROOT),
        "content_hash": content_hash,
        "file_size": path.stat().st_size,
        "mime_type": mime_type,
        "ingested_at": timestamp,
        "updated_at": timestamp,
        "domain": args.domain,
        "tags": tags,
        "notes": args.notes,
        "record_ids": [],
    }

    register_source(conn, source_data)
    if log_operation is not None:
        log_operation(
            conn, "source_ingest", "ingest",
            {"source_id": source_id, "filename": path.name, "skipped": False},
            summary=f"Ingested {path.name}",
        )
    if (
        lifecycle_hook is not None
        and not getattr(args, "no_auto_lifecycle", False)
    ):
        try:
            lifecycle_hook("source-ingest")
        except Exception as exc:  # lifecycle is best-effort; never break ingest
            print(
                f"Warning: source-ingest lifecycle hook failed: {exc}",
                file=_sys.stderr,
            )
    result = {**source_data, "skipped": False}
    emit(result, args.json)


def cmd_sources(args: argparse.Namespace, *, emit) -> None:
    conn = connect_readonly()
    sql = "SELECT * FROM sources"
    params: list = []
    if args.domain:
        sql += " WHERE domain = ?"
        params.append(args.domain)
    sql += " ORDER BY ingested_at DESC"
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(sql, params).fetchall()
    result = [_source_row_to_dict(row) for row in rows]
    emit(result, args.json)


def cmd_source_info(args: argparse.Namespace, *, emit) -> None:
    conn = connect_readonly()
    row = conn.execute(
        "SELECT * FROM sources WHERE source_id = ?", (args.source_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"Source not found: {args.source_id}")
    emit(_source_row_to_dict(row), args.json)


def cmd_summarize_status(args: argparse.Namespace, *, emit) -> None:
    conn = connect_readonly()
    sql = "SELECT * FROM sources"
    params: list = []
    if getattr(args, "domain", None):
        sql += " WHERE domain = ?"
        params.append(args.domain)
    sql += " ORDER BY ingested_at DESC"
    sources = conn.execute(sql, params).fetchall()
    result = []
    for src in sources:
        source_id = src["source_id"]
        summary_rows = conn.execute(
            "SELECT id FROM records WHERE source_id = ? AND status = 'ATIVO' AND tags_json LIKE '%source-summary%'",
            (source_id,),
        ).fetchall()
        entry = {
            "source_id": source_id,
            "filename": src["filename"],
            "domain": src["domain"],
            "has_summary": len(summary_rows) >= 1,
            "summary_record_id": summary_rows[0]["id"] if summary_rows else None,
        }
        if len(summary_rows) > 1:
            entry["warning"] = "multiple_active_summaries"
            entry["active_summary_ids"] = [r["id"] for r in summary_rows]
        result.append(entry)
    emit(result, args.json)


def cmd_analysis_status(args: argparse.Namespace, *, emit) -> None:
    conn = connect_readonly()
    sql = "SELECT * FROM sources"
    params: list = []
    if getattr(args, "domain", None):
        sql += " WHERE domain = ?"
        params.append(args.domain)
    sql += " ORDER BY ingested_at DESC"
    sources = conn.execute(sql, params).fetchall()
    result = []
    for src in sources:
        source_id = src["source_id"]
        analysis_rows = conn.execute(
            "SELECT id FROM records WHERE source_id = ? AND status = 'ATIVO' AND tags_json LIKE '%filed-analysis%'",
            (source_id,),
        ).fetchall()
        entry = {
            "source_id": source_id,
            "filename": src["filename"],
            "domain": src["domain"],
            "has_analysis": len(analysis_rows) >= 1,
            "analysis_record_id": analysis_rows[0]["id"] if analysis_rows else None,
        }
        if len(analysis_rows) > 1:
            entry["warning"] = "multiple_active_analyses"
            entry["active_analysis_ids"] = [r["id"] for r in analysis_rows]
        result.append(entry)
    emit(result, args.json)


def _read_text_content(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw.decode(encoding)
            # Reject binary content: check for null bytes
            if "\x00" in text:
                continue
            return text, encoding
        except (UnicodeDecodeError, ValueError):
            continue
    raise SystemExit(f"Source file is not a supported text format: {path.name}")


def cmd_source_content(args: argparse.Namespace, *, emit, log_operation=None) -> None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM sources WHERE source_id = ?", (args.source_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"Source not found: {args.source_id}")
    stored = resolve_stored_path(row["stored_path"], row["source_id"], row["filename"])
    if not stored.exists():
        raise SystemExit(f"Source file missing from disk: {stored}")
    text, encoding = _read_text_content(stored)
    if log_operation is not None:
        log_operation(
            conn,
            "source_access",
            "source-content",
            {"source_id": args.source_id, "filename": row["filename"]},
            summary=f"Read {row['filename']}",
        )
    if args.json:
        emit({
            "source_id": args.source_id,
            "filename": row["filename"],
            "content": text,
            "encoding": encoding,
            "size": len(text),
        }, True)
    else:
        print(text)


def build_source_status(
    conn: sqlite3.Connection,
    *,
    domain: str | None = None,
    uncovered: bool = False,
    missing_file: bool = False,
    hash_drift: bool = False,
) -> list[dict]:
    sql = "SELECT * FROM sources"
    params: list = []
    if domain:
        sql += " WHERE domain = ?"
        params.append(domain)
    sql += " ORDER BY ingested_at DESC"
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for src in rows:
        sid = src["source_id"]
        summary = conn.execute(
            "SELECT id FROM records WHERE source_id = ? AND status = 'ATIVO' "
            "AND tags_json LIKE '%source-summary%' LIMIT 1",
            (sid,),
        ).fetchone()
        analysis = conn.execute(
            "SELECT id FROM records WHERE source_id = ? AND status = 'ATIVO' "
            "AND tags_json LIKE '%filed-analysis%' LIMIT 1",
            (sid,),
        ).fetchone()
        linked = conn.execute(
            "SELECT COUNT(*) AS n FROM records WHERE source_id = ? AND status = 'ATIVO'",
            (sid,),
        ).fetchone()
        stored = resolve_stored_path(src["stored_path"], sid, src["filename"])
        stored_exists = stored.is_file()
        hash_ok: bool | None = None
        if stored_exists:
            hash_ok = compute_file_hash(stored) == src["content_hash"]
        entry = {
            "source_id": sid,
            "filename": src["filename"],
            "domain": src["domain"],
            "ingested_at": src["ingested_at"],
            "has_summary": summary is not None,
            "summary_record_id": summary["id"] if summary else None,
            "has_analysis": analysis is not None,
            "analysis_record_id": analysis["id"] if analysis else None,
            "linked_record_count": linked["n"],
            "stored_path_exists": stored_exists,
            "hash_ok": hash_ok,
        }
        is_covered = (
            entry["has_summary"]
            or entry["has_analysis"]
            or entry["linked_record_count"] > 0
        )
        if uncovered and is_covered:
            continue
        if missing_file and entry["stored_path_exists"]:
            continue
        if hash_drift and entry["hash_ok"] is not False:
            continue
        result.append(entry)
    return result


def cmd_source_status(args: argparse.Namespace, *, emit) -> None:
    conn = connect_readonly()
    result = build_source_status(
        conn,
        domain=getattr(args, "domain", None),
        uncovered=bool(getattr(args, "uncovered", False)),
        missing_file=bool(getattr(args, "missing_file", False)),
        hash_drift=bool(getattr(args, "hash_drift", False)),
    )
    emit(result, args.json)


def verify_sources(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM sources").fetchall()
    violations: list[dict] = []
    for src in rows:
        stored = resolve_stored_path(src["stored_path"], src["source_id"], src["filename"])
        if not stored.is_file():
            violations.append({
                "source_id": src["source_id"],
                "filename": src["filename"],
                "issue": "missing_file",
                "stored_path": src["stored_path"],
            })
            continue
        actual_hash = compute_file_hash(stored)
        if actual_hash != src["content_hash"]:
            violations.append({
                "source_id": src["source_id"],
                "filename": src["filename"],
                "issue": "hash_mismatch",
                "expected_hash": src["content_hash"],
                "actual_hash": actual_hash,
            })
    return violations


def cmd_source_verify(args: argparse.Namespace, *, emit, log_operation=None) -> None:
    conn = connect()
    violations = verify_sources(conn)
    total = conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]
    result = {
        "total_sources": total,
        "violation_count": len(violations),
        "violations": violations,
    }
    if log_operation is not None:
        log_operation(
            conn,
            "source_verify",
            "verify",
            {"total": total, "violations": len(violations)},
            summary=f"Verified {total} sources, {len(violations)} violation(s)",
        )
    emit(result, args.json)


def cmd_source_update(args: argparse.Namespace, *, emit, log_operation=None) -> None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM sources WHERE source_id = ?", (args.source_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"Source not found: {args.source_id}")
    updates: list[str] = []
    params: list = []
    fields_changed: list[str] = []
    if getattr(args, "domain", None) is not None:
        updates.append("domain = ?")
        params.append(args.domain)
        fields_changed.append("domain")
    if getattr(args, "tags", None) is not None:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        updates.append("tags_json = ?")
        params.append(json.dumps(tags, ensure_ascii=False))
        fields_changed.append("tags")
    if getattr(args, "notes", None) is not None:
        updates.append("notes = ?")
        params.append(args.notes)
        fields_changed.append("notes")
    if not updates:
        raise SystemExit("No updates specified. Use --domain, --tags, or --notes.")
    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(args.source_id)
    conn.execute(
        f"UPDATE sources SET {', '.join(updates)} WHERE source_id = ?", params
    )
    log_action(
        conn,
        args.source_id,
        "source_update",
        {"fields": fields_changed},
    )
    conn.commit()
    if log_operation is not None:
        log_operation(
            conn,
            "source_update",
            "update",
            {"source_id": args.source_id, "fields": fields_changed},
            summary=f"Updated source {args.source_id}: {', '.join(fields_changed)}",
        )
    new_row = conn.execute(
        "SELECT * FROM sources WHERE source_id = ?", (args.source_id,)
    ).fetchone()
    emit(_source_row_to_dict(new_row), args.json)


def _portable_original(raw: str | None) -> str | None:
    if not raw or not _is_absolute_text(raw):
        return raw
    candidate = Path(raw)
    try:
        return candidate.resolve().relative_to(KB_ROOT.parent.resolve()).as_posix()
    except (OSError, ValueError):
        return raw


def cmd_source_relink(args: argparse.Namespace, *, emit, log_operation=None) -> None:
    """Rewrite legacy absolute source paths as KB-relative paths.

    Only paths whose file is found (in place or re-rooted under this KB's
    sources/ directory) are rewritten; content hashes are never touched.
    """
    conn = connect()
    rows = conn.execute(
        "SELECT source_id, filename, original_path, stored_path FROM sources ORDER BY source_id"
    ).fetchall()
    changed: list[dict] = []
    unresolved: list[dict] = []
    for row in rows:
        resolved = resolve_stored_path(row["stored_path"], row["source_id"], row["filename"])
        if not resolved.is_file():
            unresolved.append({"source_id": row["source_id"], "stored_path": row["stored_path"]})
            continue
        new_stored = portable_path(resolved, KB_ROOT)
        new_original = _portable_original(row["original_path"])
        if new_stored == row["stored_path"] and new_original == row["original_path"]:
            continue
        changed.append(
            {
                "source_id": row["source_id"],
                "stored_path": {"from": row["stored_path"], "to": new_stored},
                "original_path": {"from": row["original_path"], "to": new_original},
            }
        )
        if not args.dry_run:
            conn.execute(
                "UPDATE sources SET stored_path = ?, original_path = ? WHERE source_id = ?",
                (new_stored, new_original, row["source_id"]),
            )
            log_action(conn, row["source_id"], "source_relink", {"stored_path": new_stored})
    if changed and not args.dry_run:
        conn.commit()
        if log_operation is not None:
            log_operation(
                conn,
                "source_update",
                "relink",
                {"changed": len(changed), "unresolved": len(unresolved)},
                summary=f"Relinked {len(changed)} source path(s) as KB-relative",
            )
    payload = {
        "total_sources": len(rows),
        "changed_count": len(changed),
        "unresolved_count": len(unresolved),
        "dry_run": bool(args.dry_run),
        "changed": changed,
        "unresolved": unresolved,
    }
    if args.json:
        emit(payload, True)
        return
    suffix = " (dry run)" if args.dry_run else ""
    lines = [
        f"Source relink{suffix}: {len(changed)} changed, "
        f"{len(unresolved)} unresolved, {len(rows)} total"
    ]
    lines.extend(f"  {item['source_id']}: {item['stored_path']['to']}" for item in changed)
    lines.extend(f"  unresolved {item['source_id']}: {item['stored_path']}" for item in unresolved)
    emit({"__plain__": True, "text": "\n".join(lines)}, False)
