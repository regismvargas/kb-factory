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


def test_the_deny_names_the_one_call_route_for_a_chat_approval(project: Path) -> None:
    create = gate.deny_reason("create", project)
    supersede = gate.deny_reason("supersede", project)
    assert "approved-filing --category <CATEGORY>" in create and "--supersedes" not in create
    assert "approved-filing --category <CATEGORY>" in supersede and "--supersedes <record id>" in supersede
    # The proposal route stays for approvals that come later.
    assert create.index("approved-filing") < create.index("filing-proposal --input")


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


# ---------------------------------------------------------------------------
# A directory change earlier in the same command moves the target KB
# ---------------------------------------------------------------------------
# 2026-10-21: a session whose cwd had no `.kb-next` ran
# `cd "<vnext project>" && python .kb/kb.py supersede ...` and the gate let the
# write through. In the tiar experiment 23% of agent KB commands began with a
# `cd "<abs>" &&` prefix.


@pytest.fixture
def spaced(tmp_path: Path) -> tuple[Path, Path]:
    """A vNext project under a folder with a space, and a session folder beside it without `.kb-next`."""
    root = tmp_path / "my projects"
    outside = root / "elsewhere"
    outside.mkdir(parents=True)
    return make_project(root / "proj"), outside


def windows(path: Path) -> str:
    """The path as a Windows shell writes it, so the backslash form runs on every CI runner."""
    return str(path).replace("/", "\\")


@pytest.mark.parametrize(
    "template",
    [
        'cd "{posix}" && python .kb/kb.py supersede ATT-KB-0002 --title "x"',
        'cd "{posix}" && python .kb/kb.py create --category FATO --domain ops --title T --content C',
        'cd "{posix}" && python .kb/kb.py update KB-1 --tier WARM',
        'cd "{posix}" && python -B .kb/kb.py file --filing-type answer --category FATO',
        'cd "{posix}"; python .kb/kb.py create --category FATO',
        'cd "{windows}" && python .kb\\kb.py supersede KB-1 --content x',
        "cd '{windows}'; python .kb/kb.py create --category FATO",
        'cd -- "{posix}" && python .kb/kb.py create --category FATO',
        'CD "{windows}" && python .kb/kb.py create --category FATO',
        'pushd "{windows}" && python .kb/kb.py create --category FATO',
        'pushd "{posix}" > /dev/null && python .kb/kb.py create --category FATO',
        'pushd "{posix}" >/dev/null 2>&1 && python .kb/kb.py create --category FATO',
        'cd "{posix}" 2>/dev/null && python .kb/kb.py create --category FATO',
        'Push-Location "{windows}" *> $null; python .kb/kb.py create --category FATO',
        '(cd "{posix}" && python .kb/kb.py create --category FATO)',
        'Set-Location "{windows}"; python .kb/kb.py create --category FATO',
        'Set-Location -Path "{windows}"; python .kb\\kb.py update KB-1 --tags x',
        'sl "{windows}"; python .kb/kb.py create --category FATO',
        'git status && cd "{posix}" && python .kb/kb.py create --category FATO 2>&1 | tail -5',
        'cd "{posix}/.kb" && python kb.py create --category FATO',
    ],
)
def test_a_directory_change_before_the_write_moves_the_target(spaced: tuple[Path, Path], template: str) -> None:
    project, outside = spaced
    command = template.format(posix=project.as_posix(), windows=windows(project))

    reason = gate.decide(payload(command, outside))

    assert reason and "kb-wiki-vnext write gate" in reason


def test_a_relative_directory_change_resolves_from_where_the_shell_stands(spaced: tuple[Path, Path]) -> None:
    project, outside = spaced
    (project / "sub").mkdir()

    assert gate.decide(payload("cd sub && python ../.kb/kb.py create --category FATO", project))
    assert gate.decide(payload("cd ../proj && python .kb/kb.py create --category FATO", outside))
    assert gate.decide(payload("cd .. && cd proj && python .kb/kb.py create --category FATO", outside))


