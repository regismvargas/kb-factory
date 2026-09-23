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

## Upgrading To 0.1.10 (Runtime 0.1.8)

This release repairs the KB + Wiki flow. Projects activated with
`--choice kb-wiki` on 0.1.9 or earlier kept the classic wiki off; this upgrade
turns it on and keeps it current. Run the steps from each project root:

1. Refresh the vNext engine from the new plugin:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.1.8`).
2. Refresh the classic engine without touching data or config:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`.
3. Re-apply the recorded decision (`sponsor_decision` in
   `.kb-next/decisions/activation-decision.json`):
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json` (or `--choice kb-alone`).
   For `kb-wiki` this sets `wiki.enabled` and `run_wiki_sync` on the
   record-filed, source-ingest, session-end and scheduled-maintenance events in
   `.kb/kb.config.json`, keeps every other key, runs the first `wiki-sync`, and
   records `classic-config-sync` and `classic-wiki-sync` in
   `.kb-next/operations.jsonl`. Edits in `.kb-next/kb-next.config.json` survive
   the merge.
4. Classic-only projects that already use the wiki:
   `python .kb/kb.py wiki-config --enable --json`.
5. Normalize legacy absolute source paths:
   `python .kb/kb.py source-relink --dry-run --json`, then without `--dry-run`.
6. Check `python .kb/kb.py doctor --json`, `python .kb/kb.py wiki-check --json`
   (`wiki_state` is not `off` for `kb-wiki`; `publication.held_back` names each
   page kept back and why) and `session-start --json` (`wiki.status` is
   `aligned`).

Behavior changes to expect:

- Commands other than `init` stop with an explicit message when `.kb/kb.db` is
  missing; nothing creates an empty KB silently.
- In a linked Git worktree the classic runtime uses the main worktree `.kb/`
  when it has a `kb.db`, so per-session worktrees share one KB. Set
  `storage.worktree_scope` to `local` to opt out. `doctor --json` reports the
  resolution and warns when `kb.db` is tracked in Git.
- New record IDs carry the project prefix (`<SLUG>-KB-<utc>-<hex>`). Set
  `project.id_prefix` to override it, or to an empty string for the old format.
- Read commands no longer write `kb.db`; `get` access counting is opt-in
  (`tracking.record_access`).
- `wiki.enabled: true` turns the wiki on in every `activation_mode`.
- `create`, `file`, `supersede`, `resolve` and `ingest` refresh exports and the
  enabled wiki; pass `--no-auto-lifecycle` to skip.
- New runtime commands: `install-classic`, `upgrade-classic`,
  `wiki-draft-status` and `session-hint`; `lookup`, `semantic-lookup` and
  `curation-proposal` accept `--domain`. The plugin adds `vnext-wiki-drafts`.

Rollback of this upgrade: restore the previous plugin and run its `bootstrap`
as below. Return the classic wiki keys to their prior values only with
approval, using `changes[].from` in the last `classic-config-sync` entry, and
restore the previous classic engine with
`python .kb-next/runtime/kb_next.py upgrade-classic --template <previous-scaffold-dir> --json`.

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

## Troubleshooting

If the new runtime fails, return to the previous artifact and preserve the
failing bundle for maintainer review. If `.kb/` changed unexpectedly, stop and
compare the workspace backup before continuing.

## Related

- [Architecture](architecture.md)
- [Command reference](command-reference.md)
- [Maintainer release](maintainer-release.md)
- [User manual](user-manual.md)
