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

## Upgrading To 0.2.1 (Runtime 0.2.1)

This release adds the subagent memory bridge, the write gate and automatic
curation, and marks the multilingual dense model not recommended. It changes
no data and no schema.

- Subagent bridge: the skill and `AGENTS.md` tell the main agent to put KB
  records in subagent briefs and to file the `KB candidates` that subagents
  report; the Claude Code plugin adds a `SubagentStart` hook (runtime
  `subagent-hint`).
- Write gate: a `PreToolUse` hook (`scripts/write_gate.py`, Bash and
  PowerShell) denies an agent's `.kb/kb.py create`, `file`, `supersede` or
  `update` in a vNext project and names the proposal path. A project owner
  can turn it off with `{"write_gate": {"enabled": false}}` in
  `.kb-next/kb-next.config.json`.
- `filing-proposal` now blocks provenance that `proposal-apply` would refuse
  (a file path, a URL or an unknown id); cite an existing `record_id` or the
  `source_id` of a file registered with `python .kb/kb.py ingest <path> --json`.
- Curation: `vnext-session-end` runs read-only hygiene detection and writes
  judged hygiene proposals, at most
  `semantic_curation.weekly_hygiene_proposals` (default 5) open per project
  over 7 days; `semantic-hygiene` reports `review_budget`, `already_open` and
  `deferred`.
- `dense-index` and dense lookups warn while `potion-multilingual-128M` is
  configured; the model stays pinned until 0.3.

1. Install the 0.2.1 plugin ZIP or marketplace entry; the hooks take effect
   in the next Claude Code session. Codex asks to trust the changed hooks
   before it runs them.
