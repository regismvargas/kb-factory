"""Automatic curation: detection is read-only, corrections are proposals within a
weekly review budget, and only an approved proposal-apply changes the KB.

Decision of 2026-10-20 (docs/benchmarks/kb-value/README.md): hygiene-audit and
semantic-hygiene run at session end and in the weekly maintenance run, and the
batched proposals fit a review of at most 15 minutes a week.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KB_NEXT = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
CLASSIC_KB_PY = ROOT / "core" / "templates" / "kb" / "kb.py"
CLASSIC_RUNTIME = ROOT / "core" / "templates" / "kb" / "runtime"
HOT_IDS = [f"HOT-{index}" for index in range(1, 9)]


def load_kb_next():
    spec = importlib.util.spec_from_file_location("kb_next_curation_under_test", KB_NEXT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kb_next = load_kb_next()


def run_kb_next(root: Path, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = kb_next.main(["--project-root", str(root), *argv])
    return code, out.getvalue(), err.getvalue()


def kb_next_json(root: Path, *argv: str) -> dict:
    code, out, err = run_kb_next(root, *argv, "--json")
    assert code == 0, err
    return json.loads(out)


def classic(root: Path, *argv: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-B", str(root / ".kb" / "kb.py"), *argv, "--json"],
        text=True,
        capture_output=True,
        check=True,
        cwd=str(root / ".kb"),
    )
    return json.loads(result.stdout)


def kb_sha(root: Path) -> str:
    return hashlib.sha256((root / ".kb" / "kb.db").read_bytes()).hexdigest()


def record(root: Path, record_id: str) -> dict:
    with contextlib.closing(sqlite3.connect(root / ".kb" / "kb.db")) as conn:
        conn.row_factory = sqlite3.Row
        return dict(conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone())


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_project(tmp_path_factory.mktemp("curation-template"))


@pytest.fixture()
def project(template: Path, tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(template, target)
    return target


def build_project(tmp_path: Path) -> Path:
    kb_root = tmp_path / ".kb"
    kb_root.mkdir()
    shutil.copytree(CLASSIC_RUNTIME, kb_root / "runtime", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(CLASSIC_KB_PY, kb_root / "kb.py")
    config = {
        "schema_version": 4,
        "project": {"name": "Curation KB", "slug": "curation-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["operations"],
        "hot_session_limit": 1,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "wiki": {"enabled": False},
    }
    (kb_root / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run([sys.executable, "-B", str(kb_root / "kb.py"), "init"], capture_output=True, check=True, cwd=str(kb_root))
    for record_id in HOT_IDS:
        classic(
            tmp_path, "create", "--id", record_id, "--category", "FATO", "--domain", "operations",
            "--title", f"Working fact {record_id}", "--content", f"Session-critical fact {record_id}.",
            "--tier", "HOT", "--source", "test", "--confidence", "0.9", "--no-auto-lifecycle",
        )
    classic(
        tmp_path, "create", "--id", "OPEN-1", "--category", "PENDENCIA", "--domain", "operations",
        "--title", "Port the hygiene tests", "--content", "Done in the curation work package.",
        "--review-after", "2026-01-01", "--source", "test", "--confidence", "0.9", "--no-auto-lifecycle",
    )
    kb_next_json(tmp_path, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    return tmp_path


def judgment(demote: list[str], resolve: list[str] = ()) -> dict:
    def items(ids):
        return [{"record_id": rid, "rationale": f"{rid} left the working set.", "confidence": 0.9} for rid in ids]

    return {
        "groups": {"demote_candidate": items(demote), "resolve_candidate": items(resolve)},
        "rationale": "HOT exceeds the session budget.",
        "confidence": 0.9,
        "provenance": [{"record_id": rid} for rid in [*demote, *resolve]],
        "conflicts": [],
    }


def write_proposals(root: Path, payload: dict) -> dict:
    path = root / "hygiene-judgment.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return kb_next_json(root, "semantic-hygiene", "--judgment", f"@{path}", "--write-proposals")


def set_weekly_limit(root: Path, value) -> None:
    path = root / ".kb-next" / "kb-next.config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.setdefault("semantic_curation", {})["weekly_hygiene_proposals"] = value
    path.write_text(json.dumps(config), encoding="utf-8")


def test_detection_is_read_only_and_reports_the_review_budget(project: Path) -> None:
    before = kb_sha(project)

    audit = classic(project, "hygiene-audit")
    detection = kb_next_json(project, "semantic-hygiene")

    assert audit["read_only"] is True and audit["hot_over_limit"] is True
    assert detection["read_only"] is True and detection["proposal_ids"] == []
    assert len(detection["mechanical_groups"]["demote_candidate"]) == len(HOT_IDS) - 1
    assert [item["record_id"] for item in detection["mechanical_groups"]["resolve_candidate"]] == ["OPEN-1"]
    budget = detection["review_budget"]
    assert budget == {"window_days": 7, "weekly_limit": 5, "open_count": 0, "room": 5, "open": []}
    assert kb_sha(project) == before
    assert not (project / ".kb-next" / "proposals" / "hygiene").exists()


def test_stale_hot_records_count_toward_the_excess_before_overflow_picks(project: Path) -> None:
    config_path = project / ".kb" / "kb.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["hot_session_limit"] = 5
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with contextlib.closing(sqlite3.connect(project / ".kb" / "kb.db")) as conn:
        conn.execute("UPDATE records SET review_after = '9999-12-31' WHERE tier = 'HOT'")
        conn.execute("UPDATE records SET review_after = '2020-01-01' WHERE id IN ('HOT-1', 'HOT-2', 'HOT-3')")
        conn.commit()

    groups = kb_next_json(project, "semantic-hygiene")["groups"]

    # 8 HOT over a limit of 5: the 3 stale records already cover the excess.
    assert sorted(item["record_id"] for item in groups["demote_candidate"]) == ["HOT-1", "HOT-2", "HOT-3"]
    assert {item["reason"] for item in groups["demote_candidate"]} == {"stale_hot_review_after_elapsed"}
    assert len(groups["keep_hot"]) == 5


def test_writes_stop_at_the_weekly_limit_and_never_duplicate_an_open_proposal(project: Path) -> None:
    before = kb_sha(project)
    first = write_proposals(project, judgment(HOT_IDS[1:]))

    assert len(first["proposal_ids"]) == 5
    assert [item["target_record_id"] for item in first["deferred"]] == HOT_IDS[6:]
    assert first["review_budget"]["open_count"] == 5 and first["review_budget"]["room"] == 0

    second = write_proposals(project, judgment(HOT_IDS[1:]))

    assert second["proposal_ids"] == []
    assert sorted(item["target_record_id"] for item in second["already_open"]) == HOT_IDS[1:6]
    assert len(second["deferred"]) == 2
    assert kb_sha(project) == before  # proposals live in .kb-next only


def test_an_approved_apply_drains_the_queue_and_frees_room(project: Path) -> None:
    written = write_proposals(project, judgment(HOT_IDS[1:3], resolve=["OPEN-1"]))
    by_target = {item["target_record_id"]: item for item in written["review_budget"]["open"]}
    assert set(by_target) == {"HOT-2", "HOT-3", "OPEN-1"}

    applied = kb_next_json(
        project, "proposal-apply", "--proposal", by_target["HOT-2"]["proposal_id"], "--approve",
        "--approval-note", "weekly review", "--actor", "test-approver", "--actor-runtime", "human",
    )
    resolved = kb_next_json(
        project, "proposal-apply", "--proposal", by_target["OPEN-1"]["proposal_id"], "--approve",
        "--approval-note", "weekly review", "--actor", "test-approver", "--actor-runtime", "human",
    )
    after = kb_next_json(project, "semantic-hygiene")

    assert applied["status"] == "applied" and resolved["status"] == "applied"
    assert record(project, "HOT-2")["tier"] == "WARM"
    assert record(project, "OPEN-1")["status"] == "RESOLVIDO"
    assert [item["target_record_id"] for item in after["review_budget"]["open"]] == ["HOT-3"]
    assert after["review_budget"]["room"] == 4


def test_a_target_changed_elsewhere_or_an_aged_proposal_leaves_the_queue(project: Path) -> None:
    written = write_proposals(project, judgment(HOT_IDS[1:3]))
    with contextlib.closing(sqlite3.connect(project / ".kb" / "kb.db")) as conn:
        conn.execute("UPDATE records SET tier = 'WARM' WHERE id = 'HOT-2'")
        conn.commit()
    aged = next(
        path for path in (project / ".kb-next" / "proposals" / "hygiene").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["target_record_id"] == "HOT-3"
    )
    payload = json.loads(aged.read_text(encoding="utf-8"))
    payload["created_at"] = "2026-01-01T00:00:00Z"
    aged.write_text(json.dumps(payload), encoding="utf-8")

    assert len(written["proposal_ids"]) == 2
    assert kb_next_json(project, "semantic-hygiene")["review_budget"]["open"] == []


def test_without_judgment_nothing_reaches_the_queue(project: Path) -> None:
    result = kb_next_json(project, "semantic-hygiene", "--write-proposals")

    assert result["validation_status"] == "needs_llm_judgment"
    assert result["proposal_ids"] == [] and result["review_budget"]["open_count"] == 0


def test_the_weekly_limit_is_configurable_and_validated(project: Path) -> None:
    set_weekly_limit(project, 0)
    closed = write_proposals(project, judgment(HOT_IDS[1:3]))
    assert closed["proposal_ids"] == [] and len(closed["deferred"]) == 2

    set_weekly_limit(project, -1)
    code, _out, err = run_kb_next(project, "semantic-hygiene", "--json")
    assert code != 0 and "weekly_hygiene_proposals" in err


def test_curation_runs_weekly_and_the_session_end_stays_lean() -> None:
    plugin = ROOT / "plugins" / "kb-wiki-vnext"
    session_end = (plugin / "commands" / "vnext-session-end.md").read_text(encoding="utf-8")
    skill = (plugin / "skills" / "kb-wiki-vnext" / "SKILL.md").read_text(encoding="utf-8")
    curation = skill.split("## Curation", 1)[1].split("\n## ", 1)[0]

    assert "python .kb/kb.py hygiene-audit --json" in curation
    assert "python <resolved-runtime-path> semantic-hygiene --json" in curation
    assert (
        "python <resolved-runtime-path> semantic-hygiene --judgment @hygiene-judgment.json "
        "--write-proposals --json"
    ) in curation
    assert "weekly maintenance run, not at session end" in curation

    # The close is lifecycle session-end, the KB candidates of subagents and the wiki draft check.
    commands = re.findall(r"`(python [^`]+)`", session_end)
    assert "python .kb/kb.py lifecycle session-end --json" in commands
    assert "python <resolved-runtime-path> wiki-draft-status --json" in commands
    for command in commands:
        assert "hygiene" not in command, command
    assert "--apply-demotions" not in session_end
    assert "weekly maintenance run, not at session end" in session_end
    assert "never apply its proposals at session end" in session_end
