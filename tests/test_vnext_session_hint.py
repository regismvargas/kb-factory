"""SessionStart hint: it is the session start, its commands run, and runtime skew is named.

The plugin hook runs `session-hint` from the plugin cache, while the agent runs
whatever command the hint prints. The text carries what `session-start` and
`.kb-next/memory/NOW.md` gave an agent (activation mode, wiki state, classic
NOW status, on-demand reads), so a session begins without a call. A workspace
without `.kb-next/runtime/` gets this file's path with `--project-root`; a
workspace whose vendored runtime differs in version from the plugin gets one
line naming both and the fix. The hook must stay silent outside vNext
workspaces, never fail, and write nothing but the `session-start` read
telemetry under `.kb-next/telemetry/`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
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
TEMPLATE = REPO / "core" / "templates" / "kb"
VERSION_LINE = re.compile(rb'^RUNTIME_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
PLUGIN_VERSION = VERSION_LINE.search(MASTER_RUNTIME.read_bytes()).group(1).decode()
LOCAL_COMMAND = "`python .kb-next/runtime/kb_next.py lookup --facet"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


def hint(project: Path) -> subprocess.CompletedProcess[str]:
    # The hook runs from the session directory with `--project-root .`.
    return run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "session-hint"], project, check=False)


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    """Files outside the read telemetry, SQLite's -shm/-wal bookkeeping aside."""
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.relative_to(root).as_posix().startswith(".kb-next/telemetry/")
        and not path.name.endswith(("-shm", "-wal"))
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
    assert tree_state(project) == before, "session-hint writes only its read telemetry"
    assert len(proc.stdout) < 2_500
    assert LOCAL_COMMAND not in proc.stdout
    assert skew_lines(proc.stdout) == []
    assert not [span for span in re.findall(r"`([^`]+)`", proc.stdout) if " session-start " in span]
    commands = [span for span in re.findall(r"`([^`]+)`", proc.stdout) if " lookup " in span]
    assert len(commands) == 1
    assert MASTER_RUNTIME.resolve().as_posix() in commands[0]
    assert f'--project-root "{project.resolve().as_posix()}"' in commands[0]
    argv = shlex.split(fill(commands[0]))
    assert argv[0] == "python"
    result = run([sys.executable, *argv[1:]], project)
    assert '"results"' in result.stdout


