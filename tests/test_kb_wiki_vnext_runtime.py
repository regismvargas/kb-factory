from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
KB_NEXT = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


def run_next(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(KB_NEXT), "--project-root", str(project_root), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def run_next_json(project_root: Path, *args: str) -> dict:
    result = run_next(project_root, *args, "--json")
    return json.loads(result.stdout)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markdown_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _start, raw, _body = text.split("---", 2)
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return parsed


def markdown_body_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    _start, _raw, body = text.split("---", 2)
    return hashlib.sha256(body.lstrip("\n").encode("utf-8")).hexdigest()


def is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def ensure_sources_table(project: Path) -> None:
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT,
            ingested_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            domain TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT,
            record_ids_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.commit()
    conn.close()


def add_source(
    project: Path,
    source_id: str,
    content: str,
    *,
    tags: list[str] | None = None,
    expected_hash: str | None = None,
) -> str:
    ensure_sources_table(project)
    source_dir = project / ".kb" / "sources" / source_id
    source_dir.mkdir(parents=True)
    source_path = source_dir / f"{source_id}.txt"
    source_path.write_text(content, encoding="utf-8")
    content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        """
        INSERT INTO sources (
            source_id, filename, original_path, stored_path, content_hash,
            file_size, mime_type, ingested_at, updated_at, domain,
            tags_json, notes, record_ids_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            source_path.name,
            str(source_path),
            str(source_path),
            expected_hash or content_hash,
            source_path.stat().st_size,
            "text/plain",
            "2026-05-25T00:00:00Z",
            "2026-05-25T00:00:00Z",
            "research",
            json.dumps(tags or []),
            None,
            json.dumps([]),
        ),
    )
    conn.commit()
    conn.close()
    return content_hash


def add_track_b_record(
    project: Path,
    record_id: str,
    *,
    source_id: str | None = None,
    content: str = "Track B candidate.",
    tags: list[str] | None = None,
) -> None:
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        """
        INSERT INTO records (
            id, category, domain, title, content, status, tier, source,
            tags_json, created_at, updated_at, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            "FATO",
            "research",
            f"Track B candidate {record_id}",
            content,
            "ATIVO",
            "WARM",
            "test",
            json.dumps(tags or ["track-b-candidate"]),
            "2026-05-25T00:00:00Z",
            "2026-05-25T00:00:00Z",
            source_id,
        ),
    )
    conn.commit()
    conn.close()


