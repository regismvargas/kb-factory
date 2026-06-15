"""Build the KB/Wiki vNext stand-alone RC bundle.

The stand-alone bundle is intentionally a product package, not a canonical
workspace snapshot. It includes the vNext runtime, the minimum classic `.kb`
template needed by new workspaces, plugin source, product docs, and validation
tools. It excludes mutable workspace state and generated caches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VERSION = "0.2.0-rc.1"
PRODUCT_DIR = Path("products/kb-wiki-vnext")
DEFAULT_OUTPUT_DIR = Path("dist/vnext")

FORBIDDEN_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "state",
    "runs",
    "worktrees",
}

FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".db-shm",
    ".db-wal",
}


@dataclass(frozen=True)
class BundleEntry:
    source: Path
    archive_path: Path
    is_tree: bool = False


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_forbidden_source(path: Path) -> bool:
    parts = set(path.parts)
    if parts & FORBIDDEN_PARTS:
        return True
    if path.name.startswith(".pytest_tmp"):
        return True
    if path.suffix in FORBIDDEN_SUFFIXES:
        return True
    normalized = path.as_posix()
    if "/.kb/wiki/live/" in normalized:
        return True
    if "/state/runs/" in normalized:
        return True
    return False


def _iter_tree_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if path.is_file() and not _is_forbidden_source(path):
            files.append(path)
    return files


def _add_file(zf: zipfile.ZipFile, source: Path, archive_path: Path) -> str:
    if not source.exists():
        raise FileNotFoundError(source)
    zf.write(source, archive_path.as_posix())
    return archive_path.as_posix()


def _write_manifest(
    zf: zipfile.ZipFile,
    *,
    bundle_root: str,
    version: str,
    entries: list[str],
    agent_package_result: dict[str, object],
) -> None:
    manifest = {
        "product": "kb-wiki-vnext",
        "version": version,
        "bundle_type": "standalone",
        "authority_limits": {
            "canonical_memory": ".kb/",
            "vnext_memory": ".kb-next/",
            "canonical_mutation_bridge": "proposal-apply via .kb/kb.py",
            "direct_kb_db_mutation": False,
            "publishes_kb_wiki_live": False,
        },
        "included_paths": entries,
        "agent_package_build": agent_package_result,
    }
    zf.writestr(
        f"{bundle_root}/bundle-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )


def build_agent_packages(root: Path) -> dict[str, object]:
    script = root / "tools" / "build_agent_packages.py"
    result = subprocess.run(
        [sys.executable, str(script), "--scope", "vnext"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return {
        "command": "python tools/build_agent_packages.py --scope vnext",
        "returncode": result.returncode,
        "stdout": result.stdout.strip().splitlines(),
    }


def bundle_entries(root: Path, version: str) -> list[BundleEntry]:
    bundle_root = Path(f"kb-wiki-vnext-{version}")
    return [
        BundleEntry(root / PRODUCT_DIR, bundle_root / "product", True),
        BundleEntry(root / "plugins" / "kb-wiki-vnext", bundle_root / "plugin", True),
        BundleEntry(
            root / "core" / "versions" / "kb-wiki-vnext" / "spec-pack",
            bundle_root / "spec-pack",
            True,
        ),
        BundleEntry(
            root / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py",
            bundle_root / "runtime" / "kb_next.py",
        ),
        BundleEntry(
            root / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "README.md",
            bundle_root / "runtime" / "README.md",
        ),
        BundleEntry(
            root / "core" / "templates" / "kb",
            bundle_root / "classic-template" / ".kb",
            True,
        ),
        BundleEntry(root / PRODUCT_DIR / "README.md", bundle_root / "README.md"),
        BundleEntry(root / "docs" / "INSTALL.md", bundle_root / "docs" / "INSTALL.md"),
        BundleEntry(
            root / "tools" / "validate_vnext_product.py",
            bundle_root / "tools" / "validate_vnext_product.py",
        ),
        BundleEntry(
            root / "tools" / "cleanup_vnext_workbench.py",
            bundle_root / "tools" / "cleanup_vnext_workbench.py",
        ),
        BundleEntry(
            root / "tools" / "build_vnext_standalone.py",
            bundle_root / "tools" / "build_vnext_standalone.py",
        ),
        BundleEntry(
            root / "tools" / "validate_kb_wiki_vnext_spec_pack.py",
            bundle_root / "tools" / "validate_kb_wiki_vnext_spec_pack.py",
        ),
    ]


def build_standalone(version: str, output_dir: Path, skip_agent_packages: bool = False) -> Path:
    root = repo_root()
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    agent_result: dict[str, object]
    if skip_agent_packages:
        agent_result = {"skipped": True}
    else:
        agent_result = build_agent_packages(root)

    zip_path = output_dir / f"kb-wiki-vnext-{version}-standalone.zip"
    bundle_root = f"kb-wiki-vnext-{version}"
    included: list[str] = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in bundle_entries(root, version):
            if entry.is_tree:
                for source_file in _iter_tree_files(entry.source):
                    relative = source_file.relative_to(entry.source)
                    archive_path = entry.archive_path / relative
                    included.append(_add_file(zf, source_file, archive_path))
            else:
                included.append(_add_file(zf, entry.source, entry.archive_path))

        _write_manifest(
            zf,
            bundle_root=bundle_root,
            version=version,
            entries=sorted(included),
            agent_package_result=agent_result,
        )

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    digest_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    digest_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--skip-agent-packages",
        action="store_true",
        help="Build only the stand-alone ZIP. Tests use this to avoid redundant package rebuilds.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    zip_path = build_standalone(args.version, args.output_dir, args.skip_agent_packages)
    print(zip_path)
    print(zip_path.with_suffix(zip_path.suffix + ".sha256"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
