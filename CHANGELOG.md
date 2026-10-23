# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.4] - 2026-10-23

Every vNext session now starts with no call and closes with one or two, and
source snapshots keep their bytes under any line-ending setting. See
"Upgrading To 0.2.4" in `products/kb-wiki-vnext/docs/en/upgrade-rollback.md`
(Portuguese: `products/kb-wiki-vnext/docs/pt-BR/upgrade-rollback.md`).

### Changed
- Session start. With the SessionStart hook, `session-hint` is the start: the
  activation mode, the classic KB root, the classic NOW header with its
  `Generated` time, the wiki state, the on-demand reads and the command
  sheet. The agent reads `.kb-next/memory/NOW.md` only when the hint says
  the team wrote it. `vnext-session-start` and `gate-session-start` stay for
  clients without the hook, and `compliance-preflight` still applies.
- Session close. `vnext-session-end` and the vNext part of `gate-session-end`
  file what the user approved, then run `lifecycle session-end` once, then
  `wiki-draft-status` when KB + Wiki is active and not dormant: one call with
  KB alone, two with an active wiki, down from four to seven.
  `gate-session-end` drops the `git status` audit, the consistency step and
  the session-id prompt.
- Curation runs in the weekly maintenance run, never at session end; a full
  maintenance pass the user asks for at close writes proposals only.
  `session-hint` adds a `Curation overdue` line when the newest read-only
  `semantic-hygiene` check is more than 7 days old.

### Fixed
- Source snapshots keep their bytes. The KB stores each source's SHA-256 at
  ingest, and a repository-wide `* text=auto`, `eol=lf` or `core.autocrlf`
  converted snapshot line endings on commit or checkout, which broke that
  check. The classic template (kb-lifecycle 0.2.8) ships `.kb/.gitattributes`
  with `sources/** -text`; `upgrade-classic` adds the rule to existing
  projects and keeps it at the end of the file. The upgrade notes give the
  `git add --renormalize` step that stores the hashed bytes and a recovery
  check for a snapshot a checkout already converted.

### Documentation
- Public docs describe the 0.2.4 session start and close.
- Release lines: Python package `0.2.4`, catalog `0.3.15`, kb-lifecycle
  `0.2.8`, kb-wiki-vnext `0.2.4`, session-gate `0.2.10`, vNext runtime `0.2.4`,
  stand-alone product `0.2.0-rc.8`.

## [0.2.3] - 2026-10-22

0.2.2 was cut before the write-gate and governed-close work of 2026-10-21
merged. This release ships it, together with fewer derived files per record.
See "Upgrading To 0.2.3" in `products/kb-wiki-vnext/docs/en/upgrade-rollback.md`
(Portuguese: `products/kb-wiki-vnext/docs/pt-BR/upgrade-rollback.md`).

### Added
- Governed retirement. `semantic-hygiene` can propose `retire` for a record
  that an existing active record already replaces; after approval,
  `proposal-apply` runs the classic `supersede --replacement-id`
  (kb-lifecycle 0.2.7), which marks the record SUPERSEDIDO without creating
  a new one, so several records can retire into one. RESOLVIDO stays for
  open items.
- `kb_next.py --help` and `kb.py --help` list the commands an agent uses day
  to day; `--help-all` prints everything. `session-hint` ends with a
  five-line command sheet on the project's runtime path.

### Changed
- Write gate. Besides `create`, `file`, `supersede` and `update`, the
  kb-wiki-vnext hook denies `resolve`, `bulk-import`, `init --seed`,
  `raw-query --allow-write`, `consolidate --apply-demotions`,
  `lifecycle scheduled-maintenance` and any `--apply-demotions` or
  `--apply-cold-demotions` flag in a vNext project, and names the governed
  route for each. It reads more launch forms (`env`, `python -m kb`,
  `cmd /c`, `powershell -Command`, `bash -lc`, `Start-Process`,
  `Invoke-Expression`, line continuations, a literal `PYTHONPATH=` or
  `KB_FACTORY_WORKTREE_SCOPE=`) and gates a linked Git worktree when it or
  its main checkout is activated. `--help` passes. The hook steers agents;
  it does not authenticate them.