def add_active_source_linkage_pendencia(project: Path) -> None:
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        """
        INSERT INTO records (
            id, category, domain, title, content, status, tier, source,
            tags_json, created_at, updated_at, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "KB-20260525141938-0cd4cc",
            "PENDENCIA",
            "wiki",
            "Canonical source-linkage debt blocks external human wiki Track B",
            "Track B remains blocked until source-linkage is resolved.",
            "ATIVO",
            "HOT",
            "test",
            json.dumps(["kb-wiki-vnext", "track-b"]),
            "2026-05-25T00:00:00Z",
            "2026-05-25T00:00:00Z",
            None,
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    kb_root = tmp_path / ".kb"
    kb_root.mkdir()
    memory_root = kb_root / "memory"
    memory_root.mkdir()
    (memory_root / "HOT.md").write_text("# HOT\n", encoding="utf-8")
    (memory_root / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")

    conn = sqlite3.connect(kb_root / "kb.db")
    conn.executescript(
        """
        CREATE TABLE records (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL,
            tier TEXT NOT NULL,
            source TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_id TEXT
        );
        """
    )
    rows = [
        (
            "DEC-1",
            "DECISAO",
            "architecture",
            "Use side-by-side vNext runtime",
            "The vNext runtime remains side-by-side and reads the classic KB only.",
            "ATIVO",
            "HOT",
            "test",
            json.dumps(["kb-wiki-vnext"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            None,
        ),
        (
            "LEARN-1",
            "APRENDIZADO",
            "operations",
            "Thin session start reduces context load",
            "Only NOW.md is mandatory by default.",
            "ATIVO",
            "WARM",
            "test",
            json.dumps(["session-start"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            None,
        ),
        (
            "OPEN-1",
            "PENDENCIA",
            "architecture",
            "Implement machine and human wiki generation",
            "Future work after activation wizard.",
            "ATIVO",
            "WARM",
            "test",
            json.dumps(["wiki"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            None,
        ),
        (
            "DEF-1",
            "FATO",
            "architecture",
            "Definition: machine wiki",
            "Machine wiki is the structured derived surface for agents.",
            "ATIVO",
            "WARM",
            "test",
            json.dumps(["definition", "wiki"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            None,
        ),
        (
            "STAT-1",
            "FATO",
            "operations",
            "Runtime package is in progress",
            "Initial runtime implementation is being validated.",
            "ATIVO",
            "HOT",
            "test",
            json.dumps(["status"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            None,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO records (
            id, category, domain, title, content, status, tier, source,
            tags_json, created_at, updated_at, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return tmp_path


def test_short_kb_alone_activation_creates_kb_next_without_wiki(project: Path) -> None:
    result = run_next_json(
        project,
        "activation-wizard",
        "--mode",
        "short",
        "--choice",
        "kb-alone",
    )

    config_path = Path(result["paths"]["config"])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["activation"]["sponsor_decision"] == "kb_alone"
    assert config["activation"]["source"] == "short"
    assert config["wiki"]["enabled"] is False
    assert config["wiki"]["surfaces"] == {"machine": False, "human": False}
    assert "semantic-hygiene" in config["semantic_curation"]["commands"]
    assert (project / ".kb-next" / "memory" / "NOW.md").is_file()
    assert (project / ".kb-next" / "operations.jsonl").is_file()


def test_short_kb_wiki_activation_enables_machine_and_human_surfaces(project: Path) -> None:
    result = run_next_json(
        project,
        "activation-wizard",
        "--mode",
        "short",
        "--choice",
        "kb-wiki",
    )

    config = json.loads(Path(result["paths"]["config"]).read_text(encoding="utf-8"))
    assert config["activation"]["sponsor_decision"] == "kb_wiki"
    assert config["wiki"]["enabled"] is True
    assert config["wiki"]["surfaces"] == {"machine": True, "human": True}


def test_guided_activation_uses_deterministic_recommendation(project: Path) -> None:
    answers = {
        "human_documentation": "high",
        "auditability": "high",
        "history_volume": "medium",
        "memory_granularity": "high",
        "multi_agent": "medium",
        "maintenance_capacity": "medium",
    }
    result = run_next_json(
        project,
        "activation-wizard",
        "--mode",
        "guided",
        "--answers",
        json.dumps(answers),
    )

    activation = result["activation"]
    assert activation["recommended_mode"] == "kb_wiki"
    assert activation["sponsor_decision"] == "kb_wiki"
    assert activation["guided_score"]["benefit_score"] >= 8
    assert activation["guided_score"]["rule"].startswith("kb_wiki when")


def test_session_start_is_thin_and_lists_on_demand_surfaces(project: Path) -> None:
    run_next_json(project, "activation-wizard", "--mode", "short", "--choice", "kb-wiki")

    result = run_next_json(project, "session-start")

    assert result["default_reads"] == ["NOW.md"]
    assert result["required_read_paths"] == [str(project / ".kb-next" / "memory" / "NOW.md")]
    assert "HOT.md" in result["on_demand_reads"]
    assert ".kb/memory/INDEX.md" in result["on_demand_reads"]
    assert "wiki_index" in result["paths"]
    assert "emit_thin_contract" in result["actions_run"]


def test_compliance_preflight_planning_lists_prd_gates_and_traceability(project: Path) -> None:
    result = run_next_json(
        project,
        "compliance-preflight",
        "--work-type",
        "planning",
        "--topic",
        "plan KB/Wiki vNext development",
    )

    assert result["status"] == "pass"
    assert result["development_contract_required"] is True
    assert result["contract_scope"].startswith("development until 100% developed")
    assert "Gate 0 PRD" in result["applicable_gates"]
    assert any("product-intent-prd.pt-br.md" in item for item in result["required_spec_surfaces"])
    assert any("release-gates.md" in item for item in result["required_spec_surfaces"])
    assert any("test-matrix.md" in item for item in result["required_spec_surfaces"])
    assert any("Development compliance preflight" == item for item in result["required_traceability_rows"])


def test_compliance_preflight_implementation_requires_tests_and_dossier(project: Path) -> None:
    result = run_next_json(
        project,
        "compliance-preflight",
        "--work-type",
        "implementation",
        "--topic",
        "implement compliance-preflight runtime",
    )

    assert result["status"] == "pass"
    assert any("validate_kb_wiki_vnext_spec_pack.py" in item for item in result["required_tests"])
    assert any("pytest" in item for item in result["required_tests"])
    assert any("run dossier" in item for item in result["required_evidence"])
    assert "Proceed only with the listed PRD/master-plan mapping" in result["next_allowed_action"]


def test_compliance_preflight_track_b_blocks_on_source_linkage_pendencia(project: Path) -> None:
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    conn.execute(
        """
        INSERT INTO records (
            id, category, domain, title, content, status, tier, source,
            tags_json, created_at, updated_at, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "KB-20260525141938-0cd4cc",
            "PENDENCIA",
            "wiki",
            "Canonical source-linkage debt blocks external human wiki Track B",
            "Track B remains blocked until source-linkage is resolved.",
            "ATIVO",
            "HOT",
            "test",
            json.dumps(["kb-wiki-vnext", "track-b"]),
            "2026-05-25T00:00:00Z",
            "2026-05-25T00:00:00Z",
            None,
        ),
    )
    conn.commit()
    conn.close()

    result = run_next_json(project, "compliance-preflight", "--work-type", "track-b")

    assert result["status"] == "blocked"
    assert result["canonical_blockers"][0]["id"] == "KB-20260525141938-0cd4cc"
    assert "Resolve or Sponsor-waive" in result["next_allowed_action"]
    assert result["source_linkage_audit"]["read_only"] is True


