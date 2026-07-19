# KB/Wiki vNext Plugin

Purpose: package the KB/Wiki vNext thin-memory harness separately from
classic `kb-lifecycle`, `session-gate`, and `case-companion`.

Release-candidate identities: plugin `0.1.9`, bundled runtime `0.1.7`, product
`0.2.0-rc.2`, Session Gate companion `0.2.7`, and marketplace `0.3.8`.

Audience: users installing the pilot, agents running vNext sessions, and
maintainers validating package shape before distribution.

Prerequisites:

- The target workspace has `.kb-next/` or is explicitly piloting vNext.
- The classic `.kb/` directory remains canonical durable memory.
- vNext development work has run the relevant `compliance-preflight`.

## Capabilities

- Starts sessions with the explicit vNext `vnext-session-start` command.
- Loads only `.kb-next/memory/NOW.md` by default.
- Uses `lookup` or `semantic-lookup` before opening broad memory surfaces.
- Reviews `.kb-next` evidence, manifests, proposals, and wiki drafts.
- Runs semantic hygiene proposal flows without direct `.kb/` mutation.
- Records packaging/release evidence in CASE-compatible run artifacts.

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
| `kb-wiki-vnext-plugin-0.1.9.zip` | `.codex-plugin/plugin.json` plus `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/` with Codex UI metadata, `commands/`, `hooks/`, `runtime/` |
| `kb-wiki-vnext-claude-plugin-0.1.9.zip` | `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/`, `commands/`, `hooks/`, `runtime/` |
| `kb-wiki-vnext-cowork-plugin-0.1.9.zip` | `.claude-plugin/plugin.json` | `AGENTS.md`, `skills/`, `commands/`, `hooks/`, `runtime/` |

The Claude Code and Cowork ZIPs use the same root-level plugin layout. They do
not contain an extra `kb-wiki-vnext/` wrapper directory.

## Verification

```powershell
python tools\build_agent_packages.py --scope vnext
python -m pytest -p no:cacheprovider tests\test_build_agent_packages.py -q
```

After installation, invoke the client-specific plugin/slash or skill-based
`vnext-session-start` surface
and confirm it tells the agent to read only `.kb-next/memory/NOW.md` by
default. Claude Code uses `/kb-wiki-vnext:vnext-session-start`; Codex uses the
embedded skill; Cowork uses the action exposed by its UI or the skill in
natural language. Existing and new project setup commands ship under explicit
`existing-project-*` and `new-project-*` names.

The Codex CLI has no plugin-management command. Use the Codex app Plugins
settings with the public marketplace, or upload
`kb-wiki-vnext-plugin-0.1.9.zip` when the app exposes file-based installation.
For a skill-only fallback, copy `skills/kb-wiki-vnext/` into
`~/.codex/skills/kb-wiki-vnext/`.

## Troubleshooting

- If a Claude Code or Cowork package misses components, confirm `skills/`,
  `commands/`, and `hooks/` are at plugin root, not inside `.claude-plugin/`.
- If Codex rejects the manifest, confirm `.codex-plugin/plugin.json` omits
  unsupported `hooks` and references only companion files that exist.
- If the package appears to collide with another KB Factory plugin, rebuild
  with `--scope vnext` and verify vNext commands use `vnext-session-*`,
  `existing-project-*`, and `new-project-*` names.

Related:

- `docs/installation.md`
- `products/kb-wiki-vnext/docs/en/admin-installation.md`
- `products/kb-wiki-vnext/docs/pt-BR/admin-installation.md`
- `tools/build_agent_packages.py`
- `tests/test_build_agent_packages.py`
