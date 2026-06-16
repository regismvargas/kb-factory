# How it works

You don't need to read this page to use KB Factory. If you just want to start
recording things and asking questions, head to [everyday use](everyday-use.md).
But once you've used it a little, the ideas here will make the whole thing
"click" — why your agent suddenly remembers decisions across conversations, why
it never seems to lose the *old* answer when something changes, and why it can
tell you where a fact came from.

This page explains the model in plain language. Everything technical lives in
collapsible blocks you can open if you're curious.

## The big idea: write it down once, never lose it

Most AI memory works like a whiteboard. The agent keeps a running summary and
keeps tidying it — when something changes, it erases the old note and writes the
new one. That's fine for a lot of work, and honestly if all you want is a few
project notes that the agent reads each time, **a plain `CLAUDE.md` file plus
your agent's built-in memory is simpler and you should just use that.**

KB Factory is for when you want something a whiteboard can't give you: a
**history you can trust**. Instead of erasing, it adds. When a decision changes,
the old decision doesn't disappear — it gets marked "replaced," linked to the
new one, and kept forever. Months later you can still ask "what did we believe
back then, and what changed our minds?" and get a real answer.

In one sentence: **you write knowledge down once as small, labeled notes, and the
project never loses any of it.**

Everything below is just the details of how that works.

## Knowledge comes in five kinds

When you tell the agent to remember something, it doesn't just dump a sentence
into a pile. It files the note under one of **five kinds**, based on *what type
of thing* you're saying. This is the single most useful idea to understand,
because it's how the agent later reasons about how much to trust each note.

Here are the five, in plain terms:

| The kind | In one phrase | You'd say something like… |
|---|---|---|
| **Decision** | A choice you made, and why | "We decided to use SQLite because it's zero-setup." |
| **Assumption** | Something you're taking as true for now | "We're assuming the launch is in Q3 — not confirmed yet." |
| **Fact** | Something confirmed and checkable | "The production database is in the eu-west region." |
| **Open item** | A question still hanging | "We still need to decide how we handle refunds." |
| **Learning** | A lesson the project picked up | "We learned that batching the imports avoids the timeout." |

Why bother separating them? Because a *fact* and an *assumption* deserve very
different treatment. An assumption can quietly go stale and should be
double-checked; a fact should be re-verifiable against where it came from; an
open item is a loose end that wants closing. By labeling each note, the agent can
say "you're relying on an assumption from three months ago — want to confirm it?"
instead of treating every sentence as equally solid.

