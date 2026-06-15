"""Validate the KB/Wiki vNext product package and source tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


PRODUCT_DIR = Path("products/kb-wiki-vnext")
REQUIRED_DOCS = [
    "user-manual.md",
    "admin-installation.md",
    "upgrade-rollback.md",
    "architecture.md",
    "maintainer-release.md",
    "troubleshooting.md",
]
REQUIRED_BUNDLE_PATHS = [
    "runtime/kb_next.py",
    "classic-template/.kb/kb.py",
    "plugin/.codex-plugin/plugin.json",
    "product/product.json",
    "product/docs/en/user-manual.md",
    "product/docs/pt-BR/user-manual.md",
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
]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_manifest(root: Path) -> dict[str, object]:
    path = root / PRODUCT_DIR / "product.json"
    if not path.exists():
        raise AssertionError(f"Missing product manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_manifest(root: Path, manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if manifest.get("name") != "kb-wiki-vnext":
        errors.append("product.json name must be kb-wiki-vnext")
    if manifest.get("version") != "0.2.0-rc.1":
        errors.append("product.json version must be 0.2.0-rc.1")

    for key in ("source_paths", "distribution_channels", "required_checks", "authority_limits"):
        if key not in manifest:
            errors.append(f"product.json missing {key}")

    for rel in manifest.get("source_paths", []):
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


def _validate_archive_inventory(root: Path) -> list[str]:
    errors: list[str] = []
    inventory = root / "archive" / "2026-05-vnext-productization" / "inventory.json"
    if not inventory.exists():
        errors.append("missing archive inventory")
        return errors
    data = json.loads(inventory.read_text(encoding="utf-8"))
    if data.get("cleanup_policy") != "archive-first":
        errors.append("archive inventory cleanup_policy must be archive-first")
    if "reversal" not in data:
        errors.append("archive inventory missing reversal block")
    return errors


def _strip_bundle_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def _validate_bundle(bundle: Path) -> list[str]:
    errors: list[str] = []
    if not bundle.exists():
        return [f"bundle not found: {bundle}"]

    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        stripped = {_strip_bundle_root(name) for name in names}
        for required in REQUIRED_BUNDLE_PATHS:
            if required not in stripped:
                errors.append(f"bundle missing {required}")
        for name in names:
            for pattern in FORBIDDEN_BUNDLE_PATTERNS:
                if pattern.search(name):
                    errors.append(f"bundle contains forbidden path: {name}")
                    break

    return errors


def validate(bundle: Path | None = None) -> list[str]:
    root = repo_root()
    errors: list[str] = []
    manifest = _load_manifest(root)
    errors.extend(_validate_manifest(root, manifest))
    errors.extend(_validate_doc_parity(root))
    errors.extend(_validate_relative_links(root))
    errors.extend(_validate_archive_inventory(root))
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
