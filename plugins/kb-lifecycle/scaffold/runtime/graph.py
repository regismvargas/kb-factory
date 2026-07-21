from __future__ import annotations

import json
import secrets
import sqlite3
from argparse import Namespace

from .db import connect
from .helpers import log_action, now_iso, record_exists
from .oplog import log_operation


EDGE_TYPES = ("depends-on", "contradicts", "duplicates")
ACTOR_RUNTIMES = ("human", "codex", "claude-code", "cowork")
SYMMETRIC_EDGE_TYPES = frozenset({"contradicts", "duplicates"})


def _fail(args: Namespace, code: str, message: str) -> None:
    payload = {"status": "error", "error_code": code, "message": message}
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    raise SystemExit(f"{code}: {message}")


def _canonical_endpoints(source_id: str, relation_type: str, target_id: str) -> tuple[str, str]:
    if relation_type in SYMMETRIC_EDGE_TYPES:
        return tuple(sorted((source_id, target_id)))  # type: ignore[return-value]
    return source_id, target_id


def _edge_id() -> str:
    stamp = now_iso().replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    return f"KBE-{stamp}-{secrets.token_hex(4)}"


def _edge_payload(row: sqlite3.Row) -> dict:
    return dict(row)


def add_edge(
    conn: sqlite3.Connection,
    *,
    source_record_id: str,
    relation_type: str,
    target_record_id: str,
    actor: str,
    actor_runtime: str,
    note: str | None,
) -> dict:
    if relation_type not in EDGE_TYPES:
        raise ValueError(
            "EDGE_TYPE_INVALID: allowed vocabulary is " + ", ".join(EDGE_TYPES)
        )
    if actor_runtime not in ACTOR_RUNTIMES:
        raise ValueError(
            "ACTOR_RUNTIME_INVALID: allowed runtimes are " + ", ".join(ACTOR_RUNTIMES)
        )
    if not actor.strip():
        raise ValueError("ACTOR_REQUIRED: actor must be non-empty")
    if source_record_id == target_record_id:
        raise ValueError("EDGE_SELF: source and target must differ")
    missing = [
        record_id
        for record_id in (source_record_id, target_record_id)
        if not record_exists(conn, record_id)
    ]
    if missing:
        raise ValueError("EDGE_ENDPOINT_MISSING: " + ", ".join(sorted(missing)))
    source_record_id, target_record_id = _canonical_endpoints(
        source_record_id, relation_type, target_record_id
    )
    existing = conn.execute(
        "SELECT edge_id FROM record_edges "
        "WHERE source_record_id = ? AND relation_type = ? "
        "AND target_record_id = ? AND removed_at IS NULL",
        (source_record_id, relation_type, target_record_id),
    ).fetchone()
    if existing is not None:
        raise ValueError(f"EDGE_DUPLICATE_ACTIVE: {existing['edge_id']}")

    happened_at = now_iso()
    edge_id = _edge_id()
    conn.execute(
        "INSERT INTO record_edges("
        "edge_id, source_record_id, target_record_id, relation_type, "
        "created_by, created_by_runtime, created_at, note"
        ") VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (
            edge_id,
            source_record_id,
            target_record_id,
            relation_type,
            actor,
            actor_runtime,
            happened_at,
            note,
        ),
    )
    details = {
        "edge_id": edge_id,
        "source_record_id": source_record_id,
        "target_record_id": target_record_id,
        "relation_type": relation_type,
        "actor": actor,
        "actor_runtime": actor_runtime,
        "note": note,
    }
    for record_id in sorted({source_record_id, target_record_id}):
        log_action(conn, record_id, "graph_edge_added", details)
    log_operation(
        conn,
        "graph",
        "edge-add",
        details,
        summary=f"{relation_type}: {source_record_id} -> {target_record_id}",
        commit=False,
    )
    row = conn.execute("SELECT * FROM record_edges WHERE edge_id = ?", (edge_id,)).fetchone()
    return _edge_payload(row)


