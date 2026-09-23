from __future__ import annotations

import json
import sqlite3

from .config import load_config, write_config
from .constants import LIFECYCLE_DEFAULTS
from .db import connect_readonly
from .paths import CONFIG_PATH, KB_ROOT, ensure_dirs

# Lifecycle events that keep the derived wiki current once it is enabled.
WIKI_SYNC_EVENTS = ("record_filed", "source_ingest", "session_end", "scheduled_maintenance")


WIKI_DEFAULTS = {
    "enabled": False,
    "activation_mode": "manual",
    "project_profile": None,
    "page_types": [
        "domain_overview",
        "research_synthesis",
        "onboarding",
        "snapshot_report",
    ],
    "eligibility": {
        "min_active_records": 30,
        "min_domains_with_records": 2,
        "min_soft_signal_score": 1,
    },
    "semantic": {
        "min_confidence_autopublish": 0.8,
        "min_confidence_review": 0.55,
        "min_sources_research_synthesis": 2,
    },
    "renderers": {"mkdocs": {"enabled": False, "site_name": "Project Wiki"}},
}

PROFILE_PRESETS: dict[str, dict] = {
    "corporate_companion": {
        "eligibility": {
            "min_active_records": 50,
            "min_domains_with_records": 2,
            "min_soft_signal_score": 2,
        },
    },
    "strategic_framework": {
        "eligibility": {
            "min_active_records": 15,
            "min_domains_with_records": 2,
            "min_soft_signal_score": 1,
        },
    },
    "hybrid_research_ops": {
        "eligibility": {
            "min_active_records": 30,
            "min_domains_with_records": 2,
            "min_soft_signal_score": 1,
        },
    },
}


def get_wiki_config(config: dict) -> dict:
    wiki = config.get("wiki", {})
    merged = {**WIKI_DEFAULTS, **wiki}

    # Start with default eligibility
    elig = {**WIKI_DEFAULTS["eligibility"]}

    # Apply profile preset thresholds if activation_mode is "profile"
    mode = merged.get("activation_mode", "manual")
    profile_name = merged.get("project_profile")
    if mode == "profile" and profile_name and profile_name in PROFILE_PRESETS:
        preset = PROFILE_PRESETS[profile_name]
        elig.update(preset.get("eligibility", {}))

    # User-specified eligibility overrides profile presets
    elig.update(wiki.get("eligibility", {}))
    merged["eligibility"] = elig

    # Semantic resolution: defaults -> profile preset overlay -> user override.
    # Mirrors the eligibility flow so profile overlays can tune hygiene gates
    # (min_confidence_autopublish, min_sources_research_synthesis, ...).
    semantic = {**WIKI_DEFAULTS["semantic"]}
    if mode == "profile" and profile_name and profile_name in PROFILE_PRESETS:
        preset = PROFILE_PRESETS[profile_name]
        semantic.update(preset.get("semantic", {}))
    semantic.update(wiki.get("semantic", {}))
    merged["semantic"] = semantic

    merged["renderers"] = {**WIKI_DEFAULTS["renderers"], **wiki.get("renderers", {})}
    return merged


def compute_wiki_hard_signals(conn: sqlite3.Connection, eligibility: dict) -> dict:
    active_count = conn.execute(
        "SELECT COUNT(*) FROM records WHERE status = 'ATIVO'"
    ).fetchone()[0]
    domain_rows = conn.execute(
        "SELECT domain, COUNT(*) AS cnt FROM records WHERE status = 'ATIVO' GROUP BY domain"
    ).fetchall()
    domains_with_records = len(domain_rows)
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM records WHERE category = 'PENDENCIA' AND status = 'ATIVO'"
    ).fetchone()[0]
    min_records = eligibility.get("min_active_records", 30)
    min_domains = eligibility.get("min_domains_with_records", 2)
    signals = {
        "active_record_count": active_count,
        "min_active_records_threshold": min_records,
        "active_record_count_met": active_count >= min_records,
        "domains_with_active_records": domains_with_records,
        "min_domains_threshold": min_domains,
        "domains_threshold_met": domains_with_records >= min_domains,
        "open_pendencias": pending_count,
        "has_open_pendencias": pending_count > 0,
    }
    signals["any_hard_signal"] = (
        signals["active_record_count_met"]
        or signals["domains_threshold_met"]
        or signals["has_open_pendencias"]
    )
    return signals


