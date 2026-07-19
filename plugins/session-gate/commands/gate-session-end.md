---
description: Thin closeout wrapper for KB/Wiki vNext, KB-lifecycle, and CASE Companion
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "[session-id, e.g. S14]"
---

# Gate Session End

Run a thin closeout sequence for this workspace. Detect which canonical systems
are present, call their closeout surfaces, and report what was persisted. Do
not fabricate missing handoffs, KB records, or CASE state.

Use this explicit command instead of a generic `/session-end` alias so Session
Gate, vNext, and classic KB lifecycle commands cannot collide.

## Input

Use the session identifier supplied by the user. If none is supplied, ask for
it or infer it only from a verified prior handoff.

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

- If vNext, KB, and CASE are all absent, stop after a graceful closeout message.
- If vNext is present, summarize vNext evidence first and do not run classic KB
  closeout unless canonical KB changes were made or the user explicitly asks
  for classic lifecycle closeout.
- If only one subsystem is present, run only that subsystem.
- Run cross-system consistency checks only when both subsystems are present.

## Step 2: Pre-close audit

Before closeout, do a verified audit:

1. KB audit: list only knowledge gaps you can verify from the current session
   artifacts or the workspace state.
2. CASE audit: list only unresolved dispatch, review, or handoff items that
   actually exist in the workspace.
3. Git audit: run `git status` only if this is a git repository. If not, say
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
pass, then run:

2. `python .kb/kb.py hygiene-audit --json`
3. `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`

Treat `hygiene-audit` as read-only. If the workspace also has `.kb-next/` and
the closeout concerns HOT overflow, route semantic cleanup into vNext
`semantic-hygiene` proposals instead of automatic LLM-only demotion.

If shell execution is unavailable, report the exact KB commands that remain
deferred.

## Step 5: CASE Companion closeout (only if `case.found == true`)

If `case.found` is `false`, skip this entire section. Do not mention CASE,
handoffs, role boundaries, ALLOW/BLOCK, or CASE cleanup in the final closeout.

Do not update `companion_state.json`. That file is owned by CASE Companion.
Session-gate only reads it for detection purposes.

When CASE is present:

1. Use the canonical CASE `/handoff` contract resolved by the detector.
2. Use the canonical handoff template reference resolved by the detector.
3. Write the handoff to `kickoffs/HANDOFF_SESSION_{ID}_EXIT.md`.
4. Fill the handoff only with verified state: session summary, git state if
   available, pending items, and files to read next.

Do not invent new decisions just to populate the handoff. If no verified
session decision exists, say so explicitly.

## Step 6: Cross-system consistency (only if multiple systems are present)

Cross-check only verified items:

- vNext proposal/materialization state vs. KB records, when vNext changed
- Handoff decisions vs. KB decision records
- Handoff pending items vs. KB pending items
- Handoff premises vs. KB premise records

If there are gaps, flag them explicitly. Do not claim consistency that you did
not verify.

## Step 7: Present the summary

Produce a concise closeout summary with only the relevant sections:

- `Workspace detected`
- `Pre-close audit`
- `vNext closeout` only if vNext was detected
- `KB closeout` only if KB was detected
- `CASE closeout` only if CASE was detected
- `Consistency` only if both were detected
- `Safe to close` conclusion

For KB-only and empty workspaces, a mention of CASE is a regression.
