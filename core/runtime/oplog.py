from __future__ import annotations

import argparse
import json
import sqlite3

from .db import connect
from .helpers import now_iso

__all__ = [
    "cmd_oplog",
    "get_recent_operations",
    "log_operation",
]


def log_operation(
    conn: sqlite3.Connection,
    category: str,
    event: str,
    details: dict,
    summary: str | None = None,
    *,
    commit: bool = True,
) -> int:
    cur = conn.execute(
        "INSERT INTO operations(category, event, happened_at, details_json, summary) VALUES(?, ?, ?, ?, ?)",
        (category, event, now_iso(), json.dumps(details, ensure_ascii=False), summary),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_recent_operations(
    conn: sqlite3.Connection,
    category: str | None = None,
    limit: int = 20,
) -> list[dict]:
    sql = "SELECT * FROM operations"
    params: list = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY op_id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["details"] = json.loads(d.pop("details_json"))
        result.append(d)
    return result


def cmd_oplog(args: argparse.Namespace, *, emit) -> None:
    conn = connect()
    ops = get_recent_operations(conn, category=args.category, limit=args.limit)
    if args.json:
        emit(ops, True)
        return
    if not ops:
        emit({"__plain__": True, "text": "No operations found."}, False)
        return
    lines = [f"Recent operations ({len(ops)})", ""]
    for op in ops:
        lines.append(f"  [{op['op_id']}] {op['category']}/{op['event']} at {op['happened_at']}")
        if op.get("summary"):
            lines.append(f"    {op['summary']}")
        lines.append("")
    emit({"__plain__": True, "text": "\n".join(lines)}, False)
