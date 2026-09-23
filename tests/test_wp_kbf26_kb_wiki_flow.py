"""WP-KBF.26: KB + Wiki flow repair (kb-wiki mode, lifecycle sync, worktree KB).

Acceptance criteria from the Sponsor kickoff (dispatch/WP-KBF.26_KICKOFF.md):
AC1 a clean kb-wiki init publishes a domain page with no manual step;
AC2 activation syncs the classic config, preserving the rest, and records it;
AC3 lifecycle session-end syncs an enabled wiki;
AC4 no command cites a nonexistent path;
AC5 a worktree without kb.db never gets a silent empty KB;
AC6 regression of the k2-project_3Sigma-Alterra case.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
MASTER_RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
PLUGIN_RUNTIME = REPO / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
TEMPLATE = REPO / "core" / "templates" / "kb"
CORE_RUNTIME = REPO / "core" / "runtime"
WIKI_SYNC_EVENTS = ("record_filed", "source_ingest", "session_end", "scheduled_maintenance")


def _env(**overrides: str | None) -> dict[str, str]:
    env = dict(os.environ)
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True):
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, env=env)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return proc


def run_json(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None):
    return json.loads(run(cmd, cwd=cwd, env=env).stdout)


def kb(project: Path, *args: str, env=None, check=True):
    return run([sys.executable, str(project / ".kb" / "kb.py"), *args], cwd=project, env=env, check=check)


def kb_json(project: Path, *args: str, env=None):
    return json.loads(kb(project, *args, "--json", env=env).stdout)


def vnext(runtime: Path, project: Path, *args: str, check=True, env=None):
    return run(
        [sys.executable, str(runtime), "--project-root", str(project), *args],
        cwd=project,
        env=env,
        check=check,
    )


def vnext_json(runtime: Path, project: Path, *args: str, env=None):
    return json.loads(vnext(runtime, project, *args, "--json", env=env).stdout)


def copy_template(project: Path) -> Path:
    target = project / ".kb"
    shutil.copytree(TEMPLATE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def load_config(project: Path) -> dict:
    return json.loads((project / ".kb" / "kb.config.json").read_text(encoding="utf-8-sig"))


def write_config(project: Path, config: dict) -> None:
    (project / ".kb" / "kb.config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def legacy_config(template_config: dict, *, slug: str, name: str, domains: list[str]) -> dict:
    """Config shape written by the kb-lifecycle 0.2.3 scaffold: sync off on all events."""
    config = copy.deepcopy(template_config)
    config["project"] = {"name": name, "slug": slug, "primary_repo_path": ".", "kb_root": ".kb"}
    config["domains"] = domains
    for block in config["lifecycle"]["events"].values():
        block["run_wiki_sync"] = False
    config["wiki"]["enabled"] = False
    config["wiki"]["activation_mode"] = "manual"
    config.pop("storage", None)
    config.pop("tracking", None)
    return config


def load_module(alias: str, path: Path, package_dir: Path | None = None):
    kwargs = {"submodule_search_locations": [str(package_dir)]} if package_dir else {}
    spec = importlib.util.spec_from_file_location(alias, path, **kwargs)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def classic_runtime():
    return load_module("kbf26_classic_runtime", CORE_RUNTIME / "__init__.py", CORE_RUNTIME)


def vnext_module():
    return load_module("kbf26_kb_next", MASTER_RUNTIME)


def read_operations(project: Path) -> list[dict]:
    path = project / ".kb-next" / "operations.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def live_pages(project: Path) -> list[str]:
    root = project / ".kb" / "wiki" / "live"
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.md")) if root.is_dir() else []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# AC1 — clean new-project kb-wiki init publishes without a manual step
# ---------------------------------------------------------------------------


def test_ac1_new_project_kb_wiki_publishes_without_manual_step(tmp_path: Path) -> None:
    project = tmp_path / "acme"
    project.mkdir()

    installed = vnext_json(
        PLUGIN_RUNTIME, project, "install-classic",
        "--slug", "acme", "--name", "Acme", "--domains", "market,operations",
    )
    assert installed["action"] == "created"
    assert installed["template"]["kind"] in {"plugin_sibling", "authoring_repo"}
    assert installed["project"]["id_prefix"] == "ACME"

    assert vnext_json(PLUGIN_RUNTIME, project, "bootstrap")["action"] == "created"
    workspace_runtime = project / ".kb-next" / "runtime" / "kb_next.py"
    activation = vnext_json(
        workspace_runtime, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki"
    )
    assert activation["classic_config_sync"]["action"] in {"updated", "unchanged"}
    assert activation["classic_wiki_sync"]["action"] == "synced"

    check = kb_json(project, "wiki-check")
    assert check["wiki_state"] != "off"
    assert "market/overview.md" not in live_pages(project)

    created = []
    for index in range(3):
        record = kb_json(
            project, "create", "--category", "FATO", "--domain", "market",
            "--title", f"Market fact {index}", "--content", f"Evidence {index}",
            "--confidence", "0.85",
        )
        created.append(record["id"])
        assert record["id"].startswith("ACME-KB-")

    assert "market/overview.md" in live_pages(project)
    page = (project / ".kb" / "wiki" / "live" / "market" / "overview.md").read_text(encoding="utf-8")
    for record_id in created:
        assert record_id in page


# ---------------------------------------------------------------------------
# AC2 — activation syncs the classic config, preserving everything else
# ---------------------------------------------------------------------------


def _existing_project(tmp_path: Path, *, wiki_enabled: bool = False) -> Path:
    project = tmp_path / "existing"
    project.mkdir()
    copy_template(project)
    config = legacy_config(load_config(project), slug="legacy-co", name="Legacy Co", domains=["ops"])
    config["wiki"]["enabled"] = wiki_enabled
    config["retention"]["hot_review_days"] = 3
    config["custom_owner_key"] = {"keep": ["me", 1]}
    write_config(project, config)
    kb(project, "init")
    return project


def _strip(config: dict, paths: list[str]) -> dict:
    stripped = copy.deepcopy(config)
    for dotted in paths:
        cursor = stripped
        parts = dotted.split(".")
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor.pop(parts[-1], None)
    return stripped


def test_ac2_activation_syncs_classic_config_and_records_it(tmp_path: Path) -> None:
    project = _existing_project(tmp_path)
    before = load_config(project)
    (project / ".kb-next").mkdir()
    previous_vnext = {
        "schema_version": 1,
        "project": {"root": str(project)},
        "activation": {"sponsor_decision": "kb_wiki", "mode": "kb_wiki"},
        "classic_kb": {"root": ".kb", "mode": "read_only"},
        "wiki": {"enabled": True, "authority": "derived", "surfaces": {"machine": True, "human": True}},
        "track_b": {"blocked_source_ids": ["SRC-20260101-000000-abcdef"]},
        "operator_notes": "keep me",
    }
    (project / ".kb-next" / "kb-next.config.json").write_text(json.dumps(previous_vnext), encoding="utf-8")

    result = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")

    after = load_config(project)
    changed = ["wiki.enabled"] + [f"lifecycle.events.{event}.run_wiki_sync" for event in WIKI_SYNC_EVENTS]
    assert after["wiki"]["enabled"] is True
    for event in WIKI_SYNC_EVENTS:
        assert after["lifecycle"]["events"][event]["run_wiki_sync"] is True
    assert after["lifecycle"]["events"]["session_start"]["run_wiki_sync"] is False
    assert _strip(after, changed) == _strip(before, changed)
    assert sorted(c["path"] for c in result["classic_config_sync"]["changes"]) == sorted(changed)

    vnext_config = json.loads((project / ".kb-next" / "kb-next.config.json").read_text(encoding="utf-8"))
    assert vnext_config["operator_notes"] == "keep me"
    assert vnext_config["track_b"]["blocked_source_ids"] == ["SRC-20260101-000000-abcdef"]
    assert vnext_config["project"]["root"] == "."
    assert result["config_merge"]["preserved_existing"] is True

    events = [op["event"] for op in read_operations(project)]
    assert events[-3:] == ["classic-config-sync", "classic-wiki-sync", "activation-wizard"]
    sync_op = next(op for op in read_operations(project) if op["event"] == "classic-config-sync")
    assert sync_op["details"]["action"] == "updated"
    assert {"path": "wiki.enabled", "from": False, "to": True} in sync_op["details"]["changes"]

    again = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")
    assert again["classic_config_sync"]["action"] == "unchanged"


def test_kb_alone_never_turns_an_enabled_classic_wiki_off_implicitly(tmp_path: Path) -> None:
    project = _existing_project(tmp_path, wiki_enabled=True)
    kept = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    assert kept["classic_config_sync"]["action"] == "kept_enabled"
    assert load_config(project)["wiki"]["enabled"] is True

    disabled = vnext_json(
        MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-alone",
        "--disable-classic-wiki",
    )
    assert disabled["classic_config_sync"]["action"] == "updated"
    assert load_config(project)["wiki"]["enabled"] is False


def test_vnext_and_classic_wiki_enable_have_identical_semantics() -> None:
    classic = classic_runtime()
    runtime = vnext_module()
    base = legacy_config(
        json.loads((TEMPLATE / "kb.config.json").read_text(encoding="utf-8-sig")),
        slug="x", name="X", domains=["a"],
    )
    for enabled in (True, False):
        left, right = copy.deepcopy(base), copy.deepcopy(base)
        assert classic.apply_wiki_enabled(left, enabled) == runtime.apply_classic_wiki_enabled(right, enabled)
        assert left == right


# ---------------------------------------------------------------------------
# AC3 — lifecycle session-end syncs the wiki whenever it is enabled
# ---------------------------------------------------------------------------


def test_ac3_session_end_syncs_enabled_wiki(tmp_path: Path) -> None:
    project = tmp_path / "ac3"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "ac3", "--name", "AC3")
    kb_json(project, "wiki-config", "--enable", "--no-sync")
    for index in range(3):
        kb_json(
            project, "create", "--category", "FATO", "--domain", "finance",
            "--title", f"F{index}", "--content", f"C{index}", "--confidence", "0.9",
            "--no-auto-lifecycle",
        )
    assert "finance/overview.md" not in live_pages(project)

    result = kb_json(project, "lifecycle", "session-end")
    assert "wiki_sync" in result["actions_run"]
    assert result["wiki_sync"].get("skipped_reason") is None
    assert "finance/overview.md" in live_pages(project)


def test_ac3_session_end_skips_sync_when_wiki_disabled(tmp_path: Path) -> None:
    project = tmp_path / "ac3-off"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "ac3-off")
    for index in range(3):
        kb_json(project, "create", "--category", "FATO", "--domain", "finance",
                "--title", f"F{index}", "--content", f"C{index}", "--confidence", "0.9")
    result = kb_json(project, "lifecycle", "session-end")
    assert result["wiki_sync"]["skipped_reason"] == "wiki_disabled"
    assert live_pages(project) == []


# ---------------------------------------------------------------------------
# AC4 — no command cites a nonexistent path
# ---------------------------------------------------------------------------

COMMAND_DIRS = (REPO / "plugins" / "kb-wiki-vnext" / "commands", REPO / "plugins" / "session-gate" / "commands")
SCAFFOLD_TOP = {"kb.py", "kb.config.json", "memory", "seed", "runtime", "exports", "SKILL.md", ".gitignore"}
REPO_PREFIXES = ("core/", "plugins/", "tools/", "docs/", "products/")


def _vnext_subcommands() -> set[str]:
    parser = vnext_module().build_parser()
    for action in parser._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            return set(action.choices)
    raise AssertionError("vNext parser has no subcommands")


def _classic_subcommands() -> set[str]:
    cli = load_module("kbf26_classic_cli", CORE_RUNTIME / "cli.py")
    parser = cli.build_parser(defaultdict(lambda: None))
    for action in parser._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            return set(action.choices)
    raise AssertionError("classic parser has no subcommands")


def test_ac4_commands_cite_only_existing_paths_and_commands() -> None:
    vnext_commands = _vnext_subcommands()
    classic_commands = _classic_subcommands()
    problems: list[str] = []
    for directory in COMMAND_DIRS:
        plugin_root = directory.parent
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            label = path.relative_to(REPO).as_posix()
            if "classic-template" in text:
                problems.append(f"{label}: cites classic-template, which ships only in the ZIP bundle")
            for token in re.findall(r"`([^`\n]+)`", text):
                token = token.strip()
                if "<" in token or "*" in token or " " in token:
                    continue
                if token.startswith("${CLAUDE_PLUGIN_ROOT}/"):
                    target = plugin_root / token.split("/", 1)[1]
                    if not target.exists():
                        problems.append(f"{label}: {token} does not exist in the plugin")
                elif token.startswith(REPO_PREFIXES):
                    if not (REPO / token.rstrip("/")).exists():
                        problems.append(f"{label}: {token} does not exist in the repository")
                elif token.startswith(".kb/"):
                    rest = token[len(".kb/"):].rstrip("/")
                    if rest.split("/", 1)[0] in SCAFFOLD_TOP and not (TEMPLATE / rest).exists():
                        problems.append(f"{label}: {token} is not provided by the classic scaffold")
            for match in re.finditer(
                r"(?:kb_next\.py|<resolved-runtime-path>|<new-source-runtime>|<restored-source-runtime>)"
                r"(?:\s+--project-root\s+\S+)?\s+([a-z][a-z-]+)",
                text,
            ):
                if match.group(1) not in vnext_commands:
                    problems.append(f"{label}: unknown vNext runtime subcommand {match.group(1)!r}")
            for match in re.finditer(r"\.kb/kb\.py\s+([a-z][a-z-]+)", text):
                if match.group(1) not in classic_commands:
                    problems.append(f"{label}: unknown classic subcommand {match.group(1)!r}")
    assert problems == []


def test_ac4_hooks_invoke_existing_entrypoints() -> None:
    hooks = json.loads((REPO / "plugins" / "kb-wiki-vnext" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "runtime/kb_next.py" in command and "session-hint" in command
    assert (REPO / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py").is_file()
    assert "session-hint" in _vnext_subcommands()


# ---------------------------------------------------------------------------
# AC5 — worktree without kb.db never gets a silent empty KB
# ---------------------------------------------------------------------------

GIT = shutil.which("git")


def _git(cwd: Path, *args: str) -> None:
    run(["git", "-c", "user.name=kbf", "-c", "user.email=kbf@localhost", *args], cwd=cwd)


@pytest.mark.skipif(GIT is None, reason="git is required for worktree tests")
def test_ac5_worktree_without_kb_db_fails_closed_then_shares_main_kb(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    copy_template(main)
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "scaffold")
    worktree = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "session", str(worktree))
    shared = _env(KB_FACTORY_WORKTREE_SCOPE=None)

    missing = kb(worktree, "list", "--json", env=shared, check=False)
    assert missing.returncode != 0
    assert "KB database not found" in missing.stderr
    assert "linked Git worktree" in missing.stderr
    assert not (worktree / ".kb" / "kb.db").exists()
    assert not (main / ".kb" / "kb.db").exists()

    kb(main, "init", "--slug", "shared-kb", env=shared)
    created = kb_json(
        worktree, "create", "--category", "FATO", "--domain", "ops",
        "--title", "Written from the worktree", "--content", "lands in main", "--no-auto-lifecycle",
        env=shared,
    )
    assert not (worktree / ".kb" / "kb.db").exists()
    main_ids = [row["id"] for row in kb_json(main, "list", env=shared)]
    assert created["id"] in main_ids
    storage = kb_json(worktree, "doctor", env=shared)["storage"]
    assert storage["resolution"] == "main_worktree"
    assert Path(storage["kb_root"]).resolve() == (main / ".kb").resolve()

    vnext_json(MASTER_RUNTIME, worktree, "activation-wizard", "--mode", "short", "--choice", "kb-alone", env=shared)
    lookup = vnext_json(MASTER_RUNTIME, worktree, "lookup", "--facet", "status", "--domain", "ops", env=shared)
    assert [row["id"] for row in lookup["results"]] == [created["id"]]

    local = kb(worktree, "list", "--json", env=_env(KB_FACTORY_WORKTREE_SCOPE="local"), check=False)
    assert local.returncode != 0
    assert "worktree_scope=local" in local.stderr
    assert not (worktree / ".kb" / "kb.db").exists()


def test_ac5_missing_db_outside_git_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    project.mkdir()
    copy_template(project)
    for args in (
        ("list", "--json"),
        ("lifecycle", "session-start", "--json"),
        ("create", "--category", "FATO", "--domain", "ops", "--title", "t", "--content", "c", "--json"),
    ):
        result = kb(project, *args, check=False)
        assert result.returncode != 0, args
        assert "KB database not found" in result.stderr
    assert not (project / ".kb" / "kb.db").exists()
    doctor = kb_json(project, "doctor")
    assert doctor["db_exists"] is False
    assert not (project / ".kb" / "kb.db").exists()


# ---------------------------------------------------------------------------
# AC6 — regression of the k2-project_3Sigma-Alterra case
# ---------------------------------------------------------------------------

K2_DOMAINS = [
    ("paquistao", 20), ("operations", 5), ("metodo", 5), ("proposta", 4), ("product", 3),
    ("governanca", 2), ("editorial", 2), ("mercado", 1), ("fontes", 1), ("architecture", 1),
]
K2_SOURCE_ID = "SRC-20260920-131400-a1b2c3"


def _k2_fixture(tmp_path: Path) -> Path:
    project = tmp_path / "k2"
    project.mkdir()
    copy_template(project)
    config = legacy_config(
        load_config(project), slug="k2-3sigma-alterra", name="3Sigma-Alterra",
        domains=[name for name, _ in K2_DOMAINS],
    )
    write_config(project, config)
    kb(project, "init")

    source_dir = project / ".kb" / "sources" / K2_SOURCE_ID
    source_dir.mkdir(parents=True)
    source_file = source_dir / "brief.txt"
    source_file.write_text("Alterra briefing.\n", encoding="utf-8")
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        "INSERT INTO sources(source_id, filename, original_path, stored_path, content_hash, file_size, "
        "mime_type, ingested_at, updated_at, domain, tags_json, notes, record_ids_json) "
        "VALUES (?, ?, ?, ?, ?, ?, 'text/plain', '2026-09-20T13:14:00Z', '2026-09-20T13:14:00Z', "
        "'fontes', '[]', NULL, '[]')",
        (
            K2_SOURCE_ID, "brief.txt", "/old-machine/k2/brief.txt",
            f"/old-machine/k2/.kb/sources/{K2_SOURCE_ID}/brief.txt",
            sha256(source_file), source_file.stat().st_size,
        ),
    )
    conn.commit()
    conn.close()

    rows = []
    pending = {("paquistao", 1), ("paquistao", 2), ("operations", 1), ("metodo", 1), ("proposta", 1)}
    for domain, count in K2_DOMAINS:
        for index in range(count):
            confidence = 0.9
            if (domain, index) == ("paquistao", 0):
                confidence = 0.6
            if (domain, index) == ("product", 0):
                confidence = 0.7
            category = "PENDENCIA" if (domain, index) in pending else ("FATO", "DECISAO", "APRENDIZADO")[index % 3]
            rows.append(
                {
                    "id": f"K2-3SIGMA-ALTERRA-KB-{len(rows) + 1:04d}",
                    "category": category,
                    "domain": domain,
                    "title": f"{domain} record {index}",
                    "content": f"{domain} content {index}",
                    "confidence": confidence,
                    "tags": [],
                    "source_id": K2_SOURCE_ID if domain == "fontes" else None,
                }
            )
    taggable = [row for row in rows if row["confidence"] >= 0.8]
    for tag_index in range(18):
        for offset in range(3):
            taggable[(3 * tag_index + offset) % len(taggable)]["tags"].append(f"t{tag_index:02d}")
    seed = project / "k2-records.jsonl"
    seed.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    kb(project, "bulk-import", str(seed))

    (project / ".kb-next" / "decisions").mkdir(parents=True)
    (project / ".kb-next" / "kb-next.config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "runtime": {"name": "kb-wiki-vnext", "version_line": "kb-wiki-vnext", "root": ".kb-next"},
                "project": {"root": str(project)},
                "activation": {"mode": "kb_wiki", "source": "short", "sponsor_decision": "kb_wiki"},
                "classic_kb": {"root": ".kb", "mode": "read_only"},
                "wiki": {"enabled": True, "authority": "derived", "surfaces": {"machine": True, "human": True}},
                "session_start": {
                    "required": True,
                    "default_reads": ["NOW.md"],
                    "on_demand_reads": ["HOT.md"],
                    "historical_artifact_allowed_reasons": ["rationale"],
                },
                "memory_facets": {"access_policy": "targeted_lookup"},
            }
        ),
        encoding="utf-8",
    )
    return project


def test_ac6_k2_regression(tmp_path: Path) -> None:
    project = _k2_fixture(tmp_path)

    # The 0.1.9 state: KB + Wiki recorded in .kb-next only, classic wiki off.
    before = kb_json(project, "wiki-check")
    assert before["wiki_state"] == "off"
    assert before["wiki_enabled_in_config"] is False
    assert before["hard_signals"]["active_record_count"] == 44
    assert before["hard_signals"]["domains_with_active_records"] == 10
    assert before["hard_signals"]["open_pendencias"] == 5
    assert before["candidate_count"] == 24
    assert live_pages(project) == []
    status = vnext_json(MASTER_RUNTIME, project, "session-start")["wiki"]["status"]
    assert status == "classic_wiki_off"

    # The upgrade path: re-apply the recorded kb-wiki decision.
    result = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")
    assert result["classic_config_sync"]["action"] == "updated"
    assert result["classic_wiki_sync"]["action"] == "synced"
    assert result["classic_wiki_sync"]["written_count"] == 4

    after = kb_json(project, "wiki-check")
    assert after["wiki_state"] == "active"
    publication = after["publication"]
    assert publication["publishable_count"] == 4
    assert publication["held_back_by_reason"] == {
        "confidence_below_autopublish": 2,
        "insufficient_sources_research_synthesis": 18,
    }
    assert sorted(live_pages(project)) == [
        "metodo/overview.md",
        "operations/overview.md",
        "proposta/overview.md",
        f"sources/{K2_SOURCE_ID}.md",
    ]
    assert all(after["lifecycle_sync_events"][event] for event in WIKI_SYNC_EVENTS)
    assert vnext_json(MASTER_RUNTIME, project, "session-start")["wiki"]["status"] == "aligned"
    vnext_config = json.loads((project / ".kb-next" / "kb-next.config.json").read_text(encoding="utf-8"))
    assert vnext_config["project"]["root"] == "."

    # The source recorded with an absolute path from another machine resolves
    # through re-rooting and is normalized by source-relink.
    assert kb_json(project, "doctor")["sources_missing_files"] == 0
    relink = kb_json(project, "source-relink")
    assert relink["changed_count"] == 1
    info = kb_json(project, "source-info", K2_SOURCE_ID)
    assert info["stored_path"] == f"sources/{K2_SOURCE_ID}/brief.txt"


# ---------------------------------------------------------------------------
# Remaining defects (P1/P2)
# ---------------------------------------------------------------------------


def test_reads_never_modify_kb_db(tmp_path: Path) -> None:
    project = tmp_path / "reads"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "reads", "--seed", "seed/initial_records.jsonl")
    record_id = kb_json(project, "list")[0]["id"]
    digest = sha256(project / ".kb" / "kb.db")
    for args in (
        ("list",), ("get", record_id), ("search", "KB"), ("stats",), ("pending",), ("wiki-check",),
        ("wiki-candidates",), ("doctor",), ("oplog",), ("sources",), ("audit-tiers",),
        ("filing-status",), ("lifecycle", "session-start"),
    ):
        kb(project, *args, "--json")
    assert sha256(project / ".kb" / "kb.db") == digest


def test_init_flags_render_config_seed_and_id_prefix(tmp_path: Path) -> None:
    project = tmp_path / "init"
    project.mkdir()
    copy_template(project)
    no_slug = kb(project, "init", "--seed", "seed/initial_records.jsonl", check=False)
    assert no_slug.returncode != 0
    assert "unresolved placeholders" in no_slug.stderr
    assert kb(project, "init", "--slug", "Bad Slug", check=False).returncode != 0

    kb(project, "init", "--name", "Gauss Labs", "--slug", "gauss-labs", "--domains", "quant,ops",
       "--seed", "seed/initial_records.jsonl")
    config = load_config(project)
    assert config["project"]["name"] == "Gauss Labs"
    assert config["project"]["slug"] == "gauss-labs"
    assert config["project"]["id_prefix"] == "GAUSS-LABS"
    assert config["domains"] == ["quant", "ops"]
    ids = sorted(row["id"] for row in kb_json(project, "list"))
    assert ids == [f"GAUSS-LABS-KB-000{n}" for n in range(1, 6)]
    assert not any("{{" in json.dumps(row) for row in kb_json(project, "list"))

    kb(project, "init", "--id-prefix", "")
    legacy = kb_json(project, "create", "--category", "FATO", "--domain", "ops",
                     "--title", "t", "--content", "c", "--no-auto-lifecycle")
    assert re.fullmatch(r"KB-\d{14}-[0-9a-f]{6}", legacy["id"])


def test_vnext_lookup_filters_and_matches_domain(tmp_path: Path) -> None:
    project = tmp_path / "lookup"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "lookup")
    for domain in ("alpha", "beta"):
        kb_json(project, "create", "--category", "FATO", "--domain", domain,
                "--title", f"{domain} fact", "--content", "shared words", "--no-auto-lifecycle")
    vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    scoped = vnext_json(MASTER_RUNTIME, project, "lookup", "--facet", "status", "--domain", "beta")
    assert {row["domain"] for row in scoped["results"]} == {"beta"}
    by_query = vnext_json(MASTER_RUNTIME, project, "lookup", "--facet", "status", "--query", "alpha")
    assert {row["domain"] for row in by_query["results"]} == {"alpha"}


def test_session_hooks_never_give_conflicting_default_reads(tmp_path: Path) -> None:
    classic_hook = REPO / "plugins" / "kb-lifecycle" / "scripts" / "session_start_context.py"
    project = tmp_path / "hooks"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "hooks")

    assert vnext(MASTER_RUNTIME, project, "session-hint").stdout == ""
    classic_only = run([sys.executable, str(classic_hook)], cwd=project).stdout
    assert "lifecycle session-start" in classic_only

    vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    hint = vnext(MASTER_RUNTIME, project, "session-hint").stdout
    assert ".kb-next/memory/NOW.md" in hint
    deferring = run([sys.executable, str(classic_hook)], cwd=project).stdout
    assert "do not preload `.kb/memory/NOW.md`" in deferring
    assert "lifecycle session-start" not in deferring


def test_source_paths_are_relative_and_survive_a_move(tmp_path: Path) -> None:
    project = tmp_path / "before"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "moves")
    document = project / "notes.txt"
    document.write_text("portable\n", encoding="utf-8")
    ingested = kb_json(project, "ingest", str(document), "--domain", "ops", "--no-auto-lifecycle")
    assert ingested["stored_path"] == f"sources/{ingested['source_id']}/notes.txt"
    assert ingested["original_path"] == "notes.txt"

    moved = tmp_path / "after"
    shutil.copytree(project, moved)
    shutil.rmtree(project)
    verify = kb_json(moved, "source-verify")
    assert verify["violation_count"] == 0
    content = kb_json(moved, "source-content", ingested["source_id"])
    assert content["content"].strip() == "portable"


def test_wiki_enabled_means_on_in_every_activation_mode() -> None:
    compute = classic_runtime().compute_wiki_state
    weak_hard, weak_soft = {"any_hard_signal": False}, {"soft_signal_score": 0}
    for mode in ("manual", "signal", "profile", "unknown"):
        cfg = {"enabled": True, "activation_mode": mode, "page_types": ["domain_overview"]}
        assert compute(cfg, weak_hard, weak_soft, 1) == "active", mode
        assert compute(cfg, weak_hard, weak_soft, 0) == "eligible", mode
    for mode in ("manual", "unknown"):
        cfg = {"enabled": False, "activation_mode": mode, "page_types": ["domain_overview"]}
        assert compute(cfg, {"any_hard_signal": True}, {"soft_signal_score": 9}, 5) == "off", mode


def test_wiki_draft_status_tracks_the_draft_lifecycle(tmp_path: Path) -> None:
    project = tmp_path / "drafts"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "drafts")
    for index in range(3):
        kb_json(project, "create", "--category", "FATO", "--domain", "strategy",
                "--title", f"S{index}", "--content", f"strategy {index}", "--confidence", "0.9",
                "--no-auto-lifecycle")
    vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")

    def state() -> str:
        status = vnext_json(MASTER_RUNTIME, project, "wiki-draft-status")
        return {topic["topic"]: topic["state"] for topic in status["topics"]}["strategy"]

    assert state() == "needs_synthesis"
    assert vnext_json(MASTER_RUNTIME, project, "session-start")["wiki_drafts"]["needs_synthesis"] >= 1

    plan = vnext_json(MASTER_RUNTIME, project, "wiki-synthesis-plan", "--topic", "strategy", "--domain", "strategy")
    ids = [row["id"] for row in plan["candidate_records"] if row["domain"] == "strategy"]
    judgment = tmp_path / "judgment.json"
    judgment.write_text(
        json.dumps(
            {
                "supporting_record_ids": ids,
                "rationale": "All three strategy facts.",
                "confidence": 0.9,
                "machine_draft": "# strategy\n\nFacts S0-S2.\n",
                "human_draft": "# Strategy\n\nThree facts.\n",
            }
        ),
        encoding="utf-8",
    )
    vnext_json(MASTER_RUNTIME, project, "wiki-synthesis-plan", "--topic", "strategy", "--domain", "strategy",
               "--judgment", f"@{judgment}", "--write-drafts")
    assert state() == "needs_review"

    review = vnext_json(MASTER_RUNTIME, project, "wiki-draft-review", "--topic", "strategy", "--materialize")
    assert review["status"] == "valid" and review["materialized"] is True
    assert state() == "current"

    time.sleep(1.1)  # record timestamps have one-second resolution
    kb_json(project, "create", "--category", "FATO", "--domain", "strategy",
            "--title", "S3", "--content", "new", "--confidence", "0.9", "--no-auto-lifecycle")
    assert state() == "stale"


def test_upgrade_classic_refreshes_engine_only(tmp_path: Path) -> None:
    project = tmp_path / "upgrade"
    project.mkdir()
    copy_template(project)
    kb(project, "init", "--slug", "upgrade")
    kb_json(project, "create", "--category", "FATO", "--domain", "ops", "--title", "keep",
            "--content", "data", "--no-auto-lifecycle")
    config = load_config(project)
    config["custom_owner_key"] = "untouched"
    write_config(project, config)
    wiki_py = project / ".kb" / "runtime" / "wiki.py"
    wiki_py.write_text("# stale engine\n" + wiki_py.read_text(encoding="utf-8"), encoding="utf-8")
    (project / ".kb" / ".gitignore").unlink()
    db_digest = sha256(project / ".kb" / "kb.db")
    config_digest = sha256(project / ".kb" / "kb.config.json")

    result = vnext_json(MASTER_RUNTIME, project, "upgrade-classic", "--template", str(TEMPLATE))
    assert result["changed_files"] == ["runtime/wiki.py"]
    assert result["gitignore_added"] is True
    assert wiki_py.read_bytes() == (TEMPLATE / "runtime" / "wiki.py").read_bytes()
    assert sha256(project / ".kb" / "kb.db") == db_digest
    assert sha256(project / ".kb" / "kb.config.json") == config_digest
    again = vnext_json(MASTER_RUNTIME, project, "upgrade-classic", "--template", str(TEMPLATE))
    assert again["action"] == "unchanged"


def test_install_classic_never_overwrites(tmp_path: Path) -> None:
    project = tmp_path / "exists"
    project.mkdir()
    copy_template(project)
    result = vnext_json(MASTER_RUNTIME, project, "install-classic", "--slug", "exists")
    assert result["action"] == "exists"

    busy = tmp_path / "busy"
    (busy / ".kb").mkdir(parents=True)
    (busy / ".kb" / "notes.md").write_text("user data\n", encoding="utf-8")
    refused = vnext(MASTER_RUNTIME, busy, "install-classic", "--slug", "busy", "--json", check=False)
    assert refused.returncode != 0
    assert (busy / ".kb" / "notes.md").read_text(encoding="utf-8") == "user data\n"

    (tmp_path / "new").mkdir()
    missing = vnext(MASTER_RUNTIME, tmp_path / "new", "install-classic", "--slug", "new",
                    "--template", str(tmp_path / "nowhere"), "--json", check=False)
    assert missing.returncode != 0
    assert "not a classic KB scaffold" in missing.stderr


def test_release_tools_bundle_from_a_desktop_worktree_path() -> None:
    """The stand-alone builder judges paths relative to the walked tree, so a
    checkout under `.claude/worktrees/` bundles its own files while nested
    worktrees, state/runs and live wiki pages inside a tree stay excluded."""
    if str(REPO / "tools") not in sys.path:
        sys.path.insert(0, str(REPO / "tools"))
    builder = load_module("kbf26_build_standalone", REPO / "tools" / "build_vnext_standalone.py")
    root = Path("/repo/.claude/worktrees/session-1/plugins/kb-wiki-vnext")
    check = builder._is_forbidden_source
    assert check(root / "commands" / "vnext-wiki-drafts.md", root) is False
    assert check(root / "commands" / "vnext-wiki-drafts.md") is True
    assert check(root / ".claude" / "worktrees" / "x" / "a.md", root) is True
    assert check(root / "state" / "runs" / "r" / "a.md", root) is True
    assert check(root / ".kb" / "wiki" / "live" / "a.md", root) is True


def test_reactivation_preserves_curated_now_and_the_recorded_decision(tmp_path: Path) -> None:
    """Re-running the wizard (upgrades, portfolio rollouts) must not replace a
    curated NOW.md with the template or reset the decision's date and rationale."""
    project = _existing_project(tmp_path)
    first = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki",
                       "--rationale", "Owner chose KB + Wiki for the research program.")
    assert first["now"]["action"] == "created"
    assert first["decision"] == "recorded"
    now = project / ".kb-next" / "memory" / "NOW.md"
    decision_file = project / ".kb-next" / "decisions" / "activation-decision.json"
    recorded = json.loads(decision_file.read_text(encoding="utf-8"))

    again = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")
    assert again["now"]["action"] == "regenerated"  # a generated template is safe to refresh
    kept = json.loads(decision_file.read_text(encoding="utf-8"))
    assert again["decision"] == "reconfirmed"
    assert kept["decided_at"] == recorded["decided_at"]
    assert kept["rationale"] == "Owner chose KB + Wiki for the research program."
    assert "reconfirmed_at" in kept

    curated = "# NOW - research program\n\nStatus written by the team; not a template.\n"
    now.write_text(curated, encoding="utf-8")
    third = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")
    assert third["now"]["action"] == "preserved"
    assert now.read_text(encoding="utf-8") == curated
    last_op = read_operations(project)[-1]
    assert last_op["details"]["now"] == "preserved"
    assert last_op["details"]["decision"] == "reconfirmed"

    switched = vnext_json(MASTER_RUNTIME, project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    assert switched["decision"] == "changed"
    changed = json.loads(decision_file.read_text(encoding="utf-8"))
    assert changed["sponsor_decision"] == "kb_alone"
    assert changed["previous_decision"]["sponsor_decision"] == "kb_wiki"
    assert changed["previous_decision"]["decided_at"] == recorded["decided_at"]


def test_generated_now_detection_recognizes_old_templates_only() -> None:
    module = vnext_module()
    old_template = (
        "# KB/Wiki vNext NOW\n\n- Generated: `2026-07-19T22:45:46Z`\n- Activation mode: `kb_wiki`\n\n"
        "## Required Default Read\n- Read this `NOW.md` only.\n\n## On Demand\n- Use `lookup` as fallback.\n"
    )
    assert module.is_generated_now(old_template) is True
    assert module.is_generated_now(old_template + "\n## Status (2026-07-21)\n\nDesign notes.\n") is False
    assert module.is_generated_now("# NOW - project\n\n- item\n") is False
