#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from runtime import (
    CATEGORIES,
    DB_PATH,
    KB_ROOT,
    LIFECYCLE_DEFAULTS,
    STATUSES,
    TIERS,
    connect,
    ensure_dirs,
    load_config,
    memory_path,
)
from runtime.cli import build_parser as runtime_build_parser
from runtime.doctor import cmd_doctor as runtime_cmd_doctor
from runtime.exports import (
    refresh_exports as runtime_refresh_exports,
    cmd_export as runtime_cmd_export,
)
from runtime.filing_policy import (
    cmd_filing_policy as runtime_cmd_filing_policy,
)
from runtime.graph import (
    cmd_edge_add as runtime_cmd_edge_add,
    cmd_edge_remove as runtime_cmd_edge_remove,
    cmd_source_link as runtime_cmd_source_link,
)
from runtime.helpers import now_iso, row_to_dict
from runtime.oplog import (
    log_operation as runtime_log_operation,
    cmd_oplog as runtime_cmd_oplog,
)
from runtime.sources import (
    cmd_analysis_status as runtime_cmd_analysis_status,
    cmd_ingest as runtime_cmd_ingest,
    cmd_source_content as runtime_cmd_source_content,
    cmd_source_info as runtime_cmd_source_info,
    cmd_sources as runtime_cmd_sources,
    cmd_source_status as runtime_cmd_source_status,
    cmd_source_verify as runtime_cmd_source_verify,
    cmd_source_update as runtime_cmd_source_update,
    cmd_summarize_status as runtime_cmd_summarize_status,
)
from runtime.lifecycle import (
    build_lifecycle_counts as runtime_build_lifecycle_counts,
    build_session_paths as runtime_build_session_paths,
    cmd_lifecycle as runtime_cmd_lifecycle,
    get_lifecycle_config as runtime_get_lifecycle_config,
)
from runtime.maintenance import (
    apply_stale_hot_demotions as runtime_apply_stale_hot_demotions,
    build_audit_tiers_result as runtime_build_audit_tiers_result,
    build_hygiene_audit_result as runtime_build_hygiene_audit_result,
    cmd_audit_tiers as runtime_cmd_audit_tiers,
    cmd_consolidate as runtime_cmd_consolidate,
    cmd_hygiene_audit as runtime_cmd_hygiene_audit,
    get_duplicate_groups as runtime_get_duplicate_groups,
    prune_snapshots as runtime_prune_snapshots,
)
from runtime.records import (
    cmd_bulk_import as runtime_cmd_bulk_import,
    cmd_create as runtime_cmd_create,
    cmd_file as runtime_cmd_file,
    cmd_filing_status as runtime_cmd_filing_status,
    cmd_get as runtime_cmd_get,
    cmd_harden as runtime_cmd_harden,
    cmd_init as runtime_cmd_init,
    cmd_list as runtime_cmd_list,
    cmd_pending as runtime_cmd_pending,
    cmd_raw_query as runtime_cmd_raw_query,
    cmd_resolve as runtime_cmd_resolve,
    cmd_search as runtime_cmd_search,
    cmd_stats as runtime_cmd_stats,
    cmd_supersede as runtime_cmd_supersede,
    cmd_update as runtime_cmd_update,
)
from runtime.wiki import (
    WIKI_DEFAULTS as RUNTIME_WIKI_DEFAULTS,
    cmd_wiki_check as runtime_cmd_wiki_check,
    compute_soft_signals as runtime_compute_soft_signals,
    compute_wiki_hard_signals as runtime_compute_wiki_hard_signals,
    compute_wiki_state as runtime_compute_wiki_state,
    get_wiki_check_result as runtime_get_wiki_check_result,
    get_wiki_config as runtime_get_wiki_config,
)
from runtime.wiki_candidates import (
    generate_wiki_candidates as runtime_generate_wiki_candidates,
    cmd_wiki_candidates as runtime_cmd_wiki_candidates,
)
from runtime.wiki_materialization import (
    WIKI_CITATION_FENCE as RUNTIME_WIKI_CITATION_FENCE,
    WIKI_CITATION_MARKER as RUNTIME_WIKI_CITATION_MARKER,
    build_wiki_page as runtime_build_wiki_page,
    cmd_wiki_lint as runtime_cmd_wiki_lint,
    cmd_wiki_pages as runtime_cmd_wiki_pages,
    cmd_wiki_sync as runtime_cmd_wiki_sync,
    get_wiki_lint_result as runtime_get_wiki_lint_result,
    is_managed_wiki_file as runtime_is_managed_wiki_file,
    parse_citation_block as runtime_parse_citation_block,
    sync_wiki as runtime_sync_wiki,
)