def test_hint_is_the_session_start(tmp_path: Path, workspace: Path) -> None:
    """The hint carries what session-start and NOW.md gave, and logs the session start."""
    project = tmp_path / "copy"
    shutil.copytree(workspace, project)
    kb_cli = project / ".kb" / "kb.py"
    run([sys.executable, str(kb_cli), "lifecycle", "session-end", "--json"], project)  # classic NOW export
    text = hint(project).stdout
    start = json.loads(run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "session-start", "--json"],
                           project).stdout)
    lines = text.splitlines()
    assert lines[0].startswith("KB/Wiki vNext workspace detected.")
    assert "replaces `session-start` and `.kb-next/memory/NOW.md`" in lines[0]
    assert f"- Mode `{start['activation_mode']}`." in text
    assert re.search(r"classic NOW of `[0-9T:-]+Z`: Project: `hint`; Open pendencias: `0`\.", text)
    assert "- Wiki: off (KB alone)." in text
    on_demand = next(line for line in lines if line.startswith("- On demand only:"))
    for read in ("`lookup`", "`NOW.md`", "`HOT.md`", "`INDEX.md`", "`.kb/memory/`"):
        assert read in on_demand
    for reason in start["historical_artifact_allowed_reasons"]:
        assert reason.replace("_", " ") in on_demand
    assert "curation runs weekly, not here" in text
    events = [json.loads(line) for line in
              (project / ".kb-next" / "telemetry" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    hook_events = [event for event in events if event.get("details", {}).get("via") == "session-hint"]
    assert len(hook_events) == 1 and hook_events[0]["event"] == "session-start"
    assert hook_events[0]["details"]["wiki_status"] == start["wiki"]["status"]


def test_session_commands_recognize_the_hint_by_its_own_phrase(workspace: Path) -> None:
    """Older hints asked for `vnext-session-start`; only the new one says it replaces it."""
    assert "replaces `session-start`" in hint(workspace).stdout.splitlines()[0]
    starts = [
        "plugins/kb-wiki-vnext/commands/vnext-session-start.md",
        "plugins/kb-wiki-vnext/skills/kb-wiki-vnext/SKILL.md",
        "plugins/kb-wiki-vnext/AGENTS.md",
        "plugins/kb-wiki-vnext/README.md",
        "plugins/session-gate/commands/gate-session-start.md",
        "plugins/session-gate/skills/session-gate/SKILL.md",
        "plugins/session-gate/README.md",
    ]
    for relative in [*starts, "plugins/session-gate/commands/gate-session-end.md"]:
        text = " ".join((REPO / relative).read_text(encoding="utf-8").split())
        assert "says it replaces `session-start`" in text, relative
        # A start that skips NOW must still read the curated one the hint names.
        assert relative not in starts or "only when that text asks for it" in text, relative


def with_project_copy(tmp_path: Path, workspace: Path) -> Path:
    project = tmp_path / "copy"
    shutil.copytree(workspace, project)
    return project


def test_hint_sends_the_agent_to_a_curated_now(tmp_path: Path, workspace: Path) -> None:
    """write_now preserves a NOW the team wrote; the hint must not tell the agent to skip it."""
    project = with_project_copy(tmp_path, workspace)
    now = project / ".kb-next" / "memory" / "NOW.md"
    first = hint(project).stdout.splitlines()[0]
    assert "replaces `session-start` and `.kb-next/memory/NOW.md`" in first  # generated template

    now.write_text("# Team NOW\n\nFocus this week: the pricing model.\n", encoding="utf-8")
    first = hint(project).stdout.splitlines()[0]
    assert "replaces `session-start`" in first
    assert "`.kb-next/memory/NOW.md` was written by the team: read it before you begin" in first

    now.write_bytes(b"# KB/Wiki vNext NOW\n" + b"- x\n" * 20_000)  # too large for a template
    assert "read it before you begin" in hint(project).stdout.splitlines()[0]

    now.unlink()
    assert "replaces `session-start` and `.kb-next/memory/NOW.md`" in hint(project).stdout.splitlines()[0]


@pytest.mark.parametrize("heading", [False, True])
def test_hint_bounds_the_classic_now_it_quotes(tmp_path: Path, workspace: Path, heading: bool) -> None:
    project = with_project_copy(tmp_path, workspace)
    body = "# hint NOW\n\n- Project: `hint`\n- Note: " + "x" * 1_000_000 + "\n" + "- More: y\n" * 500
    if heading:
        body += "\n## Where We Are\n- a\n"
    (project / ".kb" / "memory").mkdir(parents=True, exist_ok=True)
    (project / ".kb" / "memory" / "NOW.md").write_text(body, encoding="utf-8")
    text = hint(project).stdout
    assert "Project: `hint`" in text
    assert "[truncated]" in text
    assert len(text) < 3_000


@pytest.mark.parametrize("config", [None, "{not json"])
def test_hint_names_a_missing_classic_config_instead_of_an_active_wiki(
    tmp_path: Path, workspace: Path, config: str | None
) -> None:
    project = with_project_copy(tmp_path, workspace)
    vnext_config = project / ".kb-next" / "kb-next.config.json"
    data = json.loads(vnext_config.read_text(encoding="utf-8"))
    data["wiki"]["enabled"] = True
    vnext_config.write_text(json.dumps(data), encoding="utf-8")
    classic_config = project / ".kb" / "kb.config.json"
    if config is None:
        classic_config.unlink()
    else:
        classic_config.write_text(config, encoding="utf-8")
    text = hint(project).stdout
    assert "Wiki: active" not in text
    assert "`.kb/kb.config.json` is missing or unreadable" in text
    assert "existing-project-diagnose" in text
    assert "wiki-draft-status" not in text


def iso_days_ago(days: float) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log_event(path: Path, event: str, days_ago: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"event": event, "happened_at": iso_days_ago(days_ago), "details": {}}) + "\n")


def overdue_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("Curation overdue")]


