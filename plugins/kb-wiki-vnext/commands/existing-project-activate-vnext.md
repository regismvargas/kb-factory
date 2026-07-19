---
description: Activate KB/Wiki vNext in an existing project without overwriting classic KB.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Activate KB/Wiki vNext in an existing project without overwriting classic KB.

Use this command for workspaces that already have `.kb/` or other durable
project state. The default activation mode is `kb-alone` unless the user
explicitly asks for KB + Wiki.

1. Confirm `.kb/` exists and do not overwrite it.
2. If `.kb-next/kb-next.config.json` already exists, this project is already
   activated — route to `existing-project-configure-vnext` or
   `existing-project-upgrade-vnext` and stop. If `.kb-next/` exists but has no
   config or no `runtime/kb_next.py` (a partial or broken install), continue:
   the steps below repair it safely (`bootstrap` only writes `runtime/`, never
   config or memory).
3. Resolve a runtime you can RUN. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (the engine bundled in this
     plugin; Claude Code sets `CLAUDE_PLUGIN_ROOT` for plugin commands)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   - `.kb-next/runtime/kb_next.py` only as a last-resort source when no installed
     plugin or authoring runtime resolves. A self-bootstrap cannot upgrade it.
4. Install the runtime into the workspace so it is always available:
   `python <resolved-runtime-path> --project-root . bootstrap --json`
   This writes `.kb-next/runtime/kb_next.py` (resolution-ladder rung 1). If no
   runtime could be resolved at all, the plugin install is broken — report that
   and stop; do not ask the user to hand-place the runtime.
5. Run activation from the workspace runtime (`--choice kb-wiki` only if the
   user asked for KB + Wiki):
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-alone --json`
6. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python .kb-next/runtime/kb_next.py session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
7. Report activation mode, generated paths, and any deferred user decision.
