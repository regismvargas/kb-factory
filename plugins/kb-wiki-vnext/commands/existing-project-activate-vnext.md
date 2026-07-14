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
3. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
4. If no runtime was resolved, stop and report that vNext activation requires
   the vNext runtime, which this plugin does not currently bundle (known
   packaging gap). Do not attempt a classic fallback for activation. Ask the
   user to install or place the runtime at `.kb-next/runtime/kb_next.py`, run
   this command from the KB Factory authoring monorepo, or keep using the
   classic `.kb` KB.
5. Run one of:
   - `python <resolved-runtime-path> activation-wizard --mode short --choice kb-alone --json`
   - `python <resolved-runtime-path> activation-wizard --mode short --choice kb-wiki --json`
6. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
7. Report activation mode, generated paths, and any deferred user decision.
