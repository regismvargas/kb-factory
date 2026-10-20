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
   when external LLM judgment is available; add `--domain` to scope either.
   If `session-start` reports `wiki.status` = `classic_wiki_off`, recommend
   re-running `activation-wizard --choice kb-wiki`; if it reports pending
   `wiki_drafts`, point to the `vnext-wiki-drafts` command.
5. Widen a `lookup` query with the words a record might use instead.
   `lookup` ORs the words of a query, matches words of three or more letters
   as prefixes, and ranks records that match more words first. Keep the
   original words first and use at most six words in total. Add first the
   synonyms a record would use in the language the records are written in,
   less obvious ones included; add translations only with words to spare.
   When the question asks for one item or the most recent one, leave out
   broad words that many records share, or also run the original query alone.
6. For any planning or execution of vNext development until vNext is 100% developed,
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
- Do not publish vNext wiki drafts to `.kb/wiki/live`; the classic runtime
  generates that directory from records.
- New projects get their classic `.kb/` from `install-classic`, never from a
  hand-copied template.
- Apply durable changes only through `proposal-apply` with explicit approval or
  through the classic `.kb/kb.py` runtime.
- `proposal-apply` requires `--actor <id>` and `--actor-runtime
  <claude-code|codex|cowork|human>`. `--actor` is the person who approved the
  proposal; ask when it is unknown and never invent or reuse one from docs.
  When `.kb-next/kb-next.config.json` sets `proposal_apply.default_actor`,
  omit `--actor` for an approval by that person: the runtime records the
  configured id with `actor_source: config`. Pass `--actor` when someone else
  approves. Never write that key yourself unless the user names the id.
  `--actor-runtime` is the runtime that runs the apply (`claude-code`,
  `codex` or `cowork` for an agent). Proposal commands accept the same pair
  as an option to record who generated the proposal.
- For HOT overflow or memory hygiene, prefer read-only `hygiene-audit` first;
  use `semantic-hygiene --write-proposals` only for governed `.kb-next`
  proposals, not automatic demotion.

## Review Checklist

- Confirm `compliance-preflight` has mapped PRD/master plan, gates,
  traceability, tests, evidence, and blockers for development work.
- Simple operational use is exempt unless it is part of a development round.
- Verify LLM manifests, proposal hashes, draft hashes, confidence, provenance,
  stale/conflict warnings, and derived-authority markers.
- Verify each proposal-apply manifest and its `operations.jsonl` entry name
  the approving actor.
- Verify hygiene proposals preserve the grouped outputs `keep_hot`,
  `demote_candidate`, `supersede_or_merge_candidate`, `resolve_candidate`, and
  `needs_sponsor`; only approved `demote_hot` and `resolve` may apply.
- Confirm packaging names include `vnext` and do not collide with classic
  package names or generic command basenames.
- Record evidence in run artifacts before claiming release compliance.
