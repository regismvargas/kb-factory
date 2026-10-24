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

## Upgrading To 0.2.5 (Runtime 0.2.5)

This release fixes integrity defects found in the review of 2026-10-23. It
ships with KB Lifecycle 0.2.9 (classic engine and skill); Session Gate stays
0.2.10. It changes no data and no schema.

- A repeated `proposal-apply` of an applied proposal returns
  `already_applied` and writes nothing, also when it runs from another
  checkout of the same KB or at the same time as the first: classic
  `create --if-source-absent` checks and inserts in one transaction, and
  `supersede` takes only an ATIVO record. A run that stopped mid-apply is safe
  to retry.
- Classic `supersede` refuses a record that is not ATIVO. Run
  `upgrade-classic` (or the rollout) so the project's `.kb/runtime/` gets the
  0.2.9 engine.
- `approved-filing`, `proposal-apply` and wiki materialization refuse a
  confidence that is not a finite number in [0, 1].
- A supersede cannot change the domain; file a new record in the new domain
  and retire the old one instead.
- HOT curation proposes fewer demotions when stale records already cover the
  excess.

Rollback: reinstall the 0.2.4 plugins and run `bootstrap` and
`upgrade-classic` from them; no data migration is involved.

## Upgrading To 0.2.4 (Runtime 0.2.4)

This release shortens every session's start and close and keeps source
snapshot bytes under any line-ending setting. It ships with KB Lifecycle
0.2.8 and Session Gate 0.2.10. It changes no data and no schema. The classic
write boundary (E3.4) is not in this release.

Lean session boundaries:

- With the SessionStart hook, `session-hint` is the session start: it carries
  the activation mode, the classic KB root, the classic NOW header with its
  `Generated` time, the wiki state, the on-demand reads and the command
  sheet. The agent reads `.kb-next/memory/NOW.md` only when the hint says the
  team wrote it. Clients without the hook (Codex before hook trust, Cowork)
  keep `vnext-session-start` or `gate-session-start`.
- `vnext-session-end` and `gate-session-end` file what the user approved,
  then run `python .kb/kb.py lifecycle session-end --json` once, then
  `wiki-draft-status` when KB + Wiki is active and not dormant: one call with
  KB alone, two with an active wiki. Curation runs in the weekly maintenance
  run; a full maintenance pass the user asks for at close still writes
  proposals only.
- `session-hint` adds a `Curation overdue` line when the newest read-only
  `semantic-hygiene` check is more than 7 days old. A runtime older than
  0.2.4 records no check, so the line shows until the project runtime is
  bootstrapped and the next weekly run passes.

Source snapshots keep their bytes:

- The template's `.kb/.gitattributes` holds `sources/** -text`, so Git no
  longer converts snapshot line endings, whatever the repository's
  `text=auto`, `eol=lf` or `core.autocrlf`. The KB's SHA-256 of each source
  stays valid on every clone.

1. Install the 0.2.4 vNext plugin, KB Lifecycle 0.2.8 and Session Gate 0.2.10
   (ZIPs or marketplace entries), and restart the client.
