"""Lean start of a new KB/Wiki vNext project (2026-10-21 review of a new project).

- `activation-wizard --scope` files the user's scope as one HOT DECISAO, once.
- A new KB + Wiki stays dormant until `--wiki-min-sourced-records` (default
  10) active records cite a registered source: no pages, no drafts line in the
  hook, `session-start` reports `dormant`. It then publishes by itself.
- `approved-filing` files a record the user approved in chat in one call that
  writes one audit file and one oplog line; a blocked call writes nothing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
CLASSIC_CONSTANTS = REPO / "core" / "runtime" / "constants.py"
NEW_PROJECT_ANSWERS = {
    "human_documentation": 1, "auditability": 2, "history_volume": 1,
    "memory_granularity": 2, "multi_agent": 2, "maintenance_capacity": 2,
}
SCOPE = "Pesquisa, análise e crítica de protocolos de treino"
ENV = {**os.environ, "KB_FACTORY_WORKTREE_SCOPE": "local"}


def run(project: Path, script: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, str(script), *args], cwd=str(project), env=ENV,
        capture_output=True, text=True, encoding="utf-8",
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def vnext(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(project, RUNTIME, "--project-root", str(project), *args, check=check)


def vnext_json(project: Path, *args: str) -> dict:
    return json.loads(vnext(project, *args, "--json").stdout)


def kb(project: Path, *args: str) -> subprocess.CompletedProcess:
    return run(project / ".kb", project / ".kb" / "kb.py", *args)


def ingest(project: Path, name: str) -> str:
    source = project / name
    source.write_text(f"Evidence {name}.\n", encoding="utf-8")
    return json.loads(kb(project, "ingest", str(source), "--domain", "research", "--json").stdout)["source_id"]


def approved(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return vnext(
        project, "approved-filing", *args, "--approval-note", "User approved in chat: 'ok'",
        "--actor", "sponsor", "--actor-runtime", "claude-code", "--json", check=check,
    )


@pytest.fixture
def new_project(tmp_path: Path) -> Path:
    project = tmp_path / "lab"
    project.mkdir()
    installed = vnext_json(
        project, "install-classic", "--slug", "research-lab", "--id-prefix", "RLB",
        "--domains", "product,operations,research",
    )
    assert installed["action"] == "created"
    (project / "answers.json").write_text(json.dumps(NEW_PROJECT_ANSWERS), encoding="utf-8")
    return project


def activate_guided(project: Path, *extra: str) -> dict:
    return vnext_json(project, "activation-wizard", "--mode", "guided", "--answers",
                      f"@{project / 'answers.json'}", *extra)


@pytest.mark.fast
def test_new_kb_wiki_starts_dormant_with_scope_only(new_project: Path) -> None:
    result = activate_guided(new_project, "--scope", SCOPE)
    assert result["activation"]["sponsor_decision"] == "kb_wiki"  # 13/16 still recommends KB + Wiki
    assert result["wiki_dormant"] == {"min_sourced_records": 10, "sourced_records": 0}
    assert result["classic_wiki_sync"]["reason"] == "wiki_dormant"
    assert result["project_scope"]["action"] == "created"
    classic = json.loads((new_project / ".kb" / "kb.config.json").read_text(encoding="utf-8"))
    assert classic["wiki"]["enabled"] is False
    assert classic["wiki"]["activation_mode"] == "signal"
    assert classic["wiki"]["eligibility"]["min_sourced_records"] == 10

    now = (new_project / ".kb" / "memory" / "NOW.md").read_text(encoding="utf-8")
    hot = (new_project / ".kb" / "memory" / "HOT.md").read_text(encoding="utf-8")
    assert f"Scope: {SCOPE}" in now and f"Scope: {SCOPE}" in hot
    assert "Open pendencias: `0`" in now
    records = json.loads(kb(new_project, "list", "--json").stdout)
    assert [(row["category"], row["tier"], row["valid_until"]) for row in records] == [("DECISAO", "HOT", None)]

    vnext_now = (new_project / ".kb-next" / "memory" / "NOW.md").read_text(encoding="utf-8")
    assert "- Wiki active: `false`" in vnext_now
    assert "Wiki dormant until `10`" in vnext_now
    assert "## Wiki Flow" not in vnext_now
    hint = vnext(new_project, "session-hint").stdout
    assert "approved-filing" in hint
    assert "vnext-wiki-drafts" not in hint
    start = vnext_json(new_project, "session-start")
    assert start["wiki"]["status"] == "dormant"
    assert start["wiki"]["hint"] is None
    assert "wiki_drafts" not in start
    assert "dormant" in vnext_json(new_project, "wiki-draft-status")["note"]
    assert not list((new_project / ".kb" / "wiki").rglob("*.md"))


def test_scope_is_filed_once(new_project: Path) -> None:
    first = activate_guided(new_project, "--scope", SCOPE)
    again = activate_guided(new_project, "--scope", "Outro escopo")
    assert again["project_scope"] == {"action": "exists", "record_id": first["project_scope"]["record_id"]}
    blank = vnext(new_project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki", "--scope", " ",
                  check=False)
    assert blank.returncode != 0 and "--scope must not be blank" in blank.stderr


def test_dormant_wiki_wakes_at_the_sourced_record_threshold(new_project: Path) -> None:
    activate_guided(new_project, "--wiki-min-sourced-records", "3")
    for index in range(3):
        sid = ingest(new_project, f"paper{index}.md")
        approved(new_project, "--category", "FATO", "--domain", "research", "--title", f"Finding {index}",
                 "--content", f"Finding {index} with evidence.", "--confidence", "0.9", "--source-id", sid)
        dormant = vnext_json(new_project, "session-start")["wiki"].get("dormant")
        assert (dormant is None) == (index == 2)
    start = vnext_json(new_project, "session-start")
    assert start["wiki"]["status"] == "aligned"
    assert "wiki_drafts" in start
    assert "vnext-wiki-drafts" in vnext(new_project, "session-hint").stdout
    # The third filing crossed the threshold; its lifecycle sync published the first page.
    assert (new_project / ".kb" / "wiki" / "live" / "research" / "overview.md").is_file()


def test_wiki_now_and_enabled_wikis_skip_dormancy(new_project: Path) -> None:
    now = activate_guided(new_project, "--wiki-min-sourced-records", "0")
    assert now["wiki_dormant"] is None
    assert now["classic_wiki_sync"]["action"] == "synced"
    # Re-activation never puts an enabled classic wiki to sleep.
    again = activate_guided(new_project)
    assert again["wiki_dormant"] is None
    classic = json.loads((new_project / ".kb" / "kb.config.json").read_text(encoding="utf-8"))
    assert classic["wiki"]["enabled"] is True


def test_approved_filing_writes_one_audit_file_and_one_oplog_line(new_project: Path) -> None:
    activate_guided(new_project, "--scope", SCOPE)
    sid = ingest(new_project, "addendum.md")
    oplog = new_project / ".kb-next" / "operations.jsonl"
    lines_before = oplog.read_text(encoding="utf-8").splitlines()
    files_before = set((new_project / ".kb-next").rglob("*.json"))
    result = json.loads(approved(
        new_project, "--category", "DECISAO", "--domain", "operations", "--title", "Codex executa, orquestrador julga",
        "--content", "Divisao de trabalho do Sponsor.", "--confidence", "0.95", "--source-id", sid, "--tier", "HOT",
    ).stdout)
    assert result["status"] == "applied"
    new_files = set((new_project / ".kb-next").rglob("*.json")) - files_before
    assert [path.parent.name for path in new_files] == ["approved-filing"]
    manifest = json.loads(next(iter(new_files)).read_text(encoding="utf-8"))
    assert manifest["approval"]["approval_note"] == "User approved in chat: 'ok'"
    assert manifest["canonical_record_id"] == result["canonical_record_id"]
    new_lines = oplog.read_text(encoding="utf-8").splitlines()[len(lines_before):]
    assert [json.loads(line)["event"] for line in new_lines] == ["approved-filing"]
    record = json.loads(kb(new_project, "get", result["canonical_record_id"], "--json").stdout)
    assert record["source_id"] == sid
    assert record["source"].startswith("kb-wiki-vnext approved filing ")


@pytest.mark.parametrize(
    ("args", "warning"),
    [
        (("--title", "Dup", "--confidence", "0.95", "--source-id", "{sid}"), "duplicate_title:"),
        (("--title", "Weak", "--confidence", "0.6", "--source-id", "{sid}"), "low_confidence:0.6"),
        (("--title", "No provenance", "--confidence", "0.95"), "missing_provenance"),
        (("--title", "Bad source", "--confidence", "0.95", "--source-id", "SRC-nope"), "unknown_source_reference:SRC-nope"),
        (("--title", "Ghost", "--confidence", "0.95", "--source-id", "{sid}", "--supersedes", "RLB-KB-nope"),
         "unknown_supersede_target:RLB-KB-nope"),
    ],
)
def test_blocked_approved_filing_writes_nothing(new_project: Path, args: tuple[str, ...], warning: str) -> None:
    activate_guided(new_project)
    sid = ingest(new_project, "evidence.md")
    approved(new_project, "--category", "FATO", "--domain", "research", "--title", "Dup", "--content", "x",
             "--confidence", "0.9", "--source-id", sid)
    files_before = set((new_project / ".kb-next").rglob("*"))
    oplog_before = (new_project / ".kb-next" / "operations.jsonl").read_text(encoding="utf-8")
    blocked = approved(new_project, "--category", "FATO", "--domain", "research", "--content", "y",
                       *(item.format(sid=sid) for item in args), check=False)
    assert blocked.returncode == 1
    payload = json.loads(blocked.stdout)
    assert payload["status"] == "blocked"
    assert any(item.startswith(warning) for item in payload["warnings"]), payload["warnings"]
    assert set((new_project / ".kb-next").rglob("*")) == files_before
    assert (new_project / ".kb-next" / "operations.jsonl").read_text(encoding="utf-8") == oplog_before


def test_approved_supersede_can_change_category_and_clear_valid_until(new_project: Path) -> None:
    activate_guided(new_project)
    sid = ingest(new_project, "premise.md")
    premise = json.loads(approved(
        new_project, "--category", "PREMISSA", "--domain", "product", "--title", "Escopo provisorio",
        "--content", "Vale ate a revisao.", "--confidence", "0.85", "--source-id", sid, "--valid-until", "2026-11-20",
    ).stdout)["canonical_record_id"]
    decided = json.loads(approved(
        new_project, "--supersedes", premise, "--category", "DECISAO", "--domain", "product",
        "--title", "Escopo decidido", "--content", "Decidido pelo Sponsor.", "--confidence", "0.95",
        "--record-id", premise, "--valid-until", "none",
    ).stdout)
    record = json.loads(kb(new_project, "get", decided["canonical_record_id"], "--json").stdout)
    assert (record["category"], record["valid_until"], record["supersedes_id"]) == ("DECISAO", None, premise)


@pytest.mark.fast
def test_seed_list_matches_the_classic_runtime() -> None:
    def tuples(text: str, name: str) -> list[str]:
        block = re.search(rf"{name} = \((.*?)\n\)", text, re.S)
        assert block, name
        return re.findall(r'"([^"]+)"', block.group(1))

    classic = CLASSIC_CONSTANTS.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    for name in ("BOOTSTRAP_SEED_TITLES",):
        assert tuples(classic, name) == tuples(runtime, name)
    assert re.search(r'BOOTSTRAP_SEED_SOURCES = \(([^)]*)\)', classic).group(1) == \
        re.search(r'BOOTSTRAP_SEED_SOURCES = \(([^)]*)\)', runtime).group(1)
