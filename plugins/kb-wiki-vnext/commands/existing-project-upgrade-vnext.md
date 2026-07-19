---
description: Upgrade KB/Wiki vNext in an existing project without changing canonical KB.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Upgrade KB/Wiki vNext in an existing project.

Use this when replacing an installed vNext package or runtime while preserving
classic `.kb/` as canonical memory.

1. Record the current plugin and `.kb-next/runtime/kb_next.py` versions. Keep the
   previous ZIP available for rollback.
2. Install the new platform artifact for Codex, Claude Code, or Claude Cowork.
3. Resolve the NEW source runtime without using the existing workspace runtime:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` for the newly installed plugin;
   - otherwise the newly installed client plugin directory matching
     `**/kb-wiki-vnext/runtime/kb_next.py`;
   - in the KB Factory authoring monorepo only,
     `core/versions/kb-wiki-vnext/runtime/kb_next.py`.
4. If no new source runtime resolves, stop and report a broken/incomplete new
   artifact. Do not claim upgrade success and do not hand-place a runtime.
5. Update only the workspace vNext runtime:
   `python <new-source-runtime> --project-root . bootstrap --json`
   Require an `action` of `created`, `updated`, or `exists` with the expected
   new runtime version, and require `source_sha256` to equal
   `installed_sha256`. An `action` of `self` is not upgrade proof.
6. Do not overwrite `.kb/`. Run `existing-project-verify-install` using the
   refreshed `.kb-next/runtime/kb_next.py`.
7. Report old/new versions, ZIP name, bootstrap action, and verification result.
