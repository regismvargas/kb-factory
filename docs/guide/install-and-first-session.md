# Install KB Factory and run your first session

This page gets you from nothing to a working knowledge base that your agent
reads and writes for you — in a normal chat. By the end you'll have:

- installed a plugin in **Claude Code** or **Claude Cowork**,
- started your first session,
- recorded a decision just by **asking** for it, and
- recalled it later in plain language.

You won't need to type any commands to do this. You'll talk to the agent the way
you already do, and it runs the right thing behind the scenes. (If you *want* the
exact commands, they're tucked into the "Under the hood" blocks throughout.)

> **Is the KB even for you?** KB Factory shines when you want a durable,
> auditable *history* of what your project decided and why — every superseded
> decision kept and traceable. If you just want lightweight notes and don't care
> about history, your `CLAUDE.md` file plus your agent's built-in memory is the
> simpler, honest choice. See the [comparison](../comparison.md).

---

## Step 1 — Make sure the project has a `.kb/`

The knowledge base lives in a folder called `.kb/` inside your project. That
folder *is* the memory; the plugin is just a convenient way to drive it from
chat.

You have two easy paths:

- **Already have a `.kb/`?** Great — skip to [Step 2](#step-2--install-a-plugin).
- **Starting fresh?** The simplest order is to do
  [Step 2](#step-2--install-a-plugin) **first** (install a plugin), then come back
  here and just say **"set up a knowledge base for this project."** The
  `kb-lifecycle` plugin now **bundles the scaffold**, so the agent can create the
  `.kb/` for you without a repo checkout. If you installed `kb-wiki-vnext`, you
  can instead run **`/new-project-wizard`**. (Prefer to do it by hand? The "Under
  the hood" block below has the one-time steps, including `pip install
  kb-factory`.)

<details><summary>Under the hood / for the CLI</summary>

The `.kb/` is a single stdlib-only Python CLI plus a SQLite store — local-first,
offline, no API key. The quickest way to create it by hand is the published CLI:

```bash
pip install https://github.com/regismvargas/kb-factory/releases/download/v0.1.4/kb_factory-0.1.4-py3-none-any.whl
cd /path/to/your-project
kb-factory init
python .kb/kb.py stats   # confirm it worked
```

No pip? Copy the scaffold from a checkout of the repo instead:

```bash
cp -r core/templates/kb /path/to/your-project/.kb
cd /path/to/your-project
python .kb/kb.py init
```

On Windows PowerShell, `Copy-Item -Recurse core/templates/kb C:\path\to\your-project\.kb`.

It needs **Python 3.8+** with SQLite built for **FTS5** (bundled with standard
CPython everywhere). Verify:

```bash
python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 OK')"
```

Full details in [installation.md](../installation.md).

</details>

---

## Step 2 — Install a plugin

Start with **`kb-lifecycle`**. It's the everyday workflow plugin: it carries a
skill that wakes up when you mention things like "KB", "session start", or
"record a decision", and (in Claude Code) a hook that loads your context
automatically when you open the project. It has no slash commands to memorize —
you just talk.

You can add the other two plugins later:

- **`session-gate`** — add this if you work in **Cowork**, which doesn't fire
  hooks automatically. It gives you reliable `/gate-session-start` and
  `/gate-session-end`.
- **`kb-wiki-vnext`** — add this if you want the thin-session model, project
  setup/migration commands, or a review step before durable changes land.

For what each plugin does, see [the plugins](../plugins.md).

### In Claude Code

1. Add this repository as a plugin marketplace.
2. Install `kb-lifecycle`.
3. Reopen your project so the agent picks it up.

<details><summary>Under the hood / for the CLI</summary>

```bash
claude plugin marketplace add regismvargas/kb-factory
claude plugin install kb-lifecycle@kb-factory-tools
claude plugin list
```

To try it for a single session without installing permanently:

```bash
claude --plugin-dir /path/to/kb-factory/plugins/kb-lifecycle
```

Later, to add the others:

```bash
claude plugin install session-gate@kb-factory-tools
claude plugin install kb-wiki-vnext@kb-factory-tools
```

</details>

### In Claude Cowork

1. Open Claude Desktop and switch to **Cowork**.
2. Go to **Customize → Plugins**.
3. Add `regismvargas/kb-factory` as a GitHub plugin marketplace, or upload
   `kb-lifecycle-cowork-plugin-0.2.3.zip` from release `v0.1.4`.

If you're on Cowork, also install **`session-gate`** the same way — you'll want
its explicit session commands, because Cowork won't start sessions on its own.

<details><summary>Under the hood / for the CLI</summary>

Cowork installs plugins through the UI, not a command line. To add the optional
plugins, repeat step 3 with `session-gate-cowork-plugin-0.2.7.zip` and
`kb-wiki-vnext-cowork-plugin-0.1.9.zip`. A plugin never stores your memory —
the `.kb/` you created in Step 1 stays the single source of truth.

</details>

### Confirm it's installed

Type **`/`** in the chat. If you installed `session-gate` or `kb-wiki-vnext`,
their slash commands appear in the menu (`/gate-session-start`,
`/vnext-session-start`, …). `kb-lifecycle` adds **no** slash commands by design —
it works entirely through its skill, so the way to confirm it is to start a
session in the next step.

---

## Step 3 — Start your first session

A "session start" loads a thin, always-current summary of the project (a file
called `NOW.md`) so the agent doesn't guess at context. How you trigger it
differs by platform — this is the one real difference between Code and Cowork.

### In Claude Code — it's automatic

Just **open the project**. Because there's a `.kb/`, the `kb-lifecycle` hook
fires and the agent quietly reads `NOW.md` before doing anything. You'll often
see it acknowledge the project's current state in its first reply. Nothing for
you to type.

If for some reason it didn't, just say:

> "Start a KB session."

### In Claude Cowork — you start it explicitly

Cowork doesn't fire hooks automatically, so kick the session off yourself. Either
run the slash command:

> `/gate-session-start`

or just ask:

> "Start a KB session."

The agent loads `NOW.md` (and only what else it needs) and is ready to go.

<details><summary>Under the hood / for the CLI</summary>

A session start runs the bootstrap command and then reads the thin context file:

```bash
python .kb/kb.py lifecycle session-start --json
# then the agent reads .kb/memory/NOW.md
```

In Code this is triggered by the SessionStart hook; in Cowork
`/gate-session-start` (from `session-gate`) detects whether `.kb/` and/or
`.kb-next/` are present and routes to the matching startup. More in
[agent-sessions.md](../agent-sessions.md).

</details>

---

## Step 4 — Record a decision by asking

Here's the core habit. When something durable comes up — a decision you made, a
fact you learned, an assumption you're working from, an open question, a lesson —
just **say it in plain language** and ask the agent to record it. You don't pick
a format or a command; the agent classifies it and writes it.

Try this:

> "Record a decision: we'll use SQLite for storage — it's local-first and needs
> no external service. Mark it as important so it's always loaded."

The agent files it as a typed **decision** record and (because you said
"always loaded") puts it in the **HOT** tier so it surfaces at every future
session start. You'll get back a short confirmation with the record's title and
ID.

Knowledge is **typed** — every record is one of five kinds:

| You're capturing… | Type | Example phrasing |
|---|---|---|
| A choice you made | **decision** | "Record a decision: we'll ship weekly." |
| Something you're taking as given | **assumption** | "Note an assumption: traffic stays under 1k/day." |
| A verified truth | **fact** | "Record a fact: the API rate limit is 100/min." |
| A question still open | **open item** | "Log an open item: pricing tier not decided yet." |
| A lesson learned | **learning** | "Capture a learning: retries without backoff caused the outage." |

You don't need to say the type out loud — "remember that…" or "note that…" works
fine and the agent picks the right one. But naming it helps when you care.

Knowledge is also **tiered**: **HOT** (always loaded at session start), **WARM**
(the default — searchable, pulled in when relevant), and **COLD** (archived but
never deleted). Say "keep this front and center" or "this is important" to get
HOT; most things are fine as WARM.

<details><summary>Under the hood / for the CLI</summary>

That request maps to a single CLI call the plugin makes for you:

```bash
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no external services." --tier HOT
```

The five categories are `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`,
`APRENDIZADO` (decision, assumption, fact, open-item, learning). The tiers are
`HOT` / `WARM` / `COLD`. The store is **append-only**, so this record now exists
permanently — even after it's later superseded. See the full
[command reference](../commands.md).

</details>

---

## Step 5 — Recall it — now or in a future session

This is the payoff. Instead of scrolling back or hoping the agent remembers, just
**ask**:

> "What did we decide about storage, and why?"

The agent searches the knowledge base and answers from it — quoting the actual
recorded decision and its reasoning — rather than guessing from the conversation.
This works in the same session, tomorrow, or months later, and it works across
agents: a record filed by Claude Code is visible to Cowork and vice-versa,
because they read the same `.kb/`.

Other things you can just ask:

> "What's still open on this project?"
>
> "Show me everything we know about the API limits."

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py search "storage"   # full-text search across the store
python .kb/kb.py pending            # list open items
```

Search is SQLite FTS5, so it's fast and fully offline. See
[commands.md](../commands.md).

</details>

---

## Step 6 — When something changes, supersede (don't overwrite)

Plans change. When a recorded belief is no longer true, **don't ask the agent to
edit or delete it** — ask it to **supersede** it. The old record stays, linked to
the new one, so the *history* of why the decision changed is preserved. That
audit trail is the whole point of using a KB instead of a notes file.

> "We switched storage to SQLite + FTS5 for search — supersede the old decision."

Now "what did we decide about storage?" returns the current answer, and the
trail back to the original is intact if anyone ever asks "why did this change?"

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py supersede <old-record-id> \
  --title "Use SQLite + FTS5 for storage and search" \
  --content "Adds full-text search; supersedes the prior SQLite-only decision."
```

`supersede` creates a new record and marks the old one superseded — it never
mutates or removes the original. (There's also `update` for metadata-only tweaks
like tier, and `resolve` to close an open item.) See
[commands.md](../commands.md).

</details>

---

## Step 7 — Close the session

When you're done, wrap up so the KB consolidates and refreshes any exports.

- **Claude Code:** say "let's close the session."
- **Claude Cowork:** run **`/gate-session-end`** (you can pass a session id, e.g.
  `/gate-session-end S14`), or say "wrap up."

The agent runs a quick housekeeping pass and gives you a short summary of what
changed.

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py lifecycle session-end --json
```

In Cowork, `/gate-session-end` runs a pre-close audit and routes to the matching
closeout for whatever plugins you have installed.

</details>

---

## The one thing to remember: Code vs Cowork

Everything above is identical on both platforms **except how a session starts**:

| | Claude Code | Claude Cowork |
|---|---|---|
| **Session start** | **Automatic** — opening the project loads `NOW.md` | **Explicit** — run `/gate-session-start` or say "start a KB session" |
| **Skill triggering** | Reliable | Probabilistic — if it didn't fire, ask explicitly |
| **Recommended plugins** | `kb-lifecycle` | `kb-lifecycle` + `session-gate` |

If a Cowork session ever feels like it lost context, the fix is almost always
just to run `/gate-session-start` explicitly.

---

## Where to go next

- [Everyday use](everyday-use.md) — the day-to-day rhythm of filing, searching,
  and superseding once you're set up.
- [Agent sessions](../agent-sessions.md) — how a chat session flows end to end.
- [The plugins](../plugins.md) — what each plugin does and which combination fits
  you.
- [Concepts](../concepts.md) — typed/tiered/append-only memory explained.
- [Comparison](../comparison.md) — when KB Factory is worth it, and when
  `CLAUDE.md` + built-in memory is enough.
