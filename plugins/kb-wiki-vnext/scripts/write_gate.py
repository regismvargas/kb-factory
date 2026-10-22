"""PreToolUse write gate for KB/Wiki vNext workspaces (kb-wiki-vnext plugin).

In a project with `.kb-next/kb-next.config.json`, an agent shell command that
writes canonical classic records without the user's approval is denied with
the governed path. Gated: `kb.py create`, `file`, `supersede`, `update`,
`resolve` and `bulk-import`; `init --seed`; `raw-query --allow-write`;
`consolidate --apply-demotions`; `lifecycle scheduled-maintenance` and any
`lifecycle` event run with `--apply-demotions` or `--apply-cold-demotions`.
`--help` passes. The routes are `approved-filing` for a record the user
approved in chat, or `filing-proposal` or `semantic-hygiene
--write-proposals` and then `proposal-apply` once the approver says yes.
Both runtime commands run the classic CLI in their own subprocess, which
never passes through this hook. Classic-only projects are not gated, because
there the direct write is the only path. A linked Git worktree is gated when
it or its main checkout is activated, since the classic runtime may write
the main checkout's KB from there.

A relative `kb.py` resolves against the folder the shell stands in: the
hook's cwd, moved by an earlier `cd`, `pushd` or `Set-Location` in the same
command that names one literal folder. Braces end a command, so a write
inside `try { ... }` or `{ ...; }` is seen, and a parenthesis opens and
closes a subshell. The parser also follows what an agent types around the
interpreter: environment assignments, `env`, `nohup`, `exec` or `call`,
`python -m kb`, launchers (`cmd /c`, `powershell -Command`, `bash -lc`,
`Start-Process`, `Invoke-Expression`) whose text is parsed from the same
folder, PowerShell arrays, PowerShell and POSIX line continuations, and
names in any case (Windows opens `.KB/KB.py` as the same file). Commands
built from variables, encoded commands and direct SQLite access stay out of
reach: the gate steers agents, it does not authenticate them. Anything
unexpected fails open. Owners can turn it off with `"write_gate":
{"enabled": false}` in the vNext config.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Subcommands that always write canonical records.
GATED_SUBCOMMANDS = ("create", "file", "supersede", "update", "resolve", "bulk-import")
# Lifecycle events whose default config demotes HOT records.
DEMOTING_EVENTS = ("scheduled-maintenance",)
SEPARATORS = ";&|(){}\n"
INTERPRETER = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py|pypy3?)(?:\.exe)?$", re.IGNORECASE)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# `kb.py`, or `-m kb` with the module name quoted or after a line continuation; the raw
# JSON escapes quotes and newlines with a backslash, so those count as well.
KB_HINT = re.compile(r"kb\.py|-m(?:[\s`'\"]|\\[\srnt\\\"'])*kb\b", re.IGNORECASE)
# What `gated_call` returns as the script for `python -m kb`.
MODULE = "-m kb"
LINE_CONTINUATION = re.compile(r"[`\\]\r?\n")
# PowerShell array literal `@(a, b)`: its items, without the parentheses that open a subshell.
ARRAY = re.compile(r"@\(([^()]*)\)")
RESERVED_WORDS = {"!", "if", "then", "elif", "else", "do", "while", "until"}
# (shell, the flag before the text it runs): POSIX `-c` may be combined, as in `-lc`.
SCRIPT_FLAGS = (
    (re.compile(r"^(?:bash|sh|zsh|dash|ksh)(?:\.exe)?$", re.IGNORECASE), re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")),
    (re.compile(r"^(?:pwsh|powershell)(?:\.exe)?$", re.IGNORECASE), re.compile(r"^-c(?:ommand)?$", re.IGNORECASE)),
    (re.compile(r"^cmd(?:\.exe)?$", re.IGNORECASE), re.compile(r"^/[ck]$", re.IGNORECASE)),
)
EVALUATORS = {"invoke-expression", "iex"}
# Launchers that run the rest of the line as the command itself.
TRANSPARENT = {"nohup", "exec", "time", "command", "call"}
ENV_VALUE_OPTIONS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
START_PROCESS = {"start-process", "saps", "start"}
START_VALUE_PARAMETERS = (
    "redirectstandardoutput",
    "redirectstandarderror",
    "redirectstandardinput",
    "windowstyle",
    "verb",
    "credential",
    "environment",
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
    paths survive, except that a backslash or a PowerShell backtick before a
    space outside quotes escapes it (`my\\ project`). Control operators, pipes
    and braces end a command; a parenthesis ends one and stands as a command of
    its own, so a subshell is visible. A brace opens no scope in bash or
    PowerShell, so it saves nothing.
    """
    commands: list[list[str]] = []
    words: list[str] = []
    word: list[str] = []
    in_word = False
    quote = ""
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if not quote and char in "\\`" and text[index + 1 : index + 2] in (" ", "\t"):
            word.append(text[index + 1])
            in_word = escaped = True
            continue
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


