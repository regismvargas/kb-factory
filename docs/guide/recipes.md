# Recipes

Short, copy-pasteable tasks you can do **just by talking to the agent** in a
Claude Code or Cowork conversation. Each recipe shows what to *say*, what the
agent does for you, and how to confirm it worked. You don't type commands — you
describe what you want, and the plugin runs the right thing under the hood.

New here? Read [everyday use](everyday-use.md) first for the rhythm of a session,
then come back for specific tasks. For the full vocabulary, see the
[command reference](../commands.md); to understand the ideas (typed records,
tiers, supersession), see [concepts](../concepts.md).

> Throughout, the quoted lines are things **you** say in chat. You can paste them
> almost verbatim — swap in your own topic. The agent will confirm and, when a
> record is created or changed, tell you its id (something like
> `DEC-20260616-…`).

---

## 1. Capture a decision and *why* you made it

The single most valuable thing you can do. A decision without its reasoning gets
quietly re-litigated three weeks later; a decision *with* its reasoning sticks.

**Say this:**

> "Record a decision: we'll store data in SQLite instead of Postgres, because we
> want local-first with zero ops. We considered Postgres and rejected it for the
> operational overhead. Mark it as important so it stays loaded."

**What happens.** The agent files a typed `decision` record. It puts the choice
in the title and your *reasoning and the alternative you rejected* in the body —
that's the part that pays off later. Asking for it to be "important" puts it in
the always-loaded set so future sessions see it immediately without you
re-explaining.

**Confirm it:**

> "Show me that decision."

The agent reads it back, including the rationale.

> **Tip — what to put in the body.** Lead with the *why*, name the option you
> rejected, and note any constraint that drove the choice. "We picked X because
> Y, not Z, given constraint C" ages far better than just "We use X."

<details><summary>Under the hood / for the CLI</summary>

The agent runs roughly:

```bash
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage, not Postgres" \
  --content "Local-first, zero ops. Considered Postgres; rejected for operational overhead." \
  --tier HOT
```

`--category DECISAO` is the decision type; the five categories are `DECISAO`
(decision), `PREMISSA` (assumption), `FATO` (fact), `PENDENCIA` (open item),
`APRENDIZADO` (learning). `--tier HOT` is "important / always loaded"; new
records default to `WARM`. The command prints the new id.

</details>

---

## 2. Find what changed about a decision — and why

This is the recipe most other memory tools can't do, because they overwrite the
old answer when a new one lands. KB Factory keeps both, linked.

