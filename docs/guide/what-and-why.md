# What KB Factory does for you

You're working with an AI agent on a project. Over days and weeks you make
decisions, settle on assumptions, learn what works, and leave a trail of "we'll
figure that out later." Then a new chat starts — and a lot of that is gone. The
agent doesn't remember *why* you chose SQLite over Postgres, or that you already
ruled out an approach last Tuesday, or what that open question even was. So you
re-explain. Again.

KB Factory fixes that by giving your **project** a memory the agent can read and
write — a memory you talk to in plain language, that survives across every
conversation, and that remembers not just what's true now but **what changed and
why**.

This page explains the problem, what KB Factory gives you in return, and — just
as honestly — when you don't need it. If you'd rather jump straight to doing
things, head to [everyday use](everyday-use.md).

## The problem: memory that resets every chat

Most of what an AI agent "knows" about your project lives in the current
conversation. When that conversation ends, it's mostly gone. A few patterns
probably sound familiar:

- **You re-explain context every session.** "Remember, we're local-first, no
  cloud services." You said it last week. You'll say it next week too.
- **Decisions lose their reasoning.** The agent might recall *that* you picked
  SQLite, but not *why* — so it quietly suggests Postgres again, or can't defend
  the choice when someone asks.
- **Nobody can answer "why did this change?"** Six months later you switched off
  an approach. What was the old plan? What overturned it? When? If the old
  answer was simply overwritten by the new one, that story is gone.
- **Open questions evaporate.** "We'll decide the auth model later" drops out of
  context and nobody picks it back up.
- **A second agent starts from zero.** Move from Claude Code to Cowork (or back)
  and the new conversation knows nothing the old one learned.

The usual workaround is a `CLAUDE.md` file plus your agent's built-in memory.
That's genuinely good for lightweight notes and standing rules. But it
*overwrites* as it goes — it keeps polishing the current snapshot, and the past
disappears underneath it. There's no record of what you used to believe, no
typed structure, and no way to reconstruct the history of a decision.

## What KB Factory gives you

KB Factory turns that scattered, disappearing context into a **durable project
memory** the agent maintains for you. Four ideas make it work, and you can use
all of it without learning any of the internals.

### 1. A memory you talk to

You don't type commands or learn a syntax. You just say what you mean, in chat:

> "Record a decision: we'll use SQLite for storage — it's local-first and needs
> no service."

> "What did we decide about storage, and why?"

> "That changed — we're on SQLite plus full-text search now. Supersede the old
> decision."

The plugin you installed translates each of these into the right action behind
the scenes. You think in terms of *record this*, *what did we decide*, *that
changed* — and the memory takes care of itself. (See
[everyday use](everyday-use.md) for the full set of things you can say.)

### 2. Knowledge that's typed — so the agent can reason about it

Everything you save is filed as one of five kinds of knowledge. You don't have
to pick the type yourself; the agent does it from what you say. But knowing the
five helps you understand what the memory can do:

| Kind | What it captures | Example |
|---|---|---|
| **Decision** | A choice you made, with its reasoning | "We use SQLite — local-first, zero ops." |
| **Assumption** | Something you're taking as true for now (and may revisit) | "Assume single-tenant until we sign a second customer." |
| **Fact** | Confirmed, checkable information | "The export step takes about 200ms on a 10k-record store." |
| **Open item** | A question that still needs an answer | "Decide the auth model before launch." |
| **Learning** | A lesson or pattern the project has internalized | "Long-running migrations should run off-peak." |

Keeping these apart is what lets the agent reason about *confidence*. An
assumption can age out and get flagged for review; a fact can be re-checked
against where it came from; an open item stays visible until you actually
resolve it. Free-form notes can't tell these apart — to them it's all just text.

### 3. It remembers what changed *and why* — nothing is overwritten

This is the heart of it, and the thing a plain notes file can't give you.

When something's meaning changes, KB Factory does **not** edit the old entry. It
files a **new** one and **links it back** to the old, which is kept on the record
forever. So instead of a single ever-changing snapshot, you get a **history**:

- What the project believed before.
- What replaced it.
- Which one overturned the other, and when.

That's why the everyday phrasing is "supersede the old decision," not "change
it." You can always reconstruct what the project assumed at any past point and
exactly what changed its mind. This same append-only discipline applies across
all five kinds of knowledge — decisions, assumptions, facts, learnings — and
open items get *resolved* (closed with notes) rather than silently dropped.

When you record where a piece of knowledge came from — a doc, a conversation, a
file — that source is kept too, so the memory can later tell you when the
original has drifted from what you wrote down. The lineage runs **source →
knowledge → what the agent loads at the start of a session**, and every change
is logged. That's what makes this an *auditable* history rather than just a pile
of saved text. (More on the model in [concepts](../concepts.md).)

### 4. It loads light, then digs deeper on demand

A memory is only useful if it doesn't drown the conversation. KB Factory keeps
the always-loaded layer **small**: at the start of a session the agent reads a
short summary (the current working set), not the entire database. Everything
else stays one question away — when you ask "what did we decide about X?" the
agent searches the full store and pulls in just what's relevant.

