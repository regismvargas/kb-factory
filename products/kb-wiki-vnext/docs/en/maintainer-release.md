# KB/Wiki vNext Maintainer And Release Manual

## Purpose

Define how maintainers rebuild, validate, audit, and release the vNext RC package.

## Audience

Maintainers responsible for packaging, QA, and controlled distribution.

## Prerequisites

- Work on a branch with a reversible baseline tag.
- Keep unrelated dirty files out of the release commit.
- Do not publish generated wiki output into `.kb/wiki/live`.

## Steps

Build:

```powershell
python tools\build_agent_packages.py --scope vnext
python tools\build_vnext_standalone.py --version 0.2.0-rc.2
```

Validate:

```powershell
python tools\validate_vnext_product.py --json --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip
python tools\sync_vnext_runtime.py --check
python -m pytest -p no:cacheprovider tests -q
```

Audit hashes:

```powershell
Get-FileHash dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip -Algorithm SHA256
Get-ChildItem dist\agent-packages\*vnext*.zip,dist\agent-packages\session-gate-*.zip | Get-FileHash -Algorithm SHA256
```

Confirm `git status --short` contains only the intended public release changes.

## Verification

Release is acceptable when validators pass, required docs exist in English and
Portuguese, plugin ZIPs include `runtime/kb_next.py`, client invocations are
documented without cross-client slash assumptions, hashes and all component
versions are recorded, and the standalone ZIP excludes `.kb/kb.db`,
`.kb/wiki/live`, caches, worktrees, and `state/runs`.

## Troubleshooting

If a required artifact or bundled runtime is absent, rebuild from source rather
than editing the ZIP manually. If docs and manifest disagree, update the
manifest and bilingual docs in the same release change. If generic
`session-start` / `session-end` command files reappear in vNext or Session Gate
packages, treat the release as blocked. Do not replace already published bytes
under the same version without an explicit immutability decision.

## Related

- [Architecture](architecture.md)
- [Command reference](command-reference.md)
- [Upgrade and rollback](upgrade-rollback.md)
- [Admin installation](admin-installation.md)
