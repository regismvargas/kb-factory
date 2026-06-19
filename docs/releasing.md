# Release Guide (maintainers)

This page is for **maintainers cutting a release**. It documents the
build → validate → package flow and the order the scripts must run in. If you
only want to *use* KB Factory, you don't need any of this — see the
[README](../README.md) and [commands](commands.md).

Everything here runs on the **Python standard library only**. The build scripts
live in `tools/` and write their output under `dist/`.

## The rule that comes first: the gate must pass

Before you build or tag anything, the **cleanliness gate must pass**. It is a
fast, deterministic check (no full test run) that the canonical knowledge base
is in a shippable state:

```bash
python tools/gate.py
```

It verifies three things and exits non-zero if any fail:

1. **`doctor`** — SQLite integrity is `ok` and there is **zero source-hash
   drift**.
2. **`wiki-lint`** — zero issues on the live wiki.
3. **parity** — the canonical runtime (`core/runtime/*.py`) is byte-identical to
   the scaffold template runtime and the live `.kb` runtime, and `.kb/kb.py`
   matches the distributed template `kb.py`.

If the gate fails, fix the cause (the gate prints what drifted, e.g. re-sync the
runtime mirrors or run `python .kb/kb.py wiki-sync --force`) and re-run it. Do
not build a release on top of a failing gate.

Also run the test suite before tagging:

```bash
pytest
```

## Update the CHANGELOG

