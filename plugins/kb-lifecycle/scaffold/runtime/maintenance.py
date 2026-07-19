from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

from .config import load_config
from .db import connect
from .helpers import log_action, now_iso, row_to_dict, upsert_fts
from .paths import DB_PATH, KB_ROOT


def connect_readonly() -> sqlite3.Connection:
    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_audit_tiers_result(conn: sqlite3.Connection, config: dict) -> dict:
    hot_limit = config.get("hot_session_limit", 12)
    hot_count = conn.execute(
        "SELECT COUNT(*) FROM records WHERE tier = 'HOT' AND status = 'ATIVO'"
    ).fetchone()[0]
    stale_hot = [
        row_to_dict(row)
        for row in conn.execute(
            "SELECT * FROM records WHERE tier = 'HOT' AND status = 'ATIVO' AND review_after IS NOT NULL AND review_after < ? ORDER BY review_after ASC",
            (dt.date.today().isoformat(),),
        ).fetchall()
    ]
    expired_premises = [
        row_to_dict(row)
        for row in conn.execute(
            "SELECT * FROM records WHERE category = 'PREMISSA' AND status = 'ATIVO' AND valid_until IS NOT NULL AND valid_until < ? ORDER BY valid_until ASC",
            (dt.date.today().isoformat(),),
        ).fetchall()
    ]
    return {
        "hot_limit": hot_limit,
        "hot_count": hot_count,
        "hot_over_limit": hot_count > hot_limit,
        "stale_hot": stale_hot,
        "expired_premises": expired_premises,
    }