Knowledge is **tiered** to make this work: a hot tier that's always surfaced, a
warm default that's there when you search for it, and a cold archive that stays
out of the way until you ask. Old knowledge naturally drifts toward the colder
tiers over time, so the active context stays focused without you pruning it by
hand.

### Local-first, no setup tax

All of this runs **on your machine**, in your project, with **no service to run,
no database to host, no API key, and no internet required**. The whole memory is
a single file inside your project folder — easy to back up, easy to inspect,
and yours.

## When it's worth it — and when it isn't

KB Factory is opinionated, and it isn't for everyone. Being honest about that is
part of the point.

**It's worth it when:**

- You want a project's **decisions, assumptions, facts, open items, and
  learnings** to persist across many conversations — and across different agents
  (Claude Code, Cowork).
- You'll eventually need to answer **"why did this change?"** and want the old
  belief kept on the record, linked to what replaced it.
- You value **structure and discipline** — typed knowledge, an audit trail,
  search you can rely on — over a free-form scratchpad.
- You want **zero infrastructure**: nothing to run or pay for, works offline,
  backs up as one file.

**You probably don't need it when:**

- You just want **lightweight project notes and standing rules** and don't care
  about a *history* of what changed. In that case `CLAUDE.md` plus your agent's
  built-in memory is the simpler, correct choice — reach for it first.
- You need **per-user chatbot recall at scale**, an **autonomous agent that runs
  for days managing its own memory**, or **paraphrase-tolerant / semantic
  search** that finds "login" when you typed "auth." KB Factory's search matches
  words and phrases, not meaning — by design, to stay offline and dependency-free.
  Other tools fit those needs better.

The one-line test: **if you don't need an auditable *history*, you don't need KB
Factory.** It earns its keep precisely when you do. For a fuller, sourced
side-by-side against Anthropic's own memory features and the popular open-source
alternatives, see the [comparison](../comparison.md).

<details>
<summary>Under the hood / for the CLI</summary>

Everything above maps to a small, plain-Python toolkit — no magic:

- **The store.** One project = one knowledge base, kept as a single SQLite file
  under `.kb/`. It uses only the Python standard library (SQLite + FTS5 for
  full-text search). Nothing to install beyond Python 3.8+.

- **The five kinds** are *categories* on each record, stored with their original
  Portuguese labels: decision = `DECISAO`, assumption = `PREMISSA`, fact =
  `FATO`, open item = `PENDENCIA`, learning = `APRENDIZADO`. Each record also
  carries a project-defined *domain* (a workstream like `architecture` or
  `billing`), a title, content, status, tier, source, and timestamps.

- **The tiers** are `HOT` (surfaced in the always-loaded context), `WARM`
  (default, found via search), and `COLD` (archived). `consolidate` demotes
  stale records to colder tiers over time.

- **"Supersede, don't overwrite"** is two distinct operations. `supersede`
  creates a new record and links it (`supersedes_id` / `replacement_id`),
  marking the old one `SUPERSEDIDO` — used when *meaning* changes. `update`
  changes only routing metadata (tier, tags, review date) and never touches
  meaning. Open items are closed with `resolve` (status `RESOLVIDO`), not
  superseded.

- **Provenance** runs source → record → surface: raw inputs are `ingest`-ed and
  hashed, every mutation appends to an operations log (`oplog`), and
  `source-verify` detects when an on-disk source has drifted from what a record
  claims. The thin always-loaded layer is the generated Markdown under
  `.kb/memory/` (`NOW.md`, `HOT.md`, `INDEX.md`), regenerated from the database
  with `export`.

- **In chat you never type these.** When you ask the agent to record a decision,
  it runs roughly `python .kb/kb.py create --category DECISAO --domain <d>
  --title "..." --content "..." --tier HOT`; "what did we decide?" becomes
  `python .kb/kb.py search "..."`; "that changed" becomes
  `python .kb/kb.py supersede <id> ...`. The full surface — including the
  optional derived **wiki** layer and the LLM-curated-but-mechanically-governed
  proposal flow — is in the [command reference](../commands.md) and
  [concepts](../concepts.md).

One caveat worth stating plainly: `consolidate` is *mechanical* hygiene
(exact-title dedupe + age-based tier demotion + integrity checks), **not**
intelligent merging. Recognizing that two differently-worded entries mean the
same thing, or that a new decision overturns an old one, is the agent's job —
proposed with rationale and then validated before it's applied.

</details>

## Where to go next

- [Everyday use](everyday-use.md) — what to say in chat to record, recall, and
  supersede knowledge as you work.
- [The plugins](../plugins.md) — the three plugins (`kb-lifecycle`,
  `kb-wiki-vnext`, `session-gate`) and which to install for Claude Code vs.
  Cowork.
- [Concepts](../concepts.md) — the full model: typed records, tiers,
  supersession, and provenance, in depth.
- [Comparison](../comparison.md) — an honest, sourced look at how KB Factory
  stacks up against the alternatives, to confirm it fits before you commit.
