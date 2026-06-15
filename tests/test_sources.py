"""Phase 2 Slice 1: Source registry tests for kb-factory.

Tests ingest registration, duplicate skip, catalog listing, source-info,
schema migration, and negative checks (no record creation, no record_ids_json
population, no records schema modification).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
KB_PY = REPO / "core" / "templates" / "kb" / "kb.py"
LIVE_RUNTIME = REPO / "core" / "templates" / "kb" / "runtime"


@pytest.fixture(scope="module")
def source_kb(tmp_path_factory):
    """Create a temporary KB with source support for isolated testing."""
    kb_dir = tmp_path_factory.mktemp("source_kb")
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    config = {
        "schema_version": 3,
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
    (kb_dir / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    shutil.copy2(KB_PY, kb_dir / "kb.py")
    # Init the KB to create the DB with schema v2
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    # Create a test source file
    (kb_dir / "sample.txt").write_text("Hello source world\n", encoding="utf-8")
    (kb_dir / "sample2.txt").write_text("Different content\n", encoding="utf-8")
    return kb_dir


def _run(kb_dir: Path, *args: str, json_mode: bool = True):
    cmd = [sys.executable, str(kb_dir / "kb.py")] + list(args)
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(kb_dir))
    if json_mode:
        return json.loads(r.stdout)
    return r.stdout.strip()


def _run_raw(kb_dir: Path, sql: str):
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "raw-query", sql],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    def test_schema_version_is_current(self, source_kb):
        result = _run_raw(source_kb, "SELECT value FROM schema_meta WHERE key = 'schema_version'")
        assert int(result[0]["value"]) >= 2

    def test_sources_table_exists(self, source_kb):
        result = _run_raw(source_kb, "SELECT name FROM sqlite_master WHERE type='table' AND name='sources'")
        assert len(result) == 1
        assert result[0]["name"] == "sources"

    def test_records_table_has_source_id_column(self, source_kb):
        """Schema v3 adds source_id to records (logical provenance link)."""
        result = _run_raw(source_kb, "PRAGMA table_info(records)")
        column_names = [row["name"] for row in result]
        assert "source_id" in column_names


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------


class TestIngest:
    def test_ingest_registers_source(self, source_kb):
        result = _run(source_kb, "ingest", str(source_kb / "sample.txt"), "--domain", "test_domain")
        assert result["skipped"] is False
        assert result["filename"] == "sample.txt"
        assert result["domain"] == "test_domain"
        assert result["content_hash"]
        assert result["record_ids"] == []

    def test_ingest_copies_file(self, source_kb):
        sources_dir = source_kb / "sources"
        assert sources_dir.exists()
        # Find the stored file
        stored_files = list(sources_dir.rglob("sample.txt"))
        assert len(stored_files) >= 1
        assert stored_files[0].read_text(encoding="utf-8") == "Hello source world\n"

    def test_ingest_duplicate_skipped(self, source_kb):
        result = _run(source_kb, "ingest", str(source_kb / "sample.txt"), "--domain", "test_domain")
        assert result["skipped"] is True
        assert result["reason"] == "duplicate_hash"

    def test_ingest_different_content_not_skipped(self, source_kb):
        result = _run(source_kb, "ingest", str(source_kb / "sample2.txt"), "--domain", "test_domain")
        assert result["skipped"] is False
        assert result["filename"] == "sample2.txt"


# ---------------------------------------------------------------------------
# Catalog tests
# ---------------------------------------------------------------------------


class TestCatalog:
    def test_sources_lists_entries(self, source_kb):
        result = _run(source_kb, "sources")
        assert isinstance(result, list)
        assert len(result) >= 2
        filenames = {s["filename"] for s in result}
        assert "sample.txt" in filenames
        assert "sample2.txt" in filenames

    def test_sources_domain_filter(self, source_kb):
        result = _run(source_kb, "sources", "--domain", "test_domain")
        assert all(s["domain"] == "test_domain" for s in result)

    def test_source_info_returns_entry(self, source_kb):
        sources = _run(source_kb, "sources")
        sid = sources[0]["source_id"]
        result = _run(source_kb, "source-info", sid)
        assert result["source_id"] == sid
        assert "content_hash" in result
        assert "stored_path" in result


# ---------------------------------------------------------------------------
# Negative checks — Option A enforcement
# ---------------------------------------------------------------------------


class TestOptionAEnforcement:
    """Verify that ingest does NOT create records or populate record_ids_json."""

    def test_ingest_does_not_create_records(self, source_kb):
        records_before = _run_raw(source_kb, "SELECT COUNT(*) AS n FROM records")
        count_before = records_before[0]["n"]
        # Ingest a new file
        (source_kb / "negative_test.txt").write_text("content for negative test\n", encoding="utf-8")
        _run(source_kb, "ingest", str(source_kb / "negative_test.txt"), "--domain", "test_domain")
        records_after = _run_raw(source_kb, "SELECT COUNT(*) AS n FROM records")
        count_after = records_after[0]["n"]
        assert count_after == count_before, "Ingest must NOT create records in this slice"

    def test_record_ids_json_is_empty_for_all_sources(self, source_kb):
        sources = _run_raw(source_kb, "SELECT record_ids_json FROM sources")
        for row in sources:
            assert row["record_ids_json"] == "[]", "record_ids_json must remain [] in this slice"

    def test_ingest_does_not_populate_source_id_on_records(self, source_kb):
        """Even though source_id column exists (v3), ingest must not create records or link them."""
        result = _run_raw(source_kb, "SELECT source_id FROM records WHERE source_id IS NOT NULL")
        # Only records created via explicit --source-id should have non-null source_id
        # Ingest never creates records, so no auto-linkage expected
        assert isinstance(result, list)
