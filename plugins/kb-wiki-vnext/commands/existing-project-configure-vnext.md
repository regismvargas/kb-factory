---
description: Configure KB/Wiki vNext for an existing project.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Configure KB/Wiki vNext for an existing project.

Use this after activation when the operator wants to adjust vNext mode or
record a guided activation decision. Keep `.kb/` canonical.

1. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
2. If no runtime was resolved, stop and report that vNext configuration
   requires the vNext runtime, which this plugin does not currently bundle
   (known packaging gap). The guided wizard (`activation-wizard`) cannot run
   without it, and there is no classic fallback for configuration. Point the
   user to install/place the runtime at `.kb-next/runtime/kb_next.py`, run
   from the KB Factory authoring monorepo, or keep using the classic `.kb` KB.
3. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python <resolved-runtime-path> session-start --json`
   first (if `python` is not on PATH, retry with `py` or `python3`).
4. Inspect `.kb-next/kb-next.config.json` and
   `.kb-next/decisions/activation-decision.json` if present.
5. If the user has supplied guided answers, run:
   `python <resolved-runtime-path> activation-wizard --mode guided --answers '<json>' --json`
6. If the user only chooses a mode, run short mode with `kb-alone` or `kb-wiki`.
7. Do not publish `.kb-next` wiki drafts into `.kb/wiki/live`.
