---
description: Configure KB/Wiki vNext for an existing project.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Configure KB/Wiki vNext for an existing project.

Use this after activation when the operator wants to adjust vNext mode or
record a guided activation decision. Keep `.kb/` canonical.

1. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`
   first.
2. Inspect `.kb-next/kb-next.config.json` and
   `.kb-next/decisions/activation-decision.json` if present.
3. If the user has supplied guided answers, run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py activation-wizard --mode guided --answers '<json>' --json`
4. If the user only chooses a mode, run short mode with `kb-alone` or `kb-wiki`.
5. Do not publish `.kb-next` wiki drafts into `.kb/wiki/live`.
