---
name: session-gate
description: >
  Thin session-boundary wrapper for Codex, Claude Code, or Cowork workspaces
  that may use KB/Wiki vNext, KB-lifecycle, or both.
  Use for explicit startup/closeout requests such as
  "iniciar sessao", "session start", "encerrar sessao", or "wrap up". This
  skill only detects which canonical surfaces apply and points the agent to
  them. Use it as an explicit fallback when session hooks are disabled,
  unavailable, or not observable, not as a replacement for mechanical
  enforcement or a guaranteed trigger.
---

# Session Gate

Single entry point for explicit cross-client session boundaries. This wrapper is
intentionally thin: it detects whether the workspace uses KB/Wiki vNext,
KB-lifecycle, or both, then calls the canonical surfaces that already exist in
those systems.

## Why this exists

Hook availability, enablement, and execution differ by client and install.
Explicit Session Gate commands provide an auditable fallback even when the
project already ships KB-lifecycle or KB/Wiki vNext. The distributed command
names are intentionally explicit (`gate-session-start` and
`gate-session-end`) so they do not collide with vNext or classic KB lifecycle
session commands.

## What this does

- Detects whether `.kb/` is present
- Detects whether `.kb-next/` is present and routes startup to vNext first
- Points startup to the canonical KB lifecycle commands
- Points closeout to the canonical KB lifecycle commands

## What this does not do

- It does not guarantee automatic trigger in any client
- It does not replace mechanical hooks in Claude Code CLI
- It does not create a second memory layer
- It does not duplicate vNext or KB canon
- It does not perform semantic HOT demotion; route HOT overflow review to
  `hygiene-audit` and vNext proposals when available

## Anti-patterns (do not introduce)

- Do not bootstrap `.kb/`
- Do not ship `kb_stub.py` or any KB runtime partial
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
   A KB-only briefing stays KB-only.

5. Do not restate canon that already belongs elsewhere.
   Read canonical references at runtime and point to them instead of copying
   large rules into this wrapper.

## Commands

- Use the `gate-session-start` plugin/slash command before substantive work begins when Session Gate is
  the intended wrapper.
- Use the `gate-session-end` plugin/slash command before the session closes or compacts.
- Use the namespaced `vnext-session-start` plugin command directly for KB/Wiki
  vNext sessions when Session Gate is not needed. Do not present it as a
  shell/PATH executable.

## Design intent

This wrapper should remain a thin adapter around:

- the resolved vNext runtime in this order: workspace
  `.kb-next/runtime/kb_next.py`, bundled/installed plugin
  `runtime/kb_next.py`, then the authoring-monorepo
  `core/versions/kb-wiki-vnext/runtime/kb_next.py`; run
  `python <resolved-runtime-path> session-start --json`
- `python .kb/kb.py lifecycle session-start --json`
- `python .kb/kb.py lifecycle session-end --json`

If the wrapper starts carrying its own copy of those rules, it has drifted.
