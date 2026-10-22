from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import unicodedata
import urllib.request
from array import array
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn
from urllib.parse import quote
from uuid import uuid4


CONFIG_REL = Path(".kb-next") / "kb-next.config.json"
DECISION_REL = Path(".kb-next") / "decisions" / "activation-decision.json"
OPERATIONS_REL = Path(".kb-next") / "operations.jsonl"
# G-05: the versioned oplog keeps mutations and decisions only. Read events
# (session-start, lookup, semantic-lookup) and derived dense-index builds go to
# a local telemetry file that ignores itself and rotates once it reaches
# TELEMETRY_MAX_BYTES, keeping one previous generation (about 2 MiB on disk).
TELEMETRY_REL = Path(".kb-next") / "telemetry" / "events.jsonl"
TELEMETRY_ROTATED_NAME = "events.1.jsonl"
TELEMETRY_MAX_BYTES = 1024 * 1024
TELEMETRY_EVENTS = frozenset({"session-start", "lookup", "semantic-lookup", "dense_index"})
TELEMETRY_GITIGNORE = "# Local read telemetry from kb_next.py: rotated, never committed.\n*\n"
NOW_REL = Path(".kb-next") / "memory" / "NOW.md"
LLM_MANIFESTS_REL = Path(".kb-next") / "manifests" / "llm"
WIKI_REVIEW_MANIFESTS_REL = Path(".kb-next") / "manifests" / "wiki-draft-review"
PROPOSAL_APPLY_MANIFESTS_REL = Path(".kb-next") / "manifests" / "proposal-apply"
APPROVED_FILING_MANIFESTS_REL = Path(".kb-next") / "manifests" / "approved-filing"
PROPOSALS_REL = Path(".kb-next") / "proposals"
WIKI_DRAFTS_REL = Path(".kb-next") / "wiki" / "drafts"
WIKI_MACHINE_REL = Path(".kb-next") / "wiki" / "machine"
WIKI_HUMAN_REL = Path(".kb-next") / "wiki" / "human"
WIKI_MATERIALIZATION_MIN_CONFIDENCE = 0.8
ADAPTERS_REL = Path(".kb-next") / "adapters"
OBSIDIAN_ADAPTER = "obsidian_static_markdown"
OBSIDIAN_DESIGN_VERSION = "obsidian_static_markdown_design_v1"
RUNTIME_VERSION = "0.2.2"
# Classic lifecycle events that keep an enabled classic wiki current. Mirrors
# WIKI_SYNC_EVENTS in the classic runtime (core/runtime/wiki.py).
CLASSIC_WIKI_SYNC_EVENTS = ("record_filed", "source_ingest", "session_end", "scheduled_maintenance")
WORKTREE_SCOPE_ENV = "KB_FACTORY_WORKTREE_SCOPE"
# E1.4: every proposal-apply names who approves it. Identity is recorded, not
# authenticated; origin-bound capabilities are E3.4.
ACTOR_RUNTIMES = ("claude-code", "codex", "cowork", "human")
ACTOR_HINT = (
    "proposal-apply records who approves each apply: pass --actor <id> (the person "
    "or agent that approves) and --actor-runtime <claude-code|codex|cowork|human>. "
    "A project may name its usual approver in proposal_apply.default_actor of "
    ".kb-next/kb-next.config.json; --actor then defaults to it. "
    "Runtime 0.2.0 removed anonymous apply; see the KB/Wiki vNext changelog."
)
# Domains with at least this many active records get a wiki topic, matching the
# classic domain_overview candidate threshold.
WIKI_TOPIC_MIN_RECORDS = 3
# A KB + Wiki activation keeps the wiki dormant until this many active records
# cite a registered source: below it, NOW, HOT and the topic files already show
# every record, so wiki pages would repeat them. `--wiki-min-sourced-records 0`
# turns the wiki on at once.
WIKI_DORMANT_MIN_SOURCED_RECORDS = 10
PROJECT_SCOPE_TAG = "project-scope"
RECORD_CATEGORIES = ("DECISAO", "PREMISSA", "FATO", "PENDENCIA", "APRENDIZADO")
# Template seeds of kb-lifecycle < 0.2.6, the same list as the classic
# runtime/constants.py. Derived surfaces leave them out; kb.db keeps them.
BOOTSTRAP_SEED_SOURCES = ("project-bootstrap", "kb-factory-blueprint")
BOOTSTRAP_SEED_TITLES = (
    "KB enabled as the project's operating memory",
    "Initial project scope remains valid until first KB review",
    "The primary runtime is local-first",
    "Review HOT criteria after first real sessions",
    "Search before assuming reduces context drift",
)
NOT_BOOTSTRAP_SEED = (
    "NOT (COALESCE(source, '') IN ("
    + ", ".join("'" + value.replace("'", "''") + "'" for value in BOOTSTRAP_SEED_SOURCES)
    + ") AND title IN ("
    + ", ".join("'" + value.replace("'", "''") + "'" for value in BOOTSTRAP_SEED_TITLES)
    + "))"
)
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
# Automatic curation (2026-10-20): detection runs at every session end and in
# the weekly maintenance run, and at most this many valid hygiene proposals stay
# open per project and review window. Five per project keeps the nine projects
# that held candidates on 2026-10-20 at 45 decisions a week, which fits the
# 15-minute weekly review only at about 20 s per decision (assumed, not measured).
HYGIENE_WEEKLY_DEFAULT = 5
HYGIENE_REVIEW_WINDOW_DAYS = 7
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
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root).resolve()


def kb_next_root(root: Path) -> Path:
    return root / ".kb-next"


def _read_small_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        return None


def linked_worktree_main_root(project_root: Path) -> Path | None:
    """Main worktree root when ``project_root`` is a linked Git worktree.

    Same resolution as the classic runtime (core/runtime/paths.py): a `.git`
    file whose gitdir carries a `commondir` pointer, i.e. the data reported by
    `git rev-parse --git-common-dir`. Submodules have no `commondir`.
    """
    dotgit = project_root / ".git"
    if not dotgit.is_file():
        return None
    text = _read_small_text(dotgit)
    if not text or not text.lower().startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = project_root / gitdir
    common_text = _read_small_text(gitdir / "commondir")
    if not common_text:
        return None
    common = Path(common_text)
    if not common.is_absolute():
        common = gitdir / common
    try:
        common = common.resolve()
        if common.name != ".git" or not common.is_dir():
            return None
        main_root = common.parent
        if main_root.resolve() == project_root.resolve():
            return None
    except OSError:
        return None
    return main_root


def _classic_worktree_scope(local_kb: Path) -> str:
    env_value = os.environ.get(WORKTREE_SCOPE_ENV, "").strip().lower()
    if env_value in ("shared", "local"):
        return env_value
    text = _read_small_text(local_kb / "kb.config.json")
    if text:
        try:
            storage = json.loads(text).get("storage")
        except (ValueError, AttributeError):
            storage = None
        if isinstance(storage, dict):
            value = str(storage.get("worktree_scope", "")).strip().lower()
            if value in ("shared", "local"):
                return value
    return "shared"


def classic_kb_root(root: Path) -> Path:
    """The classic `.kb/` this workspace reads, including linked worktrees.

    A per-session linked worktree shares the main worktree KB (when it exists)
    so vNext reads the same database the classic runtime writes.
    """
    local = root / ".kb"
    main_root = linked_worktree_main_root(root)
    if main_root is None or _classic_worktree_scope(local) == "local":
        return local
    candidate = main_root / ".kb"
    if (candidate / "kb.db").is_file():
        return candidate
    return local


def classic_kb_resolution(root: Path) -> dict[str, Any]:
    kb_root = classic_kb_root(root)
    return {
        "path": str(kb_root),
        "resolution": "main_worktree" if kb_root != root / ".kb" else "local",
        "main_worktree_root": str(linked_worktree_main_root(root) or "") or None,
    }


def _is_absolute_text(raw: str) -> bool:
    return PureWindowsPath(raw).is_absolute() or PurePosixPath(raw).is_absolute() or (
        len(raw) >= 2 and raw[1] == ":"
    )


def resolve_source_file(root: Path, source: dict[str, Any]) -> Path | None:
    """Locate a classic source file from its `sources` row.

    Relative stored paths (classic runtime 0.2.4+) resolve against the classic
    KB root; legacy absolute paths are honoured while they exist and are
    re-rooted under `sources/<source_id>/<filename>` once the project moved.
    """
    raw = str(source.get("stored_path") or "").strip()
    if not raw:
        return None
    kb_root = classic_kb_root(root)
    if not _is_absolute_text(raw):
        return kb_root.joinpath(*PurePosixPath(raw.replace("\\", "/")).parts)
    candidate = Path(raw)
    if candidate.is_file():
        return candidate
    name = source.get("filename") or (
        PureWindowsPath(raw).name if "\\" in raw else PurePosixPath(raw).name
    )
    source_id = source.get("source_id")
    if source_id and name:
        rerooted = kb_root / "sources" / str(source_id) / str(name)
        if rerooted.is_file():
            return rerooted
    return candidate


def config_path(root: Path) -> Path:
    return root / CONFIG_REL


def decision_path(root: Path) -> Path:
    return root / DECISION_REL


def operations_path(root: Path) -> Path:
    return root / OPERATIONS_REL


def telemetry_path(root: Path) -> Path:
    return root / TELEMETRY_REL


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


def path_within(child: Path, parent: Path) -> bool:
    # `Path.is_relative_to` is Python 3.9+; this keeps the runtime 3.8-compatible.
    if child == parent:
        return True
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def is_inside_any(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    return any(path_within(resolved, root) for root in roots)


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
            # Relative on purpose: the workspace keeps working after a move.
            "root": ".",
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
                ".kb/memory/NOW.md",
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
        "retrieval": {
            "dense": dict(DENSE_DEFAULTS),
        },
        "track_b": {
            "source_linkage_policy": "strict",
            "first_adapter": "obsidian_static_markdown",
            "blocked_source_ids": [],
            "tag_synthesis_denylist": TRACK_B_DEFAULT_DENYLIST,
        },
    }


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge where ``overlay`` wins; lists and scalars are replaced."""
    merged: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def flatten_keys(payload: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {prefix: payload}
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and value:
            flat.update(flatten_keys(value, path))
        else:
            flat[path] = value
    return flat


def changed_key_paths(before: dict[str, Any] | None, after: dict[str, Any]) -> list[str]:
    old = flatten_keys(before or {})
    new = flatten_keys(after)
    return sorted(key for key in set(old) | set(new) if old.get(key, object()) != new.get(key, object()))


def merge_config(existing: dict[str, Any] | None, fresh: dict[str, Any]) -> dict[str, Any]:
    """Re-activation keeps operator edits and only rewrites activation-owned keys.

    Owned keys: `activation`, `wiki.enabled`, `wiki.surfaces`, and the portable
    `project.root`. Every other existing key survives; keys introduced by a
    newer runtime are filled from the fresh defaults.
    """
    if not isinstance(existing, dict):
        return fresh
    merged = deep_merge(fresh, existing)
    merged["activation"] = fresh["activation"]
    wiki = dict(merged.get("wiki") or {})
    wiki["enabled"] = fresh["wiki"]["enabled"]
    wiki["surfaces"] = dict(fresh["wiki"]["surfaces"])
    merged["wiki"] = wiki
    project = dict(merged.get("project") or {})
    project["root"] = fresh["project"]["root"]
    merged["project"] = project
    return merged


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_event_line(path: Path, event: str, details: dict[str, Any]) -> None:
    payload = {
        "event": event,
        "happened_at": now_iso(),
        "details": details,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_operation(root: Path, event: str, details: dict[str, Any]) -> None:
    """Append to the versioned governance trail: mutations and decisions only."""
    if event in TELEMETRY_EVENTS:
        raise ValueError(f"{event} is read telemetry; record it with append_telemetry")
    op_path = operations_path(root)
    op_path.parent.mkdir(parents=True, exist_ok=True)
    append_event_line(op_path, event, details)


def ensure_telemetry_ignore(root: Path) -> bool:
    """Write .kb-next/telemetry/.gitignore once; never touch the project's own .gitignore."""
    ignore = telemetry_path(root).parent / ".gitignore"
    if ignore.is_file():
        return False
    ignore.parent.mkdir(parents=True, exist_ok=True)
    ignore.write_bytes(TELEMETRY_GITIGNORE.encode("utf-8"))
    return True


def append_telemetry(root: Path, event: str, details: dict[str, Any]) -> None:
    """Append to the local telemetry file, best effort.

    A read command never fails because its telemetry could not be written. On
    Windows the rotation fails while another session holds the file open; the
    append then goes to the current file and a later append rotates it.
    """
    if event not in TELEMETRY_EVENTS:
        raise ValueError(f"{event} belongs in the governance trail; record it with append_operation")
    path = telemetry_path(root)
    try:
        ensure_telemetry_ignore(root)
        if path.is_file() and path.stat().st_size >= TELEMETRY_MAX_BYTES:
            try:
                os.replace(path, path.with_name(TELEMETRY_ROTATED_NAME))
            except OSError:
                pass
        append_event_line(path, event, details)
    except OSError:
        pass


def classic_wiki_enabled(root: Path) -> bool | None:
    path = classic_config_path(root)
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    wiki = config.get("wiki") if isinstance(config, dict) else None
    return bool(wiki.get("enabled", False)) if isinstance(wiki, dict) else False


def classic_wiki_sourced_threshold(root: Path) -> int | None:
    """`wiki.eligibility.min_sourced_records` of a classic wiki that waits for it, else None.

    Only a wiki that is not enabled outright and runs in `signal` mode waits:
    the classic runtime then publishes once that many active records cite a
    registered source.
    """
    path = classic_config_path(root)
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    wiki = config.get("wiki") if isinstance(config, dict) else None
    if not isinstance(wiki, dict) or wiki.get("enabled") or wiki.get("activation_mode") != "signal":
        return None
    value = (wiki.get("eligibility") or {}).get("min_sourced_records")
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def sourced_record_count(root: Path) -> int:
    """Active records, template seeds aside, that cite a registered source."""
    try:
        conn = open_classic_kb_readonly(root)
    except FileNotFoundError:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM records WHERE status = 'ATIVO' AND source_id IS NOT NULL "
            f"AND {NOT_BOOTSTRAP_SEED}"
        ).fetchone()
        return int(row["n"])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def wiki_dormancy(root: Path, config: dict[str, Any]) -> dict[str, int] | None:
    """`{min_sourced_records, sourced_records}` while a KB + Wiki workspace waits, else None."""
    if not (config.get("wiki") or {}).get("enabled"):
        return None
    threshold = classic_wiki_sourced_threshold(root)
    if threshold is None:
        return None
    count = sourced_record_count(root)
    if count >= threshold:
        return None
    return {"min_sourced_records": threshold, "sourced_records": count}


NOW_GENERATED_MARKER = "<!-- kb-next:generated-now -->"
NOW_TEMPLATE_TITLE = "# KB/Wiki vNext NOW"
NOW_TEMPLATE_HEADINGS = frozenset({"## Required Default Read", "## On Demand", "## Wiki Flow"})


