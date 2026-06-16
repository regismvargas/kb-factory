# The plugins

KB Factory ships **three plugins** so you can drive the knowledge base from
inside a Claude Code or Claude Cowork **conversation** — via slash commands,
auto-triggering skills, and (in Claude Code) a session-start hook — instead of
typing `python .kb/kb.py …` yourself.

The plugins are **thin**: none of them owns your memory. The durable memory is
always the project's `.kb/` (a single SQLite file the agent reads and writes
through the CLI). A plugin just makes that convenient in chat. You can install
one, two, or all three.

> New here? Read [agent-sessions.md](agent-sessions.md) for how a session
> actually flows; this page is the reference for *what each plugin is*.

## At a glance

| Plugin | What it owns | Slash commands | Auto-triggering skill | Session hook | Platforms |
|---|---|---|---|---|---|
| **kb-lifecycle** | the everyday `.kb/` workflow | — (skill-driven) | `kb-wiki-maintainer` | ✅ SessionStart (Claude Code) | Code · Cowork · Codex |
| **kb-wiki-vnext** | thin-session model + governed proposals (`.kb-next/`) | **12** (`/vnext-*`, `/existing-project-*`, `/new-project-*`) | `kb-wiki-vnext` | informational only | Code · Cowork · Codex |
| **session-gate** | nothing — detects & routes | **2** (`/gate-session-start`, `/gate-session-end`) | `session-gate` | — | Cowork (primarily) · Code · Codex |

