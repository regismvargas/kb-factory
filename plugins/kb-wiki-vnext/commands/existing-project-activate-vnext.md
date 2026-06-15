---
description: Activate KB/Wiki vNext in an existing project without overwriting classic KB.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Activate KB/Wiki vNext in an existing project without overwriting classic KB.

Use this command for workspaces that already have `.kb/` or other durable
project state. The default activation mode is `kb-alone` unless the user
explicitly asks for KB + Wiki.

1. Confirm `.kb/` exists and do not overwrite it.
2. If `.kb-next/` already exists, stop and route to
   `existing-project-configure-vnext` or `existing-project-upgrade-vnext`.
3. Run one of:
   - `python core/versions/kb-wiki-vnext/runtime/kb_next.py activation-wizard --mode short --choice kb-alone --json`
   - `python core/versions/kb-wiki-vnext/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json`
4. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`.
   Read only `.kb-next/memory/NOW.md`.
5. Report activation mode, generated paths, and any deferred user decision.
