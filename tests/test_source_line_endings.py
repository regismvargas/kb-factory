"""Source snapshots keep their bytes under any line-ending setting (decision 21, 0.2.4).

The KB stores each source's SHA-256 at ingest. A repository-wide
`* text=auto eol=lf` or `core.autocrlf` used to convert snapshots on commit or
checkout, which broke that check. The template's `.kb/.gitattributes` turns
conversion off for `sources/`, and `upgrade-classic` adds the rule to
existing projects and keeps it last.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "core" / "templates" / "kb"
SCAFFOLD = REPO / "plugins" / "kb-lifecycle" / "scaffold"
MASTER_RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
RULE = "sources/** -text"


def _git(cwd: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True).stdout


def _rules(path: Path) -> list[list[str]]:
    return [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]


def test_template_and_scaffold_keep_source_bytes() -> None:
    for kb in (TEMPLATE, SCAFFOLD):
        assert _rules(kb / ".gitattributes") == [RULE.split()], kb
    assert (TEMPLATE / ".gitattributes").read_bytes() == (SCAFFOLD / ".gitattributes").read_bytes()


def test_a_crlf_source_round_trips_under_repo_wide_eol_lf(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".kb" / "sources" / "SRC-1").mkdir(parents=True)
    (repo / ".kb" / "memory").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.autocrlf", "true")
    (repo / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    shutil.copy2(TEMPLATE / ".gitattributes", repo / ".kb" / ".gitattributes")
    source = repo / ".kb" / "sources" / "SRC-1" / "notes.md"
    snapshot = b"# Notes\r\n\r\nline one\r\n"
    source.write_bytes(snapshot)
    (repo / ".kb" / "memory" / "NOW.md").write_bytes(b"# NOW\r\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "snapshot")

    assert _git(repo, "show", "HEAD:.kb/sources/SRC-1/notes.md") == snapshot
    assert _git(repo, "show", "HEAD:.kb/memory/NOW.md") == b"# NOW\n"  # other KB text still normalizes
    source.unlink()
    _git(repo, "checkout", "--", ".kb/sources/SRC-1/notes.md")
    assert source.read_bytes() == snapshot
    assert _git(repo, "status", "--porcelain", "--", ".kb/sources") == b""


def test_upgrade_classic_adds_the_rule_once(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(TEMPLATE, project / ".kb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    attributes = project / ".kb" / ".gitattributes"

    def upgrade() -> dict:
        out = subprocess.run(
            [sys.executable, str(MASTER_RUNTIME), "--project-root", str(project), "upgrade-classic",
             "--template", str(TEMPLATE), "--json"],
            cwd=str(project), check=True, capture_output=True, text=True,
        )
        return json.loads(out.stdout)

    attributes.unlink()
    assert upgrade()["gitattributes_updated"] is True
    assert attributes.read_bytes() == (TEMPLATE / ".gitattributes").read_bytes()

    attributes.write_text("*.pdf binary", encoding="utf-8")  # a project's own file, no final newline
    assert upgrade()["gitattributes_updated"] is True
    assert attributes.read_text(encoding="utf-8") == "*.pdf binary\n" + RULE + "\n"

    again = upgrade()
    assert again["gitattributes_updated"] is False
    assert again["action"] == "unchanged"

    attributes.write_text(RULE + "\nsources/** text\n", encoding="utf-8")  # a later line would win
    assert upgrade()["gitattributes_updated"] is True
    assert _rules(attributes)[-1] == RULE.split()


def test_upgrade_classic_refuses_a_gitattributes_directory_before_touching_the_engine(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(TEMPLATE, project / ".kb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    stale = project / ".kb" / "runtime" / "wiki.py"
    stale.write_text("# stale engine\n", encoding="utf-8")
    (project / ".kb" / ".gitattributes").unlink()
    (project / ".kb" / ".gitattributes").mkdir()
    out = subprocess.run(
        [sys.executable, str(MASTER_RUNTIME), "--project-root", str(project), "upgrade-classic",
         "--template", str(TEMPLATE), "--json"],
        cwd=str(project), capture_output=True, text=True,
    )
    assert out.returncode != 0
    assert "regular file" in (out.stderr + out.stdout)
    assert stale.read_text(encoding="utf-8") == "# stale engine\n"
