from __future__ import annotations

import sqlite3

from .config import load_config
from .constants import LIFECYCLE_DEFAULTS
from .db import connect
from .filing_policy import build_filing_suggestions, get_filing_policy
from .paths import KB_ROOT, ensure_dirs, memory_path


def get_lifecycle_config(config: dict) -> dict:
    lifecycle = config.get("lifecycle", {})
    configured_events = lifecycle.get("events", {})
    merged_events = {}
    for event_name, defaults in LIFECYCLE_DEFAULTS["events"].items():
        merged_events[event_name] = {**defaults, **configured_events.get(event_name, {})}
    return {"events": merged_events}


def build_session_paths(config: dict) -> dict:
    paths = {
        "now": str(memory_path(config["memory"].get("now_path", "memory/NOW.md"))),
        "hot": str(memory_path(config["memory"]["hot_path"])),
        "index": str(memory_path(config["memory"]["index_path"])),
        "topics_dir": str(memory_path(config["memory"]["topics_dir"])),
        "cowork_pack": str(
            memory_path(f"{config['exports']['cowork_dir']}/PROJECT_PACK.md")
        ),
        "claude_ai_pack": str(
            memory_path(f"{config['exports']['claude_ai_dir']}/PROJECT_PACK.md")
        ),
    }
    wiki_index = KB_ROOT / "wiki" / "live" / "index.md"
    if wiki_index.exists():
        paths["wiki_index"] = str(wiki_index)
    return paths


def build_lifecycle_counts(conn: sqlite3.Connection) -> dict:
    return {
        "active_records": conn.execute(
            "SELECT COUNT(*) FROM records WHERE status = 'ATIVO'"
        ).fetchone()[0],
        "hot_records": conn.execute(
            "SELECT COUNT(*) FROM records WHERE tier = 'HOT' AND status = 'ATIVO'"
        ).fetchone()[0],
        "open_pendencias": conn.execute(
            "SELECT COUNT(*) FROM records WHERE category = 'PENDENCIA' AND status = 'ATIVO'"
        ).fetchone()[0],
    }


def build_lifecycle_result(
    args,
    *,
    now_iso,
    build_audit_tiers_result,
    apply_stale_hot_demotions,
    refresh_exports,
    get_wiki_check_result,
    get_wiki_lint_result,
    sync_wiki,
    log_operation=None,
    apply_cold_demotions=None,
    prune_snapshots=None,
) -> dict:
    config = load_config()
    ensure_dirs(config)
    event_key = args.event.replace("-", "_")
    lifecycle_cfg = get_lifecycle_config(config)
    event_cfg = dict(lifecycle_cfg["events"][event_key])

    if args.refresh_exports:
        event_cfg["refresh_exports"] = True
    if args.apply_demotions:
        event_cfg["apply_demotions"] = True
    if args.sync_wiki:
        event_cfg["run_wiki_sync"] = True
    if args.force_wiki_sync:
        event_cfg["run_wiki_sync"] = True
    if getattr(args, "apply_cold_demotions", False):
        event_cfg["apply_cold_demotions"] = True
    if getattr(args, "prune_snapshots", False):
        event_cfg["prune_snapshots"] = True

    conn = connect()
    counts = build_lifecycle_counts(conn)
    filing_policy = get_filing_policy(config)
    result = {
        "event": args.event,
        "generated_at": now_iso(),
        "event_config": event_cfg,
        "paths": build_session_paths(config),
        "counts": counts,
        "filing_suggestions": build_filing_suggestions(filing_policy, counts),
        "actions_run": [],
    }

    if event_cfg.get("run_audit"):
        result["audit"] = build_audit_tiers_result(conn, config)
        result["actions_run"].append("audit_tiers")

    if event_cfg.get("apply_demotions"):
        result["demoted_records"] = apply_stale_hot_demotions(
            conn, f"Lifecycle {args.event} automatic demotion"
        )
        result["actions_run"].append("apply_demotions")

    if event_cfg.get("apply_cold_demotions") and apply_cold_demotions is not None:
        result["cold_demoted_records"] = apply_cold_demotions(
            conn, f"Lifecycle {args.event} cold demotion"
        )
        result["actions_run"].append("apply_cold_demotions")

    if event_cfg.get("prune_snapshots") and prune_snapshots is not None:
        wiki_cfg = (config.get("wiki") or {})
        snap_cfg = wiki_cfg.get("snapshot_retention") or {}
        keep = int(snap_cfg.get("keep_last_n", 5))
        result["snapshot_prune"] = prune_snapshots(conn, keep_last_n=keep)
        result["actions_run"].append("prune_snapshots")

    if event_cfg.get("refresh_exports"):
        result["exports"] = refresh_exports()
        result["actions_run"].append("export")

    if event_cfg.get("run_wiki_check"):
        result["wiki_check"] = get_wiki_check_result(config=config)
        result["actions_run"].append("wiki_check")

    if event_cfg.get("run_wiki_lint"):
        result["wiki_lint"] = get_wiki_lint_result()
        result["actions_run"].append("wiki_lint")

    if event_cfg.get("run_wiki_sync"):
        result["wiki_sync"] = sync_wiki(domain=args.domain, force=args.force_wiki_sync)
        result["actions_run"].append("wiki_sync")

    if log_operation is not None:
        log_operation(
            conn,
            "lifecycle",
            args.event,
            {
                "actions_run": result["actions_run"],
                "counts": result["counts"],
            },
            summary=f"Lifecycle {args.event}: {', '.join(result['actions_run']) or 'none'}",
        )

    return result


