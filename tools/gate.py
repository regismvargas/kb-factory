#!/usr/bin/env python3
"""KB Factory cleanliness gate.

Fast, deterministic checks that release runtime surfaces are synchronized.
The public checkout deliberately has no root ``.kb/``. In that shape, the
authoring-only doctor and wiki-lint checks are skipped while all source,
template, pip, and vNext runtime parity checks remain mandatory.

Exit 0 if clean, 1 otherwise. Standard library only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
KB_PY = ROOT / ".kb" / "kb.py"


def _run_json(*args):
    proc = subprocess.run(
        [sys.executable, str(KB_PY), *args, "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).strip()
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"could not parse JSON from `{' '.join(args)}`: {exc}"


def check_doctor(failures):
    data, err = _run_json("doctor")
    if data is None:
        failures.append(f"doctor did not run: {err}")
        return
    if data.get("integrity_check") != "ok":
        failures.append(f"db integrity_check = {data.get('integrity_check')!r}")
    drift = data.get("sources_hash_drift", 0)
    if drift:
        failures.append(f"source hash drift = {drift}")


def check_wiki_lint(failures):
    data, err = _run_json("wiki-lint")
    if data is None:
        failures.append(f"wiki-lint did not run: {err}")
        return
    count = data.get("issue_count", len(data.get("issues", [])))
    if count:
        failures.append(f"wiki-lint issues = {count}")


def check_runtime_tree_parity(source, mirrors, failures):
    if not source.is_dir():
        failures.append(f"{source.relative_to(ROOT)} not found")
        return
    source_files = {path.name: path for path in source.glob("*.py")}
    if not source_files:
        failures.append(f"{source.relative_to(ROOT)} has no Python runtime files")
        return

    for label, mirror in mirrors.items():
        if not mirror.is_dir():
            failures.append(f"{label} not found")
            continue
        mirror_files = {path.name: path for path in mirror.glob("*.py")}
        for name in sorted(source_files.keys() - mirror_files.keys()):
            failures.append(f"{label} missing {name}")
        for name in sorted(mirror_files.keys() - source_files.keys()):
            failures.append(f"{label} unexpected {name}")
        for name, src in sorted(source_files.items()):
            other = mirror_files.get(name)
            if other is not None and other.read_bytes() != src.read_bytes():
                failures.append(f"{label} drift: {src.name}")


def check_vnext_runtime_parity(failures):
    master = ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"
    mirrors = {
        "vNext plugin runtime": ROOT / "plugins" / "kb-wiki-vnext" / "runtime" / "kb_next.py",
        "vNext pip scaffold runtime": ROOT / "kb_factory" / "_scaffold_vnext" / "runtime" / "kb_next.py",
    }
    if not master.is_file():
        failures.append("vNext master runtime not found")
        return
    master_bytes = master.read_bytes()
    for label, mirror in mirrors.items():
        if not mirror.is_file():
            failures.append(f"{label} not found")
        elif mirror.read_bytes() != master_bytes:
            failures.append(f"{label} drift: kb_next.py")


def check_parity(failures, authoring_kb):
    core_rt = ROOT / "core" / "runtime"
    template_kb = ROOT / "core" / "templates" / "kb"
    check_runtime_tree_parity(
        core_rt,
        {
            "template runtime": template_kb / "runtime",
            "pip scaffold runtime": ROOT / "kb_factory" / "_scaffold" / "runtime",
        },
        failures,
    )
    if authoring_kb:
        check_runtime_tree_parity(
            core_rt,
            {"live .kb runtime": ROOT / ".kb" / "runtime"},
            failures,
        )
        tmpl_kb_py = template_kb / "kb.py"
        if tmpl_kb_py.is_file() and KB_PY.read_bytes() != tmpl_kb_py.read_bytes():
            failures.append("kb.py drift: .kb/kb.py != template kb.py")
    check_vnext_runtime_parity(failures)


def main():
    failures: list[str] = []
    authoring_kb = KB_PY.is_file()
    if authoring_kb:
        check_doctor(failures)
        check_wiki_lint(failures)
    else:
        print("KB gate: skipping doctor and wiki-lint (no authoring .kb/kb.py).")
    check_parity(failures, authoring_kb)
    if failures:
        print("KB gate FAILED - the release surface is not shippable:")
        for item in failures:
            print(f"  - {item}")
        print("\nFix the reported mirror drift and re-run the gate.")
        return 1
    if authoring_kb:
        print("KB gate OK: integrity, zero hash drift, zero wiki-lint issues, classic and vNext runtime parity.")
    else:
        print("KB gate OK: classic and vNext runtime parity; doctor/wiki-lint skipped for public checkout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
