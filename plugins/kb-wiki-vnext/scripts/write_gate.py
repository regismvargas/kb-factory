"""PreToolUse write gate for KB/Wiki vNext workspaces (kb-wiki-vnext plugin).

In a project with `.kb-next/kb-next.config.json`, an agent shell command that
runs the classic `kb.py create`, `file`, `supersede` or `update` is denied with
the governed path: `filing-proposal`, then `proposal-apply` once the approver
says yes. `proposal-apply` runs the classic CLI in its own subprocess, which
never passes through this hook. Classic-only projects are not gated, because
there the direct write is the only path. A relative `kb.py` resolves against
the folder the shell stands in: the hook's cwd, moved by an earlier `cd`,
`pushd` or `Set-Location` in the same command that names one literal folder,
so `cd "<project>" && python .kb/kb.py create` is gated too. Braces end a
command, so a write inside `try { ... }` or `{ ...; }` is seen, and the text a
nested `bash -c`, `pwsh -Command` or `cmd /c` runs is parsed from the same
folder.

The hook fires on every Bash and PowerShell call, so it is a small stdlib
script and returns before any parsing when the command does not mention
`kb.py`. Anything unexpected fails open: the gate steers agents, it does not
authenticate them. Owners can turn it off with `"write_gate": {"enabled":
false}` in the vNext config.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

GATED_SUBCOMMANDS = ("create", "file", "supersede", "update")
SEPARATORS = ";&|(){}\n"
INTERPRETER = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py|pypy3?)(?:\.exe)?$", re.IGNORECASE)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
RESERVED_WORDS = {"!", "if", "then", "elif", "else", "do", "while", "until"}
# (shell, the flag before the text it runs): POSIX `-c` may be combined, as in `-lc`.
SCRIPT_FLAGS = (
    (re.compile(r"^(?:bash|sh|zsh|dash|ksh)(?:\.exe)?$", re.IGNORECASE), re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")),
    (re.compile(r"^(?:pwsh|powershell)(?:\.exe)?$", re.IGNORECASE), re.compile(r"^-c(?:ommand)?$", re.IGNORECASE)),
    (re.compile(r"^cmd(?:\.exe)?$", re.IGNORECASE), re.compile(r"^/[ck]$", re.IGNORECASE)),
)
CHANGE_DIRECTORY = {"cd", "chdir", "pushd", "push-location", "set-location", "sl"}
PUSH_DIRECTORY = {"pushd", "push-location"}
RESTORE_DIRECTORY = {"popd", "pop-location"}
REDIRECTION = re.compile(r"^[\d*]*[<>]")
MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?:/|$)")
RUNTIME_REL = Path(".kb-next") / "runtime" / "kb_next.py"
CONFIG_REL = Path(".kb-next") / "kb-next.config.json"


def command_text(tool_input: object) -> str:
    """The shell text of a Bash or PowerShell call; Codex may send an argv list."""
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    if isinstance(command, str):
        return command
    if isinstance(command, list) and all(isinstance(item, str) for item in command):
        if len(command) >= 3 and command[-2] in {"-c", "-lc", "-Command", "/c"}:
            return command[-1]
        return " ".join(command)
    return ""


def simple_commands(text: str) -> list[list[str]]:
    """Split shell text into simple commands of words.

    Quotes group words and are dropped; backslashes stay literal, so Windows
    paths survive. Control operators, pipes and braces end a command; a
    parenthesis ends one and stands as a command of its own, so a subshell is
    visible. A brace opens no scope in bash or PowerShell, so it saves nothing.
    """
    commands: list[list[str]] = []
    words: list[str] = []
    word: list[str] = []
    in_word = False
    quote = ""
    for char in text:
        if quote:
            if char == quote:
                quote = ""
            else:
                word.append(char)
        elif char in "'\"":
            quote = char
            in_word = True
        elif char in SEPARATORS or char.isspace():
            if in_word:
                words.append("".join(word))
                word, in_word = [], False
            if char in SEPARATORS and words:
                commands.append(words)
                words = []
            if char in "()":
                commands.append([char])
        else:
            word.append(char)
            in_word = True
    if in_word:
        words.append("".join(word))
    if words:
        commands.append(words)
    return commands


def gated_call(words: list[str]) -> tuple[str, str] | None:
    """(kb.py word, subcommand) when the words run a gated classic write."""
    index = 0
    while index < len(words) and ASSIGNMENT.match(words[index]):
        index += 1
    if index < len(words) and words[index].lower() in {"uv", "uvx"}:
        index += 2 if index + 1 < len(words) and words[index + 1] == "run" else 1
    if index >= len(words):
        return None
    head = words[index].replace("\\", "/").rsplit("/", 1)[-1]
    if INTERPRETER.match(head):
        script = next((i for i in range(index + 1, len(words)) if words[i].lower().endswith(".py")), None)
    elif head == "kb.py":
        script = index
    else:
        return None
    if script is None or words[script].replace("\\", "/").rsplit("/", 1)[-1] != "kb.py":
        return None
    if script + 1 < len(words) and words[script + 1] in GATED_SUBCOMMANDS:
        return words[script], words[script + 1]
    return None


def nested_script(words: list[str]) -> list[str]:
    """The words after `-c`, `-Command` or `/c` when the command starts a shell; empty otherwise."""
    index = next((i for i, word in enumerate(words) if not ASSIGNMENT.match(word)), len(words))
    if index == len(words):
        return []
    head = words[index].replace("\\", "/").rsplit("/", 1)[-1]
    flag = next((flag for shell, flag in SCRIPT_FLAGS if shell.match(head)), None)
    if flag is None:
        return []
    position = next((i for i in range(index + 1, len(words)) if flag.match(words[i])), None)
    return [] if position is None else words[position + 1 :]


def native(word: str) -> str:
    """A path word with forward slashes; on Windows, Git Bash's `/c/x` becomes `c:/x`."""
    path = word.replace("\\", "/")
    return MSYS_DRIVE.sub(r"\1:/", path) if os.name == "nt" else path


