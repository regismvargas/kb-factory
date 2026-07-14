---
name: session-gate
description: >
  Thin session-boundary wrapper for Cowork workspaces that may use KB-lifecycle,
  a companion workflow plugin, or both. Use for explicit startup/closeout
  requests such as "iniciar sessao", "session start", "encerrar sessao", or
  "wrap up". This skill only detects which canonical surfaces apply and points
  the agent to them. It is an operational workaround for Cowork's missing
  automatic plugin hooks, not a replacement for mechanical enforcement or
  guaranteed trigger.
---

# Session Gate

Single entry point for session boundaries in Cowork. This wrapper is
intentionally thin: it detects whether the workspace uses KB-lifecycle, a
companion workflow plugin, or both, then calls the canonical surfaces that
already exist in those systems.

## Why this exists

Cowork does not mechanically fire plugin hooks at session start. That means the
operator may need explicit Session Gate commands even when the project already
ships KB-lifecycle and a companion workflow plugin. `session-gate` is a workaround for that
operational gap. The distributed command names are intentionally explicit
(`gate-session-start` and `gate-session-end`) so they do not collide with
vNext or classic KB lifecycle session commands.

## What this does

- Detects whether `.kb/` is present
- Detects whether `.kb-next/` is present and routes startup to vNext first
- Detects whether companion workflow artifacts are present
- Points startup to the canonical KB lifecycle commands and workflow references
- Points closeout to the canonical KB lifecycle commands and workflow `/handoff`

## What this does not do

- It does not guarantee automatic trigger in Cowork
- It does not replace mechanical hooks in Claude Code CLI
- It does not create a second memory layer
- It does not duplicate role-boundary canon, handoff canon, or KB canon
- It does not perform semantic HOT demotion; route HOT overflow review to
  `hygiene-audit` and vNext proposals when available

## Anti-patterns (do not introduce)

- Do not bootstrap `.kb/` or companion workflow directories
- Do not create or update `companion_state.json`
- Do not ship `kb_stub.py` or any KB runtime partial
- Do not hardcode ALLOW/BLOCK path lists — read them from `role-boundaries.md`
- Do not create `config.yaml` — the canonical config is `kb.config.json`
- In an empty workspace, do not fabricate bootstrap without user confirmation

## Operating rules

1. Treat trigger as probabilistic.
   The skill description may help Cowork pick it, but that is not a guarantee.

2. Treat compliance as instructional.
   If the skill is invoked, it can improve consistency. It still depends on the
   agent following the instructions.

3. Treat enforcement as mechanical only where canon already provides it.
   `session-gate` does not add mechanical write blocking.

4. If a subsystem is absent, do not mention it.
   No companion workflow in KB-only workspaces. No role boundaries,
   ALLOW/BLOCK, handoffs, or companion workflow artifacts unless the companion
   workflow was actually detected.

5. Do not restate canon that already belongs elsewhere.
   Read canonical references at runtime and point to them instead of copying
   large rules into this wrapper.

## Commands

- Use the `gate-session-start` plugin/slash command before substantive work
  begins when Session Gate is the intended wrapper.
- Use the `gate-session-end` plugin/slash command before the session closes or
  compacts.
- Invoke the `vnext-session-start` plugin/slash command directly for KB/Wiki
  vNext sessions when Session Gate is not needed; in shell contexts, run the
  vNext runtime Python `session-start` command instead.

## Design intent

This wrapper should remain a thin adapter around:

- the vNext runtime `kb_next.py session-start --json`, resolved from
  `.kb-next/runtime/kb_next.py`, else
  `core/versions/kb-wiki-vnext/runtime/kb_next.py`
- `python .kb/kb.py lifecycle session-start --json`
- `python .kb/kb.py lifecycle session-end --json`
- the companion workflow plugin's `role-boundaries.md`
- the companion workflow plugin's `/handoff`

If the wrapper starts carrying its own copy of those rules, it has drifted.
