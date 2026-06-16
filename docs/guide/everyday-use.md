# Everyday use

This is the page you'll come back to. It's about the small, repeatable habit at
the heart of KB Factory: open a project, do your work, and along the way *tell
the agent what's worth remembering* — so that next week, or next session, or on
another machine, it still knows. You don't manage a database. You have a
conversation, and the project quietly accumulates a memory you can trust.

The whole thing fits in one loop:

1. **Start the session** — the agent loads a short summary of where things stand.
2. **Record knowledge as it comes up** — decisions, facts, assumptions, open
   questions, lessons. Just say them.
3. **Recall from memory** — ask what was decided instead of re-deciding it.
4. **Supersede when something changes** — replace the old answer without erasing
   it, so you keep the trail of *why*.
5. **End the session** — the agent tidies up and refreshes the summary for next
   time.

You never have to type a command. You ask, the agent runs the right thing. If
you *want* to drive it from a terminal yourself, every step has a CLI equivalent
in a collapsible block below — but lead with the conversation.

> If your project doesn't actually need an auditable *history* — what was
> believed, what changed it, when — then a `CLAUDE.md` file plus your agent's
> built-in memory is the simpler, honest choice. KB Factory earns its keep when
> you want every superseded decision to stay on the record. See the
> [comparison](../comparison.md) if you're not sure.

---

## 1. Start the session (start thin)

Begin every working session by giving the agent its bearings. The first thing it
reads is a short, always-loaded summary called `NOW.md` — a paragraph or two on
where the project stands right now. That's deliberate: it's cheap, it's fast, and
it doesn't drown the conversation in everything the project has ever known. The
deeper material (the current working set, the full map, individual records) is
pulled in **only when the conversation needs it**. This "start thin, deepen on
demand" habit is what keeps the agent sharp instead of bloated.

**In Claude Code**, you usually don't do anything — opening a project that has a
knowledge base triggers a start-up step automatically, and the agent reads
`NOW.md` before it assumes anything. (That automatic step comes from the
[kb-lifecycle plugin](../plugins.md).)

**In Cowork**, nothing fires automatically, so you start the session yourself.
Just say it:

> "Let's start a KB session."

