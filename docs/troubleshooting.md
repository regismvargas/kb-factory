# Troubleshooting & FAQ

This page covers the common setup and usage problems you'll hit with KB Factory,
the two built-in diagnostics (`doctor` and `wiki-lint`), the optional
cleanliness gate, and an honest FAQ about what the tool does and does *not* do.

The entry point for the CLI is `python .kb/kb.py`. If you use KB Factory through
a plugin in Claude Code / Cowork, see the **chat session** issues just below and
[agent-sessions.md](agent-sessions.md). See [commands](commands.md) for the full
surface and [comparison](comparison.md) for how KB Factory compares.

---

## Using KB Factory in a chat session

**The slash menu shows only generic session commands, not the KB ones.** The
plugin isn't loaded for this workspace. Confirm it's installed (Claude Code:
`claude plugin list`; Cowork: **Customize → Plugins**), then reopen the workspace
so the command/skill index refreshes — see [installation.md](installation.md).

**Nothing happens at session start.** In **Cowork**, session hooks don't fire
automatically — start explicitly with `/gate-session-start` (the `session-gate`
plugin) or say "start a KB session" to trigger the skill. In **Claude Code**, the
hook only injects context when the workspace has a `.kb/` directory.

**The skill didn't trigger from my wording.** Skill triggering is probabilistic
(especially in Cowork). Invoke the command explicitly (`/vnext-session-start`,
`/gate-session-start`) or name the action ("ingest this source", "answer from the
KB").

**Can I mix the CLI and the plugin?** Yes — both read and write the same `.kb/`.
A record filed in chat is visible from `python .kb/kb.py search …` and
vice-versa.

See [agent-sessions.md](agent-sessions.md) and [plugins.md](plugins.md).

---

## Diagnostics first

Before debugging by hand, run the two read-only diagnostics. Neither mutates the
store, and both speak `--json` for scripts and CI.

### `doctor` — store integrity and provenance drift

```bash
python .kb/kb.py doctor --json
```

`doctor` reports whether the SQLite store is healthy and whether any source has
drifted. Key fields:

- `integrity_check` — should be `"ok"` (this is SQLite's `PRAGMA integrity_check`).
- `sources_hash_drift` — number of ingested sources whose on-disk content no
  longer matches the hash recorded at ingest time. Should be `0`.
- `sources_missing_files` — ingested sources whose file is gone. Should be `0`.
- `records_table` / `fts_table` — confirm the records table and the FTS5 index
  both exist.

If `sources_hash_drift` is non-zero, a file you ingested has changed underneath
its record. Use `source-status --hash-drift` to list which ones, then re-ingest
or update the source so provenance stays trustworthy.

### After `harden`, did I break my workflow?

No. `harden` installs append-only triggers that block only *destructive* direct
SQL — editing a record's title/content in place, or deleting records / the logs.
The normal flow is unaffected: `create`, `update` (tier/tags), `supersede`,
`resolve`, `search`, and the lifecycle commands all keep working, because they
add or re-route rather than rewrite content in place. `doctor --json` shows
`append_only_hardening: "enabled"`; run `python .kb/kb.py harden --off` to remove
the triggers. If a *direct* `UPDATE`/`DELETE` (e.g. via `raw-query --allow-write`
or an external SQLite tool) now raises `append-only: …`, that's the guard working
as intended — use `supersede` instead.

### `wiki-lint` — derived-page hygiene

```bash
python .kb/kb.py wiki-lint --json
```

`wiki-lint` checks the live wiki (the derived Markdown pages) for issues such as
broken citations or pages that no longer trace cleanly to records. An
`issue_count` of `0` means the live wiki is clean. If you don't use the wiki
layer, this will simply report zero pages and zero issues.

---

## Common problems

### The agent loaded too much context at startup

The always-loaded layer is meant to be thin. By default a session loads only
`.kb/memory/NOW.md`. `HOT.md`, `.kb/memory/INDEX.md`, wiki pages, and history are
**on demand** — the agent should pull them only when the working set clearly
needs them. If startup feels heavy, confirm your harness or skill is honoring
the thin default and not eagerly reading every surface.

### Session start did nothing / the hook didn't fire

Some platforms (notably Claude Cowork) do not fire automatic session hooks. That
is a missing hook, **not** permission to skip session start. Run it explicitly:

```bash
python .kb/kb.py lifecycle session-start --json
# then read .kb/memory/NOW.md
```

If you use a plugin or slash command for session start, invoke it manually at
the top of the conversation.

### A wiki page contradicts a KB record

The **record wins.** Wiki pages are *derived* output; when they disagree with a
record, the page is stale. Re-derive it:

```bash
python .kb/kb.py wiki-sync          # refresh derived pages from records
python .kb/kb.py wiki-lint --json   # confirm zero issues
```

If a page can't be reconciled, remove it from the live wiki rather than leaving
contradictory output in place.

### A decision exists only in chat

Chat scrollback is not durable memory. If a decision, assumption, or learning
only lives in a conversation, file it before relying on it next session:

```bash
python .kb/kb.py create --category DECISAO --domain <domain> \
  --title "..." --content "..." --tier HOT
```

### My change to a record disappeared / the old text is still there

KB Factory is **append-only**: records are never edited in place when their
*meaning* changes. If you want to change what a record *says*, you don't edit it
— you `supersede` it. The old record is retained and linked; the new one becomes
active:

```bash
python .kb/kb.py supersede <record_id> --title "..." --content "..."
```

Use `update` only for routing metadata (tier, tags, review dates). `update` does
not change meaning, and that's by design.

### Search isn't finding an obviously-related record

Search is **lexical** (SQLite FTS5), not semantic. It matches words and
prefixes, not paraphrases or concepts. If a query misses, try the actual terms
that appear in the record, broaden to a stem, or list by facet instead:

```bash
python .kb/kb.py search "exact words from the record"
python .kb/kb.py list --category DECISAO --domain architecture
```

There is no embedding-based recall — see the FAQ below.

### `init` fails or FTS queries error out

KB Factory needs **Python 3.8+** and a SQLite build with **FTS5**. Standard
CPython ships FTS5, but some minimal or repackaged builds omit it. Verify:

```bash
python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 OK')"
```

If that errors, install a CPython build with FTS5 enabled and re-run
`python .kb/kb.py init`.

### `consolidate` didn't merge two records I expected it to

That's expected. `consolidate` is **mechanical**, not semantic — it does exact
lowercased-title de-duplication plus date-based tier demotion and integrity
upkeep. It will *not* recognize that two differently-worded titles mean the same
thing. Merging by meaning is a deliberate, governed step: the agent uses
semantic lookup to propose a merge or supersession, which is then reviewed and
applied. Mechanical consolidation never silently rewrites your knowledge.

### The slash-command menu shows generic session commands

If the platform menu surfaces only generic `session-start` / `session-end`
entries instead of the project's own lifecycle commands, treat that as a
packaging regression in the plugin, not a runtime problem. The CLI
(`python .kb/kb.py lifecycle session-start`) still works regardless.

---

## The cleanliness gate (optional)

`tools/gate.py` is a fast, deterministic pre-commit / CI check that the KB is in
a shippable, trustworthy state. It runs three checks and exits non-zero if any
fails:

1. **doctor** — SQLite `integrity_check` is `ok` and `sources_hash_drift` is `0`.
2. **wiki-lint** — zero issues on the live wiki.
3. **parity** — the canonical runtime, the scaffold template runtime, and the
   live `.kb/` runtime are byte-identical (catches a copy left out of sync).

```bash
python tools/gate.py
```

A clean run prints `KB gate OK`. On failure it lists exactly what drifted, e.g.
`source hash drift = 2` or `live .kb runtime drift: cli.py`. Typical fixes:

- Wiki out of date → `python .kb/kb.py wiki-sync --force`, then re-run the gate.
- Source hash drift → re-ingest or update the changed source.
- Runtime parity drift → re-sync the runtime mirrors so all copies match.

The gate is a project-hygiene tool for contributors and maintainers; you do not
need it to *use* a KB. If you must commit past it once, `git commit --no-verify`
bypasses it — but fix the underlying drift rather than making bypass a habit.

---

## FAQ

**Does KB Factory do semantic / embedding search?**
No. Retrieval is **lexical** via SQLite FTS5 — keyword and prefix matching, no
embeddings, no vector store, no semantic recall. If you need paraphrase or
relational recall at scale, a vector- or graph-backed system (Mem0, Zep, Cognee)
is the right tool. See [comparison](comparison.md).

**Is `consolidate` "smart"? Will it clean up my KB by understanding it?**
No. `consolidate` is purely **mechanical**: exact lowercased-title dedupe,
date-based tier demotion, and integrity maintenance. Semantic merges and
supersessions are proposed by the LLM and applied through a governed review
step, never automatically.

**Are the Cowork and claude.ai surfaces a live sync of my KB?**
No. They are **point-in-time exports**. There is one canonical SQLite store; the
exports are snapshots that go stale if you don't regenerate them. Re-export after
meaningful changes if an agent reads those surfaces.

**Does updating a record overwrite the old one?**
No. KB Factory is **append-only**. `update` only changes routing metadata
(tier/tags/dates). When meaning changes you `supersede`, which keeps the old
record linked so you can reconstruct what the project believed at any past point
and exactly what overturned it. See
[provenance-and-continuity](provenance-and-continuity.md).

**Do I even need this? I just want notes for my agent.**
Possibly not. If you don't need an auditable *belief history* — just lightweight,
current notes — then `CLAUDE.md` plus your agent's built-in memory is the simpler,
correct choice. KB Factory earns its keep when you need typed records,
supersession instead of silent overwrite, source provenance, and a queryable
history across sessions and agents.

**Does it need an internet connection, an API key, or a running service?**
No. It runs on the Python standard library and SQLite only — fully offline,
no key, no service, and the whole store backs up as a single file.

**Can multiple agents share one KB?**
Yes. Continuity is **project-scoped**: one project, one canonical `.kb/`. Every
conversation and every agent in that project reads and writes the same store via
the CLI, so a learning filed by one agent is immediately available — and
attributable — to the next.

---

## Advanced diagnostics

For deeper inspection beyond the two core diagnostics:

- `source-status` (with `--hash-drift`, `--missing-file`, `--uncovered`) and
  `source-verify` — pin down exactly which sources drifted.
- `hygiene-audit` and `audit-tiers` — surface tier and hygiene issues.
- `oplog` — read the append-only operation log to see who changed what, when,
  and why.

These live in the full [commands](commands.md) reference. The quickstart in the
[README](../README.md) deliberately surfaces only the core handful.