def is_generated_now(text: str) -> bool:
    """True when NOW.md is a runtime-generated template that may be regenerated.

    Generated files carry the marker; files written by older runtimes are
    recognized by their exact shape (template title, template headings only,
    bullets only). Anything else was curated and must be preserved.
    """
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    if NOW_GENERATED_MARKER in lines:
        return True
    body = [line for line in lines if line.strip()]
    if not body or body[0] != NOW_TEMPLATE_TITLE:
        return False
    for line in body[1:]:
        if line.startswith("## "):
            if line not in NOW_TEMPLATE_HEADINGS:
                return False
        elif not line.startswith("- "):
            return False
    return True


def write_now(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = now_path(root)
    if path.is_file() and not is_generated_now(path.read_text(encoding="utf-8", errors="replace")):
        return {
            "action": "preserved",
            "path": str(path),
            "reason": "curated NOW.md (not a generated template); delete it to regenerate",
        }
    existed = path.is_file()
    mode = config["activation"]["sponsor_decision"]
    dormant = wiki_dormancy(root, config)
    wiki_enabled = config["wiki"]["enabled"] and dormant is None
    classic_wiki = classic_wiki_enabled(root)
    classic_label = "absent" if classic_wiki is None else str(classic_wiki).lower()
    lines = [
        NOW_TEMPLATE_TITLE,
        NOW_GENERATED_MARKER,
        "",
        f"- Generated: `{now_iso()}`",
        f"- Activation mode: `{mode}`",
        f"- Classic KB: `{config['classic_kb']['root']}` (`read_only`)",
        f"- Wiki active: `{str(wiki_enabled).lower()}`",
        f"- Classic wiki enabled (`.kb/kb.config.json`): `{classic_label}`",
    ]
    if dormant is not None:
        lines.append(
            f"- Wiki dormant until `{dormant['min_sourced_records']}` active records cite a registered source "
            f"(now `{dormant['sourced_records']}`); it then publishes by itself and `session-start` reports it."
        )
    lines += [
        "",
        "## Required Default Read",
        "- Read this `NOW.md` only.",
        "",
        "## On Demand",
        "- Use `semantic-lookup` when LLM judgment is available.",
        "- Use `lookup` as deterministic fallback for decisions, learnings, definitions, open items, and status; add `--domain` to scope it.",
        "- Read classic `.kb/memory/NOW.md` only when the project status snapshot is needed.",
        "- Read classic `.kb/memory/HOT.md` only when the active working set is needed.",
        "- Read classic `.kb/memory/INDEX.md` only when the broad KB map is needed.",
        "- Use the Wiki index only when KB + Wiki is active and page navigation is needed.",
        "- Open historical artifacts only for rationale, source, provenance, historical heuristic, or exact wording.",
    ]
    if wiki_enabled:
        lines.extend(
            [
                "",
                "## Wiki Flow",
                "- Classic pages in `.kb/wiki/live` refresh on record, ingest, and session-end lifecycle events.",
                "- At session end, run `wiki-draft-status` and draft pending topics with `wiki-synthesis-plan` + `wiki-draft-review` (plugin command `vnext-wiki-drafts`).",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"action": "regenerated" if existed else "created", "path": str(path)}


DECISION_KEPT_KEYS = ("decided_at", "rationale", "source", "recommended_mode", "guided_score")


def reconcile_decision(root: Path, decision: dict[str, Any], *, explicit_rationale: bool) -> tuple[dict[str, Any], str]:
    """Keep the recorded decision when re-activation confirms the same mode."""
    path = decision_path(root)
    try:
        previous = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None
    except (OSError, ValueError):
        previous = None
    if not isinstance(previous, dict):
        return decision, "recorded"
    same_mode = previous.get("sponsor_decision") == decision["sponsor_decision"]
    if same_mode and not explicit_rationale:
        kept = dict(previous)
        kept["reconfirmed_at"] = decision["decided_at"]
        for key in ("mode", "sponsor_decision"):
            kept[key] = decision[key]
        return kept, "reconfirmed"
    updated = dict(decision)
    updated["previous_decision"] = {key: previous.get(key) for key in ("sponsor_decision", *DECISION_KEPT_KEYS)
                                    if key in previous}
    return updated, "changed" if not same_mode else "rationale_updated"


def load_config_or_fail(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run activation-wizard first")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_classic_wiki_enabled(config: dict[str, Any], enabled: bool) -> list[dict[str, Any]]:
    """Same semantics as classic `kb.py wiki-config` (core/runtime/wiki.py)."""
    changes: list[dict[str, Any]] = []
    wiki = config.get("wiki")
    if not isinstance(wiki, dict):
        wiki = {}
        config["wiki"] = wiki
    if wiki.get("enabled") is not enabled:
        changes.append({"path": "wiki.enabled", "from": wiki.get("enabled"), "to": enabled})
        wiki["enabled"] = enabled
    if enabled:
        lifecycle = config.get("lifecycle")
        if not isinstance(lifecycle, dict):
            lifecycle = {}
            config["lifecycle"] = lifecycle
        events = lifecycle.get("events")
        if not isinstance(events, dict):
            events = {}
            lifecycle["events"] = events
        for event in CLASSIC_WIKI_SYNC_EVENTS:
            block = events.get(event)
            if not isinstance(block, dict):
                block = {}
                events[event] = block
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


def apply_classic_wiki_dormant(config: dict[str, Any], threshold: int) -> list[dict[str, Any]]:
    """A classic wiki that publishes by itself once `threshold` active records cite a source.

    `enabled` stays false and `activation_mode` becomes `signal` with
    `eligibility.min_sourced_records`; the lifecycle sync flags go on, so the
    record that crosses the threshold publishes the first pages.
    """
    wiki = config.get("wiki") if isinstance(config.get("wiki"), dict) else {}
    before_enabled = wiki.get("enabled")
    changes = [change for change in apply_classic_wiki_enabled(config, True) if change["path"] != "wiki.enabled"]
    wiki = config["wiki"]
    wiki["enabled"] = False
    if before_enabled is not False:
        changes.insert(0, {"path": "wiki.enabled", "from": before_enabled, "to": False})
    if wiki.get("activation_mode") != "signal":
        changes.append({"path": "wiki.activation_mode", "from": wiki.get("activation_mode"), "to": "signal"})
        wiki["activation_mode"] = "signal"
    eligibility = wiki.get("eligibility") if isinstance(wiki.get("eligibility"), dict) else {}
    if eligibility.get("min_sourced_records") != threshold:
        changes.append(
            {
                "path": "wiki.eligibility.min_sourced_records",
                "from": eligibility.get("min_sourced_records"),
                "to": threshold,
            }
        )
        eligibility["min_sourced_records"] = threshold
    wiki["eligibility"] = eligibility
    return changes


def sync_classic_wiki_config(
    root: Path, mode: str, *, disable_classic_wiki: bool, min_sourced_records: int | None = None
) -> dict[str, Any]:
    """Align the classic config that publishes `.kb/wiki/live` with the decision.

    `kb_wiki` enables the classic wiki and its lifecycle sync, or with
    `min_sourced_records` leaves it dormant until that many records cite a
    source; `kb_alone` never turns an enabled classic wiki off unless
    explicitly asked to.
    """
    path = classic_config_path(root)
    display = str(path)
    if not path.is_file():
        return {"action": "skipped", "reason": "classic_config_missing", "path": display}
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError(f"classic config is not a JSON object: {path}")
    before = hashlib.sha256(raw).hexdigest()
    currently_enabled = bool((config.get("wiki") or {}).get("enabled", False)) if isinstance(config.get("wiki"), dict) else False
    if mode == "kb_wiki" and min_sourced_records:
        changes = apply_classic_wiki_dormant(config, min_sourced_records)
    elif mode == "kb_wiki":
        changes = apply_classic_wiki_enabled(config, True)
    elif currently_enabled and not disable_classic_wiki:
        return {
            "action": "kept_enabled",
            "path": display,
            "warning": (
                "classic wiki stays enabled under kb_alone; rerun with "
                "--disable-classic-wiki to turn it off"
            ),
        }
    else:
        changes = apply_classic_wiki_enabled(config, False)
    if not changes:
        return {"action": "unchanged", "path": display, "sha256": before}
    write_json(path, config)
    return {
        "action": "updated",
        "path": display,
        "changes": changes,
        "sha256_before": before,
        "sha256_after": sha256_path(path),
    }


def file_project_scope(root: Path, scope: str) -> dict[str, Any]:
    """Record the user's scope answer as a HOT DECISAO, once per project.

    The wizard is where the user states the scope, so the answer is filed as
    given. An active scope record is reported and left alone: a later change
    is a supersede through `approved-filing` or a proposal.
    """
    try:
        conn = open_classic_kb_readonly(root)
    except FileNotFoundError:
        return {"action": "skipped", "reason": "classic_kb_missing"}
    try:
        existing = conn.execute(
            "SELECT id FROM records WHERE status = 'ATIVO' AND tags_json LIKE ? ORDER BY created_at DESC LIMIT 1",
            (f'%"{PROJECT_SCOPE_TAG}"%',),
        ).fetchone()
    finally:
        conn.close()
    if existing is not None:
        return {"action": "exists", "record_id": existing["id"]}
    domains = [str(item) for item in (load_classic_config(root).get("domains") or [])]
    domain = "product" if "product" in domains or not domains else domains[0]
    title = f"Scope: {scope}"
    cmd = [
        sys.executable,
        str(classic_kb_script(root)),
        "create",
        "--category",
        "DECISAO",
        "--domain",
        domain,
        "--title",
        title if len(title) <= 160 else title[:157] + "...",
        "--content",
        scope,
        "--tier",
        "HOT",
        "--tier-reason",
        "Project scope stated by the user at activation",
        "--confidence",
        "0.95",
        "--source",
        "activation-wizard: user scope answer",
        "--tags",
        PROJECT_SCOPE_TAG,
        "--json",
    ]
    result = run_canonical_command(root, cmd)
    return {"action": "created", "record_id": result.get("id"), "domain": domain}


def run_classic_wiki_sync(root: Path) -> dict[str, Any]:
    try:
        script = classic_kb_script(root)
    except FileNotFoundError as exc:
        return {"action": "skipped", "reason": "classic_entrypoint_missing", "detail": str(exc)}
    proc = subprocess.run(
        [sys.executable, str(script), "wiki-sync", "--json"],
        cwd=str(script.parent),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "action": "failed",
            "returncode": proc.returncode,
            "detail": (proc.stderr or proc.stdout).strip()[:2000],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Older classic runtimes print a plain message when the wiki is off.
        return {"action": "skipped", "reason": "non_json_output", "detail": proc.stdout.strip()[:500]}
    return {
        "action": "skipped" if payload.get("skipped_reason") else "synced",
        "skipped_reason": payload.get("skipped_reason"),
        "written_count": payload.get("written_count", 0),
        "held_back_count": len(payload.get("held_back") or []),
        "total_candidates": payload.get("total_candidates", 0),
    }


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

    existing: dict[str, Any] | None = None
    if config_path(root).is_file():
        loaded = json.loads(config_path(root).read_text(encoding="utf-8"))
        existing = loaded if isinstance(loaded, dict) else None
    decision, decision_action = reconcile_decision(root, decision, explicit_rationale=bool(args.rationale))
    config = merge_config(existing, build_config(root, decision))
    changed_keys = changed_key_paths(existing, config)
    scope = (getattr(args, "scope", None) or "").strip()
    if getattr(args, "scope", None) is not None and not scope:
        raise ValueError("--scope must not be blank; omit it when the user gave no scope")
    # A new KB + Wiki waits for sourced records; an enabled classic wiki stays on.
    wiki_threshold: int | None = None
    sourced_records: int | None = None
    if decision_mode == "kb_wiki":
        requested = getattr(args, "wiki_min_sourced_records", WIKI_DORMANT_MIN_SOURCED_RECORDS)
        if requested < 0:
            raise ValueError("--wiki-min-sourced-records must be 0 or more")
        sourced_records = sourced_record_count(root)
        if requested > 0 and sourced_records < requested and classic_wiki_enabled(root) is not True:
            wiki_threshold = requested
    # Classic first: a malformed classic config aborts before any vNext write.
    classic_sync = sync_classic_wiki_config(
        root,
        decision_mode,
        disable_classic_wiki=bool(getattr(args, "disable_classic_wiki", False)),
        min_sourced_records=wiki_threshold,
    )
    kb_next_root(root).mkdir(parents=True, exist_ok=True)
    write_json(config_path(root), config)
    write_json(decision_path(root), decision)
    append_operation(root, "classic-config-sync", {"sponsor_decision": decision_mode, **classic_sync})
    wiki_sync: dict[str, Any] | None = None
    if decision_mode == "kb_wiki":
        if wiki_threshold is not None:
            wiki_sync = {
                "action": "skipped",
                "reason": "wiki_dormant",
                "min_sourced_records": wiki_threshold,
                "sourced_records": sourced_records,
            }
        elif getattr(args, "no_wiki_sync", False):
            wiki_sync = {"action": "skipped", "reason": "no_wiki_sync_flag"}
        else:
            wiki_sync = run_classic_wiki_sync(root)
        append_operation(root, "classic-wiki-sync", wiki_sync)
    scope_result: dict[str, Any] | None = None
    if scope:
        scope_result = file_project_scope(root, scope)
        append_operation(root, "project-scope", scope_result)
    now_result = write_now(root, config)
    append_operation(
        root,
        "activation-wizard",
        {
            "mode": args.mode,
            "sponsor_decision": decision_mode,
            "recommended_mode": recommended_mode,
            "config_path": str(config_path(root)),
            "decision_path": str(decision_path(root)),
            "decision": decision_action,
            "now": now_result.get("action"),
            "config_merge": {
                "preserved_existing": existing is not None,
                "changed_keys": changed_keys,
            },
            "classic_config_sync": classic_sync.get("action"),
            "classic_wiki_sync": (wiki_sync or {}).get("action"),
            "wiki_min_sourced_records": wiki_threshold,
            "project_scope": (scope_result or {}).get("action"),
        },
    )
    try:
        ensure_telemetry_ignore(root)
    except OSError:
        pass  # the first telemetry append writes it instead
    result = {
        "event": "activation-wizard",
        "activation": decision,
        "decision": decision_action,
        "now": now_result,
        "config_merge": {
            "preserved_existing": existing is not None,
            "changed_keys": changed_keys,
        },
        "classic_config_sync": classic_sync,
        "classic_wiki_sync": wiki_sync,
        "wiki_dormant": wiki_dormancy(root, config),
        "project_scope": scope_result,
        "paths": {
            "config": str(config_path(root)),
            "decision": str(decision_path(root)),
            "operations": str(operations_path(root)),
            "telemetry": str(telemetry_path(root)),
            "now": str(now_path(root)),
            "classic_config": str(classic_config_path(root)),
        },
    }
    if args.json:
        emit(result, True)
    else:
        label = "KB + Wiki" if decision_mode == "kb_wiki" else "KB alone"
        lines = [
            f"Activation recorded: {label}",
            f"Config: {config_path(root)}",
            f"Classic config sync: {classic_sync.get('action')}",
        ]
        if wiki_sync is not None:
            lines.append(f"Classic wiki sync: {wiki_sync.get('action')}")
        if result["wiki_dormant"]:
            dormant = result["wiki_dormant"]
            lines.append(
                f"Wiki dormant until {dormant['min_sourced_records']} active records cite a registered source "
                f"(now {dormant['sourced_records']})"
            )
        if scope_result is not None:
            lines.append(f"Project scope: {scope_result.get('action')} {scope_result.get('record_id') or ''}".rstrip())
        if classic_sync.get("warning"):
            lines.append(f"Warning: {classic_sync['warning']}")
        emit("\n".join(lines), False)
    return 0


def wiki_alignment(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    vnext_enabled = bool(config["wiki"]["enabled"])
    classic_enabled = classic_wiki_enabled(root)
    status = "aligned"
    hint = None
    dormant = wiki_dormancy(root, config) if vnext_enabled else None
    if dormant is not None:
        status = "dormant"
    elif vnext_enabled and classic_enabled is False and classic_wiki_sourced_threshold(root) is not None:
        status = "aligned"  # the classic wiki publishes by signal now that the threshold is met
    elif vnext_enabled and classic_enabled is False:
        status = "classic_wiki_off"
        hint = (
            "KB + Wiki is active but the classic wiki is off; rerun "
            "`activation-wizard --mode short --choice kb-wiki` to sync .kb/kb.config.json"
        )
    elif not vnext_enabled and classic_enabled:
        status = "classic_wiki_independent"
        hint = "classic wiki is enabled independently of the vNext kb_alone decision"
    elif classic_enabled is None:
        status = "classic_config_missing"
    result = {
        "vnext_wiki_enabled": vnext_enabled,
        "classic_wiki_enabled": classic_enabled,
        "status": status,
        "hint": hint,
    }
    if dormant is not None:
        result["dormant"] = dormant
    return result


def cmd_session_start(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    # A dormant wiki has no pages and no drafts yet: start like KB alone.
    wiki_enabled = bool(config["wiki"]["enabled"]) and wiki_dormancy(root, config) is None
    classic_root = classic_kb_root(root)
    paths = {
        "now": str(now_path(root)),
        "classic_now": str(classic_root / "memory" / "NOW.md"),
        "classic_hot": str(classic_root / "memory" / "HOT.md"),
        "classic_index": str(classic_root / "memory" / "INDEX.md"),
    }
    if wiki_enabled:
        paths["wiki_index"] = str(root / ".kb-next" / "wiki" / "index.md")
        paths["classic_wiki_live"] = str(classic_root / "wiki" / "live")
    result = {
        "event": "session-start",
        "generated_at": now_iso(),
        "activation_mode": config["activation"]["sponsor_decision"],
        "classic_kb_mode": config["classic_kb"]["mode"],
        "classic_kb": classic_kb_resolution(root),
        "default_reads": config["session_start"]["default_reads"],
        "required_read_paths": [paths["now"]],
        "on_demand_reads": config["session_start"]["on_demand_reads"],
        "historical_artifact_allowed_reasons": config["session_start"][
            "historical_artifact_allowed_reasons"
        ],
        "paths": paths,
        "wiki": wiki_alignment(root, config),
        "actions_run": ["read_kb_next_config", "emit_thin_contract"],
    }
    if wiki_enabled:
        status = build_wiki_draft_status(root, config)
        result["wiki_drafts"] = status["counts"]
        result["actions_run"].append("wiki_draft_status")
    append_telemetry(
        root,
        "session-start",
        {
            "activation_mode": result["activation_mode"],
            "default_reads": result["default_reads"],
            "on_demand_reads": result["on_demand_reads"],
            "wiki_status": result["wiki"]["status"],
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
        if result["wiki"]["hint"]:
            lines.append(f"Wiki: {result['wiki']['hint']}")
        if "wiki_drafts" in result:
            counts = result["wiki_drafts"]
            lines.append(
                "Wiki drafts: "
                f"{counts['needs_synthesis']} to synthesize, {counts['needs_review']} to review, "
                f"{counts['stale']} stale"
            )
        emit("\n".join(lines), False)
    return 0


def open_classic_kb_readonly(root: Path) -> sqlite3.Connection:
    db_path = classic_kb_root(root) / "kb.db"
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
    stored_path = resolve_source_file(root, source)
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
        "products/kb-wiki-vnext/product.json",
        "products/kb-wiki-vnext/README.md",
        "products/kb-wiki-vnext/docs/en/architecture.md",
        "products/kb-wiki-vnext/docs/en/maintainer-release.md",
        "docs/development.md",
        "docs/releasing.md",
        "tests/test_kb_wiki_vnext_runtime.py",
        "tests/test_vnext_runtime_parity.py",
    ]
    extras = {
        "implementation": [
            "core/versions/kb-wiki-vnext/runtime/kb_next.py",
            "tests/test_kb_wiki_vnext_semantic_runtime.py",
            "tests/test_vnext_pip_channel.py",
        ],
        "review": [
            "products/kb-wiki-vnext/docs/en/usage-guide.md",
            "tests/test_kb_wiki_vnext_semantic_runtime.py",
        ],
        "release": [
            "products/kb-wiki-vnext/docs/en/admin-installation.md",
            "products/kb-wiki-vnext/docs/en/upgrade-rollback.md",
            "tests/test_vnext_runtime_shipping.py",
        ],
        "track-b": [
            "docs/provenance-and-continuity.md",
            "products/kb-wiki-vnext/docs/en/architecture.md",
        ],
        "packaging": [
            "plugins/kb-wiki-vnext/AGENTS.md",
            "plugins/kb-wiki-vnext/skills/kb-wiki-vnext/SKILL.md",
            "tests/test_vnext_runtime_shipping.py",
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
        "python tools\\sync_vnext_runtime.py --check",
        "python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_vnext_compliance tests\\test_kb_wiki_vnext_runtime.py tests\\test_kb_wiki_vnext_semantic_runtime.py tests\\test_vnext_runtime_parity.py tests\\test_vnext_pip_channel.py tests\\test_vnext_runtime_shipping.py -q",
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
        "Map the requested work to the public product manifest, maintainer release guide, and focused test surface.",
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
        "Public product manifest, architecture, and maintainer release surfaces agree on the release contract.",
        "vNext runtime mirrors pass python tools\\sync_vnext_runtime.py --check.",
        "Public vNext pytest suite green.",
        "Required pilots completed or owner-waived.",
        f"{SOURCE_LINKAGE_TRACK_B_BLOCKER_ID} resolved or explicitly waived for Track B.",
        "Release decision and evidence are recorded through the approved public release process.",
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
            else "Proceed only with the listed public release mapping, traceability, tests, and evidence."
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
            ["Development Compliance Contract", "Public Product Manifest", "Public Documentation/Authority", "Runtime/Test Parity"]
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
    if is_junction and is_junction():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


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
    if not path_within(vault_resolved, adapter_resolved):
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


# ---------------------------------------------------------------------------
# Retrieval (E1.1): ranked lists fused by RRF; LIKE only as explicit fallback.
#
# A ranked lookup builds throwaway FTS5 tables in the connection's temp schema
# from the candidate rows, so the classic kb.db stays read-only and vNext owns
# no index that could go stale. Measured with SQLite 3.50 on 2026-10-17: the
# 185 live workbench records index in about 6 ms (words) plus 22 ms (trigram);
# 20,000 synthetic records of 130 words take 1.3 s and 19 s. A KB past a few
# thousand records needs a persistent index under .kb-next/ instead.
#
# The trigram list is opt-in, not a default list: fused at any weight from 0.1
# to 1 it changed no answer on the E1.0 ruler and lowered LongMemEval recall
# (docs/benchmarks/longmemeval/README.md).
# ---------------------------------------------------------------------------

RRF_K = 60
# Best first; each fallback drops one capability an older SQLite lacks.
WORD_TOKENIZERS = ("unicode61 remove_diacritics 2", "unicode61")
TRIGRAM_TOKENIZERS = ("trigram remove_diacritics 1", "trigram")  # SQLite 3.45+, 3.34+
INDEXED_COLUMNS = ("title", "content", "tags_json", "source", "domain")
# Implicit prefix matching starts at this many characters; shorter stems match too much.
PREFIX_MIN_CHARS = 3
# Each list returns this many times the requested limit before fusion.
RANK_DEPTH_FACTOR = 3
# Written plural rules over accent-folded text (PT and EN), not a stemmer.
PLURAL_ENDINGS = (("oes", "ao"), ("ais", "al"), ("eis", "el"), ("ies", "y"), ("ns", "m"))
ES_PLURAL_STEMS = ("r", "z", "s", "x", "sh", "ch")
DEFINITION_TAGS_CLAUSE = (
    "(tags_json LIKE '%definition%' OR tags_json LIKE '%definitions%' OR "
    "tags_json LIKE '%glossary%' OR tags_json LIKE '%glossario%' OR "
    "tags_json LIKE '%definicao%' OR tags_json LIKE '%definição%')"
)

_FTS5_TOKENIZERS: dict[str, str | None] | None = None


def fts5_tokenizers() -> dict[str, str | None]:
    """Return the best word and trigram tokenizers the host SQLite accepts.

    Probes by creating a table, not by parsing the version: FTS5 is a compile
    option, and tokenizer arguments arrived in different releases.
    """
    global _FTS5_TOKENIZERS
    if _FTS5_TOKENIZERS is None:
        found: dict[str, str | None] = {"words": None, "trigram": None}
        conn = sqlite3.connect(":memory:")
        try:
            for name, candidates in (("words", WORD_TOKENIZERS), ("trigram", TRIGRAM_TOKENIZERS)):
                for tokenizer in candidates:
                    try:
                        conn.execute(f"CREATE VIRTUAL TABLE temp.probe USING fts5(x, tokenize='{tokenizer}')")
                    except sqlite3.OperationalError:
                        continue
                    conn.execute("DROP TABLE temp.probe")
                    found[name] = tokenizer
                    break
        finally:
            conn.close()
        _FTS5_TOKENIZERS = found
    return dict(_FTS5_TOKENIZERS)


def fold_text(value: str) -> str:
    """Casefold and strip accents, as `unicode61 remove_diacritics 2` does."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def singular_stems(folded: str) -> list[str]:
    """Return singular stems of a folded word that looks plural."""
    stems = [folded[: -len(end)] + singular for end, singular in PLURAL_ENDINGS if folded.endswith(end)]
    if folded.endswith("es") and folded[:-2].endswith(ES_PLURAL_STEMS):
        stems.append(folded[:-2])
    if folded.endswith("s") and not folded.endswith("ss"):
        stems.append(folded[:-1])
    return [stem for stem in dict.fromkeys(stems) if stem != folded and len(stem) >= PREFIX_MIN_CHARS]


def parse_query_terms(query: str) -> list[dict[str, Any]]:
    """Split a lookup query into literal terms; FTS5 operators are never parsed.

    A trailing `*` asks for a prefix; terms of PREFIX_MIN_CHARS or more get one
    anyway, so "worktree" also finds "worktrees". Plural terms add their
    singular stems, so "snapshots" also finds "snapshot".
    """
    terms = []
    for raw in query.split():
        text = raw.rstrip("*")
        if not any(char.isalnum() for char in text):
            continue
        folded = fold_text(text)
        core = re.sub(r"^\W+|\W+$", "", folded)
        terms.append(
            {
                "text": text,
                "prefix": text != raw or len(folded) >= PREFIX_MIN_CHARS,
                "stems": singular_stems(core),
            }
        )
    return terms


def fts5_phrase(text: str) -> str:
    """Quote text as one FTS5 phrase, so `-`, `.` and keywords stay literal."""
    return '"' + text.replace('"', '""') + '"'


def words_match_expression(terms: list[dict[str, Any]]) -> str:
    """OR every term group: BM25 ranks records matching more terms first.

    OR, not AND, so an agent can widen a query with its own synonyms. The exact
    phrase is kept beside its prefix, so an exact hit outscores "gate"* -> "gateway".
    """
    groups = []
    for term in terms:
        options = [fts5_phrase(term["text"])]
        if term["prefix"]:
            options.append(fts5_phrase(term["text"]) + "*")
        options.extend(fts5_phrase(stem) + "*" for stem in term["stems"])
        groups.append("(" + " OR ".join(options) + ")")
    return " OR ".join(groups)


def trigram_match_expression(terms: list[dict[str, Any]]) -> str | None:
    """OR substring phrases of three or more characters; None when none qualifies."""
    options: list[str] = []
    for term in terms:
        for text in (term["text"], fold_text(term["text"]), *term["stems"]):
            if len(text) >= 3:
                options.append(fts5_phrase(text))
    return " OR ".join(dict.fromkeys(options)) or None


def fts5_ranked_ids(
    conn: sqlite3.Connection,
    table: str,
    tokenizer: str,
    expression: str,
    where: str,
    params: list[Any],
    depth: int,
) -> list[str]:
    """Index the candidate rows in a temp FTS5 table and return ids by BM25."""
    columns = ", ".join(INDEXED_COLUMNS)
    values = ", ".join("COALESCE(" + column + ", '')" for column in INDEXED_COLUMNS)
    conn.execute(f"DROP TABLE IF EXISTS temp.{table}")
    conn.execute(
        f"CREATE VIRTUAL TABLE temp.{table} USING fts5("
        f"id UNINDEXED, updated_at UNINDEXED, {columns}, tokenize='{tokenizer}')"
    )
    try:
        conn.execute(
            f"INSERT INTO temp.{table}(id, updated_at, {columns}) "
            f"SELECT id, updated_at, {values} FROM main.records WHERE {where}",
            params,
        )
        rows = conn.execute(
            f"SELECT id FROM temp.{table} WHERE {table} MATCH ? "
            f"ORDER BY bm25({table}), updated_at DESC, id LIMIT ?",
            (expression, depth),
        ).fetchall()
    finally:
        conn.execute(f"DROP TABLE IF EXISTS temp.{table}")
    return [row[0] for row in rows]


def words_list_provider(request: dict[str, Any]) -> list[str] | None:
    expression = words_match_expression(request["terms"])
    return fts5_ranked_ids(
        request["conn"], "lookup_words", request["tokenizers"]["words"], expression,
        request["where"], request["params"], request["depth"],
    )


def trigram_list_provider(request: dict[str, Any]) -> list[str] | None:
    """Substring list, opt-in through `rank_record_ids(..., providers=...)`.

    It finds a fragment inside a word ("atewa" in "gateway"), which no word
    list reaches; None when the host SQLite has no trigram tokenizer (3.34+).
    """
    tokenizer = request["tokenizers"].get("trigram")
    expression = trigram_match_expression(request["terms"])
    if tokenizer is None or expression is None:
        return None
    return fts5_ranked_ids(
        request["conn"], "lookup_trigram", tokenizer, expression,
        request["where"], request["params"], request["depth"],
    )


def default_ranked_list_providers(tokenizers: dict[str, str | None]) -> list[tuple[str, Any]]:
    """Name and provider of every ranked list a lookup fuses.

    A provider takes the request dict (`conn`, `query`, `terms`, `where`,
    `params`, `depth`, `tokenizers`) and returns record ids best first, or
    None when it does not apply to the query. `where` is an SQL predicate over
    `records` that every list must honor. The dense list of E4.6 joins here.

    Only the word list is a default. Fusing the trigram list at weight 1 cost
    LongMemEval M session recall@5 and recall@10 6.0 and 3.1 points, and every
    lower weight tried on S still trailed the word list alone.
    """
    return [("words", words_list_provider)]


def rrf_fuse(ranked_lists: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(id) = sum over lists of 1 / (k + rank).

    Ranks start at 1 and a list counts an id once, at its best rank. Ties break
    by the best rank in any list, then by first appearance across the lists in
    order, so equal inputs always give the same order.
    """
    if k < 1:
        raise ValueError("RRF k must be a positive integer")
    contributions: dict[str, list[float]] = {}
    best_rank: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for ranked in ranked_lists:
        seen: set[str] = set()
        for rank, item in enumerate(ranked, start=1):
            if item in seen:
                continue
            seen.add(item)
            contributions.setdefault(item, []).append(1.0 / (k + rank))
            best_rank[item] = min(best_rank.get(item, rank), rank)
            first_seen.setdefault(item, len(first_seen))
    scores = {item: math.fsum(values) for item, values in contributions.items()}
    return sorted(scores.items(), key=lambda pair: (-pair[1], best_rank[pair[0]], first_seen[pair[0]]))


def sql_like(value: str) -> str:
    return f"%{value}%"


def like_fallback_ids(conn: sqlite3.Connection, query: str, where: str, params: list[Any], limit: int) -> list[str]:
    """Unranked substring match, used only when the host SQLite has no FTS5."""
    like = sql_like(query)
    match = " OR ".join(f"{column} LIKE ?" for column in INDEXED_COLUMNS)
    sql = f"SELECT id FROM records WHERE {where} AND ({match}) {order_clause()} LIMIT ?"
    return [row[0] for row in conn.execute(sql, [*params, *([like] * len(INDEXED_COLUMNS)), limit])]


def rank_record_ids(
    conn: sqlite3.Connection,
    query: str,
    where: str,
    params: list[Any],
    limit: int,
    providers: list[tuple[str, Any]] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Return up to `limit` record ids best first, plus the retrieval report."""
    tokenizers = fts5_tokenizers()
    version = sqlite3.sqlite_version
    info: dict[str, Any] = {
        "method": "fts5_rrf",
        "lists": [],
        "fusion": {"method": "rrf", "k": RRF_K},
        "tokenizers": tokenizers,
        "fallback": None,
        "warnings": [],
    }
    if tokenizers["words"] is None:
        info.update(method="like_fallback", fusion=None, fallback="fts5_unavailable")
        info["warnings"].append(f"SQLite {version} has no FTS5: unranked LIKE substring fallback")
        return like_fallback_ids(conn, query, where, params, limit), info
    if tokenizers["words"] != WORD_TOKENIZERS[0]:
        info["warnings"].append(f"SQLite {version} lacks remove_diacritics 2: some accents may not fold")
    terms = parse_query_terms(query)
    if not terms:
        info["warnings"].append("query has no searchable terms")
        return [], info
    request = {
        "conn": conn,
        "query": query,
        "terms": terms,
        "where": where,
        "params": list(params),
        "depth": max(limit, 1) * RANK_DEPTH_FACTOR,
        "tokenizers": tokenizers,
        # Providers append here what the caller should know (e.g. a stale dense index).
        "warnings": info["warnings"],
    }
    if providers is None:
        providers = default_ranked_list_providers(tokenizers)
    ranked_lists = []
    for name, provider in providers:
        ranked = provider(request)
        if ranked is None:
            continue
        info["lists"].append(name)
        ranked_lists.append(ranked)
    if not ranked_lists and providers:
        info["warnings"].append("no requested ranked list applied; ranked by the word list")
        info["lists"].append("words")
        ranked_lists.append(words_list_provider(request))
    return [item for item, _score in rrf_fuse(ranked_lists)][:limit], info


# ---------------------------------------------------------------------------
# Dense list (E4.6): an optional meaning-based list fused by RRF with the words.
#
# Off by default and outside the stdlib core. The extra is `pip install
# model2vec==0.10.0`, which brings numpy, tokenizers, safetensors,
# huggingface-hub, jinja2, joblib and tqdm (no torch). The runtime imports it
# only when a lookup or `dense-index` asks for the dense list; without it a
# lookup ranks by words and says why. Vectors live in a derived index under
# .kb-next/index/dense/ that `dense-index` rebuilds from the classic records at
# any time; .kb/kb.db is only read. Model files are pinned by revision and
# SHA-256 and cached outside the project.
#
# A record is split into passages of `chunk_words` words over its title,
# content and tags, and scores the best cosine among its passages. On
# LongMemEval M, one vector per long record lost to the word list, while
# 32-word passages fused with it reached the decision 6 target
# (docs/benchmarks/longmemeval/README.md).
# ---------------------------------------------------------------------------

DENSE_INDEX_REL = Path(".kb-next") / "index" / "dense"
# .kb-next/ is versioned in projects; the derived index must never be.
DENSE_INDEX_GITIGNORE = "# Derived by kb_next.py dense-index: regenerate it, never commit it.\n*\n"
DENSE_MANIFEST_NAME = "manifest.json"
DENSE_VECTORS_NAME = "vectors.sqlite3"
DENSE_INDEX_SCHEMA = "kb-wiki-vnext/dense-index/v1"
DENSE_EXTRA_REQUIREMENT = "model2vec==0.10.0"
DENSE_MODEL_CACHE_ENV = "KBF_MODEL_CACHE"
DENSE_MODEL_URL = "https://huggingface.co/{repo}/resolve/{revision}/{file}"
# File sizes and SHA-256 of the file contents at the pinned revision, read on
# 2026-10-19 and re-checked before a model is used.
DENSE_MODELS: dict[str, dict[str, Any]] = {
    "potion-base-32M": {
        "repo": "minishlab/potion-base-32M",
        "revision": "1e5a03f8eeb2c98b928fbbd846f22f816360919f",
        "license": "MIT",
        "languages": "English",
        "files": {
            "config.json": (202, "63c00d90824c832c04ec1d02b6a983fb90489bf049f29fbff15ba481b8a432ee"),
            "model.safetensors": (129210456, "99f6c33204c9231a7391871b7a3c91409b532c8f587a9ea44fc282303d8dec28"),
            "tokenizer.json": (1493150, "7d75cbc54318138807c401b0f0c9721117c628b39de8e8e0edb6cb17e0ee7d18"),
        },
    },
    "potion-multilingual-128M": {
        "repo": "minishlab/potion-multilingual-128M",
        "revision": "73908c3438cf03b6a01bcb9611d62b23d0726f08",
        "license": "MIT",
        "languages": "multilingual, Portuguese included",
        # Kept pinned until 0.3 so existing indexes still load; see dense_model_advisory.
        "recommended": False,
        "advisory": (
            "costs about 11.7 s per cold CLI lookup against 0.5 s words-only, and query expansion "
            "by the agent reaches the same Portuguese synonyms at no cost; prefer potion-base-32M or "
            "words only (docs/benchmarks/kb-value/README.md)"
        ),
        "files": {
            "config.json": (271, "595e4cab2093732efd5dbe084fd5c1826b5eea693b73b4c1fd971672867d2e54"),
            "model.safetensors": (512361560, "14b5eb39cb4ce5666da8ad1f3dc6be4346e9b2d601c073302fa0a31bf7943397"),
            "tokenizer.json": (18616131, "19f1909063da3cfe3bd83a782381f040dccea475f4816de11116444a73e1b6a1"),
        },
    },
}
DENSE_DEFAULTS: dict[str, Any] = {"enabled": False, "model": "potion-base-32M", "chunk_words": 32, "chunk_stride": 32}
RANKED_LIST_NAMES = ("words", "trigram", "dense")
# Candidate ids per `IN (...)` read of the vector index, under SQLite's variable limit.
DENSE_READ_BATCH = 500
# Records embedded per model call while building, to bound memory on a large KB.
DENSE_BUILD_BATCH = 1000

_DENSE_EMBEDDERS: dict[str, Any] = {}
_VERIFIED_MODEL_DIRS: set[str] = set()


class DenseUnavailable(RuntimeError):
    """The dense list cannot run here; the message says what to do."""


def dense_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    """`retrieval.dense` from the config over DENSE_DEFAULTS, validated."""
    settings = dict(DENSE_DEFAULTS)
    retrieval = config.get("retrieval") if isinstance(config, dict) else None
    raw = retrieval.get("dense") if isinstance(retrieval, dict) else None
    if isinstance(raw, dict):
        settings.update({key: raw[key] for key in DENSE_DEFAULTS if key in raw})
    if settings["model"] not in DENSE_MODELS:
        raise ValueError(f"retrieval.dense.model must be one of {sorted(DENSE_MODELS)}, got {settings['model']!r}")
    width, stride = settings["chunk_words"], settings["chunk_stride"]
    if not (isinstance(width, int) and isinstance(stride, int) and 1 <= stride <= width):
        raise ValueError("retrieval.dense needs integers 1 <= chunk_stride <= chunk_words")
    settings["enabled"] = settings["enabled"] is True
    return settings


def dense_model_advisory(name: str) -> str | None:
    """The warning for a pinned model marked not recommended; None for the others."""
    spec = DENSE_MODELS.get(name) or {}
    if spec.get("recommended", True):
        return None
    return f"dense model {name} is not recommended: {spec['advisory']}"


def dense_model_cache(root: Path) -> Path:
    """Model cache outside the project: $KBF_MODEL_CACHE or ~/.cache/kb-factory/models."""
    raw = os.environ.get(DENSE_MODEL_CACHE_ENV)
    base = (Path(raw).expanduser() if raw else Path.home() / ".cache" / "kb-factory" / "models").resolve()
    project = root.resolve()
    if base == project or project in base.parents:
        raise DenseUnavailable(f"the model cache must live outside the project, so models stay out of Git: {base}")
    return base


def dense_model_dir(root: Path, name: str) -> Path:
    spec = DENSE_MODELS[name]
    return dense_model_cache(root) / spec["repo"].replace("/", "--") / spec["revision"]


def sha256_file_streaming(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dense_model_problems(directory: Path, name: str) -> list[str]:
    """What keeps the cached files from matching the pinned model; [] when they match."""
    if str(directory) in _VERIFIED_MODEL_DIRS:
        return []
    problems = []
    for file, (size, digest) in DENSE_MODELS[name]["files"].items():
        path = directory / file
        if not path.is_file():
            problems.append(f"{file} is missing")
        elif path.stat().st_size != size:
            problems.append(f"{file} has {path.stat().st_size} bytes, pinned {size}")
        elif sha256_file_streaming(path) != digest:
            problems.append(f"{file} differs from the pinned SHA-256")
    if not problems:
        _VERIFIED_MODEL_DIRS.add(str(directory))
    return problems


def fetch_dense_model(directory: Path, name: str) -> list[str]:
    """Download the pinned files that are missing or wrong; return their names."""
    spec = DENSE_MODELS[name]
    directory.mkdir(parents=True, exist_ok=True)
    fetched = []
    for file, (size, digest) in spec["files"].items():
        target = directory / file
        if target.is_file() and target.stat().st_size == size and sha256_file_streaming(target) == digest:
            continue
        url = DENSE_MODEL_URL.format(repo=spec["repo"], revision=spec["revision"], file=file)
        partial = target.with_name(file + ".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
                shutil.copyfileobj(response, handle, 1 << 20)
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise DenseUnavailable(f"download of {url} failed: {exc}") from exc
        if sha256_file_streaming(partial) != digest:
            partial.unlink(missing_ok=True)
            raise DenseUnavailable(f"{url} does not match the pinned SHA-256; nothing was installed")
        os.replace(partial, target)
        fetched.append(file)
    _VERIFIED_MODEL_DIRS.discard(str(directory))
    return fetched


def import_dense_extra() -> tuple[Any, Any]:
    """Import the optional dense extra (numpy, model2vec) on demand.

    The one place the runtime reaches past the standard library, and only when
    the dense list is asked for. tests/test_dev_requirements.py keeps every
    other import in this file inside the stdlib and pins these two names.
    """
    try:
        numpy = importlib.import_module("numpy")
        model2vec = importlib.import_module("model2vec")
    except ImportError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        raise DenseUnavailable(
            f"the dense extra is not installed ({missing}); install it with: pip install {DENSE_EXTRA_REQUIREMENT}"
        ) from None
    return numpy, model2vec


class Model2VecEmbedder:
    """Unit-length little-endian float32 vectors from a pinned model2vec model."""

    def __init__(self, name: str, directory: Path) -> None:
        numpy, model2vec = import_dense_extra()
        self.numpy = numpy
        self.name = name
        self.model = model2vec.StaticModel.from_pretrained(str(directory), normalize=True, max_length=None)
        self.dim = int(self.model.dim)
        self.library = f"model2vec {getattr(model2vec, '__version__', 'unknown')}, numpy {numpy.__version__}"

    def embed(self, texts: list[str]) -> list[bytes]:
        if not texts:
            return []
        numpy = self.numpy
        vectors = numpy.asarray(self.model.encode(texts, batch_size=1024, show_progress_bar=False), dtype="<f4")
        norms = numpy.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = (vectors / numpy.maximum(norms, 1e-12)).astype("<f4")
        return [row.tobytes() for row in vectors]


def load_dense_embedder(root: Path, settings: dict[str, Any]) -> Any:
    """The embedder for `settings["model"]`, loaded once per process.

    An embedder has `name`, `dim`, `library` and `embed(texts) -> list[bytes]`
    of unit-length little-endian float32 vectors; tests inject a stub here.
    """
    name = settings["model"]
    directory = dense_model_dir(root, name)
    if str(directory) not in _DENSE_EMBEDDERS:
        import_dense_extra()
        problems = dense_model_problems(directory, name)
        if problems:
            raise DenseUnavailable(
                f"model {name} is not ready in {directory} ({problems[0]}); "
                "download it with: kb_next.py dense-index --fetch-model"
            )
        _DENSE_EMBEDDERS[str(directory)] = Model2VecEmbedder(name, directory)
    return _DENSE_EMBEDDERS[str(directory)]


def dense_key_text(title: str | None, content: str | None, tags_json: Any) -> str:
    """The text a record is embedded from: title, content and tags."""
    tags = " ".join(str(tag) for tag in json_list(tags_json))
    return "\n".join(part for part in (title or "", content or "", tags) if part)


def dense_passages(text: str, width: int, stride: int) -> list[str]:
    """Windows of `width` words every `stride` words, the last one ending at the last word."""
    words = text.split()
    if len(words) <= width:
        return [" ".join(words)]
    starts = [*range(0, len(words) - width, stride), len(words) - width]
    return [" ".join(words[start : start + width]) for start in starts]


def dense_index_paths(root: Path) -> tuple[Path, Path]:
    directory = root / DENSE_INDEX_REL
    return directory / DENSE_MANIFEST_NAME, directory / DENSE_VECTORS_NAME


def dense_index_identity(settings: dict[str, Any], dim: int) -> dict[str, Any]:
    """What a stored index must match to serve a lookup under `settings`."""
    spec = DENSE_MODELS[settings["model"]]
    return {
        "model": settings["model"],
        "repo": spec["repo"],
        "revision": spec["revision"],
        "files_sha256": {file: digest for file, (_size, digest) in sorted(spec["files"].items())},
        "dim": dim,
        "key_fields": ["title", "content", "tags"],
        "chunk_words": settings["chunk_words"],
        "chunk_stride": settings["chunk_stride"],
        "score": "max cosine over passages",
        "vector_format": "float32 little-endian, unit length",
    }


def read_dense_manifest(root: Path) -> dict[str, Any] | None:
    manifest_path, vectors_path = dense_index_paths(root)
    if not (manifest_path.is_file() and vectors_path.is_file()):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("schema") != DENSE_INDEX_SCHEMA:
        return None
    return manifest


def open_dense_vectors(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    # A derived, regenerable file: skip the fsyncs, keep the rollback journal.
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dense_vectors ("
        "record_id TEXT PRIMARY KEY, key_sha256 TEXT NOT NULL, "
        "passages INTEGER NOT NULL, vectors BLOB NOT NULL)"
    )
    return conn


def build_dense_index(root: Path, settings: dict[str, Any], rebuild: bool = False) -> dict[str, Any]:
    """Embed every active record into .kb-next/index/dense/; reuse unchanged ones."""
    embedder = load_dense_embedder(root, settings)
    identity = dense_index_identity(settings, embedder.dim)
    manifest_path, vectors_path = dense_index_paths(root)
    previous = read_dense_manifest(root)
    if rebuild or previous is None or previous.get("identity") != identity:
        for path in (manifest_path, vectors_path):
            path.unlink(missing_ok=True)
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    ignore = vectors_path.parent.parent / ".gitignore"
    if not ignore.is_file():
        ignore.write_bytes(DENSE_INDEX_GITIGNORE.encode("utf-8"))
    source = open_classic_kb_readonly(root)
    try:
        rows = source.execute("SELECT id, title, content, tags_json FROM records WHERE status = 'ATIVO' ORDER BY id").fetchall()
    finally:
        source.close()
    index = open_dense_vectors(vectors_path)
    try:
        stored = dict(index.execute("SELECT record_id, key_sha256 FROM dense_vectors"))
        texts = {row[0]: dense_key_text(row[1], row[2], row[3]) for row in rows}
        wanted = {record_id: sha256_text(text) for record_id, text in texts.items()}
        stale = [record_id for record_id in stored if wanted.get(record_id) != stored[record_id]]
        todo = [record_id for record_id in wanted if stored.get(record_id) != wanted[record_id]]
        embedded_passages = 0
        with index:
            index.executemany("DELETE FROM dense_vectors WHERE record_id = ?", [(record_id,) for record_id in stale])
            for start in range(0, len(todo), DENSE_BUILD_BATCH):
                owners = []
                passages: list[str] = []
                for record_id in todo[start : start + DENSE_BUILD_BATCH]:
                    chunks = dense_passages(texts[record_id], settings["chunk_words"], settings["chunk_stride"])
                    owners.append((record_id, len(chunks)))
                    passages.extend(chunks)
                vectors = embedder.embed(passages)
                embedded_passages += len(passages)
                ends = [*itertools.accumulate(count for _record_id, count in owners)]
                index.executemany(
                    "INSERT OR REPLACE INTO dense_vectors VALUES (?, ?, ?, ?)",
                    [
                        (record_id, wanted[record_id], count, b"".join(vectors[end - count : end]))
                        for (record_id, count), end in zip(owners, ends)
                    ],
                )
        totals = index.execute("SELECT count(*), COALESCE(sum(passages), 0) FROM dense_vectors").fetchone()
    finally:
        index.close()
    manifest = {
        "schema": DENSE_INDEX_SCHEMA,
        "runtime_version": RUNTIME_VERSION,
        "identity": identity,
        "library": embedder.library,
        "source": {"classic_kb": ".kb/kb.db", "filter": "status = 'ATIVO'", "access": "read_only"},
        "records": totals[0],
        "passages": totals[1],
        "built_at": now_iso(),
        "derived": "regenerable with kb_next.py dense-index --rebuild; safe to delete",
    }
    write_json(manifest_path, manifest)
    return {
        "records": totals[0],
        "passages": totals[1],
        "embedded_records": len(todo),
        "embedded_passages": embedded_passages,
        "reused_records": len(rows) - len(todo),
        "removed_records": len([record_id for record_id in stale if record_id not in wanted]),
        "manifest": manifest,
    }


def dense_record_scores(blobs: list[tuple[str, int, bytes]], query: bytes, dim: int) -> dict[str, float]:
    """Best passage cosine per record; numpy when present, else plain Python.

    Vectors are unit length, so the cosine is the dot product.
    """
    if not blobs:
        return {}
    try:
        numpy = importlib.import_module("numpy")
    except ImportError:
        numpy = None
    if numpy is not None:
        matrix = numpy.frombuffer(b"".join(blob for _id, _count, blob in blobs), dtype="<f4").reshape(-1, dim)
        sims = matrix @ numpy.frombuffer(query, dtype="<f4")
        offsets = numpy.cumsum([0] + [count for _id, count, _blob in blobs[:-1]])
        best = numpy.maximum.reduceat(sims, offsets)
        return {record_id: float(score) for (record_id, _count, _blob), score in zip(blobs, best)}
    q = array("f")
    q.frombytes(query)
    if sys.byteorder == "big":
        q.byteswap()
    scores = {}
    for record_id, count, blob in blobs:
        values = array("f")
        values.frombytes(blob)
        if sys.byteorder == "big":
            values.byteswap()
        scores[record_id] = max(
            math.fsum(a * b for a, b in zip(values[i * dim : (i + 1) * dim], q)) for i in range(count)
        )
    return scores


def make_dense_list_provider(root: Path, settings: dict[str, Any]) -> Any:
    """The dense ranked list over the derived index, for `rank_record_ids`.

    Returns None, with a warning, when the extra, the model or the index is not
    ready; records filed or edited after the last `dense-index` are left out
    of this list (the word list still sees them) and counted in a warning.
    """

    advisory = dense_model_advisory(settings["model"])

    def dense_list_provider(request: dict[str, Any]) -> list[str] | None:
        warnings = request["warnings"]
        if advisory:
            warnings.append(advisory)
        manifest = read_dense_manifest(root)
        if manifest is None:
            warnings.append("dense list skipped: no dense index; build it with: kb_next.py dense-index")
            return None
        try:
            embedder = load_dense_embedder(root, settings)
        except DenseUnavailable as exc:
            warnings.append(f"dense list skipped: {exc}")
            return None
        if manifest.get("identity") != dense_index_identity(settings, embedder.dim):
            warnings.append("dense list skipped: the dense index was built with other settings; rebuild it with: kb_next.py dense-index")
            return None
        conn = request["conn"]
        candidates = conn.execute(
            f"SELECT id, title, content, tags_json FROM main.records WHERE {request['where']}", request["params"]
        ).fetchall()
        key_of = {row[0]: sha256_text(dense_key_text(row[1], row[2], row[3])) for row in candidates}
        ids = sorted(key_of)
        blobs: list[tuple[str, int, bytes]] = []
        _manifest_path, vectors_path = dense_index_paths(root)
        index = sqlite3.connect(vectors_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            for start in range(0, len(ids), DENSE_READ_BATCH):
                batch = ids[start : start + DENSE_READ_BATCH]
                marks = ", ".join("?" for _ in batch)
                for record_id, key, count, blob in index.execute(
                    f"SELECT record_id, key_sha256, passages, vectors FROM dense_vectors WHERE record_id IN ({marks})", batch
                ):
                    if key == key_of[record_id]:
                        blobs.append((record_id, count, blob))
        finally:
            index.close()
        blobs.sort()
        missing = len(ids) - len(blobs)
        if missing:
            warnings.append(f"dense list misses {missing} new or edited records; refresh it with: kb_next.py dense-index")
        query_vector = embedder.embed([request["query"]])[0]
        scores = dense_record_scores(blobs, query_vector, embedder.dim)
        return sorted(scores, key=lambda record_id: (-scores[record_id], record_id))[: request["depth"]]

    return dense_list_provider


def ranked_list_names(config: dict[str, Any] | None, requested: list[str] | None = None) -> list[str]:
    """Lists a lookup fuses: the request, else words plus dense when the config enables it."""
    if requested:
        return list(dict.fromkeys(requested))
    retrieval = config.get("retrieval") if isinstance(config, dict) else None
    dense = retrieval.get("dense") if isinstance(retrieval, dict) else None
    # Only an enabled dense list validates its settings, so a typo there cannot break word lookups.
    return ["words", "dense"] if isinstance(dense, dict) and dense.get("enabled") is True else ["words"]


def configured_ranked_list_providers(
    root: Path, config: dict[str, Any] | None, requested: list[str] | None = None
) -> list[tuple[str, Any]] | None:
    """Providers for `rank_record_ids`; None keeps the stdlib default (words only)."""
    names = ranked_list_names(config, requested)
    if names == ["words"]:
        return None
    by_name = {"words": words_list_provider, "trigram": trigram_list_provider}
    providers = []
    for name in names:
        if name == "dense":
            providers.append((name, make_dense_list_provider(root, dense_settings(config))))
        else:
            providers.append((name, by_name[name]))
    return providers


def parse_list_names(value: str) -> list[str]:
    names = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in names if name not in RANKED_LIST_NAMES]
    if unknown or not names:
        raise argparse.ArgumentTypeError(f"choose ranked lists from {','.join(RANKED_LIST_NAMES)}")
    return names


def rows_in_order(conn: sqlite3.Connection, ids: list[str]) -> list[sqlite3.Row]:
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    by_id = {row["id"]: row for row in conn.execute(f"SELECT * FROM records WHERE id IN ({placeholders})", ids)}
    return [by_id[item] for item in ids if item in by_id]


def fill_rows(conn: sqlite3.Connection, rows: list[sqlite3.Row], where: str, params: list[Any], limit: int) -> list[sqlite3.Row]:
    """Pad ranked rows with unranked candidates in tier and recency order."""
    seen = {row["id"] for row in rows}
    if len(rows) >= limit:
        return rows
    sql = f"SELECT * FROM records WHERE {where} {order_clause()} LIMIT ?"
    for row in fetch_rows(conn, sql, params + [limit + len(seen)]):
        if row["id"] in seen:
            continue
        rows.append(row)
        seen.add(row["id"])
        if len(rows) >= limit:
            break
    return rows


def lookup_facet_clause(facet: str) -> str:
    if facet == "definitions":
        return DEFINITION_TAGS_CLAUSE
    return facet_base_clause(facet)


def lookup_rows(
    conn: sqlite3.Connection,
    facet: str,
    query: str | None,
    domain: str | None,
    limit: int,
    providers: list[tuple[str, Any]] | None = None,
) -> tuple[list[sqlite3.Row], dict[str, Any]]:
    """Rows for `lookup` and the retrieval report; without a query, a facet listing."""
    clauses = ["status = 'ATIVO'"]
    params: list[Any] = []
    if domain:
        clauses.append("domain = ?")
        params.append(domain)
    facet_where = " AND ".join([*clauses, lookup_facet_clause(facet)])
    if not query:
        sql = f"SELECT * FROM records WHERE {facet_where} {order_clause()} LIMIT ?"
        listing = {"method": "facet_listing", "lists": [], "fusion": None, "tokenizers": None, "fallback": None, "warnings": []}
        return fetch_rows(conn, sql, params + [limit]), listing
    if facet == "definitions":
        # Any record matching the text counts; tagged definitions fill the rest.
        ids, info = rank_record_ids(conn, query, " AND ".join(clauses), params, limit, providers=providers)
        return fill_rows(conn, rows_in_order(conn, ids), facet_where, params, limit), info
    ids, info = rank_record_ids(conn, query, facet_where, params, limit, providers=providers)
    return rows_in_order(conn, ids), info


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
    providers: list[tuple[str, Any]] | None = None,
) -> list[sqlite3.Row]:
    base = ["status = 'ATIVO'", facet_base_clause(facet)]
    params: list[Any] = []
    if domain:
        base.append("domain = ?")
        params.append(domain)
    where = " AND ".join(base)
    rows: list[sqlite3.Row] = []
    if query:
        ids, _retrieval = rank_record_ids(conn, query, where, params, limit, providers=providers)
        rows = rows_in_order(conn, ids)
    return fill_rows(conn, rows, where, params, limit)


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


def actor_id_arg(value: str) -> str:
    actor = value.strip()
    if not actor:
        raise argparse.ArgumentTypeError("must name who acts, not be blank")
    return actor


def add_actor_arguments(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument(
        "--actor",
        type=actor_id_arg,
        required=required,
        metavar="ID",
        help="Who approves (proposal-apply) or generates (proposal commands) this operation",
    )
    parser.add_argument("--actor-runtime", choices=ACTOR_RUNTIMES, required=required)


def actor_from_args(args: argparse.Namespace) -> dict[str, str] | None:
    """Return the recorded actor, or None when a proposal command names none."""
    actor_id = getattr(args, "actor", None)
    actor_runtime = getattr(args, "actor_runtime", None)
    if actor_id is None and actor_runtime is None:
        return None
    if actor_id is None or actor_runtime is None:
        raise ValueError("--actor and --actor-runtime go together; pass both or neither")
    return {"id": actor_id, "runtime": actor_runtime}


def configured_default_actor(root: Path) -> str | None:
    """`proposal_apply.default_actor` from the vNext config, or None.

    A person writes this key; no runtime command fills it, so a recorded
    approver is always a name someone typed. A missing config yields None, so
    the apply still fails as a usage error before anything is read or written.
    """
    path = config_path(root)
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    section = config.get("proposal_apply") if isinstance(config, dict) else None
    value = section.get("default_actor") if isinstance(section, dict) else None
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("proposal_apply.default_actor in .kb-next/kb-next.config.json must name who approves, not be blank")
    return value.strip()


def resolve_apply_actor(root: Path, args: argparse.Namespace) -> tuple[dict[str, str], str]:
    """The approver of one apply and where its id came from: `flag` or `config`.

    `--actor` wins over the configured default. When neither names the
    approver, or `--actor-runtime` is missing, argparse exits 2 before the
    proposal is read and nothing is written.
    """
    actor_id, source = args.actor, "flag"
    if actor_id is None:
        actor_id, source = configured_default_actor(root), "config"
    missing = [flag for flag, value in (("--actor", actor_id), ("--actor-runtime", args.actor_runtime)) if value is None]
    if missing:
        parser = getattr(args, "apply_parser", None)
        if parser is None:
            raise ValueError(ACTOR_HINT)
        parser.error(f"the following arguments are required: {', '.join(missing)}")
    return {"id": actor_id, "runtime": args.actor_runtime}, source


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
    *,
    actor: dict[str, str] | None,
) -> tuple[str, Path, dict[str, Any]]:
    manifest_id = make_id("llm")
    manifest = {
        "manifest_id": manifest_id,
        "task_type": task_type,
        "created_at": now_iso(),
        # None: the proposal command ran without --actor. proposal-apply
        # always records the approver in its own manifest.
        "actor": actor,
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
    domain = getattr(args, "domain", None)
    providers = configured_ranked_list_providers(root, config, getattr(args, "lists", None))
    conn = open_classic_kb_readonly(root)
    try:
        rows, retrieval = lookup_rows(conn, args.facet, args.query, domain, args.limit, providers=providers)
    finally:
        conn.close()
    result = {
        "event": "lookup",
        "generated_at": now_iso(),
        "facet": args.facet,
        "query": args.query,
        "domain": domain,
        "access_policy": config["memory_facets"]["access_policy"],
        "default_global_preload": False,
        "classic_kb_mode": config["classic_kb"]["mode"],
        "retrieval": retrieval,
        "results": [row_to_lookup_result(row) for row in rows],
    }
    append_telemetry(
        root,
        "lookup",
        {
            "facet": args.facet,
            "query": args.query,
            "domain": domain,
            "result_count": len(rows),
            "classic_kb_mode": config["classic_kb"]["mode"],
            "retrieval": {key: retrieval[key] for key in ("method", "lists", "fallback")},
        },
    )
    if args.json:
        emit(result, True)
    else:
        lines = [f"Lookup: {args.facet}", ""]
        for item in result["results"]:
            lines.append(f"- [{item['id']}] {item['title']}")
        for warning in retrieval["warnings"]:
            lines.append(f"Warning: {warning}")
        emit("\n".join(lines), False)
    return 0


def cmd_dense_index(args: argparse.Namespace) -> int:
    """Build or refresh the derived dense index; optionally fetch the pinned model."""
    root = project_root(args)
    config = load_config_or_fail(root)
    settings = dense_settings(config)
    advisory = dense_model_advisory(settings["model"])
    fetched: list[str] = []
    if args.fetch_model:
        # Without the extra the index cannot be built, so stop before
        # downloading hundreds of megabytes of model files.
        import_dense_extra()
        fetched = fetch_dense_model(dense_model_dir(root, settings["model"]), settings["model"])
    stats = build_dense_index(root, settings, rebuild=args.rebuild)
    manifest = stats.pop("manifest")
    result = {
        "event": "dense_index",
        "generated_at": now_iso(),
        "index": DENSE_INDEX_REL.as_posix(),
        "enabled_in_config": settings["enabled"],
        "model": manifest["identity"]["model"],
        "identity": manifest["identity"],
        "fetched_model_files": fetched,
        "library": manifest["library"],
        "warnings": [advisory] if advisory else [],
        **stats,
    }
    append_telemetry(
        root,
        "dense_index",
        {key: result[key] for key in ("index", "model", "records", "passages", "embedded_records", "reused_records", "removed_records")},
    )
    if args.json:
        emit(result, True)
    else:
        lines = [
            f"Dense index: {result['records']} records, {result['passages']} passages ({result['model']})",
            f"Embedded {result['embedded_records']}, reused {result['reused_records']}, removed {result['removed_records']}.",
        ]
        if not settings["enabled"]:
            lines.append("Lookup fuses it after retrieval.dense.enabled is set to true in .kb-next/kb-next.config.json.")
        lines.extend(f"Warning: {warning}" for warning in result["warnings"])
        emit("\n".join(lines), False)
    return 0


def semantic_candidates(root: Path, facet: str, query: str | None, limit: int, domain: str | None = None) -> list[dict[str, Any]]:
    config = json.loads(config_path(root).read_text(encoding="utf-8")) if config_path(root).is_file() else None
    providers = configured_ranked_list_providers(root, config)
    conn = open_classic_kb_readonly(root)
    try:
        rows = fetch_candidate_rows(conn, facet, query, limit, domain=domain, providers=providers)
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
    actor = actor_from_args(args)
    config = load_config_or_fail(root)
    candidates = semantic_candidates(root, args.facet, args.query, args.limit, domain=getattr(args, "domain", None))
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
        actor=actor,
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
    append_telemetry(
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
    actor = actor_from_args(args)
    load_config_or_fail(root)
    candidates = semantic_candidates(root, args.facet, args.query, args.limit, domain=getattr(args, "domain", None))
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
        actor=actor,
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


def weekly_hygiene_limit(config: dict[str, Any]) -> int:
    """`semantic_curation.weekly_hygiene_proposals`: open hygiene proposals allowed per review window."""
    section = config.get("semantic_curation") if isinstance(config, dict) else None
    value = section.get("weekly_hygiene_proposals", HYGIENE_WEEKLY_DEFAULT) if isinstance(section, dict) else HYGIENE_WEEKLY_DEFAULT
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("semantic_curation.weekly_hygiene_proposals in .kb-next/kb-next.config.json must be an integer >= 0")
    return value


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def applied_proposal_ids(root: Path) -> set[str]:
    applied: set[str] = set()
    for path in proposal_apply_manifests_root(root).glob("*.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(manifest, dict) and manifest.get("status") == "applied" and manifest.get("proposal_id"):
            applied.add(str(manifest["proposal_id"]))
    return applied


def hygiene_target_still_qualifies(action: Any, record: sqlite3.Row | None) -> bool:
    if record is None or record["status"] != "ATIVO":
        return False
    if action == "demote_hot":
        return record["tier"] == "HOT"
    if action == "resolve":
        return record["category"] == "PENDENCIA"
    return True


def open_hygiene_proposals(root: Path) -> list[dict[str, Any]]:
    """Valid hygiene proposals of the review window that still wait for a decision.

    A proposal leaves the queue when it is applied, when its target no longer
    qualifies (demoted, resolved or superseded by other means) or when it ages
    past HYGIENE_REVIEW_WINDOW_DAYS; an unreviewed or declined item may then be
    proposed again if detection still finds it.
    """
    directory = proposals_root(root) / "hygiene"
    if not directory.is_dir():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - HYGIENE_REVIEW_WINDOW_DAYS * 86400
    applied = applied_proposal_ids(root)
    pending: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            proposal = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(proposal, dict) or proposal.get("validation_status") != "valid":
            continue
        proposal_id = str(proposal.get("proposal_id") or path.stem)
        created = parse_utc(proposal.get("created_at"))
        if proposal_id in applied or created is None or created.timestamp() < cutoff:
            continue
        pending.append(
            {
                "proposal_id": proposal_id,
                "path": path_relative_to_root(root, path),
                "created_at": proposal.get("created_at"),
                "group": proposal.get("group"),
                "action": proposal.get("action"),
                "target_record_id": proposal.get("target_record_id"),
                "title": (proposal.get("target_record") or {}).get("title"),
                "rationale": proposal.get("rationale"),
            }
        )
    targets = [str(item["target_record_id"]) for item in pending if item["target_record_id"]]
    records = fetch_records_by_ids(root, targets) if targets else {}
    return [
        item
        for item in pending
        if hygiene_target_still_qualifies(item["action"], records.get(str(item["target_record_id"])))
    ]


def hygiene_review_budget(limit: int, pending: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "window_days": HYGIENE_REVIEW_WINDOW_DAYS,
        "weekly_limit": limit,
        "open_count": len(pending),
        "room": max(0, limit - len(pending)),
        "open": pending,
    }


def cmd_semantic_hygiene(args: argparse.Namespace) -> int:
    root = project_root(args)
    actor = actor_from_args(args)
    config = load_config_or_fail(root)
    weekly_limit = weekly_hygiene_limit(config)
    pending = open_hygiene_proposals(root)
    deferred: list[dict[str, Any]] = []
    already_open: list[dict[str, Any]] = []
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
            actor=actor,
        )
        if judgment is not None:
            open_keys = {(item["target_record_id"], item["action"]): item["proposal_id"] for item in pending}
            room = max(0, weekly_limit - len(pending))
            for group_name in ("demote_candidate", "supersede_or_merge_candidate", "resolve_candidate", "needs_sponsor"):
                for item in judgment_groups[group_name]:
                    record = candidates_by_id.get(item["record_id"])
                    if record is None:
                        continue
                    action = str(item.get("action") or HYGIENE_ACTION_BY_GROUP[group_name])
                    entry = {"group": group_name, "action": action, "target_record_id": item["record_id"]}
                    if (item["record_id"], action) in open_keys:
                        already_open.append({**entry, "proposal_id": open_keys[(item["record_id"], action)]})
                        continue
                    if room <= 0:
                        deferred.append(entry)
                        continue
                    room -= 1
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
                "deferred_count": len(deferred),
                "already_open_count": len(already_open),
            },
        )
        pending = open_hygiene_proposals(root)

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
        "review_budget": hygiene_review_budget(weekly_limit, pending),
        "already_open": already_open,
        "deferred": deferred,
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
    actor = actor_from_args(args)
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
        if action in {"new", "update", "supersede"}:
            # Same provenance rule as proposal-apply, so a "valid" filing can be applied.
            problems = provenance_problems(root, judgment.get("provenance", []) or [])
            if problems:
                warnings = dedupe_strings([*warnings, *problems])
                validation_status = "blocked"
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
        actor=actor,
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
    # The workspace entrypoint resolves a linked worktree to the shared KB by
    # itself; fall back to the resolved KB only when no local entrypoint exists.
    for path in (root / ".kb" / "kb.py", classic_kb_root(root) / "kb.py"):
        if path.is_file():
            return path
    raise FileNotFoundError(f"classic KB entrypoint not found: {root / '.kb' / 'kb.py'}")


def classic_config_path(root: Path) -> Path:
    return classic_kb_root(root) / "kb.config.json"


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


def provenance_problems(root: Path, provenance: Any) -> list[str]:
    """Why `provenance` cannot back a canonical write; [] when it can.

    The one rule for filing-proposal and proposal-apply: each entry names an
    existing record (`record_id`) or a registered source (`source_id`, from
    `kb.py ingest`). Free text such as a file path or URL is not provenance.
    """
    record_ids, source_ids, malformed = proposal_provenance_ids(provenance)
    problems = [f"invalid_{item}" for item in malformed]
    if not record_ids and not source_ids:
        problems.append("missing_provenance")
    records = fetch_records_by_ids(root, record_ids)
    problems.extend(f"unknown_record_reference:{rid}" for rid in record_ids if rid not in records)
    sources = source_ids_exist(root, source_ids)
    problems.extend(f"unknown_source_reference:{sid}" for sid in source_ids if sid not in sources)
    return problems


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
            "actor": apply_manifest["actor"],
            "actor_source": apply_manifest.get("actor_source"),
            "canonical_record_id": apply_manifest.get("canonical_record_id"),
            "warnings": apply_manifest.get("warnings", []),
        },
    )
    result = {
        "event": "proposal-apply",
        "generated_at": now_iso(),
        "status": apply_manifest["status"],
        "apply_id": apply_manifest["apply_id"],
        "actor": apply_manifest["actor"],
        "actor_source": apply_manifest.get("actor_source"),
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
    actor, actor_source = resolve_apply_actor(root, args)
    load_config_or_fail(root)
    apply_id = make_id("proposal-apply")
    min_confidence = proposal_apply_min_confidence(root)
    apply_manifest: dict[str, Any] = {
        "apply_id": apply_id,
        "manifest_type": "proposal_apply",
        "created_at": now_iso(),
        "actor": actor,
        "actor_source": actor_source,
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
    warnings.extend(provenance_problems(root, provenance))

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


def approved_filing_manifest_path(root: Path, filing_id: str) -> Path:
    return root / APPROVED_FILING_MANIFESTS_REL / f"{filing_id}.json"


def same_title_records(root: Path, title: str, exclude_id: str | None) -> list[str]:
    """Active records whose title matches `title` (case and spacing aside)."""
    try:
        conn = open_classic_kb_readonly(root)
    except FileNotFoundError:
        return []
    try:
        rows = conn.execute(
            "SELECT id FROM records WHERE status = 'ATIVO' AND lower(trim(title)) = lower(trim(?)) ORDER BY id",
            (title,),
        ).fetchall()
    finally:
        conn.close()
    return [row["id"] for row in rows if row["id"] != exclude_id]


def cmd_approved_filing(args: argparse.Namespace) -> int:
    """File one record the user approved in chat: one call, one audit file, one oplog line.

    The same rules as filing-proposal plus proposal-apply hold: provenance
    names registered sources or existing records, confidence meets the apply
    floor, a supersede target exists and is active. Without an LLM judgment to
    declare duplicates, an active record with the same title blocks a new
    record; supersede that record instead. A blocked call writes nothing and
    exits 1.
    """
    root = project_root(args)
    actor, actor_source = resolve_apply_actor(root, args)
    load_config_or_fail(root)
    filing_id = make_id("approved-filing")
    min_confidence = proposal_apply_min_confidence(root)
    action = "supersede" if args.supersedes else "new"
    provenance = [{"source_id": sid} for sid in args.source_id or []] + [
        {"record_id": rid} for rid in args.record_id or []
    ]
    record_draft: dict[str, Any] = {
        "category": args.category,
        "domain": args.domain,
        "title": args.title,
        "content": args.content,
        "tier": args.tier,
        "tags": args.tags,
        "tier_reason": args.tier_reason,
        "review_after": args.review_after,
        "valid_until": None if action == "new" and (args.valid_until or "").lower() == "none" else args.valid_until,
        "confidence": args.confidence,
        "source_id": (args.source_id or [None])[0],
        "supersedes_id": args.supersedes,
        "source": f"kb-wiki-vnext approved filing {filing_id}",
    }
    record_draft, warnings = validate_record_draft(record_draft)
    if not args.approval_note or not args.approval_note.strip():
        warnings.append("missing_approval_note")
    if args.confidence < min_confidence:
        warnings.append(f"low_confidence:{args.confidence}")
    warnings.extend(provenance_problems(root, provenance))
    if action == "supersede":
        target = fetch_records_by_ids(root, [args.supersedes]).get(args.supersedes)
        if target is None:
            warnings.append(f"unknown_supersede_target:{args.supersedes}")
        elif target["status"] != "ATIVO":
            warnings.append(f"inactive_supersede_target:{args.supersedes}")
        elif target["category"] == args.category:
            record_draft.pop("category")  # the classic supersede keeps it; older engines lack --category
    duplicates = same_title_records(root, args.title, args.supersedes)
    if duplicates:
        warnings.append("duplicate_title:" + ",".join(duplicates))
    warnings = dedupe_strings(warnings)
    result: dict[str, Any] = {
        "event": "approved-filing",
        "generated_at": now_iso(),
        "filing_id": filing_id,
        "status": "blocked",
        "action": action,
        "actor": actor,
        "actor_source": actor_source,
        "warnings": warnings,
    }
    if warnings:
        emit(result, args.json)
        return 1
    if action == "supersede":
        cmd = canonical_supersede_command(root, filing_id, args.supersedes, record_draft)
        if record_draft.get("category"):
            cmd[-1:-1] = ["--category", str(record_draft["category"])]
    else:
        cmd = canonical_create_command(root, filing_id, record_draft)
    canonical_result = run_canonical_command(root, cmd)
    record_id = canonical_result.get("id")
    manifest = {
        "filing_id": filing_id,
        "manifest_type": "approved_filing",
        "created_at": result["generated_at"],
        "completed_at": now_iso(),
        "actor": actor,
        "actor_source": actor_source,
        "approval": {"approved": True, "approval_note": args.approval_note},
        "action": action,
        "record_draft": record_draft,
        "provenance": provenance,
        "confidence": args.confidence,
        "min_confidence": min_confidence,
        "target_record_id": args.supersedes,
        "canonical_command": cmd,
        "canonical_record_id": record_id,
        "status": "applied",
    }
    manifest_path = approved_filing_manifest_path(root, filing_id)
    write_json(manifest_path, manifest)
    append_operation(
        root,
        "approved-filing",
        {
            "filing_id": filing_id,
            "status": "applied",
            "action": action,
            "actor": actor,
            "actor_source": actor_source,
            "canonical_record_id": record_id,
            "target_record_id": args.supersedes,
        },
    )
    result.update(
        {
            "status": "applied",
            "canonical_record_id": record_id,
            "target_record_id": args.supersedes,
            "paths": {"manifest": str(manifest_path)},
        }
    )
    emit(result, args.json)
    return 0


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
    actor = actor_from_args(args)
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
        actor=actor,
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


def _read_runtime_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^RUNTIME_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Install this runtime into <project>/.kb-next/runtime/kb_next.py.

    Populates rung 1 of the resolution ladder so a consumer project can run
    vNext without a pre-existing runtime (kills the activation chicken-and-egg).
    Writes ONLY runtime/kb_next.py; never touches config, memory, proposals, or
    operations evidence, so it is safe to run as a repair on an activated
    workspace. An existing target is accepted only when its bytes match this
    artifact. Replacement is atomic and refuses links, reparse points,
    directories, and paths that resolve outside the project root.
    """
    root = project_root(args)
    src = Path(__file__).resolve()
    source_bytes = src.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    root_resolved = root.resolve()
    kb_next_dir = root / ".kb-next"
    runtime_dir = kb_next_dir / "runtime"
    target = runtime_dir / "kb_next.py"

    for candidate in (kb_next_dir, runtime_dir, target):
        if path_is_link_or_junction(candidate):
            raise RuntimeError(
                f"bootstrap target must not contain links or reparse points: {candidate}"
            )
    if kb_next_dir.exists() and not kb_next_dir.is_dir():
        raise RuntimeError(f"bootstrap .kb-next path is not a directory: {kb_next_dir}")
    if runtime_dir.exists() and not runtime_dir.is_dir():
        raise RuntimeError(f"bootstrap runtime path is not a directory: {runtime_dir}")
    if target.exists() and not target.is_file():
        raise RuntimeError(f"bootstrap target is not a regular file: {target}")

    resolved_target = target.resolve(strict=False)
    if not path_within(resolved_target, root_resolved):
        raise RuntimeError(
            f"refusing to bootstrap runtime outside project root: {target}"
        )

    same_file = False
    if target.exists():
        try:
            same_file = os.path.samefile(src, target)
        except OSError:
            same_file = False
    if same_file:
        emit(
            {
                "event": "bootstrap",
                "runtime_path": str(target),
                "action": "self",
                "runtime_version": RUNTIME_VERSION,
                "source_sha256": source_sha256,
                "installed_sha256": source_sha256,
            },
            args.json,
        )
        return 0

    runtime_dir.mkdir(parents=True, exist_ok=True)
    if path_is_link_or_junction(runtime_dir):
        raise RuntimeError(
            f"bootstrap runtime path must not be a link or reparse point: {runtime_dir}"
        )
    target_existed = target.exists()
    existing_version = _read_runtime_version(target) if target_existed else None
    existing_bytes = target.read_bytes() if target_existed else None
    previous_sha256 = (
        hashlib.sha256(existing_bytes).hexdigest()
        if existing_bytes is not None
        else None
    )
    if target_existed and not args.force and existing_bytes == source_bytes:
        action = "exists"
    else:
        temporary = runtime_dir / f".kb_next.py.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as handle:
                handle.write(source_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            shutil.copystat(src, temporary, follow_symlinks=False)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        action = "updated" if target_existed else "created"
    installed_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    if installed_sha256 != source_sha256:
        raise RuntimeError("bootstrap installed runtime hash does not match source")
    emit(
        {
            "event": "bootstrap",
            "runtime_path": str(target),
            "action": action,
            "runtime_version": RUNTIME_VERSION,
            "previous_version": existing_version,
            "previous_sha256": previous_sha256,
            "source_sha256": source_sha256,
            "installed_sha256": installed_sha256,
        },
        args.json,
    )
    return 0


def _iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_dir(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            payloads.append(data)
    return payloads


def wiki_topics(root: Path) -> list[dict[str, Any]]:
    """Domains with enough active records to deserve a wiki topic."""
    try:
        conn = open_classic_kb_readonly(root)
    except FileNotFoundError:
        return []
    try:
        rows = conn.execute(
            "SELECT domain, COUNT(*) AS n, MAX(updated_at) AS last_updated FROM records "
            f"WHERE status = 'ATIVO' AND {NOT_BOOTSTRAP_SEED} "
            "GROUP BY domain HAVING COUNT(*) >= ? ORDER BY n DESC, domain",
            (WIKI_TOPIC_MIN_RECORDS,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "topic": row["domain"],
            "domain": row["domain"],
            "active_records": row["n"],
            "last_record_update": row["last_updated"],
        }
        for row in rows
    ]


def build_wiki_draft_status(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Deterministic backlog of vNext wiki drafts; never writes anything."""
    counts = {"topics": 0, "needs_synthesis": 0, "needs_review": 0, "stale": 0, "current": 0}
    if not config["wiki"]["enabled"]:
        return {"wiki_enabled": False, "topics": [], "counts": counts}
    dormant = wiki_dormancy(root, config)
    if dormant is not None:
        return {"wiki_enabled": True, "wiki_dormant": dormant, "topics": [], "counts": counts}
    reviews = _load_json_dir(wiki_review_manifests_root(root))
    topics: list[dict[str, Any]] = []
    for topic in wiki_topics(root):
        name = topic["topic"]
        slug = slugify(name)
        drafts = {
            surface: wiki_drafts_root(root) / surface / f"{slug}.md" for surface in ("machine", "human")
        }
        draft_mtimes = [path.stat().st_mtime for path in drafts.values() if path.is_file()]
        drafts_at = _iso_from_timestamp(max(draft_mtimes)) if draft_mtimes else None
        topic_reviews = [item for item in reviews if item.get("topic") == name]
        latest = max(topic_reviews, key=lambda item: str(item.get("created_at") or ""), default=None)
        materialized = [item for item in topic_reviews if item.get("materialized")]
        last_materialized = max(materialized, key=lambda item: str(item.get("created_at") or ""), default=None)
        if not draft_mtimes and last_materialized is None:
            state = "needs_synthesis"
        elif latest is None or not latest.get("materialized") or (
            drafts_at is not None and drafts_at > str(latest.get("created_at") or "")
        ):
            state = "needs_review"
        elif str(topic["last_record_update"] or "") > str(last_materialized.get("created_at") or ""):
            state = "stale"
        else:
            state = "current"
        counts[state] += 1
        synth = ["wiki-synthesis-plan", "--topic", name, "--domain", topic["domain"], "--json"]
        review = ["wiki-draft-review", "--topic", name, "--materialize", "--json"]
        next_args = {
            "needs_synthesis": [synth, synth[:-1] + ["--judgment", "@<judgment.json>", "--write-drafts", "--json"], review],
            "stale": [synth, synth[:-1] + ["--judgment", "@<judgment.json>", "--write-drafts", "--json"], review],
            "needs_review": [review],
            "current": [],
        }[state]
        topics.append(
            {
                **topic,
                "slug": slug,
                "state": state,
                "drafts_present": {surface: path.is_file() for surface, path in drafts.items()},
                "last_review": (
                    {
                        "manifest_id": latest.get("manifest_id"),
                        "created_at": latest.get("created_at"),
                        "validation_status": latest.get("validation_status"),
                        "materialized": bool(latest.get("materialized")),
                    }
                    if latest
                    else None
                ),
                "next_args": next_args,
            }
        )
    counts["topics"] = len(topics)
    return {"wiki_enabled": True, "topics": topics, "counts": counts}


def cmd_wiki_draft_status(args: argparse.Namespace) -> int:
    root = project_root(args)
    config = load_config_or_fail(root)
    status = build_wiki_draft_status(root, config)
    result = {
        "event": "wiki-draft-status",
        "generated_at": now_iso(),
        "min_records_per_topic": WIKI_TOPIC_MIN_RECORDS,
        **status,
    }
    if not status["wiki_enabled"]:
        result["note"] = "KB + Wiki is not active; run activation-wizard --choice kb-wiki to enable wiki drafts."
    elif status.get("wiki_dormant"):
        dormant = status["wiki_dormant"]
        result["note"] = (
            f"The wiki is dormant until {dormant['min_sourced_records']} active records cite a registered "
            f"source (now {dormant['sourced_records']}); there is nothing to draft."
        )
    if args.json:
        emit(result, True)
        return 0
    lines = ["KB/Wiki vNext wiki draft status", ""]
    if result.get("note"):
        lines.append(result["note"])
    for topic in status["topics"]:
        lines.append(f"- {topic['topic']} ({topic['active_records']} records): {topic['state']}")
    emit("\n".join(lines), False)
    return 0


def _version_key(name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", name))


def _valid_classic_template(path: Path) -> bool:
    return (
        (path / "kb.py").is_file()
        and (path / "runtime" / "__init__.py").is_file()
        and (path / "kb.config.json").is_file()
    )


def classic_template_candidates(explicit: str | None) -> list[tuple[str, Path]]:
    """Ordered places where a classic `.kb/` scaffold may live."""
    here = Path(__file__).resolve().parent
    candidates: list[tuple[str, Path]] = []
    if explicit:
        candidates.append(("explicit", Path(explicit).expanduser().resolve()))
    # Stand-alone product bundle: <bundle>/runtime + <bundle>/classic-template/.kb
    candidates.append(("standalone_bundle", here.parent / "classic-template" / ".kb"))
    # Plugin source tree: plugins/kb-wiki-vnext/runtime -> plugins/kb-lifecycle/scaffold
    candidates.append(("plugin_sibling", here.parent.parent / "kb-lifecycle" / "scaffold"))
    # Client cache: <cache>/<marketplace>/kb-wiki-vnext/<ver>/runtime -> kb-lifecycle/<ver>/scaffold
    cache_parent = here.parent.parent.parent / "kb-lifecycle"
    if cache_parent.is_dir():
        for version_dir in sorted(cache_parent.iterdir(), key=lambda item: _version_key(item.name), reverse=True):
            candidates.append(("plugin_cache_sibling", version_dir / "scaffold"))
    # Authoring monorepo: core/versions/kb-wiki-vnext/runtime -> core/templates/kb
    if len(here.parents) > 3:
        candidates.append(("authoring_repo", here.parents[3] / "core" / "templates" / "kb"))
    home = Path.home()
    for base in (home / ".claude" / "plugins" / "cache", home / ".codex" / "plugins" / "cache"):
        if base.is_dir():
            found = sorted(
                base.glob("*/kb-lifecycle/*/scaffold"),
                key=lambda item: _version_key(item.parent.name),
                reverse=True,
            )
            candidates.extend(("client_cache", item) for item in found)
    return candidates


def select_classic_template(explicit: str | None) -> tuple[str | None, Path | None, list[str]]:
    tried: list[str] = []
    for kind, path in classic_template_candidates(explicit):
        tried.append(str(path))
        if _valid_classic_template(path):
            return kind, path, tried
        if kind == "explicit":
            raise FileNotFoundError(f"--template is not a classic KB scaffold (needs kb.py, runtime/, kb.config.json): {path}")
    return None, None, tried


def _copy_classic_template(source: Path, target: Path) -> int:
    copied = 0
    for current, dirs, files in os.walk(source):
        current_path = Path(current)
        dirs[:] = sorted(item for item in dirs if item != "__pycache__")
        for name in dirs:
            if path_is_link_or_junction(current_path / name):
                raise RuntimeError(f"classic template must not contain links: {current_path / name}")
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")) or name == "kb.db" or name.startswith("kb.db-"):
                continue
            source_file = current_path / name
            if path_is_link_or_junction(source_file):
                raise RuntimeError(f"classic template must not contain links: {source_file}")
            destination = target / source_file.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
            copied += 1
    return copied


def cmd_install_classic(args: argparse.Namespace) -> int:
    """Install and initialize the classic `.kb/` for a new vNext workspace."""
    root = project_root(args)
    target = root / ".kb"
    if (target / "kb.py").is_file():
        emit({"event": "install-classic", "action": "exists", "kb_root": str(target)}, args.json)
        return 0
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError(f"refusing to install into non-empty {target} that has no kb.py")
    kind, template, tried = select_classic_template(args.template)
    if template is None:
        raise FileNotFoundError(
            "classic KB template not found. Install the kb-lifecycle plugin "
            "(kb-lifecycle@kb-factory-tools), use the stand-alone bundle, or pass "
            "--template <scaffold dir>. Tried: " + "; ".join(tried)
        )
    created_target = not target.exists() or not any(target.iterdir())
    copied = _copy_classic_template(template, target)
    cmd = [sys.executable, str(target / "kb.py"), "init", "--slug", args.slug]
    add_optional_cli_arg(cmd, "--name", args.name)
    add_optional_cli_arg(cmd, "--domains", args.domains)
    add_optional_cli_arg(cmd, "--id-prefix", args.id_prefix)
    seed = target / "seed" / "initial_records.jsonl"
    if not args.no_seed and seed.is_file():
        cmd.extend(["--seed", str(seed)])
    proc = subprocess.run(cmd, cwd=str(target), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if created_target:
            shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(
            "classic init failed; the copied .kb/ was removed: "
            + ((proc.stderr or proc.stdout).strip() or f"exit {proc.returncode}")
        )
    classic_config = json.loads((target / "kb.config.json").read_text(encoding="utf-8-sig"))
    result = {
        "event": "install-classic",
        "action": "created",
        "kb_root": str(target),
        "template": {"kind": kind, "path": str(template)},
        "files_copied": copied,
        "seed_imported": "--seed" in cmd,
        "project": classic_config.get("project"),
        "domains": classic_config.get("domains"),
        "init_output": proc.stdout.strip().splitlines()[-3:],
    }
    append_operation(
        root,
        "install-classic",
        {
            "template_kind": kind,
            "files_copied": copied,
            "seed_imported": result["seed_imported"],
            "project": classic_config.get("project"),
        },
    )
    emit(result, args.json)
    return 0


def cmd_upgrade_classic(args: argparse.Namespace) -> int:
    """Refresh only the classic engine (`kb.py` + `runtime/*.py`).

    Data (`kb.db`, `memory/`, `sources/`, `wiki/`, `exports/`, `seed/`) and the
    project config are never touched. A missing `.kb/.gitignore` is added.
    """
    root = project_root(args)
    target = root / ".kb"
    if not (target / "kb.py").is_file():
        raise FileNotFoundError(f"no classic KB at {target}; use install-classic for a new project")
    kind, template, tried = select_classic_template(args.template)
    if template is None:
        raise FileNotFoundError(
            "classic KB template not found. Install or update the kb-lifecycle plugin, "
            "or pass --template <scaffold dir>. Tried: " + "; ".join(tried)
        )
    if template.resolve() == target.resolve():
        raise RuntimeError("the template resolves to the project's own .kb/; nothing to upgrade")
    engine = [Path("kb.py")] + sorted(
        path.relative_to(template) for path in (template / "runtime").glob("*.py")
    )
    changed: list[str] = []
    for relative in engine:
        source_file = template / relative
        destination = target / relative
        if path_is_link_or_junction(source_file) or path_is_link_or_junction(destination):
            raise RuntimeError(f"classic engine files must not be links: {relative}")
        new_bytes = source_file.read_bytes()
        if destination.is_file() and destination.read_bytes() == new_bytes:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(new_bytes)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        changed.append(relative.as_posix())
    gitignore_added = False
    if not (target / ".gitignore").exists() and (template / ".gitignore").is_file():
        shutil.copy2(template / ".gitignore", target / ".gitignore")
        gitignore_added = True
    result = {
        "event": "upgrade-classic",
        "action": "updated" if changed or gitignore_added else "unchanged",
        "kb_root": str(target),
        "template": {"kind": kind, "path": str(template)},
        "changed_files": changed,
        "gitignore_added": gitignore_added,
        "kb_py_sha256": sha256_path(target / "kb.py"),
    }
    append_operation(
        root,
        "upgrade-classic",
        {
            "template_kind": kind,
            "changed_files": changed,
            "gitignore_added": gitignore_added,
            "kb_py_sha256": result["kb_py_sha256"],
        },
    )
    emit(result, args.json)
    return 0


def cmd_session_hint(args: argparse.Namespace) -> int:
    """SessionStart hook text for vNext workspaces; silent anywhere else.

    Silence outside `.kb-next/` lets the classic kb-lifecycle hook govern, so a
    workspace never receives two conflicting NOW.md instructions.
    """
    try:
        root = project_root(args)
        config = load_config_or_fail(root)
        wiki_on = bool((config.get("wiki") or {}).get("enabled")) and wiki_dormancy(root, config) is None
        gate = config.get("write_gate")
        gate_on = not (isinstance(gate, dict) and gate.get("enabled") is False)
        runtime = runtime_command(root)
        skew = runtime_skew_line(root)
    except Exception:
        return 0
    lines = [
        "KB/Wiki vNext workspace detected.",
        f"Run the vnext-session-start command (shell: `{runtime} session-start --json`) "
        "and read only `.kb-next/memory/NOW.md` by default.",
        "Classic `.kb/` stays canonical: use `lookup --facet ... [--domain ...]` or `python .kb/kb.py search` "
        "for targeted reads; classic NOW/HOT/INDEX are on demand, not a default preload.",
    ]
    if skew:
        lines.append(skew)
    if gate_on:
        lines.append(
            "Canonical records change only after the user approves: a record the user approved in chat takes one "
            "`approved-filing` call; otherwise write a proposal (`filing-proposal`, or `semantic-hygiene "
            "--write-proposals` for HOT demotion and open items) and run `proposal-apply` after the yes. The "
            "kb-wiki-vnext plugin hook denies direct `.kb/kb.py create|file|supersede|update`."
        )
    if wiki_on:
        lines.append(
            "KB + Wiki is active: at session end run the vnext-wiki-drafts plugin command "
            "(runtime `wiki-draft-status`) for topics that need drafts."
        )
    print("\n".join(lines))
    return 0


def runtime_command(root: Path) -> str:
    """`python <runtime>` for this workspace: the local runtime when bootstrapped, else this file."""
    if (kb_next_root(root) / "runtime" / "kb_next.py").is_file():
        runtime = ".kb-next/runtime/kb_next.py"
    else:
        runtime = f'"{Path(__file__).resolve().as_posix()}" --project-root "{root.as_posix()}"'
    return f"python {runtime}"


def _runtime_version_key(version: str | None) -> tuple[int, ...] | None:
    if version is None or not re.fullmatch(r"\d+(\.\d+)*", version):
        return None
    return tuple(int(part) for part in version.split("."))


def runtime_skew_line(root: Path) -> str | None:
    """One line when the project's local runtime and this file carry different versions.

    A worktree cut before an upgrade commit vendors an older runtime than the
    user-scope plugin; `bootstrap` overwrites whatever is there, so a local
    runtime newer than the plugin needs a plugin update instead.
    """
    local = kb_next_root(root) / "runtime" / "kb_next.py"
    if not local.is_file():
        return None
    try:
        local_version = _read_runtime_version(local)
    except ValueError:
        local_version = None
    if local_version == RUNTIME_VERSION:
        return None
    local_key, plugin_key = _runtime_version_key(local_version), _runtime_version_key(RUNTIME_VERSION)
    versions = (
        f"Runtime skew: `.kb-next/runtime/kb_next.py` is {local_version or 'unknown'}, "
        f"the kb-wiki-vnext plugin is {RUNTIME_VERSION}."
    )
    if local_key and plugin_key and local_key > plugin_key:
        return f"{versions} Update the plugin and restart the client; do not bootstrap from it."
    return (
        f"{versions} Start the session from current main or run the existing-project-upgrade-vnext command; "
        "proposals filed by an older runtime can fail `proposal-apply` on main."
    )


def subagent_lookup_command(root: Path) -> str:
    """The read-only lookup a subagent can run: the local runtime when bootstrapped, else this file."""
    return f'{runtime_command(root)} lookup --facet status --query "<words>" --json'


def cmd_subagent_hint(args: argparse.Namespace) -> int:
    """SubagentStart hook context for vNext workspaces; silent anywhere else.

    The hook cannot see the subagent's brief, so it gives the contract and a
    read-only lookup command instead of records: records picked by the words of
    a short task description were mostly unrelated, and some briefs isolate the
    subagent on purpose. The main agent adds the records under `KB records`.
    """
    try:
        root = project_root(args)
        load_config_or_fail(root)
        has_db = (classic_kb_root(root) / "kb.db").is_file()
        lookup = subagent_lookup_command(root)
    except Exception:
        return 0
    lines = [
        "KB/Wiki vNext note for subagents, added by the kb-wiki-vnext plugin's SubagentStart hook.",
        "This workspace keeps a project knowledge base in `.kb/`; the main session is its only writer "
        "and files what subagents report.",
    ]
    if has_db:
        lines.append(
            f"- If your brief allows shell commands, you can read it with `{lookup}` (at most six words). "
            "This does not change `.kb/`; it only appends one log line under `.kb-next/`."
        )
    lines.extend(
        [
            "- Do not run commands that write the knowledge base: `filing-proposal`, `proposal-apply`, "
            "`.kb/kb.py` commands that change records, or SQL on `.kb/kb.db`.",
            "- Unless your brief fixes the output format, end your report with a `KB candidates` section: "
            "each fact, decision or learning worth keeping, one line each with its source "
            "(file and line, command, URL or person), or `none`.",
        ]
    )
    payload = {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": "\n".join(lines)}}
    print(json.dumps(payload, ensure_ascii=True))
    return 0


class RuntimeArgumentParser(argparse.ArgumentParser):
    """Subparsers inherit this class, so a bad proposal-apply --actor names the fix."""

    def error(self, message: str) -> NoReturn:
        if self.prog.endswith((" proposal-apply", " approved-filing")) and "--actor" in message:
            message = f"{message}\n{ACTOR_HINT}"
        super().error(message)


def build_parser() -> argparse.ArgumentParser:
    parser = RuntimeArgumentParser(description="KB/Wiki vNext side-by-side runtime")
    parser.add_argument("--project-root", default=".", help="Project root containing .kb/ and/or .kb-next/")
    sub = parser.add_subparsers(dest="command", required=True)

    wizard = sub.add_parser("activation-wizard")
    wizard.add_argument("--mode", choices=["short", "guided"], required=True)
    wizard.add_argument("--choice", choices=sorted(CHOICES.keys()))
    wizard.add_argument("--answers", help="JSON object or @path for guided mode answers")
    wizard.add_argument("--rationale")
    wizard.add_argument(
        "--disable-classic-wiki",
        action="store_true",
        help="With kb-alone, also turn off an enabled classic wiki in .kb/kb.config.json",
    )
    wizard.add_argument(
        "--no-wiki-sync",
        action="store_true",
        help="With kb-wiki, skip the initial classic wiki-sync",
    )
    wizard.add_argument(
        "--wiki-min-sourced-records",
        type=int,
        default=WIKI_DORMANT_MIN_SOURCED_RECORDS,
        help=(
            "With kb-wiki, keep a new wiki dormant until this many active records cite a registered source "
            f"(default {WIKI_DORMANT_MIN_SOURCED_RECORDS}; 0 turns it on at once)"
        ),
    )
    wizard.add_argument("--scope", help="The project scope in the user's words; filed once as a HOT DECISAO")
    wizard.add_argument("--json", action="store_true")
    wizard.set_defaults(func=cmd_activation_wizard)

    install = sub.add_parser(
        "install-classic",
        help="Copy the classic .kb/ scaffold into the project and run classic init",
    )
    install.add_argument("--slug", required=True, help="Project slug; default record ID prefix")
    install.add_argument("--name", help="Project display name")
    install.add_argument("--domains", help="Comma-separated KB domains")
    install.add_argument("--id-prefix", dest="id_prefix", help="Record ID prefix override")
    install.add_argument("--template", help="Classic scaffold directory (default: auto-discovery)")
    install.add_argument("--no-seed", action="store_true", help="Do not import the scaffold seed records")
    install.add_argument("--json", action="store_true")
    install.set_defaults(func=cmd_install_classic)

    upgrade_classic = sub.add_parser(
        "upgrade-classic",
        help="Refresh the classic .kb/ engine (kb.py + runtime/) without touching data or config",
    )
    upgrade_classic.add_argument("--template", help="Classic scaffold directory (default: auto-discovery)")
    upgrade_classic.add_argument("--json", action="store_true")
    upgrade_classic.set_defaults(func=cmd_upgrade_classic)

    hint = sub.add_parser("session-hint", help="SessionStart hook text; silent outside vNext workspaces")
    hint.set_defaults(func=cmd_session_hint)

    subagent_hint = sub.add_parser(
        "subagent-hint", help="SubagentStart hook JSON: subagent KB contract; silent outside vNext workspaces"
    )
    subagent_hint.set_defaults(func=cmd_subagent_hint)

    boot = sub.add_parser("bootstrap", help="Install this runtime into <project>/.kb-next/runtime/kb_next.py")
    boot.add_argument("--force", action="store_true")
    boot.add_argument("--json", action="store_true")
    boot.set_defaults(func=cmd_bootstrap)

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
    lookup.add_argument("--domain", help="Restrict results to one KB domain")
    lookup.add_argument("--limit", type=int, default=10)
    lookup.add_argument(
        "--lists",
        type=parse_list_names,
        help="Comma-separated ranked lists to fuse (words, trigram, dense); default: words, plus dense when enabled in the config",
    )
    lookup.add_argument("--json", action="store_true")
    lookup.set_defaults(func=cmd_lookup)

    dense_index = sub.add_parser(
        "dense-index",
        help="Build or refresh the optional dense index under .kb-next/index/dense (needs the model2vec extra)",
    )
    dense_index.add_argument("--fetch-model", action="store_true", help="Download the pinned model files into the model cache first")
    dense_index.add_argument("--rebuild", action="store_true", help="Drop the index and embed every active record again")
    dense_index.add_argument("--json", action="store_true")
    dense_index.set_defaults(func=cmd_dense_index)

    semantic = sub.add_parser("semantic-lookup")
    semantic.add_argument("--query", required=True)
    semantic.add_argument("--facet", choices=MEMORY_FACETS, required=True)
    semantic.add_argument("--domain", help="Restrict candidates to one KB domain")
    semantic.add_argument("--limit", type=int, default=10)
    semantic.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    semantic.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    add_actor_arguments(semantic, required=False)
    semantic.add_argument("--json", action="store_true")
    semantic.set_defaults(func=cmd_semantic_lookup)

    curation = sub.add_parser("curation-proposal")
    curation.add_argument("--query", required=True)
    curation.add_argument("--facet", choices=MEMORY_FACETS, required=True)
    curation.add_argument("--domain", help="Restrict candidates to one KB domain")
    curation.add_argument("--limit", type=int, default=10)
    curation.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    curation.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    add_actor_arguments(curation, required=False)
    curation.add_argument("--json", action="store_true")
    curation.set_defaults(func=cmd_curation_proposal)

    hygiene = sub.add_parser("semantic-hygiene")
    hygiene.add_argument("--scope", choices=["hot-overflow"], default="hot-overflow")
    hygiene.add_argument("--limit", type=int, default=50)
    hygiene.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    hygiene.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    hygiene.add_argument("--write-proposals", action="store_true")
    add_actor_arguments(hygiene, required=False)
    hygiene.add_argument("--json", action="store_true")
    hygiene.set_defaults(func=cmd_semantic_hygiene)

    filing = sub.add_parser("filing-proposal")
    filing.add_argument("--input", required=True, help="JSON object or @path with candidate memory")
    filing.add_argument("--category", required=True)
    filing.add_argument("--domain", required=True)
    filing.add_argument("--limit", type=int, default=10)
    filing.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    filing.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    add_actor_arguments(filing, required=False)
    filing.add_argument("--json", action="store_true")
    filing.set_defaults(func=cmd_filing_proposal)

    proposal_apply = sub.add_parser("proposal-apply")
    proposal_apply.add_argument("--proposal", required=True, help="Proposal path or proposal id under .kb-next/proposals")
    proposal_apply.add_argument("--approve", action="store_true")
    proposal_apply.add_argument("--approval-note")
    proposal_apply.add_argument("--target-record-id")
    # Both are required; cmd_proposal_apply checks them so that --actor can
    # default to proposal_apply.default_actor from the config.
    add_actor_arguments(proposal_apply, required=False)
    proposal_apply.add_argument("--json", action="store_true")
    proposal_apply.set_defaults(func=cmd_proposal_apply, apply_parser=proposal_apply)

    approved = sub.add_parser(
        "approved-filing",
        help="File one record the user approved in chat: one call, one audit file (no proposal files)",
    )
    approved.add_argument("--category", required=True, choices=sorted(RECORD_CATEGORIES))
    approved.add_argument("--domain", required=True)
    approved.add_argument("--title", required=True)
    approved.add_argument("--content", required=True)
    approved.add_argument("--confidence", type=float, required=True)
    approved.add_argument(
        "--source-id", action="append", help="Registered source (from `kb.py ingest`) backing the record; repeatable"
    )
    approved.add_argument("--record-id", action="append", help="Existing record backing this one; repeatable")
    approved.add_argument("--supersedes", help="Active record this one replaces")
    approved.add_argument("--tier", default="WARM", choices=["HOT", "WARM", "COLD"])
    approved.add_argument("--tags", help="Comma-separated tags")
    approved.add_argument("--tier-reason")
    approved.add_argument("--review-after")
    approved.add_argument("--valid-until", help="Date, or `none` to clear a superseded record's date")
    approved.add_argument("--approval-note", required=True, help="Who approved, where, and in their words")
    # --actor defaults to proposal_apply.default_actor; --actor-runtime is required.
    add_actor_arguments(approved, required=False)
    approved.add_argument("--json", action="store_true")
    approved.set_defaults(func=cmd_approved_filing, apply_parser=approved)

    wiki_plan = sub.add_parser("wiki-synthesis-plan")
    wiki_plan.add_argument("--topic", required=True)
    wiki_plan.add_argument("--domain", required=True)
    wiki_plan.add_argument("--limit", type=int, default=10)
    wiki_plan.add_argument("--judgment", help="JSON object or @path with external LLM judgment")
    wiki_plan.add_argument("--judgment-json", help="Inline JSON external LLM judgment")
    wiki_plan.add_argument("--write-drafts", action="store_true")
    add_actor_arguments(wiki_plan, required=False)
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

    wiki_status = sub.add_parser(
        "wiki-draft-status",
        help="List wiki topics that need vNext drafts, review, or refresh (read-only)",
    )
    wiki_status.add_argument("--json", action="store_true")
    wiki_status.set_defaults(func=cmd_wiki_draft_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    # A piped Windows stdout defaults to cp1252; escape what it cannot encode
    # (e.g. U+2192 in record text) instead of crashing with UnicodeEncodeError.
    # stderr already defaults to backslashreplace.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
