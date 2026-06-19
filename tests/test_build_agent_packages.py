"""Validator tests for tools/build_agent_packages.py.

Each test constructs a synthetic source tree, writes a ZIP through the real
`write_zip` helper, optionally tampers with it, and asserts `validate_artifact`
accepts the clean case and rejects each of the four documented rules plus the
manifest-presence guard.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_agent_packages import (  # noqa: E402
    ANTHROPIC_SKILL_AGENT_SUFFIXES,
    Artifact,
    build_artifacts,
    validate_artifact,
    validate_session_gate_skill_zip,
    write_zip,
)


def _seed_kb_plugin(root: Path) -> None:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "kb-lifecycle", "version": "0.0.0"}), encoding="utf-8"
    )
    (root / ".codex-plugin").mkdir()
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "kb-lifecycle", "version": "0.0.0"}), encoding="utf-8"
    )
    skill = root / "skills" / "kb-wiki-maintainer"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: kb-wiki-maintainer\n---\nbody\n", encoding="utf-8"
    )
    agents = skill / "agents"
    agents.mkdir()
    (agents / "openai.yaml").write_text("tool: openai\n", encoding="utf-8")


def _seed_skill(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(
        f"---\nname: {name}\n---\nbody\n", encoding="utf-8"
    )


def _add_to_zip(zip_path: Path, arcname: str, content: bytes) -> None:
    with ZipFile(zip_path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr(arcname, content)


def _rewrite_zip(zip_path: Path, drop: set[str]) -> None:
    with ZipFile(zip_path, "r") as src:
        entries = [(n, src.read(n)) for n in src.namelist() if n not in drop]
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as dst:
        for name, data in entries:
            dst.writestr(name, data)


def _command_basenames(entries: list[str]) -> set[str]:
    return {
        Path(name).name
        for name in entries
        if name.startswith("commands/") and name.endswith(".md")
    }


def _artifact_plugin_name(name: str) -> str:
    if name.startswith("kb-wiki-vnext-") or name.startswith("kb-wiki-vnext-plugin-"):
        return "kb-wiki-vnext"
    if name.startswith("session-gate-") or name.startswith("session-gate-plugin-"):
        return "session-gate"
    if name.startswith("kb-lifecycle-") or name.startswith("kb-lifecycle-plugin-"):
        return "kb-lifecycle"
    if name.startswith("claude-md-maintainer-"):
        return "claude-md-maintainer"
    return name


@pytest.fixture()
def kb_source(tmp_path: Path) -> Path:
    source = tmp_path / "plugins" / "kb-lifecycle"
    _seed_kb_plugin(source)
    return source


@pytest.fixture()
def skill_source(tmp_path: Path) -> Path:
    source = tmp_path / "skills"
    _seed_skill(source, "case-adoption-audit")
    return source


# -- Clean cases --------------------------------------------------------------


def test_clean_cowork_plugin_passes(tmp_path: Path, kb_source: Path) -> None:
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    assert validate_artifact(artifact, out) == []


def test_clean_claude_plugin_passes(tmp_path: Path, kb_source: Path) -> None:
    out = tmp_path / "kb-lifecycle-claude-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    assert validate_artifact(artifact, out) == []


def test_clean_skill_passes(tmp_path: Path, skill_source: Path) -> None:
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill_source / "case-adoption-audit",
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    assert validate_artifact(artifact, out) == []


# -- Rule 1: Plugin manifest at archive root ---------------------------------


def test_rule_1_rejects_wrapped_cowork_plugin_root(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        archive_root="kb-lifecycle",
        exclude_top_level=(".codex-plugin",),
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("manifest at archive root" in e for e in errors)


def test_rule_1_rejects_legacy_hooks_list_schema(
    tmp_path: Path, kb_source: Path
) -> None:
    hooks = kb_source / "hooks"
    hooks.mkdir()
    (hooks / "hooks.json").write_text(
        json.dumps({"hooks": [{"event": "SessionStart", "hooks": []}]}),
        encoding="utf-8",
    )
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("top-level 'hooks' object" in e for e in errors)


# -- Rule 2: No .codex-plugin/ in Anthropic-targeted packages ----------------


def test_rule_2_rejects_codex_plugin_in_cowork(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any(".codex-plugin" in e for e in errors)


def test_rule_2_rejects_codex_plugin_in_claude_plugin(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-claude-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any(".codex-plugin" in e for e in errors)


# -- Rule 3: No skills/*/agents/openai.yaml in Anthropic-targeted packages ---


def test_rule_3_rejects_openai_yaml_in_cowork(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("openai" in e for e in errors)


def test_rule_3_rejects_openai_yaml_in_claude_plugin(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-claude-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("openai" in e for e in errors)


# -- Rule 4: Skill ZIP shape --------------------------------------------------


def test_rule_4_rejects_missing_skill_md(
    tmp_path: Path, skill_source: Path
) -> None:
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill_source / "case-adoption-audit",
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    _rewrite_zip(out, drop={"case-adoption-audit/SKILL.md"})
    errors = validate_artifact(artifact, out)
    assert any("missing case-adoption-audit/SKILL.md" in e for e in errors)


def test_rule_4_rejects_multiple_skill_md(
    tmp_path: Path, skill_source: Path
) -> None:
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill_source / "case-adoption-audit",
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    _add_to_zip(
        out,
        "case-adoption-audit/nested/SKILL.md",
        b"---\nname: nested\n---\n",
    )
    errors = validate_artifact(artifact, out)
    assert any("exactly one SKILL.md" in e for e in errors)


def test_rule_4_rejects_unexpected_top_level_dir(
    tmp_path: Path, skill_source: Path
) -> None:
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill_source / "case-adoption-audit",
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    _add_to_zip(out, "other-skill/extra.txt", b"x")
    errors = validate_artifact(artifact, out)
    assert any("outside wrapped root" in e for e in errors)


def test_rule_4_rejects_root_level_file(
    tmp_path: Path, skill_source: Path
) -> None:
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill_source / "case-adoption-audit",
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    _add_to_zip(out, "README.md", b"stray root file")
    errors = validate_artifact(artifact, out)
    assert any("outside wrapped root" in e for e in errors)


def test_rule_4_rejects_skill_md_without_frontmatter(
    tmp_path: Path, skill_source: Path
) -> None:
    skill = skill_source / "case-adoption-audit"
    (skill / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    out = tmp_path / "case-adoption-audit-skill-0.0.0.zip"
    artifact = Artifact(
        source_root=skill,
        archive_path=out,
        archive_root="case-adoption-audit",
    )
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("YAML frontmatter" in e for e in errors)


# -- Manifest-presence guard --------------------------------------------------


def test_manifest_guard_rejects_plugin_without_manifest(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-cowork-plugin-0.0.0.zip"
    artifact = Artifact(
        source_root=kb_source,
        archive_path=out,
        exclude_top_level=(".codex-plugin",),
        exclude_relative_suffixes=ANTHROPIC_SKILL_AGENT_SUFFIXES,
    )
    write_zip(artifact)
    _rewrite_zip(out, drop={".claude-plugin/plugin.json"})
    errors = validate_artifact(artifact, out)
    assert any("missing plugin manifest" in e for e in errors)


def test_codex_package_requires_codex_manifest(
    tmp_path: Path, kb_source: Path
) -> None:
    out = tmp_path / "kb-lifecycle-plugin-0.0.0.zip"
    artifact = Artifact(source_root=kb_source, archive_path=out)
    write_zip(artifact)
    _rewrite_zip(out, drop={".codex-plugin/plugin.json"})
    errors = validate_artifact(artifact, out)
    assert any("missing .codex-plugin/plugin.json" in e for e in errors)


def test_codex_package_rejects_hooks_manifest_field(
    tmp_path: Path, kb_source: Path
) -> None:
    manifest = kb_source / ".codex-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["hooks"] = "./hooks/hooks.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "kb-lifecycle-plugin-0.0.0.zip"
    artifact = Artifact(source_root=kb_source, archive_path=out)
    write_zip(artifact)
    errors = validate_artifact(artifact, out)
    assert any("must not declare unsupported 'hooks'" in e for e in errors)


# -- KB-lifecycle scaffold bundle ---------------------------------------------


def test_kb_lifecycle_plugin_bundles_scaffold(tmp_path: Path) -> None:
    artifacts = build_artifacts(REPO_ROOT, tmp_path, scope="kb")
    kb_lifecycle = [
        a for a in artifacts if a.archive_path.name.startswith("kb-lifecycle-")
    ]
    assert kb_lifecycle, "expected kb-lifecycle plugin artifacts"
    for artifact in kb_lifecycle:
        write_zip(artifact)
        assert validate_artifact(artifact, artifact.archive_path) == []
        with ZipFile(artifact.archive_path, "r") as archive:
            names = set(archive.namelist())
        # The .kb/ scaffold (engine + config) is bundled so an agent can set up
        # a project KB without a repo checkout.
        assert "scaffold/kb.py" in names
        assert "scaffold/runtime/records.py" in names
        assert "scaffold/runtime/schema.py" in names
        assert "scaffold/kb.config.json" in names
        # The plugin's own surfaces remain intact.
        assert ".claude-plugin/plugin.json" in names


# -- KB/Wiki vNext packages ---------------------------------------------------


def test_vnext_packages_are_separate_and_do_not_collide(tmp_path: Path) -> None:
    artifacts = build_artifacts(REPO_ROOT, tmp_path, scope="vnext")
    names = {artifact.archive_path.name for artifact in artifacts}

    assert names == {
        "kb-wiki-vnext-plugin-0.1.4.zip",
        "kb-wiki-vnext-claude-plugin-0.1.4.zip",
        "kb-wiki-vnext-cowork-plugin-0.1.4.zip",
    }
    assert not any(name.startswith(("kb-lifecycle", "session-gate", "case-companion")) for name in names)

    for artifact in artifacts:
        write_zip(artifact)
        assert validate_artifact(artifact, artifact.archive_path) == []
        with ZipFile(artifact.archive_path, "r") as archive:
            entries = archive.namelist()
            command_names = _command_basenames(entries)
            assert "vnext-session-start.md" in command_names
            assert "vnext-session-end.md" in command_names
            assert "existing-project-diagnose.md" in command_names
            assert "existing-project-activate-vnext.md" in command_names
            assert "existing-project-configure-vnext.md" in command_names
            assert "existing-project-verify-install.md" in command_names
            assert "existing-project-upgrade-vnext.md" in command_names
            assert "existing-project-rollback-vnext.md" in command_names
            assert "new-project-wizard.md" in command_names
            assert "new-project-init-kb-alone.md" in command_names
            assert "new-project-init-kb-wiki.md" in command_names
            assert "new-project-verify-install.md" in command_names
            assert "session-start.md" not in command_names
            assert "session-end.md" not in command_names
            for command_name in [
                name for name in entries
                if name.startswith("commands/") and name.endswith(".md")
            ]:
                command_text = archive.read(command_name).decode("utf-8")
                assert command_text.startswith("---\n")
                assert "description:" in command_text.split("---", 2)[1]
            if artifact.archive_path.name == "kb-wiki-vnext-plugin-0.1.4.zip":
                assert ".codex-plugin/plugin.json" in entries
                codex_manifest = json.loads(
                    archive.read(".codex-plugin/plugin.json").decode("utf-8")
                )
                assert "hooks" not in codex_manifest
            else:
                assert ".claude-plugin/plugin.json" in entries
                assert ".codex-plugin/plugin.json" not in entries


def test_vnext_packages_keep_thin_on_demand_memory_contract(tmp_path: Path) -> None:
    artifacts = build_artifacts(REPO_ROOT, tmp_path, scope="vnext")
    for artifact in artifacts:
        write_zip(artifact)
        with ZipFile(artifact.archive_path, "r") as archive:
            entries = archive.namelist()
            combined = "\n".join(
                archive.read(name).decode("utf-8")
                for name in entries
                if name.endswith((".md", ".json"))
            )

        assert ".kb-next/memory/NOW.md" in combined
        assert "Read only" in combined or "read only" in combined
        assert "on demand" in combined
        assert ".kb/kb.db" in combined
        assert ".kb/wiki/live" in combined
        assert "compliance-preflight" in combined
        assert "100% developed" in combined
        assert "semantic-hygiene" in combined
        assert "hygiene-audit" in combined
        if "-cowork-plugin-" in artifact.archive_path.name:
            assert ".claude-plugin/plugin.json" in entries
            assert "skills/kb-wiki-vnext/SKILL.md" in entries
            assert not any(name.startswith("kb-wiki-vnext/") for name in entries)


def test_vnext_packages_disambiguate_plugin_command_from_shell_runtime(tmp_path: Path) -> None:
    artifacts = build_artifacts(REPO_ROOT, tmp_path, scope="vnext")
    for artifact in artifacts:
        write_zip(artifact)
        with ZipFile(artifact.archive_path, "r") as archive:
            combined = "\n".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith((".md", ".json"))
            )

        assert "vnext-session-start" in combined
        assert "plugin/slash command" in combined or "plugin command" in combined
        assert "core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json" in combined
        assert "run vnext-session-start" not in combined.lower()
        assert "Run `vnext-session-start`" not in combined


# -- Session-gate adapter -----------------------------------------------------
def test_session_gate_packages_use_explicit_command_names(tmp_path: Path) -> None:
    artifacts = [
        artifact
        for artifact in build_artifacts(REPO_ROOT, tmp_path, scope="kb")
        if artifact.archive_path.name.startswith("session-gate-")
        and "-skill-" not in artifact.archive_path.name
    ]
    names = {artifact.archive_path.name for artifact in artifacts}
    assert names == {
        "session-gate-plugin-0.2.5.zip",
        "session-gate-claude-plugin-0.2.5.zip",
        "session-gate-cowork-plugin-0.2.5.zip",
    }

    for artifact in artifacts:
        write_zip(artifact)
        assert validate_artifact(artifact, artifact.archive_path) == []
        with ZipFile(artifact.archive_path, "r") as archive:
            command_names = _command_basenames(archive.namelist())
        assert command_names == {"gate-session-start.md", "gate-session-end.md"}
def test_session_gate_detector_reports_vnext_before_classic_kb(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".kb" / "memory").mkdir(parents=True)
    (workspace / ".kb" / "kb.py").write_text("# classic runtime\n", encoding="utf-8")
    (workspace / ".kb" / "memory" / "NOW.md").write_text("classic\n", encoding="utf-8")
    (workspace / ".kb-next" / "memory").mkdir(parents=True)
    (workspace / ".kb-next" / "memory" / "NOW.md").write_text("vnext\n", encoding="utf-8")
    (workspace / "core" / "versions" / "kb-wiki-vnext" / "runtime").mkdir(parents=True)
    (workspace / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py").write_text(
        "# vnext runtime\n", encoding="utf-8"
    )
    (workspace / "plugins" / "kb-wiki-vnext" / "commands").mkdir(parents=True)
    (workspace / "plugins" / "kb-wiki-vnext" / "commands" / "vnext-session-start.md").write_text(
        "vnext\n", encoding="utf-8"
    )

    detector_path = REPO_ROOT / "plugins" / "session-gate" / "scripts" / "detect_workspace.py"
    spec = importlib.util.spec_from_file_location("session_gate_detector", detector_path)
    assert spec is not None
    detector = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(detector)

    result = detector.detect(workspace)
    assert result["vnext"]["found"] is True
    assert result["kb"]["found"] is True
    assert "vnext-session-start.md" in result["vnext"]["details"]["session_command_ref"]
    assert result["summary"][0].startswith("KB/Wiki vNext detected")


def test_session_gate_validator_accepts_clean_layout(tmp_path: Path) -> None:
    out = tmp_path / "session-gate-skill-0.0.0.zip"
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "session-gate/SKILL.md", "---\nname: session-gate\n---\nbody\n"
        )
        archive.writestr("session-gate/commands/gate-session-start.md", "cmd\n")
    assert validate_session_gate_skill_zip(out, "session-gate") == []


def test_session_gate_validator_rejects_missing_skill_md(tmp_path: Path) -> None:
    out = tmp_path / "session-gate-skill-0.0.0.zip"
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("session-gate/commands/gate-session-start.md", "cmd\n")
    errors = validate_session_gate_skill_zip(out, "session-gate")
    assert any("missing session-gate/SKILL.md" in e for e in errors)


def test_session_gate_validator_rejects_extra_top_level_dir(tmp_path: Path) -> None:
    out = tmp_path / "session-gate-skill-0.0.0.zip"
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "session-gate/SKILL.md", "---\nname: session-gate\n---\nbody\n"
        )
        archive.writestr("stray/extra.md", "x")
    errors = validate_session_gate_skill_zip(out, "session-gate")
    assert any("outside wrapped root" in e for e in errors)


def test_session_gate_validator_rejects_root_level_file(tmp_path: Path) -> None:
    out = tmp_path / "session-gate-skill-0.0.0.zip"
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "session-gate/SKILL.md", "---\nname: session-gate\n---\nbody\n"
        )
        archive.writestr("README.md", "stray root file")
    errors = validate_session_gate_skill_zip(out, "session-gate")
    assert any("outside wrapped root" in e for e in errors)


def test_session_gate_validator_rejects_skill_md_without_frontmatter(
    tmp_path: Path,
) -> None:
    out = tmp_path / "session-gate-skill-0.0.0.zip"
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("session-gate/SKILL.md", "no frontmatter here\n")
    errors = validate_session_gate_skill_zip(out, "session-gate")
    assert any("YAML frontmatter" in e for e in errors)
