# KB/Wiki vNext Architecture And Operating Model

## Purpose

Explain what the product contains, how each platform uses it, and where authority begins and ends.

## Audience

Admins, developers, reviewers, and maintainers evaluating the RC package.

## Prerequisites

- Basic familiarity with KB Factory workspaces.
- Awareness that this RC is productized inside the current repository, not split into a separate repository yet.

## Operating Model

`.kb/` is canonical memory. `.kb-next/` is evidence, proposals, drafts, materialization, and operational memory for vNext workflows. The vNext runtime may read `.kb/` through supported surfaces, but canonical mutation must go through `proposal-apply`, which delegates to `.kb/kb.py`.

Platform map:

| Platform | Artifact | Internal structure | Primary capabilities |
| --- | --- | --- | --- |
| Codex | `kb-wiki-vnext-plugin-0.3.0.zip` | `.codex-plugin`, skills, commands, and runtime `0.3.0` | `vnext-session-start`, setup commands, lookup, compliance preflight, proposal workflows |
| Claude Code | `kb-wiki-vnext-claude-plugin-0.3.0.zip` | Claude plugin manifest, skills, commands/hooks, and runtime `0.3.0` | guided memory workflows and explicit commands |
| Claude Cowork | `kb-wiki-vnext-cowork-plugin-0.3.0.zip` | Cowork plugin package, runtime `0.3.0`, and manual session boundary guidance | manual `vnext-session-start`, setup commands, no dependency on automatic hooks |
| Session Gate | `session-gate-*-0.2.7.zip` | plugin detector plus `gate-session-*` commands | route `.kb-next/` first, then classic `.kb/` and CASE when present |
| Stand-alone | `kb-wiki-vnext-0.3.0-standalone.zip` | runtime, classic template, plugin source, docs, tools | bootstrap and controlled admin distribution |

Plugin packaging installs client capabilities. Skills describe agent behavior. Commands expose callable workflows. Hooks are platform-specific convenience surfaces and are not assumed for Cowork.

Names in the capability column are logical basenames. Claude Code prefixes
plugin commands with `/kb-wiki-vnext:`; Codex uses the embedded skill as the
primary surface; Cowork follows the actions exposed by its installed plugin UI.

The version lines are independent component identities, not alternatives:

| Component | Version |
|---|---|
| Product release candidate | `0.3.0` |
| KB Lifecycle | `0.3.0` |
| vNext plugin container | `0.3.0` |
| Bundled `kb_next.py` engine | `0.3.0` |
| Session Gate | `0.2.7` |
| Marketplace/catalog | no independent version; plugin manifests are authoritative |

The bundled engine bootstraps a stable workspace copy at
`.kb-next/runtime/kb_next.py`. Normal sessions use the workspace copy. Upgrade
and rollback resolve the new or restored artifact first and bootstrap from that
source. Bootstrap replaces same-version byte drift, reports source and installed
SHA-256, and rejects linked or out-of-root targets. Using the current workspace
runtime as its own source returns `action: self` and does not prove a version
transition.

Operational writes under `.kb-next/` are not canonical writes. `session-start`
and `lookup` append operations evidence; semantic and wiki commands may write
manifests, proposals, drafts, or materializations. Only approved
`proposal-apply` may cross into canonical `.kb/`, and it must do so through
`.kb/kb.py`.

## Verification

Use `python tools\validate_vnext_product.py` to confirm product docs, manifest,
archive inventory, plugin runtime inclusion, and optional bundle contents. Use
the existing spec-pack validator to confirm runtime/spec consistency.

## Troubleshooting

If platform behavior differs, verify the artifact type before changing runtime code. Do not compensate for missing Cowork hooks by promising automatic startup; document manual startup instead.

## Related

- [Admin installation](admin-installation.md)
- [Command reference](command-reference.md)
- [Maintainer release](maintainer-release.md)
- [Troubleshooting](troubleshooting.md)