def directory_target(arguments: list[str], here: Path) -> Path | None:
    """The folder a `cd`, `pushd` or `Set-Location` names; None when the hook cannot follow it.

    Flags, cmd's `/d` and redirections such as `>/dev/null` are skipped. No
    folder, `-` or a variable cannot be followed.
    """
    paths: list[str] = []
    words = iter(arguments)
    for word in words:
        if REDIRECTION.match(word):
            if not REDIRECTION.sub("", word).lstrip("<>"):
                next(words, None)
        elif word == "-" or not word.startswith("-"):
            paths.append(word)
    if len(paths) == 2 and paths[0].lower() == "/d":
        paths = paths[1:]
    if len(paths) != 1 or paths[0] == "-" or any(mark in paths[0] for mark in "$%`"):
        return None
    target = Path(os.path.expanduser(native(paths[0])))
    return Path(os.path.normpath(target if target.is_absolute() else here / target))


def located_commands(text: str, cwd: Path) -> list[tuple[list[str], Path]]:
    """Each simple command with the folder the shell stands in when it runs.

    `cd`, `pushd` and `Set-Location` move the shell to an existing folder; a
    failed change leaves it where it was. `popd` and the end of a subshell
    return to the folder `pushd` or the opening parenthesis saved. A change
    the hook cannot follow falls back to `cwd`, the hook's cwd. A leading
    `then`, `do` or `!` is skipped. The text a nested shell runs is parsed
    from the folder it starts in, and its own changes stay inside it; the
    words after the flag also count as one command, for an unquoted
    `cmd /c python ...`.
    """
    located: list[tuple[list[str], Path]] = []
    saved: list[Path] = []
    here = cwd
    for words in simple_commands(text):
        while words and words[0].lower() in RESERVED_WORDS:
            words = words[1:]
        if not words:
            continue
        name = words[0].lower()
        if name == "(":
            saved.append(here)
        elif name == ")":
            here = saved.pop() if saved else here
        elif name in RESTORE_DIRECTORY:
            here = saved.pop() if saved else cwd
        elif name in CHANGE_DIRECTORY:
            target = directory_target(words[1:], here)
            if target is None:
                here = cwd
            elif os.path.isdir(target):
                if name in PUSH_DIRECTORY:
                    saved.append(here)
                here = target
        else:
            located.append((words, here))
            script = nested_script(words)
            if script:
                located.extend(located_commands(script[0], here))
                located.append((script, here))
    return located


