"""Hermetic versions of formerly non-deterministic wiki tests.

These tests previously ran against the live ``.kb`` and asserted shapes that
the live KB no longer guarantees (a disabled wiki, specific tier badges, the
presence/absence of a "Sources & Analyses" section, and source-page candidate
counts). They are rewritten here to build a temporary, isolated KB from the
scaffold template (``core/templates/kb``) and seed exactly the condition each
test asserts, so they are deterministic and safe for CI.

Pattern mirrors ``tests/test_wiki_self_clean.py``: copy the scaffold runtime +
``kb.py`` into a tmp dir, write a ``kb.config.json``, ``python kb.py init``,
then drive the CLI with ``cwd=<tmp dir>``.
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


def _config(page_types, *, domains=None, wiki_enabled=True):
    return {
        "schema_version": 3,
        "project": {"name": "Test KB", "slug": "test-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": domains or ["alpha", "beta"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "lifecycle": {"events": {"session_start": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False}}},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {
            "enabled": wiki_enabled,
            "activation_mode": "policy",
            "page_types": page_types,
            "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0},
            "semantic": {"min_confidence_autopublish": 0.5, "min_confidence_review": 0.4, "min_sources_research_synthesis": 2},
            "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}},
        },
    }


def _make_kb(tmp_path, config: dict) -> Path:
    """Build an isolated KB from the scaffold template with the given config."""
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    shutil.copytree(TEMPLATE / "runtime", kb_dir / "runtime")
    shutil.copy2(TEMPLATE / "kb.py", kb_dir / "kb.py")
    (kb_dir / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(
        [sys.executable, "kb.py", "init"],
        cwd=str(kb_dir), check=True, capture_output=True, text=True,
    )
    return kb_dir


@pytest.fixture
def kb(tmp_path):
    """Default wiki-enabled KB with the standard page types."""
    return _make_kb(
        tmp_path,
        _config(["domain_overview", "research_synthesis", "source_page"]),
    )


def _run(kb_dir, *args, json_mode=False):
    cmd = [sys.executable, "kb.py", *args]
    if json_mode:
        cmd.append("--json")
    r = subprocess.run(cmd, cwd=str(kb_dir), capture_output=True, text=True, check=True)
    return json.loads(r.stdout) if json_mode else r.stdout


def _set_min_sources(kb_dir, n):
    cfg = json.loads((kb_dir / "kb.config.json").read_text(encoding="utf-8"))
    cfg["wiki"]["semantic"]["min_sources_research_synthesis"] = n
    (kb_dir / "kb.config.json").write_text(json.dumps(cfg), encoding="utf-8")


class TestWikiCheck:
    def test_returns_off_when_disabled(self, tmp_path):
        # Build a KB whose config explicitly disables the wiki.
        kb_dir = _make_kb(
            tmp_path,
            _config(["domain_overview"], wiki_enabled=False),
        )
        result = _run(kb_dir, "wiki-check", json_mode=True)
        assert result["wiki_state"] == "off"
        assert result["wiki_enabled_in_config"] is False


class TestRicherDomainOverview:
    def test_domain_overview_has_tier_indicators(self, tmp_path):
        kb_dir = _make_kb(
            tmp_path,
            _config(["domain_overview"], domains=["platforms"]),
        )
        # Seed the 'platforms' domain with >=3 active records so a
        # domain_overview candidate is generated, including at least one HOT
        # and one WARM record so both tier badges appear.
        _run(kb_dir, "create", "--category", "FATO", "--domain", "platforms",
             "--title", "Hot platform fact", "--content", "hot content", "--tier", "HOT")
        _run(kb_dir, "create", "--category", "FATO", "--domain", "platforms",
             "--title", "Warm platform fact", "--content", "warm content", "--tier", "WARM")
        _run(kb_dir, "create", "--category", "DECISAO", "--domain", "platforms",
             "--title", "Warm platform decision", "--content", "decision content", "--tier", "WARM")
        _run(kb_dir, "wiki-sync", "--force")
        page = kb_dir / "wiki" / "live" / "platforms" / "overview.md"
        assert page.is_file(), "expected platforms overview after sync"
        content = page.read_text(encoding="utf-8")
        assert "[HOT]" in content
        assert "[WARM]" in content

    def test_sources_analyses_section_absent_when_none(self, tmp_path):
        kb_dir = _make_kb(
            tmp_path,
            _config(["domain_overview"], domains=["platforms"]),
        )
        # Seed plain records only (no source-summary / filed-analysis tags), so
        # the conditional "## Sources & Analyses" section must not appear.
        for i in range(3):
            _run(kb_dir, "create", "--category", "FATO", "--domain", "platforms",
                 "--title", f"Plain fact {i}", "--content", f"content {i}", "--tier", "WARM")
        _run(kb_dir, "wiki-sync", "--force")
        page = kb_dir / "wiki" / "live" / "platforms" / "overview.md"
        assert page.is_file(), "expected platforms overview after sync"
        content = page.read_text(encoding="utf-8")
        assert "## Sources & Analyses" not in content


@pytest.fixture
def research_kb(tmp_path):
    """Wiki-enabled KB seeded so a record-only research_synthesis page publishes.

    Seeds the tag ``codex`` on >=3 ACTIVE records spanning DECISAO/FATO/
    APRENDIZADO (so all three category sections appear), all tier WARM, with ids
    starting ``KBF-KB-``. No sources are ingested and no source links are
    created, so the page has neither a "Sources & Analyses" section nor any
    supporting sources. ``min_sources_research_synthesis`` is set to 0 so the
    record-only candidate is not held back by the hygiene gate.
    """
    kb_dir = _make_kb(
        tmp_path,
        _config(["domain_overview", "research_synthesis", "source_page"], domains=["research"]),
    )
    _set_min_sources(kb_dir, 0)
    _run(kb_dir, "create", "--id", "KBF-KB-0001", "--category", "DECISAO",
         "--domain", "research", "--title", "Codex routing decision",
         "--content", "We route codex builds through the canonical pipeline.",
         "--tier", "WARM", "--tags", "codex")
    _run(kb_dir, "create", "--id", "KBF-KB-0002", "--category", "FATO",
         "--domain", "research", "--title", "Codex baseline fact",
         "--content", "Codex baseline evidence recorded on 2026-05-25.",
         "--tier", "WARM", "--tags", "codex")
    _run(kb_dir, "create", "--id", "KBF-KB-0003", "--category", "APRENDIZADO",
         "--domain", "research", "--title", "Codex learning",
         "--content", "Learned that codex namespaces must avoid collisions.",
         "--tier", "WARM", "--tags", "codex")
    _run(kb_dir, "wiki-sync", "--force")
    return kb_dir


class TestRicherResearchSynthesis:
    """Hermetic versions of the research-synthesis shape tests.

    Each test reads the ``codex`` research_synthesis page produced from an
    isolated, seeded KB (see the ``research_kb`` fixture), so they no longer
    depend on the live ``.kb``.
    """

    def _read(self, kb_dir, tag="codex"):
        path = kb_dir / "wiki" / "live" / "research" / f"{tag}.md"
        assert path.is_file(), "expected research synthesis page after sync"
        return path.read_text(encoding="utf-8")

    def test_research_synthesis_has_category_sections(self, research_kb):
        content = self._read(research_kb)
        # The codex tag spans DECISAO, FATO, APRENDIZADO records.
        assert "## Key Decisions" in content
        assert "## Facts & Evidence" in content
        assert "## Learnings" in content

    def test_research_synthesis_has_content_excerpts(self, research_kb):
        content = self._read(research_kb)
        assert "### KBF-KB-" in content
        assert "—" in content  # em dash between id and title
        assert "> [" in content     # content excerpt blockquote with tier badge

    def test_research_synthesis_has_tier_indicators(self, research_kb):
        content = self._read(research_kb)
        assert "[WARM]" in content

    def test_research_synthesis_no_sources_section(self, research_kb):
        """Record-only research synthesis pages have no Sources & Analyses section."""
        content = self._read(research_kb)
        assert "## Sources & Analyses" not in content

    def test_research_synthesis_no_flat_bullet_list(self, research_kb):
        """Research synthesis uses category grouping, not the flat-bullet section."""
        content = self._read(research_kb)
        # The flat fallback emits a "## Supporting Records" heading; the
        # category-grouped builder does not (provenance uses a "- **Supporting
        # Records:**" bullet, which is distinct from the heading).
        assert "## Supporting Records" not in content

    def test_research_synthesis_still_has_provenance(self, research_kb):
        # Assert via string checks on the page content to avoid importing
        # runtime modules from the live .kb (the seeded KB's runtime lives in
        # the tmp dir, not on sys.path).
        content = self._read(research_kb)
        assert "<!-- kb-citation-block -->" in content  # citation marker
        assert "## Provenance" in content
        # Provenance lists the seeded supporting records (not 'none').
        assert "- **Supporting Records:** KBF-KB-" in content


class TestSourcePages:
    def test_no_source_candidates_without_linked_data(self, kb):
        # Register exactly one source via ingest, with NO linked records,
        # summaries, or analyses.
        (kb / "sample.txt").write_text("Hello source world\n", encoding="utf-8")
        ingest = _run(kb, "ingest", str(kb / "sample.txt"), "--domain", "alpha", json_mode=True)
        assert ingest["skipped"] is False
        assert ingest["record_ids"] == []

        candidates = _run(kb, "wiki-candidates", json_mode=True)
        source_cands = [c for c in candidates if c["page_type"] == "source_page"]
        assert len(source_cands) == 0
