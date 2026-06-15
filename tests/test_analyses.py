"""Phase 2 Slice 6: Filed analyses tests.

Tests analysis-status, canonicality (one per source), supersede,
coexistence with summaries, and single-source constraint.
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
def analysis_kb(tmp_path_factory):
    kb_dir = tmp_path_factory.mktemp("analysis_kb")
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
    # Ingest a source
    (kb_dir / "memo.txt").write_text("Strategic memo: market entry plan for LATAM.\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "ingest", str(kb_dir / "memo.txt"), "--domain", "test_domain", "--json"],
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
# analysis-status basics
# ---------------------------------------------------------------------------


class TestAnalysisStatus:
    def test_shows_no_analysis(self, analysis_kb):
        sid = _sid(analysis_kb)
        status = _run(analysis_kb, "analysis-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_analysis"] is False
        assert entry["analysis_record_id"] is None

    def test_shows_analysis_after_create(self, analysis_kb):
        sid = _sid(analysis_kb)
        record = _run(analysis_kb, "create",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Analysis: memo.txt",
            "--content", "Thesis: LATAM entry is viable.\n\nSupporting evidence:\n- Market memo confirms plan\n\nImplications:\n- Resource allocation needed\n\nLimitations: Single source.",
            "--source", "filed-analysis", "--source-id", sid,
            "--tags", "filed-analysis", "--confidence", "0.75",
        )
        status = _run(analysis_kb, "analysis-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_analysis"] is True
        assert entry["analysis_record_id"] == record["id"]

    def test_domain_filter(self, analysis_kb):
        status = _run(analysis_kb, "analysis-status", "--domain", "test_domain")
        assert all(s["domain"] == "test_domain" for s in status)


# ---------------------------------------------------------------------------
# Canonicality
# ---------------------------------------------------------------------------


class TestAnalysisCanonicality:
    def test_supersede_updates_analysis_record_id(self, analysis_kb):
        sid = _sid(analysis_kb)
        status = _run(analysis_kb, "analysis-status")
        entry = next(s for s in status if s["source_id"] == sid)
        old_id = entry["analysis_record_id"]
        assert old_id is not None
        new_record = _run(analysis_kb, "supersede", old_id,
            "--content", "Thesis: Updated — LATAM viable with caveats.\n\nSupporting evidence:\n- Memo + market data\n\nImplications:\n- Phased entry recommended\n\nLimitations: Currency risk not assessed.",
            "--source-id", sid, "--tags", "filed-analysis",
        )
        status = _run(analysis_kb, "analysis-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["analysis_record_id"] == new_record["id"]
        assert entry["analysis_record_id"] != old_id

    def test_detects_multiple_active_analyses(self, analysis_kb):
        sid = _sid(analysis_kb)
        _run(analysis_kb, "create",
            "--category", "APRENDIZADO", "--domain", "test_domain",
            "--title", "Analysis: memo.txt (duplicate)",
            "--content", "Duplicate analysis for test.",
            "--source", "filed-analysis", "--source-id", sid,
            "--tags", "filed-analysis",
        )
        status = _run(analysis_kb, "analysis-status")
        entry = next(s for s in status if s["source_id"] == sid)
        assert entry["has_analysis"] is True
        assert entry.get("warning") == "multiple_active_analyses"
        assert len(entry.get("active_analysis_ids", [])) >= 2


# ---------------------------------------------------------------------------
# Coexistence with summaries
# ---------------------------------------------------------------------------


class TestCoexistence:
    def test_summary_and_analysis_coexist(self, analysis_kb):
        sid = _sid(analysis_kb)
        # Create a summary for the same source
        _run(analysis_kb, "create",
            "--category", "FATO", "--domain", "test_domain",
            "--title", "Summary: memo.txt",
            "--content", "Overview: Strategic memo for LATAM.\n\nKey points:\n- Market entry plan\n\nScope: Single market.",
            "--source", "source-summary", "--source-id", sid,
            "--tags", "source-summary",
        )
        sum_status = _run(analysis_kb, "summarize-status")
        sum_entry = next(s for s in sum_status if s["source_id"] == sid)
        assert sum_entry["has_summary"] is True

        ana_status = _run(analysis_kb, "analysis-status")
        ana_entry = next(s for s in ana_status if s["source_id"] == sid)
        assert ana_entry["has_analysis"] is True

        # They should report independent record IDs
        assert sum_entry["summary_record_id"] != ana_entry["analysis_record_id"]


# ---------------------------------------------------------------------------
# Negative checks
# ---------------------------------------------------------------------------


class TestNegativeChecks:
    def test_raw_content_not_in_exports(self, analysis_kb):
        _run(analysis_kb, "export", json_mode=False)
        now_md = (analysis_kb / "memory" / "NOW.md").read_text(encoding="utf-8")
        assert "Strategic memo: market entry" not in now_md
        hot_md = (analysis_kb / "memory" / "HOT.md").read_text(encoding="utf-8")
        assert "Strategic memo: market entry" not in hot_md

    def test_schema_unchanged(self, analysis_kb):
        from pathlib import Path
        r = subprocess.run(
            [sys.executable, str(analysis_kb / "kb.py"), "raw-query",
             "SELECT value FROM schema_meta WHERE key = 'schema_version'"],
            capture_output=True, text=True, check=True, cwd=str(analysis_kb),
        )
        result = json.loads(r.stdout)
        assert result[0]["value"] == "4"