or run `/gate-session-start`. The agent loads `NOW.md` and you're ready. See
[platform differences](#platform-differences) below for why the two behave
differently.

If you ever want a fuller picture at the start — say you're doing an audit or a
big review — just ask: *"start the session and also load the current working set
and the full index."* The agent will pull in `HOT.md` (the active records) and
the broader map on top of `NOW.md`.

<details><summary>Under the hood / for the CLI</summary>

Session start runs one lifecycle event and then reads the thin surface:

```bash
python .kb/kb.py lifecycle session-start --json
# then read .kb/memory/NOW.md
```

`NOW.md` is the thin, always-loaded entry point. `.kb/memory/HOT.md` (the active
HOT records) and `.kb/memory/INDEX.md` (the broader map) are loaded *on demand*,
not at startup. These files are generated projections of the SQLite store — not a
second source of truth. See [the lifecycle command](../commands.md#lifecycle) and
[agent sessions](../agent-sessions.md) for the full bootstrap modes (thin,
standard, deep review).

</details>

---

## 2. Record knowledge as it comes up

This is the part you'll do most. Whenever something durable surfaces in the
conversation — a choice you made, a fact you confirmed, an assumption you're
running on, a question you couldn't close, a lesson you learned — tell the agent
to write it down. You describe it in plain language; the agent picks the right
*type* and files it.

KB Factory sorts knowledge into **five types**, by the *nature* of the knowledge
rather than its subject. You don't have to memorize them — say what happened and
the agent classifies — but knowing them helps you phrase things, and it's the
vocabulary the agent uses back to you.

| Type | English | You use it for | Say something like |
|---|---|---|---|
| `DECISAO` | decision | A choice you made, with its reasoning | "Record a decision: we'll use SQLite for storage — local-first, no service to run." |
| `PREMISSA` | assumption | A hypothesis you're acting on (can expire) | "Note an assumption: we expect under 10k records per project; revisit if we blow past that." |
| `FATO` | fact | Confirmed, checkable information | "Record a fact: the export step takes about 40 seconds on the full dataset." |
| `PENDENCIA` | open-item | A question that still needs an answer | "Add an open item: we haven't decided how to handle migrations yet." |
| `APRENDIZADO` | learning | A pattern or lesson the project internalized | "Capture a learning: lexical search misses paraphrases, so we should title records with the words people will search for." |

Why bother separating them? Because keeping a *fact* distinct from an
*assumption*, and a *decision* distinct from an *open question*, is what lets the
agent reason about confidence later. An assumption can age out and ask to be
re-checked; a fact stays checkable against its source; an open item nags until
it's resolved. Lumped together as "notes," none of that works.

### How to phrase it

You don't need a magic format. Any of these work, and the agent fills in the
rest:

- *"Record a decision: …"* — most explicit, names the type for you.
- *"Make a note that we decided …"* — the agent infers it's a decision.
- *"That's worth remembering — file it."* — after the agent says something
  useful, tell it to keep it.

Lead with **what** and **why**. A good decision record says both the choice and
the reasoning ("we chose X *because* Y, and rejected Z"), because the reasoning
is exactly what gets lost otherwise. The agent will give the record a short title
and put it in a **domain** — a project workstream like `architecture`, `billing`,
or `ops`. If you have a domain in mind, mention it ("file this under billing");
otherwise the agent picks a sensible one.

### Tiers: what's always in view vs. what's on demand

Every record gets a **tier**, which is just a *retrieval policy* — how eagerly it
should resurface — not a judgment of how important or true it is:

- **HOT** — should shape the start of *every* session; it shows up in that thin
  startup summary. Reserve this for the handful of things that are always
  relevant right now.
- **WARM** — the default. Retrievable any time you search, but not loaded
  automatically. Most records live here.
- **COLD** — archive and history. Never loaded unless you ask for it.

You can ask the agent to set or change a tier — *"that decision is central, keep
it HOT"* — and records naturally drift colder over time as they age (more on that
in [keeping memory healthy](how-it-works.md)). Keep HOT small; if everything's
HOT, nothing is.

### A note on sources (optional but powerful)

If a fact or summary comes from a document — a spec, a meeting note, a research
PDF — you can have the agent **ingest** that file first, then file records that
*cite* it. Just say *"ingest this spec under the research domain, then summarize
it into the KB."* The file is copied in and hashed, so later the agent can tell
you if the underlying document drifted from what a record claims it said. This is
the provenance backbone; it's optional, and you can skip it for knowledge that
comes straight out of conversation. The [everyday loop](#the-loop-in-one-screen)
works fully without it.

<details><summary>Under the hood / for the CLI</summary>

Recording a record maps to `create`:

```bash
python .kb/kb.py create \
  --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no service to run. Rejected Postgres." \
  --tier HOT
```

The five categories are `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`,
`APRENDIZADO`. Tier defaults to `WARM`; pass `--tier HOT` or `--tier COLD` to
change it. Other useful flags: `--tags`, `--confidence` (0–1, default 0.8),
`--source-id` to link to an ingested source, `--review-after`/`--valid-until` for
dates. Full flag table: [`create`](../commands.md#create).

To attach a source first:

```bash
python .kb/kb.py ingest path/to/spec.md --domain research --tags "spec"
python .kb/kb.py create --category FATO --domain research \
  --title "Summary: spec.md" --content "..." --source-id <source_id>
```

When the agent files a result it *produced* (an answer it reasoned out, an
analysis of a source), it may use the `file` helper instead of `create` — same
record, plus a provenance tag (`filed-answer`, `filed-analysis`,
`filed-synthesis`) and an audit-log entry. You rarely need to ask for this by
name; the agent chooses it when filing has clear intent. See
[filing helpers](../commands.md#filing-helpers).

</details>

---

## 3. Recall — answer from memory, not from guessing

The flip side of recording is recall. When you need to know what the project
already established, **ask the knowledge base** instead of scrolling back or
letting the agent improvise:

> "What did we decide about storage, and why?"

> "Do we have anything on rate limits?"

> "What's our assumption about expected dataset size?"

The agent searches the store and answers *from it*, with the actual recorded
content and reasoning — not a freshly invented opinion. This is the single
biggest day-to-day payoff: the project stops re-litigating settled questions and
stops contradicting itself between sessions.

To see what's still unresolved, ask for the open items:

> "What's still open?" / "Show me the unresolved questions in billing."

One honest caveat: **search is lexical, not semantic.** It matches words and
phrases, not meaning — a search for "auth" won't find a record that only ever
says "login." There's no embedding model and no fuzzy paraphrase matching. The
practical consequence flows back to step 2: title and word your records with the
terms a future search will actually use. If you genuinely need
paraphrase-tolerant or relational recall, KB Factory is the wrong tool, and the
[comparison](../comparison.md) page says so plainly.

<details><summary>Under the hood / for the CLI</summary>

Recall is full-text search over the SQLite FTS5 index:

```bash
python .kb/kb.py search "storage"
python .kb/kb.py search "auth" --category DECISAO --domain security --limit 10
```

Filters: `--category`, `--domain`, `--status`, `--tier`, `--limit`. To list open
items: `python .kb/kb.py pending [--domain <d>]`. To fetch one record by id
(including its supersession links): `python .kb/kb.py get <record_id>`. Search is
**lexical only** — no embeddings, no semantic recall. See
[`search`](../commands.md#search) and the note on lexical search in
[concepts](../concepts.md#search-is-lexical).

</details>

---

## 4. Supersede when something changes (the discipline that matters)

Things change. You revisit a decision, an assumption turns out wrong, a fact gets
updated. The instinct is to *edit* the old record. KB Factory deliberately
doesn't let you — and this is the feature, not a limitation.

When the **meaning** of something changes, you **supersede** it. The agent writes
a *new* record, links it back to the old one, and marks the old one as superseded
— but keeps it forever. Nothing is overwritten, nothing is deleted. The result is
a belief history: you can always reconstruct what the project used to think and
exactly what changed its mind.

Just say it:

> "We switched storage to SQLite plus full-text search — supersede the old
> decision."

> "That assumption was wrong; the real limit is 50k records, not 10k. Supersede
> it."

Now ask *"why did we change the storage decision?"* later and the agent can walk
you from the original choice to the current one, with both rationales intact.
That trail is the entire reason KB Factory exists — and it's why "just edit the
note" would quietly destroy the thing you came here for.

**Three different actions, easy to keep straight:**

- **Supersede** — the *meaning* changed. New record, old one kept and linked.
  ("We now use SQLite *and* FTS5.")
- **Update** — only *routing metadata* changed, not the meaning. Promote a record
  to HOT, retag it, extend an assumption's expiry. ("Bump that decision to HOT.")
- **Resolve** — close an **open item** with a note on how it was settled.
  ("That migration question is resolved — we went with the staged approach,
  shipped in #421.")

The rule in one line: **never delete, never overwrite — supersede.** When in
doubt, just describe what happened and let the agent pick the right action.

<details><summary>Under the hood / for the CLI</summary>

```bash
# Meaning changed → supersede (old record retained + linked):
python .kb/kb.py supersede <record_id> \
  --title "Use SQLite + FTS5" \
  --content "Added full-text search to the original SQLite decision."

# Only routing metadata changed → update:
python .kb/kb.py update <record_id> --tier HOT --tier-reason "now central"

# Close an open item → resolve (requires a note):
python .kb/kb.py resolve <record_id> --notes "Shipped staged migration in #421"
```

`supersede` creates a new record, sets `supersedes_id`/`replacement_id` links,
and marks the old record `SUPERSEDIDO`; it accepts the same content/metadata
flags as `create`. `update` never touches meaning — only tier, tags, dates,
confidence, source, tags. See [`supersede`](../commands.md#supersede),
[`update`](../commands.md#update), [`resolve`](../commands.md#resolve), and the
[update-vs-supersede](../concepts.md#update-vs-supersede) discussion.

</details>

---

## 5. End the session

When you're done, close the session. This isn't bookkeeping for its own sake — it
**regenerates the thin surfaces** (the `NOW.md` and friends that the *next*
session will read) so they reflect everything you just recorded. Skip it and the
next session starts from a slightly stale summary; the canonical store is still
correct, but the always-loaded snapshot lags behind.

> "Let's close the session."

**In Claude Code**, that's enough — the agent runs the close-out, consolidates,
and refreshes the exports. **In Cowork**, end explicitly with
`/gate-session-end` (you can pass a session label, e.g. `/gate-session-end S14`),
which runs a quick pre-close check and the matching close-out.

If you've recorded a lot, or it's been a while, you can ask the agent to do a
light health pass at close — *"close the session and check if anything HOT has
gone stale."* That's the gentle edge of the maintenance story covered in
[keeping memory healthy](how-it-works.md).

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py lifecycle session-end --json
```

This runs the close-out and refreshes the derived export surfaces. For a light
health check before closing, the agent may run read-only
`python .kb/kb.py hygiene-audit --json`; for a stronger retention pass that lets
stale HOT records fall back, `python .kb/kb.py lifecycle scheduled-maintenance
--apply-demotions --json`. None of these merge or delete anything by meaning —
they're mechanical hygiene. See [the lifecycle command](../commands.md#lifecycle).

</details>

---

## The loop, in one screen

Here's a whole realistic session, as you'd actually talk through it:

> **You:** Let's start a KB session.
> **Agent:** *(loads `NOW.md`)* We're mid-way on the storage layer; one open
> question about migrations.
>
> **You:** Record a decision: we'll use SQLite, local-first, no service to run —
> keep it HOT.
> **Agent:** Filed as a decision in `architecture`, tier HOT.
>
> **You:** What's still open?
> **Agent:** One open item: how to handle schema migrations.
>
> **You:** Add a learning: lexical search misses paraphrases, so title records
> with the words people will actually search.
> **Agent:** Filed as a learning in `architecture`.
>
> *(later that week, new session)*
>
> **You:** What did we decide about storage, and why?
> **Agent:** *(searches)* SQLite, local-first, no service — chosen for zero ops.
>
> **You:** That changed — we added full-text search on top. Supersede it.
> **Agent:** Superseded; the original decision is kept and linked.
>
> **You:** The migration question is resolved — staged approach, shipped. And
> let's close the session.
> **Agent:** Open item resolved; session closed and the summary refreshed.

Same five moves every time: **start thin, record, recall, supersede, close.**

---

## Platform differences

The behavior is the same on both platforms; only *who starts the session*
differs.

| | Claude Code | Claude Cowork |
|---|---|---|
| Start session | **Automatic** — opening a project with a knowledge base loads `NOW.md` | **Manual** — say "start a KB session" or run `/gate-session-start` |
| Recording / recall / supersede | Same — just ask | Same — just ask |
| Skill auto-triggers on "KB", "ingest", … | Yes | Probabilistic — if it doesn't fire, just say the command explicitly |
| End session | "close the session" | `/gate-session-end` |

Cowork doesn't fire automatic hooks, which is why you start and end sessions
explicitly there — the [session-gate plugin](../plugins.md) exists precisely to
make those boundaries clean. In both tools, if the agent seems to have skipped
loading memory, just ask it directly: *"load NOW.md and search the KB before
answering."*

---

## Where to go next

- **[How it works](how-it-works.md)** — the five knowledge types, the tiers,
  superseding vs. overwriting, and the light-touch maintenance the agent does.
- **[Agent sessions reference](../agent-sessions.md)** — the technical view of
  the same workflow, with the bootstrap modes.
- **[Command reference](../commands.md)** — every CLI verb behind every
  conversational action.
- **[Concepts](../concepts.md)** — the model from first principles (typed
  records, tiers, append-only, provenance).
- **[The plugins](../plugins.md)** — what each plugin adds and which to install.
- **[Comparison](../comparison.md)** — an honest take on when KB Factory is, and
  isn't, the right tool.
