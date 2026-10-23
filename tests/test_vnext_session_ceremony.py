"""Session start and end contracts in the plugin surfaces (review of the ceremony cut, 2026-10-22).

The SessionStart hook replaces the bootstrap of a session, not the
development preflight; the close files what the user approved before the
lifecycle refresh runs once; curation runs only in the weekly maintenance run.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VNEXT = ROOT / "plugins" / "kb-wiki-vnext"
GATE = ROOT / "plugins" / "session-gate"


def flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_the_hook_skips_only_the_bootstrap_not_the_development_preflight() -> None:
    start = flat(VNEXT / "commands" / "vnext-session-start.md")
    assert "steps 1 to 5 are done" in start
    assert "compliance-preflight" in start.split("Steps 7 to 9 still apply", 1)[1][:200]
    skill = flat(VNEXT / "skills" / "kb-wiki-vnext" / "SKILL.md").split("says it replaces `session-start`", 1)[1]
    assert "compliance-preflight" in skill[:600]
    assert "after the hook text or `session-start`" in flat(VNEXT / "AGENTS.md")


def test_the_close_files_approved_records_before_the_lifecycle_refresh() -> None:
    end = flat(VNEXT / "commands" / "vnext-session-end.md")
    gate = flat(GATE / "commands" / "gate-session-end.md").split("## Step 2", 1)[1].split("## Step 3", 1)[0]
    for text in (end, gate):
        assert text.index("KB candidates") < text.index("python .kb/kb.py lifecycle session-end --json")
        assert text.index("python .kb/kb.py lifecycle session-end --json") < text.index("wiki-draft-status --json")
    assert "dense-index" in gate  # the same close as vnext-session-end, dense condition included


def test_no_surface_still_runs_curation_at_every_session_end() -> None:
    surfaces = [*VNEXT.rglob("*.md"), *GATE.rglob("*.md"),
                ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py",
                VNEXT / "runtime" / "kb_next.py"]
    stale = [path.relative_to(ROOT).as_posix() for path in surfaces
             if re.search(r"(at|in) every session end|every `vnext-session-end`", flat(path))]
    assert stale == []
