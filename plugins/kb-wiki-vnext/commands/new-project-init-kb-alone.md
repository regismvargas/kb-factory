---
description: Initialize a new project in KB-alone vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB-alone vNext mode.

Use this for new projects that need durable KB memory and vNext thin session
startup without activating wiki workflows. Ask the user for the project title,
slug and initial domains if they are missing; never invent them.

1. Resolve a runtime you can RUN. Check these paths in order (Glob or a file
   existence check) and use the first that exists:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (the engine bundled in this
     plugin; Claude Code sets `CLAUDE_PLUGIN_ROOT` for plugin commands)
   - `~/.claude/plugins/**/kb-wiki-vnext/runtime/kb_next.py` and the Cowork/Codex
     plugin directories (glob fallback where `CLAUDE_PLUGIN_ROOT` is unset)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   - `.kb-next/runtime/kb_next.py` only as a last-resort source when no installed
     plugin or authoring runtime resolves. A self-bootstrap cannot upgrade it.
   If no runtime resolves, the plugin install is broken — report that and stop;
   do not ask the user to hand-place the runtime.
2. If `.kb/kb.py` is absent, install and initialize the classic KB:
   `python <resolved-runtime-path> --project-root . install-classic --name "<Project Title>" --slug <project-slug> --domains <a,b,c> --json`
   It copies the classic scaffold, renders the placeholders, prefixes record
   IDs with the slug and imports the seed. If it reports that no classic
   template was found, stop and ask the user to install
   `kb-lifecycle@kb-factory-tools` (or pass `--template <dir>`).
3. Install the runtime into the workspace:
   `python <resolved-runtime-path> --project-root . bootstrap --json`
   This writes `.kb-next/runtime/kb_next.py`.
4. Activate from the workspace runtime:
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-alone --json`
5. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python .kb-next/runtime/kb_next.py session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
6. Report that `.kb/` is canonical and `.kb-next/` is governed derived state.
