---
description: Verify KB/Wiki vNext installation in a new project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in a new project.

This command is read-only after initial bootstrap.

1. Confirm `.kb/`, `.kb/kb.py`, `.kb-next/`, and `.kb-next/memory/NOW.md`
   exist.
2. Run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`
3. Read only `.kb-next/memory/NOW.md`.
4. Run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py lookup --query "status atual" --json`
5. Report whether the project is ready for normal `vnext-session-start` plugin
   command use, and note the runtime Python command for shell sessions.