# ---------------------------------------------------------------------------
# Presentation layer (stays in the compatibility boundary)
# ---------------------------------------------------------------------------


def emit(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, list):
        for item in data:
            print(format_record(item))
            print()
    elif isinstance(data, dict) and data.get("__plain__"):
        print(data["text"])
    else:
        print(format_record(data))


def format_record(row: dict) -> str:
    tags = row.get("tags", [])
    if isinstance(tags, str):
        tags = json.loads(tags)
    lines = [
        f"[{row['id']}] {row['category']} {row['tier']} {row['status']}",
        f"title: {row['title']}",
        f"domain: {row['domain']}",
        f"source: {row['source']}",
        f"tags: {', '.join(tags) if tags else '-'}",
    ]
    if row.get("source_id"):
        lines.append(f"source_id: {row['source_id']}")
    if row.get("review_after"):
        lines.append(f"review_after: {row['review_after']}")
    if row.get("valid_until"):
        lines.append(f"valid_until: {row['valid_until']}")
    lines.append("content:")
    lines.append(textwrap.indent(row["content"], "  "))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Thin wrappers — record commands
# ---------------------------------------------------------------------------


def cmd_init(args):
    runtime_cmd_init(args, emit=emit, bulk_import_fn=cmd_bulk_import)


def cmd_create(args):
    runtime_cmd_create(args, emit=emit)


def cmd_list(args):
    runtime_cmd_list(args, emit=emit)


def cmd_get(args):
    runtime_cmd_get(args, emit=emit)


def cmd_search(args):
    runtime_cmd_search(args, emit=emit)


def cmd_update(args):
    runtime_cmd_update(args, emit=emit)


def cmd_supersede(args):
    runtime_cmd_supersede(args, emit=emit)


def cmd_resolve(args):
    runtime_cmd_resolve(args, emit=emit)


def cmd_pending(args):
    runtime_cmd_pending(args, emit=emit)


def cmd_stats(args):
    runtime_cmd_stats(args, emit=emit)


def cmd_raw_query(args):
    runtime_cmd_raw_query(args, emit=emit)


def cmd_harden(args):
    runtime_cmd_harden(args, emit=emit)


def cmd_file(args):
    runtime_cmd_file(args, emit=emit, log_operation=runtime_log_operation)


def cmd_filing_status(args):
    runtime_cmd_filing_status(args, emit=emit)


def cmd_filing_policy(args):
    runtime_cmd_filing_policy(args, emit=emit, load_config=load_config)


def cmd_bulk_import(args):
    runtime_cmd_bulk_import(args, emit=emit)


# ---------------------------------------------------------------------------
# Thin wrappers — export commands
# ---------------------------------------------------------------------------


def refresh_exports():
    return runtime_refresh_exports()


def cmd_export(args):
    runtime_cmd_export(args, emit=emit, log_operation=runtime_log_operation)


# ---------------------------------------------------------------------------
# Thin wrappers — source commands
# ---------------------------------------------------------------------------


def cmd_ingest(args):
    runtime_cmd_ingest(args, emit=emit, log_operation=runtime_log_operation)


def cmd_sources(args):
    runtime_cmd_sources(args, emit=emit)


def cmd_source_info(args):
    runtime_cmd_source_info(args, emit=emit)


