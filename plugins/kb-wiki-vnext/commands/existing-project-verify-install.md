---
description: Verify KB/Wiki vNext installation in an existing project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in an existing project.

This command is read-only and suitable after install, activation, upgrade, or
rollback.

1. Run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`
2. Read only `.kb-next/memory/NOW.md`.
3. Run a deterministic lookup:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py lookup --query "status atual" --json`
4. Confirm no `.kb/wiki/live` publication occurred and no direct `.kb/kb.db`
   edit was made by vNext.
5. Report package names and versions if plugin metadata is available.