- Demotions only by proposal. kb-lifecycle 0.2.7 skips automatic HOT and COLD
  demotions in a project with KB/Wiki vNext active, from config or flags,
  and reports `demotions_skipped`; Session Gate 0.2.9 runs the vNext curation
  step instead of `scheduled-maintenance --apply-demotions` there.
  Classic-only projects keep their demotions.
- Derived files are rewritten only when their content changes (the
  `Generated` stamp alone no longer counts), so one filing touches about half
  the files it did, and a replaced wiki page is snapshotted at most once per
  page per UTC day.
- The template seeds stored in Portuguese leave NOW, HOT and INDEX like the
  English ones.

### Fixed
- Governance: `proposal-apply --target-record-id` could apply an approved
  proposal to a different record, in every earlier vNext runtime including
  0.2.2. The flag now has to repeat the proposal's target (`demote_hot`,
  `resolve`, `retire`) or pick one of the duplicate candidates the proposal
  names (`supersede`); anything else is blocked and changes nothing.
- A supersede proposal that changes the category (for example a premise to a
  decision) now keeps the new category through `proposal-apply`, as
  `approved-filing` already did.
- A dormant wiki's vNext NOW no longer says "Wiki active: false" after the
  wiki wakes; it says when the wiki starts and points to `session-start`.
- Codex: the v0.2.1 known issue named two causes; only the missing hook trust
  is real. Codex runs the plugin's PreToolUse hook only after the user trusts
  it; the upgrade notes give the trust step and an acceptance check.

### Documentation
- Public docs describe the 0.2.3 write gate, the demotion guard and the
  snapshot rule.
- Public docs also brought level with 0.2.2: `docs/architecture.md` describes the
  dormant KB + Wiki activation (no wiki-sync until 10 active records cite a
  registered source) and the `--scope` record; `docs/commands.md` lists
  `activation-wizard` (`--scope`, `--wiki-min-sourced-records`) and
  `approved-filing`, with an example, and the write gate's 0.2.2 deny and
  coverage; the README, agent-sessions, provenance, plugins and guide pages
  name `approved-filing` for a record approved in chat next to the proposal
  path.
- Release lines: Python package `0.2.3`, catalog `0.3.14`, kb-lifecycle
  `0.2.7`, kb-wiki-vnext `0.2.3`, session-gate `0.2.9`, vNext runtime `0.2.3`,
  stand-alone product `0.2.0-rc.7`.

## [0.2.2] - 2026-10-22

Measured on the first day of a new project in KB + Wiki mode: 4 of its 7
records were template seeds about the KB itself, they filled NOW, HOT and the
only wiki page, the scope was a placeholder premise that expired in 30 days,
and filing one decision approved in chat took two commands and three JSON
files. This release cuts that first-day overhead.

### Added
- `approved-filing` (vNext runtime): files one record the user approved in
  chat in a single call, with the record fields inline. It applies the
  `proposal-apply` rules (provenance from a registered source or an existing
  record, the confidence floor, an active supersede target) plus a same-title
  check, and writes one manifest under `.kb-next/manifests/approved-filing/`
  and one oplog event. A blocked call writes nothing and exits 1.
  `filing-proposal` and `proposal-apply` stay for approvals that come later
  or from someone else.
- `activation-wizard --scope "<text>"` files the user's scope once as a HOT
  `DECISAO` tagged `project-scope`, with no expiry. No scope, no record.
- `activation-wizard --wiki-min-sourced-records <n>` (default 10): a new
  KB + Wiki stays dormant until that many active records cite a registered
  source. `session-start` reports `wiki.status` `dormant`, the session hook
  drops the wiki-drafts step, and the record that crosses the mark publishes
  the first pages. `0` turns the wiki on at once; an enabled wiki is never
  put back to sleep.
- Classic `supersede` accepts `--category` and `--valid-until none`, so a
  premise can become a decision and drop its expiry.
- Classic `wiki.eligibility.min_sourced_records`: when set, the only
  activation signal of a `signal`-mode wiki.

### Changed
- The classic scaffold (kb-lifecycle 0.2.6) seeds no record. KBs created
  earlier keep their five template seeds in `kb.db` and in search; NOW, HOT,
  INDEX, topics, project packs, wiki candidates and wiki signals leave them
  out. A seed is matched by its template title and bootstrap source, so a
  record the project rewrote stays visible.
