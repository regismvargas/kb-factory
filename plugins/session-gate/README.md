# Session Gate Plugin

Thin session-boundary wrapper for Cowork workspaces that may use KB/Wiki
vNext, KB-lifecycle, a companion workflow plugin, or a combination of those
surfaces.

> **Using it (start here).** To *use* KB Factory in a chat, see the
> [User Guide](../../docs/guide/index.md) (or the
> [No-code guide](../../docs/guide/no-code/index.md) for non-developers) and
> [Using KB Factory in a session](../../docs/agent-sessions.md). For how
> `session-gate` fits with the other plugins, see
> [the plugins](../../docs/plugins.md).

## Purpose

This plugin is an operational workaround for Cowork's missing automatic plugin
hooks. It does not replace KB/Wiki vNext, KB-lifecycle, or a companion workflow
plugin, and it does not add mechanical enforcement. It only detects which
canonical surfaces apply and routes startup and closeout back to them.

## Design Rules

1. KB remains the durable memory layer.
2. The companion workflow plugin remains the owner of its role boundaries and
   handoff canon.
3. `session-gate` must stay thin and must not duplicate large KB or workflow
   rules.
4. Trigger in Cowork is probabilistic, not guaranteed.
5. Compliance is instructional. Enforcement remains mechanical only where the
   canonical systems already provide it.
6. Distributed plugin/slash commands use explicit names
   (`gate-session-start` and `gate-session-end`) rather than generic
   `session-start` / `session-end` aliases.

## Contents

- Codex plugin manifest at `.codex-plugin/plugin.json`
- Claude plugin manifest at `.claude-plugin/plugin.json`
- Shared skill at `skills/session-gate/`
- Session-boundary commands at `commands/`
- Workspace detector at `scripts/detect_workspace.py`
