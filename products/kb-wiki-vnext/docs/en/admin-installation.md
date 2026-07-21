# KB/Wiki vNext Admin Installation And Distribution

## Purpose

Give admins a repeatable way to distribute KB/Wiki vNext to controlled projects without exposing workbench history as the primary onboarding path.

## Audience

Workspace admins, technical leads, and maintainers who install the package for others.

## Prerequisites

- A clean release artifact built from this repository.
- Access to the target client: Codex, Claude Code, Claude Cowork, or a Python-capable workspace.
- The target workspace owner understands that `.kb/` remains canonical and `.kb-next/` is the vNext layer.
- Release identity records release, KB Lifecycle, vNext, and runtime `0.3.0`,
  plus Session Gate `0.2.7`. Marketplace entries have no duplicated version;
  plugin manifests define update identity.

## Steps

Build all affected KB plugin distributables and the stand-alone bundle:

```powershell
python tools\build_agent_packages.py --scope kb
python tools\build_vnext_standalone.py --version 0.3.0
```

Validate the product before sharing:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip
```

Distribute only the artifact that matches the recipient:

- Codex plugin users receive the Codex plugin ZIP.
- Claude Code users receive the Claude Code plugin ZIP.
- Claude Cowork users receive the Cowork ZIP and explicit plugin action
  `vnext-session-start` manual startup instructions.
- Session Gate users receive the matching `session-gate-*-0.2.7.zip` artifact
  and use the plugin actions `gate-session-start` / `gate-session-end`.
- Admins bootstrapping a fresh workspace receive the stand-alone bundle.

For Codex marketplace installation, first select an executable that exposes
the plugin CLI, then run:

```powershell
codex plugin marketplace upgrade kb-factory-tools --json
codex plugin add kb-wiki-vnext@kb-factory-tools --json
codex plugin list --marketplace kb-factory-tools --json
```

If an older bare `codex` lacks those commands, use the Codex Desktop bundled
CLI or the app/plugin UI; do not treat the stale executable as the product
capability boundary.

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
`.kb-next/memory/NOW.md`, and run `python <installed-plugin-runtime> --project-root <workspace> lookup --facet status`.
The runtime commands `python <installed-plugin-runtime> --project-root <workspace> session-start` and
`python <installed-plugin-runtime> --project-root <workspace> lookup` may append `.kb-next/operations.jsonl`, but installation and
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
