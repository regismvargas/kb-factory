"""Validate the KB/Wiki vNext product package and source tree."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


PRODUCT_DIR = Path("products/kb-wiki-vnext")
PRODUCT_VERSION = "0.3.0"
REQUIRED_COMPONENT_VERSIONS = {
    "product": PRODUCT_VERSION,
    "python": "0.3.0",
    "kb_lifecycle": "0.3.0",
    "kb_wiki_vnext": "0.3.0",
    "session_gate": "0.2.7",
    "runtime": "0.3.0",
}
REQUIRED_DOCS = [
    "user-manual.md",
    "admin-installation.md",
    "upgrade-rollback.md",
    "architecture.md",
    "maintainer-release.md",
    "troubleshooting.md",
]
REQUIRED_BUNDLE_PATHS = [
    "README.md",
    "runtime/kb_next.py",
    "classic-template/.kb/kb.py",
    "plugin/.codex-plugin/plugin.json",
    "product/product.json",
    "product/README.md",
    "product/docs/en/user-manual.md",
    "product/docs/pt-BR/user-manual.md",
    "tools/build_agent_packages.py",
    "tools/build_vnext_standalone.py",
    "tools/validate_vnext_product.py",
]
FORBIDDEN_BUNDLE_PATTERNS = [
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.pyc$"),
    re.compile(r"(^|/)\.kb/kb\.db($|[.-])"),
    re.compile(r"(^|/)\.kb/wiki/live/"),
    re.compile(r"(^|/)state/runs/"),
    re.compile(r"(^|/)\.pytest"),
    re.compile(r"(^|/)worktrees/"),
    re.compile(r"(^|/)archive/", re.IGNORECASE),
    re.compile(r"(^|/)(private|spec-pack|workbench)/", re.IGNORECASE),
    re.compile(r"(^|/)docs/INSTALL\.md$", re.IGNORECASE),
    re.compile(r"(^|/)runtime/README\.md$", re.IGNORECASE),
    re.compile(r"(^|/)tools/(cleanup_vnext_workbench|validate_kb_wiki_vnext_spec_pack)\.py$", re.IGNORECASE),
]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_manifest(root: Path) -> tuple[dict[str, object] | None, list[str]]:
    path = root / PRODUCT_DIR / "product.json"
    if not path.exists():
        return None, [f"missing product manifest: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"invalid product manifest: {path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"product manifest must be an object: {path}"]
    return data, []


def _validate_manifest(root: Path, manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if manifest.get("name") != "kb-wiki-vnext":
        errors.append("product.json name must be kb-wiki-vnext")
    if manifest.get("version") != PRODUCT_VERSION:
        errors.append(f"product.json version must be {PRODUCT_VERSION}")

    component_versions = manifest.get("component_versions")
    if not isinstance(component_versions, dict):
        errors.append("product.json component_versions must be an object")
    else:
        for key, expected in REQUIRED_COMPONENT_VERSIONS.items():
            if component_versions.get(key) != expected:
                errors.append(f"component_versions.{key} must be {expected}")

    for key in ("source_paths", "distribution_channels", "required_checks", "authority_limits"):
        if key not in manifest:
            errors.append(f"product.json missing {key}")

    source_paths = manifest.get("source_paths", [])
    if not isinstance(source_paths, list) or not all(isinstance(path, str) for path in source_paths):
        errors.append("product.json source_paths must be a list of strings")
        source_paths = []
    for rel in source_paths:
        if not (root / rel).exists():
            errors.append(f"source path does not exist: {rel}")

    limits = manifest.get("authority_limits", {})
    if isinstance(limits, dict):
        if limits.get("direct_kb_db_mutation") is not False:
            errors.append("direct_kb_db_mutation must be false")
        if limits.get("publishes_kb_wiki_live") is not False:
            errors.append("publishes_kb_wiki_live must be false")
    else:
        errors.append("authority_limits must be an object")

    return errors


def _validate_doc_parity(root: Path) -> list[str]:
    errors: list[str] = []
    en = root / PRODUCT_DIR / "docs" / "en"
    pt = root / PRODUCT_DIR / "docs" / "pt-BR"

    for doc in REQUIRED_DOCS:
        en_path = en / doc
        pt_path = pt / doc
        if not en_path.exists():
            errors.append(f"missing EN doc: {en_path}")
        if not pt_path.exists():
            errors.append(f"missing PT-BR doc: {pt_path}")
        for path in (en_path, pt_path):
            if path.exists():
                text = path.read_text(encoding="utf-8")
                for heading in ("Purpose", "Audience", "Prerequisites", "Verification", "Troubleshooting", "Related"):
                    if heading not in text:
                        errors.append(f"{path} missing section marker: {heading}")

    return errors


def _validate_relative_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted((root / PRODUCT_DIR).rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(text):
            target = match.group(1).split("#", 1)[0]
            if not target:
                continue
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path} link escapes repo: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{path} broken relative link: {target}")
    return errors


def _strip_bundle_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def _resolve_bundle_link(source_name: str, target: str) -> str | None:
    if target.startswith("/"):
        return None
    joined = PurePosixPath(source_name).parent / target.replace("\\", "/")
    normalized: list[str] = []
    for part in joined.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not normalized:
                return None
            normalized.pop()
        else:
            normalized.append(part)
    return "/".join(normalized)


def _validate_bundle(bundle: Path) -> list[str]:
    errors: list[str] = []
    if not bundle.exists():
        return [f"bundle not found: {bundle}"]

    try:
        with zipfile.ZipFile(bundle) as zf:
            names = zf.namelist()
            expected_root = f"kb-wiki-vnext-{PRODUCT_VERSION}/"
            if any(not name.startswith(expected_root) for name in names):
                errors.append(f"bundle entries must be rooted at {expected_root}")
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                errors.append(f"bundle contains duplicate paths: {duplicates[:5]}")
            stripped = {_strip_bundle_root(name) for name in names}
            for required in REQUIRED_BUNDLE_PATHS:
                if required not in stripped:
                    errors.append(f"bundle missing {required}")
            for name in names:
                for pattern in FORBIDDEN_BUNDLE_PATTERNS:
                    if pattern.search(name):
                        errors.append(f"bundle contains forbidden path: {name}")
                        break

            for markdown_name in sorted(name for name in names if name.endswith(".md")):
                try:
                    markdown = zf.read(markdown_name).decode("utf-8")
                except UnicodeDecodeError as exc:
                    errors.append(f"bundle Markdown is not UTF-8: {markdown_name}: {exc}")
                    continue
                for match in LINK_PATTERN.finditer(markdown):
                    target = match.group(1).split("#", 1)[0]
                    if target.startswith("<") and target.endswith(">"):
                        target = target[1:-1]
                    resolved = _resolve_bundle_link(markdown_name, target)
                    if resolved is None or not resolved.startswith(expected_root):
                        errors.append(f"bundle link escapes root: {markdown_name} -> {target}")
                    elif resolved not in name_set:
                        errors.append(f"bundle contains broken link: {markdown_name} -> {target}")

            manifest_name = f"{expected_root}bundle-manifest.json"
            if manifest_name not in names:
                errors.append("bundle missing bundle-manifest.json")
            else:
                try:
                    bundle_manifest = json.loads(zf.read(manifest_name).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"bundle manifest is invalid JSON: {exc}")
                else:
                    if bundle_manifest.get("version") != PRODUCT_VERSION:
                        errors.append(f"bundle manifest version must be {PRODUCT_VERSION}")
                    inventory = bundle_manifest.get("included_paths")
                    if not isinstance(inventory, list) or not all(isinstance(path, str) for path in inventory):
                        errors.append("bundle manifest included_paths must be a list of strings")
                    elif set(inventory) != set(names) - {manifest_name}:
                        errors.append("bundle manifest included_paths does not match bundle inventory")
    except (OSError, zipfile.BadZipFile) as exc:
        return [f"bundle is not a readable ZIP: {bundle}: {exc}"]

    return errors


def validate(bundle: Path | None = None) -> list[str]:
    root = repo_root()
    errors: list[str] = []
    manifest, manifest_errors = _load_manifest(root)
    errors.extend(manifest_errors)
    if manifest is not None:
        errors.extend(_validate_manifest(root, manifest))
    errors.extend(_validate_doc_parity(root))
    errors.extend(_validate_relative_links(root))
    if bundle is not None:
        errors.extend(_validate_bundle(bundle if bundle.is_absolute() else root / bundle))
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors = validate(args.bundle)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        print("KB/Wiki vNext product validation failed:")
        for error in errors:
            print(f"- {error}")
    else:
        print("KB/Wiki vNext product validation passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
