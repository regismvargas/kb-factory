---
description: Initialize a new project in KB-alone vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB-alone vNext mode.

Use this for new projects that need durable KB memory and vNext thin session
startup without activating wiki workflows.

1. Ensure `.kb/` exists, using the stand-alone bundle `classic-template/.kb/`
   if this is a fresh workspace.
2. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
3. If no runtime was resolved, stop and report that vNext activation requires
   the vNext runtime, which this plugin does not currently bundle (known
   packaging gap). Do not attempt a classic fallback for activation. Point the
   user to install or place the runtime at `.kb-next/runtime/kb_next.py` (or
   run this command from the KB Factory authoring monorepo), or to keep using
   the classic `.kb` KB.
4. Run:
   `python <resolved-runtime-path> activation-wizard --mode short --choice kb-alone --json`
5. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
6. Report that `.kb/` is canonical and `.kb-next/` is governed derived state.
