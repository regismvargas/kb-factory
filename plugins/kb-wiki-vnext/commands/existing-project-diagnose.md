---
description: Diagnose an existing or legacy project before activating KB/Wiki vNext.
allowed-tools: Read, Bash, Grep, Glob
---

Diagnose an existing or legacy project before activating KB/Wiki vNext.

This command is read-only. It identifies whether the workspace already has
classic `.kb/`, vNext `.kb-next/`, wiki output, and a usable vNext runtime.

1. Check for `.kb/`, `.kb/kb.py`, `.kb-next/`, `.kb-next/memory/NOW.md`, and
   `.kb/wiki/live`.
2. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   Report the resolution outcome as a diagnostic finding: which path
   resolved, or that the vNext runtime was NOT found (degraded diagnosis).
3. If `.kb-next/` exists and a runtime was resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`)
   and read only `.kb-next/memory/NOW.md`.
4. If `.kb-next/` exists but no runtime was resolved, read
   `.kb-next/memory/NOW.md` directly to confirm data presence and report the
   diagnosis as degraded: the vNext runtime is not installed and the plugin
   does not currently bundle it (known packaging gap). Recommend placing the
   runtime at `.kb-next/runtime/kb_next.py` or running from the KB Factory
   authoring monorepo.
5. If `.kb-next/` is absent but `.kb/` exists, report that the workspace is an
   existing classic KB project and recommend `existing-project-activate-vnext`.
6. Do not run activation, copy templates, publish wiki output, or mutate
   `.kb/kb.db`.
