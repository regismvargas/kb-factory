from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
KB_NEXT = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
CLASSIC_KB_PY = ROOT / "core" / "templates" / "kb" / "kb.py"
CLASSIC_RUNTIME = ROOT / "core" / "templates" / "kb" / "runtime"


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


def write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return f"@{path}"


def run_classic_json(project_root: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(project_root / ".kb" / "kb.py"), *args, "--json"],
        text=True,
        capture_output=True,
        check=True,
        cwd=str(project_root / ".kb"),
    )
    return json.loads(result.stdout)


def db_record(project_root: Path, record_id: str) -> dict | None:
    conn = sqlite3.connect(project_root / ".kb" / "kb.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return dict(row) if row else None
    finally:
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
            confidence REAL,
            source_id TEXT,
            replacement_id TEXT,
            supersedes_id TEXT,
            review_after TEXT,
            valid_until TEXT
        );
        """
    )
    rows = [
        (
            "DEC-BOOT",
            "DECISAO",
            "architecture",
            "Thin session-start contract",
            "Only NOW.md is mandatory at startup; HOT and INDEX are on demand.",
            "ATIVO",
            "HOT",
            "test source",
            json.dumps(["session-start", "kb-wiki-vnext"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.96,
            "SRC-1",
        ),
        (
            "DEC-CONFLICT-A",
            "DECISAO",
            "architecture",
            "Wiki activation by Sponsor",
            "The Sponsor chooses KB alone or KB + Wiki during activation.",
            "ATIVO",
            "HOT",
            "test source",
            json.dumps(["activation"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.9,
            "SRC-2",
        ),
        (
            "DEC-CONFLICT-B",
            "DECISAO",
            "architecture",
            "Wiki activation by executor",
            "The executor may choose Wiki activation without Sponsor approval.",
            "ATIVO",
            "WARM",
            "test source",
            json.dumps(["activation"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.7,
            None,
        ),
        (
            "LEARN-DUP",
            "APRENDIZADO",
            "architecture",
            "Semantic curation is agent judged",
            "The runtime prepares evidence; the external agent supplies semantic judgment.",
            "ATIVO",
            "HOT",
            "test source",
            json.dumps(["semantic-memory"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.91,
            "SRC-3",
        ),
        (
            "DEF-MANIFEST",
            "FATO",
            "architecture",
            "Definition: LLM inference manifest",
            "A manifest records candidate records, judgment, rationale, confidence, risk, and validation status.",
            "ATIVO",
            "WARM",
            "test source",
            json.dumps(["definition", "manifest"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.88,
            "SRC-4",
        ),
        (
            "STAT-RUNTIME",
            "FATO",
            "architecture",
            "Semantic runtime package is planned",
            "Semantic lookup, filing proposals, and wiki drafts are in the next increment.",
            "ATIVO",
            "HOT",
            "test source",
            json.dumps(["status", "semantic-memory"]),
            "2026-05-24T00:00:00Z",
            "2026-05-24T00:00:00Z",
            0.85,
            "SRC-5",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO records (
            id, category, domain, title, content, status, tier, source,
            tags_json, created_at, updated_at, confidence, source_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return tmp_path


@pytest.fixture()
def apply_project(tmp_path: Path) -> Path:
    kb_root = tmp_path / ".kb"
    kb_root.mkdir()
    shutil.copytree(CLASSIC_RUNTIME, kb_root / "runtime")
    shutil.copy2(CLASSIC_KB_PY, kb_root / "kb.py")
    config = {
        "schema_version": 4,
        "project": {"name": "Apply Test KB", "slug": "apply-test-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["architecture", "operations"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "filing_policy": {"confidence_bands": {"high": 0.8, "review": 0.55}},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {"enabled": False, "activation_mode": "manual", "page_types": [], "eligibility": {"min_active_records": 1, "min_domains_with_records": 1, "min_soft_signal_score": 0}, "semantic": {"min_confidence_autopublish": 0.8, "min_confidence_review": 0.55}, "renderers": {"mkdocs": {"enabled": False, "site_name": "Apply Test Wiki"}}},
    }
    (kb_root / "kb.config.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(kb_root / "kb.py"), "init"],
        text=True,
        capture_output=True,
        check=True,
        cwd=str(kb_root),
    )
    run_classic_json(
        tmp_path,
        "create",
        "--id",
        "LEARN-DUP",
        "--category",
        "APRENDIZADO",
        "--domain",
        "architecture",
        "--title",
        "Semantic curation is agent judged",
        "--content",
        "The runtime prepares evidence; the external agent supplies semantic judgment.",
        "--source",
        "test source",
        "--tags",
        "semantic-memory",
        "--confidence",
        "0.91",
    )
    run_classic_json(
        tmp_path,
        "create",
        "--id",
        "STAT-RUNTIME",
        "--category",
        "FATO",
        "--domain",
        "architecture",
        "--title",
        "Semantic runtime package is planned",
        "--content",
        "Semantic lookup, filing proposals, and wiki drafts are in the next increment.",
        "--source",
        "test source",
        "--tags",
        "status,semantic-memory",
        "--confidence",
        "0.85",
    )
    activate(tmp_path, "kb-wiki")
    return tmp_path


def activate(project: Path, choice: str = "kb-wiki") -> None:
    run_next_json(project, "activation-wizard", "--mode", "short", "--choice", choice)


def valid_new_filing_proposal(project: Path, tmp_path: Path, *, record_id: str = "NEW-APPLY-1") -> dict:
    candidate = {
        "title": "Applied proposal creates canonical memory",
        "content": "A reviewed proposal may become a canonical KB fact.",
        "tags": ["proposal-apply"],
    }
    judgment = {
        "action": "new",
        "rationale": "The candidate is supported by existing runtime records.",
        "confidence": 0.86,
        "risk": "Low; apply is explicit and audited.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "duplicate_candidates": [],
        "conflicts": [],
        "record_draft": {
            "id": record_id,
            "category": "FATO",
            "domain": "architecture",
            "title": candidate["title"],
            "content": candidate["content"],
            "tags": ["proposal-apply"],
            "confidence": 0.86,
        },
    }
    return run_next_json(
        project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / f"{record_id}-candidate.json", candidate),
        "--category",
        "FATO",
        "--domain",
        "architecture",
        "--judgment",
        write_json(tmp_path / f"{record_id}-judgment.json", judgment),
    )


def create_apply_record(
    project: Path,
    record_id: str,
    *,
    category: str = "FATO",
    title: str | None = None,
    tier: str = "WARM",
    review_after: str | None = None,
) -> None:
    args = [
        "create",
        "--id",
        record_id,
        "--category",
        category,
        "--domain",
        "architecture",
        "--title",
        title or f"Record {record_id}",
        "--content",
        f"Content for {record_id}.",
        "--source",
        "test source",
        "--tags",
        "semantic-hygiene",
        "--tier",
        tier,
        "--confidence",
        "0.9",
    ]
    if review_after:
        args.extend(["--review-after", review_after])
    run_classic_json(project, *args)


def project_rel(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def test_semantic_lookup_synonym_uses_external_judgment(project: Path) -> None:
    activate(project)
    judgment = {
        "ranked_record_ids": ["DEC-BOOT"],
        "confidence": 0.93,
        "rationale": "Bootstrap leve maps to the thin session-start contract.",
        "ambiguity": False,
        "conflicts": [],
        "provenance_warnings": [],
        "provenance": [{"record_id": "DEC-BOOT"}],
    }

    result = run_next_json(
        project,
        "semantic-lookup",
        "--query",
        "bootstrap leve de memoria",
        "--facet",
        "decisions",
        "--judgment-json",
        json.dumps(judgment),
    )

    assert result["status"] == "valid"
    assert result["ranked_results"][0]["record"]["id"] == "DEC-BOOT"
    assert result["manifest_id"]
    assert Path(result["paths"]["manifest"]).is_file()
    assert Path(result["paths"]["proposal"]).is_file()


def test_semantic_lookup_ambiguity_requests_disambiguation(project: Path) -> None:
    activate(project)
    judgment = {
        "ranked_record_ids": ["DEC-CONFLICT-A", "DEC-CONFLICT-B"],
        "confidence": 0.62,
        "rationale": "Activation owner wording is ambiguous.",
        "ambiguity": {"needs_disambiguation": True, "question": "Sponsor or executor authority?"},
        "conflicts": [],
        "provenance_warnings": [],
        "provenance": [{"record_id": "DEC-CONFLICT-A"}, {"record_id": "DEC-CONFLICT-B"}],
    }

    result = run_next_json(
        project,
        "semantic-lookup",
        "--query",
        "quem decide wiki",
        "--facet",
        "decisions",
        "--judgment-json",
        json.dumps(judgment),
    )

    assert result["status"] == "needs_disambiguation"
    assert result["validation_status"] == "needs_human_review"
    assert "ambiguous" in json.loads(Path(result["paths"]["manifest"]).read_text(encoding="utf-8"))["warnings"]


def test_semantic_lookup_conflict_blocks_conclusive_answer(project: Path) -> None:
    activate(project)
    judgment = {
        "ranked_record_ids": ["DEC-CONFLICT-A", "DEC-CONFLICT-B"],
        "confidence": 0.71,
        "rationale": "Two active decisions disagree about activation authority.",
        "ambiguity": False,
        "conflicts": [{"record_ids": ["DEC-CONFLICT-A", "DEC-CONFLICT-B"], "reason": "Sponsor authority conflicts with executor authority."}],
        "provenance_warnings": [],
        "provenance": [{"record_id": "DEC-CONFLICT-A"}, {"record_id": "DEC-CONFLICT-B"}],
    }

    result = run_next_json(
        project,
        "semantic-lookup",
        "--query",
        "autoridade ativacao wiki",
        "--facet",
        "decisions",
        "--judgment-json",
        json.dumps(judgment),
    )

    assert result["status"] == "blocked"
    assert result["validation_status"] == "blocked"
    assert result["conflicts"]


def test_filing_proposal_duplicate_does_not_create_new_record(project: Path, tmp_path: Path) -> None:
    activate(project)
    candidate = {
        "title": "Semantic curation is agent judged",
        "content": "External agents provide the judgment while runtime records manifests.",
        "tags": ["semantic-memory"],
    }
    judgment = {
        "action": "supersede",
        "rationale": "The new candidate refines an existing learning.",
        "confidence": 0.86,
        "risk": "Could duplicate LEARN-DUP if filed as new.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "duplicate_candidates": [{"record_id": "LEARN-DUP"}],
        "conflicts": [],
        "record_draft": {"category": "APRENDIZADO", "domain": "architecture", "title": candidate["title"]},
    }

    result = run_next_json(
        project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / "candidate.json", candidate),
        "--category",
        "APRENDIZADO",
        "--domain",
        "architecture",
        "--judgment",
        write_json(tmp_path / "judgment.json", judgment),
    )

    assert result["status"] == "valid"
    assert result["action"] == "supersede"
    assert result["record_draft"]["category"] == "APRENDIZADO"
    assert Path(result["paths"]["proposal"]).is_file()


def test_filing_proposal_without_provenance_is_blocked(project: Path, tmp_path: Path) -> None:
    activate(project)
    candidate = {
        "title": "Unproven durable decision",
        "content": "This should not be filed without evidence.",
    }
    judgment = {
        "action": "new",
        "rationale": "Looks useful but lacks evidence.",
        "confidence": 0.9,
        "risk": "No supporting source or record.",
        "provenance": [],
        "duplicate_candidates": [],
        "conflicts": [],
        "record_draft": {"category": "DECISAO", "domain": "architecture", "title": candidate["title"]},
    }

    result = run_next_json(
        project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / "candidate.json", candidate),
        "--category",
        "DECISAO",
        "--domain",
        "architecture",
        "--judgment",
        write_json(tmp_path / "judgment.json", judgment),
    )

    assert result["status"] == "blocked"
    assert "missing_provenance" in result["warnings"]


def test_semantic_hygiene_without_judgment_is_report_only(project: Path) -> None:
    activate(project)
    before = file_hash(project / ".kb" / "kb.db")

    result = run_next_json(project, "semantic-hygiene", "--scope", "hot-overflow")

    assert result["status"] == "needs_llm_judgment"
    assert result["read_only"] is True
    assert result["proposal_ids"] == []
    assert result["paths"]["manifest"] is None
    assert set(result["groups"]) == {
        "keep_hot",
        "demote_candidate",
        "supersede_or_merge_candidate",
        "resolve_candidate",
        "needs_sponsor",
    }
    assert not (project / ".kb-next" / "proposals" / "hygiene").exists()
    assert file_hash(project / ".kb" / "kb.db") == before


def test_semantic_hygiene_writes_grouped_proposals_only_under_kb_next(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    create_apply_record(apply_project, "HOT-DEMOTE", title="Overflow HOT", tier="HOT")
    create_apply_record(
        apply_project,
        "PENDING-RESOLVE",
        category="PENDENCIA",
        title="Resolved follow-up",
        tier="HOT",
        review_after="2000-01-01",
    )
    before = file_hash(apply_project / ".kb" / "kb.db")
    judgment = {
        "groups": {
            "keep_hot": [{"record_id": "LEARN-DUP", "rationale": "Still active context."}],
            "demote_candidate": [{"record_id": "HOT-DEMOTE", "rationale": "Overflow item can move to WARM."}],
            "supersede_or_merge_candidate": [],
            "resolve_candidate": [{"record_id": "PENDING-RESOLVE", "rationale": "Follow-up is complete.", "resolution_notes": "Completed during hygiene review."}],
            "needs_sponsor": [],
        },
        "rationale": "TFI overflow validation requires grouped HOT hygiene review.",
        "confidence": 0.91,
        "risk": "Low; proposals require explicit apply.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "conflicts": [],
    }

    result = run_next_json(
        apply_project,
        "semantic-hygiene",
        "--scope",
        "hot-overflow",
        "--judgment",
        write_json(tmp_path / "hygiene-judgment.json", judgment),
        "--write-proposals",
    )

    assert result["status"] == "valid"
    assert result["read_only"] is False
    assert len(result["proposal_ids"]) == 2
    assert all("proposals\\hygiene" in path or "proposals/hygiene" in path for path in result["paths"]["proposals"])
    manifest = json.loads(Path(result["paths"]["manifest"]).read_text(encoding="utf-8"))
    assert manifest["task_type"] == "semantic_hygiene"
    assert len(manifest["resulting_proposals"]) == 2
    assert file_hash(apply_project / ".kb" / "kb.db") == before


def test_proposal_apply_new_creates_canonical_record_with_approval(apply_project: Path, tmp_path: Path) -> None:
    proposal = valid_new_filing_proposal(apply_project, tmp_path)

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Reviewed and approved for canonical filing.",
    )

    assert result["status"] == "applied"
    assert result["canonical_record_id"] == "NEW-APPLY-1"
    record = db_record(apply_project, "NEW-APPLY-1")
    assert record is not None
    assert record["title"] == "Applied proposal creates canonical memory"
    assert record["status"] == "ATIVO"
    assert Path(result["paths"]["apply_manifest"]).is_file()
    operations = (apply_project / ".kb-next" / "operations.jsonl").read_text(encoding="utf-8")
    assert '"event": "proposal-apply"' in operations


def test_proposal_apply_supersede_marks_original_replaced(apply_project: Path, tmp_path: Path) -> None:
    candidate = {
        "title": "Semantic curation is governed by apply",
        "content": "Approved proposals are applied through the classic KB runtime.",
    }
    judgment = {
        "action": "supersede",
        "rationale": "The new learning refines the existing semantic curation learning.",
        "confidence": 0.88,
        "risk": "Low when applied through explicit supersede.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "duplicate_candidates": [{"record_id": "LEARN-DUP"}],
        "conflicts": [],
        "record_draft": {
            "id": "LEARN-DUP-S1",
            "category": "APRENDIZADO",
            "domain": "architecture",
            "title": candidate["title"],
            "content": candidate["content"],
            "tags": ["semantic-memory", "proposal-apply"],
            "confidence": 0.88,
        },
    }
    proposal = run_next_json(
        apply_project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / "supersede-candidate.json", candidate),
        "--category",
        "APRENDIZADO",
        "--domain",
        "architecture",
        "--judgment",
        write_json(tmp_path / "supersede-judgment.json", judgment),
    )

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        proposal["paths"]["proposal"],
        "--approve",
        "--approval-note",
        "Approved supersede target from duplicate candidate.",
    )

    assert result["status"] == "applied"
    assert result["canonical_record_id"] == "LEARN-DUP-S1"
    old = db_record(apply_project, "LEARN-DUP")
    new = db_record(apply_project, "LEARN-DUP-S1")
    assert old["status"] == "SUPERSEDIDO"
    assert old["replacement_id"] == "LEARN-DUP-S1"
    assert new["supersedes_id"] == "LEARN-DUP"


def test_proposal_apply_demote_hot_and_resolve_hygiene_proposals(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    create_apply_record(apply_project, "HOT-DEMOTE-APPLY", title="HOT to demote", tier="HOT")
    create_apply_record(
        apply_project,
        "PENDING-RESOLVE-APPLY",
        category="PENDENCIA",
        title="Pending to resolve",
        tier="HOT",
        review_after="2000-01-01",
    )
    judgment = {
        "groups": {
            "demote_candidate": [{"record_id": "HOT-DEMOTE-APPLY", "rationale": "No longer session-critical."}],
            "resolve_candidate": [{"record_id": "PENDING-RESOLVE-APPLY", "rationale": "Closed by review.", "resolution_notes": "Resolved by approved hygiene proposal."}],
        },
        "rationale": "Approved semantic hygiene review.",
        "confidence": 0.92,
        "risk": "Low.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "conflicts": [],
    }
    proposal_run = run_next_json(
        apply_project,
        "semantic-hygiene",
        "--scope",
        "hot-overflow",
        "--judgment-json",
        json.dumps(judgment),
        "--write-proposals",
    )
    proposals = [json.loads(Path(path).read_text(encoding="utf-8")) for path in proposal_run["paths"]["proposals"]]
    demote = next(item for item in proposals if item["action"] == "demote_hot")
    resolve = next(item for item in proposals if item["action"] == "resolve")

    demote_result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        demote["proposal_id"],
        "--approve",
        "--approval-note",
        "Approved HOT demotion from semantic hygiene review.",
    )
    resolve_result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        resolve["proposal_id"],
        "--approve",
        "--approval-note",
        "Approved resolve from semantic hygiene review.",
    )

    assert demote_result["status"] == "applied"
    assert resolve_result["status"] == "applied"
    assert db_record(apply_project, "HOT-DEMOTE-APPLY")["tier"] == "WARM"
    resolved = db_record(apply_project, "PENDING-RESOLVE-APPLY")
    assert resolved["status"] == "RESOLVIDO"
    assert resolved["resolution_notes"] == "Resolved by approved hygiene proposal."


def test_proposal_apply_blocks_needs_sponsor_hygiene_action(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    create_apply_record(apply_project, "SPONSOR-REVIEW", title="Needs Sponsor", tier="HOT")
    before = file_hash(apply_project / ".kb" / "kb.db")
    judgment = {
        "groups": {
            "needs_sponsor": [{"record_id": "SPONSOR-REVIEW", "rationale": "Authority decision required."}],
        },
        "rationale": "Sponsor decision required.",
        "confidence": 0.93,
        "risk": "Unsafe to apply automatically.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "conflicts": [],
    }
    proposal_run = run_next_json(
        apply_project,
        "semantic-hygiene",
        "--scope",
        "hot-overflow",
        "--judgment",
        write_json(tmp_path / "needs-sponsor-judgment.json", judgment),
        "--write-proposals",
    )

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        proposal_run["proposal_ids"][0],
        "--approve",
        "--approval-note",
        "Even approved flag must not apply needs-Sponsor.",
    )

    assert result["status"] == "blocked"
    assert "unsupported_action:needs_sponsor" in result["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before


def test_proposal_apply_requires_approval_and_note(apply_project: Path, tmp_path: Path) -> None:
    proposal = valid_new_filing_proposal(apply_project, tmp_path, record_id="NEW-NO-APPROVAL")
    before = file_hash(apply_project / ".kb" / "kb.db")

    result = run_next_json(apply_project, "proposal-apply", "--proposal", proposal["proposal_id"])

    assert result["status"] == "blocked"
    assert "missing_approval" in result["warnings"]
    assert "missing_approval_note" in result["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before
    assert db_record(apply_project, "NEW-NO-APPROVAL") is None


def test_proposal_apply_blocks_tampered_proposal_and_unbound_manifest(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    proposal = valid_new_filing_proposal(apply_project, tmp_path, record_id="NEW-TAMPERED")
    before = file_hash(apply_project / ".kb" / "kb.db")
    proposal_path = Path(proposal["paths"]["proposal"])
    payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    payload["record_draft"]["title"] = "Tampered title"
    proposal_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Tampering must be detected before canonical apply.",
    )

    assert result["status"] == "blocked"
    assert "proposal_hash_mismatch" in result["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before
    assert db_record(apply_project, "NEW-TAMPERED") is None

    fresh = valid_new_filing_proposal(apply_project, tmp_path, record_id="NEW-UNBOUND")
    manifest_path = Path(fresh["paths"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("resulting_proposals", None)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    missing_link = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        fresh["proposal_id"],
        "--approve",
        "--approval-note",
        "Manifest without proposal binding must block.",
    )

    assert missing_link["status"] == "blocked"
    assert "missing_resulting_proposals" in missing_link["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before
    assert db_record(apply_project, "NEW-UNBOUND") is None


def test_proposal_apply_blocks_proposal_path_outside_kb_next(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    proposal = valid_new_filing_proposal(apply_project, tmp_path, record_id="NEW-OUTSIDE")
    outside = tmp_path / "outside-proposal.json"
    shutil.copy2(Path(proposal["paths"]["proposal"]), outside)
    before = file_hash(apply_project / ".kb" / "kb.db")

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        str(outside),
        "--approve",
        "--approval-note",
        "Outside proposal paths must not be accepted.",
    )

    assert result["status"] == "blocked"
    assert any("proposal path outside .kb-next/proposals" in warning for warning in result["warnings"])
    assert file_hash(apply_project / ".kb" / "kb.db") == before
    assert db_record(apply_project, "NEW-OUTSIDE") is None


def test_proposal_apply_blocks_update_low_confidence_conflict_and_ambiguous_target(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    scenarios = [
        (
            "update",
            {
                "action": "update",
                "confidence": 0.9,
                "provenance": [{"record_id": "LEARN-DUP"}],
                "duplicate_candidates": [],
                "conflicts": [],
            },
            "unsupported_action:update",
        ),
        (
            "low",
            {
                "action": "new",
                "confidence": 0.5,
                "provenance": [{"record_id": "LEARN-DUP"}],
                "duplicate_candidates": [],
                "conflicts": [],
            },
            "low_confidence:0.5",
        ),
        (
            "conflict",
            {
                "action": "new",
                "confidence": 0.9,
                "provenance": [{"record_id": "LEARN-DUP"}],
                "duplicate_candidates": [],
                "conflicts": [{"record_ids": ["LEARN-DUP", "STAT-RUNTIME"], "reason": "test conflict"}],
            },
            "invalid_proposal_status:blocked",
        ),
        (
            "ambiguous",
            {
                "action": "supersede",
                "confidence": 0.9,
                "provenance": [{"record_id": "LEARN-DUP"}],
                "duplicate_candidates": [{"record_id": "LEARN-DUP"}, {"record_id": "STAT-RUNTIME"}],
                "conflicts": [],
            },
            "ambiguous_supersede_target",
        ),
    ]

    for name, judgment_base, expected_warning in scenarios:
        before = file_hash(apply_project / ".kb" / "kb.db")
        candidate = {"title": f"Blocked {name}", "content": f"Blocked {name} content."}
        judgment = {
            "rationale": "Exercise apply validation.",
            "risk": "Should not mutate canonical KB.",
            "record_draft": {
                "id": f"BLOCKED-{name.upper()}",
                "category": "FATO",
                "domain": "architecture",
                "title": candidate["title"],
                "content": candidate["content"],
                "confidence": judgment_base["confidence"],
            },
            **judgment_base,
        }
        proposal = run_next_json(
            apply_project,
            "filing-proposal",
            "--input",
            write_json(tmp_path / f"{name}-candidate.json", candidate),
            "--category",
            "FATO",
            "--domain",
            "architecture",
            "--judgment",
            write_json(tmp_path / f"{name}-judgment.json", judgment),
        )

        result = run_next_json(
            apply_project,
            "proposal-apply",
            "--proposal",
            proposal["proposal_id"],
            "--approve",
            "--approval-note",
            "Approved flag present but validation should block.",
        )

        assert result["status"] == "blocked"
        assert expected_warning in result["warnings"]
        assert file_hash(apply_project / ".kb" / "kb.db") == before


def test_proposal_apply_blocks_defer_and_answer_only(
    apply_project: Path,
    tmp_path: Path,
) -> None:
    before = file_hash(apply_project / ".kb" / "kb.db")
    candidate = {"title": "Deferred candidate", "content": "No durable write."}
    defer_judgment = {
        "action": "defer",
        "rationale": "No durable write is approved.",
        "confidence": 0.9,
        "risk": "None.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "record_draft": {
            "id": "DEFER-BLOCK",
            "category": "FATO",
            "domain": "architecture",
            "title": candidate["title"],
            "content": candidate["content"],
            "confidence": 0.9,
        },
    }
    defer_proposal = run_next_json(
        apply_project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / "defer-candidate.json", candidate),
        "--category",
        "FATO",
        "--domain",
        "architecture",
        "--judgment",
        write_json(tmp_path / "defer-judgment.json", defer_judgment),
    )

    defer_result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        defer_proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Approval cannot apply defer.",
    )

    assert defer_result["status"] == "blocked"
    assert "unsupported_action:defer" in defer_result["warnings"]

    answer_only_judgment = {
        "action": "answer_only",
        "findings": ["ok"],
        "rationale": "Diagnostic only.",
        "confidence": 0.9,
        "risk": "No canonical write should occur.",
        "provenance": [{"record_id": "LEARN-DUP"}],
        "record_draft": {
            "id": "ANSWER-ONLY-BLOCK",
            "category": "FATO",
            "domain": "architecture",
            "title": "Answer only candidate",
            "content": "Diagnostic proposals are not applied.",
            "confidence": 0.9,
        },
    }
    answer_only_proposal = run_next_json(
        apply_project,
        "curation-proposal",
        "--query",
        "semantic curation",
        "--facet",
        "learnings",
        "--judgment-json",
        json.dumps(answer_only_judgment),
    )

    answer_only_result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        answer_only_proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Approval cannot apply answer-only.",
    )

    assert answer_only_result["status"] == "blocked"
    assert "unsupported_action:answer_only" in answer_only_result["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before
    assert db_record(apply_project, "DEFER-BLOCK") is None
    assert db_record(apply_project, "ANSWER-ONLY-BLOCK") is None


def test_proposal_apply_semantic_lookup_is_not_applicable(apply_project: Path) -> None:
    judgment = {
        "ranked_record_ids": ["LEARN-DUP"],
        "confidence": 0.9,
        "rationale": "Lookup only.",
        "provenance": [{"record_id": "LEARN-DUP"}],
    }
    proposal = run_next_json(
        apply_project,
        "semantic-lookup",
        "--query",
        "semantic curation",
        "--facet",
        "learnings",
        "--judgment-json",
        json.dumps(judgment),
    )
    before = file_hash(apply_project / ".kb" / "kb.db")

    result = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Lookup does not carry a record draft.",
    )

    assert result["status"] == "not_applicable"
    assert "not_applicable:semantic_lookup_has_no_record_draft" in result["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before


def test_proposal_apply_curation_requires_record_draft_then_applies(apply_project: Path, tmp_path: Path) -> None:
    without_draft = {
        "action": "new",
        "findings": ["ok"],
        "rationale": "No draft was supplied.",
        "confidence": 0.9,
        "risk": "No mutation should happen.",
        "provenance": [{"record_id": "LEARN-DUP"}],
    }
    blocked_proposal = run_next_json(
        apply_project,
        "curation-proposal",
        "--query",
        "semantic curation",
        "--facet",
        "learnings",
        "--judgment-json",
        json.dumps(without_draft),
    )
    before = file_hash(apply_project / ".kb" / "kb.db")

    blocked = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        blocked_proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Approval cannot compensate for a missing record draft.",
    )

    assert blocked["status"] == "blocked"
    assert "missing_record_draft" in blocked["warnings"]
    assert file_hash(apply_project / ".kb" / "kb.db") == before

    with_draft = {
        **without_draft,
        "rationale": "Curation proposal carries an explicit record draft.",
        "record_draft": {
            "id": "CURATION-APPLY-1",
            "category": "FATO",
            "domain": "architecture",
            "title": "Curation proposals can apply explicit drafts",
            "content": "A curation proposal with a valid record draft can be applied.",
            "confidence": 0.9,
            "tags": ["curation", "proposal-apply"],
        },
    }
    applied_proposal = run_next_json(
        apply_project,
        "curation-proposal",
        "--query",
        "semantic curation",
        "--facet",
        "learnings",
        "--judgment-json",
        json.dumps(with_draft),
    )

    applied = run_next_json(
        apply_project,
        "proposal-apply",
        "--proposal",
        applied_proposal["proposal_id"],
        "--approve",
        "--approval-note",
        "Approved curation proposal with explicit record draft.",
    )

    assert applied["status"] == "applied"
    assert db_record(apply_project, "CURATION-APPLY-1") is not None


def test_wiki_synthesis_plan_writes_only_kb_next_drafts(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    judgment = {
        "supporting_record_ids": ["STAT-RUNTIME", "LEARN-DUP"],
        "rationale": "The topic can be drafted from active semantic runtime records.",
        "confidence": 0.84,
        "machine_draft": "# Semantic Curation Runtime\n\n- record: STAT-RUNTIME\n- record: LEARN-DUP\n",
        "human_draft": "# Semantic Curation Runtime\n\nA readable draft for reviewers.\n",
    }

    result = run_next_json(
        project,
        "wiki-synthesis-plan",
        "--topic",
        "Semantic Curation Runtime",
        "--domain",
        "architecture",
        "--write-drafts",
        "--judgment",
        write_json(tmp_path / "wiki-judgment.json", judgment),
    )

    assert result["status"] == "valid"
    assert Path(result["draft_paths"]["machine"]).is_file()
    assert Path(result["draft_paths"]["human"]).is_file()
    assert ".kb-next" in result["draft_paths"]["machine"]
    assert not (project / ".kb" / "wiki" / "live").exists()


def test_wiki_draft_review_materializes_only_kb_next_surfaces(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    live_root = project / ".kb" / "wiki" / "live"
    live_root.mkdir(parents=True)
    live_page = live_root / "architecture.md"
    live_page.write_text("classic live wiki stays untouched\n", encoding="utf-8")
    db_path = project / ".kb" / "kb.db"
    before_db = file_hash(db_path)
    before_live = file_hash(live_page)
    judgment = {
        "supporting_record_ids": ["STAT-RUNTIME", "LEARN-DUP"],
        "rationale": "The topic can be materialized from active semantic runtime records.",
        "confidence": 0.86,
        "provenance": [{"record_id": "STAT-RUNTIME"}, {"record_id": "LEARN-DUP"}],
        "machine_draft": "# Semantic Curation Runtime\n\n- record: STAT-RUNTIME\n- record: LEARN-DUP\n",
        "human_draft": "# Semantic Curation Runtime\n\nA governed reviewer-facing page.\n",
    }
    run_next_json(
        project,
        "wiki-synthesis-plan",
        "--topic",
        "Semantic Curation Runtime",
        "--domain",
        "architecture",
        "--write-drafts",
        "--judgment",
        write_json(tmp_path / "wiki-judgment.json", judgment),
    )

    result = run_next_json(
        project,
        "wiki-draft-review",
        "--topic",
        "Semantic Curation Runtime",
        "--materialize",
    )

    assert result["status"] == "valid"
    assert result["materialized"] is True
    machine = Path(result["paths"]["machine"])
    human = Path(result["paths"]["human"])
    assert machine == project / ".kb-next" / "wiki" / "machine" / "semantic-curation-runtime.md"
    assert human == project / ".kb-next" / "wiki" / "human" / "semantic-curation-runtime.md"
    assert "authority: derived" in machine.read_text(encoding="utf-8")
    assert "materialization_id:" in human.read_text(encoding="utf-8")
    assert Path(result["paths"]["review_manifest"]).is_file()
    assert file_hash(db_path) == before_db
    assert file_hash(live_page) == before_live
    assert not (project / ".kb" / "wiki" / "live" / "semantic-curation-runtime.md").exists()
    operations = (project / ".kb-next" / "operations.jsonl").read_text(encoding="utf-8")
    assert '"event": "wiki-draft-review"' in operations


def test_wiki_draft_review_blocks_provenance_warnings(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    judgment = {
        "supporting_record_ids": ["STAT-RUNTIME"],
        "rationale": "The topic has a draft but the provenance needs review.",
        "confidence": 0.88,
        "provenance_warnings": [{"record_id": "STAT-RUNTIME", "reason": "source chain incomplete"}],
        "machine_draft": "# Runtime\n\n- record: STAT-RUNTIME\n",
        "human_draft": "# Runtime\n\nReadable draft.\n",
    }
    run_next_json(
        project,
        "wiki-synthesis-plan",
        "--topic",
        "Runtime",
        "--domain",
        "architecture",
        "--write-drafts",
        "--judgment-json",
        json.dumps(judgment),
    )

    result = run_next_json(project, "wiki-draft-review", "--topic", "Runtime", "--materialize")

    assert result["status"] == "blocked"
    assert result["materialized"] is False
    assert any(warning.startswith("provenance_warning") for warning in result["warnings"])
    assert not (project / ".kb-next" / "wiki" / "machine" / "runtime.md").exists()
    assert Path(result["paths"]["review_manifest"]).is_file()


def test_wiki_draft_review_requires_derived_draft_authority(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    judgment = {
        "supporting_record_ids": ["STAT-RUNTIME"],
        "rationale": "The draft is otherwise materializable.",
        "confidence": 0.9,
        "machine_draft": "# Runtime\n\n- record: STAT-RUNTIME\n",
        "human_draft": "# Runtime\n\nReadable draft.\n",
    }
    plan = run_next_json(
        project,
        "wiki-synthesis-plan",
        "--topic",
        "Runtime",
        "--domain",
        "architecture",
        "--write-drafts",
        "--judgment-json",
        json.dumps(judgment),
    )
    machine_draft = Path(plan["draft_paths"]["machine"])
    machine_draft.write_text(
        machine_draft.read_text(encoding="utf-8").replace("authority: derived_draft", "authority: canonical"),
        encoding="utf-8",
    )

    result = run_next_json(project, "wiki-draft-review", "--topic", "Runtime", "--materialize")

    assert result["status"] == "blocked"
    assert "invalid_authority:machine:canonical" in result["warnings"]
    assert result["materialized"] is False


def test_wiki_draft_review_blocks_tampered_draft_body(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    judgment = {
        "supporting_record_ids": ["STAT-RUNTIME"],
        "rationale": "The draft is otherwise materializable.",
        "confidence": 0.9,
        "machine_draft": "# Runtime\n\n- record: STAT-RUNTIME\n",
        "human_draft": "# Runtime\n\nReadable draft.\n",
    }
    plan = run_next_json(
        project,
        "wiki-synthesis-plan",
        "--topic",
        "Runtime",
        "--domain",
        "architecture",
        "--write-drafts",
        "--judgment-json",
        json.dumps(judgment),
    )
    machine_draft = Path(plan["draft_paths"]["machine"])
    machine_draft.write_text(
        machine_draft.read_text(encoding="utf-8") + "\nUnreviewed body edit.\n",
        encoding="utf-8",
    )

    result = run_next_json(project, "wiki-draft-review", "--topic", "Runtime", "--materialize")

    assert result["status"] == "blocked"
    assert "draft_hash_mismatch:machine" in result["warnings"]
    assert result["materialized"] is False


def test_wiki_draft_review_blocks_unknown_inactive_and_superseded_supporting_records(
    project: Path,
) -> None:
    activate(project, "kb-wiki")
    conn = sqlite3.connect(project / ".kb" / "kb.db")
    try:
        conn.execute(
            "UPDATE records SET status = 'SUPERSEDIDO', replacement_id = 'LEARN-DUP-S1' WHERE id = 'LEARN-DUP'"
        )
        conn.commit()
    finally:
        conn.close()

    manifest_id = "llm-manual-wiki-redteam"
    topic = "Runtime"
    supporting = ["STAT-RUNTIME", "LEARN-DUP", "UNKNOWN-RECORD"]
    draft_root = project / ".kb-next" / "wiki" / "drafts"
    machine = draft_root / "machine" / "runtime.md"
    human = draft_root / "human" / "runtime.md"
    machine.parent.mkdir(parents=True)
    human.parent.mkdir(parents=True)
    header = "\n".join(
        [
            "---",
            "kind: machine_wiki_draft",
            f"topic: {topic}",
            f"manifest_id: {manifest_id}",
            "authority: derived_draft",
            "supporting_records:",
            "  - STAT-RUNTIME",
            "  - LEARN-DUP",
            "  - UNKNOWN-RECORD",
            "---",
            "",
        ]
    )
    machine.write_text(header + "# Runtime\n", encoding="utf-8")
    human.write_text(header.replace("kind: machine_wiki_draft", "kind: human_wiki_draft") + "# Runtime\n", encoding="utf-8")
    manifest = {
        "manifest_id": manifest_id,
        "task_type": "wiki_synthesis",
        "validation_status": "valid",
        "warnings": [],
        "confidence": 0.9,
        "judgment": {
            "supporting_record_ids": supporting,
            "confidence": 0.9,
            "rationale": "Manual manifest for red-team support record validation.",
        },
        "generated_drafts": {
            "machine": {"path": project_rel(project, machine), "hash": file_hash(machine)},
            "human": {"path": project_rel(project, human), "hash": file_hash(human)},
        },
    }
    manifest_path = project / ".kb-next" / "manifests" / "llm" / f"{manifest_id}.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    result = run_next_json(project, "wiki-draft-review", "--topic", topic, "--materialize")

    assert result["status"] == "blocked"
    assert "unknown_supporting_record:UNKNOWN-RECORD" in result["warnings"]
    assert "inactive_supporting_record:LEARN-DUP:SUPERSEDIDO" in result["warnings"]
    assert "superseded_supporting_record:LEARN-DUP:LEARN-DUP-S1" in result["warnings"]
    assert result["materialized"] is False


def test_semantic_commands_leave_classic_kb_database_unchanged(project: Path, tmp_path: Path) -> None:
    activate(project, "kb-wiki")
    db_path = project / ".kb" / "kb.db"
    before = file_hash(db_path)
    lookup_judgment = {
        "ranked_record_ids": ["DEC-BOOT"],
        "confidence": 0.9,
        "rationale": "Relevant decision.",
        "provenance": [{"record_id": "DEC-BOOT"}],
    }
    curation_judgment = {
        "action": "defer",
        "findings": ["ok"],
        "rationale": "No curation mutation needed.",
        "confidence": 0.8,
        "risk": "none",
        "provenance": [{"record_id": "DEC-BOOT"}],
    }
    filing_input = {"title": "Semantic runtime", "content": "Proposal only."}
    filing_judgment = {
        "action": "defer",
        "rationale": "No durable write yet.",
        "confidence": 0.6,
        "risk": "Insufficient evidence.",
        "provenance": [{"record_id": "STAT-RUNTIME"}],
    }
    wiki_judgment = {
        "supporting_record_ids": ["STAT-RUNTIME"],
        "rationale": "Draft only.",
        "confidence": 0.8,
        "machine_draft": "# Runtime\n",
        "human_draft": "# Runtime\n",
    }

    run_next_json(project, "semantic-lookup", "--query", "bootstrap", "--facet", "decisions", "--judgment-json", json.dumps(lookup_judgment))
    run_next_json(project, "curation-proposal", "--query", "bootstrap", "--facet", "decisions", "--judgment-json", json.dumps(curation_judgment))
    run_next_json(
        project,
        "filing-proposal",
        "--input",
        write_json(tmp_path / "filing-input.json", filing_input),
        "--category",
        "FATO",
        "--domain",
        "architecture",
        "--judgment-json",
        json.dumps(filing_judgment),
    )
    run_next_json(project, "wiki-synthesis-plan", "--topic", "Runtime", "--domain", "architecture", "--write-drafts", "--judgment-json", json.dumps(wiki_judgment))

    assert file_hash(db_path) == before
