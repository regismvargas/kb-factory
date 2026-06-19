from __future__ import annotations

import argparse


LIFECYCLE_EVENTS = [
    "session-start",
    "source-ingest",
    "record-filed",
    "session-end",
    "scheduled-maintenance",
]


def build_parser(command_handlers: dict[str, object]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KB Factory stdlib-only CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--seed")
    init_p.set_defaults(func=command_handlers["init"])

    create = sub.add_parser("create")
    create.add_argument("--id")
    create.add_argument("--category", required=True)
    create.add_argument("--domain", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--content", required=True)
    create.add_argument("--status", default="ATIVO")
    create.add_argument("--tier", default="WARM")
    create.add_argument("--source", default="manual")
    create.add_argument("--tags")
    create.add_argument("--tier-reason", dest="tier_reason")
    create.add_argument("--review-after", dest="review_after")
    create.add_argument("--valid-until", dest="valid_until")
    create.add_argument("--confidence", type=float, default=0.8)
    create.add_argument("--observed-at", dest="observed_at")
    create.add_argument("--source-id", dest="source_id")
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=command_handlers["create"])

    file_p = sub.add_parser("file")
    file_p.add_argument("--filing-type", dest="filing_type", required=True, choices=["answer", "analysis", "synthesis"])
    file_p.add_argument("--id")
    file_p.add_argument("--category", required=True)
    file_p.add_argument("--domain", required=True)
    file_p.add_argument("--title", required=True)
    file_p.add_argument("--content", required=True)
    file_p.add_argument("--status", default="ATIVO")
    file_p.add_argument("--tier", default="WARM")
    file_p.add_argument("--source", default="filed")
    file_p.add_argument("--tags")
    file_p.add_argument("--tier-reason", dest="tier_reason")
    file_p.add_argument("--review-after", dest="review_after")
    file_p.add_argument("--valid-until", dest="valid_until")
    file_p.add_argument("--confidence", type=float, default=0.8)
    file_p.add_argument("--observed-at", dest="observed_at")
    file_p.add_argument("--source-id", dest="source_id")
    file_p.add_argument("--no-auto-lifecycle", dest="no_auto_lifecycle", action="store_true")
    file_p.add_argument("--json", action="store_true")
    file_p.set_defaults(func=command_handlers["file"])

    filing_status_p = sub.add_parser("filing-status")
    filing_status_p.add_argument("--domain")
    filing_status_p.add_argument("--json", action="store_true")
    filing_status_p.set_defaults(func=command_handlers["filing-status"])

    filing_policy_p = sub.add_parser("filing-policy")
    filing_policy_p.add_argument("--json", action="store_true")
    filing_policy_p.set_defaults(func=command_handlers["filing-policy"])

    list_p = sub.add_parser("list")
    for name in ("category", "domain", "status", "tier"):
        list_p.add_argument(f"--{name}")
    list_p.add_argument("--limit", type=int, default=20)
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=command_handlers["list"])

    get_p = sub.add_parser("get")
    get_p.add_argument("record_id")
    get_p.add_argument("--json", action="store_true")
    get_p.set_defaults(func=command_handlers["get"])

    search = sub.add_parser("search")
    search.add_argument("query")
    for name in ("category", "domain", "status", "tier"):
        search.add_argument(f"--{name}")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_handlers["search"])

    update = sub.add_parser("update")
    update.add_argument("record_id")
    update.add_argument("--tier")
    update.add_argument("--tier-reason", dest="tier_reason")
    update.add_argument("--review-after", dest="review_after")
    update.add_argument("--valid-until", dest="valid_until")
    update.add_argument("--confidence", type=float)
    update.add_argument("--source")
    update.add_argument("--tags")
    update.add_argument("--json", action="store_true")
    update.set_defaults(func=command_handlers["update"])

    supersede = sub.add_parser("supersede")
    supersede.add_argument("record_id")
    supersede.add_argument("--new-id")
    supersede.add_argument("--title")
    supersede.add_argument("--content")
    supersede.add_argument("--tier")
    supersede.add_argument("--tier-reason", dest="tier_reason")
    supersede.add_argument("--review-after", dest="review_after")
    supersede.add_argument("--valid-until", dest="valid_until")
    supersede.add_argument("--source")
    supersede.add_argument("--tags")
    supersede.add_argument("--confidence", type=float)
    supersede.add_argument("--source-id", dest="source_id")
    supersede.add_argument("--json", action="store_true")
    supersede.set_defaults(func=command_handlers["supersede"])

    resolve = sub.add_parser("resolve")
    resolve.add_argument("record_id")
    resolve.add_argument("--notes", required=True)
    resolve.add_argument("--json", action="store_true")
    resolve.set_defaults(func=command_handlers["resolve"])

    pending = sub.add_parser("pending")
    pending.add_argument("--domain")
    pending.add_argument("--limit", type=int, default=20)
    pending.add_argument("--json", action="store_true")
    pending.set_defaults(func=command_handlers["pending"])

    stats = sub.add_parser("stats")
    stats.add_argument("--json", action="store_true")
    stats.set_defaults(func=command_handlers["stats"])

    export = sub.add_parser("export")
    export.set_defaults(func=command_handlers["export"])

    raw = sub.add_parser("raw-query")
    raw.add_argument("sql")
    raw.add_argument(
        "--allow-write",
        dest="allow_write",
        action="store_true",
        help="Permit write statements (default: read-only via PRAGMA query_only)",
    )
    raw.set_defaults(func=command_handlers["raw-query"])

    bulk = sub.add_parser("bulk-import")
    bulk.add_argument("path")
    bulk.set_defaults(func=command_handlers["bulk-import"])

    ingest = sub.add_parser("ingest")
    ingest.add_argument("path")
    ingest.add_argument("--source-id", dest="source_id")
    ingest.add_argument("--domain")
    ingest.add_argument("--tags")
    ingest.add_argument("--notes")
    ingest.add_argument("--no-auto-lifecycle", dest="no_auto_lifecycle", action="store_true")
    ingest.add_argument("--json", action="store_true")
    ingest.set_defaults(func=command_handlers["ingest"])

    sources_p = sub.add_parser("sources")
    sources_p.add_argument("--domain")
    sources_p.add_argument("--limit", type=int, default=20)
    sources_p.add_argument("--json", action="store_true")
    sources_p.set_defaults(func=command_handlers["sources"])

    source_info = sub.add_parser("source-info")
    source_info.add_argument("source_id")
    source_info.add_argument("--json", action="store_true")
    source_info.set_defaults(func=command_handlers["source-info"])

    summarize_status = sub.add_parser("summarize-status")
    summarize_status.add_argument("--domain")
    summarize_status.add_argument("--json", action="store_true")
    summarize_status.set_defaults(func=command_handlers["summarize-status"])

    source_content = sub.add_parser("source-content")
    source_content.add_argument("source_id")
    source_content.add_argument("--json", action="store_true")
    source_content.set_defaults(func=command_handlers["source-content"])

    analysis_status_p = sub.add_parser("analysis-status")
    analysis_status_p.add_argument("--domain")
    analysis_status_p.add_argument("--json", action="store_true")
    analysis_status_p.set_defaults(func=command_handlers["analysis-status"])

    source_status = sub.add_parser("source-status")
    source_status.add_argument("--domain")
    source_status.add_argument("--uncovered", action="store_true")
    source_status.add_argument("--missing-file", dest="missing_file", action="store_true")
    source_status.add_argument("--hash-drift", dest="hash_drift", action="store_true")
    source_status.add_argument("--json", action="store_true")
    source_status.set_defaults(func=command_handlers["source-status"])

    source_verify = sub.add_parser("source-verify")
    source_verify.add_argument("--json", action="store_true")
    source_verify.set_defaults(func=command_handlers["source-verify"])

    source_update = sub.add_parser("source-update")
    source_update.add_argument("source_id")
    source_update.add_argument("--domain")
    source_update.add_argument("--tags")
    source_update.add_argument("--notes")
    source_update.add_argument("--json", action="store_true")
    source_update.set_defaults(func=command_handlers["source-update"])

    oplog_p = sub.add_parser("oplog")
    oplog_p.add_argument("--category")
    oplog_p.add_argument("--limit", type=int, default=20)
    oplog_p.add_argument("--json", action="store_true")
    oplog_p.set_defaults(func=command_handlers["oplog"])

    audit = sub.add_parser("audit-tiers")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=command_handlers["audit-tiers"])

    hygiene = sub.add_parser("hygiene-audit")
    hygiene.add_argument("--json", action="store_true")
    hygiene.set_defaults(func=command_handlers["hygiene-audit"])

    consolidate = sub.add_parser("consolidate")
    consolidate.add_argument("--apply-demotions", action="store_true")
    consolidate.set_defaults(func=command_handlers["consolidate"])

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_handlers["doctor"])

    harden_p = sub.add_parser("harden")
    harden_p.add_argument(
        "--off", action="store_true", help="Remove the optional append-only triggers"
    )
    harden_p.add_argument("--json", action="store_true")
    harden_p.set_defaults(func=command_handlers["harden"])

    wiki_check = sub.add_parser("wiki-check")
    wiki_check.add_argument("--json", action="store_true")
    wiki_check.set_defaults(func=command_handlers["wiki-check"])

    wiki_cand = sub.add_parser("wiki-candidates")
    wiki_cand.add_argument("--domain")
    wiki_cand.add_argument("--json", action="store_true")
    wiki_cand.set_defaults(func=command_handlers["wiki-candidates"])

    wiki_sync = sub.add_parser("wiki-sync")
    wiki_sync.add_argument("--domain")
    wiki_sync.add_argument(
        "--force", action="store_true", help="Sync even if wiki is disabled"
    )
    wiki_sync.add_argument("--json", action="store_true")
    wiki_sync.set_defaults(func=command_handlers["wiki-sync"])

    wiki_lint = sub.add_parser("wiki-lint")
    wiki_lint.add_argument("--json", action="store_true")
    wiki_lint.set_defaults(func=command_handlers["wiki-lint"])

    wiki_pages = sub.add_parser("wiki-pages")
    wiki_pages.add_argument("--state")
    wiki_pages.add_argument("--page-class", dest="page_class")
    wiki_pages.add_argument("--domain")
    wiki_pages.add_argument("--page-type", dest="page_type")
    wiki_pages.add_argument("--min-confidence", dest="min_confidence", type=float)
    wiki_pages.add_argument("--limit", type=int, default=50)
    wiki_pages.add_argument("--json", action="store_true")
    wiki_pages.set_defaults(func=command_handlers["wiki-pages"])

    prune_snap = sub.add_parser("prune-snapshots")
    prune_snap.add_argument("--keep-last-n", dest="keep_last_n", type=int)
    prune_snap.add_argument("--dry-run", dest="dry_run", action="store_true")
    prune_snap.add_argument("--json", action="store_true")
    prune_snap.set_defaults(func=command_handlers["prune-snapshots"])

    lifecycle = sub.add_parser("lifecycle")
    lifecycle.add_argument("event", choices=LIFECYCLE_EVENTS)
    lifecycle.add_argument("--domain")
    lifecycle.add_argument("--refresh-exports", action="store_true")
    lifecycle.add_argument("--apply-demotions", action="store_true")
    lifecycle.add_argument("--apply-cold-demotions", dest="apply_cold_demotions", action="store_true")
    lifecycle.add_argument("--prune-snapshots", dest="prune_snapshots", action="store_true")
    lifecycle.add_argument("--sync-wiki", action="store_true")
    lifecycle.add_argument("--force-wiki-sync", action="store_true")
    lifecycle.add_argument("--json", action="store_true")
    lifecycle.set_defaults(func=command_handlers["lifecycle"])

    return parser
