---
description: Roll back KB/Wiki vNext without changing canonical KB.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Roll back KB/Wiki vNext in an existing project.

Use this when a vNext package, runtime, or command namespace change must be
reverted without changing canonical `.kb/` memory.

1. Record the current plugin and workspace-runtime versions.
2. Reinstall the prior known-good platform artifact.
3. Resolve the RESTORED source runtime from `${CLAUDE_PLUGIN_ROOT}` or the
   restored client plugin directory. Do not use the current
   `.kb-next/runtime/kb_next.py` as the rollback source.
4. If no restored source runtime resolves, stop and report an incomplete
   rollback artifact.
5. Restore the workspace runtime:
   `python <restored-source-runtime> --project-root . bootstrap --json`
   Confirm the expected prior runtime version and matching `source_sha256` /
   `installed_sha256`; `action: self` is not rollback proof.
6. Do not delete or rewrite `.kb/`. Preserve `.kb-next/` evidence unless the
   user explicitly approves archival or removal.
7. Run `existing-project-verify-install` and report the restored version,
   bootstrap action, retained evidence paths, and follow-up items.