def program(word: str) -> str:
    """The lower-case program name of a word: no directory, no `.exe`."""
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def strip_prefixes(words: list[str]) -> list[str]:
    """Drop environment assignments, `env` with its options, and transparent launchers."""
    index = 0
    while index < len(words):
        name = program(words[index])
        if ASSIGNMENT.match(words[index]):
            index += 1
        elif name == "env":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index += 2 if words[index] in ENV_VALUE_OPTIONS else 1
        elif name in TRANSPARENT:
            index += 1
        else:
            break
    return words[index:]


def nested_script(words: list[str]) -> list[str]:
    """The words a shell or `Invoke-Expression` runs after `-c`, `-Command` or `/c`; empty otherwise."""
    words = strip_prefixes(words)
    if not words:
        return []
    head = words[0].replace("\\", "/").rsplit("/", 1)[-1]
    if program(head) in EVALUATORS:
        return [word for word in words[1:] if word.lower() != "-command"]
    flag = next((flag for shell, flag in SCRIPT_FLAGS if shell.match(head)), None)
    if flag is None:
        return []
    position = next((i for i in range(1, len(words)) if flag.match(words[i])), None)
    return [] if position is None else words[position + 1 :]


def start_process_command(words: list[str]) -> tuple[list[str], str | None] | None:
    """The command and working directory of `Start-Process` (or cmd `start`)."""
    words = strip_prefixes(words)
    if not words or program(words[0]) not in START_PROCESS:
        return None
    executable = None
    arguments: list[str] = []
    positional: list[str] = []
    workdir = None
    index = 1
    while index < len(words):
        word = words[index]
        value = words[index + 1] if index + 1 < len(words) else None
        key = word[1:].lower() if word.startswith("-") and len(word) > 1 else ""
        if not key:
            if word and not word.startswith("/"):
                positional.append(word)
            index += 1
        elif key.startswith("f") and "filepath".startswith(key):
            executable, index = value, index + 2
        elif key == "args" or (key.startswith("a") and "argumentlist".startswith(key)):
            arguments.extend([value] if value is not None else [])
            index += 2
        elif key == "wd" or (key.startswith("wo") and "workingdirectory".startswith(key)):
            workdir, index = value, index + 2
        elif len(key) >= 3 and any(name.startswith(key) for name in START_VALUE_PARAMETERS):
            index += 2
        else:
            index += 1
    if executable is None and positional:
        executable = positional.pop(0)
    if executable is None:
        return None
    flattened: list[str] = []
    for argument in [*arguments, *positional]:
        for piece in argument.split(","):
            for split in simple_commands(piece):
                flattened.extend(word for word in split if word not in ("(", ")"))
    return [executable, *flattened], workdir


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


def located_commands(text: str, cwd: Path, depth: int = 3) -> list[tuple[list[str], Path]]:
    """Each simple command with the folder the shell stands in when it runs.

    `cd`, `pushd` and `Set-Location` move the shell to an existing folder; a
    failed change leaves it where it was. `popd` and the end of a subshell
    return to the folder `pushd` or the opening parenthesis saved. A change
    the hook cannot follow falls back to `cwd`, the hook's cwd. A leading
    `then`, `do` or `!` and environment prefixes are skipped. The text a
    nested shell or `Start-Process` runs is parsed from the folder it starts
    in, and its own changes stay inside it; the words after a shell's flag
    also count as one command, for an unquoted `cmd /c python ...`.
    `Invoke-Expression` runs in the current scope, so its changes carry on.
    """
    located: list[tuple[list[str], Path]] = []
    walk(text, cwd, cwd, [], located, depth)
    return located


