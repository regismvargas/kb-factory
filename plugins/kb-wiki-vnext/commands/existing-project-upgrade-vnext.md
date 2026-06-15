---
description: Upgrade KB/Wiki vNext in an existing project.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Upgrade KB/Wiki vNext in an existing project.

Use this when replacing an installed vNext package or runtime while preserving
classic `.kb/` as canonical memory.

1. Record the current package/runtime version and keep the previous ZIP or
   checkout available for rollback.
2. Install the new platform artifact for Codex, Claude Code, or Claude Cowork.
3. Do not overwrite `.kb/`; update only the vNext runtime/plugin layer.
4. Invoke the `existing-project-verify-install` plugin command when the client
   exposes it; if working in shell, run the runtime verification steps from
   that command directly.
5. Report the old version, new version, ZIP name, and verification result.
