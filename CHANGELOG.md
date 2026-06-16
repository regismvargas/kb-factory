# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  environments. It now parses with the standard library, so CI passes with no
  third-party test dependency.

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