def remove_edge(
    conn: sqlite3.Connection,
    *,
    edge_id: str,
    actor: str,
    actor_runtime: str,
    note: str | None,
) -> dict:
    if actor_runtime not in ACTOR_RUNTIMES:
        raise ValueError(
            "ACTOR_RUNTIME_INVALID: allowed runtimes are " + ", ".join(ACTOR_RUNTIMES)
        )
    if not actor.strip():
        raise ValueError("ACTOR_REQUIRED: actor must be non-empty")
    row = conn.execute("SELECT * FROM record_edges WHERE edge_id = ?", (edge_id,)).fetchone()
    if row is None:
        raise ValueError(f"EDGE_NOT_FOUND: {edge_id}")
    if row["removed_at"] is not None:
        raise ValueError(f"EDGE_ALREADY_REMOVED: {edge_id}")

    happened_at = now_iso()
    conn.execute(
        "UPDATE record_edges SET removed_at = ?, removed_by = ?, "
        "removed_by_runtime = ?, removal_note = ? WHERE edge_id = ?",
        (happened_at, actor, actor_runtime, note, edge_id),
    )
    details = {
        "edge_id": edge_id,
        "source_record_id": row["source_record_id"],
        "target_record_id": row["target_record_id"],
        "relation_type": row["relation_type"],
        "actor": actor,
        "actor_runtime": actor_runtime,
        "note": note,
    }
    for record_id in sorted({row["source_record_id"], row["target_record_id"]}):
        log_action(conn, record_id, "graph_edge_removed", details)
    log_operation(
        conn,
        "graph",
        "edge-remove",
        details,
        summary=f"removed {edge_id}",
        commit=False,
    )
    updated = conn.execute(
        "SELECT * FROM record_edges WHERE edge_id = ?", (edge_id,)
    ).fetchone()
    return _edge_payload(updated)


def link_source(
    conn: sqlite3.Connection,
    *,
    record_id: str,
    source_id: str,
    actor: str,
    actor_runtime: str,
    note: str | None,
) -> dict:
    if actor_runtime not in ACTOR_RUNTIMES:
        raise ValueError(
            "ACTOR_RUNTIME_INVALID: allowed runtimes are " + ", ".join(ACTOR_RUNTIMES)
        )
    if not actor.strip():
        raise ValueError("ACTOR_REQUIRED: actor must be non-empty")
    record = conn.execute(
        "SELECT id, source_id FROM records WHERE id = ?", (record_id,)
    ).fetchone()
    if record is None:
        raise ValueError(f"RECORD_NOT_FOUND: {record_id}")
    source = conn.execute(
        "SELECT source_id, record_ids_json FROM sources WHERE source_id = ?", (source_id,)
    ).fetchone()
    if source is None:
        raise ValueError(f"SOURCE_NOT_FOUND: {source_id}")
    if record["source_id"] not in (None, "", source_id):
        raise ValueError(
            f"RECORD_SOURCE_CONFLICT: {record_id} already links {record['source_id']}"
        )
    record_ids = json.loads(source["record_ids_json"] or "[]")
    if not isinstance(record_ids, list):
        raise ValueError(f"SOURCE_RECORD_IDS_INVALID: {source_id}")
    normalized = sorted({str(item) for item in record_ids} | {record_id})
    if record["source_id"] == source_id and normalized == sorted(
        {str(item) for item in record_ids}
    ):
        raise ValueError(f"SOURCE_LINK_ALREADY_PRESENT: {record_id} -> {source_id}")

    conn.execute("UPDATE records SET source_id = ? WHERE id = ?", (source_id, record_id))
    conn.execute(
        "UPDATE sources SET record_ids_json = ?, updated_at = ? WHERE source_id = ?",
        (json.dumps(normalized, ensure_ascii=False), now_iso(), source_id),
    )
    details = {
        "record_id": record_id,
        "source_id": source_id,
        "actor": actor,
        "actor_runtime": actor_runtime,
        "note": note,
    }
    log_action(conn, record_id, "graph_source_linked", details)
    log_operation(
        conn,
        "graph",
        "source-link",
        details,
        summary=f"{record_id} -> {source_id}",
        commit=False,
    )
    return details


def _run_mutation(args: Namespace, operation) -> None:
    conn = connect()
    try:
        with conn:
            result = operation(conn)
    except (ValueError, sqlite3.IntegrityError) as exc:
        message = str(exc)
        code = message.split(":", 1)[0] if ":" in message else "GRAPH_MUTATION_FAILED"
        _fail(args, code, message)
        return
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def cmd_edge_add(args: Namespace) -> None:
    _run_mutation(
        args,
        lambda conn: add_edge(
            conn,
            source_record_id=args.source_record_id,
            relation_type=args.relation_type,
            target_record_id=args.target_record_id,
            actor=args.actor,
            actor_runtime=args.actor_runtime,
            note=args.note,
        ),
    )


def cmd_edge_remove(args: Namespace) -> None:
    _run_mutation(
        args,
        lambda conn: remove_edge(
            conn,
            edge_id=args.edge_id,
            actor=args.actor,
            actor_runtime=args.actor_runtime,
            note=args.note,
        ),
    )


def cmd_source_link(args: Namespace) -> None:
    _run_mutation(
        args,
        lambda conn: link_source(
            conn,
            record_id=args.record_id,
            source_id=args.source_id,
            actor=args.actor,
            actor_runtime=args.actor_runtime,
            note=args.note,
        ),
    )
