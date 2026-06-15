from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import uuid
from pathlib import Path

from .constants import CATEGORIES, STATUSES, TIERS
from .config import load_config
from .db import connect
from .filing_policy import evaluate_filing, get_filing_policy
from .helpers import log_action, now_iso, record_exists, row_to_dict, upsert_fts
from .paths import KB_ROOT, ensure_dirs
from .sources import source_exists, update_source_record_ids

__all__ = [
    "FILING_TYPES",
    "base_record_from_args",
    "cmd_bulk_import",
    "cmd_create",
    "cmd_file",
    "cmd_filing_status",
    "cmd_get",
    "cmd_init",
    "cmd_list",
    "cmd_pending",
    "cmd_raw_query",
    "cmd_resolve",
    "cmd_search",
    "cmd_stats",
    "cmd_supersede",
    "cmd_update",
    "fetch_filtered",
    "insert_record",
    "validate_record",
]

FILING_TYPES = {
    "answer": "filed-answer",
    "analysis": "filed-analysis",
    "synthesis": "filed-synthesis",
}


def validate_record(data: dict) -> None:
    if data["category"] not in CATEGORIES:
        raise SystemExit(f"Invalid category: {data['category']}")
    if data["status"] not in STATUSES:
        raise SystemExit(f"Invalid status: {data['status']}")
    if data["tier"] not in TIERS:
        raise SystemExit(f"Invalid tier: {data['tier']}")


def base_record_from_args(args: argparse.Namespace) -> dict:
    timestamp = now_iso()
    record_id = args.id or f"KB-{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    tags = [tag.strip() for tag in (args.tags or "").split(",") if tag.strip()]
    return {
        "id": record_id,
        "category": args.category,
        "domain": args.domain,
        "title": args.title,
        "content": args.content,
        "status": args.status,
        "tier": args.tier,
        "source": args.source,
        "tags": tags,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status_changed_at": timestamp,
        "tier_changed_at": timestamp,
        "tier_reason": args.tier_reason,
        "review_after": args.review_after,
        "valid_until": args.valid_until,
        "confidence": args.confidence,
        "replacement_id": None,
        "supersedes_id": None,
        "observed_at": getattr(args, "observed_at", None),
        "resolution_notes": None,
        "resolved_at": None,
        "source_id": getattr(args, "source_id", None),
    }


