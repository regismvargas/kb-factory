---
description: Verify KB/Wiki vNext installation in an existing project.
allowed-tools: Read, Bash, Grep, Glob
---

Verify KB/Wiki vNext installation in an existing project.

This command does not mutate canonical `.kb/` and is suitable after install,
activation, upgrade, or rollback. Its `session-start` and `lookup` checks append
operational evidence to `.kb-next/operations.jsonl`.

1. Resolve the vNext runtime. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
2. If a runtime resolved, run:
   `python <resolved-runtime-path> session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
3. If no runtime resolved, report the verification as degraded and incomplete:
   neither the workspace runtime nor an installed plugin runtime was found.
   Read `.kb-next/memory/NOW.md` directly to confirm data presence, skip step 5,
   and recommend reinstalling/upgrading the vNext plugin. Do not ask the user
   to hand-place the runtime.
4. Read only `.kb-next/memory/NOW.md` by default.
5. If a runtime resolved, run a deterministic lookup:
   `python <resolved-runtime-path> lookup --facet status --query "status atual" --json`
6. Confirm no `.kb/wiki/live` publication occurred and no direct `.kb/kb.db`
   edit was made by vNext.
7. Report package names and versions if plugin metadata is available.
