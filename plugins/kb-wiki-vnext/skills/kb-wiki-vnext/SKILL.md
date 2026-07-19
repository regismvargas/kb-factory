---
name: kb-wiki-vnext
description: Use for KB/Wiki vNext sessions, targeted memory lookup, approved proposal review/apply, wiki draft review, packaging pilots, and release compliance. Start thin with NOW.md and keep classic .kb canonical.
---

# KB/Wiki vNext

Use this skill when the project has `.kb-next/`, the user mentions KB/Wiki
vNext, or a task concerns vNext proposals, manifests, wiki draft review,
semantic hygiene, HOT overflow governance, packaging, pilots, fallback, or
release gates.

## Session Contract

1. Start with the vNext `vnext-session-start` command when available. If the
   client does not expose commands, resolve the runtime in this order:
   `.kb-next/runtime/kb_next.py`,
   `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`, an installed client-plugin path
   matching `**/kb-wiki-vnext/runtime/kb_next.py`, then
   `core/versions/kb-wiki-vnext/runtime/kb_next.py` in the authoring monorepo.
   Run `python <resolved-runtime-path> session-start --json`. If no runtime
   resolves but `.kb-next/memory/NOW.md` exists, read it directly and report
   degraded data-only mode; use classic `.kb/kb.py lifecycle session-start`
   only as the lifecycle fallback, not as the vNext `NOW.md` source.
2. Read only `.kb-next/memory/NOW.md` by default.
3. Load `.kb/memory/HOT.md`, `.kb/memory/INDEX.md`, wiki pages, and historical
   artifacts only when the task needs them.
4. Use `lookup` for deterministic targeted retrieval and `semantic-lookup`
   when external LLM judgment is available.
5. For any planning or execution of vNext development until vNext is 100% developed,
   run `compliance-preflight` for the closest work type before
   planning, editing, review, packaging, rollout, or Track B work. Simple
   operational use does not require this development preflight.

## Boundaries

- Treat `.kb/` records as canonical durable memory.
- Treat `.kb-next/` as proposal, manifest, draft, materialization, package, and
  operations evidence.
- `session-start` and `lookup` do not write canonical `.kb/`, but they append
  operational evidence to `.kb-next/operations.jsonl`.
- Do not write SQL or edit `.kb/kb.db` directly.
- Do not publish vNext wiki drafts to `.kb/wiki/live`.
- Apply durable changes only through `proposal-apply` with explicit approval or
  through the classic `.kb/kb.py` runtime.
- For HOT overflow or memory hygiene, prefer read-only `hygiene-audit` first;
  use `semantic-hygiene --write-proposals` only for governed `.kb-next`
  proposals, not automatic demotion.

## Review Checklist

- Confirm `compliance-preflight` has mapped PRD/master plan, gates,
  traceability, tests, evidence, and blockers for development work.
- Simple operational use is exempt unless it is part of a development round.
- Verify LLM manifests, proposal hashes, draft hashes, confidence, provenance,
  stale/conflict warnings, and derived-authority markers.
- Verify hygiene proposals preserve the grouped outputs `keep_hot`,
  `demote_candidate`, `supersede_or_merge_candidate`, `resolve_candidate`, and
  `needs_sponsor`; only approved `demote_hot` and `resolve` may apply.
- Confirm packaging names include `vnext` and do not collide with classic
  package names or generic command basenames.
- Record evidence in CASE-compatible run artifacts before claiming release
  compliance.
