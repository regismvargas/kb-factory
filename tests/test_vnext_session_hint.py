"""SessionStart hint: the session-start command it prints must run, and runtime skew is named.

The plugin hook runs `session-hint` from the plugin cache, while the agent runs
whatever command the hint prints. A workspace without `.kb-next/runtime/` gets
this file's path with `--project-root`; a workspace whose vendored runtime
differs in version from the plugin gets one line naming both and the fix. The
hook must stay silent outside vNext workspaces, never fail, and write nothing.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
MASTER_RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
TEMPLATE = REPO / "core" / "templates" / "kb"
VERSION_LINE = re.compile(rb'^RUNTIME_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
PLUGIN_VERSION = VERSION_LINE.search(MASTER_RUNTIME.read_bytes()).group(1).decode()
LOCAL_COMMAND = "`python .kb-next/runtime/kb_next.py session-start --json`"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


def hint(project: Path) -> subprocess.CompletedProcess[str]:
    # The hook runs from the session directory with `--project-root .`.
    return run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "session-hint"], project, check=False)


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def kb_next():
    spec = importlib.util.spec_from_file_location("session_hint_kb_next", MASTER_RUNTIME)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("hint")
    shutil.copytree(TEMPLATE, project / ".kb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    run([sys.executable, str(project / ".kb" / "kb.py"), "init", "--slug", "hint"], project)
    run([sys.executable, str(MASTER_RUNTIME), "--project-root", str(project),
         "activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json"], project)
    assert not (project / ".kb-next" / "runtime" / "kb_next.py").exists()
    return project


def local_hint(kb_next, workspace: Path, project: Path, runtime: bytes) -> str:
    """Hint text for a workspace that vendors `runtime` as `.kb-next/runtime/kb_next.py`."""
    (project / ".kb-next" / "runtime").mkdir(parents=True)
    shutil.copy2(workspace / ".kb-next" / "kb-next.config.json", project / ".kb-next" / "kb-next.config.json")
    (project / ".kb-next" / "runtime" / "kb_next.py").write_bytes(runtime)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert kb_next.main(["--project-root", str(project), "session-hint"]) == 0
    return out.getvalue()


def versioned(version: str) -> bytes:
    return VERSION_LINE.sub(f'RUNTIME_VERSION = "{version}"'.encode(), MASTER_RUNTIME.read_bytes(), count=1)


def skew_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Runtime skew")]


def test_hint_is_silent_outside_vnext_workspaces(tmp_path: Path) -> None:
    proc = hint(tmp_path)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


def test_hint_without_a_local_runtime_prints_a_command_that_runs(tmp_path: Path, workspace: Path) -> None:
    project = tmp_path / "copy"
    shutil.copytree(workspace, project)
    before = tree_state(project)
    proc = hint(project)
    assert proc.returncode == 0
    assert tree_state(project) == before, "session-hint must not write"
    assert len(proc.stdout) < 2_500
    assert LOCAL_COMMAND not in proc.stdout
    assert skew_lines(proc.stdout) == []
    commands = [span for span in re.findall(r"`([^`]+)`", proc.stdout) if " session-start " in span]
    assert len(commands) == 1
    assert MASTER_RUNTIME.resolve().as_posix() in commands[0]
    assert f'--project-root "{project.resolve().as_posix()}"' in commands[0]
    argv = shlex.split(commands[0])
    assert argv[0] == "python"
    result = run([sys.executable, *argv[1:]], project)
    assert '"event": "session-start"' in result.stdout


def test_hint_names_the_local_runtime_when_versions_match(tmp_path: Path, kb_next, workspace: Path) -> None:
    text = local_hint(kb_next, workspace, tmp_path, MASTER_RUNTIME.read_bytes())
    assert LOCAL_COMMAND in text
    assert "--project-root" not in text
    assert skew_lines(text) == []


def test_hint_reports_an_older_local_runtime(tmp_path: Path, kb_next, workspace: Path) -> None:
    text = local_hint(kb_next, workspace, tmp_path, versioned("0.0.1"))
    assert LOCAL_COMMAND in text
    skew = skew_lines(text)
    assert len(skew) == 1
    assert f"is 0.0.1, the kb-wiki-vnext plugin is {PLUGIN_VERSION}." in skew[0]
    assert "current main" in skew[0] and "existing-project-upgrade-vnext" in skew[0]


def test_hint_reports_a_newer_local_runtime_without_offering_a_downgrade(
    tmp_path: Path, kb_next, workspace: Path
) -> None:
    skew = skew_lines(local_hint(kb_next, workspace, tmp_path, versioned("99.0.0")))
    assert len(skew) == 1
    assert f"is 99.0.0, the kb-wiki-vnext plugin is {PLUGIN_VERSION}." in skew[0]
    assert "Update the plugin" in skew[0]
    assert "existing-project-upgrade-vnext" not in skew[0]


def test_hint_treats_a_non_numeric_local_version_as_unknown_order(
    tmp_path: Path, kb_next, workspace: Path
) -> None:
    # Digit runs would read 99.0.0-rc.1 as (99, 0, 0, 1), newer than the plugin.
    skew = skew_lines(local_hint(kb_next, workspace, tmp_path, versioned("99.0.0-rc.1")))
    assert len(skew) == 1
    assert f"is 99.0.0-rc.1, the kb-wiki-vnext plugin is {PLUGIN_VERSION}." in skew[0]
    assert "Update the plugin" not in skew[0]
    assert "existing-project-upgrade-vnext" in skew[0]


def test_hint_survives_an_unreadable_local_runtime(tmp_path: Path, kb_next, workspace: Path) -> None:
    text = local_hint(kb_next, workspace, tmp_path, b"\xff\xfe not a runtime \xff")
    assert LOCAL_COMMAND in text
    skew = skew_lines(text)
    assert len(skew) == 1
    assert f"is unknown, the kb-wiki-vnext plugin is {PLUGIN_VERSION}." in skew[0]


# The command sheet: one exact command per frequent task. Every placeholder
# stands for one value; a choice placeholder lists the accepted values.
SHEET_VALUES = {
    "<terms>": "scope",
    "<file>": "notes.md",
    "<domain>": "research",
    "<title>": "Finding",
    "<content>": "Finding text.",
    "<0-1>": "0.9",
    "<source-id>": "SRC-1",
    "<record-id>": "REC-1",
    "<who approved, in their words>": "User approved in chat: ok",
    "<approver>": "sponsor",
}


def fill(command: str) -> str:
    def value(match: re.Match) -> str:
        placeholder = match.group(0)
        if "|" in placeholder:
            return placeholder[1:-1].split("|")[0]
        assert placeholder in SHEET_VALUES, f"unknown placeholder {placeholder}"
        return SHEET_VALUES[placeholder]

    return re.sub(r"<[^<>]+>", value, command)


def sheet_commands(text: str) -> dict[str, str]:
    """The sheet's commands keyed by subcommand, `--supersedes` folded into a filing."""
    commands: dict[str, str] = {}
    text = text[text.find("Commands"):] if "Commands" in text else ""
    for span in re.findall(r"`(python [^`]+)`", text):
        argv = shlex.split(span)
        name = next(arg for arg in argv[2:] if not arg.startswith("-") and "/" not in arg and not arg.startswith('"'))
        if name != "session-start":
            commands[name] = span
    supersede = re.search(r"`(--supersedes [^`]+)`", text)
    if supersede and "approved-filing" in commands:
        commands["approved-filing --supersedes"] = f"{commands['approved-filing']} {supersede.group(1)}"
    return commands


def test_hint_command_sheet_parses(kb_next, workspace: Path) -> None:
    from collections import defaultdict

    spec = importlib.util.spec_from_file_location("session_hint_classic_cli", TEMPLATE / "runtime" / "cli.py")
    classic_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classic_cli)
    parsers = {"kb_next.py": kb_next.build_parser(), "kb.py": classic_cli.build_parser(defaultdict(lambda: None))}
    text = hint(workspace).stdout
    commands = sheet_commands(text)
    assert set(commands) == {"lookup", "ingest", "approved-filing", "approved-filing --supersedes", "lifecycle"}
    for name, command in commands.items():
        argv = shlex.split(fill(command))[1:]  # drop "python"
        script = Path(argv[0]).name
        args = argv[1:]
        if args[:1] == ["--project-root"]:
            args = args[2:]
        try:
            parsers[script].parse_args(args)
        except SystemExit:
            pytest.fail(f"{name}: {command!r} does not parse")
    assert "--supersedes" in commands["approved-filing --supersedes"]
