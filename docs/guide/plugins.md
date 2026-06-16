# Pick your setup

KB Factory gives your project a durable memory that the agent reads and writes
for you — typed, tiered, and append-only, so you can always see what changed and
why. You drive all of that from inside a normal Claude Code or Cowork
conversation. You don't type CLI commands; you *ask* ("record a decision: …",
"what did we decide about X?", "that changed — supersede it"), and a plugin runs
the right thing under the hood.

There are three plugins, and the good news is you don't have to understand all
of them to get started. This page helps you pick the right combination based on
two simple questions:

1. **Where do you work** — Claude Code or Cowork?
2. **What do you need** — just the everyday workflow, or also the leaner
   "thin-session" model with reviewed changes?

If you only want the quick answer, jump to [the recommended setups](#the-recommended-setups).
If you want to know what each plugin actually *does for you in chat*, keep reading.

> Not sure you even need a knowledge base? If you don't need an auditable
> *history* of how decisions changed, plain `CLAUDE.md` plus the agent's
> built-in memory is the simpler choice. KB Factory earns its keep when you want
> a searchable, typed record that survives across sessions and shows its work.
> See the [comparison](../comparison.md).

---

## What each plugin gives you (in plain terms)

### kb-lifecycle — the everyday one

This is the plugin most people start with, and for a lot of projects it's the
only one you need. It handles the day-to-day: starting a session, pulling in a
source document, recording typed knowledge, searching, and tidying up at the
end.

**What you'll notice in chat:**

- **No slash commands to memorize.** It works through a skill that wakes up on
  its own. When you say things like "let's start a KB session," "ingest this
  source," "what does the KB say about…," or "update the wiki" — or simply when
  your project has a `.kb/` folder — the skill activates and does the work.
- **In Claude Code, it greets you at session start.** When you open a project
  that already has a knowledge base, the plugin quietly nudges the agent to read
  your always-loaded summary (`NOW.md`) *before* it assumes anything. You get
  context for free, with nothing to type.
- **It picks the type for you.** When you say "record a decision: we'll use
  SQLite," the agent files it as a decision. Same for facts, assumptions, open
  items, and learnings — you just describe what happened.

<details><summary>Under the hood / for the CLI</summary>

The skill is named `kb-wiki-maintainer`. It maps your phrasing to CLI calls like
`python .kb/kb.py lifecycle session-start --json`, `… ingest <path>`,
`… create --category DECISAO …`, `… search "<query>"`, and `… wiki-sync`.
In Claude Code, the SessionStart hook injects a short reminder to read
`.kb/memory/NOW.md`. There are **no slash commands** — everything is skill- or
hook-driven. Runs on Claude Code, Cowork, and Codex.

</details>

### session-gate — the reliable "start/end" button for Cowork

Here's the one platform wrinkle worth knowing: **Claude Code starts your session
automatically, but Cowork does not.** In Claude Code, the kb-lifecycle hook fires
and your context loads on its own. In Cowork there's no hook, so nothing loads
until you ask. `session-gate` is the fix — it gives Cowork one dependable command
to open and close a session.

**What you'll notice in chat:**

- **`/gate-session-start`** — figures out what your project has set up and loads
  just the context you need, then gives you a short briefing. Use this (or say
  "session start" / "iniciar sessão") as the first thing you do in Cowork.
- **`/gate-session-end`** — runs a quick pre-close check, tidies and consolidates,
  and hands you a summary. You can pass a session id, e.g. `/gate-session-end S14`.

It doesn't store anything of its own — it just detects which subsystems you have
and routes start and end to them. Think of it as a light switch, not a second
memory.

<details><summary>Under the hood / for the CLI</summary>

`session-gate` owns no storage. On start it detects `.kb/`, `.kb-next/`, and any
companion workflow, then routes: if `.kb-next/` is present it runs the
kb-wiki-vnext startup first, otherwise the kb-lifecycle session-start. On end it
runs a pre-close audit and the matching closeout (kb-wiki-vnext evidence summary
and/or `lifecycle session-end` + `hygiene-audit`). The skill is `session-gate`,
triggered by phrases like "session start" / "wrap up" (and the Portuguese
"iniciar sessão" / "encerrar sessão"). No session hook — it *is* the workaround
for Cowork's missing hook. Primarily for Cowork; also runs on Claude Code and
Codex.

</details>

### kb-wiki-vnext — thin sessions and reviewed changes

This plugin is for two situations: **setting up or migrating a project**, and
running a leaner session model where durable changes go through a review step
before they're written. It starts a session reading **only** your `NOW.md` and
pulls more in on demand, which keeps each conversation cheap. When the agent
wants to change durable memory, it *proposes* the change first; nothing touches
your canonical knowledge base until you approve.

**What you'll notice in chat — 12 slash commands**, grouped by what you're doing:

*Running a thin session*
- `/vnext-session-start` — start a session reading only `NOW.md` by default.
- `/vnext-session-end` — close the session, recording useful evidence; durable
  changes go through the reviewed apply step rather than being written silently.

*Setting up a brand-new project*
- `/new-project-wizard` — the guided path: bootstraps a fresh workspace, routes
  you to the right init command, then verifies.
- `/new-project-init-kb-alone` — set up a new project with the knowledge base only.
- `/new-project-init-kb-wiki` — set up a new project with the knowledge base
  plus a generated wiki.
- `/new-project-verify-install` — a read-only check that the setup worked.

*Bringing an existing or legacy project on board*
- `/existing-project-diagnose` — a safe, read-only look at what's there before you
  change anything.
- `/existing-project-activate-vnext` — turn on the thin-session model **without
  overwriting** your existing knowledge base.
- `/existing-project-configure-vnext` — adjust the mode or run a guided activation.
- `/existing-project-verify-install` — read-only verification after any change.
- `/existing-project-upgrade-vnext` — upgrade the runtime, keeping your data canonical.
- `/existing-project-rollback-vnext` — roll back to the prior runtime, preserving evidence.

The thing to remember: your canonical memory is always the project's `.kb/`. This
plugin keeps its own working files (proposals, manifests, draft wiki) in a
separate `.kb-next/` so the real store is never changed without review.

<details><summary>Under the hood / for the CLI</summary>

The skill is `kb-wiki-vnext`. Beyond sessions and setup, it offers a
**review-gated** path for durable change aimed at maintainers: an agent proposes
a change (a new record, a supersession, a merge, a wiki draft), the proposal is
recorded under `.kb-next/`, and it only reaches `.kb/` after an explicit apply
step. Related capabilities: `semantic-lookup` (LLM-assisted retrieval),
`semantic-hygiene` (report-only review of HOT overflow / duplicates / stale
items), the proposal → apply flow, and `compliance-preflight` (a checklist gate
for development work). The session hook is informational only (it prints a
reminder to run the start command rather than firing automatically). Runs on
Claude Code, Cowork, and Codex. Underlying CLI verbs are in
[the command reference](../commands.md).

</details>

---

## The recommended setups

The three plugins never collide — kb-lifecycle has no slash commands,
kb-wiki-vnext uses `vnext-*` / `new-project-*` / `existing-project-*`, and
session-gate uses `gate-*` — so any combination is safe to install. Here are the
combinations worth picking:

| You are… | Install | Why |
|---|---|---|
| On **Claude Code**, everyday use | **kb-lifecycle** | Simplest. The hook auto-loads your context; the skill handles ingest / record / search. For most Claude Code projects this is all you need. |
| On **Cowork**, everyday use | **kb-lifecycle + session-gate** | Cowork won't auto-load context, so `session-gate` gives you a reliable `/gate-session-start` and `/gate-session-end`. |
| Want the **thin-session model** or are **setting up / migrating** a project (Claude Code) | **kb-lifecycle + kb-wiki-vnext** | Your `.kb/` stays canonical; `.kb-next/` holds proposals and drafts. Use `/vnext-session-start` when you want a thin session and the `/new-project-*` or `/existing-project-*` commands for setup. |
| On **Cowork** and want thin sessions and/or a workflow | **all three** | `session-gate` detects everything and routes; when `.kb-next/` is present it runs the kb-wiki-vnext startup first. |

A few principles when you mix them:

- **One canonical store.** Only `.kb/` is your durable memory. `.kb-next/` is
  working state; `session-gate` stores nothing.
- **kb-wiki-vnext goes first under the gate.** If both `.kb-next/` and `.kb/`
  exist, `/gate-session-start` runs the thin-session startup first.
- **No second memory layer.** session-gate only points at what already exists.

---

## Quick decision guide

- **On Claude Code and just want a memory that works?** Install **kb-lifecycle**
  and start working. The session loads itself.
- **On Cowork?** Add **session-gate** and begin each session with
  `/gate-session-start`.
- **Setting up a new project, or adopting one that has no KB yet?** Add
  **kb-wiki-vnext** and run `/new-project-wizard` (new) or
  `/existing-project-diagnose` then `/existing-project-activate-vnext` (existing).
- **Want every durable change reviewed before it lands?** That's the
  **kb-wiki-vnext** thin-session model — use `/vnext-session-start`.

---

## See also

- [Everyday use](everyday-use.md) — what to say in chat to record, recall, and
  supersede knowledge once your plugins are installed.
- [agent-sessions.md](../agent-sessions.md) — how a chat session flows end to end
  on each platform.
- [installation.md](../installation.md) — installing the plugins in Claude Code
  and Cowork.
- [plugins.md](../plugins.md) — the full per-plugin reference (every command,
  skill trigger, and hook).
- [commands.md](../commands.md) — the slash commands and the CLI behind them.
- [concepts.md](../concepts.md) — typed, tiered, append-only memory explained.
- [comparison.md](../comparison.md) — when KB Factory is worth it versus plain
  `CLAUDE.md` + built-in memory.
