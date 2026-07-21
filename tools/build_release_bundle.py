"""Build the selective, hash-bound release bundle for KB Factory v0.3.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PRIVATE_SOURCE_SHA = "194f235318709189011bd15e0bec145887253403"
PUBLIC_BASELINE_SHA = "af865b6aff95852d6fc1dc090055cbbc0a85f977"
PLAN_PACKAGE_SHA256 = "cdc4020fcf2e1d9c9d50b27d2ea0bb7653f7a059a1aa18c5e78cfe52d0a4b419"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def release_inputs(version: str) -> tuple[tuple[str, Path], ...]:
    root = repo_root()
    agent = root / "dist" / "agent-packages"
    return (
        ("codex", agent / f"kb-lifecycle-plugin-{version}.zip"),
        ("claude-code", agent / f"kb-lifecycle-claude-plugin-{version}.zip"),
        ("claude-cowork", agent / f"kb-lifecycle-cowork-plugin-{version}.zip"),
        ("codex", agent / f"kb-wiki-vnext-plugin-{version}.zip"),
        ("claude-code", agent / f"kb-wiki-vnext-claude-plugin-{version}.zip"),
        ("claude-cowork", agent / f"kb-wiki-vnext-cowork-plugin-{version}.zip"),
        ("standalone", root / "dist" / "vnext" / f"kb-wiki-vnext-{version}-standalone.zip"),
        ("python", root / "dist" / f"kb_factory-{version}-py3-none-any.whl"),
        ("python", root / "dist" / f"kb_factory-{version}.tar.gz"),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_bundle(
    *,
    version: str,
    public_candidate_sha: str,
    source_date_epoch: int,
    output_dir: Path,
) -> tuple[Path, ...]:
    if version != "0.3.0":
        raise ValueError("this selective release contract is bound to version 0.3.0")
    if len(public_candidate_sha) != 40 or any(
        character not in "0123456789abcdef" for character in public_candidate_sha.lower()
    ):
        raise ValueError("public candidate SHA must be a 40-character hexadecimal commit")
    if source_date_epoch < 0:
        raise ValueError("source date epoch must be non-negative")

    inputs = release_inputs(version)
    missing = [str(path) for _, path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing release inputs: " + ", ".join(missing))

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {path.name for _, path in inputs}
    expected_names.update(
        {
            f"kb-factory-v{version}-manifest.json",
            f"kb-factory-v{version}-provenance.json",
            "SHA256SUMS.txt",
        }
    )
    for existing in output_dir.iterdir():
        if existing.is_file() and existing.name not in expected_names:
            existing.unlink()

    assets: list[dict[str, object]] = []
    copied: list[Path] = []
    for platform, source in inputs:
        destination = output_dir / source.name
        shutil.copyfile(source, destination)
        copied.append(destination)
        assets.append(
            {
                "name": destination.name,
                "platform": platform,
                "sha256": sha256(destination),
                "size": destination.stat().st_size,
            }
        )

    manifest_path = output_dir / f"kb-factory-v{version}-manifest.json"
    write_json(
        manifest_path,
        {
            "assets": assets,
            "release": version,
            "selection": {
                "plugin_assets": 6,
                "python_assets": 2,
                "session_gate_assets": 0,
                "standalone_assets": 1,
            },
        },
    )

    provenance_path = output_dir / f"kb-factory-v{version}-provenance.json"
    created_at = datetime.fromtimestamp(source_date_epoch, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    write_json(
        provenance_path,
        {
            "build": {
                "created_at": created_at,
                "source_date_epoch": source_date_epoch,
            },
            "plan_package_sha256": PLAN_PACKAGE_SHA256,
            "private_source_sha": PRIVATE_SOURCE_SHA,
            "public_baseline_sha": PUBLIC_BASELINE_SHA,
            "public_candidate_sha": public_candidate_sha.lower(),
            "release": version,
            "release_route": "private-clean -> hash-bound-export -> public-clean",
            "session_gate": {
                "asset_published": False,
                "version": "0.2.7",
            },
        },
    )

    checksum_paths = sorted((*copied, manifest_path, provenance_path), key=lambda path: path.name)
    checksums_path = output_dir / "SHA256SUMS.txt"
    checksums_path.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_paths),
        encoding="ascii",
        newline="\n",
    )
    return tuple((*copied, manifest_path, provenance_path, checksums_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="0.3.0")
    parser.add_argument("--public-candidate-sha", required=True)
    parser.add_argument("--source-date-epoch", required=True, type=int)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root() / "dist" / "release" / "kb-factory-v0.3.0",
    )
    args = parser.parse_args()
    paths = build_bundle(
        version=args.version,
        public_candidate_sha=args.public_candidate_sha,
        source_date_epoch=args.source_date_epoch,
        output_dir=args.output_dir,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
