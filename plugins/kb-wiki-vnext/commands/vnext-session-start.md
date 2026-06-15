---
description: Run KB/Wiki vNext session start for the current workspace.
allowed-tools: Read, Bash, Grep, Glob
---

Run KB/Wiki vNext session start for the current workspace.

Use this explicit command instead of a generic `/session-start` alias so
vNext, Session Gate, and classic KB lifecycle commands cannot collide.

1. If shell access is available, run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json`
2. Read only `.kb-next/memory/NOW.md` by default.
3. Use targeted lookup before opening broad memory surfaces.
4. If this session is planning, executing, reviewing, packaging, rolling out,
   or releasing vNext development before vNext is 100% developed, run:
   `python core/versions/kb-wiki-vnext/runtime/kb_next.py compliance-preflight --work-type planning --json`
   with the closest work type.
5. If the session concerns HOT overflow or semantic memory hygiene, begin with
   read-only `python .kb/kb.py hygiene-audit --json`; use
   `semantic-hygiene --write-proposals` only when governed proposal evidence is
   explicitly needed.

Do not load `.kb/memory/HOT.md`, `.kb/memory/INDEX.md`, wiki pages, or
historical artifacts unless the current task requires them.
