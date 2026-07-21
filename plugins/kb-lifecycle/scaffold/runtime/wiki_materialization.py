from __future__ import annotations

import hashlib
import json
import posixpath
import re
from pathlib import Path

from .config import load_config
from .db import connect
from .helpers import now_iso
from .paths import KB_ROOT, ensure_dirs
from .wiki import get_wiki_config


WIKI_CITATION_MARKER = "<!-- kb-wiki-managed -->"
WIKI_CITATION_FENCE = "<!-- kb-citation-block -->"

EXCERPT_MAX = 200

CATEGORY_SECTIONS = [
    ("DECISAO", "Key Decisions"),
    ("FATO", "Facts & Evidence"),
    ("APRENDIZADO", "Learnings"),
    ("PENDENCIA", "Open Questions"),
    ("PREMISSA", "Premises"),
]

TIER_ORDER = {"HOT": 0, "WARM": 1, "COLD": 2}


def _excerpt(text: str, max_len: int = EXCERPT_MAX) -> str:
    """Truncate text to max_len at a word boundary. Deterministic, no LLM."""
    if not text:
        return ""
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    cut = clean[:max_len].rfind(" ")
    if cut < max_len // 2:
        cut = max_len
    return clean[:cut].rstrip() + " ..."


def _build_metadata_header(candidate: dict) -> list[str]:
    return [
        f"> **Page type:** {candidate['page_type']}  ",
        f"> **Status:** {candidate['status']}  ",
        f"> **Why now:** {candidate['why_now']}",
        "",
    ]


def _build_provenance_block(candidate: dict, page_class: str, generated_at: str) -> list[str]:
    return [
        "",
        "---",
        "",
        WIKI_CITATION_FENCE,
        "",
        "## Provenance",
        "",
        f"- **Generated:** {generated_at}",
        f"- **Class:** {page_class}",
        f"- **Candidate ID:** {candidate['candidate_id']}",
        f"- **Supporting Records:** {', '.join(candidate['supporting_record_ids']) or 'none'}",
        f"- **Supporting Sources:** {', '.join(candidate['supporting_sources']) or 'none'}",
        "",
        "<!-- /kb-citation-block -->",
    ]


