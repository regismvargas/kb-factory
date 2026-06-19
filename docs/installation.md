# Installation

KB Factory installs in two parts, and you can use either or both:

1. **The scaffold** — drop a `.kb/` directory into your project. This is the
   knowledge base itself: a single stdlib-only CLI plus the SQLite store. It is
   all you need; everything works from the command line.
2. **The agent plugins** *(optional)* — install the KB Factory plugin for
   **Claude Code** or **Claude Cowork** so the agent runs session-start and the
   core commands for you instead of you typing them by hand.

The scaffold is the product. The plugins are a convenience layer on top of it.

> **Not a developer / prefer chat?** If you'd rather not use a terminal, the
> [No-code guide](guide/no-code/index.md) walks you through installing a plugin
> and getting a working knowledge base entirely by chatting in Cowork.

## Requirements

- **Python 3.8+** with SQLite built for **FTS5** (bundled with standard
  CPython on macOS, Linux, and Windows).
- **No third-party runtime dependencies.** `pytest` is needed only if you run
  the test suite.

Verify your interpreter has FTS5:

```bash
python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 OK')"
```

If that prints `FTS5 OK`, you are ready.

## Part 1 — Scaffold a project

The fastest way is the published CLI:

```bash
pip install kb-factory
cd /path/to/your-project
kb-factory init        # scaffolds .kb/ and initializes the SQLite store
```

`kb-factory update` later refreshes the vendored runtime in `.kb/` to the
installed version, leaving your data (`kb.db`, `memory/`, config) untouched —
this is how core fixes reach a project scaffolded from an older version.

**No pip?** Copy the `.kb/` scaffold from a checkout of this repo and initialize
it directly. The commands below work on macOS, Linux, and Windows (PowerShell
understands forward slashes in paths).

```bash
# from a checkout of this repo:
cp -r core/templates/kb /path/to/your-project/.kb
cd /path/to/your-project

# initialize the SQLite store
python .kb/kb.py init
```

On Windows PowerShell, use `Copy-Item -Recurse` if you prefer native cmdlets:

```powershell
Copy-Item -Recurse core/templates/kb C:\path\to\your-project\.kb
```

That is the whole install. Confirm it worked:

```bash
python .kb/kb.py stats
```

### First records

```bash
# record a typed decision (HOT = surfaced at session start)
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no external services." --tier HOT

# find it again — in any later session, by any agent
python .kb/kb.py search "storage"
```

The five categories are `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`,
`APRENDIZADO` (decision, assumption, fact, open-item, learning). See
[commands.md](commands.md) for the full reference.

### Starting an agent session against the KB

```bash
python .kb/kb.py lifecycle session-start --json   # bootstrap
# then read .kb/memory/NOW.md  (thin, always-loaded context)
```

You can stop here. The plugins below just automate this step.

> **Do you even need the KB?** If you only want lightweight notes and don't
> care about an auditable belief *history*, `CLAUDE.md` plus your agent's
> built-in memory is the simpler, correct choice. KB Factory earns its keep when
> you want every superseded decision kept and source-attributed. See
> [comparison.md](comparison.md).

## Part 2 — Install the agent plugins (optional)

KB Factory ships **three plugins** — `kb-lifecycle` (the everyday workflow),
`kb-wiki-vnext` (thin-session model + governed proposals), and `session-gate`
(reliable session boundaries for Cowork). For what each does and which to
install, see **[plugins.md](plugins.md)**; for how a session flows once
installed, see **[agent-sessions.md](agent-sessions.md)**. Most users start with
`kb-lifecycle`.

A plugin doesn't store anything itself. It carries skills/commands that tell the
agent to run `lifecycle session-start`, read `NOW.md`, and use the core commands
— so the canonical store stays the `.kb/` you created in Part 1.

> Plugins are a convenience. The `.kb/` directory remains the single source of
> truth; a plugin never becomes a second memory.
>
> **After install:** type `/` in the chat to see the plugin's slash commands, and
> ask the agent to "start a KB session" to trigger its skill.

### Claude Code

Add this repository as a plugin marketplace, then install the `kb-lifecycle`
plugin:

```bash
claude plugin marketplace add /path/to/kb-factory
claude plugin install kb-lifecycle@kb-factory-tools
claude plugin list
```

To try a plugin without installing it permanently, point Claude Code at the
plugin folder for one session:

```bash
claude --plugin-dir /path/to/kb-factory/plugins/kb-lifecycle
```

**Verify:** open Claude Code in a project that has a `.kb/` directory and ask it
to start a KB session. The `kb-wiki-maintainer` skill should run
`python .kb/kb.py lifecycle session-start --json` and then read
`.kb/memory/NOW.md`.

**Update / remove:**

```bash
claude plugin marketplace update kb-factory-tools
claude plugin update kb-lifecycle@kb-factory-tools
claude plugin disable kb-lifecycle   # disable before removing when diagnosing
```

### Claude Cowork

Cowork installs plugins from a folder or marketplace through the UI:

1. Open Claude Desktop and switch to Cowork.
2. Open **Customize → Plugins**.
3. Either add this repository as a GitHub plugin marketplace, or upload the
   `plugins/kb-lifecycle` folder as a custom plugin.

**Verify:** the plugin appears under **Customize → Plugins**, and asking the
agent to start a KB session reads only `.kb/memory/NOW.md` by default.

> **Session boundaries in Cowork.** Cowork doesn't run automatic session-start
> hooks the way Claude Code can. If you want explicit start/end prompts, install
> the `session-gate` plugin: it provides `/gate-session-start` and
> `/gate-session-end`, which detect and route to whichever KB plugins are present
> (`.kb/` and/or `.kb-next/`). Treat it as an explicit command, not an automatic
> trigger. See [plugins.md](plugins.md).

### KB/Wiki vNext (optional)

To use the thin-session model and the project setup/migration commands, install
`kb-wiki-vnext` the same way as `kb-lifecycle`:

```bash
claude plugin install kb-wiki-vnext@kb-factory-tools   # Claude Code
```

(or upload `plugins/kb-wiki-vnext` via **Customize → Plugins** in Cowork). It
adds 12 slash commands (`/vnext-session-start`, `/new-project-wizard`,
`/existing-project-*`, …) and keeps `.kb/` canonical while using `.kb-next/` for
proposals. See [plugins.md](plugins.md).

## Troubleshooting

- **`FTS5 OK` check fails.** Your Python was built without FTS5. Install a
  standard CPython build (python.org installers and most distro packages include
  it) and retry.
- **`python` runs the wrong version.** Use `python3` (macOS/Linux) or `py -3`
  (Windows) so you get Python 3.8+.
- **The plugin's commands or skill don't appear.** Confirm the marketplace was
  added and the plugin installed (`claude plugin list`), then reopen the
  workspace so the skill index refreshes.
- **The agent edits files instead of the KB.** Remind it that `.kb/` is
  canonical and that records change via `create` / `update` / `supersede`, not by
  hand-editing.

## Advanced

The repo also ships maintenance and governance commands beyond the core five —
`doctor` (integrity), `consolidate` (mechanical dedupe + date-based tier
demotion), `audit-tiers`, `hygiene-audit`, `ingest`, `source-verify`, and the
`wiki-*` family that compiles a derived Markdown wiki. These are for upkeep and
auditing, not day-to-day filing; run `python .kb/kb.py --help` to list them, and
see [commands.md](commands.md) for details.

## Next steps

- [commands.md](commands.md) — the full command surface.
- [comparison.md](comparison.md) — when to use KB Factory and when not to.
- [provenance-and-continuity.md](provenance-and-continuity.md) — how memory
  stays continuous across sessions and agents.
