from __future__ import annotations

import json
from pathlib import Path

import tools.build_release_bundle as release_bundle


def test_release_bundle_is_selective_hash_bound_and_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    inputs: list[tuple[str, Path]] = []
    for index, (platform, source) in enumerate(release_bundle.release_inputs("0.3.0")):
        path = tmp_path / "inputs" / source.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"artifact-{index}\n".encode())
        inputs.append((platform, path))
    session_gate = tmp_path / "inputs" / "session-gate-plugin-0.2.7.zip"
    session_gate.write_bytes(b"validated but not published\n")
    monkeypatch.setattr(release_bundle, "release_inputs", lambda version: tuple(inputs))

    output = tmp_path / "release"
    kwargs = {
        "version": "0.3.0",
        "public_candidate_sha": "a" * 40,
        "source_date_epoch": 1_784_671_790,
        "output_dir": output,
    }
    release_bundle.build_bundle(**kwargs)
    first = {path.name: path.read_bytes() for path in output.iterdir()}
    release_bundle.build_bundle(**kwargs)
    second = {path.name: path.read_bytes() for path in output.iterdir()}

    assert first == second
    assert session_gate.name not in first
    manifest = json.loads(first["kb-factory-v0.3.0-manifest.json"])
    assert manifest["selection"] == {
        "plugin_assets": 6,
        "python_assets": 2,
        "session_gate_assets": 0,
        "standalone_assets": 1,
    }
    assert len(manifest["assets"]) == 9
    provenance = json.loads(first["kb-factory-v0.3.0-provenance.json"])
    assert provenance["public_candidate_sha"] == "a" * 40
    assert provenance["private_source_sha"] == release_bundle.PRIVATE_SOURCE_SHA
    checksums = first["SHA256SUMS.txt"].decode().splitlines()
    assert len(checksums) == 11
    assert not any("session-gate" in line for line in checksums)
