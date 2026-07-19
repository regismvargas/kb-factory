---
description: Initialize a new project in KB + Wiki vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB + Wiki vNext mode.

Use this only when the user explicitly wants wiki workflows in addition to
durable KB memory. Wiki drafts remain governed vNext outputs unless separately
published through an approved flow.

1. Ensure `.kb/` exists, using the stand-alone bundle `classic-template/.kb/`
   if this is a fresh workspace.
2. Resolve a runtime you can RUN. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (the engine bundled in this
     plugin; Claude Code sets `CLAUDE_PLUGIN_ROOT` for plugin commands)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   - `.kb-next/runtime/kb_next.py` only as a last-resort source when no installed
     plugin or authoring runtime resolves. A self-bootstrap cannot upgrade it.
3. Install the runtime into the workspace:
   `python <resolved-runtime-path> --project-root . bootstrap --json`
   This writes `.kb-next/runtime/kb_next.py`. If no runtime could be resolved,
   the plugin install is broken — report that and stop; do not ask the user to
   hand-place the runtime.
4. Activate from the workspace runtime:
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json`
5. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python .kb-next/runtime/kb_next.py session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
6. Do not publish `.kb-next` wiki drafts into `.kb/wiki/live`.