2. Where the project pins a local runtime, refresh it:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.2.4`).
3. Add the source rule: `python .kb-next/runtime/kb_next.py upgrade-classic --json`
   (expect `gitattributes_updated` `true` once). The classic engine files do
   not change in this release.
4. Store the snapshot bytes the KB hashed. First make sure
   `git status -- .kb/sources` is empty: commit or set aside any change you
   made there yourself, so the next step stages nothing but line endings.
   Git's stat cache hides the change the rule makes, so run
   `git add --renormalize -- .kb/sources`. Before committing, check that
   `git diff --cached --ignore-cr-at-eol -- .kb/sources` prints nothing: the
   staged snapshots then differ from Git's copy only in line endings. If it
   prints anything, stop, run `git restore --staged -- .kb/sources` and review
   those files. Otherwise commit `.kb/.gitattributes` with the staged
   snapshots and any refreshed runtime files.
5. Check the hashes: `python .kb/kb.py source-verify --json`. The rule
   prevents new conversions; it does not repair a snapshot that a checkout
   already converted. For a remaining `hash_mismatch` on a text snapshot, keep
   a copy of the file, convert it to the other line ending (CRLF to LF or LF
   to CRLF) and run `source-verify` again. When the mismatch is gone, those
   are the bytes the KB recorded at ingest: commit them. When it stays, put
   the copy back. The cause is then undetermined (the snapshot may have mixed
   line endings, or its content changed): compare it with the original file
   or a backup before you touch the record.
6. Run `python .kb-next/runtime/kb_next.py session-start --json` once and
   check that `git status` lists no new change under `.kb-next/`.

Rollback: reinstall the v0.2.3 plugins (kb-wiki-vnext 0.2.3, KB Lifecycle
0.2.7, Session Gate 0.2.9) from the public v0.2.3 release and run `bootstrap`
from the 0.2.3 runtime. The session commands go back to the longer start and
close. `.kb/.gitattributes` can stay: removing it lets Git convert snapshot
line endings again. Nothing else to undo in `.kb/`.

## Upgrading To 0.2.3 (Runtime 0.2.3)

This release brings decision 12 of 2026-10-21 (write gate and governed
retirement), which missed the 0.2.2 cut, and three later changes: fewer
derived files per record with one wiki snapshot per page per day (PR #41),
the Portuguese template seeds (PR #40) and the dormant-wiki NOW (PR #42).
It ships with KB Lifecycle 0.2.7 and Session Gate 0.2.9. It changes no data
and no schema.

Write gate and governed retirement (decision 12 of 2026-10-21):

- Codex runs the plugin's PreToolUse hook only after the user trusts it.
  A live probe on 2026-10-21 (codex-cli 0.156.1, Windows) saw two direct
  `kb.py create` calls write records without trust; with trust bypassed for
  one run, the hook fired on every shell call and denied the create. Codex
  sends `tool_name` `Bash` with the raw command, so the gate needs no
  Codex-specific parsing. This corrects the v0.2.1 known issue: the
  PowerShell-wrapped form it cites appears only in the `codex exec --json`
  event stream, never in the hook payload. The missing trust is the issue.
- The gate also denies `kb.py resolve`, `bulk-import`, `init --seed`,
  `raw-query --allow-write`, `consolidate --apply-demotions`,
  `lifecycle scheduled-maintenance` and any `lifecycle` event run with
  `--apply-demotions` or `--apply-cold-demotions`. `ingest`, plain
  `lifecycle` events, `wiki-*`, `export`, `--help` and reads stay open. It
  reads launch forms an agent types (`env`, `python -m kb`, `cmd /c`,
  `powershell -Command`, `bash -lc`, `Start-Process`, `Invoke-Expression`,
  line continuations),
  follows literal `cd`, `Set-Location`, `pushd` and `popd`, and gates a
  linked Git worktree when it or its main checkout is activated; the
  classic demotion guard uses the same rule.
- `proposal-apply --target-record-id` can no longer move an approved
  proposal to another record. For `demote_hot`, `resolve` and `retire` it
  must repeat the proposal's target; for `supersede` it may only pick one of
  the duplicate candidates the proposal names. Any other value blocks with
  `invalid_target_override`. Earlier runtimes, 0.2.2 and 0.2.1 included, applied an
  approved proposal to whatever record the flag named.
- New hygiene action `retire`: a record that an existing ATIVO record already
  replaces goes to `supersede_or_merge_candidate` with `"action": "retire"`
  and `replacement_id`; `proposal-apply` runs the classic `supersede` with
  `--replacement-id` (KB Lifecycle 0.2.7), which marks it SUPERSEDIDO without
  creating a record. RESOLVIDO stays for open
  items (PENDENCIA) only.
- KB Lifecycle 0.2.7 skips automatic HOT and COLD demotions in a project with
  `.kb-next/kb-next.config.json`, from config or flags, and reports
  `demotions_skipped`. Classic-only projects keep their demotions.
- Session Gate 0.2.9 no longer runs `scheduled-maintenance --apply-demotions`
  in a vNext workspace; it runs the vNext curation step instead.

Derived files and fixes:

- Exports and the wiki rewrite a derived file only when its content changes
  (the `Generated` stamp alone no longer counts), so one filing touches
  about half the files it did. A replaced wiki page is kept in
  `wiki/snapshots` once per page per UTC day instead of once per re-render;
  the full history stays in the records, `audit_log`, the oplog and Git.
- `session-hint` ends with a five-line command sheet for this project, and
  `--help` lists the everyday commands; `--help-all` prints everything.
- The five Portuguese template seeds found in the portfolio leave NOW, HOT
  and INDEX like the English ones after the next export.
- A dormant wiki's NOW says when the wiki starts and points to
  `session-start` for the current state.

1. Install the 0.2.3 vNext plugin, KB Lifecycle 0.2.7 and Session Gate 0.2.9
   (ZIPs or marketplace entries).
2. Where the project pins a local runtime, refresh it:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.2.3`).
3. Refresh the classic engine, which `retire` and the demotion guard need:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`
   (`supersede --help` then lists `--replacement-id`). On an older engine
   `proposal-apply` blocks a `retire` with a warning that names
   `upgrade-classic`.
4. Where the project tracks `.kb-next/runtime/kb_next.py` or `.kb/runtime/`,
   commit the refreshed files. Until that commit lands, every other clone or
   worktree of the project runs the tracked 0.2.2 runtime and engine. Then run
   `python .kb-next/runtime/kb_next.py session-start --json` once and check
   that `git status` lists no new change under `.kb-next/`.
5. Codex only: trust the plugin's hooks in Codex's hook review. Codex 0.156.1
   runs a plugin hook only after that trust, and an untrusted hook leaves no
   trace in `codex exec --json`. Check that the PreToolUse trust is recorded:
   `Select-String -Path "$HOME\.codex\config.toml" -Pattern 'kb-wiki-vnext@.*pre_tool_use'`
   This release does not change the hook commands in `hooks/hooks.json`.
   Whether a later change to them makes Codex ask for trust again is a
   hypothesis from the 2026-10-21 probe, not verified. Persisted trust itself
   is not yet tested; until the check below passes, treat the Codex gate as
   unverified.
   Acceptance, in a disposable sandbox and never in a portfolio project
   (`$runtime` is the installed plugin runtime; the record count must not
   change and the event stream must show the block):

   ```powershell
   $runtime = "$HOME\.codex\plugins\cache\kb-factory-tools\kb-wiki-vnext\0.2.3\runtime\kb_next.py"
   New-Item -ItemType Directory trust-check | Set-Location
   git init
   python $runtime --project-root . install-classic --slug trustcheck --domains general --json
   python $runtime --project-root . bootstrap --json
   python $runtime --project-root . activation-wizard --mode short --choice kb-alone --json
   Set-Content prompt.txt 'Run exactly one shell command and nothing else: python .kb/kb.py create --category FATO --domain general --title "Gate check" --content "Codex trust check" --source check --json'
   Get-Content prompt.txt | codex exec -C . --ephemeral --json - | Select-String 'Command blocked by PreToolUse hook'
   python -c "import sqlite3; print(sqlite3.connect('.kb/kb.db').execute('SELECT COUNT(*) FROM records').fetchone()[0])"
   ```

   One more record than after `install-classic` means the trust did not take.

Rollback: reinstall the v0.2.2 plugins (kb-wiki-vnext 0.2.2, KB Lifecycle
0.2.6, Session Gate 0.2.8) from the public v0.2.2 release and run `bootstrap`
from the 0.2.2 runtime. Then run its `upgrade-classic` with `--template`
pointing at the KB Lifecycle 0.2.6 scaffold folder of that release: without
it, a plugin cache that still holds 0.2.7 is picked as the newest scaffold
and the 0.2.7 engine comes back. Check that `python .kb/kb.py supersede
--help` no longer lists `--replacement-id`. Nothing to undo in `.kb/`. Records retired with 0.2.3 stay
SUPERSEDIDO, which an older classic engine reads as any superseded record;
with the 0.2.6 engine, automatic demotions run again in vNext projects.

## Upgrading To 0.2.2 (Runtime 0.2.2)

This release keeps read telemetry out of the versioned governance trail and
fixes the `session-start` command that `session-hint` prints. It changes no
data and no schema.

- `session-start`, `lookup`, `semantic-lookup` and `dense-index` append their
  events to `.kb-next/telemetry/events.jsonl` instead of
  `.kb-next/operations.jsonl`, so a session no longer changes a tracked file.
  The telemetry directory ignores itself through its own `.gitignore`, written
  once by `activation-wizard` or by the first telemetry append; the project's
  `.gitignore` is not edited. The file rotates to `events.1.jsonl` at 1 MiB.
- Both files are written with LF line endings on Windows too. Existing lines in
  `.kb-next/operations.jsonl` are not rewritten: read events and CRLF lines
  from earlier runtimes stay as history.
- `session-hint` names a runtime that exists when `.kb-next/runtime/` is
  absent and adds a `Runtime skew` line when the local runtime's version
  differs from the plugin's.

Lean onboarding (PR #37), in this release:

- Template seeds. The classic scaffold of KB Lifecycle 0.2.6 seeds no
  record. A KB created earlier keeps its five template seeds in `kb.db` and in
  search; NOW, HOT, INDEX, topics, packs, wiki candidates, wiki signals and
  vNext wiki topics leave them out from the next refresh of those surfaces,
  which `python .kb/kb.py export` (or any `lifecycle session-end`) runs.
- Scope. `activation-wizard --scope "<scope in the user's words>"` files the
  scope once as a HOT `DECISAO` tagged `project-scope`, without
  `valid_until`. Without `--scope` no record is filed.
- Dormant wiki. A `kb-wiki` activation with fewer than
  `--wiki-min-sourced-records` (default 10) active records citing a
  registered source leaves the classic wiki dormant (`signal` mode): no
  pages, no drafts line in the hook, `wiki.status` `dormant`. The record that
  crosses the mark publishes the first pages. An enabled classic wiki stays
  on; to publish right away on a new activation, pass
  `--wiki-min-sourced-records 0`.
- One call for a record approved in chat. `approved-filing` files it with the
  `proposal-apply` rules (provenance, confidence floor, active supersede
  target) plus a same-title check, one manifest under
  `.kb-next/manifests/approved-filing/` and one oplog line; a blocked call
  writes nothing and exits 1. A supersede may change the category and clear
  `valid_until` (`--valid-until none`); a category change needs classic
  0.2.6 (`supersede --category`); in 0.2.2 only `approved-filing` passes it
  (`proposal-apply` does from 0.2.3).
- Record-level wiki confidence. A record below `min_confidence_autopublish`
  leaves its page instead of holding the whole page back; a page is held back
  only when no record remains, and `wiki-sync` and `wiki-check` list the
  left-out records as `records_held_back`. After `upgrade-classic`, the next
  `wiki-sync` may publish pages that 0.2.1 held back.

1. Install the 0.2.2 plugin ZIP or marketplace entry.
2. Where the project pins a local runtime, refresh it:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (expect `runtime_version` `0.2.2`).
3. Where the project tracks `.kb-next/runtime/kb_next.py`, commit the refreshed
   runtime together with any oplog lines that 0.2.1 sessions left uncommitted.
   Then run `python .kb-next/runtime/kb_next.py session-start --json` once and
   check that `git status` lists no new change under `.kb-next/`.

Rollback: reinstall the 0.2.1 plugin from the public v0.2.1 release and run
`bootstrap` from its runtime. Nothing to undo in `.kb/`; read events then go back to
`.kb-next/operations.jsonl`, and `.kb-next/telemetry/` can be deleted.

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
`.kb-next/memory/NOW.md` remains readable. Session commands append read
telemetry to the git-ignored `.kb-next/telemetry/events.jsonl` and preflight writes nothing;
they must not change canonical `.kb/`. Compare the `.kb/kb.db` hash before and after the checks.

## Troubleshooting

If the new runtime fails, return to the previous artifact and preserve the
failing bundle for maintainer review. If `.kb/` changed unexpectedly, stop and
compare the workspace backup before continuing.

## Related

- [Architecture](architecture.md)
- [Command reference](command-reference.md)
- [Maintainer release](maintainer-release.md)
- [User manual](user-manual.md)
