from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    cwd = Path(os.getcwd())
    kb_root = cwd / ".kb"
    if not kb_root.is_dir():
        return 0

    if (cwd / ".kb-next" / "kb-next.config.json").is_file():
        # KB/Wiki vNext owns session start here; its own hook prints the
        # startup contract. Emitting the classic NOW.md instruction as well
        # would give the agent two conflicting default reads.
        print(
            "\n".join(
                [
                    "KB Factory classic KB detected alongside KB/Wiki vNext.",
                    "Follow the vNext session-start contract (default read: `.kb-next/memory/NOW.md`).",
                    "Classic `.kb/` stays canonical: `python .kb/kb.py search \"<term>\"` and "
                    "`python .kb/kb.py pending` for targeted reads; do not preload `.kb/memory/NOW.md`.",
                ]
            )
        )
        return 0

    lines = [
        "KB Factory workspace detected.",
        "Use the workspace .kb as the durable memory layer; do not create a parallel memory store in plugin-local docs.",
        "Run `python .kb/kb.py lifecycle session-start --json` before assuming prior context.",
        "Read the NOW.md path it reports (`paths.now`; in a linked Git worktree this is the main worktree KB).",
        "Load `.kb/memory/HOT.md` only when the conversation needs the active working set.",
        "Load `.kb/memory/INDEX.md` only if you need the broader map.",
        "Search before assuming with `python .kb/kb.py search \"<term>\"` and `python .kb/kb.py pending`.",
        "Use `supersede` when meaning changes; keep `update` for routing metadata only.",
    ]

    if (kb_root / "wiki").exists():
        lines.append(
            "If the wiki layer is enabled, inspect `.kb/wiki/live/index.md` or run `python .kb/kb.py wiki-check --json` before editing generated pages."
        )

    lines.append(
        "For CASE projects, keep dispatch and handoff artifacts thin. Durable project memory still belongs in `.kb/`."
    )

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
