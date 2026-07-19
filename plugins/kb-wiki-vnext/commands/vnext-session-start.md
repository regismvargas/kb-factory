---
description: Run KB/Wiki vNext session start for the current workspace.
allowed-tools: Read, Bash, Grep, Glob
---

Run KB/Wiki vNext session start for the current workspace.

Use this explicit command instead of a generic `/session-start` alias so
vNext, Session Gate, and classic KB lifecycle commands cannot collide.

1. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
2. If a runtime was resolved and shell access is available, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   This does not write canonical `.kb/`, but it appends session evidence to
   `.kb-next/operations.jsonl`.
3. If no runtime was resolved but `.kb-next/memory/NOW.md` exists, use the
   data-only fallback: read `.kb-next/memory/NOW.md` directly and treat it as
   authoritative. If `.kb/kb.py` exists, run classic
   `python .kb/kb.py lifecycle session-start --json` only to satisfy the
   lifecycle memory contract — ignore its `paths.now` pointer to the classic
   `.kb/memory/NOW.md`. Report that the vNext runtime is not installed
   (degraded mode).
4. Otherwise (no runtime resolved and no readable `.kb-next/memory/NOW.md`,
   including a partial or corrupt `.kb-next/`), stop and report that this is
   not a usable vNext workspace. Suggest classic
   `python .kb/kb.py lifecycle session-start --json` if `.kb/kb.py` exists,
   or `/kb-wiki-vnext:existing-project-activate-vnext` to adopt vNext.
5. Read only `.kb-next/memory/NOW.md` by default.
6. Use targeted lookup before opening broad memory surfaces.
7. If this session is planning, executing, reviewing, packaging, rolling out,
   or releasing vNext development before vNext is 100% developed, and a
   runtime was resolved in step 1, run:
   `python <resolved-runtime-path> compliance-preflight --work-type planning --json`
   with the closest work type. If no runtime was resolved, note that
   compliance-preflight is unavailable in this workspace.
8. If the session concerns HOT overflow or semantic memory hygiene, begin with
   read-only `python .kb/kb.py hygiene-audit --json`; use
   `semantic-hygiene --write-proposals` only when governed proposal evidence is
   explicitly needed.

Do not load `.kb/memory/HOT.md`, `.kb/memory/INDEX.md`, wiki pages, or
historical artifacts unless the current task requires them.
