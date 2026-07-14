from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MASTER = REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
PIP_SCAFFOLD = REPO_ROOT / "kb_factory" / "_scaffold_vnext" / "runtime" / "kb_next.py"

_RUN = "import sys; from kb_factory.cli import main; sys.exit(main(sys.argv[1:]))"


def _cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _RUN, *argv],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )


def test_pip_scaffold_matches_master() -> None:
    # The vendored pip engine must never drift from the single master.
    assert PIP_SCAFFOLD.is_file()
    assert PIP_SCAFFOLD.read_bytes() == MASTER.read_bytes()


def test_vnext_init_installs_engine_and_activates(tmp_path: Path) -> None:
    proc = _cli("vnext-init", str(tmp_path), "--mode", "kb-alone")
    assert proc.returncode == 0, proc.stderr
    engine = tmp_path / ".kb-next" / "runtime" / "kb_next.py"
    config = tmp_path / ".kb-next" / "kb-next.config.json"
    assert engine.is_file()
    assert engine.read_bytes() == PIP_SCAFFOLD.read_bytes()  # ladder rung 1 populated
    assert config.is_file()  # activation-wizard ran => chicken-and-egg killed
    assert (tmp_path / ".kb-next" / ".kb-next-version").is_file()


def test_vnext_update_refreshes_engine_only(tmp_path: Path) -> None:
    assert _cli("vnext-init", str(tmp_path), "--mode", "kb-alone").returncode == 0
    config = tmp_path / ".kb-next" / "kb-next.config.json"
    before = config.read_bytes()
    engine = tmp_path / ".kb-next" / "runtime" / "kb_next.py"
    engine.write_text("# stale\n", encoding="utf-8")
    proc = _cli("vnext-update", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert engine.read_bytes() == PIP_SCAFFOLD.read_bytes()  # engine refreshed
    assert config.read_bytes() == before  # data preserved


def test_vnext_update_refuses_without_activation(tmp_path: Path) -> None:
    proc = _cli("vnext-update", str(tmp_path))
    assert proc.returncode != 0
    assert "vnext-init" in proc.stderr
