from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4


CONFIG_REL = Path(".kb-next") / "kb-next.config.json"
DECISION_REL = Path(".kb-next") / "decisions" / "activation-decision.json"
OPERATIONS_REL = Path(".kb-next") / "operations.jsonl"
NOW_REL = Path(".kb-next") / "memory" / "NOW.md"
LLM_MANIFESTS_REL = Path(".kb-next") / "manifests" / "llm"
WIKI_REVIEW_MANIFESTS_REL = Path(".kb-next") / "manifests" / "wiki-draft-review"
PROPOSAL_APPLY_MANIFESTS_REL = Path(".kb-next") / "manifests" / "proposal-apply"
PROPOSALS_REL = Path(".kb-next") / "proposals"
WIKI_DRAFTS_REL = Path(".kb-next") / "wiki" / "drafts"
WIKI_MACHINE_REL = Path(".kb-next") / "wiki" / "machine"
WIKI_HUMAN_REL = Path(".kb-next") / "wiki" / "human"
WIKI_MATERIALIZATION_MIN_CONFIDENCE = 0.8
ADAPTERS_REL = Path(".kb-next") / "adapters"
OBSIDIAN_ADAPTER = "obsidian_static_markdown"
OBSIDIAN_DESIGN_VERSION = "obsidian_static_markdown_design_v1"
OBSIDIAN_DESIGN_NOTES_REL = (
    Path("state")
    / "runs"
    / "WP-KBF.VNEXT-OBSIDIAN-STATIC-MARKDOWN-PILOT"
    / "obsidian_design_notes.md"
)
OBSIDIAN_OFFICIAL_SOURCES = [
    "https://help.obsidian.md/data-storage",
    "https://help.obsidian.md/properties",
    "https://help.obsidian.md/tags",
    "https://help.obsidian.md/Linking%20notes%20and%20files/Internal%20links",
    "https://help.obsidian.md/file-formats",
    "https://help.obsidian.md/embeds",
    "https://help.obsidian.md/symlinks",
    "https://help.obsidian.md/publish/publish",
]

CHOICES = {
    "kb-alone": "kb_alone",
    "kb_alone": "kb_alone",
    "kb-wiki": "kb_wiki",
    "kb_wiki": "kb_wiki",
}

GUIDED_QUESTIONS = [
    {
        "id": "human_documentation",
        "prompt": "Need for human-readable documentation and onboarding",
        "weight": 2,
        "kind": "benefit",
    },
    {
        "id": "auditability",
        "prompt": "Need for audit, review, and narrative traceability",
        "weight": 2,
        "kind": "benefit",
    },
    {
        "id": "history_volume",
        "prompt": "Historical volume and frequency of cross-session restart",
        "weight": 1,
        "kind": "benefit",
    },
    {
        "id": "memory_granularity",
        "prompt": "Need to navigate granular decisions, learnings, definitions, open items, and status",
        "weight": 2,
        "kind": "benefit",
    },
    {
        "id": "multi_agent",
        "prompt": "Multi-agent or multi-platform operation",
        "weight": 1,
        "kind": "benefit",
    },
    {
        "id": "maintenance_capacity",
        "prompt": "Capacity to maintain derived wiki hygiene",
        "weight": 0,
        "kind": "capacity",
    },
]

HISTORICAL_REASONS = [
    "rationale",
    "source",
    "provenance",
    "historical_heuristic",
    "exact_wording",
]

MEMORY_FACETS = ["decisions", "learnings", "definitions", "open-items", "status"]
PROPOSED_ACTIONS = ["new", "update", "supersede", "defer", "answer_only"]
CURATION_FINDINGS = ["duplicate", "conflict", "stale", "missing_provenance", "ambiguous", "ok"]
VALIDATION_STATUSES = ["needs_llm_judgment", "valid", "blocked", "needs_human_review"]
HYGIENE_GROUP_KEYS = [
    "keep_hot",
    "demote_candidate",
    "supersede_or_merge_candidate",
    "resolve_candidate",
    "needs_sponsor",
]
HYGIENE_ACTION_BY_GROUP = {
    "keep_hot": "keep_hot",
    "demote_candidate": "demote_hot",
    "supersede_or_merge_candidate": "supersede",
    "resolve_candidate": "resolve",
    "needs_sponsor": "needs_sponsor",
}
COMPLIANCE_WORK_TYPES = [
    "planning",
    "implementation",
    "review",
    "release",
    "track-b",
    "packaging",
    "operational",
]
SOURCE_LINKAGE_TRACK_B_BLOCKER_ID = "KB-20260525141938-0cd4cc"
TRACK_B_DEFAULT_DENYLIST = [
    "filed-answer",
    "filed-analysis",
    "filed-synthesis",
    "decisao-locked",
    "validated",
    "next-step",
    "source-linkage",
    "track-b-gate",
    "operational-debt",
    "hash-mismatch",
    "quarantined",
    "needs-provenance-repair",
    "reingested-superseded",
    "test",
]
TRACK_B_CANDIDATE_TAG = "track-b-candidate"
TRACK_B_RELEVANT_TAGS = {
    "track-b",
    "track-b-candidate",
    "external-human-wiki",
    "external-wiki",
    "kb-wiki-vnext",
    "obsidian_static_markdown",
    "notion_mcp",
}
SOURCE_QUARANTINE_TAGS = {"hash-mismatch", "quarantined", "needs-provenance-repair"}
SOURCE_ID_RE = re.compile(r"SRC-\d{8}-\d{6}-[0-9a-fA-F]+")
COMPLIANCE_CONTRACT_SCOPE = (
    "development until 100% developed; simple operational use is not blocked "
    "unless it is part of vNext development"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit(payload: Any, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root).resolve()


def kb_next_root(root: Path) -> Path:
    return root / ".kb-next"


def config_path(root: Path) -> Path:
    return root / CONFIG_REL


def decision_path(root: Path) -> Path:
    return root / DECISION_REL


def operations_path(root: Path) -> Path:
    return root / OPERATIONS_REL


def now_path(root: Path) -> Path:
    return root / NOW_REL


def llm_manifests_root(root: Path) -> Path:
    return root / LLM_MANIFESTS_REL


def proposals_root(root: Path) -> Path:
    return root / PROPOSALS_REL


def wiki_drafts_root(root: Path) -> Path:
    return root / WIKI_DRAFTS_REL


def wiki_review_manifests_root(root: Path) -> Path:
    return root / WIKI_REVIEW_MANIFESTS_REL


def proposal_apply_manifests_root(root: Path) -> Path:
    return root / PROPOSAL_APPLY_MANIFESTS_REL


def adapter_root(root: Path, adapter: str) -> Path:
    return root / ADAPTERS_REL / adapter


def obsidian_adapter_root(root: Path) -> Path:
    return adapter_root(root, OBSIDIAN_ADAPTER)


def obsidian_vault_root(root: Path) -> Path:
    return obsidian_adapter_root(root) / "vault"


def wiki_surface_root(root: Path, surface: str) -> Path:
    if surface == "machine":
        return root / WIKI_MACHINE_REL
    if surface == "human":
        return root / WIKI_HUMAN_REL
    raise ValueError(f"unsupported wiki surface: {surface}")


def make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid4().hex[:8]}"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def proposal_allowed_dirs(root: Path) -> tuple[Path, ...]:
    return tuple(
        (proposals_root(root) / name).resolve()
        for name in ("filing", "curation", "semantic-lookup", "wiki-synthesis", "hygiene")
    )


