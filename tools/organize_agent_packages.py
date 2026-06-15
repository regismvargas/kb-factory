"""Organize current agent package ZIPs by platform and version.

The flat ``dist/agent-packages`` directory remains the canonical build output
for compatibility with existing docs, tests, and manual workflows. This helper
creates a read-friendly mirror:

    dist/agent-packages/by-platform/<platform>/<version>/<artifact>.zip
    dist/agent-packages/by-platform/<platform>/latest/<artifact>.zip

It copies only uploadable plugin ZIPs by default. Standalone skill ZIPs and
historical/test artifacts stay in the flat directory unless ``--mode all`` is
used with matching plugin package names. With ``--archive-legacy``, recognized
non-current plugin ZIPs are moved out of the flat directory into:

    dist/agent-packages/legacy/<platform>/<version>/<artifact>.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


VERSION_PATTERN = r"(?P<version>[0-9][A-Za-z0-9.+-]*)"
SKILL_PATTERN = re.compile(rf"^(?P<plugin>.+)-skill-{VERSION_PATTERN}\.zip$")
CASE_STANDALONE_SKILLS: tuple[str, ...] = (
    "case-adoption-audit",
    "case-resync",
    "case-rollout",
    "case-runtime-sync",
    "kb-audit",
    "kb-init",
    "kb-sync",
)
PACKAGE_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(rf"^(?P<plugin>.+)-claude-plugin-{VERSION_PATTERN}\.zip$"),
        "claude-code",
        "claude-plugin",
    ),
    (
        re.compile(rf"^(?P<plugin>.+)-cowork-plugin-{VERSION_PATTERN}\.zip$"),
        "claude-cowork",
        "cowork-plugin",
    ),
    (
        re.compile(rf"^(?P<plugin>.+)-plugin-{VERSION_PATTERN}\.zip$"),
        "codex",
        "codex-plugin",
    ),
)


@dataclass(frozen=True)
class PackageName:
    plugin: str
    platform: str
    package_kind: str
    version: str


@dataclass(frozen=True)
class OrganizedArtifact:
    platform: str
    plugin: str
    version: str
    package_kind: str
    source: str
    path: str
    latest_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class LegacyArtifact:
    platform: str
    plugin: str
    version: str
    package_kind: str
    original: str
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class OrganizationResult:
    source_dir: str
    output_dir: str
    legacy_dir: str
    mode: str
    check: bool
    artifacts: list[OrganizedArtifact]
    legacy_artifacts: list[LegacyArtifact]
    skipped: list[str]
    missing: list[str]
    errors: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_agent_package_name(name: str) -> PackageName | None:
    for pattern, platform, package_kind in PACKAGE_PATTERNS:
        match = pattern.match(name)
        if match:
            return PackageName(
                plugin=match.group("plugin"),
                platform=platform,
                package_kind=package_kind,
                version=match.group("version"),
            )
    return None


def parse_standalone_skill_name(name: str) -> PackageName | None:
    match = SKILL_PATTERN.match(name)
    if not match:
        return None
    return PackageName(
        plugin=match.group("plugin"),
        platform="standalone-skill",
        package_kind="skill",
        version=match.group("version"),
    )


def parse_unclassified_zip_name(name: str) -> PackageName:
    stem = Path(name).stem
    version_match = re.search(r"([0-9]+(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.]+)?)$", stem)
    version = version_match.group(1) if version_match else "unknown"
    return PackageName(
        plugin=stem,
        platform="unclassified",
        package_kind="unclassified",
        version=version,
    )


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def expected_current_plugin_archives(root: Path) -> set[str]:
    expected: set[str] = set()
    for plugin_root in sorted((root / "plugins").glob("*")):
        if not plugin_root.is_dir():
            continue
        codex_manifest = _load_manifest(plugin_root / ".codex-plugin" / "plugin.json")
        claude_manifest = _load_manifest(plugin_root / ".claude-plugin" / "plugin.json")

        if codex_manifest is not None:
            name = str(codex_manifest.get("name") or plugin_root.name)
            version = str(codex_manifest.get("version") or "0.0.0")
            expected.add(f"{name}-plugin-{version}.zip")

        if claude_manifest is not None:
            name = str(claude_manifest.get("name") or plugin_root.name)
            version = str(claude_manifest.get("version") or "0.0.0")
            expected.add(f"{name}-claude-plugin-{version}.zip")
            expected.add(f"{name}-cowork-plugin-{version}.zip")

    return expected


def expected_current_standalone_archives(root: Path, source_dir: Path) -> set[str]:
    expected: set[str] = set()
    kb_manifest = _load_manifest(root / "plugins" / "kb-lifecycle" / ".claude-plugin" / "plugin.json")
    if kb_manifest is not None:
        expected.add(f"kb-wiki-maintainer-skill-{kb_manifest.get('version', '0.0.0')}.zip")

    session_gate_manifest = _load_manifest(
        root / "plugins" / "session-gate" / ".claude-plugin" / "plugin.json"
    )
    if session_gate_manifest is not None:
        expected.add(f"session-gate-skill-{session_gate_manifest.get('version', '0.0.0')}.zip")

    for skill_name in CASE_STANDALONE_SKILLS:
        versions = [
            parsed.version
            for path in source_dir.glob(f"{skill_name}-skill-*.zip")
            for parsed in [parse_standalone_skill_name(path.name)]
            if parsed is not None
        ]
        if versions:
            expected.add(f"{skill_name}-skill-{sorted(versions)[-1]}.zip")

    return expected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _reset_latest_dirs(output_dir: Path) -> None:
    for platform in ("codex", "claude-code", "claude-cowork"):
        latest_dir = output_dir / platform / "latest"
        if not latest_dir.exists():
            continue
        resolved = latest_dir.resolve()
        expected_parent = (output_dir / platform).resolve()
        if resolved.name != "latest" or resolved.parent != expected_parent:
            raise ValueError(f"Refusing to clear unexpected latest path: {latest_dir}")
        shutil.rmtree(resolved)


def _collect_legacy_artifacts(legacy_dir: Path, root: Path) -> list[LegacyArtifact]:
    artifacts: list[LegacyArtifact] = []
    if not legacy_dir.exists():
        return artifacts
    for path in sorted(legacy_dir.rglob("*.zip")):
        package = parse_agent_package_name(path.name)
        if package is None:
            package = parse_standalone_skill_name(path.name)
        if package is None:
            package = parse_unclassified_zip_name(path.name)
        if package is None:
            continue
        artifacts.append(
            LegacyArtifact(
                platform=package.platform,
                plugin=package.plugin,
                version=package.version,
                package_kind=package.package_kind,
                original="",
                path=_display(path, root),
                size=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return artifacts


def _candidate_names(
    source_dir: Path,
    root: Path,
    mode: str,
    expected_names: set[str] | None,
) -> tuple[list[str], list[str], list[str]]:
    skipped: list[str] = []
    missing: list[str] = []

    if mode == "current":
        names = sorted(expected_names or expected_current_plugin_archives(root))
        present_names: list[str] = []
        for name in names:
            package = parse_agent_package_name(name)
            if package is None:
                skipped.append(name)
                continue
            if (source_dir / name).exists():
                present_names.append(name)
            else:
                missing.append(name)
        return present_names, skipped, missing

    present_names = []
    for path in sorted(source_dir.glob("*.zip")):
        if parse_agent_package_name(path.name) is None:
            skipped.append(path.name)
        else:
            present_names.append(path.name)
    return present_names, skipped, missing


def _write_manifest_and_readme(
    result: OrganizationResult,
    output_dir: Path,
    root: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_dir": result.source_dir,
        "output_dir": result.output_dir,
        "legacy_dir": result.legacy_dir,
        "mode": result.mode,
        "platforms": ["codex", "claude-code", "claude-cowork"],
        "artifacts": [asdict(artifact) for artifact in result.artifacts],
        "legacy_artifacts": [asdict(artifact) for artifact in result.legacy_artifacts],
        "skipped": result.skipped,
        "missing": result.missing,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Agent Packages By Platform",
        "",
        f"Generated from `{result.source_dir}`.",
        "",
        "The flat `dist/agent-packages` directory remains the canonical build output.",
        "This directory is a copied mirror for human-friendly installation and review.",
        "",
        "Use each platform's `latest/` directory when you do not need a specific",
        "component version.",
        "",
        "| Platform | Version | Plugin | Versioned ZIP | Latest ZIP | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]
    for artifact in sorted(
        result.artifacts,
        key=lambda item: (item.platform, item.version, item.plugin, item.path),
    ):
        lines.append(
            f"| {artifact.platform} | {artifact.version} | {artifact.plugin} | "
            f"`{artifact.path}` | `{artifact.latest_path}` | `{artifact.sha256}` |"
        )
    if result.legacy_artifacts:
        lines.extend(["", "## Legacy Plugin Artifacts", ""])
        lines.append("| Platform | Version | Plugin | ZIP | SHA-256 |")
        lines.append("|---|---|---|---|---|")
        for artifact in sorted(
            result.legacy_artifacts,
            key=lambda item: (item.platform, item.version, item.plugin, item.path),
        ):
            lines.append(
                f"| {artifact.platform} | {artifact.version} | {artifact.plugin} | "
                f"`{artifact.path}` | `{artifact.sha256}` |"
            )
    if result.missing:
        lines.extend(["", "## Missing Expected Current Artifacts", ""])
        lines.extend(f"- `{name}`" for name in result.missing)
    if result.skipped:
        lines.extend(["", "## Skipped", ""])
        lines.extend(f"- `{name}`" for name in result.skipped)

    readme_path = output_dir / "README.md"
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Make linters happy if this function is used with an absolute output path.
    _display(readme_path, root)


def organize_agent_packages(
    source_dir: Path,
    output_dir: Path,
    *,
    root: Path | None = None,
    legacy_dir: Path | None = None,
    mode: str = "current",
    check: bool = False,
    archive_legacy: bool = False,
    expected_names: set[str] | None = None,
) -> OrganizationResult:
    root = (root or repo_root()).resolve()
    source_dir = source_dir if source_dir.is_absolute() else root / source_dir
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    legacy_dir = legacy_dir or source_dir / "legacy"
    legacy_dir = legacy_dir if legacy_dir.is_absolute() else root / legacy_dir

    artifacts: list[OrganizedArtifact] = []
    legacy_artifacts: list[LegacyArtifact] = []
    errors: list[str] = []
    names, skipped, missing = _candidate_names(source_dir, root, mode, expected_names)
    expected_current = expected_names or expected_current_plugin_archives(root)
    expected_standalone = expected_current_standalone_archives(root, source_dir)

    if not check:
        _reset_latest_dirs(output_dir)

    for name in names:
        package = parse_agent_package_name(name)
        if package is None:
            skipped.append(name)
            continue

        source = source_dir / name
        destination = output_dir / package.platform / package.version / name
        latest_destination = output_dir / package.platform / "latest" / name
        source_hash = _sha256(source)

        if check:
            if not destination.exists():
                errors.append(f"missing organized copy: {_display(destination, root)}")
            elif _sha256(destination) != source_hash:
                errors.append(f"hash mismatch: {_display(destination, root)}")
            if not latest_destination.exists():
                errors.append(f"missing latest copy: {_display(latest_destination, root)}")
            elif _sha256(latest_destination) != source_hash:
                errors.append(f"latest hash mismatch: {_display(latest_destination, root)}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            latest_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, latest_destination)

        artifacts.append(
            OrganizedArtifact(
                platform=package.platform,
                plugin=package.plugin,
                version=package.version,
                package_kind=package.package_kind,
                source=_display(source, root),
                path=_display(destination, root),
                latest_path=_display(latest_destination, root),
                size=source.stat().st_size,
                sha256=source_hash,
            )
        )

    if archive_legacy and not check:
        legacy_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.glob("*.zip")):
            if source.name in expected_current:
                continue
            package = parse_agent_package_name(source.name)
            if package is None:
                if source.name in expected_standalone:
                    continue
                package = parse_standalone_skill_name(source.name)
                if package is None:
                    package = parse_unclassified_zip_name(source.name)
            source_hash = _sha256(source)
            destination = legacy_dir / package.platform / package.version / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if _sha256(destination) == source_hash:
                    source.unlink()
                else:
                    errors.append(
                        f"legacy destination already exists with different hash: "
                        f"{_display(destination, root)}"
                    )
                    continue
            else:
                shutil.move(str(source), str(destination))

    legacy_artifacts = _collect_legacy_artifacts(legacy_dir, root)

    result = OrganizationResult(
        source_dir=_display(source_dir, root),
        output_dir=_display(output_dir, root),
        legacy_dir=_display(legacy_dir, root),
        mode=mode,
        check=check,
        artifacts=artifacts,
        legacy_artifacts=legacy_artifacts,
        skipped=skipped,
        missing=missing,
        errors=errors,
    )

    if not check:
        _write_manifest_and_readme(result, output_dir, root)

    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="dist/agent-packages")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--legacy-dir", default=None)
    parser.add_argument("--mode", choices=("current", "all"), default="current")
    parser.add_argument(
        "--archive-legacy",
        action="store_true",
        help="Move recognized non-current plugin ZIPs into the legacy tree.",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    source_dir = Path(args.source_dir)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir is not None
        else source_dir / "by-platform"
    )
    legacy_dir = Path(args.legacy_dir) if args.legacy_dir is not None else source_dir / "legacy"

    result = organize_agent_packages(
        source_dir,
        output_dir,
        root=root,
        legacy_dir=legacy_dir,
        mode=args.mode,
        check=args.check,
        archive_legacy=args.archive_legacy,
    )
    ok = not result.errors and not result.missing

    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        action = "checked" if args.check else "organized"
        print(f"{action} {len(result.artifacts)} plugin package(s)")
        if result.legacy_artifacts:
            print(f"archived {len(result.legacy_artifacts)} legacy plugin package(s)")
        if result.missing:
            print("missing expected artifact(s):")
            for name in result.missing:
                print(f"  - {name}")
        if result.errors:
            print("error(s):")
            for error in result.errors:
                print(f"  - {error}")
        if not result.errors and not result.missing:
            print(result.output_dir)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
