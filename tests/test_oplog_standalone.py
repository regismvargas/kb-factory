"""Phase 2 Slice 4: Standalone operation logging extension tests.

Tests that standalone kb export, kb wiki-sync, and kb wiki-lint
create operation entries, and that lifecycle sub-actions do NOT
double-log.
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


@pytest.fixture(scope="module")
def standalone_kb(tmp_path_factory):
    kb_dir = tmp_path_factory.mktemp("standalone_kb")
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    config = {
        "schema_version": 4,
        "project": {"name": "Test KB", "slug": "test-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["test_domain"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "lifecycle": {"events": {
            "session_start": {"run_audit": True, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False},
            "session_end": {"run_audit": False, "apply_demotions": False, "refresh_exports": True, "run_wiki_check": False, "run_wiki_lint": True, "run_wiki_sync": False},
            "source_ingest": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": True},
        }},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {"enabled": False, "activation_mode": "policy", "page_types": ["domain_overview"], "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0}, "semantic": {"min_confidence_autopublish": 0.8, "min_confidence_review": 0.55}, "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}}},
    }
    (kb_dir / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    shutil.copy2(KB_PY, kb_dir / "kb.py")
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return kb_dir


def _run(kb_dir, *args, json_mode=True):
    cmd = [sys.executable, str(kb_dir / "kb.py")] + list(args)
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(kb_dir))
    if json_mode:
        return json.loads(r.stdout)
    return r.stdout.strip()


def _run_raw(kb_dir, sql):
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "raw-query", sql],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return json.loads(r.stdout)


def _op_count(kb_dir, category=None):
    if category:
        rows = _run_raw(kb_dir, f"SELECT COUNT(*) AS n FROM operations WHERE category = '{category}'")
    else:
        rows = _run_raw(kb_dir, "SELECT COUNT(*) AS n FROM operations")
    return rows[0]["n"]


# ---------------------------------------------------------------------------
# Standalone logging
# ---------------------------------------------------------------------------


class TestStandaloneExportLogging:
    def test_export_creates_operation_entry(self, standalone_kb):
        before = _op_count(standalone_kb, "export_refresh")
        _run(standalone_kb, "export", json_mode=False)
        after = _op_count(standalone_kb, "export_refresh")
        assert after == before + 1

    def test_export_entry_details(self, standalone_kb):
        ops = _run(standalone_kb, "oplog", "--category", "export_refresh", "--limit", "1")
        op = ops[0]
        assert op["category"] == "export_refresh"
        assert op["event"] == "export"
        assert "counts" in op["details"]
        assert "topics_written" in op["details"]["counts"]
        assert op["summary"].startswith("Exports refreshed:")


class TestStandaloneWikiSyncLogging:
    def test_wiki_sync_creates_operation_entry(self, standalone_kb):
        before = _op_count(standalone_kb, "wiki_sync")
        _run(standalone_kb, "wiki-sync", "--force")
        after = _op_count(standalone_kb, "wiki_sync")
        assert after == before + 1

    def test_wiki_sync_entry_details(self, standalone_kb):
        ops = _run(standalone_kb, "oplog", "--category", "wiki_sync", "--limit", "1")
        op = ops[0]
        assert op["category"] == "wiki_sync"
        assert op["event"] == "wiki-sync"
        assert "written_count" in op["details"]
        assert "forced" in op["details"]
        assert op["summary"].startswith("Wiki sync:")


class TestStandaloneWikiLintLogging:
    def test_wiki_lint_creates_operation_entry(self, standalone_kb):
        before = _op_count(standalone_kb, "wiki_lint")
        _run(standalone_kb, "wiki-lint")
        after = _op_count(standalone_kb, "wiki_lint")
        assert after == before + 1

    def test_wiki_lint_entry_details(self, standalone_kb):
        ops = _run(standalone_kb, "oplog", "--category", "wiki_lint", "--limit", "1")
        op = ops[0]
        assert op["category"] == "wiki_lint"
        assert op["event"] == "wiki-lint"
        assert "issue_count" in op["details"]
        assert op["summary"].startswith("Wiki lint:")


# ---------------------------------------------------------------------------
# Double-logging prevention
# ---------------------------------------------------------------------------


class TestNoDoubleLogging:
    def test_lifecycle_session_end_does_not_create_export_entry(self, standalone_kb):
        """session_end triggers refresh_exports internally, but must NOT create export_refresh entry."""
        before_export = _op_count(standalone_kb, "export_refresh")
        before_lifecycle = _op_count(standalone_kb, "lifecycle")
        _run(standalone_kb, "lifecycle", "session-end")
        after_export = _op_count(standalone_kb, "export_refresh")
        after_lifecycle = _op_count(standalone_kb, "lifecycle")
        assert after_export == before_export, "Lifecycle sub-action must NOT create export_refresh entry"
        assert after_lifecycle == before_lifecycle + 1, "Lifecycle must create its own entry"

    def test_lifecycle_session_end_does_not_create_wiki_lint_entry(self, standalone_kb):
        """session_end triggers wiki_lint internally, but must NOT create wiki_lint entry."""
        before_lint = _op_count(standalone_kb, "wiki_lint")
        _run(standalone_kb, "lifecycle", "session-end")
        after_lint = _op_count(standalone_kb, "wiki_lint")
        assert after_lint == before_lint, "Lifecycle sub-action must NOT create wiki_lint entry"

    def test_lifecycle_source_ingest_with_wiki_does_not_create_wiki_sync_entry(self, standalone_kb):
        """source-ingest with --sync-wiki triggers sync internally, but must NOT create wiki_sync entry."""
        before_sync = _op_count(standalone_kb, "wiki_sync")
        _run(standalone_kb, "lifecycle", "source-ingest", "--sync-wiki", "--force-wiki-sync")
        after_sync = _op_count(standalone_kb, "wiki_sync")
        assert after_sync == before_sync, "Lifecycle sub-action must NOT create wiki_sync entry"


# ---------------------------------------------------------------------------
# Data discipline
# ---------------------------------------------------------------------------


class TestDataDiscipline:
    def test_all_summaries_are_short(self, standalone_kb):
        ops = _run(standalone_kb, "oplog", "--limit", "20")
        for op in ops:
            if op.get("summary"):
                assert len(op["summary"]) < 200, f"Summary too long: {op['summary']}"

    def test_details_are_metadata_only(self, standalone_kb):
        ops = _run(standalone_kb, "oplog", "--limit", "20")
        allowed_keys = {
            "actions_run", "counts", "topics_written",
            "source_id", "filename", "skipped",
            "written_count", "skipped_count", "held_back_count", "forced",
            "issue_count",
        }
        for op in ops:
            for key in op["details"]:
                # Allow nested dicts like counts
                if isinstance(op["details"][key], dict):
                    continue
                assert key in allowed_keys, f"Unexpected detail key '{key}' in {op['category']}"
