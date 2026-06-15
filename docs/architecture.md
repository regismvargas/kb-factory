# Architecture

This page is for developers who want to understand how KB Factory is put
together before reading or contributing to the runtime. For the user-facing
model see [provenance & continuity](provenance-and-continuity.md); for the
command surface see [commands](commands.md).

KB Factory runs on nothing but the **Python standard library and SQLite (with
FTS5)**. There is no service, no vector store, and no network dependency. A
project's knowledge lives in one directory — `.kb/` — that backs up as a single
SQLite file plus plain Markdown.

## The layered model

Knowledge flows in one direction: from immutable raw input, into canonical typed
records, out to derived surfaces an agent reads. Nothing downstream is
canonical, and nothing downstream can silently mutate what is.

```
sources  →  typed records  →  derived surfaces
  │            (SQLite)         ├─ NOW.md / HOT.md / INDEX.md   (session context)
  │              │              ├─ wiki pages                   (machine + human)
  │              │              └─ exports / context packs      (Cowork, claude.ai)
  │              └─ canonical, typed, append-only, FTS5-indexed
  └─ raw immutable input (ingested + hashed)
```

1. **Sources** — raw evidence, ingested and content-hashed. Immutable. A record
   can point back to the source it came from, and source-verification detects
   when a file drifts from its recorded hash.
2. **Typed records** — the canonical layer, stored in SQLite. Every record has a
   category, a domain, a tier, status, timestamps, and (optionally) a source
   link and a `supersedes_id`/`replacement_id` chain. This is the only layer that
   is authoritative.
3. **Session surfaces** — `NOW.md` (thin, always loaded at session start),
   `HOT.md` (the active working set, on demand), and `INDEX.md` (the broad map,
   on demand). These are *derived* from the records: `NOW`/`HOT` are bounded so
   the always-loaded context stays cheap in tokens.
4. **Wiki surfaces** *(optional)* — a machine wiki (granular structured memory
   for agents) and a human wiki (narrative docs for onboarding and audit).
   Neither is canonical; both are regenerated from records and carry citation
   blocks and stale checks.
5. **Exports / context packs** — point-in-time Markdown bundles for surfaces that
   can't read the SQLite store directly, such as Cowork and claude.ai. These are
   **snapshots, not a live sync**, and go stale until regenerated.

Because every surface is derived from the records, you can always trace a line in
`NOW.md`, a wiki page, or an export back to the record — and the record back to
its source.

## The core data model

- **Categories** — `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`, `APRENDIZADO`
  (decision, assumption, fact, open-item, learning).
- **Tiers** — `HOT` / `WARM` / `COLD`, which control how aggressively a record is
  surfaced. `HOT` records appear in the always-loaded context.
- **Append-only versioning** — records are never overwritten. `update` changes
  only routing metadata (tier, tags, review dates). When the *meaning* changes
  you `supersede`: the old record is retained and linked to its replacement, so
  the belief history is reconstructable.

## Runtime module map

The runtime lives in `core/runtime/` as stdlib-only modules. The shipped
`.kb/kb.py` is a thin entrypoint that wires these together and presents the CLI —
the CLI surface is the compatibility contract, so internal refactors must not
change it.

