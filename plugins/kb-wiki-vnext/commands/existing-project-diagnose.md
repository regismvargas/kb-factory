---
description: Diagnose an existing or legacy project before activating KB/Wiki vNext.
allowed-tools: Read, Bash, Grep, Glob
---

Diagnose an existing or legacy project before activating KB/Wiki vNext.

This command does not mutate canonical `.kb/`. It identifies whether the
workspace already has classic `.kb/`, vNext `.kb-next/`, wiki output, and a
usable vNext runtime. If it runs `session-start`, that runtime command appends
operational evidence to `.kb-next/operations.jsonl`.

1. Check for `.kb/`, `.kb/kb.py`, `.kb-next/`, `.kb-next/memory/NOW.md`, and
   `.kb/wiki/live`.
2. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   Report the resolution outcome as a diagnostic finding: which path resolved,
   or that the vNext runtime was not found.
3. If `.kb-next/` exists and a runtime was resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`)
   and read only `.kb-next/memory/NOW.md` by default.
4. If `.kb-next/` exists but no runtime was resolved, read
   `.kb-next/memory/NOW.md` directly to confirm data presence and report the
   diagnosis as degraded. Recommend reinstalling/upgrading the vNext plugin or
   running `existing-project-activate-vnext`; do not ask the user to hand-place
   the runtime.
5. If `.kb-next/` is absent but `.kb/` exists, report that the workspace is an
   existing classic KB project and recommend `existing-project-activate-vnext`.
6. Do not run activation, copy templates, publish wiki output, or mutate
   `.kb/kb.db`.
