# Release Guide

This is the public release procedure. It builds only the three public plugins,
the KB/Wiki vNext stand-alone bundle, and the Python distribution. Private
workbench state, archives, spec packs, and sibling repositories are not release
inputs.

The selective release train has one release line, except Session Gate:

| Surface | Version |
|---|---:|
| GitHub/Python release | `0.3.0` |
| kb-lifecycle | `0.3.0` |
| kb-wiki-vnext plugin | `0.3.0` |
| session-gate | `0.2.7` |
| vNext runtime | `0.3.0` |
| vNext stand-alone product | `0.3.0` |

The marketplace has no independent version. Each plugin manifest is the
explicit update identity.

## 1. Validate the source tree

Run from a clean public checkout:

```bash
claude plugin validate .
python tools/gate.py
python tools/sync_package_scaffold.py --check
python tools/sync_vnext_runtime.py --check
python -m pytest -p no:cacheprovider tests -q
```

The gate always checks source/template/package parity and the three vNext
runtime copies. It runs `.kb` doctor and wiki checks only when an authoring
`.kb/kb.py` exists. A normal public checkout has no `.kb/`; the gate reports
that authoring-only check as skipped.

## 2. Build and validate the plugin ZIPs

```bash
python tools/build_agent_packages.py --scope all
```

The build validates three artifacts for each public plugin:

- `*-plugin-*.zip` for Codex
- `*-claude-plugin-*.zip` for Claude Code
- `*-cowork-plugin-*.zip` for Claude Cowork

The builder validates archive shape, rejects links/reparse points, and writes
deterministic ZIPs under `dist/agent-packages/`.
Only the six changed Lifecycle and vNext ZIPs are release assets. Session Gate
remains `0.2.7` and receives no new asset.

Organize the platform mirror before checking it:

```bash
python tools/organize_agent_packages.py
python tools/organize_agent_packages.py --check
```

## 3. Build and validate the stand-alone product

```bash
python tools/build_vnext_standalone.py --version 0.3.0
python tools/validate_vnext_product.py --json \
  --bundle dist/vnext/kb-wiki-vnext-0.3.0-standalone.zip
```

The bundle contains the public product docs, plugin, runtime, classic template,
and public validation tools. It excludes mutable `.kb`/`.kb-next` state,
databases, caches, worktrees, private archives, and spec packs. The builder also
writes a SHA-256 sidecar.

## 4. Build the Python artifacts

```bash
python -m build
python tools/normalize_sdist.py dist/kb_factory-0.3.0.tar.gz --epoch <release-commit-epoch>
python -m twine check dist/kb_factory-0.3.0*
```

Inspect the wheel and source distribution before publication. They must include
`kb_factory/_scaffold/kb.py`, the classic runtime mirror, and
`kb_factory/_scaffold_vnext/runtime/kb_next.py`.

For `v0.3.0`, attach the wheel and source distribution to the GitHub release.
The supported install command is:

```bash
pip install https://github.com/regismvargas/kb-factory/releases/download/v0.3.0/kb_factory-0.3.0-py3-none-any.whl
```

PyPI is optional. Upload only when a project token or trusted-publishing flow is
configured and tested; do not claim `pip install kb-factory` until the package
is visible on PyPI.

## 5. Assemble the selective release bundle

Build the upload directory only after the public candidate commit exists:

```bash
python tools/build_release_bundle.py \
  --public-candidate-sha "$(git rev-parse HEAD)" \
  --source-date-epoch "$(git show -s --format=%ct HEAD)"
cd dist/release/kb-factory-v0.3.0
sha256sum --check SHA256SUMS.txt
```

The bundle contains exactly six changed Lifecycle/vNext plugin ZIPs, the vNext
stand-alone ZIP, wheel, source distribution, hash manifest, provenance, and
`SHA256SUMS.txt`. Session Gate remains `0.2.7`; its three packages are validated
by the all-scope build but are deliberately absent from the release bundle.

## 6. Publish

After CI is green on the release commit:

1. Fast-forward `main` to the validated commit.
2. Create and push tag `v0.3.0`.
3. Create the GitHub release from `CHANGELOG.md`.
4. Attach every file from `dist/release/kb-factory-v0.3.0/` and no Session Gate
   package.
5. Download representative assets and verify their SHA-256 values and archive
   inventories.

Restarting Codex or Claude does not change a plugin's marketplace source or
cached version. After publication, point the marketplace at the public GitHub
repository, refresh it, run `claude plugin update` for each plugin, and restart
Claude Code to apply the downloaded versions. See `installation.md` for the
exact commands.
