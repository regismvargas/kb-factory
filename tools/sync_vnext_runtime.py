"""Sync the vNext runtime engine (``kb_next.py``) from its single master.

The master ``core/versions/kb-wiki-vnext/runtime/kb_next.py`` is the only
hand-edited copy. The default ``source`` scope validates only mirrors tracked in
the private source checkout, so ``tools/gate.py`` and CI are hermetic. The
explicit ``release`` and ``all`` scopes validate a caller-supplied clean public
checkout and fail closed when ``--release-root`` is absent.

The plugin ZIP is intentionally not a mirror: ``build_agent_packages.py``
injects the master at build time, so that channel is drift-proof by
construction and needs no committed copy.

Usage: python tools/sync_vnext_runtime.py --check [--scope source|release|all]
              [--release-root PATH]
       python tools/sync_vnext_runtime.py --scope source|release|all
              [--release-root PATH]

``--check`` exits non-zero if any selected mirror is stale or missing without
writing. Check mode defaults to ``source``. Write mode requires an explicit
scope so a historical no-argument invocation cannot silently skip release
mirrors. ``release`` and ``all`` require an explicit public worktree. No local
``oss-release/`` staging directory is inferred or treated as release evidence.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
# Mirrors committed in the private source checkout.
SOURCE_MIRRORS = [
    REPO / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py",
]

# Mirrors committed in the separately materialized clean public checkout.
RELEASE_MIRROR_PATHS = [
    Path("core/versions/kb-wiki-vnext/runtime/kb_next.py"),
    Path("kb_factory/_scaffold_vnext/runtime/kb_next.py"),
    Path("plugins/kb-wiki-vnext/runtime/kb_next.py"),
]

SCOPES = ("source", "release", "all")


def mirrors_for_scope(scope: str, release_root: Path | None = None) -> list[Path]:
    if scope == "source":
        return list(SOURCE_MIRRORS)
    release_mirrors = (
        [release_root / relative for relative in RELEASE_MIRROR_PATHS]
        if release_root is not None
        else []
    )
    if scope == "release":
        return release_mirrors
    if scope == "all":
        return [*SOURCE_MIRRORS, *release_mirrors]
    raise ValueError(f"unknown scope: {scope}")


def _require_release_root(scope: str, release_root: Path | None) -> None:
    if scope in {"release", "all"} and release_root is None:
        raise FileNotFoundError(
            "release scope requires an explicit public checkout via --release-root"
        )
    if scope in {"release", "all"} and not release_root.is_dir():
        raise FileNotFoundError(f"public release checkout does not exist: {release_root}")


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _mirror_safety_error(mirror: Path, release_root: Path | None = None) -> str | None:
    expected_root = (
        release_root
        if release_root is not None and mirror.is_relative_to(release_root)
        else REPO
    )
    if release_root is not None and expected_root == release_root and _is_link_or_junction(expected_root):
        return f"release root is a symlink or junction: {expected_root}"
    try:
        relative = mirror.relative_to(expected_root)
    except ValueError:
        return f"mirror escapes its declared root: {mirror}"
    cursor = expected_root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.exists() and _is_link_or_junction(cursor):
            return f"mirror path contains a symlink or junction: {cursor}"
    try:
        mirror.resolve(strict=False).relative_to(expected_root.resolve())
    except ValueError:
        return f"mirror resolves outside its declared root: {mirror}"
    return None


def stale_mirrors(
    scope: str = "source", release_root: Path | None = None
) -> list[str]:
    if not MASTER.is_file():
        return [f"<master missing: {MASTER}>"]
    try:
        _require_release_root(scope, release_root)
    except FileNotFoundError as exc:
        return [str(exc)]
    problems: list[str] = []
    for mirror in mirrors_for_scope(scope, release_root):
        safety_error = _mirror_safety_error(mirror, release_root)
        if safety_error:
            problems.append(f"{mirror} <unsafe: {safety_error}>")
        elif not mirror.is_file():
            problems.append(f"{mirror} <missing>")
        elif not filecmp.cmp(MASTER, mirror, shallow=False):
            problems.append(f"{mirror} <drift>")
    return problems


def regenerate(scope: str = "source", release_root: Path | None = None) -> None:
    _require_release_root(scope, release_root)
    for mirror in mirrors_for_scope(scope, release_root):
        safety_error = _mirror_safety_error(mirror, release_root)
        if safety_error:
            raise RuntimeError(safety_error)
        mirror.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MASTER, mirror)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sync vNext runtime mirrors from the master")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        help="mirror set to validate or regenerate (check default: source; write required)",
    )
    parser.add_argument(
        "--release-root",
        type=Path,
        help="clean public checkout used by release/all scopes",
    )
    args = parser.parse_args(argv)
    scope = args.scope or ("source" if args.check else None)
    if scope is None:
        parser.error("write mode requires explicit --scope source|release|all")
    if args.check:
        release_root = args.release_root.resolve() if args.release_root else None
        problems = stale_mirrors(scope, release_root)
        if not problems:
            count = len(mirrors_for_scope(scope, release_root))
            print(
                f"vNext runtime {scope} mirrors in sync with master "
                f"({count} mirror(s))"
            )
            return 0
        release_hint = " --release-root PATH" if scope in {"release", "all"} else ""
        print(
            f"STALE ({scope}) - re-run "
            f"`python tools/sync_vnext_runtime.py --scope {scope}{release_hint}`:\n  "
            + "\n  ".join(problems),
            file=sys.stderr,
        )
        return 1
    try:
        release_root = args.release_root.resolve() if args.release_root else None
        regenerate(scope, release_root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Cannot sync {scope} mirrors: {exc}", file=sys.stderr)
        return 1
    count = len(mirrors_for_scope(scope, release_root))
    print(f"Synced {count} vNext runtime {scope} mirror(s) from {MASTER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
