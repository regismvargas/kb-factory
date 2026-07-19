# KB/Wiki vNext Admin Installation And Distribution

## Purpose

Give admins a repeatable way to distribute KB/Wiki vNext to controlled projects without exposing workbench history as the primary onboarding path.

## Audience

Workspace admins, technical leads, and maintainers who install the package for others.

## Prerequisites

- A clean release artifact built from this repository.
- Access to the target client: Codex, Claude Code, Claude Cowork, or a Python-capable workspace.
- The target workspace owner understands that `.kb/` remains canonical and `.kb-next/` is the vNext layer.
- Release identity records product `0.2.0-rc.2`, KB Lifecycle `0.2.3`, plugin
  `0.1.9`, bundled runtime `0.1.7`, Session Gate `0.2.7`, and marketplace
  `0.3.8` separately.

## Steps

Build all affected KB plugin distributables and the stand-alone bundle:

```powershell
python tools\build_agent_packages.py --scope kb
python tools\build_vnext_standalone.py --version 0.2.0-rc.2
```

Validate the product before sharing:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip
```

Distribute only the artifact that matches the recipient:

- Codex plugin users receive the Codex plugin ZIP.
- Claude Code users receive the Claude Code plugin ZIP.
- Claude Cowork users receive the Cowork ZIP and explicit
  `vnext-session-start` manual startup instructions.
- Session Gate users receive the matching `session-gate-*-0.2.7.zip` artifact
  and use `/gate-session-start` / `/gate-session-end` in clients that expose
  slash commands.
- Admins bootstrapping a fresh workspace receive the stand-alone bundle.

The Codex CLI has no plugin-management command. In the Codex app, use the
Plugins settings with the public `regismvargas/kb-factory` marketplace or
upload `kb-wiki-vnext-plugin-0.1.9.zip` when file-based installation is
available. Restarting alone does not fetch a newer marketplace version.

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
bundle as `<installed-plugin-runtime>`. Never overwrite an existing
`<workspace>/.kb/` with `classic-template/.kb/`.

## Verification

Confirm the archive contains `runtime/kb_next.py`; bootstrap reports the
expected runtime version and equal `source_sha256` / `installed_sha256`; the
recipient can invoke the client-specific vNext startup surface, read
`.kb-next/memory/NOW.md`, and run the installed runtime with
`lookup --facet status`. The runtime's start and lookup operations may append
`.kb-next/operations.jsonl`, but installation and
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
