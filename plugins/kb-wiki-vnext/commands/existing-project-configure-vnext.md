---
description: Configure KB/Wiki vNext for an existing project.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Configure KB/Wiki vNext for an existing project.

Use this after activation when the operator wants to adjust vNext mode or
record a guided activation decision. Keep `.kb/` canonical.

1. Resolve a vNext runtime you can run. Check these paths in order (Glob or a
   file existence check) and use the first that exists:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   - `.kb-next/runtime/kb_next.py` only as a last-resort source. If this path is
     the source, `bootstrap` is a self-check, not an upgrade; report that no
     newer installed source runtime was available.
2. If no runtime was resolved, report a broken or incomplete plugin install and
   stop. Do not ask the user to hand-place the runtime.
3. Install or refresh the workspace runtime:
   `python <resolved-runtime-path> --project-root . bootstrap --json`
   This writes only `.kb-next/runtime/kb_next.py`.
4. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run:
   `python .kb-next/runtime/kb_next.py session-start --json`
   If `python` is not on PATH, retry with `py` or `python3`. This does not write
   canonical `.kb/`, but it appends session evidence to
   `.kb-next/operations.jsonl`.
5. Inspect `.kb-next/kb-next.config.json` and
   `.kb-next/decisions/activation-decision.json` if present.
6. If the user supplied guided answers, run:
   `python .kb-next/runtime/kb_next.py activation-wizard --mode guided --answers '<json>' --json`
7. If the user only chooses a mode, run short mode with `kb-alone` or `kb-wiki`.
8. Do not publish `.kb-next` wiki drafts into `.kb/wiki/live`.