def walk(text: str, cwd: Path, here: Path, saved: list[Path], located: list, depth: int) -> Path:
    """Add the commands of `text` to `located`, starting in `here`; return where the shell ends.

    `Invoke-Expression` (`iex`) runs its text in the current scope, so a
    directory change inside it moves this sequence too; a child shell's does not.
    """
    for words in simple_commands(ARRAY.sub(r"\1", LINE_CONTINUATION.sub(" ", text))):
        while words and words[0].lower() in RESERVED_WORDS:
            words = words[1:]
        bare = strip_prefixes(words)
        if not bare:
            continue
        name = bare[0].lower()
        words = words if program(bare[0]) not in EVALUATORS else bare
        if name == "(":
            saved.append(here)
        elif name == ")":
            here = saved.pop() if saved else here
        elif name in RESTORE_DIRECTORY:
            here = saved.pop() if saved else cwd
        elif name in CHANGE_DIRECTORY:
            target = directory_target(bare[1:], here)
            if target is None:
                here = cwd
            elif os.path.isdir(target):
                if name in PUSH_DIRECTORY:
                    saved.append(here)
                here = target
        elif program(name) in EVALUATORS and depth > 0:
            located.append((words, here))
            here = walk(" ".join(nested_script(words)), cwd, here, saved, located, depth - 1)
        else:
            located.extend(launched_commands(words, here, depth))
    return here


def launched_commands(words: list[str], here: Path, depth: int) -> list[tuple[list[str], Path]]:
    """The command itself plus what it launches: a nested shell's text or a `Start-Process` command."""
    located = [(words, here)]
    if depth <= 0:
        return located
    script = nested_script(words)
    if script:
        located.extend(located_commands(script[0], here, depth - 1))
        located.append((script, here))
    started = start_process_command(words)
    if started is not None:
        command, workdir = started
        start_dir = directory_target([workdir], here) if workdir else here
        located.extend(launched_commands(strip_prefixes(command), start_dir or here, depth - 1))
    return located


def has_flag(words: list[str], flag: str) -> bool:
    """True when a word is the flag or an abbreviation argparse would accept for it."""
    return any(word.startswith("--") and len(word) > 2 and flag.startswith(word.split("=", 1)[0]) for word in words)


def asks_for_help(words: list[str]) -> bool:
    """`-h` or `--help` (or an abbreviation): argparse prints help and exits before any write."""
    return any(word == "-h" or has_flag([word], "--help") for word in words)


def gated_verb(words: list[str]) -> str | None:
    """The deny key for the arguments after `kb.py`, or None when they write no record."""
    if not words:
        return None
    subcommand, rest = words[0], words[1:]
    if asks_for_help(rest):
        return None
    if subcommand in GATED_SUBCOMMANDS:
        return subcommand
    if subcommand == "init" and has_flag(rest, "--seed"):
        return "init"
    if subcommand == "raw-query" and has_flag(rest, "--allow-write"):
        return "raw-query"
    if subcommand == "consolidate" and has_flag(rest, "--apply-demotions"):
        return "demotions"
    if subcommand == "lifecycle":
        if has_flag(rest, "--apply-demotions") or any(word in DEMOTING_EVENTS for word in rest):
            return "demotions"
        if has_flag(rest, "--apply-cold-demotions"):
            return "cold-demotions"
    return None


def gated_call(words: list[str]) -> tuple[str, str] | None:
    """(kb.py word, deny key) when the words run a gated classic write."""
    words = strip_prefixes(words)
    index = 0
    if words and program(words[0]) in {"uv", "uvx"}:
        index = 2 if len(words) > 1 and words[1] == "run" else 1
    if index >= len(words):
        return None
    head = words[index].replace("\\", "/").rsplit("/", 1)[-1]
    script = None
    if INTERPRETER.match(head):
        for position in range(index + 1, len(words)):
            word = words[position]
            if word == "-m" or (word.startswith("-m") and not word.startswith("--")):
                module = words[position + 1] if word == "-m" and position + 1 < len(words) else word[2:]
                if module.lower() != "kb":
                    return None
                verb = gated_verb(words[position + (2 if word == "-m" else 1) :])
                return (MODULE, verb) if verb else None
            if word.lower().endswith(".py"):
                script = position
                break
    elif head.lower() == "kb.py":
        script = index
    if script is None or words[script].replace("\\", "/").rsplit("/", 1)[-1].lower() != "kb.py":
        return None
    verb = gated_verb(words[script + 1 :])
    return (words[script], verb) if verb else None


def module_script(words: list[str], here: Path) -> str:
    """Where `python -m kb` finds `kb.py`: the shell's folder, then a literal `PYTHONPATH=` before it."""
    if (here / "kb.py").is_file():
        return (here / "kb.py").as_posix()
    prefix = words[: len(words) - len(strip_prefixes(words))]
    for word in prefix:
        if not ASSIGNMENT.match(word):
            continue
        name, _, value = word.partition("=")
        if name.upper() != "PYTHONPATH":
            continue
        for entry in value.split(os.pathsep):
            candidate = Path(os.path.expanduser(native(entry))) if entry else here
            candidate = candidate if candidate.is_absolute() else here / candidate
            if (candidate / "kb.py").is_file():
                return (candidate / "kb.py").as_posix()
    return "kb.py"


