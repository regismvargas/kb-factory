"""Append-only integrity tests.

Covers:
- `raw-query` is read-only by default (PRAGMA query_only) and writable only with
  --allow-write.
- The opt-in `harden` command installs SQLite triggers that block direct
  UPDATE of a record's title/content and DELETE of records, while leaving the
  normal `update`/`supersede` workflow intact.
- `doctor` reports the hardening state, and `harden --off` removes the triggers.

All exercised through the scaffold CLI (no direct DB access needed): with
hardening on, `raw-query --allow-write "DELETE FROM records"` is aborted by the
trigger *before* any row is removed, so the assertions are non-destructive.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
KB_PY = REPO / "core" / "templates" / "kb" / "kb.py"
LIVE_RUNTIME = REPO / "core" / "templates" / "kb" / "runtime"

CONFIG = {
    "schema_version": 5,
    "project": {"name": "Test KB", "slug": "test-kb", "primary_repo_path": ".", "kb_root": "."},
    "domains": ["test_domain"],
    "hot_session_limit": 10,
    "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
    "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
    "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
    "lifecycle": {"events": {"session_start": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False}}},
    "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
    "wiki": {"enabled": False, "activation_mode": "policy", "page_types": [], "eligibility": {"min_active_records": 30, "min_domains_with_records": 2, "min_soft_signal_score": 1}, "semantic": {"min_confidence_autopublish": 0.8, "min_confidence_review": 0.55}, "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}}},
}


def _run(kb_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), *args],
        capture_output=True, text=True, check=check, cwd=str(kb_dir),
    )


@pytest.fixture()
def kb(tmp_path: Path) -> Path:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    shutil.copy2(KB_PY, kb_dir / "kb.py")
    (kb_dir / "kb.config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    _run(kb_dir, "init")
    _run(kb_dir, "create", "--id", "REC1", "--category", "DECISAO",
         "--domain", "test_domain", "--title", "Original title",
         "--content", "Original content.", "--json")
    return kb_dir


def test_raw_query_read_only_by_default(kb: Path) -> None:
    # A write via raw-query is rejected unless --allow-write is passed.
    blocked = _run(kb, "raw-query", "DELETE FROM records WHERE 1=0", check=False)
    assert blocked.returncode != 0
    assert "readonly" in (blocked.stderr + blocked.stdout).lower()
    # With the opt-out flag, the same (no-op) write is accepted.
    allowed = _run(kb, "raw-query", "--allow-write", "DELETE FROM records WHERE 1=0", check=False)
    assert allowed.returncode == 0
    # Reads always work.
    read = _run(kb, "raw-query", "SELECT COUNT(*) AS n FROM records", check=False)
    assert read.returncode == 0


def test_harden_blocks_direct_delete_and_content_update(kb: Path) -> None:
    _run(kb, "harden")
    # The trigger aborts the DELETE before any row is removed (--allow-write
    # disables the read-only guard, so this isolates the trigger itself).
    deleted = _run(kb, "raw-query", "--allow-write", "DELETE FROM records", check=False)
    assert deleted.returncode != 0
    assert "append-only" in (deleted.stderr + deleted.stdout).lower()
    # A direct content edit is also blocked.
    edited = _run(kb, "raw-query", "--allow-write",
                  "UPDATE records SET content='tampered' WHERE id='REC1'", check=False)
    assert edited.returncode != 0
    # The record and its content are intact.
    rows = json.loads(_run(kb, "raw-query", "SELECT content FROM records WHERE id='REC1'").stdout)
    assert rows[0]["content"] == "Original content."


def test_harden_allows_supersede_and_metadata_update(kb: Path) -> None:
    _run(kb, "harden")
    # Routing-metadata update (tier) still works.
    _run(kb, "update", "REC1", "--tier", "COLD", "--json")
    # Supersession still works (new row + old marked SUPERSEDIDO).
    _run(kb, "supersede", "REC1", "--title", "New title",
         "--content", "New content.", "--json")
    statuses = json.loads(_run(kb, "raw-query",
        "SELECT status FROM records WHERE id='REC1'").stdout)
    assert statuses[0]["status"] == "SUPERSEDIDO"
    total = json.loads(_run(kb, "raw-query", "SELECT COUNT(*) AS n FROM records").stdout)
    assert total[0]["n"] == 2  # original (superseded) + replacement


def test_doctor_reports_hardening_state(kb: Path) -> None:
    before = json.loads(_run(kb, "doctor", "--json").stdout)
    assert before["append_only_hardening"] == "disabled"
    _run(kb, "harden")
    after = json.loads(_run(kb, "doctor", "--json").stdout)
    assert after["append_only_hardening"] == "enabled"


def test_harden_off_removes_triggers(kb: Path) -> None:
    _run(kb, "harden")
    _run(kb, "harden", "--off")
    state = json.loads(_run(kb, "doctor", "--json").stdout)
    assert state["append_only_hardening"] == "disabled"
    # With triggers gone, a writable no-op DELETE is accepted again.
    ok = _run(kb, "raw-query", "--allow-write", "DELETE FROM records WHERE 1=0", check=False)
    assert ok.returncode == 0
