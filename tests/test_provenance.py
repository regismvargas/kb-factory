"""Phase 2 Slice 2: Source provenance linkage tests for kb-factory.

Tests source_id logical link on records, application-level validation,
supersede inheritance, bulk-import support, export attribution,
and negative checks (no DB FK, ingest still register-only).
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
def prov_kb(tmp_path_factory):
    """Create a temporary KB with schema v3 for isolated provenance testing."""
    kb_dir = tmp_path_factory.mktemp("prov_kb")
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
    # Init the KB
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    # Create a source file and ingest it
    (kb_dir / "test_doc.txt").write_text("Provenance test document\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "ingest", str(kb_dir / "test_doc.txt"), "--domain", "test_domain", "--json"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    source = json.loads(r.stdout)
    # Store source_id in a file since WindowsPath doesn't allow arbitrary attributes
    (kb_dir / ".test_source_id").write_text(source["source_id"], encoding="utf-8")
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


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemaV3:
    def test_schema_version_is_3(self, prov_kb):
        result = _run_raw(prov_kb, "SELECT value FROM schema_meta WHERE key = 'schema_version'")
        assert result[0]["value"] == "3"

    def test_records_table_has_source_id_column(self, prov_kb):
        result = _run_raw(prov_kb, "PRAGMA table_info(records)")
        column_names = [row["name"] for row in result]
        assert "source_id" in column_names

    def test_source_id_is_not_db_enforced_fk(self, prov_kb):
        result = _run_raw(prov_kb, "PRAGMA foreign_key_list(records)")
        fk_targets = [row.get("table") for row in result]
        assert "sources" not in fk_targets, "source_id must be logical, not a DB-enforced FK"


# ---------------------------------------------------------------------------
# Linked record creation
# ---------------------------------------------------------------------------


class TestLinkedCreate:
    def test_create_with_source_id(self, prov_kb):
        sid = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        result = _run(prov_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Linked fact", "--content", "From source",
            "--source", "test", "--source-id", sid,
        )
        assert result["source_id"] == sid

    def test_source_record_ids_json_updated(self, prov_kb):
        sid = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        info = _run(prov_kb, "source-info", sid)
        assert len(info["record_ids"]) >= 1, "record_ids_json should include the linked record"

    def test_create_without_source_id_works(self, prov_kb):
        result = _run(prov_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Unlinked fact", "--content", "No source link",
            "--source", "manual",
        )
        assert result.get("source_id") is None

    def test_create_with_nonexistent_source_id_fails(self, prov_kb):
        r = _run(prov_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Bad link", "--content", "Should fail",
            "--source", "test", "--source-id", "NONEXISTENT-SOURCE",
            check=False, json_mode=False,
        )
        assert r.returncode != 0, "Must reject nonexistent source_id"


# ---------------------------------------------------------------------------
# Supersede inheritance
# ---------------------------------------------------------------------------


class TestSupersedeProvenance:
    def test_supersede_inherits_source_id(self, prov_kb):
        sid = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        # Create a linked record
        original = _run(prov_kb, "create",
            "--category", "PREMISSA", "--domain", "test_domain",
            "--title", "To supersede", "--content", "Original",
            "--source", "test", "--source-id", sid,
        )
        # Supersede without --source-id
        replacement = _run(prov_kb, "supersede", original["id"],
            "--title", "Superseded version", "--content", "Updated",
        )
        assert replacement["source_id"] == sid, "Must inherit source_id from original"

    def test_supersede_overrides_source_id(self, prov_kb):
        # Create a second source
        (prov_kb / "second_doc.txt").write_text("Second source\n", encoding="utf-8")
        src2 = _run(prov_kb, "ingest", str(prov_kb / "second_doc.txt"), "--domain", "test_domain")
        sid2 = src2["source_id"]

        # Create a record linked to first source
        sid1 = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        original = _run(prov_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Override test", "--content", "Original",
            "--source", "test", "--source-id", sid1,
        )
        # Supersede with --source-id pointing to second source
        replacement = _run(prov_kb, "supersede", original["id"],
            "--title", "Override version", "--content", "Updated",
            "--source-id", sid2,
        )
        assert replacement["source_id"] == sid2, "Must use overridden source_id"


# ---------------------------------------------------------------------------
# Bulk import with source_id
# ---------------------------------------------------------------------------


class TestBulkImportProvenance:
    def test_bulk_import_with_source_id(self, prov_kb):
        sid = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        record = {
            "id": "TEST-PROV-BULK-001",
            "category": "FATO",
            "domain": "test_domain",
            "title": "Bulk linked",
            "content": "Imported with source_id",
            "source_id": sid,
        }
        seed_file = prov_kb / "prov_seed.jsonl"
        seed_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
        _run(prov_kb, "bulk-import", str(seed_file), json_mode=False)
        result = _run(prov_kb, "get", "TEST-PROV-BULK-001")
        assert result["source_id"] == sid


# ---------------------------------------------------------------------------
# Export attribution
# ---------------------------------------------------------------------------


class TestExportAttribution:
    def test_export_shows_source_attribution(self, prov_kb):
        sid = (prov_kb / ".test_source_id").read_text(encoding="utf-8").strip()
        # Create a HOT linked record so it shows in exports
        _run(prov_kb, "create",
            "--category", "DECISAO", "--domain", "test_domain",
            "--title", "HOT linked decision", "--content", "Appears in exports",
            "--source", "test", "--tier", "HOT", "--source-id", sid,
        )
        _run(prov_kb, "export", json_mode=False)
        hot_md = (prov_kb / "memory" / "HOT.md").read_text(encoding="utf-8")
        assert f"(source: {sid})" in hot_md, "HOT.md should show source attribution for linked records"


# ---------------------------------------------------------------------------
# Negative checks
# ---------------------------------------------------------------------------


class TestNegativeChecks:
    def test_ingest_still_register_only(self, prov_kb):
        records_before = _run_raw(prov_kb, "SELECT COUNT(*) AS n FROM records")[0]["n"]
        (prov_kb / "negative_check.txt").write_text("Negative check content\n", encoding="utf-8")
        _run(prov_kb, "ingest", str(prov_kb / "negative_check.txt"), "--domain", "test_domain")
        records_after = _run_raw(prov_kb, "SELECT COUNT(*) AS n FROM records")[0]["n"]
        assert records_after == records_before, "Ingest must NOT create records"

    def test_no_create_record_flag_on_ingest(self, prov_kb):
        r = subprocess.run(
            [sys.executable, str(prov_kb / "kb.py"), "ingest", "--help"],
            capture_output=True, text=True, cwd=str(prov_kb),
        )
        assert "--create-record" not in r.stdout, "ingest must not have --create-record flag"
