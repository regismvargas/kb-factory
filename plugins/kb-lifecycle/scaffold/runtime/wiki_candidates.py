from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3

from .config import load_config
from .db import connect
from .wiki import get_wiki_config

__all__ = [
    "cmd_wiki_candidates",
    "generate_wiki_candidates",
]


def generate_wiki_candidates(conn: sqlite3.Connection, config: dict, wiki_cfg: dict) -> list[dict]:
    allowed_types = set(wiki_cfg.get("page_types", []))
    candidates = []

    # 1. Domain volume candidates: domains with >= 3 active records -> domain_overview
    if "domain_overview" in allowed_types:
        domain_rows = conn.execute(
            "SELECT domain, COUNT(*) AS cnt FROM records WHERE status = 'ATIVO' GROUP BY domain HAVING cnt >= 3 ORDER BY cnt DESC"
        ).fetchall()
        for row in domain_rows:
            domain = row["domain"]
            cnt = row["cnt"]
            record_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM records WHERE domain = ? AND status = 'ATIVO' ORDER BY updated_at DESC",
                    (domain,),
                ).fetchall()
            ]
            source_ids = [
                r["source_id"]
                for r in conn.execute(
                    "SELECT DISTINCT source_id FROM records "
                    "WHERE domain = ? AND status = 'ATIVO' AND source_id IS NOT NULL",
                    (domain,),
                ).fetchall()
            ]
            cid = f"wc-{domain}-domain_overview-{hashlib.sha256(domain.encode()).hexdigest()[:6]}"
            candidates.append({
                "candidate_id": cid,
                "page_type": "domain_overview",
                "target_slug": f"live/{domain}/overview",
                "title": f"{domain.replace('_', ' ').title()} Overview",
                "supporting_record_ids": record_ids,
                "supporting_sources": source_ids,
                "status": "heuristic_candidate",
                "why_now": f"domain '{domain}' has {cnt} active records",
            })

    # 2. Tag cluster candidates: tags appearing on >= 3 active records -> research_synthesis
    if "research_synthesis" in allowed_types:
        all_active = conn.execute(
            "SELECT id, tags_json FROM records WHERE status = 'ATIVO'"
        ).fetchall()
        tag_map: dict[str, list[str]] = {}
        for rec in all_active:
            tags = json.loads(rec["tags_json"])
            for tag in tags:
                tag_map.setdefault(tag, []).append(rec["id"])
        for tag, record_ids in sorted(tag_map.items(), key=lambda x: -len(x[1])):
            if len(record_ids) >= 3:
                placeholders = ",".join("?" for _ in record_ids)
                source_ids = [
                    r["source_id"]
                    for r in conn.execute(
                        f"SELECT DISTINCT source_id FROM records "
                        f"WHERE id IN ({placeholders}) "
                        f"AND status = 'ATIVO' AND source_id IS NOT NULL",
                        record_ids,
                    ).fetchall()
                ]
                cid = f"wc-tag-{tag}-research_synthesis-{hashlib.sha256(tag.encode()).hexdigest()[:6]}"
                candidates.append({
                    "candidate_id": cid,
                    "page_type": "research_synthesis",
                    "target_slug": f"live/research/{tag.lower().replace(' ', '-')}",
                    "title": f"Research Synthesis: {tag}",
                    "supporting_record_ids": record_ids,
                    "supporting_sources": source_ids,
                    "status": "heuristic_candidate",
                    "why_now": f"tag '{tag}' appears on {len(record_ids)} active records",
                })

    # 3. Pending decision clusters: domains with open PENDENCIA -> domain_overview with review_required
    if "domain_overview" in allowed_types:
        pending_domains = conn.execute(
            "SELECT domain, COUNT(*) AS cnt FROM records WHERE category = 'PENDENCIA' AND status = 'ATIVO' GROUP BY domain HAVING cnt >= 1 ORDER BY cnt DESC"
        ).fetchall()
        for row in pending_domains:
            domain = row["domain"]
            cnt = row["cnt"]
            existing_ids = {c["candidate_id"] for c in candidates}
            overview_cid = f"wc-{domain}-domain_overview-{hashlib.sha256(domain.encode()).hexdigest()[:6]}"
            if overview_cid in existing_ids:
                continue
            record_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM records WHERE domain = ? AND category = 'PENDENCIA' AND status = 'ATIVO'",
                    (domain,),
                ).fetchall()
            ]
            cid = f"wc-{domain}-pending_overview-{hashlib.sha256((domain + '-pending').encode()).hexdigest()[:6]}"
            candidates.append({
                "candidate_id": cid,
                "page_type": "domain_overview",
                "target_slug": f"live/{domain}/pending-overview",
                "title": f"{domain.replace('_', ' ').title()} \u2014 Open Decisions",
                "supporting_record_ids": record_ids,
                "supporting_sources": [],
                "status": "review_required",
                "why_now": f"domain '{domain}' has {cnt} open pendencia(s)",
            })

    # 4. Source page candidates: sources with linked records, summary, or analysis
    if "source_page" in allowed_types:
        source_rows = conn.execute(
            "SELECT source_id, filename, domain FROM sources ORDER BY ingested_at DESC"
        ).fetchall()
        for src in source_rows:
            sid = src["source_id"]
            linked_records = conn.execute(
                "SELECT id FROM records WHERE source_id = ? AND status = 'ATIVO'",
                (sid,),
            ).fetchall()
            has_summary = conn.execute(
                "SELECT 1 FROM records WHERE source_id = ? AND status = 'ATIVO' "
                "AND tags_json LIKE '%source-summary%' LIMIT 1",
                (sid,),
            ).fetchone() is not None
            has_analysis = conn.execute(
                "SELECT 1 FROM records WHERE source_id = ? AND status = 'ATIVO' "
                "AND tags_json LIKE '%filed-analysis%' LIMIT 1",
                (sid,),
            ).fetchone() is not None
            if not linked_records and not has_summary and not has_analysis:
                continue
            record_ids = [r["id"] for r in linked_records]
            cid = f"wc-source-{sid}-source_page-{hashlib.sha256(sid.encode()).hexdigest()[:6]}"
            candidates.append({
                "candidate_id": cid,
                "page_type": "source_page",
                "target_slug": f"live/sources/{sid}",
                "title": f"Source: {src['filename']}",
                "supporting_record_ids": record_ids,
                "supporting_sources": [sid],
                "status": "heuristic_candidate",
                "why_now": f"source '{src['filename']}' has linked records or analyses",
            })

    return candidates


def cmd_wiki_candidates(args: argparse.Namespace, *, emit) -> None:
    config = load_config()
    wiki_cfg = get_wiki_config(config)
    conn = connect()
    candidates = generate_wiki_candidates(conn, config, wiki_cfg)
    if args.domain:
        candidates = [c for c in candidates if args.domain in c["target_slug"]]
    if args.json:
        emit(candidates, True)
        return
    if not candidates:
        emit({"__plain__": True, "text": "No wiki candidates found."}, False)
        return
    lines = [f"Wiki candidates: {len(candidates)}", ""]
    for c in candidates:
        lines.append(f"  [{c['candidate_id']}]")
        lines.append(f"    type: {c['page_type']}")
        lines.append(f"    title: {c['title']}")
        lines.append(f"    slug: {c['target_slug']}")
        lines.append(f"    status: {c['status']}")
        lines.append(f"    records: {len(c['supporting_record_ids'])}")
        lines.append(f"    why: {c['why_now']}")
        lines.append("")
    emit({"__plain__": True, "text": "\n".join(lines)}, False)
