# KB/Wiki vNext Troubleshooting

## Purpose

Provide first-response diagnostics for install, runtime, packaging, and rollback problems.

## Audience

Users, admins, and maintainers supporting controlled deployments.

## Prerequisites

- Know which artifact was installed.
- Keep the failing workspace unchanged until basic diagnostics are captured.
- Do not run destructive cleanup commands while diagnosing.

## Common Checks

Resolve the runtime in this order: workspace
`.kb-next/runtime/kb_next.py`, active plugin
`${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`, installed client-plugin path,
stand-alone `runtime/kb_next.py`, then the KB Factory authoring path. Confirm
runtime help:

```powershell
python <resolved-runtime-path> --help
```

If the workspace runtime is missing, bootstrap from the plugin or stand-alone
artifact, then confirm session startup:

```powershell
python <artifact-runtime-path> --project-root . bootstrap --json
python .\.kb-next\runtime\kb_next.py session-start --json
```

Confirm product package:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.7-standalone.zip
```

For runtime examples and safe conversation prompts, see the [detailed usage guide](usage-guide.md).

## Verification

A healthy workspace can run the plugin `vnext-session-start` command or the
runtime `session-start`, read `.kb-next/memory/NOW.md`, and complete `lookup`
or default `semantic-hygiene` without changing `.kb/kb.db`. `lookup` and
`session-start` append read telemetry to `.kb-next/telemetry/events.jsonl`;
default `semantic-hygiene` writes nothing. Session Gate installs should expose
`gate-session-start` and route `.kb-next/` before classic `.kb/`.

## Troubleshooting

If `.kb/kb.py` is missing in a new project, run the runtime
`install-classic --name <title> --slug <slug> --domains <a,b>`, which finds
the stand-alone `classic-template/.kb/` or the kb-lifecycle scaffold; it never
overwrites an existing `.kb/`. If `wiki-check` reports `off` after a KB + Wiki
activation, re-run `activation-wizard --choice kb-wiki` to sync
`.kb/kb.config.json`. If plugin install
fails, confirm the package matches the platform, contains `runtime/kb_next.py`,
and omits generic `session-start` / `session-end` command files. If bootstrap
returns `action: self` during upgrade or rollback, resolve the replacement or
restored artifact instead of the current workspace runtime. If
`semantic-hygiene` reports issues, treat them as review findings unless a
separate approved work package authorizes proposal creation. If a command
changed canonical memory unexpectedly, stop and compare the workspace backup.
If Git shows `.kb-next/operations.jsonl` changed after every session, the
workspace runtime predates 0.2.2, which moved read events to the git-ignored
`.kb-next/telemetry/events.jsonl`; refresh it with `bootstrap` from the 0.2.2
runtime and commit `.kb-next/runtime/kb_next.py` where the project tracks it.

## Related

- [User manual](user-manual.md)
- [Detailed usage guide](usage-guide.md)
- [Command reference](command-reference.md)
- [Upgrade and rollback](upgrade-rollback.md)
- [Maintainer release](maintainer-release.md)