def test_hint_flags_curation_older_than_a_week(tmp_path: Path, workspace: Path) -> None:
    """One line when the last semantic-hygiene check is over 7 days old; none while it is current."""
    project = with_project_copy(tmp_path, workspace)
    telemetry = project / ".kb-next" / "telemetry" / "events.jsonl"
    oplog = project / ".kb-next" / "operations.jsonl"

    # No record at all, project activated today: a new project gets a week before the first run.
    assert overdue_lines(hint(project).stdout) == []

    # No record at all, project activated a month ago.
    config_file = project / ".kb-next" / "kb-next.config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["activation"]["decided_at"] = iso_days_ago(30)
    config_file.write_text(json.dumps(config), encoding="utf-8")
    (line,) = overdue_lines(hint(project).stdout)
    assert "no `semantic-hygiene` check is recorded" in line
    assert "weekly maintenance run" in line and "semantic-hygiene --json" in line

    # Overdue: the last check ran ten days ago.
    log_event(telemetry, "semantic-hygiene-check", 10)
    (line,) = overdue_lines(hint(project).stdout)
    assert "ran 10 days ago" in line

    # A write pass recorded in the versioned oplog also counts as curation.
    log_event(oplog, "semantic-hygiene", 3)
    assert overdue_lines(hint(project).stdout) == []

    # Fresh: a check two days ago.
    oplog_lines = oplog.read_text(encoding="utf-8").splitlines()[:-1]
    oplog.write_text("".join(f"{line}\n" for line in oplog_lines), encoding="utf-8")
    assert len(overdue_lines(hint(project).stdout)) == 1
    log_event(telemetry, "semantic-hygiene-check", 2)
    assert overdue_lines(hint(project).stdout) == []


