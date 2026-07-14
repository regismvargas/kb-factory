from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_agent_packages import build_artifacts, validate_artifact, write_zip  # noqa: E402

MASTER = REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


def _vnext_artifacts(tmp_path: Path):
    return build_artifacts(REPO_ROOT, tmp_path, scope="vnext")


def test_every_vnext_zip_ships_the_runtime_engine(tmp_path: Path) -> None:
    # Every distributable vNext plugin ZIP (codex/claude/cowork) must carry the
    # engine at runtime/kb_next.py so the resolution ladder can find it after
    # install. Content-identity guards against a truncated or stale copy.
    master_bytes = MASTER.read_bytes()
    artifacts = _vnext_artifacts(tmp_path)
    assert len(artifacts) == 3
    for artifact in artifacts:
        write_zip(artifact)
        with ZipFile(artifact.archive_path, "r") as archive:
            names = archive.namelist()
            assert "runtime/kb_next.py" in names, artifact.archive_path.name
            assert archive.read("runtime/kb_next.py") == master_bytes, artifact.archive_path.name
        assert validate_artifact(artifact, artifact.archive_path) == [], artifact.archive_path.name


def test_required_entry_guard_rejects_missing_runtime(tmp_path: Path) -> None:
    # If a future build ever drops the engine, validate_artifact must fail loudly
    # instead of silently shipping a runtime-less plugin.
    artifact = _vnext_artifacts(tmp_path)[0]
    write_zip(artifact)
    with ZipFile(artifact.archive_path, "r") as src:
        kept = [(n, src.read(n)) for n in src.namelist() if n != "runtime/kb_next.py"]
    with ZipFile(artifact.archive_path, "w", compression=ZIP_DEFLATED) as dst:
        for name, data in kept:
            dst.writestr(name, data)
    errors = validate_artifact(artifact, artifact.archive_path)
    assert any("runtime/kb_next.py" in e and "missing required entry" in e for e in errors), errors
