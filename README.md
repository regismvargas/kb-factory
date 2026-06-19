# KB Factory

**An append-only, source-attributed memory for AI coding agents — local-first, zero-dependency, auditable.**

[![CI](https://github.com/regismvargas/kb-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/regismvargas/kb-factory/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/runtime%20deps-none%20(stdlib%20only)-brightgreen)

KB Factory gives a *project* a durable knowledge base that AI coding agents
(Claude Code, Claude Cowork, Codex) can read and write across conversations. It
runs on nothing but the **Python standard library and SQLite** — no service, no
vector database, no API key, works offline, and backs up as a single file.

> **Why it's different.** Where most agent memory is *consolidative* — it
> improves the current snapshot by overwriting the past — KB Factory is
> **append-only by design**: every superseded decision stays as a linked,
> source-attributed record, so you can reconstruct *what the project believed at
> any past point and exactly what overturned it.*

## Use this if…

- You want a project's **decisions, assumptions, facts, open items, and
  learnings** to persist across sessions and across agents, as an **auditable
  history** — not a snapshot a model silently rewrites.
- You work **offline / air-gapped**, or you simply don't want to run or pay for
  a memory service.
- You value **discipline over magic**: typed records, supersession instead of
  overwrite, source provenance, and a thin, token-cheap startup context.
- You work on a **long-lived or audit-sensitive codebase** — regulated or
  compliance-adjacent work, or a project with high context turnover — where
  *"when did this stop being true, and what overturned it?"* is a question worth
  being able to answer precisely.

## Don't use this if…

- You need **per-user chatbot recall** or **semantic/embedding search** → use
  Mem0, Zep, or Letta. KB Factory's search is lexical (SQLite FTS5).
- You just need lightweight notes and don't care about an auditable *history* →
  `CLAUDE.md` + your agent's built-in memory is simpler and correct.

See [docs/comparison.md](docs/comparison.md) for an honest, sourced comparison
against Anthropic's memory tools and the OSS field.

## Two ways to use it — start here

**Most people install a plugin and just talk to the assistant** in Claude Code or
Cowork — no terminal required:

- **New here, or not a developer?** → the
  **[No-code guide](docs/guide/no-code/index.md)** — a gentle, zero-command
  walkthrough.
- **Comfortable in a chat?** → the **[User Guide](docs/guide/index.md)** — the
  full, task-oriented walkthrough (what to say, sessions, plugins, recipes).

Prefer a terminal? The 60-second CLI quickstart is right below. Both paths read
and write the same `.kb/`.

## Quickstart (≈60 seconds)

The core is a single stdlib-only CLI. Install it from PyPI and scaffold a
project — or copy the scaffold folder directly if you'd rather not use pip:

```bash
# 1. Install the CLI and create a .kb/ in your project (initializes SQLite)
pip install kb-factory
cd /path/to/your-project
kb-factory init
#   No pip? Copy the scaffold instead:
#   cp -r core/templates/kb .kb && python .kb/kb.py init

# 2. Record a decision (typed; HOT = always surfaced at session start)
python .kb/kb.py create --category DECISAO --domain architecture \
  --title "Use SQLite for storage" \
  --content "Local-first, single file, no external services." --tier HOT

# 3. Find it again — in any later session, by any agent
python .kb/kb.py search "storage"

# 4. When the decision changes, SUPERSEDE it (the old record is kept + linked)
python .kb/kb.py supersede <record_id> \
  --title "Use SQLite + FTS5" --content "Added full-text search."
```

(`kb-factory update` later refreshes the vendored `.kb/` runtime to the installed
version, leaving your data untouched.)

At the start of an agent session:

```bash
python .kb/kb.py lifecycle session-start --json   # bootstrap
# then read .kb/memory/NOW.md  (thin, always-loaded context)
```

The five categories are `DECISAO`, `PREMISSA`, `FATO`, `PENDENCIA`,
`APRENDIZADO` (decision, assumption, fact, open-item, learning). `update`
changes only routing metadata (tier/tags); when *meaning* changes you
`supersede`. That's the whole discipline.

## What you get

- **Typed, append-only records** in SQLite — supersede, never overwrite; full
  audit trail. Append-only is enforced by interface discipline by default, with
  **opt-in database-level enforcement** (`kb.py harden`) for those who want a hard
  invariant — see the [integrity model](docs/concepts.md#integrity-model-how-append-only-is-enforced).
- **Provenance** — records link to the sources they came from; `doctor` and
  source-verification catch drift.
- **Thin startup context** — `NOW.md` (and `HOT.md` on demand) keep the
  always-loaded layer small and cheap in tokens.
- **Mechanical maintenance** — `doctor` (integrity), `consolidate` (dedupe +
  tier demotion), tier audits. *(Mechanical, not semantic — semantic merge is
  the operator's/LLM's job.)*
- **Agent integration** — plugins for Claude Code and Claude Cowork; the same
  `.kb/` is the canonical store all of them read.

## Requirements

- **Python 3.8+** and SQLite built with **FTS5** (bundled with standard CPython).
- **No third-party runtime dependencies.** `pytest` is needed only to run the
  test suite.

## Documentation

**New to KB Factory?** Start with the
**[No-code guide](docs/guide/no-code/index.md)** (a gentle, zero-command path for
non-developers) or the **[User Guide](docs/guide/index.md)** (a friendly,
task-oriented walkthrough for using it inside a Claude Code / Cowork
conversation — what to say, how sessions work, which plugins to pick, recipes).
Not sure where the docs live? See the [docs map](docs/README.md). The pages below
are the deeper technical reference.

**Two ways to use it:** in an agent chat (install a [plugin](docs/plugins.md)) or
via the CLI — both read and write the same `.kb/`.

**Start here**

| Doc | What it covers |
|---|---|
| [docs/getting-started.md](docs/getting-started.md) | Install and create your first KB record in under 5 minutes |
| [docs/agent-sessions.md](docs/agent-sessions.md) | Using KB Factory inside a Claude Code / Cowork conversation |
| [docs/plugins.md](docs/plugins.md) | The three plugins: what each does, differences, and combining them |
| [docs/installation.md](docs/installation.md) | Scaffold + plugin installation (Claude Code / Cowork) |
| [docs/concepts.md](docs/concepts.md) | The model: typed records, tiers, supersession, provenance, glossary |
| [docs/commands.md](docs/commands.md) | Slash commands + the authoritative CLI reference |
| [docs/use-cases.md](docs/use-cases.md) | When KB Factory earns its keep — and when not to use it |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Diagnostics, common problems, and FAQ |

**Understand & extend**

| Doc | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Layers, runtime module map, `.kb` vs `.kb-next` boundary |
| [docs/development.md](docs/development.md) | Dev setup, tests, the cleanliness gate, plugin development |
| [docs/releasing.md](docs/releasing.md) | Maintainer build / validate / package flow |
| [docs/comparison.md](docs/comparison.md) | Honest comparison vs. Anthropic's memory stack and the OSS field |
| [docs/merit-evaluation.md](docs/merit-evaluation.md) | The adversarial/hostile/moderated merit debate behind the positioning |
| [docs/provenance-and-continuity.md](docs/provenance-and-continuity.md) | How continuity & provenance work across sessions and agents |

**Project**

| Doc | What it covers |
|---|---|
| [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) | Design lineage and credits |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute (and the load-bearing constraints) |
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities; threat model |

## Project status

Pre-`1.0.0`, and actively developed. The core runtime is stable and tested
(green CI across Linux/macOS/Windows × Python 3.8/3.11/3.13), it's pip-installable
(`pip install kb-factory`), and the docs are complete. Latest release: **v0.1.2**.
Expect additive `0.1.x` releases as the API settles toward `1.0.0`.

## License

[Apache License 2.0](LICENSE). © 2026 KB Factory contributors.
