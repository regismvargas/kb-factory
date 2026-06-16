# Getting started

Add a knowledge base to a project and create + find your first record in under
five minutes. KB Factory is a single, stdlib-only CLI — no install step, no
service, no API key. You add it by **copying a scaffold folder** into your
project.

## Before you start

You need:

- **Python 3.8+** with SQLite built for **FTS5**. This is bundled with standard
  CPython on macOS, Linux, and Windows — nothing extra to install.
- A project directory you want to give a durable memory to.

Quick check (any platform):

```bash
python --version
python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 OK')"
```

If both print successfully, you're ready.

> **Not sure you need this?** If you just want lightweight project notes and
> don't care about an auditable *history* of what changed and why, `CLAUDE.md`
> plus your agent's built-in memory is the simpler, correct choice. KB Factory
> earns its keep when you want every superseded decision kept as a linked,
> source-attributed record. See the [comparison](comparison.md) to decide.

> **Prefer to use it inside Claude Code or Cowork?** Most people drive KB Factory
> from an agent conversation — you install a [plugin](plugins.md) and just ask
> the agent to record and recall things; it runs the commands below for you. If
> that's you, skim this page for the model, then jump to
> [Using KB Factory in a session](agent-sessions.md). The steps below set up the
> `.kb/` the plugins use, so they apply either way.
>
> **Not a developer, and would rather not open a terminal at all?** Start with the
> [No-code guide](guide/no-code/index.md) — it walks the whole thing by chat.

## 1. Install the scaffold into your project

KB Factory lives in a single `.kb/` folder. Copy the template from this repo
into the project that should own the knowledge base, then initialize the store.

On macOS / Linux:

```bash
cp -r core/templates/kb /path/to/your-project/.kb
cd /path/to/your-project
python .kb/kb.py init
```

On Windows (PowerShell):

```powershell
Copy-Item -Recurse core/templates/kb C:\path\to\your-project\.kb
Set-Location C:\path\to\your-project
python .kb\kb.py init
```

`init` creates the SQLite store and the thin memory surfaces (`NOW.md`,
`HOT.md`, `INDEX.md`) under `.kb/`. Run it once per project. After that, every
command is `python .kb/kb.py <command>` from the project root.

> One project = one KB. The `.kb/` folder is the single canonical store that
> every conversation and every agent in that project reads and writes.

## 2. Create your first record

Knowledge is filed as **typed records**. There are five categories:

| Category | Meaning |
|---|---|
| `DECISAO` | decision |
| `PREMISSA` | assumption |
| `FATO` | fact |
| `PENDENCIA` | open item |
| `APRENDIZADO` | learning |

Each record also has a **tier** — `HOT`, `WARM`, or `COLD`. `HOT` records are
the ones surfaced into the thin always-loaded context at session start; new
records default to `WARM`.

Record a decision, and mark it `HOT` so an agent sees it immediately:

```bash
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no external services." --tier HOT
```

The command prints the new record's id (for example `DEC-20260615-...`). You'll
use that id later to supersede it.

## 3. Find it again

Search is **lexical** (SQLite FTS5 full-text) — it matches words and phrases,
not meaning, so there is no embedding-based semantic recall.

```bash
python .kb/kb.py search "storage"
```

This works from any later session, in any project, by any agent — the record
lives in `.kb/`, not in a chat transcript.

## 4. Change your mind — supersede, don't overwrite

This is the core discipline. When a decision's **meaning changes**, you don't
edit the old record — you **supersede** it. The old record is retained and
linked, so the history of what the project believed (and what overturned it)
stays reconstructable.

```bash
python .kb/kb.py supersede <record_id> \
  --title "Use SQLite + FTS5" \
  --content "Added full-text search over records."
```

Two related verbs to keep straight:

- **`update`** changes only **routing metadata** — tier, tags, review date. Use
  it when the *meaning* is unchanged but where the record lives should change
  (e.g. demote a `HOT` record to `WARM`).
- **`supersede`** is for when the **meaning** changes. The prior record is never
  discarded.

## 5. Start an agent session

At the start of a coding session, bootstrap the thin context:

```bash
python .kb/kb.py lifecycle session-start --json
```

Then have the agent read `.kb/memory/NOW.md` — the small, always-loaded context.
Load `.kb/memory/HOT.md` or run a `search` only when the conversation needs more.
That's the whole startup loop.

## The five core commands

Everything above is these five:

```bash
python .kb/kb.py init                                    # once per project
python .kb/kb.py create --category <CAT> --domain <d> \
  --title "..." --content "..." [--tier HOT]             # file a typed record
python .kb/kb.py search "<query>"                        # lexical full-text find
python .kb/kb.py supersede <record_id> \
  --title "..." --content "..."                          # replace when meaning changes
python .kb/kb.py lifecycle session-start --json          # bootstrap, then read NOW.md
```

> **Advanced commands.** The CLI also has governance and maintenance verbs —
> source ingestion and provenance (`ingest`, `sources`, `source-verify`),
> mechanical hygiene (`consolidate`, `doctor`, `hygiene-audit`, `audit-tiers`),
> open-item tracking (`pending`, `resolve`), point-in-time exports, and wiki
> generation. These are optional and not part of the day-one path. Note that
> `consolidate` is **mechanical** (exact lowercased-title dedupe + date-based
> tier demotion + integrity checks), *not* semantic; the semantic path is an
> agent proposing merges and supersessions for you to apply. See the full
> [commands](commands.md) reference.

## Next steps

- [commands](commands.md) — the complete command surface.
- [provenance-and-continuity.md](provenance-and-continuity.md) — how source →
  record → session surface keeps memory continuous and auditable.
- [comparison.md](comparison.md) — an honest, sourced comparison against
  Anthropic's memory stack and OSS alternatives, to confirm KB Factory fits.
- [../README.md](../README.md) — project overview and positioning.