def compute_soft_signals(conn: sqlite3.Connection) -> dict:
    signals: dict[str, bool] = {}
    rows = conn.execute(
        "SELECT domain, COUNT(DISTINCT category) AS cat_cnt "
        "FROM records WHERE status = 'ATIVO' GROUP BY domain"
    ).fetchall()
    signals["cross_category_domain"] = any(r["cat_cnt"] >= 3 for r in rows)

    supersedes_count = conn.execute(
        "SELECT COUNT(*) FROM records WHERE status = 'ATIVO' AND supersedes_id IS NOT NULL"
    ).fetchone()[0]
    signals["has_supersede_chains"] = supersedes_count > 0

    high_access = conn.execute(
        "SELECT COUNT(*) FROM records WHERE status = 'ATIVO' AND access_count >= 3"
    ).fetchone()[0]
    signals["high_access_records"] = high_access > 0

    all_tags: set[str] = set()
    tag_rows = conn.execute(
        "SELECT tags_json FROM records WHERE status = 'ATIVO'"
    ).fetchall()
    for row in tag_rows:
        for tag in json.loads(row["tags_json"]):
            all_tags.add(tag)
    signals["tag_diversity"] = len(all_tags) >= 5

    score = sum(1 for value in signals.values() if value)
    return {
        "soft_signal_score": score,
        "signals": signals,
        "evaluator": "deterministic_phase_c",
        "note": "Deterministic heuristic evaluator. A future LLM-backed evaluator can replace or augment this.",
    }


def _state_from_candidates(wiki_cfg: dict, candidate_count: int) -> str:
    if not wiki_cfg.get("page_types", []):
        return "eligible"
    return "active" if candidate_count > 0 else "eligible"


def compute_wiki_state(
    wiki_cfg: dict, hard_signals: dict, soft_result: dict, candidate_count: int
) -> str:
    """Single semantics for every activation_mode.

    `enabled: true` is the owner's explicit opt-in: the wiki is on and signals
    never veto it, whatever the mode. With `enabled: false`, `manual` (and any
    unknown mode) stays off, while `signal`/`profile` let the hard and soft
    signals decide.
    """
    if wiki_cfg.get("enabled", False):
        return _state_from_candidates(wiki_cfg, candidate_count)
    mode = wiki_cfg.get("activation_mode", "manual")
    if mode not in ("signal", "profile"):
        return "off"
    if not hard_signals["any_hard_signal"]:
        return "off"
    soft_threshold = wiki_cfg.get("eligibility", {}).get("min_soft_signal_score", 1)
    if soft_result["soft_signal_score"] < soft_threshold:
        return "off"
    return _state_from_candidates(wiki_cfg, candidate_count)


def wiki_sync_allowed(state: str) -> bool:
    return state in ("eligible", "active")


def resolve_wiki_state(conn: sqlite3.Connection, config: dict, candidate_provider=None) -> tuple[str, dict, list]:
    """Return (state, wiki_cfg, candidates) for sync and lifecycle decisions."""
    wiki_cfg = get_wiki_config(config)
    hard_signals = compute_wiki_hard_signals(conn, wiki_cfg.get("eligibility", {}))
    soft_result = compute_soft_signals(conn)
    candidates = candidate_provider(conn, config, wiki_cfg) if candidate_provider is not None else []
    return compute_wiki_state(wiki_cfg, hard_signals, soft_result, len(candidates)), wiki_cfg, candidates


def preview_publication(conn: sqlite3.Connection, candidates: list, wiki_cfg: dict) -> dict:
    """What a sync would publish, hold back, or skip, without writing anything."""
    from .wiki_materialization import evaluate_hygiene_gates

    held_back: list[dict] = []
    review_required: list[str] = []
    publishable: list[str] = []
    for candidate in candidates:
        if candidate.get("status") == "review_required":
            review_required.append(candidate.get("candidate_id"))
            continue
        if candidate.get("status") != "heuristic_candidate":
            continue
        gate = evaluate_hygiene_gates(conn, candidate, wiki_cfg)
        if gate is None:
            publishable.append(candidate.get("candidate_id"))
        else:
            held_back.append(gate)
    by_reason: dict[str, int] = {}
    for entry in held_back:
        by_reason[entry["reason"]] = by_reason.get(entry["reason"], 0) + 1
    return {
        "publishable_count": len(publishable),
        "publishable": publishable,
        "held_back_count": len(held_back),
        "held_back_by_reason": by_reason,
        "held_back": held_back,
        "review_required_count": len(review_required),
        "review_required": review_required,
    }


def lifecycle_sync_events(config: dict) -> dict:
    events = ((config.get("lifecycle") or {}).get("events") or {})
    status = {}
    for event in WIKI_SYNC_EVENTS:
        default = LIFECYCLE_DEFAULTS["events"].get(event, {}).get("run_wiki_sync", False)
        status[event] = bool((events.get(event) or {}).get("run_wiki_sync", default))
    return status