def _build_generic_body(candidate: dict, conn) -> list[str]:
    """Original flat bullet-list body used for non-domain_overview page types."""
    rec_summaries: list[str] = []
    for record_id in candidate["supporting_record_ids"]:
        row = conn.execute(
            "SELECT id, category, title, domain FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row:
            rec_summaries.append(
                f"- **[{row['id']}]** ({row['category']}) {row['title']}"
            )
        else:
            rec_summaries.append(f"- **[{record_id}]** *(record not found)*")
    lines = ["## Supporting Records", ""]
    lines.extend(rec_summaries or ["- *(none)*"])
    return lines


def _sort_records(recs: list[dict]) -> list[dict]:
    """Sort records: tier ASC (HOT first), updated_at DESC, id ASC."""
    def key(r):
        tier_val = TIER_ORDER.get(r.get("tier", "COLD"), 9)
        ts = r.get("updated_at") or ""
        inverted_ts = "".join(chr(0xFFFF - ord(c)) for c in ts) if ts else ""
        return (tier_val, inverted_ts, r["id"])
    return sorted(recs, key=key)


def _build_domain_overview_body(candidate: dict, conn) -> list[str]:
    """Category-grouped body with content excerpts and tier badges."""
    record_ids = candidate["supporting_record_ids"]
    if not record_ids:
        return _build_generic_body(candidate, conn)

    placeholders = ",".join("?" for _ in record_ids)
    rows = conn.execute(
        f"SELECT id, category, title, content, tier, updated_at "
        f"FROM records WHERE id IN ({placeholders})",
        record_ids,
    ).fetchall()

    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        by_cat.setdefault(row["category"], []).append(dict(row))

    lines: list[str] = []

    for cat_code, heading in CATEGORY_SECTIONS:
        recs = by_cat.get(cat_code)
        if not recs:
            continue
        sorted_recs = _sort_records(recs)
        lines.append(f"## {heading}")
        lines.append("")
        for rec in sorted_recs:
            tier_badge = rec.get("tier", "WARM")
            content_excerpt = _excerpt(rec.get("content", ""))
            lines.append(f"### {rec['id']} \u2014 {rec['title']}")
            lines.append(f"> [{tier_badge}] {content_excerpt}")
            lines.append("")

    # Source summaries and filed analyses (conditional section)
    domain = candidate["target_slug"].split("/")[1] if "/" in candidate["target_slug"] else None
    if domain:
        summaries = conn.execute(
            "SELECT id, title, content FROM records "
            "WHERE domain = ? AND status = 'ATIVO' AND tags_json LIKE '%source-summary%' "
            "ORDER BY updated_at DESC",
            (domain,),
        ).fetchall()
        analyses = conn.execute(
            "SELECT id, title, content FROM records "
            "WHERE domain = ? AND status = 'ATIVO' AND tags_json LIKE '%filed-analysis%' "
            "ORDER BY updated_at DESC",
            (domain,),
        ).fetchall()
        answers = conn.execute(
            "SELECT id, title, content FROM records "
            "WHERE domain = ? AND status = 'ATIVO' AND tags_json LIKE '%filed-answer%' "
            "ORDER BY updated_at DESC",
            (domain,),
        ).fetchall()
        syntheses = conn.execute(
            "SELECT id, title, content FROM records "
            "WHERE domain = ? AND status = 'ATIVO' AND tags_json LIKE '%filed-synthesis%' "
            "ORDER BY updated_at DESC",
            (domain,),
        ).fetchall()
        if summaries or analyses or answers or syntheses:
            lines.append("## Sources & Analyses")
            lines.append("")
            if summaries:
                lines.append("### Source Summaries")
                lines.append("")
                for s in summaries:
                    lines.append(f"- **[{s['id']}]** {s['title']} \u2014 {_excerpt(s['content'] or '', 150)}")
                lines.append("")
            if analyses:
                lines.append("### Filed Analyses")
                lines.append("")
                for a in analyses:
                    lines.append(f"- **[{a['id']}]** {a['title']} \u2014 {_excerpt(a['content'] or '', 150)}")
                lines.append("")
            if answers:
                lines.append("### Filed Answers")
                lines.append("")
                for ans in answers:
                    lines.append(f"- **[{ans['id']}]** {ans['title']} \u2014 {_excerpt(ans['content'] or '', 150)}")
                lines.append("")
            if syntheses:
                lines.append("### Filed Syntheses")
                lines.append("")
                for syn in syntheses:
                    lines.append(f"- **[{syn['id']}]** {syn['title']} \u2014 {_excerpt(syn['content'] or '', 150)}")
                lines.append("")

    return lines


def _build_research_synthesis_body(candidate: dict, conn) -> list[str]:
    """Category-grouped body for tag-based research synthesis pages."""
    record_ids = candidate["supporting_record_ids"]
    if not record_ids:
        return _build_generic_body(candidate, conn)

    placeholders = ",".join("?" for _ in record_ids)
    rows = conn.execute(
        f"SELECT id, category, title, content, tier, updated_at "
        f"FROM records WHERE id IN ({placeholders})",
        record_ids,
    ).fetchall()

    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        by_cat.setdefault(row["category"], []).append(dict(row))

    lines: list[str] = []

    for cat_code, heading in CATEGORY_SECTIONS:
        recs = by_cat.get(cat_code)
        if not recs:
            continue
        sorted_recs = _sort_records(recs)
        lines.append(f"## {heading}")
        lines.append("")
        for rec in sorted_recs:
            tier_badge = rec.get("tier", "WARM")
            content_excerpt = _excerpt(rec.get("content", ""))
            lines.append(f"### {rec['id']} \u2014 {rec['title']}")
            lines.append(f"> [{tier_badge}] {content_excerpt}")
            lines.append("")

    return lines


def _build_source_page_body(candidate: dict, conn) -> list[str]:
    """Per-source detail page showing summary, analysis, and linked records."""
    source_ids = candidate.get("supporting_sources", [])
    sid = source_ids[0] if source_ids else None
    if not sid:
        return _build_generic_body(candidate, conn)

    src = conn.execute(
        "SELECT source_id, filename, domain, ingested_at, notes FROM sources WHERE source_id = ?",
        (sid,),
    ).fetchone()
    if not src:
        return ["*(source not found)*"]

    lines: list[str] = []

    # Source metadata
    lines.append("## Source Info")
    lines.append("")
    lines.append(f"- **Source ID:** {src['source_id']}")
    lines.append(f"- **Filename:** {src['filename']}")
    lines.append(f"- **Domain:** {src['domain']}")
    lines.append(f"- **Ingested:** {src['ingested_at']}")
    if src["notes"]:
        lines.append(f"- **Notes:** {src['notes']}")
    lines.append("")

    # Summary
    summary = conn.execute(
        "SELECT id, title, content FROM records "
        "WHERE source_id = ? AND status = 'ATIVO' AND tags_json LIKE '%source-summary%' "
        "ORDER BY updated_at DESC LIMIT 1",
        (sid,),
    ).fetchone()
    if summary:
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**[{summary['id']}]** {summary['title']}")
        lines.append("")
        lines.append(summary["content"] or "")
        lines.append("")

    # Analysis
    analysis = conn.execute(
        "SELECT id, title, content FROM records "
        "WHERE source_id = ? AND status = 'ATIVO' AND tags_json LIKE '%filed-analysis%' "
        "ORDER BY updated_at DESC LIMIT 1",
        (sid,),
    ).fetchone()
    if analysis:
        lines.append("## Analysis")
        lines.append("")
        lines.append(f"**[{analysis['id']}]** {analysis['title']}")
        lines.append("")
        lines.append(analysis["content"] or "")
        lines.append("")

    # Linked records (excluding summary and analysis themselves)
    exclude_ids = set()
    if summary:
        exclude_ids.add(summary["id"])
    if analysis:
        exclude_ids.add(analysis["id"])
    linked = conn.execute(
        "SELECT id, category, title, content, tier FROM records "
        "WHERE source_id = ? AND status = 'ATIVO' ORDER BY updated_at DESC",
        (sid,),
    ).fetchall()
    other_records = [r for r in linked if r["id"] not in exclude_ids]
    if other_records:
        lines.append("## Linked Records")
        lines.append("")
        for rec in other_records:
            tier_badge = rec["tier"] or "WARM"
            lines.append(f"- **[{rec['id']}]** ({rec['category']}) [{tier_badge}] {rec['title']} \u2014 {_excerpt(rec['content'] or '', 150)}")
        lines.append("")

    return lines


def _record_anchor(record_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", record_id.lower()).strip("-")
    return f"kb-{normalized}"


def _markdown_slug(target_slug: str) -> str:
    return target_slug if target_slug.endswith(".md") else f"{target_slug}.md"


def _relative_page_link(current_slug: str, target_slug: str, anchor: str | None = None) -> str:
    current_path = _markdown_slug(current_slug)
    target_path = _markdown_slug(target_slug)
    if current_path == target_path:
        relative = ""
    else:
        relative = posixpath.relpath(target_path, posixpath.dirname(current_path) or ".")
    suffix = f"#{anchor}" if anchor else ""
    return f"{relative}{suffix}" or "#"


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _record_index_candidate(conn) -> dict:
    record_ids = [
        row["id"]
        for row in conn.execute("SELECT id FROM records ORDER BY id").fetchall()
    ]
    return {
        "candidate_id": "wiki-live-record-index",
        "target_slug": "live/index",
        "page_type": "record_index",
        "title": "Knowledge Record Index",
        "status": "heuristic_candidate",
        "why_now": "Managed directory for every canonical record.",
        "supporting_record_ids": record_ids,
        "supporting_sources": [],
    }


def _build_navigation_context(conn, candidates: list[dict]) -> dict:
    rows = conn.execute(
        "SELECT id, category, title, content, domain, status, tags_json, source_id "
        "FROM records ORDER BY id"
    ).fetchall()
    records = {row["id"]: dict(row) for row in rows}
    pages_by_record: dict[str, list[dict]] = {record_id: [] for record_id in records}
    for candidate in sorted(candidates, key=lambda item: item["target_slug"]):
        for record_id in candidate.get("supporting_record_ids", []):
            if record_id in records:
                pages_by_record.setdefault(record_id, []).append(candidate)

    primary: dict[str, str] = {}
    for record_id, record in records.items():
        pages = pages_by_record.get(record_id, [])
        domain_slug = f"live/{record.get('domain')}/overview" if record.get("domain") else None
        if domain_slug and any(page["target_slug"] == domain_slug for page in pages):
            primary[record_id] = domain_slug
            continue
        non_index = sorted(
            (page["target_slug"] for page in pages if page["target_slug"] != "live/index")
        )
        primary[record_id] = non_index[0] if non_index else "live/index"

    source_links: dict[str, set[str]] = {record_id: set() for record_id in records}
    for record_id, record in records.items():
        if record.get("source_id"):
            source_links[record_id].add(str(record["source_id"]))
    if _table_exists(conn, "sources"):
        source_rows = conn.execute(
            "SELECT source_id, record_ids_json FROM sources ORDER BY source_id"
        ).fetchall()
        for source in source_rows:
            try:
                linked = json.loads(source["record_ids_json"] or "[]")
            except (TypeError, ValueError):
                linked = []
            for record_id in linked:
                if record_id in records:
                    source_links[record_id].add(str(source["source_id"]))

    typed_edges: list[dict] = []
    if _table_exists(conn, "record_edges"):
        typed_edges = [
            dict(row)
            for row in conn.execute(
                "SELECT edge_id, source_record_id, target_record_id, relation_type "
                "FROM record_edges WHERE removed_at IS NULL ORDER BY edge_id"
            ).fetchall()
        ]
    return {
        "records": records,
        "pages_by_record": pages_by_record,
        "primary": primary,
        "source_links": source_links,
        "typed_edges": typed_edges,
    }


def _record_link(record_id: str, current_slug: str, navigation: dict) -> str:
    target = navigation["primary"].get(record_id, "live/index")
    return _relative_page_link(current_slug, target, _record_anchor(record_id))


def _link_record_references(content: str, current_slug: str, navigation: dict) -> str:
    records = navigation.get("records", {})

    def replace(match: re.Match) -> str:
        record_id = match.group(1)
        if record_id not in records:
            return match.group(0)
        return f"[{record_id}]({_record_link(record_id, current_slug, navigation)})"

    return re.sub(r"\[([A-Za-z0-9][A-Za-z0-9._-]*)\](?!\()", replace, content)


def _build_index_body(candidate: dict, conn, navigation: dict) -> list[str]:
    records = navigation["records"]
    domain_pages = sorted(
        {
            page["target_slug"]
            for pages in navigation["pages_by_record"].values()
            for page in pages
            if page.get("page_type") == "domain_overview"
        }
    )
    lines = ["## Domain overviews", ""]
    if domain_pages:
        for slug in domain_pages:
            domain = slug.split("/")[1] if len(slug.split("/")) > 1 else slug
            lines.append(f"- [{domain}]({_relative_page_link(candidate['target_slug'], slug)})")
    else:
        lines.append("- *(none)*")
    lines.extend(["", "## Record directory", ""])
    by_domain: dict[str, list[dict]] = {}
    for record in records.values():
        by_domain.setdefault(record.get("domain") or "unassigned", []).append(record)
    if not by_domain:
        lines.append("- *(none)*")
        return lines
    for domain in sorted(by_domain):
        lines.extend([f"### {domain}", ""])
        for record in sorted(by_domain[domain], key=lambda item: item["id"]):
            record_id = record["id"]
            destination = _record_link(record_id, candidate["target_slug"], navigation)
            lines.append(f"- [{record_id}]({destination}) — {record['title']} "
                         f"({record['category']}, {record['status']})")
        lines.append("")
    return lines


def _build_cited_by(candidate: dict, navigation: dict) -> list[str]:
    current_slug = candidate["target_slug"]
    cited: dict[str, set[str]] = {}
    page_titles: dict[str, str] = {}
    for record_id in candidate.get("supporting_record_ids", []):
        for page in navigation["pages_by_record"].get(record_id, []):
            slug = page["target_slug"]
            if slug == current_slug:
                continue
            cited.setdefault(slug, set()).add(record_id)
            page_titles[slug] = page["title"]
    lines = ["## Cited by", ""]
    if not cited:
        lines.append("- *(none)*")
        return lines
    for slug in sorted(cited):
        record_ids = sorted(cited[slug])
        anchor = _record_anchor(record_ids[0]) if record_ids else None
        link = _relative_page_link(current_slug, slug, anchor)
        lines.append(
            f"- [{page_titles[slug]}]({link}) [page:live/managed] — "
            + ", ".join(record_ids)
        )
    return lines


def _build_related_knowledge(candidate: dict, navigation: dict) -> list[str]:
    records = navigation["records"]
    subject_ids = {
        record_id
        for record_id in candidate.get("supporting_record_ids", [])
        if record_id in records
    }
    origins: dict[str, set[str]] = {}
    for subject_id in sorted(subject_ids):
        subject = records[subject_id]
        subject_tags = set(json.loads(subject.get("tags_json") or "[]"))
        subject_sources = navigation["source_links"].get(subject_id, set())
        for page in navigation["pages_by_record"].get(subject_id, []):
            for neighbor_id in page.get("supporting_record_ids", []):
                if neighbor_id not in subject_ids and neighbor_id in records:
                    origins.setdefault(neighbor_id, set()).add(f"page:{page['target_slug']}")
        for neighbor_id, neighbor in records.items():
            if neighbor_id in subject_ids:
                continue
            if subject.get("domain") and neighbor.get("domain") == subject.get("domain"):
                origins.setdefault(neighbor_id, set()).add(f"domain:{subject['domain']}")
            neighbor_tags = set(json.loads(neighbor.get("tags_json") or "[]"))
            for tag in sorted(subject_tags & neighbor_tags):
                origins.setdefault(neighbor_id, set()).add(f"tag:{tag}")
            for source_id in sorted(subject_sources & navigation["source_links"].get(neighbor_id, set())):
                origins.setdefault(neighbor_id, set()).add(f"source:{source_id}")
        for edge in navigation["typed_edges"]:
            if edge["source_record_id"] == subject_id:
                other_id = edge["target_record_id"]
                direction = "outgoing"
            elif edge["target_record_id"] == subject_id:
                other_id = edge["source_record_id"]
                direction = "incoming"
            else:
                continue
            if other_id not in subject_ids and other_id in records:
                origins.setdefault(other_id, set()).add(
                    f"typed-edge:{edge['relation_type']}/{direction}/{edge['edge_id']}"
                )
    lines = ["## Related knowledge", ""]
    if not origins:
        lines.append("- *(none)*")
        return lines
    for record_id in sorted(origins):
        record = records[record_id]
        link = _record_link(record_id, candidate["target_slug"], navigation)
        labels = "; ".join(sorted(origins[record_id]))
        lines.append(f"- [{record_id}]({link}) — {record['title']} [{labels}]")
    return lines


def build_wiki_page(
    candidate: dict,
    conn,
    *,
    now_iso,
    navigation: dict | None = None,
    generated_at: str | None = None,
) -> str:
    page_class = "snapshot" if candidate["target_slug"].startswith("snapshots/") else "live"
    generated_at = generated_at or now_iso()
    header = _build_metadata_header(candidate)
    if candidate["page_type"] == "record_index" and navigation is not None:
        body = _build_index_body(candidate, conn, navigation)
    elif candidate["page_type"] == "domain_overview":
        body = _build_domain_overview_body(candidate, conn)
    elif candidate["page_type"] == "research_synthesis":
        body = _build_research_synthesis_body(candidate, conn)
    elif candidate["page_type"] == "source_page":
        body = _build_source_page_body(candidate, conn)
    else:
        body = _build_generic_body(candidate, conn)
    provenance = _build_provenance_block(candidate, page_class, generated_at)
    lines = [WIKI_CITATION_MARKER, f"# {candidate['title']}", ""]
    lines.extend(header)
    if navigation is not None:
        anchors = [
            f'<a id="{_record_anchor(record_id)}"></a>'
            for record_id in candidate.get("supporting_record_ids", [])
            if record_id in navigation["records"]
        ]
        lines.extend(["<!-- kb-record-anchors -->", *anchors, "<!-- /kb-record-anchors -->", ""])
    lines.extend(body)
    if navigation is not None:
        lines.extend(["", *_build_cited_by(candidate, navigation)])
        lines.extend(["", *_build_related_knowledge(candidate, navigation)])
    lines.extend(provenance)
    content = "\n".join(lines) + "\n"
    if navigation is not None:
        content = _link_record_references(content, candidate["target_slug"], navigation)
    return content


def is_managed_wiki_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        return first.strip() == WIKI_CITATION_MARKER
    except Exception:
        return False


def parse_citation_block(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if WIKI_CITATION_FENCE not in text:
        return None
    info: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        if line.strip() == WIKI_CITATION_FENCE:
            in_block = True
            continue
        if line.strip() == "<!-- /kb-citation-block -->":
            break
        if in_block and line.startswith("- **"):
            key_end = line.index(":**")
            key = line[4:key_end].strip().lower().replace(" ", "_")
            value = line[key_end + 3 :].strip()
            info[key] = value
    return info if info else None


def compute_page_id(target_slug: str) -> str:
    digest = hashlib.sha256(target_slug.encode("utf-8")).hexdigest()[:12]
    return f"wp-{digest}"


def compute_content_hash(content: str) -> str:
    # Hash a canonicalized version that strips the volatile generation
    # timestamp line, so pages with unchanged substantive content
    # produce a stable hash across re-syncs.
    stable = "\n".join(
        line
        for line in content.splitlines()
        if not line.lstrip().startswith("- **Generated:**")
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _relative_stored_path(target_md: Path) -> str:
    try:
        return target_md.relative_to(KB_ROOT).as_posix()
    except ValueError:
        return str(target_md)


def evaluate_hygiene_gates(
    conn, candidate: dict, wiki_cfg: dict
) -> dict | None:
    """Return a held-back descriptor, or None if the candidate clears all gates.

    Gates applied (all advisory-to-sync only; no DB mutation):
      1. confidence publish gate: any page whose computed confidence is below
         `semantic.min_confidence_autopublish` is held back.
      2. two-source minimum for research_synthesis: a research_synthesis page
         whose supporting_sources has fewer than
         `semantic.min_sources_research_synthesis` distinct entries is held back.

    Snapshot candidates (target_slug starts with "snapshots/") are never gated
    here — snapshot capture is handled separately by capture_snapshot().
    """
    if candidate.get("target_slug", "").startswith("snapshots/"):
        return None
    semantic = wiki_cfg.get("semantic", {}) or {}
    supporting_records = list(candidate.get("supporting_record_ids", []))
    supporting_sources = list(candidate.get("supporting_sources", []))
    confidence = compute_page_confidence(conn, supporting_records)
    distinct_sources = len({sid for sid in supporting_sources if sid})

    min_conf = semantic.get("min_confidence_autopublish")
    if (
        min_conf is not None
        and confidence is not None
        and confidence < float(min_conf)
    ):
        return {
            "candidate_id": candidate.get("candidate_id"),
            "target_slug": candidate.get("target_slug"),
            "page_type": candidate.get("page_type"),
            "reason": "confidence_below_autopublish",
            "computed_confidence": confidence,
            "threshold": float(min_conf),
            "source_count": distinct_sources,
        }

    if candidate.get("page_type") == "research_synthesis":
        min_sources = semantic.get("min_sources_research_synthesis")
        if min_sources is not None and distinct_sources < int(min_sources):
            return {
                "candidate_id": candidate.get("candidate_id"),
                "target_slug": candidate.get("target_slug"),
                "page_type": candidate.get("page_type"),
                "reason": "insufficient_sources_research_synthesis",
                "computed_confidence": confidence,
                "threshold": int(min_sources),
                "source_count": distinct_sources,
            }

    return None


def compute_page_confidence(conn, supporting_records: list[str]) -> float | None:
    """Derive a page's confidence from its supporting records.

    Returns MIN(records.confidence) over active records whose id is in
    supporting_records. Returns None if no active supporting records have
    a non-null confidence. MIN is conservative by design: a page is as
    confident as its weakest supporting record.
    """
    if not supporting_records:
        return None
    placeholders = ",".join("?" for _ in supporting_records)
    row = conn.execute(
        f"SELECT MIN(confidence) AS c FROM records "
        f"WHERE id IN ({placeholders}) AND confidence IS NOT NULL",
        supporting_records,
    ).fetchone()
    if row is None or row["c"] is None:
        return None
    return float(row["c"])


def _snapshot_slug_parts(target_slug: str) -> list[str]:
    """Strip a leading 'live/' prefix so snapshots live under
    wiki/snapshots/<rest>/ rather than wiki/snapshots/live/<rest>/."""
    parts = [p for p in target_slug.split("/") if p]
    if parts and parts[0] == "live":
        parts = parts[1:]
    return parts


def capture_snapshot(
    conn,
    *,
    live_page_id: str,
    live_row: dict,
    now: str,
) -> dict | None:
    """Copy the current on-disk content of a live page into wiki/snapshots/
    and register it as a snapshot page.

    Preconditions:
      - live_row is the existing wiki_pages row BEFORE it is overwritten.
      - The stored_path on disk still contains the old content (caller has
        not yet written the new content).

    Returns a dict with snapshot page_id and snapshot_id, or None if the
    prior file is missing (nothing to preserve).
    """
    stored = live_row["stored_path"]
    if not stored:
        return None
    stored_path = KB_ROOT / stored if not Path(stored).is_absolute() else Path(stored)
    if not stored_path.is_file():
        return None

    ts_safe = now.replace(":", "").replace("-", "").replace(".", "")
    parts = _snapshot_slug_parts(live_row["target_slug"])
    snapshot_dir = KB_ROOT / "wiki" / "snapshots" / Path(*parts) if parts else KB_ROOT / "wiki" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = snapshot_dir / f"{ts_safe}.md"
    # Avoid clobbering an existing snapshot at the same instant.
    counter = 0
    while snapshot_file.exists():
        counter += 1
        snapshot_file = snapshot_dir / f"{ts_safe}-{counter}.md"
    snapshot_file.write_bytes(stored_path.read_bytes())

    snapshot_rel = snapshot_file.relative_to(KB_ROOT).as_posix()
    old_content_hash = live_row["content_hash"] or ""
    snapshot_page_id = (
        "wps-"
        + hashlib.sha256(
            f"{live_page_id}:{now}:{counter}".encode("utf-8")
        ).hexdigest()[:12]
    )
    snapshot_slug = "snapshots/" + "/".join(parts + [ts_safe]) if parts else f"snapshots/{ts_safe}"

    conn.execute(
        """
        INSERT INTO wiki_pages (
            page_id, target_slug, page_class, page_type, title, domain, state,
            candidate_id, content_hash, stored_path, supporting_records_json,
            supporting_sources_json, confidence, superseded_by, snapshot_of,
            generated_at, updated_at
        ) VALUES (?, ?, 'snapshot', ?, ?, ?, 'managed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_page_id,
            snapshot_slug,
            live_row["page_type"],
            f"{live_row['title']} (snapshot {ts_safe})",
            live_row["domain"],
            live_row["candidate_id"],
            old_content_hash,
            snapshot_rel,
            live_row["supporting_records_json"] or "[]",
            live_row["supporting_sources_json"] or "[]",
            live_row["confidence"],
            live_page_id,
            live_page_id,
            live_row["generated_at"],
            now,
        ),
    )
    cur = conn.execute(
        """
        INSERT INTO wiki_snapshots (
            snapshot_id, live_page_id, taken_at, reason, content_hash, stored_path
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_page_id,
            live_page_id,
            now,
            "pre_resync",
            old_content_hash,
            snapshot_rel,
        ),
    )
    return {
        "snapshot_page_id": snapshot_page_id,
        "snapshot_id": snapshot_page_id,
        "stored_path": snapshot_rel,
        "reason": "pre_resync",
    }


def mark_stale_pages(conn) -> dict:
    """Transition managed live pages to 'stale' when their supporting records
    have moved beyond the page's generated_at, or when the page no longer has
    supporting records attached. Called after a sync pass so pages that were
    just (re)generated are not flagged stale immediately.

    Returns counts for reporting.
    """
    now = now_iso()
    rows = conn.execute(
        "SELECT page_id, generated_at, supporting_records_json "
        "FROM wiki_pages "
        "WHERE page_class = 'live' AND state = 'managed'"
    ).fetchall()
    staled: list[str] = []
    for row in rows:
        try:
            record_ids = json.loads(row["supporting_records_json"] or "[]")
        except (TypeError, ValueError):
            record_ids = []
        if not record_ids:
            conn.execute(
                "UPDATE wiki_pages SET state = 'stale', updated_at = ? WHERE page_id = ?",
                (now, row["page_id"]),
            )
            staled.append(row["page_id"])
            continue
        placeholders = ",".join("?" for _ in record_ids)
        newer = conn.execute(
            f"SELECT 1 FROM records WHERE id IN ({placeholders}) AND updated_at > ? LIMIT 1",
            list(record_ids) + [row["generated_at"]],
        ).fetchone()
        if newer is not None:
            conn.execute(
                "UPDATE wiki_pages SET state = 'stale', updated_at = ? WHERE page_id = ?",
                (now, row["page_id"]),
            )
            staled.append(row["page_id"])
    return {"staled_count": len(staled), "staled_page_ids": staled}


def persist_page(
    conn,
    *,
    candidate: dict,
    content: str,
    stored_path: str,
    now: str,
    snapshot_info: dict | None = None,
) -> dict:
    page_id = compute_page_id(candidate["target_slug"])
    content_hash = compute_content_hash(content)
    target_slug = candidate["target_slug"]
    page_class = "snapshot" if target_slug.startswith("snapshots/") else "live"
    page_type = candidate["page_type"]
    title = candidate["title"]
    domain = None
    parts = target_slug.split("/")
    if len(parts) >= 2 and parts[0] == "live":
        domain = parts[1]
    candidate_id = candidate["candidate_id"]
    supporting_records = list(candidate.get("supporting_record_ids", []))
    supporting_sources = list(candidate.get("supporting_sources", []))
    records_json = json.dumps(supporting_records, ensure_ascii=False)
    sources_json = json.dumps(supporting_sources, ensure_ascii=False)
    confidence = compute_page_confidence(conn, supporting_records)

    existing = conn.execute(
        "SELECT content_hash, generated_at FROM wiki_pages WHERE page_id = ?",
        (page_id,),
    ).fetchone()
    unchanged = existing is not None and existing["content_hash"] == content_hash
    generated_at = existing["generated_at"] if unchanged else now

    conn.execute(
        """
        INSERT INTO wiki_pages (
            page_id, target_slug, page_class, page_type, title, domain, state,
            candidate_id, content_hash, stored_path, supporting_records_json,
            supporting_sources_json, confidence, generated_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'managed', ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(page_id) DO UPDATE SET
            target_slug = excluded.target_slug,
            page_class = excluded.page_class,
            page_type = excluded.page_type,
            title = excluded.title,
            domain = excluded.domain,
            state = 'managed',
            candidate_id = excluded.candidate_id,
            content_hash = excluded.content_hash,
            stored_path = excluded.stored_path,
            supporting_records_json = excluded.supporting_records_json,
            supporting_sources_json = excluded.supporting_sources_json,
            confidence = excluded.confidence,
            generated_at = excluded.generated_at,
            updated_at = excluded.updated_at
        """,
        (
            page_id, target_slug, page_class, page_type, title, domain,
            candidate_id, content_hash, stored_path, records_json, sources_json,
            confidence, generated_at, now,
        ),
    )
    conn.execute("DELETE FROM wiki_page_provenance WHERE page_id = ?", (page_id,))
    for rid in supporting_records:
        conn.execute(
            "INSERT INTO wiki_page_provenance(page_id, kind, ref_id) "
            "VALUES (?, 'record', ?)",
            (page_id, rid),
        )
    for sid in supporting_sources:
        conn.execute(
            "INSERT INTO wiki_page_provenance(page_id, kind, ref_id) "
            "VALUES (?, 'source', ?)",
            (page_id, sid),
        )
    return {
        "page_id": page_id,
        "content_hash": content_hash,
        "changed": not unchanged,
        "page_class": page_class,
        "confidence": confidence,
        "snapshot": snapshot_info,
    }


def reconcile_wiki_pages(conn) -> dict:
    rows = conn.execute(
        "SELECT page_id, stored_path FROM wiki_pages WHERE state != 'orphan'"
    ).fetchall()
    now = now_iso()
    orphaned: list[str] = []
    for row in rows:
        stored = row["stored_path"]
        if not stored:
            continue
        candidate_path = KB_ROOT / stored if not Path(stored).is_absolute() else Path(stored)
        if not candidate_path.is_file():
            conn.execute(
                "UPDATE wiki_pages SET state = 'orphan', updated_at = ? WHERE page_id = ?",
                (now, row["page_id"]),
            )
            orphaned.append(row["page_id"])
    return {"orphaned_count": len(orphaned), "orphaned_page_ids": orphaned}


def reconcile_obsolete_pages(conn, keep_page_ids, *, domain=None, now=None) -> dict:
    """Remove managed/stale live pages that were not (re)published this sync, so
    the wiki self-cleans instead of carrying stale, unpublishable pages.

    ``keep_page_ids`` is the set of page_ids published this pass; a managed/stale
    live page outside it is obsolete (no candidate) or unpublishable (held back by
    a hygiene gate or review-required) and is removed.

    Wiki pages are derived surfaces, not canonical memory (the underlying typed
    records persist in the KB), so an obsolete page is removed outright. FK
    integrity is preserved by clearing the snapshot index and provenance rows
    that reference the page before deleting it; snapshot files and snapshot rows
    remain on disk as history.

    When ``domain`` is set, only pages within that domain are considered, so a
    domain-scoped sync never prunes another domain's pages.
    """
    now = now or now_iso()
    rows = conn.execute(
        "SELECT page_id, domain, stored_path "
        "FROM wiki_pages WHERE page_class = 'live' AND state IN ('managed', 'stale')"
    ).fetchall()
    removed: list[str] = []
    for row in rows:
        if row["page_id"] in keep_page_ids:
            continue
        if domain is not None and row["domain"] != domain:
            continue
        stored = row["stored_path"]
        if stored:
            path = KB_ROOT / stored if not Path(stored).is_absolute() else Path(stored)
            if path.is_file() and is_managed_wiki_file(path):
                path.unlink()
        # Clear FK references before deleting the live row (foreign_keys = ON).
        conn.execute("DELETE FROM wiki_snapshots WHERE live_page_id = ?", (row["page_id"],))
        conn.execute("DELETE FROM wiki_page_provenance WHERE page_id = ?", (row["page_id"],))
        conn.execute("DELETE FROM wiki_pages WHERE page_id = ?", (row["page_id"],))
        removed.append(row["page_id"])
    return {"removed_count": len(removed), "removed_page_ids": removed}


def sync_wiki(domain: str | None = None, force: bool = False, *, candidate_provider, now_iso) -> dict:
    config = load_config()
    ensure_dirs(config)
    wiki_cfg = get_wiki_config(config)
    if not wiki_cfg.get("enabled", False) and not force:
        return {
            "written": [],
            "written_count": 0,
            "skipped_review_required": [],
            "skipped_existing_snapshot": [],
            "total_candidates": 0,
            "skipped_reason": "wiki_disabled",
            "persisted_pages": [],
            "reconcile": {"orphaned_count": 0, "orphaned_page_ids": []},
            "obsolete_removed": {"removed_count": 0, "removed_page_ids": []},
            "snapshots_created": [],
            "stale": {"staled_count": 0, "staled_page_ids": []},
            "held_back": [],
        }
    conn = connect()
    reconcile = reconcile_wiki_pages(conn)
    candidates = candidate_provider(conn, config, wiki_cfg)
    if domain:
        candidates = [candidate for candidate in candidates if domain in candidate["target_slug"]]
    # The record index is a managed live page and part of every candidate set,
    # including a domain-scoped sync. This prevents the reconciler from pruning
    # it and keeps fallback record links available.
    candidates.append(_record_index_candidate(conn))
    syncable = [candidate for candidate in candidates if candidate["status"] == "heuristic_candidate"]
    skipped_review = [candidate for candidate in candidates if candidate["status"] == "review_required"]
    wiki_root = KB_ROOT / "wiki"
    written: list[str] = []
    skipped_existing_snapshot: list[str] = []
    persisted: list[dict] = []
    snapshots_created: list[dict] = []
    held_back: list[dict] = []
    now = now_iso()

    publishable: list[dict] = []
    for candidate in syncable:
        target = wiki_root / candidate["target_slug"]
        target_md = target if target.suffix == ".md" else target.with_suffix(".md")
        if target_md.exists() and not is_managed_wiki_file(target_md):
            held_back.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "target_slug": candidate["target_slug"],
                    "page_type": candidate["page_type"],
                    "reason": "unmanaged_target_collision",
                }
            )
            continue
        gate = None
        if candidate["page_type"] != "record_index":
            gate = evaluate_hygiene_gates(conn, candidate, wiki_cfg)
        if gate is not None:
            held_back.append(gate)
            continue
        publishable.append(candidate)

    navigation = _build_navigation_context(conn, publishable)
    for candidate in publishable:
        target = wiki_root / candidate["target_slug"]
        target_md = target if target.suffix == ".md" else target.with_suffix(".md")
        if "snapshots/" in candidate["target_slug"] and target_md.exists():
            skipped_existing_snapshot.append(candidate["candidate_id"])
            continue
        page_id_pre = compute_page_id(candidate["target_slug"])
        existing_pre = conn.execute(
            "SELECT * FROM wiki_pages WHERE page_id = ?", (page_id_pre,)
        ).fetchone()
        content = build_wiki_page(
            candidate,
            conn,
            now_iso=lambda: now,
            navigation=navigation,
            generated_at=now,
        )
        if existing_pre is not None and (
            (existing_pre["content_hash"] or "") == compute_content_hash(content)
        ):
            # Re-render with the prior timestamp so a no-op sync is byte-for-byte
            # stable, not merely stable after timestamp-stripped hashing.
            content = build_wiki_page(
                candidate,
                conn,
                now_iso=lambda: now,
                navigation=navigation,
                generated_at=existing_pre["generated_at"],
            )
        # Pre-write snapshot capture: if this is a live page whose content is
        # about to change AND a prior file exists on disk, preserve the old
        # content as a snapshot BEFORE we overwrite it.
        is_live = not candidate["target_slug"].startswith("snapshots/")
        new_hash = compute_content_hash(content)
        snapshot_info: dict | None = None
        if is_live:
            if (
                existing_pre is not None
                and (existing_pre["content_hash"] or "") != new_hash
            ):
                snapshot_info = capture_snapshot(
                    conn,
                    live_page_id=page_id_pre,
                    live_row=dict(existing_pre),
                    now=now,
                )
                if snapshot_info:
                    snapshots_created.append(snapshot_info)
        target_md.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        if not target_md.exists() or target_md.read_bytes() != encoded:
            target_md.write_bytes(encoded)
            written.append(candidate["candidate_id"])
        persisted.append(
            persist_page(
                conn,
                candidate=candidate,
                content=content,
                stored_path=_relative_stored_path(target_md),
                now=now,
                snapshot_info=snapshot_info,
            )
        )
    # Self-clean: a managed live page survives only if it was (re)published this
    # sync. Pages that are obsolete or unpublishable (held back / review-required)
    # are removed so the live wiki never carries stale, unpublishable content.
    published_page_ids = {p["page_id"] for p in persisted}
    obsolete_removed = reconcile_obsolete_pages(conn, published_page_ids, domain=domain, now=now)
    stale = mark_stale_pages(conn)
    conn.commit()
    return {
        "written": written,
        "written_count": len(written),
        "skipped_review_required": [candidate["candidate_id"] for candidate in skipped_review],
        "skipped_existing_snapshot": skipped_existing_snapshot,
        "total_candidates": len(candidates),
        "persisted_pages": persisted,
        "reconcile": reconcile,
        "obsolete_removed": obsolete_removed,
        "snapshots_created": snapshots_created,
        "stale": stale,
        "held_back": held_back,
    }


def render_wiki_sync_text(result: dict) -> str:
    lines = [f"Wiki sync: {result['written_count']} pages written"]
    if result["skipped_review_required"]:
        lines.append(f"  skipped (review_required): {len(result['skipped_review_required'])}")
    if result["skipped_existing_snapshot"]:
        lines.append(f"  skipped (existing snapshot): {len(result['skipped_existing_snapshot'])}")
    held_back = result.get("held_back") or []
    if held_back:
        lines.append(f"  held back (hygiene gates): {len(held_back)}")
        for entry in held_back:
            lines.append(
                f"    - {entry.get('candidate_id')}: {entry.get('reason')} "
                f"(page_type={entry.get('page_type')}, "
                f"confidence={entry.get('computed_confidence')}, "
                f"sources={entry.get('source_count')})"
            )
    reconcile = result.get("reconcile") or {}
    if reconcile.get("orphaned_count"):
        lines.append(f"  reconcile orphaned: {reconcile['orphaned_count']}")
    obsolete = result.get("obsolete_removed") or {}
    if obsolete.get("removed_count"):
        lines.append(f"  obsolete removed: {obsolete['removed_count']}")
    snapshots_created = result.get("snapshots_created") or []
    if snapshots_created:
        lines.append(f"  snapshots created: {len(snapshots_created)}")
    stale = result.get("stale") or {}
    if stale.get("staled_count"):
        lines.append(f"  marked stale: {stale['staled_count']}")
    persisted = result.get("persisted_pages") or []
    changed = [p for p in persisted if p.get("changed")]
    if persisted:
        lines.append(f"  persisted rows: {len(persisted)} ({len(changed)} changed)")
    for written_id in result["written"]:
        lines.append(f"  + {written_id}")
    return "\n".join(lines)


def cmd_wiki_sync(args, *, emit, candidate_provider, now_iso, log_operation=None) -> None:
    result = sync_wiki(
        domain=args.domain,
        force=args.force,
        candidate_provider=candidate_provider,
        now_iso=now_iso,
    )
    if log_operation is not None and result.get("skipped_reason") != "wiki_disabled":
        from .db import connect as _connect

        conn = _connect()
        log_operation(
            conn,
            "wiki_sync",
            "wiki-sync",
            {
                "written_count": result.get("written_count", 0),
                "skipped_count": result.get("skipped_count", 0),
                "held_back_count": len(result.get("held_back") or []),
                "forced": args.force,
            },
            summary=(
                f"Wiki sync: {result.get('written_count', 0)} written, "
                f"{len(result.get('held_back') or [])} held_back"
            ),
        )
    if result.get("skipped_reason") == "wiki_disabled":
        print("Wiki is disabled in config. Use --force to sync anyway, or set wiki.enabled = true.")
        return
    if args.json:
        emit(result, True)
        return
    emit({"__plain__": True, "text": render_wiki_sync_text(result)}, False)


def get_db_wiki_checks(conn) -> dict:
    """Deterministic DB-backed lint signals that complement the markdown-
    citation parser. Returns counts plus small sample lists for operator
    triage. No heuristics.
    """
    config = load_config()
    wiki_cfg = get_wiki_config(config)
    review_threshold = (
        wiki_cfg.get("semantic", {}) or {}
    ).get("min_confidence_review", 0.55)

    orphan_rows = conn.execute(
        "SELECT page_id, target_slug, stored_path FROM wiki_pages "
        "WHERE state = 'orphan' ORDER BY page_id"
    ).fetchall()
    stale_rows = conn.execute(
        "SELECT page_id, target_slug, generated_at FROM wiki_pages "
        "WHERE state = 'stale' ORDER BY page_id"
    ).fetchall()
    low_conf_rows = conn.execute(
        "SELECT page_id, target_slug, confidence FROM wiki_pages "
        "WHERE page_class = 'live' AND confidence IS NOT NULL AND confidence < ? "
        "ORDER BY confidence ASC LIMIT 20",
        (review_threshold,),
    ).fetchall()
    collision_rows = conn.execute(
        "SELECT category, domain, lower(title) AS title_key, COUNT(*) AS n "
        "FROM records WHERE status = 'ATIVO' "
        "GROUP BY category, domain, lower(title) "
        "HAVING COUNT(*) > 1 "
        "ORDER BY n DESC, domain ASC"
    ).fetchall()

    return {
        "review_threshold": review_threshold,
        "orphan_pages": {
            "count": len(orphan_rows),
            "items": [dict(r) for r in orphan_rows[:20]],
        },
        "stale_pages": {
            "count": len(stale_rows),
            "items": [dict(r) for r in stale_rows[:20]],
        },
        "low_confidence_pages": {
            "count": len(low_conf_rows),
            "items": [dict(r) for r in low_conf_rows],
        },
        "title_collisions": {
            "count": len(collision_rows),
            "items": [dict(r) for r in collision_rows[:20]],
        },
    }


def list_wiki_pages(
    conn,
    *,
    state: str | None = None,
    page_class: str | None = None,
    domain: str | None = None,
    page_type: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
) -> list[dict]:
    sql = (
        "SELECT page_id, target_slug, page_class, page_type, title, domain, "
        "state, confidence, generated_at, updated_at, stored_path, "
        "snapshot_of, superseded_by FROM wiki_pages WHERE 1=1"
    )
    params: list = []
    if state:
        sql += " AND state = ?"
        params.append(state)
    if page_class:
        sql += " AND page_class = ?"
        params.append(page_class)
    if domain:
        sql += " AND domain = ?"
        params.append(domain)
    if page_type:
        sql += " AND page_type = ?"
        params.append(page_type)
    if min_confidence is not None:
        sql += " AND confidence IS NOT NULL AND confidence >= ?"
        params.append(min_confidence)
    sql += " ORDER BY page_class, domain, target_slug"
    if limit and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    result: list[dict] = []
    for row in rows:
        entry = dict(row)
        supp = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM wiki_page_provenance "
            "WHERE page_id = ? GROUP BY kind",
            (entry["page_id"],),
        ).fetchall()
        entry["provenance_counts"] = {r["kind"]: r["n"] for r in supp}
        result.append(entry)
    return result


def cmd_wiki_pages(args, *, emit) -> None:
    conn = connect()
    pages = list_wiki_pages(
        conn,
        state=getattr(args, "state", None),
        page_class=getattr(args, "page_class", None),
        domain=getattr(args, "domain", None),
        page_type=getattr(args, "page_type", None),
        min_confidence=getattr(args, "min_confidence", None),
        limit=getattr(args, "limit", 50) or 50,
    )
    if getattr(args, "json", False):
        emit(pages, True)
        return
    if not pages:
        emit({"__plain__": True, "text": "No wiki pages match."}, False)
        return
    lines = [f"Wiki pages: {len(pages)}", ""]
    for p in pages:
        conf = p.get("confidence")
        conf_str = f"{conf:.2f}" if conf is not None else "-"
        lines.append(
            f"  [{p['page_id']}] {p['page_class']}/{p['state']} "
            f"conf={conf_str} {p['target_slug']}"
        )
        counts = p.get("provenance_counts") or {}
        if counts:
            lines.append(
                "    provenance: "
                + ", ".join(f"{k}={v}" for k, v in counts.items())
            )
    emit({"__plain__": True, "text": "\n".join(lines)}, False)


def get_wiki_lint_result(*, is_managed_file=None, parse_citation=None) -> dict:
    is_managed_file = is_managed_file or is_managed_wiki_file
    parse_citation = parse_citation or parse_citation_block
    load_config()
    conn = connect()
    issues: list[dict] = []
    # Lint only the live wiki. Snapshots are immutable history: they are meant to
    # be old and to cite the state they froze (records later superseded/resolved),
    # so flagging them as stale or record-inactive is incorrect.
    for wiki_dir in (KB_ROOT / "wiki" / "live",):
        if not wiki_dir.is_dir():
            continue
        for md_path in sorted(wiki_dir.rglob("*.md")):
            if not is_managed_file(md_path):
                continue
            rel = md_path.relative_to(KB_ROOT / "wiki").as_posix()
            is_record_index = rel == "live/index.md"
            citation = parse_citation(md_path)
            if citation is None:
                issues.append({"file": rel, "issue": "citation_missing", "detail": "No citation block found"})
                continue
            rec_ids = [
                record_id.strip()
                for record_id in citation.get("supporting_records", "").split(",")
                if record_id.strip() and record_id.strip() != "none"
            ]
            if not rec_ids and not is_record_index:
                issues.append({"file": rel, "issue": "orphan_page", "detail": "No supporting record IDs in citation"})
                continue
            any_active = False
            page_generated = citation.get("generated", "")
            any_record_newer = False
            for record_id in rec_ids:
                row = conn.execute(
                    "SELECT id, status, updated_at FROM records WHERE id = ?",
                    (record_id,),
                ).fetchone()
                if row is None:
                    issues.append({"file": rel, "issue": "record_missing", "detail": f"Record {record_id} not found in KB"})
                    continue
                if row["status"] != "ATIVO" and not is_record_index:
                    issues.append({"file": rel, "issue": "record_not_active", "detail": f"Record {record_id} status is {row['status']}"})
                else:
                    any_active = True
                if page_generated and row["updated_at"] > page_generated:
                    any_record_newer = True
            if not any_active and rec_ids and not is_record_index:
                issues.append({"file": rel, "issue": "orphan_page", "detail": "All supporting records are missing or inactive"})
            if any_record_newer:
                issues.append({"file": rel, "issue": "stale_page", "detail": f"Page generated at {page_generated} but supporting records updated since"})
    db_checks = get_db_wiki_checks(conn)
    db_issue_count = (
        db_checks["orphan_pages"]["count"]
        + db_checks["stale_pages"]["count"]
        + db_checks["low_confidence_pages"]["count"]
        + db_checks["title_collisions"]["count"]
    )
    return {
        "issues": issues,
        "issue_count": len(issues),
        "checked_dirs": ["wiki/live", "wiki/snapshots"],
        "db_checks": db_checks,
        "db_issue_count": db_issue_count,
    }


def render_wiki_lint_text(result: dict) -> str:
    issues = result["issues"]
    db_checks = result.get("db_checks") or {}
    db_issue_count = result.get("db_issue_count", 0)
    lines: list[str] = []
    if issues:
        lines.append(f"Wiki lint (markdown): {len(issues)} issue(s)")
        for issue in issues:
            lines.append(f"  [{issue['issue']}] {issue['file']}: {issue['detail']}")
    else:
        lines.append("Wiki lint (markdown): no issues found.")
    lines.append("")
    lines.append(f"Wiki lint (db): {db_issue_count} signal(s)")
    for key in ("orphan_pages", "stale_pages", "low_confidence_pages", "title_collisions"):
        bucket = db_checks.get(key) or {}
        count = bucket.get("count", 0)
        if count:
            lines.append(f"  {key}: {count}")
    return "\n".join(lines)


def cmd_wiki_lint(args, *, emit, is_managed_file=None, parse_citation=None, log_operation=None) -> None:
    result = get_wiki_lint_result(
        is_managed_file=is_managed_file,
        parse_citation=parse_citation,
    )
    if log_operation is not None:
        from .db import connect as _connect

        conn = _connect()
        log_operation(
            conn,
            "wiki_lint",
            "wiki-lint",
            {"issue_count": result["issue_count"]},
            summary=f"Wiki lint: {result['issue_count']} issues",
        )
    if args.json:
        emit(result, True)
        return
    text = render_wiki_lint_text(result)
    if result["issue_count"] == 0:
        print(text)
        return
    emit({"__plain__": True, "text": text}, False)
