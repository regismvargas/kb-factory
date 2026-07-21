from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "kb"


def _config() -> dict:
    return {
        "schema_version": 6,
        "project": {"name": "Graph Wiki", "slug": "graph-wiki", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["alpha"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "lifecycle": {"events": {"session_start": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False}}},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {
            "enabled": True,
            "activation_mode": "policy",
            "page_types": ["domain_overview", "source_page"],
            "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0},
            "semantic": {"min_confidence_autopublish": 0.5, "min_confidence_review": 0.4, "min_sources_research_synthesis": 0},
            "renderers": {"mkdocs": {"enabled": False, "site_name": "Graph Wiki"}},
        },
    }


def _run(root: Path, *args: str, json_mode: bool = False) -> dict | str:
    command = [sys.executable, "kb.py", *args]
    if json_mode:
        command.append("--json")
    completed = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout) if json_mode else completed.stdout


def _wiki_state(root: Path) -> tuple[list[str], dict[str, str], int]:
    wiki = root / "wiki"
    files = sorted(path.relative_to(wiki).as_posix() for path in wiki.rglob("*.md"))
    hashes = {
        relative: hashlib.sha256((wiki / relative).read_bytes()).hexdigest()
        for relative in files
    }
    with sqlite3.connect(root / "kb.db") as conn:
        snapshots = conn.execute("SELECT COUNT(*) FROM wiki_snapshots").fetchone()[0]
    return files, hashes, snapshots


def _assert_record_links_navigable(root: Path) -> None:
    live = root / "wiki" / "live"
    pattern = re.compile(r"\[(KB-[A-Za-z0-9._-]+)\]\(([^)]+)\)")
    found: set[str] = set()
    for page in sorted(live.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for record_id, href in pattern.findall(text):
            found.add(record_id)
            path_part, separator, anchor = href.partition("#")
            target = page if not path_part else (page.parent / path_part).resolve()
            assert target.is_file(), f"broken record link {href} in {page}"
            assert separator and anchor, f"record link lacks stable anchor: {href}"
            assert f'id="{anchor}"' in target.read_text(encoding="utf-8")
    assert {"KB-A", "KB-B", "KB-C"}.issubset(found)


def test_managed_graph_wiki_is_navigable_and_byte_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    root.mkdir()
    shutil.copytree(TEMPLATE / "runtime", root / "runtime")
    shutil.copy2(TEMPLATE / "kb.py", root / "kb.py")
    (root / "kb.config.json").write_text(json.dumps(_config()), encoding="utf-8")
    _run(root, "init")

    _run(root, "create", "--id", "KB-A", "--category", "FATO", "--domain", "alpha",
         "--title", "Alpha", "--content", "Depends on [KB-B].", "--tier", "WARM")
    _run(root, "create", "--id", "KB-B", "--category", "FATO", "--domain", "alpha",
         "--title", "Beta", "--content", "Beta evidence.", "--tier", "WARM")
    _run(root, "create", "--id", "KB-C", "--category", "DECISAO", "--domain", "alpha",
         "--title", "Gamma", "--content", "Gamma decision.", "--tier", "WARM")
    source_file = root / "source.txt"
    source_file.write_text("exact source evidence\n", encoding="utf-8")
    source = _run(root, "ingest", str(source_file), "--domain", "alpha", json_mode=True)
    source_id = source["source_id"]
    _run(root, "graph", "source-link", "KB-A", source_id,
         "--actor", "test", "--actor-runtime", "human")
    _run(root, "graph", "edge-add", "KB-A", "depends-on", "KB-B",
         "--actor", "test", "--actor-runtime", "human")

    first = _run(root, "wiki-sync", "--force", json_mode=True)
    assert first["written_count"] >= 3
    index = root / "wiki" / "live" / "index.md"
    overview = root / "wiki" / "live" / "alpha" / "overview.md"
    source_page = root / "wiki" / "live" / "sources" / f"{source_id}.md"
    assert index.is_file() and overview.is_file() and source_page.is_file()
    assert all(f'id="kb-{record.lower()}"' in index.read_text(encoding="utf-8") for record in ("KB-A", "KB-B", "KB-C"))
    source_text = source_page.read_text(encoding="utf-8")
    assert "## Cited by" in source_text
    assert "## Related knowledge" in source_text
    assert "typed-edge:depends-on/outgoing/" in source_text
    assert "[KB-B](#kb-kb-b)" in overview.read_text(encoding="utf-8")
    _assert_record_links_navigable(root)

    first_state = _wiki_state(root)
    time.sleep(1.1)
    second = _run(root, "wiki-sync", "--force", json_mode=True)
    second_state = _wiki_state(root)
    assert second["written_count"] == 0
    assert second["snapshots_created"] == []
    assert second_state == first_state
    assert _run(root, "wiki-lint", json_mode=True)["issue_count"] == 0