def insert_record(conn: sqlite3.Connection, data: dict, action: str = "create") -> dict:
    validate_record(data)
    sid = data.get("source_id")
    if sid is not None and not source_exists(conn, sid):
        raise SystemExit(f"Source not found: {sid}")
    conn.execute(
        """
        INSERT INTO records(
            id, category, domain, title, content, status, tier, source, tags_json,
            created_at, updated_at, status_changed_at, tier_changed_at, tier_reason,
            review_after, valid_until, confidence, replacement_id, supersedes_id,
            observed_at, resolution_notes, resolved_at, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["id"],
            data["category"],
            data["domain"],
            data["title"],
            data["content"],
            data["status"],
            data["tier"],
            data["source"],
            json.dumps(data["tags"], ensure_ascii=False),
            data["created_at"],
            data["updated_at"],
            data["status_changed_at"],
            data["tier_changed_at"],
            data["tier_reason"],
            data["review_after"],
            data["valid_until"],
            data["confidence"],
            data["replacement_id"],
            data["supersedes_id"],
            data["observed_at"],
            data["resolution_notes"],
            data["resolved_at"],
            sid,
        ),
    )
    upsert_fts(conn, data["id"])
    log_action(conn, data["id"], action, {"title": data["title"], "status": data["status"]})
    if sid is not None:
        update_source_record_ids(conn, sid, data["id"])
    conn.commit()
    return data


def fetch_filtered(conn: sqlite3.Connection, base_sql: str, params: list, args: argparse.Namespace) -> list[dict]:
    clauses = []
    if getattr(args, "category", None):
        clauses.append("category = ?")
        params.append(args.category)
    if getattr(args, "domain", None):
        clauses.append("domain = ?")
        params.append(args.domain)
    if getattr(args, "status", None):
        clauses.append("status = ?")
        params.append(args.status)
    if getattr(args, "tier", None):
        clauses.append("tier = ?")
        params.append(args.tier)
    sql = base_sql
    if clauses:
        sql += " AND " + " AND ".join(clauses) if " WHERE " in base_sql else " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"
    if getattr(args, "limit", None):
        sql += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace, *, emit, bulk_import_fn=None) -> None:
    config = load_config()
    ensure_dirs(config)
    conn = connect()
    conn.close()
    if args.seed:
        args.path = args.seed
        if bulk_import_fn is not None:
            bulk_import_fn(args)
    emit({"__plain__": True, "text": f"KB initialized at {KB_ROOT}"}, False)


def cmd_create(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    data = base_record_from_args(args)
    emit(insert_record(conn, data), args.json)


def cmd_list(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    emit(fetch_filtered(conn, "SELECT * FROM records", [], args), args.json)


def cmd_get(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    row = conn.execute("SELECT * FROM records WHERE id = ?", (args.record_id,)).fetchone()
    if row is None:
        raise SystemExit(f"Record not found: {args.record_id}")
    conn.execute(
        "UPDATE records SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
        (now_iso(), args.record_id),
    )
    conn.commit()
    emit(row_to_dict(row), args.json)


def cmd_search(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    try:
        base_sql = (
            "SELECT r.* FROM records_fts f "
            "JOIN records r ON r.id = f.id "
            "WHERE records_fts MATCH ?"
        )
        records = fetch_filtered(conn, base_sql, [args.query], args)
    except sqlite3.OperationalError:
        like = f"%{args.query}%"
        base_sql = "SELECT * FROM records WHERE (title LIKE ? OR content LIKE ? OR tags_json LIKE ?)"
        records = fetch_filtered(conn, base_sql, [like, like, like], args)
    emit(records, args.json)


def cmd_update(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    row = conn.execute("SELECT * FROM records WHERE id = ?", (args.record_id,)).fetchone()
    if row is None:
        raise SystemExit(f"Record not found: {args.record_id}")
    updates = {}
    for field in ("tier", "tier_reason", "review_after", "valid_until", "confidence", "source"):
        value = getattr(args, field)
        if value is not None:
            updates[field] = value
    if args.tags is not None:
        updates["tags_json"] = json.dumps([tag.strip() for tag in args.tags.split(",") if tag.strip()])
    if not updates:
        raise SystemExit("No mutable fields provided. Use supersede if the meaning changed.")
    updates["updated_at"] = now_iso()
    if "tier" in updates:
        if updates["tier"] not in TIERS:
            raise SystemExit(f"Invalid tier: {updates['tier']}")
        updates["tier_changed_at"] = now_iso()
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(
        f"UPDATE records SET {set_clause} WHERE id = ?",
        list(updates.values()) + [args.record_id],
    )
    upsert_fts(conn, args.record_id)
    log_action(conn, args.record_id, "update", updates)
    conn.commit()
    cmd_get(argparse.Namespace(record_id=args.record_id, json=args.json), emit=emit)


def cmd_supersede(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    old_row = conn.execute("SELECT * FROM records WHERE id = ?", (args.record_id,)).fetchone()
    if old_row is None:
        raise SystemExit(f"Record not found: {args.record_id}")
    old = row_to_dict(old_row)
    new_data = {
        **old,
        "id": args.new_id or f"{old['id']}-S{uuid.uuid4().hex[:4]}",
        "title": args.title or old["title"],
        "content": args.content or old["content"],
        "status": "ATIVO",
        "tier": args.tier or old["tier"],
        "source": args.source or old["source"],
        "tags": [tag.strip() for tag in (args.tags or ",".join(old["tags"])).split(",") if tag.strip()],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status_changed_at": now_iso(),
        "tier_changed_at": now_iso(),
        "tier_reason": args.tier_reason or old.get("tier_reason"),
        "review_after": args.review_after or old.get("review_after"),
        "valid_until": args.valid_until or old.get("valid_until"),
        "confidence": args.confidence if args.confidence is not None else old.get("confidence"),
        "replacement_id": None,
        "supersedes_id": old["id"],
        "observed_at": old.get("observed_at"),
        "resolution_notes": None,
        "resolved_at": None,
        "source_id": getattr(args, "source_id", None) or old.get("source_id"),
    }
    insert_record(conn, new_data, action="supersede_create")
    conn.execute(
        "UPDATE records SET status = 'SUPERSEDIDO', replacement_id = ?, updated_at = ?, status_changed_at = ? WHERE id = ?",
        (new_data["id"], now_iso(), now_iso(), old["id"]),
    )
    upsert_fts(conn, old["id"])
    log_action(conn, old["id"], "superseded", {"replacement_id": new_data["id"]})
    conn.commit()
    emit(new_data, args.json)


def cmd_resolve(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    conn.execute(
        """
        UPDATE records
        SET status = 'RESOLVIDO',
            resolution_notes = ?,
            resolved_at = ?,
            updated_at = ?,
            status_changed_at = ?
        WHERE id = ? AND category = 'PENDENCIA'
        """,
        (args.notes, now_iso(), now_iso(), now_iso(), args.record_id),
    )
    if conn.total_changes == 0:
        raise SystemExit("Resolve applies only to existing PENDENCIA records.")
    upsert_fts(conn, args.record_id)
    log_action(conn, args.record_id, "resolve", {"notes": args.notes})
    conn.commit()
    cmd_get(argparse.Namespace(record_id=args.record_id, json=args.json), emit=emit)


def cmd_pending(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    today = dt.date.today().isoformat()
    payload = {
        "open_pending": fetch_filtered(
            conn,
            "SELECT * FROM records WHERE category = 'PENDENCIA' AND status = 'ATIVO'",
            [],
            argparse.Namespace(category=None, domain=args.domain, status=None, tier=None, limit=args.limit),
        ),
        "expired_premises": fetch_filtered(
            conn,
            "SELECT * FROM records WHERE category = 'PREMISSA' AND status = 'ATIVO' AND valid_until IS NOT NULL AND valid_until < ?",
            [today],
            argparse.Namespace(category=None, domain=args.domain, status=None, tier=None, limit=args.limit),
        ),
    }
    if args.json:
        emit(payload, True)
        return
    lines = ["Open pendencias:"]
    lines.extend([f"- {item['id']} {item['title']}" for item in payload["open_pending"]] or ["- none"])
    lines.append("")
    lines.append("Expired premises:")
    lines.extend([f"- {item['id']} {item['title']}" for item in payload["expired_premises"]] or ["- none"])
    emit({"__plain__": True, "text": "\n".join(lines)}, False)


def cmd_stats(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    summary = {
        "total_records": conn.execute("SELECT COUNT(*) FROM records").fetchone()[0],
        "by_category": dict(conn.execute("SELECT category, COUNT(*) FROM records GROUP BY category").fetchall()),
        "by_status": dict(conn.execute("SELECT status, COUNT(*) FROM records GROUP BY status").fetchall()),
        "by_tier": dict(conn.execute("SELECT tier, COUNT(*) FROM records GROUP BY tier").fetchall()),
        "by_domain": dict(conn.execute("SELECT domain, COUNT(*) FROM records GROUP BY domain").fetchall()),
    }
    emit(summary, True)


def cmd_file(
    args: argparse.Namespace,
    *,
    emit,
    log_operation=None,
    lifecycle_hook=None,
) -> None:
    """Thin convenience wrapper: create a KB record with explicit filing intent."""
    import sys as _sys

    conn = connect()
    data = base_record_from_args(args)
    filing_tag = FILING_TYPES[args.filing_type]
    if filing_tag not in data["tags"]:
        data["tags"].append(filing_tag)

    policy = get_filing_policy(load_config())
    enforcement_mode = policy.get("enforcement_mode", "advisory")
    violations: list[dict] = []
    if enforcement_mode != "off":
        violations = evaluate_filing(policy, args.filing_type, data)
    if violations and enforcement_mode == "strict":
        lines = ["Filing rejected (enforcement_mode=strict):"]
        for v in violations:
            lines.append(f"  [{v['issue']}] {v['field']}: {v['detail']}")
        raise SystemExit("\n".join(lines))
    if violations and enforcement_mode == "advisory":
        print("Filing advisory warnings:", file=_sys.stderr)
        for v in violations:
            print(f"  [{v['issue']}] {v['field']}: {v['detail']}", file=_sys.stderr)

    result = insert_record(conn, data, action="file")
    if log_operation is not None:
        log_operation(
            conn,
            "record_filing",
            f"file-{args.filing_type}",
            {
                "filing_type": args.filing_type,
                "record_id": data["id"],
                "domain": data["domain"],
                "category": data["category"],
                "confidence": data["confidence"],
                "source_id": data.get("source_id"),
                "title": data["title"],
                "enforcement_mode": enforcement_mode,
                "violations": violations,
            },
            summary=f"Filed {args.filing_type}: {data['title']}",
        )
    if (
        lifecycle_hook is not None
        and not getattr(args, "no_auto_lifecycle", False)
    ):
        try:
            lifecycle_hook("record-filed")
        except Exception as exc:  # lifecycle is best-effort; never break filing
            print(
                f"Warning: record-filed lifecycle hook failed: {exc}",
                file=_sys.stderr,
            )
    emit(result, args.json)


def cmd_filing_status(args: argparse.Namespace, *, emit) -> None:
    """Show counts and distribution of filed records by type, domain, confidence."""
    conn = connect()
    tag_clauses = " OR ".join(
        f"tags_json LIKE '%{tag}%'" for tag in FILING_TYPES.values()
    )
    domain_filter = ""
    params: list = []
    if getattr(args, "domain", None):
        domain_filter = " AND domain = ?"
        params.append(args.domain)
    rows = conn.execute(
        f"SELECT id, category, domain, title, tags_json, confidence, source_id "
        f"FROM records WHERE status = 'ATIVO' AND ({tag_clauses}){domain_filter} "
        f"ORDER BY updated_at DESC",
        params,
    ).fetchall()

    policy = get_filing_policy(load_config())
    bands = policy.get("confidence_bands", {}) or {}
    band_high = bands.get("high", 0.8)
    band_review = bands.get("review", 0.55)

    by_type: dict[str, int] = {"answer": 0, "analysis": 0, "synthesis": 0}
    by_domain: dict[str, int] = {}
    by_confidence: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    items: list[dict] = []
    for row in rows:
        tags = json.loads(row["tags_json"])
        for ftype, ftag in FILING_TYPES.items():
            if ftag in tags:
                by_type[ftype] += 1
                break
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
        conf = row["confidence"] if row["confidence"] is not None else band_high
        if conf >= band_high:
            by_confidence["high"] += 1
        elif conf >= band_review:
            by_confidence["medium"] += 1
        else:
            by_confidence["low"] += 1
        items.append({
            "id": row["id"],
            "category": row["category"],
            "domain": row["domain"],
            "title": row["title"],
            "confidence": row["confidence"],
            "source_id": row["source_id"],
        })

    # Gap analysis: domains with active records but no filings
    all_domains = conn.execute(
        "SELECT DISTINCT domain FROM records WHERE status = 'ATIVO'"
    ).fetchall()
    filed_domains = set(by_domain.keys())
    gaps = [d["domain"] for d in all_domains if d["domain"] not in filed_domains]

    result = {
        "total_filed": len(rows),
        "by_type": by_type,
        "by_domain": by_domain,
        "by_confidence": by_confidence,
        "gaps": gaps,
        "items": items,
    }

    if args.json:
        emit(result, True)
        return

    lines = [f"Filing status: {len(rows)} filed record(s)"]
    if by_type["answer"] or by_type["analysis"] or by_type["synthesis"]:
        lines.append(f"  answers: {by_type['answer']}  analyses: {by_type['analysis']}  syntheses: {by_type['synthesis']}")
    if by_domain:
        lines.append(f"  domains: {', '.join(f'{d}({c})' for d, c in sorted(by_domain.items()))}")
    if by_confidence["medium"] or by_confidence["low"]:
        lines.append(f"  confidence: high={by_confidence['high']} medium={by_confidence['medium']} low={by_confidence['low']}")
    if gaps:
        lines.append(f"  gaps (domains with records but no filings): {', '.join(gaps)}")
    for item in items[:10]:
        lines.append(f"  - [{item['id']}] {item['category']} {item['domain']}: {item['title']}")
    if len(items) > 10:
        lines.append(f"  ... and {len(items) - 10} more")
    emit({"__plain__": True, "text": "\n".join(lines)}, False)


def cmd_raw_query(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    rows = conn.execute(args.sql).fetchall()
    emit([dict(row) for row in rows], True)


def cmd_bulk_import(args: argparse.Namespace, *, emit) -> None:
    path = Path(args.path)
    if not path.is_absolute():
        path = KB_ROOT / path
    if not path.exists():
        raise SystemExit(f"Seed file not found: {path}")
    conn = connect()
    imported = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if record_exists(conn, data["id"]):
            continue
        data.setdefault("status", "ATIVO")
        data.setdefault("tier", "WARM")
        data.setdefault("source", "bulk-import")
        data.setdefault("tags", [])
        data.setdefault("created_at", now_iso())
        data.setdefault("updated_at", data["created_at"])
        data.setdefault("status_changed_at", data["created_at"])
        data.setdefault("tier_changed_at", data["created_at"])
        data.setdefault("tier_reason", None)
        data.setdefault("source_id", None)
        data.setdefault("review_after", None)
        data.setdefault("valid_until", None)
        data.setdefault("confidence", None)
        data.setdefault("replacement_id", None)
        data.setdefault("supersedes_id", None)
        data.setdefault("observed_at", None)
        data.setdefault("resolution_notes", None)
        data.setdefault("resolved_at", None)
        insert_record(conn, data, action="bulk_import")
        imported += 1
    emit({"__plain__": True, "text": f"Imported {imported} records from {path}"}, False)
