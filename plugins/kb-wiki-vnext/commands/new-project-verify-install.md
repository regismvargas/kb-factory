---
description: Verify KB/Wiki vNext installation in a new project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in a new project.

This command is read-only after initial bootstrap.

1. Confirm `.kb/`, `.kb/kb.py`, `.kb-next/`, and `.kb-next/memory/NOW.md`
   exist.
2. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
3. If a runtime was resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
4. Read only `.kb-next/memory/NOW.md`.
5. If a runtime was resolved, run:
   `python <resolved-runtime-path> lookup --query "status atual" --json`
6. If no runtime was resolved, the verification result is DEGRADED/INCOMPLETE:
   report that the vNext runtime is not installed (the plugin does not
   currently bundle it), skip the `session-start` and `lookup` runtime checks,
   and rely on the direct read of `.kb-next/memory/NOW.md` from step 4 to
   confirm data presence. Suggest installing/placing the runtime at
   `.kb-next/runtime/kb_next.py` (or running from the KB Factory authoring
   monorepo) to complete verification.
7. Report whether the project is ready for normal `vnext-session-start` plugin
   command use, and note the resolved runtime Python command for shell
   sessions (or that no runtime resolved, in degraded mode).
