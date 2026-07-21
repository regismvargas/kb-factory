# KB/Wiki vNext Usage Guide

## Purpose

Explain how to use every KB/Wiki vNext runtime command in real projects and agent conversations.

## Audience

Project users, admins, and maintainers who need more than install instructions: when to use each feature, what to ask the agent, and how to avoid accidental canonical memory changes.

## Prerequisites

- KB/Wiki vNext `0.3.0` installed through a plugin ZIP or the stand-alone bundle.
- Component identity recorded by the maintainer: release, KB Lifecycle, vNext,
  and runtime `0.3.0`; Session Gate `0.2.7`. The marketplace has no version
  authority; plugin manifests define update identity.
- A workspace with `.kb/` available as canonical memory.
- Python available as `python`.
- Agreement that `.kb-next/` is operational memory, proposal evidence, and draft materialization, not the canonical source of truth.

## Mental Model

`.kb/` remains canonical. It stores durable project memory and is the only place that should be treated as the source of truth. KB/Wiki vNext reads `.kb/` through supported runtime paths, and only `proposal-apply` may bridge an approved proposal back through `.kb/kb.py`.

`.kb-next/` is the working layer. It stores activation decisions, session hints, semantic proposals, inference manifests, wiki drafts, materialized review surfaces, adapter exports, and operational evidence. It is designed to help agents work thinly and reviewably without loading the whole project history by default.

Commands described as read-only are read-only against canonical `.kb/`. Commands such as `session-start` and `lookup` still append operational evidence to `.kb-next/operations.jsonl`.

Mutation summary:

| Command family | `.kb/` | `.kb-next/` |
|---|---|---|
| `bootstrap` | no change | installs only `runtime/kb_next.py` |
| `compliance-preflight`, `source-linkage-audit`, default `semantic-hygiene` | read-only | no write |
| `session-start`, `lookup` | read-only | append operational evidence |
| activation, semantic, proposal, export, and wiki commands | read-only unless noted below | write governed config, manifests, proposals, drafts, exports, or operations evidence |
| approved `proposal-apply` | mutates only through `.kb/kb.py` | writes apply evidence and operations evidence |