def project_for(kb_word: str, cwd: Path) -> Path | None:
    """The project whose KB the call writes; None for a kb.py outside `.kb/`."""
    path = Path(os.path.expanduser(native(kb_word)))
    if not path.is_absolute():
        path = cwd / path
    if path.parent.name == ".kb":
        return path.parent.parent
    if len(Path(native(kb_word)).parts) > 1:
        return None
    for candidate in (cwd, *cwd.parents):
        if (candidate / CONFIG_REL).is_file() or (candidate / ".kb").is_dir():
            return candidate
    return None


def gate_enabled(project: Path) -> bool:
    config_file = project / CONFIG_REL
    if not config_file.is_file():
        return False
    try:
        config = json.loads(config_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return True
    gate = config.get("write_gate") if isinstance(config, dict) else None
    return not (isinstance(gate, dict) and gate.get("enabled") is False)


def runtime_path(project: Path) -> str:
    local = project / RUNTIME_REL
    if local.is_file():
        return RUNTIME_REL.as_posix()
    return (Path(__file__).resolve().parent.parent / "runtime" / "kb_next.py").as_posix()


def deny_reason(subcommand: str, project: Path) -> str:
    runtime = runtime_path(project)
    if subcommand == "update":
        route = (
            "For a HOT to WARM demotion, run "
            f"`python {runtime} semantic-hygiene --json`, classify the candidates and write the "
            f"proposal with `python {runtime} semantic-hygiene --judgment @hygiene-judgment.json "
            "--write-proposals --json`. A content change is a supersede through filing-proposal "
            "(below). Other metadata edits (tags, confidence, review dates) have no proposal path: "
            "ask the user to run that command in their own terminal."
        )
    else:
        action = "supersede" if subcommand == "supersede" else "new"
        target = ", supersedes_id naming the record it replaces" if action == "supersede" else ""
        route = (
            f"Prepare the proposal with `python {runtime} filing-proposal --input @candidate.json "
            "--category <CATEGORY> --domain <domain> --judgment @judgment.json --json` "
            "(candidate.json holds title, content and source; judgment.json holds action "
            f"\"{action}\", record_draft with category, domain, title and content{target}, "
            "confidence, rationale and provenance as a list of {\"record_id\": \"<existing id>\"} or "
            "{\"source_id\": \"<SRC id>\"}; a file path or URL is not provenance, so register a file "
            "first with `python .kb/kb.py ingest <path> --json` and cite its source_id)."
        )
    supersedes = " --supersedes <record id>" if subcommand in {"supersede", "update"} else ""
    return (
        f"kb-wiki-vnext write gate (plugin hook): this project has KB/Wiki vNext "
        f"({CONFIG_REL.as_posix()}), so agent shells do not run `kb.py {subcommand}`; canonical "
        "records change only after the user approves. When the user approved the record in chat, "
        f"file it in one call: `python {runtime} approved-filing --category <CATEGORY> --domain "
        "<domain> --title \"<title>\" --content \"<content>\" --confidence <0.8-1.0> --source-id "
        f"<SRC id>{supersedes} --approval-note \"<who approved, their words>\" --actor-runtime "
        "<claude-code|codex|cowork> --json`. Otherwise write a proposal the user approves. "
        f"{route} After the approver says "
        f"yes, apply it with `python {runtime} proposal-apply --proposal <proposal_id> --approve "
        "--approval-note \"<who approved and why>\" --actor-runtime <claude-code|codex|cowork> "
        "--json`, adding `--actor <id>` unless `proposal_apply.default_actor` names the approver."
    )


def decide(payload: object) -> str | None:
    """The deny reason for a hook payload, or None to let the call run."""
    if not isinstance(payload, dict):
        return None
    text = command_text(payload.get("tool_input"))
    if "kb.py" not in text:
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    for words, here in located_commands(text, cwd):
        call = gated_call(words)
        if call is None:
            continue
        project = project_for(call[0], here)
        if project is not None and gate_enabled(project):
            return deny_reason(call[1], project)
    return None


def main() -> int:
    try:
        raw = sys.stdin.buffer.read() if sys.stdin is not None else b""
        if b"kb.py" not in raw:
            return 0
        reason = decide(json.loads(raw.decode("utf-8-sig")))
    except Exception:
        return 0
    if reason:
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        sys.stdout.write(json.dumps(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