def project_for(kb_word: str, cwd: Path) -> Path | None:
    """The project whose KB the call writes; None for a kb.py outside `.kb/`."""
    path = Path(os.path.expanduser(native(kb_word)))
    if not path.is_absolute():
        path = cwd / path
    if path.parent.name.lower() == ".kb":
        return path.parent.parent
    if len(Path(native(kb_word)).parts) > 1:
        return None
    for candidate in (cwd, *cwd.parents):
        if (candidate / CONFIG_REL).is_file() or (candidate / ".kb").is_dir():
            return candidate
    return None


def main_worktree_root(project: Path) -> Path | None:
    """The main checkout when `project` is a linked Git worktree, read as the classic runtime reads it."""
    try:
        dotgit = project / ".git"
        if not dotgit.is_file():
            return None
        text = dotgit.read_text(encoding="utf-8-sig", errors="replace").strip()
        if not text.lower().startswith("gitdir:"):
            return None
        gitdir = Path(text.split(":", 1)[1].strip())
        if not gitdir.is_absolute():
            gitdir = project / gitdir
        common = Path((gitdir / "commondir").read_text(encoding="utf-8-sig", errors="replace").strip())
        if not common.is_absolute():
            common = gitdir / common
        common = common.resolve()
        if common.name != ".git" or not common.is_dir():
            return None
        return common.parent
    except (OSError, ValueError):
        return None


