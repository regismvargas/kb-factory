from __future__ import annotations

import json
import os
from pathlib import Path


# Directory that holds this runtime (the `.kb/` the invoked kb.py lives in).
RUNTIME_KB_ROOT = Path(__file__).resolve().parent.parent
WORKTREE_SCOPE_ENV = "KB_FACTORY_WORKTREE_SCOPE"
WORKTREE_SCOPES = ("shared", "local")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        return None


def linked_worktree_main_root(project_root: Path) -> Path | None:
    """Return the main worktree root when ``project_root`` is a linked Git worktree.

    A linked worktree carries a `.git` file (`gitdir: <common>/worktrees/<name>`)
    whose gitdir holds a `commondir` file pointing back at the shared `.git`
    directory; this is the data `git rev-parse --git-common-dir` reports. A
    submodule also uses a `.git` file but has no `commondir`, so it never
    matches. Pure file reads keep the lookup fast and independent of a `git`
    executable.
    """
    dotgit = project_root / ".git"
    if not dotgit.is_file():
        return None
    text = _read_text(dotgit)
    if not text or not text.lower().startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = project_root / gitdir
    common_text = _read_text(gitdir / "commondir")
    if not common_text:
        return None
    common = Path(common_text)
    if not common.is_absolute():
        common = gitdir / common
    try:
        common = common.resolve()
        if common.name != ".git" or not common.is_dir():
            return None
        main_root = common.parent
        if main_root.resolve() == project_root.resolve():
            return None
    except OSError:
        return None
    return main_root


def worktree_scope(local_kb_root: Path) -> str:
    """`shared` (default) or `local`, from the environment or kb.config.json."""
    env_value = os.environ.get(WORKTREE_SCOPE_ENV, "").strip().lower()
    if env_value in WORKTREE_SCOPES:
        return env_value
    config_text = _read_text(local_kb_root / "kb.config.json")
    if config_text:
        try:
            storage = json.loads(config_text).get("storage")
        except (ValueError, AttributeError):
            storage = None
        if isinstance(storage, dict):
            value = str(storage.get("worktree_scope", "")).strip().lower()
            if value in WORKTREE_SCOPES:
                return value
    return "shared"


def resolve_kb_root(local_kb_root: Path = RUNTIME_KB_ROOT) -> tuple[Path, dict]:
    """Resolve the KB a command operates on.

    In a linked Git worktree (for example a per-session desktop worktree) the
    project KB is the one in the main worktree: every session reads and writes
    that single database instead of a divergent per-branch copy. The redirect
    applies only to a `.kb/` at the worktree root and only when the main
    worktree already has a `kb.db`.
    """
    info = {
        "runtime_kb_root": str(local_kb_root),
        "resolution": "local",
        "main_worktree_root": None,
        "worktree_scope": None,
        "shadowed_local_db": False,
    }
    main_root = linked_worktree_main_root(local_kb_root.parent)
    if main_root is None:
        return local_kb_root, info
    scope = worktree_scope(local_kb_root)
    info["main_worktree_root"] = str(main_root)
    info["worktree_scope"] = scope
    candidate = main_root / local_kb_root.name
    if scope == "shared" and (candidate / "kb.db").is_file():
        info["resolution"] = "main_worktree"
        info["shadowed_local_db"] = (local_kb_root / "kb.db").is_file()
        return candidate, info
    info["resolution"] = "local_worktree"
    return local_kb_root, info


KB_ROOT, KB_ROOT_INFO = resolve_kb_root()
CONFIG_PATH = KB_ROOT / "kb.config.json"
DB_PATH = KB_ROOT / "kb.db"


def missing_db_message() -> str:
    lines = [f"KB database not found: {DB_PATH}"]
    main_root = KB_ROOT_INFO.get("main_worktree_root")
    if main_root:
        if KB_ROOT_INFO.get("worktree_scope") == "local":
            lines.append(
                f"This checkout is a linked Git worktree of {main_root} and "
                "worktree_scope=local keeps a separate KB for it."
            )
        else:
            lines.append(
                f"This checkout is a linked Git worktree of {main_root}, whose "
                ".kb/kb.db is missing as well."
            )
    lines.append(
        "No command creates an empty KB implicitly. Restore the project's kb.db, "
        f"or run `python {RUNTIME_KB_ROOT / 'kb.py'} init` to create a new KB on purpose."
    )
    return "\n".join(lines)


def memory_path(relative_path: str) -> Path:
    return KB_ROOT / relative_path


def ensure_dirs(config: dict) -> None:
    memory = config["memory"]
    exports = config["exports"]
    for rel in (
        "seed",
        Path(memory["topics_dir"]).as_posix(),
        Path(memory.get("now_path", "memory/NOW.md")).parent.as_posix(),
        Path(memory["index_path"]).parent.as_posix(),
        Path(memory["hot_path"]).parent.as_posix(),
        Path(exports["cowork_dir"]).as_posix(),
        Path(exports["claude_ai_dir"]).as_posix(),
    ):
        (KB_ROOT / rel).mkdir(parents=True, exist_ok=True)
    if "wiki" in config:
        for wiki_rel in ("wiki/live", "wiki/snapshots", "wiki/mkdocs"):
            (KB_ROOT / wiki_rel).mkdir(parents=True, exist_ok=True)
