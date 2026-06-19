from __future__ import annotations

import json
import sqlite3

from .config import load_config
from .db import connect
from .paths import KB_ROOT, ensure_dirs


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


def compute_wiki_state(
    wiki_cfg: dict, hard_signals: dict, soft_result: dict, candidate_count: int
) -> str:
    mode = wiki_cfg.get("activation_mode", "manual")

    if mode == "manual":
        # Original behavior: wiki.enabled must be true.
        if not wiki_cfg.get("enabled", False):
            return "off"
    elif mode in ("signal", "profile"):
        # enabled=true acts as an override that bypasses signal checks.
        # enabled=false (or absent) means signals decide eligibility.
        if wiki_cfg.get("enabled", False):
            # Explicit override: skip hard/soft signal checks, go straight
            # to candidate gating.
            page_types = wiki_cfg.get("page_types", [])
            if not page_types:
                return "eligible"
            if candidate_count > 0:
                return "active"
            return "eligible"
        # Fall through: let hard/soft signals decide.
    else:
        # Unknown mode: treat as manual for safety.
        if not wiki_cfg.get("enabled", False):
            return "off"

    if not hard_signals["any_hard_signal"]:
        return "off"
    soft_threshold = wiki_cfg.get("eligibility", {}).get("min_soft_signal_score", 1)
    if soft_result["soft_signal_score"] < soft_threshold:
        return "off"
    page_types = wiki_cfg.get("page_types", [])
    if not page_types:
        return "eligible"
    if candidate_count > 0:
        return "active"
    return "eligible"


def get_wiki_check_result(
    config: dict | None = None,
    conn: sqlite3.Connection | None = None,
    candidate_provider=None,
) -> dict:
    config = config or load_config()
    ensure_dirs(config)
    wiki_cfg = get_wiki_config(config)
    conn = conn or connect()
    hard_signals = compute_wiki_hard_signals(conn, wiki_cfg.get("eligibility", {}))
    soft_result = compute_soft_signals(conn)
    candidate_count = 0
    if candidate_provider is not None:
        candidate_count = len(candidate_provider(conn, config, wiki_cfg))
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
    lines.append(
        "Page types configured: "
        f"{', '.join(result['page_types_configured']) or 'none'}"
    )
    lines.append(f"Wiki dirs exist: {result['wiki_dirs_exist']}")
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
