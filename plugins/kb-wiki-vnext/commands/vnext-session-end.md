---
description: Close a KB/Wiki vNext session with governed operational evidence.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Close a KB/Wiki vNext session by recording only useful operational evidence.

Use this explicit command instead of a generic `/session-end` alias so vNext,
Session Gate, and classic KB lifecycle commands cannot collide.

1. Summarize vNext manifests, proposals, package checks, tests, or pilot
   evidence touched in the session.
2. If subagents ran in the session, collect the `KB candidates` sections of
   their reports. Each candidate needs an `approved-filing` or a
   `filing-proposal` from this session, or a noted reason to drop it. List
   the ones with none and offer to file the ones the user approves now with
   `approved-filing` (step 4), or to prepare proposals (resolve the runtime as
   in step 6) with
   `python <resolved-runtime-path> filing-proposal --input @candidate.json --category FATO --domain <domain> --json`
   (`DECISAO` or `APRENDIZADO` as fits; `candidate.json` holds `title`,
   `content` and `source`). Preparing a proposal writes only `.kb-next/`.
3. Do not write durable memory unless the user approved canonical KB changes.
4. If the user approves a record in chat, file it with one
   `approved-filing` call (see the kb-wiki-vnext skill); if a canonical KB
   update was approved as a proposal, apply it with `proposal-apply`. Do not
   run `.kb/kb.py create`, `file`, `supersede` or `update` (the plugin's write
   gate denies them). Both commands need `--actor` set to the person
   who approved (ask if unknown; omit it only when that person is the
   `proposal_apply.default_actor` of the vNext config) and `--actor-runtime`
   set to this runtime.
5. If `.kb/kb.py` exists, run `python .kb/kb.py lifecycle session-end --json`.
   It refreshes exports and, when the classic wiki is enabled, syncs
   `.kb/wiki/live`. Report `wiki_sync.written_count` and any `held_back`
   pages.
6. If KB + Wiki is active and not dormant (`session-start` `wiki.status`), resolve the vNext runtime (`.kb-next/runtime/kb_next.py`,
   then `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`) and run
   `python <resolved-runtime-path> wiki-draft-status --json`. When any topic
   is `needs_synthesis`, `needs_review` or `stale`, offer to run the
   `vnext-wiki-drafts` command now or list the topics for the next session.
7. If `retrieval.dense.enabled` is `true` in `.kb-next/kb-next.config.json`
   and records were filed or edited in the session, refresh the dense index
   with `python <resolved-runtime-path> dense-index --json` (it embeds only
   new or changed records). If it fails for a missing extra or model, report
   the message; lookup still ranks by words.
8. Curation. Run the read-only detection `python .kb/kb.py hygiene-audit --json`
   and `python <resolved-runtime-path> semantic-hygiene --json`, and report
   the candidates per group and `review_budget` (`open_count`, `room`,
   `weekly_limit`). When `room` is above zero and candidates remain outside
   `review_budget.open`, classify at most `room` of them (only records that
   `semantic-hygiene` returned; it drops others) in
   `hygiene-judgment.json`: `groups` holding `demote_candidate`,
   `resolve_candidate`, `supersede_or_merge_candidate` (with a
   `record_draft`) or `needs_sponsor` items, each with `record_id`,
   `rationale` and `confidence`, plus a top-level `rationale`, `confidence`,
   `provenance` (a list of `{"record_id": ...}`) and `conflicts`. Leave out a
   record that should stay as it is. Write the batch with
   `python <resolved-runtime-path> semantic-hygiene --judgment @hygiene-judgment.json --write-proposals --json`;
   it writes only `.kb-next/`, skips targets that already have an open
   proposal and lists the overflow under `deferred`. Do not apply these
   proposals at session end: list their ids for the user's weekly review.
   Do not run `python .kb/kb.py lifecycle scheduled-maintenance` here; its
   default config demotes stale HOT records without a proposal.