Use the repository layout when running from this repo:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py <command>
```

Use the stand-alone layout when running from the unpacked bundle:

```powershell
python runtime\kb_next.py <command>
```

For an installed plugin, treat `vnext-session-start` as a logical basename.
Claude Code invokes `/kb-wiki-vnext:vnext-session-start`; Codex primarily
invokes the embedded `kb-wiki-vnext` skill; Cowork uses the namespaced action
actually exposed by its plugin UI or the skill in natural language. In a shell,
resolve a runnable engine in this order:

1. `./.kb-next/runtime/kb_next.py` for an already bootstrapped workspace.
2. `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` for the active Claude plugin.
3. The installed Codex, Cowork, or Claude plugin path matching
   `**/kb-wiki-vnext/runtime/kb_next.py`.
4. `core/versions/kb-wiki-vnext/runtime/kb_next.py` only in the KB Factory
   authoring monorepo.

When rung 1 is absent, install the resolved engine into the workspace once:

```powershell
python <plugin-runtime-path> --project-root . bootstrap --json
python .kb-next\runtime\kb_next.py <command>
```

For normal sessions prefer the workspace runtime. For upgrade or rollback,
bootstrap from the newly installed plugin runtime, never from the existing
workspace runtime itself.

## Daily Conversation Workflow

Start every new conversation thinly:

```powershell
python .kb-next\runtime\kb_next.py session-start --json
```

Then read only `.kb-next/memory/NOW.md` by default. Ask the agent to widen context only when the task needs it.

Good conversation prompt:

```text
Use this client's KB/Wiki vNext startup surface. In Claude Code run `/kb-wiki-vnext:vnext-session-start`; in Codex invoke the `kb-wiki-vnext` skill. Read only .kb-next/memory/NOW.md by default, then answer from lookup before opening broader history.
```

Ask for deterministic lookup when you need status, decisions, definitions, learnings, or open items:

```text
Use vNext lookup to find the current decision about wiki activation. Do not scan the whole repo unless lookup is insufficient.
```

Stop and ask for explicit approval when an action would create a proposal, write a draft, materialize review output, or apply canonical memory.

## Project Lifecycle Workflows

New project:

1. Ensure `.kb/` exists from the bundled classic template or an existing KB Factory setup.
2. Run `activation-wizard`.
3. Run `python runtime/kb_next.py --project-root <workspace> session-start`.
4. Use `lookup` first; use semantic commands only when you can supply or review LLM judgment.

Existing project:

1. Run `python runtime/kb_next.py --project-root <workspace> session-start`.
2. Read `.kb-next/memory/NOW.md`.
3. Use `compliance-preflight` before planning, packaging, release, or development work.
4. Use `proposal-apply` only after human approval.

Audit and release:

1. Run `compliance-preflight`.
2. Run `source-linkage-audit` when external wiki/export evidence depends on canonical source links.
3. Run build and product validators.
4. Record hashes and evidence in the run dossier.

Curating memory:

1. Use `lookup` or `semantic-lookup` to retrieve evidence.
2. Use `curation-proposal`, `filing-proposal`, or `semantic-hygiene` to prepare proposals.
3. Review the proposal and manifest.
4. Apply only with `proposal-apply --approve --approval-note`.

Wiki draft work:

1. Use `wiki-synthesis-plan --write-drafts`.
2. Review machine and human drafts.
3. Use `wiki-draft-review --materialize` only for `.kb-next/` review materialization.
4. Do not publish to `.kb/wiki/live` as part of vNext.

Upgrade and rollback:

1. Record current package/runtime.
2. Install the new plugin or unpack the new stand-alone bundle beside the previous one.
3. Bootstrap from the newly installed artifact, then run `python runtime/kb_next.py --project-root <workspace> session-start`,
   `compliance-preflight`, and default report-only `semantic-hygiene`.
4. Roll back by reinstalling the previous artifact and bootstrapping from its
   runtime. Do not use the current workspace runtime as its own upgrade or
   rollback source.

## Command Reference

### `bootstrap`

Purpose: install the runtime that is executing the command into
`.kb-next/runtime/kb_next.py` for the selected project root.

Use when: activating, repairing, upgrading, or rolling back a consumer
workspace.

Do not use when: the source runtime is the same workspace runtime you are
trying to replace; `action: self` does not prove an upgrade or rollback.

Plugin or stand-alone source example:

```powershell
python <artifact-runtime-path> --project-root . bootstrap --json
```

Expected output: `runtime_version`, target path, and `action` equal to
`created`, `updated`, or `exists`, plus equal `source_sha256` and
`installed_sha256`. Same-version drift is replaced. The command writes only the
workspace runtime file; it does not create config, memory, proposals, or
operations evidence.

Risks: bootstrapping from an old or unverified artifact installs that exact
runtime version. Confirm artifact identity and hash first.

### `activation-wizard`

Purpose: choose and record whether the workspace runs as KB-only or KB + Wiki.

Use when: setting up `.kb-next/` for a workspace or revisiting activation mode with sponsor intent.

Do not use when: you only need to start a normal conversation; use plugin command `vnext-session-start` or runtime subcommand `session-start`.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py activation-wizard --mode short --choice kb_alone --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py activation-wizard --mode short --choice kb_alone --json
```

Conversation prompt:

```text
Run activation-wizard in short mode with kb_alone unless the sponsor has explicitly approved KB + Wiki.
```

Expected output: activation decision JSON and `.kb-next/` bootstrap surfaces.

Risks: choosing KB + Wiki without sponsor approval can imply a broader wiki workflow than the project authorized.

### `session-start`

Purpose: emit the thin startup contract for the current conversation.

Distributed logical basename: `vnext-session-start`. Claude Code invocation:
`/kb-wiki-vnext:vnext-session-start`. Codex surface: embedded skill. Runtime
subcommand: `session-start`.

Use when: beginning every agent session.