def is_inside_any(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    return any(resolved == root or resolved.is_relative_to(root) for root in roots)


def parse_json_payload(raw: str | None, label: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    payload = raw
    if raw.startswith("@"):
        payload = Path(raw[1:]).read_text(encoding="utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "topic"


def normalize_choice(value: str) -> str:
    key = value.strip().lower()
    if key not in CHOICES:
        raise ValueError(f"Unsupported activation choice: {value}")
    return CHOICES[key]


def normalize_answer_value(value: Any) -> int:
    if isinstance(value, bool):
        return 2 if value else 0
    if isinstance(value, int):
        if value not in (0, 1, 2):
            raise ValueError("numeric answers must be 0, 1, or 2")
        return value
    text = str(value).strip().lower()
    mapping = {
        "none": 0,
        "low": 0,
        "baixo": 0,
        "baixa": 0,
        "no": 0,
        "nao": 0,
        "não": 0,
        "medium": 1,
        "medio": 1,
        "médio": 1,
        "media": 1,
        "média": 1,
        "partial": 1,
        "yes": 2,
        "sim": 2,
        "high": 2,
        "alto": 2,
        "alta": 2,
    }
    if text not in mapping:
        raise ValueError(f"Unsupported guided answer value: {value}")
    return mapping[text]


def parse_guided_answers(raw: str | None) -> dict[str, int]:
    if raw is None:
        if not sys.stdin.isatty():
            raise ValueError("--answers is required for non-interactive guided mode")
        answers: dict[str, int] = {}
        print("Answer each question as low, medium, or high.")
        for question in GUIDED_QUESTIONS:
            value = input(f"{question['prompt']} [{question['id']}]: ")
            answers[question["id"]] = normalize_answer_value(value)
        return answers

    payload = raw
    if raw.startswith("@"):
        payload = Path(raw[1:]).read_text(encoding="utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("--answers must be a JSON object")
    answers = {str(k): normalize_answer_value(v) for k, v in parsed.items()}
    missing = [q["id"] for q in GUIDED_QUESTIONS if q["id"] not in answers]
    if missing:
        raise ValueError(f"missing guided answers: {', '.join(missing)}")
    return answers


def score_guided_answers(answers: dict[str, int]) -> dict[str, Any]:
    benefit_score = 0
    max_benefit_score = 0
    detail: dict[str, dict[str, int]] = {}
    for question in GUIDED_QUESTIONS:
        qid = question["id"]
        value = answers[qid]
        if question["kind"] == "benefit":
            weighted = value * int(question["weight"])
            benefit_score += weighted
            max_benefit_score += 2 * int(question["weight"])
        else:
            weighted = value
        detail[qid] = {"value": value, "weighted": weighted}

    maintenance_capacity = answers["maintenance_capacity"]
    recommended_mode = "kb_wiki" if benefit_score >= 8 and maintenance_capacity >= 1 else "kb_alone"
    return {
        "benefit_score": benefit_score,
        "max_benefit_score": max_benefit_score,
        "maintenance_capacity": maintenance_capacity,
        "recommended_mode": recommended_mode,
        "details": detail,
        "rule": "kb_wiki when benefit_score >= 8 and maintenance_capacity >= 1; otherwise kb_alone",
    }


def default_rationale(mode: str, source: str, score: dict[str, Any] | None = None) -> str:
    if source == "short":
        if mode == "kb_wiki":
            return "Owner selected KB + Wiki through the short activation path."
        return "Owner selected KB alone through the short activation path."
    assert score is not None
    label = "KB + Wiki" if mode == "kb_wiki" else "KB alone"
    return (
        f"Guided deterministic wizard recommended {label}: "
        f"benefit_score={score['benefit_score']}/{score['max_benefit_score']}, "
        f"maintenance_capacity={score['maintenance_capacity']}."
    )


def build_config(root: Path, decision: dict[str, Any]) -> dict[str, Any]:
    mode = decision["sponsor_decision"]
    wiki_enabled = mode == "kb_wiki"
    return {
        "schema_version": 1,
        "runtime": {
            "name": "kb-wiki-vnext",
            "version_line": "kb-wiki-vnext",
            "root": ".kb-next",
        },
        "project": {
            "root": str(root),
        },
        "activation": decision,
        "classic_kb": {
            "root": ".kb",
            "mode": "read_only",
        },
        "wiki": {
            "enabled": wiki_enabled,
            "authority": "derived",
            "surfaces": {
                "machine": wiki_enabled,
                "human": wiki_enabled,
            },
        },
        "session_start": {
            "required": True,
            "default_reads": ["NOW.md"],
            "on_demand_reads": [
                "HOT.md",
                ".kb/memory/INDEX.md",
                "kb_search",
                "wiki_index_when_active",
                "historical_artifacts_with_allowed_reason",
            ],
            "historical_artifact_allowed_reasons": HISTORICAL_REASONS,
        },
        "memory_facets": {
            "canonical_source": "typed_kb_records",
            "facets": MEMORY_FACETS,
            "access_policy": "targeted_lookup",
            "forbid_default_global_preload": True,
        },
        "semantic_curation": {
            "llm_boundary": "external_agent",
            "write_policy": ".kb-next_only",
            "classic_kb_mutation": "forbidden",
            "judgment_inputs": ["--judgment", "--judgment-json"],
            "commands": [
                "semantic-lookup",
                "curation-proposal",
                "semantic-hygiene",
                "filing-proposal",
                "wiki-synthesis-plan",
                "wiki-draft-review",
                "proposal-apply",
            ],
        },
        "track_b": {
            "source_linkage_policy": "strict",
            "first_adapter": "obsidian_static_markdown",
            "blocked_source_ids": [],
            "tag_synthesis_denylist": TRACK_B_DEFAULT_DENYLIST,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_operation(root: Path, event: str, details: dict[str, Any]) -> None:
    op_path = operations_path(root)
    op_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": event,
        "happened_at": now_iso(),
        "details": details,
    }
    with op_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_now(root: Path, config: dict[str, Any]) -> None:
    mode = config["activation"]["sponsor_decision"]
    wiki_enabled = config["wiki"]["enabled"]
    lines = [
        "# KB/Wiki vNext NOW",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Activation mode: `{mode}`",
        f"- Classic KB: `{config['classic_kb']['root']}` (`read_only`)",
        f"- Wiki active: `{str(wiki_enabled).lower()}`",
        "",
        "## Required Default Read",
        "- Read this `NOW.md` only.",
        "",
        "## On Demand",
        "- Use `semantic-lookup` when LLM judgment is available.",
        "- Use `lookup` as deterministic fallback for decisions, learnings, definitions, open items, and status.",
        "- Read classic `.kb/memory/HOT.md` only when the active working set is needed.",
        "- Read classic `.kb/memory/INDEX.md` only when the broad KB map is needed.",
        "- Use the Wiki index only when KB + Wiki is active and page navigation is needed.",
        "- Open historical artifacts only for rationale, source, provenance, historical heuristic, or exact wording.",
    ]
    path = now_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_config_or_fail(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run activation-wizard first")
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_activation_wizard(args: argparse.Namespace) -> int:
    root = project_root(args)
    if args.mode == "short":
        if not args.choice:
            raise ValueError("--choice is required for short mode")
        decision_mode = normalize_choice(args.choice)
        recommended_mode = decision_mode
        score = None
    else:
        answers = parse_guided_answers(args.answers)
        score = score_guided_answers(answers)
        decision_mode = score["recommended_mode"]
        recommended_mode = decision_mode
        if args.answers is None:
            label = "KB + Wiki" if decision_mode == "kb_wiki" else "KB alone"
            confirmed = input(f"Confirm recommended activation mode ({label})? [y/N]: ")
            if confirmed.strip().lower() not in {"y", "yes", "s", "sim"}:
                raise RuntimeError("guided recommendation was not confirmed")

    decision = {
        "mode": decision_mode,
        "source": args.mode,
        "sponsor_decision": decision_mode,
        "recommended_mode": recommended_mode,
        "rationale": args.rationale or default_rationale(decision_mode, args.mode, score),
        "decided_at": now_iso(),
    }
    if score is not None:
        decision["guided_score"] = score

    config = build_config(root, decision)
    kb_next_root(root).mkdir(parents=True, exist_ok=True)
    write_json(config_path(root), config)
    write_json(decision_path(root), decision)
    write_now(root, config)
    append_operation(
        root,
        "activation-wizard",
        {
            "mode": args.mode,
            "sponsor_decision": decision_mode,
            "recommended_mode": recommended_mode,
            "config_path": str(config_path(root)),
            "decision_path": str(decision_path(root)),
        },
    )
    result = {
        "event": "activation-wizard",
        "activation": decision,
        "paths": {
            "config": str(config_path(root)),
            "decision": str(decision_path(root)),
            "operations": str(operations_path(root)),
            "now": str(now_path(root)),
        },
    }
    if args.json:
        emit(result, True)
    else:
        label = "KB + Wiki" if decision_mode == "kb_wiki" else "KB alone"
        emit(f"Activation recorded: {label}\nConfig: {config_path(root)}", False)
    return 0


def cmd_session_start(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    wiki_enabled = bool(config["wiki"]["enabled"])
    paths = {
        "now": str(now_path(root)),
        "classic_hot": str(root / ".kb" / "memory" / "HOT.md"),
        "classic_index": str(root / ".kb" / "memory" / "INDEX.md"),
    }
    if wiki_enabled:
        paths["wiki_index"] = str(root / ".kb-next" / "wiki" / "index.md")
    result = {
        "event": "session-start",
        "generated_at": now_iso(),
        "activation_mode": config["activation"]["sponsor_decision"],
        "classic_kb_mode": config["classic_kb"]["mode"],
        "default_reads": config["session_start"]["default_reads"],
        "required_read_paths": [paths["now"]],
        "on_demand_reads": config["session_start"]["on_demand_reads"],
        "historical_artifact_allowed_reasons": config["session_start"][
            "historical_artifact_allowed_reasons"
        ],
        "paths": paths,
        "actions_run": ["read_kb_next_config", "emit_thin_contract"],
    }
    append_operation(
        root,
        "session-start",
        {
            "activation_mode": result["activation_mode"],
            "default_reads": result["default_reads"],
            "on_demand_reads": result["on_demand_reads"],
        },
    )
    if args.json:
        emit(result, True)
    else:
        lines = [
            "KB/Wiki vNext session-start",
            "",
            f"Activation mode: {result['activation_mode']}",
            f"Required default read: {paths['now']}",
            "On demand: " + ", ".join(result["on_demand_reads"]),
        ]
        emit("\n".join(lines), False)
    return 0


def open_classic_kb_readonly(root: Path) -> sqlite3.Connection:
    db_path = root / ".kb" / "kb.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"classic KB database not found: {db_path}")
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def active_pendencias(root: Path) -> list[dict[str, Any]]:
    try:
        with open_classic_kb_readonly(root) as conn:
            rows = conn.execute(
                """
                SELECT id, title, content, status
                FROM records
                WHERE category = 'PENDENCIA' AND status = 'ATIVO'
                ORDER BY updated_at DESC, created_at DESC, id
                """
            ).fetchall()
    except FileNotFoundError:
        return []
    return [dict(row) for row in rows]


def json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def track_b_policy(root: Path) -> dict[str, Any]:
    try:
        config = load_config_or_fail(root)
    except FileNotFoundError:
        config = {}
    track_b = config.get("track_b", {}) if isinstance(config, dict) else {}
    denylist = track_b.get("tag_synthesis_denylist", TRACK_B_DEFAULT_DENYLIST)
    blocked_source_ids = track_b.get("blocked_source_ids", [])
    return {
        "source_linkage_policy": track_b.get("source_linkage_policy", "strict"),
        "first_adapter": track_b.get("first_adapter", "obsidian_static_markdown"),
        "blocked_source_ids": sorted(str(item) for item in blocked_source_ids),
        "tag_synthesis_denylist": sorted(str(item) for item in denylist),
    }


def fetch_all_sources(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
    ).fetchone()
    if table is None:
        return {}
    rows = fetch_rows(conn, "SELECT * FROM sources", [])
    sources: dict[str, dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        data["tags"] = json_list(row_get(row, "tags_json"))
        data["record_ids"] = json_list(row_get(row, "record_ids_json"))
        sources[data["source_id"]] = data
    return sources


def fetch_active_records(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return fetch_rows(
        conn,
        """
        SELECT * FROM records
        WHERE status = 'ATIVO'
        ORDER BY CASE tier WHEN 'HOT' THEN 0 WHEN 'WARM' THEN 1 ELSE 2 END,
                 updated_at DESC,
                 created_at DESC,
                 id
        """,
        [],
    )


def record_tags(row: sqlite3.Row) -> set[str]:
    return {str(item) for item in json_list(row["tags_json"])}


def record_source_ids(row: sqlite3.Row) -> list[str]:
    ids: list[str] = []
    explicit = row_get(row, "source_id")
    if explicit:
        ids.append(str(explicit))
    for field in ("content", "source"):
        value = row_get(row, field)
        if not value:
            continue
        ids.extend(SOURCE_ID_RE.findall(str(value)))
    return dedupe_strings(ids)


def source_health(root: Path, source: dict[str, Any], blocked_source_ids: set[str]) -> dict[str, Any]:
    source_id = str(source["source_id"])
    tags = {str(item) for item in source.get("tags", [])}
    stored_path_raw = source.get("stored_path")
    stored_path = Path(str(stored_path_raw)) if stored_path_raw else None
    stored_path_exists = bool(stored_path and stored_path.is_file())
    actual_hash = sha256_path(stored_path) if stored_path_exists and stored_path is not None else None
    expected_hash = source.get("content_hash")
    hash_ok = bool(actual_hash and expected_hash and actual_hash == expected_hash)
    quarantined = bool(tags & SOURCE_QUARANTINE_TAGS) or source_id in blocked_source_ids
    return {
        "source_id": source_id,
        "stored_path": str(stored_path) if stored_path is not None else None,
        "stored_path_exists": stored_path_exists,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "hash_ok": hash_ok,
        "quarantined": quarantined,
        "tags": sorted(tags),
    }


def build_source_linkage_audit(root: Path, scope: str) -> dict[str, Any]:
    if scope != "track-b":
        raise ValueError("source-linkage-audit currently supports only --scope track-b")

    policy = track_b_policy(root)
    denylist = set(policy["tag_synthesis_denylist"])
    blocked_source_ids = set(policy["blocked_source_ids"])
    publishable_record_ids: list[str] = []
    blocked_record_ids: list[str] = []
    excluded_record_ids: list[str] = []
    blocked_records: list[dict[str, Any]] = []
    excluded_records: list[dict[str, Any]] = []
    required_actions: list[str] = []

    with open_classic_kb_readonly(root) as conn:
        sources = fetch_all_sources(conn)
        source_health_by_id = {
            source_id: source_health(root, source, blocked_source_ids)
            for source_id, source in sources.items()
        }
        rows = fetch_active_records(conn)

    hash_mismatch_source_ids = sorted(
        source_id
        for source_id, health in source_health_by_id.items()
        if health["stored_path_exists"] and not health["hash_ok"]
    )
    quarantined_source_ids = sorted(
        source_id
        for source_id, health in source_health_by_id.items()
        if health["quarantined"]
    )

    for row in rows:
        tags = record_tags(row)
        is_candidate = TRACK_B_CANDIDATE_TAG in tags
        relevant = bool(tags & TRACK_B_RELEVANT_TAGS)
        denied_tags = sorted(tags & denylist)

        if denied_tags:
            if is_candidate or relevant:
                excluded_record_ids.append(row["id"])
                excluded_records.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "reason": "denylisted_tags",
                        "tags": denied_tags,
                    }
                )
            continue

        if not is_candidate:
            if relevant:
                excluded_record_ids.append(row["id"])
                excluded_records.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "reason": "not_marked_track_b_candidate",
                    }
                )
            continue

        source_ids = record_source_ids(row)
        record_reasons: list[str] = []
        if not source_ids:
            record_reasons.append("missing_source_linkage")
        for source_id in source_ids:
            health = source_health_by_id.get(source_id)
            if health is None:
                record_reasons.append(f"unknown_source_reference:{source_id}")
                continue
            if not health["stored_path_exists"]:
                record_reasons.append(f"missing_source_file:{source_id}")
            if not health["hash_ok"]:
                record_reasons.append(f"source_hash_mismatch:{source_id}")
            if health["quarantined"]:
                record_reasons.append(f"source_quarantined:{source_id}")

        if record_reasons:
            blocked_record_ids.append(row["id"])
            blocked_records.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "source_ids": source_ids,
                    "reasons": record_reasons,
                }
            )
            continue

        publishable_record_ids.append(row["id"])

    if blocked_record_ids:
        required_actions.append("Supersede blocked Track B candidates with clean source linkage or remove track-b-candidate.")
    if hash_mismatch_source_ids:
        required_actions.append("Keep hash-mismatch sources quarantined unless reingested and relinked through canonical KB records.")
    if not publishable_record_ids:
        required_actions.append("No publishable Track B candidates were found; add track-b-candidate only after source linkage is clean.")

    status = "blocked" if blocked_record_ids else "pass"
    return {
        "event": "source-linkage-audit",
        "generated_at": now_iso(),
        "status": status,
        "scope": scope,
        "source_linkage_policy": policy["source_linkage_policy"],
        "first_adapter": policy["first_adapter"],
        "publishable_record_ids": sorted(publishable_record_ids),
        "blocked_record_ids": sorted(blocked_record_ids),
        "excluded_record_ids": sorted(dedupe_strings(excluded_record_ids)),
        "blocked_records": blocked_records,
        "excluded_records": excluded_records,
        "quarantined_source_ids": quarantined_source_ids,
        "hash_mismatch_source_ids": hash_mismatch_source_ids,
        "tag_synthesis_denylist": policy["tag_synthesis_denylist"],
        "required_actions": required_actions,
        "read_only": True,
    }


def cmd_source_linkage_audit(args: argparse.Namespace) -> int:
    root = project_root(args)
    result = build_source_linkage_audit(root, args.scope)
    emit(result, args.json)
    return 0


def infer_compliance_work_type(topic: str | None) -> str:
    if not topic:
        return "unknown"
    text = topic.lower()
    if any(token in text for token in ("track b", "track-b", "external human", "publicacao externa", "publicação externa")):
        return "track-b"
    if any(token in text for token in ("package", "packaging", "plugin", "codex", "claude", "cowork")):
        return "packaging"
    if any(token in text for token in ("release", "gate", "pilot", "piloto", "rollout")):
        return "release"
    if any(token in text for token in ("review", "audit", "red team", "revis")):
        return "review"
    if any(token in text for token in ("implement", "hardening", "refactor", "runtime", "validator", "test")):
        return "implementation"
    if any(token in text for token in ("plan", "planej", "prd", "master plan", "proposal-apply", "semantic-lookup", "wiki-synthesis", "wiki-draft-review")):
        return "planning"
    return "unknown"


def compliance_surfaces(work_type: str) -> list[str]:
    base = [
        "core/versions/kb-wiki-vnext/spec-pack/product-intent-prd.pt-br.md",
        "core/versions/kb-wiki-vnext/spec-pack/README.md",
        "core/versions/kb-wiki-vnext/spec-pack/release-gates.md",
        "core/versions/kb-wiki-vnext/spec-pack/test-matrix.md",
        "core/versions/kb-wiki-vnext/spec-pack/golden-rules-map.md",
        ".kb/memory/NOW.md",
    ]
    extras = {
        "implementation": [
            "core/versions/kb-wiki-vnext/spec-pack/engineer-maintainer-guide.md",
            "core/versions/kb-wiki-vnext/spec-pack/provenance-chain-spec.md",
            "core/versions/kb-wiki-vnext/spec-pack/feature-rationale-register.md",
        ],
        "review": [
            "core/versions/kb-wiki-vnext/spec-pack/operator-runbook.md",
            "state/runs/",
        ],
        "release": [
            "core/versions/kb-wiki-vnext/spec-pack/packaging-distribution-guide.md",
            "core/versions/kb-wiki-vnext/spec-pack/migration-rollout-fallback-guide.md",
            "state/runs/",
        ],
        "track-b": [
            "core/versions/kb-wiki-vnext/spec-pack/provenance-chain-spec.md",
            "core/versions/kb-wiki-vnext/spec-pack/operator-runbook.md",
        ],
        "packaging": [
            "core/versions/kb-wiki-vnext/spec-pack/packaging-distribution-guide.md",
            "plugins/kb-wiki-vnext/AGENTS.md",
            "plugins/kb-wiki-vnext/skills/kb-wiki-vnext/SKILL.md",
        ],
        "operational": [
            ".kb-next/memory/NOW.md",
        ],
    }
    return base + extras.get(work_type, [])


def compliance_required_tests(work_type: str) -> list[str]:
    if work_type == "operational":
        return ["No development test run required for simple operational use."]
    tests = [
        "python tools\\validate_kb_wiki_vnext_spec_pack.py",
        "python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_vnext_compliance tests\\test_kb_wiki_vnext_runtime.py tests\\test_kb_wiki_vnext_semantic_runtime.py tests\\test_kb_wiki_vnext_spec_pack.py tests\\test_build_agent_packages.py -q",
    ]
    if work_type == "packaging":
        tests.append("python -m pytest -p no:cacheprovider tests\\test_build_agent_packages.py -q")
    return tests


def compliance_required_evidence(work_type: str) -> list[str]:
    if work_type == "operational":
        return [
            "Use session-start and targeted lookup; development dossier is not required.",
            "Do not mutate .kb/ or publish .kb/wiki/live.",
        ]
    evidence = [
        "Map the requested work to PRD/master plan, release checkpoint, and test-matrix row.",
        "Record commands and results in a compatible run dossier when implementation, hardening, release, or rollout work occurs.",
        "Record any waiver explicitly with owner approval before bypassing a checkpoint.",
    ]
    if work_type in {"release", "packaging"}:
        evidence.append("Include platform/package evidence and sign-off in the run dossier.")
    if work_type == "track-b":
        evidence.append("Resolve or explicitly waive source-linkage blocker before external human wiki publication.")
    return evidence


def completion_rule() -> list[str]:
    return [
        "Final release dossier signed by Runtime, Provenance, Docs/Spec, QA, Packaging, and Red Team.",
        "Spec-pack validator green.",
        "vNext pytest suite green.",
        "Required pilots completed or owner-waived.",
        f"{SOURCE_LINKAGE_TRACK_B_BLOCKER_ID} resolved or explicitly waived for Track B.",
        "Canonical KB decision records that vNext is 100% developed against PRD/master plan.",
    ]


def build_compliance_preflight(root: Path, work_type_arg: str | None, topic: str | None) -> dict[str, Any]:
    inferred = infer_compliance_work_type(topic)
    work_type = work_type_arg or inferred
    if work_type not in COMPLIANCE_WORK_TYPES:
        work_type = "unknown"

    pendencias = active_pendencias(root)
    blockers: list[dict[str, Any]] = []
    source_linkage_audit: dict[str, Any] | None = None
    if work_type == "track-b":
        blockers = [
            {
                "id": item["id"],
                "title": item["title"],
                "reason": "Track B and external human wiki publication are blocked until canonical source-linkage debt is resolved or owner-waived.",
            }
            for item in pendencias
            if item["id"] == SOURCE_LINKAGE_TRACK_B_BLOCKER_ID
        ]
        source_linkage_audit = build_source_linkage_audit(root, "track-b")
        if not blockers and source_linkage_audit["status"] != "pass":
            blockers.append(
                {
                    "id": "source-linkage-audit",
                    "title": "Track B source-linkage audit failed",
                    "reason": "Track B publication candidates still include missing, quarantined, hash-mismatched, or unknown source linkage.",
                    "blocked_record_ids": source_linkage_audit["blocked_record_ids"],
                }
            )

    if work_type == "unknown":
        status = "needs_evidence"
        next_allowed_action = "Classify the vNext development work type, then rerun compliance-preflight."
    elif blockers:
        status = "blocked"
        next_allowed_action = (
            "Resolve or Sponsor-waive the canonical blocker before development proceeds."
            if any(item["id"] == SOURCE_LINKAGE_TRACK_B_BLOCKER_ID for item in blockers)
            else "Resolve source-linkage audit blockers before Track B development proceeds."
        )
    else:
        status = "pass"
        next_allowed_action = (
            "Operational vNext use may proceed with thin memory."
            if work_type == "operational"
            else "Proceed only with the listed PRD/master-plan mapping, traceability, tests, and evidence."
        )

    development_contract_required = work_type not in {"operational", "unknown"}
    result = {
        "event": "compliance-preflight",
        "generated_at": now_iso(),
        "status": status,
        "work_type": work_type,
        "topic": topic,
        "contract_scope": COMPLIANCE_CONTRACT_SCOPE,
        "development_contract_required": development_contract_required,
        "applicable_gates": (
            ["Development Compliance Contract", "Gate 0 PRD", "Gate 1 Docs/Provenance", "Semantic Memory Gate"]
            if work_type not in {"operational", "unknown"}
            else ["Thin Session Contract"]
        ),
        "canonical_blockers": blockers,
        "required_spec_surfaces": compliance_surfaces(work_type),
        "required_traceability_rows": (
            [
                "Development compliance preflight",
                f"vNext {work_type} traceability",
                "Track B source-linkage blocker" if work_type == "track-b" else "No open canonical blocker for selected work type",
            ]
            if work_type != "operational"
            else ["Operational thin session-start"]
        ),
        "required_tests": compliance_required_tests(work_type),
        "required_evidence": compliance_required_evidence(work_type),
        "mutation_boundaries": [
            ".kb/ is canonical durable memory; canonical mutations must go through .kb/kb.py or approved proposal-apply.",
            ".kb-next/ stores proposals, manifests, drafts, materializations, packages, and operations evidence.",
            "Do not edit .kb/kb.db directly.",
            "Do not publish vNext drafts to .kb/wiki/live.",
        ],
        "completion_rule": completion_rule(),
        "next_allowed_action": next_allowed_action,
        "read_only": True,
    }
    if source_linkage_audit is not None:
        result["source_linkage_audit"] = source_linkage_audit
    return result


def cmd_compliance_preflight(args: argparse.Namespace) -> int:
    root = project_root(args)
    result = build_compliance_preflight(root, args.work_type, args.topic)
    emit(result, args.json)
    return 0


def fetch_sources_by_ids(root: Path, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    with open_classic_kb_readonly(root) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
        ).fetchone()
        if table is None:
            return {}
        placeholders = ", ".join("?" for _ in ids)
        rows = fetch_rows(conn, f"SELECT * FROM sources WHERE source_id IN ({placeholders})", ids)

    sources: dict[str, dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        data["tags"] = json_list(row_get(row, "tags_json"))
        data["record_ids"] = json_list(row_get(row, "record_ids_json"))
        sources[str(data["source_id"])] = data
    return sources


def path_is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def assert_no_reparse_points(path: Path) -> None:
    if not path.exists():
        return
    paths = [path]
    if path.is_dir():
        paths.extend(path.rglob("*"))
    for candidate in paths:
        if path_is_link_or_junction(candidate):
            raise RuntimeError(f"Obsidian vault output must not contain symlinks or junctions: {candidate}")


def reset_derived_vault(root: Path) -> Path:
    adapter = obsidian_adapter_root(root)
    vault = obsidian_vault_root(root)
    adapter_resolved = adapter.resolve()
    vault_resolved = vault.resolve() if vault.exists() else vault.absolute().resolve()
    if not (vault_resolved == adapter_resolved or vault_resolved.is_relative_to(adapter_resolved)):
        raise RuntimeError(f"refusing to replace output outside adapter root: {vault}")
    if vault.exists():
        if path_is_link_or_junction(vault):
            raise RuntimeError(f"refusing to replace symlink or junction output root: {vault}")
        if vault.is_dir():
            shutil.rmtree(vault)
        else:
            vault.unlink()
    for child in ("records", "sources", "manifests"):
        (vault / child).mkdir(parents=True, exist_ok=True)
    return vault


def safe_filename(value: str, fallback: str = "item") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    text = re.sub(r"-{2,}", "-", text).strip(".-")
    text = text[:120].rstrip(".-")
    return text or fallback


def obsidian_safe_tag(value: str) -> str | None:
    text = value.strip().lower().lstrip("#")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9_/-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-/")
    if not text:
        return None
    if not re.search(r"[a-z]", text):
        text = f"tag-{text}"
    return text


def obsidian_tags(row: sqlite3.Row | None = None, extra: list[str] | None = None) -> list[str]:
    raw = [
        "kb-wiki-vnext",
        "track-b",
        OBSIDIAN_ADAPTER,
    ]
    if row is not None:
        raw.extend(str(item) for item in json_list(row_get(row, "tags_json")))
        raw.extend([str(row["category"]), str(row["domain"])])
    raw.extend(extra or [])
    tags = [tag for item in raw if (tag := obsidian_safe_tag(str(item)))]
    return dedupe_strings(tags)


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if value is None:
        return "null"
    return json.dumps(str(value), ensure_ascii=False)


def yaml_frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {yaml_scalar(item)}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def markdown_link(label: str, target: str) -> str:
    safe_label = label.replace("[", "\\[").replace("]", "\\]")
    return f"[{safe_label}]({quote(target, safe='/._-')})"


def source_hash_entries(source_ids: list[str], sources: dict[str, dict[str, Any]]) -> list[str]:
    entries: list[str] = []
    for source_id in source_ids:
        source = sources.get(source_id)
        if not source:
            continue
        content_hash = source.get("content_hash")
        if content_hash:
            entries.append(f"{source_id}={content_hash}")
    return entries


def record_output_filename(row: sqlite3.Row) -> str:
    return f"{safe_filename(str(row['id']), 'record')}.md"


def source_output_filename(source_id: str) -> str:
    return f"{safe_filename(source_id, 'source')}.md"


def obsidian_record_markdown(
    row: sqlite3.Row,
    manifest_id: str,
    generated_at: str,
    audit_status: str,
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> str:
    source_ids = record_source_ids(row)
    linked_sources = [
        markdown_link(source_id, f"../{source_paths[source_id]}")
        for source_id in source_ids
        if source_id in source_paths
    ]
    lines = [
        f"# {row['title']}",
        "",
        "> Derived Track B export. The canonical record remains in `.kb/`; this note is not canonical memory.",
        "",
        "## Record",
        "",
        f"- Record ID: `{row['id']}`",
        f"- Category: `{row['category']}`",
        f"- Domain: `{row['domain']}`",
        f"- Source IDs: {', '.join(linked_sources) if linked_sources else 'none'}",
        "",
        "## Content",
        "",
        str(row["content"]).rstrip(),
        "",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    metadata = {
        "title": row["title"],
        "aliases": dedupe_strings([row["title"], row["id"]]),
        "tags": obsidian_tags(row),
        "manifest_id": manifest_id,
        "record_id": row["id"],
        "record_ids": [row["id"]],
        "source_ids": source_ids,
        "source_hashes": source_hash_entries(source_ids, sources),
        "content_hash": sha256_text(body),
        "confidence": row_get(row, "confidence"),
        "warnings": [],
        "stale_warnings": [],
        "provenance_warnings": [],
        "adapter": OBSIDIAN_ADAPTER,
        "authority": "derived",
        "derived": True,
        "canonical": False,
        "generated_at": generated_at,
        "source_linkage_audit_status": audit_status,
    }
    return yaml_frontmatter(metadata) + body


def obsidian_source_markdown(
    source_id: str,
    source: dict[str, Any],
    manifest_id: str,
    record_ids: list[str],
    generated_at: str,
    audit_status: str,
) -> str:
    lines = [
        f"# {source_id}",
        "",
        "> Derived source metadata for Track B export. Raw source content is not copied into this vault.",
        "",
        "## Source Metadata",
        "",
        f"- Source ID: `{source_id}`",
        f"- Filename: `{source.get('filename') or 'unknown'}`",
        f"- Content hash: `{source.get('content_hash') or 'unknown'}`",
        f"- MIME type: `{source.get('mime_type') or 'unknown'}`",
        "",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    metadata = {
        "title": source_id,
        "aliases": [source_id],
        "tags": obsidian_tags(extra=["source"]),
        "manifest_id": manifest_id,
        "record_ids": record_ids,
        "source_id": source_id,
        "source_ids": [source_id],
        "source_hash": source.get("content_hash"),
        "content_hash": sha256_text(body),
        "confidence": None,
        "warnings": [],
        "stale_warnings": [],
        "provenance_warnings": [],
        "adapter": OBSIDIAN_ADAPTER,
        "authority": "derived",
        "derived": True,
        "canonical": False,
        "generated_at": generated_at,
        "source_linkage_audit_status": audit_status,
    }
    return yaml_frontmatter(metadata) + body


def obsidian_readme_markdown(manifest_id: str, generated_at: str, record_ids: list[str], source_ids: list[str]) -> str:
    lines = [
        "# KB/Wiki vNext Obsidian Static Markdown Export",
        "",
        "This vault is a derived, local Track B pilot surface. It is not canonical memory.",
        "",
        "- Canonical authority remains in `.kb/` typed records.",
        "- This export is generated under `.kb-next/` and can be removed without changing `.kb/`.",
        "- No external adapter, Notion workspace, Obsidian Publish site, or remote publication was used.",
        "- Semantic changes discovered while reading this vault must return through governed `.kb-next/proposals` and approved apply flow.",
        "",
        f"Start at {markdown_link('00_Index.md', '00_Index.md')}.",
        "",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    metadata = {
        "title": "KB/Wiki vNext Obsidian Static Markdown Export",
        "aliases": ["KB/Wiki vNext Obsidian Export"],
        "tags": obsidian_tags(extra=["readme"]),
        "manifest_id": manifest_id,
        "record_ids": record_ids,
        "source_ids": source_ids,
        "content_hash": sha256_text(body),
        "confidence": None,
        "warnings": [],
        "stale_warnings": [],
        "provenance_warnings": [],
        "adapter": OBSIDIAN_ADAPTER,
        "authority": "derived",
        "derived": True,
        "canonical": False,
        "generated_at": generated_at,
    }
    return yaml_frontmatter(metadata) + body


def obsidian_index_markdown(
    manifest_id: str,
    generated_at: str,
    records: list[sqlite3.Row],
    record_paths: dict[str, str],
    source_ids: list[str],
    source_paths: dict[str, str],
) -> str:
    record_ids = [row["id"] for row in records]
    lines = [
        "# KB/Wiki vNext Track B Index",
        "",
        "## Records",
        "",
    ]
    for row in records:
        rid = row["id"]
        lines.append(f"- {markdown_link(row['title'], record_paths[rid])} `{rid}`")
    lines.extend(["", "## Sources", ""])
    for source_id in source_ids:
        if source_id in source_paths:
            lines.append(f"- {markdown_link(source_id, source_paths[source_id])}")
    lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    metadata = {
        "title": "KB/Wiki vNext Track B Index",
        "aliases": ["Track B Index", "Obsidian Static Markdown Index"],
        "tags": obsidian_tags(extra=["index"]),
        "manifest_id": manifest_id,
        "record_ids": record_ids,
        "source_ids": source_ids,
        "content_hash": sha256_text(body),
        "confidence": None,
        "warnings": [],
        "stale_warnings": [],
        "provenance_warnings": [],
        "adapter": OBSIDIAN_ADAPTER,
        "authority": "derived",
        "derived": True,
        "canonical": False,
        "generated_at": generated_at,
    }
    return yaml_frontmatter(metadata) + body


def source_manifest_details(
    root: Path,
    source_ids: list[str],
    sources: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    blocked_source_ids = set(track_b_policy(root)["blocked_source_ids"])
    details: dict[str, dict[str, Any]] = {}
    for source_id in source_ids:
        source = sources.get(source_id)
        if not source:
            details[source_id] = {"source_id": source_id, "available": False}
            continue
        health = source_health(root, source, blocked_source_ids)
        details[source_id] = {
            "source_id": source_id,
            "available": True,
            "filename": source.get("filename"),
            "content_hash": source.get("content_hash"),
            "actual_hash": health["actual_hash"],
            "hash_ok": health["hash_ok"],
            "quarantined": health["quarantined"],
        }
    return details


def blocked_track_b_export_result(
    root: Path,
    adapter: str,
    preflight: dict[str, Any],
    audit: dict[str, Any],
    json_mode: bool,
) -> int:
    reasons: list[str] = []
    if preflight["status"] != "pass":
        reasons.append(f"compliance-preflight:{preflight['status']}")
    if audit["status"] != "pass":
        reasons.append(f"source-linkage-audit:{audit['status']}")
    result = {
        "event": "track-b-export",
        "generated_at": now_iso(),
        "status": "blocked",
        "adapter": adapter,
        "blocked_reasons": reasons,
        "input_preflight_status": preflight["status"],
        "input_audit_status": audit["status"],
        "exported_record_ids": [],
        "paths": {},
    }
    append_operation(
        root,
        "track-b-export",
        {
            "adapter": adapter,
            "status": "blocked",
            "blocked_reasons": reasons,
            "input_preflight_status": preflight["status"],
            "input_audit_status": audit["status"],
        },
    )
    emit(result, json_mode)
    return 0


def cmd_track_b_export(args: argparse.Namespace) -> int:
    root = project_root(args)
    if args.adapter != OBSIDIAN_ADAPTER:
        raise ValueError(f"unsupported Track B adapter: {args.adapter}")

    preflight = build_compliance_preflight(root, "track-b", f"{OBSIDIAN_ADAPTER} export")
    audit = build_source_linkage_audit(root, "track-b")
    if preflight["status"] != "pass" or audit["status"] != "pass":
        return blocked_track_b_export_result(root, args.adapter, preflight, audit, args.json)

    generated_at = now_iso()
    export_manifest_id = make_id("obsidian-export")
    record_ids_to_export = sorted(audit["publishable_record_ids"])
    records_by_id = fetch_records_by_ids(root, record_ids_to_export)
    missing_records = [rid for rid in record_ids_to_export if rid not in records_by_id]
    if missing_records:
        raise RuntimeError(f"source-linkage audit returned unknown records: {', '.join(missing_records)}")

    records = [records_by_id[rid] for rid in record_ids_to_export]
    source_ids = sorted(dedupe_strings([sid for row in records for sid in record_source_ids(row)]))
    sources = fetch_sources_by_ids(root, source_ids)

    vault = reset_derived_vault(root)
    record_paths = {
        row["id"]: (Path("records") / record_output_filename(row)).as_posix()
        for row in records
    }
    source_paths = {
        source_id: (Path("sources") / source_output_filename(source_id)).as_posix()
        for source_id in source_ids
        if source_id in sources
    }
    source_record_ids = {
        source_id: [row["id"] for row in records if source_id in record_source_ids(row)]
        for source_id in source_ids
    }

    generated_files: list[Path] = []
    readme_path = vault / "README.md"
    readme_path.write_text(
        obsidian_readme_markdown(export_manifest_id, generated_at, record_ids_to_export, source_ids),
        encoding="utf-8",
    )
    generated_files.append(readme_path)

    index_path = vault / "00_Index.md"
    index_path.write_text(
        obsidian_index_markdown(export_manifest_id, generated_at, records, record_paths, source_ids, source_paths),
        encoding="utf-8",
    )
    generated_files.append(index_path)

    for row in records:
        output_path = vault / record_paths[row["id"]]
        output_path.write_text(
            obsidian_record_markdown(row, export_manifest_id, generated_at, audit["status"], sources, source_paths),
            encoding="utf-8",
        )
        generated_files.append(output_path)

    for source_id, rel_path in source_paths.items():
        output_path = vault / rel_path
        output_path.write_text(
            obsidian_source_markdown(
                source_id,
                sources[source_id],
                export_manifest_id,
                source_record_ids.get(source_id, []),
                generated_at,
                audit["status"],
            ),
            encoding="utf-8",
        )
        generated_files.append(output_path)

    assert_no_reparse_points(vault)

    root_manifest_path = obsidian_adapter_root(root) / "manifest.json"
    vault_manifest_path = vault / "manifests" / f"{export_manifest_id}.json"
    file_hashes = {
        path_relative_to_root(root, path): sha256_path(path)
        for path in sorted(generated_files, key=lambda item: item.as_posix())
    }
    manifest_payload = {
        "manifest_id": export_manifest_id,
        "manifest_type": "track_b_export",
        "adapter": OBSIDIAN_ADAPTER,
        "generated_at": generated_at,
        "status": "exported",
        "input_preflight_status": preflight["status"],
        "input_audit_status": audit["status"],
        "input_source_linkage_audit": audit,
        "exported_record_ids": record_ids_to_export,
        "excluded_record_ids": audit["excluded_record_ids"],
        "blocked_record_ids": audit["blocked_record_ids"],
        "source_ids": source_ids,
        "source_details": source_manifest_details(root, source_ids, sources),
        "quarantined_source_ids": audit["quarantined_source_ids"],
        "hash_mismatch_source_ids": audit["hash_mismatch_source_ids"],
        "output_paths": {
            "adapter_root": path_relative_to_root(root, obsidian_adapter_root(root)),
            "vault": path_relative_to_root(root, vault),
            "readme": path_relative_to_root(root, readme_path),
            "index": path_relative_to_root(root, index_path),
            "records": {
                rid: path_relative_to_root(root, vault / rel_path)
                for rid, rel_path in record_paths.items()
            },
            "sources": {
                source_id: path_relative_to_root(root, vault / rel_path)
                for source_id, rel_path in source_paths.items()
            },
            "manifest": path_relative_to_root(root, root_manifest_path),
            "vault_manifest": path_relative_to_root(root, vault_manifest_path),
        },
        "file_hashes": file_hashes,
        "obsidian_design_decisions": {
            "version": OBSIDIAN_DESIGN_VERSION,
            "design_notes_path": OBSIDIAN_DESIGN_NOTES_REL.as_posix(),
            "official_sources": OBSIDIAN_OFFICIAL_SOURCES,
            "vault_local_self_contained": True,
            "markdown_only": True,
            "link_format": "markdown",
            "frontmatter_format": "yaml",
            "uses_tags_property": True,
            "uses_aliases_property": True,
            "uses_deprecated_properties": False,
            "uses_symlinks_or_junctions": False,
            "uses_community_plugins": False,
            "uses_obsidian_publish": False,
        },
        "classic_kb_mutation": "forbidden",
        "classic_wiki_live_publish": False,
        "external_adapter_called": False,
        "derived": True,
        "canonical": False,
    }
    write_json(root_manifest_path, manifest_payload)
    write_json(vault_manifest_path, manifest_payload)

    manifest_hash = sha256_path(root_manifest_path)
    append_operation(
        root,
        "track-b-export",
        {
            "adapter": OBSIDIAN_ADAPTER,
            "status": "exported",
            "exported_record_ids": record_ids_to_export,
            "source_ids": source_ids,
            "manifest_path": str(root_manifest_path),
            "vault_root": str(vault),
            "external_adapter_called": False,
            "classic_kb_mutation": "forbidden",
            "classic_wiki_live_publish": False,
        },
    )

    result = {
        "event": "track-b-export",
        "generated_at": now_iso(),
        "status": "exported",
        "adapter": OBSIDIAN_ADAPTER,
        "exported_record_ids": record_ids_to_export,
        "source_ids": source_ids,
        "manifest_sha256": manifest_hash,
        "paths": {
            "manifest": str(root_manifest_path),
            "vault_manifest": str(vault_manifest_path),
            "vault": str(vault),
            "index": str(index_path),
            "readme": str(readme_path),
        },
        "external_adapter_called": False,
        "classic_kb_mutation": "forbidden",
        "classic_wiki_live_publish": False,
    }
    emit(result, args.json)
    return 0


def sql_like(value: str) -> str:
    return f"%{value}%"


def build_lookup_sql(facet: str, query: str | None) -> tuple[str, list[Any]]:
    clauses = ["status = 'ATIVO'"]
    params: list[Any] = []
    if facet == "decisions":
        clauses.append("category = 'DECISAO'")
    elif facet == "learnings":
        clauses.append("category = 'APRENDIZADO'")
    elif facet == "open-items":
        clauses.append("category = 'PENDENCIA'")
    elif facet == "definitions":
        if query:
            like = sql_like(query)
            clauses.append(
                "(title LIKE ? OR content LIKE ? OR tags_json LIKE '%definition%' OR "
                "tags_json LIKE '%definitions%' OR tags_json LIKE '%glossary%' OR "
                "tags_json LIKE '%glossario%' OR tags_json LIKE '%definicao%' OR "
                "tags_json LIKE '%definição%')"
            )
            params.extend([like, like])
        else:
            clauses.append(
                "(tags_json LIKE '%definition%' OR tags_json LIKE '%definitions%' OR "
                "tags_json LIKE '%glossary%' OR tags_json LIKE '%glossario%' OR "
                "tags_json LIKE '%definicao%' OR tags_json LIKE '%definição%')"
            )
    elif facet == "status":
        clauses.append("category IN ('DECISAO', 'FATO', 'APRENDIZADO', 'PENDENCIA')")
    else:
        raise ValueError(f"unsupported facet: {facet}")

    if query and facet != "definitions":
        like = sql_like(query)
        clauses.append("(title LIKE ? OR content LIKE ? OR tags_json LIKE ?)")
        params.extend([like, like, like])

    sql = (
        "SELECT * FROM records WHERE "
        + " AND ".join(clauses)
        + " ORDER BY CASE tier WHEN 'HOT' THEN 0 WHEN 'WARM' THEN 1 ELSE 2 END, updated_at DESC LIMIT ?"
    )
    return sql, params


def excerpt(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 4].rstrip() + " ..."


def row_keys(row: sqlite3.Row) -> set[str]:
    return set(row.keys())


def row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    if key not in row_keys(row):
        return default
    return row[key]


def row_to_lookup_result(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "domain": row["domain"],
        "title": row["title"],
        "tier": row["tier"],
        "excerpt": excerpt(row["content"]),
        "provenance": {
            "record_id": row["id"],
            "source": row["source"],
            "source_id": row_get(row, "source_id"),
        },
    }


def row_to_candidate(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "domain": row["domain"],
        "title": row["title"],
        "tier": row["tier"],
        "confidence": row_get(row, "confidence"),
        "excerpt": excerpt(row["content"]),
        "provenance": {
            "record_id": row["id"],
            "source": row["source"],
            "source_id": row_get(row, "source_id"),
        },
    }


def row_to_supporting_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "domain": row["domain"],
        "title": row["title"],
        "status": row["status"],
        "tier": row["tier"],
        "confidence": row_get(row, "confidence"),
        "source": row["source"],
        "source_id": row_get(row, "source_id"),
        "replacement_id": row_get(row, "replacement_id"),
        "review_after": row_get(row, "review_after"),
        "valid_until": row_get(row, "valid_until"),
    }


def facet_base_clause(facet: str) -> str:
    if facet == "decisions":
        return "category = 'DECISAO'"
    if facet == "learnings":
        return "category = 'APRENDIZADO'"
    if facet == "open-items":
        return "category = 'PENDENCIA'"
    if facet == "definitions":
        return (
            "(tags_json LIKE '%definition%' OR tags_json LIKE '%definitions%' OR "
            "tags_json LIKE '%glossary%' OR tags_json LIKE '%glossario%' OR "
            "tags_json LIKE '%definicao%' OR tags_json LIKE '%definição%' OR "
            "title LIKE '%Definition:%' OR title LIKE '%Definição:%')"
        )
    if facet == "status":
        return "category IN ('DECISAO', 'FATO', 'APRENDIZADO', 'PENDENCIA')"
    raise ValueError(f"unsupported facet: {facet}")


def order_clause() -> str:
    return "ORDER BY CASE tier WHEN 'HOT' THEN 0 WHEN 'WARM' THEN 1 ELSE 2 END, updated_at DESC"


def fetch_rows(conn: sqlite3.Connection, sql: str, params: list[Any]) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def fetch_records_by_ids(root: Path, ids: list[str]) -> dict[str, sqlite3.Row]:
    if not ids:
        return {}
    placeholders = ", ".join("?" for _ in ids)
    conn = open_classic_kb_readonly(root)
    try:
        rows = fetch_rows(conn, f"SELECT * FROM records WHERE id IN ({placeholders})", ids)
        return {row["id"]: row for row in rows}
    finally:
        conn.close()


def source_ids_exist(root: Path, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    conn = open_classic_kb_readonly(root)
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
        ).fetchone()
        if table is None:
            return set()
        placeholders = ", ".join("?" for _ in ids)
        rows = fetch_rows(conn, f"SELECT source_id FROM sources WHERE source_id IN ({placeholders})", ids)
        return {row["source_id"] for row in rows}
    finally:
        conn.close()


def fetch_candidate_rows(
    conn: sqlite3.Connection,
    facet: str,
    query: str | None,
    limit: int,
    domain: str | None = None,
) -> list[sqlite3.Row]:
    base = ["status = 'ATIVO'", facet_base_clause(facet)]
    params: list[Any] = []
    if domain:
        base.append("domain = ?")
        params.append(domain)
    rows: list[sqlite3.Row] = []
    seen: set[str] = set()

    if query:
        like = sql_like(query)
        lexical = base + ["(title LIKE ? OR content LIKE ? OR tags_json LIKE ? OR source LIKE ? OR domain LIKE ?)"]
        lexical_params = params + [like, like, like, like, like]
        sql = f"SELECT * FROM records WHERE {' AND '.join(lexical)} {order_clause()} LIMIT ?"
        rows = fetch_rows(conn, sql, lexical_params + [limit])
        seen = {row["id"] for row in rows}

    if len(rows) < limit:
        remaining = limit - len(rows)
        sql = f"SELECT * FROM records WHERE {' AND '.join(base)} {order_clause()} LIMIT ?"
        for row in fetch_rows(conn, sql, params + [limit + len(seen)]):
            if row["id"] in seen:
                continue
            rows.append(row)
            seen.add(row["id"])
            remaining -= 1
            if remaining <= 0:
                break
    return rows


def judgment_arg(args: argparse.Namespace) -> dict[str, Any] | None:
    raw = getattr(args, "judgment_json", None) or getattr(args, "judgment", None)
    return parse_json_payload(raw, "judgment")


def judgment_source_arg(args: argparse.Namespace) -> str | None:
    if getattr(args, "judgment_json", None) is not None:
        return "--judgment-json"
    raw = getattr(args, "judgment", None)
    if raw is None:
        return None
    if raw.startswith("@"):
        return f"--judgment @{Path(raw[1:]).resolve()}"
    return "--judgment inline-json"


def record_ids(records: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in records}


def validate_record_references(ids: list[Any], candidates: list[dict[str, Any]], field: str) -> list[str]:
    allowed = record_ids(candidates)
    normalized: list[str] = []
    for item in ids:
        if isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
        else:
            rid = item
        if rid is None:
            normalized.append(f"{field}:missing_record_id")
            continue
        normalized.append(str(rid))
    return [rid for rid in normalized if rid not in allowed]


def normalize_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return bool(value.get("needs_disambiguation") or value.get("ambiguous") or value.get("value"))
    if isinstance(value, list):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "yes", "sim", "1", "ambiguous"}


def build_llm_task(task_type: str, instruction: str, expected_fields: list[str]) -> dict[str, Any]:
    return {
        "task_type": task_type,
        "llm_boundary": "external_agent",
        "instruction": instruction,
        "expected_judgment_fields": expected_fields,
        "write_policy": ".kb-next_only",
        "classic_kb_mutation": "forbidden",
    }


def write_llm_manifest(
    root: Path,
    task_type: str,
    context: dict[str, Any],
    candidates: list[dict[str, Any]],
    judgment: dict[str, Any] | None,
    validation_status: str,
    proposed_action: str,
    warnings: list[str],
    judgment_source: str | None = None,
) -> tuple[str, Path, dict[str, Any]]:
    manifest_id = make_id("llm")
    manifest = {
        "manifest_id": manifest_id,
        "task_type": task_type,
        "created_at": now_iso(),
        "actor": "external_agent_or_operator",
        "runtime_version": "kb-wiki-vnext",
        "context": context,
        "input_records": candidates,
        "input_sources": [],
        "input_wiki_pages": [],
        "historical_artifacts_opened": [],
        "prompt_or_template": "kb-wiki-vnext-semantic-curation-v1",
        "judgment_source": judgment_source,
        "judgment": judgment,
        "judgment_hash": sha256_text(canonical_json(judgment)) if judgment is not None else None,
        "resulting_proposals": [],
        "generated_drafts": {},
        "generated_rationale": (judgment or {}).get("rationale"),
        "confidence": (judgment or {}).get("confidence"),
        "uncertainty_notes": (judgment or {}).get("uncertainty_notes"),
        "risk": (judgment or {}).get("risk"),
        "proposed_action": proposed_action,
        "provenance_pointers": (judgment or {}).get("provenance", []),
        "validation_status": validation_status,
        "warnings": warnings,
    }
    path = llm_manifests_root(root) / f"{manifest_id}.json"
    write_json(path, manifest)
    return manifest_id, path, manifest


def register_manifest_proposal(root: Path, manifest_id: str, proposal_path: Path, kind: str, payload: dict[str, Any]) -> None:
    manifest_path = llm_manifests_root(root) / f"{manifest_id}.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = {
        "proposal_id": payload.get("proposal_id"),
        "proposal_kind": kind,
        "proposal_path": path_relative_to_root(root, proposal_path),
        "proposal_hash": sha256_text(canonical_json(payload)),
    }
    proposals = [
        item
        for item in list_from_payload(manifest.get("resulting_proposals"))
        if isinstance(item, dict) and item.get("proposal_id") != entry["proposal_id"]
    ]
    proposals.append(entry)
    manifest["resulting_proposals"] = proposals
    write_json(manifest_path, manifest)


def register_manifest_drafts(root: Path, manifest_id: str, draft_paths: dict[str, str]) -> None:
    manifest_path = llm_manifests_root(root) / f"{manifest_id}.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated: dict[str, dict[str, str]] = {}
    for surface, raw_path in draft_paths.items():
        path = Path(raw_path)
        generated[surface] = {
            "path": path_relative_to_root(root, path),
            "hash": sha256_path(path),
        }
    manifest["generated_drafts"] = generated
    write_json(manifest_path, manifest)


def write_proposal(root: Path, kind: str, payload: dict[str, Any]) -> tuple[str, Path]:
    proposal_id = make_id(kind.replace("_", "-"))
    payload = {"proposal_id": proposal_id, **payload}
    path = proposals_root(root) / kind / f"{proposal_id}.json"
    write_json(path, payload)
    manifest_id = payload.get("manifest_id")
    if manifest_id:
        register_manifest_proposal(root, str(manifest_id), path, kind, payload)
    return proposal_id, path


def validation_from_judgment(
    judgment: dict[str, Any] | None,
    *,
    warnings: list[str] | None = None,
) -> str:
    if judgment is None:
        return "needs_llm_judgment"
    warnings = warnings or []
    explicit = judgment.get("validation_status")
    if explicit in VALIDATION_STATUSES:
        return explicit
    if "conflict" in warnings or "missing_provenance" in warnings:
        return "blocked"
    if "ambiguous" in warnings or "duplicate" in warnings or "stale" in warnings:
        return "needs_human_review"
    return "valid"


def cmd_lookup(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    conn = open_classic_kb_readonly(root)
    sql, params = build_lookup_sql(args.facet, args.query)
    rows = conn.execute(sql, params + [args.limit]).fetchall()
    result = {
        "event": "lookup",
        "generated_at": now_iso(),
        "facet": args.facet,
        "query": args.query,
        "access_policy": config["memory_facets"]["access_policy"],
        "default_global_preload": False,
        "classic_kb_mode": config["classic_kb"]["mode"],
        "results": [row_to_lookup_result(row) for row in rows],
    }
    append_operation(
        root,
        "lookup",
        {
            "facet": args.facet,
            "query": args.query,
            "result_count": len(rows),
            "classic_kb_mode": config["classic_kb"]["mode"],
        },
    )
    if args.json:
        emit(result, True)
    else:
        lines = [f"Lookup: {args.facet}", ""]
        for item in result["results"]:
            lines.append(f"- [{item['id']}] {item['title']}")
        emit("\n".join(lines), False)
    return 0


def semantic_candidates(root: Path, facet: str, query: str | None, limit: int, domain: str | None = None) -> list[dict[str, Any]]:
    conn = open_classic_kb_readonly(root)
    try:
        rows = fetch_candidate_rows(conn, facet, query, limit, domain=domain)
        return [row_to_candidate(row) for row in rows]
    finally:
        conn.close()


def build_ranked_results(judgment: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    candidate_by_id = {item["id"]: item for item in candidates}
    warnings: list[str] = []
    ranked_input = judgment.get("ranked_results") or judgment.get("results")
    if ranked_input is None and "ranked_record_ids" in judgment:
        ranked_input = [{"record_id": rid} for rid in judgment["ranked_record_ids"]]
    ranked_input = ranked_input or []
    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(ranked_input, start=1):
        if isinstance(item, str):
            rid = item
            entry = {"record_id": rid}
        elif isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
            entry = dict(item)
        else:
            continue
        if rid not in candidate_by_id:
            warnings.append(f"unknown_record_reference:{rid}")
            continue
        ranked.append(
            {
                "rank": entry.get("rank", index),
                "record": candidate_by_id[rid],
                "confidence": entry.get("confidence", judgment.get("confidence")),
                "rationale": entry.get("rationale", judgment.get("rationale")),
            }
        )
    return ranked, warnings


def cmd_semantic_lookup(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    candidates = semantic_candidates(root, args.facet, args.query, args.limit)
    judgment = judgment_arg(args)
    warnings: list[str] = []
    ranked_results: list[dict[str, Any]] = []
    ambiguity = None
    conflicts = []
    provenance_warnings = []
    proposed_action = "answer_only"

    if judgment is not None:
        ranked_results, ranking_warnings = build_ranked_results(judgment, candidates)
        warnings.extend(ranking_warnings)
        ambiguity = judgment.get("ambiguity")
        conflicts = judgment.get("conflicts", []) or []
        provenance_warnings = judgment.get("provenance_warnings", []) or []
        if normalize_boolish(ambiguity):
            warnings.append("ambiguous")
        if conflicts:
            warnings.append("conflict")
        if provenance_warnings:
            warnings.append("missing_provenance")

    validation_status = validation_from_judgment(judgment, warnings=warnings)
    status = "needs_llm_judgment" if judgment is None else validation_status
    if judgment is not None and normalize_boolish(ambiguity):
        status = "needs_disambiguation"
    if judgment is not None and conflicts:
        status = "blocked"
        validation_status = "blocked"

    context = {
        "query": args.query,
        "facet": args.facet,
        "command": "semantic-lookup",
        "classic_kb_mode": config["classic_kb"]["mode"],
    }
    manifest_id, manifest_path, _manifest = write_llm_manifest(
        root,
        "semantic_lookup",
        context,
        candidates,
        judgment,
        validation_status,
        proposed_action,
        warnings,
        judgment_source_arg(args),
    )
    proposal_payload = {
        "kind": "semantic-lookup",
        "created_at": now_iso(),
        "manifest_id": manifest_id,
        "query": args.query,
        "facet": args.facet,
        "candidate_records": candidates,
        "ranked_results": ranked_results,
        "confidence": (judgment or {}).get("confidence"),
        "ambiguity": ambiguity,
        "conflicts": conflicts,
        "provenance_warnings": provenance_warnings,
        "validation_status": validation_status,
        "status": status,
        "warnings": warnings,
    }
    proposal_id, proposal_path = write_proposal(root, "semantic-lookup", proposal_payload)
    result = {
        "event": "semantic-lookup",
        "generated_at": now_iso(),
        "status": status,
        "validation_status": validation_status,
        "query": args.query,
        "facet": args.facet,
        "candidate_records": candidates,
        "llm_task": build_llm_task(
            "semantic_lookup",
            "Rerank candidate KB records semantically, detect ambiguity/conflicts, and return provenance-backed confidence.",
            ["ranked_results", "confidence", "rationale", "ambiguity", "conflicts", "provenance_warnings"],
        ),
        "ranked_results": ranked_results,
        "confidence": (judgment or {}).get("confidence"),
        "ambiguity": ambiguity,
        "conflicts": conflicts,
        "provenance_warnings": provenance_warnings,
        "manifest_id": manifest_id,
        "proposal_id": proposal_id,
        "paths": {"manifest": str(manifest_path), "proposal": str(proposal_path)},
    }
    append_operation(
        root,
        "semantic-lookup",
        {
            "query": args.query,
            "facet": args.facet,
            "candidate_count": len(candidates),
            "status": status,
            "manifest_id": manifest_id,
            "proposal_id": proposal_id,
        },
    )
    emit(result, args.json)
    return 0


def validate_curation_judgment(judgment: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    action = judgment.get("action") or judgment.get("proposed_action")
    if action not in PROPOSED_ACTIONS:
        warnings.append("invalid_action")
    findings = judgment.get("findings", []) or []
    if isinstance(findings, str):
        findings = [findings]
    for finding in findings:
        if finding not in CURATION_FINDINGS:
            warnings.append(f"invalid_finding:{finding}")
        elif finding != "ok":
            warnings.append(finding)
    if action == "update" and (judgment.get("semantic_change") or judgment.get("change_type") == "semantic"):
        warnings.append("semantic_update_requires_supersede")
        return "blocked", warnings
    unknown = validate_record_references(judgment.get("record_ids", []) or [], candidates, "record_ids")
    warnings.extend([f"unknown_record_reference:{rid}" for rid in unknown])
    if "conflict" in warnings or "missing_provenance" in warnings or "invalid_action" in warnings:
        return "blocked", warnings
    if any(item in warnings for item in ("duplicate", "stale", "ambiguous")):
        return "needs_human_review", warnings
    return "valid", warnings


def cmd_curation_proposal(args: argparse.Namespace) -> int:
    root = project_root(args)
    load_config_or_fail(root)
    candidates = semantic_candidates(root, args.facet, args.query, args.limit)
    judgment = judgment_arg(args)
    if judgment is None:
        validation_status = "needs_llm_judgment"
        warnings: list[str] = []
    else:
        validation_status, warnings = validate_curation_judgment(judgment, candidates)
    action = (judgment or {}).get("action") or (judgment or {}).get("proposed_action") or "defer"
    context = {
        "query": args.query,
        "facet": args.facet,
        "command": "curation-proposal",
    }
    manifest_id, manifest_path, _manifest = write_llm_manifest(
        root,
        "curation_proposal",
        context,
        candidates,
        judgment,
        validation_status,
        action,
        warnings,
        judgment_source_arg(args),
    )
    proposal_payload = {
        "kind": "curation-proposal",
        "created_at": now_iso(),
        "manifest_id": manifest_id,
        "query": args.query,
        "facet": args.facet,
        "candidate_records": candidates,
        "action": action,
        "findings": (judgment or {}).get("findings", []),
        "rationale": (judgment or {}).get("rationale"),
        "confidence": (judgment or {}).get("confidence"),
        "risk": (judgment or {}).get("risk"),
        "provenance": (judgment or {}).get("provenance", []),
        "record_draft": (judgment or {}).get("record_draft"),
        "validation_status": validation_status,
        "warnings": warnings,
    }
    proposal_id, proposal_path = write_proposal(root, "curation", proposal_payload)
    result = {
        "event": "curation-proposal",
        "generated_at": now_iso(),
        "status": validation_status,
        **proposal_payload,
        "proposal_id": proposal_id,
        "paths": {"manifest": str(manifest_path), "proposal": str(proposal_path)},
        "llm_task": build_llm_task(
            "curation_proposal",
            "Review candidate records for duplicate, conflict, stale, missing provenance, ambiguity, or ok findings.",
            ["action", "findings", "rationale", "confidence", "risk", "provenance"],
        ),
    }
    append_operation(
        root,
        "curation-proposal",
        {
            "query": args.query,
            "facet": args.facet,
            "action": action,
            "status": validation_status,
            "manifest_id": manifest_id,
            "proposal_id": proposal_id,
        },
    )
    emit(result, args.json)
    return 0


def active_hygiene_records(root: Path, limit: int) -> list[dict[str, Any]]:
    conn = open_classic_kb_readonly(root)
    try:
        rows = fetch_rows(
            conn,
            f"SELECT * FROM records WHERE status = 'ATIVO' {order_clause()} LIMIT ?",
            [limit],
        )
        return [row_to_hygiene_record(row) for row in rows]
    finally:
        conn.close()


def row_to_hygiene_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "domain": row["domain"],
        "title": row["title"],
        "status": row["status"],
        "tier": row["tier"],
        "confidence": row_get(row, "confidence"),
        "review_after": row_get(row, "review_after"),
        "valid_until": row_get(row, "valid_until"),
        "source": row["source"],
        "source_id": row_get(row, "source_id"),
        "excerpt": excerpt(row["content"]),
        "provenance": {
            "record_id": row["id"],
            "source": row["source"],
            "source_id": row_get(row, "source_id"),
        },
    }


def classic_hot_limit(root: Path) -> int:
    try:
        return int(load_classic_config(root).get("hot_session_limit", 10))
    except (TypeError, ValueError):
        return 10


def empty_hygiene_groups() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in HYGIENE_GROUP_KEYS}


def build_mechanical_hygiene_groups(root: Path, records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    today = datetime.now(timezone.utc).date().isoformat()
    hot_limit = classic_hot_limit(root)
    groups = empty_hygiene_groups()
    hot_records = [record for record in records if record["tier"] == "HOT"]
    demote_ids: set[str] = set()

    for record in hot_records:
        if record.get("review_after") and str(record["review_after"]) < today:
            demote_ids.add(record["id"])
            groups["demote_candidate"].append(
                {
                    "record_id": record["id"],
                    "reason": "stale_hot_review_after_elapsed",
                    "rationale": "HOT review date has elapsed.",
                }
            )

    overflow_needed = max(0, len(hot_records) - hot_limit)
    for record in sorted(
        hot_records,
        key=lambda item: (
            str(item.get("review_after") or "9999-12-31"),
            float(item.get("confidence") or 0.0),
            item["id"],
        ),
    ):
        if overflow_needed <= 0:
            break
        if record["id"] in demote_ids:
            continue
        demote_ids.add(record["id"])
        overflow_needed -= 1
        groups["demote_candidate"].append(
            {
                "record_id": record["id"],
                "reason": "hot_over_limit",
                "rationale": "HOT count exceeds the configured session budget.",
            }
        )

    for record in hot_records:
        if record["id"] not in demote_ids:
            groups["keep_hot"].append(
                {
                    "record_id": record["id"],
                    "reason": "within_hot_budget",
                    "rationale": "Record remains inside the mechanically selected HOT budget.",
                }
            )

    title_groups: dict[tuple[str, str, str], list[str]] = {}
    for record in records:
        key = (record["category"], record["domain"], record["title"].strip().lower())
        title_groups.setdefault(key, []).append(record["id"])
    for (category, domain, title_key), record_ids in sorted(title_groups.items()):
        if len(record_ids) < 2:
            continue
        groups["supersede_or_merge_candidate"].append(
            {
                "record_ids": record_ids,
                "category": category,
                "domain": domain,
                "title_key": title_key,
                "reason": "duplicate_active_title",
                "rationale": "Multiple active records share the same title.",
            }
        )

    for record in records:
        if record["category"] == "PENDENCIA" and record.get("review_after") and str(record["review_after"]) < today:
            groups["resolve_candidate"].append(
                {
                    "record_id": record["id"],
                    "reason": "pending_review_after_elapsed",
                    "rationale": "Open item review date has elapsed.",
                }
            )
        if record["category"] == "PREMISSA" and record.get("valid_until") and str(record["valid_until"]) < today:
            groups["needs_sponsor"].append(
                {
                    "record_id": record["id"],
                    "reason": "expired_premise",
                    "rationale": "Expired premise requires owner review.",
                }
            )

    return groups


def normalize_hygiene_judgment_groups(
    judgment: dict[str, Any] | None,
    records: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    groups = empty_hygiene_groups()
    warnings: list[str] = []
    if judgment is None:
        return groups, warnings
    known_ids = {record["id"] for record in records}
    raw_groups = judgment.get("groups") or {}
    if not isinstance(raw_groups, dict):
        return groups, ["invalid_groups"]
    for group_name, raw_items in raw_groups.items():
        if group_name not in groups:
            warnings.append(f"invalid_group:{group_name}")
            continue
        for item in list_from_payload(raw_items):
            if isinstance(item, str):
                entry = {"record_id": item}
            elif isinstance(item, dict):
                entry = dict(item)
            else:
                warnings.append(f"invalid_group_item:{group_name}")
                continue
            record_id = entry.get("record_id") or entry.get("id")
            if not record_id:
                warnings.append(f"missing_record_id:{group_name}")
                continue
            entry["record_id"] = str(record_id)
            if entry["record_id"] not in known_ids:
                warnings.append(f"unknown_record_reference:{entry['record_id']}")
            groups[group_name].append(entry)
    return groups, warnings


def hygiene_validation_status(judgment: dict[str, Any] | None, warnings: list[str]) -> str:
    if judgment is None:
        return "needs_llm_judgment"
    explicit = judgment.get("validation_status")
    if explicit in VALIDATION_STATUSES:
        return explicit
    if any(
        warning.startswith(("invalid_", "unknown_", "missing_record_id"))
        or warning in {"conflict", "missing_provenance"}
        for warning in warnings
    ):
        return "blocked"
    if judgment.get("conflicts"):
        return "blocked"
    return "valid"


def hygiene_proposal_payload(
    *,
    manifest_id: str,
    group_name: str,
    item: dict[str, Any],
    record: dict[str, Any],
    judgment: dict[str, Any],
    validation_status: str,
    warnings: list[str],
) -> dict[str, Any]:
    action = str(item.get("action") or HYGIENE_ACTION_BY_GROUP[group_name])
    confidence = item.get("confidence", judgment.get("confidence"))
    provenance = item.get("provenance", judgment.get("provenance", []))
    rationale = item.get("rationale") or judgment.get("rationale")
    return {
        "kind": "semantic-hygiene",
        "created_at": now_iso(),
        "manifest_id": manifest_id,
        "group": group_name,
        "action": action,
        "target_record_id": item["record_id"],
        "target_record": record,
        "rationale": rationale,
        "confidence": confidence,
        "risk": item.get("risk", judgment.get("risk")),
        "provenance": provenance,
        "record_draft": item.get("record_draft"),
        "duplicate_candidates": item.get("duplicate_candidates", []),
        "resolution_notes": item.get("resolution_notes") or item.get("notes") or rationale,
        "tier_reason": item.get("tier_reason") or rationale,
        "validation_status": validation_status,
        "warnings": warnings,
    }


def cmd_semantic_hygiene(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    records = active_hygiene_records(root, args.limit)
    candidates_by_id = {record["id"]: record for record in records}
    mechanical_groups = build_mechanical_hygiene_groups(root, records)
    judgment = judgment_arg(args)
    judgment_groups, warnings = normalize_hygiene_judgment_groups(judgment, records)
    if judgment is not None and judgment.get("conflicts"):
        warnings.append("conflict")
    if judgment is not None and not judgment.get("provenance"):
        warnings.append("missing_provenance")
    validation_status = hygiene_validation_status(judgment, warnings)
    status = validation_status
    proposal_ids: list[str] = []
    proposal_paths: list[str] = []
    manifest_id = None
    manifest_path = None

    context = {
        "command": "semantic-hygiene",
        "scope": args.scope,
        "classic_kb_mode": config["classic_kb"]["mode"],
        "hot_limit": classic_hot_limit(root),
        "record_count": len(records),
        "write_proposals": bool(args.write_proposals),
    }

    if args.write_proposals:
        manifest_id, manifest_path, _manifest = write_llm_manifest(
            root,
            "semantic_hygiene",
            context,
            records,
            judgment,
            validation_status,
            "hygiene_review",
            warnings,
            judgment_source_arg(args),
        )
        if judgment is not None:
            for group_name in ("demote_candidate", "supersede_or_merge_candidate", "resolve_candidate", "needs_sponsor"):
                for item in judgment_groups[group_name]:
                    record = candidates_by_id.get(item["record_id"])
                    if record is None:
                        continue
                    payload = hygiene_proposal_payload(
                        manifest_id=manifest_id,
                        group_name=group_name,
                        item=item,
                        record=record,
                        judgment=judgment,
                        validation_status=validation_status,
                        warnings=warnings,
                    )
                    proposal_id, proposal_path = write_proposal(root, "hygiene", payload)
                    proposal_ids.append(proposal_id)
                    proposal_paths.append(str(proposal_path))
        append_operation(
            root,
            "semantic-hygiene",
            {
                "scope": args.scope,
                "status": status,
                "manifest_id": manifest_id,
                "proposal_ids": proposal_ids,
            },
        )

    result = {
        "event": "semantic-hygiene",
        "generated_at": now_iso(),
        "status": status,
        "validation_status": validation_status,
        "read_only": not args.write_proposals,
        "classic_kb_mode": config["classic_kb"]["mode"],
        "scope": args.scope,
        "hot_limit": classic_hot_limit(root),
        "hot_count": len([record for record in records if record["tier"] == "HOT"]),
        "groups": judgment_groups if judgment is not None else mechanical_groups,
        "mechanical_groups": mechanical_groups,
        "warnings": warnings,
        "manifest_id": manifest_id,
        "proposal_ids": proposal_ids,
        "paths": {
            "manifest": str(manifest_path) if manifest_path else None,
            "proposals": proposal_paths,
        },
        "llm_task": build_llm_task(
            "semantic_hygiene",
            "Classify KB hygiene and HOT overflow records into keep-HOT, demote, supersede-or-merge, resolve, and needs-owner-review groups.",
            ["groups", "rationale", "confidence", "risk", "provenance", "conflicts"],
        ),
    }
    emit(result, args.json)
    return 0


def infer_facet_for_category(category: str, candidate: dict[str, Any]) -> str:
    if category == "DECISAO":
        return "decisions"
    if category == "APRENDIZADO":
        return "learnings"
    if category == "PENDENCIA":
        return "open-items"
    text = " ".join(
        str(candidate.get(key, ""))
        for key in ("title", "content", "tags")
    ).lower()
    if "definition" in text or "defini" in text or "gloss" in text:
        return "definitions"
    return "status"


def validate_filing_judgment(
    judgment: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[str, list[str], str]:
    warnings: list[str] = []
    action = judgment.get("action") or judgment.get("proposed_action")
    if action not in {"new", "update", "supersede", "defer"}:
        warnings.append("invalid_action")
        action = "defer"
    provenance = judgment.get("provenance", []) or []
    if action in {"new", "update", "supersede"} and not provenance:
        warnings.append("missing_provenance")
    duplicate_candidates = judgment.get("duplicate_candidates", []) or []
    if duplicate_candidates and action == "new":
        warnings.append("duplicate")
    if judgment.get("conflicts"):
        warnings.append("conflict")
    if action == "update" and (judgment.get("semantic_change") or judgment.get("change_type") == "semantic"):
        warnings.append("semantic_update_requires_supersede")
    unknown = validate_record_references(
        [item["record_id"] if isinstance(item, dict) and "record_id" in item else item for item in duplicate_candidates],
        candidates,
        "duplicate_candidates",
    )
    warnings.extend([f"unknown_record_reference:{rid}" for rid in unknown])
    if any(item in warnings for item in ("missing_provenance", "conflict", "invalid_action", "semantic_update_requires_supersede")):
        return "blocked", warnings, action
    if "duplicate" in warnings:
        return "needs_human_review", warnings, action
    return "valid", warnings, action


def cmd_filing_proposal(args: argparse.Namespace) -> int:
    root = project_root(args)
    load_config_or_fail(root)
    candidate_memory = parse_json_payload(args.input, "input")
    if candidate_memory is None:
        raise ValueError("--input is required")
    query = " ".join(
        str(candidate_memory.get(key, ""))
        for key in ("title", "content")
        if candidate_memory.get(key)
    ).strip()
    facet = infer_facet_for_category(args.category, candidate_memory)
    candidates = semantic_candidates(root, facet, query or None, args.limit, domain=args.domain)
    judgment = judgment_arg(args)
    if judgment is None:
        validation_status = "needs_llm_judgment"
        warnings: list[str] = []
        action = "defer"
    else:
        validation_status, warnings, action = validate_filing_judgment(judgment, candidates)
    context = {
        "command": "filing-proposal",
        "category": args.category,
        "domain": args.domain,
        "candidate_memory": candidate_memory,
        "inferred_facet": facet,
    }
    manifest_id, manifest_path, _manifest = write_llm_manifest(
        root,
        "filing_proposal",
        context,
        candidates,
        judgment,
        validation_status,
        action,
        warnings,
        judgment_source_arg(args),
    )
    proposal_payload = {
        "kind": "filing-proposal",
        "created_at": now_iso(),
        "manifest_id": manifest_id,
        "category": args.category,
        "domain": args.domain,
        "candidate_memory": candidate_memory,
        "candidate_records": candidates,
        "action": action,
        "rationale": (judgment or {}).get("rationale"),
        "confidence": (judgment or {}).get("confidence"),
        "risk": (judgment or {}).get("risk"),
        "provenance": (judgment or {}).get("provenance", []),
        "duplicate_candidates": (judgment or {}).get("duplicate_candidates", []),
        "conflicts": (judgment or {}).get("conflicts", []),
        "record_draft": (judgment or {}).get("record_draft"),
        "validation_status": validation_status,
        "warnings": warnings,
    }
    proposal_id, proposal_path = write_proposal(root, "filing", proposal_payload)
    result = {
        "event": "filing-proposal",
        "generated_at": now_iso(),
        "status": validation_status,
        **proposal_payload,
        "proposal_id": proposal_id,
        "paths": {"manifest": str(manifest_path), "proposal": str(proposal_path)},
        "llm_task": build_llm_task(
            "filing_proposal",
            "Decide whether candidate memory should be new, update, supersede, or defer with provenance and risk.",
            ["action", "rationale", "confidence", "risk", "provenance", "duplicate_candidates", "conflicts", "record_draft"],
        ),
    }
    append_operation(
        root,
        "filing-proposal",
        {
            "category": args.category,
            "domain": args.domain,
            "action": action,
            "status": validation_status,
            "manifest_id": manifest_id,
            "proposal_id": proposal_id,
        },
    )
    emit(result, args.json)
    return 0


def classic_kb_script(root: Path) -> Path:
    path = root / ".kb" / "kb.py"
    if not path.is_file():
        raise FileNotFoundError(f"classic KB entrypoint not found: {path}")
    return path


def classic_config_path(root: Path) -> Path:
    return root / ".kb" / "kb.config.json"


def load_classic_config(root: Path) -> dict[str, Any]:
    path = classic_config_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def proposal_apply_min_confidence(root: Path) -> float:
    config = load_classic_config(root)
    bands = (((config.get("filing_policy") or {}).get("confidence_bands")) or {})
    if "high" in bands:
        try:
            return float(bands["high"])
        except (TypeError, ValueError):
            pass
    return 0.8


def resolve_proposal_path(root: Path, value: str) -> Path:
    allowed_dirs = proposal_allowed_dirs(root)
    path = resolve_project_path(root, value)
    if path.is_file():
        if not is_inside_any(path, allowed_dirs):
            raise ValueError(f"proposal path outside .kb-next/proposals: {path}")
        return path.resolve()
    matches = list(proposals_root(root).glob(f"*/*{value}*.json"))
    exact = [candidate for candidate in matches if candidate.stem == value]
    candidates = exact or matches
    if not candidates:
        raise FileNotFoundError(f"proposal not found: {value}")
    if len(candidates) > 1:
        display = ", ".join(str(candidate) for candidate in candidates)
        raise ValueError(f"proposal id is ambiguous: {display}")
    candidate = candidates[0].resolve()
    if not is_inside_any(candidate, allowed_dirs):
        raise ValueError(f"proposal path outside .kb-next/proposals: {candidate}")
    return candidate


def proposal_apply_manifest_path(root: Path, apply_id: str) -> Path:
    return proposal_apply_manifests_root(root) / f"{apply_id}.json"


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def proposal_provenance_ids(provenance: Any) -> tuple[list[str], list[str], list[str]]:
    record_ids: list[str] = []
    source_ids: list[str] = []
    malformed: list[str] = []
    for index, item in enumerate(list_from_payload(provenance)):
        if isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
            sid = item.get("source_id")
            if rid:
                record_ids.append(str(rid))
            if sid:
                source_ids.append(str(sid))
            if not rid and not sid:
                malformed.append(f"provenance[{index}]")
        else:
            text = str(item).strip()
            if text:
                record_ids.append(text)
            else:
                malformed.append(f"provenance[{index}]")
    return dedupe_strings(record_ids), dedupe_strings(source_ids), malformed


def duplicate_candidate_ids(value: Any) -> list[str]:
    ids: list[str] = []
    for item in list_from_payload(value):
        if isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
        else:
            rid = item
        if rid:
            ids.append(str(rid))
    return dedupe_strings(ids)


def tags_arg(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        tags = [str(item).strip() for item in value if str(item).strip()]
        return ",".join(tags) if tags else None
    text = str(value).strip()
    return text or None


def add_optional_cli_arg(cmd: list[str], flag: str, value: Any) -> None:
    if value is None:
        return
    text = str(value)
    if text == "":
        return
    cmd.extend([flag, text])


def validate_record_draft(record_draft: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(record_draft, dict):
        return {}, ["missing_record_draft"]
    errors: list[str] = []
    for field in ("category", "domain", "title", "content"):
        if not record_draft.get(field):
            errors.append(f"record_draft_missing_{field}")
    return dict(record_draft), errors


def resolve_supersede_target(
    args: argparse.Namespace,
    proposal: dict[str, Any],
    record_draft: dict[str, Any],
) -> tuple[str | None, list[str]]:
    if args.target_record_id:
        return args.target_record_id, []
    if record_draft.get("supersedes_id"):
        return str(record_draft["supersedes_id"]), []
    candidates = duplicate_candidate_ids(proposal.get("duplicate_candidates"))
    if len(candidates) == 1:
        return candidates[0], []
    if not candidates:
        return None, ["missing_supersede_target"]
    return None, ["ambiguous_supersede_target"]


def canonical_create_command(root: Path, proposal_id: str, record_draft: dict[str, Any]) -> list[str]:
    cmd = [
        sys.executable,
        str(classic_kb_script(root)),
        "create",
    ]
    add_optional_cli_arg(cmd, "--id", record_draft.get("id"))
    cmd.extend(
        [
            "--category",
            str(record_draft["category"]),
            "--domain",
            str(record_draft["domain"]),
            "--title",
            str(record_draft["title"]),
            "--content",
            str(record_draft["content"]),
            "--status",
            str(record_draft.get("status") or "ATIVO"),
            "--tier",
            str(record_draft.get("tier") or "WARM"),
            "--source",
            str(record_draft.get("source") or f"kb-wiki-vnext approved proposal {proposal_id}"),
        ]
    )
    add_optional_cli_arg(cmd, "--tags", tags_arg(record_draft.get("tags")))
    add_optional_cli_arg(cmd, "--tier-reason", record_draft.get("tier_reason"))
    add_optional_cli_arg(cmd, "--review-after", record_draft.get("review_after"))
    add_optional_cli_arg(cmd, "--valid-until", record_draft.get("valid_until"))
    add_optional_cli_arg(cmd, "--confidence", record_draft.get("confidence"))
    add_optional_cli_arg(cmd, "--observed-at", record_draft.get("observed_at"))
    add_optional_cli_arg(cmd, "--source-id", record_draft.get("source_id"))
    cmd.append("--json")
    return cmd


def canonical_supersede_command(
    root: Path,
    proposal_id: str,
    target_record_id: str,
    record_draft: dict[str, Any],
) -> list[str]:
    cmd = [
        sys.executable,
        str(classic_kb_script(root)),
        "supersede",
        target_record_id,
    ]
    add_optional_cli_arg(cmd, "--new-id", record_draft.get("id"))
    add_optional_cli_arg(cmd, "--title", record_draft.get("title"))
    add_optional_cli_arg(cmd, "--content", record_draft.get("content"))
    add_optional_cli_arg(cmd, "--tier", record_draft.get("tier") or "WARM")
    add_optional_cli_arg(cmd, "--source", record_draft.get("source") or f"kb-wiki-vnext approved proposal {proposal_id}")
    add_optional_cli_arg(cmd, "--tags", tags_arg(record_draft.get("tags")))
    add_optional_cli_arg(cmd, "--tier-reason", record_draft.get("tier_reason"))
    add_optional_cli_arg(cmd, "--review-after", record_draft.get("review_after"))
    add_optional_cli_arg(cmd, "--valid-until", record_draft.get("valid_until"))
    add_optional_cli_arg(cmd, "--confidence", record_draft.get("confidence"))
    add_optional_cli_arg(cmd, "--source-id", record_draft.get("source_id"))
    cmd.append("--json")
    return cmd


def canonical_demote_hot_command(
    root: Path,
    proposal_id: str,
    target_record_id: str,
    proposal: dict[str, Any],
) -> list[str]:
    reason = (
        proposal.get("tier_reason")
        or proposal.get("rationale")
        or f"kb-wiki-vnext approved hygiene proposal {proposal_id}"
    )
    return [
        sys.executable,
        str(classic_kb_script(root)),
        "update",
        target_record_id,
        "--tier",
        "WARM",
        "--tier-reason",
        str(reason),
        "--json",
    ]


def canonical_resolve_command(
    root: Path,
    proposal_id: str,
    target_record_id: str,
    proposal: dict[str, Any],
) -> list[str]:
    notes = (
        proposal.get("resolution_notes")
        or proposal.get("rationale")
        or f"kb-wiki-vnext approved hygiene proposal {proposal_id}"
    )
    return [
        sys.executable,
        str(classic_kb_script(root)),
        "resolve",
        target_record_id,
        "--notes",
        str(notes),
        "--json",
    ]


def run_canonical_command(root: Path, cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        cmd,
        cwd=str(root / ".kb"),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"classic KB command failed: {result.returncode}")
    return json.loads(result.stdout)


def apply_blocking_warning(warning: str) -> bool:
    return (
        warning == "conflict"
        or warning == "missing_provenance"
        or warning == "low_confidence"
        or warning.startswith("low_confidence:")
        or warning.startswith("unknown_")
        or warning.startswith("invalid_")
        or warning.startswith("record_draft_missing_")
        or warning.startswith("missing_")
        or warning.startswith("ambiguous_")
        or warning.startswith("manifest_")
        or warning.startswith("proposal_")
        or warning.startswith("unsupported_action")
        or warning.startswith("provenance_warning")
    )


def matching_manifest_proposal(
    root: Path,
    source_manifest: dict[str, Any],
    proposal_path: Path,
    proposal: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    resulting = [
        item
        for item in list_from_payload(source_manifest.get("resulting_proposals"))
        if isinstance(item, dict)
    ]
    if not resulting:
        return None, ["missing_resulting_proposals"]
    proposal_id = proposal.get("proposal_id")
    rel_path = path_relative_to_root(root, proposal_path)
    matches = [
        item
        for item in resulting
        if item.get("proposal_id") == proposal_id or item.get("proposal_path") == rel_path
    ]
    if not matches:
        return None, ["proposal_not_listed_in_manifest"]
    match = matches[0]
    expected_path = match.get("proposal_path")
    if expected_path != rel_path:
        warnings.append("proposal_path_mismatch")
    expected_hash = match.get("proposal_hash")
    actual_hash = sha256_text(canonical_json(proposal))
    if not expected_hash:
        warnings.append("missing_proposal_hash")
    elif expected_hash != actual_hash:
        warnings.append("proposal_hash_mismatch")
    expected_kind = match.get("proposal_kind")
    proposal_kind_dir = proposal_path.parent.name
    if expected_kind and expected_kind != proposal_kind_dir:
        warnings.append("proposal_kind_mismatch")
    return match, warnings


def finalize_proposal_apply(
    root: Path,
    apply_manifest: dict[str, Any],
    *,
    json_mode: bool,
) -> int:
    apply_manifest["completed_at"] = now_iso()
    manifest_path = proposal_apply_manifest_path(root, apply_manifest["apply_id"])
    write_json(manifest_path, apply_manifest)
    append_operation(
        root,
        "proposal-apply",
        {
            "apply_id": apply_manifest["apply_id"],
            "proposal_id": apply_manifest.get("proposal_id"),
            "status": apply_manifest["status"],
            "action": apply_manifest.get("action"),
            "canonical_record_id": apply_manifest.get("canonical_record_id"),
            "warnings": apply_manifest.get("warnings", []),
        },
    )
    result = {
        "event": "proposal-apply",
        "generated_at": now_iso(),
        "status": apply_manifest["status"],
        "apply_id": apply_manifest["apply_id"],
        "proposal_id": apply_manifest.get("proposal_id"),
        "proposal_path": apply_manifest.get("proposal_path"),
        "action": apply_manifest.get("action"),
        "warnings": apply_manifest.get("warnings", []),
        "canonical_record_id": apply_manifest.get("canonical_record_id"),
        "canonical_result": apply_manifest.get("canonical_result"),
        "paths": {"apply_manifest": str(manifest_path)},
    }
    emit(result, json_mode)
    return 0


def cmd_proposal_apply(args: argparse.Namespace) -> int:
    root = project_root(args)
    load_config_or_fail(root)
    apply_id = make_id("proposal-apply")
    min_confidence = proposal_apply_min_confidence(root)
    apply_manifest: dict[str, Any] = {
        "apply_id": apply_id,
        "manifest_type": "proposal_apply",
        "created_at": now_iso(),
        "approval": {
            "approved": bool(args.approve),
            "approval_note": args.approval_note,
        },
        "min_confidence": min_confidence,
        "status": "blocked",
        "warnings": [],
        "classic_kb_mutation": "via_classic_cli_only",
        "classic_wiki_live_publish": False,
    }

    warnings: list[str] = []
    if not args.approve:
        warnings.append("missing_approval")
    if not args.approval_note:
        warnings.append("missing_approval_note")

    proposal: dict[str, Any] | None = None
    source_manifest: dict[str, Any] | None = None
    source_manifest_path: Path | None = None
    record_draft: dict[str, Any] = {}
    canonical_cmd: list[str] | None = None
    target_record_id: str | None = None

    try:
        proposal_path = resolve_proposal_path(root, args.proposal)
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        apply_manifest["proposal_path"] = str(proposal_path)
        apply_manifest["proposal_path_relative"] = path_relative_to_root(root, proposal_path)
        apply_manifest["proposal_hash"] = sha256_text(canonical_json(proposal))
        apply_manifest["proposal_id"] = proposal.get("proposal_id")
        apply_manifest["proposal_kind"] = proposal.get("kind")
    except Exception as exc:
        warnings.append(f"invalid_proposal:{exc}")
        apply_manifest["warnings"] = dedupe_strings(warnings)
        return finalize_proposal_apply(root, apply_manifest, json_mode=args.json)

    proposal_id = str(proposal.get("proposal_id") or proposal_path.stem)
    manifest_id = proposal.get("manifest_id")
    apply_manifest["source_llm_manifest_id"] = manifest_id
    if not manifest_id:
        warnings.append("missing_manifest_id")
    else:
        source_manifest_path = llm_manifests_root(root) / f"{manifest_id}.json"
        if not source_manifest_path.is_file():
            warnings.append(f"missing_llm_manifest:{manifest_id}")
        else:
            source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
            apply_manifest["source_llm_manifest_path"] = str(source_manifest_path)
            if source_manifest.get("manifest_id") != manifest_id:
                warnings.append("invalid_manifest_id_mismatch")
            if source_manifest.get("validation_status") != "valid":
                warnings.append(f"invalid_manifest_status:{source_manifest.get('validation_status')}")
            if source_manifest.get("judgment") is not None and not source_manifest.get("judgment_hash"):
                warnings.append("missing_judgment_hash")
            _manifest_entry, manifest_proposal_warnings = matching_manifest_proposal(
                root,
                source_manifest,
                proposal_path,
                proposal,
            )
            warnings.extend(manifest_proposal_warnings)
            manifest_action = source_manifest.get("proposed_action")
            proposal_action = proposal.get("action")
            if (
                proposal_action
                and manifest_action
                and proposal_action != manifest_action
                and manifest_action not in {"hygiene_review", "mixed"}
            ):
                warnings.append("manifest_action_mismatch")
            for warning in source_manifest.get("warnings", []) or []:
                warnings.append(str(warning))

    if proposal.get("validation_status") != "valid":
        warnings.append(f"invalid_proposal_status:{proposal.get('validation_status')}")
    for warning in proposal.get("warnings", []) or []:
        warnings.append(str(warning))
    action = proposal.get("action") or (source_manifest or {}).get("proposed_action")
    apply_manifest["action"] = action

    if proposal.get("kind") == "semantic-lookup" and not proposal.get("record_draft"):
        apply_manifest["status"] = "not_applicable"
        warnings.append("not_applicable:semantic_lookup_has_no_record_draft")
        apply_manifest["warnings"] = dedupe_strings(warnings)
        return finalize_proposal_apply(root, apply_manifest, json_mode=args.json)

    if action not in {"new", "supersede", "demote_hot", "resolve"}:
        warnings.append(f"unsupported_action:{action}")

    if action in {"new", "supersede"}:
        record_draft, draft_errors = validate_record_draft(proposal.get("record_draft"))
        warnings.extend(draft_errors)
    else:
        raw_record_draft = proposal.get("record_draft")
        record_draft = dict(raw_record_draft) if isinstance(raw_record_draft, dict) else {}
    confidence = coerce_float(first_present(proposal.get("confidence"), (source_manifest or {}).get("confidence"), record_draft.get("confidence")))
    apply_manifest["confidence"] = confidence
    if confidence is None:
        warnings.append("missing_confidence")
    elif confidence < min_confidence:
        warnings.append(f"low_confidence:{confidence}")

    provenance = proposal.get("provenance") or (source_manifest or {}).get("provenance_pointers") or []
    record_ids, source_ids, malformed_provenance = proposal_provenance_ids(provenance)
    warnings.extend([f"invalid_{item}" for item in malformed_provenance])
    if not record_ids and not source_ids:
        warnings.append("missing_provenance")
    records_by_id = fetch_records_by_ids(root, record_ids)
    missing_records = [rid for rid in record_ids if rid not in records_by_id]
    warnings.extend([f"unknown_record_reference:{rid}" for rid in missing_records])
    existing_source_ids = source_ids_exist(root, source_ids)
    missing_sources = [sid for sid in source_ids if sid not in existing_source_ids]
    warnings.extend([f"unknown_source_reference:{sid}" for sid in missing_sources])

    if action == "supersede":
        target_record_id, target_errors = resolve_supersede_target(args, proposal, record_draft)
        warnings.extend(target_errors)
        if target_record_id:
            target_records = fetch_records_by_ids(root, [target_record_id])
            if target_record_id not in target_records:
                warnings.append(f"unknown_supersede_target:{target_record_id}")
            apply_manifest["target_record_id"] = target_record_id
    elif action in {"demote_hot", "resolve"}:
        target_record_id = args.target_record_id or proposal.get("target_record_id")
        if not target_record_id:
            warnings.append("missing_target_record")
        else:
            target_record_id = str(target_record_id)
            target_records = fetch_records_by_ids(root, [target_record_id])
            target = target_records.get(target_record_id)
            if target is None:
                warnings.append(f"unknown_target_record:{target_record_id}")
            elif action == "demote_hot" and not (target["tier"] == "HOT" and target["status"] == "ATIVO"):
                warnings.append("invalid_demote_target")
            elif action == "resolve" and not (target["category"] == "PENDENCIA" and target["status"] == "ATIVO"):
                warnings.append("invalid_resolve_target")
            apply_manifest["target_record_id"] = target_record_id

    warnings = dedupe_strings(warnings)
    apply_manifest["warnings"] = warnings
    if any(apply_blocking_warning(warning) for warning in warnings):
        return finalize_proposal_apply(root, apply_manifest, json_mode=args.json)

    try:
        if action == "new":
            canonical_cmd = canonical_create_command(root, proposal_id, record_draft)
        elif action == "supersede" and target_record_id:
            canonical_cmd = canonical_supersede_command(root, proposal_id, target_record_id, record_draft)
        elif action == "demote_hot" and target_record_id:
            canonical_cmd = canonical_demote_hot_command(root, proposal_id, target_record_id, proposal)
        elif action == "resolve" and target_record_id:
            canonical_cmd = canonical_resolve_command(root, proposal_id, target_record_id, proposal)
        else:
            warnings.append(f"unsupported_action:{action}")
            apply_manifest["warnings"] = dedupe_strings(warnings)
            return finalize_proposal_apply(root, apply_manifest, json_mode=args.json)
        apply_manifest["status"] = "applying"
        apply_manifest["canonical_command"] = canonical_cmd
        write_json(proposal_apply_manifest_path(root, apply_id), apply_manifest)
        canonical_result = run_canonical_command(root, canonical_cmd)
        apply_manifest["status"] = "applied"
        apply_manifest["canonical_result"] = canonical_result
        apply_manifest["canonical_record_id"] = canonical_result.get("id") or target_record_id
    except Exception as exc:
        apply_manifest["status"] = "blocked"
        apply_manifest["warnings"] = dedupe_strings([*warnings, f"canonical_apply_failed:{exc}"])

    return finalize_proposal_apply(root, apply_manifest, json_mode=args.json)


def resolve_project_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def parse_frontmatter_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]
    items: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text or text.lower() == "none":
            continue
        items.append(text)
    return items


def parse_markdown_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter")
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValueError("unterminated frontmatter")

    metadata: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in lines[1:end_index]:
        if not raw_line.strip():
            continue
        stripped = raw_line.strip()
        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip()
            existing = metadata.setdefault(current_key, [])
            if isinstance(existing, list):
                existing.append(value)
            continue
        if ":" not in raw_line:
            current_key = None
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            metadata[key] = value
            current_key = None
        else:
            metadata[key] = []
            current_key = key

    body = "\n".join(lines[end_index + 1 :]).rstrip() + "\n"
    return metadata, body


def list_from_payload(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_record_id_list(value: Any) -> list[str]:
    ids: list[str] = []
    for item in list_from_payload(value):
        if isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
        else:
            rid = item
        if rid is None:
            continue
        text = str(rid).strip()
        if text:
            ids.append(text)
    return dedupe_strings(ids)


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def date_has_passed(value: Any) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text}T00:00:00+00:00")
        except ValueError:
            return False
    return parsed.date() < datetime.now(timezone.utc).date()


def warning_payload_labels(prefix: str, payload: Any) -> list[str]:
    labels: list[str] = []
    for item in list_from_payload(payload):
        if isinstance(item, dict):
            rid = item.get("record_id") or item.get("id")
            reason = item.get("reason") or item.get("warning") or item.get("message")
            if rid and reason:
                labels.append(f"{prefix}:{rid}:{reason}")
            elif rid:
                labels.append(f"{prefix}:{rid}")
            elif reason:
                labels.append(f"{prefix}:{reason}")
            else:
                labels.append(prefix)
        else:
            text = str(item).strip()
            labels.append(f"{prefix}:{text}" if text else prefix)
    return labels


def is_blocking_wiki_review_warning(warning: str) -> bool:
    blocking_prefixes = (
        "conflict",
        "draft_",
        "invalid_",
        "missing_draft",
        "missing_manifest_draft_hash",
        "missing_llm_manifest",
        "missing_supporting_records",
        "provenance_warning",
        "source_manifest_warning:blocked",
        "source_manifest_warning:conflict",
        "source_manifest_warning:missing_provenance",
        "source_manifest_warning:stale",
        "stale_supporting_record",
        "superseded_supporting_record",
        "supporting_record_mismatch",
        "unknown_supporting_record",
        "inactive_supporting_record",
        "llm_manifest_blocked",
    )
    return warning.startswith(blocking_prefixes)


def wiki_review_status(warnings: list[str]) -> str:
    if any(is_blocking_wiki_review_warning(warning) for warning in warnings):
        return "blocked"
    review_prefixes = (
        "confidence_below_materialization_threshold",
        "llm_manifest_needs_human_review",
        "missing_confidence",
        "source_manifest_warning:needs_human_review",
    )
    if any(warning.startswith(review_prefixes) for warning in warnings):
        return "needs_human_review"
    return "valid"


def materialized_page_with_header(
    kind: str,
    topic: str,
    source_manifest_id: str,
    materialization_id: str,
    supporting_record_ids: list[str],
    body: str,
) -> str:
    header = [
        "---",
        f"kind: {kind}",
        f"topic: {topic}",
        f"manifest_id: {source_manifest_id}",
        f"materialization_id: {materialization_id}",
        "authority: derived",
        "derived_from: wiki_draft_review",
        "supporting_records:",
    ]
    header.extend([f"  - {rid}" for rid in supporting_record_ids] or ["  - none"])
    header.extend(["---", ""])
    return "\n".join(header) + body.rstrip() + "\n"


def cmd_wiki_draft_review(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    if not config["wiki"]["enabled"]:
        raise RuntimeError("wiki-draft-review requires KB + Wiki activation")

    slug = slugify(args.topic)
    draft_paths = {
        "machine": resolve_project_path(root, args.machine_draft)
        if args.machine_draft
        else wiki_drafts_root(root) / "machine" / f"{slug}.md",
        "human": resolve_project_path(root, args.human_draft)
        if args.human_draft
        else wiki_drafts_root(root) / "human" / f"{slug}.md",
    }
    warnings: list[str] = []
    parsed_drafts: dict[str, dict[str, Any]] = {}
    draft_bodies: dict[str, str] = {}

    for surface, path in draft_paths.items():
        if not path.is_file():
            warnings.append(f"missing_draft:{surface}")
            continue
        try:
            metadata, body = parse_markdown_frontmatter(path)
        except ValueError as exc:
            warnings.append(f"invalid_draft_frontmatter:{surface}:{exc}")
            continue
        parsed_drafts[surface] = metadata
        draft_bodies[surface] = body
        expected_kind = f"{surface}_wiki_draft"
        if metadata.get("kind") != expected_kind:
            warnings.append(f"invalid_draft_kind:{surface}:{metadata.get('kind')}")
        if metadata.get("authority") != "derived_draft":
            warnings.append(f"invalid_authority:{surface}:{metadata.get('authority')}")
        if metadata.get("topic") != args.topic:
            warnings.append(f"invalid_topic:{surface}:{metadata.get('topic')}")

    manifest_ids = {
        str(metadata.get("manifest_id")).strip()
        for metadata in parsed_drafts.values()
        if metadata.get("manifest_id")
    }
    source_manifest: dict[str, Any] | None = None
    source_manifest_id: str | None = None
    source_manifest_path: Path | None = None
    if len(manifest_ids) != 1:
        warnings.append("invalid_manifest_linkage")
    else:
        source_manifest_id = next(iter(manifest_ids))
        source_manifest_path = llm_manifests_root(root) / f"{source_manifest_id}.json"
        if not source_manifest_path.is_file():
            warnings.append(f"missing_llm_manifest:{source_manifest_id}")
        else:
            source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))

    supporting_by_surface = {
        surface: parse_frontmatter_list(metadata.get("supporting_records"))
        for surface, metadata in parsed_drafts.items()
    }
    supporting_record_ids = dedupe_strings(
        [rid for ids in supporting_by_surface.values() for rid in ids]
    )
    if len(supporting_by_surface) == 2 and set(supporting_by_surface["machine"]) != set(supporting_by_surface["human"]):
        warnings.append("supporting_record_mismatch:draft_surfaces")
    if not supporting_record_ids:
        warnings.append("missing_supporting_records")

    confidence: float | None = None
    if source_manifest is not None:
        if source_manifest.get("manifest_id") != source_manifest_id:
            warnings.append("invalid_manifest_id_mismatch")
        if source_manifest.get("task_type") != "wiki_synthesis":
            warnings.append(f"invalid_llm_manifest_task:{source_manifest.get('task_type')}")
        manifest_status = source_manifest.get("validation_status")
        if manifest_status == "blocked":
            warnings.append("llm_manifest_blocked")
        elif manifest_status == "needs_human_review":
            warnings.append("llm_manifest_needs_human_review")
        elif manifest_status != "valid":
            warnings.append(f"invalid_llm_manifest_status:{manifest_status}")
        for warning in source_manifest.get("warnings", []) or []:
            warnings.append(f"source_manifest_warning:{warning}")

        generated_drafts = source_manifest.get("generated_drafts") or {}
        for surface, path in draft_paths.items():
            expected = generated_drafts.get(surface)
            if not isinstance(expected, dict):
                warnings.append(f"missing_manifest_draft_hash:{surface}")
                continue
            expected_path = expected.get("path")
            if expected_path != path_relative_to_root(root, path):
                warnings.append(f"draft_path_mismatch:{surface}")
            expected_hash = expected.get("hash")
            if not expected_hash:
                warnings.append(f"missing_manifest_draft_hash:{surface}")
            elif path.is_file() and expected_hash != sha256_path(path):
                warnings.append(f"draft_hash_mismatch:{surface}")

        judgment = source_manifest.get("judgment") or {}
        manifest_supporting = normalize_record_id_list(judgment.get("supporting_record_ids"))
        if set(manifest_supporting) != set(supporting_record_ids):
            warnings.append("supporting_record_mismatch:llm_manifest")
        if judgment.get("conflicts"):
            warnings.extend(warning_payload_labels("conflict", judgment.get("conflicts")))
        if judgment.get("stale_warnings"):
            warnings.extend(warning_payload_labels("stale_supporting_record", judgment.get("stale_warnings")))
        if judgment.get("provenance_warnings"):
            warnings.extend(warning_payload_labels("provenance_warning", judgment.get("provenance_warnings")))

        raw_confidence = source_manifest.get("confidence", judgment.get("confidence"))
        if raw_confidence is not None:
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                warnings.append(f"invalid_confidence:{raw_confidence}")

    if confidence is None:
        warnings.append("missing_confidence")
    elif confidence < args.min_confidence:
        warnings.append(f"confidence_below_materialization_threshold:{confidence}")

    records_by_id = fetch_records_by_ids(root, supporting_record_ids)
    for rid in supporting_record_ids:
        row = records_by_id.get(rid)
        if row is None:
            warnings.append(f"unknown_supporting_record:{rid}")
            continue
        if row["status"] != "ATIVO":
            warnings.append(f"inactive_supporting_record:{rid}:{row['status']}")
        if row_get(row, "replacement_id"):
            warnings.append(f"superseded_supporting_record:{rid}:{row_get(row, 'replacement_id')}")
        if date_has_passed(row_get(row, "review_after")) or date_has_passed(row_get(row, "valid_until")):
            warnings.append(f"stale_supporting_record:{rid}")

    warnings = dedupe_strings(warnings)
    validation_status = wiki_review_status(warnings)
    materialization_id = make_id("wiki-review")
    output_paths: dict[str, str] = {}
    output_hashes: dict[str, str] = {}
    materialized = bool(args.materialize and validation_status == "valid")

    if materialized:
        assert source_manifest_id is not None
        for surface, body in draft_bodies.items():
            output_path = wiki_surface_root(root, surface) / f"{slug}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            kind = f"{surface}_wiki_page"
            output_path.write_text(
                materialized_page_with_header(
                    kind,
                    args.topic,
                    source_manifest_id,
                    materialization_id,
                    supporting_record_ids,
                    body,
                ),
                encoding="utf-8",
            )
            output_paths[surface] = str(output_path)
            output_hashes[surface] = sha256_text(output_path.read_text(encoding="utf-8"))

    manifest_payload = {
        "manifest_id": materialization_id,
        "manifest_type": "wiki_draft_review",
        "created_at": now_iso(),
        "topic": args.topic,
        "slug": slug,
        "source_llm_manifest_id": source_manifest_id,
        "source_llm_manifest_path": str(source_manifest_path) if source_manifest_path else None,
        "source_draft_paths": {surface: str(path) for surface, path in draft_paths.items()},
        "source_draft_hashes": {
            surface: sha256_text(path.read_text(encoding="utf-8"))
            for surface, path in draft_paths.items()
            if path.is_file()
        },
        "supporting_record_ids": supporting_record_ids,
        "supporting_records": [row_to_supporting_record(records_by_id[rid]) for rid in supporting_record_ids if rid in records_by_id],
        "confidence": confidence,
        "min_confidence": args.min_confidence,
        "validation_status": validation_status,
        "warnings": warnings,
        "materialize_requested": bool(args.materialize),
        "materialized": materialized,
        "output_paths": output_paths,
        "output_hashes": output_hashes,
        "authority": "derived",
        "classic_kb_mode": config["classic_kb"]["mode"],
        "classic_kb_mutation": "forbidden",
        "classic_wiki_live_publish": False,
    }
    review_manifest_path = wiki_review_manifests_root(root) / f"{materialization_id}.json"
    write_json(review_manifest_path, manifest_payload)

    append_operation(
        root,
        "wiki-draft-review",
        {
            "topic": args.topic,
            "status": validation_status,
            "source_llm_manifest_id": source_manifest_id,
            "review_manifest_id": materialization_id,
            "materialize_requested": bool(args.materialize),
            "materialized": materialized,
            "output_paths": output_paths,
            "warnings": warnings,
        },
    )

    result = {
        "event": "wiki-draft-review",
        "generated_at": now_iso(),
        "status": validation_status,
        "topic": args.topic,
        "source_llm_manifest_id": source_manifest_id,
        "review_manifest_id": materialization_id,
        "supporting_record_ids": supporting_record_ids,
        "confidence": confidence,
        "warnings": warnings,
        "materialize_requested": bool(args.materialize),
        "materialized": materialized,
        "paths": {
            "review_manifest": str(review_manifest_path),
            "machine_draft": str(draft_paths["machine"]),
            "human_draft": str(draft_paths["human"]),
            **output_paths,
        },
    }
    emit(result, args.json)
    return 0


def draft_with_header(kind: str, topic: str, manifest_id: str, supporting_record_ids: list[str], body: str) -> str:
    header = [
        "---",
        f"kind: {kind}",
        f"topic: {topic}",
        f"manifest_id: {manifest_id}",
        "authority: derived_draft",
        "supporting_records:",
    ]
    header.extend([f"  - {rid}" for rid in supporting_record_ids] or ["  - none"])
    header.extend(["---", ""])
    return "\n".join(header) + body.rstrip() + "\n"


def cmd_wiki_synthesis_plan(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    if not config["wiki"]["enabled"]:
        raise RuntimeError("wiki-synthesis-plan requires KB + Wiki activation")
    candidates = semantic_candidates(root, "status", args.topic, args.limit, domain=args.domain)
    judgment = judgment_arg(args)
    warnings: list[str] = []
    if judgment is None:
        validation_status = "needs_llm_judgment"
    else:
        supporting = judgment.get("supporting_record_ids", []) or []
        unknown = validate_record_references(supporting, candidates, "supporting_record_ids")
        warnings.extend([f"unknown_record_reference:{rid}" for rid in unknown])
        if unknown:
            validation_status = "blocked"
        elif judgment.get("confidence") is not None and judgment.get("confidence") < 0.55:
            warnings.append("low_confidence")
            validation_status = "needs_human_review"
        else:
            validation_status = judgment.get("validation_status") if judgment.get("validation_status") in VALIDATION_STATUSES else "valid"
    action = "answer_only"
    context = {
        "command": "wiki-synthesis-plan",
        "topic": args.topic,
        "domain": args.domain,
        "write_drafts": args.write_drafts,
    }
    manifest_id, manifest_path, _manifest = write_llm_manifest(
        root,
        "wiki_synthesis",
        context,
        candidates,
        judgment,
        validation_status,
        action,
        warnings,
        judgment_source_arg(args),
    )
    draft_paths: dict[str, str] = {}
    supporting_record_ids = (judgment or {}).get("supporting_record_ids", []) or []
    if args.write_drafts and judgment is not None and validation_status in {"valid", "needs_human_review"}:
        slug = slugify(args.topic)
        machine_body = judgment.get("machine_draft") or f"# {args.topic}\n\nMachine draft pending refinement.\n"
        human_body = judgment.get("human_draft") or f"# {args.topic}\n\nHuman draft pending refinement.\n"
        machine_path = wiki_drafts_root(root) / "machine" / f"{slug}.md"
        human_path = wiki_drafts_root(root) / "human" / f"{slug}.md"
        machine_path.parent.mkdir(parents=True, exist_ok=True)
        human_path.parent.mkdir(parents=True, exist_ok=True)
        machine_path.write_text(
            draft_with_header("machine_wiki_draft", args.topic, manifest_id, supporting_record_ids, machine_body),
            encoding="utf-8",
        )
        human_path.write_text(
            draft_with_header("human_wiki_draft", args.topic, manifest_id, supporting_record_ids, human_body),
            encoding="utf-8",
        )
        draft_paths = {"machine": str(machine_path), "human": str(human_path)}
        register_manifest_drafts(root, manifest_id, draft_paths)
    proposal_payload = {
        "kind": "wiki-synthesis-plan",
        "created_at": now_iso(),
        "manifest_id": manifest_id,
        "topic": args.topic,
        "domain": args.domain,
        "candidate_records": candidates,
        "supporting_record_ids": supporting_record_ids,
        "rationale": (judgment or {}).get("rationale"),
        "confidence": (judgment or {}).get("confidence"),
        "validation_status": validation_status,
        "warnings": warnings,
        "draft_paths": draft_paths,
    }
    proposal_id, proposal_path = write_proposal(root, "wiki-synthesis", proposal_payload)
    result = {
        "event": "wiki-synthesis-plan",
        "generated_at": now_iso(),
        "status": validation_status,
        **proposal_payload,
        "proposal_id": proposal_id,
        "paths": {"manifest": str(manifest_path), "proposal": str(proposal_path), **draft_paths},
        "llm_task": build_llm_task(
            "wiki_synthesis",
            "Plan machine and human wiki drafts from canonical KB inputs without publishing live surfaces.",
            ["supporting_record_ids", "rationale", "confidence", "machine_draft", "human_draft"],
        ),
    }
    append_operation(
        root,
        "wiki-synthesis-plan",
        {
            "topic": args.topic,
            "domain": args.domain,
            "status": validation_status,
            "manifest_id": manifest_id,
            "proposal_id": proposal_id,
            "draft_paths": draft_paths,
        },
    )
    emit(result, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KB/Wiki vNext side-by-side runtime")
    parser.add_argument("--project-root", default=".", help="Project root containing .kb/ and/or .kb-next/")
    sub = parser.add_subparsers(dest="command", required=True)

    wizard = sub.add_parser("activation-wizard")
    wizard.add_argument("--mode", choices=["short", "guided"], required=True)
    wizard.add_argument("--choice", choices=sorted(CHOICES.keys()))
    wizard.add_argument("--answers", help="JSON object or @path for guided mode answers")
    wizard.add_argument("--rationale")
    wizard.add_argument("--json", action="store_true")
    wizard.set_defaults(func=cmd_activation_wizard)

    session = sub.add_parser("session-start")
    session.add_argument("--json", action="store_true")
    session.set_defaults(func=cmd_session_start)

    preflight = sub.add_parser("compliance-preflight")
    preflight.add_argument("--work-type", choices=COMPLIANCE_WORK_TYPES)
    preflight.add_argument("--topic")
    preflight.add_argument("--json", action="store_true")
    preflight.set_defaults(func=cmd_compliance_preflight)

    source_linkage = sub.add_parser("source-linkage-audit")
    source_linkage.add_argument("--scope", choices=["track-b"], required=True)
    source_linkage.add_argument("--json", action="store_true")
    source_linkage.set_defaults(func=cmd_source_linkage_audit)

    track_b_export = sub.add_parser("track-b-export")
    track_b_export.add_argument("--adapter", choices=[OBSIDIAN_ADAPTER], required=True)
    track_b_export.add_argument("--json", action="store_true")
    track_b_export.set_defaults(func=cmd_track_b_export)

    lookup = sub.add_parser("lookup")
    lookup.add_argument("--facet", choices=MEMORY_FACETS, required=True)
    lookup.add_argument("--query")
    lookup.add_argument("--limit", type=int, default=10)
    lookup.add_argument("--json", action="store_true")
    lookup.set_defaults(func=cmd_lookup)

    semantic = sub.add_parser("semantic-lookup")
    semantic.add_argument("--query", required=True)
    semantic.add_argument("--facet", choices=MEMORY_FACETS, required=True)
    semantic.add_argument("--limit", type=int, default=10)
    semantic.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    semantic.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    semantic.add_argument("--json", action="store_true")
    semantic.set_defaults(func=cmd_semantic_lookup)

    curation = sub.add_parser("curation-proposal")
    curation.add_argument("--query", required=True)
    curation.add_argument("--facet", choices=MEMORY_FACETS, required=True)
    curation.add_argument("--limit", type=int, default=10)
    curation.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    curation.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    curation.add_argument("--json", action="store_true")
    curation.set_defaults(func=cmd_curation_proposal)

    hygiene = sub.add_parser("semantic-hygiene")
    hygiene.add_argument("--scope", choices=["hot-overflow"], default="hot-overflow")
    hygiene.add_argument("--limit", type=int, default=50)
    hygiene.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    hygiene.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    hygiene.add_argument("--write-proposals", action="store_true")
    hygiene.add_argument("--json", action="store_true")
    hygiene.set_defaults(func=cmd_semantic_hygiene)

    filing = sub.add_parser("filing-proposal")
    filing.add_argument("--input", required=True, help="JSON object or @path with candidate memory")
    filing.add_argument("--category", required=True)
    filing.add_argument("--domain", required=True)
    filing.add_argument("--limit", type=int, default=10)
    filing.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    filing.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    filing.add_argument("--json", action="store_true")
    filing.set_defaults(func=cmd_filing_proposal)

    proposal_apply = sub.add_parser("proposal-apply")
    proposal_apply.add_argument("--proposal", required=True, help="Proposal path or proposal id under .kb-next/proposals")
    proposal_apply.add_argument("--approve", action="store_true")
    proposal_apply.add_argument("--approval-note")
    proposal_apply.add_argument("--target-record-id")
    proposal_apply.add_argument("--json", action="store_true")
    proposal_apply.set_defaults(func=cmd_proposal_apply)

    wiki_plan = sub.add_parser("wiki-synthesis-plan")
    wiki_plan.add_argument("--topic", required=True)
    wiki_plan.add_argument("--domain", required=True)
    wiki_plan.add_argument("--limit", type=int, default=10)
    wiki_plan.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    wiki_plan.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    wiki_plan.add_argument("--write-drafts", action="store_true")
    wiki_plan.add_argument("--json", action="store_true")
    wiki_plan.set_defaults(func=cmd_wiki_synthesis_plan)

    wiki_review = sub.add_parser("wiki-draft-review")
    wiki_review.add_argument("--topic", required=True)
    wiki_review.add_argument("--machine-draft", help="Optional machine draft path; defaults to .kb-next/wiki/drafts/machine/<topic>.md")
    wiki_review.add_argument("--human-draft", help="Optional human draft path; defaults to .kb-next/wiki/drafts/human/<topic>.md")
    wiki_review.add_argument("--min-confidence", type=float, default=WIKI_MATERIALIZATION_MIN_CONFIDENCE)
    wiki_review.add_argument("--materialize", action="store_true")
    wiki_review.add_argument("--json", action="store_true")
    wiki_review.set_defaults(func=cmd_wiki_draft_review)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
