"""Template seeds stay out of derived surfaces; the wiki can wait for sourced records.

Projects created before kb-lifecycle 0.2.6 carry five records the KB Factory
template seeded. They describe the KB, not the project, and used to fill NOW,
HOT and the first wiki page of a new project (2026-10-21). The template
no longer seeds them; existing KBs keep them in kb.db and in search, while NOW,
HOT, INDEX, topics, packs and the wiki leave them out. A record the project
rewrote (other title or source) is not a seed.

`wiki.eligibility.min_sourced_records`, when set, is the only activation signal
of a `signal` wiki: it stays off until that many active records cite a source.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "kb"

LEGACY_SEEDS = [
    {"id": "{{PROJECT_NAME}}-KB-0001", "category": "DECISAO", "domain": "operations",
     "title": "KB enabled as the project's operating memory", "content": "Chat history is not the source of truth.",
     "tier": "HOT", "source": "project-bootstrap", "confidence": 0.95},
    {"id": "{{PROJECT_NAME}}-KB-0002", "category": "PREMISSA", "domain": "product",
     "title": "Initial project scope remains valid until first KB review", "content": "Scope stays until review.",
     "tier": "HOT", "source": "project-bootstrap", "confidence": 0.7},
    {"id": "{{PROJECT_NAME}}-KB-0003", "category": "FATO", "domain": "architecture",
     "title": "The primary runtime is local-first", "content": "Local files and Git.",
     "tier": "WARM", "source": "project-bootstrap", "confidence": 0.95},
    {"id": "{{PROJECT_NAME}}-KB-0004", "category": "PENDENCIA", "domain": "operations",
     "title": "Review HOT criteria after first real sessions", "content": "Review HOT.",
     "tier": "HOT", "source": "project-bootstrap", "confidence": 0.85},
    {"id": "{{PROJECT_NAME}}-KB-0005", "category": "APRENDIZADO", "domain": "operations",
     "title": "Search before assuming reduces context drift", "content": "Search first.",
     "tier": "HOT", "source": "kb-factory-blueprint", "confidence": 0.9},
]
SEED_TITLES = [seed["title"] for seed in LEGACY_SEEDS]


def _run(kb_dir: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, "kb.py", *args], cwd=str(kb_dir), capture_output=True, text=True, encoding="utf-8"
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout


@pytest.fixture(scope="module")
def legacy_kb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A KB initialized the old way: template seeds plus project records (read-only in tests)."""
    kb_dir = tmp_path_factory.mktemp("legacy") / ".kb"
    kb_dir.mkdir()
    shutil.copytree(TEMPLATE / "runtime", kb_dir / "runtime")
    shutil.copy2(TEMPLATE / "kb.py", kb_dir / "kb.py")
    config = json.loads((TEMPLATE / "kb.config.json").read_text(encoding="utf-8"))
    config["project"] = {"name": "Legacy KB", "slug": "legacy-kb", "primary_repo_path": ".", "kb_root": "."}
    config["domains"] = ["product", "operations", "architecture"]
    (kb_dir / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    seed = kb_dir / "legacy_seed.jsonl"
    seed.write_text("".join(json.dumps(item) + "\n" for item in LEGACY_SEEDS), encoding="utf-8")
    _run(kb_dir, "init", "--seed", str(seed))
    _run(kb_dir, "create", "--category", "DECISAO", "--domain", "product", "--tier", "HOT",
         "--title", "Escopo real do projeto", "--content", "Pesquisa de protocolos.", "--json")
    # Same title as a seed but a project source: a rewrite, not a seed.
    _run(kb_dir, "create", "--category", "APRENDIZADO", "--domain", "operations", "--tier", "HOT",
         "--title", "Search before assuming reduces context drift", "--source", "team retro",
         "--content", "Measured in our sessions.", "--json")
    _run(kb_dir, "export")
    return kb_dir


def _memory(kb_dir: Path, name: str) -> str:
    return (kb_dir / "memory" / name).read_text(encoding="utf-8")


def test_template_ships_no_seed_records() -> None:
    for seed in (TEMPLATE / "seed" / "initial_records.jsonl",
                 REPO / "plugins" / "kb-lifecycle" / "scaffold" / "seed" / "initial_records.jsonl"):
        assert seed.read_text(encoding="utf-8").strip() == ""


def test_derived_surfaces_leave_legacy_seeds_out(legacy_kb: Path) -> None:
    now, hot, index = _memory(legacy_kb, "NOW.md"), _memory(legacy_kb, "HOT.md"), _memory(legacy_kb, "INDEX.md")
    topics = "".join(path.read_text(encoding="utf-8") for path in (legacy_kb / "memory" / "topics").glob("*.md"))
    for title in SEED_TITLES[:4]:
        for surface in (now, hot, index, topics):
            assert title not in surface
    assert "Escopo real do projeto" in now
    assert "Escopo real do projeto" in hot
    assert "Open pendencias: `0`" in now
    # The project's own record with a seed title stays visible.
    assert "Search before assuming reduces context drift" in hot


def test_seeds_stay_in_kb_db_and_search(legacy_kb: Path) -> None:
    listed = json.loads(_run(legacy_kb, "list", "--json"))
    titles = {row["title"] for row in listed}
    assert set(SEED_TITLES) <= titles
    found = json.loads(_run(legacy_kb, "search", "operating memory", "--json"))
    assert any(row["title"] == SEED_TITLES[0] for row in found)


def test_wiki_candidates_and_signals_ignore_seeds(legacy_kb: Path) -> None:
    sys.path.insert(0, str(legacy_kb))
    try:
        from runtime.wiki import compute_wiki_hard_signals
        from runtime.wiki_candidates import generate_wiki_candidates
    finally:
        sys.path.remove(str(legacy_kb))
    conn = sqlite3.connect(str(legacy_kb / "kb.db"))
    conn.row_factory = sqlite3.Row
    signals = compute_wiki_hard_signals(conn, {})
    assert signals["active_record_count"] == 2
    assert signals["open_pendencias"] == 0
    candidates = generate_wiki_candidates(conn, {}, {"page_types": ["domain_overview", "research_synthesis"]})
    supporting = {rid for cand in candidates for rid in cand["supporting_record_ids"]}
    assert not any(rid.endswith(("-KB-0001", "-KB-0004", "-KB-0005")) for rid in supporting)


def test_min_sourced_records_is_the_only_signal_when_set() -> None:
    sys.path.insert(0, str(TEMPLATE))
    try:
        from runtime.wiki import compute_wiki_hard_signals, compute_wiki_state
    finally:
        sys.path.remove(str(TEMPLATE))
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE records (id TEXT, category TEXT, domain TEXT, title TEXT, status TEXT, "
        "source TEXT, source_id TEXT)"
    )
    for index in range(40):
        domain = "a" if index % 2 else "b"
        source_id = f"SRC-{index}" if index < 9 else None
        conn.execute(
            "INSERT INTO records VALUES (?, 'FATO', ?, ?, 'ATIVO', 'agent', ?)",
            (f"R{index}", domain, f"title {index}", source_id),
        )
    cfg = {"enabled": False, "activation_mode": "signal", "page_types": ["domain_overview"],
           "eligibility": {"min_sourced_records": 10, "min_soft_signal_score": 0}}
    soft = {"soft_signal_score": 5}
    signals = compute_wiki_hard_signals(conn, cfg["eligibility"])
    assert signals["any_hard_signal"] is True  # 40 records in 2 domains would fire before
    assert signals["sourced_record_count"] == 9
    assert compute_wiki_state(cfg, signals, soft, 3) == "off"
    conn.execute("INSERT INTO records VALUES ('R40', 'FATO', 'a', 't', 'ATIVO', 'agent', 'SRC-40')")
    signals = compute_wiki_hard_signals(conn, cfg["eligibility"])
    assert signals["sourced_records_met"] is True
    assert compute_wiki_state(cfg, signals, soft, 3) == "active"
    # Without the key the old OR'd signals still decide.
    plain = {"enabled": False, "activation_mode": "signal", "page_types": ["domain_overview"],
             "eligibility": {"min_soft_signal_score": 0}}
    assert compute_wiki_state(plain, compute_wiki_hard_signals(conn, {}), soft, 3) == "active"
