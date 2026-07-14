from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class Artifact:
    source_root: Path
    archive_path: Path
    archive_root: str | None = None
    exclude_top_level: tuple[str, ...] = ()
    exclude_relative_paths: tuple[str, ...] = ()
    exclude_relative_suffixes: tuple[str, ...] = ()
    # Extra (source_dir, archive_prefix) trees injected into the zip at build
    # time — used to bundle the `.kb/` scaffold into the kb-lifecycle plugin
    # without keeping a committed second copy of the runtime under plugins/.
    extra_trees: tuple[tuple[Path, str], ...] = ()
    required_entries: tuple[str, ...] = ()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_version(plugin_root: Path) -> str:
    manifest_paths = (
        plugin_root / ".codex-plugin" / "plugin.json",
        plugin_root / ".claude-plugin" / "plugin.json",
    )
    for manifest in manifest_paths:
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("version", "0.0.0")
    return "0.0.0"


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        if path.is_file():
            yield path


def write_zip(artifact: Artifact) -> None:
    artifact.archive_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(artifact.archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in iter_files(artifact.source_root):
            rel_path = file_path.relative_to(artifact.source_root)
            if rel_path.parts and rel_path.parts[0] in artifact.exclude_top_level:
                continue
            rel_posix = rel_path.as_posix()
            if rel_posix in artifact.exclude_relative_paths:
                continue
            if any(rel_posix.endswith(sfx) for sfx in artifact.exclude_relative_suffixes):
                continue
            archive_name = rel_posix
            if artifact.archive_root:
                archive_name = f"{artifact.archive_root}/{archive_name}"
            archive.write(file_path, archive_name)
        for extra_root, prefix in artifact.extra_trees:
            for file_path in iter_files(extra_root):
                if file_path.name in ("kb.db", "kb.db-shm", "kb.db-wal"):
                    continue
                rel_posix = file_path.relative_to(extra_root).as_posix()
                archive_name = f"{prefix}/{rel_posix}"
                if artifact.archive_root:
                    archive_name = f"{artifact.archive_root}/{archive_name}"
                archive.write(file_path, archive_name)


ANTHROPIC_SKILL_AGENT_SUFFIXES: tuple[str, ...] = ("agents/openai.yaml",)


def validate_artifact(artifact: Artifact, archive_path: Path) -> list[str]:
    """Validate a built ZIP against the documented platform upload shape.

    Returns a list of error strings; empty means pass.
    """
    errors: list[str] = []
    name = archive_path.name

    with ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        for entry in artifact.required_entries:
            if entry not in names:
                errors.append(f"{name}: package missing required entry {entry!r}")

    is_cowork_plugin = "-cowork-plugin-" in name
    is_claude_plugin = "-claude-plugin-" in name
    is_anthropic_plugin = is_cowork_plugin or is_claude_plugin
    is_skill = "-skill-" in name
    is_plugin = "-plugin-" in name and not is_skill
    is_codex_plugin = is_plugin and not is_anthropic_plugin

    if is_anthropic_plugin:
        codex_hits = [
            n for n in names
            if ".codex-plugin/" in n or n.rstrip("/").endswith(".codex-plugin")
        ]
        if codex_hits:
            errors.append(
                f"{name}: anthropic-targeted package contains .codex-plugin entries "
                f"(rule 2): {codex_hits[:5]}"
            )
        if ".claude-plugin/plugin.json" not in names:
            errors.append(
                f"{name}: anthropic-targeted package missing .claude-plugin/plugin.json "
                "at archive root"
            )

    if is_anthropic_plugin:
        openai_hits = [
            n for n in names
            if any(n.endswith(sfx) for sfx in ANTHROPIC_SKILL_AGENT_SUFFIXES)
        ]
        if openai_hits:
            errors.append(
                f"{name}: anthropic-targeted package contains openai agent metadata "
                f"(rule 3): {openai_hits}"
            )

    if is_skill:
        openai_hits = [
            n for n in names
            if any(n.endswith(sfx) for sfx in ANTHROPIC_SKILL_AGENT_SUFFIXES)
        ]
        if openai_hits:
            errors.append(
                f"{name}: anthropic-targeted skill package contains openai agent "
                f"metadata (rule 3): {openai_hits}"
            )
        codex_hits = [
            n for n in names
            if ".codex-plugin/" in n or n.rstrip("/").endswith(".codex-plugin")
        ]
        if codex_hits:
            errors.append(
                f"{name}: anthropic-targeted skill package contains .codex-plugin "
                f"entries (rule 2): {codex_hits[:5]}"
            )

    if is_skill:
        if not artifact.archive_root:
            errors.append(f"{name}: skill package missing archive_root (rule 4)")
        else:
            expected_skill_md = f"{artifact.archive_root}/SKILL.md"
            skill_md_entries = [n for n in names if n.endswith("/SKILL.md") or n == "SKILL.md"]
            if expected_skill_md not in names:
                errors.append(
                    f"{name}: skill package missing {expected_skill_md} (rule 4)"
                )
            if len(skill_md_entries) != 1:
                errors.append(
                    f"{name}: skill package must have exactly one SKILL.md, "
                    f"found {len(skill_md_entries)}: {skill_md_entries} (rule 4)"
                )
            expected_prefix = f"{artifact.archive_root}/"
            stray = [n for n in names if not n.startswith(expected_prefix)]
            if stray:
                preview = stray[:5] + (["..."] if len(stray) > 5 else [])
                errors.append(
                    f"{name}: skill package contains entries outside wrapped root "
                    f"{artifact.archive_root!r}: {preview} (rule 4)"
                )
            if expected_skill_md in names:
                with ZipFile(archive_path, "r") as archive:
                    try:
                        content = archive.read(expected_skill_md).decode("utf-8")
                    except UnicodeDecodeError:
                        content = ""
                if not content.lstrip().startswith("---"):
                    errors.append(
                        f"{name}: SKILL.md missing YAML frontmatter "
                        f"(must start with '---') (rule 4)"
                    )

    if is_codex_plugin:
        if ".codex-plugin/plugin.json" not in names:
            errors.append(
                f"{name}: Codex-targeted package missing .codex-plugin/plugin.json "
                "at archive root"
            )
        else:
            with ZipFile(archive_path, "r") as archive:
                try:
                    codex_manifest = json.loads(
                        archive.read(".codex-plugin/plugin.json").decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(
                        f"{name}: .codex-plugin/plugin.json is invalid JSON: {exc}"
                    )
                else:
                    if "hooks" in codex_manifest:
                        errors.append(
                            f"{name}: Codex plugin manifest must not declare unsupported "
                            "'hooks'; ship hooks as a companion file when needed"
                        )
                    if "mcpServers" in codex_manifest and ".mcp.json" not in names:
                        errors.append(
                            f"{name}: Codex plugin manifest declares mcpServers but "
                            ".mcp.json is absent"
                        )
                    if "apps" in codex_manifest and ".app.json" not in names:
                        errors.append(
                            f"{name}: Codex plugin manifest declares apps but "
                            ".app.json is absent"
                        )

    if is_plugin:
        manifest_candidates = (
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
        )
        if not any(m in names for m in manifest_candidates):
            errors.append(
                f"{name}: plugin package missing plugin manifest at archive root; expected one of "
                f"{list(manifest_candidates)}"
            )
        if "hooks/hooks.json" in names:
            with ZipFile(archive_path, "r") as archive:
                try:
                    hooks_config = json.loads(
                        archive.read("hooks/hooks.json").decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"{name}: hooks/hooks.json is invalid JSON: {exc}")
                else:
                    hooks = hooks_config.get("hooks")
                    if not isinstance(hooks, dict):
                        errors.append(
                            f"{name}: hooks/hooks.json must use the Claude hooks map schema "
                            "with a top-level 'hooks' object"
                        )
                    else:
                        for event_name, groups in hooks.items():
                            if not isinstance(event_name, str) or not isinstance(groups, list):
                                errors.append(
                                    f"{name}: hooks/hooks.json has invalid hook event entry "
                                    f"{event_name!r}"
                                )
                                continue
                            for group in groups:
                                if not isinstance(group, dict) or not isinstance(
                                    group.get("hooks"), list
                                ):
                                    errors.append(
                                        f"{name}: hooks/hooks.json event {event_name!r} "
                                        "must contain matcher groups with a hooks list"
                                    )
                                    break

    return errors


def validate_session_gate_skill_zip(
    archive_path: Path, expected_root: str
) -> list[str]:
    """Validator for the session-gate skill zip, which is built outside write_zip."""
    errors: list[str] = []
    name = archive_path.name
    with ZipFile(archive_path, "r") as archive:
        names = archive.namelist()

    expected_skill_md = f"{expected_root}/SKILL.md"
    skill_md_entries = [n for n in names if n.endswith("/SKILL.md") or n == "SKILL.md"]
    if expected_skill_md not in names:
        errors.append(f"{name}: session-gate skill missing {expected_skill_md} (rule 4)")
    if len(skill_md_entries) != 1:
        errors.append(
            f"{name}: session-gate skill must have exactly one SKILL.md, "
            f"found {len(skill_md_entries)}: {skill_md_entries} (rule 4)"
        )
    expected_prefix = f"{expected_root}/"
    stray = [n for n in names if not n.startswith(expected_prefix)]
    if stray:
        preview = stray[:5] + (["..."] if len(stray) > 5 else [])
        errors.append(
            f"{name}: session-gate skill contains entries outside wrapped root "
            f"{expected_root!r}: {preview} (rule 4)"
        )
    if expected_skill_md in names:
        with ZipFile(archive_path, "r") as archive:
            try:
                content = archive.read(expected_skill_md).decode("utf-8")
            except UnicodeDecodeError:
                content = ""
        if not content.lstrip().startswith("---"):
            errors.append(
                f"{name}: SKILL.md missing YAML frontmatter "
                f"(must start with '---') (rule 4)"
            )
    return errors


def build_skill_artifacts(
    skills_root: Path, output_dir: Path, version: str, skill_names: tuple[str, ...]
) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for skill_name in skill_names:
        artifacts.append(
            Artifact(
                source_root=skills_root / skill_name,
                archive_path=output_dir / f"{skill_name}-skill-{version}.zip",
                archive_root=skill_name,
                exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            )
        )
    return artifacts


def _write_session_gate_skill_zip(plugin_root: Path, archive_path: Path) -> None:
    """Build the session-gate standalone skill ZIP.

    Unlike kb-wiki-maintainer (all files under skills/), session-gate's
    operational files live at the plugin root (commands/, scripts/, README.md)
    while SKILL.md is at skills/session-gate/SKILL.md.  This function maps
    them into a flat skill-directory layout expected by Cowork.
    """
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "session-gate"

    # Explicit source → archive mapping
    mappings: list[tuple[Path, str]] = [
        (plugin_root / "skills" / "session-gate" / "SKILL.md", f"{prefix}/SKILL.md"),
        (plugin_root / "README.md", f"{prefix}/README.md"),
    ]
    # Add commands/ and scripts/ recursively (excluding __pycache__, .pyc)
    for subdir in ("commands", "scripts"):
        source_dir = plugin_root / subdir
        if source_dir.is_dir():
            for file_path in iter_files(source_dir):
                rel = file_path.relative_to(plugin_root)
                mappings.append((file_path, f"{prefix}/{rel.as_posix()}"))

    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for src, arc in mappings:
            if src.is_file():
                archive.write(src, arc)


def build_artifacts(
    root: Path,
    output_dir: Path,
    include_standalone_skill: bool = False,
    scope: str = "all",
    case_output_dir: Path | None = None,
) -> list[Artifact]:
    """Build the full list of Artifact entries.

    Artifacts are grouped by owner:
      - companion-owned (sibling repo): companion plugin ZIPs and standalone
        skills under `templates/claude-code-skills/`.
      - this-repo-owned: kb-lifecycle, kb-wiki-maintainer, session-gate, and the
        local deployment copy of the companion plugin.

    If ``case_output_dir`` is provided, companion-owned artifacts (plugins +
    standalone skills) are routed there; otherwise they share ``output_dir``.
    The ``scope`` filter accepts ``"all" | "case" | "kb" | "vnext"``.
    """
    kb_root = root / "plugins" / "kb-lifecycle"
    vnext_root = root / "plugins" / "kb-wiki-vnext"
    session_gate_root = root / "plugins" / "session-gate"
    claude_md_root = root / "plugins" / "claude-md-maintainer"
    case_framework_root = root.parent / "case-framework"
    # The companion plugin lives in the sibling repo under plugins/.
    case_plugin_root = case_framework_root / "plugins" / "case-companion"
    case_skill_root = case_framework_root / "templates" / "claude-code-skills"

    kb_version = load_version(kb_root)
    session_gate_version = load_version(session_gate_root)
    vnext_version = load_version(vnext_root)
    claude_md_version = load_version(claude_md_root)
    case_plugin_version = load_version(case_plugin_root)

    case_out = case_output_dir if case_output_dir is not None else output_dir

    # The kb-lifecycle plugin bundles the .kb/ scaffold (engine + config) so an
    # agent can scaffold a project's KB without a repo checkout. Injected at
    # build time from the single canonical template — no committed copy here.
    scaffold_tree = ((root / "core" / "templates" / "kb", "scaffold"),)

    # KB-owned artifacts (kb-factory)
    kb_artifacts: list[Artifact] = [
        Artifact(
            source_root=kb_root,
            archive_path=output_dir / f"kb-lifecycle-plugin-{kb_version}.zip",
            extra_trees=scaffold_tree,
        ),
        Artifact(
            source_root=kb_root,
            archive_path=output_dir / f"kb-lifecycle-claude-plugin-{kb_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            extra_trees=scaffold_tree,
        ),
        Artifact(
            source_root=kb_root,
            archive_path=output_dir / f"kb-lifecycle-cowork-plugin-{kb_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            extra_trees=scaffold_tree,
        ),
        # Companion artifacts live in the sibling repo; build them with
        # --scope case or from that repo's own build tooling.
        Artifact(
            source_root=session_gate_root,
            archive_path=output_dir / f"session-gate-plugin-{session_gate_version}.zip",
        ),
        Artifact(
            source_root=session_gate_root,
            archive_path=output_dir / f"session-gate-claude-plugin-{session_gate_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
        Artifact(
            source_root=session_gate_root,
            archive_path=output_dir / f"session-gate-cowork-plugin-{session_gate_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
        Artifact(
            source_root=claude_md_root,
            archive_path=output_dir / f"claude-md-maintainer-claude-plugin-{claude_md_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
        Artifact(
            source_root=claude_md_root,
            archive_path=output_dir / f"claude-md-maintainer-cowork-plugin-{claude_md_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
    ]

    # The vNext plugin COMMITS its runtime engine at
    # plugins/kb-wiki-vnext/runtime/kb_next.py (kept byte-identical to the master
    # by tools/sync_vnext_runtime.py + the parity gate) so every install path —
    # ZIP (via iter_files), marketplace (repo source), and pip — carries it.
    # required_entries locks its presence in the built ZIP.
    vnext_runtime_required = ("runtime/kb_next.py",)
    vnext_artifacts: list[Artifact] = [
        Artifact(
            source_root=vnext_root,
            archive_path=output_dir / f"kb-wiki-vnext-plugin-{vnext_version}.zip",
            required_entries=vnext_runtime_required,
        ),
        Artifact(
            source_root=vnext_root,
            archive_path=output_dir / f"kb-wiki-vnext-claude-plugin-{vnext_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            required_entries=vnext_runtime_required,
        ),
        Artifact(
            source_root=vnext_root,
            archive_path=output_dir / f"kb-wiki-vnext-cowork-plugin-{vnext_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            required_entries=vnext_runtime_required,
        ),
    ]

    # Companion-owned artifacts, sourced from the sibling repo's
    # plugins/case-companion/ directory.
    case_artifacts: list[Artifact] = [
        Artifact(
            source_root=case_plugin_root,
            archive_path=case_out / f"case-companion-plugin-{case_plugin_version}.zip",
        ),
        Artifact(
            source_root=case_plugin_root,
            archive_path=case_out / f"case-companion-claude-plugin-{case_plugin_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
        Artifact(
            source_root=case_plugin_root,
            archive_path=case_out / f"case-companion-cowork-plugin-{case_plugin_version}.zip",
            exclude_top_level=(".codex-plugin",),
            exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
        ),
    ]

    if include_standalone_skill:
        case_artifacts.extend(
            build_skill_artifacts(
                case_skill_root,
                case_out,
                case_claude_version,
                (
                    "case-adoption-audit",
                    "case-resync",
                    "case-rollout",
                    "case-runtime-sync",
                    "kb-audit",
                    "kb-init",
                    "kb-sync",
                ),
            )
        )
        kb_artifacts.append(
            Artifact(
                source_root=kb_root / "skills" / "kb-wiki-maintainer",
                archive_path=output_dir / f"kb-wiki-maintainer-skill-{kb_version}.zip",
                archive_root="kb-wiki-maintainer",
                exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
            )
        )

    if scope == "case":
        return case_artifacts
    if scope == "vnext":
        return vnext_artifacts
    if scope == "kb":
        return kb_artifacts + vnext_artifacts
    return kb_artifacts + vnext_artifacts + case_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build KB Factory plugin and skill ZIP artifacts from canonical plugin sources."
    )
    parser.add_argument(
        "--output-dir",
        default="dist/agent-packages",
        help="Output directory (this repo's own artifacts) relative to the repository root.",
    )
    parser.add_argument(
        "--case-output-dir",
        default=None,
        help=(
            "Explicit override for the companion-owned output directory. "
            "Absolute paths are used as-is; relative paths resolve against the "
            "repository root. When unset, defaults to the sibling repo's "
            "dist/agent-packages/ directory. Using this flag overrides "
            "--legacy-shared-output."
        ),
    )
    parser.add_argument(
        "--legacy-shared-output",
        action="store_true",
        help=(
            "Legacy opt-out: force all artifacts (including companion ones) to "
            "share --output-dir, matching the older shared-output behavior. Not "
            "recommended. Kept for reproducing historical builds only."
        ),
    )
    parser.add_argument(
        "--per-owner-output",
        action="store_true",
        help=argparse.SUPPRESS,  # deprecated no-op: per-owner routing is now the default.
    )
    parser.add_argument(
        "--scope",
        choices=("all", "case", "kb", "vnext"),
        default="all",
        help=(
            "Restrict built artifacts by owner: 'case' builds only the "
            "companion-owned artifacts; 'kb' builds only this repo's artifacts "
            "including vNext; 'vnext' builds only KB/Wiki vNext; 'all' "
            "(default) builds all."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned artifacts without writing ZIP files.",
    )
    parser.add_argument(
        "--include-standalone-skill",
        action="store_true",
        help="Also build standalone skill ZIPs (kb-wiki-maintainer and session-gate) for direct Cowork skill installation.",
    )
    args = parser.parse_args()

    root = repo_root()
    output_dir = root / args.output_dir

    # Resolution order (highest precedence first):
    #   1. --case-output-dir (explicit override, always wins)
    #   2. --legacy-shared-output (opt-in to older shared routing)
    #   3. Default: route companion-owned artifacts to the sibling repo's
    #      dist/agent-packages/ directory.
    if args.case_output_dir is not None:
        case_raw = Path(args.case_output_dir)
        case_output_dir: Path | None = case_raw if case_raw.is_absolute() else root / case_raw
    elif args.legacy_shared_output:
        case_output_dir = None
    else:
        case_output_dir = (root.parent / "case-framework" / "dist" / "agent-packages").resolve()

    artifacts = build_artifacts(
        root,
        output_dir,
        include_standalone_skill=args.include_standalone_skill,
        scope=args.scope,
        case_output_dir=case_output_dir,
    )

    # session-gate standalone skill is KB-owned (kb-factory) — only emit it
    # when the KB slice is in scope.
    build_session_gate_skill = args.include_standalone_skill and args.scope in ("all", "kb")

    if args.dry_run:
        for artifact in artifacts:
            print(
                f"{artifact.source_root} -> {artifact.archive_path} "
                f"(root={artifact.archive_root}, exclude={artifact.exclude_top_level})"
            )
        if build_session_gate_skill:
            sg_root = root / "plugins" / "session-gate"
            sg_version = load_version(sg_root)
            sg_skill_path = output_dir / f"session-gate-skill-{sg_version}.zip"
            print(f"{sg_root} -> {sg_skill_path} (standalone skill, custom layout)")
        return 0

    all_errors: list[str] = []

    for artifact in artifacts:
        write_zip(artifact)
        errors = validate_artifact(artifact, artifact.archive_path)
        if errors:
            all_errors.extend(errors)
            print(f"{artifact.archive_path} FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print(artifact.archive_path)

    if build_session_gate_skill:
        sg_root = root / "plugins" / "session-gate"
        sg_version = load_version(sg_root)
        sg_skill_path = output_dir / f"session-gate-skill-{sg_version}.zip"
        _write_session_gate_skill_zip(sg_root, sg_skill_path)
        errors = validate_session_gate_skill_zip(sg_skill_path, "session-gate")
        if errors:
            all_errors.extend(errors)
            print(f"{sg_skill_path} FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print(sg_skill_path)

    if all_errors:
        print("")
        print(f"validation failed for {len(all_errors)} issue(s)")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
