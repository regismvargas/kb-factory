---
description: Diagnose an existing or legacy project before activating KB/Wiki vNext.
allowed-tools: Read, Bash, Grep, Glob
---

Diagnose an existing or legacy project before activating KB/Wiki vNext.

This command is read-only. It identifies whether the workspace already has
classic `.kb/`, vNext `.kb-next/`, wiki output, and a usable vNext runtime.

1. Check for `.kb/`, `.kb/kb.py`, `.kb-next/`, `.kb-next/memory/NOW.md`, and
   `.kb/wiki/live`.
2. If `.kb-next/` exists, run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`
   and read only `.kb-next/memory/NOW.md`.
3. If `.kb-next/` is absent but `.kb/` exists, report that the workspace is an
   existing classic KB project and recommend `existing-project-activate-vnext`.
4. Do not run activation, copy templates, publish wiki output, or mutate
   `.kb/kb.db`.
