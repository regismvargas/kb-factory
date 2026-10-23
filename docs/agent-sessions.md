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

- **Plugin commands.** `kb-wiki-vnext` adds 13 (`vnext-session-start`,
  `new-project-wizard`, `vnext-wiki-drafts`, …); `session-gate` adds 2
  (`gate-session-start`, `gate-session-end`); `kb-lifecycle` adds none and
  works through its skill. These are logical names, not one literal invocation
  for every client: Claude Code lists them in the `/` menu prefixed with the
  plugin name (for example `/kb-wiki-vnext:vnext-session-start`), Codex runs
  them through the plugin's skill when you ask in natural language, and Cowork
  uses the action its plugin UI exposes.
- **An auto-triggering skill.** `kb-lifecycle`'s `kb-wiki-maintainer` skill
  activates on its own when you mention things like "KB", "knowledge base",
  "ingest this source", "session start", "update the wiki", or "answer from the
  KB" — or simply when the workspace has a `.kb/`.
- **(Claude Code only) a session-start hook.** When you open a project that has
  a `.kb/`, `kb-lifecycle` injects a short reminder so the agent loads
  `.kb/memory/NOW.md` *before* assuming anything. If the project has also
  activated vNext (a `.kb-next/kb-next.config.json` is present), the hook
  defers to vNext instead: it does not ask the agent to read `.kb/memory/NOW.md`,
  and the agent reads `.kb-next/memory/NOW.md` by default. From kb-wiki-vnext
  0.2.4 the vNext hook prints the session start itself (activation mode, the
  NOW header, wiki state, on-demand reads and a command sheet), so the agent
  makes no start call and reads `.kb-next/memory/NOW.md` only when the hint
  says the team wrote it. Cowork doesn't do this automatically. That's what
  `session-gate` is for.
- **(vNext projects) a write gate.** With `kb-wiki-vnext` installed and vNext
  active, the agent files new records and supersessions only after you
  approve: in one `approved-filing` call when you approve in chat, or through a
  proposal it shows you and applies with `proposal-apply` once you approve.
  The plugin's write gate hook denies an agent's direct
  `.kb/kb.py create`, `file`, `supersede`, `update`, `resolve` or
  `bulk-import` (in Codex, once you
  trust the plugin's PreToolUse hook). Classic-only projects keep the direct
  commands.

## First session — in Claude Code

1. **Open the project** (one that has a `.kb/`). The `kb-lifecycle` hook fires
   and the agent reads `.kb/memory/NOW.md` — a short, always-loaded summary.
   (No `.kb/` yet? Ask the agent to set one up — the `kb-lifecycle` plugin bundles
   the scaffold, so no repo checkout is needed; or use the `new-project-wizard`
   plugin command; or run `kb-factory init` from a terminal.)
2. **Work normally.** When something durable comes up, just say so:
   > "Record a decision: we'll use SQLite for storage — it's local-first and
   > needs no service."

   The agent files it as a typed `DECISAO` record (it runs `create`/`file` under
   the hood; with vNext active it files it with `approved-filing` once you
   approve in chat, or prepares a proposal and applies it after you approve). Same for facts, assumptions, open items, and learnings.
3. **Recall later — in this or a future session:**
   > "What did we decide about storage, and why?"

   The agent searches the KB and answers from it (rather than guessing).
4. **When something changes**, ask it to **supersede** (not overwrite):
   > "We switched storage to SQLite + FTS5 — supersede the old decision."
5. **Wrap up:** "let's close the session" → the agent consolidates and refreshes
   the exports.

## First session — in Claude Cowork

Cowork does **not** auto-fire hooks, so start the session explicitly:

1. Start with the **`gate-session-start`** plugin command, as your Cowork plugin
   UI exposes it (or say "session start"). `session-gate` detects
   whether `.kb/` / `.kb-next/` are present and loads the thin context for you.
   (If you installed only `kb-lifecycle`, just say "start a KB session" to invoke
   its skill.)
2. **Work the same way** as above — ask the agent to record decisions/facts and
   to answer from the KB.
3. **Close with the `gate-session-end` plugin command**, or say "wrap up".
   It files what you approved and runs the matching closeout: in a vNext
   workspace one `lifecycle session-end`, plus `wiki-draft-status` when the
   wiki is active. Curation runs in the weekly maintenance run, or when you
   ask for a full maintenance pass.

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

In a project with KB/Wiki vNext active, the "record" and "supersede" rows go
through `approved-filing` once you approve in chat, or through
`filing-proposal` and, after your approval, `proposal-apply` instead;
the write gate denies the direct commands, and the session starts from the
vNext hook's hint (or `vnext-session-start` where no hook runs) and closes
with one `lifecycle session-end`, plus `wiki-draft-status` with an active
wiki. See [KB/Wiki vNext runtime](commands.md#kbwiki-vnext-runtime).

Full command reference (slash **and** CLI): [commands.md](commands.md).

## Platform differences

| | Claude Code | Claude Cowork | Codex |
|---|---|---|---|
| Session start | **Automatic** (hook loads `NOW.md`) | **Manual**: the `gate-session-start` command or the skill | command / skill |
| Slash menu | Yes (`/`, plugin commands prefixed with the plugin name) | plugin actions in the UI | no plugin slash commands: ask in plain language and the plugin skill runs |
| Skill auto-trigger | Yes | Probabilistic — invoke explicitly if needed | Yes |
| Exports to other tools | `.kb/` is read directly | point-in-time export packs | point-in-time export packs |

## Tips

- Prefer **`kb-lifecycle`** for the everyday workflow; add **`session-gate`** on
  Cowork; add **`kb-wiki-vnext`** for the thin-session model and governed
  proposals. See [plugins.md](plugins.md).
- If the slash menu shows only generic session commands, or the skill didn't
  fire, see [troubleshooting.md](troubleshooting.md) — usually you just invoke
  the command explicitly.