- Wiki confidence gate: a record below `min_confidence_autopublish` is left
  off its page instead of holding the whole page back. Sources follow the
  kept records, a page is held back only when no record remains, and
  `wiki-sync` and `wiki-check` list the left-out records as
  `records_held_back`.
- Read telemetry leaves the governance trail: `session-start`, `lookup`,
  `semantic-lookup` and `dense-index` append to the git-ignored
  `.kb-next/telemetry/events.jsonl`; `.kb-next/operations.jsonl` keeps
  mutations and decisions, written with LF line endings.
- `session-hint` prints a runnable command and names a skew between the
  project's runtime and the plugin.

### Fixed
- Write gate: a relative `kb.py` write after `cd`, `pushd` or `Set-Location`
  in the same command, inside `{ }` blocks (`try`/`finally`, `if`, loops) or
  inside a nested `bash -c`, `pwsh -Command` or `cmd /c` is now denied in a
  vNext project. The deny names `approved-filing` first.
- The runtime-skew version key no longer shadows the helper that sorts
  plugin cache directories, which would have raised on a pre-release
  directory name.

### Documentation
- Public docs brought level with 0.2.0 and 0.2.1: the optional dense list is
  described where search is discussed; `docs/comparison.md` cites the measured
  evidence instead of saying there is none; agent workflows name the vNext
  proposal path and the write gate; `docs/commands.md` gains a KB/Wiki vNext
  runtime section; the subagent boundary is in
  `docs/provenance-and-continuity.md`; the README summarizes the evidence.
- The Codex CLI `codex plugin` commands replace the "no plugin command"
  wording in the plugin READMEs and the admin installation guides (en, pt-BR),
  which 0.2.1 had fixed only in `docs/installation.md`.
- `docs/releasing.md` describes the pull-request flow that the protected `main`
  requires instead of a direct fast-forward.
- The vNext command reference (en, pt-BR) lists the 0.2.x runtime subcommands
  and the three plugin hooks, and the full `vnext-session-end` sequence.

## [0.2.1] - 2026-10-20

### Added
- Subagent memory bridge. The `kb-wiki-vnext` skill and plugin `AGENTS.md`
  tell the main agent to run a widened `lookup --facet status` before it
  launches a subagent and to paste the records that bear on the subtask into
  the brief under `KB records`; subagents report `KB candidates`, which the
  main agent turns into `filing-proposal` entries. A new runtime
  `subagent-hint` command and a `SubagentStart` plugin hook give every Claude
  Code subagent in a vNext workspace the no-write rule and the candidates
  section. Subagents never write the KB.
- Write gate. A `PreToolUse` plugin hook (`scripts/write_gate.py`) denies an
  agent shell command that runs `.kb/kb.py create`, `file`, `supersede` or
  `update` in a vNext project and points to `filing-proposal`,
  `semantic-hygiene` and `proposal-apply`. Reads and classic-only projects are
  not affected; `{"write_gate": {"enabled": false}}` in the vNext config turns
  it off.
- Automatic curation. `vnext-session-end` runs the read-only detection
  (`kb.py hygiene-audit`, `semantic-hygiene`) and writes a judged batch of
  hygiene proposals. `semantic-hygiene` reports a `review_budget` (default 5
  open proposals per project per 7 days), skips targets that already have an
  open proposal and lists the rest under `deferred`. Corrections still need an
  approved `proposal-apply`.
- [docs/evidence.md](docs/evidence.md): two pre-registered counterfactual
  experiments on real projects. The value of the knowledge base is its
  curated content; the same content as plain Markdown matched it.

### Changed
- `filing-proposal` applies the provenance rule of `proposal-apply`: each
  provenance entry must be an existing `record_id` or a registered
  `source_id`, so an invalid judgment is `blocked` at proposal time instead of
  refused at apply.
- `potion-multilingual-128M` is not recommended for routine use (about 11.7 s
  per cold command-line lookup against 0.5 s words-only); `dense-index` and
  dense lookups report an advisory. It stays pinned until 0.3.