def get_wiki_check_result(
    config: dict | None = None,
    conn: sqlite3.Connection | None = None,
    candidate_provider=None,
) -> dict:
    config = config or load_config()
    ensure_dirs(config)
    wiki_cfg = get_wiki_config(config)
    conn = conn or connect_readonly()
    hard_signals = compute_wiki_hard_signals(conn, wiki_cfg.get("eligibility", {}))
    soft_result = compute_soft_signals(conn)
    candidates: list = []
    if candidate_provider is not None:
        candidates = candidate_provider(conn, config, wiki_cfg)
    candidate_count = len(candidates)
    state = compute_wiki_state(wiki_cfg, hard_signals, soft_result, candidate_count)
    soft_threshold = wiki_cfg.get("eligibility", {}).get("min_soft_signal_score", 1)
    state_rows = conn.execute(
        "SELECT page_class, state, COUNT(*) AS n FROM wiki_pages "
        "GROUP BY page_class, state"
    ).fetchall()
    page_state_counts: dict = {"live": {}, "snapshot": {}, "totals": {}}
    for row in state_rows:
        cls = row["page_class"] or "unknown"
        st = row["state"] or "unknown"
        page_state_counts.setdefault(cls, {})[st] = row["n"]
        page_state_counts["totals"][st] = page_state_counts["totals"].get(st, 0) + row["n"]
    conf_row = conn.execute(
        "SELECT AVG(confidence) AS avg_c, MIN(confidence) AS min_c, MAX(confidence) AS max_c, "
        "COUNT(confidence) AS with_c, COUNT(*) AS total_pages "
        "FROM wiki_pages WHERE page_class = 'live'"
    ).fetchone()
    confidence_summary = {
        "pages_total": conf_row["total_pages"] or 0,
        "pages_with_confidence": conf_row["with_c"] or 0,
        "avg": float(conf_row["avg_c"]) if conf_row["avg_c"] is not None else None,
        "min": float(conf_row["min_c"]) if conf_row["min_c"] is not None else None,
        "max": float(conf_row["max_c"]) if conf_row["max_c"] is not None else None,
    }
    semantic_cfg = wiki_cfg.get("semantic", {}) or {}
    hygiene_gates = {
        "min_confidence_autopublish": semantic_cfg.get("min_confidence_autopublish"),
        "min_confidence_review": semantic_cfg.get("min_confidence_review"),
        "min_sources_research_synthesis": semantic_cfg.get(
            "min_sources_research_synthesis"
        ),
    }
    publication = preview_publication(conn, candidates, wiki_cfg)
    sync_events = lifecycle_sync_events(config)
    live_pages = sum(page_state_counts.get("live", {}).values())
    next_actions: list[str] = []
    if state == "off":
        next_actions.append(
            "wiki is off: run `kb.py wiki-config --enable` (or activate vNext with "
            "--choice kb-wiki) to turn it on"
        )
    elif not any(sync_events.values()):
        next_actions.append(
            "no lifecycle event syncs the wiki: run `kb.py wiki-config --enable` to "
            "enable run_wiki_sync on " + ", ".join(WIKI_SYNC_EVENTS)
        )
    if wiki_sync_allowed(state) and publication["publishable_count"] and not live_pages:
        next_actions.append("pages are publishable but none is live: run `kb.py wiki-sync`")
    if publication["held_back_by_reason"].get("insufficient_sources_research_synthesis"):
        next_actions.append(
            "research syntheses are held back for missing sources: ingest sources and "
            "link records with --source-id"
        )
    return {
        "wiki_state": state,
        "wiki_enabled_in_config": wiki_cfg.get("enabled", False),
        "activation_mode": wiki_cfg.get("activation_mode", "manual"),
        "project_profile": wiki_cfg.get("project_profile"),
        "effective_thresholds": wiki_cfg.get("eligibility", {}),
        "hard_signals": hard_signals,
        "soft_signals": soft_result,
        "soft_signal_threshold": soft_threshold,
        "candidate_count": candidate_count,
        "page_types_configured": wiki_cfg.get("page_types", []),
        "wiki_dirs_exist": (KB_ROOT / "wiki" / "live").is_dir(),
        "page_state_counts": page_state_counts,
        "confidence_summary": confidence_summary,
        "hygiene_gates": hygiene_gates,
        "sync_allowed": wiki_sync_allowed(state),
        "lifecycle_sync_events": sync_events,
        "publication": publication,
        "next_actions": next_actions,
    }