def get_duplicate_groups(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT category, domain, lower(title) AS title_key, COUNT(*) AS count
            FROM records
            WHERE status = 'ATIVO'
            GROUP BY category, domain, lower(title)
            HAVING COUNT(*) > 1
            ORDER BY count DESC, domain ASC
            """
        ).fetchall()
    ]


HYGIENE_GROUP_KEYS = [
    "keep_hot",
    "demote_candidate",
    "supersede_or_merge_candidate",
    "resolve_candidate",
    "needs_sponsor",
]


def _hygiene_record(row: sqlite3.Row, *, reason: str, recommendation: str) -> dict:
    data = row_to_dict(row)
    return {
        "record_id": data["id"],
        "title": data["title"],
        "category": data["category"],
        "domain": data["domain"],
        "status": data["status"],
        "tier": data["tier"],
        "confidence": data.get("confidence"),
        "review_after": data.get("review_after"),
        "valid_until": data.get("valid_until"),
        "source_id": data.get("source_id"),
        "reason": reason,
        "recommendation": recommendation,
    }


def _duplicate_group_records(conn: sqlite3.Connection, group: dict) -> list[str]:
    rows = conn.execute(
        """
        SELECT id
        FROM records
        WHERE status = 'ATIVO'
          AND category = ?
          AND domain = ?
          AND lower(title) = ?
        ORDER BY updated_at DESC, id ASC
        """,
        (group["category"], group["domain"], group["title_key"]),
    ).fetchall()
    return [row["id"] for row in rows]


def build_hygiene_audit_result(conn: sqlite3.Connection, config: dict) -> dict:
    today = dt.date.today().isoformat()
    tier_audit = build_audit_tiers_result(conn, config)
    hot_rows = conn.execute(
        """
        SELECT *
        FROM records
        WHERE tier = 'HOT' AND status = 'ATIVO'
        ORDER BY
          CASE WHEN review_after IS NULL THEN '9999-12-31' ELSE review_after END ASC,
          COALESCE(confidence, 0.0) ASC,
          updated_at ASC,
          id ASC
        """
    ).fetchall()
    stale_hot_ids = {row["id"] for row in tier_audit["stale_hot"]}
    groups = {key: [] for key in HYGIENE_GROUP_KEYS}

    demote_ids: set[str] = set()
    for row in hot_rows:
        if row["id"] in stale_hot_ids:
            demote_ids.add(row["id"])
            groups["demote_candidate"].append(
                _hygiene_record(
                    row,
                    reason="stale_hot_review_after_elapsed",
                    recommendation="review and demote from HOT if no longer session-critical",
                )
            )

    hot_limit = int(tier_audit["hot_limit"])
    overflow_needed = max(
        0,
        int(tier_audit["hot_count"]) - hot_limit - len(demote_ids),
    )
    for row in hot_rows:
        if overflow_needed <= 0:
            break
        if row["id"] in demote_ids:
            continue
        demote_ids.add(row["id"])
        overflow_needed -= 1
        groups["demote_candidate"].append(
            _hygiene_record(
                row,
                reason="hot_over_limit",
                recommendation="review HOT budget and demote if this is not among the active working set",
            )
        )

    for row in hot_rows:
        if row["id"] in demote_ids:
            continue
        groups["keep_hot"].append(
            _hygiene_record(
                row,
                reason="within_hot_budget",
                recommendation="keep HOT unless semantic review says otherwise",
            )
        )

    duplicate_groups = get_duplicate_groups(conn)
    for group in duplicate_groups:
        record_ids = _duplicate_group_records(conn, group)
        groups["supersede_or_merge_candidate"].append(
            {
                **group,
                "record_ids": record_ids,
                "reason": "duplicate_active_title",
                "recommendation": "review for supersede, merge, or explicit keep-separate rationale",
            }
        )

    pending_rows = conn.execute(
        """
        SELECT *
        FROM records
        WHERE category = 'PENDENCIA'
          AND status = 'ATIVO'
          AND review_after IS NOT NULL
          AND review_after < ?
        ORDER BY review_after ASC, updated_at ASC, id ASC
        """,
        (today,),
    ).fetchall()
    for row in pending_rows:
        groups["resolve_candidate"].append(
            _hygiene_record(
                row,
                reason="pending_review_after_elapsed",
                recommendation="review whether this pendencia should be resolved or re-dated",
            )
        )

    expired_ids = {row["id"] for row in tier_audit["expired_premises"]}
    for row in conn.execute(
        """
        SELECT *
        FROM records
        WHERE category = 'PREMISSA'
          AND status = 'ATIVO'
          AND valid_until IS NOT NULL
          AND valid_until < ?
        ORDER BY valid_until ASC, updated_at ASC, id ASC
        """,
        (today,),
    ).fetchall():
        if row["id"] not in expired_ids:
            continue
        groups["needs_sponsor"].append(
            _hygiene_record(
                row,
                reason="expired_premise",
                recommendation="Owner review required before treating this premise as current",
            )
        )

    return {
        "event": "hygiene-audit",
        "generated_at": now_iso(),
        "read_only": True,
        **tier_audit,
        "duplicate_groups": duplicate_groups,
        "groups": groups,
    }


def apply_stale_hot_demotions(conn: sqlite3.Connection, reason: str) -> list[str]:
    stale_rows = conn.execute(
        "SELECT id FROM records WHERE tier = 'HOT' AND status = 'ATIVO' AND review_after IS NOT NULL AND review_after < ?",
        (dt.date.today().isoformat(),),
    ).fetchall()
    demoted = []
    for row in stale_rows:
        conn.execute(
            "UPDATE records SET tier = 'WARM', tier_reason = ?, updated_at = ?, tier_changed_at = ? WHERE id = ?",
            (reason, now_iso(), now_iso(), row["id"]),
        )
        upsert_fts(conn, row["id"])
        log_action(conn, row["id"], "demote_hot", {"reason": reason})
        demoted.append(row["id"])
    if demoted:
        conn.commit()
    return demoted


def apply_cold_demotions(conn: sqlite3.Connection, reason: str) -> list[str]:
    """Demote WARM records to COLD when they have not been accessed within
    the configured cold_after_days window. Records with NULL last_accessed_at
    use created_at as the baseline so newly-created records are not demoted
    on their first maintenance pass.

    Deterministic: a single SQL predicate decides eligibility.
    """
    config = load_config()
    retention = config.get("retention", {}) or {}
    days = int(retention.get("cold_after_days", 90))
    if days <= 0:
        return []
    cutoff_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    cutoff_iso = (
        cutoff_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    stale_rows = conn.execute(
        "SELECT id FROM records "
        "WHERE tier = 'WARM' AND status = 'ATIVO' "
        "AND COALESCE(last_accessed_at, created_at) < ?",
        (cutoff_iso,),
    ).fetchall()
    demoted: list[str] = []
    for row in stale_rows:
        now = now_iso()
        conn.execute(
            "UPDATE records SET tier = 'COLD', tier_reason = ?, "
            "updated_at = ?, tier_changed_at = ? WHERE id = ?",
            (reason, now, now, row["id"]),
        )
        upsert_fts(conn, row["id"])
        log_action(conn, row["id"], "demote_cold", {"reason": reason, "cutoff": cutoff_iso})
        demoted.append(row["id"])
    if demoted:
        conn.commit()
    return demoted


def prune_snapshots(
    conn: sqlite3.Connection,
    *,
    keep_last_n: int = 5,
    dry_run: bool = False,
) -> dict:
    """Keep the most recent N snapshots per live page; remove older ones
    from wiki_snapshots, wiki_pages (page_class='snapshot'),
    wiki_page_provenance, and from disk. Deterministic by taken_at DESC.

    dry_run=True skips DB + filesystem mutations and returns the plan.
    """
    if keep_last_n < 0:
        keep_last_n = 0
    groups = conn.execute(
        "SELECT live_page_id, COUNT(*) AS n FROM wiki_snapshots "
        "GROUP BY live_page_id HAVING COUNT(*) > ?",
        (keep_last_n,),
    ).fetchall()
    pruned_ids: list[str] = []
    pruned_files: list[str] = []
    for group in groups:
        live_id = group["live_page_id"]
        overflow = conn.execute(
            "SELECT snapshot_id, stored_path FROM wiki_snapshots "
            "WHERE live_page_id = ? ORDER BY taken_at DESC, snapshot_id DESC "
            "LIMIT -1 OFFSET ?",
            (live_id, keep_last_n),
        ).fetchall()
        for row in overflow:
            sid = row["snapshot_id"]
            stored = row["stored_path"]
            pruned_ids.append(sid)
            if stored:
                pruned_files.append(stored)
            if dry_run:
                continue
            conn.execute("DELETE FROM wiki_snapshots WHERE snapshot_id = ?", (sid,))
            conn.execute("DELETE FROM wiki_page_provenance WHERE page_id = ?", (sid,))
            conn.execute("DELETE FROM wiki_pages WHERE page_id = ?", (sid,))
            if stored:
                candidate_path = (
                    KB_ROOT / stored if not Path(stored).is_absolute() else Path(stored)
                )
                try:
                    if candidate_path.is_file():
                        candidate_path.unlink()
                except OSError:
                    pass
    if not dry_run and pruned_ids:
        conn.commit()
    return {
        "keep_last_n": keep_last_n,
        "pruned_count": len(pruned_ids),
        "pruned_snapshot_ids": pruned_ids,
        "pruned_files": pruned_files,
        "dry_run": dry_run,
    }


def build_consolidate_result(
    conn: sqlite3.Connection,
    args: argparse.Namespace,
    *,
    refresh_exports,
) -> dict:
    duplicates = get_duplicate_groups(conn)
    demoted = []
    if args.apply_demotions:
        demoted = apply_stale_hot_demotions(conn, "Automatic demotion during consolidate")
    refresh_exports()
    return {
        "duplicates": duplicates,
        "applied_demotions": args.apply_demotions,
        "demoted_records": demoted,
    }


def cmd_audit_tiers(args: argparse.Namespace, *, emit) -> None:
    config = load_config()
    conn = connect()
    result = build_audit_tiers_result(conn, config)
    emit(result, True)


def cmd_hygiene_audit(args: argparse.Namespace, *, emit) -> None:
    config = load_config()
    conn = connect_readonly()
    result = build_hygiene_audit_result(conn, config)
    emit(result, True)


def cmd_consolidate(args: argparse.Namespace, *, emit, refresh_exports) -> None:
    conn = connect()
    result = build_consolidate_result(conn, args, refresh_exports=refresh_exports)
    emit(result, True)