def test_a_detection_pass_records_the_check_the_hint_reads(tmp_path: Path, workspace: Path) -> None:
    project = with_project_copy(tmp_path, workspace)
    config_file = project / ".kb-next" / "kb-next.config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["activation"]["decided_at"] = iso_days_ago(30)
    config_file.write_text(json.dumps(config), encoding="utf-8")
    assert len(overdue_lines(hint(project).stdout)) == 1

    run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "semantic-hygiene", "--json"], project)
    events = [json.loads(line) for line in
              (project / ".kb-next" / "telemetry" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events].count("semantic-hygiene-check") == 1
    assert overdue_lines(hint(project).stdout) == []


def test_a_worktree_reads_the_curation_of_its_main_checkout(
    kb_next, tmp_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The weekly run curates the main checkout; a linked worktree has its own empty telemetry."""
    main = tmp_path / "main"
    (main / ".kb").mkdir(parents=True)
    (main / ".kb" / "kb.db").write_bytes(b"")  # the shared KB the worktree resolves to
    log_event(main / ".kb-next" / "telemetry" / "events.jsonl", "semantic-hygiene-check", 1)
    worktree = with_project_copy(tmp_path, workspace)
    monkeypatch.setattr(kb_next, "linked_worktree_main_root", lambda root: main)
    monkeypatch.delenv("KB_FACTORY_WORKTREE_SCOPE", raising=False)
    config = {"activation": {"decided_at": iso_days_ago(30)}}
    assert kb_next.classic_kb_root(worktree) == main / ".kb"
    assert kb_next.curation_overdue_line(worktree, config, "python kb_next.py") is None


@pytest.mark.parametrize("isolation", ["env", "config"])
def test_a_worktree_with_its_own_kb_ignores_the_main_checkout_curation(
    kb_next, tmp_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch, isolation: str
) -> None:
    """A worktree scoped local keeps its own KB, so a check on main says nothing about it."""
    main = tmp_path / "main"
    (main / ".kb").mkdir(parents=True)
    (main / ".kb" / "kb.db").write_bytes(b"")
    log_event(main / ".kb-next" / "telemetry" / "events.jsonl", "semantic-hygiene-check", 1)
    worktree = with_project_copy(tmp_path, workspace)
    monkeypatch.setattr(kb_next, "linked_worktree_main_root", lambda root: main)
    monkeypatch.delenv("KB_FACTORY_WORKTREE_SCOPE", raising=False)
    if isolation == "env":
        monkeypatch.setenv("KB_FACTORY_WORKTREE_SCOPE", "local")
    else:
        classic_config = worktree / ".kb" / "kb.config.json"
        data = json.loads(classic_config.read_text(encoding="utf-8"))
        data["storage"] = {**(data.get("storage") or {}), "worktree_scope": "local"}
        classic_config.write_text(json.dumps(data), encoding="utf-8")
    config = {"activation": {"decided_at": iso_days_ago(30)}}
    assert kb_next.classic_kb_root(worktree) == worktree / ".kb"
    line = kb_next.curation_overdue_line(worktree, config, "python kb_next.py")
    assert line is not None and "no `semantic-hygiene` check is recorded" in line


def test_the_last_check_survives_two_telemetry_rotations(kb_next, tmp_path: Path, workspace: Path) -> None:
    """Telemetry keeps one previous generation; a busy week must not erase a clean check."""
    project = with_project_copy(tmp_path, workspace)
    config_file = project / ".kb-next" / "kb-next.config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["activation"]["decided_at"] = iso_days_ago(30)
    config_file.write_text(json.dumps(config), encoding="utf-8")
    run([sys.executable, str(MASTER_RUNTIME), "--project-root", ".", "semantic-hygiene", "--json"], project)
    assert overdue_lines(hint(project).stdout) == []

    events = project / ".kb-next" / "telemetry" / "events.jsonl"
    filler = json.dumps({"event": "lookup", "happened_at": iso_days_ago(0), "details": {"q": "x" * 200}}) + "\n"
    for _ in range(2):
        with events.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(filler * (kb_next.TELEMETRY_MAX_BYTES // len(filler) + 1))
        kb_next.append_telemetry(project, "lookup", {})  # rotates the full file
    logged = events.read_text(encoding="utf-8") + events.with_name("events.1.jsonl").read_text(encoding="utf-8")
    assert "semantic-hygiene-check" not in logged  # both generations rotated past the check
    assert overdue_lines(hint(project).stdout) == []


def context(kb_next, root: Path, wiki: dict, *, mode: str = "kb_wiki") -> str:
    config = {"activation": {"sponsor_decision": mode}}
    wiki = {"vnext_wiki_enabled": mode == "kb_wiki", "classic_wiki_enabled": True, "hint": None, **wiki}
    return "\n".join(kb_next.session_context_lines(root, config, wiki, kb_next.hint_wiki_active(wiki)))


def test_hint_states_each_wiki_state(kb_next, workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counts = {"topics": 3, "needs_synthesis": 2, "needs_review": 0, "stale": 1, "current": 0}
    monkeypatch.setattr(kb_next, "build_wiki_draft_status", lambda root, config: {"counts": counts})
    active = context(kb_next, workspace, {"status": "aligned"})
    assert "- Wiki: active;" in active
    assert "`2` to synthesize, `0` to review, `1` stale of `3` topics" in active
    assert "vnext-wiki-drafts command, do not start it unprompted" in active

    counts.update(needs_synthesis=0, stale=0, current=3)
    assert "vnext-wiki-drafts" not in context(kb_next, workspace, {"status": "aligned"})

    dormant = context(kb_next, workspace, {"status": "dormant",
                                           "dormant": {"min_sourced_records": 10, "sourced_records": 4}})
    assert "- Wiki: dormant until `10` active records cite a registered source (now `4`)" in dormant
    assert "Drafts" not in dormant and "vnext-wiki-drafts" not in dormant

    off = context(kb_next, workspace, {"status": "classic_wiki_off", "classic_wiki_enabled": False})
    assert "classic wiki is off" in off and "existing-project-configure-vnext" in off

    alone = context(kb_next, workspace, {"status": "classic_wiki_independent"}, mode="kb_alone")
    assert "- Wiki: off (KB alone); the classic wiki runs on its own." in alone


def test_hint_names_the_main_checkout_classic_kb(kb_next, tmp_path: Path, workspace: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """In a linked worktree the classic memory files the agent may open live in the main checkout."""
    main = tmp_path / "main"
    (main / ".kb" / "memory").mkdir(parents=True)
    (main / ".kb" / "memory" / "NOW.md").write_text(
        "# main NOW\n\n- Project: `main`\n- Generated: `x`\n- Open pendencias: `2`\n\n## Where We Are\n- a\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kb_next, "classic_kb_root", lambda root: main / ".kb")
    monkeypatch.setattr(kb_next, "build_wiki_draft_status", lambda root, config: {"counts": None})
    text = context(kb_next, workspace, {"status": "aligned"})
    assert f"(main checkout `{main.as_posix()}`)" in text
    assert f"`{(main / '.kb' / 'memory').as_posix()}/`" in text
    assert f"pages in `{(main / '.kb' / 'wiki' / 'live').as_posix()}`" in text
    assert "Project: `main`; Open pendencias: `2`" in text


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
    # With an active wiki the close line adds the draft check on the same runtime.
    wiki_sheet = "\n".join(kb_next.command_sheet("python .kb-next/runtime/kb_next.py", True))
    commands["wiki-draft-status"] = sheet_commands(wiki_sheet)["wiki-draft-status"]
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
