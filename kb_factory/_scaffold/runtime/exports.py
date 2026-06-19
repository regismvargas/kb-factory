from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import load_config
from .db import connect
from .helpers import now_iso
from .paths import ensure_dirs, memory_path

__all__ = [
    "build_export_artifacts",
    "cmd_export",
    "refresh_exports",
    "write_text",
]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _record_line(row, prefix="- ") -> str:
    sid = row["source_id"] if "source_id" in row.keys() else None
    base = f"{prefix}[{row['id']}] {row['title']}"
    return f"{base} (source: {sid})" if sid else base


def _record_line_tick(row) -> str:
    sid = row["source_id"] if "source_id" in row.keys() else None
    base = f"- `{row['id']}` {row['title']}"
    return f"{base} (source: {sid})" if sid else base


def build_export_artifacts(config: dict, conn: sqlite3.Connection) -> dict:
    hot_limit = config.get("hot_session_limit", 12)
    now_path = memory_path(config["memory"].get("now_path", "memory/NOW.md"))
    hot_rows = conn.execute(
        "SELECT * FROM records WHERE tier = 'HOT' AND status = 'ATIVO' ORDER BY updated_at DESC LIMIT ?",
        (hot_limit,),
    ).fetchall()
    pending_rows = conn.execute(
        "SELECT * FROM records WHERE category = 'PENDENCIA' AND status = 'ATIVO' ORDER BY updated_at DESC LIMIT 10"
    ).fetchall()
    state_rows = conn.execute(
        """
        SELECT *
        FROM records
        WHERE status = 'ATIVO' AND category IN ('DECISAO', 'FATO', 'APRENDIZADO')
        ORDER BY
            CASE tier WHEN 'HOT' THEN 0 WHEN 'WARM' THEN 1 ELSE 2 END,
            updated_at DESC
        LIMIT 3
        """
    ).fetchall()
    project = config["project"]
    now_lines = [
        f"# {project['name']} NOW",
        "",
        f"- Project: `{project['slug']}`",
        f"- Generated: `{now_iso()}`",
        f"- Open pendencias: `{len(pending_rows)}`",
        "",
        "## Where We Are",
    ]
    now_lines.extend([_record_line(row) for row in state_rows] or ["- No active state captured yet."])
    now_lines.extend(["", "## Next Steps"])
    now_lines.extend([_record_line(row) for row in pending_rows[:3]] or ["- No open pendencias."])
    now_lines.extend(
        [
            "",
            "## Expand If Needed",
            "- Read HOT.md for the critical working set.",
            "- Read INDEX.md for the broader KB map.",
            "- Load topic files only for the domain you are touching.",
            "- Open historical artifacts only when you need rationale or audit trail.",
        ]
    )
    index_lines = [
        f"# {project['name']} KB Index",
        "",
        f"- Project: `{project['slug']}`",
        f"- Generated: `{now_iso()}`",
        "- Warm start: read `NOW.md`, then `HOT.md`.",
        "",
        "## Hot Memory",
    ]
    index_lines.extend([_record_line(row) for row in hot_rows] or ["- No active HOT items."])
    index_lines.extend(["", "## Open Pendencias"])
    index_lines.extend([_record_line(row) for row in pending_rows] or ["- No open pendencias."])
    hot_lines = ["# HOT", ""]
    hot_lines.extend([_record_line_tick(row) for row in hot_rows] or ["- None"])
    topics_dir = memory_path(config["memory"]["topics_dir"])
    domains = config.get("domains", [])
    topic_payloads = {}
    topic_paths = {}
    for domain in domains:
        rows = conn.execute(
            "SELECT * FROM records WHERE domain = ? AND status = 'ATIVO' ORDER BY updated_at DESC LIMIT 15",
            (domain,),
        ).fetchall()
        topic_lines = [f"# Topic: {domain}", ""]
        topic_lines.extend([_record_line_tick(row) for row in rows] or ["- No active records."])
        topic_payloads[domain] = "\n".join(topic_lines)
        topic_paths[domain] = str(topics_dir / f"{domain}.md")
    pack_text = "\n".join(
        now_lines
        + [
            "",
            "## Warm Start",
            "- Read HOT.md next.",
            "- Use INDEX.md for the full KB map.",
            "- Search before assuming.",
        ]
    )
    return {
        "generated_at": now_iso(),
        "paths": {
            "now": str(now_path),
            "index": str(memory_path(config["memory"]["index_path"])),
            "hot": str(memory_path(config["memory"]["hot_path"])),
            "cowork_pack": str(memory_path(f"{config['exports']['cowork_dir']}/PROJECT_PACK.md")),
            "claude_ai_pack": str(memory_path(f"{config['exports']['claude_ai_dir']}/PROJECT_PACK.md")),
            "topics_dir": str(topics_dir),
        },
        "counts": {
            "hot_records": len(hot_rows),
            "pending_records": len(pending_rows),
            "state_records": len(state_rows),
            "topics_written": len(domains),
        },
        "documents": {
            "now": "\n".join(now_lines),
            "index": "\n".join(index_lines),
            "hot": "\n".join(hot_lines),
            "topic_payloads": topic_payloads,
            "project_pack": pack_text,
        },
        "topic_paths": topic_paths,
    }


def refresh_exports() -> dict:
    config = load_config()
    ensure_dirs(config)
    conn = connect()
    artifacts = build_export_artifacts(config, conn)
    write_text(Path(artifacts["paths"]["now"]), artifacts["documents"]["now"])
    write_text(Path(artifacts["paths"]["index"]), artifacts["documents"]["index"])
    write_text(Path(artifacts["paths"]["hot"]), artifacts["documents"]["hot"])
    for domain, payload in artifacts["documents"]["topic_payloads"].items():
        write_text(Path(artifacts["topic_paths"][domain]), payload)
    write_text(Path(artifacts["paths"]["cowork_pack"]), artifacts["documents"]["project_pack"])
    write_text(Path(artifacts["paths"]["claude_ai_pack"]), artifacts["documents"]["project_pack"])
    return {
        "generated_at": artifacts["generated_at"],
        "paths": artifacts["paths"],
        "counts": artifacts["counts"],
    }


def cmd_export(args, *, emit, log_operation=None) -> None:
    result = refresh_exports()
    if log_operation is not None:
        from .db import connect as _connect

        conn = _connect()
        log_operation(
            conn,
            "export_refresh",
            "export",
            {"counts": result["counts"]},
            summary=f"Exports refreshed: {result['counts']['topics_written']} topics",
        )
    emit({"__plain__": True, "text": "Exports refreshed."}, False)