- [docs/installation.md](docs/installation.md): the Codex CLI does have a
  `plugin` subcommand; the Codex section now gives
  `codex plugin marketplace upgrade` and `codex plugin add`.
- Release lines: Python package `0.2.1`, catalog `0.3.12`, kb-wiki-vnext
  `0.2.1`, vNext runtime `0.2.1`, stand-alone product `0.2.0-rc.5`;
  kb-lifecycle `0.2.5` and session-gate `0.2.8` unchanged.

## [0.2.0] - 2026-10-20

This release breaks the `proposal-apply` command line. See "Upgrading To
0.2.0" in `products/kb-wiki-vnext/docs/en/upgrade-rollback.md` (Portuguese:
`docs/pt-BR/upgrade-rollback.md`) before upgrading a project.

### Changed
- **Breaking:** vNext `proposal-apply` records who approves each apply. It
  requires `--actor <id>` and `--actor-runtime <claude-code|codex|cowork|human>`;
  without them it exits 2 before it reads the proposal and writes nothing. A
  project with one usual approver can name that person once in
  `proposal_apply.default_actor` of `.kb-next/kb-next.config.json`; `--actor`
  then defaults to it. The apply manifest, the `proposal-apply` oplog entry and
  the JSON result carry `actor: {id, runtime}` and `actor_source` (`flag` or
  `config`). The identity is recorded, not authenticated.
- vNext `lookup` ranks by relevance instead of an unranked `LIKE`: one
  throwaway FTS5 word index per query (accents folded, BM25), fused through
  Reciprocal Rank Fusion. Identifiers such as `MC-G1` need no escaping, a
  trailing `*` asks for a prefix, plural and singular forms find each other,
  and terms are OR-joined so an agent can add synonyms. The output carries a
  `retrieval` block. A trigram substring list is available with
  `--lists words,trigram` but is not part of the default fusion.
- Classic `kb.py search` compiles the query the same way and orders FTS5
  matches by BM25; a trailing `?` or a `-` no longer drops the search to a
  `LIKE` of the whole string. `kb.py` JSON output escapes non-ASCII characters,
  so a piped Windows console no longer fails on them.
- The `kb-wiki-vnext` and `kb-wiki-maintainer` skills tell the agent to widen
  `lookup` and `kb.py search` queries with the words a record might use: the
  original words first, at most six in total, synonyms in the language of the
  records before translations, and no broad words when the question asks for
  one item or the most recent one.
- Release lines: Python package `0.2.0`, catalog `0.3.11`, kb-lifecycle
  `0.2.5`, kb-wiki-vnext `0.2.0`, session-gate `0.2.8`, vNext runtime `0.2.0`,
  stand-alone product `0.2.0-rc.4`.

### Added
- Optional dense list that ranks by meaning (`kb_next.py dense-index`), fused
  by RRF with the word list when `retrieval.dense.enabled` is `true`. It needs
  the extra `pip install model2vec==0.10.0`; the default install stays
  stdlib-only and never imports it. Models are pinned by revision and SHA-256
  (`potion-base-32M` for English, `potion-multilingual-128M` with Portuguese)
  and cached outside the project; the derived index under `.kb-next/index/`
  ignores itself in Git. On LongMemEval M (2024 file), session recall@5 and
  recall@10 with `potion-base-32M` reach the dense retriever of the paper's
  Table 9 (0.764 and 0.864 against 0.762 and 0.862, paper-era mean) with no
  margin, inside the measurement's own calibration error (about 2 points).
  A cold command-line lookup with the dense list takes about 3 s more with
  `potion-base-32M` and about 11 s more with `potion-multilingual-128M`,
  almost all of it loading the model.
- Proposal commands (`semantic-lookup`, `curation-proposal`,
  `semantic-hygiene`, `filing-proposal`, `wiki-synthesis-plan`) accept the
  same `--actor` pair to record who generated a proposal; LLM manifests no
  longer carry a fixed placeholder actor.

## [0.1.5] - 2026-09-23

### Fixed
- KB + Wiki now has a flow: `activation-wizard --choice kb-wiki` enables the
  classic wiki in `.kb/kb.config.json` (keeping every other key), turns on
  lifecycle wiki sync, runs the first `wiki-sync`, and records the steps in
  `.kb-next/operations.jsonl`. Re-activation merges instead of rewriting the
  vNext config.