**First, when the decision actually changes, supersede it (don't overwrite):**

> "That storage decision changed — we moved to SQLite plus full-text search
> because plain SQLite couldn't query record contents. Supersede the old
> decision with this."

The agent retires the old record and files a new one **linked** to it. Nothing is
lost.

**Later, to see the history:**

> "What did we decide about storage, and what did we believe before? Walk me
> through what changed and why."

**What happens.** The agent searches the knowledge base, finds the current
decision, follows the link back to the superseded one, and tells you the
sequence: what the project believed, what replaced it, and the reason captured at
the time. If you want the paper trail of *when* changes were logged, ask:

> "Show me the recent activity log for the knowledge base."

> **Why this matters.** "Why did we move off X?" is answerable months later, for a
> postmortem, an audit, or onboarding someone new — without anyone having to
> remember the conversation it happened in.

<details><summary>Under the hood / for the CLI</summary>

Changing meaning:

```bash
python .kb/kb.py supersede <record_id> \
  --title "Use SQLite + FTS5 for full-text search" \
  --content "Lexical search was needed; plain SQLite couldn't query content."
```

Reconstructing history:

```bash
python .kb/kb.py search "storage"     # find current + see supersession link
python .kb/kb.py get <record_id>      # read a specific record
python .kb/kb.py oplog                # the operation log: lifecycle/ingest events
```

Don't confuse `supersede` with `update`: `update` only changes routing metadata
(tier, tags, review date) and leaves the meaning — and the record — in place.
Use `supersede` whenever the *meaning* changes. See [concepts](../concepts.md).

</details>

---

## 3. Carry context across a new session — or a second agent

The point of a durable memory is that the *next* conversation starts where the
last one ended, even with a different agent.

### Same project, next session (Claude Code)

Just **open the project**. The `kb-lifecycle` session-start hook fires
automatically and the agent loads the thin always-loaded summary
(`NOW.md`) before doing anything. Then ask for whatever you need:

> "What's the current state of the project? What did we decide last session?"

The agent answers from the knowledge base, not from a transcript it doesn't have.

### Same project, next session (Cowork)

Cowork does **not** fire hooks automatically, so start the session explicitly:

> Run **`/gate-session-start`** — or just say "start a KB session."

That loads the thin context for you. Then continue as above. (Skill triggering in
Cowork is probabilistic, so if nothing seems to load, run the slash command
explicitly.)

### Handing off to another agent (e.g. Claude Code → Codex → Cowork review)

You don't export or copy anything. **One project = one knowledge base**, and
every agent reads and writes the same `.kb/` through the same commands. So a
learning one agent files is immediately available to the next:

> "Record a learning: CI fails on Windows because of path separators — use
> pathlib, not string joins. It bit us in the export step."

Then, in the *other* agent's session:

> "What do we know about Windows path issues in CI?"

It comes back, with where it came from.

> **Honest scope.** Continuity is *within one project's* `.kb/`. The Cowork and
> claude.ai export packs are **point-in-time snapshots**, not a live sync — if you
> rely on them, regenerate them when memory changes (just ask the agent to "close
> the session and refresh the exports"). The live, always-correct source is the
> `.kb/` in the repo. See [agent sessions](../agent-sessions.md) for the platform
> differences in one table.

<details><summary>Under the hood / for the CLI</summary>

Session bootstrap (what the hook or `/gate-session-start` triggers):

```bash
python .kb/kb.py lifecycle session-start --json   # then read .kb/memory/NOW.md
```

Cross-agent continuity works because every runtime calls the same
`python .kb/kb.py …` against the same SQLite file committed in the repo — there's
no per-agent account and no service to stand up. A record filed via one agent's
`create` is returned by another agent's `search`, with its source attribution.

</details>

---

## 4. Work fully offline or air-gapped

There's nothing special to enable — this is the default. The entire runtime is
the **Python standard library plus SQLite**: no network calls, no external store,
no API key.

**Say this (it works the same with no connection):**

> "Record a decision …" / "What did we decide about …?" / "What's still open?"

Everything runs locally. The whole knowledge base is a **single file** you can
copy, commit to git, diff in a review, or carry on a USB stick to a disconnected
machine.

**To back it up or move it:**

> "Where does the knowledge base live so I can back it up?"

The agent points you at the `.kb/` folder; copying it copies the entire memory.

> **When this is the deciding factor.** Disconnected networks, strict proxies, or
> just not wanting to run and pay for a vector database — KB Factory is viable
> where hosted memory layers aren't an option. (If you *do* have connectivity and
> want embedding-based semantic recall, KB Factory's search is lexical, not
> semantic — see the [comparison](../comparison.md).)

<details><summary>Under the hood / for the CLI</summary>

The store is `.kb/kb.db` (SQLite, with an FTS5 full-text index). No `pip install`,
no daemon, no key. To back up: copy the `.kb/` directory, or just commit it. To
verify integrity offline:

```bash
python .kb/kb.py doctor
```

</details>

---

## 5. Review what's still open

"What's unresolved?" gets re-asked every session. Make the knowledge base answer
it instead of relying on memory.

**File open items as you hit them:**

> "Add an open item: we still need to decide on the auth provider before the beta."

**Then, any time:**

> "What's still open in this project?"

The agent lists every open item that hasn't been resolved.

**When you close one out, resolve it — don't delete it:**

> "We picked Auth0 for the auth provider — resolve that open item and note why."

The open item is marked resolved and kept, with your note. The trail of what
*was* open survives, so nothing about the project's history disappears.

> **Want a quick health check?** Ask "give me the knowledge base stats" — the
> agent reports counts by type and tier, a fast way to see how much is open,
> decided, or learned.

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py create --category PENDENCIA --domain auth \
  --title "Decide auth provider before beta" --content "..."
python .kb/kb.py pending                 # everything still open
python .kb/kb.py resolve <record_id> --notes "Picked Auth0; SSO + low ops."
python .kb/kb.py stats                   # counts by category / tier
```

Resolving keeps the record (status changes) rather than removing it — same
append-only discipline as supersession.

</details>

---

## 6. Bring an existing project under KB Factory

You don't have to start fresh. You can give a project that already has history a
durable memory without disturbing anything that's there.

**If you have the `kb-wiki-vnext` plugin, the safest path is to look before you
leap:**

> Run **`/existing-project-diagnose`** — or say "diagnose this project for KB
> Factory."

This is **read-only**. It reports what the project already has (any existing
knowledge base, wiki output, a usable runtime) and recommends the next step. It
won't change a thing.

**Then activate, without overwriting what exists:**

> Run **`/existing-project-activate-vnext`** — or say "activate KB Factory here
> without touching my existing setup."

It sets up the thin-session model alongside your project's existing state. The
default is the lighter "knowledge base only" mode; ask explicitly if you want the
derived wiki too.

**Don't have that plugin? You can still adopt it conversationally:**

> "Set up a knowledge base for this project and record our first few decisions
> from what's already here."

The agent scaffolds `.kb/` and starts filing the decisions, facts, and open
items you describe.

**Then seed it.** The fastest way to make the memory useful is to back-fill the
handful of things that matter:

> "Let's capture the durable knowledge we already have. I'll list our key
> decisions, current assumptions, and open items — file each one with its
> reasoning."

> **Should you even adopt it?** If you only want lightweight, overwritable notes
> and don't care about an auditable *history* of what changed and why,
> `CLAUDE.md` plus your agent's built-in memory is the simpler, correct choice.
> KB Factory earns its keep when you want every superseded decision kept and
> queryable. See the [comparison](../comparison.md) to decide before you commit.

<details><summary>Under the hood / for the CLI</summary>

The `/existing-project-diagnose` command checks for `.kb/`, `.kb/kb.py`, vNext
`.kb-next/`, and wiki output, then recommends a path — it never mutates the
store. `/existing-project-activate-vnext` defaults to "kb-alone" mode and refuses
to overwrite an existing `.kb/`. Related commands:
`/existing-project-configure-vnext`, `/existing-project-verify-install`,
`/existing-project-upgrade-vnext`, `/existing-project-rollback-vnext`.

To scaffold a knowledge base manually from the terminal — quickest is the
published CLI:

```bash
pip install kb-factory && kb-factory init            # run in the project root
# no pip? copy the scaffold instead:
# cp -r core/templates/kb /path/to/your-project/.kb && python .kb/kb.py init
```

See [the plugins](../plugins.md) for which plugin gives you which commands.

</details>

---

## 7. Ingest a document and turn it into filed knowledge

When the durable knowledge lives in a file (a spec, a research note, a meeting
doc), you can register it and have the agent file what matters — with the source
attached, so later you can trace a fact back to where it came from.

**Say this:**

> "Ingest this document into the knowledge base, then file the key facts and one
> analysis from it, each linked to the source."

**What happens.** The agent registers the file (a copy is stored and cataloged;
duplicates are skipped by content hash), reads it, and files typed records —
facts, learnings, decisions — **linked to that source**. Later you can ask:

> "What do we know that came from that document?"

and get the records *with* their provenance.

> **Curation, not capture.** The agent files what's worth keeping, not the whole
> document — so the memory stays a curated set of durable beliefs rather than a
> dumping ground. That's a deliberate trade: you get signal, not a transcript.

<details><summary>Under the hood / for the CLI</summary>

```bash
python .kb/kb.py ingest <path> --domain <domain> --json   # copies + catalogs the file
python .kb/kb.py sources                                   # list registered sources
python .kb/kb.py create --category FATO --domain <domain> \
  --title "..." --content "..." --source-id <source_id>    # file a record linked to it
python .kb/kb.py source-verify                             # confirm sources still match their hash
```

The `file` command (`--filing-type answer|analysis|synthesis`) is a thin wrapper
over `create` that adds filing intent, automatic tagging, and an entry in the
operation log — useful when you want the audit trail to record *why* something
was filed. See [the command reference](../commands.md).

</details>

---

## Where to go next

- [Everyday use](everyday-use.md) — the rhythm of a normal session.
- [The command reference](../commands.md) — every slash command and CLI verb.
- [Concepts](../concepts.md) — typed records, tiers, and supersession explained.
- [Agent sessions](../agent-sessions.md) — Claude Code vs. Cowork differences.
- [Comparison](../comparison.md) — an honest look at whether KB Factory is the
  right tool for you.