def test_source_linkage_audit_blocks_hash_mismatch_source(project: Path) -> None:
    add_source(project, "SRC-20260525-000001-deadbe", "changed", expected_hash="0" * 64)
    add_track_b_record(
        project,
        "TRACKB-BAD-HASH",
        source_id="SRC-20260525-000001-deadbe",
        content="Uses SRC-20260525-000001-deadbe.",
    )

    result = run_next_json(project, "source-linkage-audit", "--scope", "track-b")

    assert result["status"] == "blocked"
    assert result["blocked_record_ids"] == ["TRACKB-BAD-HASH"]
    assert result["hash_mismatch_source_ids"] == ["SRC-20260525-000001-deadbe"]
    assert "source_hash_mismatch:SRC-20260525-000001-deadbe" in result["blocked_records"][0]["reasons"]


def test_source_linkage_audit_ignores_quarantined_unlinked_blocked_source(project: Path) -> None:
    add_source(
        project,
        "SRC-20260525-000002-badbad",
        "quarantined",
        tags=["hash-mismatch", "quarantined", "needs-provenance-repair"],
        expected_hash="1" * 64,
    )

    result = run_next_json(project, "source-linkage-audit", "--scope", "track-b")

    assert result["status"] == "pass"
    assert result["blocked_record_ids"] == []
    assert result["hash_mismatch_source_ids"] == ["SRC-20260525-000002-badbad"]
    assert result["quarantined_source_ids"] == ["SRC-20260525-000002-badbad"]


def test_source_linkage_audit_blocks_candidate_without_source_linkage(project: Path) -> None:
    add_track_b_record(project, "TRACKB-NO-SOURCE")

    result = run_next_json(project, "source-linkage-audit", "--scope", "track-b")

    assert result["status"] == "blocked"
    assert result["blocked_record_ids"] == ["TRACKB-NO-SOURCE"]
    assert result["blocked_records"][0]["reasons"] == ["missing_source_linkage"]