Do not use when: you are trying to apply canonical memory changes. It does not write `.kb/`, but it appends session evidence to `.kb-next/operations.jsonl`.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py session-start --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py session-start --json
```

Conversation prompt:

```text
Start with the client-specific vNext surface, or runtime `session-start`, and read only NOW.md before deciding whether more context is needed.
```

Expected output: default reads, required `NOW.md` path, on-demand surfaces.

Risks: skipping this command usually leads to broad, noisy historical loading.

### `compliance-preflight`

Purpose: check the required gates for a work type before planning or implementation.

Use when: doing planning, implementation, packaging, release, Track B, operational checks, or unknown work.

Do not use when: the task is a simple lookup with no change intent.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py compliance-preflight --work-type packaging --topic "vNext package update" --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py compliance-preflight --work-type release --topic "vNext release validation" --json
```

Conversation prompt:

```text
Before implementing, run compliance-preflight for work-type implementation and tell me any blockers.
```

Expected output: pass/block status, required tests, evidence, and next allowed action.

Risks: treating a blocked preflight as advisory can bypass release or governance requirements.

### `source-linkage-audit`

Purpose: verify source linkage for Track B/export-sensitive records.

Use when: preparing external wiki/export work that relies on canonical source provenance.

Do not use when: you are just asking for project status.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py source-linkage-audit --scope track-b --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py source-linkage-audit --scope track-b --json
```

Conversation prompt:

```text
Run source-linkage-audit for Track B and summarize only blockers that affect export readiness.
```

Expected output: read-only audit status and source linkage blockers.

Risks: exporting externally before resolving source linkage can create weak or unverifiable provenance.

### `track-b-export`

Purpose: generate a derived Track B export for a supported adapter.

Use when: producing reviewable external markdown surfaces such as the Obsidian static markdown pilot.

Do not use when: you expect it to update canonical memory or publish live wiki pages.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py track-b-export --adapter obsidian_static_markdown --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py track-b-export --adapter obsidian_static_markdown --json
```

Conversation prompt:

```text
Export Track B to the Obsidian static markdown adapter as a derived artifact only. Do not publish it as canonical.
```

Expected output: export manifest and derived adapter paths under `.kb-next/`.

Risks: confusing derived export with canonical wiki publication.

### `lookup`

Purpose: deterministic read-only retrieval from classic KB memory.

Use when: you need decisions, learnings, definitions, open items, or status without broad historical scanning.

Do not use when: you need semantic judgment across ambiguous records; use `semantic-lookup`.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py lookup --facet decisions --query "wiki activation" --limit 5 --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py lookup --facet status --query "release" --limit 5 --json
```

Conversation prompt:

```text
Use lookup for open-items about vNext packaging and summarize only active records.
```

Expected output: matching records with `classic_kb_mode` read-only.

Risks: weak query terms can miss relevant records; widen with another lookup before scanning files.

### `semantic-lookup`

Purpose: combine deterministic candidates with external LLM judgment.

Use when: wording differs, synonyms matter, or the user asks a question that needs semantic interpretation.

Do not use when: you cannot provide or review the judgment; start with `lookup`.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py semantic-lookup --query "thin startup memory" --facet decisions --limit 5 --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py semantic-lookup --query "how do we avoid reading too much history" --facet learnings --limit 5 --json
```

These are executable first passes. They return deterministic candidate IDs and
`needs_llm_judgment`. Only a second pass should add `--judgment @<path>` or
`--judgment-json <json>`, using an operator-reviewed payload built from those
actual IDs.

Conversation prompt:

```text
Use semantic-lookup only after you show the deterministic candidates and your judgment rationale.
```

Expected output: candidates, judgment status, selected records, confidence, and conflicts.

Risks: an unsupported or low-confidence judgment should not be treated as canonical truth.

### `curation-proposal`

Purpose: prepare a governed memory curation proposal from lookup evidence and semantic judgment.

Use when: a memory record appears outdated, duplicate, misleading, or needs supersession.

