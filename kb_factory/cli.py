"""`kb-factory` console entry point: scaffold and update a project's `.kb/`.

`init`   — copy the vendored scaffold into <project>/.kb and initialize the store.
`update` — refresh only the engine (`kb.py` + `runtime/`) in an existing `.kb/`,
           leaving your data (`kb.db`, `memory/`, `exports/`, `kb.config.json`)
           untouched. This is how core fixes propagate to projects that were
           scaffolded from an older version.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__

SCAFFOLD = Path(__file__).resolve().parent / "_scaffold"
# Engine files refreshed by `update`; everything else in .kb/ is project data.
ENGINE = ("kb.py", "runtime")
VERSION_MARKER = ".kb-version"


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src, dst, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "kb.db"),
    )


def _copy_item(name: str, dest: Path) -> None:
    src = SCAFFOLD / name
    target = dest / name
    if src.is_dir():
        if target.exists():
            shutil.rmtree(target)
        _copy_tree(src, target)
    elif src.is_file():
        shutil.copy2(src, target)


def cmd_init(args: argparse.Namespace) -> int:
    if not SCAFFOLD.is_dir():
        print("packaged scaffold is missing; reinstall kb-factory", file=sys.stderr)
        return 1
    dest = Path(args.path).resolve() / ".kb"
    if dest.exists() and not args.force:
        print(f"refusing to overwrite existing {dest} (pass --force)", file=sys.stderr)
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    for item in sorted(SCAFFOLD.iterdir()):
        if item.name == "__pycache__":
            continue
        _copy_item(item.name, dest)
    (dest / VERSION_MARKER).write_text(__version__ + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(dest / "kb.py"), "init"], cwd=str(dest), check=True)
    print(f"Initialized KB Factory {__version__} at {dest}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    dest = Path(args.path).resolve() / ".kb"
    if not (dest / "kb.py").exists():
        print(f"no .kb/ found at {dest} — run `kb-factory init` first", file=sys.stderr)
        return 1
    for name in ENGINE:
        _copy_item(name, dest)
    (dest / VERSION_MARKER).write_text(__version__ + "\n", encoding="utf-8")
    print(
        f"Updated the .kb/ runtime at {dest} to {__version__}. "
        "Your data (kb.db, memory/, exports/, kb.config.json) was left untouched."
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kb-factory", description="KB Factory installer / CLI")
    parser.add_argument("--version", action="version", version=f"kb-factory {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Scaffold a .kb/ into a project and initialize it")
    init_p.add_argument("path", nargs="?", default=".", help="project directory (default: cwd)")
    init_p.add_argument("--force", action="store_true", help="overwrite an existing .kb/")
    init_p.set_defaults(func=cmd_init)

    update_p = sub.add_parser("update", help="Refresh the .kb/ engine to this version (keeps data)")
    update_p.add_argument("path", nargs="?", default=".", help="project directory (default: cwd)")
    update_p.set_defaults(func=cmd_update)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