| Module | Responsibility |
|---|---|
| `paths.py` | Resolve `KB_ROOT`, the DB path, config path, and derived directories. |
| `config.py` | Load and merge `kb.config.json` with defaults. |
| `constants.py` | Canonical categories, tiers, statuses, and lifecycle defaults. |
| `db.py` | Open the SQLite connection. |
| `schema.py` | Bootstrap tables and the FTS5 index; schema versioning. |
| `helpers.py` | Shared utilities — timestamps, row→dict, FTS upsert, action logging. |
| `records.py` | The record lifecycle: `init`, `create`, `get`, `list`, `update`, `supersede`, `resolve`, `pending`, `stats`, plus validation and inserts. |
| `search.py` *(roadmap)* | FTS5 query + filters; currently implemented inside `records.py`. |
| `filing_policy.py` | Advisory policy for `file` — which categories/sources/confidence a filing type requires. |
| `sources.py` | Ingest, register, hash, verify, and report on raw sources and their coverage. |
| `exports.py` | Build the derived surfaces: `NOW`, `HOT`, `INDEX`, topics, and the Cowork / claude.ai context packs. |
| `lifecycle.py` | Session and maintenance events — `session-start`, `session-end`, `record-filed`, etc. |
| `maintenance.py` | Mechanical governance: `consolidate`, `audit-tiers`, `hygiene-audit`, tier demotions, snapshot pruning. |
| `doctor.py` | Integrity, schema, and invariant checks. |
| `oplog.py` | Append and read the operations log (what changed, when, why). |
| `wiki.py` | Wiki configuration and state — whether the wiki is active and which page types it covers. |
| `wiki_candidates.py` | Propose which wiki pages should exist from current records. |
| `wiki_materialization.py` | Render, hash, lint, and reconcile wiki pages; mark stale pages; capture snapshots. |
| `cli.py` | Argument parser and subcommand wiring. |

> **Note on the roadmap row.** `core/README.md` describes a planned split that
> extracts a dedicated `search.py` (and others) from the historical monolith.
> Search is real and built on FTS5 today; it simply lives in `records.py` until
> that extraction lands. The external CLI behavior does not change.

## `.kb` (canonical) vs. `.kb-next` (operational)

A project can carry two sibling directories:

- **`.kb/`** is the **canonical store** — the SQLite database (`kb.db`), the
  scaffolded runtime, the typed records, and the derived `memory/`, `wiki/`, and
  `exports/` surfaces. This is the source of truth.
- **`.kb-next/`** is **operational state** for the lifecycle harness layered
  *around* the canonical store. It holds an append-only operations ledger
  (`operations.jsonl`), the harness configuration, activation decisions, and
  external-adapter scaffolding (e.g. Obsidian/static-Markdown).

The boundary is a safety property: the harness in `.kb-next/` treats `.kb/` as
the authority and never mutates it directly. Lifecycle, sync, and export events
are recorded as a lineage in `.kb-next/operations.jsonl`, but durable knowledge
only ever changes by creating or superseding a record in `.kb/` through the CLI.

If you only need a knowledge base, you only need `.kb/`. `.kb-next/` exists for
projects running the fuller session/wiki/adapter lifecycle.

## LLM-curated, mechanically-governed

KB Factory deliberately splits responsibility between the LLM and the runtime.
Getting this split right is what keeps the store both useful and honest.

**The LLM does the semantic work.** Deciding *what* to file, judging that two
records mean the same thing, recognizing that a new decision overturns an old
one, and synthesizing records into an answer or a wiki page — these require
meaning, and the model does them. The model proposes; it does not get to silently
rewrite history.

**The runtime does the mechanical governance.** Persistence, schema validation,
provenance links, the append-only/supersession invariants, integrity checks, and
the operations log are deterministic code. In particular:

- **Search is lexical.** It is SQLite FTS5, not embeddings. There is no semantic
  recall in the runtime; paraphrased or relational lookup is the LLM's job on top
  of FTS results.
- **`consolidate` is mechanical, not semantic.** It does exact lowercased-title
  dedupe, date-based tier demotion, and integrity housekeeping. It will **not**
  merge two records that *mean* the same thing in different words. The semantic
  path is explicit: the LLM uses lookup to find candidates, proposes a
  merge/supersession, the runtime validates it, and only then is it applied.

The rule is simple: **mechanical code can narrow inputs and validate outputs, but
semantic judgment belongs to the LLM, and the canonical store only changes
through a validated record create/supersede.** No feature claims semantic
curation when it is really regex matching or tag lookup.

For projects that don't need an auditable belief *history*, this whole apparatus
is overkill — `CLAUDE.md` plus your agent's built-in memory is the simpler,
correct choice. See the [comparison](comparison.md) for where each tool fits.