Do not use when: you only need to answer a question.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py curation-proposal --query "obsolete startup instructions" --facet decisions --limit 10 --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py curation-proposal --query "duplicate release notes" --facet learnings --limit 10 --json
```

Both commands create review evidence under `.kb-next/` and may return
`needs_llm_judgment`; they do not curate `.kb/`. A reviewed second pass may use
`--judgment @<path>` with record IDs from the first pass.

Conversation prompt:

```text
Prepare a curation proposal for stale vNext instructions, but do not apply it.
```

Expected output: proposal draft and inference manifest under `.kb-next/`.

Risks: proposals are not canonical until reviewed and applied.

### `semantic-hygiene`

Purpose: inspect semantic memory hygiene, especially HOT overflow, and optionally write proposals.

Use when: the active memory set is noisy, duplicated, stale, or overloaded.

Do not use when: you want direct cleanup in `.kb/`; this command prepares evidence/proposals.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py semantic-hygiene --scope hot-overflow --limit 50 --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py semantic-hygiene --scope hot-overflow --limit 50 --json
```

This default invocation is report-only. A reviewed second pass may add
`--judgment @<path> --write-proposals`; that judgment must preserve the groups
`keep_hot`, `demote_candidate`, `supersede_or_merge_candidate`,
`resolve_candidate`, and `needs_sponsor`, and reference only record IDs returned
by the first pass.

Conversation prompt:

```text
Review HOT overflow in report-only mode first. If there are clear candidates, propose changes but do not apply them.
```

Expected output: report-only findings or proposal IDs when `--write-proposals` is used.

Risks: writing proposals is still not applying them, but it does create review artifacts that need triage.

### `filing-proposal`

Purpose: prepare a new canonical memory filing proposal from a candidate memory object.

Use when: a new decision, learning, definition, open item, or status should be considered for canonical KB.

Do not use when: the content lacks provenance or should remain conversation-only.

Repository example:

```powershell
$candidatePath = Join-Path $env:TEMP 'kb-vnext-candidate-memory.json'
@{
  title = 'Use NOW-only startup'
  content = 'Read only .kb-next/memory/NOW.md at session start.'
  source = 'operator-reviewed usage-guide example'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $candidatePath -Encoding ascii
python core\versions\kb-wiki-vnext\runtime\kb_next.py filing-proposal --input "@$candidatePath" --category DECISAO --domain architecture --json
Remove-Item -LiteralPath $candidatePath
```

Stand-alone example:

```powershell
$candidatePath = Join-Path $env:TEMP 'kb-vnext-candidate-memory.json'
@{
  title = 'Use artifact-first runtime bootstrap'
  content = 'Bootstrap the workspace runtime from the installed or unpacked artifact.'
  source = 'operator-reviewed usage-guide example'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $candidatePath -Encoding ascii
python runtime\kb_next.py filing-proposal --input "@$candidatePath" --category DECISAO --domain operations --json
Remove-Item -LiteralPath $candidatePath
```

Conversation prompt:

```text
Turn this new operational rule into a filing proposal with provenance. Do not write to .kb/kb.db.
```

Expected output: filing proposal and manifest under `.kb-next/proposals`.

Risks: low-provenance memory should be blocked or left as draft evidence.

### `proposal-apply`

Purpose: apply an approved proposal through `.kb/kb.py`.

Use when: a human has reviewed a proposal and explicitly approved canonical mutation.

Do not use when: approval is missing, ambiguous, or the proposal is outside `.kb-next/proposals`.

Repository example:

```powershell
$proposalId = 'replace-with-reviewed-proposal-id'
python core\versions\kb-wiki-vnext\runtime\kb_next.py proposal-apply --proposal $proposalId --approve --approval-note "Approved by project owner after proposal review" --json
```

Stand-alone example:

```powershell
$proposalPath = '.kb-next\proposals\replace-with-reviewed-proposal.json'
python runtime\kb_next.py proposal-apply --proposal $proposalPath --approve --approval-note "Maintainer approved after review" --json
```

Replace the example variable value with the reviewed proposal returned by the earlier
proposal command. Never infer an ID or reuse an approval note from documentation.

Conversation prompt:

```text
Apply this proposal only if it is bound to a valid manifest and I have explicitly approved it in this message.
```

Expected output: applied/blocked status and canonical bridge details.

