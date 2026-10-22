"""Two-tier help for `kb_next.py` and the classic `kb.py`.

`--help` lists the handful of commands an agent uses day to day, so a session
finds its flags without paging through every subcommand; `--help-all` prints
the full argparse help, every command included, with the tiers named. Every
subcommand keeps working and keeps its own `--help`.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VNEXT = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
TEMPLATE = REPO / "core" / "templates" / "kb"
VNEXT_AGENT = {"session-start", "lookup", "semantic-lookup", "approved-filing", "filing-proposal",
               "proposal-apply", "semantic-hygiene", "wiki-draft-status"}
CLASSIC_AGENT = {"search", "get", "pending", "ingest", "create", "supersede", "resolve", "lifecycle"}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def subcommands(parser: argparse.ArgumentParser) -> dict:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError("no subcommands")


def cli(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(script), *args], cwd=str(script.parent),
                          capture_output=True, text=True, encoding="utf-8")


def listed(text: str) -> set:
    block = text.split("Agent commands:", 1)[1].split("\n\n", 1)[0]
    return {line.split()[0] for line in block.splitlines() if line.strip()}


@pytest.fixture(scope="module")
def parsers() -> dict:
    vnext = load("help_tiers_kb_next", VNEXT).build_parser()
    classic = load("help_tiers_classic_cli", TEMPLATE / "runtime" / "cli.py").build_parser(defaultdict(lambda: None))
    return {"vnext": vnext, "classic": classic}


@pytest.mark.parametrize("kind, script, agent", [
    ("vnext", VNEXT, VNEXT_AGENT),
    ("classic", TEMPLATE / "kb.py", CLASSIC_AGENT),
])
def test_help_lists_the_agent_commands_and_help_all_lists_every_command(parsers, kind, script, agent) -> None:
    commands = set(subcommands(parsers[kind]))
    short = cli(script, "--help")
    assert short.returncode == 0, short.stderr
    assert listed(short.stdout) == agent
    assert agent < commands
    assert "--help-all" in short.stdout
    assert len(short.stdout.splitlines()) < 25
    full = cli(script, "--help-all")
    assert full.returncode == 0, full.stderr
    braces = re.search(r"\{([a-z0-9,-]+)\}", re.sub(r"\s+", "", full.stdout))
    assert braces and set(braces.group(1).split(",")) == commands
    assert listed(full.stdout) == agent
    maintenance = full.stdout.split("Maintenance commands:", 1)[1]
    assert {name.strip() for name in maintenance.split(",")} == commands - agent


@pytest.mark.parametrize("kind", ["vnext", "classic"])
def test_every_subcommand_keeps_its_own_help(parsers, kind) -> None:
    root = parsers[kind]
    for name, parser in subcommands(root).items():
        assert "format_help" not in vars(parser), name
        assert type(parser) is type(root), name
        text = parser.format_help()
        assert text.startswith(f"usage: {root.prog} {name}"), name


def test_a_subcommand_help_still_runs() -> None:
    proc = cli(VNEXT, "lookup", "--help")
    assert proc.returncode == 0 and "--facet" in proc.stdout
    proc = cli(TEMPLATE / "kb.py", "ingest", "--help")
    assert proc.returncode == 0 and "--domain" in proc.stdout
