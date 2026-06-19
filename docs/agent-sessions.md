# Using KB Factory in a Claude Code / Cowork session

There are **two ways** to use KB Factory, and they read and write the **same**
`.kb/`:

1. **In an agent conversation** (Claude Code / Cowork) — you install a
   [plugin](plugins.md) and then just *talk to the agent*; it runs the knowledge
   base for you via slash commands and skills. **This is how most people use it,
   and this page is about this path.**
2. **From the terminal** — you run `python .kb/kb.py …` yourself. See
   [getting-started.md](getting-started.md) and [commands.md](commands.md).

You can freely mix the two: a record you file in chat is visible from the CLI and
vice-versa.

## What you get after installing a plugin

Once a plugin is installed (see [installation.md](installation.md)):

- **Slash commands** appear in the `/` menu — type `/` to see them.
  `kb-wiki-vnext` adds 12 (`/vnext-session-start`, `/new-project-wizard`, …);
  `session-gate` adds 2 (`/gate-session-start`, `/gate-session-end`);
  `kb-lifecycle` adds none — it works through its skill.
- **An auto-triggering skill.** `kb-lifecycle`'s `kb-wiki-maintainer` skill
  activates on its own when you mention things like "KB", "knowledge base",
  "ingest this source", "session start", "update the wiki", or "answer from the
  KB" — or simply when the workspace has a `.kb/`.
- **(Claude Code only) a session-start hook.** When you open a project that has
  a `.kb/`, `kb-lifecycle` injects a short reminder so the agent loads
  `.kb/memory/NOW.md` *before* assuming anything. Cowork doesn't do this
  automatically — that's what `session-gate` is for.

## First session — in Claude Code

1. **Open the project** (one that has a `.kb/`). The `kb-lifecycle` hook fires
   and the agent reads `.kb/memory/NOW.md` — a short, always-loaded summary.
   (No `.kb/` yet? Ask the agent to set one up — the `kb-lifecycle` plugin bundles
   the scaffold, so no repo checkout is needed — or run `/new-project-wizard`, or
   `kb-factory init` from a terminal.)
2. **Work normally.** When something durable comes up, just say so:
   > "Record a decision: we'll use SQLite for storage — it's local-first and
   > needs no service."

   The agent files it as a typed `DECISAO` record (it runs `create`/`file` under
   the hood). Same for facts, assumptions, open items, and learnings.
3. **Recall later — in this or a future session:**
   > "What did we decide about storage, and why?"

   The agent searches the KB and answers from it (rather than guessing).
4. **When something changes**, ask it to **supersede** (not overwrite):
   > "We switched storage to SQLite + FTS5 — supersede the old decision."
5. **Wrap up:** "let's close the session" → the agent consolidates and refreshes
   the exports.

## First session — in Claude Cowork

Cowork does **not** auto-fire hooks, so start the session explicitly:

1. Run **`/gate-session-start`** (or say "session start"). `session-gate` detects
   whether `.kb/` / `.kb-next/` are present and loads the thin context for you.
   (If you installed only `kb-lifecycle`, just say "start a KB session" to invoke
   its skill.)
2. **Work the same way** as above — ask the agent to record decisions/facts and
   to answer from the KB.
3. **Close with `/gate-session-end`** (optionally with a session id, e.g.
   `/gate-session-end S14`). It runs the pre-close audit and the matching
   closeout.

## The conversational workflow (both platforms)

The discipline is the same whether you type commands or talk:

- **Start thin.** Load `NOW.md` first; pull `HOT.md`, the full index, or a
  search **only when the conversation needs it**. This keeps context cheap.
- **File durable, non-derivable knowledge** as one of five types — decision,
  assumption, fact, open-item, learning. Just describe it; the agent picks the
  type and writes it.
- **Supersede, don't overwrite.** When meaning changes, the old record is kept
  and linked — so the history of *why* a decision changed survives.
- **Search before assuming.** Ask the agent to check the KB rather than rely on
  scrollback.
- **End the session** to consolidate and refresh exports.

## How chat maps to the CLI

Every conversational action is just a CLI call the plugin makes for you:

| You say (in chat) | The agent runs |
|---|---|
| "start a KB session" / hook fires | `python .kb/kb.py lifecycle session-start --json`, then reads `NOW.md` |
| "record a decision that …" | `python .kb/kb.py create --category DECISAO …` |
| "what did we decide about X?" | `python .kb/kb.py search "X"` |
| "that changed — supersede it" | `python .kb/kb.py supersede <id> …` |
| "what's still open?" | `python .kb/kb.py pending` |
| "close the session" | `python .kb/kb.py lifecycle session-end --json` |

Full command reference (slash **and** CLI): [commands.md](commands.md).

## Platform differences

| | Claude Code | Claude Cowork | Codex |
|---|---|---|---|
| Session start | **Automatic** (hook loads `NOW.md`) | **Manual** — `/gate-session-start` or the skill | command / skill |
| Slash menu | Yes (`/`) | Yes (plugin) | Yes |
| Skill auto-trigger | Yes | Probabilistic — invoke explicitly if needed | Yes |
| Exports to other tools | `.kb/` is read directly | point-in-time export packs | point-in-time export packs |

## Tips

- Prefer **`kb-lifecycle`** for the everyday workflow; add **`session-gate`** on
  Cowork; add **`kb-wiki-vnext`** for the thin-session model and governed
  proposals. See [plugins.md](plugins.md).
- If the slash menu shows only generic session commands, or the skill didn't
  fire, see [troubleshooting.md](troubleshooting.md) — usually you just invoke
  the command explicitly.