Risks: this is the only command in the workflow intended to mutate canonical memory; use it deliberately.

### `wiki-synthesis-plan`

Purpose: plan and optionally write machine/human wiki drafts under `.kb-next/`.

Use when: preparing reviewable wiki content from KB evidence.

Do not use when: you intend to publish directly to `.kb/wiki/live`.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py wiki-synthesis-plan --topic "vnext-architecture" --domain architecture --limit 10 --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py wiki-synthesis-plan --topic "release-operations" --domain operations --limit 10 --json
```

These are first-pass plans. Only after reviewing the returned records should a
second pass provide `--judgment @<path> --write-drafts`. Drafts remain under
`.kb-next/`; neither pass publishes to `.kb/wiki/live`.

Conversation prompt:

```text
Create a wiki synthesis plan and drafts under .kb-next only. Do not publish live wiki pages.
```

Expected output: synthesis plan, supporting records, and optional draft paths.

Risks: drafts are derived and reviewable; they are not canonical publication.

### `wiki-draft-review`

Purpose: review and optionally materialize wiki draft review surfaces under `.kb-next/`.

Use when: machine and human drafts exist and need provenance/confidence checks before promotion decisions.

Do not use when: source records are unknown, inactive, superseded, or below confidence threshold.

Repository example:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py wiki-draft-review --topic "vnext-architecture" --materialize --json
```

Stand-alone example:

```powershell
python runtime\kb_next.py wiki-draft-review --topic "release-operations" --min-confidence 0.8 --json
```

Conversation prompt:

```text
Review the wiki drafts for provenance and confidence. Materialize review output only under .kb-next.
```

Expected output: review status, warnings/blockers, and optional materialized `.kb-next/` paths.

Risks: materialization is not live wiki publication; do not present it as `.kb/wiki/live`.

## Practical Conversation Patterns

Start thin:

```text
Use the client-specific vNext startup surface or runtime `session-start`. Read only NOW.md. Then tell me what extra context you need, if any.
```

Ask status without broad history:

```text
Use lookup with facet status for the current vNext release state. Do not open historical artifacts unless lookup is insufficient.
```

Turn a discovery into a proposal:

```text
Prepare a filing-proposal for this discovery with source and tags. Stop before proposal-apply.
```

Review HOT overflow:

```text
Run semantic-hygiene for hot-overflow in report-only mode. Group findings into keep, propose, and ignore.
```

Draft wiki safely:

```text
Run wiki-synthesis-plan with write-drafts, then wiki-draft-review. Keep everything under .kb-next.
```

Use Cowork manually:

```text
Because Cowork may not run hooks or expose commands consistently, begin with the namespaced vNext action exposed by the installed plugin UI or invoke the skill in natural language. Use runtime `session-start` as fallback and read only NOW.md.
```

## Verification

This guide is current when every command listed in the runtime parser, including
`bootstrap`, appears in both English and Portuguese guides; product validation
passes; plugin ZIPs contain `runtime/kb_next.py`; and the stand-alone bundle
includes `products/kb-wiki-vnext/docs/*/usage-guide.md`.

## Troubleshooting

If a command fails because `.kb/kb.py` is missing, bootstrap `.kb/` from the
stand-alone `classic-template/.kb/`. If the vNext runtime is missing, resolve
the plugin or stand-alone artifact runtime and run `bootstrap`; do not ask the
user to hand-place the file. If a command asks for judgment, prefer
`--judgment @path` after reviewing first-pass candidates. If a workflow would
change `.kb/kb.db`, stop unless the operation is an approved `proposal-apply`.

## Graph reads

Use the `graph` namespace for deterministic structural inspection without
writing `.kb/` or `.kb-next`:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . graph backlinks KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph lineage KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph neighbors KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph source-records SRC-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph verify --json
python .\.kb-next\runtime\kb_next.py --project-root . graph source-backfill --limit 3 --json
```

Treat backfill rows as proposals. Apply an accepted pair only through the
classic `graph source-link` command with actor evidence.

## Related

- [User manual](user-manual.md)
- [Plugin command reference](command-reference.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)
