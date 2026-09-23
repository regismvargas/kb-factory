"""Shipped plugin surfaces and the marketplace must not reference CASE.

CASE (the case-framework repository, the CASE Companion plugin, its CCH
harness, and the CASE workflow conventions) is deprecated. Nothing shipped in
the kb-lifecycle, kb-wiki-vnext, or session-gate plugins, or in the
marketplace manifests, may detect, route to, depend on, advertise, or mention
it. SQL ``CASE ... WHEN`` expressions in bundled runtimes stay allowed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_PLUGINS = ("kb-lifecycle", "kb-wiki-vnext", "session-gate")
MARKETPLACES = (
    Path(".claude-plugin") / "marketplace.json",
    Path(".agents") / "plugins" / "marketplace.json",
)
SKIPPED_PARTS = {"__pycache__"}
SKIPPED_SUFFIXES = {".pyc", ".db", ".db-shm", ".db-wal", ".zip"}

CASE_PATTERNS = (
    ("CASE token", re.compile(r"(?<![A-Za-z])CASE(?![A-Za-z])")),
    ("CCH token", re.compile(r"\bCCH\b")),
    ("CCH version", re.compile(r"cch[-_ ]v", re.IGNORECASE)),
    ("case-framework", re.compile(r"case[-_]framework", re.IGNORECASE)),
    ("CASE Companion", re.compile(r"case[-_\s]+companion", re.IGNORECASE)),
    ("Companion plugin", re.compile(r"\bCompanion\b")),
    ("case-orchestration", re.compile(r"case[-_]orchestration", re.IGNORECASE)),
    ("companion state", re.compile(r"companion_state", re.IGNORECASE)),
    ("case tag", re.compile(r"[\"']case[\"']")),
    ("CASE skill", re.compile(r"case-(?:adoption-audit|resync|rollout|runtime-sync)")),
    ("kickoffs marker", re.compile(r"\bkickoffs\b")),
    ("reviews marker", re.compile(r"[\"']reviews[\"']")),
    ("workpackages marker", re.compile(r"\bworkpackages\b", re.IGNORECASE)),
    ("handoff marker", re.compile(r"HANDOFF_SESSION")),
)
# SQL searched CASE (`CASE WHEN`) or simple CASE (`CASE <expr> WHEN`).
SQL_CASE = re.compile(r"\bCASE(?=\s+WHEN\b|\s+[\w.()']+\s+WHEN\b)")


def case_references(text: str) -> list[str]:
    sql_starts = {match.start() for match in SQL_CASE.finditer(text)}
    found: list[str] = []
    for label, pattern in CASE_PATTERNS:
        for match in pattern.finditer(text):
            if label == "CASE token" and match.start() in sql_starts:
                continue
            line = text.count("\n", 0, match.start()) + 1
            found.append(f"line {line}: {label} {match.group(0)!r}")
    return found


def _shipped_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not SKIPPED_PARTS.intersection(path.parts)
        and path.suffix.lower() not in SKIPPED_SUFFIXES
    ]


def _offenders(paths: list[Path]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for hit in case_references(text):
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()} {hit}")
    return offenders


def test_matcher_flags_case_and_allows_sql_case_expressions() -> None:
    assert case_references("ORDER BY CASE tier WHEN 'HOT' THEN 0 ELSE 2 END") == []
    assert case_references("SELECT CASE\n  WHEN review_after IS NULL THEN 1 END") == []
    assert case_references("a use case, a test case, lowercase text") == []
    for sample in (
        "detect `.kb-next/`, `.kb/`, CASE; route vNext first",
        "then classic `.kb/` and CASE when present",
        "Thin session wrapper for KB + CASE",
        "CASE_COMPANION_ROOT",
        "wrapper for KB-lifecycle and CASE\nCompanion",
        'keywords: ["kb", "case"]',
        "case-framework/templates/companion-plugin",
        "plugins/case-companion/skills/case-orchestration/SKILL.md",
        "Distribute KB lifecycle. (CCH v0.7-aware)",
        '"cch-v0.7"',
        '"cch_version": "0.7"',
        "## CCH Conformance",
        "companion_state.json",
        'case_markers = ["kickoffs", "reviews", "workpackages"]',
        "kickoffs/HANDOFF_SESSION_S1_EXIT.md",
        "case-adoption-audit-skill-0.3.1.zip",
    ):
        assert case_references(sample), sample


@pytest.mark.parametrize("plugin", SHIPPED_PLUGINS)
def test_shipped_plugin_has_no_case_reference(plugin: str) -> None:
    root = REPO_ROOT / "plugins" / plugin
    paths = _shipped_files(root)
    names = {path.relative_to(root).as_posix() for path in paths}
    assert ".claude-plugin/plugin.json" in names, f"{plugin}: nothing scanned"
    assert _offenders(paths) == []


def test_marketplace_has_no_case_reference() -> None:
    paths = [REPO_ROOT / rel for rel in MARKETPLACES if (REPO_ROOT / rel).is_file()]
    assert REPO_ROOT / MARKETPLACES[0] in paths
    assert _offenders(paths) == []
