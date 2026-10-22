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
   `wiki_drafts`, point to the `vnext-wiki-drafts` command. `dormant` means a
   new KB + Wiki waits for `wiki.dormant.min_sourced_records` records that
   cite a source; work as in KB alone, nothing to do for the wiki.
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

## Subagents

A subagent (Claude Code `Agent` tool, Codex `spawn_agent`) starts without the
KB. The main agent stays its only writer.

1. Before launching one, run `lookup` for the subtask with a widened query
   (step 5):
   `python <resolved-runtime-path> lookup --facet status --query "<words>" --limit 8 --json`.
   Paste the records that bear on the subtask into the brief under a
   `KB records` heading, one line each: id, title, excerpt and source. Write
   `none found` when nothing fits, so the subagent does not repeat the search.
   Leave the section out only when the brief isolates the subagent on purpose
   (blind grading, held-out authoring, no-tool tasks).
2. Say in the brief that the subagent must not write to the KB, and that its
   report ends with a `KB candidates` section: each fact, decision or learning
   worth keeping, one line each with its source (file and line, command, URL
   or person), or `none`.
3. A subagent with a shell may run the same `lookup` itself. It does not
   change `.kb/`; it appends one line to `.kb-next/telemetry/events.jsonl`. No other
   KB command runs in a subagent: not `filing-proposal`, not `proposal-apply`,
   not a `.kb/kb.py` command that changes records.
4. When the report comes back, show the user the candidates you keep. File
   the ones the user approves in chat with `approved-filing` (Boundaries
   below); turn the rest into proposals, with `candidate.json` holding
   `title`, `content` and `source`:
   `python <resolved-runtime-path> filing-proposal --input @candidate.json --category FATO --domain <domain> --json`
   (`DECISAO` for a decision, `APRENDIZADO` for a learning). Note a reason for
   each candidate you drop. `vnext-session-end` lists candidates left with
   none of the three.
5. In Claude Code the plugin's `SubagentStart` hook (runtime `subagent-hint`)
   shows rules 2 and 3 and the lookup command to every subagent in a vNext
   workspace. It is a backstop, not a substitute: subagents follow it less
   reliably than the brief, so the brief still states rules 2 and 3. Its rules
   yield to a brief that forbids commands or fixes the output format, so an
   isolated brief should say so in words. The hook cannot see the brief and
   adds no records; picking them is rule 1. Codex has no such hook.

## Boundaries

- Treat `.kb/` records as canonical durable memory.
- Treat `.kb-next/` as proposal, manifest, draft, materialization, package, and
  operations evidence.
- `session-start` and `lookup` do not write canonical `.kb/`; they append read
  telemetry to the git-ignored `.kb-next/telemetry/events.jsonl`.
- Do not write SQL or edit `.kb/kb.db` directly.
- Do not publish vNext wiki drafts to `.kb/wiki/live`; the classic runtime
  generates that directory from records.
- New projects get their classic `.kb/` from `install-classic`, never from a
  hand-copied template.
- Change canonical records only after the approver says yes. Do not run
  `.kb/kb.py create`, `file`, `supersede` or `update` yourself. In Claude Code
  the plugin's PreToolUse hook denies them in a vNext project and names the
  vNext commands (Codex runs the same hook once it is trusted); the rule holds
  where the hook does not run.
- When the user approves a record in chat (title, content, category,
  confidence and backing shown first), file it in one call:
  `python <resolved-runtime-path> approved-filing --category DECISAO --domain <domain> --title "<title>" --content "<content>" --confidence 0.9 --source-id <SRC id> --approval-note "<who approved, where, their words>" --actor-runtime claude-code --json`
  (`FATO`, `PREMISSA`, `PENDENCIA` or `APRENDIZADO` as fits; the confidence
  you showed the user, at least 0.8; `--record-id <id>` instead of or
  besides `--source-id` when an existing
  record backs it; `--supersedes <id>` to replace a record, which may change
  its category; `--valid-until none` clears a superseded date). It writes one
  file under `.kb-next/manifests/approved-filing/` and one oplog line, and
  exits 1 without writing anything when provenance, confidence, the
  supersede target or an active record with the same title blocks it.
