from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_VERSIONS = {
    "kb-lifecycle": "0.2.3",
    "kb-wiki-vnext": "0.1.9",
    "session-gate": "0.2.7",
}
RUNTIME_PATHS = (
    ROOT / "core/versions/kb-wiki-vnext/runtime/kb_next.py",
    ROOT / "plugins/kb-wiki-vnext/runtime/kb_next.py",
    ROOT / "kb_factory/_scaffold_vnext/runtime/kb_next.py",
)


def _json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_public_release_version_matrix_is_coherent() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert project_version is not None and project_version.group(1) == "0.1.4"
    assert '__version__ = "0.1.4"' in (ROOT / "kb_factory/__init__.py").read_text(
        encoding="utf-8"
    )

    marketplace = _json(".claude-plugin/marketplace.json")
    assert set(marketplace) == {"name", "metadata", "owner", "plugins"}
    assert marketplace["name"] == "kb-factory-tools"
    assert marketplace["metadata"]["version"] == "0.3.8"
    catalog = {item["name"]: item["version"] for item in marketplace["plugins"]}
    assert catalog == PLUGIN_VERSIONS

    for plugin, expected in PLUGIN_VERSIONS.items():
        for platform in (".claude-plugin", ".codex-plugin"):
            manifest = _json(f"plugins/{plugin}/{platform}/plugin.json")
            assert manifest["name"] == plugin
            assert manifest["version"] == expected

    product = _json("products/kb-wiki-vnext/product.json")
    assert product["version"] == "0.2.0-rc.2"
    assert product["component_versions"] == {
        "product": "0.2.0-rc.2",
        "python": "0.1.4",
        "marketplace": "0.3.8",
        "kb_lifecycle": "0.2.3",
        "kb_wiki_vnext": "0.1.9",
        "session_gate": "0.2.7",
        "runtime": "0.1.7",
    }


def test_runtime_copies_and_release_provenance_are_bound() -> None:
    payloads = [path.read_bytes() for path in RUNTIME_PATHS]
    assert payloads[1:] == payloads[:-1]
    match = re.search(rb'^RUNTIME_VERSION = "([^"]+)"$', payloads[0], re.MULTILINE)
    assert match is not None and match.group(1) == b"0.1.7"

    provenance = _json(".kb-factory-public-export.json")
    assert provenance["source_sha"] == "6c8873797add4f068b7635403c9b18d478442315"
    assert provenance["baseline_public_sha"] == "256b217aafac0dbe6663af9edfb70b0d66761bc4"
    assert provenance["policy_version"] == "2026-07-19.3"
    assert provenance["final_public_file_count"] == 250
    assert provenance["final_integrity_binding"] == {
        "git_ref": "refs/tags/v0.1.4",
        "scope": "all tracked files in the tagged public commit",
        "release_assets": "SHA256SUMS.txt",
    }


def test_public_product_does_not_require_private_surfaces() -> None:
    product = _json("products/kb-wiki-vnext/product.json")
    serialized = json.dumps(product, sort_keys=True).lower()
    for forbidden in (
        "case-framework",
        "kb-factory-workbench",
        "cleanup_vnext_workbench",
        "validate_kb_wiki_vnext_spec_pack",
        "docs/install.md",
    ):
        assert forbidden not in serialized

    builder = (ROOT / "tools/build_vnext_standalone.py").read_text(encoding="utf-8")
    assert 'DEFAULT_VERSION = "0.2.0-rc.2"' in builder
