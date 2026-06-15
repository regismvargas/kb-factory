from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from organize_agent_packages import (  # noqa: E402
    organize_agent_packages,
    parse_agent_package_name,
)


def _write_fake_zip(path: Path, payload: bytes = b"zip-bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_parse_agent_package_name_classifies_platforms() -> None:
    assert parse_agent_package_name("kb-wiki-vnext-plugin-0.1.3.zip").platform == "codex"  # type: ignore[union-attr]
    assert parse_agent_package_name("kb-wiki-vnext-claude-plugin-0.1.3.zip").platform == "claude-code"  # type: ignore[union-attr]
    assert parse_agent_package_name("kb-wiki-vnext-cowork-plugin-0.1.3.zip").platform == "claude-cowork"  # type: ignore[union-attr]
    assert parse_agent_package_name("session-gate-skill-0.2.4.zip") is None
    assert parse_agent_package_name("kb-wiki-vnext-cowork-plugin-root-test-0.1.0.zip") is None


def test_organize_current_agent_packages_by_platform_and_version(tmp_path: Path) -> None:
    source_dir = tmp_path / "dist" / "agent-packages"
    output_dir = source_dir / "by-platform"
    expected = {
        "kb-wiki-vnext-plugin-0.1.3.zip",
        "kb-wiki-vnext-claude-plugin-0.1.3.zip",
        "kb-wiki-vnext-cowork-plugin-0.1.3.zip",
    }
    for name in expected:
        _write_fake_zip(source_dir / name, payload=name.encode("utf-8"))
    _write_fake_zip(source_dir / "session-gate-skill-0.2.4.zip")

    result = organize_agent_packages(
        source_dir,
        output_dir,
        root=tmp_path,
        expected_names=expected,
    )

    assert result.errors == []
    assert result.missing == []
    assert {artifact.platform for artifact in result.artifacts} == {
        "codex",
        "claude-code",
        "claude-cowork",
    }
    assert (
        output_dir / "codex" / "0.1.3" / "kb-wiki-vnext-plugin-0.1.3.zip"
    ).exists()
    assert (
        output_dir / "codex" / "latest" / "kb-wiki-vnext-plugin-0.1.3.zip"
    ).exists()
    assert (
        output_dir
        / "claude-code"
        / "0.1.3"
        / "kb-wiki-vnext-claude-plugin-0.1.3.zip"
    ).exists()
    assert (
        output_dir
        / "claude-cowork"
        / "0.1.3"
        / "kb-wiki-vnext-cowork-plugin-0.1.3.zip"
    ).exists()
    assert not (
        output_dir / "claude-cowork" / "0.2.4" / "session-gate-skill-0.2.4.zip"
    ).exists()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["platforms"] == ["codex", "claude-code", "claude-cowork"]
    assert len(manifest["artifacts"]) == 3
    assert manifest["artifacts"][0]["latest_path"]


def test_organize_current_reports_missing_expected_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "dist" / "agent-packages"
    output_dir = source_dir / "by-platform"
    _write_fake_zip(source_dir / "kb-wiki-vnext-plugin-0.1.3.zip")

    result = organize_agent_packages(
        source_dir,
        output_dir,
        root=tmp_path,
        expected_names={
            "kb-wiki-vnext-plugin-0.1.3.zip",
            "kb-wiki-vnext-claude-plugin-0.1.3.zip",
        },
    )

    assert result.errors == []
    assert result.missing == ["kb-wiki-vnext-claude-plugin-0.1.3.zip"]


def test_organize_check_detects_hash_drift(tmp_path: Path) -> None:
    source_dir = tmp_path / "dist" / "agent-packages"
    output_dir = source_dir / "by-platform"
    expected = {"kb-wiki-vnext-plugin-0.1.3.zip"}
    _write_fake_zip(source_dir / "kb-wiki-vnext-plugin-0.1.3.zip", b"source")

    organize_agent_packages(
        source_dir,
        output_dir,
        root=tmp_path,
        expected_names=expected,
    )
    (output_dir / "codex" / "0.1.3" / "kb-wiki-vnext-plugin-0.1.3.zip").write_bytes(
        b"changed"
    )

    result = organize_agent_packages(
        source_dir,
        output_dir,
        root=tmp_path,
        expected_names=expected,
        check=True,
    )

    assert result.missing == []
    assert any("hash mismatch" in error for error in result.errors)


def test_archive_legacy_moves_non_current_plugin_zips(tmp_path: Path) -> None:
    source_dir = tmp_path / "dist" / "agent-packages"
    output_dir = source_dir / "by-platform"
    legacy_dir = source_dir / "legacy"
    current = {"kb-wiki-vnext-plugin-0.1.3.zip"}
    old_name = "kb-wiki-vnext-plugin-0.1.2.zip"
    current_skill_name = "case-adoption-audit-skill-0.3.1.zip"
    old_skill_name = "kb-wiki-maintainer-skill-0.1.1.zip"
    unclassified_name = "kb-wiki-vnext-cowork-plugin-root-test-0.1.0.zip"
    _write_fake_zip(source_dir / "kb-wiki-vnext-plugin-0.1.3.zip", b"current")
    _write_fake_zip(source_dir / old_name, b"old")
    _write_fake_zip(source_dir / current_skill_name, b"current-skill")
    _write_fake_zip(source_dir / old_skill_name, b"old-skill")
    _write_fake_zip(source_dir / unclassified_name, b"test")

    result = organize_agent_packages(
        source_dir,
        output_dir,
        root=tmp_path,
        legacy_dir=legacy_dir,
        expected_names=current,
        archive_legacy=True,
    )

    assert result.errors == []
    assert len(result.legacy_artifacts) == 3
    assert not (source_dir / old_name).exists()
    assert (legacy_dir / "codex" / "0.1.2" / old_name).exists()
    assert (source_dir / current_skill_name).exists()
    assert not (source_dir / old_skill_name).exists()
    assert (legacy_dir / "standalone-skill" / "0.1.1" / old_skill_name).exists()
    assert not (source_dir / unclassified_name).exists()
    assert (legacy_dir / "unclassified" / "0.1.0" / unclassified_name).exists()