- Otherwise, for an approval that comes later or from someone else, write a
  proposal. A new record or a content change starts with
  `python <resolved-runtime-path> filing-proposal --input @candidate.json --category <CATEGORY> --domain <domain> --judgment @judgment.json --json`
  (`judgment.json` holds `action` `new` or `supersede`, a `record_draft` with
  `category`, `domain`, `title` and `content`, plus `supersedes_id` for a
  supersede, `confidence`, `rationale` and `provenance` as a list of
  `{"record_id": "<existing id>"}` or `{"source_id": "<SRC id>"}`). A file
  path or URL is not provenance: register a file first with
  `python .kb/kb.py ingest <path> --json` and cite its `source_id`. A HOT
  demotion or a resolved open item starts with `semantic-hygiene` (see
  Curation below). Then
  `python <resolved-runtime-path> proposal-apply --proposal <proposal_id> --approve --approval-note "<who approved and why>" --actor-runtime claude-code --json`
  applies it (`--actor-runtime codex` or `cowork` in those clients, `--actor`
  as the next rule says). A metadata-only edit
  (tags, confidence, review dates) has no proposal path: give the user the
  command to run in their own terminal.
- `proposal-apply` and `approved-filing` require `--actor <id>` and
  `--actor-runtime <claude-code|codex|cowork|human>`. `--actor` is the person who approved the
  proposal; ask when it is unknown and never invent or reuse one from docs.
  When `.kb-next/kb-next.config.json` sets `proposal_apply.default_actor`,
  omit `--actor` for an approval by that person: the runtime records the
  configured id with `actor_source: config`. Pass `--actor` when someone else
  approves. Never write that key yourself unless the user names the id.
  `--actor-runtime` is the runtime that runs the apply (`claude-code`,
  `codex` or `cowork` for an agent). Proposal commands accept the same pair
  as an option to record who generated the proposal.
- For HOT overflow or memory hygiene, follow Curation below: read-only
  detection first, then governed `.kb-next` proposals, never automatic
  demotion.

## Curation

Detection runs by itself; corrections are proposals the user approves.

1. At every session end (`vnext-session-end`) and in the weekly maintenance
   run, detect with `python .kb/kb.py hygiene-audit --json` and
   `python <resolved-runtime-path> semantic-hygiene --json`. Neither changes
   `.kb/` or writes a proposal.
2. When `review_budget.room` is above zero, classify at most that many
   candidates that are not in `review_budget.open`, taken from the records
   `semantic-hygiene` returned (it drops others), and write the batch with
   `python <resolved-runtime-path> semantic-hygiene --judgment @hygiene-judgment.json --write-proposals --json`.
   Per project the runtime keeps at most
   `semantic_curation.weekly_hygiene_proposals` (default 5) valid hygiene
   proposals open over 7 days, skips a target that already has one and lists
   the rest under `deferred`.
3. Never apply in the detection step. In the weekly review, show each open
   proposal (target, action, rationale) and apply only the ones the user
   approves with
   `python <resolved-runtime-path> proposal-apply --proposal <proposal_id> --approve --approval-note "<who approved and why>" --actor-runtime claude-code --json`,
   with `--actor-runtime codex` or `cowork` in those clients and
   `--actor <id>` unless `proposal_apply.default_actor` names the approver.
   A proposal leaves the queue when it is applied, when its target changed by
   other means, or after 7 days; detection may then propose it again.
4. The weekly maintenance run is an agent session (a scheduled Claude Code or
   Codex task in the project), because step 2 needs judgment; a plain
   scheduler can only run step 1. In a vNext project it uses
   `python .kb/kb.py lifecycle session-end --json` for exports and the wiki,
   not `lifecycle scheduled-maintenance`, whose default config demotes stale
   HOT records without a proposal.

## Review Checklist

- Confirm `compliance-preflight` has mapped PRD/master plan, gates,
  traceability, tests, evidence, and blockers for development work.
- Simple operational use is exempt unless it is part of a development round.
- Verify LLM manifests, proposal hashes, draft hashes, confidence, provenance,
  stale/conflict warnings, and derived-authority markers.
- Verify each proposal-apply and approved-filing manifest and its
  `operations.jsonl` entry name the approving actor.
- Verify hygiene proposals preserve the grouped outputs `keep_hot`,
  `demote_candidate`, `supersede_or_merge_candidate`, `resolve_candidate`, and
  `needs_sponsor`; only approved `demote_hot` and `resolve` may apply.
- Confirm packaging names include `vnext` and do not collide with classic
  package names or generic command basenames.
- Record evidence in run artifacts before claiming release compliance.