def cmd_summarize_status(args):
    runtime_cmd_summarize_status(args, emit=emit)


def cmd_source_content(args):
    runtime_cmd_source_content(args, emit=emit, log_operation=runtime_log_operation)


def cmd_analysis_status(args):
    runtime_cmd_analysis_status(args, emit=emit)


def cmd_source_status(args):
    runtime_cmd_source_status(args, emit=emit)


def cmd_source_verify(args):
    runtime_cmd_source_verify(args, emit=emit, log_operation=runtime_log_operation)


def cmd_source_update(args):
    runtime_cmd_source_update(args, emit=emit, log_operation=runtime_log_operation)


# ---------------------------------------------------------------------------
# Thin wrappers — operation log
# ---------------------------------------------------------------------------


def cmd_oplog(args):
    runtime_cmd_oplog(args, emit=emit)


# ---------------------------------------------------------------------------
# Thin wrappers — maintenance commands
# ---------------------------------------------------------------------------


def build_audit_tiers_result(conn, config):
    return runtime_build_audit_tiers_result(conn, config)


def build_hygiene_audit_result(conn, config):
    return runtime_build_hygiene_audit_result(conn, config)


def get_duplicate_groups(conn):
    return runtime_get_duplicate_groups(conn)


def apply_stale_hot_demotions(conn, reason):
    return runtime_apply_stale_hot_demotions(conn, reason)


def cmd_audit_tiers(args):
    runtime_cmd_audit_tiers(args, emit=emit)


def cmd_hygiene_audit(args):
    runtime_cmd_hygiene_audit(args, emit=emit)


def cmd_consolidate(args):
    runtime_cmd_consolidate(args, emit=emit, refresh_exports=refresh_exports)


def prune_snapshots(conn, *, keep_last_n=5, dry_run=False):
    return runtime_prune_snapshots(conn, keep_last_n=keep_last_n, dry_run=dry_run)


def cmd_prune_snapshots(args):
    wiki_cfg = (load_config().get("wiki") or {})
    snap_cfg = wiki_cfg.get("snapshot_retention") or {}
    keep = args.keep_last_n if args.keep_last_n is not None else int(snap_cfg.get("keep_last_n", 5))
    conn = connect()
    result = runtime_prune_snapshots(conn, keep_last_n=keep, dry_run=bool(args.dry_run))
    emit(result, args.json)


# ---------------------------------------------------------------------------
# Thin wrappers — doctor
# ---------------------------------------------------------------------------


def cmd_doctor(args):
    runtime_cmd_doctor(args, emit=emit)


# ---------------------------------------------------------------------------
# Thin wrappers — wiki
# ---------------------------------------------------------------------------

WIKI_DEFAULTS = RUNTIME_WIKI_DEFAULTS


def get_wiki_config(config):
    return runtime_get_wiki_config(config)


def compute_wiki_hard_signals(conn, eligibility):
    return runtime_compute_wiki_hard_signals(conn, eligibility)


def compute_soft_signals(conn):
    return runtime_compute_soft_signals(conn)


def compute_wiki_state(wiki_cfg, hard_signals, soft_result, candidate_count):
    return runtime_compute_wiki_state(wiki_cfg, hard_signals, soft_result, candidate_count)


def generate_wiki_candidates(conn, config, wiki_cfg):
    return runtime_generate_wiki_candidates(conn, config, wiki_cfg)


def get_wiki_check_result(config=None, conn=None):
    return runtime_get_wiki_check_result(
        config=config,
        conn=conn,
        candidate_provider=generate_wiki_candidates,
    )


def cmd_wiki_check(args):
    runtime_cmd_wiki_check(args, emit=emit, candidate_provider=generate_wiki_candidates)


def cmd_wiki_candidates(args):
    runtime_cmd_wiki_candidates(args, emit=emit)


WIKI_CITATION_MARKER = RUNTIME_WIKI_CITATION_MARKER
WIKI_CITATION_FENCE = RUNTIME_WIKI_CITATION_FENCE


