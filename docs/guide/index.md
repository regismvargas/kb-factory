# KB Factory — User Guide

Welcome. This guide is for people who want their **project** to *remember
things* — decisions, facts, assumptions, open questions, and lessons learned —
so an AI assistant can pick up where the last conversation left off instead of
starting from a blank slate each time.

You don't need to be a programmer to use it. Most of the time you just **talk to
your assistant** in plain language — "record this decision", "what did we decide
about X?", "that changed, update it" — and it handles the rest.

## Who this guide is for

You'll feel at home here if you want a project where:

- The assistant **remembers what you decided and why**, across days and across
  separate chats.
- You can later **see what changed** — every superseded decision is kept and
  linked, so the *history* survives, not just the latest snapshot.
- Everything lives **on your own machine** — no service to sign up for, no API
  key, works offline.

> **Maybe you don't need all this.** If you just want a few lightweight project
> notes and you don't care about an auditable *history* of what changed and why,
> a plain `CLAUDE.md` file plus your assistant's built-in memory is simpler and
> perfectly fine. KB Factory earns its keep when the *history* matters. The
> [comparison](../comparison.md) lays this out honestly.

## Two ways to use KB Factory

Both ways read and write the **same** knowledge base — a small `.kb/` folder in
your project. A decision you record in chat shows up at the command line, and
vice versa. Pick whichever feels natural; you can mix them freely.

### 1. In a conversation (the easy path — most people)

You install a **plugin** in Claude Code or Cowork, then just *ask* the assistant
to record and recall things. You never type a command yourself — the plugin runs
the right one for you behind the scenes.

> "Record a decision: we'll use SQLite for storage — it's local-first and needs
> no service."

> "What did we decide about storage, and why?"

This is what most of this guide focuses on. Start with
[install and first session](install-and-first-session.md).

### 2. From the command line (for the hands-on)

If you prefer a terminal, you can run the knowledge base directly. It's a single
Python script — no install step, no dependencies beyond Python itself.

<details><summary>Under the hood / for the CLI</summary>

The whole tool is `python .kb/kb.py <command>`. The five everyday commands are:

```bash
python .kb/kb.py init                              # once per project
python .kb/kb.py create --category DECISAO ...      # file a typed record
python .kb/kb.py search "storage"                  # lexical full-text find
python .kb/kb.py supersede <record_id> ...          # replace when meaning changes
python .kb/kb.py lifecycle session-start --json     # bootstrap, then read NOW.md
```

When you use the conversational path, this is exactly what the plugin runs for
you. The full command-line reference (and how chat phrases map to commands)
lives in [the command reference](../commands.md) and
[getting-started](../getting-started.md).

</details>

## A map of this guide

Read top to bottom the first time, or jump to whatever you need:

| Page | What it covers |
|---|---|
| [What and why](what-and-why.md) | What a durable project memory buys you, in plain terms — and when *not* to bother. |
| [Install and first session](install-and-first-session.md) | Get a plugin running and record your first thing — in Claude Code or in Cowork. |
| [Everyday use](everyday-use.md) | The day-to-day rhythm: recording, recalling, changing your mind, wrapping up. |
| [How it works](how-it-works.md) | The simple model behind it: typed knowledge, what's always loaded, and why nothing is ever overwritten. |
| [Plugins](plugins.md) | The three plugins, what each one adds, and which to install. |
| [Recipes](recipes.md) | Concrete walkthroughs for common situations — starting fresh, adopting an existing project, and more. |
| [Troubleshooting](troubleshooting.md) | When the assistant didn't load the memory, or a command didn't fire — and how to nudge it. |

## How the assistant remembers (the 30-second version)

Three ideas carry the whole thing, and you'll meet them again in
[how it works](how-it-works.md):

- **Typed.** Each thing you save is one of five kinds — a **decision**, an
  **assumption**, a **fact**, an **open item**, or a **learning**. You just
  describe it; the assistant picks the type.
- **Tiered.** The most important records are **always loaded** at the start of a
  session (kept small and cheap); the rest stays a search away until you need it.
- **Append-only.** When something changes, the old version is **kept and
  linked**, never erased. That's what lets you reconstruct *what the project
  believed before, and what overturned it.*

## A note on the two environments

There's one difference worth knowing up front, covered fully in
[install and first session](install-and-first-session.md):

- In **Claude Code**, when you open a project that already has a knowledge base,
  the assistant loads it **automatically** — you don't have to do anything.
- In **Cowork**, you start a memory session **explicitly** — run
  `/gate-session-start` or just say "start a KB session" — because Cowork doesn't
  fire startup hooks on its own.

## Going deeper

This guide is the friendly, task-oriented path. When you want the **deeper
technical reference** — exact command surfaces, the data model, the architecture,
plugin internals — the top-level [`docs/`](../) folder is where that lives.
Useful starting points:

- [Concepts](../concepts.md) — the full model: typed records, tiers,
  supersession, provenance.
- [Command reference](../commands.md) — every slash command and CLI verb.
- [The plugins](../plugins.md) — the technical breakdown of all three.
- [Comparison](../comparison.md) — an honest, sourced look at how KB Factory
  stacks up against Anthropic's memory tools and other open-source options.

Ready? Head to [what and why](what-and-why.md) to decide if this fits, or jump
straight to [install and first session](install-and-first-session.md).
