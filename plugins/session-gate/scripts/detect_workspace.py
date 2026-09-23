"""Detect KB/Wiki vNext and KB-lifecycle surfaces for Session Gate.

The wrapper must stay thin, so this detector resolves canonical references when
possible instead of hardcoding KB rules into the wrapper itself.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


_WORKSPACE_BOUNDARY_MARKERS = (".git", ".kb", ".kb-next", "pyproject.toml")


def _workspace_search_bases(start: Path) -> tuple[Path, ...]:
    """Return search bases without crossing the nearest workspace boundary."""
    resolved_start = start.resolve()
    home = Path.home().resolve()
    bases: list[Path] = []

    for base in (resolved_start, *resolved_start.parents):
        # A user-level ``plugins/`` directory is an unrelated authority, not a
        # workspace fallback. Explicit environment roots remain available for
        # callers that intentionally need an external canonical reference.
        if base == home:
            break
        bases.append(base)
        if any((base / marker).exists() for marker in _WORKSPACE_BOUNDARY_MARKERS):
            return tuple(bases)

    # Without a recognizable workspace boundary, do not search arbitrary
    # ancestors such as a profile directory or filesystem root.
    return (resolved_start,) if resolved_start != home else ()


def _search_upwards(start: Path, relative_path: str) -> str | None:
    for base in _workspace_search_bases(start):
        candidate = base / relative_path
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _resolve_reference(root: Path, *relative_candidates: str) -> str | None:
    env_roots = [
        os.environ.get("SESSION_GATE_CANON_ROOT"),
        os.environ.get("KB_WIKI_VNEXT_ROOT"),
        os.environ.get("KB_LIFECYCLE_ROOT"),
    ]

    checked: set[str] = set()
    for env_root in env_roots:
        if not env_root:
            continue
        base = Path(env_root)
        for relative in relative_candidates:
            candidate = base / relative
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in checked:
                continue
            checked.add(key)
            if candidate.exists():
                return str(candidate.resolve())

    for relative in relative_candidates:
        resolved = _search_upwards(root.resolve(), relative)
        if resolved:
            return resolved

    return None


def detect(root: Path) -> dict:
    result = {
        "vnext": {"found": False, "details": {}},
        "kb": {"found": False, "details": {}},
        "summary": [],
    }

    vnext_root = root / ".kb-next"
    if vnext_root.is_dir():
        result["vnext"]["found"] = True
        details = result["vnext"]["details"]
        details["vnext_root"] = str(vnext_root.resolve())
        details["config_json"] = (vnext_root / "kb-next.config.json").is_file()
        details["now_md"] = (vnext_root / "memory" / "NOW.md").is_file()
        details["operations_jsonl"] = (vnext_root / "operations.jsonl").is_file()
        details["runtime_ref"] = _resolve_reference(
            root,
            ".kb-next/runtime/kb_next.py",
            "core/versions/kb-wiki-vnext/runtime/kb_next.py",
            "runtime/kb_next.py",
        )
        details["session_command_ref"] = _resolve_reference(
            root, "plugins/kb-wiki-vnext/commands/vnext-session-start.md"
        )
        result["summary"].append("KB/Wiki vNext detected (.kb-next/ present)")

    kb_root = root / ".kb"
    if kb_root.is_dir():
        result["kb"]["found"] = True
        details = result["kb"]["details"]
        details["kb_root"] = str(kb_root.resolve())
        details["kb_py"] = (kb_root / "kb.py").is_file()
        details["now_md"] = (kb_root / "memory" / "NOW.md").is_file()
        details["hot_md"] = (kb_root / "memory" / "HOT.md").is_file()
        details["index_md"] = (kb_root / "memory" / "INDEX.md").is_file()
        details["wiki"] = (kb_root / "wiki").is_dir()
        details["config_json"] = (kb_root / "kb.config.json").is_file()
        records_dir = kb_root / "records"
        details["record_count"] = len(list(records_dir.glob("*.md"))) if records_dir.is_dir() else 0
        details["session_helper_ref"] = _resolve_reference(
            root, "plugins/kb-lifecycle/scripts/session_start_context.py"
        )
        result["summary"].append("KB-lifecycle detected (.kb/ present)")

    if not result["vnext"]["found"] and not result["kb"]["found"]:
        result["summary"].append(
            "No KB/Wiki vNext or KB-lifecycle artifacts found in this workspace"
        )

    return result


def main() -> int:
    root = Path(os.getcwd())
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    print(json.dumps(detect(root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
