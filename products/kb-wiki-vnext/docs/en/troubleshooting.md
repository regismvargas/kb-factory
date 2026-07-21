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
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip
```

For runtime examples and safe conversation prompts, see the [detailed usage guide](usage-guide.md).

## Verification

A healthy workspace can run the plugin `vnext-session-start` command or the
runtime `session-start`, read `.kb-next/memory/NOW.md`, and complete `lookup`
or default `semantic-hygiene` without changing `.kb/kb.db`. `lookup` and
`session-start` append operations evidence; default `semantic-hygiene` does
not. Session Gate installs should expose `gate-session-start` and route
`.kb-next/` before classic `.kb/`.

## Troubleshooting

If `.kb/kb.py` is missing in a new project, bootstrap from
`classic-template/.kb/`; never overwrite an existing `.kb/`. If plugin install
fails, confirm the package matches the platform, contains `runtime/kb_next.py`,
and omits generic `session-start` / `session-end` command files. If bootstrap
returns `action: self` during upgrade or rollback, resolve the replacement or
restored artifact instead of the current workspace runtime. If
`semantic-hygiene` reports issues, treat them as review findings unless a
separate approved work package authorizes proposal creation. If a command
changed canonical memory unexpectedly, stop and compare the workspace backup.

For graph failures, run `graph verify --json` first. Exit `1` means structural
findings, not a runtime crash. On a schema v5 KB,
`TYPED_EDGE_CAPABILITY_UNAVAILABLE` is an expected warning. Exit `2` means a
usage or environment error. If any vNext graph read changes the DB or
`.kb-next` tree hash, stop: that violates the read-only contract. Do not apply
`source-backfill` output automatically.

## Related

- [User manual](user-manual.md)
- [Detailed usage guide](usage-guide.md)
- [Command reference](command-reference.md)
- [Upgrade and rollback](upgrade-rollback.md)
- [Maintainer release](maintainer-release.md)
