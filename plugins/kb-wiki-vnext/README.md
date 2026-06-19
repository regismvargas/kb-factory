# KB/Wiki vNext Plugin

Purpose: package the KB/Wiki vNext thin-memory harness separately from
classic `kb-lifecycle` and `session-gate`.

Audience: users installing the pilot, agents running vNext sessions, and
maintainers validating package shape before distribution.

> **Using it (start here).** This README covers packaging and validation. To
> *use* the plugin in a chat, see the [User Guide](../../docs/guide/index.md) (or
> the [No-code guide](../../docs/guide/no-code/index.md) if you're not a
> developer) and [Using KB Factory in a session](../../docs/agent-sessions.md).
> For what all three plugins do and how they combine, see
> [the plugins](../../docs/plugins.md).

Prerequisites:

- The target workspace has `.kb-next/` or is explicitly piloting vNext.
- The classic `.kb/` directory remains canonical durable memory.
- vNext development work has run the relevant `compliance-preflight`.

## Capabilities

- Starts sessions with the explicit vNext `vnext-session-start` plugin command
  when exposed, or the runtime Python `session-start` command in shells.
- Loads only `.kb-next/memory/NOW.md` by default.
- Uses `lookup` or `semantic-lookup` before opening broad memory surfaces.
- Reviews `.kb-next` evidence, manifests, proposals, and wiki drafts.
- Runs semantic hygiene proposal flows without direct `.kb/` mutation.
- Records packaging/release evidence in run artifacts.

## Boundaries

- `.kb/` is canonical.
- `.kb-next/` is proposal, manifest, draft, materialization, package, and
  operations evidence.
- The plugin must not publish vNext drafts to `.kb/wiki/live`.
- The plugin must not edit `.kb/kb.db` directly.
- HOT overflow governance starts with read-only `hygiene-audit`.
- `semantic-hygiene --write-proposals` writes only governed `.kb-next`
  proposal evidence.
- Only approved `demote_hot` and `resolve` proposals may apply through the
  classic runtime.

## Platform Contents

| Platform artifact | Manifest | Components |
|---|---|---|
| `kb-wiki-vnext-plugin-0.1.4.zip` | `.codex-plugin/plugin.json` plus `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/`, `commands/`, `hooks/` |
| `kb-wiki-vnext-claude-plugin-0.1.4.zip` | `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/`, `commands/`, `hooks/` |
| `kb-wiki-vnext-cowork-plugin-0.1.4.zip` | `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/`, `commands/`, `hooks/` |

The Claude Code and Cowork ZIPs use the same root-level plugin layout. They do
not contain an extra `kb-wiki-vnext/` wrapper directory.

After building, run `python tools/organize_agent_packages.py --mode current
--archive-legacy` to copy the current plugin ZIPs into
`dist/agent-packages/by-platform/<platform>/<version>/` and each platform's
`latest/` folder. Recognized non-current plugin ZIPs move to
`dist/agent-packages/legacy/<platform>/<version>/`. The flat current ZIPs remain
the canonical build output; the organized mirror is for manual install and hash
review.

## Verification

```powershell
python tools\build_agent_packages.py --scope kb
python tools\organize_agent_packages.py --mode current --check
python -m pytest -p no:cacheprovider tests\test_build_agent_packages.py -q
```

After installation, invoke the `vnext-session-start` plugin command when the
client exposes it, or run
`python core/versions/kb-wiki-vnext/runtime/kb_next.py session-start --json` in
a shell, and confirm it tells the agent to read only `.kb-next/memory/NOW.md`
by default. Existing and new project setup commands are also shipped under
explicit `existing-project-*` and `new-project-*` names.

## Troubleshooting

- If a Claude Code or Cowork package misses components, confirm `skills/`,
  `commands/`, and `hooks/` are at plugin root, not inside `.claude-plugin/`.
- If Codex rejects the manifest, confirm `.codex-plugin/plugin.json` omits
  unsupported `hooks` and references only companion files that exist.
- If the package appears to collide with another KB Factory plugin, rebuild
  with `--scope kb` and verify vNext commands use `vnext-session-*`,
  `existing-project-*`, and `new-project-*` names.

Related:

- `tools/build_agent_packages.py`
- `tests/test_build_agent_packages.py`
