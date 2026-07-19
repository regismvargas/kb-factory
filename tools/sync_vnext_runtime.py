#!/usr/bin/env python3
"""Synchronize the KB/Wiki vNext runtime mirrors from the source master.

The authoring runtime is the sole source of truth. The plugin and pip
scaffold copies are release mirrors and must remain byte-identical.
"""
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MASTER_REL = Path("core/versions/kb-wiki-vnext/runtime/kb_next.py")
MIRROR_RELS = (
    Path("plugins/kb-wiki-vnext/runtime/kb_next.py"),
    Path("kb_factory/_scaffold_vnext/runtime/kb_next.py"),
)


def runtime_mirror_drift(root: Path) -> list[str]:
    """Return deterministic descriptions of mirrors that differ from master."""
    master = root / MASTER_REL
    if not master.is_file():
        return [f"master runtime not found: {MASTER_REL.as_posix()}"]

    master_bytes = master.read_bytes()
    drift: list[str] = []
    for relative in MIRROR_RELS:
        mirror = root / relative
        if not mirror.is_file():
            drift.append(f"mirror runtime not found: {relative.as_posix()}")
        elif mirror.read_bytes() != master_bytes:
            drift.append(f"runtime drift: {relative.as_posix()}")
    return drift


def sync_runtime_mirrors(root: Path) -> list[str]:
    """Write the two release mirrors from the master and return changed paths."""
    master = root / MASTER_REL
    if not master.is_file():
        raise FileNotFoundError(f"master runtime not found: {master}")

    master_bytes = master.read_bytes()
    changed: list[str] = []
    for relative in MIRROR_RELS:
        mirror = root / relative
        if not mirror.is_file() or mirror.read_bytes() != master_bytes:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_bytes(master_bytes)
            changed.append(relative.as_posix())
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify mirrors without writing; exits non-zero when drift exists",
    )
    args = parser.parse_args(argv)

    if args.check:
        drift = runtime_mirror_drift(ROOT)
        if drift:
            print("KB/Wiki vNext runtime mirror check FAILED:")
            for item in drift:
                print(f"  - {item}")
            return 1
        print("KB/Wiki vNext runtime mirrors are synchronized.")
        return 0

    changed = sync_runtime_mirrors(ROOT)
    if changed:
        print("Synchronized KB/Wiki vNext runtime mirrors:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("KB/Wiki vNext runtime mirrors already synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