- The scaffold enables `run_wiki_sync` on record-filed, source-ingest,
  session-end and scheduled-maintenance, and the shipped `kb.py` fires those
  lifecycle hooks after `create`, `file`, `supersede`, `resolve`, `ingest` and
  `init --seed`; pages publish without a manual `wiki-sync`.
- `wiki.enabled: true` means on in every activation mode; `wiki-check` reports
  publishable and held-back pages with reasons.
- Commands other than `init` fail closed when `.kb/kb.db` is missing; a linked
  Git worktree uses the main worktree KB; read commands never write `kb.db`;
  source paths are stored KB-relative (`source-relink` migrates older KBs).
- Plugin commands cite only paths that exist; SessionStart hooks no longer
  give conflicting default reads; `lookup` accepts `--domain`.
- `kb-factory vnext-init` defaults to `kb-alone`, like the plugin commands.
- Re-running `activation-wizard` keeps a curated `.kb-next/memory/NOW.md` (only
  a generated template is regenerated) and, for the same mode, keeps the
  recorded decision date and rationale (adds `reconfirmed_at`).

### Added
- `kb.py init --name --slug --domains --id-prefix`, project-prefixed record
  IDs, `kb.py wiki-config`, `kb.py source-relink`.
- vNext runtime `install-classic`, `upgrade-classic`, `wiki-draft-status`,
  `session-hint`; plugin command `vnext-wiki-drafts`.
- `kb-factory init --name/--slug/--domains/--id-prefix/--no-seed`.

### Removed
- Every reference to the retired CASE workflow framework: Session Gate no
  longer detects or routes to CASE surfaces, and plugin descriptions, tags,
  the scaffold seed and the KB skill no longer mention it.

### Changed
- Release lines: Python package `0.1.5`, catalog `0.3.9`, kb-lifecycle
  `0.2.4`, kb-wiki-vnext `0.1.10`, session-gate `0.2.8`, vNext runtime `0.1.8`,
  stand-alone product `0.2.0-rc.3`.

## [0.1.4] - 2026-07-19

### Added
- Published the first hash-bound private-to-public release transformation. The
  public tree records private source commit
  `6c8873797add4f068b7635403c9b18d478442315`, public baseline
  `256b217aafac0dbe6663af9edfb70b0d66761bc4`, and policy
  `2026-07-19.3`; private state, workbench files, personal paths, and credentials
  are excluded before the public checkout is changed.
- Added the public KB/Wiki vNext `0.2.0-rc.2` product bundle and platform
  artifacts for Codex, Claude Code, and Claude Cowork.

### Changed
- Coordinated the independently versioned release surfaces: Python package
  `0.1.4`, catalog release line `0.3.8`, kb-lifecycle `0.2.3`, kb-wiki-vnext `0.1.9`,
  session-gate `0.2.7`, and bundled vNext runtime `0.1.7`.
- The supported Python install for this release is the wheel attached to the
  GitHub `v0.1.4` release. PyPI remains an optional future channel and is not
  claimed as available.
