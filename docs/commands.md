# Command Reference

This is the authoritative reference for the KB Factory CLI. Every command runs
through one entry point:

```bash
python .kb/kb.py <command> [options]
```

It is stdlib-only (Python 3.8+ and SQLite with FTS5) — no service, no API key,
works offline. Records are **typed** and **append-only**: you supersede, you
never overwrite. For the concepts behind the model, see the
[README](../README.md) and [provenance & continuity](provenance-and-continuity.md).
For how KB Factory compares to other memory systems, see
[comparison](comparison.md).

> **Conventions.** Most read commands accept `--json` for machine-readable
> output; the examples below show the human-readable form. Commands are
> cross-platform — on Windows use `python`, on macOS/Linux use `python3` if
> that's how your interpreter is named. `<record_id>` and `<source_id>` are the
> identifiers printed when records and sources are created.

---

## The core commands

These five are the entire day-to-day discipline. If you only learn these, you
can use KB Factory fully.

| Command | What it does |
|---|---|
| [`init`](#init) | Create the SQLite store in `.kb/` |
| [`create`](#create) | File a new typed record |
| [`search`](#search) | Lexical full-text search (SQLite FTS5) |
| [`supersede`](#supersede) | Replace a record when its *meaning* changes (old one is kept + linked) |
| [`lifecycle session-start`](#lifecycle) | Bootstrap a session, then read `.kb/memory/NOW.md` |

The **five categories** are `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`,
`APRENDIZADO` (decision, assumption, fact, open-item, learning). The **three
tiers** are `HOT` (always surfaced at session start), `WARM` (the default), and
`COLD` (archived). Use [`update`](#update) only for *routing metadata* (tier,
tags, review dates); when *meaning* changes, use [`supersede`](#supersede).

> **Getting the CLI:** install the `v0.3.0` GitHub release wheel (see
> [installation.md](installation.md)), then `kb-factory init` scaffolds
> a project's `.kb/` (and `kb-factory update` refreshes it later). After that, the
> commands on this page run as `python .kb/kb.py <command>` from the project root.
> See [installation.md](installation.md).

---

## Slash commands (in a chat session)

If you drive KB Factory through a [plugin](plugins.md) in Claude Code or Cowork,
you use **slash commands** (and an auto-triggering skill) instead of typing the
CLI — but they run exactly the CLI verbs documented on this page. See
[agent-sessions.md](agent-sessions.md) for the workflow.

- **kb-lifecycle** — no slash commands; its `kb-wiki-maintainer` skill auto-runs
  session-start, `ingest`, `create`/`file`, `search`, and `wiki-sync` when you
  ask in plain language.
- **kb-wiki-vnext** — 12 commands:

  | Command(s) | Does |
  |---|---|
  | `/vnext-session-start`, `/vnext-session-end` | start a thin session / close it |
  | `/new-project-wizard`, `/new-project-init-kb-alone`, `/new-project-init-kb-wiki`, `/new-project-verify-install` | bootstrap a new project |
  | `/existing-project-diagnose`, `/existing-project-activate-vnext`, `/existing-project-configure-vnext`, `/existing-project-verify-install`, `/existing-project-upgrade-vnext`, `/existing-project-rollback-vnext` | set up / migrate an existing project |

- **session-gate** — `/gate-session-start`, `/gate-session-end` (Cowork session
  boundaries; routes to whichever KB plugins are present).

Full per-plugin detail and when to use each: [plugins.md](plugins.md).

---

## Records

The typed knowledge store. This is the canonical group.

### `init`

```bash
python .kb/kb.py init [--seed <path>]
```

Creates the SQLite store and schema in `.kb/`. Run once per project. `--seed`
optionally loads an initial set of records from a file.

### `create`

Files a new record. **Core command.**

```bash
python .kb/kb.py create \
  --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no external services." \
  --tier HOT
```

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--category` | yes | — | `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`, `APRENDIZADO` |
| `--domain` | yes | — | Free-text grouping, e.g. `architecture`, `ops` |
| `--title` | yes | — | Short, unique-ish title (used for dedupe) |
| `--content` | yes | — | The record body |
| `--tier` | no | `WARM` | `HOT` / `WARM` / `COLD` |
| `--status` | no | `ATIVO` | Record status |
| `--source` | no | `manual` | Free-text origin label |
| `--source-id` | no | — | Link to an ingested source (see [Sources](#sources)) |
| `--tags` | no | — | Comma-separated tags |
| `--confidence` | no | `0.8` | Float 0–1 |
| `--tier-reason` | no | — | Why this tier |
| `--review-after` | no | — | Date after which to revisit (`YYYY-MM-DD`) |
| `--valid-until` | no | — | Expiry date for assumptions (`YYYY-MM-DD`) |
| `--observed-at` | no | — | When the fact was observed |
| `--id` | no | auto | Override the generated record id |
| `--json` | no | — | Machine-readable output |

### `search`

Lexical full-text search over the store (SQLite FTS5). **Core command.**

```bash
python .kb/kb.py search "storage"
python .kb/kb.py search "auth" --category DECISAO --domain security --limit 10
```

Filters: `--category`, `--domain`, `--status`, `--tier`, `--limit` (default 20),
`--json`.

> Search is **lexical**, not semantic — it matches words and phrases, not
> meaning. There is no embedding or vector recall. If you need paraphrase or
> relational recall, see the alternatives in [comparison](comparison.md).

### `get`

```bash
python .kb/kb.py get <record_id> [--json]
```

Prints a single record by id, including its supersession links.

### `list`

```bash
python .kb/kb.py list --tier HOT --limit 20
```

Lists records with optional filters: `--category`, `--domain`, `--status`,
`--tier`, `--limit` (default 20), `--json`.

### `update`

Changes **routing metadata only** — never the meaning of a record.

```bash
python .kb/kb.py update <record_id> --tier COLD --tier-reason "no longer active"
```

Flags: `--tier`, `--tier-reason`, `--review-after`, `--valid-until`,
`--confidence`, `--source`, `--tags`, `--json`. If the *meaning* changed, use
`supersede` instead.

### `supersede`

Replaces a record when its meaning changes. **Core command.** The old record is
**retained and linked** — this is the append-only discipline that lets you
reconstruct past beliefs.

```bash
python .kb/kb.py supersede <record_id> \
  --title "Use SQLite + FTS5" \
  --content "Added full-text search."
```

Flags: `--title`, `--content`, `--tier`, `--tier-reason`, `--review-after`,
`--valid-until`, `--source`, `--source-id`, `--tags`, `--confidence`,
`--new-id`, `--json`.

### `resolve`

Closes a `PENDENCIA` (open item) with a required note.

```bash
python .kb/kb.py resolve <record_id> --notes "Shipped in #421"
```

### `pending`

Lists open `PENDENCIA` records.

```bash
python .kb/kb.py pending [--domain <d>] [--limit 20] [--json]
```

### `stats`

```bash
python .kb/kb.py stats [--json]
```

Summary counts by category, tier, and status.

---

## Sources

Raw inputs you ingest, hashed and retained, so records can cite where they came
from. This is the provenance backbone described in
[provenance & continuity](provenance-and-continuity.md).

### `ingest`

Ingests a file as an immutable, hashed source.

```bash
python .kb/kb.py ingest path/to/notes.md --domain research --tags "spec,api"
```

Flags: `--source-id`, `--domain`, `--tags`, `--notes`, `--no-auto-lifecycle`,
`--json`. Once ingested, link records to it with `create --source-id <id>`.

### `sources`

```bash
python .kb/kb.py sources [--domain <d>] [--limit 20] [--json]
```

Lists ingested sources.

### `source-info` / `source-content`

```bash
python .kb/kb.py source-info <source_id> [--json]
python .kb/kb.py source-content <source_id> [--json]
```

Show a source's metadata, or its stored raw content.

### `source-update`

```bash
python .kb/kb.py source-update <source_id> --domain ops --tags "runbook" --notes "..."
```

Updates a source's routing metadata (`--domain`, `--tags`, `--notes`, `--json`).

### `source-status` / `source-verify`

Audit coverage and integrity of sources.

```bash
python .kb/kb.py source-status --uncovered      # sources with no records filed from them
python .kb/kb.py source-status --missing-file   # sources whose stored file is gone
python .kb/kb.py source-status --hash-drift      # sources whose content hash changed
python .kb/kb.py source-verify --json            # full integrity check
```

`source-status` also accepts `--domain`. These are read-only.

---

## Wiki

An optional, derived human-readable wiki generated *from* the records. The wiki
is a projection, not a second source of truth — the SQLite store remains
canonical.

| Command | Purpose |
|---|---|
| `wiki-check` | Report wiki configuration / readiness (`--json`) |
| `wiki-candidates` | Records eligible for wiki pages (`--domain`, `--json`) |
| `wiki-sync` | Regenerate wiki pages from records (`--domain`, `--force`, `--json`) |
| `wiki-lint` | Lint generated wiki pages (`--json`) |
| `wiki-pages` | List wiki pages with filters (see below) |

```bash
python .kb/kb.py wiki-sync --domain architecture
python .kb/kb.py wiki-pages --state live --domain architecture --limit 50
```

`wiki-pages` filters: `--state`, `--page-class`, `--domain`, `--page-type`,
`--min-confidence`, `--limit` (default 50), `--json`. `wiki-sync --force`
regenerates even when the wiki is disabled.

---

## Lifecycle

Bootstraps and closes sessions, and bundles maintenance into named events.

### `lifecycle`

```bash
python .kb/kb.py lifecycle <event> [options]
```

Events: `session-start`, `source-ingest`, `record-filed`, `session-end`,
`scheduled-maintenance`.

**Session start is a core command.** At the start of an agent session:

```bash
python .kb/kb.py lifecycle session-start --json
# then read .kb/memory/NOW.md  (the thin, always-loaded context)
```

`NOW.md` is the cheap, always-loaded surface; `.kb/memory/HOT.md` and
`.kb/memory/INDEX.md` are loaded on demand. At the end of a session:

```bash
python .kb/kb.py lifecycle session-end --json
```

Options (apply to the relevant events): `--domain`, `--refresh-exports`,
`--apply-demotions`, `--apply-cold-demotions`, `--prune-snapshots`,
`--sync-wiki`, `--force-wiki-sync`, `--json`. For example, scheduled
maintenance that lets stale HOT records fall back:

```bash
python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json
```

---

## Advanced: maintenance & integrity

These keep the store healthy. They are **mechanical, not semantic** — they
operate on exact rules (lowercased-title dedupe, date-based tier demotion,
integrity checks), and they never merge records by *meaning*. Deciding that two
differently-worded records say the same thing, and superseding accordingly, is
the operator's (or the agent's) job, done with `supersede`.

### `doctor`

```bash
python .kb/kb.py doctor [--json]
```

Schema and integrity check (FTS index, links, store health). Run it if search or
schema behaves unexpectedly. The JSON output includes `append_only_hardening`
(`enabled`/`disabled`).

### `harden`

```bash
python .kb/kb.py harden [--off] [--json]
```

Opt in to **database-level** append-only enforcement. Installs SQLite triggers
that block direct `UPDATE` of a record's title/content and direct `DELETE` of
`records` / `audit_log` / `operations` — turning the CLI's interface discipline
into a real invariant that even a direct SQLite session can't bypass. The normal
`supersede` / `resolve` / `update` workflow keeps working (those change only
status/tier/links, never content). `--off` removes the triggers. See the
[integrity model](concepts.md#integrity-model-how-append-only-is-enforced).

### `consolidate`

```bash
python .kb/kb.py consolidate [--apply-demotions]
```

Reports exact-title duplicate groups and refreshes exports. With
`--apply-demotions`, it also demotes HOT records whose `--review-after` date has
elapsed (to WARM). It does **not** merge or supersede anything semantically —
it only flags exact-title duplicates for you to act on.

### `audit-tiers`

```bash
python .kb/kb.py audit-tiers [--json]
```

Reports the HOT budget, HOT records over the limit, stale HOT records, and
expired assumptions (`PREMISSA` past `--valid-until`).

### `hygiene-audit`

```bash
python .kb/kb.py hygiene-audit [--json]
```

Read-only. Groups records into actionable buckets — keep-HOT, demote-candidate,
supersede-or-merge-candidate, resolve-candidate, and items needing owner review
— as *recommendations*. It changes nothing; you decide and apply with `update`,
`supersede`, or `resolve`.

### `prune-snapshots`

```bash
python .kb/kb.py prune-snapshots --keep-last-n 5 [--dry-run] [--json]
```

Keeps the most recent N wiki snapshots per live page and removes older ones.
`--dry-run` shows the plan without deleting.

---

## Advanced: operation log & data access

### `oplog`

The append-only operation log — who changed what, when, and why. This is what
makes the audit trail reconstructable.

```bash
python .kb/kb.py oplog [--category <op>] [--limit 20] [--json]
```

### `export`

```bash
python .kb/kb.py export
```

Regenerates the derived export surfaces (e.g. context packs). Note: surfaces for
Cowork / claude.ai are **point-in-time exports**, not a live sync — regenerate
them when the store changes or they will go stale.

### `bulk-import`

```bash
python .kb/kb.py bulk-import path/to/records.jsonl
```

Imports many records from a file in one pass.

### `raw-query`

```bash
python .kb/kb.py raw-query "SELECT category, COUNT(*) FROM records GROUP BY category"
```

Runs a SQL query against the store directly, for inspection and reporting;
prefer the typed commands above for routine work. **Read-only by default** — the
connection is opened with `PRAGMA query_only`, so a stray `UPDATE`/`DELETE` is
rejected. Pass `--allow-write` only if you deliberately need to issue a write.

---

## Filing helpers

Convenience commands for agents that file records as part of answering,
analyzing, or synthesizing. They wrap `create` with a `--filing-type`
(`answer`, `analysis`, `synthesis`) and matching status reports. Most users do
not need these and can stick to `create`.

| Command | Purpose |
|---|---|
| `file --filing-type <answer\|analysis\|synthesis>` | File a record tagged with how it was produced (same flags as `create`, plus `--no-auto-lifecycle`) |
| `filing-status` | Report filing activity by domain (`--domain`, `--json`) |
| `filing-policy` | Show the active filing policy (`--json`) |
| `analysis-status` | Coverage of analysis filings (`--domain`, `--json`) |
| `summarize-status` | Summarization coverage by domain (`--domain`, `--json`) |

---

## Not the right tool?

If you don't need an auditable belief *history* — typed records, supersession,
and source provenance — then `CLAUDE.md` plus your agent's built-in memory is
the simpler, correct choice. KB Factory earns its keep only when reconstructing
*what the project believed and what overturned it* matters. See
[comparison](comparison.md) for an honest breakdown.
