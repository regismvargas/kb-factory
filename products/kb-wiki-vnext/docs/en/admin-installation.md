# KB/Wiki vNext Admin Installation And Distribution

## Purpose

Give admins a repeatable way to distribute KB/Wiki vNext to controlled projects without exposing workbench history as the primary onboarding path.

## Audience

Workspace admins, technical leads, and maintainers who install the package for others.

## Prerequisites

- A clean release artifact built from this repository.
- Access to the target client: Codex, Claude Code, Claude Cowork, or a Python-capable workspace.
- The target workspace owner understands that `.kb/` remains canonical and `.kb-next/` is the vNext layer.
- Release identity records product `0.2.0-rc.8`, KB Lifecycle `0.2.8`, plugin
  `0.2.4`, bundled runtime `0.2.4`, Session Gate `0.2.10`, and marketplace
  `0.3.15` separately.

## Steps

Build all affected KB plugin distributables and the stand-alone bundle:

```powershell
python tools\build_agent_packages.py --scope kb
python tools\build_vnext_standalone.py --version 0.2.0-rc.8
```

Validate the product before sharing:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.8-standalone.zip
```

Distribute only the artifact that matches the recipient:

- Codex plugin users receive the Codex plugin ZIP.
- Claude Code users receive the Claude Code plugin ZIP.
- Claude Cowork users receive the Cowork ZIP and explicit
  `vnext-session-start` manual startup instructions.
- Session Gate users receive the matching `session-gate-*-0.2.10.zip` artifact
  and use `/gate-session-start` / `/gate-session-end` in clients that expose
  slash commands.
- Admins bootstrapping a fresh workspace receive the stand-alone bundle.
- Memory curation no longer runs at session end. Schedule one weekly agent
  session per project (a Claude Code, Cowork or Codex scheduled task) that
  follows the Curation section of the kb-wiki-vnext skill; without it no
  curation runs.

The Codex CLI manages plugins from the command line (checked on codex-cli
0.156.1). Add the public marketplace once, then install the plugin:

```powershell
codex plugin marketplace add regismvargas/kb-factory
codex plugin add kb-wiki-vnext@kb-factory-tools
```

Install `session-gate@kb-factory-tools` the same way where Session Gate is
distributed. After a release, `codex plugin marketplace upgrade kb-factory-tools`
refreshes the marketplace snapshot. In the Codex app, the Plugins settings do
the same, or upload `kb-wiki-vnext-plugin-0.2.1.zip` when file-based
installation is available. Restarting alone does not fetch a newer marketplace
version.

Every vNext plugin ZIP must contain `runtime/kb_next.py` at archive root. Do
not distribute an artifact that contains only commands referring to a bundled
engine but omits that file.

For a plugin consumer workspace, resolve the engine from
`${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` or the installed client-plugin path,
then run:

```powershell
python <installed-plugin-runtime> --project-root <workspace> bootstrap --json
```

For stand-alone distribution, use `runtime/kb_next.py` from the unpacked
bundle as `<installed-plugin-runtime>`. For a new workspace, run
`python <installed-plugin-runtime> --project-root <workspace> install-classic --name "<Title>" --slug <slug> --domains <a,b> --json`;
it copies the bundle's `classic-template/.kb/` (or the kb-lifecycle plugin
scaffold) and runs classic `init`. It refuses an existing `<workspace>/.kb/`.

## Verification

Confirm the archive contains `runtime/kb_next.py`; bootstrap reports the
expected runtime version and equal `source_sha256` / `installed_sha256`; the
recipient can invoke the client-specific vNext startup surface, read
`.kb-next/memory/NOW.md`, and run the installed runtime with
`lookup --facet status`. The runtime's start and lookup operations append read
telemetry to the git-ignored `.kb-next/telemetry/events.jsonl`, but `bootstrap` and
verification must not alter canonical `.kb/` or publish `.kb/wiki/live`. For
Session Gate, confirm the client-specific Session Gate startup surface detects `.kb-next/` before falling
back to classic `.kb/`.

## Troubleshooting

If a user installs the wrong ZIP, remove that client package using the client
UI or package manager and install the matching package. If a plugin ZIP lacks
`runtime/kb_next.py`, or the stand-alone bundle lacks docs or the classic
template, block distribution and rebuild from source instead of hand-assembling
files.

## Related

- [User manual](user-manual.md)
- [Command reference](command-reference.md)
- [Maintainer release](maintainer-release.md)
- [Troubleshooting](troubleshooting.md)
