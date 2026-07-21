"""Phase 3 Slice 5: Filing path for durable answers and analyses.

Tests the `file` command, `filing-status` command, oplog integration,
wiki surfacing, and backward compatibility with existing create/analysis-status.
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
def filing_kb(tmp_path_factory):
    kb_dir = tmp_path_factory.mktemp("filing_kb")
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    config = {
        "schema_version": 4,
        "project": {"name": "Test KB", "slug": "test-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["test_domain", "other_domain"],
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
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    # Ingest a source for source-linked filing tests
    (kb_dir / "report.txt").write_text("Quarterly revenue report Q1 2026.\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "ingest", str(kb_dir / "report.txt"), "--domain", "test_domain", "--json"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    src = json.loads(r.stdout)
    (kb_dir / ".test_source_id").write_text(src["source_id"], encoding="utf-8")
    return kb_dir


def _sid(kb_dir):
    return (kb_dir / ".test_source_id").read_text(encoding="utf-8").strip()


def _run(kb_dir, *args, json_mode=True, check=True):
    cmd = [sys.executable, str(kb_dir / "kb.py")] + list(args)
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, check=check, cwd=str(kb_dir))
    if json_mode and r.returncode == 0:
        return json.loads(r.stdout)
    return r


# ---------------------------------------------------------------------------
# File command basics
# ---------------------------------------------------------------------------


class TestFileCommand:
    def test_file_answer_creates_record(self, filing_kb):
        record = _run(filing_kb, "file",
            "--filing-type", "answer",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Key insight on market dynamics",
            "--content", "The LATAM market shows strong growth potential due to demographic shifts.",
        )
        assert record["id"].startswith("KB-")
        assert record["category"] == "APRENDIZADO"
        assert record["domain"] == "test_domain"
        assert "filed-answer" in record["tags"]
        assert record["status"] == "ATIVO"

    def test_file_analysis_creates_record(self, filing_kb):
        sid = _sid(filing_kb)
        record = _run(filing_kb, "file",
            "--filing-type", "analysis",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Analysis: report.txt",
            "--content", "Revenue trends indicate sustained growth.",
            "--source-id", sid,
        )
        assert "filed-analysis" in record["tags"]
        assert record["source_id"] == sid

    def test_file_synthesis_creates_record(self, filing_kb):
        record = _run(filing_kb, "file",
            "--filing-type", "synthesis",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Cross-source synthesis on LATAM entry",
            "--content", "Multiple signals converge on LATAM as the priority market.",
        )
        assert "filed-synthesis" in record["tags"]

    def test_file_preserves_user_tags(self, filing_kb):
        record = _run(filing_kb, "file",
            "--filing-type", "answer",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Tagged insight",
            "--content", "Testing tag preservation.",
            "--tags", "custom-tag,strategic",
        )
        assert "custom-tag" in record["tags"]
        assert "strategic" in record["tags"]
        assert "filed-answer" in record["tags"]

    def test_file_default_source_is_filed(self, filing_kb):
        record = _run(filing_kb, "file",
            "--filing-type", "answer",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Default source check",
            "--content", "Checking default source field.",
        )
        assert record["source"] == "filed"

    def test_file_requires_filing_type(self, filing_kb):
        r = _run(filing_kb, "file",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Missing type", "--content", "Should fail.",
            json_mode=False, check=False,
        )
        assert r.returncode != 0

    def test_file_rejects_invalid_filing_type(self, filing_kb):
        r = _run(filing_kb, "file",
            "--filing-type", "invalid",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Bad type", "--content", "Should fail.",
            json_mode=False, check=False,
        )
        assert r.returncode != 0

    def test_file_does_not_duplicate_tag(self, filing_kb):
        record = _run(filing_kb, "file",
            "--filing-type", "answer",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Dedup tag test",
            "--content", "Tag should appear once.",
            "--tags", "filed-answer",
        )
        assert record["tags"].count("filed-answer") == 1


# ---------------------------------------------------------------------------
# Oplog integration
# ---------------------------------------------------------------------------


class TestFileOplog:
    def test_file_creates_operation_entry(self, filing_kb):
        ops_before = _run(filing_kb, "oplog", "--category", "record_filing")
        count_before = len(ops_before)
        _run(filing_kb, "file",
            "--filing-type", "answer",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Oplog test filing",
            "--content", "Should create oplog entry.",
        )
        ops_after = _run(filing_kb, "oplog", "--category", "record_filing")
        assert len(ops_after) > count_before

    def test_file_operation_has_correct_category(self, filing_kb):
        ops = _run(filing_kb, "oplog", "--category", "record_filing")
        assert len(ops) > 0
        assert all(op["category"] == "record_filing" for op in ops)

    def test_file_operation_has_correct_event(self, filing_kb):
        _run(filing_kb, "file",
            "--filing-type", "synthesis",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Event check synthesis",
            "--content", "Checking event field.",
        )
        ops = _run(filing_kb, "oplog", "--category", "record_filing", "--limit", "1")
        assert ops[0]["event"] == "file-synthesis"

    def test_file_operation_details(self, filing_kb):
        ops = _run(filing_kb, "oplog", "--category", "record_filing", "--limit", "1")
        details = ops[0]["details"]
        assert "filing_type" in details
        assert "record_id" in details
        assert "domain" in details
        assert "title" in details

    def test_regular_create_does_not_log_operation(self, filing_kb):
        ops_before = _run(filing_kb, "oplog", "--category", "record_filing")
        count_before = len(ops_before)
        _run(filing_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Regular create",
            "--content", "Should NOT create oplog filing entry.",
        )
        ops_after = _run(filing_kb, "oplog", "--category", "record_filing")
        assert len(ops_after) == count_before


# ---------------------------------------------------------------------------
# Filing status
# ---------------------------------------------------------------------------


class TestFilingStatus:
    def test_filing_status_counts(self, filing_kb):
        status = _run(filing_kb, "filing-status")
        assert status["total_filed"] > 0
        assert "by_type" in status
        assert "by_domain" in status
        assert "by_confidence" in status

    def test_filing_status_counts_by_type(self, filing_kb):
        status = _run(filing_kb, "filing-status")
        assert status["by_type"]["answer"] > 0
        assert status["by_type"]["analysis"] > 0
        assert status["by_type"]["synthesis"] > 0

    def test_filing_status_domain_filter(self, filing_kb):
        status = _run(filing_kb, "filing-status", "--domain", "test_domain")
        assert all(item["domain"] == "test_domain" for item in status["items"])

    def test_filing_status_confidence_bands(self, filing_kb):
        status = _run(filing_kb, "filing-status")
        total_conf = sum(status["by_confidence"].values())
        assert total_conf == status["total_filed"]

    def test_filing_status_gap_analysis(self, filing_kb):
        # Create a record in other_domain but no filing
        _run(filing_kb, "create",
            "--category", "FATO", "--domain", "other_domain",
            "--title", "Unfiled record",
            "--content", "This domain has records but no filings.",
        )
        status = _run(filing_kb, "filing-status")
        assert "other_domain" in status["gaps"]

    def test_filing_status_human_output(self, filing_kb):
        r = _run(filing_kb, "filing-status", json_mode=False)
        assert "Filing status:" in r.stdout


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestFilingBackwardCompat:
    def test_analysis_status_still_works(self, filing_kb):
        status = _run(filing_kb, "analysis-status")
        assert isinstance(status, list)

    def test_create_with_filed_analysis_tag_still_works(self, filing_kb):
        sid = _sid(filing_kb)
        record = _run(filing_kb, "create",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Manual analysis via create",
            "--content", "Filed using the old create path.",
            "--source", "filed-analysis", "--source-id", sid,
            "--tags", "filed-analysis",
        )
        assert "filed-analysis" in record["tags"]
        assert record["source_id"] == sid

    def test_schema_version_is_6(self, filing_kb):
        r = subprocess.run(
            [sys.executable, str(filing_kb / "kb.py"), "raw-query",
             "SELECT value FROM schema_meta WHERE key = 'schema_version'"],
            capture_output=True, text=True, check=True, cwd=str(filing_kb),
        )
        result = json.loads(r.stdout)
        assert result[0]["value"] == "6"

    def test_create_command_unchanged(self, filing_kb):
        record = _run(filing_kb, "create",
            "--category", "DECISAO", "--domain", "test_domain",
            "--title", "Standard create test",
            "--content", "Verifying create still works as before.",
        )
        assert record["source"] == "manual"
        assert record["status"] == "ATIVO"
