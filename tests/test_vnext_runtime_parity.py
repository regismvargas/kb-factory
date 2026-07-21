from __future__ import annotations

import importlib.util
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "tools" / "sync_vnext_runtime.py"
MASTER = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
SOURCE_COPY = ROOT / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py"

SPEC = importlib.util.spec_from_file_location("sync_vnext_runtime", SYNC)
assert SPEC is not None and SPEC.loader is not None
sync_vnext_runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_vnext_runtime)


def test_vnext_runtime_mirror_in_sync() -> None:
    # The default gate must be hermetic to the tracked private checkout.
    proc = subprocess.run(
        [sys.executable, str(SYNC), "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "source mirrors" in proc.stdout


def test_private_source_mirror_matches_master() -> None:
    assert SOURCE_COPY.is_file()
    assert SOURCE_COPY.read_bytes() == MASTER.read_bytes()


def test_write_mode_requires_explicit_scope() -> None:
    before = SOURCE_COPY.read_bytes()

    proc = subprocess.run(
        [sys.executable, str(SYNC)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "write mode requires explicit --scope" in proc.stderr
    assert SOURCE_COPY.read_bytes() == before


def test_windows_reparse_attribute_is_treated_as_junction() -> None:
    class ReparsePoint:
        def is_symlink(self) -> bool:
            return False

        def lstat(self) -> SimpleNamespace:
            return SimpleNamespace(st_file_attributes=0x400)

    assert sync_vnext_runtime._is_link_or_junction(ReparsePoint()) is True


def test_source_scope_does_not_require_or_create_release_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master" / "kb_next.py"
    source_copy = tmp_path / "plugins" / "runtime" / "kb_next.py"
    release_root = tmp_path / "public-checkout"
    release_copy = release_root / "runtime" / "kb_next.py"
    master.parent.mkdir(parents=True)
    source_copy.parent.mkdir(parents=True)
    master.write_bytes(b"canonical\n")
    source_copy.write_bytes(b"stale\n")

    monkeypatch.setattr(sync_vnext_runtime, "MASTER", master)
    monkeypatch.setattr(sync_vnext_runtime, "REPO", tmp_path)
    monkeypatch.setattr(sync_vnext_runtime, "SOURCE_MIRRORS", [source_copy])
    monkeypatch.setattr(
        sync_vnext_runtime,
        "RELEASE_MIRROR_PATHS",
        [release_copy.relative_to(release_root)],
    )

    sync_vnext_runtime.regenerate("source")

    assert source_copy.read_bytes() == master.read_bytes()
    assert not release_root.exists()


@pytest.mark.parametrize("scope", ["release", "all"])
def test_release_scopes_fail_closed_without_explicit_public_checkout(
    scope: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master" / "kb_next.py"
    source_copy = tmp_path / "plugins" / "runtime" / "kb_next.py"
    release_root = tmp_path / "public-checkout"
    release_copy = release_root / "runtime" / "kb_next.py"
    master.parent.mkdir(parents=True)
    source_copy.parent.mkdir(parents=True)
    master.write_bytes(b"canonical\n")
    source_copy.write_bytes(b"canonical\n")

    monkeypatch.setattr(sync_vnext_runtime, "MASTER", master)
    monkeypatch.setattr(sync_vnext_runtime, "REPO", tmp_path)
    monkeypatch.setattr(sync_vnext_runtime, "SOURCE_MIRRORS", [source_copy])
    monkeypatch.setattr(
        sync_vnext_runtime,
        "RELEASE_MIRROR_PATHS",
        [release_copy.relative_to(release_root)],
    )

    problems = sync_vnext_runtime.stale_mirrors(scope)

    assert len(problems) == 1
    assert "requires an explicit public checkout" in problems[0]
    with pytest.raises(FileNotFoundError, match="requires an explicit public checkout"):
        sync_vnext_runtime.regenerate(scope)


def test_release_scope_checks_every_declared_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = tmp_path / "master" / "kb_next.py"
    release_root = tmp_path / "public-checkout"
    current_copy = release_root / "runtime-a" / "kb_next.py"
    missing_copy = release_root / "runtime-b" / "kb_next.py"
    master.parent.mkdir(parents=True)
    current_copy.parent.mkdir(parents=True)
    master.write_bytes(b"canonical\n")
    current_copy.write_bytes(b"canonical\n")

    monkeypatch.setattr(sync_vnext_runtime, "MASTER", master)
    monkeypatch.setattr(sync_vnext_runtime, "REPO", tmp_path)
    monkeypatch.setattr(
        sync_vnext_runtime,
        "RELEASE_MIRROR_PATHS",
        [
            current_copy.relative_to(release_root),
            missing_copy.relative_to(release_root),
        ],
    )

    problems = sync_vnext_runtime.stale_mirrors("release", release_root)

    assert problems == [f"{missing_copy} <missing>"]


def test_source_scope_refuses_mirror_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    master = repo / "core" / "kb_next.py"
    outside = tmp_path / "outside" / "kb_next.py"
    master.parent.mkdir(parents=True)
    outside.parent.mkdir(parents=True)
    master.write_bytes(b"canonical\n")
    outside.write_bytes(b"stale\n")

    monkeypatch.setattr(sync_vnext_runtime, "REPO", repo)
    monkeypatch.setattr(sync_vnext_runtime, "MASTER", master)
    monkeypatch.setattr(sync_vnext_runtime, "SOURCE_MIRRORS", [outside])

    problems = sync_vnext_runtime.stale_mirrors("source")

    assert len(problems) == 1
    assert "<unsafe:" in problems[0]
    with pytest.raises(RuntimeError, match="escapes its declared root"):
        sync_vnext_runtime.regenerate("source")
