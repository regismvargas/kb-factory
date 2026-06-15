# Contributing to KB Factory

Thanks for your interest in KB Factory. This project is small, opinionated, and
deliberately dependency-free — contributions are welcome, but a few constraints
are load-bearing and non-negotiable.

## Core constraints (please read first)

1. **Standard library only.** The runtime (`core/runtime/`) must import only the
   Python standard library — no `pip install` dependencies. This is the product:
   it must clone, run offline, and back up as a single SQLite file. PRs that add
   a third-party runtime dependency will not be merged.
2. **Append-only by design.** Knowledge is never silently overwritten. `update`
   changes only routing metadata; when the *meaning* of a record changes, use
   `supersede` (which links the new record to the old and preserves the audit
   trail). Do not add code paths that delete or mutate the meaning of records.
3. **Memory is index + curation, not raw storage.** Do not add features that
   bulk-load transcripts/logs into the curated layer.

See [docs/architecture.md](docs/architecture.md) for the full design rationale.

## Development setup

```bash
git clone <your-fork-url>
cd kb-factory
python -m venv .venv && . .venv/bin/activate   # optional
pip install pytest                              # test runner only; not a runtime dep
pytest
```

Requirements: a recent Python 3 (see the version declared in the README/CI
matrix). No other tooling is required to run the core.

## Before you open a PR

- **Run the tests:** `pytest` must be green.
- **Run the integrity checks** if you touched the runtime, scaffold, or wiki
  generation:
  - `python core/runtime/cli.py doctor` (schema / invariant integrity)
  - the runtime-parity test (ensures the scaffold template stays in sync with
    the canonical runtime)
- Keep changes focused; one logical change per PR.
- Match the surrounding code style (the runtime is plain, explicit Python — no
  clever metaprogramming).
- Update docs when you change behavior. If you change the command surface,
  update [docs/commands.md](docs/commands.md).

## Commit messages

Use clear, imperative commit subjects (e.g. "Add stale-premise audit to doctor").
Reference issues where relevant.

## Reporting bugs and proposing features

Open a GitHub issue using the provided templates. For anything security-related,
do **not** open a public issue — see [SECURITY.md](SECURITY.md).

## License of contributions

By contributing, you agree that your contributions are licensed under the
project's [Apache License 2.0](LICENSE).
