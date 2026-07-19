---
description: Close a KB/Wiki vNext session with governed operational evidence.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Close a KB/Wiki vNext session by recording only useful operational evidence.

Use this explicit command instead of a generic `/session-end` alias so vNext,
Session Gate, and classic KB lifecycle commands cannot collide.

1. Summarize vNext manifests, proposals, package checks, tests, or pilot
   evidence touched in the session.
2. Do not write durable memory unless the user approved canonical KB changes.
3. If a canonical KB update is approved, use `.kb/kb.py` or an already approved
   `proposal-apply` flow.
