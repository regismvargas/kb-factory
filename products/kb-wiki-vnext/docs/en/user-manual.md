# KB/Wiki vNext User Manual

## Purpose

Use KB/Wiki vNext to start a thin memory session, search project memory, prepare governed proposals, and review wiki drafts without making `.kb/` stop being the canonical memory layer.

## Audience

Project users who receive the plugin ZIP or stand-alone bundle from a maintainer.

## Prerequisites

- Python available as `python`.
- A project workspace with a `.kb/` folder created from the bundled classic template or an existing KB Factory workspace.
- One installed distribution channel: Codex plugin, Claude Code plugin, Claude Cowork plugin, or the stand-alone bundle.

## Steps

Choose the package that matches your client:

- Codex: `kb-wiki-vnext-plugin-0.1.9.zip`
- Claude Code: `kb-wiki-vnext-claude-plugin-0.1.9.zip`
- Claude Cowork: `kb-wiki-vnext-cowork-plugin-0.1.9.zip`
- Stand-alone: `kb-wiki-vnext-0.2.0-rc.2-standalone.zip`

The product, KB Lifecycle, plugin container, bundled runtime, Session Gate, and
marketplace have separate version lines: `0.2.0-rc.2`, `0.2.3`, `0.1.9`,
`0.1.7`, `0.2.7`, and `0.3.8`, respectively. Record all applicable values
during install or upgrade.

For a plugin installation, use `existing-project-activate-vnext` to resolve the
bundled engine and bootstrap the workspace. The equivalent shell flow is:

```powershell
python <installed-plugin-runtime> --project-root . bootstrap --json
python .\.kb-next\runtime\kb_next.py session-start --json
python .\.kb-next\runtime\kb_next.py lookup --facet status --query "current status" --json
```

Resolve `<installed-plugin-runtime>` from `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`
or the installed Codex, Cowork, or Claude plugin path. Do not assume the KB
Factory authoring path exists in a consumer project.

From the repository layout:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py session-start --json
python core\versions\kb-wiki-vnext\runtime\kb_next.py lookup --facet status --query "current status" --json
```

From the stand-alone bundle layout:

```powershell
python runtime\kb_next.py session-start --json
python runtime\kb_next.py lookup --facet status --query "current status" --json
```

For a persistent workspace runtime, run the stand-alone engine once with
`--project-root <workspace> bootstrap --json`, then use
`<workspace>/.kb-next/runtime/kb_next.py` for normal sessions.

Use `proposal-apply` only when you intentionally approve a prepared proposal. Do not edit `.kb/kb.db` directly.

Installed plugin workflows use explicit logical names. Claude Code invokes
`/kb-wiki-vnext:vnext-session-start`; Codex uses the embedded
`kb-wiki-vnext` skill as its primary surface; Cowork uses the namespaced action
actually exposed by its UI or the skill in natural language. The logical
`existing-project-*` and `new-project-*` families cover legacy and fresh
workspaces. Do not assume a bare slash command works across clients.

For runtime examples and safe conversation patterns, use the [detailed usage guide](usage-guide.md).

## Verification

The runtime `session-start` should report the active mode and point you to
`.kb-next/memory/NOW.md`. The logical plugin basename is
`vnext-session-start`; invocation is client-specific. `lookup`
may return no records in a new workspace and appends operational evidence to
`.kb-next/operations.jsonl`, but it must not change canonical `.kb/` or publish
`.kb/wiki/live`.

## Troubleshooting

If the runtime cannot find `.kb/kb.py`, copy `classic-template/.kb/` from the
stand-alone bundle into a new project as `.kb/`; never overwrite an existing
`.kb/`. If `.kb-next/runtime/kb_next.py` is missing, bootstrap it from the
installed plugin or stand-alone engine. If Cowork does not start automatically,
use the namespaced action exposed by its plugin UI, invoke the skill in natural
language, or run the runtime fallback.

## Related

- [Admin installation](admin-installation.md)
- [Detailed usage guide](usage-guide.md)
- [Command reference](command-reference.md)
- [Upgrade and rollback](upgrade-rollback.md)
- [Architecture](architecture.md)
