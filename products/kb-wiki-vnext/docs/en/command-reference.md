# KB/Wiki vNext Command Reference

Use explicit command names. Do not use generic `/session-start` or
`/session-end` aliases for vNext or Session Gate packages.

Runtime paths are resolved separately from plugin command names. For normal
shell sessions use `./.kb-next/runtime/kb_next.py`; if absent, resolve the
plugin-bundled `runtime/kb_next.py` and run `bootstrap`. Use the authoring
`core/versions/...` path only inside KB Factory.

The table below uses **logical basenames**, not one literal invocation for all
clients:

| Client | Startup invocation |
|---|---|
| Claude Code | `/kb-wiki-vnext:vnext-session-start` |
| Codex | invoke the embedded `kb-wiki-vnext` skill in natural language; use the runtime fallback when needed |
| Claude Cowork | use the namespaced action exposed by the installed plugin UI, or invoke the skill in natural language; use the runtime fallback when commands are not exposed |

Do not promise a bare slash command such as `/vnext-session-start` across
clients. Session Gate follows the same distinction with the logical basename
`gate-session-start`.

| Command | Project type | Platforms | Runtime or instruction | Mutation behavior |
|---|---|---|---|---|
| `vnext-session-start` | general vNext session | Codex, Claude Code, Claude Cowork | `python ./.kb-next/runtime/kb_next.py session-start --json` after bootstrap | no canonical write; appends read telemetry to the git-ignored `.kb-next/telemetry/events.jsonl` |
| `vnext-session-end` | general vNext session | Codex, Claude Code, Claude Cowork | summarize vNext evidence; collect subagent `KB candidates`; run `python .kb/kb.py lifecycle session-end` and, with KB + Wiki, the runtime `wiki-draft-status`; refresh the dense index when `retrieval.dense.enabled` is on and records changed; curation: read-only `hygiene-audit` and `semantic-hygiene`, then a judged batch within `review_budget` | classic session-end refreshes exports and the enabled wiki; filing and hygiene proposals go to `.kb-next/` only; no canonical record write |
| `vnext-wiki-drafts` | KB + Wiki session | Codex, Claude Code, Claude Cowork | `wiki-draft-status`, then per topic `wiki-synthesis-plan` with agent judgment and `wiki-draft-review --materialize` | writes `.kb-next/wiki/` drafts, manifests and pages; no canonical write |
| `existing-project-diagnose` | existing/legacy | Codex, Claude Code, Claude Cowork | inspect `.kb/`, `.kb-next/`, runtime, and `NOW.md` | no canonical write; appends read telemetry if it runs `session-start` |
| `existing-project-activate-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` by default | writes `.kb-next/`; with `kb-wiki` also enables the classic wiki keys in `.kb/kb.config.json` and syncs `.kb/wiki/live` |
| `existing-project-configure-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | short or guided `activation-wizard` (merges the existing config) | writes `.kb-next/`; `kb-wiki` enables and syncs the classic wiki; `kb-alone` keeps it unless `--disable-classic-wiki` |
| `existing-project-verify-install` | existing/legacy | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends read telemetry to the git-ignored `.kb-next/telemetry/events.jsonl` |
| `existing-project-upgrade-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from replacement artifact, `upgrade-classic`, re-apply the recorded mode, verify | workspace runtimes, classic engine files and classic wiki keys; no canonical record write |
| `existing-project-rollback-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from restored artifact and verify prior version | package/workspace runtime plus operational evidence; no canonical write |
| `new-project-wizard` | new project | Codex, Claude Code, Claude Cowork | ask for title, slug and domains, then choose the init mode | creates `.kb/` (through `install-classic`) and `.kb-next/` when absent |
| `new-project-init-kb-alone` | new project | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-alone` | creates `.kb/` when absent and configures `.kb-next/` |
| `new-project-init-kb-wiki` | new project | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-wiki` | creates `.kb/` when absent and `.kb-next/`; `--scope` files the user's scope as one HOT `DECISAO`; the classic wiki stays dormant until 10 active records cite a registered source (`--wiki-min-sourced-records`, `0` for at once), then publishes `.kb/wiki/live` by itself; vNext drafts are never copied there |
| `new-project-verify-install` | new project | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends read telemetry to the git-ignored `.kb-next/telemetry/events.jsonl` |
| `gate-session-start` | Session Gate | Codex, Claude Code, Claude Cowork | detect `.kb-next/` and `.kb/`; route vNext first | no canonical write; vNext route appends read telemetry to `.kb-next/telemetry/events.jsonl` |
| `gate-session-end` | Session Gate | Codex, Claude Code, Claude Cowork | detect systems and summarize closeout; a full maintenance pass runs `scheduled-maintenance --apply-demotions` only in a classic-only workspace and the vNext curation step in a vNext workspace | no canonical write by default; vNext curation writes `.kb-next/` hygiene proposals only |

Runtime-only commands:

| Subcommand | Purpose | Mutation behavior |
|---|---|---|
| `bootstrap` | atomically install the executing artifact runtime at `<project>/.kb-next/runtime/kb_next.py` | replaces byte drift, reports source/installed SHA-256, rejects unsafe targets; `action: self` is not upgrade proof |
| `install-classic` | copy the classic scaffold (kb-lifecycle plugin, stand-alone bundle, authoring repo or `--template`) into `.kb/` and run classic `init --name --slug --domains` | creates `.kb/`; refuses an existing or non-empty `.kb/` |
| `upgrade-classic` | refresh only `.kb/kb.py` and `.kb/runtime/*.py` from the discovered scaffold | engine files only; never `kb.db`, data or `kb.config.json` |
| `wiki-draft-status` | list wiki topics that need synthesis, review or refresh | read-only |
| `session-hint` | SessionStart hook text for vNext workspaces | read-only; prints nothing outside vNext workspaces |
| `subagent-hint` | SubagentStart hook JSON for vNext workspaces: the subagent KB contract and a lookup command | read-only; prints nothing outside vNext workspaces |

Agent-facing runtime subcommands that changed in 0.2.x (details in
`usage-guide.md`):

| Subcommand | Purpose | Mutation behavior |
|---|---|---|
| `lookup` | ranked lookup: an FTS5 word list (BM25) fused by Reciprocal Rank Fusion; `--lists` picks from `words`, `trigram` and `dense`; the default is `words`, plus `dense` when `retrieval.dense.enabled` is `true` | no canonical write; appends read telemetry to the git-ignored `.kb-next/telemetry/events.jsonl` |
| `dense-index` | build or refresh the optional local dense index; `--fetch-model` downloads the pinned model, `--rebuild` embeds every active record again | writes `.kb-next/index/` and one telemetry line in `.kb-next/telemetry/events.jsonl`, both ignored by Git; needs the dense extra; reports an advisory for `potion-multilingual-128M`, which is not recommended |
| `proposal-apply` | apply an approved proposal to `.kb/`; needs `--approve`, `--approval-note`, `--actor-runtime` (`claude-code`, `codex`, `cowork` or `human`) and an approver from `--actor` or `proposal_apply.default_actor` | one of the two canonical write paths for agents in a vNext project; with no approver it exits 2 before reading the proposal |
| `approved-filing` | file one record the user approved in chat: `--category`, `--domain`, `--title`, `--content`, `--confidence`, `--source-id` or `--record-id`, optional `--supersedes`, plus `--approval-note` and the approver pair of `proposal-apply` | writes `.kb/` through `.kb/kb.py`, one manifest under `.kb-next/manifests/approved-filing/` and one oplog line; a blocked call writes nothing and exits 1 |
| `semantic-hygiene` | detect demotion, resolution and supersede candidates; with `--judgment` and `--write-proposals`, write a judged batch, including `retire` items (`replacement_id` names the existing ATIVO record that replaces the target) | writes `.kb-next/` proposals only, and only with `--write-proposals`; reports `review_budget` (`semantic_curation.weekly_hygiene_proposals`, default 5 open proposals per project per 7 days), skips targets that already have an open proposal and lists the overflow under `deferred` |

Plugin hooks, as registered in `hooks/hooks.json`. Claude Code runs all three.
Codex runs plugin hooks only after the user trusts that file and has no
subagent hook; its main agent follows the subagent protocol in `AGENTS.md`.

| Hook | Runs | Behavior |
|---|---|---|
| `SessionStart` | runtime `session-hint` | prints the vNext startup instruction in vNext workspaces |
| `SubagentStart` | runtime `subagent-hint` | gives each Claude Code subagent the no-write rule and the `KB candidates` report section |
| `PreToolUse` on shell calls | `scripts/write_gate.py` | denies `.kb/kb.py create`, `file`, `supersede`, `update`, `resolve`, `bulk-import`, `init --seed`, `raw-query --allow-write`, `lifecycle scheduled-maintenance` and `--apply-demotions` or `--apply-cold-demotions` in a vNext project and points to `approved-filing`, `filing-proposal`, `semantic-hygiene` and `proposal-apply`; `"write_gate": {"enabled": false}` in `.kb-next/kb-next.config.json` turns it off |

Classic `.kb/` remains canonical durable memory. `.kb-next/` remains governed
proposal, evidence, draft, materialization, and operations state.
