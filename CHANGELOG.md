# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Documentation brought fully in line with v0.1.2: pip-first install/upgrade
  (`pip install kb-factory` → `kb-factory init` / `update`) across
  getting-started, installation, the User Guide and recipes (copy-scaffold kept
  as the no-pip fallback; the no-code track stays zero-CLI, now backed by the
  plugin's bundled scaffold); `harden` / read-only `raw-query` covered in
  concepts, commands, troubleshooting and the glossaries; `merit-evaluation.md`
  added to the docs maps; README "Project status" updated to v0.1.2; and the
  developer / releasing / architecture / CONTRIBUTING docs now document the pip
  package, the scaffold-mirror sync tool + parity test, and the PyPI
  build/publish flow.

## [0.1.2] - 2026-06-16

Acted on an external technical review (validated point-by-point against the code).

### Added
- **`pip install kb-factory`** — the engine is now pip-installable with a
  `kb-factory` CLI: `kb-factory init` scaffolds a project's `.kb/` and
  initializes the store; `kb-factory update` refreshes the vendored runtime to
  the installed version (preserving your data), so core fixes can propagate.
- The **kb-lifecycle plugin now bundles the `.kb/` scaffold** (under `scaffold/`),
  so an agent can set up a project KB without a repo checkout.
- Opt-in **append-only database hardening** — `kb.py harden` installs SQLite
  triggers that block direct content `UPDATE` and `DELETE` of
  `records` / `audit_log` / `operations`, turning the CLI's interface discipline
  into a true database invariant (`harden --off` removes them). `doctor` reports
  the state.
- A published **`docs/merit-evaluation.md`** — the adversarial/hostile/moderated
  merit debate that `docs/comparison.md` references (fixes the only broken link).

### Changed
- `raw-query` is now **read-only by default** (`PRAGMA query_only`); pass
  `--allow-write` to deliberately issue writes.
- Docs state the integrity model precisely ("append-only **by interface
  discipline**", with the opt-in DB enforcement via `harden`); the wiki layer is
  documented as optional/off-by-default; the lexical-search trade-off and a
  possible future *opt-in* embeddings adapter are spelled out; the README "Use
  this if" sharpens the audience (regulated / long-lived / high-context-rotation).

## [0.1.1] - 2026-06-16

### Added
- Conversational/chat usage docs: `docs/agent-sessions.md` (using KB Factory in a
  Claude Code / Cowork session) and `docs/plugins.md` (the three plugins — what
  each does, their differences, and how to combine them).
- Slash-command coverage in `docs/commands.md`; a chat-first track in
  `docs/getting-started.md`; `kb-wiki-vnext` install + "what becomes available"
  in `docs/installation.md`; a chat/plugin FAQ in `docs/troubleshooting.md`.
- A dedicated end-user **User Guide** under `docs/guide/` (index, what-and-why,
  install-and-first-session, everyday-use, how-it-works, plugins, recipes,
  troubleshooting): task-oriented, accessible-by-default, with technical/CLI
  detail in collapsible blocks; surfaced from the README.
- A **no-code track** for non-developers under `docs/guide/no-code/` (index,
  what-this-is, first-session, words, when-stuck): a zero-command, Cowork-first
  walkthrough with confirmation checkpoints, a plain-language glossary, and a
  non-technical FAQ.
- User-doc discoverability: a chat-first "start here" callout atop the `README`,
  a `docs/` landing page (`docs/README.md`) that routes by audience, a
  "Using it (start here)" block in each of the three plugin READMEs, and a docs
  pointer added to the marketplace/plugin descriptions.

### Fixed
- Corrected a stale `session-gate` command name in the marketplace description
  (`/gate-session-start` / `/gate-session-end`, not `/session-start`).
- Set the plugin manifests' `license` to **Apache-2.0** (matching the project
  `LICENSE`); they previously declared MIT.
- Synced the marketplace plugin versions to the canonical plugin manifests
  (kb-lifecycle 0.2.1, session-gate 0.2.4, kb-wiki-vnext 0.1.3).
- Made the test suite stdlib-only again: a vNext runtime test parsed
  generated-page frontmatter with PyYAML, which broke CI in `pytest`-only
  environments. It now parses with the standard library, so the suite needs no
  third-party test dependency.
- Restored real **Python 3.8** support: the vNext runtime used
  `Path.is_relative_to` (added in 3.9), so the documented "3.8+" claim failed on
  3.8. Replaced it with a 3.8-safe containment check; the full CI matrix
  (Linux/macOS/Windows × Python 3.8/3.11/3.13) now passes.

## [0.1.0] - 2026-06-16

First public release of KB Factory — the initial open-source extraction from a
private authoring workspace.

### Added
- Apache-2.0 `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, and this changelog.
- `ACKNOWLEDGMENTS.md` crediting design influences (Andrej Karpathy;
  Carlos Perez / @IntuitMachine).
- User & developer documentation under `docs/` (getting-started, installation,
  commands, concepts, use-cases, troubleshooting, architecture, development,
  releasing) plus a sourced competitive comparison and a provenance/continuity
  note.
- Self-cleaning wiki sync, a cleanliness gate (`tools/gate.py` + pre-commit
  hook), and a cross-platform CI matrix (Linux/macOS/Windows × Python
  3.8/3.11/3.13).

### Changed
- Removed internal/private references (cross-repo paths, a private compliance
  artifact, personal contact details) from the published tree.
- Neutralized internal-framework vocabulary in code and documentation.

### Notes
- The core runtime is **standard-library only** (Python + SQLite); no
  third-party runtime dependencies.
- Knowledge is **append-only**: records are superseded, never silently
  overwritten.
