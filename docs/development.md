# Developer guide

This page is for people who want to **hack on KB Factory itself** — fix a bug,
extend the runtime, add a check, or build a plugin. If you just want to *use* a
KB in your project, start with the [README](../README.md) quickstart instead.

Before you open a pull request, read [CONTRIBUTING.md](../CONTRIBUTING.md) — it
spells out the load-bearing constraints (the most important ones are summarized
below).

## The one constraint that shapes everything

**The runtime imports only the Python standard library.** No `pip install`
dependencies, ever. This is not a stylistic preference — it *is* the product:

- the KB must clone, run, and back up offline with nothing but CPython + SQLite;
- the whole store is a single file you can copy, diff, and version;
- the only hard requirement is **SQLite built with FTS5**, which ships with
  standard CPython.

`pytest` is the one exception, and it is a **test-runner only** — never imported
by the runtime. A PR that adds a third-party runtime import will not be merged.

Two more constraints from `CONTRIBUTING.md` that the code enforces:

- **Append-only by design.** `update` changes routing metadata only; when a
  record's *meaning* changes you `supersede` it (the old record is kept and
  linked). Don't add code paths that delete or rewrite the meaning of records.
- **Memory is index + curation, not raw storage.** Don't add features that
  bulk-load transcripts or logs into the curated layer.

## Dev setup

You need a recent Python 3 (the project targets **3.8+**). No other tooling is
required to run the core.

```bash
git clone <your-fork-url>
cd kb-factory

# optional virtualenv
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate

# pytest is the only dev dependency (test runner, not a runtime dep)
pip install pytest
```

## Running the tests

The suite lives in `tests/` and runs against the in-repo runtime. From the repo
root:

```bash
pytest                        # full suite
pytest tests/test_filing.py   # one file
pytest -k supersede           # by keyword
```

`pytest` must be green before you open a PR. A few tests worth knowing about:

- **`tests/test_runtime_modularization.py`** is the *runtime-parity* test. KB
  Factory ships the runtime in three places — the canonical `core/runtime/`, the
  scaffold template `core/templates/kb/runtime/`, and the live workbench copy
  `.kb/runtime/` — and this test asserts they stay byte-identical. If you edit
  the runtime, edit the canonical copy and re-sync the mirrors, or this test
  (and the gate, below) will fail.
- **`tests/test_provenance.py`** and **`tests/test_sources.py`** cover the
  source → record linkage and hash-drift detection.
- **`tests/test_wiki*.py`** cover the derived wiki layer (generation, lint,
  hygiene gates).

If you touched the runtime, scaffold, or wiki generation, also run the integrity
check:

```bash
python core/runtime/cli.py doctor   # schema / invariant integrity
```

## The cleanliness gate

`tools/gate.py` is a fast, deterministic check that the workbench KB is in a
shippable, trustworthy state. It runs no tests — it just confirms the KB hasn't
drifted. It runs three checks and exits non-zero on any failure:

1. **`doctor`** — SQLite integrity is `ok` and there is **zero source hash
   drift** (no recorded source has been mutated out from under its hash).
2. **`wiki-lint`** — the live wiki has **zero** lint issues.
3. **parity** — `core/runtime/*.py` is byte-identical to both the scaffold
   template runtime and the live `.kb/runtime/`, and `.kb/kb.py` matches the
   template `kb.py`.

Run it directly any time:

```bash
python tools/gate.py
```

It prints exactly what drifted and how to fix it (typically
`python .kb/kb.py wiki-sync --force` or re-syncing the runtime mirrors).

### Enable it as a pre-commit hook

The hook lives in `.githooks/pre-commit` (it just `exec`s `python
tools/gate.py`). Enable it once per clone:

```bash
git config core.hooksPath .githooks
```

After that, a commit is blocked if the gate fails. To bypass it for a single
commit (e.g. a docs-only change):

```bash
git commit --no-verify
```

The same gate is meant to run in CI, so the authoring repo can't drift back into
a stale-wiki / hash-drift / out-of-sync-runtime state.

## Developing or extending a plugin

Plugins are how KB Factory reaches the agent runtimes (Claude Code, Claude
Cowork, Codex). They are deliberately **thin**: a plugin does not own durable
memory — it points the agent back at the workspace `.kb/` and its CLI. Plugin
and export artifacts must stay disposable and never become a second
memory store.

The reference plugin is `plugins/kb-lifecycle/`:

```
plugins/kb-lifecycle/
  .claude-plugin/plugin.json        # Claude manifest (name, version, skills dir)
  .codex-plugin/plugin.json         # Codex manifest
  hooks/hooks.json                  # Claude SessionStart reminder hook
  scripts/session_start_context.py  # stdlib helper the hook runs
  skills/kb-wiki-maintainer/
    SKILL.md                        # the skill: name + description front-matter, then body
    reference.md
    agents/openai.yaml
  README.md
```

To extend it:

- **Edit the skill body** in `skills/<skill>/SKILL.md`. The YAML front-matter
  (`name`, `description`) is what the agent matches on, so keep the description
  specific. The body is procedural guidance — it should reuse the same `python
  .kb/kb.py` commands a human would, never invent a parallel storage path.
- **Touch a hook** only via `hooks/hooks.json`; keep hook scripts stdlib-only,
  like the rest of the runtime. The session-start hook just injects a short
  reminder when a `.kb/` directory is present.
- **Keep both manifests in step.** If you add a skill or bump a version, update
  both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

Package the plugin into distributable ZIPs with the bundled builder (stdlib
only, covered by `tests/test_build_agent_packages.py`):

```bash
python tools/build_agent_packages.py
```

This produces a plugin ZIP (files at archive root, for Claude/Cowork upload) and
a standalone skill ZIP (for a direct Codex/Claude skill install). See the plugin
`README.md` for the per-runtime install surfaces.

## Code style

The runtime is plain, explicit Python — no clever metaprogramming. Match the
surrounding code, keep each PR to one logical change, and update docs when you
change behavior. If you change the command surface, update
[commands](commands.md).

## Where to go next

- [CONTRIBUTING.md](../CONTRIBUTING.md) — full contribution rules and the
  non-negotiable constraints.
- [commands](commands.md) — the full CLI surface.
- [SECURITY.md](../SECURITY.md) — report vulnerabilities privately; do **not**
  open a public issue for security bugs.
