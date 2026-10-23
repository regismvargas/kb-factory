---
description: Close a KB/Wiki vNext session with governed operational evidence.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Close a KB/Wiki vNext session: one call in KB alone, two with an active wiki.

Use this explicit command instead of a generic `/session-end` alias so vNext,
Session Gate, and classic KB lifecycle commands cannot collide.

1. Only if subagents ran in the session: collect the `KB candidates` sections
   of their reports. Each candidate needs an `approved-filing` or a
   `filing-proposal` from this session, or a noted reason to drop it. List
   the ones with none and offer to file the ones the user approves now with
   `approved-filing`, or to prepare proposals with
   `python <resolved-runtime-path> filing-proposal --input @candidate.json --category FATO --domain <domain> --json`
   (`DECISAO` or `APRENDIZADO` as fits; `candidate.json` holds `title`,
   `content` and `source`). Preparing a proposal writes only `.kb-next/`.
   File every record the user approves before step 2.
2. If `.kb/kb.py` exists, run `python .kb/kb.py lifecycle session-end --json`
   once, after those filings. It refreshes exports and, when the classic wiki
   is enabled, syncs `.kb/wiki/live`. Report `wiki_sync.written_count` and any
   `held_back` pages. When its `audit` shows `hot_over_limit`, `stale_hot` or
   `expired_premises`, say so and leave them to the weekly maintenance run.
3. Only if KB + Wiki is active and not dormant (the session hook's `Wiki:`
   line, or the runtime `session-start` `wiki.status`), run
   `python <resolved-runtime-path> wiki-draft-status --json`. When any topic
   is `needs_synthesis`, `needs_review` or `stale`, offer to run the
   `vnext-wiki-drafts` command now or list the topics for the next session.

`<resolved-runtime-path>` is the runtime the session hook printed (its
`Commands` lines). Without the hook, use the first that exists:
`.kb-next/runtime/kb_next.py`, then `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`.

Rules:

- Do not write durable memory unless the user approved canonical KB changes.
  A record the user approves in chat takes one `approved-filing` call (see
  the kb-wiki-vnext skill); a canonical KB update approved as a proposal
  takes `proposal-apply`. Both need `--actor` set to the person who approved
  (ask if unknown; omit it only when that person is the
  `proposal_apply.default_actor` of the vNext config) and `--actor-runtime`
  set to this runtime. Do not run `.kb/kb.py create`, `file`, `supersede`,
  `update`, `resolve` or `bulk-import` (the plugin's write gate denies them).
- Curation (`hygiene-audit`, `semantic-hygiene` and its judged proposals)
  runs in the weekly maintenance run, not at session end; see the Curation
  section of the kb-wiki-vnext skill. Run it here only when the user asks,
  and never apply its proposals at session end.
- Do not run `python .kb/kb.py lifecycle scheduled-maintenance` here; its
  default config demotes stale HOT records without a proposal, and the write
  gate denies it in a vNext project.
- If `retrieval.dense.enabled` is `true` in `.kb-next/kb-next.config.json`
  and records were filed or edited in the session, refresh the dense index
  with `python <resolved-runtime-path> dense-index --json` (it embeds only new
  or changed records; off by default, so no call).