2. Where the project pins a local runtime, refresh it:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.2.1`).

Rollback: reinstall the 0.2.0 plugin and run `bootstrap` from its runtime.
Nothing to undo in `.kb/`; hygiene proposals that 0.2.1 wrote stay in
`.kb-next/proposals/hygiene` as review evidence, and the hooks write nothing.

## Upgrading To 0.2.0 (Runtime 0.2.0)

This release breaks the `proposal-apply` command line: every apply must name
who approves it. It also replaces the `LIKE` lookup with ranked retrieval,
fixes the classic `kb.py search` query (KB Lifecycle 0.2.5) and adds an
optional dense list that ranks by meaning. Run the steps from each project
root:

1. Refresh the vNext engine from the new plugin:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.2.0`).
2. Refresh the classic engine without touching data or config:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`.
3. Add `--actor <id>` and `--actor-runtime <claude-code|codex|cowork|human>`
   to every script, alias or saved prompt that calls `proposal-apply`.
   `--actor` is the person who approved the proposal; `--actor-runtime` is
   the runtime that runs the apply (`human` when a person runs it by hand):

```powershell
$proposalId = 'replace-with-reviewed-proposal-id'
$approver = 'replace-with-approver-id'
python .\.kb-next\runtime\kb_next.py --project-root . proposal-apply --proposal $proposalId --approve --approval-note "Approved after review" --actor $approver --actor-runtime human --json
```

   A project with one usual approver can instead name that person once, so
   an agent does not ask on every approval. Merge this key into
   `.kb-next/kb-next.config.json`; `--actor` then defaults to it, and
   `--actor-runtime` stays required:

```json
{"proposal_apply": {"default_actor": "replace-with-approver-id"}}
```

4. Optional, for projects that want the dense list: install the extra in
   the Python that runs the runtime, choose the model, then build the index.

```powershell
python -m pip install model2vec==0.10.0
python .\.kb-next\runtime\kb_next.py --project-root . dense-index --fetch-model --json
python .\.kb-next\runtime\kb_next.py --project-root . lookup --facet status --query "release" --limit 5 --lists words,dense --json
```

   Set `retrieval.dense.enabled` to `true` in `.kb-next/kb-next.config.json`
   and keep `retrieval.dense.model` at `potion-base-32M` (the default) before
   the `dense-index` run, so the index is built with that model.
   `potion-multilingual-128M` is not recommended: a cold command-line lookup
   costs about 11.7 s with it against 0.5 s words-only, and query expansion
   by the agent reaches the same Portuguese synonyms at no cost. It stays
   pinned until 0.3 so existing indexes keep loading, and `dense-index` and
   `lookup` print a warning while it is configured. The model
   downloads once into `~/.cache/kb-factory/models` (or `KBF_MODEL_CACHE`),
   outside the project, and `.kb-next/index/` ignores itself in Git. The
   lookup check must list `dense` in `retrieval.lists` with no warning.
   Run `python .kb-next/runtime/kb_next.py dense-index --json` again after
   filing records; until then lookup warns how many records the dense list
   misses. The `vnext-session-end` plugin command runs that refresh when the
   dense list is on and the session changed records.

Behavior changes to expect:

- `proposal-apply` without `--actor` (and without
  `proposal_apply.default_actor` in the config) or without `--actor-runtime`
  exits 2 before it reads the proposal and writes nothing; stderr names the
  missing flags. A blank `--actor` or a runtime outside the four values fails
  the same way; a blank or non-string `default_actor` fails with exit 1,
  also before any write.
- Each apply manifest under `.kb-next/manifests/proposal-apply`, each
  `proposal-apply` entry in `.kb-next/operations.jsonl` and the JSON result
  carry `actor: {id, runtime}` and `actor_source` (`flag` or `config`),
  blocked attempts included. The identity is recorded, not authenticated.
  No runtime command writes `proposal_apply.default_actor`; activation keeps
  it.
- LLM manifests no longer carry the fixed placeholder actor. `semantic-lookup`,
  `curation-proposal`, `semantic-hygiene`, `filing-proposal` and
  `wiki-synthesis-plan` accept the same pair as an option and record who
  generated the proposal, or `actor: null` without it; one flag alone fails.
  The configured default applies to `proposal-apply` only.
- Manifests and oplog entries written before 0.2.0 keep their old shape. A
  reader of `actor` must accept the legacy string, `null` and the
  `{id, runtime}` object.
- `lookup` and the proposal commands rank by an FTS5 word list with BM25
  through Reciprocal Rank Fusion; result order changes, terms are OR-joined,
  and the output carries a `retrieval` block. The trigram substring list is
  opt-in (`--lists words,trigram`), not part of the default fusion.
- With `retrieval.dense.enabled`, lookup also fuses the dense list. A cold
  command-line lookup takes about 3 s more with `potion-base-32M` and about
  11 s more with `potion-multilingual-128M`, almost all of it loading and
  verifying the model (measured on a 446-record KB). Without
  the extra, the model or a current index, lookup ranks by words and says why
  in `retrieval.warnings`. The default install never imports the extra.
- Classic `kb.py search` compiles the query like the vNext word list: a
  trailing `?` or a `-` no longer drops the search to a `LIKE` of the whole
  string, and FTS5 matches are ordered by BM25. The JSON output of `kb.py`
  now escapes non-ASCII characters (`\uXXXX`), so a JSON parser reads the same
  values and a piped Windows console no longer fails on them.

Rollback of this upgrade: restore the 0.1.10 plugin and run its `bootstrap`
as below, then remove `--actor` and `--actor-runtime` from your scripts; the
0.1.8 runtime rejects them as unrecognized arguments. The 0.1.8 runtime
ignores the `retrieval.dense` and `proposal_apply` keys, and
`.kb-next/index/` can be deleted. The classic engine has no schema change:
keep 0.2.5, or restore 0.2.4 with `upgrade-classic` from the old plugin.

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
   the merge. A curated `.kb-next/memory/NOW.md` is kept (only a generated
   template is regenerated) and re-applying the same mode keeps the recorded
   `decided_at` and `rationale`, adding `reconfirmed_at`; the JSON result
   reports `now.action` and `decision`.
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