**The short version:** start with **kb-lifecycle** (the everyday workflow). Add
**session-gate** if you work in **Cowork** (which doesn't auto-fire hooks). Add
**kb-wiki-vnext** if you want the thin-session model and governed proposals.

---

## kb-lifecycle — the everyday KB workflow

**What it's for:** the day-to-day knowledge-base lifecycle — bootstrap a session,
ingest sources, file typed records, search, refresh the optional wiki, and run
maintenance. This is the plugin most users start with.

- **Slash commands:** none. It works through its skill.
- **Skill — `kb-wiki-maintainer`:** auto-triggers in conversation when you
  mention "KB", "knowledge base", "ingest source", "session start", "update
  wiki", or "answer from KB", or simply when the workspace has a `.kb/`
  directory. It then runs the right CLI commands for you (session bootstrap,
  `ingest`, `create`/`file`, `search`, `wiki-sync`, lifecycle maintenance).
- **Session hook (Claude Code):** when a session starts in a workspace that has
  a `.kb/`, the plugin injects a short reminder so the agent loads `NOW.md`
  before assuming context. (This is the "automatic" behavior Cowork lacks — see
  session-gate.)
- **Platforms:** Claude Code, Claude Cowork, Codex.
- **Use it when:** you want the normal KB workflow in chat. For most projects on
  Claude Code, this plugin alone is enough.

---

## kb-wiki-vnext — thin-session harness + governed proposals

**What it's for:** a leaner session model and a *governed* path for durable
changes. It starts a session reading **only `NOW.md`** (pulling more on demand),
and routes proposed changes through a review step before they touch the
canonical KB. The classic `.kb/` stays the source of truth; this plugin keeps
its working state (proposals, manifests, draft wiki) in a separate `.kb-next/`.

- **Skill — `kb-wiki-vnext`:** auto-triggers for thin-session work, targeted
  lookup, proposal review/apply, and project setup.
- **Session hook:** informational only (prints a reminder to run the
  session-start command).
- **Platforms:** Claude Code, Claude Cowork, Codex.
- **Use it when:** you want the thin-session model, you're **setting up or
  migrating a project**, or you want changes to go through a review/proposal step
  rather than being written directly.

**Slash commands (12):**

*Session*
- `/vnext-session-start` — start a thin session; read only `NOW.md` by default.
- `/vnext-session-end` — close the session, recording useful evidence; durable
  changes are routed through the governed apply step, not written silently.

*Set up / migrate an existing project*
- `/existing-project-diagnose` — read-only check of an existing (or legacy)
  project before you activate anything.
- `/existing-project-activate-vnext` — activate the thin-session model in an
  existing project (KB-alone or KB+Wiki) **without overwriting** the classic KB.
- `/existing-project-configure-vnext` — adjust the mode / run a guided
  activation for an existing project.
- `/existing-project-verify-install` — read-only verification after
  install / activate / upgrade / rollback.
- `/existing-project-upgrade-vnext` — upgrade the runtime, keeping `.kb/`
  canonical.
- `/existing-project-rollback-vnext` — roll back to the prior runtime,
  preserving evidence.

*Start a new project*
- `/new-project-wizard` — bootstrap a fresh workspace; routes to one of the two
  init commands, then verifies.
- `/new-project-init-kb-alone` — initialize a new project in **KB-alone** mode.
- `/new-project-init-kb-wiki` — initialize a new project in **KB + Wiki** mode.
- `/new-project-verify-install` — read-only verification after bootstrapping.

### Advanced — governed proposals & checks

Beyond sessions and setup, kb-wiki-vnext provides a **review-gated** path for
durable change, intended for power users and project maintainers. In short: an
agent can *propose* a change (a new record, a supersession, a merge, a wiki
draft); the proposal is recorded under `.kb-next/`; and it only reaches the
canonical `.kb/` after an explicit apply step. The relevant capabilities are
`semantic-lookup` (LLM-assisted retrieval), `semantic-hygiene` (report-only
review of HOT overflow / duplicates / stale items), the proposal → apply flow,
and `compliance-preflight` (a checklist gate for development work). Day-to-day
users don't need these; they exist so durable memory is never mutated
un-reviewed. See [commands.md](commands.md) for the underlying CLI verbs.

---

## session-gate — one reliable entry point for Cowork

**What it's for:** Claude Cowork does **not** automatically fire session hooks,
so the "load `NOW.md` at the start" behavior that's automatic in Claude Code
won't happen on its own. `session-gate` gives Cowork a single, explicit
session-boundary entry point. It **owns nothing** — it detects which subsystems
are present (`.kb/`, `.kb-next/`, a companion workflow) and routes startup and
closeout to them.

- **Slash commands (2):**
  - `/gate-session-start` — detect the workspace, then route to the right
    startup (kb-wiki-vnext first if present, else kb-lifecycle), and present a
    briefing of only the subsystems that actually exist.
  - `/gate-session-end` — detect, run a pre-close audit, route the matching
    closeout (kb-wiki-vnext evidence summary and/or kb-lifecycle `session-end` +
    `hygiene-audit`), and produce a concise summary. Accepts an optional
    session id, e.g. `/gate-session-end S14`.
- **Skill — `session-gate`:** triggers on explicit requests like "session
  start", "wrap up" (and the Portuguese "iniciar sessão" / "encerrar sessão").
- **Session hook:** none (it's the workaround *for* the missing hook).
- **Platforms:** Cowork primarily; also Claude Code and Codex.
- **Use it when:** you work in **Cowork** and want one dependable command to
  start and end sessions that routes to whatever KB plugins you have installed.

> Honest note: in Cowork, skill triggering is probabilistic — if a session
> didn't start cleanly, just invoke `/gate-session-start` explicitly.

---

## Use them together or separately

There are **no command-namespace collisions** (kb-lifecycle has no slash
commands; kb-wiki-vnext uses `vnext-*` / `existing-project-*` / `new-project-*`;
session-gate uses `gate-*`), so any combination is safe. Recommended setups:

| You are… | Install | Why |
|---|---|---|
| On **Claude Code**, everyday KB use | **kb-lifecycle** | The hook auto-loads context; the skill handles ingest/file/search. Simplest. |
| On **Cowork**, everyday KB use | **kb-lifecycle + session-gate** | Cowork won't auto-fire hooks; `session-gate` gives you reliable `/gate-session-start` and `/gate-session-end`. |
| Piloting the **thin-session model** | **kb-lifecycle + kb-wiki-vnext** | `.kb/` stays canonical; `.kb-next/` holds proposals/manifests; choose `/vnext-session-start` per session. |
| **Cowork + thin-session + a workflow** | **all three** | `session-gate` detects and routes to each; the kb-wiki-vnext startup runs first when `.kb-next/` is present. |

Key principles when combining:
- **One canonical store.** Only `.kb/` is durable memory. kb-wiki-vnext's
  `.kb-next/` is working state; session-gate stores nothing.
- **kb-wiki-vnext first under the gate.** If both `.kb-next/` and `.kb/` exist,
  `/gate-session-start` routes to the kb-wiki-vnext startup first.
- **No duplication.** session-gate points at existing surfaces — it never
  creates a second memory layer.

## See also
- [agent-sessions.md](agent-sessions.md) — how a chat session flows with these plugins.
- [installation.md](installation.md) — installing the plugins in Claude Code / Cowork.
- [commands.md](commands.md) — the slash commands and the underlying CLI.
- [comparison.md](comparison.md) — how KB Factory compares to other memory tools.