def render_wiki_check_text(result: dict) -> str:
    lines = [f"Wiki state: {result['wiki_state']}", ""]
    lines.append(f"Activation mode: {result['activation_mode']}")
    if result.get("project_profile"):
        lines.append(f"Project profile: {result['project_profile']}")
    lines.append("")
    lines.append("Hard signals:")
    hard_signals = result["hard_signals"]
    lines.append(
        "  active records: "
        f"{hard_signals['active_record_count']} "
        f"(threshold: {hard_signals['min_active_records_threshold']}, "
        f"met: {hard_signals['active_record_count_met']})"
    )
    lines.append(
        "  domains with records: "
        f"{hard_signals['domains_with_active_records']} "
        f"(threshold: {hard_signals['min_domains_threshold']}, "
        f"met: {hard_signals['domains_threshold_met']})"
    )
    lines.append(
        "  open pendencias: "
        f"{hard_signals['open_pendencias']} "
        f"(signal: {hard_signals['has_open_pendencias']})"
    )
    lines.append(f"  any hard signal met: {hard_signals['any_hard_signal']}")
    lines.append("")
    soft_signals = result["soft_signals"]
    soft_threshold = result["soft_signal_threshold"]
    lines.append(
        "Soft signal score: "
        f"{soft_signals['soft_signal_score']} "
        f"(threshold: {soft_threshold}, evaluator: {soft_signals['evaluator']})"
    )
    for signal_name, signal_value in soft_signals["signals"].items():
        lines.append(f"  {signal_name}: {signal_value}")
    lines.append("")
    lines.append(f"Candidate count: {result['candidate_count']}")
    publication = result.get("publication") or {}
    if publication:
        lines.append(
            f"  publishable: {publication.get('publishable_count', 0)}, "
            f"held back: {publication.get('held_back_count', 0)}, "
            f"review required: {publication.get('review_required_count', 0)}"
        )
        for reason, count in sorted((publication.get("held_back_by_reason") or {}).items()):
            lines.append(f"  held back ({reason}): {count}")
    lines.append(
        "Page types configured: "
        f"{', '.join(result['page_types_configured']) or 'none'}"
    )
    lines.append(f"Wiki dirs exist: {result['wiki_dirs_exist']}")
    sync_events = result.get("lifecycle_sync_events") or {}
    if sync_events:
        enabled = [name for name, on in sync_events.items() if on]
        lines.append(f"Lifecycle wiki sync on: {', '.join(enabled) or 'none'}")
    for action in result.get("next_actions") or []:
        lines.append(f"Next: {action}")
    return "\n".join(lines)


def cmd_wiki_check(args, *, emit, candidate_provider=None) -> None:
    config = load_config()
    result = get_wiki_check_result(
        config=config,
        candidate_provider=candidate_provider,
    )
    if args.json:
        emit(result, True)
        return
    emit({"__plain__": True, "text": render_wiki_check_text(result)}, False)


def apply_wiki_enabled(config: dict, enabled: bool) -> list[dict]:
    """Set wiki.enabled and, when enabling, the lifecycle sync flags.

    Returns the list of changed keys ({path, from, to}); every other key of
    the config is preserved as is.
    """
    changes: list[dict] = []
    wiki = config.setdefault("wiki", {})
    if wiki.get("enabled") is not enabled:
        changes.append({"path": "wiki.enabled", "from": wiki.get("enabled"), "to": enabled})
        wiki["enabled"] = enabled
    if enabled:
        events = config.setdefault("lifecycle", {}).setdefault("events", {})
        for event in WIKI_SYNC_EVENTS:
            block = events.setdefault(event, {})
            if block.get("run_wiki_sync") is not True:
                changes.append(
                    {
                        "path": f"lifecycle.events.{event}.run_wiki_sync",
                        "from": block.get("run_wiki_sync"),
                        "to": True,
                    }
                )
                block["run_wiki_sync"] = True
    return changes


def cmd_wiki_config(args, *, emit, sync_wiki=None, log_operation=None) -> None:
    if args.enable == args.disable:
        raise SystemExit("wiki-config needs exactly one of --enable or --disable")
    enabled = bool(args.enable)
    config = load_config()
    changes = apply_wiki_enabled(config, enabled)
    if changes:
        write_config(config)
    result = {
        "config_path": str(CONFIG_PATH),
        "wiki_enabled": enabled,
        "changed": bool(changes),
        "changes": changes,
    }
    if enabled and not getattr(args, "no_sync", False) and sync_wiki is not None:
        sync = sync_wiki()
        result["wiki_sync"] = {
            "written_count": sync.get("written_count", 0),
            "held_back_count": len(sync.get("held_back") or []),
            "skipped_reason": sync.get("skipped_reason"),
        }
    if log_operation is not None and changes:
        from .db import connect as _connect

        log_operation(
            _connect(),
            "wiki_config",
            "enable" if enabled else "disable",
            {"changes": changes},
            summary=f"Wiki {'enabled' if enabled else 'disabled'}: {len(changes)} config change(s)",
        )
    if args.json:
        emit(result, True)
        return
    lines = [f"Wiki {'enabled' if enabled else 'disabled'} ({len(changes)} config change(s))"]
    lines.extend(f"  {c['path']}: {c['from']} -> {c['to']}" for c in changes)
    if "wiki_sync" in result:
        lines.append(f"  initial sync: {result['wiki_sync']['written_count']} page(s) written")
    emit({"__plain__": True, "text": "\n".join(lines)}, False)