You almost never have to name the kind yourself. You just talk, and the agent
picks the right one. You can always correct it ("no, that's a fact, not an
assumption").

<details><summary>Under the hood / for the CLI</summary>

Internally the five kinds are stored under fixed category codes (the project's
runtime is bilingual, so the codes are Portuguese):
`DECISAO` (decision), `PREMISSA` (assumption), `FATO` (fact),
`PENDENCIA` (open-item), `APRENDIZADO` (learning). These never change per
project. Each stored note ("record") also carries a **domain** (a workstream you
define, like `architecture` or `billing` — pick 4 to 12), a title, the content,
a status, a tier, a source link, tags, and timestamps. Creating one by hand is
`python .kb/kb.py create --category FATO --domain infra --title "…" --content "…"`,
but in chat you never type that — you just ask, and the plugin runs it. See the
full set in the [command reference](../commands.md) and the deeper writeup in
[concepts](../concepts.md).

</details>

## Not everything needs to be in front of you: HOT, WARM, COLD

If the project remembered everything *equally loudly*, every conversation would
start by drowning you in old notes. So each note also has a **tier** that says
how eagerly it should show up. Think of it as three shelves:

| The shelf | What it means in practice |
|---|---|
| **HOT** | The handful of things that matter *right now*. The agent loads these at the very start of every conversation, automatically. |
| **WARM** | The default shelf. Not loaded up front, but instantly found when you (or the agent) search for it. This is where most notes live. |
| **COLD** | The archive. Old history, settled questions, superseded decisions. Out of the way, but never gone — pulled up only if you ask. |

A note's tier is **not** a judgment about how true or important it is — it's
purely about *when it should appear*. A rock-solid fact you rarely need can sit
in WARM; a still-unsettled open item you're actively working can be HOT.

Tiers also drift over time on purpose. As things settle, the agent quietly moves
stale HOT and WARM notes to colder shelves so the "front of mind" layer stays
small and useful. You can also just ask it to "promote that to HOT" when
something becomes important again.

<details><summary>Under the hood / for the CLI</summary>

Tier is one of the few things you can freely change without creating a new record
(that's an "update," see below). A maintenance pass called `consolidate` demotes
aging HOT/WARM records to colder tiers by date, and `audit-tiers` flags when the
HOT layer has grown larger than a session should reasonably carry. None of this
is semantic — it's date-and-rule based housekeeping. Details in
[concepts](../concepts.md).

</details>

## When something changes, you replace — you don't erase

This is the heart of KB Factory, and it's worth a moment.

Say three months ago you recorded: *"We decided to store everything in one
database."* Today you change course: *"We're splitting reads and writes into two
databases."* In an erase-and-overwrite system, the first decision would simply
vanish, and the record would just say "two databases" as if it had always been
that way.

KB Factory does something different. The old decision **stays**. It gets stamped
"replaced," it gets linked forward to the new decision, and the new decision
links back to it. Nothing is overwritten. So later you can trace the whole story:
*here's what we used to think, here's what we think now, and here's the thread
connecting them.*

In chat, this is effortless. You just say something like **"that changed — we
moved to two databases, supersede the old decision"** and the agent does the
right thing. You don't manage links or versions by hand.

There's a useful distinction the agent makes automatically:

- If only the *meaning* changed, it **supersedes** — new note, old one kept and
  linked. ("We switched databases.")
- If only *housekeeping* changed — like which shelf it lives on, or a tag — it
  **updates** in place, because the meaning is the same. ("Promote that to HOT.")
- If an *open item* finally gets answered, it **resolves** — the question is
  closed with notes on the answer, rather than thrown away.

The one rule that makes the history trustworthy: **never delete, never overwrite
— replace.**

> **Why keep all the old stuff around?** Because the most valuable question a
> project can answer is often *"why did we change our minds?"* Erase-and-overwrite
> memory can never answer it. Keeping the trail means a new teammate, a future you,
> or a second agent can reconstruct the reasoning instead of guessing.

<details><summary>Under the hood / for the CLI</summary>

Three distinct operations back this: `supersede` creates a new record, marks the
old one `SUPERSEDIDO`, and wires `supersedes_id` / `replacement_id` between them;
`update` changes only routing metadata (tier, tags, review dates, confidence,
source pointer) and never the content; `resolve` closes a `PENDENCIA` with
resolution notes. The content of a record is treated as immutable — once filed,
its *meaning* is fixed; change comes only by superseding. See
[update vs. supersede in concepts](../concepts.md).

</details>

## Every note can say where it came from

A claim is only as good as its source. So a note can be **linked back to the raw
material it came from** — a document you ingested, a meeting summary, a spec.

This gives you two things. First, when the agent tells you a fact, it can tell
you *where that fact came from*. Second — and this is the quietly powerful part —
KB Factory takes a fingerprint of each source when you bring it in, so it can
later notice if the underlying document has **changed since the note was filed**.
If the spec you ingested gets edited, the system can flag that a note resting on
it may now be out of date.

The chain runs in one direction, and you can always walk it:

```
source  →  note  →  what the agent reads in a conversation
   │         │
   │         └─ the typed, labeled, versioned record
   └─ the raw document it came from (brought in and fingerprinted)
```

So you can take any line the agent surfaces, trace it back to the note behind it,
and trace that note back to the source it came from. That traceability is the
whole reason to use KB Factory over a simpler notes file.

<details><summary>Under the hood / for the CLI</summary>

Raw material is brought in with `ingest`, which content-hashes the file.
`source-status` and `source-verify` later detect drift between a source on disk
and the hash a record recorded. Separately, every change to the store is appended
to an **operations log**, so "who changed what, when, and why" is reconstructable.
Honest status note: this lineage is fully *specified and implemented in code*, but
an end-to-end live demonstration (ingest → file → export → trace back) is still a
pending verification step — see
[provenance & continuity](../provenance-and-continuity.md) for the exact status.

</details>

## Your conversation starts thin, on purpose

Here's how all of this stays *fast* instead of overwhelming. When a conversation
begins, the agent does **not** read the whole knowledge base. It reads a tiny,
generated summary first:

- **NOW** — the single thin starting point. A short "here's where the project is
  right now" page. The agent reads this first, every time.
- **HOT** — the current front-of-mind notes, pulled in when needed.

That's it to start. Everything else stays out of the way until you ask a question
that needs it, at which point the agent searches and pulls in exactly the
relevant notes. This is why a project with hundreds of recorded notes can still
start a conversation quickly: the always-loaded layer is deliberately small, and
the rest is search-on-demand.

These thin pages are **generated from the notes**, not written by hand — they're
a view of the real knowledge base, refreshed as things change. The notes are the
truth; these pages are just the convenient front door.

> **One thing to know per platform.** In **Claude Code**, this thin context loads
> automatically when a conversation starts (a quiet hook notices your project has
> a knowledge base and reads NOW for you). In **Cowork**, that auto-loading
> doesn't happen, so you start a session explicitly — by running
> `/gate-session-start` or just asking *"start a KB session."* More on this in
> [in a conversation](everyday-use.md).

<details><summary>Under the hood / for the CLI</summary>

The thin surfaces are Markdown files under `.kb/memory/` — `NOW.md`, `HOT.md`,
plus `INDEX.md` (a broad map, read only when you need the wider picture) and
`topics/` (short per-domain slices). They're regenerated from the database with
`python .kb/kb.py export`; they are projections of the canonical store, never a
second source of truth. The Claude Code auto-load is a SessionStart hook shipped
by the **kb-lifecycle** plugin. See [the plugins](../plugins.md) and
[agent sessions](../agent-sessions.md).

</details>

## The optional wiki: a readable view on top

Notes are great for the agent and fine for searching, but sometimes you want
something a human can *browse* — a set of tidy pages like "Architecture
overview" or "Billing decisions." That's the **wiki**, and it's entirely
optional.

The important thing to understand: the wiki is **generated from the notes**, and
the notes always win. It's a readable, browsable view synthesized from the real
knowledge base — handy for onboarding someone or skimming a topic — but if a wiki
page and the underlying notes ever disagree, the notes are the truth and the page
is just out of date. A knowledge base works completely without the wiki; turn it
on only if browsable pages are useful to you.

<details><summary>Under the hood / for the CLI</summary>

The wiki is materialized from canonical records (`wiki-sync`, `wiki-candidates`,
`wiki-pages`, `wiki-lint`, `wiki-check`), carries citation blocks back to the
records behind each page, and is governed by the same provenance manifests as
exports. It ships as a machine wiki (granular structured memory for agents) and a
human wiki (narrative docs). The KB + Wiki mode is one choice the
**kb-wiki-vnext** plugin's setup wizards offer; see [the plugins](../plugins.md)
and [concepts](../concepts.md).

</details>

## How the labels keep the agent honest

Worth saying plainly, because it's a deliberate design choice: the **agent does
the thinking, the system enforces the rules.**

The agent (the LLM) is the one that reads your sentence and decides "that's a
decision, file it as one" or "this new fact overturns that old assumption,
propose superseding it." That's genuine judgment, and the model does it.

But the agent never gets to *silently* rewrite history. When it proposes a change,
the underlying system validates it, records it in the operations log, and keeps
the links intact. So you get the flexibility of a smart assistant with the safety
of a system that won't quietly lose or scramble your knowledge. The model
curates; the runtime governs.

One honest limitation to know: **search matches words, not meaning.** If you
recorded something using the word "login" and later search for "auth," the search
itself won't connect them — that paraphrasing is the agent's job on top of the
results, not magic in the search box. So it pays to record notes using the words
a future you would actually search for. (If you specifically need
meaning-based or relational recall, KB Factory may be the wrong tool — see the
[comparison](../comparison.md).)

<details><summary>Under the hood / for the CLI</summary>

Search is lexical full-text search over a SQLite FTS5 index — no embeddings, no
semantic recall in the runtime. The mechanical hygiene pass `consolidate` only
does exact lowercased-title dedupe, date-based tier demotion, and integrity
reconciliation; it never merges records that *mean* the same thing. Semantic
merging and supersession run through an LLM-proposes / runtime-validates pipeline.
This "LLM-curated, mechanically-governed" split is detailed in
[architecture](../architecture.md) and [concepts](../concepts.md).

</details>

## Glossary in plain words

| Term | What it really means |
|---|---|
| **Note / record** | One small labeled thing the project remembers, with a kind, a topic, a title, content, and a source. |
| **Kind / category** | What *type* of thing the note is: decision, assumption, fact, open item, or learning. |
| **Domain / topic** | The workstream a note belongs to, like "architecture" or "billing." You pick a handful per project. |
| **Tier** | Which shelf a note sits on: HOT (loaded up front), WARM (found on demand), COLD (archived but kept). |
| **Supersede** | Replacing a note because its meaning changed — the old one is kept and linked, never erased. |
| **Update** | Changing only housekeeping (which shelf, tags, dates) without touching the note's meaning. |
| **Resolve** | Closing an open item by recording the answer. |
| **Source** | The raw document a note came from; fingerprinted so the system can spot if it later changes. |
| **Provenance** | The traceable line from source → note → what the agent reads, plus a log of every change. |
| **Operations log** | The append-only "who changed what, when, and why" history. |
| **NOW / HOT** | The thin, generated pages the agent reads at the start of a conversation so it starts up fast. |
| **Ingest** | Bringing a raw document into the project so notes can be linked back to it. |
| **Wiki** | An optional, generated set of browsable pages built from the notes — never the source of truth. |
| **Export / context pack** | A point-in-time bundle of the knowledge for surfaces that can't read the database directly (Cowork, claude.ai). A snapshot, not a live feed. |
| **Lexical search** | Word-and-phrase matching. It doesn't understand synonyms — record with searchable words. |

## Where to go next

- **Just want to use it?** → [everyday use](everyday-use.md) and
  [in a conversation](everyday-use.md).
- **Setting up a project?** → [getting started](../getting-started.md) and
  [installation](../installation.md).
- **Want the technical depth?** → [concepts](../concepts.md),
  [architecture](../architecture.md), and
  [provenance & continuity](../provenance-and-continuity.md).
- **Wondering if it's the right tool at all?** → the honest
  [comparison](../comparison.md). If you don't need an auditable history,
  `CLAUDE.md` plus built-in memory is the simpler, correct choice.
