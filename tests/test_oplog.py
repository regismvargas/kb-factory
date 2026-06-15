"""Phase 2 Slice 3: Operation log tests for kb-factory.

Tests operation logging for lifecycle and ingest events, oplog query,
and negative checks (standalone export/wiki do NOT log, record CRUD
does NOT log, data discipline enforced).
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
def oplog_kb(tmp_path_factory):
    """Create a temporary KB with schema v4 for isolated oplog testing."""
    kb_dir = tmp_path_factory.mktemp("oplog_kb")
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
        }},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {"enabled": False, "activation_mode": "policy", "page_types": [], "eligibility": {"min_active_records": 30, "min_domains_with_records": 2, "min_soft_signal_score": 1}, "semantic": {"min_confidence_autopublish": 0.8, "min_confidence_review": 0.55}, "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}}},
    }
    (kb_dir / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    shutil.copy2(KB_PY, kb_dir / "kb.py")
    # Init the KB
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    # Create test source files
    (kb_dir / "test_source.txt").write_text("Test source for oplog\n", encoding="utf-8")
    (kb_dir / "test_source_dup.txt").write_text("Test source for oplog\n", encoding="utf-8")  # same content = duplicate
    return kb_dir


def _run(kb_dir: Path, *args: str, json_mode: bool = True, check: bool = True):
    cmd = [sys.executable, str(kb_dir / "kb.py")] + list(args)
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, check=check, cwd=str(kb_dir))
    if json_mode and r.returncode == 0:
        return json.loads(r.stdout)
    return r


def _run_raw(kb_dir: Path, sql: str):
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "raw-query", sql],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return json.loads(r.stdout)


def _op_count(kb_dir: Path, category: str | None = None) -> int:
    if category:
        rows = _run_raw(kb_dir, f"SELECT COUNT(*) AS n FROM operations WHERE category = '{category}'")
    else:
        rows = _run_raw(kb_dir, "SELECT COUNT(*) AS n FROM operations")
    return rows[0]["n"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchemaV4:
    def test_schema_version_is_4(self, oplog_kb):
        result = _run_raw(oplog_kb, "SELECT value FROM schema_meta WHERE key = 'schema_version'")
        assert result[0]["value"] == "4"

    def test_operations_table_exists(self, oplog_kb):
        result = _run_raw(oplog_kb, "SELECT name FROM sqlite_master WHERE type='table' AND name='operations'")
        assert len(result) == 1

    def test_operations_columns(self, oplog_kb):
        result = _run_raw(oplog_kb, "PRAGMA table_info(operations)")
        cols = {r["name"] for r in result}
        assert cols == {"op_id", "category", "event", "happened_at", "details_json", "summary"}


# ---------------------------------------------------------------------------
# Lifecycle logging
# ---------------------------------------------------------------------------


class TestLifecycleLogging:
    def test_lifecycle_creates_operation_entry(self, oplog_kb):
        count_before = _op_count(oplog_kb, "lifecycle")
        _run(oplog_kb, "lifecycle", "session-start")
        count_after = _op_count(oplog_kb, "lifecycle")
        assert count_after == count_before + 1

    def test_lifecycle_entry_has_correct_fields(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--category", "lifecycle", "--limit", "1")
        assert len(ops) >= 1
        op = ops[0]
        assert op["category"] == "lifecycle"
        assert op["event"] == "session-start"
        assert "actions_run" in op["details"]
        assert "counts" in op["details"]
        assert op["summary"].startswith("Lifecycle session-start:")

    def test_lifecycle_summary_is_short(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--category", "lifecycle", "--limit", "1")
        summary = ops[0]["summary"]
        assert len(summary) < 200, "summary must be short and derived"

    def test_lifecycle_details_is_metadata_only(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--category", "lifecycle", "--limit", "1")
        details = ops[0]["details"]
        # Should only contain operational metadata
        for key in details:
            assert key in ("actions_run", "counts"), f"Unexpected key in details: {key}"


# ---------------------------------------------------------------------------
# Ingest logging
# ---------------------------------------------------------------------------


class TestIngestLogging:
    def test_ingest_creates_operation_entry(self, oplog_kb):
        count_before = _op_count(oplog_kb, "source_ingest")
        _run(oplog_kb, "ingest", str(oplog_kb / "test_source.txt"), "--domain", "test_domain")
        count_after = _op_count(oplog_kb, "source_ingest")
        assert count_after == count_before + 1

    def test_ingest_entry_has_correct_fields(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--category", "source_ingest", "--limit", "1")
        assert len(ops) >= 1
        op = ops[0]
        assert op["category"] == "source_ingest"
        assert op["event"] == "ingest"
        assert "source_id" in op["details"]
        assert "filename" in op["details"]
        assert op["details"]["skipped"] is False

    def test_duplicate_ingest_logs_with_skipped_true(self, oplog_kb):
        count_before = _op_count(oplog_kb, "source_ingest")
        _run(oplog_kb, "ingest", str(oplog_kb / "test_source_dup.txt"), "--domain", "test_domain")
        count_after = _op_count(oplog_kb, "source_ingest")
        assert count_after == count_before + 1
        ops = _run(oplog_kb, "oplog", "--category", "source_ingest", "--limit", "1")
        assert ops[0]["details"]["skipped"] is True


# ---------------------------------------------------------------------------
# Oplog query
# ---------------------------------------------------------------------------


class TestOplogQuery:
    def test_oplog_lists_all(self, oplog_kb):
        ops = _run(oplog_kb, "oplog")
        assert isinstance(ops, list)
        assert len(ops) >= 2  # at least lifecycle + ingest

    def test_oplog_category_filter(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--category", "lifecycle")
        assert all(op["category"] == "lifecycle" for op in ops)

    def test_oplog_limit(self, oplog_kb):
        ops = _run(oplog_kb, "oplog", "--limit", "1")
        assert len(ops) <= 1


# ---------------------------------------------------------------------------
# Negative checks
# ---------------------------------------------------------------------------


class TestNegativeChecks:
    def test_standalone_export_logs_operation(self, oplog_kb):
        """WP-KBF.06: standalone export now logs export_refresh."""
        count_before = _op_count(oplog_kb, "export_refresh")
        _run(oplog_kb, "export", json_mode=False)
        count_after = _op_count(oplog_kb, "export_refresh")
        assert count_after == count_before + 1

    def test_standalone_wiki_sync_logs_operation(self, oplog_kb):
        """WP-KBF.06: standalone wiki-sync now logs wiki_sync."""
        count_before = _op_count(oplog_kb, "wiki_sync")
        _run(oplog_kb, "wiki-sync", "--force")
        count_after = _op_count(oplog_kb, "wiki_sync")
        assert count_after == count_before + 1

    def test_record_crud_does_not_log(self, oplog_kb):
        count_before = _op_count(oplog_kb)
        _run(oplog_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Oplog negative test", "--content", "Should not log operation",
            "--source", "test",
        )
        count_after = _op_count(oplog_kb)
        assert count_after == count_before, "Record CRUD must NOT create operation entry"

    def test_ingest_still_register_only(self, oplog_kb):
        records_before = _run_raw(oplog_kb, "SELECT COUNT(*) AS n FROM records")[0]["n"]
        (oplog_kb / "negative_test.txt").write_text("Should not create records\n", encoding="utf-8")
        _run(oplog_kb, "ingest", str(oplog_kb / "negative_test.txt"), "--domain", "test_domain")
        records_after = _run_raw(oplog_kb, "SELECT COUNT(*) AS n FROM records")[0]["n"]
        # Only the one record created by test_record_crud_does_not_log should exist
        assert records_after == records_before, "Ingest must NOT create records"
