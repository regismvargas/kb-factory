from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB_NEXT = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


def _bootstrap(project_root: Path, *extra: str) -> dict:
    result = subprocess.run(
        [
            sys.executable, str(KB_NEXT),
            "--project-root", str(project_root),
            "bootstrap", "--json", *extra,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def _activate(project_root: Path) -> None:
    subprocess.run(
        [
            sys.executable, str(KB_NEXT),
            "--project-root", str(project_root),
            "activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )


def _runtime(project_root: Path) -> Path:
    return project_root / ".kb-next" / "runtime" / "kb_next.py"


def test_bootstrap_populates_ladder_rung1(tmp_path: Path) -> None:
    out = _bootstrap(tmp_path)
    target = _runtime(tmp_path)
    assert out["action"] == "created"
    assert out["runtime_version"]
    assert target.is_file()
    # content identity: rung 1 is the real engine, not a stub
    assert target.read_bytes() == KB_NEXT.read_bytes()


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    out = _bootstrap(tmp_path)
    assert out["action"] == "exists"
    assert _runtime(tmp_path).read_bytes() == KB_NEXT.read_bytes()


def test_bootstrap_writes_only_runtime(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    entries = {p.name for p in (tmp_path / ".kb-next").iterdir()}
    assert entries == {"runtime"}


def test_bootstrap_repairs_legacy_runtime(tmp_path: Path) -> None:
    # a pre-existing engine lacking RUNTIME_VERSION must be refreshed, not skipped
    target = _runtime(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text("# legacy runtime without RUNTIME_VERSION\n", encoding="utf-8")
    out = _bootstrap(tmp_path)
    assert out["action"] == "updated"
    assert out["previous_version"] is None
    assert target.read_bytes() == KB_NEXT.read_bytes()


def test_bootstrap_safe_on_activated_workspace(tmp_path: Path) -> None:
    # bootstrap on an already-activated .kb-next/ must add runtime/ without
    # touching config or memory
    _activate(tmp_path)
    now = tmp_path / ".kb-next" / "memory" / "NOW.md"
    config = tmp_path / ".kb-next" / "kb-next.config.json"
    before = (now.read_bytes(), config.read_bytes())
    out = _bootstrap(tmp_path)
    assert out["action"] == "created"
    assert _runtime(tmp_path).read_bytes() == KB_NEXT.read_bytes()
    assert (now.read_bytes(), config.read_bytes()) == before