def test_source_linkage_audit_excludes_denylisted_meta_tags(project: Path) -> None:
    add_track_b_record(
        project,
        "TRACKB-META",
        tags=["track-b-candidate", "filed-analysis"],
    )

    result = run_next_json(project, "source-linkage-audit", "--scope", "track-b")

    assert result["status"] == "pass"
    assert result["blocked_record_ids"] == []
    assert "TRACKB-META" in result["excluded_record_ids"]


def test_source_linkage_audit_passes_with_clean_sources(project: Path) -> None:
    add_source(project, "SRC-20260525-000003-c0ffee", "clean")
    add_track_b_record(
        project,
        "TRACKB-CLEAN",
        content="Uses SRC-20260525-000003-c0ffee.",
    )

    result = run_next_json(project, "source-linkage-audit", "--scope", "track-b")

    assert result["status"] == "pass"
    assert result["publishable_record_ids"] == ["TRACKB-CLEAN"]
    assert result["blocked_record_ids"] == []


def test_compliance_preflight_track_b_passes_after_pendencia_resolved_and_audit_passes(project: Path) -> None:
    add_source(project, "SRC-20260525-000004-c0ffee", "clean")
    add_track_b_record(
        project,
        "TRACKB-PREFLIGHT-CLEAN",
        content="Uses SRC-20260525-000004-c0ffee.",
    )

    result = run_next_json(project, "compliance-preflight", "--work-type", "track-b")

    assert result["status"] == "pass"
    assert result["canonical_blockers"] == []
    assert result["source_linkage_audit"]["status"] == "pass"


def test_compliance_preflight_track_b_blocks_when_audit_fails_after_pendencia_resolved(project: Path) -> None:
    add_track_b_record(project, "TRACKB-PREFLIGHT-NO-SOURCE")

    result = run_next_json(project, "compliance-preflight", "--work-type", "track-b")

    assert result["status"] == "blocked"
    assert result["canonical_blockers"][0]["id"] == "source-linkage-audit"
    assert result["source_linkage_audit"]["blocked_record_ids"] == ["TRACKB-PREFLIGHT-NO-SOURCE"]
    assert "audit blockers" in result["next_allowed_action"]


def test_track_b_export_blocks_when_source_linkage_audit_fails(project: Path) -> None:
    add_track_b_record(project, "TRACKB-EXPORT-NO-SOURCE")
    db_before = file_hash(project / ".kb" / "kb.db")

    result = run_next_json(
        project,
        "track-b-export",
        "--adapter",
        "obsidian_static_markdown",
    )

    db_after = file_hash(project / ".kb" / "kb.db")
    assert result["status"] == "blocked"
    assert "source-linkage-audit:blocked" in result["blocked_reasons"]
    assert result["exported_record_ids"] == []
    assert not (project / ".kb-next" / "adapters" / "obsidian_static_markdown" / "vault").exists()
    assert db_before == db_after


def test_track_b_export_blocks_when_track_b_preflight_fails(project: Path) -> None:
    add_active_source_linkage_pendencia(project)
    add_source(project, "SRC-20260525-000005-c0ffee", "clean")
    add_track_b_record(
        project,
        "TRACKB-EXPORT-PREFLIGHT-BLOCKED",
        source_id="SRC-20260525-000005-c0ffee",
    )

    result = run_next_json(
        project,
        "track-b-export",
        "--adapter",
        "obsidian_static_markdown",
    )

    assert result["status"] == "blocked"
    assert "compliance-preflight:blocked" in result["blocked_reasons"]
    assert result["input_audit_status"] == "pass"
    assert not (project / ".kb-next" / "adapters" / "obsidian_static_markdown" / "vault").exists()


