# Session Gate Plugin

Thin session-boundary wrapper for Codex, Claude Code, and Claude Cowork
workspaces that may use KB/Wiki vNext, KB-lifecycle, or both.

Release-candidate version: `0.2.10`.

## Purpose

This plugin is an explicit compatibility fallback when session hooks are
disabled, unavailable, or not observable in the active client. It does not
replace KB/Wiki vNext or KB-lifecycle, and it does not add mechanical
enforcement. It only detects which canonical surfaces apply and
routes startup and closeout back to them.

## Design Rules

1. KB remains the durable memory layer.
2. `session-gate` must stay thin and must not duplicate large KB or vNext rules.
3. Trigger in Cowork is probabilistic, not guaranteed.
4. Compliance is instructional. Enforcement remains mechanical only where the
   canonical systems already provide it.
5. In a vNext workspace where the kb-wiki-vnext SessionStart hook text says
   it replaces `session-start`, the startup runs nothing and reads
   `.kb-next/memory/NOW.md` only when that text asks for it, and the closeout
   is the `vnext-session-end` close; curation runs in the weekly maintenance
   run, not at session end.
6. Distributed plugin/slash command files have explicit names (`gate-session-start` and
   `gate-session-end`) rather than generic `session-start` / `session-end`
   aliases.

## Contents

- Codex plugin manifest at `.codex-plugin/plugin.json`
- Claude plugin manifest at `.claude-plugin/plugin.json`
- Shared skill at `skills/session-gate/`
- Session-boundary commands at `commands/`
- Workspace detector at `scripts/detect_workspace.py`

## Distribution

- Codex: `dist/agent-packages/session-gate-plugin-0.2.10.zip`
- Claude Code: `dist/agent-packages/session-gate-claude-plugin-0.2.10.zip`
- Claude Cowork: `dist/agent-packages/session-gate-cowork-plugin-0.2.10.zip`

The Codex CLI manages plugins from the command line (checked on codex-cli
0.156.1). Add the public marketplace once, then install the plugin:

```bash
codex plugin marketplace add regismvargas/kb-factory
codex plugin add session-gate@kb-factory-tools
```

After a release, `codex plugin marketplace upgrade kb-factory-tools` refreshes
the marketplace snapshot. In the Codex app, the Plugins settings do the same,
or upload `session-gate-plugin-0.2.8.zip` when file-based installation is
available.
