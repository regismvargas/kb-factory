from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "core" / "templates" / "kb"


def run(kb: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(kb / "kb.py"), *args, "--json"],
        cwd=kb.parent,
        text=True,
        capture_output=True,
        check=check,
    )


def make_kb(tmp_path: Path) -> Path:
    kb = tmp_path / ".kb"
    shutil.copytree(TEMPLATE, kb)
    for record_id in ("KB-A", "KB-B", "KB-C"):
        run(
            kb,
            "create",
            "--id",
            record_id,
            "--category",
            "DECISAO",
            "--domain",
            "test",
            "--title",
            record_id,
            "--content",
            record_id,
        )
    return kb


def test_schema_v6_is_additive_and_preserves_hardening_state(tmp_path: Path) -> None:
    plain = make_kb(tmp_path / "plain")
    with sqlite3.connect(plain / "kb.db") as conn:
        assert conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0] == "6"
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM records"
        ).fetchone()[0] == 3

    hardened = make_kb(tmp_path / "hardened")
    run(hardened, "harden")
    with sqlite3.connect(hardened / "kb.db") as conn:
        before = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
    run(hardened, "stats")
    with sqlite3.connect(hardened / "kb.db") as conn:
        after = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
    assert before
    assert after == before


def test_v5_to_v6_migration_preserves_canonical_rows_fts_and_provenance(tmp_path: Path) -> None:
    kb = make_kb(tmp_path)
    with sqlite3.connect(kb / "kb.db") as conn:
        conn.execute("DROP TABLE record_edges")
        conn.execute("UPDATE schema_meta SET value='5' WHERE key='schema_version'")
        before = {
            "records": conn.execute("SELECT * FROM records ORDER BY id").fetchall(),
            "fts": conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()[0],
            "provenance": conn.execute(
                "SELECT * FROM wiki_page_provenance ORDER BY page_id, kind, ref_id"
            ).fetchall(),
            "triggers": conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
            ).fetchall(),
        }
    run(kb, "stats")
    with sqlite3.connect(kb / "kb.db") as conn:
        assert conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0] == "6"
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='record_edges'"
        ).fetchone() is not None
        assert conn.execute("SELECT * FROM records ORDER BY id").fetchall() == before["records"]
        assert conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()[0] == before["fts"]
        assert conn.execute(
            "SELECT * FROM wiki_page_provenance ORDER BY page_id, kind, ref_id"
        ).fetchall() == before["provenance"]
        assert conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
        ).fetchall() == before["triggers"]


def test_typed_edges_are_canonical_audited_and_tombstoned(tmp_path: Path) -> None:
    kb = make_kb(tmp_path)
    added = json.loads(
        run(
            kb,
            "graph",
            "edge-add",
            "KB-B",
            "duplicates",
            "KB-A",
            "--actor",
            "regis",
            "--actor-runtime",
            "human",
            "--note",
            "fixture",
        ).stdout
    )
    assert added["source_record_id"] == "KB-A"
    assert added["target_record_id"] == "KB-B"
    duplicate = run(
        kb,
        "graph",
        "edge-add",
        "KB-A",
        "duplicates",
        "KB-B",
        "--actor",
        "regis",
        "--actor-runtime",
        "human",
        check=False,
    )
    assert duplicate.returncode == 2
    assert "EDGE_DUPLICATE_ACTIVE" in duplicate.stdout

    removed = json.loads(
        run(
            kb,
            "graph",
            "edge-remove",
            added["edge_id"],
            "--actor",
            "regis",
            "--actor-runtime",
            "human",
        ).stdout
    )
    assert removed["removed_at"]
    repeated = run(
        kb,
        "graph",
        "edge-remove",
        added["edge_id"],
        "--actor",
        "regis",
        "--actor-runtime",
        "human",
        check=False,
    )
    assert repeated.returncode == 2
    assert "EDGE_ALREADY_REMOVED" in repeated.stdout
    with sqlite3.connect(kb / "kb.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action LIKE 'graph_edge_%'"
        ).fetchone()[0] == 4
        assert conn.execute(
            "SELECT COUNT(*) FROM operations WHERE category='graph'"
        ).fetchone()[0] == 2


def test_source_link_updates_both_encodings_in_one_human_action(tmp_path: Path) -> None:
    kb = make_kb(tmp_path)
    with sqlite3.connect(kb / "kb.db") as conn:
        conn.execute(
            "INSERT INTO sources(source_id, filename, original_path, stored_path, "
            "content_hash, file_size, mime_type, ingested_at, updated_at, domain, "
            "tags_json, notes, record_ids_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SRC-1",
                "source.md",
                "source.md",
                "sources/SRC-1/source.md",
                "0" * 64,
                1,
                "text/markdown",
                "2026-07-21T00:00:00Z",
                "2026-07-21T00:00:00Z",
                "test",
                "[]",
                None,
                "[]",
            ),
        )
    result = json.loads(
        run(
            kb,
            "graph",
            "source-link",
            "KB-A",
            "SRC-1",
            "--actor",
            "regis",
            "--actor-runtime",
            "human",
        ).stdout
    )
    assert result["record_id"] == "KB-A"
    with sqlite3.connect(kb / "kb.db") as conn:
        assert conn.execute(
            "SELECT source_id FROM records WHERE id='KB-A'"
        ).fetchone()[0] == "SRC-1"
        assert json.loads(
            conn.execute(
                "SELECT record_ids_json FROM sources WHERE source_id='SRC-1'"
            ).fetchone()[0]
        ) == ["KB-A"]


def test_invalid_type_self_and_missing_endpoints_are_explicit(tmp_path: Path) -> None:
    kb = make_kb(tmp_path)
    for source, relation, target, expected in (
        ("KB-A", "relates-to", "KB-B", "EDGE_TYPE_INVALID"),
        ("KB-A", "depends-on", "KB-A", "EDGE_SELF"),
        ("KB-A", "depends-on", "KB-X", "EDGE_ENDPOINT_MISSING"),
    ):
        result = run(
            kb,
            "graph",
            "edge-add",
            source,
            relation,
            target,
            "--actor",
            "regis",
            "--actor-runtime",
            "human",
            check=False,
        )
        assert result.returncode == 2
        assert expected in result.stdout


def test_graph_mutation_rolls_back_state_audit_and_operation_together(tmp_path: Path) -> None:
    kb = make_kb(tmp_path)
    with sqlite3.connect(kb / "kb.db") as conn:
        conn.execute(
            "CREATE TRIGGER reject_graph_operation BEFORE INSERT ON operations "
            "WHEN NEW.category='graph' BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
        baseline_audit = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        baseline_ops = conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    result = run(
        kb,
        "graph",
        "edge-add",
        "KB-A",
        "depends-on",
        "KB-B",
        "--actor",
        "regis",
        "--actor-runtime",
        "human",
        check=False,
    )
    assert result.returncode == 2
    assert "injected failure" in result.stdout
    with sqlite3.connect(kb / "kb.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM record_edges").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == baseline_audit
        assert conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == baseline_ops