def test_track_b_export_writes_safe_self_contained_obsidian_vault(project: Path) -> None:
    clean_hash_1 = add_source(project, "SRC-20260525-000006-c0ffee", "clean source 1")
    clean_hash_2 = add_source(project, "SRC-20260525-000007-c0ffee", "clean source 2")
    add_source(
        project,
        "SRC-20260421-142649-5810a8",
        "quarantined old source",
        tags=["hash-mismatch", "quarantined", "needs-provenance-repair"],
        expected_hash="1" * 64,
    )
    add_source(
        project,
        "SRC-20260421-142649-63aca2",
        "quarantined old source",
        tags=["hash-mismatch", "quarantined", "needs-provenance-repair"],
        expected_hash="2" * 64,
    )
    add_track_b_record(
        project,
        "TRACKB-EXPORT-CLEAN-1",
        source_id="SRC-20260525-000006-c0ffee",
        content="First clean Track B record.",
    )
    add_track_b_record(
        project,
        "TRACKB-EXPORT-CLEAN-2",
        source_id="SRC-20260525-000007-c0ffee",
        content="Second clean Track B record.",
    )
    add_track_b_record(
        project,
        "TRACKB-EXPORT-META",
        source_id="SRC-20260525-000007-c0ffee",
        tags=["track-b-candidate", "filed-answer"],
    )
    db_before = file_hash(project / ".kb" / "kb.db")

    result = run_next_json(
        project,
        "track-b-export",
        "--adapter",
        "obsidian_static_markdown",
    )

    db_after = file_hash(project / ".kb" / "kb.db")
    assert result["status"] == "exported"
    assert result["exported_record_ids"] == ["TRACKB-EXPORT-CLEAN-1", "TRACKB-EXPORT-CLEAN-2"]
    assert result["source_ids"] == ["SRC-20260525-000006-c0ffee", "SRC-20260525-000007-c0ffee"]
    assert result["external_adapter_called"] is False
    assert result["classic_wiki_live_publish"] is False
    assert result["classic_kb_mutation"] == "forbidden"
    assert db_before == db_after

    vault = Path(result["paths"]["vault"])
    manifest_path = Path(result["paths"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_id"].startswith("obsidian-export-")
    assert manifest["adapter"] == "obsidian_static_markdown"
    assert manifest["status"] == "exported"
    assert manifest["exported_record_ids"] == ["TRACKB-EXPORT-CLEAN-1", "TRACKB-EXPORT-CLEAN-2"]
    assert manifest["input_audit_status"] == "pass"
    assert manifest["source_ids"] == ["SRC-20260525-000006-c0ffee", "SRC-20260525-000007-c0ffee"]
    assert "TRACKB-EXPORT-META" in manifest["excluded_record_ids"]
    assert "SRC-20260421-142649-5810a8" in manifest["hash_mismatch_source_ids"]
    assert "SRC-20260421-142649-63aca2" in manifest["quarantined_source_ids"]
    assert manifest["obsidian_design_decisions"]["version"] == "obsidian_static_markdown_design_v1"
    assert manifest["obsidian_design_decisions"]["uses_obsidian_publish"] is False
    assert manifest["obsidian_design_decisions"]["uses_symlinks_or_junctions"] is False

    output_records = manifest["output_paths"]["records"]
    output_sources = manifest["output_paths"]["sources"]
    assert sorted(output_records) == ["TRACKB-EXPORT-CLEAN-1", "TRACKB-EXPORT-CLEAN-2"]
    assert sorted(output_sources) == ["SRC-20260525-000006-c0ffee", "SRC-20260525-000007-c0ffee"]
    assert all("TRACKB-EXPORT-META" not in path for path in output_records.values())
    assert all("SRC-20260421-142649" not in path for path in output_sources.values())

    for rel_path, expected_hash in manifest["file_hashes"].items():
        assert file_hash(project / rel_path) == expected_hash

    generated_md = sorted(vault.rglob("*.md"))
    assert generated_md
    forbidden_filename_chars = set('<>:"\\|?*#^[]')
    for path in generated_md:
        assert not any(char in forbidden_filename_chars for char in path.name)
        assert " " not in path.name
        assert not is_reparse_point(path)
        text = path.read_text(encoding="utf-8")
        assert "[[" not in text
        assert "#^" not in text
        metadata = markdown_frontmatter(path)
        assert metadata["manifest_id"] == manifest["manifest_id"]
        assert isinstance(metadata["record_ids"], list)
        assert isinstance(metadata["content_hash"], str)
        assert len(metadata["content_hash"]) == 64
        assert metadata["content_hash"] == markdown_body_hash(path)
        assert "confidence" in metadata
        assert isinstance(metadata["warnings"], list)
        assert isinstance(metadata["stale_warnings"], list)
        assert isinstance(metadata["provenance_warnings"], list)
        assert metadata["authority"] == "derived"
        assert "tag" not in metadata
        assert "alias" not in metadata
        assert "cssclass" not in metadata
        assert isinstance(metadata["tags"], list)
        assert isinstance(metadata["aliases"], list)
        for tag in metadata["tags"]:
            assert re.match(r"^[a-z0-9_/-]+$", tag)
            assert re.search(r"[a-z]", tag)
            assert " " not in tag

    for record_id, rel_path in output_records.items():
        record_path = project / rel_path
        metadata = markdown_frontmatter(record_path)
        assert metadata["record_id"] == record_id
        assert metadata["record_ids"] == [record_id]
        assert metadata["adapter"] == "obsidian_static_markdown"
        assert metadata["derived"] is True
        assert metadata["canonical"] is False
        assert metadata["source_linkage_audit_status"] == "pass"
        assert isinstance(metadata["source_ids"], list)
        assert isinstance(metadata["source_hashes"], list)
        assert any(item.endswith(clean_hash_1) or item.endswith(clean_hash_2) for item in metadata["source_hashes"])

    for path in vault.rglob("*"):
        assert not is_reparse_point(path)

    shutil.rmtree(vault)
    assert file_hash(project / ".kb" / "kb.db") == db_before


def test_compliance_preflight_operational_is_lightweight(project: Path) -> None:
    result = run_next_json(
        project,
        "compliance-preflight",
        "--work-type",
        "operational",
        "--topic",
        "lookup existing vNext memory",
    )

    assert result["status"] == "pass"
    assert result["development_contract_required"] is False
    assert result["applicable_gates"] == ["Thin Session Contract"]
    assert result["required_tests"] == ["No development test run required for simple operational use."]


def test_compliance_preflight_is_read_only_and_unknown_needs_evidence(project: Path) -> None:
    run_next_json(project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    db_before = file_hash(project / ".kb" / "kb.db")
    operations_before = file_hash(project / ".kb-next" / "operations.jsonl")

    result = run_next_json(project, "compliance-preflight")

    db_after = file_hash(project / ".kb" / "kb.db")
    operations_after = file_hash(project / ".kb-next" / "operations.jsonl")
    assert result["status"] == "needs_evidence"
    assert result["work_type"] == "unknown"
    assert result["read_only"] is True
    assert db_before == db_after
    assert operations_before == operations_after


@pytest.mark.parametrize(
    ("facet", "expected_id"),
    [
        ("decisions", "DEC-1"),
        ("learnings", "LEARN-1"),
        ("open-items", "OPEN-1"),
        ("status", "STAT-1"),
    ],
)
def test_lookup_reads_classic_kb_read_only(project: Path, facet: str, expected_id: str) -> None:
    run_next_json(project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")
    before = file_hash(project / ".kb" / "kb.db")

    result = run_next_json(project, "lookup", "--facet", facet)

    after = file_hash(project / ".kb" / "kb.db")
    assert before == after
    assert result["classic_kb_mode"] == "read_only"
    assert result["default_global_preload"] is False
    assert any(item["id"] == expected_id for item in result["results"])


def test_lookup_definitions_uses_definition_tags_and_query_fallback(project: Path) -> None:
    run_next_json(project, "activation-wizard", "--mode", "short", "--choice", "kb-alone")

    tagged = run_next_json(project, "lookup", "--facet", "definitions")
    queried = run_next_json(project, "lookup", "--facet", "definitions", "--query", "machine")

    assert any(item["id"] == "DEF-1" for item in tagged["results"])
    assert any(item["id"] == "DEF-1" for item in queried["results"])
