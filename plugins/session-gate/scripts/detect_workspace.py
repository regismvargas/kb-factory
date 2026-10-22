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


def _main_worktree_root(project: Path) -> Path | None:
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


def vnext_project_root(root: Path) -> Path | None:
    """The folder whose `.kb-next/` governs this workspace.

    The workspace itself when it has `.kb-next/`; otherwise, for a linked Git
    worktree, its main checkout when that holds `.kb-next/kb-next.config.json`.
    The kb-wiki-vnext write gate and the classic runtime's demotion guard use
    the same rule, so all three agree on a worktree activated only in main.
    """
    if (root / ".kb-next").is_dir():
        return root
    main = _main_worktree_root(root)
    if main is not None and (main / ".kb-next" / "kb-next.config.json").is_file():
        return main
    return None


def detect(root: Path) -> dict:
    result = {
        "vnext": {"found": False, "details": {}},
        "kb": {"found": False, "details": {}},
        "summary": [],
    }

    project_root = vnext_project_root(root)
    if project_root is not None:
        vnext_root = project_root / ".kb-next"
        result["vnext"]["found"] = True
        details = result["vnext"]["details"]
        details["vnext_root"] = str(vnext_root.resolve())
        # Runtime commands take `--project-root <project_root>`, which differs
        # from the workspace in a worktree activated only in its main checkout.
        details["project_root"] = str(project_root.resolve())
        details["activation"] = "workspace" if project_root == root else "main_checkout"
        details["config_json"] = (vnext_root / "kb-next.config.json").is_file()
        details["now_md"] = (vnext_root / "memory" / "NOW.md").is_file()
        details["operations_jsonl"] = (vnext_root / "operations.jsonl").is_file()
        details["runtime_ref"] = _resolve_reference(
            project_root,
            ".kb-next/runtime/kb_next.py",
            "core/versions/kb-wiki-vnext/runtime/kb_next.py",
            "runtime/kb_next.py",
        )
        details["session_command_ref"] = _resolve_reference(
            root, "plugins/kb-wiki-vnext/commands/vnext-session-start.md"
        )
        result["summary"].append(
            "KB/Wiki vNext detected (.kb-next/ present)"
            if project_root == root
            else f"KB/Wiki vNext detected in the main checkout {project_root.resolve()}"
        )

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
