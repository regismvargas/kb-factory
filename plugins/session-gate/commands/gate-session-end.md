---
description: Thin closeout wrapper for KB/Wiki vNext and KB-lifecycle
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Gate Session End

Run a thin closeout for this workspace and report what was persisted. In a
vNext workspace it is the plugin's `vnext-session-end` close: one call with KB
alone, two with an active wiki. Do not fabricate missing KB records or vNext
evidence.

Use this explicit command instead of a generic `/session-end` alias so Session
Gate, vNext, and classic KB lifecycle commands cannot collide.

## Step 1: Detect workspace capabilities

When the kb-wiki-vnext SessionStart hook text (it says it replaces
`session-start`) is in this session, the workspace is a vNext project rooted
here: skip the detector, take `.` as
`<vnext.details.project_root>` and the runtime that text printed as
`<resolved-runtime-path>`, and go to Step 2.

Otherwise run:

```bash
python plugins/session-gate/scripts/detect_workspace.py
```

If that authoring-repository path is absent, resolve the detector relative to
the installed plugin: `${CLAUDE_PLUGIN_ROOT}/scripts/detect_workspace.py`, the
`scripts/detect_workspace.py` sibling of this plugin's `SKILL.md`, or an
installed client-plugin path matching
`**/session-gate/scripts/detect_workspace.py`. Use the first verified file. If
none resolves, stop and report that Session Gate is incomplete; do not infer
workspace capabilities from memory.

Interpret the JSON output:

- If vNext and KB are both absent, stop after a graceful closeout message.
- If vNext is present, run Step 2 only.
- If only KB is present, run Step 3 only.

## Step 2: KB/Wiki vNext closeout (only if `vnext.found == true`)

1. Only if subagents ran in the session: the `KB candidates` step of the
   `vnext-session-end` command. File what the user approves before step 2.
2. `python .kb/kb.py lifecycle session-end --json` when `.kb/kb.py` exists,
   once, after those filings. Report `wiki_sync.written_count`, any
   `held_back` pages, and the `audit` flags (`hot_over_limit`, `stale_hot`,
   `expired_premises`) as items for the weekly maintenance run.
3. Only if KB + Wiki is active and not dormant:
   `python <resolved-runtime-path> --project-root <vnext.details.project_root> wiki-draft-status --json`,
   with the runtime resolved as `gate-session-start` does: the detector's
   `vnext.details.runtime_ref`, else an installed client-plugin path matching
   `**/kb-wiki-vnext/runtime/kb_next.py`, else
   `core/versions/kb-wiki-vnext/runtime/kb_next.py` in the authoring monorepo.
   `vnext.details.project_root` is the folder that holds the vNext config:
   this workspace, or the main checkout of a linked worktree activated only
   there (`vnext.details.activation` is `main_checkout`). Offer the
   `vnext-wiki-drafts` command when topics need drafts.
4. Only if `retrieval.dense.enabled` is on and records changed: the
   `dense-index` refresh of the `vnext-session-end` command.

vNext workspace (`vnext.found == true`) rules: demotions, resolved open items
and retired records are proposals the user approves, and curation
(`hygiene-audit`, `semantic-hygiene` and its judged proposals) runs in the
weekly maintenance run, not at session end, unless the user asks for a full
maintenance pass (below). Do not run
`lifecycle scheduled-maintenance` or any `--apply-demotions` flag; the
kb-wiki-vnext write gate denies them, and classic runtime 0.2.7 skips their
demotions in a vNext project. Apply nothing at session end; approvals follow
the kb-wiki-vnext skill. Do not publish `.kb-next` wiki drafts to
`.kb/wiki/live`.

Full maintenance on request: when the user explicitly asks for a full
maintenance pass at closeout, follow the Curation section of the kb-wiki-vnext
skill after step 2:

- `python .kb/kb.py hygiene-audit --json`
- `python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene --json`,
  then report the candidates per group and `review_budget`
- when `room` is above zero, classify at most `room` candidates in
  `hygiene-judgment.json` and write them with
  `python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene --judgment @hygiene-judgment.json --write-proposals --json`

These write only `.kb-next/` proposals: list their ids for the user's review
and apply nothing at session end.

## Step 3: KB-lifecycle closeout (only if `kb.found == true` and `vnext.found == false`)

Run the canonical KB surface:

1. `python .kb/kb.py lifecycle session-end --json`

If that output recommends maintenance and the user asked for a full
maintenance pass in this classic-only workspace:

2. `python .kb/kb.py hygiene-audit --json`
3. `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`

Treat `hygiene-audit` as read-only.

If shell execution is unavailable, report the exact KB commands that remain
deferred.

## Step 4: Present the summary

Produce a concise closeout summary with only the relevant sections:

- `Workspace detected`
- `vNext closeout` only if vNext was detected
- `KB closeout` only if KB was detected
- `Safe to close` conclusion, naming any command that failed or was deferred
