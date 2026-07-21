# KB/Wiki vNext Upgrade And Rollback

## Purpose

Upgrade KB/Wiki vNext safely while preserving canonical `.kb/` memory and keeping rollback possible.

## Audience

Admins, maintainers, and project owners receiving a new controlled bundle.

## Prerequisites

- Current workspace state committed or otherwise backed up.
- Current package version recorded.
- No pending unreviewed `proposal-apply` operation.

## Steps

Record the current package, workspace-runtime version, and command namespace:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . session-start --json
```

For plugin installs, also confirm `vnext-session-start` is available and
generic `session-start` / `session-end` command basenames are absent.

Install the replacement plugin or unpack the replacement stand-alone bundle
beside the old one. Keep the previous artifact available. Do not overwrite
`.kb/` with the bundled template in an existing workspace.

Resolve the runtime from the **new artifact**, in this order:

1. `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` for the newly installed plugin.
2. The newly installed client-plugin path matching
   `**/kb-wiki-vnext/runtime/kb_next.py`.
3. `runtime/kb_next.py` inside the newly unpacked stand-alone bundle.
4. `core/versions/kb-wiki-vnext/runtime/kb_next.py` only inside the KB Factory
   authoring monorepo.

Do not use the current `.kb-next/runtime/kb_next.py` as the upgrade source. If
the new artifact has no runtime, stop and report an incomplete artifact.

Bootstrap the workspace from that new source:

```powershell
python <new-source-runtime> --project-root . bootstrap --json
```

Require the expected new `runtime_version` and an `action` of `created`,
`updated`, or `exists`. Require `source_sha256` to equal `installed_sha256`;
same-version but different bytes are replaced. An `action` of `self` is not
upgrade proof because it means the workspace runtime was used as its own source.

Run the checks from the refreshed workspace runtime:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . compliance-preflight --work-type operational --topic "vNext upgrade check" --json
python .\.kb-next\runtime\kb_next.py --project-root . session-start --json
python .\.kb-next\runtime\kb_next.py --project-root . semantic-hygiene --scope hot-overflow --json
```

For rollback, reinstall the previous plugin ZIP or restore the previous
stand-alone bundle. Resolve its runtime by the same artifact-first ladder and
run:

```powershell
python <restored-source-runtime> --project-root . bootstrap --json
```

Require the expected prior `runtime_version` and equal `source_sha256` /
`installed_sha256`; `action: self` is not rollback proof. Leave `.kb/`
untouched unless a human maintainer explicitly restores it from a workspace
backup.

## Verification

The upgrade is acceptable when bootstrap reports the expected version and
matching source/installed hashes, `vnext-session-start` or runtime
`session-start` succeeds, and
`.kb-next/memory/NOW.md` remains readable. Session and preflight commands may
append operational evidence to `.kb-next/operations.jsonl`; they must not change
canonical `.kb/`. Compare the `.kb/kb.db` hash before and after the checks.

Schema v6 rollback is forward-compatible. Rolling runtime code back does not
drop `record_edges` or reduce `schema_meta`; there is no destructive schema
downgrade. Before migrating a production copy, prove that the v0.1.4 runtime
still reads a migrated v6 copy, retain the pre-migration backup and hash, and
do not apply typed edges or source-link candidates during activation.

## Troubleshooting

If the new runtime fails, return to the previous artifact and preserve the
failing bundle for maintainer review. If `.kb/` changed unexpectedly, stop and
compare the workspace backup before continuing.

## Related

- [Architecture](architecture.md)
- [Command reference](command-reference.md)
- [Maintainer release](maintainer-release.md)
- [User manual](user-manual.md)
