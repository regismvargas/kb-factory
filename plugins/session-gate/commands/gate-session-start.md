---
description: Thin startup wrapper for KB/Wiki vNext and KB-lifecycle
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Gate Session Start

Run a thin startup sequence for this workspace. Detect which canonical systems
are present, call their startup surfaces, and present a concise briefing. Do
not invent absent subsystems and do not duplicate canon already owned by
KB/Wiki vNext or KB-lifecycle.

Use this explicit command instead of a generic `/session-start` alias so
Session Gate, vNext, and classic KB lifecycle commands cannot collide.

## Step 1: Detect workspace capabilities

Run the detector first:

```bash
python plugins/session-gate/scripts/detect_workspace.py
```

If the script path is not at `plugins/session-gate/scripts/`, look for the
`detect_workspace.py` script relative to the SKILL.md location of this plugin
(e.g., under `.remote-plugins/` or `.local-plugins/` in Cowork).

Interpret the JSON output:

- If `vnext.found` and `kb.found` are both `false`: stop after a graceful
  message. Explain that no KB/Wiki vNext or KB-lifecycle artifacts were found
  and that the user can install the relevant package if they want
  session-boundary infrastructure.
- If `vnext.found` is `true`: run the vNext startup path first and do not run
  classic KB startup unless the user explicitly asks for classic `.kb/`
  lifecycle context.
- If only one subsystem is found: run only that subsystem.

## Step 2: KB/Wiki vNext startup (only if `vnext.found == true`)

Use the vNext thin bootstrap contract. It supersedes classic KB startup for
default session orientation because `.kb-next/memory/NOW.md` is the only
default read.

1. If the detector reports `runtime_ref`, run
   `python <runtime_ref> session-start --json`.
2. If `runtime_ref` is absent, resolve the runtime in this order and use the
   first runnable path: `.kb-next/runtime/kb_next.py`, an installed client-plugin
   path matching `**/kb-wiki-vnext/runtime/kb_next.py` (the engine ships with
   the kb-wiki-vnext plugin; this session-gate plugin carries no runtime), then
   `core/versions/kb-wiki-vnext/runtime/kb_next.py` in the authoring monorepo.
3. Read only `.kb-next/memory/NOW.md`.
4. Stop. HOT, INDEX, wiki pages, and historical artifacts remain on demand.

If no vNext runtime resolves, invoke the installed namespaced
`/kb-wiki-vnext:vnext-session-start` plugin command when the client exposes it;
do not treat `vnext-session-start` as a shell/PATH executable. If neither
surface is available, run the classic lifecycle fallback
`python .kb/kb.py lifecycle session-start --json` when present, read
`.kb-next/memory/NOW.md` directly, and report degraded data-only vNext mode.

## Step 3: KB-lifecycle startup (only if `kb.found == true` and `vnext.found == false`)

Use thin bootstrap by default. Load richer context only when the conversation
demands it.

Thin bootstrap (default):

1. `python .kb/kb.py lifecycle session-start --json`
2. Read `.kb/memory/NOW.md`
3. Stop. HOT, INDEX, pending, and wiki surfaces are available on demand.

Standard bootstrap (when the active working set is clearly needed):

1. `python .kb/kb.py lifecycle session-start --json`
2. Read `.kb/memory/NOW.md`
3. Read `.kb/memory/HOT.md`
4. Run `python .kb/kb.py pending` if needed

If shell execution is unavailable, fall back to reading `NOW.md` directly and
explicitly say that the lifecycle command was deferred. Load `HOT.md` and
`INDEX.md` only if the conversation needs them.

## Step 4: Present the briefing

Produce a structured briefing with sections only for the subsystems that were
actually detected.

Recommended structure:

- `Workspace detected`
- `vNext state` only if vNext was detected
- `KB state` only if KB was detected
- `Suggested next action`

Output rules:

- For KB-only workspaces, the briefing must stay KB-only.
- For vNext workspaces, the briefing must name the explicit
  `vnext-session-start` command and must not imply generic `/session-start`
  routing.
- For empty workspaces, do not fabricate memory or records.
- Suggested actions should prefer verified pending items, not assumptions.
