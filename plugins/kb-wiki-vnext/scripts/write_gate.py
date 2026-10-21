"""PreToolUse write gate for KB/Wiki vNext workspaces (kb-wiki-vnext plugin).

In a project with `.kb-next/kb-next.config.json`, an agent shell command that
runs the classic `kb.py create`, `file`, `supersede` or `update` is denied with
the governed path: `filing-proposal`, then `proposal-apply` once the approver
says yes. `proposal-apply` runs the classic CLI in its own subprocess, which
never passes through this hook. Classic-only projects are not gated, because
there the direct write is the only path.

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
SEPARATORS = ";&|()\n"
INTERPRETER = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py|pypy3?)(?:\.exe)?$", re.IGNORECASE)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
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
    paths survive. Control operators, pipes and parentheses end a command.
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


def project_for(kb_word: str, cwd: Path) -> Path | None:
    """The project whose KB the call writes; None for a kb.py outside `.kb/`."""
    path = Path(os.path.expanduser(kb_word.replace("\\", "/")))
    if not path.is_absolute():
        path = cwd / path
    if path.parent.name == ".kb":
        return path.parent.parent
    if len(Path(kb_word.replace("\\", "/")).parts) > 1:
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
    return (
        f"kb-wiki-vnext write gate (plugin hook): this project has KB/Wiki vNext "
        f"({CONFIG_REL.as_posix()}), so agent shells do not run `kb.py {subcommand}`; canonical "
        f"records change through a proposal the user approves. {route} After the approver says "
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
    for words in simple_commands(text):
        call = gated_call(words)
        if call is None:
            continue
        project = project_for(call[0], cwd)
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
