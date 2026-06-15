---
description: Initialize a new project in KB-alone vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB-alone vNext mode.

Use this for new projects that need durable KB memory and vNext thin session
startup without activating wiki workflows.

1. Ensure `.kb/` exists, using the stand-alone bundle `classic-template/.kb/`
   if this is a fresh workspace.
2. Run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py activation-wizard --mode short --choice kb-alone --json`
3. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`.
   Read only `.kb-next/memory/NOW.md`.
4. Report that `.kb/` is canonical and `.kb-next/` is governed derived state.
