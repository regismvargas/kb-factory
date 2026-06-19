# Concepts & glossary

This page explains KB Factory's model from scratch — no prior context assumed.
Read it once and the [commands](commands.md) and
[comparison](comparison.md) pages will make sense.

If you only want lightweight project notes and don't need an auditable *history*
of what your project believed and why, you don't need any of this:
`CLAUDE.md` plus your agent's built-in memory is the simpler, correct choice.
KB Factory earns its keep when you want every superseded decision to stay on the
record, linked to its source and to whatever replaced it.

## The one idea

Most agent memory is **consolidative**: it keeps improving the current snapshot
by overwriting the past. KB Factory is **append-only by design**. Knowledge is
filed as discrete, typed records, and when a record's meaning changes you do not
edit it — you *supersede* it. The old record stays, linked to the new one and to
the source it came from. The result is a belief history: you can reconstruct what
the project assumed at any past point and exactly what overturned it.

One project gets one knowledge base, stored as a single SQLite file under
`.kb/`. Every conversation and every agent (Claude Code, Cowork, Codex) reads
and writes that same canonical store.

## Typed records: the five categories

Knowledge is filed as **records**, and every record has a **category** that
describes the *nature* of the knowledge — not its subject. There are exactly
five, and they don't change per project:

| Category | English | Use it for |
|---|---|---|
| `DECISAO` | decision | A choice made, with its rationale. |
| `PREMISSA` | assumption | A hypothesis or assumption currently in use (can expire). |
| `FATO` | fact | Confirmed, verifiable information. |
| `PENDENCIA` | open-item | An open question that still needs resolution. |
| `APRENDIZADO` | learning | A pattern or lesson the project has internalized. |

Keeping facts separate from assumptions, and decisions separate from open items,
is what lets the agent reason about *confidence* — an assumption can age out; a
fact should be re-checkable against its source.

Beyond category, each record carries a **domain** (a project-defined workstream
like `architecture` or `billing` — pick 4 to 12), a **title**, **content**,
a **status**, a **tier**, a **source**, **tags**, and timestamps. The content —
the actual meaning of the record — is treated as **immutable**.

## Tiers: HOT / WARM / COLD

A record's **tier** is a *retrieval policy*, not a statement about how true or
important the knowledge is.

| Tier | Meaning |
|---|---|
| `HOT` | Should shape the start of every session — surfaced in the always-loaded context. |
| `WARM` | Retrievable on demand via search; the default home for most records. |
| `COLD` | History, archive, audit trail — never loaded unless you ask for it. |

Tier is one of the few things about a record you're allowed to change freely
(see update vs. supersede). Records drift downward over time: `consolidate`
demotes stale HOT/WARM records to colder tiers based on age, and `audit-tiers`
reports when the HOT layer has grown beyond what a session should carry.

## Update vs. supersede

This is the core discipline, and the line between the two operations is the
meaning of the record:

- **`update`** changes only **routing metadata** — tier, tags, review dates,
  confidence, source pointer. It never changes what the record *means*. Use it to
  promote a record to HOT, retag it, or extend an assumption's validity.
- **`supersede`** is for when the **meaning changes**. It creates a *new* record
  and links it back to the old one (`supersedes_id` / `replacement_id`); the old
  record is marked `SUPERSEDIDO` and kept forever. Nothing is overwritten.

So "we now use SQLite *and* FTS5" is a supersession of "we use SQLite"; bumping
that decision from WARM to HOT is an update. Open items have a third path:
`resolve` closes a `PENDENCIA` with resolution notes instead of superseding it.

The rule in one line: **never delete, never overwrite — supersede.**

## Integrity model: how "append-only" is enforced

Be precise about what "append-only" means here, because it's the heart of the
pitch. By default it is enforced by **interface discipline**: the CLI has no
delete verb, `update` refuses to touch title/content, and `supersede` only ever
*adds* a row. There is no command that destroys history. (Even `raw-query` is
read-only by default; it needs an explicit `--allow-write` to issue any write.)

What that does **not** mean: a determined user with direct SQLite access to the
file can still run `DELETE`/`UPDATE` and rewrite history — the discipline lives
in the application layer, not (by default) in the database. For most users that
is the right trade-off: zero ceremony, and the audit/operations logs still record
what the tool itself did.

If you want append-only to be a **true database invariant** — so that *nothing*,
not even a direct SQLite session, can edit a record's title/content or delete
records and the logs — opt in with:

```bash
python .kb/kb.py harden          # install the integrity triggers
python .kb/kb.py harden --off    # remove them
```

This installs SQLite triggers that `RAISE` on content `UPDATE` and on `DELETE` of
`records` / `audit_log` / `operations`, while leaving the normal
`supersede`/`resolve`/`update` workflow fully working (they only change
status/tier/links, never content). `doctor` reports whether hardening is on.

## Provenance: source → record → surface

Every record can point back to the **source** it came from, and every surface an
agent reads points back to the records behind it. The lineage runs in one
direction:

```
source  →  record  →  { wiki page | export / context pack | session surface }
   │          │                         │
   │          │                         └─ what an agent loads at session start
   │          └─ canonical, typed, versioned (SQLite + FTS5)
   └─ raw, immutable input (ingested and hashed)
```

Raw material is **ingested** (via `ingest`) and hashed, so the runtime can later
detect when a source on disk has drifted from what a record claims it said
(`source-status`, `source-verify`). Mutations append to an **operations log**,
so "who changed what, when, and why" is reconstructable. This is what makes the
belief history auditable rather than merely stored. For the full picture and its
verification status, see
[provenance-and-continuity](provenance-and-continuity.md).

