from __future__ import annotations

import json
import sys
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_agent_command_surfaces import (  # noqa: E402
    Document,
    audit_documents,
    discover_plugin_slugs,
    iter_documents,
    run_audit,
)
from build_agent_packages import build_artifacts, write_zip  # noqa: E402


def _categories(documents: list[Document], slugs: set[str] | None = None) -> set[str]:
    findings = audit_documents(
        documents,
        slugs or {"vnext-session-start", "gate-session-start", "gate-session-end"},
    )
    return {finding.category for finding in findings}


def test_bare_session_slug_as_shell_is_fix_required() -> None:
    categories = _categories(
        [
            Document(
                path="plugins/example/README.md",
                text="Run vnext-session-start before doing work.\n",
                source="file",
            )
        ]
    )

    assert "fix_required" in categories


def test_plugin_slash_or_runtime_wording_is_accepted() -> None:
    categories = _categories(
        [
            Document(
                path="plugins/example/README.md",
                text=(
                    "Invoke the `vnext-session-start` plugin/slash command when "
                    "exposed; in shell run python core/versions/kb-wiki-vnext/"
                    "runtime/kb_next.py session-start --json.\n"
                ),
                source="file",
            )
        ]
    )

    assert "fix_required" not in categories
    assert "accepted_specificity" in categories


def test_runtime_subcommand_without_python_surface_is_fix_required() -> None:
    categories = _categories(
        [
            Document(
                path="core/versions/kb-wiki-vnext/spec-pack/use-case-catalog.md",
                text="Flow: run session-start, read NOW.md.\n",
                source="file",
            )
        ]
    )

    assert "fix_required" in categories


def test_explicit_python_runtime_command_is_accepted() -> None:
    categories = _categories(
        [
            Document(
                path="plugins/kb-lifecycle/reference.md",
                text="Run `python .kb/kb.py lifecycle session-start --json`.\n",
                source="file",
            )
        ]
    )

    assert "fix_required" not in categories
    assert "accepted_specificity" in categories


def test_generic_session_command_file_is_fix_required() -> None:
    categories = _categories(
        [
            Document(
                path="plugins/example/commands/session-start.md",
                text="---\ndescription: bad\n---\n",
                source="file",
            )
        ]
    )

    assert "fix_required" in categories


def test_generic_session_command_in_zip_is_fix_required(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad-plugin-0.0.0.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("commands/session-end.md", "---\ndescription: bad\n---\n")

    categories = _categories(
        [
            Document(
                path=f"{archive_path.as_posix()}!commands/session-end.md",
                text="---\ndescription: bad\n---\n",
                source="zip",
            )
        ]
    )

    assert "fix_required" in categories


def test_hook_support_qualified_wording_is_accepted() -> None:
    categories = _categories(
        [
            Document(
                path="plugins/example/README.md",
                text="When hook support is enabled, the hook runs on session start.\n",
                source="file",
            )
        ]
    )

    assert "fix_required" not in categories
    assert "accepted_specificity" in categories


def test_current_source_tree_has_no_fix_required_command_surface_findings() -> None:
    report = run_audit(ROOT, include_dist=False, include_cache=False)
    fix_required = [finding for finding in report.findings if finding.category == "fix_required"]

    assert fix_required == [], json.dumps(
        [finding.__dict__ for finding in fix_required],
        indent=2,
    )


def test_built_kb_plugin_packages_have_no_fix_required_command_surface_findings(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "dist" / "agent-packages"
    for artifact in build_artifacts(ROOT, output_dir, scope="kb"):
        write_zip(artifact)

    documents = iter_documents(
        tmp_path,
        include_dist=True,
        include_cache=False,
        include_all_dist=True,
    )
    findings = audit_documents(documents, discover_plugin_slugs(ROOT))
    fix_required = [finding for finding in findings if finding.category == "fix_required"]

    assert fix_required == [], json.dumps(
        [finding.__dict__ for finding in fix_required],
        indent=2,
    )
