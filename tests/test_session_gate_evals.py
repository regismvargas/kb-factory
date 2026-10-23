"""The Session Gate eval harness closes out with the sections gate-session-end names.

gate-session-end dropped the pre-close audit (KB gaps and `git status`) and the
session id; the deterministic harness must not keep grading them.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "run_session_gate_evals.py"
TEMPLATE = ROOT / "core" / "templates" / "kb"
COMMAND = ROOT / "plugins" / "session-gate" / "commands" / "gate-session-end.md"


def load_harness():
    spec = importlib.util.spec_from_file_location("session_gate_evals_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_closeout_sections_match_the_gate_session_end_summary(tmp_path: Path) -> None:
    harness = load_harness()
    command = COMMAND.read_text(encoding="utf-8")
    summary = command.split("## Step 4: Present the summary", 1)[1]
    allowed = set(re.findall(r"^- `([^`]+)`", summary, re.MULTILINE))
    assert {"Workspace detected", "KB closeout", "Safe to close"} <= allowed

    workspace = tmp_path / "kb-only"
    workspace.mkdir()
    shutil.copytree(TEMPLATE, workspace / ".kb", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.run([sys.executable, str(workspace / ".kb" / "kb.py"), "init", "--slug", "evals"],
                   cwd=workspace, check=True, capture_output=True)
    empty = tmp_path / "empty"
    empty.mkdir()

    for path, closed in ((workspace, True), (empty, False)):
        output, data = harness.closeout_executor(path, with_skill=True)
        sections = set(re.findall(r"^## (.+)$", output, re.MULTILINE))
        assert sections <= allowed, sorted(sections - allowed)
        assert "Pre-close audit" not in output and "Git audit" not in output
        assert data["kb_end"] is closed
