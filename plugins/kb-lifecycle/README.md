# KB Lifecycle Plugin

Cross-tool distribution package for KB Factory memory lifecycle and derived wiki workflows.

Release-candidate version: `0.2.3`.

## Purpose

This plugin packages a CASE-compatible workflow for:

- Codex
- Claude Code
- Claude Cowork

The plugin is intentionally thin. It does not own durable memory. It points the agent back to the workspace `.kb/` runtime and its exported working set.

## Contents

- Codex plugin manifest at `.codex-plugin/plugin.json`
- Claude plugin manifest at `.claude-plugin/plugin.json`
- Shared skill at `skills/kb-wiki-maintainer/`
- Claude session-start hook at `hooks/hooks.json`
- Shared helper script at `scripts/session_start_context.py`

## CASE Compatibility Rules

1. `.kb/` remains the durable memory layer.
2. `NOW`, `HOT`, `INDEX`, and `python .kb/kb.py` remain the operating surface.
3. Plugin output must not become a second memory store.
4. Dispatch and export artifacts stay thin and disposable.

## Install Surfaces

### Codex

The Codex CLI has no `plugin` or `marketplace` subcommand. In the Codex app,
use the Plugins settings and the public `regismvargas/kb-factory` marketplace,
or upload `kb-lifecycle-plugin-0.2.3.zip` when file-based installation is
available. CLI-only users can copy `skills/kb-wiki-maintainer/` to
`~/.codex/skills/kb-wiki-maintainer/`.

Restarting Codex reloads the installed cache but does not fetch a newer source
by itself. Refresh or reinstall from the public marketplace, then verify the
reported source and version. Test with: `Use KB Lifecycle to start a KB session
and summarize .kb/memory/NOW.md.`

### Claude Code

- Use `.claude-plugin/plugin.json` as the Claude manifest in environments that support local plugin folders
- Include `hooks/hooks.json` and `scripts/session_start_context.py` with the plugin bundle when you want the session-start reminder
- Install the standalone skill into `~/.claude/skills/`
- Use the Claude plugin bundle when you want hooks and easier distribution
- The plugin ZIP is compatible as a Claude-style plugin artifact; the skill ZIP is also valid as a direct skill install.

### Claude Cowork

- Upload the plugin ZIP as a custom plugin
- Or use a GitHub-synced team marketplace that points at this repository
- The standalone skill ZIP is not the main Cowork install surface; prefer the plugin ZIP or marketplace.

## Packaging

Run:

```powershell
python tools/build_agent_packages.py --scope kb --include-standalone-skill
```

This builds:

- a Codex plugin ZIP with `.codex-plugin/` and Codex skill metadata;
- root-level Claude Code and Cowork plugin ZIPs without Codex-only metadata;
- a standalone `kb-wiki-maintainer` skill ZIP for direct skill installation.

By default the artifacts are saved under:

- `dist/agent-packages/kb-lifecycle-plugin-0.2.3.zip`
- `dist/agent-packages/kb-lifecycle-claude-plugin-0.2.3.zip`
- `dist/agent-packages/kb-lifecycle-cowork-plugin-0.2.3.zip`
- `dist/agent-packages/kb-wiki-maintainer-skill-0.2.3.zip`

The version in `.claude-plugin/plugin.json` is the package authority. Rebuilds
at the same version refresh source-controlled artifacts but do not force an
already installed client cache to update.
