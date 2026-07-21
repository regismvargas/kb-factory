from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


def create_v5_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    kb = root / ".kb"
    kb.mkdir(parents=True)
    with sqlite3.connect(kb / "kb.db") as conn:
        conn.executescript(
            """
            CREATE TABLE records(
                id TEXT PRIMARY KEY, title TEXT, domain TEXT, status TEXT,
                tags_json TEXT, source TEXT, source_id TEXT,
                supersedes_id TEXT, replacement_id TEXT
            );
            CREATE TABLE sources(
                source_id TEXT PRIMARY KEY, filename TEXT, original_path TEXT,
                stored_path TEXT, record_ids_json TEXT
            );
            CREATE TABLE wiki_pages(
                page_id TEXT PRIMARY KEY, target_slug TEXT, page_class TEXT,
                page_type TEXT, domain TEXT, state TEXT, stored_path TEXT
            );
            CREATE TABLE wiki_page_provenance(
                page_id TEXT, kind TEXT, ref_id TEXT
            );
            CREATE TABLE audit_log(
                audit_id INTEGER PRIMARY KEY, record_id TEXT, action TEXT,
                details_json TEXT
            );
            """
        )
        records = [
            ("KB-A", "A", "alpha", "SUPERSEDIDO", '["shared"]', "manual", None, None, "KB-B"),
            ("KB-B", "B", "alpha", "ATIVO", '["shared"]', "SRC-1", "SRC-1", "KB-A", None),
            ("KB-C", "C", "beta", "ATIVO", '["other"]', "manual", None, None, None),
        ]
        conn.executemany("INSERT INTO records VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", records)
        conn.execute(
            "INSERT INTO sources VALUES(?, ?, ?, ?, ?)",
            ("SRC-1", "source.md", "source.md", "sources/SRC-1/source.md", '["KB-B"]'),
        )
        conn.execute(
            "INSERT INTO wiki_pages VALUES(?, ?, ?, ?, ?, ?, ?)",
            ("PAGE-1", "live/alpha", "live", "domain_overview", "alpha", "managed", "wiki/live/alpha.md"),
        )
        conn.executemany(
            "INSERT INTO wiki_page_provenance VALUES(?, 'record', ?)",
            [("PAGE-1", "KB-A"), ("PAGE-1", "KB-B")],
        )
        conn.execute(
            "INSERT INTO audit_log VALUES(1, 'KB-A', 'superseded', ?)",
            (json.dumps({"replacement_id": "KB-B"}),),
        )
    return root


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNTIME), "--project-root", str(root), *args, "--json"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=check,
    )


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def test_graph_reads_are_pure_and_old_schema_capability_is_explicit(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    db_before = hashlib.sha256((root / ".kb" / "kb.db").read_bytes()).hexdigest()
    next_before = tree_hash(root / ".kb-next")
    commands = [
        ("backlinks", "KB-A"),
        ("lineage", "KB-A"),
        ("neighbors", "KB-A"),
        ("source-records", "SRC-1"),
        ("source-backfill", "--limit", "3"),
    ]
    for command in commands:
        payload = json.loads(run(root, "graph", *command).stdout)
        assert payload["graph_contract_version"] == 1
        assert set(payload) == {
            "graph_contract_version",
            "command",
            "subject",
            "results",
            "warnings",
            "blind_spots",
        }
    neighbors = json.loads(run(root, "graph", "neighbors", "KB-A").stdout)
    assert any(
        warning.get("code") == "TYPED_EDGE_CAPABILITY_UNAVAILABLE"
        for warning in neighbors["warnings"]
    )
    assert hashlib.sha256((root / ".kb" / "kb.db").read_bytes()).hexdigest() == db_before
    assert tree_hash(root / ".kb-next") == next_before


def test_lineage_backlinks_neighbors_and_source_records_are_labeled(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    backlinks = json.loads(run(root, "graph", "backlinks", "KB-A").stdout)
    assert backlinks["results"] == [
        {
            "page_id": "PAGE-1",
            "target_slug": "live/alpha",
            "page_class": "live",
            "page_type": "domain_overview",
            "domain": "alpha",
            "state": "managed",
            "stored_path": "wiki/live/alpha.md",
        }
    ]
    lineage = json.loads(run(root, "graph", "lineage", "KB-A").stdout)["results"][0]
    assert lineage["roots"] == ["KB-A"]
    assert lineage["tips"] == ["KB-B"]
    assert lineage["paths"] == [["KB-A", "KB-B"]]
    neighbors = json.loads(run(root, "graph", "neighbors", "KB-A").stdout)
    kb_b = next(item for item in neighbors["results"] if item["record_id"] == "KB-B")
    assert {origin["kind"] for origin in kb_b["origins"]} == {"domain", "tag", "wiki_page"}
    source_records = json.loads(run(root, "graph", "source-records", "SRC-1").stdout)
    assert source_records["results"][0]["records_source_id"] is True
    assert source_records["results"][0]["source_record_ids_json"] is True


def test_verify_detects_seeded_inconsistency_and_backfill_is_bounded(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    with sqlite3.connect(root / ".kb" / "kb.db") as conn:
        conn.execute("UPDATE records SET replacement_id='KB-C' WHERE id='KB-A'")
    verify = run(root, "graph", "verify", check=False)
    assert verify.returncode == 1
    issue_codes = {item["code"] for item in json.loads(verify.stdout)["results"]}
    assert "SUPERSEDE_RECIPROCAL_MISMATCH" in issue_codes
    invalid = run(root, "graph", "source-backfill", "--limit", "4", check=False)
    assert invalid.returncode == 2
    assert "between 1 and 3" in invalid.stderr


def test_unknown_subject_is_usage_error_and_zero_backlinks_is_valid(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    unknown = run(root, "graph", "backlinks", "KB-X", check=False)
    assert unknown.returncode == 2
    empty = json.loads(run(root, "graph", "backlinks", "KB-C").stdout)
    assert empty["results"] == []


def test_lineage_reports_depth_branch_and_cycle_without_selecting_one_tip(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    with sqlite3.connect(root / ".kb" / "kb.db") as conn:
        conn.executemany(
            "INSERT INTO records VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("KB-D", "D", "alpha", "SUPERSEDIDO", "[]", "manual", None, "KB-B", "KB-E"),
                ("KB-E", "E", "alpha", "ATIVO", "[]", "manual", None, "KB-D", None),
                ("KB-F", "F", "alpha", "ATIVO", "[]", "manual", None, "KB-B", None),
            ],
        )
        conn.execute("UPDATE records SET replacement_id='KB-D' WHERE id='KB-B'")
        conn.executemany(
            "INSERT INTO audit_log(record_id, action, details_json) VALUES(?, 'superseded', ?)",
            [
                ("KB-B", json.dumps({"replacement_id": "KB-D"})),
                ("KB-D", json.dumps({"replacement_id": "KB-E"})),
                ("KB-B", json.dumps({"replacement_id": "KB-F"})),
            ],
        )
    lineage = json.loads(run(root, "graph", "lineage", "KB-A").stdout)
    graph = lineage["results"][0]
    assert ["KB-A", "KB-B", "KB-D", "KB-E"] in graph["paths"]
    assert any(branch["record_id"] == "KB-B" for branch in graph["branches"])
    warning_codes = {warning["code"] for warning in lineage["warnings"]}
    assert "SUPERSEDE_BRANCH" in warning_codes

    with sqlite3.connect(root / ".kb" / "kb.db") as conn:
        conn.execute(
            "INSERT INTO audit_log(record_id, action, details_json) VALUES(?, 'superseded', ?)",
            ("KB-E", json.dumps({"replacement_id": "KB-A"})),
        )
    cyclic = json.loads(run(root, "graph", "lineage", "KB-A").stdout)
    assert cyclic["results"][0]["cycles"]
    assert "SUPERSEDE_CYCLE" in {warning["code"] for warning in cyclic["warnings"]}


def test_source_backfill_returns_at_most_three_exact_candidates(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    with sqlite3.connect(root / ".kb" / "kb.db") as conn:
        for index in range(4):
            record_id = f"KB-X{index}"
            source_id = f"SRC-X{index}"
            conn.execute(
                "INSERT INTO records VALUES(?, ?, 'alpha', 'ATIVO', '[]', ?, NULL, NULL, NULL)",
                (record_id, record_id, source_id),
            )
            conn.execute(
                "INSERT INTO sources VALUES(?, ?, ?, ?, ?)",
                (source_id, f"source-{index}.md", f"source-{index}.md", f"sources/{source_id}/source-{index}.md", json.dumps([record_id])),
            )
    payload = json.loads(run(root, "graph", "source-backfill", "--limit", "3").stdout)
    assert len(payload["results"]) == 3
    assert [item["record_id"] for item in payload["results"]] == ["KB-X0", "KB-X1", "KB-X2"]
    assert all("source_record_ids_json" in item["evidence"] for item in payload["results"])


def test_verify_reports_corrupt_provenance_and_typed_edges_deterministically(tmp_path: Path) -> None:
    root = create_v5_project(tmp_path)
    with sqlite3.connect(root / ".kb" / "kb.db") as conn:
        conn.execute(
            "CREATE TABLE record_edges(edge_id TEXT, source_record_id TEXT, "
            "target_record_id TEXT, relation_type TEXT, removed_at TEXT, "
            "removed_by TEXT, removed_by_runtime TEXT)"
        )
        conn.executemany(
            "INSERT INTO record_edges VALUES(?, ?, ?, ?, ?, ?, ?)",
            [
                ("E-1", "KB-A", "KB-A", "relates-to", None, None, None),
                ("E-2", "KB-A", "KB-X", "depends-on", None, None, None),
                ("E-3", "KB-A", "KB-B", "depends-on", "2026-01-01T00:00:00Z", None, None),
                ("E-4", "KB-A", "KB-B", "depends-on", None, None, None),
                ("E-5", "KB-A", "KB-B", "depends-on", None, None, None),
            ],
        )
        conn.executemany(
            "INSERT INTO wiki_page_provenance VALUES(?, ?, ?)",
            [
                ("PAGE-X", "record", "KB-X"),
                ("PAGE-1", "source", "SRC-X"),
                ("PAGE-1", "invalid", "KB-A"),
            ],
        )
    first = run(root, "graph", "verify", check=False)
    second = run(root, "graph", "verify", check=False)
    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout
    codes = {item["code"] for item in json.loads(first.stdout)["results"]}
    assert {
        "EDGE_TYPE_INVALID",
        "EDGE_SELF",
        "EDGE_ENDPOINT_DANGLING",
        "EDGE_REMOVAL_METADATA_INVALID",
        "EDGE_DUPLICATE_ACTIVE",
        "PROVENANCE_DANGLING_PAGE",
        "PROVENANCE_DANGLING_RECORD",
        "PROVENANCE_DANGLING_SOURCE",
        "PROVENANCE_KIND_INVALID",
    }.issubset(codes)
