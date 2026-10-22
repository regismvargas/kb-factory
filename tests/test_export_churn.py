"""Derived files keep their bytes when a refresh changes nothing in them.

Every record filing refreshes NOW, INDEX, HOT, one topic file per configured
domain, both project packs and, with the wiki on, every published page. The
`Generated` stamp alone used to make NOW, INDEX, the packs and each wiki page
differ on every refresh. A refresh now rewrites a file only when its content
apart from that stamp changes, so the file and its stamp stay as they were.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "kb"
OLD_MTIME = 1_000_000_000
OLD_STAMP = "2001-09-09T01:46:40Z"
DERIVED = (
    "memory/NOW.md",
    "memory/INDEX.md",
    "memory/HOT.md",
    "memory/topics/alpha.md",
    "memory/topics/beta.md",
    "exports/cowork/PROJECT_PACK.md",
    "exports/claude-ai/PROJECT_PACK.md",
)


def _config(wiki_enabled: bool) -> dict:
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
            "enabled": wiki_enabled,
            "activation_mode": "policy",
            "page_types": ["source_page"],
            "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0},
            "semantic": {"min_confidence_autopublish": 0.5, "min_confidence_review": 0.4, "min_sources_research_synthesis": 2},
            "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}},
        },
    }


def _make_kb(tmp_path: Path, *, wiki_enabled: bool) -> Path:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    shutil.copytree(TEMPLATE / "runtime", kb_dir / "runtime")
    shutil.copy2(TEMPLATE / "kb.py", kb_dir / "kb.py")
    (kb_dir / "kb.config.json").write_text(json.dumps(_config(wiki_enabled)), encoding="utf-8")
    _run(kb_dir, "init")
    return kb_dir


def _run(kb_dir: Path, *args: str, json_mode: bool = False):
    cmd = [sys.executable, "-B", "kb.py", *args]
    if json_mode:
        cmd.append("--json")
    proc = subprocess.run(cmd, cwd=str(kb_dir), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout) if json_mode else proc.stdout


def _create(kb_dir: Path, title: str, domain: str = "alpha", *extra: str) -> None:
    _run(kb_dir, "create", "--category", "FATO", "--domain", domain, "--title", title,
         "--content", f"{title} content.", "--tier", "WARM", *extra)


def _age(path: Path, restamp: bool = True) -> None:
    """Make a refreshed file look old: CRLF endings, an old mtime and, unless
    `restamp` is False, an old `Generated` stamp."""
    text = path.read_text(encoding="utf-8")
    if restamp:
        text = re.sub(r"(- Generated: `)[^`]+(`)", rf"\g<1>{OLD_STAMP}\g<2>", text)
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    os.utime(path, (OLD_MTIME, OLD_MTIME))


def _stamp_free(text: str) -> list:
    return [line for line in text.splitlines() if "Generated:" not in line]


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    return _make_kb(tmp_path, wiki_enabled=False)


def test_refresh_without_changes_rewrites_no_derived_file(kb: Path) -> None:
    _create(kb, "Alpha fact")  # create runs the record_filed refresh
    files = [kb / rel for rel in DERIVED]
    assert all(path.is_file() for path in files)
    for path in files:
        _age(path)
    before = {path: path.read_bytes() for path in files}

    _run(kb, "export")

    for path in files:
        assert path.read_bytes() == before[path], f"{path.name} was rewritten"
        assert path.stat().st_mtime == OLD_MTIME, f"{path.name} was touched"

    # A domain without records still gets its topic file.
    beta = kb / "memory" / "topics" / "beta.md"
    beta.unlink()
    _run(kb, "export")
    assert "No active records." in beta.read_text(encoding="utf-8")


def test_refresh_rewrites_only_files_whose_content_changed(kb: Path) -> None:
    _create(kb, "Alpha fact")
    for rel in DERIVED:
        _age(kb / rel)

    _create(kb, "Beta fact", "beta")

    changed = {rel for rel in DERIVED if (kb / rel).stat().st_mtime != OLD_MTIME}
    # The new WARM fact enters NOW (and so both packs) and the beta topic;
    # HOT, INDEX and the alpha topic keep their bytes.
    assert changed == {
        "memory/NOW.md",
        "memory/topics/beta.md",
        "exports/cowork/PROJECT_PACK.md",
        "exports/claude-ai/PROJECT_PACK.md",
    }
    now = (kb / "memory" / "NOW.md").read_text(encoding="utf-8")
    assert "Beta fact" in now and OLD_STAMP not in now
    index = (kb / "memory" / "INDEX.md").read_text(encoding="utf-8")
    assert OLD_STAMP in index
    cowork = (kb / "exports" / "cowork" / "PROJECT_PACK.md").read_bytes()
    assert cowork == (kb / "exports" / "claude-ai" / "PROJECT_PACK.md").read_bytes()


@pytest.mark.full
def test_wiki_sync_keeps_unchanged_pages_and_rewrites_changed_ones(tmp_path: Path) -> None:
    kb = _make_kb(tmp_path, wiki_enabled=True)
    pages = []
    for name in ("one", "two"):
        source = tmp_path / f"{name}.md"
        source.write_text(f"Evidence {name}.\n", encoding="utf-8")
        sid = _run(kb, "ingest", str(source), "--domain", "alpha", json_mode=True)["source_id"]
        _create(kb, f"Fact {name}", "alpha", "--source-id", sid)
        pages.append((sid, kb / "wiki" / "live" / "sources" / f"{sid}.md"))
    _run(kb, "wiki-sync", "--force")
    for _, page in pages:
        assert page.is_file()
        # wiki-lint compares the page stamp with its records: keep the real one.
        _age(page, restamp=False)
    before = {page: page.read_bytes() for _, page in pages}

    sync = _run(kb, "wiki-sync", "--force", json_mode=True)
    assert sync["written_count"] == 2
    for _, page in pages:
        assert page.read_bytes() == before[page], f"{page.name} was rewritten"
        assert page.stat().st_mtime == OLD_MTIME
    assert _run(kb, "wiki-lint", json_mode=True)["issue_count"] == 0

    # A second record citing source one changes that page only.
    _create(kb, "Fact one bis", "alpha", "--source-id", pages[0][0])
    _run(kb, "wiki-sync", "--force")
    first, second = pages[0][1], pages[1][1]
    assert first.stat().st_mtime != OLD_MTIME
    assert first.read_bytes() != before[first]
    assert second.read_bytes() == before[second]
    assert _run(kb, "wiki-lint", json_mode=True)["issue_count"] == 0

    # A supporting record that changes without changing the page text: the
    # next sync restamps the page, so wiki-lint does not report it stale.
    time.sleep(1.1)  # record and page stamps have one-second resolution
    record_id = json.loads(_run(kb, "raw-query", "SELECT id FROM records WHERE title = 'Fact two'"))[0]["id"]
    _run(kb, "update", record_id, "--tags", "retagged")
    _run(kb, "wiki-sync", "--force")
    text = second.read_text(encoding="utf-8")
    assert _stamp_free(text) == _stamp_free(before[second].decode("utf-8"))
    assert second.stat().st_mtime != OLD_MTIME
    assert _run(kb, "wiki-lint", json_mode=True)["issue_count"] == 0


@pytest.mark.full
def test_wiki_keeps_one_snapshot_per_page_per_day(tmp_path: Path) -> None:
    """A batch of filings on one day re-renders a page many times; only the
    version generated on an earlier day becomes a snapshot."""
    kb = _make_kb(tmp_path, wiki_enabled=True)
    source = tmp_path / "paper.md"
    source.write_text("Evidence.\n", encoding="utf-8")
    sid = _run(kb, "ingest", str(source), "--domain", "alpha", json_mode=True)["source_id"]
    page = kb / "wiki" / "live" / "sources" / f"{sid}.md"
    snapshots = kb / "wiki" / "snapshots"

    def snapshot_files() -> list:
        return sorted(snapshots.rglob("*.md")) if snapshots.is_dir() else []

    for index in range(3):  # each create runs the record_filed wiki sync
        _create(kb, f"Same-day fact {index}", "alpha", "--source-id", sid)
    assert page.is_file()
    assert snapshot_files() == []

    # The live version now dates from an earlier day: the next change keeps it.
    _run(kb, "raw-query", "--allow-write",
         "UPDATE wiki_pages SET generated_at = '2001-09-09T01:46:40Z' WHERE page_class = 'live'")
    previous = page.read_bytes()
    _create(kb, "Next-day fact", "alpha", "--source-id", sid)
    files = snapshot_files()
    assert len(files) == 1
    assert files[0].read_bytes() == previous
    rows = json.loads(_run(kb, "raw-query", "SELECT COUNT(*) AS n FROM wiki_snapshots"))
    assert rows[0]["n"] == 1

    _create(kb, "Next-day fact bis", "alpha", "--source-id", sid)
    assert len(snapshot_files()) == 1
    assert _run(kb, "wiki-lint", json_mode=True)["issue_count"] == 0


def _runtime_module(name: str):
    sys.path.insert(0, str(TEMPLATE))
    try:
        return importlib.import_module(f"runtime.{name}")
    finally:
        sys.path.remove(str(TEMPLATE))


def _page(note: str, stamp: str, fence: str) -> str:
    return "\n".join([
        "# Page", "", f"- **Generated:** {note}", "", "---", "", fence, "",
        "## Provenance", "", f"- **Generated:** {stamp}", "- **Class:** live", "",
        "<!-- /kb-citation-block -->",
    ])


def test_wiki_hash_ignores_only_the_provenance_stamp() -> None:
    wm = _runtime_module("wiki_materialization")
    fence = wm.WIKI_CITATION_FENCE
    base = wm.compute_content_hash(_page("note one", "2026-01-01T00:00:00Z", fence))
    assert base == wm.compute_content_hash(_page("note one", "2026-02-02T00:00:00Z", fence))
    # A body line that happens to look like the stamp is content: changing it
    # must change the hash, or the skip would keep the stale page.
    assert base != wm.compute_content_hash(_page("note two", "2026-01-01T00:00:00Z", fence))


def test_export_compare_ignores_only_the_header_stamp() -> None:
    ex = _runtime_module("exports")
    prefix = ex.GENERATED_LINE_PREFIX
    first = f"# NOW\n\n{prefix}2026-01-01T00:00:00Z`\n\n- body\n{prefix}note one`\n"
    restamped = f"# NOW\n\n{prefix}2026-02-02T00:00:00Z`\n\n- body\n{prefix}note one`\n"
    changed = f"# NOW\n\n{prefix}2026-01-01T00:00:00Z`\n\n- body\n{prefix}note two`\n"
    assert ex._without_stamp(first) == ex._without_stamp(restamped)
    assert ex._without_stamp(first) != ex._without_stamp(changed)
