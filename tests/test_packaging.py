"""Packaging tests for the pip-installable `kb-factory` CLI.

Verifies the bundled scaffold mirror stays in sync with the canonical template,
ships the full engine, and that `kb-factory init` / `update` actually produce a
working `.kb/`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def test_scaffold_mirror_in_sync():
    r = subprocess.run(
        [sys.executable, str(REPO / "tools" / "sync_package_scaffold.py"), "--check"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert r.returncode == 0, f"_scaffold is stale; run tools/sync_package_scaffold.py\n{r.stderr}"


def test_packaged_scaffold_has_engine():
    scaffold = REPO / "kb_factory" / "_scaffold"
    assert (scaffold / "kb.py").is_file()
    assert (scaffold / "runtime" / "records.py").is_file()
    assert (scaffold / "runtime" / "schema.py").is_file()
    assert (scaffold / "kb.config.json").is_file()


def test_version_declared():
    import kb_factory

    assert kb_factory.__version__


def test_init_and_update_roundtrip(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    # init via the package CLI (no install needed — run from the source tree)
    init = subprocess.run(
        [sys.executable, "-m", "kb_factory", "init", str(project)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert init.returncode == 0, init.stderr
    kb = project / ".kb"
    assert (kb / "kb.py").is_file()
    assert (kb / "runtime" / "records.py").is_file()
    assert (kb / "kb.db").is_file()  # `kb.py init` ran and created the store
    assert (kb / ".kb-version").is_file()

    # the scaffolded store actually works
    stats = subprocess.run(
        [sys.executable, str(kb / "kb.py"), "stats", "--json"],
        capture_output=True, text=True, cwd=str(kb),
    )
    assert stats.returncode == 0, stats.stderr

    # write a marker into a data file, then update, and confirm data is preserved
    (kb / "memory" / "NOW.md").write_text("MARKER-KEEP-ME\n", encoding="utf-8")
    update = subprocess.run(
        [sys.executable, "-m", "kb_factory", "update", str(project)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert update.returncode == 0, update.stderr
    assert (kb / "kb.db").is_file()  # data preserved
    assert "MARKER-KEEP-ME" in (kb / "memory" / "NOW.md").read_text(encoding="utf-8")