def config_root(project: Path) -> Path | None:
    """The project, or the main checkout of a linked worktree, whose vNext config keeps the gate on."""
    roots = [project]
    main = main_worktree_root(project)
    if main is not None and main != project:
        roots.append(main)
    for root in roots:
        config_file = root / CONFIG_REL
        if not config_file.is_file():
            continue
        try:
            config = json.loads(config_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return root
        gate = config.get("write_gate") if isinstance(config, dict) else None
        if not (isinstance(gate, dict) and gate.get("enabled") is False):
            return root
    return None


def gate_enabled(project: Path) -> bool:
    """On when the project, or the main checkout of a linked worktree, has a vNext config that keeps it on."""
    return config_root(project) is not None


def runtime_path(project: Path, root: Path | None = None) -> str:
    """The runtime invocation for the deny; with `--project-root` when the config lives elsewhere."""
    root = root or project
    local = root / RUNTIME_REL
    if root == project and local.is_file():
        return RUNTIME_REL.as_posix()
    runtime = local if local.is_file() else Path(__file__).resolve().parent.parent / "runtime" / "kb_next.py"
    if root == project:
        return runtime.as_posix()
    return f'"{runtime.as_posix()}" --project-root "{root.as_posix()}"'


DISPLAY = {
    "init": "`kb.py init --seed`",
    "raw-query": "`kb.py raw-query --allow-write`",
    "demotions": "`kb.py lifecycle scheduled-maintenance` or `--apply-demotions`",
    "cold-demotions": "`kb.py lifecycle --apply-cold-demotions`",
}
# Verbs whose record a chat approval can file in one `approved-filing` call.
APPROVED_FILING = {"create", "file", "supersede", "update", "bulk-import", "init"}


def hygiene_route(runtime: str, what: str) -> str:
    return (
        f"{what} Detect with `python {runtime} semantic-hygiene --json`, classify the candidates in "
        f"hygiene-judgment.json and write the proposal with `python {runtime} semantic-hygiene --judgment "
        "@hygiene-judgment.json --write-proposals --json`. Both passes see at most 50 active records, HOT "
        "first; when the record is not among them, add the same `--limit 500` to both commands."
    )


def filing_route(runtime: str, action: str) -> str:
    target = ", supersedes_id naming the record it replaces" if action == "supersede" else ""
    return (
        f"Prepare the proposal with `python {runtime} filing-proposal --input @candidate.json "
        "--category <CATEGORY> --domain <domain> --judgment @judgment.json --json` "
        "(candidate.json holds title, content and source; judgment.json holds action "
        f"\"{action}\", record_draft with category, domain, title and content{target}, "
        "confidence, rationale and provenance as a list of {\"record_id\": \"<existing id>\"} or "
        "{\"source_id\": \"<SRC id>\"}; a file path or URL is not provenance, so register a file "
        "first with `python .kb/kb.py ingest <path> --json` and cite its source_id)."
    )


def approved_filing_route(runtime: str, verb: str) -> str:
    supersedes = " --supersedes <record id>" if verb in {"supersede", "update"} else ""
    return (
        "When the user approved the record in chat, file it in one call: "
        f"`python {runtime} approved-filing --category <CATEGORY> --domain <domain> --title \"<title>\" "
        f"--content \"<content>\" --confidence <0.8-1.0> --source-id <SRC id>{supersedes} --approval-note "
        "\"<who approved, their words>\" --actor-runtime <claude-code|codex|cowork> --json`. Otherwise "
        "write a proposal the user approves."
    )


RETIRE = (
    "A record that an existing ATIVO record already replaces (a FATO or DECISAO that newer information "
    "superseded, or a duplicate) retires without new content: put it in `supersede_or_merge_candidate` "
    "with \"action\": \"retire\" and replacement_id naming that record."
)


def deny_reason(verb: str, project: Path) -> str:
    runtime = runtime_path(project, config_root(project))
    proposal = True
    if verb == "update":
        route = (
            hygiene_route(runtime, "A HOT to WARM demotion goes to `demote_candidate`.")
            + " A content change is a supersede through filing-proposal: "
            + filing_route(runtime, "supersede")
            + " Other metadata edits (tags, confidence, review dates) have no proposal path: "
            "ask the user to run that command in their own terminal."
        )
    elif verb == "resolve":
        route = hygiene_route(
            runtime,
            "An open item (PENDENCIA) closes through `resolve_candidate`, with resolution_notes.",
        ) + " " + RETIRE
    elif verb == "demotions":
        route = hygiene_route(runtime, "HOT demotion goes through a proposal in `demote_candidate`.") + (
            " For exports and the wiki run `python .kb/kb.py lifecycle session-end --json`; "
            "`consolidate` without `--apply-demotions` still lists duplicates."
        )
    elif verb == "cold-demotions":
        proposal = False
        route = (
            "WARM to COLD demotion has no proposal action, and from classic runtime 0.2.6 the lifecycle skips "
            "`--apply-cold-demotions` in a vNext project for every caller. To move one record, ask the user to "
            "run `kb.py update <record_id> --tier COLD --tier-reason <reason>` in their own terminal. For "
            "exports and the wiki run `python .kb/kb.py lifecycle session-end --json`."
        )
    elif verb == "raw-query":
        proposal = False
        route = (
            "SQL writes have no proposal path: ask the user to run the statement in their own terminal. "
            "`raw-query` without `--allow-write` stays open for reads."
        )
    elif verb in ("bulk-import", "init"):
        route = (
            "A batch import (also `init --seed` on an existing KB) has no proposal path: file each record "
            "through filing-proposal, or ask the user to run the import in their own terminal. "
            + filing_route(runtime, "new")
        )
    elif verb == "supersede":
        route = filing_route(runtime, "supersede") + " " + hygiene_route(runtime, RETIRE)
    else:
        route = filing_route(runtime, "new")
    if verb in APPROVED_FILING:
        route = approved_filing_route(runtime, verb) + " " + route
    reason = (
        f"kb-wiki-vnext write gate (plugin hook): this project has KB/Wiki vNext "
        f"({CONFIG_REL.as_posix()}), so agent shells do not run {DISPLAY.get(verb, f'`kb.py {verb}`')}; canonical "
        f"records change only after the user approves. {route}"
    )
    if proposal:
        reason += (
            f" After the approver says yes, apply it with `python {runtime} proposal-apply --proposal "
            "<proposal_id> --approve --approval-note \"<who approved and why>\" --actor-runtime "
            "<claude-code|codex|cowork> --json`, adding `--actor <id>` unless "
            "`proposal_apply.default_actor` names the approver."
        )
    return reason


def decide(payload: object) -> str | None:
    """The deny reason for a hook payload, or None to let the call run."""
    if not isinstance(payload, dict):
        return None
    text = command_text(payload.get("tool_input"))
    if not KB_HINT.search(text):
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    for words, here in located_commands(text, cwd):
        call = gated_call(words)
        if call is None:
            continue
        script = module_script(words, here) if call[0] == MODULE else call[0]
        project = project_for(script, here)
        if project is not None and gate_enabled(project):
            return deny_reason(call[1], project)
    return None


def main() -> int:
    try:
        raw = sys.stdin.buffer.read() if sys.stdin is not None else b""
        if not KB_HINT.search(raw.decode("utf-8-sig", errors="replace")):
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