def render_lifecycle_text(result: dict) -> str:
    lines = [f"Lifecycle event: {result['event']}", ""]
    lines.append(f"Active records: {result['counts']['active_records']}")
    lines.append(f"HOT records: {result['counts']['hot_records']}")
    lines.append(f"Open pendencias: {result['counts']['open_pendencias']}")
    lines.append(f"Actions run: {', '.join(result['actions_run']) or 'none'}")
    if result.get("demoted_records"):
        lines.append(f"Demoted HOT records: {len(result['demoted_records'])}")
    lines.extend(
        [
            "",
            "Primary paths:",
            f"- NOW: {result['paths']['now']}",
            f"- HOT: {result['paths']['hot']}",
            f"- INDEX: {result['paths']['index']}",
        ]
    )
    if "exports" in result:
        lines.append(f"- Cowork pack: {result['exports']['paths']['cowork_pack']}")
        lines.append(f"- Claude pack: {result['exports']['paths']['claude_ai_pack']}")
    if "wiki_check" in result:
        lines.append(f"- Wiki state: {result['wiki_check']['wiki_state']}")
    if "wiki_lint" in result:
        lines.append(f"- Wiki issues: {result['wiki_lint']['issue_count']}")
    if "wiki_sync" in result:
        lines.append(
            f"- Wiki pages written: {result['wiki_sync'].get('written_count', 0)}"
        )
    return "\n".join(lines)


def cmd_lifecycle(
    args,
    *,
    emit,
    now_iso,
    build_audit_tiers_result,
    apply_stale_hot_demotions,
    refresh_exports,
    get_wiki_check_result,
    get_wiki_lint_result,
    sync_wiki,
    log_operation=None,
    apply_cold_demotions=None,
    prune_snapshots=None,
) -> None:
    result = build_lifecycle_result(
        args,
        now_iso=now_iso,
        build_audit_tiers_result=build_audit_tiers_result,
        apply_stale_hot_demotions=apply_stale_hot_demotions,
        refresh_exports=refresh_exports,
        get_wiki_check_result=get_wiki_check_result,
        get_wiki_lint_result=get_wiki_lint_result,
        sync_wiki=sync_wiki,
        log_operation=log_operation,
        apply_cold_demotions=apply_cold_demotions,
        prune_snapshots=prune_snapshots,
    )
    if args.json:
        emit(result, True)
        return
    emit({"__plain__": True, "text": render_lifecycle_text(result)}, False)
