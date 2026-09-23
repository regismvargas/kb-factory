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
   If the classic wiki settings must also return to their pre-upgrade values,
   read the last `classic-config-sync` entry in `.kb-next/operations.jsonl`:
   each `changes[]` item carries the key path and its previous (`from`)
   value. Restore them only with the user's approval, then run
   `python .kb/kb.py wiki-check --json` to confirm the resulting state.
7. Run `existing-project-verify-install` and report the restored version,
   bootstrap action, retained evidence paths, and follow-up items.