- Documentation brought fully in line with v0.1.2: pip-first install/upgrade
  (`pip install kb-factory` → `kb-factory init` / `update`) across
  getting-started, installation, the User Guide and recipes (copy-scaffold kept
  as the no-pip fallback; the no-code track stays zero-CLI, now backed by the
  plugin's bundled scaffold); `harden` / read-only `raw-query` covered in
  concepts, commands, troubleshooting and the glossaries; `merit-evaluation.md`
  added to the docs maps; README "Project status" updated to v0.1.2; and the
  developer / releasing / architecture / CONTRIBUTING docs now document the pip
  package, the scaffold-mirror sync tool + parity test, and the PyPI
  build/publish flow.
- Bumped plugin patch versions so the v0.1.2 plugin changes (Apache license
  metadata, the `kb-wiki-maintainer` "Bootstrapping a new project" guidance, the
  bundled `.kb/` scaffold) propagate cleanly via `marketplace update` +
  reinstall: **kb-lifecycle 0.2.1→0.2.2, session-gate 0.2.4→0.2.5, kb-wiki-vnext
  0.1.3→0.1.4** (marketplace catalog 0.3.1→0.3.2). Corrected the Claude Code
  update commands in `installation.md`. Current Claude Code supports
  `claude plugin update`; restart is required to apply the downloaded version.

### Fixed
- **vNext runtime now ships via the marketplace too**: the engine is committed at
  `plugins/kb-wiki-vnext/runtime/kb_next.py` (kept byte-identical to the master by
  the parity gate + `sync_vnext_runtime.py`), so a marketplace install (repo
  source, no build step) carries it — not only the built ZIP. The packager picks
  up the committed copy via `iter_files`; build-time injection was removed to
  avoid a duplicate entry. Bumped **kb-wiki-vnext 0.1.7→0.1.8** (marketplace
  catalog 0.3.6→0.3.7).
- **Durable vNext runtime distribution (all channels)**: the vNext engine
  (`kb_next.py`) now reaches consumer projects through every channel instead of
  none. The single master `core/versions/kb-wiki-vnext/runtime/kb_next.py` is
  (a) injected into every plugin ZIP at `runtime/kb_next.py` (build-time, no
  committed copy; locked by a required-entry guard + content-identity test),
  (b) vendored into the pip package under `_scaffold_vnext/` with new
  `kb-factory vnext-init` / `vnext-update` console commands, and (c) installed
  into `.kb-next/runtime/kb_next.py` by a new runtime `bootstrap` subcommand the
  activate/init commands run before `activation-wizard` — killing the
  chicken-and-egg where activation required the very runtime a consumer lacked.
  Added `tools/sync_vnext_runtime.py` + byte-identity parity wired into the
  pre-commit gate and CI so the copies can never drift. Bumped
  **kb-wiki-vnext 0.1.6→0.1.7** (marketplace catalog 0.3.5→0.3.6) and **pip
  kb-factory 0.1.2→0.1.3**.
- **Runtime portability across all vNext surfaces**: the `vnext-session-start`
  command already resolved the runtime via a ladder; extended the same ladder to
  the 7 remaining kb-wiki-vnext commands and to the non-command surfaces (hooks
  echo, SKILL, `AGENTS.md`, README, Codex `defaultPrompt`), plus Session Gate's
  vNext routing docs. Surfaces now resolve `.kb-next/runtime/kb_next.py`, else the
  authoring-monorepo path, else fall back to classic
  `python .kb/kb.py lifecycle session-start --json`, instead of hardcoding
  `core/versions/...` (which failed with "Exit 2" in consumer projects).
  Generalized the packaging disambiguation test accordingly. Bumped
  **kb-wiki-vnext 0.1.5→0.1.6, session-gate 0.2.5→0.2.6** (marketplace catalog
  0.3.3→0.3.5).
- **kb-wiki-vnext failed to load in Claude Code** ("duplicate hooks file"): its
  Claude manifest declared `hooks: ./hooks/hooks.json`, which Claude Code already
  auto-loads. Removed the redundant declaration; bumped kb-wiki-vnext 0.1.4→0.1.5
  (catalog 0.3.2→0.3.3) so the fix propagates. Added a regression test
  (`test_claude_manifests_do_not_redeclare_standard_hooks`).
- Corrected the kb-lifecycle README's **Codex** section: the Codex CLI has no
  plugin/marketplace command, so the integration is the `~/.codex/skills/` skill +
  the pip/`.kb.py` engine (+ optional `AGENTS.md`), not a repo-local marketplace.

## [0.1.2] - 2026-06-16

Acted on an external technical review (validated point-by-point against the code).

### Added
- **`pip install kb-factory`** — the engine is now pip-installable with a
  `kb-factory` CLI: `kb-factory init` scaffolds a project's `.kb/` and
  initializes the store; `kb-factory update` refreshes the vendored runtime to
  the installed version (preserving your data), so core fixes can propagate.
- The **kb-lifecycle plugin now bundles the `.kb/` scaffold** (under `scaffold/`),
  so an agent can set up a project KB without a repo checkout.
- Opt-in **append-only database hardening** — `kb.py harden` installs SQLite
  triggers that block direct content `UPDATE` and `DELETE` of
  `records` / `audit_log` / `operations`, turning the CLI's interface discipline
  into a true database invariant (`harden --off` removes them). `doctor` reports
  the state.
- A published **`docs/merit-evaluation.md`** — the adversarial/hostile/moderated
  merit debate that `docs/comparison.md` references (fixes the only broken link).

### Changed
- `raw-query` is now **read-only by default** (`PRAGMA query_only`); pass
  `--allow-write` to deliberately issue writes.
- Docs state the integrity model precisely ("append-only **by interface
  discipline**", with the opt-in DB enforcement via `harden`); the wiki layer is
  documented as optional/off-by-default; the lexical-search trade-off and a
  possible future *opt-in* embeddings adapter are spelled out; the README "Use
  this if" sharpens the audience (regulated / long-lived / high-context-rotation).

## [0.1.1] - 2026-06-16

### Added
- Conversational/chat usage docs: `docs/agent-sessions.md` (using KB Factory in a
  Claude Code / Cowork session) and `docs/plugins.md` (the three plugins — what
  each does, their differences, and how to combine them).
- Slash-command coverage in `docs/commands.md`; a chat-first track in
  `docs/getting-started.md`; `kb-wiki-vnext` install + "what becomes available"
  in `docs/installation.md`; a chat/plugin FAQ in `docs/troubleshooting.md`.
- A dedicated end-user **User Guide** under `docs/guide/` (index, what-and-why,
  install-and-first-session, everyday-use, how-it-works, plugins, recipes,
  troubleshooting): task-oriented, accessible-by-default, with technical/CLI
  detail in collapsible blocks; surfaced from the README.
- A **no-code track** for non-developers under `docs/guide/no-code/` (index,
  what-this-is, first-session, words, when-stuck): a zero-command, Cowork-first
  walkthrough with confirmation checkpoints, a plain-language glossary, and a
  non-technical FAQ.
- User-doc discoverability: a chat-first "start here" callout atop the `README`,
  a `docs/` landing page (`docs/README.md`) that routes by audience, a
  "Using it (start here)" block in each of the three plugin READMEs, and a docs
  pointer added to the marketplace/plugin descriptions.

### Fixed
- Corrected a stale `session-gate` command name in the marketplace description
  (`/gate-session-start` / `/gate-session-end`, not `/session-start`).
- Set the plugin manifests' `license` to **Apache-2.0** (matching the project
  `LICENSE`); they previously declared MIT.
- Synced the marketplace plugin versions to the canonical plugin manifests
  (kb-lifecycle 0.2.1, session-gate 0.2.4, kb-wiki-vnext 0.1.3).
- Made the test suite stdlib-only again: a vNext runtime test parsed
  generated-page frontmatter with PyYAML, which broke CI in `pytest`-only
  environments. It now parses with the standard library, so the suite needs no
  third-party test dependency.
- Restored real **Python 3.8** support: the vNext runtime used
  `Path.is_relative_to` (added in 3.9), so the documented "3.8+" claim failed on
  3.8. Replaced it with a 3.8-safe containment check; the full CI matrix
  (Linux/macOS/Windows × Python 3.8/3.11/3.13) now passes.

## [0.1.0] - 2026-06-16

First public release of KB Factory — the initial open-source extraction from a
private authoring workspace.

### Added
- Apache-2.0 `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, and this changelog.
- `ACKNOWLEDGMENTS.md` crediting design influences (Andrej Karpathy;
  Carlos Perez / @IntuitMachine).
- User & developer documentation under `docs/` (getting-started, installation,
  commands, concepts, use-cases, troubleshooting, architecture, development,
  releasing) plus a sourced competitive comparison and a provenance/continuity
  note.
- Self-cleaning wiki sync, a cleanliness gate (`tools/gate.py` + pre-commit
  hook), and a cross-platform CI matrix (Linux/macOS/Windows × Python
  3.8/3.11/3.13).

### Changed
- Removed internal/private references (cross-repo paths, a private compliance
  artifact, personal contact details) from the published tree.
- Neutralized internal-framework vocabulary in code and documentation.

### Notes
- The core runtime is **standard-library only** (Python + SQLite); no
  third-party runtime dependencies.
- Knowledge is **append-only**: records are superseded, never silently
  overwritten.
