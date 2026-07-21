# KB Lifecycle Plugin

Cross-tool distribution package for KB Factory memory lifecycle and derived wiki workflows.

Release-candidate version: `0.3.0`.

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

- Preferred install surface: repo-local marketplace at `.agents/plugins/marketplace.json`
- Plugin location for this repository: `plugins/kb-lifecycle/`
- Marketplace entry should point to `./plugins/kb-lifecycle`
- Skill-only fallback: extract the standalone `kb-wiki-maintainer` artifact into `~/.codex/skills/` so the resulting folder is `~/.codex/skills/kb-wiki-maintainer/`
- Important: Codex should treat this plugin ZIP as a distributable source bundle, not the primary install surface. The normal Codex install path for this package is the marketplace entry plus the checked-out plugin folder.

With a Codex executable that exposes the plugin CLI, install or refresh the
stable marketplace package with:

```powershell
codex plugin marketplace upgrade kb-factory-tools --json
codex plugin add kb-lifecycle@kb-factory-tools --json
codex plugin list --marketplace kb-factory-tools --json
```

If the bare executable on `PATH` lacks these subcommands, qualify the Codex
Desktop bundled CLI or use the app/plugin UI.

Recommended repo-local setup:

1. Copy or extract the plugin files into `plugins/kb-lifecycle/`.
2. Add or keep this entry in `.agents/plugins/marketplace.json`:

```json
{
  "name": "kb-lifecycle",
  "source": {
    "source": "local",
    "path": "./plugins/kb-lifecycle"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

3. Reopen the workspace in Codex so the marketplace entry is picked up.
4. Test with a prompt such as `Use KB Lifecycle to run a maintenance pass on NOW, HOT, and the wiki.`

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

- `dist/agent-packages/kb-lifecycle-plugin-0.3.0.zip`
- `dist/agent-packages/kb-lifecycle-claude-plugin-0.3.0.zip`
- `dist/agent-packages/kb-lifecycle-cowork-plugin-0.3.0.zip`
- `dist/agent-packages/kb-wiki-maintainer-skill-0.3.0.zip`

The version in `.claude-plugin/plugin.json` is the package authority. Rebuilds
at the same version refresh source-controlled artifacts but do not force an
already installed client cache to update.
