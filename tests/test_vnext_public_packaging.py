"""Focused release checks for the public KB/Wiki vNext package surfaces."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_agent_packages import build_artifacts, validate_artifact, write_zip  # noqa: E402
from build_vnext_standalone import DEFAULT_VERSION, build_standalone  # noqa: E402
from validate_vnext_product import validate  # noqa: E402
import validate_vnext_product as product_validator  # noqa: E402


PUBLIC_ARCHIVES = {
    "kb-lifecycle-plugin-0.3.0.zip",
    "kb-lifecycle-claude-plugin-0.3.0.zip",
    "kb-lifecycle-cowork-plugin-0.3.0.zip",
    "kb-wiki-vnext-plugin-0.3.0.zip",
    "kb-wiki-vnext-claude-plugin-0.3.0.zip",
    "kb-wiki-vnext-cowork-plugin-0.3.0.zip",
    "session-gate-plugin-0.2.7.zip",
    "session-gate-claude-plugin-0.2.7.zip",
    "session-gate-cowork-plugin-0.2.7.zip",
}


def test_public_all_scope_builds_only_nine_released_plugin_zips(tmp_path: Path) -> None:
    artifacts = build_artifacts(REPO_ROOT, tmp_path, scope="all")
    assert {artifact.archive_path.name for artifact in artifacts} == PUBLIC_ARCHIVES
    assert all("0.0.0" not in artifact.archive_path.name for artifact in artifacts)

    for artifact in artifacts:
        write_zip(artifact)
        assert validate_artifact(artifact, artifact.archive_path) == []


def test_public_agent_packages_are_deterministic(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = build_artifacts(REPO_ROOT, first_dir, scope="all")
    second = build_artifacts(REPO_ROOT, second_dir, scope="all")

    for artifact in first + second:
        write_zip(artifact)

    first_bytes = {
        artifact.archive_path.name: artifact.archive_path.read_bytes() for artifact in first
    }
    second_bytes = {
        artifact.archive_path.name: artifact.archive_path.read_bytes() for artifact in second
    }
    assert first_bytes == second_bytes


def test_missing_mandatory_public_plugin_fails_before_artifact_planning(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="required plugin manifest"):
        build_artifacts(tmp_path, tmp_path / "dist", scope="all")


def test_standalone_bundle_is_public_and_validator_accepts_its_inventory(tmp_path: Path) -> None:
    zip_path = build_standalone(DEFAULT_VERSION, tmp_path, skip_agent_packages=True)
    assert validate(zip_path) == []

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert zip_path.with_suffix(".zip.sha256").read_text(encoding="utf-8") == (
        f"{digest}  {zip_path.name}\n"
    )

    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        bundle_root = f"kb-wiki-vnext-{DEFAULT_VERSION}"
        root_readme = archive.read(f"{bundle_root}/README.md").decode("utf-8")
        product_readme = archive.read(f"{bundle_root}/product/README.md").decode("utf-8")
    assert all("spec-pack" not in name for name in names)
    assert all("cleanup_vnext_workbench" not in name for name in names)
    assert all("validate_kb_wiki_vnext_spec_pack" not in name for name in names)
    assert all("docs/INSTALL.md" not in name for name in names)
    assert all("runtime/README.md" not in name for name in names)
    assert "](product/docs/en/user-manual.md)" in root_readme
    assert "](product/product.json)" in root_readme
    assert "](tools/build_vnext_standalone.py)" in root_readme
    assert "](docs/en/user-manual.md)" in product_readme
    assert "](../tools/build_vnext_standalone.py)" in product_readme
    assert "../../" not in root_readme
    assert "../../" not in product_readme


def test_standalone_bundle_is_deterministic(tmp_path: Path) -> None:
    first = build_standalone(DEFAULT_VERSION, tmp_path / "first", skip_agent_packages=True)
    second = build_standalone(DEFAULT_VERSION, tmp_path / "second", skip_agent_packages=True)
    assert first.read_bytes() == second.read_bytes()


def test_validator_returns_structured_error_when_product_manifest_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(product_validator, "repo_root", lambda: tmp_path)
    errors = product_validator.validate()
    assert f"missing product manifest: {tmp_path / 'products' / 'kb-wiki-vnext' / 'product.json'}" in errors
