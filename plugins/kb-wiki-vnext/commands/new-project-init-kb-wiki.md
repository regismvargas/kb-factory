---
description: Initialize a new project in KB + Wiki vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB + Wiki vNext mode.

Use this only when the user explicitly wants wiki workflows in addition to
durable KB memory. Wiki drafts remain governed vNext outputs unless separately
published through an approved flow.

1. Ensure `.kb/` exists, using the stand-alone bundle `classic-template/.kb/`
   if this is a fresh workspace.
2. Run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json`
3. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`.
   Read only `.kb-next/memory/NOW.md`.
4. Do not publish `.kb-next` wiki drafts into `.kb/wiki/live`.
