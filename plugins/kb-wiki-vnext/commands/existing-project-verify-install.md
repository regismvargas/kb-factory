---
description: Verify KB/Wiki vNext installation in an existing project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in an existing project.

This command is read-only and suitable after install, activation, upgrade, or
rollback.

1. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
2. If a runtime was resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
3. If no runtime was resolved, the verification result is degraded and
   incomplete: report that the vNext runtime is not installed (the plugin does
   not currently bundle it — known packaging gap), and fall back to reading
   `.kb-next/memory/NOW.md` directly to confirm data presence. Skip step 5.
   Suggest installing or placing the runtime at `.kb-next/runtime/kb_next.py`
   (or running from the KB Factory authoring monorepo) to complete
   verification.
4. Read only `.kb-next/memory/NOW.md`.
5. If a runtime was resolved, run a deterministic lookup:
   `python <resolved-runtime-path> lookup --query "status atual" --json`
6. Confirm no `.kb/wiki/live` publication occurred and no direct `.kb/kb.db`
   edit was made by vNext.
7. Report package names and versions if plugin metadata is available.
