"""The kb-wiki-vnext write gate: agent shells in a vNext project cannot run the
classic `kb.py create|file|supersede|update`; the deny names the proposal path.

Product requirement from 2026-10-20 (docs/benchmarks/kb-value/README.md): in 60
days, 0 of 123 agent writes went through filing-proposal and proposal-apply.
"""
from __future__ import annotations

import contextlib
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

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugins" / "kb-wiki-vnext"
GATE = PLUGIN / "scripts" / "write_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("kb_wiki_vnext_write_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_gate()


def make_project(root: Path, *, vnext: bool = True, config: dict | None = None) -> Path:
    (root / ".kb").mkdir(parents=True)
    (root / ".kb" / "kb.py").write_text("# classic entrypoint\n", encoding="utf-8")
    if vnext:
        (root / ".kb-next").mkdir()
        payload = {"schema_version": 1, **(config or {})}
        (root / ".kb-next" / "kb-next.config.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def payload(command, cwd: Path, tool: str = "Bash") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }


def run_hook(data) -> subprocess.CompletedProcess:
    raw = data if isinstance(data, (bytes, str)) else json.dumps(data)
    return subprocess.run(
        [sys.executable, "-B", str(GATE)],
        input=raw if isinstance(raw, bytes) else raw.encode("utf-8"),
        capture_output=True,
        check=False,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return make_project(tmp_path / "proj")


@pytest.mark.parametrize(
    "command",
    [
        'python .kb/kb.py create --category FATO --domain ops --title "T" --content "C"',
        "python -B .kb/kb.py file --filing-type answer --category FATO --domain ops --title T --content C",
        "python .kb/kb.py supersede KB-1 --content new",
        "python .kb/kb.py update KB-1 --tier WARM",
        r"py -3 .\.kb\kb.py create --category FATO --domain ops --title T --content C",
        r'& python ".\.kb\kb.py" update KB-1 --tags x',
        "cd .kb && python kb.py create --category FATO --domain ops --title T --content C",
        "git status; python3 .kb/kb.py create --category FATO --domain ops --title T --content C 2>&1 | tail -5",
        "PYTHONIOENCODING=utf-8 python .kb/kb.py update KB-1 --confidence 0.9",
        "uv run python .kb/kb.py supersede KB-1 --content x",
        "./.kb/kb.py create --category FATO --domain ops --title T --content C",
    ],
)
def test_classic_writes_are_denied_in_a_vnext_project(project: Path, command: str) -> None:
    reason = gate.decide(payload(command, project))

    assert reason and "kb-wiki-vnext write gate" in reason
    assert "proposal-apply --proposal" in reason


@pytest.mark.parametrize(
    "command",
    [
        'grep -rn "kb.py create" docs',
        'git commit -m "docs: never run kb.py update by hand"',
        "python .kb/kb.py search create",
        "python .kb/kb.py lifecycle session-end --json",
        "python .kb/kb.py pending --json",
        "python .kb/kb.py hygiene-audit --json",
        "python .kb/kb.py get KB-1",
        "python core/templates/kb/kb.py create --category FATO --domain ops --title T --content C",
        "python tools/report.py .kb/kb.py create",
        "echo done",
    ],
)
def test_reads_and_other_commands_pass(project: Path, command: str) -> None:
    assert gate.decide(payload(command, project)) is None


def test_the_commands_the_deny_recommends_are_not_gated(project: Path) -> None:
    for subcommand in gate.GATED_SUBCOMMANDS:
        reason = gate.deny_reason(subcommand, project)
        for quoted in re.findall(r"`(python [^`]+)`", reason):
            assert gate.decide(payload(quoted, project)) is None, quoted


def test_proposal_apply_writes_through_its_own_subprocess(project: Path) -> None:
    # The hook sees only the agent's shell text; proposal-apply calls the
    # classic CLI with subprocess.run, so the governed path stays open.
    command = (
        "python .kb-next/runtime/kb_next.py proposal-apply --proposal filing-1 --approve "
        '--approval-note "approved in chat" --actor regis --actor-runtime claude-code --json'
    )
    assert gate.decide(payload(command, project)) is None


def test_update_points_to_semantic_hygiene_not_to_an_unappliable_filing(project: Path) -> None:
    update = gate.deny_reason("update", project)
    create = gate.deny_reason("create", project)
    supersede = gate.deny_reason("supersede", project)

    assert "semantic-hygiene --judgment @hygiene-judgment.json --write-proposals --json" in update
    assert "own terminal" in update
    assert '"new"' in create and "filing-proposal --input @candidate.json" in create
    assert '"supersede"' in supersede


def test_the_deny_names_the_project_runtime_or_the_plugin_runtime(project: Path) -> None:
    plugin_runtime = (PLUGIN / "runtime" / "kb_next.py").as_posix()
    assert plugin_runtime in gate.deny_reason("create", project)

    (project / ".kb-next" / "runtime").mkdir()
    (project / ".kb-next" / "runtime" / "kb_next.py").write_text("# runtime\n", encoding="utf-8")
    assert "python .kb-next/runtime/kb_next.py filing-proposal" in gate.deny_reason("create", project)


def test_classic_only_projects_are_not_gated(tmp_path: Path) -> None:
    classic = make_project(tmp_path / "classic", vnext=False)

    assert gate.decide(payload("python .kb/kb.py create --category FATO", classic)) is None


def test_the_owner_can_turn_the_gate_off(tmp_path: Path) -> None:
    off = make_project(tmp_path / "off", config={"write_gate": {"enabled": False}})
    on = make_project(tmp_path / "on", config={"write_gate": {"enabled": True}})

    assert gate.decide(payload("python .kb/kb.py create --category FATO", off)) is None
    assert gate.decide(payload("python .kb/kb.py create --category FATO", on))


def test_the_target_kb_decides_not_the_session_folder(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)

    into_vnext = f'python "{(vnext / ".kb" / "kb.py").as_posix()}" create --category FATO'
    into_classic = f'python "{(classic / ".kb" / "kb.py").as_posix()}" create --category FATO'

    assert gate.decide(payload(into_vnext, classic))
    assert gate.decide(payload(into_classic, vnext)) is None


def test_codex_argv_commands_are_read(project: Path) -> None:
    argv = ["bash", "-lc", "python .kb/kb.py create --category FATO --domain ops --title T --content C"]

    assert gate.decide(payload(argv, project))


def test_the_hook_prints_a_deny_decision_for_bash_and_powershell(project: Path) -> None:
    for tool in ("Bash", "PowerShell"):
        result = run_hook(payload("python .kb/kb.py create --category FATO --domain ops", project, tool))

        assert result.returncode == 0, result.stderr
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert decision["hookEventName"] == "PreToolUse"
        assert decision["permissionDecision"] == "deny"
        assert "filing-proposal" in decision["permissionDecisionReason"]


@pytest.mark.parametrize("raw", [b"", b"not json", b'{"tool_input": "kb.py"}', b"[1, 2, \"kb.py\"]"])
def test_the_hook_fails_open_and_silent(raw: bytes) -> None:
    result = run_hook(raw)

    assert result.returncode == 0
    assert result.stdout == b""


def test_an_allowed_command_leaves_no_output(project: Path) -> None:
    result = run_hook(payload("python .kb/kb.py search gate", project))

    assert result.returncode == 0 and result.stdout == b""


def test_the_plugin_registers_the_gate_for_both_shell_tools() -> None:
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    pre = hooks["PreToolUse"]
    assert [entry["matcher"] for entry in pre] == ["Bash|PowerShell"]
    commands = [hook["command"] for hook in pre[0]["hooks"]]
    assert commands == ['python "${CLAUDE_PLUGIN_ROOT}/scripts/write_gate.py"']
    assert "SessionStart" in hooks


def test_session_hint_states_the_rule_while_the_gate_is_on(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("kb_next_gate_hint", REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py")
    kb_next = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kb_next)
    memory = tmp_path / ".kb" / "memory"
    memory.mkdir(parents=True)
    for name in ("HOT.md", "INDEX.md"):
        (memory / name).write_text(f"# {name}\n", encoding="utf-8")
    with contextlib.closing(sqlite3.connect(tmp_path / ".kb" / "kb.db")) as conn:
        conn.execute(
            "CREATE TABLE records (id TEXT PRIMARY KEY, category TEXT, domain TEXT, title TEXT, content TEXT, "
            "status TEXT, tier TEXT, source TEXT, tags_json TEXT, created_at TEXT, updated_at TEXT, source_id TEXT)"
        )

    def run(*argv: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            assert kb_next.main(["--project-root", str(tmp_path), *argv]) == 0
        return out.getvalue()

    run("activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json")
    rule = "plugin hook denies direct `.kb/kb.py create|file|supersede|update`"
    assert rule in run("session-hint")

    config_path = tmp_path / ".kb-next" / "kb-next.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["write_gate"] = {"enabled": False}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert rule not in run("session-hint")


# ---------------------------------------------------------------------------
# The path the deny points to completes on a real classic KB
# ---------------------------------------------------------------------------

KB_NEXT_MASTER = REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


@pytest.fixture(scope="module")
def governed_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("governed-template")
    kb_root = root / ".kb"
    kb_root.mkdir()
    shutil.copytree(REPO_ROOT / "core" / "templates" / "kb" / "runtime", kb_root / "runtime", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(REPO_ROOT / "core" / "templates" / "kb" / "kb.py", kb_root / "kb.py")
    config = {
        "schema_version": 4,
        "project": {"name": "Governed KB", "slug": "governed-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["operations"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "wiki": {"enabled": False},
    }
    (kb_root / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run([sys.executable, "-B", str(kb_root / "kb.py"), "init"], capture_output=True, check=True, cwd=str(kb_root))
    classic_json(
        root, "create", "--id", "FACT-OLD", "--category", "FATO", "--domain", "operations",
        "--title", "Release cadence is monthly", "--content", "The team ships one release a month.",
        "--source", "test", "--confidence", "0.9", "--no-auto-lifecycle",
    )
    (root / "notes.md").write_text("Release cadence moved to every two weeks on 2026-10-01.\n", encoding="utf-8")
    vnext_json(root, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    return root


@pytest.fixture()
def governed(governed_template: Path, tmp_path: Path) -> Path:
    target = tmp_path / "governed"
    shutil.copytree(governed_template, target)
    return target


def classic_json(root: Path, *argv: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-B", str(root / ".kb" / "kb.py"), *argv, "--json"],
        capture_output=True, check=True, text=True, cwd=str(root / ".kb"),
    )
    return json.loads(result.stdout)


def vnext_json(root: Path, *argv: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-B", str(KB_NEXT_MASTER), "--project-root", str(root), *argv, "--json"],
        capture_output=True, check=True, text=True,
    )
    return json.loads(result.stdout)


def file_and_apply(root: Path, judgment: dict) -> tuple[dict, dict | None]:
    """Run the deny's two commands: filing-proposal, then proposal-apply when the filing is valid."""
    candidate = root / "candidate.json"
    candidate.write_text(json.dumps({k: judgment["record_draft"][k] for k in ("title", "content")} | {"source": "notes.md"}), encoding="utf-8")
    judgment_path = root / "judgment.json"
    judgment_path.write_text(json.dumps(judgment), encoding="utf-8")
    filed = vnext_json(
        root, "filing-proposal", "--input", f"@{candidate}", "--category", "FATO", "--domain", "operations",
        "--judgment", f"@{judgment_path}",
    )
    if filed["validation_status"] != "valid":
        return filed, None
    applied = vnext_json(
        root, "proposal-apply", "--proposal", filed["proposal_id"], "--approve",
        "--approval-note", "approved in chat", "--actor", "test-approver", "--actor-runtime", "human",
    )
    return filed, applied


def draft(record_id: str, **extra) -> dict:
    return {
        "id": record_id, "category": "FATO", "domain": "operations",
        "title": "Release cadence is every two weeks",
        "content": "The team ships a release every two weeks since 2026-10-01.", **extra,
    }


def record_status(root: Path, record_id: str) -> str | None:
    with contextlib.closing(sqlite3.connect(root / ".kb" / "kb.db")) as conn:
        row = conn.execute("SELECT status FROM records WHERE id = ?", (record_id,)).fetchone()
    return row[0] if row else None


def test_a_file_source_goes_through_ingest_then_files_and_applies(governed: Path) -> None:
    source_id = classic_json(governed, "ingest", str(governed / "notes.md"), "--domain", "operations")["source_id"]

    filed, applied = file_and_apply(governed, {
        "action": "new", "record_draft": draft("FACT-NEW"), "confidence": 0.9,
        "rationale": "Cadence changed.", "provenance": [{"source_id": source_id}], "conflicts": [],
    })

    assert filed["validation_status"] == "valid", filed["warnings"]
    assert applied and applied["status"] == "applied", applied
    assert record_status(governed, "FACT-NEW") == "ATIVO"


def test_an_existing_record_is_valid_provenance(governed: Path) -> None:
    filed, applied = file_and_apply(governed, {
        "action": "new", "record_draft": draft("FACT-CITED"), "confidence": 0.9,
        "rationale": "Follows from the old cadence record.", "provenance": [{"record_id": "FACT-OLD"}], "conflicts": [],
    })

    assert applied and applied["status"] == "applied", (filed["warnings"], applied)
    assert record_status(governed, "FACT-CITED") == "ATIVO"


def test_a_supersede_names_its_target_in_the_draft(governed: Path) -> None:
    filed, applied = file_and_apply(governed, {
        "action": "supersede", "record_draft": draft("FACT-NEXT", supersedes_id="FACT-OLD"), "confidence": 0.9,
        "rationale": "Cadence changed.", "provenance": [{"record_id": "FACT-OLD"}], "conflicts": [],
    })

    assert applied and applied["status"] == "applied", (filed["warnings"], applied)
    assert record_status(governed, "FACT-OLD") == "SUPERSEDIDO"
    assert record_status(governed, "FACT-NEXT") == "ATIVO"


@pytest.mark.parametrize(
    "provenance, warning",
    [
        ([{"source": "notes.md:1"}], "invalid_provenance[0]"),
        (["https://example.com/cadence"], "unknown_record_reference:https://example.com/cadence"),
        ([{"source_id": "SRC-MISSING"}], "unknown_source_reference:SRC-MISSING"),
    ],
)
def test_filing_blocks_provenance_that_apply_would_block(governed: Path, provenance: list, warning: str) -> None:
    filed, applied = file_and_apply(governed, {
        "action": "new", "record_draft": draft("FACT-LOOSE"), "confidence": 0.9,
        "rationale": "Cadence changed.", "provenance": provenance, "conflicts": [],
    })

    assert filed["validation_status"] == "blocked" and applied is None
    assert warning in filed["warnings"]
    assert record_status(governed, "FACT-LOOSE") is None


def test_the_gate_stays_on_the_standard_library() -> None:
    source = GATE.read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) ([A-Za-z_]+)", source, re.MULTILINE))

    assert imports <= {"__future__", "json", "os", "re", "sys", "pathlib"}
