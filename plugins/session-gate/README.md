# Session Gate Plugin

Thin session-boundary wrapper for Codex, Claude Code, and Claude Cowork
workspaces that may use KB/Wiki vNext, KB-lifecycle, CASE Companion, or a
combination of those surfaces.

Release-candidate version: `0.2.7`.

## Purpose

This plugin is an explicit compatibility fallback when session hooks are
disabled, unavailable, or not observable in the active client. It does not
replace KB/Wiki vNext, KB-lifecycle, or CASE Companion, and it does not add
mechanical enforcement. It only detects which canonical surfaces apply and
routes startup and closeout back to them.

## Design Rules

1. KB remains the durable memory layer.
2. CASE Companion remains the owner of CASE role boundaries and handoff canon.
3. `session-gate` must stay thin and must not duplicate large KB or CASE rules.
4. Trigger in Cowork is probabilistic, not guaranteed.
5. Compliance is instructional. Enforcement remains mechanical only where the
   canonical systems already provide it.
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

- Codex: `dist/agent-packages/session-gate-plugin-0.2.7.zip`
- Claude Code: `dist/agent-packages/session-gate-claude-plugin-0.2.7.zip`
- Claude Cowork: `dist/agent-packages/session-gate-cowork-plugin-0.2.7.zip`

The Codex CLI has no plugin-management command. Use the Codex app Plugins
settings with the public marketplace, or upload
`session-gate-plugin-0.2.7.zip` when file-based installation is available.
