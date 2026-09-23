---
description: Initialize a new project in KB + Wiki vNext mode.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Initialize a new project in KB + Wiki vNext mode.

Use this only when the user explicitly wants wiki workflows in addition to
durable KB memory. Ask the user for the project title, slug and initial
domains if they are missing; never invent them.

KB + Wiki has two layers and this command turns both on:
- the classic derived wiki in `.kb/wiki/live`, published by the classic
  runtime from records (hygiene gates apply: page confidence >= 0.8, research
  syntheses need two sources);
- the vNext drafts in `.kb-next/wiki/`, written only through
  `wiki-synthesis-plan` + `wiki-draft-review` (see `vnext-wiki-drafts`).

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
   If it reports that no classic template was found, stop and ask the user to
   install `kb-lifecycle@kb-factory-tools` (or pass `--template <dir>`).
3. Install the runtime into the workspace:
   `python <resolved-runtime-path> --project-root . bootstrap --json`
   This writes `.kb-next/runtime/kb_next.py`.
4. Activate from the workspace runtime:
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json`
   This also enables the classic wiki in `.kb/kb.config.json` (`wiki.enabled`
   and `run_wiki_sync` on record-filed, source-ingest, session-end and
   scheduled-maintenance), runs the initial classic `wiki-sync`, and records
   both steps in `.kb-next/operations.jsonl`. Confirm that
   `classic_config_sync.action` is `updated` or `unchanged` and that
   `classic_wiki_sync.action` is `synced`.
5. Verify the wiki is on: `python .kb/kb.py wiki-check --json` must report a
   `wiki_state` other than `off`. `publication.held_back` lists pages kept back
   by hygiene gates and why.
6. From now on no manual sync is needed: `create`, `file`, `supersede`,
   `resolve`, `ingest` and `lifecycle session-end` refresh `.kb/wiki/live`.
7. Invoke the `vnext-session-start` plugin command when the client exposes it;
   in a shell run
   `python .kb-next/runtime/kb_next.py session-start --json`
   (if `python` is not on PATH, retry with `py` or `python3`).
   Read only `.kb-next/memory/NOW.md`.
8. vNext drafts materialize only into `.kb-next/wiki/{machine,human}` through
   `wiki-draft-review --materialize`. Never copy them into `.kb/wiki/live`,
   which the classic runtime generates from records.
