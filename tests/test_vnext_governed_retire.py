"""Decision 12 of 2026-10-21: governed retirement of records that are not open
items, and demotions only by proposal in a KB/Wiki vNext project.

The blueprint keeps RESOLVIDO for PENDENCIA only and defines SUPERSEDIDO as
"replaced by newer information" (docs/canon/KB_FACTORY_BLUEPRINT.md, 8.2). A
FATO or DECISAO that newer information replaced therefore retires as
SUPERSEDIDO into the existing record that replaces it: classic
`supersede --replacement-id` (kb-lifecycle 0.2.6), reached in a vNext project
only through a `retire` hygiene proposal and `proposal-apply`.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import importlib.util
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


def load_kb_next():
    spec = importlib.util.spec_from_file_location("kb_next_retire_under_test", KB_NEXT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kb_next = load_kb_next()


def kb_next_json(root: Path, *argv: str) -> dict:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = kb_next.main(["--project-root", str(root), *argv, "--json"])
    assert code == 0, err.getvalue()
    return json.loads(out.getvalue())


def run_classic(root: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(root / ".kb" / "kb.py"), *argv],
        text=True,
        capture_output=True,
        check=False,
        cwd=str(root / ".kb"),
    )


def classic(root: Path, *argv: str) -> dict:
    result = run_classic(root, *argv, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def records(root: Path) -> dict[str, dict]:
    with contextlib.closing(sqlite3.connect(root / ".kb" / "kb.db")) as conn:
        conn.row_factory = sqlite3.Row
        return {row["id"]: dict(row) for row in conn.execute("SELECT * FROM records")}


def build_classic(root: Path) -> Path:
    kb_root = root / ".kb"
    kb_root.mkdir(parents=True)
    shutil.copytree(CLASSIC_RUNTIME, kb_root / "runtime", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(CLASSIC_KB_PY, kb_root / "kb.py")
    config = {
        "schema_version": 4,
        "project": {"name": "Retire KB", "slug": "retire-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["operations"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "wiki": {"enabled": False},
    }
    (kb_root / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run([sys.executable, "-B", str(kb_root / "kb.py"), "init"], capture_output=True, check=True, cwd=str(kb_root))
    seeds = [
        ("FACT-OLD", "FATO", "WARM", "The release tool is CASE", None),
        ("DEC-OLD", "DECISAO", "WARM", "Adopt CASE for releases", None),
        ("DEC-NEW", "DECISAO", "WARM", "CASE is retired; releases use the gate", None),
        ("HOT-STALE", "FATO", "HOT", "Sprint focus is the gate", "2020-01-01"),
    ]
    for record_id, category, tier, title, review_after in seeds:
        argv = [
            "create", "--id", record_id, "--category", category, "--domain", "operations", "--title", title,
            "--content", f"{title}.", "--tier", tier, "--source", "test", "--confidence", "0.9", "--no-auto-lifecycle",
        ]
        if review_after:
            argv += ["--review-after", review_after]
        classic(root, *argv)
    return root


@pytest.fixture(scope="module")
def classic_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_classic(tmp_path_factory.mktemp("retire-classic"))


@pytest.fixture(scope="module")
def vnext_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = build_classic(tmp_path_factory.mktemp("retire-vnext"))
    kb_next_json(root, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    return root


@pytest.fixture()
def classic_only(classic_template: Path, tmp_path: Path) -> Path:
    return Path(shutil.copytree(classic_template, tmp_path / "classic"))


@pytest.fixture()
def vnext(vnext_template: Path, tmp_path: Path) -> Path:
    return Path(shutil.copytree(vnext_template, tmp_path / "vnext"))


# ---------------------------------------------------------------------------
# Classic: supersede into an existing record
# ---------------------------------------------------------------------------


def test_supersede_into_an_existing_record_creates_no_row(classic_only: Path) -> None:
    before = records(classic_only)

    out = classic(classic_only, "supersede", "FACT-OLD", "--replacement-id", "DEC-NEW")
    after = records(classic_only)

    assert out["id"] == "FACT-OLD" and out["status"] == "SUPERSEDIDO"
    assert set(after) == set(before)
    assert after["FACT-OLD"]["replacement_id"] == "DEC-NEW"
    assert after["FACT-OLD"]["content"] == before["FACT-OLD"]["content"]
    assert after["DEC-NEW"] == before["DEC-NEW"]


def test_several_records_retire_into_one(classic_only: Path) -> None:
    classic(classic_only, "supersede", "FACT-OLD", "--replacement-id", "DEC-NEW")
    classic(classic_only, "supersede", "DEC-OLD", "--replacement-id", "DEC-NEW")

    rows = records(classic_only)
    assert [rows[rid]["status"] for rid in ("FACT-OLD", "DEC-OLD", "DEC-NEW")] == ["SUPERSEDIDO", "SUPERSEDIDO", "ATIVO"]
    assert rows["FACT-OLD"]["replacement_id"] == rows["DEC-OLD"]["replacement_id"] == "DEC-NEW"
    assert rows["DEC-NEW"]["supersedes_id"] is None


@pytest.mark.parametrize(
    "argv, message",
    [
        (["FACT-OLD", "--replacement-id", "DEC-NEW", "--content", "x"], "drop --content"),
        (["FACT-OLD", "--replacement-id", "DEC-NEW", "--category", "DECISAO"], "drop --category"),
        (["FACT-OLD", "--replacement-id", "NOPE"], "Replacement record not found: NOPE"),
        (["FACT-OLD", "--replacement-id", "FACT-OLD"], "cannot replace itself"),
    ],
)
def test_supersede_into_an_existing_record_refuses(classic_only: Path, argv: list[str], message: str) -> None:
    before = records(classic_only)

    result = run_classic(classic_only, "supersede", *argv, "--json")

    assert result.returncode != 0 and message in result.stderr
    assert records(classic_only) == before


def test_only_active_records_take_part(classic_only: Path) -> None:
    classic(classic_only, "supersede", "DEC-OLD", "--replacement-id", "DEC-NEW")

    into_retired = run_classic(classic_only, "supersede", "FACT-OLD", "--replacement-id", "DEC-OLD", "--json")
    twice = run_classic(classic_only, "supersede", "DEC-OLD", "--replacement-id", "DEC-NEW", "--json")

    assert "The replacement must be ATIVO: DEC-OLD is SUPERSEDIDO" in into_retired.stderr
    assert "Only an ATIVO record can be superseded: DEC-OLD is SUPERSEDIDO" in twice.stderr
    assert records(classic_only)["FACT-OLD"]["status"] == "ATIVO"


def test_retire_works_on_a_hardened_kb(classic_only: Path) -> None:
    assert classic(classic_only, "harden")["append_only_hardening"] == "enabled"

    out = classic(classic_only, "supersede", "FACT-OLD", "--replacement-id", "DEC-NEW")

    assert out["status"] == "SUPERSEDIDO"


# ---------------------------------------------------------------------------
# Classic lifecycle: demotions only by proposal in a vNext project
# ---------------------------------------------------------------------------


def test_classic_only_projects_still_demote(classic_only: Path) -> None:
    result = classic(classic_only, "lifecycle", "scheduled-maintenance")

    assert result["demoted_records"] == ["HOT-STALE"]
    assert "demotions_skipped" not in result
    assert records(classic_only)["HOT-STALE"]["tier"] == "WARM"


def test_a_vnext_project_skips_configured_demotions(vnext: Path) -> None:
    before = records(vnext)

    result = classic(vnext, "lifecycle", "scheduled-maintenance")

    assert "apply_demotions" not in result["actions_run"]
    assert result["demotions_skipped"]["actions"] == ["apply_demotions"]
    assert "semantic-hygiene --write-proposals" in result["demotions_skipped"]["reason"]
    assert records(vnext)["HOT-STALE"] == before["HOT-STALE"]


def test_a_vnext_project_skips_explicit_demotion_flags(vnext: Path) -> None:
    lifecycle = classic(vnext, "lifecycle", "session-end", "--apply-demotions", "--apply-cold-demotions")
    consolidate = json.loads(run_classic(vnext, "consolidate", "--apply-demotions").stdout)  # JSON without --json

    assert lifecycle["demotions_skipped"]["actions"] == ["apply_demotions", "apply_cold_demotions"]
    assert consolidate["applied_demotions"] is False and consolidate["demoted_records"] == []
    assert consolidate["demotions_skipped"]["actions"] == ["apply_demotions"]
    assert records(vnext)["HOT-STALE"]["tier"] == "HOT"


# ---------------------------------------------------------------------------
# vNext: the `retire` proposal
# ---------------------------------------------------------------------------


def hygiene_judgment(items: list[dict], provenance: list[str]) -> dict:
    return {
        "groups": {"supersede_or_merge_candidate": items},
        "rationale": "CASE was retired; its records point at the decision that retired it.",
        "confidence": 0.9,
        "provenance": [{"record_id": rid} for rid in provenance],
        "conflicts": [],
    }


def write_hygiene(root: Path, judgment: dict) -> dict:
    path = root / "hygiene-judgment.json"
    path.write_text(json.dumps(judgment), encoding="utf-8")
    return kb_next_json(root, "semantic-hygiene", "--judgment", f"@{path}", "--write-proposals")


def apply(root: Path, proposal_id: str) -> dict:
    return kb_next_json(
        root, "proposal-apply", "--proposal", proposal_id, "--approve", "--approval-note", "approved in chat",
        "--actor", "test-approver", "--actor-runtime", "human",
    )


def retire_item(record_id: str, **extra) -> dict:
    return {"record_id": record_id, "action": "retire", "rationale": "Retired with CASE.", "confidence": 0.9, **extra}


def test_a_retire_proposal_applies_through_the_classic_cli(vnext: Path) -> None:
    written = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-NEW")], ["DEC-NEW"]))
    assert written["validation_status"] == "valid", written["warnings"]
    proposal = json.loads(Path(written["paths"]["proposals"][0]).read_text(encoding="utf-8"))
    assert proposal["action"] == "retire" and proposal["replacement_id"] == "DEC-NEW"

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "applied", applied["warnings"]
    assert applied["canonical_record_id"] == "FACT-OLD"
    row = records(vnext)["FACT-OLD"]
    assert (row["status"], row["replacement_id"]) == ("SUPERSEDIDO", "DEC-NEW")
    assert kb_next.hygiene_target_still_qualifies("retire", None) is False


@pytest.mark.parametrize(
    "item, warning",
    [
        (retire_item("FACT-OLD"), "invalid_retire_item:FACT-OLD:missing_replacement_id"),
        (retire_item("FACT-OLD", replacement_id="FACT-OLD"), "invalid_retire_item:FACT-OLD:replaces_itself"),
        (retire_item("FACT-OLD", replacement_id="NOPE"), "unknown_replacement_record:NOPE"),
    ],
)
def test_a_retire_without_a_live_replacement_is_blocked(vnext: Path, item: dict, warning: str) -> None:
    written = write_hygiene(vnext, hygiene_judgment([item], ["DEC-NEW"]))

    assert written["validation_status"] == "blocked"
    assert warning in written["warnings"]


def test_apply_blocks_a_retire_on_an_older_classic_engine(vnext: Path) -> None:
    written = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-NEW")], ["DEC-NEW"]))
    cli = vnext / ".kb" / "runtime" / "cli.py"
    cli.write_text(cli.read_text(encoding="utf-8").replace('"--replacement-id",', '"--replacement-ref",'), encoding="utf-8")

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "blocked"
    assert any("upgrade-classic" in warning for warning in applied["warnings"])
    assert records(vnext)["FACT-OLD"]["status"] == "ATIVO"


def test_apply_blocks_a_retire_whose_replacement_was_retired_meanwhile(vnext: Path) -> None:
    written = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-OLD")], ["DEC-OLD"]))
    classic(vnext, "supersede", "DEC-OLD", "--replacement-id", "DEC-NEW")

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "blocked" and "invalid_replacement_record" in applied["warnings"]


def test_both_hygiene_passes_need_the_same_limit(vnext: Path) -> None:
    judgment = hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-NEW")], ["DEC-NEW"])
    path = vnext / "hygiene-judgment.json"
    path.write_text(json.dumps(judgment), encoding="utf-8")

    def write(limit: str) -> dict:
        return kb_next_json(vnext, "semantic-hygiene", "--limit", limit, "--judgment", f"@{path}", "--write-proposals")

    narrow = write("1")  # HOT-STALE sorts first; FACT-OLD falls outside the write pass
    wide = write("10")

    assert narrow["validation_status"] == "blocked" and narrow["proposal_ids"] == []
    assert "unknown_record_reference:FACT-OLD" in narrow["warnings"]
    assert wide["validation_status"] == "valid" and len(wide["proposal_ids"]) == 1


def test_a_hygiene_supersede_names_its_target_through_the_proposal(vnext: Path) -> None:
    draft = {
        "category": "FATO", "domain": "operations", "title": "The release tool is the gate",
        "content": "Releases run through the gate since CASE was retired.",
    }
    item = {"record_id": "FACT-OLD", "record_draft": draft, "rationale": "Newer information.", "confidence": 0.9}
    written = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "applied", applied["warnings"]
    assert records(vnext)["FACT-OLD"]["status"] == "SUPERSEDIDO"


# ---------------------------------------------------------------------------
# Session Gate 0.2.9 and the classic skill (KB Lifecycle 0.2.6)
# ---------------------------------------------------------------------------


def test_session_gate_end_keeps_demotions_out_of_vnext_workspaces() -> None:
    command = (ROOT / "plugins" / "session-gate" / "commands" / "gate-session-end.md").read_text(encoding="utf-8")
    vnext_part = command.split("## Step 2: KB/Wiki vNext closeout", 1)[1].split("\n## ", 1)[0]
    classic_part = command.split("## Step 3: KB-lifecycle closeout", 1)[1].split("\n## ", 1)[0]

    assert "python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json" in classic_part
    assert "--apply-demotions --json" not in vnext_part
    # The default vNext close is the vnext-session-end close; curation runs in the weekly run.
    default_steps, on_request = vnext_part.split("Full maintenance on request", 1)
    assert re.findall(r"`(python [^`]+)`", default_steps) == [
        "python .kb/kb.py lifecycle session-end --json",
        "python <resolved-runtime-path> --project-root <vnext.details.project_root> wiki-draft-status --json",
    ]
    assert "weekly maintenance run, not at session end" in " ".join(default_steps.split())
    # A full maintenance pass the user asks for runs the skill's Curation, proposals only.
    assert "Curation section of the kb-wiki-vnext skill" in " ".join(on_request.split())
    assert "python .kb/kb.py hygiene-audit --json" in on_request
    assert "python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene --json" in on_request
    assert (
        "python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene "
        "--judgment @hygiene-judgment.json --write-proposals --json"
    ) in on_request
    assert "--apply-demotions --json" not in on_request and "proposal-apply" not in on_request


def test_the_classic_skill_routes_vnext_projects_to_proposals() -> None:
    skill = (ROOT / "plugins" / "kb-lifecycle" / "skills" / "kb-wiki-maintainer" / "SKILL.md").read_text(encoding="utf-8")
    note = skill.split("## KB/Wiki vNext Projects", 1)[1].split("\n## ", 1)[0]

    assert "`.kb-next/kb-next.config.json`" in note
    assert "python .kb-next/runtime/kb_next.py filing-proposal --input @candidate.json" in note
    assert "python .kb-next/runtime/kb_next.py proposal-apply --proposal filing-20261021T120000Z-0a1b2c3d --approve" in note
    assert "<" not in "".join(span for span in note.split("`")[1::2] if span.startswith("python "))
    assert "write gate denies" in note


# ---------------------------------------------------------------------------
# Review of PR #36 at 060cb91 (2026-10-21)
# ---------------------------------------------------------------------------


def apply_with(root: Path, proposal_id: str, *extra: str) -> dict:
    return kb_next_json(
        root, "proposal-apply", "--proposal", proposal_id, "--approve", "--approval-note", "approved in chat",
        "--actor", "test-approver", "--actor-runtime", "human", *extra,
    )


def test_apply_refuses_a_target_override_for_hygiene_actions(vnext: Path) -> None:
    retire = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-NEW")], ["DEC-NEW"]))
    demote = write_hygiene(vnext, {
        "groups": {"demote_candidate": [{"record_id": "HOT-STALE", "rationale": "Review date passed.", "confidence": 0.9}]},
        "rationale": "HOT review.", "confidence": 0.9, "provenance": [{"record_id": "HOT-STALE"}], "conflicts": [],
    })
    before = records(vnext)

    retired = apply_with(vnext, retire["proposal_ids"][0], "--target-record-id", "DEC-OLD")
    demoted = apply_with(vnext, demote["proposal_ids"][0], "--target-record-id", "FACT-OLD")

    for result in (retired, demoted):
        assert result["status"] == "blocked"
        assert any(warning.startswith("invalid_target_override") for warning in result["warnings"]), result["warnings"]
    assert records(vnext) == before

    same = apply_with(vnext, retire["proposal_ids"][0], "--target-record-id", "FACT-OLD")
    assert same["status"] == "applied", same["warnings"]


def test_apply_refuses_a_supersede_override_the_proposal_does_not_name(vnext: Path) -> None:
    draft = {
        "category": "FATO", "domain": "operations", "title": "The release tool is the gate",
        "content": "Releases run through the gate since CASE was retired.",
    }
    item = {"record_id": "FACT-OLD", "record_draft": draft, "rationale": "Newer information.", "confidence": 0.9}
    written = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))
    before = records(vnext)

    applied = apply_with(vnext, written["proposal_ids"][0], "--target-record-id", "DEC-OLD")

    assert applied["status"] == "blocked"
    assert any(warning.startswith("invalid_target_override") for warning in applied["warnings"])
    assert records(vnext) == before


def test_an_invalidated_retire_leaves_the_queue_for_its_correction(vnext: Path) -> None:
    first = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-OLD")], ["DEC-OLD"]))
    assert first["validation_status"] == "valid" and len(first["proposal_ids"]) == 1
    classic(vnext, "supersede", "DEC-OLD", "--replacement-id", "DEC-NEW")

    corrected = write_hygiene(vnext, hygiene_judgment([retire_item("FACT-OLD", replacement_id="DEC-NEW")], ["DEC-NEW"]))

    assert corrected["already_open"] == []
    assert len(corrected["proposal_ids"]) == 1
    open_ids = [item["proposal_id"] for item in corrected["review_budget"]["open"]]
    assert first["proposal_ids"][0] not in open_ids


def classic_env(root: Path, scope: str, *argv: str) -> dict:
    env = {**os.environ, "KB_FACTORY_WORKTREE_SCOPE": scope}
    result = subprocess.run(
        [sys.executable, "-B", str(root / ".kb" / "kb.py"), *argv, "--json"],
        text=True, capture_output=True, check=False, cwd=str(root / ".kb"), env=env,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def linked_pair(classic_template: Path, tmp_path: Path) -> tuple[Path, Path]:
    main = Path(shutil.copytree(classic_template, tmp_path / "main"))
    worktree = Path(shutil.copytree(classic_template, tmp_path / "wt"))
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    (worktree / ".git").write_text(f"gitdir: {gitdir.as_posix()}\n", encoding="utf-8")
    return main, worktree


def activate(root: Path) -> None:
    (root / ".kb-next").mkdir(exist_ok=True)
    (root / ".kb-next" / "kb-next.config.json").write_text('{"schema_version": 1}', encoding="utf-8")


def test_a_local_worktree_of_a_vnext_main_checkout_skips_demotions(classic_template: Path, tmp_path: Path) -> None:
    main, worktree = linked_pair(classic_template, tmp_path)
    activate(main)

    result = classic_env(worktree, "local", "lifecycle", "scheduled-maintenance")

    assert result["kb_root"]["resolution"] == "local_worktree"
    assert result["demotions_skipped"]["actions"] == ["apply_demotions"]
    assert records(worktree)["HOT-STALE"]["tier"] == "HOT"


def test_a_worktree_activated_alone_skips_demotions_on_the_shared_kb(classic_template: Path, tmp_path: Path) -> None:
    main, worktree = linked_pair(classic_template, tmp_path)
    activate(worktree)

    result = classic_env(worktree, "shared", "lifecycle", "scheduled-maintenance")

    assert result["kb_root"]["resolution"] == "main_worktree"
    assert result["demotions_skipped"]["actions"] == ["apply_demotions"]
    assert records(main)["HOT-STALE"]["tier"] == "HOT"


def test_a_classic_worktree_pair_still_demotes(classic_template: Path, tmp_path: Path) -> None:
    main, worktree = linked_pair(classic_template, tmp_path)

    result = classic_env(worktree, "shared", "lifecycle", "scheduled-maintenance")

    assert "demotions_skipped" not in result
    assert records(main)["HOT-STALE"]["tier"] == "WARM"


# ---------------------------------------------------------------------------
# Second review of PR #36 at 23af579 (2026-10-21): category change on supersede
# ---------------------------------------------------------------------------


def run_kb_next(root: Path, *argv: str) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = kb_next.main(["--project-root", str(root), *argv, "--json"])
    return code, json.loads(out.getvalue())


def decision_draft(**extra) -> dict:
    return {
        "category": "DECISAO", "domain": "operations", "title": "Releases go through the gate",
        "content": "Decided: every release goes through the gate.", **extra,
    }


def test_a_hygiene_supersede_through_proposal_apply_changes_the_category(vnext: Path) -> None:
    item = {"record_id": "FACT-OLD", "record_draft": decision_draft(), "rationale": "Now a decision.", "confidence": 0.9}
    written = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "applied", applied["warnings"]
    rows = records(vnext)
    assert rows[applied["canonical_record_id"]]["category"] == "DECISAO"
    assert rows["FACT-OLD"]["status"] == "SUPERSEDIDO"


def test_a_filing_supersede_through_proposal_apply_changes_the_category(vnext: Path) -> None:
    candidate = vnext / "candidate.json"
    candidate.write_text(json.dumps({"title": "Releases go through the gate", "content": "Decided.", "source": "chat"}), encoding="utf-8")
    judgment = vnext / "judgment.json"
    judgment.write_text(json.dumps({
        "action": "supersede", "record_draft": decision_draft(supersedes_id="FACT-OLD"), "confidence": 0.9,
        "rationale": "Now a decision.", "provenance": [{"record_id": "FACT-OLD"}], "conflicts": [],
    }), encoding="utf-8")
    filed = kb_next_json(vnext, "filing-proposal", "--input", f"@{candidate}", "--category", "DECISAO",
                         "--domain", "operations", "--judgment", f"@{judgment}")
    assert filed["validation_status"] == "valid", filed["warnings"]

    applied = apply(vnext, filed["proposal_id"])

    assert applied["status"] == "applied", applied["warnings"]
    assert records(vnext)[applied["canonical_record_id"]]["category"] == "DECISAO"


def make_engine_lack_category(root: Path) -> None:
    cli = root / ".kb" / "runtime" / "cli.py"
    text = cli.read_text(encoding="utf-8")
    old = 'supersede.add_argument("--category"'
    assert text.count(old) == 1
    cli.write_text(text.replace(old, 'supersede.add_argument("--kind"'), encoding="utf-8")


def test_both_routes_refuse_a_category_change_on_an_older_engine(vnext: Path) -> None:
    item = {"record_id": "FACT-OLD", "record_draft": decision_draft(), "rationale": "Now a decision.", "confidence": 0.9}
    written = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))
    make_engine_lack_category(vnext)
    before = records(vnext)

    applied = apply(vnext, written["proposal_ids"][0])
    code, filed = run_kb_next(
        vnext, "approved-filing", "--supersedes", "FACT-OLD", "--category", "DECISAO", "--domain", "operations",
        "--title", "Releases go through the gate", "--content", "Decided.", "--confidence", "0.95",
        "--record-id", "FACT-OLD", "--approval-note", "User approved in chat: 'ok'", "--actor", "sponsor",
        "--actor-runtime", "claude-code",
    )

    assert applied["status"] == "blocked"
    assert any("upgrade-classic" in warning for warning in applied["warnings"]), applied["warnings"]
    assert code == 1 and filed["status"] == "blocked"
    assert any("upgrade-classic" in warning for warning in filed["warnings"]), filed["warnings"]
    assert records(vnext) == before


def test_an_unchanged_category_still_supersedes_on_an_older_engine(vnext: Path) -> None:
    draft = {"category": "FATO", "domain": "operations", "title": "The release tool is the gate", "content": "Gate."}
    item = {"record_id": "FACT-OLD", "record_draft": draft, "rationale": "Newer information.", "confidence": 0.9}
    written = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))
    make_engine_lack_category(vnext)

    applied = apply(vnext, written["proposal_ids"][0])

    assert applied["status"] == "applied", applied["warnings"]


# ---------------------------------------------------------------------------
# One worktree rule for the detector, the gate and the classic guard
# ---------------------------------------------------------------------------

GATE_SCRIPT = ROOT / "plugins" / "kb-wiki-vnext" / "scripts" / "write_gate.py"
DETECTOR_SCRIPT = ROOT / "plugins" / "session-gate" / "scripts" / "detect_workspace.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_detector_gate_and_classic_guard_agree_on_a_main_only_activation(classic_template: Path, tmp_path: Path) -> None:
    # Three copies of the worktree reader ship in three packages (Session Gate,
    # kb-wiki-vnext, kb-lifecycle); this test keeps them in step.
    main, worktree = linked_pair(classic_template, tmp_path)
    kb_next_json(main, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    detector = load_module("detector_parity", DETECTOR_SCRIPT)
    gate = load_module("gate_parity", GATE_SCRIPT)

    found = detector.detect(worktree)
    lifecycle = classic_env(worktree, "local", "lifecycle", "scheduled-maintenance")

    assert Path(found["vnext"]["details"]["project_root"]) == main.resolve()
    assert gate.config_root(worktree).resolve() == main.resolve()
    assert lifecycle["demotions_skipped"]["actions"] == ["apply_demotions"]


def test_session_gate_startup_runs_against_the_main_checkout(classic_template: Path, tmp_path: Path) -> None:
    main, worktree = linked_pair(classic_template, tmp_path)
    kb_next_json(main, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    detector = load_module("detector_startup", DETECTOR_SCRIPT)
    details = detector.detect(worktree)["vnext"]["details"]
    command = (ROOT / "plugins" / "session-gate" / "commands" / "gate-session-start.md").read_text(encoding="utf-8")

    without = subprocess.run(
        [sys.executable, "-B", str(KB_NEXT), "session-start", "--json"],
        cwd=str(worktree), capture_output=True, text=True, check=False,
    )
    started = subprocess.run(
        [sys.executable, "-B", str(KB_NEXT), "--project-root", details["project_root"], "session-start", "--json"],
        cwd=str(worktree), capture_output=True, text=True, check=False,
    )

    assert without.returncode != 0
    assert started.returncode == 0, started.stderr
    assert (Path(details["project_root"]) / ".kb-next" / "memory" / "NOW.md").is_file()
    assert "python <runtime_ref> --project-root <vnext.details.project_root> session-start --json" in command
    assert "`<vnext.details.project_root>/.kb-next/memory/NOW.md`" in command


# ---------------------------------------------------------------------------
# Review of 2026-10-23: replays, confidence range and domain on supersede
# ---------------------------------------------------------------------------


def approved_filing(root: Path, *argv: str) -> tuple[int, dict]:
    return run_kb_next(
        root, "approved-filing", "--category", "FATO", "--content", "Approved in chat.", "--record-id", "DEC-NEW",
        "--approval-note", "approved in chat", "--actor", "test-approver", "--actor-runtime", "human", *argv,
    )


def new_record_proposal(root: Path, title: str, confidence: float = 0.9, drafted=None) -> str:
    draft = {"category": "FATO", "domain": "operations", "title": title, "content": f"{title}."}
    if drafted is not None:
        draft["confidence"] = drafted
    judgment = {"action": "new", "record_draft": draft, "confidence": confidence, "rationale": "New fact.",
                "provenance": [{"record_id": "DEC-NEW"}], "conflicts": []}
    candidate = {"title": title, "content": f"{title}.", "source": "test"}
    return kb_next_json(
        root, "filing-proposal", "--input", json.dumps(candidate), "--category", "FATO", "--domain", "operations",
        "--judgment", json.dumps(judgment),
    )["proposal_id"]


def test_a_version_supersede_refuses_a_record_already_superseded(classic_only: Path) -> None:
    first = classic(classic_only, "supersede", "FACT-OLD", "--content", "The release tool is the gate.")

    again = run_classic(classic_only, "supersede", "FACT-OLD", "--content", "A second successor.", "--json")

    assert again.returncode != 0
    assert "Only an ATIVO record can be superseded: FACT-OLD is SUPERSEDIDO" in again.stderr
    successors = [r["id"] for r in records(classic_only).values() if r["supersedes_id"] == "FACT-OLD"]
    assert successors == [first["id"]]


def test_a_replayed_supersede_proposal_writes_nothing(vnext: Path) -> None:
    draft = {"category": "FATO", "domain": "operations", "title": "The release tool is the gate",
             "content": "Releases run through the gate since CASE was retired."}
    item = {"record_id": "FACT-OLD", "record_draft": draft, "rationale": "Newer information.", "confidence": 0.9}
    proposal_id = write_hygiene(vnext, hygiene_judgment([item], ["FACT-OLD"]))["proposal_ids"][0]
    first = apply(vnext, proposal_id)
    after_first = records(vnext)

    replay = apply(vnext, proposal_id)

    assert first["status"] == "applied", first["warnings"]
    assert replay["status"] == "already_applied"
    assert replay["canonical_record_id"] == first["canonical_record_id"]
    assert replay["warnings"] == [f"already_applied:{first['apply_id']}"]
    assert records(vnext) == after_first


def test_a_replayed_new_record_proposal_writes_nothing(vnext: Path) -> None:
    proposal_id = new_record_proposal(vnext, "Releases are tagged after the gate")
    first = apply(vnext, proposal_id)
    after_first = records(vnext)

    replay = apply(vnext, proposal_id)

    assert first["status"] == "applied", first["warnings"]
    assert (replay["status"], replay["canonical_record_id"]) == ("already_applied", first["canonical_record_id"])
    assert records(vnext) == after_first


def test_an_apply_stopped_after_the_classic_write_is_found_in_the_canonical_kb(vnext: Path) -> None:
    proposal_id = new_record_proposal(vnext, "Releases need a changelog")
    first = apply(vnext, proposal_id)
    manifest_path = Path(first["paths"]["apply_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "applying"  # what a run killed after the classic write leaves behind
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = records(vnext)

    replay = apply(vnext, proposal_id)

    assert (replay["status"], replay["canonical_record_id"]) == ("already_applied", first["canonical_record_id"])
    assert replay["warnings"] == [f"already_applied:record {first['canonical_record_id']}"]
    assert records(vnext) == before


def test_an_old_apply_whose_manifest_stayed_in_another_worktree_is_still_found(
    vnext_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KB_FACTORY_WORKTREE_SCOPE", "shared")
    main, worktree = linked_pair(vnext_template, tmp_path)
    proposal_id = new_record_proposal(main, "Releases are mirrored")
    for part in ("proposals", "manifests"):
        shutil.copytree(main / ".kb-next" / part, worktree / ".kb-next" / part, dirs_exist_ok=True)
    first = apply(worktree, proposal_id)  # its manifest stays in the worktree
    before = records(main)

    replay = apply(main, proposal_id)

    assert (replay["status"], replay["canonical_record_id"]) == ("already_applied", first["canonical_record_id"])
    assert records(main) == before


@pytest.mark.parametrize("applied_in", ["main", "worktree"])
def test_a_linked_worktree_and_its_main_checkout_share_the_replay_guard(
    vnext_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, applied_in: str
) -> None:
    monkeypatch.setenv("KB_FACTORY_WORKTREE_SCOPE", "shared")  # conftest defaults tests to local
    main, worktree = linked_pair(vnext_template, tmp_path)
    proposal_id = new_record_proposal(main, "Releases are announced")
    for part in ("proposals", "manifests"):
        shutil.copytree(main / ".kb-next" / part, worktree / ".kb-next" / part, dirs_exist_ok=True)
    first_root, second_root = (main, worktree) if applied_in == "main" else (worktree, main)
    first = apply(first_root, proposal_id)
    before = records(main)

    replay = apply(second_root, proposal_id)

    assert first["status"] == "applied", first["warnings"]
    assert (replay["status"], replay["canonical_record_id"]) == ("already_applied", first["canonical_record_id"])
    assert records(main) == before


def test_two_worktrees_on_a_classic_main_write_one_record_for_one_proposal(
    classic_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KB_FACTORY_WORKTREE_SCOPE", "shared")
    main, first_wt = linked_pair(classic_template, tmp_path)
    second_wt = Path(shutil.copytree(classic_template, tmp_path / "wt2"))
    gitdir = main / ".git" / "worktrees" / "wt2"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    (second_wt / ".git").write_text(f"gitdir: {gitdir.as_posix()}\n", encoding="utf-8")
    for worktree in (first_wt, second_wt):
        kb_next_json(worktree, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    proposal_id = new_record_proposal(first_wt, "Releases are reviewed twice")
    for part in ("proposals", "manifests"):
        shutil.copytree(first_wt / ".kb-next" / part, second_wt / ".kb-next" / part, dirs_exist_ok=True)
    first = apply(first_wt, proposal_id)
    before = records(main)
    # The second run checked before the first one wrote: only the classic
    # transaction on the shared KB stands between it and a second record.
    monkeypatch.setattr(kb_next, "prior_proposal_apply", lambda root, proposal_id: None)

    racing = apply(second_wt, proposal_id)

    assert first["status"] == "applied", first["warnings"]
    assert (racing["status"], racing["canonical_record_id"]) == ("already_applied", first["canonical_record_id"])
    assert records(main) == before


def test_create_if_source_absent_returns_the_record_with_that_source(classic_only: Path) -> None:
    argv = ["create", "--category", "FATO", "--domain", "operations", "--title", "Gate first",
            "--content", "Releases go through the gate.", "--source", "kb-wiki-vnext approved proposal filing-x"]
    first = classic(classic_only, *argv)
    before = records(classic_only)

    again = classic(classic_only, *argv[:-1], "kb-wiki-vnext approved proposal filing-x", "--if-source-absent")
    other = classic(classic_only, *argv[:-1], "kb-wiki-vnext approved proposal filing-y", "--if-source-absent")

    assert (again["id"], again["existing"]) == (first["id"], True)
    assert "existing" not in other and other["id"] != first["id"]
    assert set(records(classic_only)) == set(before) | {other["id"]}


def test_a_supersede_that_loses_the_race_leaves_no_successor(classic_only: Path) -> None:
    # Another supersede commits between the status check and this write.
    script = """