def test_a_subshell_and_popd_return_to_the_saved_directory(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    (vnext / "sub").mkdir()
    write = "python .kb/kb.py create --category FATO"

    assert gate.decide(payload(f'(cd "{classic.as_posix()}" && ls) && {write}', vnext))
    assert gate.decide(payload(f'echo $(cd "{classic.as_posix()}" && pwd); {write}', vnext))
    assert gate.decide(payload(f'cd "{vnext.as_posix()}" && pushd sub && popd && {write}', classic))
    assert gate.decide(payload(f'(cd "{vnext.as_posix()}" && ls) && {write}', classic)) is None


def test_a_directory_change_expands_the_home_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    make_project(home / "proj")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    assert gate.decide(payload("cd ~/proj && python .kb/kb.py create --category FATO", outside))


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash drive paths exist only on Windows")
def test_git_bash_drive_paths_are_followed(spaced: tuple[Path, Path]) -> None:
    project, outside = spaced
    drive, rest = project.as_posix().split(":", 1)
    msys = f"/{drive.lower()}{rest}"

    assert gate.decide(payload(f'cd "{msys}" && python .kb/kb.py create --category FATO', outside))
    assert gate.decide(payload(f'python "{msys}/.kb/kb.py" create --category FATO', outside))


def test_a_directory_change_into_a_classic_only_project_is_not_gated(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    command = f'cd "{classic.as_posix()}" && python .kb/kb.py create --category FATO'

    assert gate.decide(payload(command, vnext)) is None
    assert gate.decide(payload(command, tmp_path)) is None


@pytest.mark.parametrize("read", ["search create", "list --json", "get KB-1", "pending --json"])
def test_reads_after_a_directory_change_pass(spaced: tuple[Path, Path], read: str) -> None:
    project, outside = spaced

    assert gate.decide(payload(f'cd "{project.as_posix()}" && python .kb/kb.py {read}', outside)) is None


@pytest.mark.parametrize(
    "change",
    [
        "cd && ",
        "cd - && ",
        'cd "$PROJECT_DIR" && ',
        "cd ${{PROJECT_DIR}} && ",
        "cd missing; ",
        'pushd "{classic}" && popd && ',
        'Push-Location "{classic}"; Pop-Location; ',
    ],
)
def test_a_directory_the_gate_cannot_follow_falls_back_to_the_hook_cwd(tmp_path: Path, change: str) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    command = change.format(classic=classic.as_posix()) + "python .kb/kb.py create --category FATO"

    assert gate.decide(payload(command, vnext))


def test_the_hook_denies_a_write_behind_a_directory_change(spaced: tuple[Path, Path]) -> None:
    project, outside = spaced
    command = f'cd "{project.as_posix()}" && python .kb/kb.py supersede ATT-KB-0002 --title "x"'

    result = run_hook(payload(command, outside))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# Blocks and nested shells do not hide the write
# ---------------------------------------------------------------------------
# 2026-10-21 review of the directory fix: `{` and `}` did not end a command, so
# in `Push-Location "<project>"; try { python .kb/kb.py create } finally { ... }`
# the first word was `try` and the interpreter went unseen; bash `then`, `do`
# and `!` hid it the same way. The text a nested `bash -c`, `pwsh -Command` or
# `cmd /c` runs was one quoted word that the gate never parsed.

BLOCKED = [
    'Push-Location "{windows}"; try {{ python .kb/kb.py create --category FATO }} finally {{ Pop-Location }}',
    'Push-Location "{windows}"; try{{python .kb\\kb.py create --category FATO}}finally{{Pop-Location}}',
    'Set-Location "{windows}"; Get-ChildItem | ForEach-Object {{ python .kb/kb.py update KB-1 --tags x }}',
    'if (Test-Path "{windows}") {{ Set-Location "{windows}"; python .kb/kb.py create --category FATO }}',
    'cd "{posix}" && {{ python .kb/kb.py create --category FATO; }}',
    '{{ cd "{posix}"; }} && python .kb/kb.py create --category FATO',
    'if cd "{posix}"; then python .kb/kb.py create --category FATO; fi',
    'for f in a; do cd "{posix}" && python .kb/kb.py supersede KB-1 --content x; done',
    'cd "{posix}" && ! python .kb/kb.py create --category FATO',
]

NESTED = [
    "bash -c 'cd \"{posix}\" && python .kb/kb.py create --category FATO'",
    "bash -lc \"cd '{posix}' && python .kb/kb.py supersede KB-1 --content x\"",
    "sh -ec \"cd '{posix}'; python .kb/kb.py create --category FATO\"",
    "pwsh -NoProfile -Command \"Set-Location '{windows}'; python .kb/kb.py create --category FATO\"",
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -c \"Push-Location '{windows}'; "
    "try {{ python .kb\\kb.py create --category FATO }} finally {{ Pop-Location }}\"",
    "cmd /c 'cd /d \"{windows}\" && python .kb\\kb.py create --category FATO'",
    'cd "{posix}" && bash -c "python .kb/kb.py create --category FATO"',
    'cd "{posix}" && cmd /C python .kb\\kb.py create --category FATO',
    'cd "{posix}" && pwsh -c python .kb/kb.py update KB-1 --tags x',
    "cd \"{posix}\" && bash -c \"pwsh -Command 'python .kb/kb.py create --category FATO'\"",
]


@pytest.mark.parametrize("template", BLOCKED + NESTED)
def test_a_block_or_a_nested_shell_does_not_hide_the_write(spaced: tuple[Path, Path], template: str) -> None:
    project, outside = spaced
    command = template.format(posix=project.as_posix(), windows=windows(project))

    reason = gate.decide(payload(command, outside))

    assert reason and "kb-wiki-vnext write gate" in reason


@pytest.mark.parametrize(
    "command",
    [
        "if true; then python .kb/kb.py create --category FATO; fi",
        "while true; do python .kb/kb.py update KB-1 --tier WARM; break; done",
        "bash -c 'python .kb/kb.py create --category FATO'",
        "cmd.exe /S /C \"python .kb\\kb.py create --category FATO\"",
    ],
)
def test_keywords_and_nested_shells_in_the_project_folder_are_denied(project: Path, command: str) -> None:
    assert gate.decide(payload(command, project))


def test_quoted_braces_stay_inside_their_word(project: Path) -> None:
    assert gate.decide(payload("python .kb/kb.py create --category FATO --content '{\"k\": \"v\"}'", project))
    assert gate.decide(payload("python .kb/kb.py search '{\"a\": 1}'", project)) is None
    assert gate.decide(payload('git commit -m "wrap { python .kb/kb.py create } in a block"', project)) is None


def test_nested_shells_keep_reads_and_classic_projects_open(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    write = "python .kb/kb.py create --category FATO"

    assert gate.decide(payload('bash -c "python .kb/kb.py search create"', vnext)) is None
    assert gate.decide(payload(f"bash -c 'cd \"{classic.as_posix()}\" && {write}'", vnext)) is None
    assert gate.decide(payload(f"pwsh -Command \"Set-Location '{windows(classic)}'; {write}\"", vnext)) is None
    assert gate.decide(payload(f"git commit -m \"bash -c '{write}'\"", vnext)) is None
    assert gate.decide(payload(f"echo 'pwsh -Command {write}'", vnext)) is None


def test_a_nested_shell_does_not_move_the_outer_shell(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    write = "python .kb/kb.py create --category FATO"

    assert gate.decide(payload(f"bash -c \"cd '{classic.as_posix()}'\" && {write}", vnext))
    assert gate.decide(payload(f"pwsh -Command \"Set-Location '{windows(vnext)}'\"; {write}", classic)) is None


def test_a_pop_inside_finally_returns_before_the_next_command(tmp_path: Path) -> None:
    vnext = make_project(tmp_path / "vnext")
    classic = make_project(tmp_path / "classic", vnext=False)
    block = 'Push-Location "{}"; try {{ ls }} finally {{ Pop-Location }}; python .kb/kb.py create --category FATO'

    assert gate.decide(payload(block.format(windows(classic)), vnext))
    assert gate.decide(payload(block.format(windows(vnext)), classic)) is None


@pytest.mark.parametrize("template", [BLOCKED[0], NESTED[0]])
def test_the_hook_denies_a_write_inside_a_block_or_a_nested_shell(spaced: tuple[Path, Path], template: str) -> None:
    project, outside = spaced
    command = template.format(posix=project.as_posix(), windows=windows(project))

    result = run_hook(payload(command, outside, "PowerShell"))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


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
    draft = {k: judgment["record_draft"][k] for k in ("title", "content")}
    candidate.write_text(json.dumps({**draft, "source": "notes.md"}), encoding="utf-8")
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
