from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MASTER = REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
PLUGIN = REPO_ROOT / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
PIP_SCAFFOLD = REPO_ROOT / "kb_factory" / "_scaffold_vnext" / "runtime" / "kb_next.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_runtime(root: Path, relative: Path, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _seed_vnext_mirrors(root: Path, master: bytes, plugin: bytes, pip: bytes) -> None:
    _write_runtime(root, Path("core/versions/kb-wiki-vnext/runtime/kb_next.py"), master)
    _write_runtime(root, Path("plugins/kb-wiki-vnext/runtime/kb_next.py"), plugin)
    _write_runtime(root, Path("kb_factory/_scaffold_vnext/runtime/kb_next.py"), pip)


def _seed_classic_mirrors(root: Path) -> None:
    content = b"# runtime mirror\n"
    for relative in (
        Path("core/runtime/example.py"),
        Path("core/templates/kb/runtime/example.py"),
        Path("kb_factory/_scaffold/runtime/example.py"),
    ):
        _write_runtime(root, relative, content)


def test_all_shipped_vnext_runtimes_match_the_master() -> None:
    master = MASTER.read_bytes()
    assert PLUGIN.read_bytes() == master
    assert PIP_SCAFFOLD.read_bytes() == master


def test_sync_tool_check_detects_and_write_mode_repairs_drift(tmp_path: Path) -> None:
    sync = _load_module("sync_vnext_runtime_test", REPO_ROOT / "tools" / "sync_vnext_runtime.py")
    _seed_vnext_mirrors(tmp_path, b"master\n", b"stale plugin\n", b"master\n")

    assert sync.runtime_mirror_drift(tmp_path) == [
        "runtime drift: plugins/kb-wiki-vnext/runtime/kb_next.py"
    ]
    assert sync.sync_runtime_mirrors(tmp_path) == ["plugins/kb-wiki-vnext/runtime/kb_next.py"]
    assert sync.runtime_mirror_drift(tmp_path) == []


def test_gate_passes_clean_public_checkout_without_authoring_kb(tmp_path: Path, monkeypatch, capsys) -> None:
    gate = _load_module("gate_public_checkout_test", REPO_ROOT / "tools" / "gate.py")
    _seed_classic_mirrors(tmp_path)
    _seed_vnext_mirrors(tmp_path, b"vnext runtime\n", b"vnext runtime\n", b"vnext runtime\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "KB_PY", tmp_path / ".kb" / "kb.py")

    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "skipping doctor and wiki-lint" in output
    assert "KB gate OK" in output


def test_gate_rejects_vnext_mirror_drift_without_authoring_kb(tmp_path: Path, monkeypatch, capsys) -> None:
    gate = _load_module("gate_vnext_drift_test", REPO_ROOT / "tools" / "gate.py")
    _seed_classic_mirrors(tmp_path)
    _seed_vnext_mirrors(tmp_path, b"vnext runtime\n", b"stale plugin\n", b"vnext runtime\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "KB_PY", tmp_path / ".kb" / "kb.py")

    assert gate.main() == 1
    assert "vNext plugin runtime drift" in capsys.readouterr().out