import argparse, sqlite3, sys
sys.path.insert(0, ".")
from runtime import records
original = records.insert_record
def racing_insert(conn, data, action="create", **kwargs):
    other = sqlite3.connect("kb.db")
    other.execute("UPDATE records SET status = 'SUPERSEDIDO', replacement_id = 'DEC-NEW' WHERE id = 'FACT-OLD'")
    other.commit()
    other.close()
    return original(conn, data, action, **kwargs)
records.insert_record = racing_insert
fields = dict.fromkeys(dest for _, dest in records.SUPERSEDE_VERSION_FLAGS)
fields.update(record_id="FACT-OLD", replacement_id=None, new_id="FACT-RACE", content="The losing successor.", json=True)
records.cmd_supersede(argparse.Namespace(**fields), emit=lambda *args, **kwargs: None)
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], text=True, capture_output=True,
                            cwd=str(classic_only / ".kb"))

    assert result.returncode != 0
    assert "FACT-OLD changed during this supersede" in result.stderr
    after = records(classic_only)
    assert "FACT-RACE" not in after
    assert (after["FACT-OLD"]["status"], after["FACT-OLD"]["replacement_id"]) == ("SUPERSEDIDO", "DEC-NEW")


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "1.1", "-0.1"])
def test_approved_filing_refuses_a_confidence_outside_zero_to_one(vnext: Path, value: str) -> None:
    before = records(vnext)

    code, payload = approved_filing(vnext, "--domain", "operations", "--title", f"Range {value}", f"--confidence={value}")

    assert code == 1
    assert payload["status"] == "blocked"
    assert any(warning.startswith("invalid_confidence:") for warning in payload["warnings"]), payload["warnings"]
    assert records(vnext) == before


