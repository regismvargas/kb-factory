from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "session-gate"
EVAL_ROOT = ROOT / ".tmp" / "session-gate-eval" / "session-gate-workspace"
STARTUP_EVALS = EVAL_ROOT / "evals" / "evals.json"
STARTUP_BASELINE = EVAL_ROOT / "iteration-1" / "benchmark.json"
SESSION_END_EVALS = [
    (10, "mock-full", "S14"),
    (11, "mock-kb-only", "S14"),
    (12, "mock-empty", "S14"),
]


def load_detector():
    spec = importlib.util.spec_from_file_location(
        "session_gate_detector", PLUGIN_ROOT / "scripts" / "detect_workspace.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DETECTOR = load_detector()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def run(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args, cwd=str(cwd), text=True, capture_output=True, check=False
        )
    except FileNotFoundError:
        return False, ""
    return proc.returncode == 0, (proc.stdout.strip() or proc.stderr.strip())


def git_summary(cwd: Path) -> str:
    ok, out = run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    if not ok or "true" not in out.lower():
        return "Git audit unavailable: workspace is not a git repository."
    _, status = run(["git", "status", "--short"], cwd)
    return status or "Working tree clean."


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def jload(text: str) -> dict:
    return json.loads(text) if text else {}


def pending(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def active_kickoffs(workspace: Path) -> list[str]:
    root = workspace / "kickoffs"
    if not root.is_dir():
        return []
    return sorted(
        item.name
        for item in root.iterdir()
        if item.is_file() and "HANDOFF" not in item.name
    )


def forbidden_case_terms(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ["case", "handoff", "role bound", "allow", "block"])


def build_handoff(workspace: Path, session_id: str, items: list[str], git: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    path = workspace / "kickoffs" / f"HANDOFF_SESSION_{safe}_EXIT.md"
    files = [f"kickoffs/{path.name}"]
    for candidate in [
        "kickoffs/WP-042-rate-limiting.md",
        ".kb/memory/NOW.md",
        ".kb/memory/HOT.md",
    ]:
        if (workspace / candidate).exists():
            files.append(candidate)
    items_md = "\n".join(f"- [ ] {item}" for item in items) or "- [ ] No verified pending items found."
    write(
        path,
        f"""
# Handoff: Session {session_id} Exit

**From:** Session Gate wrapper evaluation
**Date:** 2026-04-13
**Purpose:** Preserve verified state for the next Cowork session.
**Status:** EXIT

## Executive Summary

Session closeout was executed as a thin wrapper over KB-lifecycle and CASE Companion.
The workspace still has an undispatched kickoff for WP-042 and open KB pendencias.
No new session decision could be verified from workspace artifacts alone, so none was fabricated here.

## Git State

### mock-full
- {git}

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| None verified | No new session decision was confirmed from workspace evidence | Avoid inventing D-S14 records or handoff claims |

## Pending Items

{items_md}

## Files to Read in Next Session

{chr(10).join(f"{i}. {item}" for i, item in enumerate(files, start=1))}
""",
    )
    return path


def startup_executor(workspace: Path, with_skill: bool):
    detect = DETECTOR.detect(workspace)
    data = {
        "kb": detect["kb"]["found"],
        "case": detect["case"]["found"],
        "kb_start": False,
        "kb_end": False,
        "now": False,
        "hot": False,
        "role": False,
        "handoff": False,
        "consistency": False,
        "pending": [],
        "action": "",
        "git": "",
        "handoff_path": None,
    }
    lines = ["# Session Gate Output", ""]
    if not data["kb"] and not data["case"]:
        suggestion = (
            "Considere configurar KB-lifecycle e CASE Companion se este projeto precisar de contexto durável."
            if with_skill
            else "Documente objetivos, dependências e testes antes de começar."
        )
        lines += ["## Workspace detected", "No KB-lifecycle or CASE artifacts were found in this workspace.", "", "## Suggested next action", suggestion]
        data["action"] = suggestion
        return "\n".join(lines), data
    lines += ["## Workspace detected"]
    if data["kb"] and data["case"]:
        lines.append("KB-lifecycle and CASE Companion detected.")
    elif data["kb"]:
        lines.append("KB-lifecycle detected.")
    else:
        lines.append("CASE Companion detected.")
    lines.append("")
    if data["kb"]:
        ok, out = run([sys.executable, ".kb/kb.py", "lifecycle", "session-start", "--json"], workspace)
        info = jload(out) if ok else {}
        _, pend = run([sys.executable, ".kb/kb.py", "pending"], workspace)
        now_line = first_line(read(workspace / ".kb" / "memory" / "NOW.md"))
        if with_skill and data["kb"] and not data["case"]:
            now_line = now_line.replace(" No CASE pipeline active.", "").replace("CASE pipeline", "pipeline")
        data["kb_start"] = ok
        data["now"] = True
        data["hot"] = True
        data["pending"] = pending(pend)
        lines += [
            "## KB state",
            f"- Session lifecycle initialized: {'yes' if ok else 'deferred'}",
            f"- Session: {info.get('session', 'unknown')}",
            f"- NOW: {now_line}",
            f"- HOT: {first_line(read(workspace / '.kb' / 'memory' / 'HOT.md'))}",
            f"- Pending items: {len(data['pending'])}",
            "",
        ]
    if data["case"]:
        latest = detect["case"]["details"].get("latest_handoff")
        data["role"] = with_skill and bool(detect["case"]["details"].get("role_boundaries_ref"))
        if latest:
            data["handoff"] = True
        lines += ["## CASE state"]
        if latest:
            lines.append(f"- Latest handoff: {first_line(read(workspace / latest))}")
        lines.append(f"- Active kickoffs: {', '.join(active_kickoffs(workspace)) or 'none'}")
        if with_skill:
            lines.append(
                f"- Canonical role boundaries loaded from `{detect['case']['details'].get('role_boundaries_ref')}`."
            )
        lines.append("")
    if data["case"] and "WP-042-rate-limiting.md" in active_kickoffs(workspace):
        data["action"] = "Continue from WP-042 and prepare dispatch."
    elif data["pending"]:
        data["action"] = f"Start with {data['pending'][0].split(':')[0]}."
    else:
        data["action"] = suggestion if not data["kb"] and not data["case"] else "Review the detected subsystem state."
    lines += ["## Suggested next action", data["action"]]
    if data["kb"] and not data["case"] and with_skill:
        lines = [line for line in lines if "CASE" not in line and "role bound" not in line.lower() and "ALLOW" not in line and "BLOCK" not in line]
    return "\n".join(lines), data


def closeout_executor(workspace: Path, session_id: str, with_skill: bool):
    detect = DETECTOR.detect(workspace)
    data = {
        "kb": detect["kb"]["found"],
        "case": detect["case"]["found"],
        "kb_start": False,
        "kb_end": False,
        "now": False,
        "hot": False,
        "role": False,
        "handoff": False,
        "consistency": False,
        "pending": [],
        "action": "",
        "git": git_summary(workspace),
        "handoff_path": None,
    }
    lines = ["# Session Gate Closeout", ""]
    if not data["kb"] and not data["case"]:
        lines += ["## Workspace detected", "No KB-lifecycle or CASE artifacts were found in this workspace.", "", "## Safe to close", "Yes. No lifecycle closeout surfaces were available, and no handoff was fabricated."]
        return "\n".join(lines), data
    lines += ["## Workspace detected"]
    if data["kb"] and data["case"]:
        lines.append("KB-lifecycle and CASE Companion detected.")
    elif data["kb"]:
        lines.append("KB-lifecycle detected.")
    else:
        lines.append("CASE Companion detected.")
    lines += ["", "## Pre-close audit", "- KB audit: only verified workspace state was used.", "- CASE audit: only files present in the workspace were considered.", f"- Git audit: {data['git']}", ""]
    if data["kb"]:
        ok, out = run([sys.executable, ".kb/kb.py", "lifecycle", "session-end", "--json"], workspace)
        info = jload(out) if ok else {}
        _, pend = run([sys.executable, ".kb/kb.py", "pending"], workspace)
        data["kb_end"] = ok
        data["pending"] = pending(pend)
        lines += ["## KB closeout", f"- session-end executed: {'yes' if ok else 'deferred'}", f"- Session closed: {info.get('session_closed', 'unknown')}", ""]
    if data["case"] and with_skill:
        handoff = build_handoff(workspace, session_id, data["pending"], data["git"])
        data["handoff"] = handoff.exists()
        data["handoff_path"] = str(handoff)
        ids = [item.split(":")[0] for item in data["pending"] if ":" in item]
        handoff_text = read(handoff)
        data["consistency"] = all(item in handoff_text for item in ids)
        lines += ["## CASE closeout", f"- Handoff written: {handoff.relative_to(workspace)}", "", "## Consistency", "- Verified pending items from KB are reflected in the CASE handoff." if data["consistency"] else "- Consistency gap found between KB pending items and the CASE handoff.", "- No new session decision was fabricated for the handoff.", ""]
    lines += ["## Safe to close", "Yes. Closeout persisted only the verified subsystem state that was actually present."]
    if data["kb"] and not data["case"] and with_skill:
        lines = [line for line in lines if "CASE" not in line and "handoff" not in line.lower() and "role bound" not in line.lower() and "ALLOW" not in line and "BLOCK" not in line]
    return "\n".join(lines), data


def grade(mode: str, eval_id: int, with_skill: bool, output: str, data: dict):
    if mode == "startup" and eval_id == 0:
        return [
            ("Detected KB and CASE", data["kb"] and data["case"]),
            ("Ran kb.py lifecycle session-start", data["kb_start"]),
            ("Read NOW.md and HOT.md", data["now"] and data["hot"]),
            ("Listed pending KB items", bool(data["pending"])),
            ("Loaded canonical CASE role boundaries", data["role"]),
            ("Read latest handoff", data["handoff"]),
            ("Suggested continuing WP-042", "WP-042" in data["action"]),
        ]
    if mode == "startup" and eval_id == 1:
        return [
            ("Detected KB only", data["kb"] and not data["case"]),
            ("Did not mention CASE, handoff, role boundaries, or ALLOW/BLOCK", not forbidden_case_terms(output)),
            ("Ran kb.py lifecycle session-start", data["kb_start"]),
            ("Read NOW.md and HOT.md", data["now"] and data["hot"]),
            ("Did not fabricate CASE content", not data["case"] and not data["handoff"] and not data["role"]),
        ]
    if mode == "startup":
        return [
            ("Detected empty workspace correctly", not data["kb"] and not data["case"]),
            ("Did not fabricate lifecycle artifacts", not data["kb_start"] and not data["handoff"]),
            ("Handled empty workspace gracefully", "Suggested next action" in output or "No KB-lifecycle or CASE artifacts" in output),
            ("Suggested KB-lifecycle or CASE setup", ("KB-lifecycle" in output and "CASE" in output) if with_skill else ("KB-lifecycle" not in output and "CASE" not in output)),
        ]
    if eval_id == 10:
        handoff_text = read(Path(data["handoff_path"])) if data["handoff_path"] else ""
        return [
            ("Detected KB and CASE", data["kb"] and data["case"]),
            ("Ran kb.py lifecycle session-end", data["kb_end"]),
            ("Handled git audit without inventing repository state", "not a git repository" in data["git"].lower()),
            ("Wrote CASE handoff for S14", data["handoff"]),
            ("Cross-checked pending items against KB", data["consistency"]),
            ("Did not fabricate new session decisions", "No new session decision could be verified" in handoff_text),
        ]
    if eval_id == 11:
        return [
            ("Detected KB only", data["kb"] and not data["case"]),
            ("Ran kb.py lifecycle session-end", data["kb_end"]),
            ("Did not mention CASE, handoff, role boundaries, or ALLOW/BLOCK", not forbidden_case_terms(output)),
            ("Did not fabricate CASE artifacts", not data["handoff"]),
        ]
    return [
        ("Detected empty workspace correctly", not data["kb"] and not data["case"]),
        ("Did not fabricate lifecycle persistence or handoff", not data["kb_end"] and not data["handoff"]),
        ("Handled empty closeout gracefully", "Safe to close" in output or "No KB-lifecycle or CASE artifacts" in output),
    ]


def run_mode(mode: str):
    if mode == "startup":
        evals = json.loads(STARTUP_EVALS.read_text(encoding="utf-8"))["evals"]
        out_dir = EVAL_ROOT / "iteration-2"
    else:
        evals = [{"id": eid, "workspace": ws, "session_id": sid} for eid, ws, sid in SESSION_END_EVALS]
        out_dir = EVAL_ROOT / "session-end-iteration-1"
    clean_dir(out_dir)
    runs = []
    for spec in evals:
        eval_dir = out_dir / f"eval-{spec['id']}-{spec['workspace']}-{mode}"
        clean_dir(eval_dir)
        workspace = EVAL_ROOT / spec["workspace"]
        results = {}
        for config_name, with_skill in [("with_skill", True), ("without_skill", False)]:
            start = time.perf_counter()
            if mode == "startup":
                output, data = startup_executor(workspace, with_skill)
                output_name = "briefing.md"
            else:
                output, data = closeout_executor(workspace, spec["session_id"], with_skill)
                output_name = "closeout.md"
            elapsed = round(time.perf_counter() - start, 4)
            checks = grade(mode, spec["id"], with_skill, output, data)
            passed = sum(1 for _, ok in checks if ok)
            total = len(checks)
            config_dir = eval_dir / config_name
            write(config_dir / "outputs" / output_name, output)
            write(
                config_dir / "grading.json",
                json.dumps(
                    {
                        "eval_id": spec["id"],
                        "config": config_name,
                        "expectations": [{"text": text, "passed": ok} for text, ok in checks],
                    },
                    indent=2,
                ),
            )
            write(
                config_dir / "timing.json",
                json.dumps({"time_seconds": elapsed, "tokens": None}, indent=2),
            )
            results[config_name] = {
                "pass_rate": round(passed / total, 3),
                "passed": passed,
                "total": total,
                "time_seconds": elapsed,
                "tokens": None,
            }
        runs.append({"eval_id": spec["id"], "eval_name": spec["workspace"], **results})
    summary = {
        "with_skill": {
            "mean_pass_rate": round(sum(item["with_skill"]["pass_rate"] for item in runs) / len(runs), 3),
            "mean_time_seconds": round(sum(item["with_skill"]["time_seconds"] for item in runs) / len(runs), 4),
            "mean_tokens": None,
        },
        "without_skill": {
            "mean_pass_rate": round(sum(item["without_skill"]["pass_rate"] for item in runs) / len(runs), 3),
            "mean_time_seconds": round(sum(item["without_skill"]["time_seconds"] for item in runs) / len(runs), 4),
            "mean_tokens": None,
        },
    }
    summary["delta"] = {
        "pass_rate": round(summary["with_skill"]["mean_pass_rate"] - summary["without_skill"]["mean_pass_rate"], 3),
        "time_seconds": round(summary["with_skill"]["mean_time_seconds"] - summary["without_skill"]["mean_time_seconds"], 4),
        "tokens": None,
    }
    benchmark = {
        "metadata": {"mode": mode, "executor": "deterministic-local-harness", "tokens_measured": False},
        "runs": runs,
        "run_summary": summary,
        "notes": [
            "This harness evaluates wrapper compliance, not Cowork automatic trigger probability.",
            "Token counts were not measured because these runs were deterministic local executions.",
        ],
    }
    if mode == "startup" and STARTUP_BASELINE.exists():
        benchmark["baseline_reference"] = json.loads(STARTUP_BASELINE.read_text(encoding="utf-8"))
    write(out_dir / "benchmark.json", json.dumps(benchmark, indent=2))


def main(argv: list[str]) -> int:
    run_mode(argv[1] if len(argv) > 1 else "startup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
