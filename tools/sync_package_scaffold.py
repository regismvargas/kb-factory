"""Regenerate `kb_factory/_scaffold/` from the canonical `core/templates/kb/`.

`kb_factory/_scaffold/` is a GENERATED mirror of the scaffold template, bundled
into the pip wheel so `kb-factory init` works offline. It must never be edited
by hand — edit `core/templates/kb/` and re-run this tool. `tests/test_packaging.py`
asserts the two stay identical, so drift is caught in CI (the same governed-mirror
discipline used for `core/runtime` ↔ `core/templates/kb/runtime`).

Usage:  python tools/sync_package_scaffold.py [--check]
  --check : exit non-zero if the mirror is stale (does not write)
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "core" / "templates" / "kb"
MIRROR = REPO / "kb_factory" / "_scaffold"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "kb.db")


def _relevant_files(root: Path) -> set[str]:
    files = set()
    for p in root.rglob("*"):
        if p.is_dir() or "__pycache__" in p.parts or p.suffix == ".pyc" or p.name == "kb.db":
            continue
        files.add(str(p.relative_to(root)).replace("\\", "/"))
    return files


def is_in_sync() -> tuple[bool, list[str]]:
    if not MIRROR.exists():
        return False, ["<mirror missing>"]
    src_files = _relevant_files(SOURCE)
    mir_files = _relevant_files(MIRROR)
    diffs = sorted(src_files ^ mir_files)
    for rel in sorted(src_files & mir_files):
        if not filecmp.cmp(SOURCE / rel, MIRROR / rel, shallow=False):
            diffs.append(rel)
    return (not diffs), diffs


def regenerate() -> None:
    if MIRROR.exists():
        shutil.rmtree(MIRROR)
    shutil.copytree(SOURCE, MIRROR, ignore=IGNORE)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sync the packaged scaffold mirror")
    parser.add_argument("--check", action="store_true", help="report staleness without writing")
    args = parser.parse_args(argv)
    if args.check:
        ok, diffs = is_in_sync()
        if ok:
            print("kb_factory/_scaffold is in sync with core/templates/kb")
            return 0
        print("STALE — differs at:\n  " + "\n  ".join(diffs), file=sys.stderr)
        return 1
    regenerate()
    print(f"Regenerated {MIRROR} from {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
