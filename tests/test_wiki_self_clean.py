"""Hermetic self-clean tests for wiki-sync.

These tests run against a temporary, isolated KB built from the scaffold
template (never the live .kb), so they are deterministic and safe for CI.

They prove the self-clean contract: when the candidate set changes so that a
previously-generated managed live page is no longer produced by any candidate,
`wiki-sync` removes that obsolete page (file + DB rows) instead of leaving it to
rot as a stale page that cites resolved/changed records.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "kb"


def _config(page_types):
    return {
        "schema_version": 3,
        "project": {"name": "Test KB", "slug": "test-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["alpha", "beta"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "lifecycle": {"events": {"session_start": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False}}},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {
            "enabled": True,
            "activation_mode": "policy",
            "page_types": page_types,
            "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0},
            "semantic": {"min_confidence_autopublish": 0.5, "min_confidence_review": 0.4, "min_sources_research_synthesis": 2},
            "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}},
        },
    }


@pytest.fixture
def kb(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    shutil.copytree(TEMPLATE / "runtime", kb_dir / "runtime")
    shutil.copy2(TEMPLATE / "kb.py", kb_dir / "kb.py")
    (kb_dir / "kb.config.json").write_text(
        json.dumps(_config(["domain_overview", "research_synthesis", "source_page"])),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "kb.py", "init"],
        cwd=str(kb_dir), check=True, capture_output=True, text=True,
    )
    return kb_dir


def _run(kb_dir, *args, json_mode=False):
    cmd = [sys.executable, "kb.py", *args]
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, cwd=str(kb_dir), capture_output=True, text=True, check=True)
    return json.loads(r.stdout) if json_mode else r.stdout


def _set_page_types(kb_dir, page_types):
    cfg = json.loads((kb_dir / "kb.config.json").read_text(encoding="utf-8"))
    cfg["wiki"]["page_types"] = page_types
    (kb_dir / "kb.config.json").write_text(json.dumps(cfg), encoding="utf-8")


def _set_min_sources(kb_dir, n):
    cfg = json.loads((kb_dir / "kb.config.json").read_text(encoding="utf-8"))
    cfg["wiki"]["semantic"]["min_sources_research_synthesis"] = n
    (kb_dir / "kb.config.json").write_text(json.dumps(cfg), encoding="utf-8")


def _lint_issue_count(kb_dir):
    result = _run(kb_dir, "wiki-lint", json_mode=True)
    return result.get("issue_count", len(result.get("issues", [])))


def test_obsolete_managed_page_is_pruned_on_sync(kb):
    # Seed 3 active records in domain 'alpha' -> domain_overview candidate.
    for i in range(3):
        _run(kb, "create", "--category", "FATO", "--domain", "alpha",
             "--title", f"Alpha fact {i}", "--content", f"content {i}", "--tier", "WARM")
    sync1 = _run(kb, "wiki-sync", "--force", json_mode=True)
    page = kb / "wiki" / "live" / "alpha" / "overview.md"
    assert page.is_file(), f"expected alpha overview after sync; result={sync1}"
    assert _lint_issue_count(kb) == 0, "freshly synced wiki should lint clean"

    # Candidate set changes: domain_overview no longer produced -> alpha page obsolete.
    _set_page_types(kb, [])
    sync2 = _run(kb, "wiki-sync", "--force", json_mode=True)
    assert sync2["obsolete_removed"]["removed_count"] >= 1, f"expected a prune; result={sync2}"
    assert not page.exists(), "obsolete managed live page file should be removed"
    assert _lint_issue_count(kb) == 0, "after self-clean the wiki must lint clean"


def test_domain_scoped_sync_does_not_prune_other_domains(kb):
    # Two domains, each with a page.
    for dom in ("alpha", "beta"):
        for i in range(3):
            _run(kb, "create", "--category", "FATO", "--domain", dom,
                 "--title", f"{dom} fact {i}", "--content", f"c{i}", "--tier", "WARM")
    _run(kb, "wiki-sync", "--force")
    alpha = kb / "wiki" / "live" / "alpha" / "overview.md"
    beta = kb / "wiki" / "live" / "beta" / "overview.md"
    assert alpha.is_file() and beta.is_file()

    # Drop page types, but sync ONLY domain 'alpha': beta must be untouched.
    _set_page_types(kb, [])
    _run(kb, "wiki-sync", "--force", "--domain", "alpha", json_mode=True)
    assert not alpha.exists(), "alpha page should be pruned within its scope"
    assert beta.is_file(), "beta page must NOT be pruned by an alpha-scoped sync"


def test_unpublishable_held_back_page_is_pruned(kb):
    # With the source bar at 0, a record-only research_synthesis publishes.
    _set_min_sources(kb, 0)
    for i in range(3):
        _run(kb, "create", "--category", "FATO", "--domain", "alpha",
             "--title", f"Topic fact {i}", "--content", f"c{i}", "--tier", "WARM", "--tags", "topic")
    _run(kb, "wiki-sync", "--force")
    page = kb / "wiki" / "live" / "research" / "topic.md"
    assert page.is_file(), "research_synthesis page should publish when the source bar is met"
    assert _lint_issue_count(kb) == 0

    # Raise the bar: the candidate is now held back (0 < 2) and can no longer be
    # republished -> its existing managed page must be pruned (self-clean).
    _set_min_sources(kb, 2)
    sync = _run(kb, "wiki-sync", "--force", json_mode=True)
    assert sync["obsolete_removed"]["removed_count"] >= 1, f"expected prune of held-back page; {sync}"
    assert not page.exists(), "held-back, unpublishable page must be removed"
    assert _lint_issue_count(kb) == 0
