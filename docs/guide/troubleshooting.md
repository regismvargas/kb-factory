# When something is off

Most KB Factory hiccups are small and quick to fix. This page walks through the
ones you're most likely to hit while working **in a chat** — the plugin or its
commands don't show up, nothing happened when your session started, the agent
didn't catch what you meant, your search came up empty. For each one, you'll find
a plain answer and, where it helps, the under-the-hood detail tucked into a
collapsible block.

If you're brand new, start with [getting started](../getting-started.md) and
[everyday use](everyday-use.md). For the deep, command-line diagnostics (`doctor`,
`wiki-lint`, the cleanliness gate), see the full
[troubleshooting reference](../troubleshooting.md).

---

## The plugin or its slash commands don't show up

You type `/` in the chat and you only see the generic, built-in commands — none
of the KB ones (`/vnext-session-start`, `/gate-session-start`, the
`/new-project-*` and `/existing-project-*` family). Or you ask the agent to
"start a KB session" and it acts like it's never heard of one.

That almost always means **the plugin isn't loaded for this workspace**. Two
things to check, in order:

1. **Is the plugin installed?**
   - In **Claude Code**, the quickest check is to ask in chat ("which KB plugins
     are installed?") or run `claude plugin list` in a terminal.
   - In **Cowork**, open **Customize → Plugins** and confirm the plugin is listed
     and enabled.
2. **Did the workspace pick it up?** Newly installed plugins sometimes need the
   workspace reopened before their commands and skills appear in the menu. Close
   and reopen the workspace, then type `/` again.

Remember there are three separate plugins, and each carries different things:

- **kb-lifecycle** — the everyday workflow. It has **no slash commands**; it works
  through a skill that triggers when you mention KB-ish things (and, in Claude
  Code, a hook that loads your project memory at session start). So if you
  installed *only* this one, an empty slash menu is expected — drive it by asking
  in plain language instead.
- **kb-wiki-vnext** — this is the one with the 12 slash commands (session
  start/end, the new-project wizard, the existing-project setup and migration
  commands). If you want those `/` commands, this is the plugin to install.
- **session-gate** — adds `/gate-session-start` and `/gate-session-end` for
  Cowork.

So "I don't see any slash commands" can simply mean you installed `kb-lifecycle`
(which has none) and not `kb-wiki-vnext` (which has all of them). See
[the plugins](../plugins.md) for who's who, and
[installation](../installation.md) for how to add them.

<details><summary>Under the hood / for the CLI</summary>

A plugin never stores your knowledge — it just tells the agent to run the right
`python .kb/kb.py …` command. So even with **no plugin at all**, everything still
works from a terminal:

```bash
python .kb/kb.py lifecycle session-start --json
python .kb/kb.py search "whatever you were looking for"
```

If the slash menu surfaces only generic `session-start` / `session-end` entries
where you'd expect a project's own lifecycle commands, treat that as a packaging
glitch in the plugin rather than a problem with the store. The CLI keeps working
regardless.

</details>

---

## Nothing happened when my session started

You opened the workspace expecting the agent to greet you with where the project
left off — and it didn't. What "should" happen depends on which app you're in,
and the difference matters.

**In Claude Code:** a session-start hook fires *automatically*, but only when the
project actually contains a `.kb/` directory. If your project has a knowledge
base, opening the workspace should quietly load your current context (the
always-on `NOW.md` note). If nothing loaded, the most likely reasons are: there's
no `.kb/` here yet (so there's nothing to load), the `kb-lifecycle` plugin isn't
installed (it's the one carrying that hook), or the workspace needs reopening.

**In Cowork:** session hooks **do not fire on their own**. This is a known
platform gap, not a sign anything is broken. You start the session **explicitly**
— either run `/gate-session-start` (from the `session-gate` plugin) or just say
*"start a KB session."* Make that the first thing you do in a Cowork
conversation, every time, so the agent loads your context before it starts
working.

A quick way to tell whether your session really started: ask *"what's the current
state of this project?"* If the agent answers from your recorded memory, you're
good. If it shrugs, start the session explicitly and try again.

<details><summary>Under the hood / for the CLI</summary>

The bootstrap step the plugins run for you is:

```bash
python .kb/kb.py lifecycle session-start --json
# then the agent reads .kb/memory/NOW.md  (your thin, always-loaded context)
```

A "thin" start is intentional: only `NOW.md` loads by default. The fuller
surfaces — `HOT.md`, the `INDEX.md` map, wiki pages, history — are pulled on
demand when the work actually needs them. If startup ever feels heavy (the agent
reading everything up front), that's a sign the thin default isn't being honored,
not that you're missing context.

</details>

---

## The skill didn't trigger from my wording

You asked for something KB-related — "save this," "remember that we decided X" —
and the agent just answered in chat without recording anything to the knowledge
base.

The everyday `kb-lifecycle` plugin works through a **skill** that the agent
decides to invoke based on what you say. That triggering is **probabilistic**, and
it's noticeably less reliable in **Cowork** than in Claude Code. If your phrasing
was oblique, the agent may not have connected it to the knowledge base.

Two reliable ways to get the behavior you want:

- **Name the action plainly.** Words like *"record a decision,"* *"file this to
  the KB,"* *"ingest this source,"* *"answer from the knowledge base,"* or *"start
  a KB session"* are far more likely to trigger the skill than a vague "save
  this."
- **Use a slash command when one exists.** If you have `kb-wiki-vnext` or
  `session-gate` installed, `/vnext-session-start` or `/gate-session-start` are
  *explicit* — they don't depend on the agent guessing your intent. In Cowork
  especially, prefer the explicit command for anything that must happen.

If the agent still answers without recording, just say so directly: *"that was a
decision — please record it in the KB."* See [everyday use](everyday-use.md) for
the natural phrasings that work well.

---

## Can I mix the CLI and chat?

Yes — freely, and they never conflict.

There is exactly **one** knowledge base per project: the `.kb/` directory. Whether
a record gets created by you asking in chat or by someone running a command in a
terminal, it lands in the same store. Something you filed by chatting will show up
when you (or a teammate, or a different agent) query from the command line later,
and vice versa.

So you don't have to choose. Use chat for the day-to-day ("record this," "what did
we decide about auth?") and drop to the CLI when you want to script something,
batch-import, or run a check — they're two doors into the same room.

<details><summary>Under the hood / for the CLI</summary>

The plugin is purely a convenience layer: when you ask in chat, it runs the
matching `python .kb/kb.py <command>` for you. Nothing is cached in the
conversation. That's why a record filed in chat is immediately visible to:

```bash
python .kb/kb.py search "term"
python .kb/kb.py list --category DECISAO --domain architecture
```

One caveat about *exported* surfaces (the snapshots some agents read on
claude.ai or in Cowork): those are **point-in-time exports**, not a live view of
the store. If you've made meaningful changes, regenerate the export so the
snapshot doesn't go stale. The canonical store is always the `.kb/` SQLite
database — never an export.

</details>

---

## My search didn't find something I know is in there

You searched for a concept and got nothing back, even though you're sure the
project recorded it.

The most common cause is a mismatch in *wording*. KB Factory's search is
**lexical**, not semantic — it matches the actual words and word-beginnings that
appear in your records, **not** paraphrases, synonyms, or concepts. So a search
for "auth approach" won't surface a record titled "login strategy" the way a
search engine with AI-style recall might. This is a deliberate design choice (it
keeps everything local, offline, and dependency-free), not a bug.

What to do when a search comes up empty:

- **Try the words that are likely in the record itself.** Think about how the
  decision was probably *titled* or *worded*, and search for those terms.
- **Search a shorter stem.** "deploy" will match "deployment," "deploying," and
  "deployed"; "auth" will match "authentication" and "authorize."
- **Browse by category or domain instead of searching.** If you remember it was a
  decision about the database, ask the agent to *"list all decisions in the
  database domain"* — that doesn't depend on guessing the exact words at all.
- **Ask the agent to rephrase the query for you.** Since it can read the records,
  it can often find what you mean even when your first search term missed, and
  then tell you the exact wording so your next search lands.

If you genuinely need paraphrase-level or relationship-based recall across a large
store, that's a job for a vector- or graph-backed memory system rather than KB
Factory — see the [comparison](../comparison.md) for an honest take on the
trade-off.

<details><summary>Under the hood / for the CLI</summary>

Search is backed by SQLite's **FTS5** full-text index — keyword and prefix
matching, no embeddings, no vector store. From the CLI:

```bash
python .kb/kb.py search "exact words from the record"
python .kb/kb.py list --category DECISAO --domain architecture
```

The five categories you can filter by are `DECISAO`, `PREMISSA`, `FATO`,
`PENDENCIA`, `APRENDIZADO` (decision, assumption, fact, open-item, learning).

</details>

---

## Setup basics: Python and FTS5

KB Factory runs on the Python standard library and SQLite only — no API key, no
internet connection, no background service. The two things it does need:

- **Python 3.8 or newer.**
- A SQLite build that includes **FTS5** (the full-text search engine behind
  search). Standard CPython from python.org bundles it, but a few minimal or
  repackaged builds leave it out.

If setting up a new project fails, or searches throw errors, an FTS5-less Python
is the usual culprit. You can check in one line:

```bash
python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 OK')"
```

If that prints `FTS5 OK`, you're set. If it errors, install a standard CPython
build (the python.org installers and most distro packages include FTS5) and try
again. If `python` runs the wrong version, use `python3` (macOS/Linux) or `py -3`
(Windows) to be sure you get 3.8+. More setup detail is in
[installation](../installation.md).

---

## Do I even need all this?

Worth saying plainly: if you only want lightweight, current notes for your agent
and you **don't** care about an auditable *history* of how the project's thinking
changed, then `CLAUDE.md` plus your agent's built-in memory is the simpler, right
choice — you don't need KB Factory at all.

KB Factory earns its place when you want the things plain notes can't give you:
typed records, supersession instead of silent overwrite (so you can always see
what changed and why), source provenance, and a queryable history that carries
across sessions and across different agents. If that's what you're after, the
trade-offs are laid out honestly in the [comparison](../comparison.md).

---

## Still stuck? Go deeper

For hands-on, command-line diagnostics — the built-in `doctor` (store integrity
and source-drift checks), `wiki-lint` (derived-page hygiene), the optional
cleanliness gate, and the full FAQ — see the
[troubleshooting reference](../troubleshooting.md).

Related guide pages: [getting started](../getting-started.md),
[everyday use](everyday-use.md), and how a session flows in each app
([agent sessions](../agent-sessions.md)). For the bigger picture, see
[concepts](../concepts.md), [the plugins](../plugins.md), and the
[command reference](../commands.md).