def build_wiki_page(candidate, conn):
    return runtime_build_wiki_page(candidate, conn, now_iso=now_iso)


def is_managed_wiki_file(path):
    return runtime_is_managed_wiki_file(path)


def parse_citation_block(path):
    return runtime_parse_citation_block(path)


def sync_wiki(domain=None, force=False):
    return runtime_sync_wiki(
        domain=domain,
        force=force,
        candidate_provider=generate_wiki_candidates,
        now_iso=now_iso,
    )


def cmd_wiki_sync(args):
    runtime_cmd_wiki_sync(
        args,
        emit=emit,
        candidate_provider=generate_wiki_candidates,
        now_iso=now_iso,
        log_operation=runtime_log_operation,
    )


def get_wiki_lint_result():
    return runtime_get_wiki_lint_result(
        is_managed_file=is_managed_wiki_file,
        parse_citation=parse_citation_block,
    )


def cmd_wiki_lint(args):
    runtime_cmd_wiki_lint(
        args,
        emit=emit,
        is_managed_file=is_managed_wiki_file,
        parse_citation=parse_citation_block,
        log_operation=runtime_log_operation,
    )


def cmd_wiki_pages(args):
    runtime_cmd_wiki_pages(args, emit=emit)


# ---------------------------------------------------------------------------
# Thin wrappers — lifecycle
# ---------------------------------------------------------------------------


def get_lifecycle_config(config):
    return runtime_get_lifecycle_config(config)


def build_session_paths(config):
    return runtime_build_session_paths(config)


def build_lifecycle_counts(conn):
    return runtime_build_lifecycle_counts(conn)


def cmd_lifecycle(args):
    runtime_cmd_lifecycle(
        args,
        emit=emit,
        now_iso=now_iso,
        build_audit_tiers_result=build_audit_tiers_result,
        apply_stale_hot_demotions=apply_stale_hot_demotions,
        refresh_exports=refresh_exports,
        get_wiki_check_result=get_wiki_check_result,
        get_wiki_lint_result=get_wiki_lint_result,
        sync_wiki=sync_wiki,
        log_operation=runtime_log_operation,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser():
    return runtime_build_parser(
        {
            "init": cmd_init,
            "create": cmd_create,
            "file": cmd_file,
            "filing-status": cmd_filing_status,
            "filing-policy": cmd_filing_policy,
            "list": cmd_list,
            "get": cmd_get,
            "search": cmd_search,
            "update": cmd_update,
            "supersede": cmd_supersede,
            "resolve": cmd_resolve,
            "pending": cmd_pending,
            "stats": cmd_stats,
            "export": cmd_export,
            "raw-query": cmd_raw_query,
            "harden": cmd_harden,
            "graph-edge-add": runtime_cmd_edge_add,
            "graph-edge-remove": runtime_cmd_edge_remove,
            "graph-source-link": runtime_cmd_source_link,
            "bulk-import": cmd_bulk_import,
            "ingest": cmd_ingest,
            "sources": cmd_sources,
            "source-info": cmd_source_info,
            "summarize-status": cmd_summarize_status,
            "source-content": cmd_source_content,
            "analysis-status": cmd_analysis_status,
            "source-status": cmd_source_status,
            "source-verify": cmd_source_verify,
            "source-update": cmd_source_update,
            "oplog": cmd_oplog,
            "audit-tiers": cmd_audit_tiers,
            "hygiene-audit": cmd_hygiene_audit,
            "consolidate": cmd_consolidate,
            "doctor": cmd_doctor,
            "wiki-check": cmd_wiki_check,
            "wiki-candidates": cmd_wiki_candidates,
            "wiki-sync": cmd_wiki_sync,
            "wiki-lint": cmd_wiki_lint,
            "wiki-pages": cmd_wiki_pages,
            "prune-snapshots": cmd_prune_snapshots,
            "lifecycle": cmd_lifecycle,
        }
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
