---
description: Thin closeout wrapper for KB/Wiki vNext and KB-lifecycle
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "[session-id, e.g. S14]"
---

# Gate Session End

Run a thin closeout sequence for this workspace. Detect which canonical systems
are present, call their closeout surfaces, and report what was persisted. Do
not fabricate missing KB records or vNext evidence.

Use this explicit command instead of a generic `/session-end` alias so Session
Gate, vNext, and classic KB lifecycle commands cannot collide.

## Input

Use the session identifier supplied by the user. If none is supplied, ask for
it or infer it only from verified session evidence.

## Step 1: Detect workspace capabilities

Run:

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
- If vNext is present, summarize vNext evidence first and do not run classic KB
  closeout unless canonical KB changes were made or the user explicitly asks
  for classic lifecycle closeout.
- If only one subsystem is present, run only that subsystem.
- Run cross-system consistency checks only when both subsystems are present.

## Step 2: Pre-close audit

Before closeout, do a verified audit:

1. KB audit: list only knowledge gaps you can verify from the current session
   artifacts or the workspace state.
2. Git audit: run `git status` only if this is a git repository. If not, say
   that git audit was unavailable.

Do not fabricate decisions or missing records from conversation memory alone.

## Step 3: KB/Wiki vNext closeout (only if `vnext.found == true`)

Summarize touched vNext manifests, proposals, package checks, tests, or pilot
evidence. If canonical KB updates were approved through `proposal-apply`, cite
that evidence and then run the classic KB closeout below.

Do not publish `.kb-next` wiki drafts to `.kb/wiki/live`.

## Step 4: KB-lifecycle closeout (only if `kb.found == true` and needed)

Run the canonical KB surface:

1. `python .kb/kb.py lifecycle session-end --json`

If that output recommends maintenance and the user asked for a full maintenance
pass, the next steps depend on vNext.

Classic-only workspace (`vnext.found == false`):

2. `python .kb/kb.py hygiene-audit --json`
3. `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`

Treat `hygiene-audit` as read-only.

vNext workspace (`vnext.found == true`): demotions, resolved open items and
retired records are proposals the user approves. Do not run
`lifecycle scheduled-maintenance` or any `--apply-demotions` flag; the
kb-wiki-vnext write gate denies them, and classic runtime 0.2.7 skips their
demotions in a vNext project. Instead, run the curation step of
the plugin's `vnext-session-end` command:

2. `python .kb/kb.py hygiene-audit --json`
3. `python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene --json`,
   with the runtime resolved as `gate-session-start` does: the detector's
   `vnext.details.runtime_ref`, else an installed client-plugin path matching
   `**/kb-wiki-vnext/runtime/kb_next.py`, else
   `core/versions/kb-wiki-vnext/runtime/kb_next.py` in the authoring monorepo.
   `vnext.details.project_root` is the folder that holds the vNext config:
   this workspace, or the main checkout of a linked worktree activated only
   there (`vnext.details.activation` is `main_checkout`). Report the
   candidates per group and `review_budget`. When `room` is above zero,
   classify at most `room` candidates in `hygiene-judgment.json` and write
   them with
   `python <resolved-runtime-path> --project-root <vnext.details.project_root> semantic-hygiene --judgment @hygiene-judgment.json --write-proposals --json`.
   Do not apply them at session end; list their ids for the user's review.

If shell execution is unavailable, report the exact KB commands that remain
deferred.

## Step 5: Cross-system consistency (only if vNext and KB are both present)

Cross-check only verified items:

- vNext proposal/materialization state vs. KB records, when vNext changed

If there are gaps, flag them explicitly. Do not claim consistency that you did
not verify.

## Step 6: Present the summary

Produce a concise closeout summary with only the relevant sections:

- `Workspace detected`
- `Pre-close audit`
- `vNext closeout` only if vNext was detected
- `KB closeout` only if KB was detected
- `Consistency` only if both were detected
- `Safe to close` conclusion