Update [`CHANGELOG.md`](../CHANGELOG.md) **as part of the release**, not after.
The file follows [Keep a Changelog](https://keepachangelog.com/) and the project
aims for [Semantic Versioning](https://semver.org/). On a tagged release, move
the relevant items out of `## [Unreleased]` into a dated
`## [X.Y.Z] - YYYY-MM-DD` heading and reset `Unreleased`.

## Build flow

The four scripts below have a clear order. Build first, then validate, then
package, then organize.

### 1. Build the standalone bundle

```bash
python tools/build_vnext_standalone.py --version <X.Y.Z>
```

This writes a single product ZIP (plus a `.sha256` sidecar) to `dist/vnext/`:

```
dist/vnext/kb-wiki-vnext-<X.Y.Z>-standalone.zip
dist/vnext/kb-wiki-vnext-<X.Y.Z>-standalone.zip.sha256
```

The bundle is a **product package, not a workspace snapshot**. It includes the
runtime, the minimum classic `.kb` template a new workspace needs, plugin
source, product docs, and the validation tools. It deliberately **excludes**
mutable state and caches — `.git`, `__pycache__`, `*.pyc`, any `*.db` /
`*.db-shm` / `*.db-wal`, `state/`, `runs/`, `worktrees/`, and the generated live
wiki. The SHA-256 sidecar is written automatically from the final ZIP bytes.

By default this script also invokes the agent-package build (step 3) for you.
Pass `--skip-agent-packages` to build only the standalone ZIP (the test suite
uses this to avoid redundant rebuilds).

### 2. Validate the product

```bash
python tools/validate_vnext_product.py --bundle dist/vnext/kb-wiki-vnext-<X.Y.Z>-standalone.zip
```

The validator returns a non-zero exit code (and `--json` gives machine-readable
output) when anything is wrong. It checks:

- the product manifest (`product.json`) — name, version, and that the
  authority limits hold (`direct_kb_db_mutation` and `publishes_kb_wiki_live`
  must both be `false`);
- documentation parity — required docs exist in both `en` and `pt-BR` with the
  expected section headings;
- relative links — no broken or repo-escaping Markdown links;
- the bundle's contents — required paths are present and **forbidden paths are
  absent** (no `__pycache__`, `*.pyc`, committed `kb.db`, live wiki, or
  `state/runs/`).

Treat a failing validation as a hard stop.

### 3. Build the agent packages

```bash
python tools/build_agent_packages.py
```

This builds the per-platform plugin ZIPs (Claude Code, Claude Cowork, Codex)
from the canonical plugin sources into `dist/agent-packages/`. Each ZIP is
shape-validated as it is written — the build fails if a package has the wrong
manifest, leaks `.codex-plugin` entries into an Anthropic-targeted package, or
otherwise violates the platform upload rules. Use `--scope <all|kb|vnext|case>`
to limit which owners are built, and `--dry-run` to print the planned artifacts
without writing anything.

> Step 1 already runs this with `--scope vnext`. Run it directly here when you
> are cutting plugin packages on their own or building the full set.

### 4. Organize packages by platform

```bash
python tools/organize_agent_packages.py
```

The flat `dist/agent-packages/` directory stays the canonical build output. This
script creates a read-friendly, copied mirror so installers can find the right
file by platform and version:

```
dist/agent-packages/by-platform/<platform>/<version>/<artifact>.zip
dist/agent-packages/by-platform/<platform>/latest/<artifact>.zip
```

It writes a `manifest.json` and a `README.md` table (with SHA-256s) into the
mirror. Use `--check` to verify the mirror matches the flat directory without
copying, and `--archive-legacy` to move recognized non-current plugin ZIPs into
`dist/agent-packages/legacy/`.

### 5. Build & publish the pip package (PyPI)

The `kb-factory` pip package is separate from the plugin/standalone ZIPs. Its
version lives in `pyproject.toml` (bump it to match the release); its payload is
the `kb_factory/` package plus the generated scaffold mirror
`kb_factory/_scaffold/` (kept in sync by `tools/sync_package_scaffold.py` —
`pytest` fails if it is stale). `MANIFEST.in` governs what ships in the sdist.

```bash
python tools/sync_package_scaffold.py --check    # mirror must be in sync
python -m build                                   # sdist + wheel into dist/
python -m twine check dist/kb_factory-<X.Y.Z>*    # metadata sanity
python -m twine upload dist/kb_factory-<X.Y.Z>*   # requires a PyPI token
```

`build` and `twine` are **release-time dev tools** (`pip install build twine`),
not runtime dependencies. Confirm the wheel bundles the scaffold (it must contain
`kb_factory/_scaffold/kb.py` and `_scaffold/runtime/`). Publish **after** CI is
green on the release commit and the git tag is pushed.

## End-to-end (copy/paste)

```bash
# 0. Gate + tests must be green
python tools/gate.py
pytest

# 1. Update CHANGELOG.md (move Unreleased -> dated heading)

# 2. Build the standalone bundle (also builds vnext agent packages)
python tools/build_vnext_standalone.py --version <X.Y.Z>

# 3. Validate the product + bundle
python tools/validate_vnext_product.py \
  --bundle dist/vnext/kb-wiki-vnext-<X.Y.Z>-standalone.zip

# 4. Build the full agent-package set and organize the mirror
python tools/build_agent_packages.py
python tools/organize_agent_packages.py --check

# 5. Build & publish the pip package (after CI green on the release commit + tag)
python tools/sync_package_scaffold.py --check
python -m build && python -m twine upload dist/kb_factory-<X.Y.Z>*
```

## Notes

- **Output locations.** Standalone bundle → `dist/vnext/`. Plugin packages →
  `dist/agent-packages/` (with the platform mirror under `by-platform/`).
- **Checksums.** The standalone bundle ships a `.sha256` sidecar; the organized
  mirror records a SHA-256 per artifact in its `manifest.json`. Publish these so
  consumers can verify downloads.
- **No third-party tooling in the runtime.** The build scripts are
  standard-library Python. The only third-party tools anywhere are
  release-time-only: `pytest` (tests) and `build` / `twine` (publishing the pip
  package). The shipped runtime and the `kb-factory` package import only the
  standard library — the zero-runtime-dependency constraint holds (see
  [CONTRIBUTING.md](../CONTRIBUTING.md)).
