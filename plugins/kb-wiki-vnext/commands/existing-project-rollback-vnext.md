---
description: Roll back KB/Wiki vNext in an existing project.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Roll back KB/Wiki vNext in an existing project.

Use this when a vNext package, runtime, or command namespace change must be
reverted without changing canonical `.kb/` memory.

1. Reinstall the prior known-good ZIP or restore the prior checked-out runtime.
2. Do not delete or rewrite `.kb/`.
3. Preserve `.kb-next/` evidence unless the user explicitly approves archival
   or removal.
4. Invoke the `existing-project-verify-install` plugin command when the client
   exposes it; if working in shell, run the runtime verification steps from
   that command directly.
5. Report the restored version, retained evidence paths, and any manual follow-up.
