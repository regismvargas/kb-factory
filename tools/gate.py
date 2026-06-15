#!/usr/bin/env python3
"""KB Factory cleanliness gate.

Fast, deterministic checks that the workbench KB is in a shippable, trustworthy
state. Intended as a pre-commit hook and a CI step so the authoring repo cannot
drift back into the state the merit review flagged (stale wiki pages, source
hash drift, runtime copies out of sync).

Checks (all fast — no full test run):
  1. doctor    — SQLite integrity ok, zero source hash drift.
  2. wiki-lint — zero issues on the live wiki.
  3. parity    — the canonical runtime (core/runtime/*.py) is byte-identical to
                 the scaffold template runtime and the live .kb runtime, and
                 .kb/kb.py matches the template kb.py.

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
        capture_output=True, text=True,
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


def check_parity(failures):
    core_rt = ROOT / "core" / "runtime"
    template_kb = ROOT / "core" / "templates" / "kb"
    mirrors = {
        "template runtime": template_kb / "runtime",
        "live .kb runtime": ROOT / ".kb" / "runtime",
    }
    if not core_rt.is_dir():
        failures.append("core/runtime not found")
        return
    for label, mirror in mirrors.items():
        if not mirror.is_dir():
            failures.append(f"{label} not found")
            continue
        for src in sorted(core_rt.glob("*.py")):
            other = mirror / src.name
            if not other.is_file():
                failures.append(f"{label} missing {src.name}")
            elif other.read_bytes() != src.read_bytes():
                failures.append(f"{label} drift: {src.name}")
    # The live kb.py entry point must match the distributed template.
    tmpl_kb_py = template_kb / "kb.py"
    if KB_PY.is_file() and tmpl_kb_py.is_file():
        if KB_PY.read_bytes() != tmpl_kb_py.read_bytes():
            failures.append("kb.py drift: .kb/kb.py != template kb.py")


def main():
    failures: list[str] = []
    check_doctor(failures)
    check_wiki_lint(failures)
    check_parity(failures)
    if failures:
        print("KB gate FAILED — the KB is not in a shippable state:")
        for item in failures:
            print(f"  - {item}")
        print("\nFix the above (e.g. `python .kb/kb.py wiki-sync --force`, "
              "re-sync runtime mirrors) or bypass once with `git commit --no-verify`.")
        return 1
    print("KB gate OK: integrity, zero hash drift, zero wiki-lint issues, runtime parity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
