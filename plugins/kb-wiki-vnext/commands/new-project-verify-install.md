---
description: Verify KB/Wiki vNext installation in a new project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in a new project.

This command does not mutate canonical `.kb/` after initial bootstrap. Its
`session-start` and `lookup` checks append operational evidence to
`.kb-next/operations.jsonl`.

1. Confirm `.kb/`, `.kb/kb.py`, `.kb-next/`, and `.kb-next/memory/NOW.md`
   exist.
2. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
3. If a runtime resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
4. Read only `.kb-next/memory/NOW.md` by default.
5. If a runtime resolved, run:
   `python <resolved-runtime-path> lookup --facet status --query "status atual" --json`
6. If no runtime resolved, report the verification as degraded and incomplete:
   neither the workspace runtime nor an installed plugin runtime was found.
   Skip the runtime checks and use the direct `NOW.md` read from step 4 to
   confirm data presence. Recommend reinstalling/upgrading the vNext plugin;
   do not ask the user to hand-place the runtime.
7. Report whether the project is ready for normal plugin/slash `vnext-session-start`
   use and
   the resolved runtime command for shell sessions, or report degraded mode.
