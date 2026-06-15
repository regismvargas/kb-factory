# Use cases

Concrete scenarios where KB Factory earns its keep — and, just as important,
where it doesn't. KB Factory shines when a project needs its **decisions,
assumptions, facts, open items, and learnings** to persist as an *auditable
history* across conversations and across agents. If you only need lightweight,
overwritable notes, skip to [When not to use it](#when-not-to-use-it).

For the underlying mechanics, see
[provenance-and-continuity.md](provenance-and-continuity.md); for how this
compares to other memory systems, see [comparison.md](comparison.md).

---

## 1. Durable decisions that survive across sessions

**The problem.** You decide something on Tuesday — "we store data in SQLite, not
Postgres, because we want local-first and zero ops" — and by the following week
the agent has forgotten the *reasoning*, or worse, quietly re-litigates it.

**With KB Factory.** File the decision once, as a typed record:

```bash
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, zero ops. Rejected Postgres." --tier HOT
```

Every later session — yours or another agent's — finds it:

```bash
python .kb/kb.py search "storage"
```

`HOT`-tier records also surface in the thin startup context, so the agent sees
the live working set at session start without you re-explaining it. The decision
and its rationale are now project memory, not chat scrollback.

## 2. Auditing *why* a decision changed

**The problem.** Six months later someone asks: "Why did we move off SQLite?"
Most memory systems can only show you the *current* answer — the old belief was
overwritten when the new one landed.

**With KB Factory.** When meaning changes, you `supersede` rather than overwrite.
The old record is retained and linked to the one that replaced it:

```bash
python .kb/kb.py supersede REC-... \
  --title "Move to SQLite + FTS5 for full-text search" \
  --content "Lexical search was needed; plain SQLite couldn't query content."
```

Now the history is reconstructable: what the project believed before, what
overturned it, and when. Combined with the operation log
(`python .kb/kb.py oplog`), you can trace *who changed what, when, and why*. This
append-only audit trail is KB Factory's core differentiator — see
[provenance-and-continuity.md](provenance-and-continuity.md).

## 3. Cross-agent continuity in one project

**The problem.** You start a task in Claude Code, hand off to Codex for a
refactor, and review in Cowork. Each agent re-discovers the same context from
scratch, and a learning one agent captured is invisible to the next.

**With KB Factory.** One project = one canonical `.kb/` store. Every agent reads
and writes through the same CLI, so a learning filed by one is immediately
available — and attributable — to the others:

```bash
python .kb/kb.py create --category APRENDIZADO --domain build \
  --title "CI fails on Windows path separators" \
  --content "Use pathlib, not string joins; bit us in the export step."
```

The next agent's `search "windows path"` returns it, with its source. The shared
substrate is the SQLite file in the repo — no service to stand up, no per-agent
account.

> **Honest scope.** Continuity is *project-scoped* and lives in one canonical
> store. The Cowork and claude.ai surfaces are **point-in-time exports**, not a
> live sync — regenerate them when canonical memory changes or they go stale.

## 4. Offline, air-gapped, or zero-infrastructure work

**The problem.** You work on a disconnected network, behind a strict proxy, or
simply don't want to run and pay for a memory service with a vector database and
an API key.

**With KB Factory.** The entire runtime is the **Python standard library plus
SQLite** — no network calls, no external store, no key. It runs fully offline,
and the whole knowledge base backs up as a single file you can copy, commit, or
diff. This makes it viable in environments where hosted memory layers are simply
not an option.

## 5. Curated project memory instead of auto-captured noise

**The problem.** Auto-extraction memory layers capture *everything* the model
sees, which is great for recall but accumulates noise, half-truths, and
transient context that was never meant to be durable.

**With KB Factory.** Records are *filed deliberately*, typed into one of five
categories — `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`, `APRENDIZADO`
(decision, assumption, fact, open-item, learning). The agent (or you) decides
what is worth keeping, so the store stays a curated set of durable beliefs
rather than a transcript. This is a deliberate trade: curation over automatic
capture.

## 6. Tracking open items and project status across conversations

**The problem.** "What's still unresolved?" is a question that gets re-asked
every session, and the answer drifts between people and agents.

**With KB Factory.** File open items as `PENDENCIA` and query them directly:

```bash
python .kb/kb.py pending          # everything still open
python .kb/kb.py stats            # counts by category / tier
```

Because open items are typed records, they carry the same provenance and
supersession discipline as everything else — an open item isn't deleted when
resolved, it's `resolve`d and kept, so the trail of what *was* open survives.

## 7. Reconstructing project belief at a past point in time

**The problem.** You need to understand not what the project believes *now*, but
what it believed when a specific decision was made — for a postmortem, an audit,
or onboarding someone who's asking "what changed and why?"

**With KB Factory.** Because nothing is overwritten — superseded records stay
linked and source-attributed — you can walk the supersession chain and the
operation log to reconstruct the project's belief state at any past point, and
exactly what overturned it. This is the scenario most consolidative memory
systems cannot serve, because their model improves the current snapshot by
discarding the past.

---

## When *not* to use it

KB Factory is opinionated, and that opinion isn't right for everyone. Reach for
something else when:

- **You don't need an auditable belief *history*.** If lightweight,
  overwritable notes are enough, `CLAUDE.md` plus your agent's built-in memory is
  the simpler, correct choice. Don't take on the filing discipline you won't use.
- **You need semantic or paraphrase recall.** KB Factory's search is **lexical**
  (SQLite FTS5) — it matches words, not meaning. If you need embedding-based
  recall, prefer Mem0, Zep, or similar.
- **You need per-user chatbot recall at scale**, an **autonomous agent that runs
  for days** managing its own memory, or a **temporal / document knowledge
  graph** — those are different tools (Mem0, Letta/MemGPT, Zep, Cognee). See
  [comparison.md](comparison.md).
- **You expect automatic, intelligent consolidation.** `consolidate` is
  **mechanical** — exact lowercased-title dedupe, date-based tier demotion, and
  integrity checks — *not* semantic merging. Semantic supersession is a governed
  path the agent proposes; it is not automatic.
- **You're fully inside managed/hosted agents** and want account-scoped, hosted
  memory rather than a local, repo-owned store.

> **Advanced.** Beyond the core (`init`, `create`, `search`, `supersede`,
> `lifecycle session-start`), the runtime also exposes ingestion and provenance
> commands (`ingest`, `sources`, `source-verify`), maintenance (`doctor`,
> `consolidate`, `hygiene-audit`, `audit-tiers`), the operation log (`oplog`),
> and governed wiki/export sync. These support auditing and large update waves;
> they aren't needed for everyday filing and lookup.