## Search is lexical

Search is **lexical full-text search** over the SQLite FTS5 index — it matches
words and phrases, not meaning. There is no embedding model and no semantic
recall: a query for "auth" will not surface a record that only ever says
"login." Choose titles and content with the words a future search will use. If
you need paraphrase-tolerant or relational recall, KB Factory is the wrong tool
(see [comparison](comparison.md)).

## Thin always-loaded context: NOW / HOT / INDEX

The point of typed records and tiers is to keep the *always-loaded* layer small.
At session start an agent reads a thin set of generated Markdown files under
`.kb/memory/`, not the whole database:

| File | Role |
|---|---|
| `NOW.md` | The single thin entry point — read first, every session. |
| `HOT.md` | The current HOT records — the active working set, loaded on demand. |
| `INDEX.md` | A map of the broader KB — read only when you need the wider picture. |
| `topics/` | Short per-domain slices, pulled in when a domain is in play. |

These are **regenerated from the database** with `python .kb/kb.py export`; they
are projections of the canonical store, never a second source of truth. Bounding
this layer is what keeps continuity cheap in tokens.

## The optional wiki layer

On top of the records you can keep a **derived wiki** — human- and
machine-readable Markdown pages synthesized from canonical records
(`wiki-sync`, `wiki-pages`, and friends). The wiki is **derived and never
canonical**: it is a generated view for browsing and onboarding, governed by
the same provenance manifests as exports. If the records and the wiki ever
disagree, the records win. The wiki is entirely optional — a KB works fully
without it.

## Mechanical governance vs. the semantic path

This distinction matters, so it is stated plainly: **`consolidate` is
mechanical, not semantic.** It does three deterministic things — exact
lowercased-title deduplication, date-based tier demotion, and integrity
reconciliation. It does **not** read records for meaning, merge near-duplicates,
or judge which assumption a new fact overturns. `doctor` (integrity, schema,
invariants) and `audit-tiers` / `hygiene-audit` are the same kind of mechanical
checks.

The **semantic** work — recognizing that two differently-worded records say the
same thing, or that a new decision supersedes an old one — is done by the **LLM**
and then routed through governance: the agent uses semantic lookup, proposes a
merge or supersession with rationale and provenance, and the runtime validates
and applies it. The model curates; the runtime governs. Nothing semantic is
trusted without provenance and validation. (This is the "LLM-curated,
mechanically-governed" design.)

So when you read "consolidation" in KB Factory, read it as *mechanical hygiene*,
not *intelligent merging*. The intelligence lives in the proposal pipeline, not
in `consolidate`.

## The core loop

Putting it together, a normal session looks like:

1. **Start thin.** `lifecycle session-start --json`, then read `NOW.md`.
2. **Search before assuming.** Query the KB instead of trusting scrollback.
3. **File new knowledge** as typed records (`create`), each in its category.
4. **Supersede** when meaning changes; **update** for routing only; **resolve**
   open items.
5. **Regenerate** the thin surfaces (`export`) so the next session starts clean.

> **Advanced.** Beyond this core loop, the CLI exposes governance and
> maintenance operations — `ingest` and `source-verify` for provenance, the
> `wiki-*` family, `consolidate` / `doctor` / `audit-tiers` / `hygiene-audit`
> for hygiene, `oplog` for the audit trail, and the proposal/apply flow for
> LLM-curated changes. These are not part of the quickstart; see
> [commands](commands.md) for the full surface.

## Glossary

| Term | Definition |
|---|---|
| **Record** | A single typed unit of knowledge in the KB, with category, domain, title, content, status, tier, source, and timestamps. |
| **Category** | The *nature* of a record's knowledge: `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`, `APRENDIZADO`. |
| **Domain** | A project-defined workstream (4–12 per project) that groups records by subject, e.g. `architecture`. |
| **Tier** | A retrieval policy: `HOT` (always-loaded), `WARM` (on demand), `COLD` (archive). |
| **Status** | A record's lifecycle state: `ATIVO` (active), `SUPERSEDIDO` (superseded), `RESOLVIDO` (resolved open item). |
| **Update** | Changing only routing metadata (tier, tags, dates, confidence). Meaning is unchanged. |
| **Supersede** | Replacing a record because its *meaning* changed: a new record is created and linked; the old one is kept. |
| **Resolve** | Closing a `PENDENCIA` (open item) with resolution notes. |
| **Source** | The raw, hashed input a record was derived from; the start of the provenance chain. |
| **Provenance** | The auditable lineage source → record → surface, plus the operations log of every mutation. |
| **Operations log** | An append-only record of mutations ("who changed what, when, and why"). |
| **Consolidate** | A *mechanical* hygiene pass: exact-title dedupe + date-based tier demotion + integrity — **not** semantic merging. |
| **Doctor** | A mechanical integrity check over schema, indexes, and invariants. |
| **Semantic path** | The LLM-curated flow: semantic lookup → governed merge/supersede proposal → validated apply. |
| **Thin context** | The small always-loaded layer (`NOW.md`, `HOT.md`) read at session start, generated from the store. |
| **Wiki** | An optional, *derived* Markdown view synthesized from records — never canonical. |
| **Export** | A point-in-time projection of the store (context packs, Cowork / claude.ai surfaces) — not a live sync. |
| **Lexical search** | Word/phrase matching via SQLite FTS5; no embeddings, no semantic recall. |
