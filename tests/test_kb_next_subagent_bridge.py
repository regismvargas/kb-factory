"""Subagent memory bridge: the SubagentStart hint and the documented commands.

Briefs carry KB records picked by the main agent (skill rule); the plugin's
SubagentStart hook adds the contract (no KB writes, a `KB candidates` section
in the report) and a lookup command the subagent can run. The hook must stay
silent outside vNext workspaces, never fail, and write nothing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
MASTER_RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
PLUGIN = REPO / "plugins" / "kb-wiki-vnext"
TEMPLATE = REPO / "core" / "templates" / "kb"
HOOK_CONTEXT_CAP = 10_000  # Claude Code truncates hook context above this size.


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


def vnext(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(MASTER_RUNTIME), "--project-root", str(project), *args], project, check)


def hint(project: Path) -> subprocess.CompletedProcess[str]:
    # The hook runs from the session directory with `--project-root .`.
    return run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "subagent-hint"], project, check=False)


def context_of(proc: subprocess.CompletedProcess[str]) -> str:
    output = json.loads(proc.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SubagentStart"
    return output["additionalContext"]


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def parser():
    spec = importlib.util.spec_from_file_location("subagent_bridge_kb_next", MASTER_RUNTIME)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_parser()


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("bridge")
    shutil.copytree(TEMPLATE, project / ".kb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    kb = [sys.executable, str(project / ".kb" / "kb.py")]
    run([*kb, "init", "--slug", "bridge"], project)
    run(
        [*kb, "create", "--category", "DECISAO", "--domain", "ops", "--title", "Subagents never write the KB",
         "--content", "Only the main session files records.", "--no-auto-lifecycle", "--json"],
        project,
    )
    vnext(project, "activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json")
    return project


def test_hint_is_silent_outside_vnext_workspaces(tmp_path: Path) -> None:
    proc = hint(tmp_path)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


def test_hint_is_silent_on_an_unreadable_config(tmp_path: Path) -> None:
    (tmp_path / ".kb-next").mkdir()
    (tmp_path / ".kb-next" / "kb-next.config.json").write_text("{not json", encoding="utf-8")
    proc = hint(tmp_path)
    assert (proc.returncode, proc.stdout) == (0, "")


def test_hint_gives_the_contract_and_a_lookup_that_runs(workspace: Path) -> None:
    before = tree_state(workspace)
    proc = hint(workspace)
    assert proc.returncode == 0
    assert tree_state(workspace) == before, "subagent-hint must not write"
    text = context_of(proc)
    assert len(text) < HOOK_CONTEXT_CAP // 4
    for phrase in ("KB candidates", "only writer", "filing-proposal", "proposal-apply", "source"):
        assert phrase in text
    commands = [span for span in re.findall(r"`([^`]+)`", text) if " lookup " in span]
    assert len(commands) == 1
    # Without a bootstrapped local runtime the hint names this runtime and the root.
    assert MASTER_RUNTIME.resolve().as_posix() in commands[0]
    argv = shlex.split(commands[0].replace("<words>", "subagents write"))
    assert argv[0] == "python"
    result = json.loads(run([sys.executable, *argv[1:]], workspace).stdout)
    assert result["event"] == "lookup"
    assert [row["title"] for row in result["results"]] == ["Subagents never write the KB"]


def test_hint_names_the_local_runtime_once_bootstrapped(tmp_path: Path, workspace: Path) -> None:
    project = tmp_path / "local"
    shutil.copytree(workspace, project)
    vnext(project, "bootstrap", "--json")
    text = context_of(hint(project))
    assert '`python .kb-next/runtime/kb_next.py lookup --facet status --query "<words>" --json`' in text
    assert "--project-root" not in text


def test_hint_drops_the_lookup_without_a_classic_database(tmp_path: Path, workspace: Path) -> None:
    (tmp_path / ".kb-next").mkdir()
    shutil.copy2(workspace / ".kb-next" / "kb-next.config.json", tmp_path / ".kb-next" / "kb-next.config.json")
    text = context_of(hint(tmp_path))
    assert "KB candidates" in text
    assert " lookup " not in text


def test_plugin_registers_the_subagent_hook() -> None:
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    (group,) = hooks["SubagentStart"]
    assert group["matcher"] == "*"
    (entry,) = group["hooks"]
    assert entry["type"] == "command"
    assert entry["command"] == 'python "${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py" --project-root . subagent-hint'
    # A PreToolUse hook on Agent would see the brief but adds records picked by a
    # few task words, and could not tell isolated briefs apart; none is shipped.
    # The only PreToolUse hook is the shell write gate.
    assert set(hooks) == {"PreToolUse", "SessionStart", "SubagentStart"}
    assert [group["matcher"] for group in hooks["PreToolUse"]] == ["Bash|PowerShell"]


def documented_runtime_commands() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    gate = REPO / "plugins" / "session-gate"
    paths = [PLUGIN / "AGENTS.md", PLUGIN / "README.md", *sorted((PLUGIN / "skills").rglob("SKILL.md")),
             *sorted((PLUGIN / "commands").glob("*.md")), gate / "README.md",
             *sorted((gate / "skills").rglob("SKILL.md")), *sorted((gate / "commands").glob("*.md"))]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for span in re.findall(r"`(python [^`]+)`", text):
            command = " ".join(span.split())
            if "kb_next.py" in command or "<resolved-runtime-path>" in command:
                found.append((path.relative_to(REPO).as_posix(), command))
    return found


def test_documented_runtime_commands_are_complete() -> None:
    commands = documented_runtime_commands()
    assert any(" filing-proposal " in c for _, c in commands)
    assert any(label.startswith("plugins/session-gate/") and " wiki-draft-status " in c for label, c in commands)
    vnext_parser = parser()
    with pytest.raises(SystemExit):  # the check itself rejects a missing required flag
        vnext_parser.parse_args(["lookup", "--query", "x", "--json"])
    problems: list[str] = []
    for label, command in commands:
        # A placeholder stands for one value; a missing flag still fails.
        argv = shlex.split(re.sub(r"<[^<>]+>", "x", command))[2:]  # drop "python <runtime>"
        try:
            vnext_parser.parse_args(argv)
        except SystemExit:
            problems.append(f"{label}: incomplete or invalid command {command!r}")
    assert problems == []
