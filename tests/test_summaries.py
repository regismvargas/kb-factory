"""Phase 2 Slice 5: Source summary tooling tests.

Tests summarize-status, source-content, canonicality (one summary per source),
supersede-for-re-summary, text-only boundary, and oplog wiring.
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
def summary_kb(tmp_path_factory):
    kb_dir = tmp_path_factory.mktemp("summary_kb")
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    config = {
        "schema_version": 4,
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
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    # Create and ingest a text source
    (kb_dir / "report.txt").write_text("Quarterly revenue grew 15%. Market share stable.\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "ingest", str(kb_dir / "report.txt"), "--domain", "test_domain", "--json"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    src = json.loads(r.stdout)
    (kb_dir / ".test_source_id").write_text(src["source_id"], encoding="utf-8")
    # Create a binary file and ingest it
    (kb_dir / "image.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "ingest", str(kb_dir / "image.bin"), "--domain", "test_domain", "--json"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
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


def _run_raw(kb_dir, sql):
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "raw-query", sql],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------
# source-content
# ---------------------------------------------------------------------------


class TestSourceContent:
    def test_reads_text_source(self, summary_kb):
        sid = _sid(summary_kb)
        result = _run(summary_kb, "source-content", sid)
        assert "Quarterly revenue" in result["content"]
        assert result["encoding"] == "utf-8"
        assert result["size"] > 0

    def test_hard_fails_on_binary(self, summary_kb):
        # Find binary source
        sources = _run(summary_kb, "sources")
        bin_src = [s for s in sources if s["filename"] == "image.bin"]
        assert len(bin_src) == 1
        r = _run(summary_kb, "source-content", bin_src[0]["source_id"], check=False, json_mode=False)
        assert r.returncode != 0
        assert "not a supported text format" in r.stderr

    def test_logs_source_access_operation(self, summary_kb):
        sid = _sid(summary_kb)
        _run(summary_kb, "source-content", sid)
        ops = _run(summary_kb, "oplog", "--category", "source_access")
        access_ops = [o for o in ops if o["details"].get("source_id") == sid]
        assert len(access_ops) >= 1


# ---------------------------------------------------------------------------
# summarize-status
# ---------------------------------------------------------------------------


class TestSummarizeStatus:
    def test_shows_unsummarized_source(self, summary_kb):
        sid = _sid(summary_kb)
        status = _run(summary_kb, "summarize-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_summary"] is False
        assert entry["summary_record_id"] is None

    def test_shows_summarized_after_create(self, summary_kb):
        sid = _sid(summary_kb)
        record = _run(summary_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Summary: report.txt",
            "--content", "Overview: Q report.\n\nKey points:\n- Revenue up 15%\n\nScope: Financial quarter.",
            "--source", "source-summary", "--source-id", sid,
            "--tags", "source-summary", "--confidence", "0.85",
        )
        status = _run(summary_kb, "summarize-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_summary"] is True
        assert entry["summary_record_id"] == record["id"]

    def test_domain_filter(self, summary_kb):
        status = _run(summary_kb, "summarize-status", "--domain", "test_domain")
        assert all(s["domain"] == "test_domain" for s in status)


# ---------------------------------------------------------------------------
# Canonicality — one summary per source
# ---------------------------------------------------------------------------


class TestCanonicality:
    def test_supersede_updates_summary_record_id(self, summary_kb):
        sid = _sid(summary_kb)
        # Find existing summary
        status = _run(summary_kb, "summarize-status")
        entry = next(s for s in status if s["source_id"] == sid)
        old_id = entry["summary_record_id"]
        assert old_id is not None
        # Supersede
        new_record = _run(summary_kb, "supersede", old_id,
            "--content", "Overview: Updated Q report.\n\nKey points:\n- Revenue up 15%\n- Market stable\n\nScope: Updated financial quarter.",
            "--source-id", sid, "--tags", "source-summary",
        )
        # Verify
        status = _run(summary_kb, "summarize-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_summary"] is True
        assert entry["summary_record_id"] == new_record["id"]
        assert entry["summary_record_id"] != old_id

    def test_detects_multiple_active_summaries(self, summary_kb):
        sid = _sid(summary_kb)
        # Create a second summary (breaking canonicality intentionally for test)
        _run(summary_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Summary: report.txt (duplicate)",
            "--content", "Duplicate summary.",
            "--source", "source-summary", "--source-id", sid,
            "--tags", "source-summary",
        )
        status = _run(summary_kb, "summarize-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_summary"] is True
        assert entry.get("warning") == "multiple_active_summaries"
        assert len(entry.get("active_summary_ids", [])) >= 2


# ---------------------------------------------------------------------------
# Negative checks
# ---------------------------------------------------------------------------


class TestNegativeChecks:
    def test_source_content_not_in_exports(self, summary_kb):
        _run(summary_kb, "export", json_mode=False)
        now_md = (summary_kb / "memory" / "NOW.md").read_text(encoding="utf-8")
        assert "Quarterly revenue" not in now_md, "Raw source content must NOT appear in exports"
        hot_md = (summary_kb / "memory" / "HOT.md").read_text(encoding="utf-8")
        assert "Quarterly revenue" not in hot_md