@pytest.mark.parametrize(("judged", "drafted"), [(1.5, None), (0.9, 1.5), (0.9, "nan")])
def test_proposal_apply_refuses_a_confidence_outside_zero_to_one(vnext: Path, judged: float, drafted) -> None:
    # The judgment's confidence gates the apply; the draft's is what the classic command stores.
    proposal_id = new_record_proposal(vnext, "Releases need two reviews", confidence=judged, drafted=drafted)
    before = records(vnext)

    applied = apply(vnext, proposal_id)

    assert applied["status"] == "blocked"
    assert any(warning.startswith("invalid_confidence:") for warning in applied["warnings"]), applied["warnings"]
    assert records(vnext) == before


def test_a_supersede_that_changes_the_domain_is_refused(vnext: Path) -> None:
    config_path = vnext / ".kb" / "kb.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["domains"].append("finance")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    before = records(vnext)

    code, payload = approved_filing(
        vnext, "--domain", "finance", "--title", "The release tool is the gate", "--confidence", "0.9",
        "--supersedes", "FACT-OLD",
    )

    assert code == 1
    assert "invalid_domain_change:operations->finance" in payload["warnings"]
    assert records(vnext) == before


def test_a_failed_engine_probe_blocks_the_apply_instead_of_dropping_the_guard(
    vnext: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposal_id = new_record_proposal(vnext, "Releases are probed")
    original = kb_next.subprocess.run

    def failing_help(cmd, *args, **kwargs):
        if "--help" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "crashed")
        return original(cmd, *args, **kwargs)

    monkeypatch.setattr(kb_next.subprocess, "run", failing_help)
    before = records(vnext)

    applied = apply(vnext, proposal_id)

    assert applied["status"] == "blocked"
    assert any("classic engine probe failed" in warning for warning in applied["warnings"]), applied["warnings"]
    assert records(vnext) == before
