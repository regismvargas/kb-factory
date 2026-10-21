# KB/Wiki vNext Agent Instructions

Use this package only for projects that have a `.kb-next/` runtime line or are
explicitly piloting KB/Wiki vNext.

Session start is thin:

- Invoke the explicit vNext `vnext-session-start` plugin/slash command when
  the client exposes it. When working in a shell, resolve the runtime —
  `.kb-next/runtime/kb_next.py`, else the plugin-bundled `runtime/kb_next.py`,
  else `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
  monorepo) — and run `python <resolved-runtime-path> session-start --json`;
  if no runtime resolves, fall back to classic
  `python .kb/kb.py lifecycle session-start --json`.
- Runtime `session-start` does not write canonical `.kb/`, but appends session
  evidence to `.kb-next/operations.jsonl`.
- Read only `.kb-next/memory/NOW.md` by default.
- Load `.kb/memory/HOT.md`, `.kb/memory/INDEX.md`, wiki pages, and historical
  artifacts only on demand.
- Use targeted `lookup` or `semantic-lookup` before opening broad memory;
  `--domain` scopes both.
- `lookup` ORs the words of a query, so widen it with the words a record might
  use instead: the original words first, at most six words in total, synonyms
  in the language of the records before translations, and no broad words when
  you want one item or the most recent one.
- When KB + Wiki is active, `session-start` reports `wiki.status` and the
  `wiki_drafts` backlog. `classic_wiki_off` means the classic wiki must be
  re-synced with `activation-wizard --choice kb-wiki`; pending drafts go
  through the `vnext-wiki-drafts` command.
- For any planning or execution of vNext development until vNext is 100% developed,
  run runtime `compliance-preflight` after thin vNext session-start and before
  planning or editing. Simple operational use does not require the development
  preflight unless it is part of a development round.

Subagents (`spawn_agent`) start without the KB, and only the main agent writes
it. Codex has no hook that adds this for you:

- Before spawning, run
  `python <resolved-runtime-path> lookup --facet status --query "<words>" --limit 8 --json`
  with a widened query and paste the records that bear on the subtask into the
  brief under `KB records` (id, title, excerpt, source), or `none found`. Leave
  it out only when the brief isolates the subagent on purpose.
- The brief says: do not write to the KB; a shell may run the same `lookup`,
  which changes no record and appends one line to `.kb-next/operations.jsonl`;
  end the report with `KB candidates` (each fact, decision or learning with
  its source, or `none`).
- Turn each kept candidate into
  `python <resolved-runtime-path> filing-proposal --input @candidate.json --category FATO --domain <domain> --json`
  (`DECISAO` or `APRENDIZADO` as fits) and note why you drop the others;
  `vnext-session-end` lists candidates left with neither.

Governance boundaries:

- `.kb/` is canonical durable memory.
- `.kb-next/` stores vNext proposals, manifests, draft wiki pages, materialized
  vNext wiki surfaces, and operations evidence.
- Do not write SQL or edit `.kb/kb.db` directly.
- Do not publish vNext drafts to `.kb/wiki/live`; the classic runtime owns that
  directory and refreshes it on lifecycle events.
- Canonical record changes go through a proposal (`filing-proposal`, or
  `semantic-hygiene --write-proposals` for HOT demotion and open items) and
  then vNext `proposal-apply`, which itself calls the classic runtime and
  requires `--actor` (who approved; defaults to `proposal_apply.default_actor`
  when the vNext config sets it) and `--actor-runtime`. Do not run
  `.kb/kb.py create`, `file`, `supersede` or `update` yourself; the plugin's
  PreToolUse hook denies them in a vNext project once Codex trusts it.
- HOT overflow governance must start read-only. Use
  `python .kb/kb.py hygiene-audit --json` for mechanical health and
  `semantic-hygiene --write-proposals` only for
  `.kb-next` proposal evidence; do not auto-demote based on LLM judgment alone.
