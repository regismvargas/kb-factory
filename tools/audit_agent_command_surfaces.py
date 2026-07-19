"""Audit agent plugin command surfaces for shell/plugin ambiguity.

The audit is intentionally conservative: it flags the small set of wording
patterns that have caused real session-start failures, while allowing explicit
plugin/slash command wording and explicit Python runtime commands.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile


DEFAULT_ROOTS = (
    "plugins",
    "products/kb-wiki-vnext",
    "docs/references",
)
TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml"}
GENERIC_COMMAND_BASENAMES = {"session-start.md", "session-end.md"}
SESSION_SLUGS = {
    "vnext-session-start",
    "vnext-session-end",
    "gate-session-start",
    "gate-session-end",
}
RUNTIME_SUBCOMMANDS = {"session-start", "session-end", "hygiene-audit"}
PLUGIN_EXECUTION_RE = re.compile(
    r"(?<![-\w])(?:run|invoke|execute|call|use|rodar|executar|invoque|rode|usar)(?![-\w])",
    re.IGNORECASE,
)
RUNTIME_EXECUTION_RE = re.compile(
    r"(?<![-\w])(?:run|invoke|execute|call|rodar|executar|invoque|rode)(?![-\w])",
    re.IGNORECASE,
)
SAFE_PLUGIN_RE = re.compile(
    r"\b(plugin|slash|client exposes|when exposed|manual|manually|"
    r"PowerShell/PATH|PATH executable|shell equivalent|runtime|Python|"
    r"comando de plugin|plugin/slash)\b",
    re.IGNORECASE,
)
SAFE_RUNTIME_RE = re.compile(
    r"(python\s+[\w./\\-]+|kb_next\.py|\.kb/kb\.py|\.kb\\kb\.py|"
    r"runtime|plugin/slash|plugin command|comando de plugin|shell equivalent|"
    r"shell contexts?|PowerShell/PATH|generic|alias|basename|command files?|"
    r"do not ship)",
    re.IGNORECASE,
)
HOOK_DRIFT_RE = re.compile(
    r"\bhook\b.*\b(automatic|automatically|fires?|firing|guarantee|"
    r"guaranteed|runs on session start|session start)\b",
    re.IGNORECASE,
)
HOOK_SAFE_RE = re.compile(
    r"\b(when supported|when enabled|manual|manually|not guarantee|"
    r"support is enabled|does not guarantee|reminder|lightweight|"
    r"unavailable|disabled)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Document:
    path: str
    text: str
    source: str


@dataclass(frozen=True)
class Finding:
    category: str
    rule: str
    path: str
    line: int
    text: str
    detail: str


@dataclass(frozen=True)
class AuditReport:
    generated_at: str
    root: str
    findings: list[Finding]

    @property
    def counts(self) -> dict[str, int]:
        return dict(Counter(f.category for f in self.findings))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if _is_text_file(path):
            files.append(path)
    return files


def discover_plugin_slugs(root: Path) -> set[str]:
    slugs: set[str] = set()
    for command_dir in sorted((root / "plugins").glob("*/commands")):
        for command_file in sorted(command_dir.glob("*.md")):
            slugs.add(command_file.stem)
    return slugs


def expected_dist_archive_names(root: Path) -> set[str]:
    expected: set[str] = set()
    for plugin_root in sorted((root / "plugins").glob("*")):
        if not plugin_root.is_dir():
            continue
        codex_manifest = _load_manifest(plugin_root / ".codex-plugin" / "plugin.json")
        claude_manifest = _load_manifest(plugin_root / ".claude-plugin" / "plugin.json")
        manifest = codex_manifest or claude_manifest
        if manifest is None:
            continue
        name = str(manifest.get("name") or plugin_root.name)
        version = str(manifest.get("version") or "0.0.0")
        if codex_manifest is not None:
            expected.add(f"{name}-plugin-{version}.zip")
        if claude_manifest is not None:
            expected.add(f"{name}-claude-plugin-{version}.zip")
            expected.add(f"{name}-cowork-plugin-{version}.zip")
    return expected


def iter_documents(
    root: Path,
    include_dist: bool = True,
    include_cache: bool = True,
    include_all_dist: bool = False,
    extra_roots: tuple[Path, ...] = (),
) -> list[Document]:
    documents: list[Document] = []
    scan_roots = [root / rel for rel in DEFAULT_ROOTS]
    scan_roots.extend(extra_roots)

    for scan_root in scan_roots:
        for path in _iter_files(scan_root):
            text = _read_text(path)
            if text is None:
                continue
            try:
                display = path.relative_to(root).as_posix()
            except ValueError:
                display = str(path)
            documents.append(Document(path=display, text=text, source="file"))

    if include_dist:
        expected_archives = expected_dist_archive_names(root)
        for zip_path in sorted((root / "dist" / "agent-packages").glob("*.zip")):
            if not include_all_dist and expected_archives and zip_path.name not in expected_archives:
                continue
            try:
                with ZipFile(zip_path, "r") as archive:
                    for name in sorted(archive.namelist()):
                        if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                            continue
                        try:
                            text = archive.read(name).decode("utf-8")
                        except UnicodeDecodeError:
                            continue
                        display = f"{zip_path.relative_to(root).as_posix()}!{name}"
                        documents.append(Document(path=display, text=text, source="zip"))
            except (OSError, BadZipFile):
                continue

    if include_cache:
        cache_root = Path.home() / ".codex" / "plugins" / "cache" / "kb-factory-local"
        if cache_root.exists():
            for path in _iter_files(cache_root):
                text = _read_text(path)
                if text is None:
                    continue
                documents.append(Document(path=str(path), text=text, source="cache"))

    return documents


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _has_plugin_execution_verb(line: str) -> bool:
    return PLUGIN_EXECUTION_RE.search(line) is not None


def _has_runtime_execution_verb(line: str) -> bool:
    return RUNTIME_EXECUTION_RE.search(line) is not None


def _add_finding(
    findings: list[Finding],
    category: str,
    rule: str,
    document: Document,
    line_no: int,
    line: str,
    detail: str,
) -> None:
    if document.source == "cache" and category == "fix_required":
        category = "needs_review"
        detail = f"Local cache copy may be stale; source/package audit should drive reinstall. {detail}"
    findings.append(
        Finding(
            category=category,
            rule=rule,
            path=document.path,
            line=line_no,
            text=line.strip(),
            detail=detail,
        )
    )


def _audit_generic_command_files(document: Document, findings: list[Finding]) -> None:
    normalized = document.path.replace("\\", "/")
    if "!" in normalized:
        entry_name = normalized.rsplit("!", 1)[1]
        parts = entry_name.split("/")
    else:
        parts = normalized.split("/")
    if len(parts) >= 2 and parts[-2] == "commands" and parts[-1] in GENERIC_COMMAND_BASENAMES:
        _add_finding(
            findings,
            "fix_required",
            "generic-command-basename",
            document,
            1,
            parts[-1],
            "Distributed command files must use explicit names, not generic session aliases.",
        )


def _audit_plugin_slugs(
    document: Document,
    findings: list[Finding],
    plugin_slugs: set[str],
) -> None:
    for line_no, line in enumerate(document.text.splitlines(), start=1):
        if not _has_plugin_execution_verb(line):
            continue
        lowered = line.lower()
        for slug in sorted(plugin_slugs):
            if slug.lower() not in lowered:
                continue
            explicit_slash = re.compile(
                rf"/(?:[\w-]+:)?{re.escape(slug)}(?![-\w])",
                re.IGNORECASE,
            )
            if SAFE_PLUGIN_RE.search(line) or explicit_slash.search(line):
                _add_finding(
                    findings,
                    "accepted_specificity",
                    "plugin-slug-explicit-surface",
                    document,
                    line_no,
                    line,
                    "Plugin command wording distinguishes plugin/slash or runtime shell behavior.",
                )
                continue
            category = "fix_required" if slug in SESSION_SLUGS else "needs_review"
            _add_finding(
                findings,
                category,
                "plugin-slug-as-shell",
                document,
                line_no,
                line,
                f"`{slug}` is invoked without saying whether it is plugin/slash or shell/runtime.",
            )


def _audit_runtime_subcommands(document: Document, findings: list[Finding]) -> None:
    for line_no, line in enumerate(document.text.splitlines(), start=1):
        if not _has_runtime_execution_verb(line):
            continue
        lowered = line.lower()
        for command in sorted(RUNTIME_SUBCOMMANDS):
            command_re = re.compile(
                rf"(?<![-\w]){re.escape(command)}(?![-\w])",
                re.IGNORECASE,
            )
            if command_re.search(lowered) is None:
                continue
            if SAFE_RUNTIME_RE.search(line):
                _add_finding(
                    findings,
                    "accepted_specificity",
                    "runtime-command-explicit-surface",
                    document,
                    line_no,
                    line,
                    "Runtime command wording includes a Python/runtime/shell surface.",
                )
                continue
            category = "fix_required" if command in {"session-start", "session-end"} else "needs_review"
            _add_finding(
                findings,
                category,
                "runtime-subcommand-ambiguous",
                document,
                line_no,
                line,
                f"`{command}` is invoked without an explicit runtime or shell command.",
            )


def _audit_hook_promises(document: Document, findings: list[Finding]) -> None:
    for line_no, line in enumerate(document.text.splitlines(), start=1):
        if not HOOK_DRIFT_RE.search(line):
            continue
        if HOOK_SAFE_RE.search(line):
            _add_finding(
                findings,
                "accepted_specificity",
                "hook-promise-qualified",
                document,
                line_no,
                line,
                "Hook wording is qualified by support/enabled/manual/reminder language.",
            )
            continue
        _add_finding(
            findings,
            "needs_review",
            "hook-promise-drift",
            document,
            line_no,
            line,
            "Hook wording may imply automatic behavior; qualify by surface support.",
        )


def audit_documents(documents: list[Document], plugin_slugs: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for document in documents:
        _audit_generic_command_files(document, findings)
        _audit_plugin_slugs(document, findings, plugin_slugs)
        _audit_runtime_subcommands(document, findings)
        _audit_hook_promises(document, findings)
    return findings


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _append_version_finding(
    findings: list[Finding],
    category: str,
    rule: str,
    path: str,
    detail: str,
) -> None:
    findings.append(
        Finding(
            category=category,
            rule=rule,
            path=path,
            line=1,
            text="",
            detail=detail,
        )
    )


def audit_package_version_surfaces(root: Path, include_cache: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    dist_dir = root / "dist" / "agent-packages"
    cache_root = Path.home() / ".codex" / "plugins" / "cache" / "kb-factory-local"

    for plugin_root in sorted((root / "plugins").glob("*")):
        if not plugin_root.is_dir():
            continue
        codex_manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        claude_manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        codex_manifest = _load_manifest(codex_manifest_path)
        claude_manifest = _load_manifest(claude_manifest_path)
        manifest = codex_manifest or claude_manifest
        if manifest is None:
            continue
        name = str(manifest.get("name") or plugin_root.name)
        version = str(manifest.get("version") or "0.0.0")
        expected_archives: list[str] = []
        if codex_manifest is not None:
            expected_archives.append(f"{name}-plugin-{version}.zip")
        if claude_manifest is not None:
            expected_archives.extend(
                [
                    f"{name}-claude-plugin-{version}.zip",
                    f"{name}-cowork-plugin-{version}.zip",
                ]
            )

        for archive_name in expected_archives:
            archive_path = dist_dir / archive_name
            if archive_path.is_file():
                _append_version_finding(
                    findings,
                    "accepted_specificity",
                    "package-version-present",
                    archive_path.relative_to(root).as_posix(),
                    f"Expected package for {name} {version} is present.",
                )
            else:
                _append_version_finding(
                    findings,
                    "needs_review",
                    "package-version-missing",
                    archive_path.relative_to(root).as_posix(),
                    f"Expected package for {name} {version} is missing from dist.",
                )

        if include_cache and codex_manifest is not None and cache_root.exists():
            cache_path = cache_root / name / version
            if cache_path.is_dir():
                _append_version_finding(
                    findings,
                    "accepted_specificity",
                    "codex-cache-version-present",
                    str(cache_path),
                    f"Codex local cache has {name} {version}.",
                )
            else:
                _append_version_finding(
                    findings,
                    "needs_review",
                    "codex-cache-version-missing",
                    str(cache_path),
                    f"Codex local cache is missing {name} {version}; reinstall if this cache should be refreshed.",
                )

    return findings


def run_audit(
    root: Path,
    include_dist: bool = True,
    include_cache: bool = True,
    include_all_dist: bool = False,
    extra_roots: tuple[Path, ...] = (),
) -> AuditReport:
    root = root.resolve()
    plugin_slugs = discover_plugin_slugs(root)
    documents = iter_documents(
        root,
        include_dist=include_dist,
        include_cache=include_cache,
        include_all_dist=include_all_dist,
        extra_roots=extra_roots,
    )
    findings = audit_documents(documents, plugin_slugs)
    findings.extend(audit_package_version_surfaces(root, include_cache=include_cache))
    return AuditReport(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        root=str(root),
        findings=findings,
    )


def report_to_json(report: AuditReport) -> str:
    return json.dumps(
        {
            "generated_at": report.generated_at,
            "root": report.root,
            "counts": report.counts,
            "findings": [asdict(finding) for finding in report.findings],
        },
        indent=2,
        sort_keys=True,
    )


def report_to_markdown(report: AuditReport) -> str:
    lines = [
        "# Agent Command Surface Audit",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Root: `{report.root}`",
        "",
        "## Summary",
        "",
    ]
    counts = Counter(f.category for f in report.findings)
    for category in ("fix_required", "needs_review", "accepted_specificity", "false_positive"):
        lines.append(f"- `{category}`: {counts.get(category, 0)}")
    if not report.findings:
        lines.extend(["", "No command surface findings."])
        return "\n".join(lines) + "\n"

    for category in ("fix_required", "needs_review", "accepted_specificity", "false_positive"):
        category_findings = [f for f in report.findings if f.category == category]
        if not category_findings:
            continue
        lines.extend(["", f"## {category}", ""])
        for finding in category_findings:
            location = f"{finding.path}:{finding.line}"
            lines.append(f"- `{finding.rule}` at `{location}`")
            lines.append(f"  - {finding.detail}")
            if finding.text:
                lines.append(f"  - `{finding.text}`")
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit plugin/slash commands, shell commands, hooks, package ZIPs, and local cache wording."
    )
    parser.add_argument("--root", default=str(repo_root()), help="Repository root to audit.")
    parser.add_argument("--no-dist", action="store_true", help="Skip dist/agent-packages ZIP contents.")
    parser.add_argument("--all-dist", action="store_true", help="Scan all ZIPs in dist, including historical artifacts.")
    parser.add_argument("--no-cache", action="store_true", help="Skip local Codex plugin cache.")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown report to stdout.")
    parser.add_argument("--output-dir", default=None, help="Write findings.json and README.md to this directory.")
    parser.add_argument(
        "--fail-on",
        action="append",
        choices=("fix_required", "needs_review", "accepted_specificity", "false_positive"),
        default=[],
        help="Exit non-zero when any listed category is present.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root)
    report = run_audit(
        root,
        include_dist=not args.no_dist,
        include_cache=not args.no_cache,
        include_all_dist=args.all_dist,
    )

    if args.output_dir:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = root / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "findings.json").write_text(report_to_json(report) + "\n", encoding="utf-8")
        (output_dir / "README.md").write_text(report_to_markdown(report), encoding="utf-8")

    if args.json:
        print(report_to_json(report))
    elif args.markdown:
        print(report_to_markdown(report), end="")
    else:
        print(report_to_markdown(report), end="")

    fail_categories = set(args.fail_on)
    if any(finding.category in fail_categories for finding in report.findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
